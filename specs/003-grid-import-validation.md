---
id: "003"
title: Grid validation at import
status: approved
---

# 003 - Grid validation at import

Epic E1 Grid content and model (US-1.2) · Release: MVP · Epic depends on: None
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a content editor, I want invalid grids rejected at import, so that players never meet an unsolvable grid.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Every name below is importable from `nock.grid_import`. The grid model, clue
resolution (`Grid.word_cells`), the JSON format and the coordinate format
`(row, column)` (for example `(0, 5)`, one space after the comma) are those of
spec 002.

```python
# src/nock/grid_import.py
from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from nock.grid import Grid


class GridImportError(ValueError):
    """Raised when a grid is rejected. The message names the cell, run or words."""


class ImportReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    grid: Grid
    word_count: int  # number of clues in the grid, one word per clue
    letter_cell_count: int
    clue_cell_count: int


def import_grid(text: str) -> ImportReport:
    """Parse and check a grid given as JSON text.

    Raises:
        GridImportError: at the first problem found (see "Order of checks").
    """
```

### Order of checks

`import_grid` stops at the first problem and raises a single `GridImportError`.
It never lets `pydantic.ValidationError`, `ValueError` from `word_cells`, or any
other exception escape for an invalid grid. Checks run in this order:

1. Parse: `Grid.model_validate_json(text)` (spec 002). A
   `pydantic.ValidationError`, including invalid JSON and the one-cell-per-position
   rule of spec 002 AC-5, becomes `GridImportError` (raised `from` the original
   error) whose message contains the Pydantic error text, so a position named by
   spec 002 is named here too.
2. Arrows (AC-1): clue cells in row-major order, clues in their order in the cell.
3. Answer lengths (AC-5): same order as step 2.
4. Two clues with the same word (AC-7): clues in the order of step 2; the error
   is raised at the first clue whose word equals the word of an earlier clue.
5. Letter cells in no word (AC-6): letter cells in row-major order.
6. Runs without a clue (AC-2): horizontal runs in row-major order of their first
   cell, then vertical runs in column-major order of their first cell.
7. Crossing letters (AC-3): letter cells in row-major order.

Why this order: the clue-by-clue checks (steps 2 and 3) come first, then the check
over all words together (step 4), then cell coverage from the simplest rule (each
letter cell is in some word, step 5) to the strictest (each run is exactly one
word, step 6). Crossing letters come last, because step 3 guarantees that
`answer[k]` exists for every cell of every word.

The checks of steps 2 to 7 are plain functions over the validated grid, following
`specs/_architecture.md`. Their names are not part of the public interface.

### Definitions

- A clue's word is `grid.word_cells(row, column, clue_index)` (spec 002).
- A run is a maximal sequence of two or more letter cells that are consecutive in
  one row (horizontal run) or one column (vertical run). It ends at a clue cell,
  an empty cell or the grid edge. A single letter between two non-letter cells is
  not a run.
- A run has a clue when some clue's word is exactly the run's cells (same cells,
  same direction). Since a word runs to the next non-letter cell, that means a
  word starts at the run's first cell.
- The letter a word puts in its k-th cell (from 0) is `answer[k]` of its clue.
- A word is named in messages by its answer, for example `MIME`.
- A clue is named in messages by its clue cell coordinates and its text, for
  example `(0, 0)` and `Passoire fine`.
- Two clues have the same word when their `word_cells` lists are equal, whether
  the clues sit in one clue cell or in two.

### FX-01 for tests

The test-writer creates `tests/fixtures/fx01.json` as specified in spec 002 (and
shares it with the tests of spec 002). Most failure cases below are FX-01 with one
change. Such a change can cause more than one problem; the expected error is then
the first one in "Order of checks". In the small hand-built grids below, each
clue's text may be any non-empty string unless a text is given.

## Acceptance criteria

- **AC-1** (AC-1.2.1) Given a clue whose arrow points to a clue cell, an empty cell or outside the grid, when I import, then the import fails and names the cell: `import_grid` raises `GridImportError` whose message contains the coordinates of the clue cell and of the cell the arrow points to. Examples on FX-01: the clue at (2, 0) given arrow `down` points to the clue cell (3, 0), so the message contains `(2, 0)` and `(3, 0)`; the clue at (0, 4) given arrow `right` points outside to (0, 5), so the message contains `(0, 4)` and `(0, 5)`; with (0, 1) made an empty cell, the second clue of (0, 0) points to it, so the message contains `(0, 0)` and `(0, 1)`.
- **AC-2** (AC-1.2.2) Given a run of two or more letter cells in a row or column with no clue, the import fails and names the run: `import_grid` raises `GridImportError` whose message contains the coordinates of the run's first and last cells. Example: FX-01 with (3, 0) made an empty cell leaves the run (3, 1) to (3, 4) without a clue, so the message contains `(3, 1)` and `(3, 4)`.
- **AC-3** (AC-1.2.3) Given two crossing words that disagree on their shared letter, the import fails and names both words: `import_grid` raises `GridImportError` whose message contains both answers and the coordinates of the shared cell. Example: FX-01 with the answer of the clue at (0, 2) changed from `MIME` to `MIMA` disagrees with `LEST` at (4, 2), so the message contains `MIMA`, `LEST` and `(4, 2)`.
- **AC-4** (AC-1.2.4) FX-01 imports and reports 8 words, 18 letter cells and 7 clue cells: `import_grid(fx01_text)` returns an `ImportReport` with `word_count == 8`, `letter_cell_count == 18`, `clue_cell_count == 7`, and `grid == Grid.model_validate_json(fx01_text)`.
- **AC-5** (new) Given a clue whose answer length differs from its word's cell count, the import fails and names the clue: `import_grid` raises `GridImportError` whose message contains the clue cell coordinates and the answer. Example: FX-01 with the answer of the clue at (0, 2) changed from `MIME` to `MIM` (3 letters for 4 cells), so the message contains `(0, 2)` and `MIM`.
- **AC-6** (new) Given a letter cell that belongs to no clue's word, the import fails and names the cell: `import_grid` raises `GridImportError` whose message contains its coordinates. Example: FX-01 with the second clue of (0, 0) (`De la marine`, `NAVAL`) removed leaves (0, 1) in no word, so the message contains `(0, 1)`.
- **AC-7** (new) Given two clues that resolve to the same word, the import fails and names both clues: `import_grid` raises `GridImportError` whose message contains the coordinates of both clue cells and both clue texts. Example: FX-01 with the second clue of (0, 0) changed to arrow `down_then_right` and answer `TAMIS` makes both clues of (0, 0) resolve to (1, 0) to (1, 4), so the message contains `(0, 0)`, `Passoire fine` and `De la marine`.

## Edge cases and errors

- Parse errors (all criteria): `import_grid("not json")` raises `GridImportError`.
  FX-01 without its cell at (2, 3) raises `GridImportError` whose message contains
  `(2, 3)`. A clue cell with 0 or 3 clues raises `GridImportError`. In each case
  `error.__cause__` is a `pydantic.ValidationError`.
- First problem wins (AC-1, AC-2): FX-01 with the clue at (0, 4) given arrow
  `right` also leaves the run (1, 4) to (4, 4) without a clue; the error is the
  arrow one, so its message contains `(0, 5)`.
- First problem wins (AC-2, AC-3): FX-01 with (3, 0) made an empty cell and the
  answer `MIME` changed to `MIMA` raises the run error, whose message contains
  `(3, 1)` and `(3, 4)`.
- Isolated letters are not runs (AC-2): FX-01 itself has the single letters (0, 1)
  across and (1, 0) down, and imports without error (AC-4).
- First problem wins (AC-6, AC-2): FX-01 with the clue cell at (4, 0) replaced by
  a letter cell leaves (4, 0) in no word and the run (4, 0) to (4, 4) without a
  clue; the error is the AC-6 one, so its message contains `(4, 0)`. Likewise the
  AC-6 example also leaves the run (0, 1) to (4, 1) without a clue, and the error
  is the AC-6 one.
- First problem wins (AC-7, AC-2): the AC-7 example also leaves the run (0, 1) to
  (4, 1) without a clue and (0, 1) in no word; the error is the AC-7 one.
- First problem wins (AC-5, AC-3): with `MIM` the crossing at (4, 2) cannot be
  compared; the error is the AC-5 one and no other exception escapes.
- Lengths are checked against words, not runs (AC-5): FX-01 with the answer of the
  clue at (2, 0) changed from `VIDE` to `VIDES` raises the AC-5 error, whose
  message contains `(2, 0)` and `VIDES`.
- Two clue cells with the same word (AC-7). Grid of width 3, height 2: (0, 0)
  empty; (0, 1) clue cell with one clue, text `Haut`, arrow `down_then_right`,
  answer `AB`; (0, 2) empty; (1, 0) clue cell with one clue, text `Gauche`, arrow
  `right`, answer `AB`; (1, 1) letter; (1, 2) letter. Both clues resolve to
  (1, 1) to (1, 2), so the message contains `(0, 1)`, `(1, 0)`, `Haut` and
  `Gauche`.
- A word that starts in the middle of a run does not give the run a clue (AC-2).
  Grid of width 2, height 3: (0, 0) clue cell with one clue `right`, answer `A`;
  (0, 1) letter; (1, 0) clue cell with one clue `right_then_down`, answer `BC`;
  (1, 1) letter; (2, 0) empty; (2, 1) letter. The vertical run (0, 1) to (2, 1)
  has no word starting at (0, 1), so the message contains `(0, 1)` and `(2, 1)`.
- Empty cells are counted nowhere (AC-4): a report counts only letter cells and
  clue cells.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Reporting more than one problem per import.
- Rejecting one-letter words: a clue whose word has one cell is accepted when its
  answer has one letter.
- Grid schema: spec 002.
- Grid catalogue: spec 004.
- Licensed content only: spec 005.

## Work packages

None.

## Open questions

None.
