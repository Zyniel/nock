"""Grid import: parse a grid from JSON and check that it can be solved."""

from __future__ import annotations

from typing import NamedTuple

from pydantic import BaseModel, ConfigDict, ValidationError

from nock.grid import Arrow, ClueCell, Edge, Grid, LetterCell, Position


class GridImportError(ValueError):
    """Raised when a grid is rejected. The message names the cell, run or words."""


class ImportReport(BaseModel):
    """What a successful import found."""

    model_config = ConfigDict(frozen=True)

    grid: Grid
    word_count: int  # number of clues in the grid, one word per clue
    letter_cell_count: int
    clue_cell_count: int


class _PlacedClue(NamedTuple):
    """A clue with the position of its clue cell and its resolved word."""

    row: int
    column: int
    text: str
    answer: str  # as written, for messages
    letters: str
    word: list[Position]
    clue_index: int  # index of the clue in its clue cell


# Offset of the word's first cell from the clue cell: (rows, columns).
_START_OFFSETS = {
    Arrow.RIGHT: (0, 1),
    Arrow.DOWN: (1, 0),
    Arrow.DOWN_THEN_RIGHT: (1, 0),
    Arrow.RIGHT_THEN_DOWN: (0, 1),
}


def _format_position(position: Position) -> str:
    """Write a position the way messages show it, e.g. ``(0, 5)``."""
    row, column = position
    return f"({row}, {column})"


def _format_clue(clue: _PlacedClue) -> str:
    """Name a clue by its clue cell coordinates and its text."""
    cell = _format_position((clue.row, clue.column))
    return f'{cell} "{clue.text}"'


def _clue_cells_in_order(grid: Grid) -> list[ClueCell]:
    """Return the clue cells in row-major order."""
    clue_cells = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            clue_cells.append(cell)
    return sorted(clue_cells, key=lambda cell: (cell.row, cell.column))


def _letter_positions_in_order(grid: Grid) -> list[Position]:
    """Return the positions of the letter cells in row-major order."""
    positions = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    return sorted(positions)


def check_arrows(grid: Grid) -> None:
    """Check that every arrow points to a letter cell (step 2 of the checks).

    Args:
        grid: A grid that parsed into the model.

    Raises:
        GridImportError: At the first arrow that points outside the grid or to
            a cell that is not a letter cell.
    """
    for clue_cell in _clue_cells_in_order(grid):
        for clue in clue_cell.clues:
            row_offset, column_offset = _START_OFFSETS[clue.arrow]
            target_row = clue_cell.row + row_offset
            target_column = clue_cell.column + column_offset
            inside = 0 <= target_row < grid.height and 0 <= target_column < grid.width
            if inside:
                target_cell = grid.cell_at(target_row, target_column)
                if isinstance(target_cell, LetterCell):
                    continue
                reason = f"not a letter cell (its type is {target_cell.type})"
            else:
                reason = "outside the grid"
            source = _format_position((clue_cell.row, clue_cell.column))
            target = _format_position((target_row, target_column))
            raise GridImportError(
                f'clue at {source} ("{clue.text}") has arrow {clue.arrow.value} '
                f"pointing to {target}, which is {reason}"
            )


def _place_clues(grid: Grid) -> list[_PlacedClue]:
    """Resolve every clue to its word, in the order of the checks.

    Only call this once the arrows have been checked.
    """
    placed_clues = []
    for clue_cell in _clue_cells_in_order(grid):
        for clue_index, clue in enumerate(clue_cell.clues):
            word = grid.word_cells(clue_cell.row, clue_cell.column, clue_index)
            placed_clue = _PlacedClue(
                row=clue_cell.row,
                column=clue_cell.column,
                text=clue.text,
                answer=clue.answer,
                letters=clue.letters,
                word=word,
                clue_index=clue_index,
            )
            placed_clues.append(placed_clue)
    return placed_clues


def _check_answer_lengths(placed_clues: list[_PlacedClue]) -> None:
    """Check that every answer has as many letters as its word has cells."""
    for clue in placed_clues:
        if len(clue.letters) != len(clue.word):
            raise GridImportError(
                f"clue {_format_clue(clue)} has answer {clue.answer} with "
                f"{len(clue.letters)} letters, but its word has "
                f"{len(clue.word)} cells"
            )


def _check_no_duplicate_words(placed_clues: list[_PlacedClue]) -> None:
    """Check that no two clues resolve to the same word."""
    for index, clue in enumerate(placed_clues):
        for earlier_clue in placed_clues[:index]:
            if earlier_clue.word == clue.word:
                raise GridImportError(
                    f"clues {_format_clue(earlier_clue)} and {_format_clue(clue)} "
                    "resolve to the same word"
                )


def _check_letters_in_a_word(grid: Grid, placed_clues: list[_PlacedClue]) -> None:
    """Check that every letter cell belongs to some word."""
    covered_positions: set[Position] = set()
    for clue in placed_clues:
        covered_positions.update(clue.word)
    for position in _letter_positions_in_order(grid):
        if position not in covered_positions:
            raise GridImportError(
                f"letter cell at {_format_position(position)} belongs to no word"
            )


def _is_letter(grid: Grid, row: int, column: int) -> bool:
    """Tell whether (row, column) is inside the grid and holds a letter."""
    if not (0 <= row < grid.height and 0 <= column < grid.width):
        return False
    return isinstance(grid.cell_at(row, column), LetterCell)


def _find_runs(grid: Grid, row_step: int, column_step: int) -> list[list[Position]]:
    """Find the runs of two or more letter cells in one direction.

    Runs come ordered by their first cell: row-major for a horizontal step
    (0, 1), column-major for a vertical step (1, 0).
    """
    scan_order = []
    if row_step == 0:
        for row in range(grid.height):
            for column in range(grid.width):
                scan_order.append((row, column))
    else:
        for column in range(grid.width):
            for row in range(grid.height):
                scan_order.append((row, column))

    runs = []
    for row, column in scan_order:
        if not _is_letter(grid, row, column):
            continue
        if _is_letter(grid, row - row_step, column - column_step):
            continue  # not the first cell of its run
        run = []
        current_row, current_column = row, column
        while _is_letter(grid, current_row, current_column):
            run.append((current_row, current_column))
            current_row += row_step
            current_column += column_step
        if len(run) >= 2:
            runs.append(run)
    return runs


def _check_runs_have_a_clue(grid: Grid, placed_clues: list[_PlacedClue]) -> None:
    """Check that every run of letter cells is exactly one word."""
    words = [clue.word for clue in placed_clues]
    horizontal_runs = _find_runs(grid, 0, 1)
    vertical_runs = _find_runs(grid, 1, 0)
    for run in horizontal_runs + vertical_runs:
        if run not in words:
            first = _format_position(run[0])
            last = _format_position(run[-1])
            raise GridImportError(
                f"run of letter cells from {first} to {last} has no clue"
            )


def _check_crossing_letters(grid: Grid, placed_clues: list[_PlacedClue]) -> None:
    """Check that crossing words agree on their shared letter."""
    for position in _letter_positions_in_order(grid):
        first_clue: _PlacedClue | None = None
        first_letter = ""
        for clue in placed_clues:
            if position not in clue.word:
                continue
            letter = clue.letters[clue.word.index(position)]
            if first_clue is None:
                first_clue = clue
                first_letter = letter
            elif letter != first_letter:
                raise GridImportError(
                    f"words {first_clue.answer} and {clue.answer} disagree at "
                    f"{_format_position(position)}: {first_letter} against {letter}"
                )


def _edges_of(grid: Grid, clue: _PlacedClue) -> list[tuple[Edge, bool]]:
    """Return the edges between a word's cells, each with whether it is a break.

    Only call this once the answer lengths have been checked.
    """
    hyphen_edges = grid.hyphen_edges(clue.row, clue.column, clue.clue_index)
    edges: list[tuple[Edge, bool]] = []
    for index in range(len(clue.word) - 1):
        edge = (clue.word[index], clue.word[index + 1])
        is_break = edge in hyphen_edges
        edges.append((edge, is_break))
    return edges


def _check_shared_hyphens(grid: Grid, placed_clues: list[_PlacedClue]) -> None:
    """Check that two words sharing an edge agree on its hyphen."""
    first_clue_of_edge: dict[Edge, _PlacedClue] = {}
    first_break_of_edge: dict[Edge, bool] = {}
    for clue in placed_clues:
        for edge, is_break in _edges_of(grid, clue):
            if edge not in first_clue_of_edge:
                first_clue_of_edge[edge] = clue
                first_break_of_edge[edge] = is_break
                continue
            if is_break == first_break_of_edge[edge]:
                continue
            first_clue = first_clue_of_edge[edge]
            before, after = edge
            raise GridImportError(
                f"words {first_clue.answer} and {clue.answer} disagree on the "
                f"hyphen of the edge {_format_position(before)}, "
                f"{_format_position(after)}"
            )


def check_words(grid: Grid) -> ImportReport:
    """Run the checks 3 to 8 on a grid whose arrows were checked.

    Args:
        grid: A grid for which `check_arrows` found nothing.

    Returns:
        The grid with its word, letter cell and clue cell counts.

    Raises:
        GridImportError: At the first problem found.
    """
    placed_clues = _place_clues(grid)
    _check_answer_lengths(placed_clues)
    _check_no_duplicate_words(placed_clues)
    _check_letters_in_a_word(grid, placed_clues)
    _check_runs_have_a_clue(grid, placed_clues)
    _check_crossing_letters(grid, placed_clues)
    _check_shared_hyphens(grid, placed_clues)

    return ImportReport(
        grid=grid,
        word_count=len(placed_clues),
        letter_cell_count=len(_letter_positions_in_order(grid)),
        clue_cell_count=len(_clue_cells_in_order(grid)),
    )


def import_grid(text: str) -> ImportReport:
    """Parse and check a grid given as JSON text.

    Args:
        text: The grid as JSON, in the format of spec 002.

    Returns:
        The grid with its word, letter cell and clue cell counts.

    Raises:
        GridImportError: at the first problem found (see "Order of checks").
    """
    try:
        grid = Grid.model_validate_json(text)
    except ValidationError as error:
        raise GridImportError(f"invalid grid: {error}") from error

    check_arrows(grid)
    return check_words(grid)
