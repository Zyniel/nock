"""The registry of live rooms and the tasks that run them.

The pure rules live in `nock.room`. This module owns the time and the threads:
a registry runs its rooms on its own asyncio event loop in a daemon thread, with
one task per room that applies the room's inputs one at a time.

Each connection bounds what waits for it in both directions (spec 036): a client
that never reads its socket is closed as stalled, and a client that sends faster
than its room applies is closed as flooding.

A room lives 30 days from its last edit (spec 032). An expired room is deleted by
`expire_rooms`, which the app runs every hour, and by any lookup that meets it.

Each step made by a client message logs its relay time (spec 038): how long the
server took from reading the message to handing the step's entries to the store.
"""

from __future__ import annotations

import asyncio
import logging
import math
import secrets
import threading
import time
from collections.abc import Awaitable, Callable, Sequence
from typing import NamedTuple

from nock.catch_up import CatchUp, CatchUpRequest, build_catch_up
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
from nock.recap import PublicRecap, Recap, build_recap, public_recap
from nock.room import (
    DEFAULT_CONFIG,
    SILENCE_CLOSE_CODE,
    Clock,
    LogEntry,
    Outcome,
    RoomConfig,
    RoomKey,
    RoomState,
    RoomSummary,
    after_restart,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    room_summary,
    tick,
    with_last_seen,
    with_player_erased,
)
from nock.room import member_id as room_member_id
from nock.store import RoomStore

__all__ = [
    "FLOOD_CLOSE_CODE",
    "MAX_FRAME_BYTES",
    "ROOM_NOT_FOUND_CLOSE_CODE",
    "SESSION_REPLACED_CLOSE_CODE",
    "SILENCE_CLOSE_CODE",
    "STALLED_CLOSE_CODE",
    "RoomConnection",
    "RoomRegistry",
]

logger = logging.getLogger(__name__)

ROOM_CODE_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0, O, 1, I
ROOM_CODE_LENGTH: int = 6
SHARE_TOKEN_BYTES: int = 16  # spec 028: secrets.token_urlsafe(16), 22 characters

MAX_FRAME_BYTES: int = 4096  # spec 037: larger frames are not parsed
ROOM_NOT_FOUND_CLOSE_CODE: int = 4404  # unknown room, or deleted (spec 032)
SESSION_REPLACED_CLOSE_CODE: int = 4001  # the same player opened another socket
STALLED_CLOSE_CODE: int = 4507  # spec 036: the client did not read its messages
FLOOD_CLOSE_CODE: int = 1008  # spec 036: the client sent faster than the room applies

_REFUSAL_TEXTS: dict[ErrorCode, str] = {
    ErrorCode.NOT_JOINED: "Send a join message before anything else.",
    ErrorCode.INVALID_MESSAGE: "The message is not a valid client message.",
}

_NORMAL_CLOSE_CODE = 1000
_INTERNAL_ERROR_CLOSE_CODE = 1011  # the server could not save the join
_STOP_TIMEOUT_SECONDS = 5.0


class _Message(NamedTuple):
    """Input: a client message of a connection, a join included."""

    connection: RoomConnection
    message: ClientMessage
    read_at: float  # time.monotonic() when the server read the message (spec 038)


class _Invalid(NamedTuple):
    """Input: a frame of a connection that is not a valid client message."""

    connection: RoomConnection


class _Detach(NamedTuple):
    """Input: a connection closed, or stalled (spec 036)."""

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

    Both directions are bounded (spec 036):

    - Stalled: when the room delivers a message while `max_outbound` items wait
      in the queue, the queued items are dropped, the connection gets nothing
      more, its writer closes the socket with STALLED_CLOSE_CODE and the room
      disconnects the connection.
    - Flooded: when a frame arrives while `max_inbound` inputs of the connection
      wait to be applied by the room, that frame and every later one are
      dropped, and the socket is closed with FLOOD_CLOSE_CODE once the items
      already queued are sent.

    The room's thread and the socket's thread both change the counts behind
    these bounds, so a lock guards them.
    """

    def __init__(
        self,
        owner_loop: asyncio.AbstractEventLoop,
        post: Callable[[_Input], None],
        max_outbound: int = DEFAULT_CONFIG.max_outbound_messages,
        max_inbound: int = DEFAULT_CONFIG.max_inbound_pending,
    ) -> None:
        """Create a connection owned by `owner_loop`, the loop of the socket.

        `player_id` stays None until the room task accepts the connection's join.

        Args:
            owner_loop: The event loop of the socket's handler.
            post: Passes an input to the room task, from any thread.
            max_outbound: How many items may wait in the outbound queue.
            max_inbound: How many inputs may wait to be applied by the room.
        """
        self.player_id: str | None = None
        self._owner_loop = owner_loop
        self._post = post
        self._max_outbound = max_outbound
        self._max_inbound = max_inbound
        self._outbound: asyncio.Queue[_Outbound] = asyncio.Queue()
        self._stall_alarm = asyncio.Event()  # set on the owner loop once stalled
        self._lock = threading.Lock()
        self._outbound_count = 0  # items queued and not taken by the writer yet
        self._inbound_count = 0  # inputs passed on and not applied by the room yet
        self._is_stalled = False
        self._is_flooded = False

    def submit(self, message: ClientMessage) -> None:
        """Pass a message of this player to the room (any thread).

        The server calls it as soon as it has read the message's frame, so the
        time of the call goes with the message: the room logs its relay time
        from it (spec 038). The message is dropped when it floods the
        connection, or comes after.
        """
        read_at = time.monotonic()
        if self._admit_frame():
            self._post(_Message(self, message, read_at))

    def submit_invalid(self) -> None:
        """Tell the room that this player sent an invalid frame (any thread).

        The frame is dropped when it floods the connection, or comes after.
        """
        if self._admit_frame():
            self._post(_Invalid(self))

    def leave(self) -> None:
        """Tell the room that the socket closed (any thread).

        Never dropped, even after a flood, and not counted as an input.
        """
        self._post(_Detach(self))

    def mark_input_applied(self) -> None:
        """Count one input of this connection as applied. Called by the room task.

        The room calls it when it finished the step of a message or of an
        invalid frame that this connection passed on.
        """
        with self._lock:
            self._inbound_count -= 1

    def deliver_text(self, text: str) -> None:
        """Queue a message for the socket. Called by the room task.

        The message is dropped when it stalls the connection, or comes after.
        """
        if self._admit_message():
            self._enqueue(_Outbound(text=text, close_code=None))

    def deliver_close(self, close_code: int) -> None:
        """Queue the closing of the socket. Called by the room task."""
        self._queue_close(close_code)

    async def run_writer(
        self,
        send_text: Callable[[str], Awaitable[None]],
        close: Callable[[int], Awaitable[None]],
    ) -> None:
        """Write the queued items to the socket, in order, until a close.

        Then `close` is called once, with the code of the close item. When the
        connection stalls, the writer stops waiting for the text it is sending,
        even one that never completes, and the code is STALLED_CLOSE_CODE.

        Must run on the event loop that owns this connection.
        """
        close_code = await self._send_until_close(send_text)
        await close(close_code)

    async def _send_until_close(
        self, send_text: Callable[[str], Awaitable[None]]
    ) -> int:
        """Send the queued texts until a close item comes or the connection stalls.

        Returns:
            The code of the close item, or STALLED_CLOSE_CODE.
        """
        sending = asyncio.create_task(self._send_queued_texts(send_text))
        stalled = asyncio.create_task(self._stall_alarm.wait())
        try:
            await asyncio.wait({sending, stalled}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            # Neither task is awaited: a send that never completes is left behind.
            sending.cancel()
            stalled.cancel()
        if sending.done():
            return sending.result()
        return STALLED_CLOSE_CODE

    async def _send_queued_texts(
        self, send_text: Callable[[str], Awaitable[None]]
    ) -> int:
        """Send the queued texts, in order, until a close item.

        Returns:
            The code of the close item.
        """
        while True:
            item = await self._outbound.get()
            with self._lock:
                self._outbound_count -= 1
            if item.close_code is not None:
                return item.close_code
            if item.text is not None:
                await send_text(item.text)

    def _admit_frame(self) -> bool:
        """Count a frame of the client as one more input waiting for the room.

        A frame that arrives while `max_inbound` inputs wait floods the
        connection: the socket is closed with FLOOD_CLOSE_CODE through the
        outbound queue, without waiting for the room task.

        Returns:
            True when the frame goes to the room; False when it is dropped
            because it flooded the connection, or came after the flood.
        """
        with self._lock:
            if self._is_flooded:
                return False
            if self._inbound_count < self._max_inbound:
                self._inbound_count += 1
                return True
            self._is_flooded = True
        self._queue_close(FLOOD_CLOSE_CODE)
        return False

    def _admit_message(self) -> bool:
        """Count a message of the room as one more item in the outbound queue.

        A message that comes while `max_outbound` items wait stalls the
        connection: the writer drops the queued items and closes the socket
        with STALLED_CLOSE_CODE, and the room is asked to disconnect it.

        Returns:
            True when the message is queued; False when it is dropped because
            it stalled the connection, or came after the stall.
        """
        with self._lock:
            if self._is_stalled:
                return False
            if self._outbound_count < self._max_outbound:
                self._outbound_count += 1
                return True
            self._is_stalled = True
        self._stop_writer()
        self._post(_Detach(self))
        return False

    def _queue_close(self, close_code: int) -> None:
        """Queue the closing of the socket, unless the connection is stalled."""
        with self._lock:
            if self._is_stalled:
                return
            self._outbound_count += 1
        self._enqueue(_Outbound(text=None, close_code=close_code))

    def _enqueue(self, item: _Outbound) -> None:
        """Put an item in the queue from any thread."""
        try:
            self._owner_loop.call_soon_threadsafe(self._outbound.put_nowait, item)
        except RuntimeError:
            # The socket's event loop is closed: nobody is left to read.
            return

    def _stop_writer(self) -> None:
        """Make the writer drop the queue and close as stalled, from any thread."""
        try:
            self._owner_loop.call_soon_threadsafe(self._drop_queue_and_wake_writer)
        except RuntimeError:
            # The socket's event loop is closed: there is no writer to stop.
            return

    def _drop_queue_and_wake_writer(self) -> None:
        """Drop the items waiting in the queue, then wake the writer.

        Runs on the event loop that owns this connection.
        """
        while not self._outbound.empty():
            self._outbound.get_nowait()
        self._stall_alarm.set()


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
        # The joined connections, which the room's messages go to.
        self._connections: list[RoomConnection] = []
        # Every connection opened to the room whose socket has not closed yet,
        # joined or not: a deletion closes them all (spec 032).
        self._open_connections: list[RoomConnection] = []
        self._inbox: asyncio.Queue[_Input] = asyncio.Queue()
        self._task: asyncio.Task[None] | None = None
        self._is_closed = False
        self._is_deleted = False
        self._store = store
        self._snapshot_seq = snapshot_seq
        self._events_since_snapshot = 0

    def keep_connection(self, connection: RoomConnection) -> None:
        """Keep a connection just opened to the room, so a deletion can close it.

        Called on the engine's loop, before any input of the connection.

        Args:
            connection: The new connection, joined or not. When the room is
                already deleted, it is closed at once with
                ROOM_NOT_FOUND_CLOSE_CODE instead.
        """
        if self._is_deleted:
            connection.deliver_close(ROOM_NOT_FOUND_CLOSE_CODE)
            return
        self._open_connections.append(connection)

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

    async def delete(self) -> None:
        """Stop the room for good, delete it from the store, then close its sockets.

        The inputs still in the inbox are dropped, and no step, snapshot or log
        entry is made. Then each connection opened to the room is sent a close
        with ROOM_NOT_FOUND_CLOSE_CODE and no other message (spec 032), also
        when the store fails.
        """
        self._is_deleted = True
        await self.cancel()
        try:
            self._store.delete_room(self.state.code)
        finally:
            self._close_open_connections()

    async def stop_for_deletion(self) -> None:
        """Stop the room for good and close its sockets, leaving the store alone.

        For a room the registry already deleted from the store, where a new room
        may have its code by now. As in `delete`, the inputs still in the inbox
        are dropped, and each connection opened to the room is sent a close with
        ROOM_NOT_FOUND_CLOSE_CODE, also when stopping the task fails.
        """
        self._is_deleted = True
        try:
            await self.cancel()
        finally:
            self._close_open_connections()

    def erase_player(self, player_id: str) -> None:
        """Erase a player's nickname from the room, between two of its steps.

        Called on the engine's loop, so no step runs meanwhile. The live state
        changes first, then the store; no event is logged or sent (spec 033).
        A deleted room changes nothing.
        """
        if self._is_deleted:
            return
        self.state = with_player_erased(self.state, player_id)
        self._store.erase_player(self.state.code, player_id)

    def _close_open_connections(self) -> None:
        """Close each connection opened to the room with ROOM_NOT_FOUND_CLOSE_CODE."""
        for connection in self._open_connections:
            connection.deliver_close(ROOM_NOT_FOUND_CLOSE_CODE)
        self._open_connections = []

    def save_snapshot(self) -> None:
        """Save a snapshot of the room unless the store has one at this seq.

        A failure is logged: the log alone is enough to rebuild the room. A
        deleted room saves nothing.
        """
        if self._is_deleted or self._snapshot_seq == self.state.seq:
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
            self._apply_input(item)
            if not self._connections and self._inbox.empty():
                return

    def _apply_input(self, item: _Input) -> None:
        """Run the step of one input, then tell its connection it is applied.

        A detach is not one of the inputs a connection counts (spec 036).
        """
        try:
            self._input_step(item)
        finally:
            if not isinstance(item, _Detach):
                item.connection.mark_input_applied()

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
            self._unjoined_step(item.connection, item.message, item.read_at)
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
        self._store_and_deliver(outcome, item.connection, joined, read_at=item.read_at)

    def _note_frame_seen(self, connection: RoomConnection) -> None:
        """Set `last_seen_at` for a frame that has no other effect (spec 017)."""
        if connection.player_id is None or connection not in self._connections:
            return
        self.state = with_last_seen(self.state, connection.player_id, self._clock())

    def _unjoined_step(
        self, connection: RoomConnection, message: ClientMessage, read_at: float
    ) -> None:
        """Handle a message of a connection that has not joined yet.

        `read_at` is when the server read the message (see `RoomConnection.submit`).
        """
        if isinstance(message, Join):
            self._join_step(connection, message, read_at)
        elif isinstance(message, Ping):
            connection.deliver_text(Pong().model_dump_json())
        else:
            self._refuse(connection, ErrorCode.NOT_JOINED)

    def _refuse(self, connection: RoomConnection, code: ErrorCode) -> None:
        """Answer a connection with an error; its socket stays open."""
        text = _REFUSAL_TEXTS[code]
        connection.deliver_text(ErrorMessage(code=code, message=text).model_dump_json())

    def _join_step(
        self, connection: RoomConnection, message: Join, read_at: float
    ) -> None:
        """Run the join in the rules, then attach the connection if it succeeded.

        The snapshot is built by the rules in the same step as the attach, so
        the connection gets no event before it and none is missed after it.
        `read_at` is when the server read the join (see `RoomConnection.submit`).
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
        if not self._store_and_deliver(outcome, connection, joined, read_at=read_at):
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
        if leaving in self._open_connections:
            self._open_connections.remove(leaving)
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
        *,
        read_at: float | None = None,
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
            read_at: When the server read the client message of the step, from
                `time.monotonic()`; None for a step without one (a tick, a
                closed connection). The logged entries get their relay time
                from it (spec 038); what the players receive does not change.

        Returns:
            False when the entries could not be committed: the step is then
            dropped, nothing is delivered and the state is left as it was.
        """
        if len(outcome.entries) > 0:
            logged_entries = _with_relay_time(outcome.entries, read_at)
            try:
                self._store.append(self.state.code, logged_entries)
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

        for item in outcome.to_others:
            item_text = item.model_dump_json()
            for connection in joined:
                if connection is sender or connection.player_id == item.player_id:
                    continue  # never sent to its own player (spec 011 step 4)
                connection.deliver_text(item_text)

        for disconnect in outcome.disconnects:
            targets = []
            for connection in list(self._connections):
                if connection.player_id == disconnect.player_id:
                    targets.append(connection)
            for target in targets:
                if disconnect.error is not None:
                    target.deliver_text(disconnect.error.model_dump_json())
                # A disconnected connection is no longer routed to the room, so
                # a frame still in flight cannot act as that player (spec 014
                # AC-5).
                self._connections.remove(target)
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
        # Deletions started on the engine's own thread, kept until they end: an
        # event loop keeps only weak references to its tasks.
        self._deletion_tasks: set[asyncio.Task[None]] = set()

    @property
    def config(self) -> RoomConfig:
        """The thresholds of the rooms."""
        return self._config

    @property
    def clock(self) -> Clock:
        """The clock of the rooms."""
        return self._clock

    @property
    def store(self) -> RoomStore:
        """The store of the rooms. The server's routes read logs through it."""
        return self._store

    def register_room(self, grid: Grid, grid_number: int | None = None) -> str:
        """Create a room on `grid` and return its code.

        Args:
            grid: The grid to solve.
            grid_number: Catalogue number of the grid, None for a bare grid.

        Returns:
            A code of ROOM_CODE_LENGTH characters of ROOM_CODE_ALPHABET, drawn
            at random and different from every code in use. The room also gets
            a random share token (spec 028), which is not its code.

        Raises:
            RuntimeError: the registry is closed.
        """
        with self._lock:
            self._check_open()
            code = _draw_code()
            while self._is_taken(code):
                code = _draw_code()
            share_token = secrets.token_urlsafe(SHARE_TOKEN_BYTES)
            state = new_room(code, grid, self._clock(), grid_number, share_token)
            self._store.create_room(state)
            self._runners[code] = self._new_runner(state, state.seq)
            return code

    def add_room(self, state: RoomState) -> None:
        """Register a room in a given state (tests, and spec 018's loader).

        The room keeps the share token of `state` (spec 028). Its life starts at
        `clock()`, whatever its `created_at` (spec 032).

        Raises:
            ValueError: a room with `state.code` already exists, or another room
                already has the share token `state.share_token`.
            RuntimeError: the registry is closed.
        """
        with self._lock:
            self._check_open()
            if self._is_taken(state.code):
                raise ValueError(f"A room with code {state.code} already exists")
            self._store.create_room(state, last_edit_at=self._clock())
            self._runners[state.code] = self._new_runner(state, state.seq)

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of room `code`, or None when there is no such room.

        An expired room is deleted first, and so gives None (see `room_state`).
        """
        state = self.room_state(code)
        if state is None:
            return None
        return state.grid

    def room_state(self, code: str) -> RoomState | None:
        """Return the latest state of room `code`, or None.

        Read-only: the returned model is the one the room task last stored.
        A room that is only in the store is loaded first (see `_find_runner`).
        An expired room is deleted first, and so gives None (spec 032).
        """
        runner = self._find_runner(code)
        if runner is None:
            return None
        return runner.state

    def peek_room(self, code: str) -> RoomState | None:
        """Return the room's latest state without making it live.

        A live room gives its live state; a room only in the store gives
        `store.load_room(code)`, with no `after_restart` step and nothing logged.

        Returns:
            The state; None when the room is unknown or expired. An expired room
            is deleted first, as by `expire_rooms`.
        """
        if self._delete_if_expired(code):
            return None
        runner = self._runners.get(code)
        if runner is not None:
            return runner.state
        return self._store.load_room(code)

    def member_id(self, code: str, resume_token: str) -> str | None:
        """Return the id of the room's member whose resume token is `resume_token`.

        Returns:
            `nock.room.member_id` of the room's latest state, as `peek_room`
            reads it; None when the room is unknown or expired, or when no
            member holds the token.
        """
        state = self.peek_room(code)
        if state is None:
            return None
        return room_member_id(state, resume_token)

    def catch_up(self, code: str, request: CatchUpRequest) -> CatchUp | None:
        """Return the catch-up that a member asks for, or None (spec 034).

        None when `member_id(code, request.resume_token)` is None (the room is
        unknown or expired, or the token is not a member's, spec 032), or when
        `before = store.load_room_at(code, request.after_seq)` is None.
        Otherwise `build_catch_up(request.after_seq, request.until_seq, before,
        entries)`, with `entries` the entries of
        `store.read_log(code, before.seq)` whose seq is at most
        `request.until_seq`. It only reads: the room is not made live and
        nothing is logged.
        """
        if self.member_id(code, request.resume_token) is None:
            return None
        before = self._store.load_room_at(code, request.after_seq)
        if before is None:
            return None
        entries: list[LogEntry] = []
        for entry in self._store.read_log(code, before.seq):
            if entry.event.seq <= request.until_seq:
                entries.append(entry)
        return build_catch_up(request.after_seq, request.until_seq, before, entries)

    def room_summaries(self, keys: Sequence[RoomKey]) -> list[RoomSummary]:
        """Return the summaries of the rooms that a key's token is a member of.

        One summary per code, whatever the number of keys naming it: one key
        holding a member's token is enough. A room that is unknown or expired,
        or whose keys hold no member's token, is left out, and nothing tells
        why. No room is made live and nothing is logged.

        Returns:
            The summaries, the newest `last_activity_at` first, then by code in
            code-point order.
        """
        tokens_by_code: dict[str, list[str]] = {}
        for key in keys:
            if key.code not in tokens_by_code:
                tokens_by_code[key.code] = []
            tokens_by_code[key.code].append(key.resume_token)
        summaries: list[RoomSummary] = []
        for code, tokens in tokens_by_code.items():
            summary = self._summary_for_members(code, tokens)
            if summary is not None:
                summaries.append(summary)
        summaries.sort(key=_newest_first)
        return summaries

    def expire_rooms(self) -> list[str]:
        """Delete every room that is expired at `clock()` (spec 032).

        A room is expired once more than `config.room_life_seconds` passed since
        its last edit. A live room's task stops first, and each of its sockets is
        closed with ROOM_NOT_FOUND_CLOSE_CODE.

        Returns:
            The codes of the rooms deleted, in code-point order.
        """
        expired_codes = self._store.expired_codes(self._expiry_limit())
        for code in expired_codes:
            self._delete_room(code)
        return expired_codes

    def erase_player(self, code: str, player_id: str) -> bool:
        """Erase a player's nickname from a room, live state included (spec 033).

        For a live room, the room's task does it between two steps: the player's
        record (in `players` or `past_players`) gets FORMER_PLAYER_NICKNAME, then
        `store.erase_player`. For a room only in the store, `store.erase_player`.
        No event is logged or sent: a snapshot built afterwards shows the new
        nickname. Returns once it is done.

        Args:
            code: The room.
            player_id: The player whose account was deleted.

        Returns:
            True when the room exists; False when it is unknown or expired (an
            expired room is deleted first, spec 032).
        """
        if self._delete_if_expired(code):
            return False
        with self._lock:
            runner = self._runners.get(code)
            loop = self._loop
            if runner is None or loop is None or self._closed:
                # No task runs the room, and none can start while the lock is
                # held: the state can change here.
                if runner is not None:
                    runner.state = with_player_erased(runner.state, player_id)
                return self._store.erase_player(code, player_id)

        async def erase_between_steps() -> None:
            runner.erase_player(player_id)

        erasing = asyncio.run_coroutine_threadsafe(erase_between_steps(), loop)
        erasing.result(timeout=_STOP_TIMEOUT_SECONDS)
        return True

    def room_recap(self, code: str) -> Recap | None:
        """Return the recap of room `code` (spec 028), from its state and its log.

        Returns:
            `build_recap` of the room's latest state and its stored log; None when
            there is no such room, when it is not solved, or when `build_recap`
            raises ValueError, for example when its log does not hold its whole
            history (a room added in a later state).
        """
        state = self.room_state(code)
        if state is None or not state.solved:
            return None
        # The log is read after the state: the store holds every entry of the
        # state, and build_recap leaves out the ones that came after it.
        log = self._store.read_log(code)
        try:
            return build_recap(state, log)
        except ValueError:
            return None

    def shared_recap(self, token: str) -> PublicRecap | None:
        """Return the public recap of the room whose share token is `token`.

        A room that is only in the store is loaded first (see `room_state`).

        Returns:
            `public_recap` of the room's recap; None when no room has this token
            (a malformed token included) or `room_recap` gives None.
        """
        code = self._store.code_for_share_token(token)
        if code is None:
            return None
        recap = self.room_recap(code)
        if recap is None:
            return None
        return public_recap(recap)

    def connect(self, code: str) -> RoomConnection | None:
        """Open a connection to room `code` for a socket that has not joined.

        The connection receives the room's messages once the player's join is
        accepted by the room task. Its bounds are the registry's
        `max_outbound_messages` and `max_inbound_pending` (spec 036).

        Must be called from the event loop that serves the socket.

        Returns:
            The connection, or None when there is no such room. An expired room
            is deleted first, and so gives None (spec 032).

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

        connection = RoomConnection(
            asyncio.get_running_loop(),
            post,
            max_outbound=self._config.max_outbound_messages,
            max_inbound=self._config.max_inbound_pending,
        )
        # Scheduled before any input of the connection, so the room knows it
        # before its first frame.
        engine_loop.call_soon_threadsafe(runner.keep_connection, connection)
        return connection

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

        An expired room is deleted first, and gives None (spec 032). A room that
        is only in the store is loaded, made live, and goes through one
        `after_restart` step, which is logged, before anything else. Two threads
        asking for the same code load it once.
        """
        if self._delete_if_expired(code):
            return None
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

    def _summary_for_members(self, code: str, tokens: list[str]) -> RoomSummary | None:
        """Return the summary of room `code` when one of `tokens` is a member's.

        Returns:
            The summary; None when the room is unknown or expired, or when no
            token is a member's.
        """
        state = self.peek_room(code)
        if state is None:
            return None
        holds_a_members_token = False
        for token in tokens:
            if room_member_id(state, token) is not None:
                holds_a_members_token = True
        if not holds_a_members_token:
            return None
        last_edit_at = self._store.last_edit_at(code)
        if last_edit_at is None:
            return None  # deleted since `peek_room` read it
        return room_summary(state, last_edit_at)

    def _expiry_limit(self) -> float:
        """Return the oldest last edit time a room may have at `clock()`.

        A room whose last edit time is strictly less is expired (spec 032).
        """
        return self._clock() - self._config.room_life_seconds

    def _delete_if_expired(self, code: str) -> bool:
        """Delete room `code` when it is expired at `clock()`.

        Returns:
            True when the room was expired, and so is deleted now.
        """
        last_edit_at = self._store.last_edit_at(code)
        if last_edit_at is None or last_edit_at >= self._expiry_limit():
            return False
        self._delete_room(code)
        return True

    def _delete_room(self, code: str) -> None:
        """Delete a room: stop it when it is live, then remove it from the store.

        The lock is held throughout, so that no lookup loads the room again while
        it goes. A live room is stopped on the engine's loop, which then deletes
        it from the store and closes its sockets (`_RoomRunner.delete`); this
        waits until that is done, except on the engine's own thread.
        """
        with self._lock:
            runner = self._runners.pop(code, None)
            loop = self._loop
            if runner is None or loop is None or self._closed:
                # No task or socket to stop: none ever connected, or close()
                # stopped them all.
                self._store.delete_room(code)
                return
            if threading.current_thread() is self._thread:
                # Waiting for ourselves would block, as in close(): the store
                # forgets the room now, under the lock, and the room's task stops
                # after this step, even when the store fails. The stop leaves the
                # store alone: a new room may have taken the code by then.
                try:
                    self._store.delete_room(code)
                finally:
                    stopping = loop.create_task(runner.stop_for_deletion())
                    self._deletion_tasks.add(stopping)
                    stopping.add_done_callback(self._deletion_tasks.discard)
                return
            deleting = asyncio.run_coroutine_threadsafe(runner.delete(), loop)
            deleting.result(timeout=_STOP_TIMEOUT_SECONDS)

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


def _with_relay_time(
    entries: Sequence[LogEntry], read_at: float | None
) -> tuple[LogEntry, ...]:
    """Return a step's entries as the log keeps them, with their relay time.

    Args:
        entries: The entries of one step, about to be handed to the store.
        read_at: When the server read the client message of the step, from
            `time.monotonic()`; None for a step without one.

    Returns:
        With `read_at`, each entry with `relay_ms` set to the whole milliseconds,
        rounded down, from `read_at` to now (spec 038). Without it, the entries
        as they are, whose `relay_ms` is None.
    """
    if read_at is None:
        return tuple(entries)
    relay_ms = math.floor((time.monotonic() - read_at) * 1000)
    timed_entries: list[LogEntry] = []
    for entry in entries:
        timed_entries.append(entry.model_copy(update={"relay_ms": relay_ms}))
    return tuple(timed_entries)


def _newest_first(summary: RoomSummary) -> tuple[float, str]:
    """Sort key of the summaries: the newest last activity first, then the code."""
    return (-summary.last_activity_at.timestamp(), summary.code)


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
