"""Tests of spec 024, AC-10: reveals and the budget survive a reload.

`replay` of the logged entries, and a room saved in a `RoomStore` and loaded again
(spec 018). The shared setup is in `spec024_harness`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import CellTarget, ErrorCode, RevealBudget, RevealResult
from nock.room import LogEntry, RoomState, new_room, replay
from nock.store import RoomStore
from spec024_harness import (
    MIME,
    MIME_CELLS,
    NOW,
    ROOM_CODE,
    TAMIS,
    accepted_reveal,
    cell_state,
    grid_from_text,
    r1_room,
    r1_with_entries,
    refusal_code,
    reveal,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Helpers ----


def r1_and_the_two_reveals(grid: Grid) -> tuple[RoomState, list[LogEntry]]:
    """`R1`'s play then AC-1's reveals: the live state and the entries 1 to 12."""
    state, entries = r1_with_entries(grid)
    first = accepted_reveal(state, CellTarget(row=1, column=1), "p1")
    entries.extend(first.entries)
    second = accepted_reveal(first.state, MIME, "p2")
    entries.extend(second.entries)
    assert second.state.seq == 12
    return second.state, entries


def saved_and_loaded(path: Path, entries: list[LogEntry], grid: Grid) -> RoomState:
    """Save the room in a store file as the hub does, then load it in a new store."""
    store = RoomStore(path)
    try:
        store.create_room(new_room(ROOM_CODE, grid, NOW))
        store.append(ROOM_CODE, entries)
    finally:
        store.close()
    reopened = RoomStore(path)
    try:
        loaded = reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()
    assert loaded is not None
    return loaded


REVEALED_CELLS = [(1, 1), *MIME_CELLS]

# ---- AC-10 ----


def test_ac10_replaying_a_reveal_result_sets_the_budget_left(fx01_grid: Grid) -> None:
    state = r1_room(fx01_grid)
    event = RevealResult(
        seq=6,
        player_id="p1",
        target=CellTarget(row=1, column=1),
        reveal_budget=RevealBudget(letters=4, words=1),
    )

    replayed = replay(state, LogEntry(at=NOW, event=event))

    assert replayed.seq == 6
    assert replayed.reveal_budget == RevealBudget(letters=4, words=1)
    assert replayed.settings == state.settings
    assert replayed.cells == state.cells


def test_ac10_replaying_the_entries_gives_the_live_state(fx01_grid: Grid) -> None:
    live, entries = r1_and_the_two_reveals(fx01_grid)
    assert [entry.event.seq for entry in entries] == list(range(1, 13))

    replayed = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in entries:
        replayed = replay(replayed, entry)

    assert replayed.seq == live.seq == 12
    assert replayed.reveal_budget == live.reveal_budget
    assert replayed.reveal_budget == RevealBudget(letters=4, words=0)
    assert replayed.settings == live.settings
    assert replayed.cells == live.cells


def test_ac10_a_reloaded_room_keeps_the_budget_left(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    _, entries = r1_and_the_two_reveals(fx01_grid)

    loaded = saved_and_loaded(tmp_path / "rooms.sqlite3", entries, fx01_grid)

    assert loaded.seq == 12
    assert loaded.reveal_budget == RevealBudget(letters=4, words=0)
    assert loaded.settings.reveal_budget == RevealBudget(letters=5, words=1)


def test_ac10_a_reloaded_room_keeps_the_revealed_cells_without_author(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    _, entries = r1_and_the_two_reveals(fx01_grid)

    loaded = saved_and_loaded(tmp_path / "rooms.sqlite3", entries, fx01_grid)

    expected = {(1, 1): "A", (1, 2): "M", (2, 2): "I", (3, 2): "M", (4, 2): "E"}
    for row, column in REVEALED_CELLS:
        cell = cell_state(loaded, row, column)
        assert (cell.letter, cell.locked, cell.revealed, cell.author) == (
            expected[(row, column)],
            True,
            True,
            None,
        ), (row, column)


def test_ac10_a_reloaded_room_answers_a_word_reveal_with_budget_exhausted(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    _, entries = r1_and_the_two_reveals(fx01_grid)
    loaded = saved_and_loaded(tmp_path / "rooms.sqlite3", entries, fx01_grid)

    outcome = reveal(loaded, TAMIS, "p1", NOW + 10)

    assert refusal_code(outcome) is ErrorCode.BUDGET_EXHAUSTED
    assert outcome.entries == ()
