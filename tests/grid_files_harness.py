"""Shared setup of the tests of the domain grid-files (`specs/content/grid-files.md`).

Pytest does not collect this module (its name does not start with `test_`). It
holds what the tests of the domain and the numbered tests that edit its pointers
share: FX-01 as an ipuz file (`tests/fixtures/fx01.ipuz`) as plain data a test
changes, small one-line grids, and the writers of an index and of grid files.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from nock.grid import ClueCell, Grid
from nock.ipuz import GridFile, IpuzError, read_ipuz
from spec004_harness import credits

# Raw JSON can hold anything, so its values are typed Any.
JsonData = dict[str, Any]

FIXTURES_DIR = Path(__file__).parent / "fixtures"
FX01_IPUZ_PATH = FIXTURES_DIR / "fx01.ipuz"
INDEX_NAME = "catalogue.json"


def fx01_ipuz_data() -> JsonData:
    """Return a fresh copy of FX-01 as ipuz data, which a test may change."""
    return json.loads(FX01_IPUZ_PATH.read_text(encoding="utf-8"))


def dump(data: JsonData) -> str:
    """Return the JSON text of ipuz data."""
    return json.dumps(data, ensure_ascii=False)


def fx01_model_grid(fx01_text: str) -> Grid:
    """Return FX-01 in the model's JSON as a grid (the `fx01_text` fixture)."""
    return Grid.model_validate_json(fx01_text)


def read_data(data: JsonData) -> GridFile:
    """Read ipuz data that must be accepted."""
    return read_ipuz(dump(data))


def read_error(data: JsonData) -> str:
    """Read ipuz data that must be refused and return the error's message."""
    with pytest.raises(IpuzError) as error_info:
        read_ipuz(dump(data))
    return str(error_info.value)


def clue_named(data: JsonData, text: str) -> JsonData:
    """Return the clue of ipuz data whose text is `text`, to change in place."""
    for clue in data["clues"]["Clues"]:
        if clue["clue"] == text:
            return clue
    raise ValueError(f"no clue {text!r} in the data")


def cell_with_clues(grid: Grid, row: int, column: int) -> ClueCell:
    """Return the clue cell at (row, column), failing when it is another cell."""
    cell = grid.cell_at(row, column)
    assert isinstance(cell, ClueCell), cell
    return cell


def dashed_cell(letters: str) -> JsonData:
    """Return a letter cell of a puzzle drawn with dashed edges."""
    return {"cell": 0, "style": {"dashed": letters}}


def mini_data(
    answer: str,
    letters: str,
    enumeration: str | None = None,
    vertical: bool = False,
) -> JsonData:
    """Return a one-line grid as ipuz data: a clue cell then one word.

    Args:
        answer: The clue's answer as written.
        letters: The letters of the answer, for `solution`.
        enumeration: The clue's `enumeration`, or None to leave the key out.
        vertical: True for a column (the word runs down), else a row.

    Returns:
        The data, which is accepted when `answer` fits `letters`.
    """
    length = len(letters)
    base = fx01_ipuz_data()
    if vertical:
        cells = [[0, step] for step in range(1, length + 1)]
        puzzle: list[list[Any]] = [["#"]]
        solution: list[list[Any]] = [["#"]]
        for letter in letters:
            puzzle.append([0])
            solution.append([letter])
        dimensions = {"width": 1, "height": length + 1}
    else:
        cells = [[step, 0] for step in range(1, length + 1)]
        puzzle = [["#"] + [0] * length]
        solution = [["#"]]
        for letter in letters:
            solution[0].append(letter)
        dimensions = {"width": length + 1, "height": 1}
    clue: JsonData = {
        "clue": "Indice",
        "location": [0, 0],
        "cells": cells,
        "answer": answer,
    }
    if enumeration is not None:
        clue["enumeration"] = enumeration
    base["dimensions"] = dimensions
    base["puzzle"] = puzzle
    base["solution"] = solution
    base["clues"] = {"Clues": [clue]}
    return base


def index_entry(
    number: int = 1, file: str = "g1.ipuz", /, **overrides: object
) -> JsonData:
    """Return a valid entry of the index (the credits of tests/fixtures/credits.json).

    Args:
        number: The grid number.
        file: The name of the grid file.
        overrides: Keys to set or replace in the entry.

    Returns:
        The entry: published, with a source and a licence.
    """
    credit_fields = credits()
    entry: JsonData = {
        "number": number,
        "file": file,
        "published": True,
        "source": credit_fields["source"],
        "licence": credit_fields["licence"],
    }
    entry.update(overrides)
    return entry


def write_index(directory: Path, entries: object) -> Path:
    """Write `grids/catalogue.json` of `directory` with `entries` as its JSON."""
    path = directory / INDEX_NAME
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")
    return path


def write_grid_file(directory: Path, name: str, data: JsonData | None = None) -> Path:
    """Write a grid file: `data` (default FX-01) as the JSON text of `name`."""
    content = fx01_ipuz_data() if data is None else data
    path = directory / name
    path.write_text(dump(content), encoding="utf-8")
    return path


def write_one_grid(
    directory: Path, data: JsonData | None = None, /, **index_overrides: object
) -> None:
    """Write the index and the file `g1.ipuz` of grid number 1.

    Args:
        directory: The directory to fill.
        data: The ipuz data of the file, FX-01 by default.
        index_overrides: Keys to set in the index entry.
    """
    write_grid_file(directory, "g1.ipuz", data)
    write_index(directory, [index_entry(**index_overrides)])
