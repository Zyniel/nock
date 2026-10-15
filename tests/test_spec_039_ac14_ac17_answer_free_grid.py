"""Tests of spec 039, AC-14 to AC-17: the grid in the snapshot has no answers.

AC-14 and AC-15: the schema and the parser refuse an answer. AC-16 and
AC-17: `grid_view` keeps the structure of the grid and leaks no answer. The
shared setup is in `spec039_harness`.
"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from nock.grid import Arrow, Grid
from nock.protocol import (
    ClueCellView,
    ClueView,
    EmptyCellView,
    GridView,
    LetterCellView,
    Snapshot,
    grid_view,
    parse_server_message,
)
from spec039_harness import build_fx01_grid, server_data

# ---- AC-14 --------------------------------------------------------------


def collect_property_names(node: object, names: set[str]) -> int:
    """Add every property name found under a schema node (any: raw JSON).

    Returns:
        The number of `properties` mappings that were walked.
    """
    walked = 0
    if isinstance(node, dict):
        properties = node.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
            walked += 1
        for value in node.values():
            walked += collect_property_names(value, names)
    elif isinstance(node, list):
        for item in node:
            walked += collect_property_names(item, names)
    return walked


def test_ac14_snapshot_schema_has_no_answer_property() -> None:
    schema = Snapshot.model_json_schema()
    names: set[str] = set()

    walked = collect_property_names(schema, names)

    assert walked > 5
    assert "grid" in names
    assert "clues" in names
    assert "answer" not in names
    assert "solution" not in names


def test_ac14_clue_view_is_part_of_the_schema() -> None:
    schema = Snapshot.model_json_schema()

    clue_view = schema["$defs"]["ClueView"]

    assert set(clue_view["properties"]) == {"text", "arrow"}


# ---- AC-15 --------------------------------------------------------------

CLUE_WITH_ANSWER = (
    '{"type": "clue", "row": 0, "column": 0, "clues": '
    '[{"text": "Note", "arrow": "right", "answer": "A"}]}'
)
CLUE_WITHOUT_ANSWER = (
    '{"type": "clue", "row": 0, "column": 0, "clues": '
    '[{"text": "Note", "arrow": "right"}]}'
)


def snapshot_with_clue_cell(clue_cell_text: str) -> str:
    """Return the snapshot example whose first grid cell is the given cell."""
    data = server_data("snapshot")
    data["grid"]["cells"][0] = json.loads(clue_cell_text)
    return json.dumps(data)


def test_ac15_snapshot_with_a_clue_answer_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_server_message(snapshot_with_clue_cell(CLUE_WITH_ANSWER))


def test_ac15_same_snapshot_without_the_answer_parses() -> None:
    message = parse_server_message(snapshot_with_clue_cell(CLUE_WITHOUT_ANSWER))

    assert isinstance(message, Snapshot)
    clue_cell = message.grid.cells[0]
    assert isinstance(clue_cell, ClueCellView)
    assert clue_cell.clues[0].text == "Note"


def test_ac15_clue_view_rejects_an_answer() -> None:
    with pytest.raises(ValidationError):
        ClueView.model_validate({"text": "Note", "arrow": "right", "answer": "A"})


def test_ac15_clue_view_without_answer_validates() -> None:
    clue = ClueView.model_validate({"text": "Note", "arrow": "right"})

    assert clue == ClueView(text="Note", arrow=Arrow.RIGHT)


def test_ac15_clue_view_has_no_answer_field() -> None:
    assert "answer" not in ClueView.model_fields


# ---- AC-16 --------------------------------------------------------------


def test_ac16_view_has_the_size_and_cell_order_of_the_grid(fx01_text: str) -> None:
    grid = build_fx01_grid(fx01_text)

    view = grid_view(grid)

    assert view.width == 5
    assert view.height == 5
    assert len(view.cells) == 25
    for grid_cell, view_cell in zip(grid.cells, view.cells, strict=True):
        assert view_cell.type == grid_cell.type
        assert view_cell.row == grid_cell.row
        assert view_cell.column == grid_cell.column


def test_ac16_clue_cell_keeps_its_clues_in_order(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    first_cell = view.cells[0]

    assert first_cell.type == "clue"
    assert (first_cell.row, first_cell.column) == (0, 0)
    assert first_cell.clues == (
        ClueView(text="Passoire fine", arrow=Arrow.DOWN_THEN_RIGHT),
        ClueView(text="De la marine", arrow=Arrow.RIGHT_THEN_DOWN),
    )


def test_ac16_single_clue_cell_keeps_its_clue(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    cell = view.cells[2]

    assert isinstance(cell, ClueCellView)
    assert cell.clues == (ClueView(text="Artiste muet", arrow=Arrow.DOWN),)


def test_ac16_letter_cells_are_empty_and_untouched(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))
    letter_cells = [cell for cell in view.cells if cell.type == "letter"]

    assert len(letter_cells) == 18
    for cell in letter_cells:
        assert isinstance(cell, LetterCellView)
        assert cell.letter is None
        assert cell.pencil is False
        assert cell.author is None
        assert cell.locked is False
        assert cell.revealed is False
        assert cell.wrong is False


def test_ac16_cell_kinds_match_the_grid(fx01_text: str) -> None:
    grid = build_fx01_grid(fx01_text)
    view = grid_view(grid)
    grid_kinds = [cell.type for cell in grid.cells]
    view_kinds = [cell.type for cell in view.cells]

    assert view_kinds == grid_kinds
    assert all(
        isinstance(cell, EmptyCellView) for cell in view.cells if cell.type == "empty"
    )


def test_ac16_view_is_a_grid_view_that_round_trips(fx01_text: str) -> None:
    view = grid_view(build_fx01_grid(fx01_text))

    again = GridView.model_validate_json(view.model_dump_json())

    assert isinstance(view, GridView)
    assert again == view


def test_ac16_empty_cells_are_kept_in_place() -> None:
    grid = Grid.model_validate(
        {
            "width": 3,
            "height": 2,
            "cells": [
                {
                    "type": "clue",
                    "row": 0,
                    "column": 0,
                    "clues": [{"text": "Note", "arrow": "right", "answer": "AB"}],
                },
                {"type": "letter", "row": 0, "column": 1},
                {"type": "empty", "row": 0, "column": 2},
                {"type": "empty", "row": 1, "column": 0},
                {"type": "letter", "row": 1, "column": 1},
                {"type": "empty", "row": 1, "column": 2},
            ],
        }
    )

    view = grid_view(grid)

    assert view.width == 3
    assert view.height == 2
    assert [cell.type for cell in view.cells] == [
        "clue",
        "letter",
        "empty",
        "empty",
        "letter",
        "empty",
    ]
    assert view.cells[2] == EmptyCellView(row=0, column=2)
    assert view.cells[3] == EmptyCellView(row=1, column=0)
    assert view.cells[5] == EmptyCellView(row=1, column=2)
    assert GridView.model_validate_json(view.model_dump_json()) == view


# ---- AC-17 --------------------------------------------------------------

ANSWERS = ["TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST"]


@pytest.mark.parametrize("answer", ANSWERS)
def test_ac17_view_json_does_not_contain_an_answer(fx01_text: str, answer: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert answer not in text


def test_ac17_view_json_has_no_answer_key(fx01_text: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert '"answer"' not in text


def test_ac17_view_json_still_holds_the_clue_texts(fx01_text: str) -> None:
    text = grid_view(build_fx01_grid(fx01_text)).model_dump_json()

    assert "Passoire fine" in text
    assert "De la marine" in text
