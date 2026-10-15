"""Spec 036 tests: the hub scenarios of AC-5 and AC-6, with fake sockets.

A hub client is a connection of `RoomRegistry` whose socket is a fake the test
reads. Each scenario is a coroutine that the test runs on an event loop of its own
with `run_hub_scenario`, and it returns what it saw. Used by the tests of AC-5 and
AC-6.

The shared setup of the other themes is in `spec036_harness`.
"""

from __future__ import annotations

import asyncio
import contextlib
import string
import threading
from collections.abc import Callable, Coroutine, Generator, Sequence
from typing import NamedTuple

import pytest

from nock.hub import RoomConnection, RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorMessage,
    Join,
    LetterChanged,
    Ping,
    PlayerStateChanged,
    ServerMessage,
    Snapshot,
    parse_server_message,
)
from nock.room import LogEntry, RoomConfig, RoomState
from nock.store import RoomStore
from spec036_harness import POLL_SECONDS, WAIT_SECONDS

# ---- Values of the spec --------------------------------------------------------------

STALL_BUDGET_SECONDS = 1.0

OUTBOUND_LIMIT = 20  # AC-5's max_outbound_messages
EDIT_GROUP_SIZE = 10  # AC-5: B's edits go in groups, its own queue is bounded too
INBOUND_LIMIT = 5  # AC-6's max_inbound_pending
PACED_EDIT_COUNT = 20  # AC-6's second case: A to T, one at a time
ANSWER_BUDGET_SECONDS = 1.0  # AC-6's second case: the wait for each answer


# ---- Values of the test harness ------------------------------------------------------

SETTLE_SECONDS = 0.3

SCENARIO_LIMIT_SECONDS = 60.0
BLOCK_LIMIT_SECONDS = 10.0


# ---- Hub scenarios (AC-5, AC-6) ------------------------------------------------------


class FakeSocket:
    """The socket of a hub connection, as its writer sees it: keeps what it gets."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.close_codes: list[int] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(text)

    async def close(self, code: int) -> None:
        self.close_codes.append(code)

    def messages(self) -> list[ServerMessage]:
        """Every text received so far, parsed."""
        parsed: list[ServerMessage] = []
        for text in self.texts:
            parsed.append(parse_server_message(text))
        return parsed


class StuckSocket(FakeSocket):
    """The socket of a client that never reads: `send_text` never completes."""

    def __init__(self) -> None:
        super().__init__()
        self._never_set = asyncio.Event()

    async def send_text(self, text: str) -> None:
        self.texts.append(text)
        await self._never_set.wait()


class HubClient(NamedTuple):
    """A connection of a hub test, its socket and the task of its writer."""

    connection: RoomConnection
    socket: FakeSocket
    writer: asyncio.Task[None]


def open_hub_client(
    registry: RoomRegistry, code: str, fake_socket: FakeSocket
) -> HubClient:
    """Connect to room `code` and start the connection's writer on `fake_socket`.

    Called from the scenario's event loop, which then owns the connection.
    """
    connection = registry.connect(code)
    assert connection is not None, f"room {code} is unknown"
    writer = asyncio.create_task(
        connection.run_writer(fake_socket.send_text, fake_socket.close)
    )
    return HubClient(connection=connection, socket=fake_socket, writer=writer)


async def wait_until_async(
    condition: Callable[[], bool], what: str, timeout: float = WAIT_SECONDS
) -> None:
    """Poll `condition` on the running loop until it holds, else fail the test."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        if loop.time() >= deadline:
            pytest.fail(f"timed out after {timeout}s waiting for {what}")
        await asyncio.sleep(POLL_SECONDS)


async def join_hub_client(client: HubClient, nickname: str) -> Snapshot:
    """Send a join and wait for the snapshot that answers it."""
    client.connection.submit(Join(nickname=nickname, resume_token=None))
    await wait_until_async(
        lambda: len(client.socket.texts) > 0, f"the snapshot of {nickname}"
    )
    first = parse_server_message(client.socket.texts[0])
    assert isinstance(first, Snapshot), first
    return first


def run_hub_scenario[ResultT](scenario: Coroutine[object, object, ResultT]) -> ResultT:
    """Run `scenario` with asyncio.run in a thread of its own; return its result.

    A failure inside the scenario fails the test.
    """
    results: list[ResultT] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(asyncio.run(scenario))
        except BaseException as error:  # handed over to the test thread
            errors.append(error)

    thread = threading.Thread(target=run, name="hub-scenario", daemon=True)
    thread.start()
    thread.join(timeout=SCENARIO_LIMIT_SECONDS)
    if thread.is_alive():
        pytest.fail(f"the hub scenario did not end within {SCENARIO_LIMIT_SECONDS}s")
    if errors:
        raise errors[0]
    return results[0]


class BlockingStore(RoomStore):
    """The spec's blocking store: `append` waits on an event while a flag is set."""

    def __init__(self) -> None:
        super().__init__(":memory:")
        self.is_blocking = False
        self.released = threading.Event()
        self.append_waiting = threading.Event()

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        if self.is_blocking:
            self.append_waiting.set()
            # Bounded, so that a failing test never hangs the engine thread.
            self.released.wait(BLOCK_LIMIT_SECONDS)
        super().append(code, entries)

    def block(self) -> None:
        """Make the next appends wait until `release`."""
        self.released.clear()
        self.append_waiting.clear()
        self.is_blocking = True

    def release(self) -> None:
        """Let the waiting append, and every later one, go through."""
        self.is_blocking = False
        self.released.set()


@contextlib.contextmanager
def open_registry(
    config: RoomConfig, store: BlockingStore | None = None
) -> Generator[RoomRegistry]:
    """A registry for one hub test, closed at the end (its store released first)."""
    registry = RoomRegistry(config=config, store=store)
    try:
        yield registry
    finally:
        if store is not None:
            store.release()
        registry.close()


def letter_in_state(state: RoomState | None, row: int, column: int) -> str | None:
    """The letter the room holds at (row, column)."""
    assert state is not None, "the room is unknown"
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell.letter
    pytest.fail(f"no letter cell at ({row}, {column})")


def own_letter_changes(
    messages: list[ServerMessage], player_id: str
) -> list[LetterChanged]:
    """The letter_changed events of `player_id` among `messages`."""
    found: list[LetterChanged] = []
    for message in messages:
        if isinstance(message, LetterChanged) and message.player_id == player_id:
            found.append(message)
    return found


def state_changes_of(
    messages: list[ServerMessage], player_id: str
) -> list[PlayerStateChanged]:
    """The player_state_changed events about `player_id` among `messages`."""
    found: list[PlayerStateChanged] = []
    for message in messages:
        if isinstance(message, PlayerStateChanged) and message.player_id == player_id:
            found.append(message)
    return found


def b_edit(index: int) -> EditLetter:
    """B's edit number `index`, on row 1 of FX-01: the grid is never filled."""
    letter = string.ascii_uppercase[index % len(string.ascii_uppercase)]
    return EditLetter(row=1, column=index % 5, letter=letter)


class StallRun(NamedTuple):
    """What the stalled-client scenario of AC-5 saw."""

    a_id: str
    b_id: str
    close_codes_within_budget: list[int]
    writer_returned: bool
    b_messages_after_30: list[ServerMessage]
    a_texts: list[str]
    final_close_codes: list[int]
    b_messages_after_40: list[ServerMessage]


def submit_b_edit_group(b: HubClient, first_index: int) -> None:
    """B sends EDIT_GROUP_SIZE edits, the first one being edit `first_index`.

    Args:
        b: B's connection.
        first_index: Index (see `b_edit`) of the first edit of the group.
    """
    for index in range(first_index, first_index + EDIT_GROUP_SIZE):
        b.connection.submit(b_edit(index))


async def wait_for_b_letters(b: HubClient, b_id: str, count: int) -> None:
    """Wait until B's `send_text` has recorded `count` of its own letter_changed.

    The outbound bound of the registry applies to B's connection too. One burst of
    30 edits queues 30 letter_changed for B within a few milliseconds, and B is
    itself closed as stalled when its writer is not scheduled in that window.
    Waiting for B's own letter_changed between the groups keeps B's queue at
    EDIT_GROUP_SIZE + 1 messages at most, far under the bound.

    Args:
        b: B's connection.
        b_id: B's player id.
        count: Number of letter_changed of B to wait for, in all.
    """
    await wait_until_async(
        lambda: len(own_letter_changes(b.socket.messages(), b_id)) >= count,
        f"B's {count} letter_changed",
    )


async def stalled_client_scenario(registry: RoomRegistry, code: str) -> StallRun:
    """A never reads; B sends 30 edits in three groups of 10, then 10 more (AC-5).

    B sends a group only once it has received the previous one. A's queue holds
    B's player_joined (and A's snapshot, unless the stuck `send_text` has taken it)
    and one letter_changed per edit of B: A stalls on B's 19th or 20th edit, so
    during the second group either way. The exact edit is not asserted.
    """
    a = open_hub_client(registry, code, StuckSocket())
    a_id = (await join_hub_client(a, "Ana")).you
    b = open_hub_client(registry, code, FakeSocket())
    b_id = (await join_hub_client(b, "Bob")).you

    submit_b_edit_group(b, 0)
    await wait_for_b_letters(b, b_id, EDIT_GROUP_SIZE)
    submit_b_edit_group(b, EDIT_GROUP_SIZE)
    # The 1 s of the spec starts when B has sent the last edit of the second group.
    await wait_until_async(
        lambda: len(a.socket.close_codes) > 0 and a.writer.done(),
        "A's close and the end of A's writer",
        timeout=STALL_BUDGET_SECONDS,
    )
    close_codes_within_budget = list(a.socket.close_codes)
    writer_returned = not a.writer.cancelled() and a.writer.exception() is None
    await wait_for_b_letters(b, b_id, 2 * EDIT_GROUP_SIZE)
    submit_b_edit_group(b, 2 * EDIT_GROUP_SIZE)

    def b_saw_the_stall() -> bool:
        messages = b.socket.messages()
        if len(own_letter_changes(messages, b_id)) < 30:
            return False
        return len(state_changes_of(messages, a_id)) > 0

    await wait_until_async(b_saw_the_stall, "B's 30 letter_changed and A's new state")
    b_messages_after_30 = b.socket.messages()

    submit_b_edit_group(b, 3 * EDIT_GROUP_SIZE)
    await wait_for_b_letters(b, b_id, 4 * EDIT_GROUP_SIZE)
    await asyncio.sleep(SETTLE_SECONDS)
    return StallRun(
        a_id=a_id,
        b_id=b_id,
        close_codes_within_budget=close_codes_within_budget,
        writer_returned=writer_returned,
        b_messages_after_30=b_messages_after_30,
        a_texts=list(a.socket.texts),
        final_close_codes=list(a.socket.close_codes),
        b_messages_after_40=b.socket.messages(),
    )


class BoundRun(NamedTuple):
    """What a scenario saw at the bound, then one input or message over it."""

    close_codes_at_bound: list[int]
    writer_done_at_bound: bool
    close_codes_over_bound: list[int]


async def outbound_bound_scenario(registry: RoomRegistry, code: str) -> BoundRun:
    """A never reads; its queue gets exactly 20 messages, then one more (AC-5).

    A's snapshot is in the stuck `send_text`, so it is no longer queued. A's
    queue then gets B's player_joined and one letter_changed per edit of B:
    after 19 edits it holds 20 messages.
    """
    a = open_hub_client(registry, code, StuckSocket())
    await join_hub_client(a, "Ana")
    b = open_hub_client(registry, code, FakeSocket())
    b_id = (await join_hub_client(b, "Bob")).you

    for index in range(OUTBOUND_LIMIT - 1):
        b.connection.submit(b_edit(index))
    await wait_until_async(
        lambda: len(own_letter_changes(b.socket.messages(), b_id))
        >= OUTBOUND_LIMIT - 1,
        "B's 19 letter_changed",
    )
    await asyncio.sleep(SETTLE_SECONDS)
    close_codes_at_bound = list(a.socket.close_codes)
    writer_done_at_bound = a.writer.done()

    b.connection.submit(b_edit(OUTBOUND_LIMIT - 1))
    await wait_until_async(
        lambda: len(a.socket.close_codes) > 0,
        "A's close after one more message",
        timeout=STALL_BUDGET_SECONDS,
    )
    return BoundRun(
        close_codes_at_bound=close_codes_at_bound,
        writer_done_at_bound=writer_done_at_bound,
        close_codes_over_bound=list(a.socket.close_codes),
    )


async def ana_edit_waiting_in_append(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> HubClient:
    """Ana joins; then the store blocks and her edit T at (1, 0) waits in append."""
    ana = open_hub_client(registry, code, FakeSocket())
    await join_hub_client(ana, "Ana")
    await asyncio.sleep(SETTLE_SECONDS)  # the step of the join is over
    store.block()
    ana.connection.submit(EditLetter(row=1, column=0, letter="T"))
    await wait_until_async(store.append_waiting.is_set, "the edit's step in append")
    return ana


async def send_pings_until_closed(client: HubClient, count: int) -> None:
    """Submit `count` pings, then wait for the connection's close."""
    for _ in range(count):
        client.connection.submit(Ping())
    await wait_until_async(
        lambda: len(client.socket.close_codes) > 0,
        "the close of the flooding connection",
    )


async def release_and_wait_for_t(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> None:
    """Release the store and wait until the room holds T at (1, 0)."""
    store.release()
    await wait_until_async(
        lambda: letter_in_state(registry.room_state(code), 1, 0) == "T",
        "T at (1, 0) once the store is released",
    )


async def join_cleo(registry: RoomRegistry, code: str) -> Snapshot:
    """A new connection C joins as Cleo; return its snapshot."""
    cleo = open_hub_client(registry, code, FakeSocket())
    return await join_hub_client(cleo, "Cleo")


class FloodRun(NamedTuple):
    """What the flooding-client scenario of AC-6 saw."""

    close_codes_while_blocked: list[int]
    store_still_blocked: bool
    letter_in_room: str | None
    c_snapshot: Snapshot
    final_close_codes: list[int]


async def flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> FloodRun:
    """A's edit waits in append, then A sends 7 pings (AC-6)."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    await send_pings_until_closed(ana, 7)
    close_codes_while_blocked = list(ana.socket.close_codes)
    store_still_blocked = store.is_blocking and not store.released.is_set()

    await release_and_wait_for_t(registry, store, code)
    letter_in_room = letter_in_state(registry.room_state(code), 1, 0)
    c_snapshot = await join_cleo(registry, code)
    await asyncio.sleep(SETTLE_SECONDS)
    return FloodRun(
        close_codes_while_blocked=close_codes_while_blocked,
        store_still_blocked=store_still_blocked,
        letter_in_room=letter_in_room,
        c_snapshot=c_snapshot,
        final_close_codes=list(ana.socket.close_codes),
    )


async def inbound_bound_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> BoundRun:
    """A's edit and 4 pings are unapplied (5 in all), then one more ping (AC-6)."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    for _ in range(INBOUND_LIMIT - 1):
        ana.connection.submit(Ping())
    await asyncio.sleep(SETTLE_SECONDS)
    close_codes_at_bound = list(ana.socket.close_codes)
    writer_done_at_bound = ana.writer.done()

    await send_pings_until_closed(ana, 1)
    close_codes_over_bound = list(ana.socket.close_codes)
    await release_and_wait_for_t(registry, store, code)
    return BoundRun(
        close_codes_at_bound=close_codes_at_bound,
        writer_done_at_bound=writer_done_at_bound,
        close_codes_over_bound=close_codes_over_bound,
    )


async def stranger_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str, frame: str
) -> list[int]:
    """While A's edit waits in append, a socket that never joined sends 6 frames."""
    await ana_edit_waiting_in_append(registry, store, code)
    stranger = open_hub_client(registry, code, FakeSocket())
    for _ in range(INBOUND_LIMIT + 1):
        if frame == "ping":
            stranger.connection.submit(Ping())
        else:
            stranger.connection.submit_invalid()
    await wait_until_async(
        lambda: len(stranger.socket.close_codes) > 0,
        "the close of the stranger while the store is blocked",
    )
    close_codes = list(stranger.socket.close_codes)
    await release_and_wait_for_t(registry, store, code)
    return close_codes


async def frame_after_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> Snapshot:
    """A floods; once the room caught up, A sends an edit of (1, 1); C joins."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    await send_pings_until_closed(ana, 7)
    await release_and_wait_for_t(registry, store, code)
    ana.connection.submit(EditLetter(row=1, column=1, letter="X"))
    return await join_cleo(registry, code)


async def close_after_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> tuple[str, Snapshot]:
    """A floods, then A's socket closes (`leave`); C joins once the room caught up."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    ana_snapshot = parse_server_message(ana.socket.texts[0])
    assert isinstance(ana_snapshot, Snapshot), ana_snapshot
    await send_pings_until_closed(ana, 7)
    ana.connection.leave()  # what the server's socket handler does once closed
    await release_and_wait_for_t(registry, store, code)
    return ana_snapshot.you, await join_cleo(registry, code)


def paced_edit(index: int) -> EditLetter:
    """The edit number `index` of AC-6's second case: one letter at (1, 0).

    The letter is the one at place `index` of the alphabet.

    Args:
        index: 0 for the first edit (`A`) up to 19 for the last (`T`).
    """
    letter = string.ascii_uppercase[index]
    return EditLetter(row=1, column=0, letter=letter)


def letter_changes_in(messages: list[ServerMessage]) -> list[LetterChanged]:
    """Every letter_changed among `messages`, whoever made the change."""
    found: list[LetterChanged] = []
    for message in messages:
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def errors_in(messages: list[ServerMessage]) -> list[ErrorMessage]:
    """Every error among `messages`."""
    found: list[ErrorMessage] = []
    for message in messages:
        if isinstance(message, ErrorMessage):
            found.append(message)
    return found


class PacedRun(NamedTuple):
    """What the paced scenario of AC-6's second case saw."""

    you: str
    messages: list[ServerMessage]
    close_codes: list[int]
    letter_in_room: str | None


async def wait_for_answers(client: HubClient, count: int) -> None:
    """Wait until the client's socket holds `count` answers to its edits, at most 1 s.

    An answer is a letter_changed or, for a refused edit, an error: a refusal then
    shows in the test's assertions instead of as a time-out. A missing answer fails
    the test.

    Args:
        client: The client that sent the edits.
        count: How many answers its socket must hold, in all.
    """

    def answers_received() -> bool:
        messages = client.socket.messages()
        answers = letter_changes_in(messages) + errors_in(messages)
        return len(answers) >= count

    await wait_until_async(
        answers_received,
        f"the answer to edit number {count}",
        timeout=ANSWER_BUDGET_SECONDS,
    )


async def paced_edits_scenario(registry: RoomRegistry, code: str) -> PacedRun:
    """A joins, then sends 20 edits one at a time, each after the answer to the last.

    The edits are `paced_edit(0)` to `paced_edit(19)`. Before each one, A's socket
    must hold the answers to all the earlier ones (AC-6, second case).
    """
    ana = open_hub_client(registry, code, FakeSocket())
    you = (await join_hub_client(ana, "Ana")).you
    for index in range(PACED_EDIT_COUNT):
        ana.connection.submit(paced_edit(index))
        await wait_for_answers(ana, index + 1)
    await asyncio.sleep(SETTLE_SECONDS)  # anything unexpected still on its way
    return PacedRun(
        you=you,
        messages=ana.socket.messages(),
        close_codes=list(ana.socket.close_codes),
        letter_in_room=letter_in_state(registry.room_state(code), 1, 0),
    )
