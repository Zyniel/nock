"""Tests of spec 018, AC-3: undo on `handle_message`.

How the accepted edits and erases record `last_edit`, and the undo rules: what an
undo restores, when it is refused with `nothing_to_undo`, and that it is not an
edit for the rate limit. Not tested: the `grid_solved` refusal (spec 026). The
shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import EditLetter, Erase, ErrorCode, ErrorMessage, Undo
from nock.room import (
    CellState,
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    UndoEntry,
    handle_message,
)
from spec018_harness import (
    NOW,
    cell_state,
    grid_from_text,
    letter_changed,
    other_cells,
    player_record,
    two_player_room,
    with_cell,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-3: undo on handle_message ----


def assert_refused_as_nothing_to_undo(outcome: Outcome, before: RoomState) -> None:
    """The undo changed nothing but possibly `last_edit`, and answered the sender."""
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.NOTHING_TO_UNDO
    assert outcome.state.seq == before.seq
    assert outcome.state.cells == before.cells
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac3_an_accepted_edit_records_the_cell_before_it_as_last_edit(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW)

    assert player_record(outcome.state, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=3, letter="B", pencil=True, author="p2"
    )
    assert player_record(outcome.state, "p2").last_edit is None


def test_ac3_an_accepted_edit_in_an_empty_cell_records_an_empty_cell(
    fx01_grid: Grid,
) -> None:
    outcome = handle_message(
        two_player_room(fx01_grid), "p2", EditLetter(row=1, column=0, letter="T"), NOW
    )

    assert player_record(outcome.state, "p2").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter=None, pencil=False, author=None
    )


def test_ac3_an_accepted_erase_records_the_erased_letter_as_last_edit(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    outcome = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)

    assert player_record(outcome.state, "p1").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter="T", pencil=False, author="p2"
    )


def test_ac3_a_later_edit_replaces_last_edit_with_the_latest_one(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    assert player_record(second.state, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=4, letter=None, pencil=False, author=None
    )


def test_ac3_a_refused_edit_leaves_last_edit_alone(fx01_grid: Grid) -> None:
    locked = CellState(
        row=1,
        column=2,
        letter="M",
        author="p2",
        locked=True,
        changed_seq=2,
        changed_by="p2",
    )
    state = with_cell(two_player_room(fx01_grid), locked)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    expected = player_record(first.state, "p1").last_edit
    assert expected is not None

    refused = handle_message(
        first.state, "p1", EditLetter(row=1, column=2, letter="X"), NOW + 1
    )

    assert refused.entries == ()
    assert player_record(refused.state, "p1").last_edit == expected


def test_ac3_undo_of_a_letter_in_an_empty_cell_empties_it_again(
    fx01_grid: Grid,
) -> None:
    typed = handle_message(
        two_player_room(fx01_grid), "p1", EditLetter(row=1, column=0, letter="T"), NOW
    )

    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 0, None, "p1"), undo=True),
    )
    assert undone.reply == ()
    assert undone.state.seq == 4
    assert cell_state(undone.state, 1, 0) == CellState(
        row=1, column=0, changed_seq=4, changed_by="p1"
    )
    assert other_cells(undone.state, 1, 0) == other_cells(typed.state, 1, 0)
    assert player_record(undone.state, "p1").last_edit is None
    assert undone.close_sender is False
    assert undone.disconnects == ()


def test_ac3_undo_over_another_players_letter_brings_it_back_authored_by_me(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=1, letter="B", author="p2", changed_seq=2, changed_by="p2"
        ),
    )
    overwritten = handle_message(
        seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW
    )

    undone = handle_message(overwritten.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 1, "B", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 1) == CellState(
        row=1, column=1, letter="B", author="p1", changed_seq=4, changed_by="p1"
    )
    assert undone.state.seq == 4
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_gives_back_the_pencil_flag_of_the_old_letter(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )
    overwritten = handle_message(
        seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW
    )

    undone = handle_message(overwritten.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(
            at=NOW + 1,
            event=letter_changed(4, 1, 1, "B", "p1", pencil=True),
            undo=True,
        ),
    )
    assert cell_state(undone.state, 1, 1) == CellState(
        row=1,
        column=1,
        letter="B",
        pencil=True,
        author="p1",
        wrong=False,
        changed_seq=4,
        changed_by="p1",
    )


def test_ac3_undo_of_an_erase_restores_the_erased_letter_authored_by_the_undoer(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )
    erased = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)
    assert cell_state(erased.state, 1, 0).letter is None

    undone = handle_message(erased.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 0, "T", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 0) == CellState(
        row=1, column=0, letter="T", author="p1", changed_seq=4, changed_by="p1"
    )


def test_ac3_undo_after_another_player_changed_the_cell_is_refused(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    mine = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    theirs = handle_message(
        mine.state, "p2", EditLetter(row=1, column=0, letter="X"), NOW + 1
    )

    undone = handle_message(theirs.state, "p1", Undo(), NOW + 2)

    assert_refused_as_nothing_to_undo(undone, theirs.state)
    assert cell_state(undone.state, 1, 0).letter == "X"
    assert cell_state(undone.state, 1, 0).author == "p2"
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_after_my_own_later_edit_of_the_same_cell_goes_back_one_step(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="U"), NOW + 1
    )

    undone = handle_message(second.state, "p1", Undo(), NOW + 2)

    assert undone.entries == (
        LogEntry(at=NOW + 2, event=letter_changed(5, 1, 0, "T", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 0).letter == "T"
    assert cell_state(undone.state, 1, 0).author == "p1"
    again = handle_message(undone.state, "p1", Undo(), NOW + 3)
    assert_refused_as_nothing_to_undo(again, undone.state)
    assert cell_state(again.state, 1, 0).letter == "T"


def test_ac3_a_second_undo_right_after_an_undo_is_refused(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)
    assert undone.entries != ()

    second = handle_message(undone.state, "p1", Undo(), NOW + 2)

    assert_refused_as_nothing_to_undo(second, undone.state)
    assert cell_state(second.state, 1, 0).letter is None


def test_ac3_after_an_undo_a_new_edit_can_be_undone_again(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)
    retyped = handle_message(
        undone.state, "p1", EditLetter(row=1, column=0, letter="V"), NOW + 2
    )

    undone_again = handle_message(retyped.state, "p1", Undo(), NOW + 3)

    assert undone_again.entries == (
        LogEntry(at=NOW + 3, event=letter_changed(6, 1, 0, None, "p1"), undo=True),
    )
    assert cell_state(undone_again.state, 1, 0).letter is None


def test_ac3_only_my_latest_edit_can_be_undone_not_the_one_before(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    undone = handle_message(second.state, "p1", Undo(), NOW + 2)
    again = handle_message(undone.state, "p1", Undo(), NOW + 3)

    assert cell_state(undone.state, 1, 1).letter is None
    assert cell_state(undone.state, 1, 0).letter == "T"
    assert_refused_as_nothing_to_undo(again, undone.state)
    assert cell_state(again.state, 1, 0).letter == "T"


@pytest.mark.parametrize("lock_seq", [3, 4])
def test_ac3_undo_on_a_locked_cell_is_refused(fx01_grid: Grid, lock_seq: int) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=2, letter="M"), NOW)
    locked_cell = cell_state(typed.state, 1, 2).model_copy(
        update={"locked": True, "changed_seq": lock_seq, "changed_by": None}
    )
    locked = with_cell(typed.state, locked_cell)

    undone = handle_message(locked, "p1", Undo(), NOW + 1)

    assert_refused_as_nothing_to_undo(undone, locked)
    assert cell_state(undone.state, 1, 2).letter == "M"
    assert cell_state(undone.state, 1, 2).locked is True
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_by_a_player_who_never_edited_is_refused(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)

    undone = handle_message(state, "p1", Undo(), NOW)

    assert_refused_as_nothing_to_undo(undone, state)
    assert undone.state == state


def test_ac3_undo_by_a_player_whose_neighbour_edited_is_still_refused(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    theirs = handle_message(state, "p2", EditLetter(row=1, column=0, letter="X"), NOW)

    undone = handle_message(theirs.state, "p1", Undo(), NOW + 1)

    assert_refused_as_nothing_to_undo(undone, theirs.state)
    assert cell_state(undone.state, 1, 0).letter == "X"
    assert player_record(undone.state, "p2").last_edit is not None


def test_ac3_an_undo_leaves_the_other_players_last_edit_alone(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )
    expected = player_record(second.state, "p1").last_edit
    assert expected is not None

    undone = handle_message(second.state, "p2", Undo(), NOW + 2)

    assert cell_state(undone.state, 1, 1).letter is None
    assert player_record(undone.state, "p1").last_edit == expected
    assert player_record(undone.state, "p2").last_edit is None


def test_ac3_a_cell_changed_by_another_players_undo_cannot_be_undone_by_me(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    mine = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    theirs = handle_message(
        mine.state, "p2", EditLetter(row=1, column=0, letter="X"), NOW + 1
    )
    their_undo = handle_message(theirs.state, "p2", Undo(), NOW + 2)
    assert their_undo.entries != ()
    assert cell_state(their_undo.state, 1, 0).letter == "T"

    undone = handle_message(their_undo.state, "p1", Undo(), NOW + 3)

    assert_refused_as_nothing_to_undo(undone, their_undo.state)


def test_ac3_an_undo_is_not_counted_by_the_rate_limit(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=2)
    state = two_player_room(fx01_grid)
    typed = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )

    undone = handle_message(typed.state, "p1", Undo(), NOW, config)
    retyped = handle_message(
        undone.state, "p1", EditLetter(row=1, column=0, letter="V"), NOW, config
    )

    assert undone.entries != ()
    assert player_record(undone.state, "p1").recent_edits == (NOW,)
    assert retyped.entries != ()
    assert [m for m in retyped.reply if isinstance(m, ErrorMessage)] == []


def test_ac3_an_undo_is_accepted_when_the_player_is_at_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = two_player_room(fx01_grid)
    typed = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )
    blocked = handle_message(
        typed.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW, config
    )
    assert isinstance(blocked.reply[0], ErrorMessage)
    assert blocked.reply[0].code is ErrorCode.RATE_LIMITED

    undone = handle_message(blocked.state, "p1", Undo(), NOW, config)

    assert len(undone.entries) == 1
    assert undone.entries[0].undo is True
    assert undone.reply == ()
