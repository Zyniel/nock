"""Tests of spec 023, AC-1 and AC-2: a word, a letter and the grid are checked.

AC-1: a word check marks the wrong letters and locks the correct ones. AC-2: a
letter check and a grid check apply the same rule. Both check the rule on
`handle_message` and `replay`. The shared setup is in `spec023_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellTarget,
    Check,
    CheckResult,
    GridTarget,
    PlayerState,
    PlayerStateChanged,
    WordTarget,
)
from nock.room import (
    CellState,
    LogEntry,
    PlayerRecord,
    RoomConfig,
    RoomState,
    handle_message,
    replay,
    tick,
)
from spec023_harness import (
    CHECK_NOW,
    NOW,
    TAMIS,
    cell_state,
    cell_view,
    check,
    grid_from_text,
    refs,
    s1_room,
    two_player_room,
    write_letter,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Helper of the tests of this file ----


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


# ---- AC-1: a word check marks the wrong letters and locks the correct ones ----


def test_ac1_checking_a_word_gives_a_result_then_one_lock_per_correct_cell(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW)

    assert outcome.reply == ()
    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=10, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=11, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=12, row=1, column=4, letter="S", revealed=False),
    ]


def test_ac1_the_target_is_returned_as_received(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    target = WordTarget(row=0, column=0, clue_index=0)

    events = check(state, target)

    assert isinstance(events[0], CheckResult)
    assert events[0].target == target


def test_ac1_correct_cells_are_locked_and_keep_letter_and_author(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    assert after.seq == 12
    assert cell_state(after, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        author="p1",
        locked=True,
        wrong=False,
        changed_seq=10,
        changed_by=None,
    )
    assert cell_state(after, 1, 3) == CellState(
        row=1,
        column=3,
        letter="I",
        author="p1",
        locked=True,
        changed_seq=11,
        changed_by=None,
    )
    assert cell_state(after, 1, 4) == CellState(
        row=1,
        column=4,
        letter="S",
        author="p1",
        locked=True,
        changed_seq=12,
        changed_by=None,
    )


def test_ac1_a_wrong_cell_is_marked_and_keeps_letter_author_and_changed_seq(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    before = cell_state(state, 1, 1)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    assert cell_state(after, 1, 1) == before.model_copy(update={"wrong": True})
    assert cell_state(after, 1, 1).letter == "X"
    assert cell_state(after, 1, 1).author == "p1"
    assert cell_state(after, 1, 1).locked is False


def test_ac1_the_cells_outside_the_word_are_unchanged(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    for row, column in [(2, 1), (2, 2), (1, 2), (3, 1), (4, 4)]:
        assert cell_state(after, row, column) == cell_state(state, row, column)


def test_ac1_grid_state_shows_the_same_values(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    locked_t = cell_view(after, 1, 0)
    assert (locked_t.letter, locked_t.author, locked_t.locked, locked_t.wrong) == (
        "T",
        "p1",
        True,
        False,
    )
    assert locked_t.revealed is False
    for column, letter in ((3, "I"), (4, "S")):
        view = cell_view(after, 1, column)
        assert (view.letter, view.author, view.locked, view.wrong) == (
            letter,
            "p1",
            True,
            False,
        )
    struck = cell_view(after, 1, 1)
    assert (struck.letter, struck.author, struck.locked, struck.wrong) == (
        "X",
        "p1",
        False,
        True,
    )


def test_ac1_replaying_the_entries_gives_the_cells_of_the_live_step(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    outcome = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW)

    replayed = state
    for entry in outcome.entries:
        assert isinstance(entry, LogEntry)
        replayed = replay(replayed, entry)

    assert replayed.cells == outcome.state.cells
    assert replayed.seq == outcome.state.seq == 12
    assert cell_state(replayed, 1, 1).wrong is True


def test_ac1_checking_again_a_wrong_cell_lists_it_again(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    first = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    events = check(first, TAMIS)

    assert events == [
        CheckResult(
            seq=13,
            player_id="p1",
            target=TAMIS,
            correct=(),
            wrong=refs((1, 1)),
        )
    ]


def test_ac1_any_player_checks_the_letters_of_another(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    events = check(state, TAMIS, player_id="p2")

    assert isinstance(events[0], CheckResult)
    assert events[0].player_id == "p2"
    assert events[0].correct == refs((1, 0), (1, 3), (1, 4))
    assert events[0].wrong == refs((1, 1))


def test_ac1_a_check_is_input_but_not_an_edit_for_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    before = player_record(state, "p1")

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    record = player_record(after, "p1")
    assert record.recent_edits == before.recent_edits
    assert record.last_input_at == CHECK_NOW
    assert record.last_seen_at == CHECK_NOW


def test_ac1_a_check_by_p2_does_not_change_the_other_player(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p2", Check(target=TAMIS), CHECK_NOW).state

    assert player_record(after, "p1") == player_record(state, "p1")


def idle_room(grid: Grid) -> RoomState:
    """`S1` after two minutes of silence: `p1` then `p2` turned idle (seq 10)."""
    config = RoomConfig(silence_timeout_seconds=3600)
    outcome = tick(s1_room(grid), NOW + 120, config)
    assert outcome.state.seq == 10
    assert player_record(outcome.state, "p1").state is PlayerState.IDLE
    assert player_record(outcome.state, "p2").state is PlayerState.IDLE
    return outcome.state


def test_ac1_a_check_wakes_an_idle_player_before_its_own_entries(
    fx01_grid: Grid,
) -> None:
    state = idle_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=TAMIS), NOW + 130)

    assert outcome.reply == ()
    assert [entry.event for entry in outcome.entries] == [
        PlayerStateChanged(seq=11, player_id="p1", state=PlayerState.ACTIVE),
        CheckResult(
            seq=12,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=13, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=14, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=15, row=1, column=4, letter="S", revealed=False),
    ]
    assert outcome.state.seq == 15
    assert player_record(outcome.state, "p1").state is PlayerState.ACTIVE
    assert player_record(outcome.state, "p1").last_input_at == NOW + 130
    assert player_record(outcome.state, "p2").state is PlayerState.IDLE


def test_ac1_a_grid_check_wakes_an_idle_player_even_when_it_finds_nothing(
    fx01_grid: Grid,
) -> None:
    state = tick(
        two_player_room(fx01_grid), NOW + 120, RoomConfig(silence_timeout_seconds=3600)
    ).state
    assert state.seq == 4

    outcome = handle_message(state, "p2", Check(target=GridTarget()), NOW + 130)

    assert [entry.event for entry in outcome.entries] == [
        PlayerStateChanged(seq=5, player_id="p2", state=PlayerState.ACTIVE),
        CheckResult(seq=6, player_id="p2", target=GridTarget(), correct=(), wrong=()),
    ]
    assert player_record(outcome.state, "p1").state is PlayerState.IDLE


# ---- AC-2: a letter check and a grid check apply the same rule ----


def test_ac2_checking_a_wrong_letter_marks_it_and_locks_nothing(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    target = CellTarget(row=2, column=2)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9, player_id="p1", target=target, correct=(), wrong=refs((2, 2))
        )
    ]
    assert outcome.state.seq == 9
    assert cell_state(outcome.state, 2, 2).wrong is True
    assert cell_state(outcome.state, 2, 2).letter == "Q"
    assert cell_state(outcome.state, 2, 2).locked is False


def test_ac2_checking_a_correct_letter_locks_it(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    target = CellTarget(row=2, column=1)

    events = check(state, target)

    assert events == [
        CheckResult(
            seq=9, player_id="p1", target=target, correct=refs((2, 1)), wrong=()
        ),
        CellLocked(seq=10, row=2, column=1, letter="V", revealed=False),
    ]


def test_ac2_checking_the_grid_covers_every_letter_cell_in_state_order(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    target = GridTarget()

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9,
            player_id="p1",
            target=target,
            correct=refs((1, 0), (1, 3), (1, 4), (2, 1)),
            wrong=refs((1, 1), (2, 2)),
        ),
        CellLocked(seq=10, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=11, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=12, row=1, column=4, letter="S", revealed=False),
        CellLocked(seq=13, row=2, column=1, letter="V", revealed=False),
    ]
    assert outcome.state.seq == 13
    assert cell_state(outcome.state, 1, 1).wrong is True
    assert cell_state(outcome.state, 2, 2).wrong is True
    assert cell_state(outcome.state, 2, 1).locked is True


def test_ac2_empty_cells_of_the_grid_are_not_touched_by_a_grid_check(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW).state

    for cell in after.cells:
        if cell.letter is None:
            assert cell == CellState(row=cell.row, column=cell.column)


def test_ac2_locked_cells_are_left_out_and_not_locked_again(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    first = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW).state

    outcome = handle_message(first, "p1", Check(target=GridTarget()), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=14,
            player_id="p1",
            target=GridTarget(),
            correct=(),
            wrong=refs((1, 1), (2, 2)),
        )
    ]
    assert cell_state(outcome.state, 1, 0) == cell_state(first, 1, 0)


def test_ac2_a_word_of_locked_letters_gives_empty_lists(fx01_grid: Grid) -> None:
    state = write_letter(s1_room(fx01_grid), "p2", 1, 1, "A")
    first = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state
    assert cell_state(first, 1, 1).locked is True

    events = check(first, TAMIS)

    assert events == [
        CheckResult(
            seq=first.seq + 1, player_id="p1", target=TAMIS, correct=(), wrong=()
        )
    ]


def test_ac2_replaying_a_grid_check_gives_the_cells_of_the_live_step(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    outcome = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW)

    replayed = state
    for entry in outcome.entries:
        replayed = replay(replayed, entry)

    assert replayed.cells == outcome.state.cells
    assert replayed.seq == 13


def test_ac2_replaying_a_lock_clears_the_wrong_mark(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    marked = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state
    assert cell_state(marked, 1, 1).wrong is True
    fixed = write_letter(marked, "p2", 1, 1, "A")
    assert cell_state(fixed, 1, 1).wrong is False
    # Mark it again by hand, then replay a lock: the lock must clear the mark.
    struck = fixed.model_copy(
        update={
            "cells": tuple(
                (
                    cell.model_copy(update={"wrong": True})
                    if (cell.row, cell.column) == (1, 1)
                    else cell
                )
                for cell in fixed.cells
            )
        }
    )
    lock = LogEntry(
        at=CHECK_NOW,
        event=CellLocked(
            seq=struck.seq + 1, row=1, column=1, letter="A", revealed=False
        ),
    )

    replayed = replay(struck, lock)

    assert cell_state(replayed, 1, 1).locked is True
    assert cell_state(replayed, 1, 1).wrong is False
