"""Grid files in the ipuz ArrowWord format: the reader and the writer.

The rules are in `specs/content/grid-files.md`. A file is a JSON object of the
ipuz v2 ArrowWord kind. Every coordinate in a file is `[column, row]`; messages
write positions `(row, column)`.
"""

from __future__ import annotations

import html
import json
import re
from collections.abc import Collection
from datetime import date
from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, ValidationError

from nock.grid import (
    Arrow,
    Cell,
    Clue,
    ClueCell,
    Edge,
    EmptyCell,
    Grid,
    LetterCell,
    Position,
    separators_of,
)
from nock.grid_import import GridImportError, check_arrows, check_words

JsonObject = dict[str, object]

VERSION = "http://ipuz.org/v2"
KIND = "http://ipuz.org/crossword/arrowword#1"
CLUE_PLACEMENT = "blocks"
DEFAULT_BLOCK = "#"
DEFAULT_EMPTY = 0
WRITTEN_LETTER_CELL = 0

OPTIONAL_TEXT_FIELDS = (
    "title",
    "editor",
    "publisher",
    "publication",
    "url",
    "uniqueid",
    "origin",
    "copyright",
)
_REQUIRED_KEYS = (
    "version",
    "kind",
    "clueplacement",
    "dimensions",
    "puzzle",
    "clues",
    "author",
    "date",
    "difficulty",
)
_OPTIONAL_KEYS = ("block", "empty", "solution", *OPTIONAL_TEXT_FIELDS)
_IGNORED_KEYS = (
    "notes",
    "intro",
    "explanation",
    "annotation",
    "charset",
    "showenumerations",
)
_TOP_LEVEL_KEYS = (*_REQUIRED_KEYS, *_OPTIONAL_KEYS, *_IGNORED_KEYS)
_REQUIRED_CLUE_KEYS = ("clue", "location", "cells", "answer")
_CLUE_KEYS = (*_REQUIRED_CLUE_KEYS, "enumeration")

_MAX_AUTHOR_LENGTH = 200
_DATE_PATTERN = re.compile(r"([0-9]{2})/([0-9]{2})/([0-9]{4})")
_ENUMERATION_PATTERN = re.compile(r"[0-9]+(?:[-. '][0-9]+)*")
_COUNT_PATTERN = re.compile(r"[0-9]+")
_SEPARATOR_PATTERN = re.compile(r"[^0-9]")
_DASHED_LETTERS = "TRBL"
_FORCE_OF_TEXT = {"1": 1, "2": 2, "3": 3, "4": 4}


class IpuzError(ValueError):
    """A grid file is refused. The message names the key, clue, cell or edge."""


class GridFile(BaseModel):
    """What a grid file holds: the grid, and how it was published.

    The title and the other optional fields are recorded as written. They are
    never shown to players and never interpreted.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    grid: Grid
    published_on: date
    force: int
    author: str
    title: str | None = None
    editor: str | None = None
    publisher: str | None = None
    publication: str | None = None
    url: str | None = None
    uniqueid: str | None = None
    origin: str | None = None
    copyright: str | None = None


class _Layout(NamedTuple):
    """What the `puzzle` of a file says about each position."""

    letters: set[Position]
    blocks: set[Position]
    dashed_letters: dict[Position, str]  # the `dashed` letters of a letter cell


class _RawClue(NamedTuple):
    """A clue of the file, with its coordinates already turned to (row, column)."""

    text: str
    location: Position
    cells: list[Position]
    answer: str
    enumeration: str | None


class _ClueFacts(NamedTuple):
    """What a file says about a clue that the model does not keep."""

    cells: list[Position]
    enumeration: str | None  # as written in the file, None without one


ClueKey = tuple[Position, int]  # a clue cell and the index of the clue in it


def _format_position(position: Position) -> str:
    """Write a position the way messages show it, e.g. ``(0, 5)``."""
    row, column = position
    return f"({row}, {column})"


def _is_inside(grid: Grid, position: Position) -> bool:
    """Tell whether a position is inside the grid."""
    row, column = position
    return 0 <= row < grid.height and 0 <= column < grid.width


def _format_edge(edge: Edge, grid: Grid) -> str:
    """Write an edge as its two cells, leaving out a cell outside the grid."""
    names: list[str] = []
    for position in edge:
        if _is_inside(grid, position):
            names.append(_format_position(position))
    return ", ".join(names)


def _clue_name(location: Position, text: str) -> str:
    """Name a clue by its clue cell and its text."""
    return f'clue at {_format_position(location)} ("{text}")'


# ---- Reading: the shape of the JSON ---------------------------------------------


def _as_object(value: object, where: str) -> JsonObject:
    """Return `value` as a JSON object, or refuse it."""
    if not isinstance(value, dict):
        raise IpuzError(f"{where} must be a JSON object")
    return value


def _as_list(value: object, where: str) -> list[object]:
    """Return `value` as a JSON array, or refuse it."""
    if not isinstance(value, list):
        raise IpuzError(f"{where} must be a JSON array")
    return value


def _check_keys(data: JsonObject, allowed: Collection[str], where: str) -> None:
    """Refuse a key that is not in `allowed`, unless it holds `:` (a namespace)."""
    for key in data:
        if ":" in key:
            continue
        if key not in allowed:
            raise IpuzError(f"{where} holds the key {key!r}, which is not supported")


def _check_required(data: JsonObject, required: Collection[str], where: str) -> None:
    """Refuse an object that lacks one of the `required` keys."""
    for key in required:
        if key not in data:
            raise IpuzError(f"{where} lacks the key {key!r}")


def _read_position(value: object, where: str) -> Position:
    """Turn an ipuz coordinate `[column, row]` into a position `(row, column)`."""
    if not isinstance(value, list) or len(value) != 2:
        raise IpuzError(f"{where} must be a pair [column, row], got {value!r}")
    column, row = value
    if type(column) is not int or type(row) is not int:
        raise IpuzError(f"{where} must be a pair of whole numbers, got {value!r}")
    return (row, column)


def _parse_object(text: str) -> JsonObject:
    """Parse the text of a file into a JSON object."""
    try:
        data = json.loads(text)
    except ValueError as error:
        raise IpuzError(f"the file is not valid JSON: {error}") from error
    return _as_object(data, "the file")


# ---- Reading: the fields beside the grid ----------------------------------------


def _check_kind(data: JsonObject) -> None:
    """Check `version`, `kind` and `clueplacement`."""
    if data["version"] != VERSION:
        raise IpuzError(f"version must be {VERSION!r}, got {data['version']!r}")
    if data["kind"] != [KIND]:
        raise IpuzError(f"kind must be [{KIND!r}], got {data['kind']!r}")
    if data["clueplacement"] != CLUE_PLACEMENT:
        raise IpuzError(
            f"clueplacement must be {CLUE_PLACEMENT!r}, got {data['clueplacement']!r}"
        )


def _read_publication_date(value: object) -> date:
    """Read `date`, written MM/DD/YYYY and a real date."""
    match = None
    if isinstance(value, str):
        match = _DATE_PATTERN.fullmatch(value)
    if match is None:
        raise IpuzError(f"date must be written MM/DD/YYYY, got {value!r}")
    month, day, year = match.groups()
    try:
        return date(int(year), int(month), int(day))
    except ValueError as error:
        raise IpuzError(f"date {value!r} is not a real date") from error


def _read_force(value: object) -> int:
    """Read `difficulty`: a whole number 1 to 4, or the same digit as a text."""
    if isinstance(value, str) and value in _FORCE_OF_TEXT:
        return _FORCE_OF_TEXT[value]
    if type(value) is int and value in _FORCE_OF_TEXT.values():
        return value
    raise IpuzError(f"difficulty must be a whole number 1 to 4, got {value!r}")


def _read_author(value: object) -> str:
    """Read `author`: a text of 1 to 200 characters once stripped."""
    if not isinstance(value, str):
        raise IpuzError(f"author must be a text, got {value!r}")
    author = value.strip()
    if not 1 <= len(author) <= _MAX_AUTHOR_LENGTH:
        raise IpuzError(
            f"author must have 1 to {_MAX_AUTHOR_LENGTH} characters once stripped"
        )
    return author


def _read_optional_texts(data: JsonObject) -> dict[str, str]:
    """Read the optional texts of rule 11 that the file holds, as written."""
    texts: dict[str, str] = {}
    for name in OPTIONAL_TEXT_FIELDS:
        if name not in data:
            continue
        value = data[name]
        if not isinstance(value, str):
            raise IpuzError(f"{name} must be a text, got {value!r}")
        texts[name] = value
    return texts


def _read_dimensions(value: object) -> tuple[int, int]:
    """Read `dimensions` as (width, height)."""
    dimensions = _as_object(value, "dimensions")
    _check_keys(dimensions, ("width", "height"), "dimensions")
    _check_required(dimensions, ("width", "height"), "dimensions")
    width = dimensions["width"]
    height = dimensions["height"]
    if type(width) is not int or type(height) is not int or width < 1 or height < 1:
        raise IpuzError("dimensions must hold a width and a height of 1 or more")
    return width, height


# ---- Reading: the puzzle --------------------------------------------------------


def _normalised(value: object) -> object:
    """Give the text "0" and the number 0 the same value."""
    if isinstance(value, str) and value == "0":
        return DEFAULT_EMPTY
    return value


def _same_value(value: object, other: object) -> bool:
    """Tell whether two cell values are the same, "0" and 0 being the same."""
    first = _normalised(value)
    second = _normalised(other)
    return type(first) is type(second) and first == second


def _read_block_and_empty(data: JsonObject) -> tuple[str, object]:
    """Read the `block` value and the `empty` value, which must differ."""
    block = data.get("block", DEFAULT_BLOCK)
    empty = data.get("empty", DEFAULT_EMPTY)
    if not isinstance(block, str):
        raise IpuzError(f"block must be a text, got {block!r}")
    if type(empty) is not int and not isinstance(empty, str):
        raise IpuzError(f"empty must be a text or a whole number, got {empty!r}")
    if _same_value(block, empty):
        raise IpuzError(f"block {block!r} must differ from empty {empty!r}")
    return block, empty


def _read_dashed_cell(value: JsonObject, empty: object, where: str) -> str:
    """Read a letter cell drawn with dashed edges and return its `dashed` letters."""
    _check_keys(value, ("cell", "style"), where)
    _check_required(value, ("cell", "style"), where)
    if not _same_value(value["cell"], empty):
        raise IpuzError(f"{where}: cell must be {empty!r}, got {value['cell']!r}")
    style = _as_object(value["style"], f"{where}: style")
    _check_keys(style, ("dashed",), f"{where}: style")
    _check_required(style, ("dashed",), f"{where}: style")
    dashed = style["dashed"]
    if not isinstance(dashed, str) or dashed == "":
        raise IpuzError(f"{where}: dashed must be a text of T, R, B, L")
    for letter in dashed:
        if letter not in _DASHED_LETTERS:
            raise IpuzError(f"{where}: dashed {dashed!r} holds {letter!r}, not T R B L")
    return dashed


def _read_layout(puzzle: object, block: str, empty: object) -> _Layout:
    """Read the values of `puzzle` into the positions of letters and blocks."""
    letters: set[Position] = set()
    blocks: set[Position] = set()
    dashed_letters: dict[Position, str] = {}
    rows = _as_list(puzzle, "puzzle")
    for row_index, row in enumerate(rows):
        values = _as_list(row, f"row {row_index} of puzzle")
        for column_index, value in enumerate(values):
            position = (row_index, column_index)
            where = f"puzzle at {_format_position(position)}"
            if isinstance(value, str) and value == block:
                blocks.add(position)
            elif _same_value(value, empty):
                letters.add(position)
            elif isinstance(value, dict):
                dashed_letters[position] = _read_dashed_cell(value, empty, where)
                letters.add(position)
            else:
                raise IpuzError(
                    f"{where} holds {value!r}, expected {block!r}, {empty!r} "
                    "or a dashed cell"
                )
    return _Layout(letters, blocks, dashed_letters)


# ---- Reading: the clues ---------------------------------------------------------


def _read_raw_clue(item: object, index: int) -> _RawClue:
    """Read one clue of `Clues`, checking its keys and the type of its values."""
    where = f"clue {index + 1} of Clues"
    data = _as_object(item, where)
    _check_keys(data, _CLUE_KEYS, where)
    _check_required(data, _REQUIRED_CLUE_KEYS, where)

    text = data["clue"]
    answer = data["answer"]
    if not isinstance(text, str):
        raise IpuzError(f"{where}: clue must be a text, got {text!r}")
    if not isinstance(answer, str):
        raise IpuzError(f"{where}: answer must be a text, got {answer!r}")
    location = _read_position(data["location"], f"{where}: location")

    cells: list[Position] = []
    cell_values = _as_list(data["cells"], f"{where}: cells")
    if len(cell_values) == 0:
        raise IpuzError(f"{where}: cells must hold one or more cells")
    for cell_value in cell_values:
        cells.append(_read_position(cell_value, f"{where}: a cell of cells"))

    enumeration = None
    if "enumeration" in data:
        enumeration = data["enumeration"]
        if not isinstance(enumeration, str):
            raise IpuzError(f"{where}: enumeration must be a text")
    return _RawClue(text, location, cells, answer, enumeration)


def _read_raw_clues(clues: object) -> list[_RawClue]:
    """Read `clues` into its list of clues, in order."""
    clues_object = _as_object(clues, "clues")
    _check_keys(clues_object, ("Clues",), "clues")
    _check_required(clues_object, ("Clues",), "clues")
    items = _as_list(clues_object["Clues"], "Clues")
    raw_clues: list[_RawClue] = []
    for index, item in enumerate(items):
        raw_clues.append(_read_raw_clue(item, index))
    return raw_clues


def _check_location(raw: _RawClue, layout: _Layout) -> None:
    """Check that a clue sits on a block of the puzzle."""
    if raw.location in layout.blocks:
        return
    row, column = raw.location
    name = _clue_name(raw.location, raw.text)
    written = f"[{column}, {row}]"
    if raw.location in layout.letters:
        raise IpuzError(
            f"{name} has location {written}, a letter cell, expected a clue cell"
        )
    raise IpuzError(f"{name} has location {written}, which is outside the grid")


def _plain_text(raw: _RawClue) -> str:
    """Return the text of a clue: a raw `<` or `>` is refused, entities decoded."""
    if "<" in raw.text or ">" in raw.text:
        name = _clue_name(raw.location, raw.text)
        raise IpuzError(f"{name} holds a raw < or >, expected plain text")
    return html.unescape(raw.text)


def _arrow_of(raw: _RawClue) -> Arrow:
    """Derive the arrow of a clue from its clue cell and the first cells of `cells`."""
    name = _clue_name(raw.location, raw.text)
    clue_row, clue_column = raw.location
    first_row, first_column = raw.cells[0]
    if (first_row, first_column) == (clue_row, clue_column + 1):
        starts_right = True
    elif (first_row, first_column) == (clue_row + 1, clue_column):
        starts_right = False
    else:
        raise IpuzError(
            f"{name} has cells starting at {_format_position(raw.cells[0])}, "
            f"expected right of or below its clue cell {_format_position(raw.location)}"
        )
    if len(raw.cells) == 1:
        return Arrow.RIGHT if starts_right else Arrow.DOWN

    second_row, second_column = raw.cells[1]
    if (second_row, second_column) == (first_row, first_column + 1):
        runs_across = True
    elif (second_row, second_column) == (first_row + 1, first_column):
        runs_across = False
    else:
        raise IpuzError(
            f"{name} has a second cell {_format_position(raw.cells[1])}, expected "
            f"right of or below its first cell {_format_position(raw.cells[0])}"
        )
    if starts_right:
        return Arrow.RIGHT if runs_across else Arrow.RIGHT_THEN_DOWN
    return Arrow.DOWN_THEN_RIGHT if runs_across else Arrow.DOWN


def _read_counts(enumeration: str, name: str) -> list[int]:
    """Read an enumeration: counts of one or more letters joined by separators."""
    if _ENUMERATION_PATTERN.fullmatch(enumeration) is None:
        raise IpuzError(
            f"{name} has the enumeration {enumeration!r}, expected counts of "
            "letters joined by single separators (- . space '), like 3-2-5"
        )
    counts: list[int] = []
    for part in _COUNT_PATTERN.findall(enumeration):
        count = int(part)
        if count < 1:
            raise IpuzError(
                f"{name} has the enumeration {enumeration!r}, "
                "expected each count to be one or more"
            )
        counts.append(count)
    return counts


def _join_counts(pieces: list[str], separators: tuple[str, ...]) -> str:
    """Write pieces one after the other, each pair joined by its separator."""
    text = pieces[0]
    for index, separator in enumerate(separators):
        text += separator + pieces[index + 1]
    return text


def _normalized_enumeration(enumeration: str) -> str:
    """Write an enumeration by its counts and separators, without leading zeros."""
    counts: list[str] = []
    for part in _COUNT_PATTERN.findall(enumeration):
        counts.append(str(int(part)))
    separators = tuple(_SEPARATOR_PATTERN.findall(enumeration))
    return _join_counts(counts, separators)


def _separate(letters: str, counts: list[int], separators: tuple[str, ...]) -> str:
    """Write letters with a separator after each count of an enumeration."""
    pieces: list[str] = []
    start = 0
    for count in counts:
        pieces.append(letters[start : start + count])
        start += count
    return _join_counts(pieces, separators)


def _make_clue(raw: _RawClue, text: str, arrow: Arrow) -> tuple[Clue, _ClueFacts]:
    """Build the model's clue of a file clue, with the answer of rule 9."""
    name = _clue_name(raw.location, raw.text)
    try:
        written_clue = Clue(text=text, arrow=arrow, answer=raw.answer)
    except ValidationError as error:
        raise IpuzError(f"{name} is invalid: {error}") from error
    facts = _ClueFacts(raw.cells, raw.enumeration)
    if raw.enumeration is None:
        return written_clue, facts

    counts = _read_counts(raw.enumeration, name)
    letters = written_clue.letters
    if sum(counts) != len(letters):
        raise IpuzError(
            f"{name} has the enumeration {raw.enumeration!r}, which counts "
            f"{sum(counts)} letters, but the answer {raw.answer} has {len(letters)}"
        )
    if len(written_clue.breaks) > 0 or len(counts) == 1:
        return written_clue, facts
    separators = separators_of(raw.enumeration)
    separated_answer = _separate(letters, counts, separators)
    return Clue(text=text, arrow=arrow, answer=separated_answer), facts


# ---- Reading: building the model and checking it --------------------------------


def _read_clues_by_cell(
    raw_clues: list[_RawClue], layout: _Layout
) -> tuple[dict[Position, list[Clue]], dict[ClueKey, _ClueFacts]]:
    """Build the clues of each clue cell, in the order of `Clues`."""
    clues_by_cell: dict[Position, list[Clue]] = {}
    facts_by_clue: dict[ClueKey, _ClueFacts] = {}
    for raw in raw_clues:
        _check_location(raw, layout)
        clues_of_cell = clues_by_cell.setdefault(raw.location, [])
        if len(clues_of_cell) == 2:
            name = _clue_name(raw.location, raw.text)
            raise IpuzError(f"{name} is a third clue of one cell, expected at most two")
        text = _plain_text(raw)
        arrow = _arrow_of(raw)
        clue, facts = _make_clue(raw, text, arrow)
        facts_by_clue[(raw.location, len(clues_of_cell))] = facts
        clues_of_cell.append(clue)
    return clues_by_cell, facts_by_clue


def _build_grid(
    width: int,
    height: int,
    layout: _Layout,
    clues_by_cell: dict[Position, list[Clue]],
) -> Grid:
    """Build the model's grid from the puzzle and the clues."""
    cells: list[Cell] = []
    for position in sorted(layout.letters | layout.blocks):
        row, column = position
        clues = clues_by_cell.get(position, [])
        if position in layout.letters:
            cells.append(LetterCell(row=row, column=column))
        elif len(clues) > 0:
            cells.append(ClueCell(row=row, column=column, clues=tuple(clues)))
        else:
            cells.append(EmptyCell(row=row, column=column))
    try:
        return Grid(width=width, height=height, cells=tuple(cells))
    except ValidationError as error:
        raise IpuzError(f"puzzle does not fit its dimensions: {error}") from error


def _clue_cells(grid: Grid) -> list[ClueCell]:
    """Return the clue cells of a grid, in the order of the grid's cells."""
    clue_cells: list[ClueCell] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            clue_cells.append(cell)
    return clue_cells


def _check_cells_are_words(
    grid: Grid, facts_by_clue: dict[ClueKey, _ClueFacts]
) -> None:
    """Check that the `cells` of every clue is the word the clue resolves to."""
    for clue_cell in _clue_cells(grid):
        location = (clue_cell.row, clue_cell.column)
        for index, clue in enumerate(clue_cell.clues):
            word = grid.word_cells(clue_cell.row, clue_cell.column, index)
            declared_cells = facts_by_clue[(location, index)].cells
            if word == declared_cells:
                continue
            name = _clue_name(location, clue.text)
            raise IpuzError(
                f"{name} lists {len(declared_cells)} cells, but its word runs from "
                f"{_format_position(word[0])} to {_format_position(word[-1])}, "
                f"{len(word)} cells"
            )


def _read_solution_values(solution: object) -> dict[Position, object]:
    """Read the rows of `solution` into a value for each position."""
    values: dict[Position, object] = {}
    rows = _as_list(solution, "solution")
    for row_index, row in enumerate(rows):
        row_values = _as_list(row, f"row {row_index} of solution")
        for column_index, value in enumerate(row_values):
            values[(row_index, column_index)] = value
    return values


def _check_solution(data: JsonObject, grid: Grid, block: str) -> None:
    """Check that `solution` holds the answers' letters and the block value."""
    if "solution" not in data:
        return
    found_values = _read_solution_values(data["solution"])
    for cell in grid.cells:
        position = (cell.row, cell.column)
        expected = grid.solution_letter(cell.row, cell.column) or block
        if position not in found_values:
            raise IpuzError(
                f"solution has no value at {_format_position(position)}, "
                f"expected {expected!r}"
            )
        if found_values[position] != expected:
            raise IpuzError(
                f"solution holds {found_values[position]!r} at "
                f"{_format_position(position)}, expected {expected!r}"
            )
    for position in found_values:
        if not _is_inside(grid, position):
            raise IpuzError(
                f"solution holds a value at {_format_position(position)}, "
                "outside the grid"
            )


def _check_enumerations(grid: Grid, facts_by_clue: dict[ClueKey, _ClueFacts]) -> None:
    """Check that each answer and its enumeration agree on their separators."""
    for clue_cell in _clue_cells(grid):
        location = (clue_cell.row, clue_cell.column)
        for index, clue in enumerate(clue_cell.clues):
            enumeration = facts_by_clue[(location, index)].enumeration
            if enumeration is None:
                continue
            if _normalized_enumeration(enumeration) == _written_enumeration(clue):
                continue
            name = _clue_name(location, clue.text)
            raise IpuzError(
                f"{name} has the answer {clue.answer}, whose separators do not "
                f"agree with its enumeration {enumeration!r}"
            )


def _break_edges(grid: Grid) -> list[Edge]:
    """Return the edges of the breaks of every word of a grid, each one once.

    Two words that share an edge agree on its break, so it is listed once.
    """
    edges: list[Edge] = []
    for clue_cell in _clue_cells(grid):
        for index in range(len(clue_cell.clues)):
            word_edges = grid.hyphen_edges(clue_cell.row, clue_cell.column, index)
            for edge in word_edges:
                if edge not in edges:
                    edges.append(edge)
    return edges


def _dashed_edge(position: Position, letter: str) -> Edge:
    """Return the edge a `dashed` letter names, its first cell first."""
    row, column = position
    if letter == "T":
        return ((row - 1, column), position)
    if letter == "L":
        return ((row, column - 1), position)
    if letter == "R":
        return (position, (row, column + 1))
    return (position, (row + 1, column))


def _dashed_edges(layout: _Layout) -> list[Edge]:
    """Return the edges named by the `dashed` letters, each one once."""
    edges: list[Edge] = []
    for position in sorted(layout.dashed_letters):
        for letter in layout.dashed_letters[position]:
            edge = _dashed_edge(position, letter)
            if edge not in edges:
                edges.append(edge)
    return edges


def _check_dashed_edges(grid: Grid, layout: _Layout) -> None:
    """Check that the dashed edges are the edges of the breaks, when any is drawn."""
    if len(layout.dashed_letters) == 0:
        return
    break_edges = _break_edges(grid)
    dashed_edges = _dashed_edges(layout)
    for edge in dashed_edges:
        if edge in break_edges:
            continue
        name = _format_edge(edge, grid)
        raise IpuzError(
            f"the dashed edge {name} is not the edge of a break between two letter "
            "cells"
        )
    for edge in break_edges:
        if edge not in dashed_edges:
            raise IpuzError(
                f"the break edge {_format_edge(edge, grid)} is not dashed, while "
                "other edges are"
            )


def _check_grid(
    data: JsonObject,
    grid: Grid,
    layout: _Layout,
    block: str,
    facts_by_clue: dict[ClueKey, _ClueFacts],
) -> None:
    """Run the checks of rule 6 of `content/grids.md` with those of rule 12."""
    try:
        check_arrows(grid)
        _check_cells_are_words(grid, facts_by_clue)
        check_words(grid)
    except GridImportError as error:
        raise IpuzError(str(error)) from error
    _check_solution(data, grid, block)
    _check_enumerations(grid, facts_by_clue)
    _check_dashed_edges(grid, layout)


def read_ipuz(text: str) -> GridFile:
    """Read the text of a `.ipuz` ArrowWord file.

    Args:
        text: The JSON text of the file.

    Returns:
        The grid and the fields the file holds.

    Raises:
        IpuzError: At the first problem, naming the key, clue, position or edge.
    """
    data = _parse_object(text)
    _check_keys(data, _TOP_LEVEL_KEYS, "the file")
    _check_required(data, _REQUIRED_KEYS, "the file")
    _check_kind(data)
    fields: dict[str, object] = {}
    fields["published_on"] = _read_publication_date(data["date"])
    fields["force"] = _read_force(data["difficulty"])
    fields["author"] = _read_author(data["author"])
    fields.update(_read_optional_texts(data))

    width, height = _read_dimensions(data["dimensions"])
    block, empty = _read_block_and_empty(data)
    layout = _read_layout(data["puzzle"], block, empty)
    raw_clues = _read_raw_clues(data["clues"])
    clues_by_cell, facts_by_clue = _read_clues_by_cell(raw_clues, layout)
    grid = _build_grid(width, height, layout, clues_by_cell)
    _check_grid(data, grid, layout, block, facts_by_clue)
    fields["grid"] = grid
    return GridFile.model_validate(fields)


# ---- Writing --------------------------------------------------------------------


def _written_position(position: Position) -> list[int]:
    """Write a position as an ipuz coordinate `[column, row]`."""
    row, column = position
    return [column, row]


def _written_dashed_letters(grid: Grid) -> dict[Position, str]:
    """Return the `dashed` letters of each letter cell that starts a break edge."""
    letters_by_position: dict[Position, str] = {}
    for cell_before, cell_after in _break_edges(grid):
        is_across = cell_before[0] == cell_after[0]
        letter = "R" if is_across else "B"
        already_written = letters_by_position.get(cell_before, "")
        letters_by_position[cell_before] = already_written + letter
    return letters_by_position


def _written_puzzle(grid: Grid) -> list[list[object]]:
    """Write `puzzle`: `#` for a block, `0` for a letter cell, dashed edges."""
    dashed_letters = _written_dashed_letters(grid)
    rows: list[list[object]] = []
    for row in range(grid.height):
        values: list[object] = []
        for column in range(grid.width):
            cell = grid.cell_at(row, column)
            if not isinstance(cell, LetterCell):
                values.append(DEFAULT_BLOCK)
            elif (row, column) in dashed_letters:
                style = {"dashed": dashed_letters[(row, column)]}
                values.append({"cell": WRITTEN_LETTER_CELL, "style": style})
            else:
                values.append(WRITTEN_LETTER_CELL)
        rows.append(values)
    return rows


def _written_solution(grid: Grid) -> list[list[str]]:
    """Write `solution`: the letters at the letter cells, `#` elsewhere."""
    rows: list[list[str]] = []
    for row in range(grid.height):
        values: list[str] = []
        for column in range(grid.width):
            values.append(grid.solution_letter(row, column) or DEFAULT_BLOCK)
        rows.append(values)
    return rows


def _written_enumeration(clue: Clue) -> str:
    """Write the enumeration of a clue: the letters between its breaks."""
    separators = separators_of(clue.answer)
    boundaries = [0, *clue.breaks, len(clue.letters)]
    counts: list[str] = []
    for index in range(len(boundaries) - 1):
        counts.append(str(boundaries[index + 1] - boundaries[index]))
    return _join_counts(counts, separators)


def _written_clues(grid: Grid) -> list[JsonObject]:
    """Write the clues, in the order of their clue cells."""
    written_clues: list[JsonObject] = []
    for clue_cell in _clue_cells(grid):
        for index, clue in enumerate(clue_cell.clues):
            word = grid.word_cells(clue_cell.row, clue_cell.column, index)
            cells = [_written_position(position) for position in word]
            written_clue: JsonObject = {
                "clue": html.escape(clue.text, quote=False),
                "location": _written_position((clue_cell.row, clue_cell.column)),
                "cells": cells,
                "answer": clue.answer,
                "enumeration": _written_enumeration(clue),
            }
            written_clues.append(written_clue)
    return written_clues


def _written_date(published_on: date) -> str:
    """Write a date MM/DD/YYYY."""
    return f"{published_on.month:02d}/{published_on.day:02d}/{published_on.year:04d}"


def write_ipuz(grid_file: GridFile) -> str:
    """Write a grid file as ipuz text.

    Args:
        grid_file: The grid and fields to write.

    Returns:
        The JSON text of an ipuz ArrowWord file. Reading it gives back
        `grid_file`.
    """
    grid = grid_file.grid
    document: JsonObject = {
        "version": VERSION,
        "kind": [KIND],
        "clueplacement": CLUE_PLACEMENT,
        "dimensions": {"width": grid.width, "height": grid.height},
        "author": grid_file.author,
        "date": _written_date(grid_file.published_on),
        "difficulty": grid_file.force,
    }
    for name in OPTIONAL_TEXT_FIELDS:
        value = getattr(grid_file, name)
        if value is not None:
            document[name] = value
    document["puzzle"] = _written_puzzle(grid)
    document["solution"] = _written_solution(grid)
    document["clues"] = {"Clues": _written_clues(grid)}
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
