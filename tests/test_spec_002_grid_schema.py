"""Tests of spec 002: the grid schema."""

from __future__ import annotations

import json
from typing import Any

import pytest
from pydantic import ValidationError

from grids_harness import FX01_HYPHENS, with_answers
from nock.grid import (
    Arrow,
    Clue,
    ClueCell,
    EmptyCell,
    Grid,
    LetterCell,
    normalize_answer,
)
from nock.grid_import import import_grid
from nock.protocol import CheckResult, WordTarget
from spec023_harness import check, refs, two_player_room, write_letter

# Raw JSON can hold anything, so these values are typed Any.
JsonData = dict[str, Any]


def load_fx01_data(fx01_text: str) -> JsonData:
    """Parse the FX-01 JSON text into a dictionary (any: raw JSON)."""
    return json.loads(fx01_text)


def build_grid(data: JsonData) -> Grid:
    """Validate a grid given as a dictionary, through JSON."""
    return Grid.model_validate_json(json.dumps(data))


def clue_cell(row: int, column: int, arrow: str) -> JsonData:
    """Return a clue cell with one clue of the given arrow."""
    clue = {"text": "Indice", "arrow": arrow, "answer": "AB"}
    return {"type": "clue", "row": row, "column": column, "clues": [clue]}


def letter_cell(row: int, column: int) -> JsonData:
    """Return a letter cell."""
    return {"type": "letter", "row": row, "column": column}


def empty_cell(row: int, column: int) -> JsonData:
    """Return an empty cell."""
    return {"type": "empty", "row": row, "column": column}


def without_cell(data: JsonData, row: int, column: int) -> JsonData:
    """Return the grid data without the cell at (row, column)."""
    kept = []
    for cell in data["cells"]:
        if (cell["row"], cell["column"]) != (row, column):
            kept.append(cell)
    return {**data, "cells": kept}


@pytest.fixture
def fx01(fx01_text: str) -> Grid:
    """Return FX-01 loaded as a Grid."""
    return Grid.model_validate_json(fx01_text)


# AC-1: width, height and one type per cell


def test_ac1_fx01_has_width_and_height_five(fx01: Grid) -> None:
    assert fx01.width == 5
    assert fx01.height == 5


def test_ac1_fx01_cell_at_letter_and_clue(fx01: Grid) -> None:
    assert isinstance(fx01.cell_at(0, 1), LetterCell)
    assert isinstance(fx01.cell_at(0, 0), ClueCell)


def test_ac1_fx01_has_seven_clue_cells_and_eighteen_letter_cells(
    fx01: Grid,
) -> None:
    assert len(fx01.cells) == 25
    clue_cells = [cell for cell in fx01.cells if isinstance(cell, ClueCell)]
    letter_cells = [cell for cell in fx01.cells if isinstance(cell, LetterCell)]
    assert len(clue_cells) == 7
    assert len(letter_cells) == 18


def test_ac1_empty_cell_is_loaded_as_empty_cell() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [empty_cell(0, 0), letter_cell(0, 1)],
    }
    grid = build_grid(data)
    assert isinstance(grid.cell_at(0, 0), EmptyCell)
    assert isinstance(grid.cell_at(0, 1), LetterCell)


def test_ac1_unknown_cell_type_is_rejected() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [{"type": "black", "row": 0, "column": 0}, letter_cell(0, 1)],
    }
    with pytest.raises(ValidationError):
        build_grid(data)


def test_ac1_cell_without_type_is_rejected() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [{"row": 0, "column": 0}, letter_cell(0, 1)],
    }
    with pytest.raises(ValidationError):
        build_grid(data)


@pytest.mark.parametrize("field", ["width", "height"])
@pytest.mark.parametrize("value", [0, -1])
def test_ac1_non_positive_size_is_rejected(
    fx01_text: str, field: str, value: int
) -> None:
    data = load_fx01_data(fx01_text)
    data[field] = value
    with pytest.raises(ValidationError):
        build_grid(data)


@pytest.mark.parametrize("field", ["row", "column"])
def test_ac1_negative_cell_coordinate_is_rejected(field: str) -> None:
    bad_cell = letter_cell(0, 0)
    bad_cell[field] = -1
    data = {"width": 1, "height": 1, "cells": [bad_cell]}
    with pytest.raises(ValidationError):
        build_grid(data)


def test_ac1_cell_at_outside_the_grid_raises_index_error(fx01: Grid) -> None:
    with pytest.raises(IndexError):
        fx01.cell_at(5, 0)
    with pytest.raises(IndexError):
        fx01.cell_at(0, 5)


def test_ac1_cells_may_be_listed_in_any_order(fx01_text: str, fx01: Grid) -> None:
    data = load_fx01_data(fx01_text)
    data["cells"].reverse()
    reversed_grid = build_grid(data)
    for row in range(5):
        for column in range(5):
            assert reversed_grid.cell_at(row, column) == fx01.cell_at(row, column)


# AC-2: clues and word resolution


def test_ac2_fx01_clue_cell_with_two_clues(fx01: Grid) -> None:
    cell = fx01.cell_at(0, 0)
    assert isinstance(cell, ClueCell)
    assert cell.clues == (
        Clue(text="Passoire fine", arrow=Arrow.DOWN_THEN_RIGHT, answer="TAMIS"),
        Clue(text="De la marine", arrow=Arrow.RIGHT_THEN_DOWN, answer="NAVAL"),
    )


def test_ac2_fx01_clue_cell_with_one_clue(fx01: Grid) -> None:
    cell = fx01.cell_at(0, 2)
    assert isinstance(cell, ClueCell)
    assert cell.clues == (Clue(text="Artiste muet", arrow=Arrow.DOWN, answer="MIME"),)


def test_ac2_word_cells_down_then_right(fx01: Grid) -> None:
    expected = [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]
    assert fx01.word_cells(0, 0, 0) == expected


def test_ac2_word_cells_right_then_down(fx01: Grid) -> None:
    expected = [(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)]
    assert fx01.word_cells(0, 0, 1) == expected


def test_ac2_word_cells_down(fx01: Grid) -> None:
    expected = [(1, 2), (2, 2), (3, 2), (4, 2)]
    assert fx01.word_cells(0, 2, 0) == expected


def test_ac2_word_cells_right(fx01: Grid) -> None:
    expected = [(2, 1), (2, 2), (2, 3), (2, 4)]
    assert fx01.word_cells(2, 0, 0) == expected


@pytest.mark.parametrize(
    ("row", "column", "start", "step"),
    [
        (0, 3, (1, 3), (1, 0)),
        (0, 4, (1, 4), (1, 0)),
        (3, 0, (3, 1), (0, 1)),
        (4, 0, (4, 1), (0, 1)),
    ],
)
def test_ac2_word_cells_of_the_other_fx01_words(
    fx01: Grid,
    row: int,
    column: int,
    start: tuple[int, int],
    step: tuple[int, int],
) -> None:
    expected = []
    for offset in range(4):
        expected.append((start[0] + step[0] * offset, start[1] + step[1] * offset))
    assert fx01.word_cells(row, column, 0) == expected


def test_ac2_word_stops_before_an_empty_cell() -> None:
    data = {
        "width": 4,
        "height": 1,
        "cells": [
            clue_cell(0, 0, "right"),
            letter_cell(0, 1),
            letter_cell(0, 2),
            empty_cell(0, 3),
        ],
    }
    assert build_grid(data).word_cells(0, 0, 0) == [(0, 1), (0, 2)]


def test_ac2_word_stops_before_a_clue_cell_across() -> None:
    data = {
        "width": 4,
        "height": 1,
        "cells": [
            clue_cell(0, 0, "right"),
            letter_cell(0, 1),
            letter_cell(0, 2),
            clue_cell(0, 3, "right"),
        ],
    }
    assert build_grid(data).word_cells(0, 0, 0) == [(0, 1), (0, 2)]


def test_ac2_word_stops_before_a_clue_cell_down() -> None:
    data = {
        "width": 1,
        "height": 4,
        "cells": [
            clue_cell(0, 0, "down"),
            letter_cell(1, 0),
            letter_cell(2, 0),
            clue_cell(3, 0, "down"),
        ],
    }
    assert build_grid(data).word_cells(0, 0, 0) == [(1, 0), (2, 0)]


def test_ac2_one_letter_word_is_allowed() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [clue_cell(0, 0, "right"), letter_cell(0, 1)],
    }
    assert build_grid(data).word_cells(0, 0, 0) == [(0, 1)]


def test_ac2_word_cells_on_a_letter_cell_raises_value_error(fx01: Grid) -> None:
    with pytest.raises(ValueError, match=r".+"):
        fx01.word_cells(1, 0, 0)


def test_ac2_word_cells_clue_index_out_of_range_raises_index_error(
    fx01: Grid,
) -> None:
    with pytest.raises(IndexError):
        fx01.word_cells(0, 2, 1)


def test_ac2_word_cells_position_outside_the_grid_raises_index_error(
    fx01: Grid,
) -> None:
    with pytest.raises(IndexError):
        fx01.word_cells(5, 0, 0)


def test_ac2_start_cell_outside_the_grid_names_the_start_cell() -> None:
    data = {
        "width": 5,
        "height": 1,
        "cells": [
            letter_cell(0, 0),
            letter_cell(0, 1),
            letter_cell(0, 2),
            letter_cell(0, 3),
            clue_cell(0, 4, "right"),
        ],
    }
    with pytest.raises(ValueError, match=r"\(0, 5\)"):
        build_grid(data).word_cells(0, 4, 0)


def test_ac2_start_cell_below_the_grid_names_the_start_cell() -> None:
    data = {
        "width": 1,
        "height": 2,
        "cells": [letter_cell(0, 0), clue_cell(1, 0, "down")],
    }
    with pytest.raises(ValueError, match=r"\(2, 0\)"):
        build_grid(data).word_cells(1, 0, 0)


def test_ac2_start_cell_that_is_a_clue_cell_names_the_start_cell() -> None:
    data = {
        "width": 2,
        "height": 4,
        "cells": [
            letter_cell(0, 0),
            letter_cell(0, 1),
            letter_cell(1, 0),
            letter_cell(1, 1),
            clue_cell(2, 0, "down"),
            letter_cell(2, 1),
            clue_cell(3, 0, "right"),
            letter_cell(3, 1),
        ],
    }
    with pytest.raises(ValueError, match=r"\(3, 0\)"):
        build_grid(data).word_cells(2, 0, 0)


def test_ac2_start_cell_that_is_empty_raises_value_error() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [clue_cell(0, 0, "right"), empty_cell(0, 1)],
    }
    with pytest.raises(ValueError, match=r"\(0, 1\)"):
        build_grid(data).word_cells(0, 0, 0)


def test_ac2_clue_cell_without_clues_is_rejected() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [
            {"type": "clue", "row": 0, "column": 0, "clues": []},
            letter_cell(0, 1),
        ],
    }
    with pytest.raises(ValidationError):
        build_grid(data)


def test_ac2_clue_cell_with_three_clues_is_rejected() -> None:
    clue = {"text": "Indice", "arrow": "right", "answer": "AB"}
    data = {
        "width": 2,
        "height": 1,
        "cells": [
            {"type": "clue", "row": 0, "column": 0, "clues": [clue, clue, clue]},
            letter_cell(0, 1),
        ],
    }
    with pytest.raises(ValidationError):
        build_grid(data)


def test_ac2_clue_with_empty_text_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Clue(text="", arrow="right", answer="AB")


def test_ac2_clue_with_unknown_arrow_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Clue(text="Indice", arrow="left", answer="AB")


def test_ac2_arrow_values() -> None:
    assert Arrow.RIGHT == "right"
    assert Arrow.DOWN == "down"
    assert Arrow.DOWN_THEN_RIGHT == "down_then_right"
    assert Arrow.RIGHT_THEN_DOWN == "right_then_down"


# AC-3: an answer as written, its letters and its breaks


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ÊTRE", "ETRE"),
        ("ARC-EN-CIEL", "ARCENCIEL"),
        ("AUJOURD'HUI", "AUJOURDHUI"),
        ("aujourd" + chr(0x2019) + "hui", "AUJOURDHUI"),
        ("CŒUR", "COEUR"),
        ("cœur", "COEUR"),
        ("Æther", "AETHER"),
        ("æther", "AETHER"),
        ("tamis", "TAMIS"),
        ("Fatales à César", "FATALESACESAR"),
        ("Ça", "CA"),
        ("Noël", "NOEL"),
    ],
)
def test_ac3_normalize_answer(text: str, expected: str) -> None:
    assert normalize_answer(text) == expected


@pytest.mark.parametrize("text", ["'", "", "   ", "- -"])
def test_ac3_normalize_answer_empty_result_raises_value_error(text: str) -> None:
    with pytest.raises(ValueError, match=r".+"):
        normalize_answer(text)


def test_ac3_normalize_answer_digit_raises_value_error_naming_the_text() -> None:
    with pytest.raises(ValueError, match="'R2D2'"):
        normalize_answer("R2D2")


def test_ac3_normalize_answer_error_shows_the_original_text_with_ligature() -> None:
    with pytest.raises(ValueError, match="'CŒUR2'"):
        normalize_answer("CŒUR2")


def test_ac3_clue_answer_keeps_its_text() -> None:
    # The answer keeps its text; its letters are the normalised form.
    clue = Clue(text="Etre", arrow="down", answer="être")
    assert clue.answer == "être"
    assert clue.letters == "ETRE"


@pytest.mark.parametrize(
    ("answer", "letters", "breaks"),
    [
        ("ÊTRE", "ETRE", ()),
        ("ARC-EN-CIEL", "ARCENCIEL", (3, 5)),
        ("AUJOURD'HUI", "AUJOURDHUI", (7,)),
        ("aujourd" + chr(0x2019) + "hui", "AUJOURDHUI", (7,)),
        ("A.I", "AI", (1,)),
        ("A I", "AI", (1,)),
        ("A-I", "AI", (1,)),
        ("ARC-EN CIEL", "ARCENCIEL", (3, 5)),
        ("CŒUR", "COEUR", ()),
        ("Fatales à César", "FATALESACESAR", (7, 8)),
        ("VI-DE", "VIDE", (2,)),
        ("ARCENCIEL", "ARCENCIEL", ()),
    ],
)
def test_ac3_clue_keeps_its_answer_and_derives_letters_and_breaks(
    answer: str, letters: str, breaks: tuple[int, ...]
) -> None:
    clue = Clue(text="Indice", arrow="right", answer=answer)
    assert clue.answer == answer
    assert clue.letters == letters
    assert clue.breaks == breaks


@pytest.mark.parametrize("name", ["letters", "breaks"])
def test_ac3_letters_and_breaks_are_read_only(name: str) -> None:
    clue = Clue(text="Indice", arrow="right", answer="ARC-EN-CIEL")
    with pytest.raises((AttributeError, ValidationError)):
        setattr(clue, name, "ARC")
    assert clue.letters == "ARCENCIEL"
    assert clue.breaks == (3, 5)


def test_ac3_clue_with_empty_answer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Clue(text="Indice", arrow="down", answer="")


def test_ac3_clue_with_digit_in_answer_is_rejected() -> None:
    with pytest.raises(ValidationError, match="R2D2"):
        Clue(text="Indice", arrow="down", answer="R2D2")


def test_ac3_a_loaded_grid_keeps_its_answer_text() -> None:
    # Loaded, the answer stays as written; letters and breaks are derived.
    clue = {"text": "Indice", "arrow": "right", "answer": "arc-en-ciel"}
    cell = {"type": "clue", "row": 0, "column": 0, "clues": [clue]}
    grid = build_grid({"width": 2, "height": 1, "cells": [cell, letter_cell(0, 1)]})
    loaded = grid.cell_at(0, 0)
    assert isinstance(loaded, ClueCell)
    assert loaded.clues[0].answer == "arc-en-ciel"
    assert loaded.clues[0].letters == "ARCENCIEL"
    assert loaded.clues[0].breaks == (3, 5)


def test_ac3_a_saved_grid_holds_the_answer_as_written_and_nothing_derived() -> None:
    clue = {"text": "Indice", "arrow": "right", "answer": "ARC-EN-CIEL"}
    cell = {"type": "clue", "row": 0, "column": 0, "clues": [clue]}
    grid = build_grid({"width": 2, "height": 1, "cells": [cell, letter_cell(0, 1)]})

    saved = json.loads(grid.model_dump_json())

    assert saved["cells"][0]["clues"] == [clue]
    assert Grid.model_validate_json(grid.model_dump_json()) == grid


def test_ac3_a_hyphenated_answer_fits_as_many_cells_as_it_has_letters(
    fx01_text: str,
) -> None:
    report = import_grid(with_answers(fx01_text, FX01_HYPHENS))

    assert report.word_count == 8
    assert report.letter_cell_count == 18
    vide = report.grid.cell_at(2, 0)
    naval = report.grid.cell_at(0, 0)
    assert isinstance(vide, ClueCell)
    assert isinstance(naval, ClueCell)
    assert (vide.clues[0].answer, vide.clues[0].breaks) == ("VI-DE", (2,))
    assert (naval.clues[1].answer, naval.clues[1].breaks) == ("NA-VAL", (2,))


def test_ac3_a_room_checks_a_hyphenated_word_against_its_letters(
    fx01_text: str,
) -> None:
    grid = Grid.model_validate_json(with_answers(fx01_text, FX01_HYPHENS))
    state = two_player_room(grid)
    for column, letter in zip((1, 2, 3, 4), "VIDE", strict=True):
        state = write_letter(state, "p1", 2, column, letter)
    target = WordTarget(row=2, column=0, clue_index=0)

    events = check(state, target)

    result = events[0]
    assert isinstance(result, CheckResult)
    assert result.correct == refs((2, 1), (2, 2), (2, 3), (2, 4))
    assert result.wrong == ()


def test_ac3_fx01_answers_are_the_reference_answers(fx01: Grid) -> None:
    expected = {
        (0, 0): ("TAMIS", "NAVAL"),
        (0, 2): ("MIME",),
        (0, 3): ("IDES",),
        (0, 4): ("SENT",),
        (2, 0): ("VIDE",),
        (3, 0): ("AMEN",),
        (4, 0): ("LEST",),
    }
    for (row, column), answers in expected.items():
        cell = fx01.cell_at(row, column)
        assert isinstance(cell, ClueCell)
        assert tuple(clue.answer for clue in cell.clues) == answers


# AC-4: round trip


def test_ac4_fx01_survives_load_save_load(fx01_text: str) -> None:
    first = Grid.model_validate_json(fx01_text)
    second = Grid.model_validate_json(first.model_dump_json())
    assert second == first
    assert second.model_dump_json() == first.model_dump_json()


def test_ac4_round_trip_keeps_an_empty_cell() -> None:
    data = {
        "width": 2,
        "height": 1,
        "cells": [empty_cell(0, 0), letter_cell(0, 1)],
    }
    first = build_grid(data)
    second = Grid.model_validate_json(first.model_dump_json())
    assert second == first
    assert isinstance(second.cell_at(0, 0), EmptyCell)


# AC-5: one cell per position


def test_ac5_missing_cell_names_the_position(fx01_text: str) -> None:
    data = without_cell(load_fx01_data(fx01_text), 2, 3)
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(2, 3)" in message
    assert "missing" in message


def test_ac5_first_missing_position_in_row_major_order_is_named(
    fx01_text: str,
) -> None:
    data = without_cell(load_fx01_data(fx01_text), 3, 1)
    data = without_cell(data, 1, 4)
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(1, 4)" in message
    assert "missing" in message


def test_ac5_cell_outside_the_grid(fx01_text: str) -> None:
    data = load_fx01_data(fx01_text)
    data["cells"].append(letter_cell(5, 0))
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(5, 0)" in message
    assert "outside" in message


def test_ac5_cell_outside_the_grid_by_column(fx01_text: str) -> None:
    data = load_fx01_data(fx01_text)
    data["cells"].append(letter_cell(0, 5))
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(0, 5)" in message
    assert "outside" in message


def test_ac5_duplicate_position_with_a_missing_one(fx01_text: str) -> None:
    data = load_fx01_data(fx01_text)
    cells = []
    for cell in data["cells"]:
        if (cell["row"], cell["column"]) == (1, 2):
            cells.append(letter_cell(1, 1))
        else:
            cells.append(cell)
    data["cells"] = cells
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(1, 1)" in message
    assert "duplicate" in message


def test_ac5_extra_cell_at_an_existing_position(fx01_text: str) -> None:
    data = load_fx01_data(fx01_text)
    data["cells"].append(letter_cell(1, 1))
    assert len(data["cells"]) == 26
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(1, 1)" in message
    assert "duplicate" in message


def test_ac5_outside_is_reported_before_duplicate(fx01_text: str) -> None:
    data = load_fx01_data(fx01_text)
    data["cells"].append(letter_cell(1, 1))
    data["cells"].append(letter_cell(5, 0))
    with pytest.raises(ValidationError) as error:
        build_grid(data)
    message = str(error.value)
    assert "(5, 0)" in message
    assert "outside" in message
