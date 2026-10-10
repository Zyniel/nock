"""Grid schema: cells, clues, answer normalisation and clue resolution."""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Position = tuple[int, int]  # (row, column), from zero

LIGATURES = {"Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae"}
RIGHT_SINGLE_QUOTE = chr(0x2019)
REMOVED_CHARACTERS = {" ", "-", "'", RIGHT_SINGLE_QUOTE}
ALLOWED_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class Arrow(StrEnum):
    """Where a clue's word starts and which way it runs."""

    RIGHT = "right"
    DOWN = "down"
    DOWN_THEN_RIGHT = "down_then_right"
    RIGHT_THEN_DOWN = "right_then_down"


def format_position(row: int, column: int) -> str:
    """Write a position the way error messages show it, e.g. ``(0, 5)``."""
    return f"({row}, {column})"


def normalize_answer(text: str) -> str:
    """Normalise an answer to uppercase A to Z only.

    Ligatures are expanded, accents folded, and spaces, hyphens and apostrophes
    removed.

    Args:
        text: The answer as written, possibly with accents or punctuation.

    Returns:
        The answer made only of the letters A to Z.

    Raises:
        ValueError: if the result is empty or holds a character outside A to Z.
    """
    for ligature, expansion in LIGATURES.items():
        text_without_ligatures = text.replace(ligature, expansion)
        text = text_without_ligatures

    decomposed = unicodedata.normalize("NFD", text)
    kept_characters = []
    for character in decomposed:
        if unicodedata.category(character) == "Mn":
            continue
        if character in REMOVED_CHARACTERS:
            continue
        kept_characters.append(character)
    result = "".join(kept_characters).upper()

    if result == "":
        raise ValueError(f"answer {text!r} is empty once normalised")
    for character in result:
        if character not in ALLOWED_LETTERS:
            raise ValueError(
                f"answer {text!r} holds {character!r}, expected only letters A to Z"
            )
    return result


class Clue(BaseModel):
    """A clue: its text, its arrow and the answer of its word."""

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    arrow: Arrow
    answer: Annotated[str, AfterValidator(normalize_answer)]


class LetterCell(BaseModel):
    """A cell that holds one letter of the solution."""

    model_config = ConfigDict(frozen=True)

    type: Literal["letter"] = "letter"
    row: int = Field(ge=0)
    column: int = Field(ge=0)


class ClueCell(BaseModel):
    """A cell that holds one or two clues."""

    model_config = ConfigDict(frozen=True)

    type: Literal["clue"] = "clue"
    row: int = Field(ge=0)
    column: int = Field(ge=0)
    clues: tuple[Clue, ...] = Field(min_length=1, max_length=2)


class EmptyCell(BaseModel):
    """A cell that holds nothing."""

    model_config = ConfigDict(frozen=True)

    type: Literal["empty"] = "empty"
    row: int = Field(ge=0)
    column: int = Field(ge=0)


Cell = Annotated[LetterCell | ClueCell | EmptyCell, Field(discriminator="type")]


class Grid(BaseModel):
    """A grid of width x height cells, one cell per position."""

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    cells: tuple[Cell, ...]

    @model_validator(mode="after")
    def check_one_cell_per_position(self) -> Grid:
        """Check there is exactly one cell for each position of the grid."""
        for cell in self.cells:
            if cell.row >= self.height or cell.column >= self.width:
                position = format_position(cell.row, cell.column)
                raise ValueError(f"cell at {position} is outside the grid")

        seen_positions: set[Position] = set()
        for cell in self.cells:
            position = (cell.row, cell.column)
            if position in seen_positions:
                text = format_position(cell.row, cell.column)
                raise ValueError(f"duplicate cell at {text}")
            seen_positions.add(position)

        for row in range(self.height):
            for column in range(self.width):
                if (row, column) not in seen_positions:
                    text = format_position(row, column)
                    raise ValueError(f"missing cell at {text}")
        return self

    def is_inside(self, row: int, column: int) -> bool:
        """Tell whether (row, column) is a position of the grid."""
        return 0 <= row < self.height and 0 <= column < self.width

    def cell_at(self, row: int, column: int) -> LetterCell | ClueCell | EmptyCell:
        """Return the cell at (row, column).

        Args:
            row: Row of the cell, from zero.
            column: Column of the cell, from zero.

        Returns:
            The cell at that position.

        Raises:
            IndexError: if (row, column) is outside the grid.
        """
        if not self.is_inside(row, column):
            position = format_position(row, column)
            raise IndexError(f"position {position} is outside the grid")
        for cell in self.cells:
            if cell.row == row and cell.column == column:
                return cell
        # Unreachable: the validator guarantees a cell at every position.
        raise IndexError(f"no cell at {format_position(row, column)}")

    def word_cells(self, row: int, column: int, clue_index: int) -> list[Position]:
        """Return the ordered letter cells of the word a clue resolves to.

        The clue is clue `clue_index` of the clue cell at (row, column).

        Args:
            row: Row of the clue cell.
            column: Column of the clue cell.
            clue_index: Index of the clue in that cell.

        Returns:
            The positions of the word's letter cells, in reading order.

        Raises:
            IndexError: if (row, column) is outside the grid, or clue_index is
                not a valid index into that cell's clues.
            ValueError: if the cell at (row, column) is not a clue cell, or the
                word's start cell is outside the grid or is not a letter cell.
        """
        clue_cell = self.cell_at(row, column)
        if not isinstance(clue_cell, ClueCell):
            position = format_position(row, column)
            raise ValueError(f"cell at {position} is not a clue cell")
        if not 0 <= clue_index < len(clue_cell.clues):
            raise IndexError(
                f"clue index {clue_index} is invalid, the clue cell at "
                f"{format_position(row, column)} has {len(clue_cell.clues)} clue(s)"
            )

        arrow = clue_cell.clues[clue_index].arrow
        start_row, start_column, row_step, column_step = self.start_and_step(
            row, column, arrow
        )

        start_position = format_position(start_row, start_column)
        if not self.is_inside(start_row, start_column):
            raise ValueError(f"word starts at {start_position}, outside the grid")
        if not isinstance(self.cell_at(start_row, start_column), LetterCell):
            raise ValueError(f"word starts at {start_position}, not a letter cell")

        positions: list[Position] = []
        current_row = start_row
        current_column = start_column
        while self.is_inside(current_row, current_column):
            if not isinstance(self.cell_at(current_row, current_column), LetterCell):
                break
            positions.append((current_row, current_column))
            current_row += row_step
            current_column += column_step
        return positions

    @staticmethod
    def start_and_step(
        row: int, column: int, arrow: Arrow
    ) -> tuple[int, int, int, int]:
        """Return the start row, start column, row step and column step."""
        if arrow == Arrow.RIGHT:
            return row, column + 1, 0, 1
        if arrow == Arrow.DOWN:
            return row + 1, column, 1, 0
        if arrow == Arrow.DOWN_THEN_RIGHT:
            return row + 1, column, 0, 1
        return row, column + 1, 1, 0
