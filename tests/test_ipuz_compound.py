"""Tests of content/ipuz AC-14: the breaks of a word in a grid file.

`enumeration`, an answer written with separators and the `dashed` edges of the
puzzle all say where a word breaks, and must agree (rule 5). Positions are
written `[column, row]` in a file and `(row, column)` in a message. The shared
setup is in `grid_files_harness`.

Choices where the spec leaves room:

- A `dashed` edge that is not an edge of the grid's breaks, outside the grid or
  beside a block is expected to name the cells of the edge it can name, in
  `(row, column)`: both cells when both are in the grid, else the one inside.
"""

from __future__ import annotations

import pytest

from grid_files_harness import (
    JsonData,
    cell_with_clues,
    clue_named,
    dashed_cell,
    fx01_ipuz_data,
    mini_data,
    read_data,
    read_error,
)


def vide_data(answer: str = "VI-DE", enumeration: str | None = "2-2") -> JsonData:
    """FX-01 with the answer of `Sans contenu` (VIDE across from (2, 1)) rewritten."""
    data = fx01_ipuz_data()
    clue = clue_named(data, "Sans contenu")
    clue["answer"] = answer
    if enumeration is None:
        del clue["enumeration"]
    else:
        clue["enumeration"] = enumeration
    return data


def set_dashed(data: JsonData, column: int, row: int, letters: str) -> None:
    """Draw `letters` as the dashed edges of the letter cell at [column, row]."""
    data["puzzle"][row][column] = dashed_cell(letters)


def add_naval_hyphen(data: JsonData) -> None:
    """Write NAVAL (down from (0, 1)) as NA-VAL."""
    clue = clue_named(data, "De la marine")
    clue["answer"] = "NA-VAL"
    clue["enumeration"] = "2-3"


# ---- The answer and the enumeration --------------------------------------------


@pytest.mark.parametrize(
    ("answer", "enumeration", "model_answer"),
    [
        pytest.param("VIDE", "2-2", "VI-DE", id="letters-with-enumeration"),
        pytest.param("VI-DE", None, "VI-DE", id="hyphen-without-enumeration"),
        pytest.param("VI-DE", "2-2", "VI-DE", id="hyphen-with-enumeration"),
        pytest.param("VIDE", "2.2", "VI.DE", id="letters-with-a-dot"),
        pytest.param("VI.DE", "2.2", "VI.DE", id="dot-with-enumeration"),
        pytest.param("VI DE", None, "VI DE", id="space-without-enumeration"),
    ],
)
def test_ac14_a_word_loads_with_its_separator_and_its_break(
    answer: str, enumeration: str | None, model_answer: str
) -> None:
    grid_file = read_data(vide_data(answer, enumeration))

    clue = cell_with_clues(grid_file.grid, 2, 0).clues[0]
    assert clue.answer == model_answer
    assert clue.breaks == (2,)


def test_ac14_an_enumeration_without_separator_leaves_the_answer_as_written() -> None:
    grid_file = read_data(mini_data("ÊTRE", "ETRE", enumeration="4"))

    clue = cell_with_clues(grid_file.grid, 0, 0).clues[0]
    assert clue.answer == "ÊTRE"
    assert clue.letters == "ETRE"
    assert clue.breaks == ()


@pytest.mark.parametrize("answer", ["ARCENCIEL", "ARC-EN-CIEL"])
def test_ac14_an_enumeration_with_hyphens_gives_the_breaks(answer: str) -> None:
    grid_file = read_data(mini_data(answer, "ARCENCIEL", enumeration="3-2-4"))

    clue = cell_with_clues(grid_file.grid, 0, 0).clues[0]
    assert clue.answer == "ARC-EN-CIEL"
    assert clue.breaks == (3, 5)


@pytest.mark.parametrize(
    ("answer", "letters", "enumeration", "model_answer", "breaks"),
    [
        ("AI", "AI", "1.1", "A.I", (1,)),
        ("AI", "AI", "1 1", "A I", (1,)),
        ("A.I", "AI", "1.1", "A.I", (1,)),
        ("AUJOURDHUI", "AUJOURDHUI", "7'3", "AUJOURD'HUI", (7,)),
        ("AUJOURD'HUI", "AUJOURDHUI", "7'3", "AUJOURD'HUI", (7,)),
        ("ARCENCIEL", "ARCENCIEL", "3-2 4", "ARC-EN CIEL", (3, 5)),
        ("ARC-EN CIEL", "ARCENCIEL", None, "ARC-EN CIEL", (3, 5)),
        ("AIDE", "AIDE", "1.1-2", "A.I-DE", (1, 2)),
    ],
)
def test_ac14_every_separator_of_rule_4_gives_a_break(
    answer: str,
    letters: str,
    enumeration: str | None,
    model_answer: str,
    breaks: tuple[int, ...],
) -> None:
    grid_file = read_data(mini_data(answer, letters, enumeration=enumeration))

    clue = cell_with_clues(grid_file.grid, 0, 0).clues[0]
    assert clue.answer == model_answer
    assert clue.letters == letters
    assert clue.breaks == breaks


def test_ac14_an_answer_with_hyphens_and_no_enumeration_gives_the_breaks() -> None:
    grid_file = read_data(mini_data("ARC-EN-CIEL", "ARCENCIEL"))

    clue = cell_with_clues(grid_file.grid, 0, 0).clues[0]
    assert clue.answer == "ARC-EN-CIEL"
    assert clue.breaks == (3, 5)


@pytest.mark.parametrize(
    ("answer", "enumeration"),
    [
        pytest.param("VID-E", "2-2", id="hyphen-in-another-place"),
        pytest.param("VI-DE", "4", id="hyphen-under-an-enumeration-with-none"),
        pytest.param("VI DE", "2.2", id="space-under-a-dot"),
        pytest.param("VI-DE", "2.2", id="hyphen-under-a-dot"),
        pytest.param("VI.DE", "2-2", id="dot-under-a-hyphen"),
    ],
)
def test_ac14_separators_of_the_answer_and_of_the_enumeration_must_agree(
    answer: str, enumeration: str
) -> None:
    message = read_error(vide_data(answer, enumeration))

    assert "(2, 0)" in message
    assert "Sans contenu" in message


@pytest.mark.parametrize(
    ("answer", "letters", "enumeration"),
    [
        ("ARC-EN-CIEL", "ARCENCIEL", "3-3-3"),
        ("A I", "AI", "1.1"),
        ("A-I", "AI", "1.1"),
    ],
)
def test_ac14_separators_of_a_one_line_grid_must_agree_too(
    answer: str, letters: str, enumeration: str
) -> None:
    data = mini_data(answer, letters, enumeration=enumeration)

    message = read_error(data)

    assert "(0, 0)" in message
    assert "Indice" in message


# ---- The dashed edges -----------------------------------------------------------


@pytest.mark.parametrize("answer", ["VI-DE", "VI.DE", "VI DE"])
@pytest.mark.parametrize(
    ("column", "row", "letters"),
    [
        pytest.param(2, 2, "R", id="right-of-the-letter-before"),
        pytest.param(3, 2, "L", id="left-of-the-letter-after"),
    ],
)
def test_ac14_a_dashed_edge_that_is_the_edge_of_the_break_agrees(
    answer: str, column: int, row: int, letters: str
) -> None:
    data = vide_data(answer, None)
    set_dashed(data, column, row, letters)

    assert read_data(data) == read_data(vide_data(answer, None))


def test_ac14_a_dashed_edge_next_to_the_break_edge_is_refused_naming_it() -> None:
    data = vide_data()
    set_dashed(data, 3, 2, "R")

    message = read_error(data)

    assert "(2, 3)" in message
    assert "(2, 4)" in message
    assert message.index("(2, 3)") < message.index("(2, 4)")


def test_ac14_a_dashed_edge_on_a_word_with_no_break_is_refused_naming_it() -> None:
    data = vide_data("VIDE", None)
    set_dashed(data, 2, 2, "R")

    message = read_error(data)

    assert "(2, 2)" in message
    assert "(2, 3)" in message
    assert message.index("(2, 2)") < message.index("(2, 3)")


def test_ac14_a_break_edge_with_no_dashed_edge_is_refused_naming_it() -> None:
    data = vide_data()
    add_naval_hyphen(data)
    set_dashed(data, 2, 2, "R")

    message = read_error(data)

    assert "(1, 1)" in message
    assert "(2, 1)" in message
    assert message.index("(1, 1)") < message.index("(2, 1)")


def test_ac14_every_break_edge_dashed_loads() -> None:
    data = vide_data()
    add_naval_hyphen(data)
    set_dashed(data, 2, 2, "R")
    set_dashed(data, 1, 1, "B")

    grid_file = read_data(data)

    assert cell_with_clues(grid_file.grid, 2, 0).clues[0].breaks == (2,)
    assert cell_with_clues(grid_file.grid, 0, 0).clues[1].breaks == (2,)


@pytest.mark.parametrize(
    ("column", "row", "letters", "named"),
    [
        pytest.param(0, 1, "T", ["(0, 0)", "(1, 0)"], id="beside-a-clue-cell"),
        pytest.param(0, 1, "L", ["(1, 0)"], id="outside-on-the-left"),
        pytest.param(4, 1, "R", ["(1, 4)"], id="outside-on-the-right"),
        pytest.param(1, 4, "B", ["(4, 1)"], id="outside-at-the-bottom"),
    ],
)
def test_ac14_a_dashed_edge_outside_the_grid_or_beside_a_block_is_refused(
    column: int, row: int, letters: str, named: list[str]
) -> None:
    data = fx01_ipuz_data()
    set_dashed(data, column, row, letters)

    message = read_error(data)

    for cell_name in named:
        assert cell_name in message
