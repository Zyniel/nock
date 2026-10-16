"""Tests of spec 038 (privacy and operations), AC-11: the server's relay time.

The hub test drives a registry on spec 036's blocking store (a `RoomStore(":memory:")`
whose `append` waits while it blocks), on an event loop of its own, as spec 036's
AC-6 does: Ana's first edit waits in `append`, her second waits in the room's
inbox, and the store is released after 300 ms. The Python tests call `tick`,
`after_restart` and `LogEntry` directly. The shared setup is in
`spec036_hub_harness` and `spec038_harness`.

This file measures durations (a store blocked for 300 ms against a bound of
250 ms), so it runs in the serial pass of the gate: it is listed in
`SERIAL_TEST_FILES` (`scripts/gate_browsers.py`).

Edge cases checked as well: Bob, a second client, receives no `relay_ms` either;
the hub's own tick and its `after_restart` when it loads a room log `relay_ms`
None; an entry stored before this spec (no `relay_ms` key) loads with None; and
`relay_ms` accepts 0 and refuses a float and a bool, being strict.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterator
from typing import NamedTuple

import pytest
from pydantic import ValidationError

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    Join,
    LetterChanged,
    PlayerJoined,
    PlayerState,
    PlayerStateChanged,
)
from nock.room import (
    LogEntry,
    RoomConfig,
    RoomState,
    after_restart,
    join_room,
    new_room,
    tick,
)
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec036_hub_harness import (
    BlockingStore,
    FakeSocket,
    join_hub_client,
    open_hub_client,
    open_registry,
    run_hub_scenario,
    wait_until_async,
)

# ---- Values of the spec --------------------------------------------------------------

BLOCK_SECONDS = 0.3  # the store is released 300 ms after it started blocking
FIRST_EDIT_LIMIT_MS = 250  # the first edit's relay_ms is below this
SECOND_EDIT_FLOOR_MS = 250  # the second's is at least this
RELAY_KEY = "relay_ms"

# ---- Values of the test harness ------------------------------------------------------

SETTLE_SECONDS = 0.3
ROOM_CODE = "RELAY1"
NOW = 1_800_000_000.0
TICK_SECONDS = 0.05


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def blocking_store() -> Iterator[BlockingStore]:
    store = BlockingStore()
    yield store
    store.release()
    store.close()


# ---- The hub scenario ----------------------------------------------------------------


class RelayRun(NamedTuple):
    """What the relay scenario logged and what its two clients received."""

    ana_id: str
    log: list[LogEntry]
    received_texts: list[str]


def letters_logged(log: list[LogEntry]) -> list[LogEntry]:
    """The `letter_changed` entries of a log, in seq order."""
    found: list[LogEntry] = []
    for entry in log:
        if isinstance(entry.event, LetterChanged):
            found.append(entry)
    return found


def disconnections_of(log: list[LogEntry], player_id: str) -> list[LogEntry]:
    """The `player_state_changed` entries to `disconnected` of one player."""
    found: list[LogEntry] = []
    for entry in log:
        event = entry.event
        if not isinstance(event, PlayerStateChanged):
            continue
        if event.player_id == player_id and event.state is PlayerState.DISCONNECTED:
            found.append(entry)
    return found


def join_of(log: list[LogEntry], player_id: str) -> LogEntry:
    """The `player_joined` entry of one player."""
    for entry in log:
        event = entry.event
        if isinstance(event, PlayerJoined) and event.player.player_id == player_id:
            return entry
    pytest.fail(f"no player_joined of {player_id} in the log")


async def relay_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> RelayRun:
    """AC-11's run: two edits of Ana while the store blocks for 300 ms.

    Ana then Bob join; once the steps of the joins are over, the store starts
    blocking; Ana submits T at (1, 0), whose step waits in `append`, then A at
    (1, 1); 300 ms later the store is released. Then Ana's socket closes.
    """
    ana = open_hub_client(registry, code, FakeSocket())
    ana_id = (await join_hub_client(ana, "Ana")).you
    bob = open_hub_client(registry, code, FakeSocket())
    await join_hub_client(bob, "Bob")
    await asyncio.sleep(SETTLE_SECONDS)  # the steps of the joins are over

    store.block()
    ana.connection.submit(EditLetter(row=1, column=0, letter="T"))
    await wait_until_async(store.append_waiting.is_set, "the first edit in append")
    ana.connection.submit(EditLetter(row=1, column=1, letter="A"))
    await asyncio.sleep(BLOCK_SECONDS)
    store.release()
    await wait_until_async(
        lambda: len(letters_logged(store.read_log(code))) >= 2, "both edits logged"
    )

    ana.connection.leave()  # what the socket handler does once the socket closed
    await wait_until_async(
        lambda: len(disconnections_of(store.read_log(code), ana_id)) >= 1,
        "Ana's disconnection logged",
    )
    await asyncio.sleep(SETTLE_SECONDS)  # anything still on its way
    received = list(ana.socket.texts) + list(bob.socket.texts)
    return RelayRun(ana_id=ana_id, log=store.read_log(code), received_texts=received)


@pytest.fixture
def relay_run(blocking_store: BlockingStore, fx01_grid: Grid) -> RelayRun:
    config = RoomConfig(max_edits_per_second=1000)
    with open_registry(config, blocking_store) as registry:
        code = registry.register_room(fx01_grid)
        return run_hub_scenario(relay_scenario(registry, blocking_store, code))


def keys_in(value: object) -> list[str]:
    """Every key of every object inside a parsed JSON value."""
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(keys_in(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(keys_in(child))
    return keys


# ---- AC-11: the relay time of each client step --------------------------------------


def test_ac11_the_first_edit_logs_a_relay_time_below_250_ms(
    relay_run: RelayRun,
) -> None:
    first, _ = letters_logged(relay_run.log)

    assert isinstance(first.event, LetterChanged)
    assert (first.event.row, first.event.column, first.event.letter) == (1, 0, "T")
    relay_ms = first.relay_ms
    assert isinstance(relay_ms, int), relay_ms
    assert 0 <= relay_ms < FIRST_EDIT_LIMIT_MS


def test_ac11_the_second_edit_logs_its_wait_in_the_inbox_at_least_250_ms(
    relay_run: RelayRun,
) -> None:
    _, second = letters_logged(relay_run.log)

    assert isinstance(second.event, LetterChanged)
    assert (second.event.row, second.event.column, second.event.letter) == (1, 1, "A")
    relay_ms = second.relay_ms
    assert isinstance(relay_ms, int), relay_ms
    assert relay_ms >= SECOND_EDIT_FLOOR_MS


def test_ac11_the_join_logs_an_integer_relay_time(relay_run: RelayRun) -> None:
    joined = join_of(relay_run.log, relay_run.ana_id)

    relay_ms = joined.relay_ms
    assert isinstance(relay_ms, int), relay_ms
    assert relay_ms >= 0


def test_ac11_the_disconnection_of_a_closed_socket_logs_no_relay_time(
    relay_run: RelayRun,
) -> None:
    disconnections = disconnections_of(relay_run.log, relay_run.ana_id)

    relay_times = [entry.relay_ms for entry in disconnections]
    assert relay_times == [None]


def test_ac11_no_message_the_clients_receive_holds_relay_ms(
    relay_run: RelayRun,
) -> None:
    keys_found: list[str] = []
    for text in relay_run.received_texts:
        if RELAY_KEY in keys_in(json.loads(text)):
            keys_found.append(text)

    assert len(relay_run.received_texts) > 0
    assert keys_found == []


# ---- AC-11: steps without a client message -------------------------------------------

# No tick disconnects a player for silence, so that a jump of the clock only makes
# Ana idle.
QUIET_CONFIG = RoomConfig(silence_timeout_seconds=1e9, tick_seconds=TICK_SECONDS)
IDLE_AFTER_SECONDS = RoomConfig().idle_after_seconds


def ana_joined(grid: Grid, now: float) -> tuple[RoomState, list[LogEntry]]:
    """A FX-01 room where Ana joined at `now`, and the entries of her join."""
    state = new_room(ROOM_CODE, grid, now)
    join = Join(nickname="Ana", resume_token=None)
    outcome = join_room(state, join, now, "p1", "token-of-ana-0001")
    return outcome.state, list(outcome.entries)


def test_ac11_the_entries_of_an_idle_change_by_tick_have_no_relay_time(
    fx01_grid: Grid,
) -> None:
    state, _ = ana_joined(fx01_grid, NOW)

    outcome = tick(state, NOW + IDLE_AFTER_SECONDS + 1, QUIET_CONFIG)

    events = [entry.event for entry in outcome.entries]
    idle = PlayerStateChanged(seq=2, player_id="p1", state=PlayerState.IDLE)
    assert events == [idle]
    assert [entry.relay_ms for entry in outcome.entries] == [None]


def test_ac11_the_entries_of_after_restart_have_no_relay_time(fx01_grid: Grid) -> None:
    state, _ = ana_joined(fx01_grid, NOW)

    outcome = after_restart(state, NOW + 10)

    events = [entry.event for entry in outcome.entries]
    gone = PlayerStateChanged(seq=2, player_id="p1", state=PlayerState.DISCONNECTED)
    assert events == [gone]
    assert [entry.relay_ms for entry in outcome.entries] == [None]


async def idle_scenario(
    registry: RoomRegistry, clock: FakeClock, code: str
) -> list[LogEntry]:
    """Ana joins; the clock jumps past the idle delay; the hub's tick logs it."""
    ana = open_hub_client(registry, code, FakeSocket())
    ana_id = (await join_hub_client(ana, "Ana")).you
    clock.advance(IDLE_AFTER_SECONDS + 1)

    def idle_logged() -> bool:
        for entry in registry.store.read_log(code):
            event = entry.event
            if isinstance(event, PlayerStateChanged) and event.player_id == ana_id:
                return event.state is PlayerState.IDLE
        return False

    await wait_until_async(idle_logged, "Ana's idle change, logged by a tick")
    ana.connection.leave()
    return registry.store.read_log(code)


def test_ac11_the_hubs_tick_logs_no_relay_time(
    fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    registry = RoomRegistry(clock=fake_clock, config=QUIET_CONFIG)
    try:
        code = registry.register_room(fx01_grid)
        log = run_hub_scenario(idle_scenario(registry, fake_clock, code))
    finally:
        registry.close()

    idle_entries: list[LogEntry] = []
    for entry in log:
        event = entry.event
        if isinstance(event, PlayerStateChanged) and event.state is PlayerState.IDLE:
            idle_entries.append(entry)
    assert [entry.relay_ms for entry in idle_entries] == [None]


def test_ac11_the_hubs_after_restart_step_logs_no_relay_time(fx01_grid: Grid) -> None:
    # Ana joined in an earlier process; loading the room disconnects her.
    store = RoomStore(":memory:")
    now = time.time()
    _, join_entries = ana_joined(fx01_grid, now)
    store.create_room(new_room(ROOM_CODE, fx01_grid, now))
    store.append(ROOM_CODE, join_entries)
    registry = RoomRegistry(store=store)
    try:
        assert registry.room_state(ROOM_CODE) is not None
        log = store.read_log(ROOM_CODE)
    finally:
        registry.close()
        store.close()

    restart_entries = log[len(join_entries) :]
    events = [entry.event for entry in restart_entries]
    gone = PlayerStateChanged(seq=2, player_id="p1", state=PlayerState.DISCONNECTED)
    assert events == [gone]
    assert [entry.relay_ms for entry in restart_entries] == [None]


# ---- AC-11: the field of LogEntry ----------------------------------------------------


def a_letter_changed() -> LetterChanged:
    return LetterChanged(
        seq=1, row=1, column=0, letter="T", pencil=False, player_id="p1"
    )


@pytest.mark.parametrize(
    ("relay_ms", "problem"),
    [
        pytest.param(-1, "greater_than_equal", id="minus-one"),
        pytest.param("5", "int_type", id="string"),
        # Edge cases: the field is strict, so a float or a bool is no integer.
        pytest.param(5.0, "int_type", id="float"),
        pytest.param(True, "int_type", id="bool"),
    ],
)
def test_ac11_a_log_entry_refuses_a_relay_time_that_is_no_whole_milliseconds(
    relay_ms: object, problem: str
) -> None:
    fields = {"at": NOW, "event": a_letter_changed(), "relay_ms": relay_ms}

    with pytest.raises(ValidationError) as caught:
        LogEntry.model_validate(fields)

    problems = [(error["loc"], error["type"]) for error in caught.value.errors()]
    assert problems == [((RELAY_KEY,), problem)]


def test_ac11_a_log_entry_refuses_a_relay_time_written_as_a_string_in_json() -> None:
    event = json.loads(a_letter_changed().model_dump_json())
    text = json.dumps({"at": NOW, "event": event, RELAY_KEY: "5"})

    with pytest.raises(ValidationError) as caught:
        LogEntry.model_validate_json(text)

    problems = [(error["loc"], error["type"]) for error in caught.value.errors()]
    assert problems == [((RELAY_KEY,), "int_type")]


def test_ac11_a_log_entry_has_no_relay_time_by_default() -> None:
    entry = LogEntry(at=NOW, event=a_letter_changed())

    assert entry.relay_ms is None


def test_ac11_an_entry_stored_before_this_spec_loads_with_no_relay_time() -> None:
    event = json.loads(a_letter_changed().model_dump_json())
    text = json.dumps({"at": NOW, "event": event, "resume_token": None, "undo": False})

    entry = LogEntry.model_validate_json(text)

    assert entry.relay_ms is None


def test_ac11_a_relay_time_of_zero_is_kept_through_json() -> None:
    entry = LogEntry.model_validate(
        {"at": NOW, "event": a_letter_changed(), RELAY_KEY: 0}
    )

    stored = LogEntry.model_validate_json(entry.model_dump_json())

    assert stored.relay_ms == 0


def test_ac11_a_relay_time_is_kept_through_the_store(fx01_grid: Grid) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        entry = LogEntry.model_validate(
            {"at": NOW, "event": a_letter_changed(), RELAY_KEY: 12}
        )
        store.append(ROOM_CODE, [entry])
        log = store.read_log(ROOM_CODE)
    finally:
        store.close()

    assert [stored.relay_ms for stored in log] == [12]
