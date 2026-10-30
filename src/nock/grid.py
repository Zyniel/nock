"""Grid schema: cells, clues, answer letters and breaks, and clue resolution."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    model_validator,
)

Position = tuple[int, int]  # (row, column), from zero
Edge = tuple[Position, Position]  # two neighbouring cells of a word, first one first

_LIGATURES = {"Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae"}
_RIGHT_SINGLE_QUOTE = chr(0x2019)
_SEPARATORS = {"-", ".", " ", "'", _RIGHT_SINGLE_QUOTE}
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

    Ligatures are expanded, accents folded, and the separators removed.
    """
    expanded_text = text
    for ligature, expansion in _LIGATURES.items():
        expanded_text = expanded_text.replace(ligature, expansion)

    decomposed = unicodedata.normalize("NFD", expanded_text)
    kept_characters = []
    for character in decomposed:
        if unicodedata.category(character) == "Mn":
            continue
        if character in _SEPARATORS:
            continue
        kept_characters.append(character)
    return "".join(kept_characters).upper()


def normalize_answer(text: str) -> str:
    """Normalise an answer to uppercase A to Z only: its letters.

    Ligatures are expanded, accents folded, and the separators (hyphen, dot,
    space, apostrophe) removed.

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


def _check_separators(text: str) -> None:
    """Check that every separator of an answer has a letter right before and after.

    Args:
        text: The answer as written.

    Raises:
        ValueError: if a separator starts or ends the answer, or sits beside
            another separator.
    """
    last_index = len(text) - 1
    for index, character in enumerate(text):
        if character not in _SEPARATORS:
            continue
        if index == 0 or index == last_index:
            raise ValueError(
                f'answer "{text}" starts or ends with a separator, '
                "expected each separator between two letters"
            )
        before = text[index - 1]
        after = text[index + 1]
        if before in _SEPARATORS or after in _SEPARATORS:
            raise ValueError(
                f'answer "{text}" has two separators in a row, '
                "expected each separator between two letters"
            )


def separators_of(text: str) -> tuple[str, ...]:
    """Return the separators of an answer, one per break, in reading order.

    Args:
        text: The answer as written.

    Returns:
        The separator of each break; the right single quote is given as `'`.
    """
    separators: list[str] = []
    for character in text:
        if character not in _SEPARATORS:
            continue
        if character == _RIGHT_SINGLE_QUOTE:
            separators.append("'")
        else:
            separators.append(character)
    return tuple(separators)


def _breaks_of(text: str) -> tuple[int, ...]:
    """Return the breaks of an answer: the number of letters before each separator.

    Args:
        text: The answer as written.

    Returns:
        One count per separator, in reading order.
    """
    breaks: list[int] = []
    for index, character in enumerate(text):
        if character in _SEPARATORS:
            letters_before = _letters_of(text[:index])
            breaks.append(len(letters_before))
    return tuple(breaks)


def _check_answer(text: str) -> str:
    """Check an answer as written: it has letters, and its separators are well placed.

    Args:
        text: The answer as written.

    Returns:
        The same text, unchanged.

    Raises:
        ValueError: if the answer breaks rule 4 of the grid model.
    """
    normalize_answer(text)
    _check_separators(text)
    return text


@dataclass
class _AnswerFacts:
    """What a clue derives from its answer; the clue fills it, then only reads."""

    letters: str = ""
    breaks: tuple[int, ...] = ()


class Clue(BaseModel):
    """A clue: its text, its arrow and the answer of its word.

    The answer is kept as written; its letters and breaks are derived from it
    once, when the clue is built, and never dumped.
    """

    model_config = ConfigDict(frozen=True)

    text: str = Field(min_length=1)
    arrow: Arrow
    answer: Annotated[str, AfterValidator(_check_answer)]

    _derived: _AnswerFacts = PrivateAttr(default_factory=_AnswerFacts)

    def model_post_init(self, context: object, /) -> None:
        """Derive the letters and the breaks of the answer, once."""
        self._derived.letters = normalize_answer(self.answer)
        self._derived.breaks = _breaks_of(self.answer)

    @property
    def letters(self) -> str:
        """The answer's letters, A to Z: the solution of the clue's word."""
        return self._derived.letters

    @property
    def breaks(self) -> tuple[int, ...]:
        """The answer's breaks: the letters before each separator."""
        return self._derived.breaks


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


class Word(BaseModel):
    """The word a clue resolves to: where it is and what it spells."""

    model_config = ConfigDict(frozen=True)

    row: int  # row of the clue cell
    column: int  # column of the clue cell
    clue_index: int  # index of the clue in its clue cell
    cells: tuple[Position, ...]  # the letter cells, in reading order
    letters: str  # the letters of the clue's answer


@dataclass
class _Lookups:
    """What a grid derives once it is built; the grid fills it, then only reads."""

    cell_at: dict[Position, LetterCell | ClueCell | EmptyCell] = field(
        default_factory=dict
    )
    words: tuple[Word, ...] = ()
    word_of_clue: dict[tuple[int, int, int], Word] = field(default_factory=dict)
    letter_of_cell: dict[Position, str] = field(default_factory=dict)


class Grid(BaseModel):
    """A grid of width x height cells, one cell per position.

    Once built, the grid derives its lookups once: the cell at each position,
    its words and the solution letter of each letter cell. They are private
    and never dumped, so the JSON of a grid holds only its fields.
    """

    model_config = ConfigDict(frozen=True)

    width: int = Field(gt=0)
    height: int = Field(gt=0)
    cells: tuple[Cell, ...]

    _lookups: _Lookups = PrivateAttr(default_factory=_Lookups)

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

        # The rules hold, so the lookups can be filled, in this order.
        self._lookups.cell_at = self._index_cells()
        self._lookups.words = self._resolve_words()
        self._lookups.word_of_clue = self._index_words()
        self._lookups.letter_of_cell = self._index_solution_letters()
        return self

    def _index_cells(self) -> dict[Position, LetterCell | ClueCell | EmptyCell]:
        """Return the cell at each position."""
        index: dict[Position, LetterCell | ClueCell | EmptyCell] = {}
        for cell in self.cells:
            index[(cell.row, cell.column)] = cell
        return index

    def _resolve_words(self) -> tuple[Word, ...]:
        """Return the word of each clue that resolves, in clue order.

        Clue order is the clue cell's row, then its column, then the clue's
        index. A clue that does not resolve has no word and raises nothing here.
        """
        clue_cells: list[ClueCell] = []
        for cell in self.cells:
            if isinstance(cell, ClueCell):
                clue_cells.append(cell)
        clue_cells.sort(key=lambda clue_cell: (clue_cell.row, clue_cell.column))

        words: list[Word] = []
        for clue_cell in clue_cells:
            for clue_index, clue in enumerate(clue_cell.clues):
                try:
                    positions = self._resolve_word_cells(
                        clue_cell.row, clue_cell.column, clue_index
                    )
                except ValueError:
                    continue
                word = Word(
                    row=clue_cell.row,
                    column=clue_cell.column,
                    clue_index=clue_index,
                    cells=tuple(positions),
                    letters=clue.letters,
                )
                words.append(word)
        return tuple(words)

    def _index_words(self) -> dict[tuple[int, int, int], Word]:
        """Return each word by the clue it belongs to."""
        index: dict[tuple[int, int, int], Word] = {}
        for word in self._lookups.words:
            index[(word.row, word.column, word.clue_index)] = word
        return index

    def _index_solution_letters(self) -> dict[Position, str]:
        """Return the solution letter of each cell some word gives a letter to.

        A cell takes the letter of the first word, in clue order, whose answer
        has a letter there.
        """
        letters: dict[Position, str] = {}
        for word in self._lookups.words:
            for letter_index, position in enumerate(word.cells):
                if letter_index >= len(word.letters) or position in letters:
                    continue
                letters[position] = word.letters[letter_index]
        return letters

    @property
    def words(self) -> tuple[Word, ...]:
        """The words of the grid, one per clue that resolves, in clue order."""
        return self._lookups.words

    def solution_letter(self, row: int, column: int) -> str | None:
        """Return the solution letter of the cell at (row, column).

        Args:
            row: Row of the cell, from zero.
            column: Column of the cell, from zero.

        Returns:
            The letter of the first word, in clue order, that holds the cell and
            whose answer has a letter there. None for a clue cell, an empty cell,
            a letter cell in no word and a position outside the grid.
        """
        return self._lookups.letter_of_cell.get((row, column))

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
        return self._lookups.cell_at[(row, column)]

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
        word = self._lookups.word_of_clue.get((row, column, clue_index))
        if word is not None:
            return list(word.cells)
        return self._resolve_word_cells(row, column, clue_index)

    def _resolve_word_cells(
        self, row: int, column: int, clue_index: int
    ) -> list[Position]:
        """Walk the word of a clue, with the errors of `word_cells`."""
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

    def hyphen_edges(self, row: int, column: int, clue_index: int) -> list[Edge]:
        """Return the edges where a clue's answer has a break, whatever its separator.

        The clue is clue `clue_index` of the clue cell at (row, column). Its word
        must have as many cells as the answer has letters.

        Args:
            row: Row of the clue cell.
            column: Column of the clue cell.
            clue_index: Index of the clue in that cell.

        Returns:
            One (cell before, cell after) pair per break, in reading order.

        Raises:
            IndexError: if (row, column) is outside the grid, clue_index is not a
                valid index into that cell's clues, or the word is shorter than
                the answer.
            ValueError: if the cell at (row, column) is not a clue cell, or the
                word's start cell is outside the grid or is not a letter cell.
        """
        word = self.word_cells(row, column, clue_index)
        clue_cell = self.cell_at(row, column)
        if not isinstance(clue_cell, ClueCell):
            raise ValueError(f"cell at {_format_position(row, column)} is not a clue")
        edges: list[Edge] = []
        for letters_before in clue_cell.clues[clue_index].breaks:
            cell_before = word[letters_before - 1]
            cell_after = word[letters_before]
            edges.append((cell_before, cell_after))
        return edges

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
