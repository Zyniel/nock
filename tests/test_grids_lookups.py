"""Tests of grids AC-22, AC-23 and AC-24: the lookups of a grid (rule 12).

AC-22: `Grid.words` lists the words in clue order. AC-23:
`Grid.solution_letter` gives the solution letter of a cell. AC-24: FX-02 keeps
its JSON as it is, and every one of its letter cells has a solution letter.

The grids are loaded through the model (`Grid.model_validate_json`), not through
the import: the lookups refuse no grid (rule 12), so a grid the import would
refuse is a valid input here.

Choices where the spec leaves room:

- AC-23: `solution_letter` of a position outside the grid, including a negative
  one, gives None and raises nothing (rule 12: "a cell no word reaches has none").
- AC-23, rule 12: a word whose answer is shorter than its cells has no letter at
  the cells past its answer, so the next word in clue order that holds the cell
  gives the letter (`MIME` changed to `MIM`).
"""

from __future__ import annotations

import json
import random

import pytest
from pydantic import ValidationError

from grids_harness import FX01_HYPHENS, JsonData, with_answers
from nock.grid import Grid, Position, Word

# ---- Values of the spec --------------------------------------------------------------

FX02_LETTER_CELLS = 125


# ---- Builders ------------------------------------------------------------------------


def across(row: int, first_column: int, last_column: int) -> tuple[Position, ...]:
    """The cells of an across word, in reading order."""
    cells: list[Position] = []
    for column in range(first_column, last_column + 1):
        cells.append((row, column))
    return tuple(cells)


def down(column: int, first_row: int, last_row: int) -> tuple[Position, ...]:
    """The cells of a down word, in reading order."""
    cells: list[Position] = []
    for row in range(first_row, last_row + 1):
        cells.append((row, column))
    return tuple(cells)


def fx01_words() -> list[Word]:
    """The 8 words of FX-01 in clue order, written out from the fixture."""
    return [
        Word(row=0, column=0, clue_index=0, cells=across(1, 0, 4), letters="TAMIS"),
        Word(row=0, column=0, clue_index=1, cells=down(1, 0, 4), letters="NAVAL"),
        Word(row=0, column=2, clue_index=0, cells=down(2, 1, 4), letters="MIME"),
        Word(row=0, column=3, clue_index=0, cells=down(3, 1, 4), letters="IDES"),
        Word(row=0, column=4, clue_index=0, cells=down(4, 1, 4), letters="SENT"),
        Word(row=2, column=0, clue_index=0, cells=across(2, 1, 4), letters="VIDE"),
        Word(row=3, column=0, clue_index=0, cells=across(3, 1, 4), letters="AMEN"),
        Word(row=4, column=0, clue_index=0, cells=across(4, 1, 4), letters="LEST"),
    ]


def grid_of(data: JsonData) -> Grid:
    """Load a grid given as a dictionary, through JSON and the model only."""
    return Grid.model_validate_json(json.dumps(data))


def fx01_data(fx01_text: str) -> JsonData:
    """The JSON of FX-01 as a dictionary (any: raw JSON)."""
    return json.loads(fx01_text)


def clue_cell_data(data: JsonData, row: int, column: int) -> JsonData:
    """The clue cell of a grid's data at (row, column)."""
    for cell in data["cells"]:
        if (cell["row"], cell["column"]) == (row, column):
            return cell
    raise AssertionError(f"no cell at ({row}, {column})")


def with_arrow_turned_right(fx01_text: str) -> Grid:
    """FX-01 with the clue of (0, 4) turned `right`: it points outside the grid."""
    data = fx01_data(fx01_text)
    clue_cell_data(data, 0, 4)["clues"][0]["arrow"] = "right"
    return grid_of(data)


def without_marine_clue(fx01_text: str) -> Grid:
    """FX-01 without the clue `De la marine`: (0, 1) is in no word."""
    data = fx01_data(fx01_text)
    clue_cell = clue_cell_data(data, 0, 0)
    kept: list[JsonData] = []
    for clue in clue_cell["clues"]:
        if clue["text"] != "De la marine":
            kept.append(clue)
    clue_cell["clues"] = kept
    return grid_of(data)


def with_answer_changed(fx01_text: str, old: str, new: str) -> Grid:
    """FX-01 with one answer written another way."""
    return Grid.model_validate_json(with_answers(fx01_text, {old: new}))


@pytest.fixture
def fx01(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


# ---- AC-22: the words of a grid ------------------------------------------------------


def test_ac22_fx01_lists_its_eight_words_in_clue_order(fx01: Grid) -> None:
    words = fx01.words
    assert isinstance(words, tuple)
    assert list(words) == fx01_words()


def test_ac22_first_second_and_last_words_of_fx01(fx01: Grid) -> None:
    words = fx01.words
    assert len(words) == 8
    assert words[0] == Word(
        row=0, column=0, clue_index=0, cells=across(1, 0, 4), letters="TAMIS"
    )
    assert words[1] == Word(
        row=0, column=0, clue_index=1, cells=down(1, 0, 4), letters="NAVAL"
    )
    assert words[-1] == Word(
        row=4, column=0, clue_index=0, cells=across(4, 1, 4), letters="LEST"
    )


def test_ac22_a_clue_that_does_not_resolve_has_no_word(fx01_text: str) -> None:
    grid = with_arrow_turned_right(fx01_text)
    clues = []
    for word in grid.words:
        clues.append((word.row, word.column, word.clue_index))
    assert len(clues) == 7
    assert (0, 4, 0) not in clues
    expected: list[tuple[int, int, int]] = []
    for word in fx01_words():
        if (word.row, word.column) != (0, 4):
            expected.append((word.row, word.column, word.clue_index))
    assert clues == expected


def test_ac22_cells_listed_in_any_order_give_the_same_words(fx01_text: str) -> None:
    data = fx01_data(fx01_text)
    random.Random(22).shuffle(data["cells"])
    assert list(grid_of(data).words) == fx01_words()


def test_ac22_letters_leave_out_the_separators(fx01_text: str) -> None:
    grid = Grid.model_validate_json(with_answers(fx01_text, FX01_HYPHENS))
    assert list(grid.words) == fx01_words()


def test_ac22_a_word_is_frozen(fx01: Grid) -> None:
    first_word = fx01.words[0]
    with pytest.raises(ValidationError):
        first_word.letters = "TAMIX"


# ---- AC-23: the solution letter of a cell --------------------------------------------


@pytest.mark.parametrize(
    ("row", "column", "letter"),
    [
        (1, 0, "T"),
        (4, 2, "E"),
        (0, 1, "N"),
        (2, 3, "D"),
        (4, 4, "T"),
    ],
)
def test_ac23_fx01_gives_the_letter_of_a_letter_cell(
    fx01: Grid, row: int, column: int, letter: str
) -> None:
    assert fx01.solution_letter(row, column) == letter


@pytest.mark.parametrize(
    ("row", "column"),
    [(0, 0), (0, 2), (2, 0), (5, 0), (0, 5), (5, 5), (-1, 1), (1, -1), (99, 99)],
)
def test_ac23_a_clue_cell_or_a_position_outside_the_grid_gives_none(
    fx01: Grid, row: int, column: int
) -> None:
    assert fx01.solution_letter(row, column) is None


def test_ac23_a_letter_cell_in_no_word_gives_none(fx01_text: str) -> None:
    grid = without_marine_clue(fx01_text)
    assert grid.solution_letter(0, 1) is None
    assert grid.solution_letter(1, 0) == "T"


def test_ac23_a_grid_the_import_would_refuse_still_answers(fx01_text: str) -> None:
    grid = with_answer_changed(fx01_text, "MIME", "MIMA")
    assert grid.solution_letter(4, 2) == "A"


def test_ac23_a_word_with_no_letter_there_leaves_the_cell_to_the_next(
    fx01_text: str,
) -> None:
    grid = with_answer_changed(fx01_text, "MIME", "MIM")
    assert grid.solution_letter(3, 2) == "M"
    assert grid.solution_letter(4, 2) == "E"


# ---- AC-24: FX-02 --------------------------------------------------------------------


def test_ac24_fx02_survives_load_save_load(fx02_text: str) -> None:
    first = Grid.model_validate_json(fx02_text)
    second = Grid.model_validate_json(first.model_dump_json())
    assert second == first
    assert second.model_dump_json() == first.model_dump_json()


def test_ac24_two_loads_of_fx02_are_equal(fx02_text: str) -> None:
    assert Grid.model_validate_json(fx02_text) == Grid.model_validate_json(fx02_text)


def test_ac24_the_saved_json_holds_only_the_fields_of_rule_8(fx02: Grid) -> None:
    saved: JsonData = json.loads(fx02.model_dump_json())
    assert set(saved) == {"width", "height", "cells"}
    for cell in saved["cells"]:
        if cell["type"] == "clue":
            assert set(cell) == {"type", "row", "column", "clues"}
            for clue in cell["clues"]:
                assert set(clue) == {"text", "arrow", "answer"}
        else:
            assert set(cell) == {"type", "row", "column"}


def test_ac24_every_letter_cell_of_fx02_has_a_solution_letter(fx02: Grid) -> None:
    letter_cells = 0
    for row in range(fx02.height):
        for column in range(fx02.width):
            cell = fx02.cell_at(row, column)
            letter = fx02.solution_letter(row, column)
            if cell.type == "letter":
                letter_cells += 1
                assert letter is not None
                assert len(letter) == 1
                assert letter.isascii()
                assert letter.isalpha()
                assert letter.isupper()
            else:
                assert letter is None
    assert letter_cells == FX02_LETTER_CELLS
