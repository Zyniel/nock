"""Tests of server AC-20, AC-21 and AC-22: the engine time budgets (rule 20).

Rule 20's measure: the room's rules alone, with no socket and no store, on FX-02,
as the median of 5 runs after one warm-up, timed with `time.perf_counter`.
`nock.room.handle_message` runs the edit and the check, and
`nock.catch_up.build_catch_up` the catch-up. Each room state is built outside the
timed part; only the operation itself is timed. This file is in
`SERIAL_TEST_FILES` (`scripts/gate_browsers.py`): it runs on its own, after the
parallel pass.

Each test also checks the outcome its criterion names, so that a fast wrong
answer cannot pass.

Choices where the spec leaves room:

- AC-20: the one empty cell is the last letter cell in row-major order. The room
  is built by one player, whose edits come 0.1 s apart, under the default limit
  of 20 a second (`RoomConfig()`).
- AC-20, edge case: the budget holds for a grid taken from the model's JSON, for
  the grid of a room loaded from the store's JSON (`RoomState` read from its own
  JSON) and for a grid returned by `import_grid`, the way the catalogue builds
  its grids.
- AC-21: the whole grid is full of wrong letters (each is a letter other than the
  solution letter), so the room holds a `grid_full_wrong` before the check.
- AC-22: the 100 letters are the first 100 cells of the words of FX-02 in clue
  order (word after word, a cell once), typed by one player in that order. The
  words completed are worked out in this file from `Grid.word_cells`.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Callable, Sequence
from typing import NamedTuple

import pytest

from nock.catch_up import CatchUp, WordCompleted, build_catch_up
from nock.grid import ClueCell, Grid, LetterCell, Position
from nock.grid_import import import_grid
from nock.protocol import (
    CellRef,
    Check,
    CheckResult,
    ClueRef,
    EditLetter,
    GridSolved,
    GridTarget,
    Join,
    LetterChanged,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomState,
    handle_message,
    join_room,
    new_room,
)

# ---- Values of the spec --------------------------------------------------------------

RUNS = 5
EDIT_BUDGET_MS = 5.0
CHECK_BUDGET_MS = 10.0
CATCH_UP_BUDGET_MS = 50.0
FX02_LETTER_CELLS = 125
ABSENCE_LETTERS = 100

# ---- Values of the test harness ------------------------------------------------------

ROOM_CODE = "ABC123"
PLAYER_ID = "p1"
RESUME_TOKEN = "first-token-number-0001"
START_TIME = 2_000_000.0
EDIT_GAP_SECONDS = 0.1
GRID_SOURCES = ("model", "store", "catalogue")


# ---- The grid ------------------------------------------------------------------------


def grid_from_source(source: str, fx02_text: str) -> Grid:
    """FX-02 built the way a room gets its grid: model, store or catalogue."""
    if source == "model":
        return Grid.model_validate_json(fx02_text)
    if source == "store":
        model_grid = Grid.model_validate_json(fx02_text)
        room = new_room(ROOM_CODE, model_grid, START_TIME)
        stored_room = RoomState.model_validate_json(room.model_dump_json())
        return stored_room.grid
    if source == "catalogue":
        return import_grid(fx02_text).grid
    raise ValueError(f"unknown grid source {source!r}")


def clue_cells_in_order(grid: Grid) -> list[ClueCell]:
    """The clue cells of a grid, by row then column."""
    clue_cells: list[ClueCell] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            clue_cells.append(cell)
    clue_cells.sort(key=lambda clue_cell: (clue_cell.row, clue_cell.column))
    return clue_cells


def solution_of(grid: Grid) -> dict[Position, str]:
    """The solution letter of each letter cell, from the answers of the words.

    A cell held by several words takes the letter of the first in clue order. In
    FX-02 the crossing words agree, so the choice changes nothing.
    """
    solution: dict[Position, str] = {}
    for clue_cell in clue_cells_in_order(grid):
        for clue_index, clue in enumerate(clue_cell.clues):
            cells = grid.word_cells(clue_cell.row, clue_cell.column, clue_index)
            for position, letter in zip(cells, clue.letters, strict=True):
                solution.setdefault(position, letter)
    return solution


def letter_positions(grid: Grid) -> list[Position]:
    """The positions of the letter cells of a grid, in row-major order."""
    positions: list[Position] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


def words_in_clue_order(grid: Grid) -> list[tuple[ClueRef, list[Position]]]:
    """Each clue of the grid with the cells of its word, in clue order."""
    words: list[tuple[ClueRef, list[Position]]] = []
    for clue_cell in clue_cells_in_order(grid):
        for clue_index in range(len(clue_cell.clues)):
            cells = grid.word_cells(clue_cell.row, clue_cell.column, clue_index)
            clue = ClueRef(
                row=clue_cell.row, column=clue_cell.column, clue_index=clue_index
            )
            words.append((clue, cells))
    return words


def wrong_letter(solution_letter: str) -> str:
    """A letter other than the solution letter."""
    if solution_letter == "A":
        return "B"
    return "A"


# ---- The room ------------------------------------------------------------------------


class TypedRoom(NamedTuple):
    """A room, every entry logged since it was built and the time of its last step."""

    state: RoomState
    entries: tuple[LogEntry, ...]
    now: float


def room_with_one_player(grid: Grid) -> TypedRoom:
    """A room with its one player, `p1`, and no letter (seq 1)."""
    room = new_room(ROOM_CODE, grid, START_TIME)
    join = Join(nickname="Ana", resume_token=None)
    outcome = join_room(room, join, START_TIME, PLAYER_ID, RESUME_TOKEN)
    assert outcome.state.seq == 1
    return TypedRoom(state=outcome.state, entries=(), now=START_TIME)


def type_letters(room: TypedRoom, letters: Sequence[tuple[Position, str]]) -> TypedRoom:
    """Have `p1` type letters one after the other, each 0.1 s after the last.

    Every edit has to be accepted with no refusal.
    """
    state = room.state
    entries = list(room.entries)
    now = room.now
    for (row, column), letter in letters:
        now += EDIT_GAP_SECONDS
        edit = EditLetter(row=row, column=column, letter=letter)
        outcome = handle_message(state, PLAYER_ID, edit, now)
        assert outcome.reply == ()
        state = outcome.state
        entries.extend(outcome.entries)
    return TypedRoom(state=state, entries=tuple(entries), now=now)


def events_of(outcome: Outcome) -> list[object]:
    """The events of the entries a step logged."""
    return [entry.event for entry in outcome.entries]


# ---- The measure ---------------------------------------------------------------------


def median_milliseconds[T](operation: Callable[[], T]) -> tuple[T, float]:
    """Run an operation once to warm up, then 5 times; return a result and the median.

    Returns:
        The result of the last timed run and the median of the 5 durations, in
        milliseconds, each measured with `time.perf_counter`.
    """
    result = operation()
    durations_ms: list[float] = []
    for _ in range(RUNS):
        started = time.perf_counter()
        result = operation()
        elapsed = time.perf_counter() - started
        durations_ms.append(elapsed * 1000.0)
    return result, statistics.median(durations_ms)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


# ---- AC-20: the edit that solves the grid --------------------------------------------


@pytest.mark.parametrize("source", GRID_SOURCES)
def test_ac20_the_edit_that_solves_the_grid_takes_under_5_ms(
    source: str, fx02_text: str
) -> None:
    grid = grid_from_source(source, fx02_text)
    solution = solution_of(grid)
    positions = letter_positions(grid)
    assert len(positions) == FX02_LETTER_CELLS
    last_position = positions[-1]
    room = room_with_one_player(grid)
    all_but_one: list[tuple[Position, str]] = []
    for position in positions[:-1]:
        all_but_one.append((position, solution[position]))
    almost_solved = type_letters(room, all_but_one)
    assert almost_solved.state.solved is False
    last_row, last_column = last_position
    last_edit = EditLetter(
        row=last_row, column=last_column, letter=solution[last_position]
    )
    now = almost_solved.now + EDIT_GAP_SECONDS

    outcome, median_ms = median_milliseconds(
        lambda: handle_message(almost_solved.state, PLAYER_ID, last_edit, now)
    )

    assert outcome.reply == ()
    assert outcome.state.solved is True
    events = events_of(outcome)
    letter_changed = events[0]
    assert isinstance(letter_changed, LetterChanged)
    assert (letter_changed.row, letter_changed.column) == last_position
    assert letter_changed.letter == solution[last_position]
    assert isinstance(events[-1], GridSolved)
    assert median_ms < EDIT_BUDGET_MS


# ---- AC-21: the check of the whole grid ----------------------------------------------


def test_ac21_a_check_of_a_grid_all_wrong_takes_under_10_ms(
    fx02_grid: Grid,
) -> None:
    solution = solution_of(fx02_grid)
    positions = letter_positions(fx02_grid)
    all_wrong: list[tuple[Position, str]] = []
    for position in positions:
        all_wrong.append((position, wrong_letter(solution[position])))
    room = type_letters(room_with_one_player(fx02_grid), all_wrong)
    assert room.state.solved is False
    check = Check(target=GridTarget())
    now = room.now + EDIT_GAP_SECONDS

    outcome, median_ms = median_milliseconds(
        lambda: handle_message(room.state, PLAYER_ID, check, now)
    )

    assert outcome.reply == ()
    events = events_of(outcome)
    assert len(events) == 1
    result = events[0]
    assert isinstance(result, CheckResult)
    expected_wrong = tuple(CellRef(row=row, column=column) for row, column in positions)
    assert result.correct == ()
    assert len(result.wrong) == FX02_LETTER_CELLS
    assert sorted(result.wrong, key=lambda ref: (ref.row, ref.column)) == list(
        expected_wrong
    )
    assert median_ms < CHECK_BUDGET_MS


# ---- AC-22: the catch-up of 100 letters ----------------------------------------------


def absence_letters(grid: Grid) -> list[tuple[Position, str]]:
    """The first 100 cells of the words of the grid in clue order, with their letter."""
    solution = solution_of(grid)
    chosen: list[tuple[Position, str]] = []
    seen: set[Position] = set()
    for _, cells in words_in_clue_order(grid):
        for position in cells:
            if position in seen or len(chosen) == ABSENCE_LETTERS:
                continue
            seen.add(position)
            chosen.append((position, solution[position]))
    assert len(chosen) == ABSENCE_LETTERS
    return chosen


def completed_words(
    grid: Grid, letters: Sequence[tuple[Position, str]], first_seq: int
) -> tuple[WordCompleted, ...]:
    """The words that the letters complete, worked out letter by letter.

    Args:
        grid: The grid.
        letters: The letters typed, each into a cell that was empty, in order.
        first_seq: The seq of the first letter's `letter_changed`.

    Returns:
        One `WordCompleted` for each word whose last empty cell a letter filled,
        in seq order, words completed by one letter in clue order.
    """
    words = words_in_clue_order(grid)
    filled: set[Position] = set()
    completed: list[WordCompleted] = []
    for offset, (position, _) in enumerate(letters):
        filled.add(position)
        for clue, cells in words:
            if position not in cells:
                continue
            if all(cell in filled for cell in cells):
                line = WordCompleted(
                    seq=first_seq + offset, player_id=PLAYER_ID, clue=clue
                )
                completed.append(line)
    return tuple(completed)


def test_ac22_the_catch_up_of_100_letters_takes_under_50_ms(
    fx02_grid: Grid,
) -> None:
    letters = absence_letters(fx02_grid)
    before = room_with_one_player(fx02_grid)
    after_typing = type_letters(before, letters)
    assert after_typing.state.seq == before.state.seq + ABSENCE_LETTERS
    assert len(after_typing.entries) == ABSENCE_LETTERS
    expected_lines = completed_words(fx02_grid, letters, before.state.seq + 1)
    assert len(expected_lines) > 0
    changed_positions = sorted(position for position, _ in letters)
    expected_cells = tuple(
        CellRef(row=row, column=column) for row, column in changed_positions
    )

    catch_up, median_ms = median_milliseconds(
        lambda: build_catch_up(
            before.state.seq,
            after_typing.state.seq,
            before.state,
            after_typing.entries,
        )
    )

    assert isinstance(catch_up, CatchUp)
    assert catch_up.after_seq == before.state.seq
    assert catch_up.until_seq == after_typing.state.seq
    assert catch_up.cells == expected_cells
    assert catch_up.lines == expected_lines
    assert median_ms < CATCH_UP_BUDGET_MS
