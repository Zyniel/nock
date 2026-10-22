"""Tests of spec 025, AC-3: a vote that fails or times out changes nothing.

The rule on `handle_message` and `tick` (the room `V3`), the real WebSocket with a
fake clock, and the page with a mocked socket. A vote that passes when its request
can no longer apply also closes `rejected` (the edge cases of the spec). The shared
setup is in `spec025_harness`.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    ChangeSettings,
    Check,
    CheckResult,
    Direction,
    EditLetter,
    ErrorCode,
    HelpMode,
    HostChanged,
    PlayerState,
    PlayerStateChanged,
    Reveal,
    RevealBudget,
    RevealResult,
    SelectCell,
    Vote,
    VoteClosed,
    VoteOutcome,
)
from nock.room import CellState, RoomConfig, RoomState
from nock.server import create_app
from spec025_harness import (
    FIVE_AND_ONE,
    NOW,
    REVEAL_1_0,
    VOTE_RESULT_MAX_SECONDS,
    VOTE_RESULT_MIN_SECONDS,
    FakeClock,
    Peer,
    Play,
    all_but_last_cell,
    cell_at,
    closed,
    config_with_vote_timeout,
    events_of,
    fr_text,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    open_room,
    open_vote_of,
    opened,
    refusal_code,
    seconds_until_hidden,
    set_vote_mode,
    v3,
    vote_room,
    with_times_of,
    write,
)

WS_DETECTION_SECONDS = 1.0  # "within 1 second of real time"
SETTLE_SECONDS = 0.3

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


# ---- Helpers ----


def cell_1_0(state: RoomState) -> CellState:
    """The room's state of the cell (1, 0)."""
    for cell in state.cells:
        if (cell.row, cell.column) == (1, 0):
            return cell
    pytest.fail("no letter cell at (1, 0)")


def opened_reveal_vote(grid: Grid) -> Play:
    """`V3` after `p1`'s reveal of (1, 0) opened vote 1 (seq 5) at NOW."""
    play = v3(grid)
    outcome = play.send("p1", REVEAL_1_0)
    assert events_of(outcome) == [opened(5, 1, "p1", REVEAL_1_0, 3)]
    return play


def vote_among_idle_players(grid: Grid) -> Play:
    """`V3` where `p2` and `p3` went idle, then vote 1 opened at NOW + 121.

    `p1` wrote `X` at (1, 1) at NOW + 100 (seq 5), the tick at NOW + 120 made `p2`
    and `p3` idle (seq 6 and 7), and `p1`'s reveal of (1, 0) at NOW + 121 opened
    vote 1 (seq 8), which expires at NOW + 141.
    """
    play = v3(grid)
    play.send("p1", EditLetter(row=1, column=1, letter="X"), NOW + 100.0)
    play.tick(NOW + 120.0)
    states = [player.state for player in play.state.players]
    assert states == [PlayerState.ACTIVE, PlayerState.IDLE, PlayerState.IDLE]
    opening = play.send("p1", REVEAL_1_0, NOW + 121.0)
    assert events_of(opening) == [opened(8, 1, "p1", REVEAL_1_0, 3)]
    return play


# ---- AC-3: the rule, a vote that fails ----


def test_ac3_two_no_of_three_reject_the_vote_and_leave_the_room_as_it_was(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    room_v3 = play.state
    play.send("p1", REVEAL_1_0)

    first = play.send("p2", Vote(vote_id=1, yes=False))
    second = play.send("p3", Vote(vote_id=1, yes=False))

    assert first.entries == ()
    assert first.reply == ()
    assert events_of(second) == [closed(6, 1, VoteOutcome.REJECTED, 1, 3)]
    assert second.reply == ()
    assert play.state.cells == room_v3.cells
    assert play.state.reveal_budget == FIVE_AND_ONE
    assert open_vote_of(play.state) is None
    expected = room_v3.model_copy(update={"seq": 6, "last_vote_id": 1})
    assert with_times_of(play.state, room_v3) == expected


@pytest.mark.parametrize(
    ("count", "noes"),
    [(2, 1), (3, 2), (4, 2)],
    ids=["1-no-of-2", "2-no-of-3", "2-no-of-4"],
)
def test_ac3_a_vote_is_rejected_as_soon_as_a_majority_can_no_longer_be_reached(
    fx01_grid: Grid, count: int, noes: int
) -> None:
    play = vote_room(fx01_grid, count)
    play.send("p1", REVEAL_1_0)

    for number in range(2, noes + 1):
        ballot = play.send(f"p{number}", Vote(vote_id=1, yes=False))
        assert ballot.entries == (), f"the vote closed at {number - 1} no"
    deciding = play.send(f"p{noes + 1}", Vote(vote_id=1, yes=False))

    assert events_of(deciding) == [closed(count + 3, 1, VoteOutcome.REJECTED, 1, count)]
    assert open_vote_of(play.state) is None
    assert play.state.reveal_budget == FIVE_AND_ONE


# ---- AC-3: the rule, a vote that times out ----


def test_ac3_tick_closes_an_unanswered_vote_at_twenty_seconds_and_not_before(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    vote = open_vote_of(play.state)
    cells = play.state.cells

    early = play.tick(NOW + 19.9)

    assert early.entries == ()
    assert open_vote_of(play.state) == vote

    due = play.tick(NOW + 20.0)

    assert events_of(due) == [closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    assert open_vote_of(play.state) is None
    assert play.state.cells == cells
    assert play.state.reveal_budget == FIVE_AND_ONE


def test_ac3_a_ballot_at_twenty_seconds_closes_the_vote_first_then_is_refused(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    cells = play.state.cells

    outcome = play.send("p2", Vote(vote_id=1, yes=True), NOW + 20.0)

    assert events_of(outcome) == [closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    assert refusal_code(outcome) is ErrorCode.NO_OPEN_VOTE
    assert open_vote_of(play.state) is None
    assert play.state.cells == cells
    assert play.state.reveal_budget == FIVE_AND_ONE


def test_ac3_a_vote_expires_after_the_timeout_it_was_opened_with(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)

    opening = play.send("p1", REVEAL_1_0, NOW, config_with_vote_timeout(5))

    assert events_of(opening) == [opened(5, 1, "p1", REVEAL_1_0, 3, timeout_seconds=5)]
    assert play.tick(NOW + 4.9).entries == ()
    assert events_of(play.tick(NOW + 5.0)) == [
        closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3)
    ]


def test_ac3_an_expired_vote_closes_before_a_new_request_which_opens_vote_2(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    request = Reveal(target=CellTarget(row=2, column=1))

    outcome = play.send("p2", request, NOW + 25.0)

    assert events_of(outcome) == [
        closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3),
        opened(7, 2, "p2", request, 3),
    ]
    assert outcome.reply == ()


def test_ac3_an_expired_vote_closes_before_a_letter_check(fx01_grid: Grid) -> None:
    play = v3(fx01_grid)
    write(play, "p1", [(1, 1, "X")])
    play.send("p1", REVEAL_1_0)
    letter_check = Check(target=CellTarget(row=1, column=1))

    outcome = play.send("p2", letter_check, NOW + 20.0)

    assert events_of(outcome) == [
        closed(7, 1, VoteOutcome.TIMED_OUT, 1, 3),
        CheckResult(
            seq=8,
            player_id="p2",
            target=CellTarget(row=1, column=1),
            correct=(),
            wrong=(CellRef(row=1, column=1),),
        ),
    ]


def test_ac3_the_expiry_entry_comes_after_the_wake_up_of_an_idle_voter(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    select = SelectCell(row=1, column=0, direction=Direction.ACROSS)
    play.send("p1", select, NOW + 100.0)
    play.tick(NOW + 120.0)
    states = [player.state for player in play.state.players]
    assert states == [PlayerState.ACTIVE, PlayerState.IDLE, PlayerState.IDLE]
    assert events_of(play.send("p1", REVEAL_1_0, NOW + 121.0)) == [
        opened(7, 1, "p1", REVEAL_1_0, 3)
    ]

    outcome = play.send("p2", Vote(vote_id=1, yes=True), NOW + 141.0)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=8, player_id="p2", state=PlayerState.ACTIVE),
        closed(9, 1, VoteOutcome.TIMED_OUT, 1, 3),
    ]
    assert refusal_code(outcome) is ErrorCode.NO_OPEN_VOTE


def test_ac3_the_expiry_entry_comes_after_the_wake_up_and_before_a_letter_check(
    fx01_grid: Grid,
) -> None:
    play = vote_among_idle_players(fx01_grid)
    letter_check = Check(target=CellTarget(row=1, column=1))

    outcome = play.send("p2", letter_check, NOW + 141.0)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=9, player_id="p2", state=PlayerState.ACTIVE),
        closed(10, 1, VoteOutcome.TIMED_OUT, 1, 3),
        CheckResult(
            seq=11,
            player_id="p2",
            target=CellTarget(row=1, column=1),
            correct=(),
            wrong=(CellRef(row=1, column=1),),
        ),
    ]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None


def test_ac3_the_expiry_entry_comes_after_the_wake_up_and_before_a_reveal(
    fx01_grid: Grid,
) -> None:
    play = vote_among_idle_players(fx01_grid)
    request = Reveal(target=CellTarget(row=2, column=1))

    outcome = play.send("p2", request, NOW + 141.0)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=9, player_id="p2", state=PlayerState.ACTIVE),
        closed(10, 1, VoteOutcome.TIMED_OUT, 1, 3),
        opened(11, 2, "p2", request, 3),
    ]
    assert outcome.reply == ()


def test_ac3_tick_closes_a_due_vote_after_the_host_hand_over_of_the_same_tick(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.disconnect("p1", NOW + 1.0)
    opening = play.send("p2", REVEAL_1_0, NOW + 50.0)
    assert events_of(opening) == [opened(6, 1, "p2", REVEAL_1_0, 2)]

    # At NOW + 70 the host has been away for 69 s (more than 60) and the vote,
    # opened at NOW + 50, is due: both steps act in this one tick.
    outcome = play.tick(NOW + 70.0)

    assert events_of(outcome) == [
        HostChanged(seq=7, player_id="p2"),
        closed(8, 1, VoteOutcome.TIMED_OUT, 1, 2),
    ]
    assert open_vote_of(play.state) is None
    hosts = [player.player_id for player in play.state.players if player.is_host]
    assert hosts == ["p2"]


# ---- AC-3: the rule, a vote that passes when its request can no longer apply ----


def test_ac3_a_vote_that_passes_after_the_budget_was_spent_closes_rejected(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    no_letter_left = ChangeSettings(
        help_mode=HelpMode.VOTE, reveal_budget=RevealBudget(letters=0, words=1)
    )
    change = play.send("p1", no_letter_left)
    assert len(change.entries) == 1
    assert play.state.seq == 6

    outcome = play.send("p2", Vote(vote_id=1, yes=True))

    assert events_of(outcome) == [closed(7, 1, VoteOutcome.REJECTED, 2, 3)]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    cell = cell_1_0(play.state)
    assert (cell.letter, cell.locked, cell.revealed) == (None, False, False)


def test_ac3_a_vote_that_passes_after_the_host_set_none_closes_rejected(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    play.send("p1", ChangeSettings(help_mode=HelpMode.NONE, reveal_budget=FIVE_AND_ONE))
    assert play.state.seq == 6

    outcome = play.send("p2", Vote(vote_id=1, yes=True))

    assert events_of(outcome) == [closed(7, 1, VoteOutcome.REJECTED, 2, 3)]
    assert outcome.reply == ()
    assert play.state.reveal_budget == FIVE_AND_ONE
    cell = cell_1_0(play.state)
    assert (cell.letter, cell.locked, cell.revealed) == (None, False, False)


def test_ac3_a_vote_that_passes_after_the_host_set_free_applies_its_request(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    play.send("p1", ChangeSettings(help_mode=HelpMode.FREE, reveal_budget=FIVE_AND_ONE))
    assert play.state.seq == 6

    outcome = play.send("p2", Vote(vote_id=1, yes=True))

    assert events_of(outcome) == [
        closed(7, 1, VoteOutcome.PASSED, 2, 3),
        RevealResult(
            seq=8,
            player_id="p1",
            target=CellTarget(row=1, column=0),
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=9, row=1, column=0, letter="T", revealed=True),
    ]


def test_ac3_a_vote_whose_target_was_locked_meanwhile_closes_rejected(
    fx01_grid: Grid,
) -> None:
    play = opened_reveal_vote(fx01_grid)
    write(play, "p2", [(1, 0, "T")])
    letter_check = play.send("p3", Check(target=CellTarget(row=1, column=0)))
    assert events_of(letter_check) == [
        CheckResult(
            seq=7,
            player_id="p3",
            target=CellTarget(row=1, column=0),
            correct=(CellRef(row=1, column=0),),
            wrong=(),
        ),
        CellLocked(seq=8, row=1, column=0, letter="T", revealed=False),
    ]

    outcome = play.send("p2", Vote(vote_id=1, yes=True))

    assert events_of(outcome) == [closed(9, 1, VoteOutcome.REJECTED, 2, 3)]
    assert outcome.reply == ()
    assert play.state.reveal_budget == FIVE_AND_ONE
    assert cell_1_0(play.state).revealed is False


def test_ac3_a_vote_that_passes_on_a_grid_solved_meanwhile_closes_rejected(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    write(play, "p1", all_but_last_cell())
    last_cell = Reveal(target=CellTarget(row=4, column=4))
    assert events_of(play.send("p1", last_cell)) == [opened(22, 1, "p1", last_cell, 3)]
    write(play, "p2", [(4, 4, "T")])
    assert play.state.solved is True
    assert play.state.seq == 24
    assert open_vote_of(play.state) is not None

    outcome = play.send("p3", Vote(vote_id=1, yes=True))

    assert events_of(outcome) == [closed(25, 1, VoteOutcome.REJECTED, 2, 3)]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    assert play.state.reveal_budget == FIVE_AND_ONE


# ---- AC-3: WebSocket with a fake clock ----


def vote_closings(peer: Peer) -> list[VoteClosed]:
    found: list[VoteClosed] = []
    for message in peer.after_snapshot():
        if isinstance(message, VoteClosed):
            found.append(message)
    return found


def reveal_results(peer: Peer) -> list[RevealResult]:
    found: list[RevealResult] = []
    for message in peer.after_snapshot():
        if isinstance(message, RevealResult):
            found.append(message)
    return found


def test_ac3_websocket_an_unanswered_vote_times_out_for_everyone_after_20_seconds(
    fake_clock: FakeClock, dist_dir: Path, catalogue: Catalogue, fx01_grid: Grid
) -> None:
    # The spec's timing registry, with spec 011's long silence: the 20 s jump of the
    # clock must not also close the silent sockets (spec 017) under the test.
    config = RoomConfig(
        tick_seconds=0.05, max_edits_per_second=1000, silence_timeout_seconds=600
    )
    registry = RoomRegistry(clock=fake_clock, config=config)
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
        with TestClient(app) as client, contextlib.ExitStack() as stack:
            peers = join_peers(stack, client, code, ["Ana", "Bob", "Cy"])
            set_vote_mode(peers[0], peers)
            peers[0].send(REVEAL_1_0)
            for peer in peers:
                peer.wait_for_seq(5, "the vote_opened")

            started = time.monotonic()
            fake_clock.advance(20)
            for peer in peers:
                remaining = WS_DETECTION_SECONDS - (time.monotonic() - started)
                peer.wait_until(
                    lambda peer=peer: len(vote_closings(peer)) == 1,
                    "the vote_closed",
                    timeout=max(remaining, 0.0),
                )
            time.sleep(SETTLE_SECONDS)

            for peer in peers:
                assert vote_closings(peer) == [
                    closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3)
                ]
                assert reveal_results(peer) == []
            state = registry.room_state(code)
            assert state is not None
            assert state.reveal_budget == FIVE_AND_ONE
    finally:
        registry.close()


# ---- AC-3: browser with a mocked socket ----


@pytest.mark.parametrize(
    "outcome",
    [VoteOutcome.REJECTED, VoteOutcome.TIMED_OUT],
    ids=["rejected", "timed-out"],
)
def test_ac3_browser_a_failed_vote_shows_its_result_and_changes_nothing(
    page: Page, live_server: str, fx01_grid: Grid, outcome: VoteOutcome
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    # Spec 043: what is left is the item's detail.
    reveal_letter = page.get_by_test_id("reveal-letter-detail")
    expect(reveal_letter).to_have_text(fr_text("reveal.letters_left", count=5))
    banner = page.get_by_test_id("vote-banner")
    request = Reveal(target=CellTarget(row=1, column=0))
    mock.send(opened(6, 1, "p2", request, 3).model_dump_json())
    expect(banner).to_be_visible()

    started = time.monotonic()
    mock.send(closed(7, 1, outcome, 1, 3).model_dump_json())

    expect(page.get_by_test_id("vote-result")).to_have_text(
        fr_text(f"vote.result.{outcome.value}")
    )
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-letter", "")
    expect(cell).to_have_attribute("data-locked", "false")
    expect(cell).to_have_attribute("data-revealed", "false")
    expect(reveal_letter).to_have_text(fr_text("reveal.letters_left", count=5))
    elapsed = seconds_until_hidden(page, banner, started)
    assert VOTE_RESULT_MIN_SECONDS <= elapsed <= VOTE_RESULT_MAX_SECONDS, elapsed
