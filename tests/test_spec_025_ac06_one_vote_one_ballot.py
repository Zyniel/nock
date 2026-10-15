"""Tests of spec 025, AC-6: one vote at a time, and one ballot per eligible player.

The rule on `handle_message` (the room `V3` with vote 1 open, `p1`'s reveal of
(1, 0)) and the real WebSocket. A ballot is input and is not an edit (the edge
cases of the spec). The shared setup is in `spec025_harness`.
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
    CheckResult,
    ClientMessage,
    Direction,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    GridTarget,
    LetterChanged,
    PlayerState,
    PlayerStateChanged,
    Reveal,
    RevealBudget,
    RevealResult,
    SelectCell,
    Vote,
    VoteOutcome,
    WordTarget,
)
from nock.room import RoomConfig
from nock.server import create_app
from spec025_harness import (
    GRID_CHECK,
    NOW,
    REVEAL_1_0,
    Play,
    closed,
    events_of,
    grid_from_text,
    join_peers,
    last_vote_id_of,
    make_catalogue,
    make_dist_dir,
    make_registry,
    open_vote_of,
    opened,
    refusal_code,
    seen_at,
    set_vote_mode,
    v3,
    vote_room,
)

LATER = NOW + 3.0

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


def with_vote_1_open(grid: Grid) -> Play:
    """`V3` with vote 1 open: `p1`'s reveal of (1, 0) at NOW (seq 5)."""
    play = v3(grid)
    assert events_of(play.send("p1", REVEAL_1_0)) == [opened(5, 1, "p1", REVEAL_1_0, 3)]
    return play


# ---- AC-6: one vote at a time ----


@pytest.mark.parametrize(
    ("sender", "message"),
    [
        ("p2", GRID_CHECK),
        ("p3", Reveal(target=WordTarget(row=0, column=2, clue_index=0))),
    ],
    ids=["grid-check", "word-reveal"],
)
def test_ac6_a_request_that_needs_a_vote_during_a_vote_is_vote_in_progress(
    fx01_grid: Grid, sender: str, message: ClientMessage
) -> None:
    play = with_vote_1_open(fx01_grid)
    before = play.state

    outcome = play.send(sender, message, LATER)

    assert refusal_code(outcome) is ErrorCode.VOTE_IN_PROGRESS
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, sender, LATER)


def test_ac6_a_ballot_for_another_vote_id_is_no_open_vote(fx01_grid: Grid) -> None:
    play = with_vote_1_open(fx01_grid)
    before = play.state

    outcome = play.send("p2", Vote(vote_id=2, yes=True), LATER)

    assert refusal_code(outcome) is ErrorCode.NO_OPEN_VOTE
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", LATER)


def test_ac6_a_ballot_with_no_vote_open_is_no_open_vote(fx01_grid: Grid) -> None:
    play = v3(fx01_grid)
    before = play.state

    outcome = play.send("p2", Vote(vote_id=1, yes=True), LATER)

    assert refusal_code(outcome) is ErrorCode.NO_OPEN_VOTE
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", LATER)


# ---- AC-6: one ballot per eligible player ----


def test_ac6_the_requesters_own_ballot_changes_nothing(fx01_grid: Grid) -> None:
    play = with_vote_1_open(fx01_grid)
    vote = open_vote_of(play.state)

    outcome = play.send("p1", Vote(vote_id=1, yes=False), LATER)

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert open_vote_of(play.state) == vote
    assert vote is not None
    assert vote.yes == ("p1",)
    assert vote.no == ()


def test_ac6_a_second_ballot_of_the_same_player_changes_nothing(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1_open(fx01_grid)
    first = play.send("p2", Vote(vote_id=1, yes=False))
    assert first.entries == ()
    assert first.reply == ()
    after_first = open_vote_of(play.state)

    second = play.send("p2", Vote(vote_id=1, yes=True), LATER)

    assert second.entries == ()
    assert second.reply == ()
    assert open_vote_of(play.state) == after_first
    assert after_first is not None
    assert after_first.yes == ("p1",)
    assert after_first.no == ("p2",)


def test_ac6_a_player_who_joined_after_the_opening_is_not_eligible(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1_open(fx01_grid)
    play.join(4)
    assert play.state.seq == 6
    vote = open_vote_of(play.state)

    outcome = play.send("p4", Vote(vote_id=1, yes=True), LATER)

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert open_vote_of(play.state) == vote
    assert vote is not None
    assert vote.eligible == ("p1", "p2", "p3")
    assert vote.yes == ("p1",)


def test_ac6_once_closed_the_old_vote_is_no_open_vote_and_a_request_opens_vote_2(
    fx01_grid: Grid,
) -> None:
    play = with_vote_1_open(fx01_grid)
    play.send("p2", Vote(vote_id=1, yes=False))
    closing = play.send("p3", Vote(vote_id=1, yes=False))
    assert events_of(closing) == [closed(6, 1, VoteOutcome.REJECTED, 1, 3)]
    before = play.state

    late = play.send("p2", Vote(vote_id=1, yes=True), LATER)

    assert refusal_code(late) is ErrorCode.NO_OPEN_VOTE
    assert late.entries == ()
    assert late.state == seen_at(before, "p2", LATER)

    request = Reveal(target=CellTarget(row=2, column=1))
    reopening = play.send("p2", request, LATER)

    assert events_of(reopening) == [opened(7, 2, "p2", request, 3)]
    assert last_vote_id_of(play.state) == 2


# ---- AC-6: a requester alone among connected players ----


def alone_in_vote_mode(grid: Grid) -> Play:
    """A FX-01 room in vote mode with `p1` and `p2`, where `p2` is disconnected."""
    play = vote_room(grid, 2)
    disconnection = play.disconnect("p2")
    assert events_of(disconnection) == [
        PlayerStateChanged(seq=4, player_id="p2", state=PlayerState.DISCONNECTED)
    ]
    return play


def test_ac6_a_requester_alone_gets_the_reveal_at_once_with_no_vote(
    fx01_grid: Grid,
) -> None:
    play = alone_in_vote_mode(fx01_grid)

    outcome = play.send("p1", REVEAL_1_0)

    assert events_of(outcome) == [
        RevealResult(
            seq=5,
            player_id="p1",
            target=CellTarget(row=1, column=0),
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=6, row=1, column=0, letter="T", revealed=True),
    ]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    assert last_vote_id_of(play.state) == 0


def test_ac6_a_requester_alone_gets_the_grid_check_at_once_with_no_vote(
    fx01_grid: Grid,
) -> None:
    play = alone_in_vote_mode(fx01_grid)

    outcome = play.send("p1", GRID_CHECK)

    assert events_of(outcome) == [
        CheckResult(seq=5, player_id="p1", target=GridTarget(), correct=(), wrong=())
    ]
    assert open_vote_of(play.state) is None


# ---- AC-6: a ballot is input, not an edit ----


def test_ac6_a_ballot_is_input_and_wakes_an_idle_voter_first(fx01_grid: Grid) -> None:
    play = v3(fx01_grid)
    select = SelectCell(row=1, column=0, direction=Direction.ACROSS)
    play.send("p1", select, NOW + 100.0)
    opening = play.send("p1", REVEAL_1_0, NOW + 110.0)
    assert events_of(opening) == [opened(5, 1, "p1", REVEAL_1_0, 3)]
    play.tick(NOW + 120.0)
    states = [player.state for player in play.state.players]
    assert states == [PlayerState.ACTIVE, PlayerState.IDLE, PlayerState.IDLE]
    assert play.state.seq == 7

    outcome = play.send("p2", Vote(vote_id=1, yes=True), NOW + 121.0)

    events = events_of(outcome)
    assert events[:2] == [
        PlayerStateChanged(seq=8, player_id="p2", state=PlayerState.ACTIVE),
        closed(9, 1, VoteOutcome.PASSED, 2, 3),
    ]
    assert [type(event) for event in events[2:]] == [RevealResult, CellLocked]


def test_ac6_neither_a_ballot_nor_a_request_counts_against_the_edit_rate_limit(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    one_edit = RoomConfig(silence_timeout_seconds=600, max_edits_per_second=1)
    at = NOW + 1.0

    opening = play.send("p1", REVEAL_1_0, at, one_edit)
    edit_after_request = play.send(
        "p1", EditLetter(row=2, column=1, letter="V"), at, one_edit
    )
    edit_before_ballot = play.send(
        "p2", EditLetter(row=2, column=2, letter="I"), at, one_edit
    )
    ballot = play.send("p2", Vote(vote_id=1, yes=True), at, one_edit)

    assert events_of(opening) == [opened(5, 1, "p1", REVEAL_1_0, 3)]
    assert [type(event) for event in events_of(edit_after_request)] == [LetterChanged]
    assert [type(event) for event in events_of(edit_before_ballot)] == [LetterChanged]
    assert ballot.reply == ()
    assert events_of(ballot)[0] == closed(8, 1, VoteOutcome.PASSED, 2, 3)


# ---- AC-6: WebSocket ----


def test_ac6_websocket_a_refusal_reaches_its_sender_only(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, cy = peers
        set_vote_mode(ana, peers)
        ana.send(REVEAL_1_0)
        for peer in peers:
            peer.wait_for_seq(5, "the vote_opened")

        bob.send(GRID_CHECK)
        bob.wait_until(lambda: len(bob.errors()) == 1, "Bob's refusal")
        cy.send(Vote(vote_id=2, yes=True))
        cy.wait_until(lambda: len(cy.errors()) == 1, "Cy's refusal")
        ana.send(EditLetter(row=2, column=1, letter="V"))
        for peer in peers:
            peer.wait_for_seq(6, "Ana's letter")

        tail_of_ana = ana.after_snapshot()[-2:]
        assert [message.type for message in tail_of_ana] == [
            "vote_opened",
            "letter_changed",
        ]
        bob_tail = bob.after_snapshot()[-3:]
        assert [message.type for message in bob_tail] == [
            "vote_opened",
            "error",
            "letter_changed",
        ]
        assert isinstance(bob_tail[1], ErrorMessage)
        assert bob_tail[1].code is ErrorCode.VOTE_IN_PROGRESS
        cy_tail = cy.after_snapshot()[-3:]
        assert [message.type for message in cy_tail] == [
            "vote_opened",
            "error",
            "letter_changed",
        ]
        assert isinstance(cy_tail[1], ErrorMessage)
        assert cy_tail[1].code is ErrorCode.NO_OPEN_VOTE
