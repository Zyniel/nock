"""Tests of spec 024, AC-10: reveals and the budget survive a reload.

`replay` of the logged entries, and a room saved in a `RoomStore` and loaded again
(spec 018). Since the lead's refinement of 2026-10-15 (decision 13), this covers
`RoomState.reveals_used` too: rebuilt by `replay`, carried by a snapshot, and 0 and
0 when a stored snapshot has no `reveals_used` key. The shared setup is in
`spec024_harness`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ErrorCode,
    HelpMode,
    RevealBudget,
    RevealResult,
    RoomSettings,
    SettingsChanged,
    WordTarget,
)
from nock.room import LogEntry, RoomState, new_room, replay
from nock.store import RoomStore
from spec024_harness import (
    MIME,
    MIME_CELLS,
    NOW,
    ROOM_CODE,
    TAMIS,
    accepted_reveal,
    allowance_cut,
    cell_state,
    grid_from_text,
    host_change_outcome,
    r1_room,
    r1_with_entries,
    refusal_code,
    reveal,
    single_settings_changed,
    two_player_room,
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


def load_from(path: Path) -> RoomState:
    """Load room ROOM_CODE from the store file at `path`, in a new store."""
    reopened = RoomStore(path)
    try:
        loaded = reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()
    assert loaded is not None
    return loaded


def saved_and_loaded(
    path: Path,
    entries: list[LogEntry],
    grid: Grid,
    last_snapshot: RoomState | None = None,
) -> RoomState:
    """Save the room in a store file as the hub does, then load it in a new store.

    Args:
        path: The store file.
        entries: Every entry of the room's log, from seq 1.
        grid: The room's grid.
        last_snapshot: A state saved with `save_snapshot` after the entries, or
            None for no snapshot but the room's first one.

    Returns:
        The state `load_room` gives.
    """
    store = RoomStore(path)
    try:
        store.create_room(new_room(ROOM_CODE, grid, NOW))
        store.append(ROOM_CODE, entries)
        if last_snapshot is not None:
            store.save_snapshot(last_snapshot)
    finally:
        store.close()
    return load_from(path)


REVEALED_CELLS = [(1, 1), *MIME_CELLS]
LOAD_WAYS = ["log-only", "snapshot-after-the-cut"]

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
    assert replayed.reveals_used == live.reveals_used
    assert replayed.reveals_used == RevealBudget(letters=1, words=1)
    assert replayed.settings == live.settings
    assert replayed.cells == live.cells


@pytest.mark.parametrize(
    ("target", "used"),
    [
        (CellTarget(row=1, column=1), RevealBudget(letters=1, words=0)),
        (MIME, RevealBudget(letters=0, words=1)),
    ],
    ids=["letter", "word"],
)
def test_ac10_replaying_a_reveal_result_adds_one_of_its_kind_to_reveals_used(
    fx01_grid: Grid, target: CellTarget | WordTarget, used: RevealBudget
) -> None:
    state = r1_room(fx01_grid)
    assert state.reveals_used == RevealBudget(letters=0, words=0)
    event = RevealResult(
        seq=6,
        player_id="p1",
        target=target,
        reveal_budget=RevealBudget(letters=4, words=1),
    )

    replayed = replay(state, LogEntry(at=NOW, event=event))

    assert replayed.reveals_used == used


def test_ac10_replaying_settings_changed_leaves_reveals_used_as_it_was(
    fx01_grid: Grid,
) -> None:
    live, entries = allowance_cut(fx01_grid)
    before_the_cut = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in entries[:-1]:
        before_the_cut = replay(before_the_cut, entry)
    assert before_the_cut.reveals_used == RevealBudget(letters=3, words=1)
    cut = entries[-1]
    assert isinstance(cut.event, SettingsChanged)

    replayed = replay(before_the_cut, cut)

    assert replayed.reveals_used == RevealBudget(letters=3, words=1)
    assert replayed.reveal_budget == RevealBudget(letters=0, words=0)
    assert replayed.settings == live.settings


def test_ac10_replaying_the_allowance_example_gives_the_live_budget_and_used(
    fx01_grid: Grid,
) -> None:
    live, entries = allowance_cut(fx01_grid)
    assert [entry.event.seq for entry in entries] == list(range(1, 15))

    replayed = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in entries:
        replayed = replay(replayed, entry)

    assert replayed.reveal_budget == live.reveal_budget
    assert replayed.reveal_budget == RevealBudget(letters=0, words=0)
    assert replayed.reveals_used == live.reveals_used
    assert replayed.reveals_used == RevealBudget(letters=3, words=1)


def test_ac10_a_reloaded_room_keeps_the_budget_left(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    _, entries = r1_and_the_two_reveals(fx01_grid)

    loaded = saved_and_loaded(tmp_path / "rooms.sqlite3", entries, fx01_grid)

    assert loaded.seq == 12
    assert loaded.reveal_budget == RevealBudget(letters=4, words=0)
    assert loaded.settings.reveal_budget == RevealBudget(letters=5, words=1)


def test_ac10_a_reloaded_room_keeps_reveals_used(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    _, entries = r1_and_the_two_reveals(fx01_grid)

    loaded = saved_and_loaded(tmp_path / "rooms.sqlite3", entries, fx01_grid)

    assert loaded.reveals_used == RevealBudget(letters=1, words=1)


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


# ---- AC-10: AC-2's allowance example loaded from a RoomStore (decision 13) ----


def loaded_after_the_cut(grid: Grid, path: Path, way: str) -> RoomState:
    """AC-2's allowance example up to its first `ChangeSettings`, stored and loaded.

    Args:
        grid: FX-01.
        path: The store file.
        way: `log-only`, (a) of AC-10: the room's first snapshot and every entry,
            so that `load_room` replays the whole log; or
            `snapshot-after-the-cut`, (b): the same plus `save_snapshot` of the
            live state after the allowance change.

    Returns:
        The state `load_room` gives.
    """
    live, entries = allowance_cut(grid)
    if way == "log-only":
        return saved_and_loaded(path, entries, grid)
    return saved_and_loaded(path, entries, grid, last_snapshot=live)


@pytest.mark.parametrize("way", LOAD_WAYS)
def test_ac10_a_room_loaded_after_the_cut_keeps_its_budget_and_reveals_used(
    fx01_grid: Grid, tmp_path: Path, way: str
) -> None:
    loaded = loaded_after_the_cut(fx01_grid, tmp_path / "rooms.sqlite3", way)

    assert loaded.seq == 14
    assert loaded.reveal_budget == RevealBudget(letters=0, words=0)
    assert loaded.reveals_used == RevealBudget(letters=3, words=1)


@pytest.mark.parametrize("way", LOAD_WAYS)
def test_ac10_a_room_loaded_after_the_cut_gives_2_and_0_on_an_allowance_of_5_and_1(
    fx01_grid: Grid, tmp_path: Path, way: str
) -> None:
    loaded = loaded_after_the_cut(fx01_grid, tmp_path / "rooms.sqlite3", way)

    outcome = host_change_outcome(loaded, HelpMode.FREE, 5, 1, NOW + 10)

    allowance = RevealBudget(letters=5, words=1)
    assert single_settings_changed(outcome) == SettingsChanged(
        seq=15,
        player_id="p1",
        settings=RoomSettings(
            help_mode=HelpMode.FREE, reveal_budget=allowance, locked=False
        ),
        reveal_budget=RevealBudget(letters=2, words=0),
    )


# ---- AC-10: a stored snapshot without reveals_used ----


def stored_without_reveals_used(
    path: Path, state: RoomState, monkeypatch: pytest.MonkeyPatch
) -> list[str]:
    """Store `state` with `create_room` while its JSON leaves `reveals_used` out.

    `RoomState.model_dump_json` is patched only while the room is created, as
    AC-10 says (spec 018 writes a stored `RoomState` with `model_dump_json()`).

    Args:
        path: The store file.
        state: The room's first snapshot.
        monkeypatch: pytest's fixture, which undoes the patch.

    Returns:
        One `reveals_used` per JSON text the patch took that key out of, so that
        the test can check the stored snapshot really lacked it.
    """
    original_dump = RoomState.model_dump_json
    removed_keys: list[str] = []

    def dump_without_reveals_used(self: RoomState) -> str:
        data = json.loads(original_dump(self))
        assert isinstance(data, dict)
        if "reveals_used" in data:
            del data["reveals_used"]
            removed_keys.append("reveals_used")
        return json.dumps(data)

    with monkeypatch.context() as patch:
        patch.setattr(RoomState, "model_dump_json", dump_without_reveals_used)
        store = RoomStore(path)
        try:
            store.create_room(state)
        finally:
            store.close()
    return removed_keys


def test_ac10_a_stored_snapshot_without_reveals_used_loads_with_0_and_0(
    fx01_grid: Grid, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rooms.sqlite3"
    state = two_player_room(fx01_grid)
    removed_keys = stored_without_reveals_used(path, state, monkeypatch)

    loaded = load_from(path)

    assert removed_keys == ["reveals_used"]
    assert loaded.seq == 2
    assert loaded.reveal_budget == RevealBudget(letters=5, words=1)
    assert loaded.settings.reveal_budget == RevealBudget(letters=5, words=1)
    assert loaded.reveals_used == RevealBudget(letters=0, words=0)


def test_ac10_from_a_snapshot_without_reveals_used_3_and_1_leave_3_and_1(
    fx01_grid: Grid, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "rooms.sqlite3"
    removed_keys = stored_without_reveals_used(
        path, two_player_room(fx01_grid), monkeypatch
    )
    loaded = load_from(path)

    outcome = host_change_outcome(loaded, HelpMode.FREE, 3, 1, NOW + 10)

    assert removed_keys == ["reveals_used"]
    allowance = RevealBudget(letters=3, words=1)
    assert single_settings_changed(outcome) == SettingsChanged(
        seq=3,
        player_id="p1",
        settings=RoomSettings(
            help_mode=HelpMode.FREE, reveal_budget=allowance, locked=False
        ),
        reveal_budget=RevealBudget(letters=3, words=1),
    )
