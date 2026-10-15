"""Tests of spec 025, AC-9: an open vote survives a reconnection and a reload.

The rule on `snapshot_for`, `replay`, `after_restart` and `tick` (the room `V3`),
spec 018's store (a restart from a snapshot taken after a ballot, and one from the
log alone, decision 16), and the real WebSocket. The shared setup is in
`spec025_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    PlayerState,
    PlayerStateChanged,
    RevealBudget,
    RevealResult,
    Vote,
    VoteOutcome,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomState,
    after_restart,
    new_room,
    replay,
    snapshot_for,
    tick,
)
from nock.server import create_app
from nock.store import RoomStore
from spec025_harness import (
    NOW,
    QUIET,
    REVEAL_1_0,
    ROOM_CODE,
    VOTE_SETTINGS,
    Peer,
    Play,
    closed,
    events_of,
    grid_from_text,
    join_peer,
    last_vote_id_of,
    make_catalogue,
    make_dist_dir,
    make_registry,
    open_vote,
    open_vote_of,
    opened,
    set_vote_mode,
    v3,
    vote_room,
)

OPENED_AT = NOW + 7.0
OPENING = opened(5, 1, "p1", REVEAL_1_0, 3)
RESTART_AT = NOW + 5.0  # the store case of AC-9: vote 1 opened at NOW
V3_PLAYERS = ("p1", "p2", "p3")

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def store(tmp_path: Path) -> Iterator[RoomStore]:
    """The store of AC-9 (spec 018's harness)."""
    room_store = RoomStore(tmp_path / "nock.sqlite3")
    yield room_store
    room_store.close()


@pytest.fixture
def log_only_store(tmp_path: Path) -> Iterator[RoomStore]:
    """A second store, which never gets a snapshot after `create_room`."""
    room_store = RoomStore(tmp_path / "log-only.sqlite3")
    yield room_store
    room_store.close()


# ---- Helpers ----


class RecordedPlay(Play):
    """A `Play` whose every step appends its entries to stores, as the hub does."""

    def __init__(self, state: RoomState, stores: list[RoomStore]) -> None:
        super().__init__(state)
        self.stores = stores

    def apply(self, outcome: Outcome) -> Outcome:
        """Append the entries of one step to each store, then keep the step."""
        if len(outcome.entries) > 0:
            for room_store in self.stores:
                room_store.append(ROOM_CODE, outcome.entries)
        return super().apply(outcome)


def recorded_vote_1(grid: Grid, stores: list[RoomStore]) -> RecordedPlay:
    """`V3` and vote 1 (`p1`'s reveal of (1, 0) at NOW, seq 5), in each store.

    The room `new_room` gives is recorded with `create_room`, then each step of
    `V3` and of vote 1 appends its entries.
    """
    room = new_room(ROOM_CODE, grid, NOW)
    for room_store in stores:
        room_store.create_room(room)
    play = RecordedPlay(room, stores)
    for number in (1, 2, 3):
        play.join(number)
    assert play.send("p1", VOTE_SETTINGS).reply == ()
    assert play.state.seq == 4
    assert events_of(play.send("p1", REVEAL_1_0)) == [OPENING]
    return play


def cast_no_of_p2(play: Play) -> None:
    """`p2`'s `Vote(vote_id=1, yes=False)` at NOW + 1, which adds no entry."""
    ballot = play.send("p2", Vote(vote_id=1, yes=False), NOW + 1.0)
    assert ballot.entries == ()
    live_vote = open_vote_of(play.state)
    assert live_vote is not None
    assert live_vote.no == ("p2",)


def loaded(room_store: RoomStore) -> RoomState:
    """`load_room` of the room of AC-9."""
    state = room_store.load_room(ROOM_CODE)
    assert state is not None, "the store lost the room"
    return state


def with_vote_1(grid: Grid) -> Play:
    """`V3` after `p1`'s reveal of (1, 0) opened vote 1 (seq 5) at OPENED_AT."""
    play = v3(grid)
    assert events_of(play.send("p1", REVEAL_1_0, OPENED_AT)) == [OPENING]
    return play


def replayed(grid: Grid, entries: list[LogEntry]) -> RoomState:
    """The room rebuilt from `new_room` and the given log entries."""
    state = new_room(ROOM_CODE, grid, NOW)
    for entry in entries:
        state = replay(state, entry)
    return state


# ---- AC-9: the rule ----


def test_ac9_snapshot_for_sends_the_event_that_opened_the_vote(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1(fx01_grid)

    assert snapshot_for(play.state, "p2").open_vote == OPENING
    assert snapshot_for(play.state, "p1").open_vote == OPENING


def test_ac9_snapshot_for_sends_no_vote_once_it_closed(fx01_grid: Grid) -> None:
    play = with_vote_1(fx01_grid)
    play.send("p2", Vote(vote_id=1, yes=False))
    play.send("p3", Vote(vote_id=1, yes=False))
    assert open_vote_of(play.state) is None

    assert snapshot_for(play.state, "p2").open_vote is None


def test_ac9_replaying_the_log_rebuilds_the_open_vote_with_the_requesters_yes(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1(fx01_grid)
    assert play.entries[-1].at == OPENED_AT

    state = replayed(fx01_grid, play.entries)

    expected = open_vote(OPENING, OPENED_AT, ("p1", "p2", "p3"), ("p1",))
    assert open_vote_of(state) == expected
    assert last_vote_id_of(state) == 1
    assert state.seq == 5


def test_ac9_replaying_a_vote_closed_clears_the_open_vote(fx01_grid: Grid) -> None:
    play = with_vote_1(fx01_grid)
    play.send("p2", Vote(vote_id=1, yes=False))
    closing = play.send("p3", Vote(vote_id=1, yes=False))
    assert events_of(closing) == [closed(6, 1, VoteOutcome.REJECTED, 1, 3)]

    state = replayed(fx01_grid, play.entries)

    assert open_vote_of(state) is None
    assert last_vote_id_of(state) == 1
    assert state.seq == 6


def test_ac9_a_ballot_cast_before_the_reload_is_not_restored(fx01_grid: Grid) -> None:
    play = with_vote_1(fx01_grid)
    ballot = play.send("p2", Vote(vote_id=1, yes=False))
    assert ballot.entries == ()
    live_vote = open_vote_of(play.state)
    assert live_vote is not None
    assert live_vote.no == ("p2",)

    state = replayed(fx01_grid, play.entries)

    expected = open_vote(OPENING, OPENED_AT, ("p1", "p2", "p3"), ("p1",))
    assert open_vote_of(state) == expected


def test_ac9_replay_leaves_out_the_players_disconnected_before_the_opening(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.disconnect("p3", NOW + 1.0)
    opening = play.send("p1", REVEAL_1_0, OPENED_AT)
    expected_event = opened(6, 1, "p1", REVEAL_1_0, 2)
    assert events_of(opening) == [expected_event]

    state = replayed(fx01_grid, play.entries)

    expected = open_vote(expected_event, OPENED_AT, ("p1", "p2"), ("p1",))
    assert open_vote_of(state) == expected
    assert open_vote_of(play.state) == expected


def test_ac9_a_vote_open_at_a_restart_stays_open_and_expires_at_its_time(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1(fx01_grid)
    state = replayed(fx01_grid, play.entries)
    vote = open_vote_of(state)

    restart = after_restart(state, NOW + 10.0)

    assert [type(event) for event in events_of(restart)] == [PlayerStateChanged] * 3
    assert open_vote_of(restart.state) == vote
    early = tick(restart.state, OPENED_AT + 19.9, QUIET)
    assert early.entries == ()
    due = tick(early.state, OPENED_AT + 20.0, QUIET)
    assert events_of(due) == [closed(9, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    assert open_vote_of(due.state) is None


def test_ac9_after_restart_resets_a_yes_ballot_and_the_vote_expires_with_one_yes(
    fx01_grid: Grid,
) -> None:
    play = vote_room(fx01_grid, 4)
    opening = opened(6, 1, "p1", REVEAL_1_0, 4)
    assert events_of(play.send("p1", REVEAL_1_0, OPENED_AT)) == [opening]
    assert play.send("p2", Vote(vote_id=1, yes=True), OPENED_AT + 1.0).entries == ()
    live_vote = open_vote_of(play.state)
    assert live_vote is not None
    assert live_vote.yes == ("p1", "p2")

    restart = after_restart(play.state, OPENED_AT + 5.0)

    # The reset adds no entry: only spec 018's disconnections are logged.
    assert events_of(restart) == [
        PlayerStateChanged(seq=7, player_id="p1", state=PlayerState.DISCONNECTED),
        PlayerStateChanged(seq=8, player_id="p2", state=PlayerState.DISCONNECTED),
        PlayerStateChanged(seq=9, player_id="p3", state=PlayerState.DISCONNECTED),
        PlayerStateChanged(seq=10, player_id="p4", state=PlayerState.DISCONNECTED),
    ]
    eligible = ("p1", "p2", "p3", "p4")
    expected = open_vote(opening, OPENED_AT, eligible, ("p1",))
    assert open_vote_of(restart.state) == expected
    assert last_vote_id_of(restart.state) == 1
    due = tick(restart.state, OPENED_AT + 20.0, QUIET)
    assert events_of(due) == [closed(11, 1, VoteOutcome.TIMED_OUT, 1, 4)]


# ---- AC-9: the store (decision 16) ----


def test_ac9_store_a_snapshot_saved_after_a_ballot_loads_with_that_ballot(
    fx01_grid: Grid, store: RoomStore
) -> None:
    play = recorded_vote_1(fx01_grid, [store])
    cast_no_of_p2(play)

    store.save_snapshot(play.state)

    loaded_vote = open_vote_of(loaded(store))
    assert loaded_vote is not None
    assert loaded_vote.no == ("p2",)


def test_ac9_store_after_restart_resets_the_ballots_that_a_snapshot_brought_back(
    fx01_grid: Grid, store: RoomStore
) -> None:
    play = recorded_vote_1(fx01_grid, [store])
    cast_no_of_p2(play)
    store.save_snapshot(play.state)
    state = loaded(store)

    restart = after_restart(state, RESTART_AT)

    restarted_vote = open_vote_of(restart.state)
    assert restarted_vote is not None
    assert restarted_vote.no == ()
    assert restarted_vote.yes == ("p1",)
    assert restarted_vote == open_vote(OPENING, NOW, V3_PLAYERS, ("p1",))
    assert last_vote_id_of(restart.state) == 1


def test_ac9_store_a_snapshot_load_and_a_log_only_load_give_the_same_vote(
    fx01_grid: Grid, store: RoomStore, log_only_store: RoomStore
) -> None:
    play = recorded_vote_1(fx01_grid, [store, log_only_store])
    cast_no_of_p2(play)
    store.save_snapshot(play.state)

    from_snapshot = after_restart(loaded(store), RESTART_AT).state
    from_log = after_restart(loaded(log_only_store), RESTART_AT).state

    assert open_vote_of(from_log) == open_vote(OPENING, NOW, V3_PLAYERS, ("p1",))
    assert open_vote_of(from_snapshot) == open_vote_of(from_log)
    assert last_vote_id_of(from_log) == 1
    assert last_vote_id_of(from_snapshot) == last_vote_id_of(from_log)


def test_ac9_store_a_vote_restored_from_a_snapshot_expires_at_its_time(
    fx01_grid: Grid, store: RoomStore
) -> None:
    play = recorded_vote_1(fx01_grid, [store])
    cast_no_of_p2(play)
    store.save_snapshot(play.state)
    restart = after_restart(loaded(store), RESTART_AT)
    assert restart.state.seq == 8

    early = tick(restart.state, NOW + 19.9, QUIET)
    due = tick(early.state, NOW + 20.0, QUIET)

    assert early.entries == ()
    assert events_of(due) == [closed(9, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    assert open_vote_of(due.state) is None


# ---- AC-9: WebSocket ----


def is_disconnected_event(peer: Peer, player_id: str) -> bool:
    for message in peer.after_snapshot():
        if (
            isinstance(message, PlayerStateChanged)
            and message.player_id == player_id
            and message.state is PlayerState.DISCONNECTED
        ):
            return True
    return False


def test_ac9_websocket_a_voter_who_reconnects_gets_the_open_vote_and_can_vote(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as bob_stack:
        ana = join_peer(stack, client, room_code, "Ana")
        bob = join_peer(bob_stack, client, room_code, "Bob")
        cy = join_peer(stack, client, room_code, "Cy")
        for peer in (ana, bob, cy):
            peer.wait_for_seq(3, "every player_joined event")
        set_vote_mode(ana, [ana, bob, cy])
        ana.send(REVEAL_1_0)
        for peer in (ana, bob, cy):
            peer.wait_for_seq(5, "the vote_opened")
        token = bob.snapshot().resume_token
        bob_id = bob.you()

        bob_stack.close()
        ana.wait_until(
            lambda: is_disconnected_event(ana, bob_id), "Bob's disconnection"
        )
        bob_again = join_peer(stack, client, room_code, "Bob", resume_token=token)

        snapshot = bob_again.snapshot()
        assert snapshot.you == bob_id
        assert snapshot.open_vote == opened(5, 1, ana.you(), REVEAL_1_0, 3)

        bob_again.send(Vote(vote_id=1, yes=True))

        first_seq = snapshot.seq + 1
        expected = [
            closed(first_seq, 1, VoteOutcome.PASSED, 2, 3),
            RevealResult(
                seq=first_seq + 1,
                player_id=ana.you(),
                target=CellTarget(row=1, column=0),
                reveal_budget=RevealBudget(letters=4, words=1),
            ),
            CellLocked(seq=first_seq + 2, row=1, column=0, letter="T", revealed=True),
        ]
        for peer in (ana, cy, bob_again):
            peer.wait_for_seq(first_seq + 2, "the end of the vote and the reveal")
            assert peer.numbered_from(first_seq) == expected
            assert peer.errors() == []
