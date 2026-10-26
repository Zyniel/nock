"""Tests of grid-files AC-11 to AC-15: how a file's clues become the model's.

Where a clue sits (`location`), the order of a cell's clues, the arrow that comes
from `cells`, the check that `cells` is the resolved word, and the `solution` and
`enumeration` checks that come last. The shared setup is in `grid_files_harness`.

Choices where the spec leaves room:

- AC-14, "with SENT also changed to SE": the clue's `enumeration` is changed to
  "2" too, so that only the length check of rule 6 can compete with the `cells`
  check. That the message is not the length check's is read from the answer `SE`
  not being quoted in it.
- AC-15: "0-5" and "2--3" are refused like the criterion's samples, since
  rule 9 asks for counts of one or more.
"""

from __future__ import annotations

import copy
import re

import pytest

from grid_files_harness import (
    cell_with_clues,
    clue_named,
    fx01_ipuz_data,
    mini_data,
    read_data,
    read_error,
)
from nock.grid import Arrow

# ---- AC-11: where a clue sits --------------------------------------------------


@pytest.mark.parametrize(
    ("location", "cell_name"),
    [
        pytest.param([5, 0], "(0, 5)", id="outside-the-grid"),
        pytest.param([1, 0], "(0, 1)", id="on-a-letter-cell"),
    ],
)
def test_ac11_a_location_outside_the_grid_or_on_a_letter_cell_is_refused(
    location: list[int], cell_name: str
) -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["location"] = location

    message = read_error(data)

    assert cell_name in message


# ---- AC-12: the order of a cell's clues ----------------------------------------


def test_ac12_the_clues_of_a_cell_come_in_the_order_of_clues() -> None:
    data = fx01_ipuz_data()
    clues = data["clues"]["Clues"]
    clues[0], clues[1] = clues[1], clues[0]

    grid_file = read_data(data)

    cell = cell_with_clues(grid_file.grid, 0, 0)
    texts = []
    for clue in cell.clues:
        texts.append(clue.text)
    assert texts == ["De la marine", "Passoire fine"]


def test_ac12_a_third_clue_in_a_cell_is_refused_naming_it() -> None:
    data = fx01_ipuz_data()
    third_clue = copy.deepcopy(clue_named(data, "Passoire fine"))
    third_clue["clue"] = "Troisième indice"
    data["clues"]["Clues"].append(third_clue)

    message = read_error(data)

    assert "(0, 0)" in message


# ---- AC-13: the arrow comes from the clue cell and the first cells -------------


@pytest.mark.parametrize(
    ("cells", "cell_name"),
    [
        pytest.param([[4, 2], [4, 3], [4, 4]], "(2, 4)", id="first-cell-too-far"),
        pytest.param(
            [[4, 1], [3, 2], [3, 3], [3, 4]], "(2, 3)", id="second-cell-diagonal"
        ),
    ],
)
def test_ac13_cells_that_do_not_start_the_word_are_refused_naming_both_cells(
    cells: list[list[int]], cell_name: str
) -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["cells"] = cells

    message = read_error(data)

    assert "(0, 4)" in message
    assert cell_name in message


def test_ac13_a_first_cell_outside_the_grid_gives_the_arrow_error_of_grids() -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["cells"] = [[5, 0]]

    message = read_error(data)

    assert "(0, 4)" in message
    assert "(0, 5)" in message


@pytest.mark.parametrize(
    ("vertical", "arrow"),
    [
        pytest.param(False, Arrow.RIGHT, id="right-of-its-clue-cell"),
        pytest.param(True, Arrow.DOWN, id="below-its-clue-cell"),
    ],
)
def test_ac13_a_one_cell_word_takes_the_straight_arrow_of_its_first_cell(
    vertical: bool, arrow: Arrow
) -> None:
    data = mini_data("A", "A", enumeration="1", vertical=vertical)

    grid_file = read_data(data)

    assert cell_with_clues(grid_file.grid, 0, 0).clues[0].arrow == arrow


# ---- AC-14: cells is the resolved word -----------------------------------------


@pytest.mark.parametrize(
    "cells",
    [
        pytest.param([[4, 1], [4, 2]], id="cut-short"),
        pytest.param([[4, 1], [4, 2], [4, 3], [3, 4]], id="wrong-last-cell"),
        pytest.param([[4, 1], [4, 2], [4, 3], [4, 4], [4, 5]], id="too-long"),
    ],
)
def test_ac14_cells_that_are_not_the_resolved_word_are_refused_naming_the_clue(
    cells: list[list[int]],
) -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Flaire")["cells"] = cells

    message = read_error(data)

    assert "(0, 4)" in message
    assert "Flaire" in message


def test_ac14_the_check_comes_before_the_length_of_the_answer() -> None:
    data = fx01_ipuz_data()
    clue = clue_named(data, "Flaire")
    clue["cells"] = [[4, 1], [4, 2]]
    clue["answer"] = "SE"
    clue["enumeration"] = "2"

    message = read_error(data)

    assert "(0, 4)" in message
    assert "Flaire" in message
    assert re.search(r"\bSE\b", message) is None, message


# ---- AC-15: solution and enumeration -------------------------------------------


@pytest.mark.parametrize(
    ("row", "column", "letter"),
    [
        pytest.param(1, 4, "X", id="wrong-letter"),
        pytest.param(0, 0, "A", id="letter-on-a-clue-cell"),
    ],
)
def test_ac15_a_solution_that_disagrees_with_the_answers_is_refused_naming_the_cell(
    row: int, column: int, letter: str
) -> None:
    data = fx01_ipuz_data()
    data["solution"][row][column] = letter

    message = read_error(data)

    assert f"({row}, {column})" in message


def test_ac15_the_solution_is_checked_after_every_check_of_the_import() -> None:
    data = fx01_ipuz_data()
    data["solution"][1][4] = "X"
    clue_named(data, "Artiste muet")["answer"] = "MIMA"

    message = read_error(data)

    assert "MIMA" in message
    assert "LEST" in message
    assert "(4, 2)" in message
    assert "(1, 4)" not in message


@pytest.mark.parametrize("enumeration", ["5", None])
def test_ac15_an_enumeration_that_counts_the_letters_loads(
    enumeration: str | None,
) -> None:
    data = fx01_ipuz_data()
    clue = clue_named(data, "Passoire fine")
    if enumeration is None:
        del clue["enumeration"]
    else:
        clue["enumeration"] = enumeration

    assert read_data(data) == read_data(fx01_ipuz_data())


@pytest.mark.parametrize("enumeration", ["4", "2 3", "2'3", "5-", "0-5", "2--3"])
def test_ac15_an_enumeration_that_is_not_the_letters_counted_is_refused(
    enumeration: str,
) -> None:
    data = fx01_ipuz_data()
    clue_named(data, "Passoire fine")["enumeration"] = enumeration

    message = read_error(data)

    assert "(0, 0)" in message
    assert "Passoire fine" in message
