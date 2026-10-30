"""Tests of hints AC-21 to AC-23: the hint limit on checks and reveals.

The rule 2 of `specs/gameplay/hints.md`: a player who already has
`RoomConfig.hint_limit` counted checks or reveals in the last
`hint_window_seconds` has the next one dropped, with no reply, no entry and no
change but their presence. The rules are tested on `handle_message`, `tick`,
`replay` and `after_restart` with exact clock values, on the rooms of spec 025's
harness (`Play`, `v3`). What a request gives "every player" is read from the
outcome of the room: its `entries` are the numbered events sent to all, its
`reply` goes to the sender only.

The window of a player is private to the room and the spec does not name its
field, so no test reads it: a test reads what the room does next.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellTarget,
    ChangeSettings,
    Check,
    CheckResult,
    CheckTarget,
    ErrorCode,
    GridTarget,
    HelpMode,
    Join,
    PlayerState,
    PlayerStateChanged,
    Reveal,
    RevealBudget,
    RevealResult,
    Snapshot,
    Vote,
    VoteOutcome,
)
from nock.room import (
    Outcome,
    RoomConfig,
    RoomState,
    after_restart,
    join_room,
    new_room,
    replay,
)
from spec025_harness import (
    FIVE_AND_ONE,
    GRID_CHECK,
    MIME,
    NOW,
    REVEAL_1_0,
    ROOM_CODE,
    TAMIS,
    Play,
    closed,
    events_of,
    grid_from_text,
    open_vote_of,
    opened,
    refusal_code,
    seen_at,
    token_of,
    v3,
)

WINDOW_SECONDS = 10.0
LIMIT = 5

# Cells of FX-01 used as targets: (1, 0) is a letter cell, (0, 0) a clue cell.
LETTER_1_1 = CellTarget(row=1, column=1)
LETTER_2_1 = CellTarget(row=2, column=1)
CLUE_CELL = CellTarget(row=0, column=0)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Helpers of the tests of this file ----


def free_room(grid: Grid, count: int = 2) -> Play:
    """A FX-01 room in `free` where `p1` (Ana) to `p<count>` joined at NOW."""
    play = Play(new_room(ROOM_CODE, grid, NOW))
    for number in range(1, count + 1):
        play.join(number)
    assert play.state.settings.help_mode == HelpMode.FREE
    assert play.state.seq == count
    return play


def empty_result(seq: int, player_id: str, target: CheckTarget) -> CheckResult:
    """The `check_result` of a check that finds nothing to compare."""
    return CheckResult(
        seq=seq, player_id=player_id, target=target, correct=(), wrong=()
    )


def check_applied(
    play: Play, player_id: str, target: CheckTarget, now: float = NOW
) -> Outcome:
    """Send a check of an empty room; assert it applied with its one result.

    The result is among the `entries`, which every player receives, and the
    sender gets no reply.
    """
    seq_before = play.state.seq
    outcome = play.send(player_id, Check(target=target), now)
    assert outcome.reply == ()
    assert outcome.to_others == ()
    assert events_of(outcome) == [empty_result(seq_before + 1, player_id, target)]
    assert outcome.state.seq == seq_before + 1
    return outcome


def dropped(
    play: Play,
    player_id: str,
    message: Check | Reveal,
    now: float = NOW,
) -> None:
    """Send a request; assert it was dropped and changed only the presence."""
    before = play.state
    outcome = play.send(player_id, message, now)
    assert outcome == Outcome(state=seen_at(before, player_id, now))


def host_sets_none(play: Play) -> None:
    """The host (`p1`) turns the help mode to `none`, at NOW."""
    settings = ChangeSettings(help_mode=HelpMode.NONE, reveal_budget=FIVE_AND_ONE)
    outcome = play.send("p1", settings)
    assert outcome.reply == ()


# ---- AC-21: the limit, the window and the players' own windows ----


def test_ac21_the_sixth_grid_check_at_one_instant_is_dropped_whole(
    fx01_grid: Grid,
) -> None:
    play = free_room(fx01_grid)

    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())
    seq_of_the_fifth = play.state.seq
    entries_before = len(play.entries)
    before = play.state
    sixth = play.send("p1", GRID_CHECK)

    assert seq_of_the_fifth == 2 + LIMIT
    assert sixth == Outcome(state=seen_at(before, "p1", NOW))
    assert sixth.state.seq == seq_of_the_fifth
    assert len(play.entries) == entries_before


@pytest.mark.parametrize(
    ("offset", "is_applied"),
    [(9.9, False), (10.0, True)],
    ids=["9.9-s-later-dropped", "10-s-later-applies"],
)
def test_ac21_the_window_slides_it_holds_the_requests_after_now_minus_ten(
    fx01_grid: Grid, offset: float, is_applied: bool
) -> None:
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())

    if is_applied:
        check_applied(play, "p1", GridTarget(), NOW + offset)
    else:
        dropped(play, "p1", GRID_CHECK, NOW + offset)


def test_ac21_each_player_has_their_own_window(fx01_grid: Grid) -> None:
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())
    dropped(play, "p1", GRID_CHECK)

    for _ in range(LIMIT):
        check_applied(play, "p2", GridTarget())
    dropped(play, "p2", GRID_CHECK)


def test_ac21_a_dropped_check_does_not_count(fx01_grid: Grid) -> None:
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())
    dropped(play, "p1", GRID_CHECK, NOW + 6.0)

    # If the check dropped at +6 s had counted, it would still be in the window
    # at +10 s and the fifth check here would be dropped.
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget(), NOW + WINDOW_SECONDS)
    dropped(play, "p1", GRID_CHECK, NOW + WINDOW_SECONDS)


@pytest.mark.parametrize("from_the_log", [False, True], ids=["live-state", "log"])
def test_ac21_a_restart_empties_every_window(
    fx01_grid: Grid, from_the_log: bool
) -> None:
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())
    for _ in range(LIMIT - 1):
        check_applied(play, "p2", GridTarget())
    stored = play.state
    if from_the_log:
        stored = new_room(ROOM_CODE, fx01_grid, NOW)
        for entry in play.entries:
            stored = replay(stored, entry)

    restarted = Play(after_restart(stored, NOW + 1.0).state)
    for number in (1, 2):
        join = Join(nickname=f"player {number}", resume_token=token_of(number))
        rejoined = join_room(
            restarted.state, join, NOW + 2.0, f"new-{number}", f"new-token-{number:02d}"
        )
        assert isinstance(rejoined.reply[0], Snapshot), rejoined.reply
        restarted.apply(rejoined)

    for _ in range(LIMIT):
        check_applied(restarted, "p1", GridTarget(), NOW + 2.0)
    dropped(restarted, "p1", GRID_CHECK, NOW + 2.0)
    for _ in range(LIMIT):
        check_applied(restarted, "p2", GridTarget(), NOW + 2.0)
    dropped(restarted, "p2", GRID_CHECK, NOW + 2.0)


def test_ac21_a_dropped_check_still_wakes_an_idle_sender(fx01_grid: Grid) -> None:
    # A window of 200 s keeps Ana's five checks while she goes idle (120 s).
    long_window = RoomConfig(silence_timeout_seconds=600, hint_window_seconds=200.0)
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        outcome = play.send("p1", Check(target=GridTarget()), NOW, long_window)
        assert len(outcome.entries) == 1
    play.tick(NOW + 120.0)
    assert _state_of(play.state, "p1") == PlayerState.IDLE

    woken = play.send("p1", Check(target=GridTarget()), NOW + 130.0, long_window)

    assert woken.reply == ()
    assert events_of(woken) == [
        PlayerStateChanged(seq=play.state.seq, player_id="p1", state=PlayerState.ACTIVE)
    ]
    assert _state_of(play.state, "p1") == PlayerState.ACTIVE


def _state_of(state: RoomState, player_id: str) -> PlayerState:
    """The presence state of one player."""
    for player in state.players:
        if player.player_id == player_id:
            return player.state
    pytest.fail(f"no player {player_id}")


def test_ac21_the_limit_and_the_window_follow_the_room_config(
    fx01_grid: Grid,
) -> None:
    default = RoomConfig()
    assert default.hint_limit == LIMIT
    assert default.hint_window_seconds == WINDOW_SECONDS
    config = RoomConfig(
        silence_timeout_seconds=600, hint_limit=2, hint_window_seconds=3.0
    )
    play = Play(free_room(fx01_grid).state)

    for _ in range(2):
        outcome = play.send("p1", Check(target=GridTarget()), NOW, config)
        assert len(outcome.entries) == 1
    before = play.state
    third = play.send("p1", GRID_CHECK, NOW + 2.9, config)
    assert third == Outcome(state=seen_at(before, "p1", NOW + 2.9))
    again = play.send("p1", GRID_CHECK, NOW + 3.0, config)
    assert len(again.entries) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [("hint_limit", 0), ("hint_window_seconds", 0.0)],
    ids=["limit-at-least-1", "window-above-0"],
)
def test_ac21_the_config_bounds(field: str, value: float) -> None:
    smallest_valid = RoomConfig.model_validate({field: 1})
    assert getattr(smallest_valid, field) == 1
    with pytest.raises(ValidationError, match=field):
        RoomConfig.model_validate({field: value})


# ---- AC-22: what counts, what does not, and the order ----


def test_ac22_a_refused_request_does_not_count_and_a_dropped_one_gets_no_error(
    fx01_grid: Grid,
) -> None:
    play = free_room(fx01_grid)
    check_applied(play, "p1", LETTER_1_1)
    check_applied(play, "p1", TAMIS)
    check_applied(play, "p1", GridTarget())
    letter_reveal = play.send("p1", Reveal(target=CellTarget(row=1, column=0)))
    assert letter_reveal.reply == ()
    assert events_of(letter_reveal) == [
        RevealResult(
            seq=6,
            player_id="p1",
            target=CellTarget(row=1, column=0),
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=7, row=1, column=0, letter="T", revealed=True),
    ]

    # Four requests are counted: the clue cell is refused, and the refusal is
    # not a fifth request.
    before = play.state
    refused = play.send("p1", Reveal(target=CLUE_CELL))
    assert refusal_code(refused) == ErrorCode.NOT_A_LETTER_CELL
    assert refused.entries == ()
    assert refused.state == seen_at(before, "p1", NOW)

    word_reveal = play.send("p1", Reveal(target=MIME))
    assert word_reveal.reply == ()
    reveal_result = events_of(word_reveal)[0]
    assert reveal_result == RevealResult(
        seq=8,
        player_id="p1",
        target=MIME,
        reveal_budget=RevealBudget(letters=4, words=0),
    )

    # The fifth counted request was MIME: the window is full.
    dropped(play, "p1", Check(target=LETTER_1_1))
    dropped(play, "p1", Reveal(target=CLUE_CELL))


def test_ac22_the_limit_comes_before_the_refusal_steps(fx01_grid: Grid) -> None:
    play = free_room(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", GridTarget())
    host_sets_none(play)

    dropped(play, "p1", GRID_CHECK)

    later = play.send("p1", GRID_CHECK, NOW + WINDOW_SECONDS)
    assert refusal_code(later) == ErrorCode.HELP_DISABLED


def test_ac22_a_refusal_that_closes_an_expired_vote_does_not_count(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.send("p1", REVEAL_1_0)

    refused = play.send("p2", Reveal(target=CLUE_CELL), NOW + 21.0)

    # The refusal carries the entry of the expired vote, and no entry of its own.
    assert refusal_code(refused) == ErrorCode.NOT_A_LETTER_CELL
    assert events_of(refused) == [closed(6, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    for _ in range(LIMIT):
        check_applied(play, "p2", TAMIS, NOW + 21.0)
    dropped(play, "p2", Check(target=TAMIS), NOW + 21.0)


# ---- AC-23: votes and the limit ----


def test_ac23_a_vote_counts_once_for_its_requester_when_it_opens(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    for _ in range(LIMIT):
        applied = play.send("p2", Check(target=TAMIS))
        assert [type(event) for event in events_of(applied)] == [CheckResult]
    assert play.state.seq == 9

    opening = play.send("p1", REVEAL_1_0)

    assert opening.reply == ()
    assert events_of(opening) == [opened(10, 1, "p1", REVEAL_1_0, 3)]

    # Bob's window is full, and a ballot is not held back by it.
    passing = play.send("p2", Vote(vote_id=1, yes=True))

    assert passing.reply == ()
    assert events_of(passing) == [
        closed(11, 1, VoteOutcome.PASSED, 2, 3),
        RevealResult(
            seq=12,
            player_id="p1",
            target=CellTarget(row=1, column=0),
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=13, row=1, column=0, letter="T", revealed=True),
    ]
    dropped(play, "p2", Check(target=TAMIS))

    # Ana's window holds the reveal that opened the vote, not the pass: four
    # letter checks apply, the fifth is dropped.
    for _ in range(LIMIT - 1):
        check_applied(play, "p1", LETTER_2_1)
    dropped(play, "p1", Check(target=LETTER_2_1))


def test_ac23_a_grid_check_over_the_limit_opens_no_vote(fx01_grid: Grid) -> None:
    play = v3(fx01_grid)
    for _ in range(LIMIT):
        check_applied(play, "p1", LETTER_2_1)

    dropped(play, "p1", GRID_CHECK)

    assert open_vote_of(play.state) is None
    assert play.state.last_vote_id == 0


def test_ac23_a_check_dropped_after_the_votes_time_leaves_it_for_the_tick(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.send("p1", REVEAL_1_0)
    for _ in range(LIMIT):
        check_applied(play, "p2", TAMIS, NOW + 19.0)
    vote = open_vote_of(play.state)
    assert vote is not None

    dropped(play, "p2", Check(target=TAMIS), NOW + 20.5)

    assert open_vote_of(play.state) == vote
    timed_out = play.tick(NOW + 20.5)
    assert events_of(timed_out) == [closed(11, 1, VoteOutcome.TIMED_OUT, 1, 3)]
    assert open_vote_of(play.state) is None


def test_ac23_a_vote_passes_though_its_requesters_window_is_full_and_counts_nothing(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.send("p1", REVEAL_1_0)
    for _ in range(LIMIT - 1):
        check_applied(play, "p1", LETTER_2_1)

    # Ana's window is full (the opening and four checks) when the vote passes.
    passing = play.send("p2", Vote(vote_id=1, yes=True), NOW + 9.0)

    assert passing.reply == ()
    assert events_of(passing) == [
        closed(10, 1, VoteOutcome.PASSED, 2, 3),
        RevealResult(
            seq=11,
            player_id="p1",
            target=CellTarget(row=1, column=0),
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=12, row=1, column=0, letter="T", revealed=True),
    ]
    # Once the requests of NOW have left the window, the pass is in nobody's:
    # five checks apply for Ana and for Bob.
    for player_id, target in (("p1", LETTER_2_1), ("p2", TAMIS)):
        for _ in range(LIMIT):
            check_applied(play, player_id, target, NOW + WINDOW_SECONDS)
        dropped(play, player_id, Check(target=target), NOW + WINDOW_SECONDS)
