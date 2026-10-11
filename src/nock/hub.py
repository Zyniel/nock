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
from nock.protocol import ClientMessage
from nock.room import (
    Clock,
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    new_room,
    tick,
)

logger = logging.getLogger(__name__)

ROOM_CODE_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I
ROOM_CODE_LENGTH: int = 6

_NORMAL_CLOSE_CODE = 1000
_STOP_TIMEOUT_SECONDS = 5.0


class _Attach(NamedTuple):
    """Input: a connection joined the room and must receive its messages."""

    connection: RoomConnection


class _Message(NamedTuple):
    """Input: a client message from a joined player."""

    connection: RoomConnection
    message: ClientMessage


class _Detach(NamedTuple):
    """Input: a connection closed."""

    connection: RoomConnection


_Input = _Attach | _Message | _Detach


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
        player_id: str,
        owner_loop: asyncio.AbstractEventLoop,
        post: Callable[[_Input], None],
    ) -> None:
        """Create a connection owned by `owner_loop`, the loop of the socket."""
        self.player_id = player_id
        self._owner_loop = owner_loop
        self._post = post
        self._outbound: asyncio.Queue[_Outbound] = asyncio.Queue()

    def submit(self, message: ClientMessage) -> None:
        """Pass a message of this player to the room (any thread)."""
        self._post(_Message(self, message))

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

    def __init__(self, state: RoomState, config: RoomConfig, clock: Clock) -> None:
        """Create a runner with no task yet; the first connection starts it."""
        self.state = state
        self.log: list[LogEntry] = []
        self._config = config
        self._clock = clock
        self._connections: list[RoomConnection] = []
        self._inbox: asyncio.Queue[_Input] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._is_closed = False

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

    async def _run(self) -> None:
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
        if isinstance(item, _Attach):
            self._connections.append(item.connection)
            return
        if isinstance(item, _Detach):
            self._detach_step(item.connection)
            return
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

    def _detach_step(self, leaving: RoomConnection) -> None:
        """Remove one connection; the player leaves with their last connection."""
        if leaving not in self._connections:
            return
        self._connections.remove(leaving)
        for other in self._connections:
            if other.player_id == leaving.player_id:
                return
        try:
            outcome = disconnect_player(self.state, leaving.player_id, self._clock())
        except Exception:
            logger.exception("A disconnection in room %s failed", self.state.code)
            return
        self._store_and_deliver(outcome, None, list(self._connections))

    def _store_and_deliver(
        self,
        outcome: Outcome,
        sender: RoomConnection | None,
        joined: list[RoomConnection],
    ) -> None:
        """Store the new state in one assignment, then deliver the outcome.

        Args:
            outcome: What the step produced.
            sender: The connection whose message made the step; None for a tick
                or a closed connection.
            joined: The connections that were joined before the step.
        """
        self.state = outcome.state
        self.log.extend(outcome.entries)

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
                if connection is not sender:
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


class RoomRegistry:
    """The rooms of this process, by code, and the tasks that run them.

    A plain class, not a Pydantic model: a mutable service. Every method may be
    called from any thread.
    """

    def __init__(
        self, *, config: RoomConfig | None = None, clock: Clock | None = None
    ) -> None:
        """Create a registry with no room.

        Args:
            config: Thresholds of the rooms. None: RoomConfig().
            clock: Seconds since the epoch. None: time.time.
        """
        self._config = config if config is not None else RoomConfig()
        self._clock: Clock = clock if clock is not None else time.time
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
            while code in self._runners:
                code = _draw_code()
            state = new_room(code, grid, self._clock(), grid_number)
            self._runners[code] = _RoomRunner(state, self._config, self._clock)
            return code

    def add_room(self, state: RoomState) -> None:
        """Register a room in a given state (tests, and spec 018's loader).

        Raises:
            ValueError: a room with `state.code` already exists.
            RuntimeError: the registry is closed.
        """
        with self._lock:
            self._check_open()
            if state.code in self._runners:
                raise ValueError(f"A room with code {state.code} already exists")
            self._runners[state.code] = _RoomRunner(state, self._config, self._clock)

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of room `code`, or None when there is no such room."""
        state = self.room_state(code)
        if state is None:
            return None
        return state.grid

    def room_state(self, code: str) -> RoomState | None:
        """Return the latest state of room `code`, or None.

        Read-only: the returned model is the one the room task last stored.
        """
        runner = self._runners.get(code)
        if runner is None:
            return None
        return runner.state

    def connect(self, code: str, player_id: str) -> RoomConnection | None:
        """Join a socket to room `code` so that it receives the room's messages.

        Must be called from the event loop that serves the socket.

        Returns:
            The connection, or None when there is no such room.

        Raises:
            RuntimeError: the registry is closed.
        """
        runner = self._runners.get(code)
        if runner is None:
            return None
        engine_loop = self._engine_loop()

        def post(item: _Input) -> None:
            try:
                engine_loop.call_soon_threadsafe(runner.post, item)
            except RuntimeError:
                # The registry was closed: the room no longer runs.
                return

        connection = RoomConnection(player_id, asyncio.get_running_loop(), post)
        post(_Attach(connection))
        return connection

    def close(self) -> None:
        """Stop the room tasks and the engine thread. Idempotent.

        Spec 018 adds saving a snapshot of each live room first.
        """
        with self._lock:
            if self._closed:
                return
            self._closed = True
            loop = self._loop
            thread = self._thread
        if loop is None or thread is None:
            return
        if threading.current_thread() is thread:
            # Waiting for ourselves would block: the engine stops afterwards.
            self._stop_task = loop.create_task(self._cancel_runners_and_stop())
            return
        stopping = asyncio.run_coroutine_threadsafe(self._cancel_runners(), loop)
        stopping.result(timeout=_STOP_TIMEOUT_SECONDS)
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=_STOP_TIMEOUT_SECONDS)

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
