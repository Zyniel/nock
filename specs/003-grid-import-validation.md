---
id: "003"
title: Grid validation at import
status: draft
---

# 003 - Grid validation at import

Epic E1 Grid content and model (US-1.2) · Release: MVP · Epic depends on: None
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a content editor, I want invalid grids rejected at import, so that players never meet an unsolvable grid.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Proposed, to confirm in review (see open questions):

```python
# src/nock/grid_import.py
from pydantic import BaseModel, ConfigDict

from nock.grid import Grid


class GridImportError(ValueError):
    """Raised when a grid is rejected. The message names the cells or words."""


class ImportReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    grid: Grid
    word_count: int
    letter_cell_count: int
    clue_cell_count: int


def import_grid(text: str) -> ImportReport: ...
```

`import_grid` first parses the JSON into `Grid` (spec 002). A Pydantic
`ValidationError` there is turned into `GridImportError`. The checks of AC-1 to
AC-3 then run as plain functions over the validated grid, following
`specs/_architecture.md`.

## Acceptance criteria

- **AC-1** (AC-1.2.1) Given a clue whose arrow points to a clue cell, an empty cell or outside the grid, when I import, then the import fails and names the cell.
- **AC-2** (AC-1.2.2) Given a run of two or more letter cells in a row or column with no clue, the import fails and names the run.
- **AC-3** (AC-1.2.3) Given two crossing words that disagree on their shared letter, the import fails and names both words.
- **AC-4** (AC-1.2.4) FX-01 imports and reports 8 words, 18 letter cells and 7 clue cells.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid schema: spec 002.
- Grid catalogue: spec 004.
- Licensed content only: spec 005.

## Work packages

None.

## Open questions

- Should import report every problem at once or stop at the first one? Proposed: stop at the first, with the message naming the cell, run or words.
