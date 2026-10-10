---
id: "002"
title: Grid schema
status: draft
---

# 002 - Grid schema

Epic E1 Grid content and model (US-1.1) · Release: MVP · Epic depends on: None
The FX-01 reference grid and the glossary are in `specs/_reference.md`.

## Goal

As a builder agent, I need one grid schema, so that every component reads a grid the same way.

Every other epic reads the grid through this model, so it ships first.

## Public interface

Proposed, to confirm in review (see open questions). Models follow
`specs/_architecture.md`.

```python
# src/nock/grid.py
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
    """Uppercase A to Z only: accents folded, spaces and hyphens removed."""


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
    cells: tuple[Cell, ...]  # exactly one per position, width * height in all

    def cell_at(self, row: int, column: int) -> Cell: ...

    def clue_cells(self, row: int, column: int, clue_index: int) -> list[Position]:
        """Ordered letter cells the clue at (row, column) resolves to."""
```

Loading and saving use Pydantic directly: `Grid.model_validate_json(text)` and
`grid.model_dump_json()`. Invalid structure raises `pydantic.ValidationError`.

## Acceptance criteria

- **AC-1** (AC-1.1.1) A grid declares its width, its height and one type per cell: letter, clue or empty.
- **AC-2** (AC-1.1.2) A clue cell holds one or two clues. Each clue has a text, one of the four arrow types, and resolves to an ordered list of letter cells.
- **AC-3** (AC-1.1.3) Answers are stored as uppercase A to Z without accents, spaces or hyphens: ÊTRE is ETRE, ARC-EN-CIEL is ARCENCIEL.
- **AC-4** (AC-1.1.4) FX-01 written in the schema survives load, save and load again with no difference.

## Edge cases and errors

None stated in the backlog. To complete during review.

## Out of scope

- A grid editor and automatic grid generation (epic E1).
- Grid validation at import: spec 003.
- Grid catalogue: spec 004.
- Licensed content only: spec 005.

## Work packages

None.

## Open questions

- Confirm the proposed interface, in particular that the solution letters live on each clue (as above) rather than on each letter cell.
- Should the cell-count rule (one cell per position, width * height in all) be a model validator here or an import check in spec 003? Proposed: model validator here, since a grid without it is not a grid.
- `pydantic` is a new dependency; the human adds it before this spec is built.
