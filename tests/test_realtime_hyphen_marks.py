"""Tests of realtime AC-20: the hyphen marks of the snapshot's letter cells.

`grid_view` gives each letter cell `hyphen_right` and `hyphen_down`; the room's
own view (`grid_state`, the grid of every snapshot) carries the same marks with
its letters. A letter cell written without the marks parses with both false, and
the marks are strict booleans.

Choices where the spec leaves room:

- The criterion's view is read twice: `grid_view` of the grid, and `grid_state`
  of a room on it, with a letter typed at (2, 2) so the marks survive a change.
- "Refused" is tried with `"yes"`, `"true"` and `1` on both marks, after checking
  that `true` itself parses.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from grids_harness import FX01_HYPHENS, JsonData, grid_with_answers
from nock.grid import Grid
from nock.protocol import (
    GridView,
    LetterCellView,
    Snapshot,
    grid_view,
    parse_server_message,
)
from nock.room import grid_state
from spec023_harness import two_player_room, write_letter
from spec039_harness import server_data

Marks = dict[tuple[int, int], tuple[bool, bool]]

# (row, column): (hyphen_right, hyphen_down) of the cells with a mark set.
FX01_HYPHEN_MARKS: Marks = {(2, 2): (True, False), (1, 1): (False, True)}


def marks_of(view: GridView) -> Marks:
    """The two marks of every letter cell of a view, by position."""
    marks: Marks = {}
    for cell in view.cells:
        if isinstance(cell, LetterCellView):
            marks[(cell.row, cell.column)] = (cell.hyphen_right, cell.hyphen_down)
    return marks


def expected_marks(view: GridView, set_marks: Marks) -> Marks:
    """Every letter cell of a view false on both marks, but those of `set_marks`."""
    expected: Marks = {}
    for cell in view.cells:
        if isinstance(cell, LetterCellView):
            position = (cell.row, cell.column)
            expected[position] = set_marks.get(position, (False, False))
    return expected


def room_view(grid: Grid) -> GridView:
    """The grid of a room on `grid`, once `p1` typed `I` at (2, 2)."""
    state = two_player_room(grid)
    state = write_letter(state, "p1", 2, 2, "I")
    return grid_state(state)


@pytest.fixture
def hyphen_grid(fx01_text: str) -> Grid:
    """FX-01 with `VI-DE` and `NA-VAL`."""
    return grid_with_answers(fx01_text, FX01_HYPHENS)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def test_ac20_grid_view_marks_the_edges_of_vi_de_and_na_val(
    hyphen_grid: Grid,
) -> None:
    view = grid_view(hyphen_grid)

    marks = marks_of(view)

    assert len(marks) == 18
    assert marks == expected_marks(view, FX01_HYPHEN_MARKS)


def test_ac20_the_rooms_snapshot_grid_carries_the_same_marks(
    hyphen_grid: Grid,
) -> None:
    view = room_view(hyphen_grid)

    marks = marks_of(view)

    assert marks == expected_marks(view, FX01_HYPHEN_MARKS)
    typed = [cell for cell in view.cells if (cell.row, cell.column) == (2, 2)]
    assert isinstance(typed[0], LetterCellView)
    assert typed[0].letter == "I"


def test_ac20_the_marks_hold_no_answer(hyphen_grid: Grid) -> None:
    text = grid_view(hyphen_grid).model_dump_json()

    for answer in ("VI-DE", "VIDE", "NA-VAL", "NAVAL"):
        assert answer not in text
    assert '"answer"' not in text


def test_ac20_an_across_and_a_down_hyphen_after_one_cell_set_both_marks(
    fx01_text: str,
) -> None:
    grid = grid_with_answers(fx01_text, {"TAMIS": "TA-MIS", "NAVAL": "NA-VAL"})
    view = grid_view(grid)

    assert marks_of(view) == expected_marks(view, {(1, 1): (True, True)})


@pytest.mark.parametrize("source", ["grid_view", "room"])
def test_ac20_on_fx01_as_published_every_mark_is_false(
    fx01_grid: Grid, source: str
) -> None:
    # A room stored while answers held letters only (VIDE) is FX-01 as published.
    view = grid_view(fx01_grid) if source == "grid_view" else room_view(fx01_grid)

    assert marks_of(view) == expected_marks(view, {})


LETTER_CELL: JsonData = {
    "type": "letter",
    "row": 0,
    "column": 1,
    "letter": None,
    "pencil": False,
    "author": None,
    "locked": False,
    "revealed": False,
    "wrong": False,
}


def test_ac20_a_letter_cell_written_without_the_marks_parses_with_both_false() -> None:
    cell = LetterCellView.model_validate(LETTER_CELL)

    assert cell.hyphen_right is False
    assert cell.hyphen_down is False


def test_ac20_the_snapshot_example_without_marks_parses_with_both_false() -> None:
    message = parse_server_message(json.dumps(server_data("snapshot")))

    assert isinstance(message, Snapshot)
    cell = message.grid.cells[1]
    assert isinstance(cell, LetterCellView)
    assert (cell.hyphen_right, cell.hyphen_down) == (False, False)


@pytest.mark.parametrize("mark", ["hyphen_right", "hyphen_down"])
@pytest.mark.parametrize("value", ["yes", "true", 1])
def test_ac20_a_mark_that_is_not_a_strict_boolean_is_refused(
    mark: str, value: str | int
) -> None:
    accepted = LetterCellView.model_validate({**LETTER_CELL, mark: True})
    assert getattr(accepted, mark) is True

    with pytest.raises(ValidationError):
        LetterCellView.model_validate({**LETTER_CELL, mark: value})


def test_ac20_a_snapshot_with_hyphen_right_yes_is_refused() -> None:
    data = server_data("snapshot")
    data["grid"]["cells"][1]["hyphen_right"] = True
    accepted = parse_server_message(json.dumps(data))
    assert isinstance(accepted, Snapshot)

    data["grid"]["cells"][1]["hyphen_right"] = "yes"
    with pytest.raises(ValidationError):
        parse_server_message(json.dumps(data))
