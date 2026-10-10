"""Tests of spec 003: grid validation at import."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from nock.grid import Grid
from nock.grid_import import GridImportError, ImportReport, import_grid

# Grids are edited as parsed JSON, whose values can be any JSON type, hence Any.
GridData = dict[str, Any]
CellData = dict[str, Any]


def _load(text: str) -> GridData:
    """Parse the JSON text of a grid into a dictionary."""
    return json.loads(text)


def _dump(data: GridData) -> str:
    """Write a grid dictionary back to JSON text."""
    return json.dumps(data)


def _find_cell(data: GridData, row: int, column: int) -> CellData:
    """Return the cell dictionary at (row, column)."""
    for cell in data["cells"]:
        if cell["row"] == row and cell["column"] == column:
            return cell
    raise AssertionError(f"test grid has no cell at ({row}, {column})")


def _replace_cell(data: GridData, new_cell: CellData) -> None:
    """Replace the cell at the position of new_cell by new_cell."""
    cells = data["cells"]
    for index, cell in enumerate(cells):
        if cell["row"] == new_cell["row"] and cell["column"] == new_cell["column"]:
            cells[index] = new_cell
            return
    raise AssertionError("test grid has no cell to replace")


def _make_empty(data: GridData, row: int, column: int) -> None:
    """Turn the cell at (row, column) into an empty cell."""
    _replace_cell(data, {"type": "empty", "row": row, "column": column})


def _make_letter(data: GridData, row: int, column: int) -> None:
    """Turn the cell at (row, column) into a letter cell."""
    _replace_cell(data, {"type": "letter", "row": row, "column": column})


def _clue_at(data: GridData, row: int, column: int, index: int) -> CellData:
    """Return the clue dictionary `index` of the clue cell at (row, column)."""
    return _find_cell(data, row, column)["clues"][index]


def _error_message(text: str) -> str:
    """Import a grid that must be rejected and return the error message."""
    with pytest.raises(GridImportError) as error_info:
        import_grid(text)
    return str(error_info.value)


def _letter(row: int, column: int) -> CellData:
    """Build a letter cell dictionary."""
    return {"type": "letter", "row": row, "column": column}


def _empty(row: int, column: int) -> CellData:
    """Build an empty cell dictionary."""
    return {"type": "empty", "row": row, "column": column}


def _clue_cell(row: int, column: int, *clues: tuple[str, str, str]) -> CellData:
    """Build a clue cell dictionary from (text, arrow, answer) tuples."""
    clue_dicts = []
    for text, arrow, answer in clues:
        clue_dicts.append({"text": text, "arrow": arrow, "answer": answer})
    return {"type": "clue", "row": row, "column": column, "clues": clue_dicts}


def _small_grid(width: int, height: int, cells: list[CellData]) -> str:
    """Build the JSON text of a small hand-made grid."""
    return _dump({"width": width, "height": height, "cells": cells})


# Parse errors (all criteria)


def test_ac1_invalid_json_becomes_grid_import_error() -> None:
    with pytest.raises(GridImportError) as error_info:
        import_grid("not json")
    assert isinstance(error_info.value.__cause__, ValidationError)


def test_ac1_missing_cell_is_named_and_cause_is_validation_error(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    data["cells"].remove(_find_cell(data, 2, 3))
    with pytest.raises(GridImportError) as error_info:
        import_grid(_dump(data))
    assert "(2, 3)" in str(error_info.value)
    assert isinstance(error_info.value.__cause__, ValidationError)


def test_ac1_clue_cell_without_clue_is_rejected(fx01_text: str) -> None:
    data = _load(fx01_text)
    _find_cell(data, 0, 2)["clues"] = []
    with pytest.raises(GridImportError) as error_info:
        import_grid(_dump(data))
    assert isinstance(error_info.value.__cause__, ValidationError)


def test_ac1_clue_cell_with_three_clues_is_rejected(fx01_text: str) -> None:
    data = _load(fx01_text)
    clue = _clue_at(data, 0, 2, 0)
    _find_cell(data, 0, 2)["clues"] = [clue, clue, clue]
    with pytest.raises(GridImportError) as error_info:
        import_grid(_dump(data))
    assert isinstance(error_info.value.__cause__, ValidationError)


# AC-1: arrows


@pytest.mark.parametrize(
    ("row", "column", "arrow", "clue_cell", "target"),
    [
        (2, 0, "down", "(2, 0)", "(3, 0)"),
        (0, 4, "right", "(0, 4)", "(0, 5)"),
        (4, 0, "down", "(4, 0)", "(5, 0)"),
    ],
)
def test_ac1_arrow_to_clue_cell_or_outside_names_both_cells(
    fx01_text: str, row: int, column: int, arrow: str, clue_cell: str, target: str
) -> None:
    data = _load(fx01_text)
    _clue_at(data, row, column, 0)["arrow"] = arrow
    message = _error_message(_dump(data))
    assert clue_cell in message
    assert target in message


def test_ac1_arrow_to_empty_cell_names_both_cells(fx01_text: str) -> None:
    data = _load(fx01_text)
    _make_empty(data, 0, 1)
    message = _error_message(_dump(data))
    assert "(0, 0)" in message
    assert "(0, 1)" in message


def test_ac1_arrow_error_wins_over_run_without_clue(fx01_text: str) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 4, 0)["arrow"] = "right"
    message = _error_message(_dump(data))
    assert "(0, 5)" in message


def test_ac1_first_clue_cell_in_row_major_order_is_reported(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _clue_at(data, 2, 0, 0)["arrow"] = "down"
    _clue_at(data, 0, 4, 0)["arrow"] = "right"
    message = _error_message(_dump(data))
    assert "(0, 5)" in message
    assert "(3, 0)" not in message


def test_ac1_first_clue_of_a_cell_is_reported(fx01_text: str) -> None:
    data = _load(fx01_text)
    _make_empty(data, 1, 0)
    _make_empty(data, 0, 1)
    message = _error_message(_dump(data))
    assert "(1, 0)" in message
    assert "(0, 1)" not in message


def test_ac1_arrow_error_wins_over_answer_length(fx01_text: str) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 2, 0)["answer"] = "MIM"
    _clue_at(data, 2, 0, 0)["arrow"] = "down"
    message = _error_message(_dump(data))
    assert "(3, 0)" in message


# AC-2: runs without a clue


def test_ac2_horizontal_run_without_clue_names_first_and_last_cell(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _make_empty(data, 3, 0)
    message = _error_message(_dump(data))
    assert "(3, 1)" in message
    assert "(3, 4)" in message


def test_ac2_vertical_run_without_clue_names_first_and_last_cell(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _make_empty(data, 0, 2)
    message = _error_message(_dump(data))
    assert "(1, 2)" in message
    assert "(4, 2)" in message


def test_ac2_run_error_wins_over_crossing_letters(fx01_text: str) -> None:
    data = _load(fx01_text)
    _make_empty(data, 3, 0)
    _clue_at(data, 0, 2, 0)["answer"] = "MIMA"
    message = _error_message(_dump(data))
    assert "(3, 1)" in message
    assert "(3, 4)" in message


def test_ac2_word_starting_in_the_middle_of_a_run_gives_it_no_clue() -> None:
    cells = [
        _clue_cell(0, 0, ("Un", "right", "A")),
        _letter(0, 1),
        _clue_cell(1, 0, ("Deux", "right_then_down", "BC")),
        _letter(1, 1),
        _empty(2, 0),
        _letter(2, 1),
    ]
    message = _error_message(_small_grid(2, 3, cells))
    assert "(0, 1)" in message
    assert "(2, 1)" in message


def test_ac2_horizontal_runs_are_reported_before_vertical_runs() -> None:
    # Vertical run (0, 1) to (2, 1) and horizontal run (4, 0) to (4, 2) both
    # have no clue (each has a word starting in its middle or not at its
    # start). The vertical run starts earlier, but horizontal runs come first.
    cells = [
        _clue_cell(0, 0, ("Un", "right", "A")),
        _letter(0, 1),
        _empty(0, 2),
        _clue_cell(1, 0, ("Deux", "right_then_down", "BC")),
        _letter(1, 1),
        _empty(1, 2),
        _empty(2, 0),
        _letter(2, 1),
        _empty(2, 2),
        _clue_cell(3, 0, ("Trois", "down", "D")),
        _clue_cell(3, 1, ("Quatre", "down_then_right", "EF")),
        _empty(3, 2),
        _letter(4, 0),
        _letter(4, 1),
        _letter(4, 2),
    ]
    message = _error_message(_small_grid(3, 5, cells))
    assert "(4, 0)" in message
    assert "(4, 2)" in message
    assert "(0, 1)" not in message
    assert "(2, 1)" not in message


def _square_grid(size: int, special_cells: list[CellData]) -> str:
    """Build a square grid from some cells, every other position being empty."""
    special_positions = {}
    for cell in special_cells:
        special_positions[(cell["row"], cell["column"])] = cell
    cells = []
    for row in range(size):
        for column in range(size):
            cells.append(special_positions.get((row, column), _empty(row, column)))
    return _small_grid(size, size, cells)


def test_ac2_first_horizontal_run_in_row_major_order_is_reported() -> None:
    # Each letter is a one-cell vertical word, so only the run check can fail.
    # Run (1, 2) to (1, 3) comes first in row-major order, run (3, 0) to (3, 1)
    # comes first in column-major order.
    special_cells = [
        _clue_cell(0, 2, ("Un", "down", "A")),
        _clue_cell(0, 3, ("Deux", "down", "B")),
        _letter(1, 2),
        _letter(1, 3),
        _clue_cell(2, 0, ("Trois", "down", "C")),
        _clue_cell(2, 1, ("Quatre", "down", "D")),
        _letter(3, 0),
        _letter(3, 1),
    ]
    message = _error_message(_square_grid(4, special_cells))
    assert "(1, 2)" in message
    assert "(1, 3)" in message
    assert "(3, 0)" not in message
    assert "(3, 1)" not in message


def test_ac2_first_vertical_run_in_column_major_order_is_reported() -> None:
    # Each letter is a one-cell horizontal word, so only the run check can fail.
    # Run (2, 1) to (3, 1) comes first in column-major order, run (0, 3) to
    # (1, 3) comes first in row-major order.
    special_cells = [
        _clue_cell(2, 0, ("Un", "right", "A")),
        _clue_cell(3, 0, ("Deux", "right", "B")),
        _letter(2, 1),
        _letter(3, 1),
        _clue_cell(0, 2, ("Trois", "right", "C")),
        _clue_cell(1, 2, ("Quatre", "right", "D")),
        _letter(0, 3),
        _letter(1, 3),
    ]
    message = _error_message(_square_grid(4, special_cells))
    assert "(2, 1)" in message
    assert "(3, 1)" in message
    assert "(0, 3)" not in message
    assert "(1, 3)" not in message


def test_ac2_isolated_letters_are_not_runs(fx01_text: str) -> None:
    report = import_grid(fx01_text)
    assert report.word_count == 8


# AC-3: crossing letters


def test_ac3_disagreeing_words_are_named_with_the_shared_cell(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 2, 0)["answer"] = "MIMA"
    message = _error_message(_dump(data))
    assert "MIMA" in message
    assert "LEST" in message
    assert "(4, 2)" in message


def test_ac3_second_disagreement_names_its_words_and_cell(fx01_text: str) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 4, 0)["answer"] = "SANT"
    message = _error_message(_dump(data))
    assert "SANT" in message
    assert "VIDE" in message
    assert "(2, 4)" in message


def test_ac3_first_shared_cell_in_row_major_order_is_reported(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 2, 0)["answer"] = "MIMA"
    _clue_at(data, 0, 4, 0)["answer"] = "SANT"
    message = _error_message(_dump(data))
    assert "(2, 4)" in message
    assert "(4, 2)" not in message


# AC-4: a valid grid


def test_ac4_fx01_report_counts(fx01_text: str) -> None:
    report = import_grid(fx01_text)
    assert isinstance(report, ImportReport)
    assert report.word_count == 8
    assert report.letter_cell_count == 18
    assert report.clue_cell_count == 7


def test_ac4_fx01_report_holds_the_parsed_grid(fx01_text: str) -> None:
    report = import_grid(fx01_text)
    assert report.grid == Grid.model_validate_json(fx01_text)


def test_ac4_report_is_frozen(fx01_text: str) -> None:
    report = import_grid(fx01_text)
    # The attribute name goes through a variable: a direct assignment is
    # rejected by the type checker on a frozen model, and setattr with a
    # constant name is rejected by the linter.
    attribute_name = "word_count"
    with pytest.raises(ValidationError):
        setattr(report, attribute_name, 9)


def test_ac4_empty_cells_are_not_counted() -> None:
    cells = [
        _clue_cell(0, 0, ("Deux lettres", "right", "AB")),
        _letter(0, 1),
        _letter(0, 2),
        _empty(0, 3),
    ]
    report = import_grid(_small_grid(4, 1, cells))
    assert report.word_count == 1
    assert report.letter_cell_count == 2
    assert report.clue_cell_count == 1


def test_ac4_one_letter_word_is_accepted() -> None:
    cells = [_clue_cell(0, 0, ("Une lettre", "right", "A")), _letter(0, 1)]
    report = import_grid(_small_grid(2, 1, cells))
    assert report.word_count == 1
    assert report.letter_cell_count == 1
    assert report.clue_cell_count == 1


# AC-5: answer length


def test_ac5_answer_too_short_names_clue_cell_and_answer(fx01_text: str) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 2, 0)["answer"] = "MIM"
    message = _error_message(_dump(data))
    assert "(0, 2)" in message
    assert "MIM" in message


def test_ac5_answer_too_long_names_clue_cell_and_answer(fx01_text: str) -> None:
    data = _load(fx01_text)
    _clue_at(data, 2, 0, 0)["answer"] = "VIDES"
    message = _error_message(_dump(data))
    assert "(2, 0)" in message
    assert "VIDES" in message


def test_ac5_first_clue_cell_in_row_major_order_is_reported(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _clue_at(data, 0, 2, 0)["answer"] = "MIM"
    _clue_at(data, 2, 0, 0)["answer"] = "VIDES"
    message = _error_message(_dump(data))
    assert "(0, 2)" in message
    assert "VIDES" not in message


def test_ac5_length_error_wins_over_same_word(fx01_text: str) -> None:
    data = _load(fx01_text)
    second_clue = _clue_at(data, 0, 0, 1)
    second_clue["arrow"] = "down_then_right"
    second_clue["answer"] = "TAMIS"
    _clue_at(data, 2, 0, 0)["answer"] = "VIDES"
    message = _error_message(_dump(data))
    assert "(2, 0)" in message
    assert "VIDES" in message


# AC-6: letter cell in no word


def test_ac6_letter_cell_in_no_word_is_named(fx01_text: str) -> None:
    data = _load(fx01_text)
    del _find_cell(data, 0, 0)["clues"][1]
    message = _error_message(_dump(data))
    assert "(0, 1)" in message
    # The run error that would come next says "from (0, 1) to (4, 1)".
    assert "(4, 1)" not in message


def test_ac6_clue_cell_replaced_by_letter_is_named_first(fx01_text: str) -> None:
    data = _load(fx01_text)
    _make_letter(data, 4, 0)
    message = _error_message(_dump(data))
    assert "(4, 0)" in message
    # The run error that would come next says "from (4, 0) to (4, 4)".
    assert "(4, 4)" not in message


def test_ac6_first_letter_cell_in_row_major_order_is_reported(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    _make_letter(data, 3, 0)
    _make_letter(data, 4, 0)
    message = _error_message(_dump(data))
    assert "(3, 0)" in message
    assert "(4, 0)" not in message
    # The run error that would come next says "from (3, 0) to (3, 4)".
    assert "(3, 4)" not in message


def test_ac6_isolated_letter_cell_in_no_word_is_named() -> None:
    # (0, 4) is no run and no word, so only the AC-6 check can reject it.
    cells = [
        _clue_cell(0, 0, ("Deux lettres", "right", "AB")),
        _letter(0, 1),
        _letter(0, 2),
        _empty(0, 3),
        _letter(0, 4),
    ]
    message = _error_message(_small_grid(5, 1, cells))
    assert "(0, 4)" in message


# AC-7: two clues with the same word


def test_ac7_two_clues_of_one_cell_with_same_word_are_named(
    fx01_text: str,
) -> None:
    data = _load(fx01_text)
    second_clue = _clue_at(data, 0, 0, 1)
    second_clue["arrow"] = "down_then_right"
    second_clue["answer"] = "TAMIS"
    message = _error_message(_dump(data))
    assert "(0, 0)" in message
    assert "Passoire fine" in message
    assert "De la marine" in message


def test_ac7_clues_of_two_cells_with_same_word_are_named() -> None:
    cells = [
        _empty(0, 0),
        _clue_cell(0, 1, ("Haut", "down_then_right", "AB")),
        _empty(0, 2),
        _clue_cell(1, 0, ("Gauche", "right", "AB")),
        _letter(1, 1),
        _letter(1, 2),
    ]
    message = _error_message(_small_grid(3, 2, cells))
    assert "(0, 1)" in message
    assert "(1, 0)" in message
    assert "Haut" in message
    assert "Gauche" in message
