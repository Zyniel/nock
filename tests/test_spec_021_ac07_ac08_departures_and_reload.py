"""Tests of spec 021, AC-7 and AC-8: a player who leaves takes their flag; flags
survive a reload and a server restart.

AC-7 on the rules (a removal, a disconnection kept through spec 017's resume
window, a time-out), on the real WebSocket with spec 011's fake clock, and on the
page with a mocked socket. AC-8 on `replay`, on a `RoomStore` (from the log alone,
and from a saved snapshot), after `after_restart`, and on the page: a later
snapshot replaces the kept flags (the edge case "Snapshot after a reconnection").
The shared setup is in `spec021_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClueRef,
    Flag,
    FlagChanged,
    FlagView,
    Join,
    LeaveReason,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    RemovePlayer,
    grid_view,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    after_restart,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    replay,
    tick,
)
from nock.server import create_app
from nock.store import RoomStore
from spec013_harness import FakeClock
from spec021_harness import (
    IDES,
    MIME,
    SENT,
    accepted_flag,
    expect_marker,
    expect_unflagged,
    expected_flagged_map,
    flag_changes,
    flag_of,
    flagged_map,
    flags_by_player,
    open_flag_room,
    snapshot_flags,
    snapshot_with_flags,
    three_players,
)
from spec024_harness import (
    FIRST_TOKEN,
    NOW,
    ROOM_CODE,
    SECOND_TOKEN,
    Peer,
    events_of,
    expect_seq,
    grid_from_text,
    join_one,
    make_catalogue,
    make_dist_dir,
    player_record,
    two_player_room,
)

QUIET = RoomConfig(silence_timeout_seconds=3600)
CLOCK_CONFIG = RoomConfig(
    max_edits_per_second=1000, tick_seconds=0.05, silence_timeout_seconds=3600
)
RESUME_WINDOW_SECONDS = 300
# The play of AC-8 after the two joins: who sends which `Flag`.
FLAG_STEPS: list[tuple[str, ClueRef | None]] = [
    ("p2", IDES),
    ("p1", MIME),
    ("p1", None),
    ("p2", SENT),
]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def clock_registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on the fake clock, ticking every 0.05 s, with no silence time-out."""
    room_registry = RoomRegistry(clock=fake_clock, config=CLOCK_CONFIG)
    yield room_registry
    room_registry.close()


@pytest.fixture
def clock_client(
    clock_registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient on an app serving `clock_registry`."""
    app = create_app(rooms=clock_registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- Helpers ----


def ides_flagged_by_p2(grid: Grid) -> RoomState:
    """The two-player room where `p2` flagged IDES (seq 3)."""
    state = accepted_flag(two_player_room(grid), "p2", IDES).state
    assert state.seq == 3
    return state


def flag_changes_of(events: list[object]) -> list[object]:
    """The `flag_changed` events among a step's events."""
    found: list[object] = []
    for event in events:
        if isinstance(event, FlagChanged):
            found.append(event)
    return found


def has_disconnected(peer: Peer, player_id: str) -> bool:
    """Whether a client saw a player become disconnected."""
    for message in peer.messages():
        if (
            isinstance(message, PlayerStateChanged)
            and message.player_id == player_id
            and message.state is PlayerState.DISCONNECTED
        ):
            return True
    return False


def has_left(peer: Peer, player_id: str) -> bool:
    """Whether a client saw a player leave the room."""
    for message in peer.messages():
        if isinstance(message, PlayerLeft) and message.player_id == player_id:
            return True
    return False


def the_play(grid: Grid) -> list[Outcome]:
    """AC-8's play from `new_room`: the joins of `p1` and `p2`, then FLAG_STEPS.

    Returns:
        The outcome of each step, in order.
    """
    state = new_room(ROOM_CODE, grid, NOW)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    outcomes = [first, second]
    current = second.state
    for player_id, clue in FLAG_STEPS:
        outcome = accepted_flag(current, player_id, clue)
        outcomes.append(outcome)
        current = outcome.state
    return outcomes


def store_the_play(path: Path, grid: Grid, save_last_state: bool) -> None:
    """Create the room in a `RoomStore` and append every entry of the play.

    Args:
        path: The store's file.
        grid: FX-01.
        save_last_state: Also save the live state after the play as a snapshot.
    """
    outcomes = the_play(grid)
    store = RoomStore(path)
    try:
        store.create_room(new_room(ROOM_CODE, grid, NOW))
        for outcome in outcomes:
            store.append(ROOM_CODE, outcome.entries)
        if save_last_state:
            store.save_snapshot(outcomes[-1].state)
    finally:
        store.close()


def load_from(path: Path) -> RoomState:
    """Load room ROOM_CODE from the store file at `path`, in a new store."""
    reopened = RoomStore(path)
    try:
        loaded = reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()
    assert loaded is not None
    return loaded


# ---- AC-7, rule ----


def test_ac7_removing_a_flagger_writes_only_player_left_and_drops_the_flag(
    fx01_grid: Grid,
) -> None:
    state = ides_flagged_by_p2(fx01_grid)

    outcome = handle_message(state, "p1", RemovePlayer(player_id="p2"), NOW)

    assert events_of(outcome) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert snapshot_flags(outcome.state) == ()


def test_ac7_a_disconnected_flagger_keeps_the_flag_through_the_resume_window(
    fx01_grid: Grid,
) -> None:
    state = ides_flagged_by_p2(fx01_grid)

    disconnected = disconnect_player(state, "p2", NOW).state
    still_waiting = tick(disconnected, NOW + RESUME_WINDOW_SECONDS, QUIET).state

    assert player_record(disconnected, "p2").state is PlayerState.DISCONNECTED
    assert flag_of(disconnected, "p2") == IDES
    assert snapshot_flags(disconnected) == (FlagView(player_id="p2", clue=IDES),)
    assert snapshot_flags(still_waiting) == (FlagView(player_id="p2", clue=IDES),)


def test_ac7_a_flagger_who_times_out_leaves_with_the_flag_and_no_flag_changed(
    fx01_grid: Grid,
) -> None:
    disconnected = disconnect_player(ides_flagged_by_p2(fx01_grid), "p2", NOW).state
    assert disconnected.seq == 4

    outcome = tick(disconnected, NOW + RESUME_WINDOW_SECONDS + 1, QUIET)

    events = events_of(outcome)
    assert PlayerLeft(seq=5, player_id="p2", reason=LeaveReason.TIMED_OUT) in events
    assert flag_changes_of(events) == []
    assert snapshot_flags(outcome.state) == ()


# ---- AC-7, WebSocket with a fake clock ----


def test_ac7_websocket_a_late_joiner_gets_no_flag_of_a_timed_out_player(
    clock_client: TestClient,
    clock_registry: RoomRegistry,
    fx01_grid: Grid,
    fake_clock: FakeClock,
) -> None:
    code = clock_registry.register_room(fx01_grid)
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as bob_stack:
        ana = join_one(stack, clock_client, code, "Ana")
        bob = join_one(bob_stack, clock_client, code, "Bob")
        ana.wait_for_seq(2, "Bob's join on Ana")
        bob_id = bob.you()
        bob.send(Flag(clue=IDES))
        ana.wait_for_seq(3, "Bob's flag on Ana")
        assert flag_changes(ana) == [FlagChanged(seq=3, player_id=bob_id, clue=IDES)]

        bob_stack.close()
        ana.wait_until(lambda: has_disconnected(ana, bob_id), "Bob's disconnection")
        fake_clock.advance(RESUME_WINDOW_SECONDS + 1)
        ana.wait_until(lambda: has_left(ana, bob_id), "Bob's time-out on Ana")

        cy = join_one(stack, clock_client, code, "Cy")
        snapshot = cy.snapshot()
        player_ids = [player.player_id for player in snapshot.players]
        assert bob_id not in player_ids
        assert snapshot.flags == ()
        assert flag_changes(ana) == [FlagChanged(seq=3, player_id=bob_id, clue=IDES)]


# ---- AC-7, page with a mocked socket ----


def test_ac7_browser_a_flagger_who_leaves_takes_the_marker_away(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    ides_flag = FlagView(player_id="p2", clue=IDES)
    mock = open_flag_room(page, live_server, grid_view(fx01_grid), flags=[ides_flag])
    expect_marker(page, IDES, "p2", ["Bob"])

    left = PlayerLeft(seq=6, player_id="p2", reason=LeaveReason.TIMED_OUT)
    mock.send(left.model_dump_json())

    expect_seq(page, 6)
    expect_unflagged(page, IDES)
    assert flagged_map(page) == expected_flagged_map([])


# ---- AC-8, replay ----


def test_ac8_the_play_logs_one_flag_changed_per_flag_step(fx01_grid: Grid) -> None:
    flag_events: list[object] = []
    for outcome in the_play(fx01_grid)[2:]:
        flag_events.extend(events_of(outcome))

    assert flag_events == [
        FlagChanged(seq=3, player_id="p2", clue=IDES),
        FlagChanged(seq=4, player_id="p1", clue=MIME),
        FlagChanged(seq=5, player_id="p1", clue=None),
        FlagChanged(seq=6, player_id="p2", clue=SENT),
    ]


def test_ac8_replay_gives_each_player_the_live_flag_after_every_step(
    fx01_grid: Grid,
) -> None:
    replayed = new_room(ROOM_CODE, fx01_grid, NOW)

    for number, outcome in enumerate(the_play(fx01_grid)):
        for entry in outcome.entries:
            replayed = replay(replayed, entry)
        assert flags_by_player(replayed) == flags_by_player(outcome.state), number

    assert flags_by_player(replayed) == {"p1": None, "p2": SENT}


def test_ac8_replaying_a_flag_of_a_player_not_in_the_room_changes_only_the_seq(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    entry = LogEntry(at=NOW, event=FlagChanged(seq=3, player_id="p9", clue=IDES))

    assert replay(state, entry) == state.model_copy(update={"seq": 3})


# ---- AC-8, RoomStore and restart ----


def test_ac8_a_room_loaded_from_its_log_keeps_the_flags_after_a_restart(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    path = tmp_path / "rooms.sqlite3"
    store_the_play(path, fx01_grid, save_last_state=False)

    loaded = load_from(path)
    restarted = after_restart(loaded, NOW + 60).state

    expected = (FlagView(player_id="p2", clue=SENT),)
    assert snapshot_flags(loaded) == expected
    for player in restarted.players:
        assert player.state is PlayerState.DISCONNECTED
    assert snapshot_flags(restarted) == expected


def test_ac8_a_room_loaded_from_a_saved_snapshot_keeps_the_flags(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    path = tmp_path / "rooms.sqlite3"
    store_the_play(path, fx01_grid, save_last_state=True)

    loaded = load_from(path)

    assert flags_by_player(loaded) == {"p1": None, "p2": SENT}
    assert snapshot_flags(loaded) == (FlagView(player_id="p2", clue=SENT),)


# ---- AC-8, page: a later snapshot replaces the kept flags ----


def test_ac8_browser_a_new_snapshot_replaces_the_kept_flags(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = grid_view(fx01_grid)
    ides_flag = FlagView(player_id="p2", clue=IDES)
    mock = open_flag_room(page, live_server, view, flags=[ides_flag])
    expect_marker(page, IDES, "p2", ["Bob"])
    sent_flags = [
        FlagView(player_id="p2", clue=SENT),
        FlagView(player_id="p3", clue=SENT),
    ]

    second = snapshot_with_flags(view, 9, three_players(), sent_flags)
    mock.send(second.model_dump_json())

    expect_seq(page, 9)
    expect_unflagged(page, IDES)
    expect_marker(page, SENT, "p2 p3", ["Bob", "Cy"])
    assert flagged_map(page) == expected_flagged_map([SENT])
