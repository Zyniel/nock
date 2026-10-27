"""Tests of grids AC-20 and AC-21: separators and breaks.

AC-20: a separator must sit between two letters of its answer. AC-21: two words
that share an edge agree on its break, whatever the separator of each, a check
that comes after the crossing check. The answers are read through `Clue` and
`import_grid`.

Choices where the spec leaves room:

- AC-20, rule 4: `ARC -EN`, `ARC-'EN` and `ARC` + right single quote + `-EN` hold
  two separators in a row and are refused like the criterion's nine samples.
- AC-21: the shared edge is tested both ways, a break in the longer word only and
  in the shorter word only; its two cells are named in reading order.
"""

from __future__ import annotations

import json
import re

import pytest
from pydantic import ValidationError

from grids_harness import JsonData, with_answers
from nock.grid import Clue, ClueCell, Grid
from nock.grid_import import GridImportError, import_grid

RIGHT_SINGLE_QUOTE = chr(0x2019)


def names(message: str, answer: str) -> bool:
    """Tell whether a message names an answer as a whole, not inside another."""
    before = r"(?<![A-Za-z\-'])(?<![A-Za-z]\.)"
    after = r"(?![A-Za-z\-'])(?!\.[A-Za-z])"
    pattern = before + re.escape(answer) + after
    return re.search(pattern, message) is not None


def clue_cell(row: int, column: int, *clues: tuple[str, str, str]) -> JsonData:
    """A clue cell holding (text, arrow, answer) clues."""
    clue_list = []
    for text, arrow, answer in clues:
        clue_list.append({"text": text, "arrow": arrow, "answer": answer})
    return {"type": "clue", "row": row, "column": column, "clues": clue_list}


def letter(row: int, column: int) -> JsonData:
    return {"type": "letter", "row": row, "column": column}


def empty(row: int, column: int) -> JsonData:
    return {"type": "empty", "row": row, "column": column}


def import_error(text: str) -> str:
    """Import a grid that must be refused and return the error's message."""
    with pytest.raises(GridImportError) as error:
        import_grid(text)
    return str(error.value)


# ---- AC-20: a separator sits between two letters -------------------------------------

REFUSED_ANSWERS = [
    "-ARC",
    "ARC-",
    "ARC--EN",
    "ARC- EN",
    ".AI",
    "A.I.",
    "A..I",
    "A.-I",
    "A  I",
    "ARC -EN",
    "ARC-'EN",
    "ARC" + RIGHT_SINGLE_QUOTE + "-EN",
]


@pytest.mark.parametrize("answer", REFUSED_ANSWERS)
def test_ac20_a_separator_not_between_two_letters_is_refused_naming_the_answer(
    answer: str,
) -> None:
    with pytest.raises(ValidationError) as error:
        Clue(text="Indice", arrow="right", answer=answer)

    messages = [str(item["msg"]) for item in error.value.errors()]
    assert any(answer in message for message in messages), messages


def run_grid(answer: str, length: int) -> str:
    """A 1-row grid: a clue cell, then a run of `length` letter cells."""
    cells = [clue_cell(0, 0, ("Indice", "right", answer))]
    for column in range(1, length + 1):
        cells.append(letter(0, column))
    return json.dumps({"width": length + 1, "height": 1, "cells": cells})


@pytest.mark.parametrize(
    ("answer", "length"), [("ARC-", 3), ("A.I.", 2), ("A  I", 2)], ids=str
)
def test_ac20_a_grid_with_a_misplaced_separator_is_refused_naming_it(
    answer: str, length: int
) -> None:
    message = import_error(run_grid(answer, length))

    assert names(message, answer), message


def test_ac20_a_hyphen_then_a_space_between_words_loads_with_two_breaks() -> None:
    report = import_grid(run_grid("ARC-EN CIEL", 9))

    cell = report.grid.cell_at(0, 0)
    assert isinstance(cell, ClueCell)
    clue = cell.clues[0]
    assert clue.answer == "ARC-EN CIEL"
    assert clue.letters == "ARCENCIEL"
    assert clue.breaks == (3, 5)


# ---- AC-21: words sharing an edge agree on its break ------------------------------


def shared_edge_grid(long_answer: str, short_answer: str, down_answer: str) -> str:
    """A 4 by 3 grid where a word starts inside a longer run.

    The long word runs across from (1, 0) to (1, 3) (clue (0, 0)), the short one
    across from (1, 1) to (1, 3) (clue (0, 1)), and a down word from (1, 2) to
    (2, 2) (clue (0, 2)) crosses both.
    """
    cells = [
        clue_cell(0, 0, ("Sans contenu", "down_then_right", long_answer)),
        clue_cell(0, 1, ("Pronom", "down_then_right", short_answer)),
        clue_cell(0, 2, ("Note", "down", down_answer)),
        empty(0, 3),
        letter(1, 0),
        letter(1, 1),
        letter(1, 2),
        letter(1, 3),
        empty(2, 0),
        empty(2, 1),
        letter(2, 2),
        empty(2, 3),
    ]
    return json.dumps({"width": 4, "height": 3, "cells": cells})


@pytest.mark.parametrize(
    ("long_answer", "short_answer"),
    [("VI-DE", "IDE"), ("VIDE", "I-DE"), ("VI DE", "IDE"), ("VIDE", "I.DE")],
    ids=[
        "break-in-the-long-word",
        "break-in-the-short-word",
        "space-in-the-long-word",
        "dot-in-the-short-word",
    ],
)
def test_ac21_words_sharing_an_edge_that_disagree_on_its_break_are_refused(
    long_answer: str, short_answer: str
) -> None:
    message = import_error(shared_edge_grid(long_answer, short_answer, "DO"))

    assert names(message, long_answer), message
    assert names(message, short_answer), message
    assert "(1, 1)" in message, message
    assert "(1, 2)" in message, message
    assert message.index("(1, 1)") < message.index("(1, 2)"), message


@pytest.mark.parametrize(
    ("long_answer", "short_answer", "breaks"),
    [
        ("VI-DE", "I-DE", ((2,), (1,))),
        ("VI-DE", "I DE", ((2,), (1,))),
        ("VI.DE", "I'DE", ((2,), (1,))),
        ("VIDE", "IDE", ((), ())),
    ],
)
def test_ac21_words_that_agree_on_the_break_of_their_edge_load(
    long_answer: str, short_answer: str, breaks: tuple[tuple[int, ...], ...]
) -> None:
    report = import_grid(shared_edge_grid(long_answer, short_answer, "DO"))

    found: list[tuple[int, ...]] = []
    for column in (0, 1):
        cell = report.grid.cell_at(0, column)
        assert isinstance(cell, ClueCell)
        found.append(cell.clues[0].breaks)
    assert tuple(found) == breaks
    assert report.word_count == 3


def test_ac21_the_crossing_check_comes_before_the_break_check() -> None:
    # XO disagrees with VI-DE and IDE at (1, 2), and IDE has no hyphen there.
    message = import_error(shared_edge_grid("VI-DE", "IDE", "XO"))

    assert names(message, "XO"), message
    assert "(1, 2)" in message, message


def test_ac21_an_across_and_a_down_break_after_one_cell_are_both_kept(
    fx01_text: str,
) -> None:
    # TA-MIS breaks after (1, 1) across, NA-VAL after (1, 1) down.
    text = with_answers(fx01_text, {"TAMIS": "TA-MIS", "NAVAL": "NA-VAL"})

    report = import_grid(text)

    cell = report.grid.cell_at(0, 0)
    assert isinstance(cell, ClueCell)
    assert [clue.breaks for clue in cell.clues] == [(2,), (2,)]
    assert report.grid == Grid.model_validate_json(text)
