"""Tests of spec 015, AC-3: the fields of an accepted edit.

`handle_message` is called directly, with exact clock values, to check the cell
that an accepted `edit_letter` or `erase` writes and the `letter_changed` event
that it numbers. The shared setup is in `spec015_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import EditLetter, Erase, Join, LetterChanged
from nock.room import (
    CellState,
    LogEntry,
    RoomState,
    handle_message,
    join_room,
    new_room,
)
from spec015_harness import grid_from_text

ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-3: the accepted edit, directly on handle_message ---------------------


def two_player_room(grid: Grid) -> RoomState:
    """A room with players `p1` and `p2` (seq 2), every cell empty."""
    state = new_room(ROOM_CODE, grid, START_TIME)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    assert second.state.seq == 2
    return second.state


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def other_cells(state: RoomState, row: int, column: int) -> list[CellState]:
    return [cell for cell in state.cells if (cell.row, cell.column) != (row, column)]


def test_ac3_an_accepted_edit_writes_the_letter_and_numbers_the_event(
    fx01_grid: Grid,
) -> None:
    before = two_player_room(fx01_grid)

    outcome = handle_message(before, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p1",
        locked=False,
        revealed=False,
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )
    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter="T", pencil=False, player_id="p1"
            ),
        ),
    )
    assert other_cells(outcome.state, 1, 0) == other_cells(before, 1, 0)
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac3_an_edit_replaces_the_letter_the_author_and_clears_pencil_and_wrong(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p1",
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )


def test_ac3_the_same_letter_again_is_accepted_and_numbered(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter="T", pencil=False, player_id="p1"
            ),
        ),
    )
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("T", "p1", 3)
    assert cell.changed_by == "p1"


def test_ac3_an_erase_empties_the_cell_and_its_author(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="T",
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter=None,
        pencil=False,
        author=None,
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )
    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter=None, pencil=False, player_id="p1"
            ),
        ),
    )


def test_ac3_erasing_an_empty_cell_is_accepted_and_changes_nothing_else(
    fx01_grid: Grid,
) -> None:
    before = two_player_room(fx01_grid)

    outcome = handle_message(before, "p2", Erase(row=1, column=1), NOW)

    assert outcome.state.seq == 3
    assert cell_state(outcome.state, 1, 1) == CellState(
        row=1, column=1, changed_seq=3, changed_by="p2"
    )
    assert other_cells(outcome.state, 1, 1) == other_cells(before, 1, 1)
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=1, letter=None, pencil=False, player_id="p2"
            ),
        ),
    )


def test_ac3_successive_edits_get_successive_seqs(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    assert [entry.event.seq for entry in first.entries] == [3]
    assert [entry.event.seq for entry in second.entries] == [4]
    assert second.entries[0].at == NOW + 1
    assert second.state.seq == 4
    assert cell_state(second.state, 1, 0).changed_seq == 3
    assert cell_state(second.state, 1, 1).changed_seq == 4
    assert cell_state(second.state, 1, 1).author == "p2"
