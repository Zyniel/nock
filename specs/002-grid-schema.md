---
id: "002"
title: Grid schema
status: done
---

# 002 - Grid schema

Epic E1 Grid content and model (US-1.1) · Release: MVP · Epic depends on: None
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a builder agent, I need one grid schema, so that every component reads a grid the same way.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Models follow `specs/_architecture.md`. Every name below is importable from
`nock.grid`.

```python
# src/nock/grid.py
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

Position = tuple[int, int]  # (row, column), from zero


class Arrow(StrEnum):
    RIGHT = "right"
    DOWN = "down"
    DOWN_THEN_RIGHT = "down_then_right"
    RIGHT_THEN_DOWN = "right_then_down"


def normalize_answer(text: str) -> str:
    """Uppercase A to Z only: ligatures expanded, accents folded, spaces,
    hyphens and apostrophes removed.

    Raises:
        ValueError: if the result is empty or holds a character outside A to Z.
    """


class Clue(BaseModel):
    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    arrow: Arrow
    answer: Annotated[str, AfterValidator(normalize_answer)]


class LetterCell(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["letter"] = "letter"
    row: int = Field(ge=0)
    column: int = Field(ge=0)


class ClueCell(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["clue"] = "clue"
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    clues: tuple[Clue, ...] = Field(min_length=1, max_length=2)


class EmptyCell(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Literal["empty"] = "empty"
    row: int = Field(ge=0)
    column: int = Field(ge=0)


Cell = Annotated[LetterCell | ClueCell | EmptyCell, Field(discriminator="type")]


class Grid(BaseModel):
    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    cells: tuple[Cell, ...]
    # A model validator (mode="after") enforces exactly one cell per position
    # inside width x height, width * height cells in all (AC-5).

    def cell_at(self, row: int, column: int) -> LetterCell | ClueCell | EmptyCell:
        """Return the cell at (row, column).

        Raises:
            IndexError: if (row, column) is outside the grid.
        """

    def word_cells(self, row: int, column: int, clue_index: int) -> list[Position]:
        """Ordered letter cells of the word that clue `clue_index` of the clue
        cell at (row, column) resolves to.

        Raises:
            IndexError: if (row, column) is outside the grid, or clue_index is
                not a valid index into that cell's clues.
            ValueError: if the cell at (row, column) is not a clue cell, or the
                word's start cell is outside the grid or is not a letter cell.
        """
```

### Solution letters

The solution lives on each clue, in `Clue.answer`. A `LetterCell` holds no letter.

### Normalisation (`normalize_answer`)

Applied in this order:

1. Expand the ligatures: `Œ` to `OE`, `œ` to `oe`, `Æ` to `AE`, `æ` to `ae`.
2. Decompose the text with Unicode NFD and drop every combining mark (Unicode
   category `Mn`), so `É` becomes `E` and `ç` becomes `c`.
3. Remove every space (U+0020), hyphen-minus (U+002D), apostrophe (U+0027 `'`)
   and right single quotation mark (U+2019 `’`).
4. Uppercase.
5. If the result is empty, raise `ValueError`. If it holds any character other
   than `A` to `Z`, raise `ValueError` whose message contains the original text
   in `repr` form.

`Clue.answer` runs it as an `AfterValidator`, so a bad answer makes `Clue(...)`
or `Grid.model_validate_json(...)` raise `pydantic.ValidationError`.

### Clue resolution (`Grid.word_cells`)

For the clue cell at (r, c), the start cell and direction depend on the arrow:

| Arrow | Start cell | Direction |
| --- | --- | --- |
| `right` | (r, c + 1) | across (column + 1 each step) |
| `down` | (r + 1, c) | down (row + 1 each step) |
| `down_then_right` | (r + 1, c) | across |
| `right_then_down` | (r, c + 1) | down |

The word is the start cell followed by every next cell in the direction, and
stops before the first cell that is not a letter cell (clue or empty) or at the
grid edge. The start cell must be a letter cell inside the grid; otherwise
`word_cells` raises `ValueError` whose message contains the start cell
coordinates. The list is never empty.

### One cell per position (AC-5)

A `Grid` model validator (`mode="after"`) raises `ValueError` (which Pydantic
reports as `pydantic.ValidationError`) at the first problem, checked in this
order:

1. A cell outside the grid (`row >= height` or `column >= width`): the message
   contains its coordinates and the word `outside`.
2. A position held by two or more cells: the message contains its coordinates and
   the word `duplicate`.
3. A position inside the grid with no cell (first in row-major order): the message
   contains its coordinates and the word `missing`.

### Coordinates in messages

Wherever an error message must name a position, it is written as
`f"({row}, {column})"`, for example `(0, 5)`, with one space after the comma.

### JSON format

Loading and saving use Pydantic directly: `Grid.model_validate_json(text)` and
`grid.model_dump_json()`. Invalid structure raises `pydantic.ValidationError`,
and `str(error)` contains the messages of the validators below.

A grid is an object with `width`, `height` and `cells` (a list, any order). Each
cell must carry its `type` (`"letter"`, `"clue"` or `"empty"`), `row` and
`column`; a clue cell also carries `clues`. Each clue has `text`, `arrow` (one of
the four arrow values) and `answer`. One clue cell (FX-01 at (0,0)) and one
letter cell:

```json
{"type": "clue", "row": 0, "column": 0, "clues": [
  {"text": "Passoire fine", "arrow": "down_then_right", "answer": "TAMIS"},
  {"text": "De la marine", "arrow": "right_then_down", "answer": "NAVAL"}
]}
{"type": "letter", "row": 0, "column": 1}
```

### FX-01 for tests

The test-writer creates `tests/fixtures/fx01.json` from the tables in
`specs/_reference.md`, in the format above: `width` 5, `height` 5, 25 cells
(7 clue cells, 18 letter cells, no empty cell), with the clue texts and answers
of words W1 to W8. Specs 002 and 003 both read that file.

## Acceptance criteria

- **AC-1** (AC-1.1.1) A grid declares its width, its height and one type per cell: letter, clue or empty. Given FX-01 loaded with `Grid.model_validate_json`, `width` and `height` are 5, `cell_at(0, 1)` is a `LetterCell` and `cell_at(0, 0)` is a `ClueCell`; given a grid of width 2 and height 1 whose cells are `{"type": "empty", "row": 0, "column": 0}` and a letter cell at (0, 1), `cell_at(0, 0)` is an `EmptyCell`. A cell whose `type` is anything else (for example `"black"`) raises `pydantic.ValidationError`.
- **AC-2** (AC-1.1.2) A clue cell holds one or two clues. Each clue has a text, one of the four arrow types, and resolves to an ordered list of letter cells following the resolution table above. On FX-01: `word_cells(0, 0, 0)` (down then right) is `[(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)]`; `word_cells(0, 0, 1)` (right then down) is `[(0, 1), (1, 1), (2, 1), (3, 1), (4, 1)]`; `word_cells(0, 2, 0)` (down) is `[(1, 2), (2, 2), (3, 2), (4, 2)]`; `word_cells(2, 0, 0)` (right) is `[(2, 1), (2, 2), (2, 3), (2, 4)]`.
- **AC-3** (AC-1.1.3) Answers are stored as uppercase A to Z without accents, spaces, hyphens or apostrophes, ligatures expanded: `normalize_answer("ÊTRE")` is `"ETRE"`, `normalize_answer("ARC-EN-CIEL")` is `"ARCENCIEL"`, `normalize_answer("AUJOURD'HUI")` is `"AUJOURDHUI"`, `normalize_answer("CŒUR")` is `"COEUR"`, and `Clue(text="Etre", arrow="down", answer="être").answer` is `"ETRE"`.
- **AC-4** (AC-1.1.4) FX-01 written in the schema survives load, save and load again with no difference: with `first = Grid.model_validate_json(fx01_text)` and `second = Grid.model_validate_json(first.model_dump_json())`, `second == first` and `second.model_dump_json() == first.model_dump_json()`.
- **AC-5** (new) A grid has exactly one cell for each (row, column) inside width x height, width * height cells in all; otherwise `Grid.model_validate_json` raises `pydantic.ValidationError` whose message names the position concerned: given FX-01 without its cell at (2, 3), the message contains `(2, 3)` and `missing`.

## Edge cases and errors

Normalisation (AC-3):

- `normalize_answer("tamis")` is `"TAMIS"` (lowercase accepted).
- `normalize_answer("Fatales à César")` is `"FATALESACESAR"` (accents and spaces).
- `normalize_answer("Ça")` is `"CA"`; `normalize_answer("Noël")` is `"NOEL"`.
- Apostrophes: `normalize_answer("AUJOURD'HUI")` and `normalize_answer("aujourd’hui")`
  (U+2019) are both `"AUJOURDHUI"`.
- Ligatures: `normalize_answer("CŒUR")` and `normalize_answer("cœur")` are
  `"COEUR"`; `normalize_answer("Æther")` and `normalize_answer("æther")` are
  `"AETHER"`.
- `normalize_answer("'")` raises `ValueError` (empty result).
- `normalize_answer("")`, `normalize_answer("   ")` and `normalize_answer("- -")`
  raise `ValueError` (empty result).
- `normalize_answer("R2D2")` raises `ValueError` (digit), and its message contains
  `'R2D2'`.
- A `Clue` with answer `""` raises `pydantic.ValidationError`.

Clues and clue cells (AC-2):

- A clue cell with 0 clues or with 3 clues raises `pydantic.ValidationError`.
- A clue with `text` `""` raises `pydantic.ValidationError`.
- A clue whose `arrow` is `"left"` raises `pydantic.ValidationError`.
- `word_cells(1, 0, 0)` on FX-01 ((1,0) is a letter cell) raises `ValueError`.
- `word_cells(0, 2, 1)` on FX-01 ((0,2) has one clue) raises `IndexError`.
- On a grid where a `right` clue at (0, 4) of a 5-wide grid points to (0, 5),
  `word_cells(0, 4, 0)` raises `ValueError` whose message contains `(0, 5)`.
- On a grid where a `down` clue at (2, 0) sits above a clue cell at (3, 0),
  `word_cells(2, 0, 0)` raises `ValueError` whose message contains `(3, 0)`.
- A one-letter word is allowed here: a `right` clue at (0, 0) of a grid of width 2 and height 1 with
  a letter cell at (0, 1) resolves to `[(0, 1)]`.

Grid shape (AC-1, AC-5):

- `width` or `height` of 0 or below raises `pydantic.ValidationError`.
- A cell with `row` or `column` below 0 raises `pydantic.ValidationError`.
- A cell missing its `type` field raises `pydantic.ValidationError`.
- A cell outside the grid (FX-01 plus a letter cell at (5, 0)) raises
  `pydantic.ValidationError` whose message contains `(5, 0)` and `outside`.
- A duplicate position (FX-01 where a second letter cell at (1, 1) replaces the
  cell at (1, 2), so (1, 1) appears twice and (1, 2) is missing) raises
  `pydantic.ValidationError` whose message contains `(1, 1)` and `duplicate`
  (duplicates are checked before missing positions).
- FX-01 plus a second letter cell at (1, 1) (26 cells) raises
  `pydantic.ValidationError` whose message contains `(1, 1)` and `duplicate`.
- Cells may be listed in any order: FX-01 with its `cells` list reversed loads, and
  `cell_at` returns the same cell at every position as for FX-01 in file order.
  (The two `Grid` objects are not compared with `==`, since `cells` keeps the
  input order.)
- `cell_at(5, 0)` and `cell_at(0, 5)` on FX-01 raise `IndexError`.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid validation at import (arrows pointing at a wrong cell, runs without a clue,
  crossing words that disagree): spec 003. Here `word_cells` only raises when asked
  to resolve such a clue.
- Checking that an answer's length matches its word's cell count: spec 003.
- Rejecting unknown JSON fields.
- Grid catalogue: spec 004.
- Licensed content only: spec 005.

## Work packages

None.

## Open questions

None.
