"""Grid schema: cells, clues, answer letters and breaks, and clue resolution."""

from __future__ import annotations

import unicodedata
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

Position = tuple[int, int]  # (row, column), from zero

_LIGATURES = {"Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae"}
_RIGHT_SINGLE_QUOTE = chr(0x2019)
_HYPHEN = "-"
_REMOVED_CHARACTERS = {" ", _HYPHEN, "'", _RIGHT_SINGLE_QUOTE}
_ALLOWED_LETTERS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class Arrow(StrEnum):
    """Where a clue's word starts and which way it runs."""

    RIGHT = "right"
    DOWN = "down"
    DOWN_THEN_RIGHT = "down_then_right"
    RIGHT_THEN_DOWN = "right_then_down"


class _WordStart(BaseModel):
    """First cell of a word and the step taken from one letter to the next."""

    model_config = ConfigDict(frozen=True)

    row: int
    column: int
    row_step: int
    column_step: int


def _format_position(row: int, column: int) -> str:
    """Write a position the way error messages show it, e.g. ``(0, 5)``."""
    return f"({row}, {column})"


def _letters_of(text: str) -> str:
    """Return the letters of a text, uppercased, without checking them.

    Ligatures are expanded, accents folded, and spaces, hyphens and apostrophes
    removed.
    """
    expanded_text = text
    for ligature, expansion in _LIGATURES.items():
        expanded_text = expanded_text.replace(ligature, expansion)

    decomposed = unicodedata.normalize("NFD", expanded_text)
    kept_characters = []
    for character in decomposed:
        if unicodedata.category(character) == "Mn":
            continue
        if character in _REMOVED_CHARACTERS:
            continue
        kept_characters.append(character)
    return "".join(kept_characters).upper()


def normalize_answer(text: str) -> str:
    """Normalise an answer to uppercase A to Z only: its letters.

    Ligatures are expanded, accents folded, and spaces, hyphens and apostrophes
    removed.

    Args:
        text: The answer as written, possibly with accents or punctuation.

    Returns:
        The answer made only of the letters A to Z.

    Raises:
        ValueError: if the result is empty or holds a character outside A to Z.
    """
    result = _letters_of(text)
    if result == "":
        raise ValueError(f"answer {text!r} is empty once normalised")
    for character in result:
        if character not in _ALLOWED_LETTERS:
            raise ValueError(
                f"answer {text!r} holds {character!r}, expected only letters A to Z"
            )
    return result


def _check_hyphens(text: str) -> None:
    """Check that every hyphen of an answer has a letter right before and after.

    Args:
        text: The answer as written.

    Raises:
        ValueError: if a hyphen starts or ends the answer, or sits beside another
            hyphen, a space or an apostrophe.
    """
    last_index = len(text) - 1
    for index, character in enumerate(text):
        if character != _HYPHEN:
            continue
        if index == 0 or index == last_index:
            raise ValueError(
                f'answer "{text}" starts or ends with a hyphen, '
                "expected each hyphen between two letters"
            )
        before = text[index - 1]
        after = text[index + 1]
        if before in _REMOVED_CHARACTERS or after in _REMOVED_CHARACTERS:
            raise ValueError(
                f'answer "{text}" has a hyphen beside a hyphen, a space or an '
                "apostrophe, expected each hyphen between two letters"
            )


def _breaks_of(text: str) -> tuple[int, ...]:
    """Return the breaks of an answer: the number of letters before each hyphen.

    Args:
        text: The answer as written.

    Returns:
        One count per hyphen, in reading order.
    """
    breaks: list[int] = []
    for index, character in enumerate(text):
        if character == _HYPHEN:
            letters_before = _letters_of(text[:index])
            breaks.append(len(letters_before))
    return tuple(breaks)


def _check_answer(text: str) -> str:
    """Check an answer as written: it has letters, and its hyphens are well placed.

    Args:
        text: The answer as written.

    Returns:
        The same text, unchanged.

    Raises:
        ValueError: if the answer breaks rule 4 of the grid model.
    """
    normalize_answer(text)
    _check_hyphens(text)
    return text


class Clue(BaseModel):
    """A clue: its text, its arrow and the answer of its word.

    The answer is kept as written; its letters and breaks are derived from it
    and never stored.
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    arrow: Arrow
    answer: Annotated[str, AfterValidator(_check_answer)]

    @property
    def letters(self) -> str:
        """The answer's letters, A to Z: the solution of the clue's word."""
        return normalize_answer(self.answer)

    @property
    def breaks(self) -> tuple[int, ...]:
        """The answer's hyphens, each counted as the number of letters before it."""
        return _breaks_of(self.answer)


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
                position = _format_position(cell.row, cell.column)
                raise ValueError(f"cell at {position} is outside the grid")

        seen_positions: set[Position] = set()
        for cell in self.cells:
            position = (cell.row, cell.column)
            if position in seen_positions:
                text = _format_position(cell.row, cell.column)
                raise ValueError(f"duplicate cell at {text}")
            seen_positions.add(position)

        for row in range(self.height):
            for column in range(self.width):
                if (row, column) not in seen_positions:
                    text = _format_position(row, column)
                    raise ValueError(f"missing cell at {text}")
        return self

    def _is_inside(self, row: int, column: int) -> bool:
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
        if not self._is_inside(row, column):
            position = _format_position(row, column)
            raise IndexError(f"position {position} is outside the grid")
        for cell in self.cells:
            if cell.row == row and cell.column == column:
                return cell
        # Unreachable: the validator guarantees a cell at every position.
        raise IndexError(f"no cell at {_format_position(row, column)}")

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
            position = _format_position(row, column)
            raise ValueError(f"cell at {position} is not a clue cell")
        if not 0 <= clue_index < len(clue_cell.clues):
            raise IndexError(
                f"clue index {clue_index} is invalid, the clue cell at "
                f"{_format_position(row, column)} has {len(clue_cell.clues)} clue(s)"
            )

        arrow = clue_cell.clues[clue_index].arrow
        word_start = self._start_and_step(row, column, arrow)

        start_position = _format_position(word_start.row, word_start.column)
        if not self._is_inside(word_start.row, word_start.column):
            raise ValueError(f"word starts at {start_position}, outside the grid")
        start_cell = self.cell_at(word_start.row, word_start.column)
        if not isinstance(start_cell, LetterCell):
            raise ValueError(f"word starts at {start_position}, not a letter cell")

        positions: list[Position] = []
        current_row = word_start.row
        current_column = word_start.column
        while self._is_inside(current_row, current_column):
            if not isinstance(self.cell_at(current_row, current_column), LetterCell):
                break
            positions.append((current_row, current_column))
            current_row += word_start.row_step
            current_column += word_start.column_step
        return positions

    @staticmethod
    def _start_and_step(row: int, column: int, arrow: Arrow) -> _WordStart:
        """Return where the word of a clue starts and which way it runs."""
        if arrow == Arrow.RIGHT:
            return _WordStart(row=row, column=column + 1, row_step=0, column_step=1)
        if arrow == Arrow.DOWN:
            return _WordStart(row=row + 1, column=column, row_step=1, column_step=0)
        if arrow == Arrow.DOWN_THEN_RIGHT:
            return _WordStart(row=row + 1, column=column, row_step=0, column_step=1)
        if arrow == Arrow.RIGHT_THEN_DOWN:
            return _WordStart(row=row, column=column + 1, row_step=1, column_step=0)
        raise ValueError(f"unknown arrow {arrow!r}")
