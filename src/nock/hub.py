"""The registry of live rooms and the tasks that run them.

The pure rules live in `nock.room`. This module owns the time and the threads:
a registry runs its rooms on its own asyncio event loop in a daemon thread, with
one task per room that applies the room's inputs one at a time.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import threading
import time
from collections.abc import Awaitable, Callable
from typing import NamedTuple

from nock.grid import Grid
from nock.protocol import (
    ClientMessage,
    ErrorCode,
    ErrorMessage,
    Join,
    Ping,
    Pong,
    Snapshot,
)
from nock.room import (
    SILENCE_CLOSE_CODE,
    Clock,
    Outcome,
    RoomConfig,
    RoomState,
    after_restart,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    tick,
    with_last_seen,
)
from nock.store import RoomStore

__all__ = [
    "MAX_FRAME_BYTES",
    "SESSION_REPLACED_CLOSE_CODE",
    "SILENCE_CLOSE_CODE",
    "RoomConnection",
    "RoomRegistry",
]

logger = logging.getLogger(__name__)

ROOM_CODE_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I
ROOM_CODE_LENGTH: int = 6

MAX_FRAME_BYTES: int = 4096  # spec 037: larger frames are not parsed
SESSION_REPLACED_CLOSE_CODE: int = 4001  # the same player opened another socket

_REFUSAL_TEXTS: dict[ErrorCode, str] = {
    ErrorCode.NOT_JOINED: "Send a join message before anything else.",
    ErrorCode.INVALID_MESSAGE: "The message is not a valid client message.",
}

_NORMAL_CLOSE_CODE = 1000
_INTERNAL_ERROR_CLOSE_CODE = 1011  # the server could not save the join
_STOP_TIMEOUT_SECONDS = 5.0


class _Message(NamedTuple):
    """Input: a client message from a joined player."""

    connection: RoomConnection
    message: ClientMessage


class _Invalid(NamedTuple):
    """Input: a frame of a connection that is not a valid client message."""

    connection: RoomConnection


class _Detach(NamedTuple):
    """Input: a connection closed."""

    connection: RoomConnection


_Input = _Message | _Invalid | _Detach


class _Outbound(NamedTuple):
    """One item of a connection's outbound queue: a text, or a close code."""

    text: str | None
    close_code: int | None


class RoomConnection:
    """One player connection, seen from the room task and from the socket.

    The outbound queue belongs to the event loop of the socket's handler. The
    room task puts items in it without waiting, so a slow socket never delays
    the room or any other connection.
    """

    def __init__(
        self,
        owner_loop: asyncio.AbstractEventLoop,
        post: Callable[[_Input], None],
    ) -> None:
        """Create a connection owned by `owner_loop`, the loop of the socket.

        `player_id` stays None until the room task accepts the connection's join.
        """
        self.player_id: str | None = None
        self._owner_loop = owner_loop
        self._post = post
        self._outbound: asyncio.Queue[_Outbound] = asyncio.Queue()

    def submit(self, message: ClientMessage) -> None:
        """Pass a message of this player to the room (any thread)."""
        self._post(_Message(self, message))

    def submit_invalid(self) -> None:
        """Tell the room that this player sent an invalid frame (any thread)."""
        self._post(_Invalid(self))

    def leave(self) -> None:
        """Tell the room that the socket closed (any thread)."""
        self._post(_Detach(self))

    def deliver_text(self, text: str) -> None:
        """Queue a message for the socket. Called by the room task."""
        self._enqueue(_Outbound(text=text, close_code=None))

    def deliver_close(self, close_code: int) -> None:
        """Queue the closing of the socket. Called by the room task."""
        self._enqueue(_Outbound(text=None, close_code=close_code))

    async def run_writer(
        self,
        send_text: Callable[[str], Awaitable[None]],
        close: Callable[[int], Awaitable[None]],
    ) -> None:
        """Write the queued items to the socket, in order, until a close.

        Must run on the event loop that owns this connection.
        """
        while True:
            item = await self._outbound.get()
            if item.text is not None:
                await send_text(item.text)
            elif item.close_code is not None:
                await close(item.close_code)
                return

    def _enqueue(self, item: _Outbound) -> None:
        """Put an item in the queue from any thread."""
        try:
            self._owner_loop.call_soon_threadsafe(self._outbound.put_nowait, item)
        except RuntimeError:
            # The socket's event loop is closed: nobody is left to read.
            return


class _RoomRunner:
    """The state of one room and the task that applies its inputs.

    Everything except `state` is only touched from the engine's event loop.
    """

    def __init__(
        self,
        state: RoomState,
        config: RoomConfig,
        clock: Clock,
        store: RoomStore,
        snapshot_seq: int | None,
    ) -> None:
        """Create a runner with no task yet; the first connection starts it.

        Args:
            state: The room.
            config: Thresholds of the rooms.
            clock: Seconds since the epoch.
            store: Where the steps of the room are written.
            snapshot_seq: Seq of the newest snapshot the store holds for the
                room, None when that is not known.
        """
        self.state = state
        self._config = config
        self._clock = clock
        self._connections: list[RoomConnection] = []
        self._inbox: asyncio.Queue[_Input] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._is_closed = False
        self._store = store
        self._snapshot_seq = snapshot_seq
        self._events_since_snapshot = 0

    def post(self, item: _Input) -> None:
        """Add an input to the inbox, starting the task if it is not running.

        Once the runner is cancelled, inputs are refused and no task starts.
        """
        if self._is_closed:
            return
        self._inbox.put_nowait(item)
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run())

    async def cancel(self) -> None:
        """Refuse further inputs, stop the task and wait until it is over."""
        self._is_closed = True
        task = self._task
        if task is None:
            return
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    def save_snapshot(self) -> None:
        """Save a snapshot of the room unless the store has one at this seq.

        A failure is logged: the log alone is enough to rebuild the room.
        """
        if self._snapshot_seq == self.state.seq:
            return
        try:
            self._store.save_snapshot(self.state)
        except Exception:
            logger.exception("The snapshot of room %s failed", self.state.code)
            return
        self._snapshot_seq = self.state.seq
        self._events_since_snapshot = 0

    async def _run(self) -> None:
        """Apply the inputs and the ticks until no connection is left.

        A snapshot is saved when the task stops, however it stops.
        """
        try:
            await self._apply_inputs()
        finally:
            self.save_snapshot()

    async def _apply_inputs(self) -> None:
        """Apply the inputs and the ticks until no connection is left."""
        loop = asyncio.get_running_loop()
        # Time-outs that fell due while the room had no task apply first.
        self._tick_step()
        next_tick = loop.time() + self._config.tick_seconds
        while True:
            wait_seconds = next_tick - loop.time()
            if wait_seconds <= 0:
                self._tick_step()
                next_tick = loop.time() + self._config.tick_seconds
                continue
            try:
                item = await asyncio.wait_for(self._inbox.get(), wait_seconds)
            except TimeoutError:
                continue
            self._input_step(item)
            if not self._connections and self._inbox.empty():
                return

    def _tick_step(self) -> None:
        """Run one tick of the rules."""
        joined = list(self._connections)
        try:
            outcome = tick(self.state, self._clock(), self._config)
        except Exception:
            logger.exception("The tick of room %s failed", self.state.code)
            return
        self._store_and_deliver(outcome, None, joined)

    def _input_step(self, item: _Input) -> None:
        """Run the step that one input asks for."""
        if isinstance(item, _Detach):
            self._detach_step(item.connection)
            return
        if isinstance(item, _Invalid):
            self._note_frame_seen(item.connection)
            self._refuse(item.connection, ErrorCode.INVALID_MESSAGE)
            return
        if item.connection.player_id is None:
            self._unjoined_step(item.connection, item.message)
            return
        if isinstance(item.message, Join):
            self._note_frame_seen(item.connection)
            return
        if item.connection not in self._connections:
            return  # replaced by a newer socket of the same player
        joined = list(self._connections)
        try:
            outcome = handle_message(
                self.state,
                item.connection.player_id,
                item.message,
                self._clock(),
                self._config,
            )
        except Exception:
            logger.exception("A message in room %s failed", self.state.code)
            return
        self._store_and_deliver(outcome, item.connection, joined)

    def _note_frame_seen(self, connection: RoomConnection) -> None:
        """Set `last_seen_at` for a frame that has no other effect (spec 017)."""
        if connection.player_id is None or connection not in self._connections:
            return
        self.state = with_last_seen(self.state, connection.player_id, self._clock())

    def _unjoined_step(
        self, connection: RoomConnection, message: ClientMessage
    ) -> None:
        """Handle a message of a connection that has not joined yet."""
        if isinstance(message, Join):
            self._join_step(connection, message)
        elif isinstance(message, Ping):
            connection.deliver_text(Pong().model_dump_json())
        else:
            self._refuse(connection, ErrorCode.NOT_JOINED)

    def _refuse(self, connection: RoomConnection, code: ErrorCode) -> None:
        """Answer a connection with an error; its socket stays open."""
        text = _REFUSAL_TEXTS[code]
        connection.deliver_text(ErrorMessage(code=code, message=text).model_dump_json())

    def _join_step(self, connection: RoomConnection, message: Join) -> None:
        """Run the join in the rules, then attach the connection if it succeeded.

        The snapshot is built by the rules in the same step as the attach, so
        the connection gets no event before it and none is missed after it.
        """
        joined = list(self._connections)
        try:
            outcome = join_room(
                self.state,
                message,
                self._clock(),
                secrets.token_urlsafe(8),
                secrets.token_urlsafe(24),
                self._config,
            )
        except Exception:
            logger.exception("A join in room %s failed", self.state.code)
            return
        if not self._store_and_deliver(outcome, connection, joined):
            # The player is not in the room: do not leave the joiner waiting.
            connection.deliver_close(_INTERNAL_ERROR_CLOSE_CODE)
            return
        for reply in outcome.reply:
            if isinstance(reply, Snapshot):
                self._attach(connection, reply.you, message.resume_token is not None)

    def _attach(
        self, connection: RoomConnection, player_id: str, is_resume: bool
    ) -> None:
        """Bind a connection to its player.

        A resume takes over: the older sockets of the same player are closed
        with SESSION_REPLACED_CLOSE_CODE and are sent nothing else.
        """
        connection.player_id = player_id
        if is_resume:
            for older in list(self._connections):
                if older.player_id == player_id:
                    self._connections.remove(older)
                    older.deliver_close(SESSION_REPLACED_CLOSE_CODE)
        self._connections.append(connection)

    def _detach_step(self, leaving: RoomConnection) -> None:
        """Remove one connection; the player leaves with their last connection.

        When the player's disconnection cannot be committed, the connection
        stays registered: the room still shows the player as active, so it
        still has a connection for them (a resume of the player replaces it).
        """
        if leaving not in self._connections:
            return
        others = [other for other in self._connections if other is not leaving]
        is_last_of_player = True
        for other in others:
            if other.player_id == leaving.player_id:
                is_last_of_player = False
        if is_last_of_player and leaving.player_id is not None:
            try:
                outcome = disconnect_player(
                    self.state, leaving.player_id, self._clock()
                )
            except Exception:
                logger.exception("A disconnection in room %s failed", self.state.code)
                return
            if not self._store_and_deliver(outcome, None, others):
                return
        self._connections.remove(leaving)

    def _store_and_deliver(
        self,
        outcome: Outcome,
        sender: RoomConnection | None,
        joined: list[RoomConnection],
    ) -> bool:
        """Commit the step's entries, store the new state, then deliver.

        Nothing is delivered before the entries are committed (spec 011
        delivery step 1). The commit is made in the engine's thread: it waits
        for the disk, but a step never waits for a socket.

        Args:
            outcome: What the step produced.
            sender: The connection whose message made the step; None for a tick
                or a closed connection.
            joined: The connections that were joined before the step.

        Returns:
            False when the entries could not be committed: the step is then
            dropped, nothing is delivered and the state is left as it was.
        """
        if len(outcome.entries) > 0:
            try:
                self._store.append(self.state.code, outcome.entries)
            except Exception:
                logger.exception("The log of room %s failed", self.state.code)
                return False
        self.state = outcome.state
        self._events_since_snapshot += len(outcome.entries)

        for entry in outcome.entries:
            event_text = entry.event.model_dump_json()
            for connection in joined:
                connection.deliver_text(event_text)

        if sender is not None:
            for message in outcome.reply:
                sender.deliver_text(message.model_dump_json())

        for moved in outcome.to_others:
            moved_text = moved.model_dump_json()
            for connection in joined:
                if connection is sender or connection.player_id == moved.player_id:
                    continue  # a selection is never sent to its own player
                connection.deliver_text(moved_text)

        for disconnect in outcome.disconnects:
            for target in self._connections:
                if target.player_id != disconnect.player_id:
                    continue
                if disconnect.error is not None:
                    target.deliver_text(disconnect.error.model_dump_json())
                target.deliver_close(disconnect.close_code)

        if outcome.close_sender and sender is not None:
            sender.deliver_close(_NORMAL_CLOSE_CODE)

        if self._events_since_snapshot >= self._config.snapshot_every:
            self.save_snapshot()
        return True


class RoomRegistry:
    """The rooms of this process, by code, and the tasks that run them.

    A plain class, not a Pydantic model: a mutable service. Every method may be
    called from any thread.
    """

    def __init__(
        self,
        *,
        config: RoomConfig | None = None,
        clock: Clock | None = None,
        store: RoomStore | None = None,
    ) -> None:
        """Create a registry with no live room.

        Args:
            config: Thresholds of the rooms. None: RoomConfig().
            clock: Seconds since the epoch. None: time.time.
            store: Where the rooms are written. None: a new in-memory store,
                which the registry closes itself. A store given is never closed.
        """
        self._config = config if config is not None else RoomConfig()
        self._clock: Clock = clock if clock is not None else time.time
        self._owns_store = store is None
        self._store = store if store is not None else RoomStore(":memory:")
        self._lock = threading.Lock()
        self._runners: dict[str, _RoomRunner] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._closed = False
        self._stop_task: asyncio.Task[None] | None = None

    @property
    def config(self) -> RoomConfig:
        """The thresholds of the rooms."""
        return self._config

    @property
    def clock(self) -> Clock:
        """The clock of the rooms."""
        return self._clock

    def register_room(self, grid: Grid, grid_number: int | None = None) -> str:
        """Create a room on `grid` and return its code.

        Args:
            grid: The grid to solve.
            grid_number: Catalogue number of the grid, None for a bare grid.

        Returns:
            A code of ROOM_CODE_LENGTH characters of ROOM_CODE_ALPHABET, drawn
            at random and different from every code in use.

        Raises:
            RuntimeError: the registry is closed.
        """
        with self._lock:
            self._check_open()
            code = _draw_code()
            while self._is_taken(code):
                code = _draw_code()
            state = new_room(code, grid, self._clock(), grid_number)
            self._store.create_room(state)
            self._runners[code] = self._new_runner(state, state.seq)
            return code

    def add_room(self, state: RoomState) -> None:
        """Register a room in a given state (tests, and spec 018's loader).

        Raises:
            ValueError: a room with `state.code` already exists.
            RuntimeError: the registry is closed.
        """
        with self._lock:
            self._check_open()
            if self._is_taken(state.code):
                raise ValueError(f"A room with code {state.code} already exists")
            self._store.create_room(state)
            self._runners[state.code] = self._new_runner(state, state.seq)

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of room `code`, or None when there is no such room."""
        state = self.room_state(code)
        if state is None:
            return None
        return state.grid

    def room_state(self, code: str) -> RoomState | None:
        """Return the latest state of room `code`, or None.

        Read-only: the returned model is the one the room task last stored.
        A room that is only in the store is loaded first (see `_find_runner`).
        """
        runner = self._find_runner(code)
        if runner is None:
            return None
        return runner.state

    def connect(self, code: str) -> RoomConnection | None:
        """Open a connection to room `code` for a socket that has not joined.

        The connection receives the room's messages once the player's join is
        accepted by the room task.

        Must be called from the event loop that serves the socket.

        Returns:
            The connection, or None when there is no such room.

        Raises:
            RuntimeError: the registry is closed.
        """
        runner = self._find_runner(code)
        if runner is None:
            return None
        engine_loop = self._engine_loop()

        def post(item: _Input) -> None:
            try:
                engine_loop.call_soon_threadsafe(runner.post, item)
            except RuntimeError:
                # The registry was closed: the room no longer runs.
                return

        return RoomConnection(asyncio.get_running_loop(), post)

    def close(self) -> None:
        """Stop the room tasks and the engine thread. Idempotent.

        Then a snapshot of each live room is saved, and the store is closed
        when the registry created it.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            loop = self._loop
            thread = self._thread
        if loop is None or thread is None:
            self._finish()
            return
        if threading.current_thread() is thread:
            # Waiting for ourselves would block: the engine stops afterwards.
            self._stop_task = loop.create_task(self._cancel_runners_and_stop())
            return
        try:
            stopping = asyncio.run_coroutine_threadsafe(self._cancel_runners(), loop)
            stopping.result(timeout=_STOP_TIMEOUT_SECONDS)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            thread.join(timeout=_STOP_TIMEOUT_SECONDS)
            self._finish()

    def _is_taken(self, code: str) -> bool:
        """Tell whether a room has this code, live or only in the store.

        The caller holds the lock.
        """
        return code in self._runners or self._store.has_room(code)

    def _new_runner(self, state: RoomState, snapshot_seq: int | None) -> _RoomRunner:
        """Create the runner of a room."""
        return _RoomRunner(state, self._config, self._clock, self._store, snapshot_seq)

    def _find_runner(self, code: str) -> _RoomRunner | None:
        """Return the live runner of room `code`, loading it from the store.

        A room that is only in the store is loaded, made live, and goes through
        one `after_restart` step, which is logged, before anything else. Two
        threads asking for the same code load it once.
        """
        runner = self._runners.get(code)
        if runner is not None:
            return runner
        with self._lock:
            runner = self._runners.get(code)
            if runner is not None or self._closed:
                return runner
            state = self._store.load_room(code)
            if state is None:
                return None
            outcome = after_restart(state, self._clock())
            if len(outcome.entries) > 0:
                self._store.append(code, outcome.entries)
            runner = self._new_runner(outcome.state, None)
            self._runners[code] = runner
            return runner

    def _finish(self) -> None:
        """Save a snapshot of each live room, then close the store if owned."""
        for runner in list(self._runners.values()):
            runner.save_snapshot()
        if self._owns_store:
            self._store.close()

    def _check_open(self) -> None:
        """Raise RuntimeError when the registry is closed."""
        if self._closed:
            raise RuntimeError("The room registry is closed")

    def _engine_loop(self) -> asyncio.AbstractEventLoop:
        """Return the engine's event loop, starting its thread on first use."""
        with self._lock:
            self._check_open()
            if self._loop is None:
                loop = asyncio.new_event_loop()
                thread = threading.Thread(
                    target=_run_loop, args=(loop,), name="nock-rooms", daemon=True
                )
                thread.start()
                self._loop = loop
                self._thread = thread
            return self._loop

    async def _cancel_runners(self) -> None:
        """Stop the task of every room."""
        for runner in list(self._runners.values()):
            await runner.cancel()

    async def _cancel_runners_and_stop(self) -> None:
        """Stop the task of every room, then the event loop."""
        await self._cancel_runners()
        self._finish()
        asyncio.get_running_loop().stop()


def _run_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Run the engine's event loop until it is stopped, then close it."""
    asyncio.set_event_loop(loop)
    loop.run_forever()
    loop.close()


def _draw_code() -> str:
    """Return a random room code, which may already be taken."""
    characters: list[str] = []
    for _ in range(ROOM_CODE_LENGTH):
        characters.append(secrets.choice(ROOM_CODE_ALPHABET))
    return "".join(characters)
