"""Tests of spec 018: durable room state.

AC-1 is checked in four layers: `RoomStore` on its own (log, snapshots, errors),
`replay` and `after_restart` on their own, a 250-step room driven with the rules
and read back with `load_room`, and the real WebSocket with a simulated restart
(a second store, registry and app on the same SQLite file). AC-2 uses the real
WebSocket with writer threads. AC-3 checks undo on `handle_message`, on the real
WebSocket and on the page with a mocked socket.

The table layout is the implementer's choice, so the snapshots the hub saves are
observed through `load_room` only: a log row is damaged on purpose, and
`load_room` fails exactly when it has to replay that row, that is when no
snapshot covers it.

Not tested here, by the spec's own decision: a real process kill and a power cut
(`synchronous=FULL` is relied on). Not tested: the `grid_solved` refusal of an
undo (spec 026), the refusal of a removed player's join (spec 014), the README.
"""

from __future__ import annotations

import contextlib
import json
import random
import re
import sqlite3
import string
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from pydantic import ValidationError
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellView,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridSolved,
    GridView,
    HelpMode,
    HostChanged,
    Join,
    LeaveReason,
    LetterCellView,
    LetterChanged,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Selection,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    Undo,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    LogEntry,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    UndoEntry,
    after_restart,
    grid_state,
    handle_message,
    join_room,
    new_room,
    player_views,
    replay,
)
from nock.server import create_app
from nock.store import RoomStore

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
OTHER_CODE = "GHJKLM"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
LATER = 3_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
PUBLISHED_NUMBER = 2

WAIT_SECONDS = 10.0
OVERALL_SECONDS = 180.0
SETTLE_SECONDS = 0.5
POLL_SECONDS = 0.02
SHORT_PAUSE_SECONDS = 0.3
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
UNDO_MESSAGE_SECONDS = 3
DRIVE_EVENTS = 250
DRIVE_CYCLES = 80
EDITS_PER_WRITER = 200

Edit = EditLetter | Erase
ClientSend = Join | EditLetter | Erase | Undo
CellValue = tuple[str | None, bool, str | None]  # letter, pencil, author
ChangeList = list[tuple[int, int, dict[str, object]]]
PlayerSummary = tuple[
    str, str, str, int, bool, bool, PlayerState, int, UndoEntry | None
]

SERVER_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
SNAPSHOT_CONFIG = RoomConfig(
    max_edits_per_second=1000, silence_timeout_seconds=600, snapshot_every=100
)

# ---- Fixtures ----


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


@pytest.fixture
def file_store(tmp_path: Path) -> Iterator[RoomStore]:
    store = RoomStore(tmp_path / "nock.sqlite3")
    yield store
    store.close()


@pytest.fixture
def memory_store() -> Iterator[RoomStore]:
    store = RoomStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry (default in-memory store) whose throttle never refuses."""
    room_registry = RoomRegistry(config=SERVER_CONFIG)
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving the room `room_code`."""
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    published = CatalogueEntry(
        number=PUBLISHED_NUMBER,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        grid=fx01_grid,
    )
    return Catalogue(entries=(published,))


# ---- Helpers on room states ----


def letter_cells(grid: Grid) -> list[tuple[int, int]]:
    """The letter cells of `grid` in row-major order."""
    positions: list[tuple[int, int]] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


def token_of(index: int) -> str:
    return f"resume-token-number-{index:04d}"


def two_player_room(grid: Grid, code: str = ROOM_CODE) -> RoomState:
    """A room with players `p1` and `p2` (seq 2), every cell empty."""
    state = new_room(code, grid, START_TIME)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    assert second.state.seq == 2
    return second.state


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def other_cells(state: RoomState, row: int, column: int) -> list[CellState]:
    return [cell for cell in state.cells if (cell.row, cell.column) != (row, column)]


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


def letter_changed(
    seq: int,
    row: int,
    column: int,
    letter: str | None,
    player_id: str,
    pencil: bool = False,
) -> LetterChanged:
    return LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player_id,
    )


def log_entry(
    seq: int,
    row: int = 1,
    column: int = 0,
    letter: str | None = "A",
    player_id: str = "p1",
) -> LogEntry:
    return LogEntry(at=NOW, event=letter_changed(seq, row, column, letter, player_id))


def grid_values(view: GridView) -> dict[tuple[int, int], CellValue]:
    """The (letter, pencil, author) of each letter cell of a grid view."""
    values: dict[tuple[int, int], CellValue] = {}
    for cell in view.cells:
        if isinstance(cell, LetterCellView):
            values[(cell.row, cell.column)] = (cell.letter, cell.pencil, cell.author)
    return values


def summarize_players(state: RoomState) -> list[PlayerSummary]:
    """The fields of each player that the log carries."""
    summaries: list[PlayerSummary] = []
    for player in state.players:
        summaries.append(
            (
                player.player_id,
                player.resume_token,
                player.nickname,
                player.colour,
                player.is_host,
                player.muted,
                player.state,
                player.joined_seq,
                player.last_edit,
            )
        )
    return summaries


def resume_tokens(state: RoomState) -> list[str]:
    return [player.resume_token for player in state.players]


def assert_same_room(loaded: RoomState | None, live: RoomState) -> None:
    """Check every field the log carries is the same in `loaded` and `live`."""
    assert loaded is not None
    assert loaded.code == live.code
    assert loaded.seq == live.seq
    assert grid_state(loaded) == grid_state(live)
    assert player_views(loaded) == player_views(live)
    assert resume_tokens(loaded) == resume_tokens(live)
    assert loaded.cells == live.cells
    assert summarize_players(loaded) == summarize_players(live)
    assert loaded.settings == live.settings
    assert loaded.reveal_budget == live.reveal_budget
    assert loaded.removed_tokens == live.removed_tokens
    assert loaded.grid == live.grid


# ---- A 250-step room driven with the rules ----


def commit(store: RoomStore, code: str, outcome: Outcome) -> RoomState:
    """Append the entries of a step, as the hub does, and return its state."""
    if len(outcome.entries) > 0:
        store.append(code, outcome.entries)
    return outcome.state


def drive_room(
    store: RoomStore, grid: Grid, snapshot_at: int | None = None
) -> RoomState:
    """Create FX-01 room `ROOM_CODE` in `store` and play it up to DRIVE_EVENTS.

    Three players join, then each cycle (player after player) is: a letter in a
    cell, another letter over it, an undo (back to the first letter), an erase
    of a second cell, an undo (the erased letter is back). Each step's entries
    are appended. Returns the live state. When the rules cannot reach the
    DRIVE_EVENTS events, the returned state has a smaller seq.
    """
    state = new_room(ROOM_CODE, grid, START_TIME)
    store.create_room(state)
    now = START_TIME
    for index, nickname in enumerate(["Ana", "Bob", "Cleo"]):
        now += 1
        outcome = join_room(
            state,
            Join(nickname=nickname, resume_token=None),
            now,
            f"p{index + 1}",
            token_of(index),
        )
        state = commit(store, ROOM_CODE, outcome)

    cells = letter_cells(grid)
    letters = string.ascii_uppercase
    for cycle in range(DRIVE_CYCLES):
        player_id = f"p{cycle % 3 + 1}"
        first_row, first_column = cells[(cycle * 7) % len(cells)]
        second_row, second_column = cells[(cycle * 7 + 3) % len(cells)]
        messages: list[EditLetter | Erase | Undo] = [
            EditLetter(row=first_row, column=first_column, letter=letters[cycle % 26]),
            EditLetter(
                row=first_row, column=first_column, letter=letters[(cycle + 9) % 26]
            ),
            Undo(),
            Erase(row=second_row, column=second_column),
            Undo(),
        ]
        for message in messages:
            if state.seq >= DRIVE_EVENTS:
                return state
            now += 1
            outcome = handle_message(state, player_id, message, now, SERVER_CONFIG)
            state = commit(store, ROOM_CODE, outcome)
            if snapshot_at is not None and state.seq == snapshot_at:
                store.save_snapshot(state)
    return state


# ---- Helpers on the SQLite file ----


def corrupt_log_entry(path: Path, seq: int) -> None:
    """Replace the stored `letter_changed` log row of `seq` by an invalid JSON.

    The layout is the implementer's choice: every text column of every table is
    tried. Exactly one value must match: the JSON of that log entry.
    """
    connection = sqlite3.connect(path, timeout=WAIT_SECONDS)
    changed = 0
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for (table,) in tables:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            for column_info in columns:
                column = column_info[1]
                cursor = connection.execute(
                    f'UPDATE "{table}" SET "{column}" = ? '
                    f"WHERE typeof(\"{column}\") = 'text' "
                    f'AND "{column}" LIKE ? AND "{column}" LIKE ?',
                    ("{}", '%"type":"letter_changed"%', f'%"seq":{seq},%'),
                )
                changed += cursor.rowcount
        connection.commit()
    finally:
        connection.close()
    assert changed == 1, f"expected to damage one log row, damaged {changed}"


def load_from_file(path: Path, code: str) -> RoomState | None:
    """`load_room` of a fresh store on the file, closed afterwards."""
    store = RoomStore(path)
    try:
        return store.load_room(code)
    finally:
        store.close()


def wait_until_loadable(path: Path, code: str) -> RoomState:
    """Poll `load_room` until it stops failing on the damaged row."""
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            loaded = load_from_file(path, code)
        except ValidationError:
            if time.monotonic() > deadline:
                pytest.fail("the damaged row is still replayed: no snapshot covers it")
            time.sleep(POLL_SECONDS)
            continue
        assert loaded is not None
        return loaded


def wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")
        time.sleep(POLL_SECONDS)


# ---- AC-1: RoomStore ----


def test_ac1_store_a_created_room_is_known_and_loads_as_created(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    state = two_player_room(fx01_grid)

    memory_store.create_room(state)

    assert memory_store.has_room(ROOM_CODE) is True
    assert memory_store.load_room(ROOM_CODE) == state
    assert memory_store.read_log(ROOM_CODE) == []


def test_ac1_store_an_unknown_code_gives_false_none_and_an_empty_log(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    assert memory_store.has_room(OTHER_CODE) is False
    assert memory_store.load_room(OTHER_CODE) is None
    assert memory_store.read_log(OTHER_CODE) == []
    assert memory_store.read_log(OTHER_CODE, after_seq=3) == []


def test_ac1_store_creating_a_room_twice_raises_and_keeps_the_first(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    first = two_player_room(fx01_grid)
    memory_store.create_room(first)

    with pytest.raises(ValueError, match=r".+"):
        memory_store.create_room(new_room(ROOM_CODE, fx01_grid, START_TIME))

    assert memory_store.load_room(ROOM_CODE) == first


def test_ac1_store_appended_entries_read_back_equal_and_in_order(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    joined = LogEntry(
        at=NOW,
        event=PlayerJoined(
            seq=3,
            player=PlayerView(
                player_id="p3",
                nickname="Cleo",
                colour=2,
                state=PlayerState.ACTIVE,
                is_host=False,
                muted=False,
                selection=None,
            ),
        ),
        resume_token=token_of(3),
    )
    undone = LogEntry(
        at=NOW + 2.5, event=letter_changed(5, 1, 0, None, "p1"), undo=True
    )
    typed = log_entry(4)

    memory_store.append(ROOM_CODE, [joined])
    memory_store.append(ROOM_CODE, [typed, undone])

    assert memory_store.read_log(ROOM_CODE) == [joined, typed, undone]
    assert memory_store.read_log(ROOM_CODE)[0].resume_token == token_of(3)
    assert memory_store.read_log(ROOM_CODE)[2].undo is True


def test_ac1_store_read_log_after_seq_returns_only_the_later_entries(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    entries = [log_entry(seq) for seq in range(3, 9)]
    memory_store.append(ROOM_CODE, entries)

    assert memory_store.read_log(ROOM_CODE, after_seq=5) == entries[3:]
    assert memory_store.read_log(ROOM_CODE, after_seq=8) == []
    assert memory_store.read_log(ROOM_CODE, after_seq=0) == entries


@pytest.mark.parametrize("first_seq", [1, 2, 4, 5])
def test_ac1_store_the_first_entry_must_follow_the_snapshot_seq(
    memory_store: RoomStore, fx01_grid: Grid, first_seq: int
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))  # snapshot at seq 2

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(first_seq)])

    assert memory_store.read_log(ROOM_CODE) == []


def test_ac1_store_a_gap_in_the_seqs_raises_and_writes_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    memory_store.append(ROOM_CODE, [log_entry(3)])

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(5)])

    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_gap_inside_the_batch_writes_none_of_it(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(3), log_entry(4), log_entry(6)])

    assert memory_store.read_log(ROOM_CODE) == []
    memory_store.append(ROOM_CODE, [log_entry(3)])
    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_repeated_seq_raises_and_writes_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    memory_store.append(ROOM_CODE, [log_entry(3), log_entry(4)])

    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(ROOM_CODE, [log_entry(4)])

    assert [entry.event.seq for entry in memory_store.read_log(ROOM_CODE)] == [3, 4]


def test_ac1_store_entries_for_an_unknown_room_raise(
    memory_store: RoomStore,
) -> None:
    with pytest.raises(ValueError, match=r".+"):
        memory_store.append(OTHER_CODE, [log_entry(1)])

    assert memory_store.read_log(OTHER_CODE) == []


def test_ac1_store_an_empty_append_writes_nothing_and_raises_nothing(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))

    memory_store.append(ROOM_CODE, [])
    memory_store.append(ROOM_CODE, ())

    assert memory_store.read_log(ROOM_CODE) == []
    memory_store.append(ROOM_CODE, [log_entry(3)])
    assert memory_store.read_log(ROOM_CODE) == [log_entry(3)]


def test_ac1_store_a_snapshot_of_an_unknown_room_raises(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    with pytest.raises(ValueError, match=r".+"):
        memory_store.save_snapshot(two_player_room(fx01_grid))

    assert memory_store.has_room(ROOM_CODE) is False


def test_ac1_store_the_snapshot_with_the_highest_seq_is_the_one_loaded(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(new_room(ROOM_CODE, fx01_grid, START_TIME))
    two_players = two_player_room(fx01_grid)

    memory_store.save_snapshot(two_players)

    assert memory_store.load_room(ROOM_CODE) == two_players


def test_ac1_store_a_snapshot_at_the_same_seq_replaces_the_old_one(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    original = two_player_room(fx01_grid)
    memory_store.create_room(original)
    replaced = original.model_copy(
        update={"reveal_budget": RevealBudget(letters=1, words=0)}
    )

    memory_store.save_snapshot(replaced)

    assert memory_store.load_room(ROOM_CODE) == replaced


def test_ac1_store_load_room_replays_only_the_entries_after_the_snapshot(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    base = two_player_room(fx01_grid)
    memory_store.create_room(base)
    first = handle_message(base, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    memory_store.append(ROOM_CODE, first.entries)
    memory_store.save_snapshot(first.state)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )
    memory_store.append(ROOM_CODE, second.entries)

    loaded = memory_store.load_room(ROOM_CODE)

    assert_same_room(loaded, second.state)
    assert loaded is not None
    assert len(loaded.players) == 2


def test_ac1_store_the_log_is_not_truncated_by_snapshots(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    entries = [log_entry(seq) for seq in range(3, 13)]
    memory_store.append(ROOM_CODE, entries)
    state = two_player_room(fx01_grid).model_copy(update={"seq": 12})

    memory_store.save_snapshot(state)

    assert memory_store.read_log(ROOM_CODE) == entries


def test_ac1_store_close_can_be_called_twice(fx01_grid: Grid, tmp_path: Path) -> None:
    store = RoomStore(tmp_path / "nock.sqlite3")
    store.create_room(two_player_room(fx01_grid))

    store.close()
    store.close()


def test_ac1_store_a_missing_file_is_created_and_the_room_survives_a_reopen(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    assert not path.exists()
    first = RoomStore(path)
    try:
        assert path.exists()
        assert first.has_room(ROOM_CODE) is False
        first.create_room(two_player_room(fx01_grid))
        first.append(ROOM_CODE, [log_entry(3)])
    finally:
        first.close()

    second = RoomStore(path)
    try:
        assert second.has_room(ROOM_CODE) is True
        assert second.read_log(ROOM_CODE) == [log_entry(3)]
    finally:
        second.close()


def test_ac1_store_a_file_database_uses_the_wal_journal(
    file_store: RoomStore, tmp_path: Path, fx01_grid: Grid
) -> None:
    file_store.create_room(two_player_room(fx01_grid))
    file_store.append(ROOM_CODE, [log_entry(3)])

    connection = sqlite3.connect(tmp_path / "nock.sqlite3")
    try:
        row = connection.execute("PRAGMA journal_mode").fetchone()
    finally:
        connection.close()

    assert row is not None
    assert str(row[0]).lower() == "wal"


def test_ac1_store_a_second_store_sees_what_the_first_committed_without_closing(
    file_store: RoomStore, tmp_path: Path, fx01_grid: Grid
) -> None:
    file_store.create_room(two_player_room(fx01_grid))
    file_store.append(ROOM_CODE, [log_entry(3), log_entry(4)])

    reader = RoomStore(tmp_path / "nock.sqlite3")
    try:
        assert reader.has_room(ROOM_CODE) is True
        assert reader.read_log(ROOM_CODE) == [log_entry(3), log_entry(4)]
    finally:
        reader.close()


def test_ac1_store_several_threads_can_append_to_their_own_rooms(
    file_store: RoomStore, fx01_grid: Grid
) -> None:
    codes = ["AAAAA1", "AAAAA2", "AAAAA3", "AAAAA4"]
    for code in codes:
        file_store.create_room(two_player_room(fx01_grid, code))
    problems: list[str] = []

    def append_forty(code: str) -> None:
        try:
            for seq in range(3, 43):
                file_store.append(code, [log_entry(seq)])
        except Exception as error:  # reported by the test thread
            problems.append(repr(error))

    threads: list[threading.Thread] = []
    for code in codes:
        thread = threading.Thread(target=append_forty, args=(code,), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(timeout=OVERALL_SECONDS)
        assert not thread.is_alive(), "an appending thread did not finish"

    assert problems == []
    for code in codes:
        seqs = [entry.event.seq for entry in file_store.read_log(code)]
        assert seqs == list(range(3, 43))


# ---- AC-1: replay ----


def test_ac1_replay_player_joined_appends_a_record_with_the_logged_token(
    fx01_grid: Grid,
) -> None:
    empty = new_room(ROOM_CODE, fx01_grid, START_TIME)
    view = PlayerView(
        player_id="p1",
        nickname="Ana",
        colour=3,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )
    entry = LogEntry(
        at=NOW, event=PlayerJoined(seq=1, player=view), resume_token=FIRST_TOKEN
    )

    replayed = replay(empty, entry)

    assert replayed.seq == 1
    assert replayed.players == (
        PlayerRecord(
            player_id="p1",
            resume_token=FIRST_TOKEN,
            nickname="Ana",
            colour=3,
            is_host=True,
            muted=False,
            state=PlayerState.ACTIVE,
            joined_seq=1,
            last_input_at=NOW,
            last_seen_at=NOW,
            disconnected_at=None,
            selection=None,
            recent_edits=(),
            last_edit=None,
        ),
    )


def test_ac1_replay_a_second_join_goes_after_the_first(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)
    view = PlayerView(
        player_id="p3",
        nickname="Cleo",
        colour=2,
        state=PlayerState.ACTIVE,
        is_host=False,
        muted=False,
        selection=None,
    )

    replayed = replay(
        base,
        LogEntry(
            at=LATER, event=PlayerJoined(seq=3, player=view), resume_token=token_of(3)
        ),
    )

    assert [player.player_id for player in replayed.players] == ["p1", "p2", "p3"]
    third = player_record(replayed, "p3")
    assert third.resume_token == token_of(3)
    assert third.joined_seq == 3
    assert third.last_input_at == LATER
    assert third.last_seen_at == LATER
    assert replayed.players[:2] == base.players


def test_ac1_replay_player_state_changed_sets_the_state_and_disconnected_at(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)
    gone = replay(
        base,
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=3, player_id="p2", state=PlayerState.DISCONNECTED
            ),
        ),
    )

    back = replay(
        gone,
        LogEntry(
            at=LATER + 5,
            event=PlayerStateChanged(seq=4, player_id="p2", state=PlayerState.ACTIVE),
        ),
    )

    assert gone.seq == 3
    assert player_record(gone, "p2").state is PlayerState.DISCONNECTED
    assert player_record(gone, "p2").disconnected_at == LATER
    assert player_record(gone, "p1") == player_record(base, "p1")
    assert back.seq == 4
    assert player_record(back, "p2").state is PlayerState.ACTIVE
    assert player_record(back, "p2").disconnected_at is None


def test_ac1_replay_player_left_removed_drops_the_player_and_bans_the_token(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)

    replayed = replay(
        base,
        LogEntry(
            at=LATER,
            event=PlayerLeft(seq=3, player_id="p2", reason=LeaveReason.REMOVED),
        ),
    )

    assert replayed.seq == 3
    assert [player.player_id for player in replayed.players] == ["p1"]
    assert replayed.removed_tokens == (SECOND_TOKEN,)


@pytest.mark.parametrize("reason", [LeaveReason.LEFT, LeaveReason.TIMED_OUT])
def test_ac1_replay_player_left_for_another_reason_does_not_ban_the_token(
    fx01_grid: Grid, reason: LeaveReason
) -> None:
    replayed = replay(
        two_player_room(fx01_grid),
        LogEntry(at=LATER, event=PlayerLeft(seq=3, player_id="p2", reason=reason)),
    )

    assert [player.player_id for player in replayed.players] == ["p1"]
    assert replayed.removed_tokens == ()


def test_ac1_replay_letter_changed_writes_the_cell_and_remembers_the_old_one(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    replayed = replay(
        seeded, LogEntry(at=NOW, event=letter_changed(3, 1, 1, "A", "p1"))
    )

    assert replayed.seq == 3
    assert cell_state(replayed, 1, 1) == CellState(
        row=1, column=1, letter="A", author="p1", changed_seq=3, changed_by="p1"
    )
    assert player_record(replayed, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=3, letter="B", pencil=True, author="p2"
    )
    assert player_record(replayed, "p2").last_edit is None
    assert other_cells(replayed, 1, 1) == other_cells(seeded, 1, 1)


def test_ac1_replay_an_erase_clears_the_author_and_remembers_the_letter(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    replayed = replay(
        seeded, LogEntry(at=NOW, event=letter_changed(3, 1, 0, None, "p1"))
    )

    assert cell_state(replayed, 1, 0) == CellState(
        row=1, column=0, changed_seq=3, changed_by="p1"
    )
    assert player_record(replayed, "p1").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter="T", pencil=False, author="p2"
    )


def test_ac1_replay_an_undo_entry_clears_last_edit(fx01_grid: Grid) -> None:
    typed = replay(
        two_player_room(fx01_grid),
        LogEntry(at=NOW, event=letter_changed(3, 1, 0, "T", "p1")),
    )
    assert player_record(typed, "p1").last_edit is not None

    undone = replay(
        typed,
        LogEntry(at=NOW, event=letter_changed(4, 1, 0, None, "p1"), undo=True),
    )

    assert undone.seq == 4
    assert player_record(undone, "p1").last_edit is None
    assert cell_state(undone, 1, 0) == CellState(
        row=1, column=0, changed_seq=4, changed_by="p1"
    )


def test_ac1_replay_cell_locked_by_a_check_keeps_the_letter_and_locks_it(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=2,
            letter="X",
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    replayed = replay(
        seeded,
        LogEntry(
            at=NOW, event=CellLocked(seq=3, row=1, column=2, letter="M", revealed=False)
        ),
    )

    cell = cell_state(replayed, 1, 2)
    assert replayed.seq == 3
    assert (cell.letter, cell.locked, cell.revealed) == ("M", True, False)
    assert (cell.changed_seq, cell.changed_by) == (3, None)


def test_ac1_replay_cell_locked_by_a_reveal_has_no_author(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=2, letter="X", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    replayed = replay(
        seeded,
        LogEntry(
            at=NOW, event=CellLocked(seq=3, row=1, column=2, letter="M", revealed=True)
        ),
    )

    assert cell_state(replayed, 1, 2) == CellState(
        row=1,
        column=2,
        letter="M",
        pencil=False,
        author=None,
        locked=True,
        revealed=True,
        wrong=False,
        changed_seq=3,
        changed_by=None,
    )


def test_ac1_replay_settings_changed_sets_the_settings_and_the_budget(
    fx01_grid: Grid,
) -> None:
    settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=9, words=3),
        locked=True,
    )
    left = RevealBudget(letters=4, words=2)

    replayed = replay(
        two_player_room(fx01_grid),
        LogEntry(
            at=NOW,
            event=SettingsChanged(
                seq=3, player_id="p1", settings=settings, reveal_budget=left
            ),
        ),
    )

    assert replayed.seq == 3
    assert replayed.settings == settings
    assert replayed.reveal_budget == left


def test_ac1_replay_host_changed_moves_the_host_role(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)
    assert player_record(base, "p1").is_host is True

    replayed = replay(base, LogEntry(at=NOW, event=HostChanged(seq=3, player_id="p2")))

    assert replayed.seq == 3
    assert player_record(replayed, "p1").is_host is False
    assert player_record(replayed, "p2").is_host is True


def test_ac1_replay_player_muted_sets_and_clears_the_flag(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)

    muted = replay(
        base,
        LogEntry(at=NOW, event=PlayerMuted(seq=3, player_id="p2", muted=True)),
    )
    unmuted = replay(
        muted,
        LogEntry(at=NOW, event=PlayerMuted(seq=4, player_id="p2", muted=False)),
    )

    assert player_record(muted, "p2").muted is True
    assert player_record(muted, "p1").muted is False
    assert player_record(unmuted, "p2").muted is False
    assert unmuted.seq == 4


def test_ac1_replay_an_event_of_a_later_spec_only_moves_the_seq(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)

    replayed = replay(base, LogEntry(at=NOW, event=GridSolved(seq=3, elapsed_ms=1000)))

    assert replayed == base.model_copy(update={"seq": 3})


# ---- AC-1: after_restart ----


def three_player_room_with_live_data(grid: Grid) -> RoomState:
    """p1 active with edits, p2 already disconnected, p3 idle with a selection."""
    state = two_player_room(grid)
    third = join_room(
        state, Join(nickname="Cleo", resume_token=None), NOW, "p3", token_of(3)
    )
    state = third.state
    edited = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    state = edited.state
    selection = Selection(row=1, column=1, direction=Direction.ACROSS)
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == "p1":
            players.append(player.model_copy(update={"selection": selection}))
        elif player.player_id == "p2":
            players.append(
                player.model_copy(
                    update={"state": PlayerState.DISCONNECTED, "disconnected_at": 500.0}
                )
            )
        else:
            players.append(
                player.model_copy(
                    update={"state": PlayerState.IDLE, "selection": selection}
                )
            )
    return state.model_copy(update={"players": tuple(players)})


def test_ac1_after_restart_disconnects_every_player_who_was_not(
    fx01_grid: Grid,
) -> None:
    before = three_player_room_with_live_data(fx01_grid)
    assert before.seq == 4
    assert len(player_record(before, "p1").recent_edits) == 1

    outcome = after_restart(before, LATER)

    first = player_record(outcome.state, "p1")
    third = player_record(outcome.state, "p3")
    assert first.state is PlayerState.DISCONNECTED
    assert third.state is PlayerState.DISCONNECTED
    for restarted in (first, third):
        assert restarted.disconnected_at == LATER
        assert restarted.selection is None
        assert restarted.recent_edits == ()
    second = player_record(outcome.state, "p2")
    assert second == player_record(before, "p2")
    assert second.disconnected_at == 500.0


def test_ac1_after_restart_logs_one_state_change_per_player_in_players_order(
    fx01_grid: Grid,
) -> None:
    before = three_player_room_with_live_data(fx01_grid)

    outcome = after_restart(before, LATER)

    assert outcome.entries == (
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=5, player_id="p1", state=PlayerState.DISCONNECTED
            ),
        ),
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=6, player_id="p3", state=PlayerState.DISCONNECTED
            ),
        ),
    )
    assert outcome.state.seq == 6
    assert outcome.reply == ()
    assert outcome.to_others == ()
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac1_after_restart_keeps_the_grid_and_the_tokens(fx01_grid: Grid) -> None:
    before = three_player_room_with_live_data(fx01_grid)

    after = after_restart(before, LATER).state

    assert [player.state for player in after.players] == [PlayerState.DISCONNECTED] * 3
    assert after.cells == before.cells
    assert resume_tokens(after) == resume_tokens(before)
    assert [player.nickname for player in after.players] == ["Ana", "Bob", "Cleo"]
    assert player_record(after, "p1").last_edit == player_record(before, "p1").last_edit


def test_ac1_after_restart_of_a_room_with_nobody_to_disconnect_changes_nothing(
    fx01_grid: Grid,
) -> None:
    empty = new_room(ROOM_CODE, fx01_grid, START_TIME)
    gone = after_restart(three_player_room_with_live_data(fx01_grid), LATER).state
    assert [player.state for player in gone.players] == [PlayerState.DISCONNECTED] * 3

    for state in (empty, gone):
        outcome = after_restart(state, LATER + 10)
        assert outcome.entries == ()
        assert outcome.state == state


# ---- AC-1: load_room after 250 steps ----


def test_ac1_the_drive_reaches_250_events_with_real_undos(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)

    assert live.seq == DRIVE_EVENTS
    log = memory_store.read_log(ROOM_CODE)
    assert [entry.event.seq for entry in log] == list(range(1, DRIVE_EVENTS + 1))
    undo_entries = [entry for entry in log if entry.undo]
    assert len(undo_entries) >= 40
    for entry in undo_entries:
        assert isinstance(entry.event, LetterChanged)
    assert log[0].resume_token == token_of(0)
    assert [entry.resume_token for entry in log[:3]] == [token_of(i) for i in range(3)]
    assert all(entry.resume_token is None for entry in log[3:])


def test_ac1_load_room_replays_250_steps_to_the_live_state(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)

    loaded = memory_store.load_room(ROOM_CODE)

    assert live.seq == DRIVE_EVENTS
    assert_same_room(loaded, live)
    assert loaded is not None
    assert loaded.seq == DRIVE_EVENTS
    assert resume_tokens(loaded) == [token_of(0), token_of(1), token_of(2)]
    letters = [value[0] for value in grid_values(grid_state(loaded)).values()]
    assert any(letter is not None for letter in letters)


def test_ac1_load_room_after_a_snapshot_at_seq_100_gives_the_same_state(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid, snapshot_at=100)

    loaded = memory_store.load_room(ROOM_CODE)

    assert live.seq == DRIVE_EVENTS
    assert_same_room(loaded, live)
    assert loaded is not None
    assert len(loaded.players) == 3


def test_ac1_load_room_in_a_file_survives_a_crash_without_close(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    crashed = RoomStore(path)
    try:
        live = drive_room(crashed, fx01_grid)
        # The first store is neither closed nor given a last snapshot, as in a crash.
        restarted = RoomStore(path)
        try:
            assert_same_room(restarted.load_room(ROOM_CODE), live)
            assert len(restarted.read_log(ROOM_CODE)) == DRIVE_EVENTS
        finally:
            restarted.close()
    finally:
        crashed.close()


def test_ac1_a_removed_player_is_gone_after_load_and_their_token_is_banned(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)
    second_token = token_of(1)
    removal = LogEntry(
        at=LATER,
        event=PlayerLeft(seq=live.seq + 1, player_id="p2", reason=LeaveReason.REMOVED),
    )
    memory_store.append(ROOM_CODE, [removal])

    loaded = memory_store.load_room(ROOM_CODE)

    assert loaded is not None
    assert loaded.seq == DRIVE_EVENTS + 1
    assert [player.player_id for player in loaded.players] == ["p1", "p3"]
    assert loaded.removed_tokens == (second_token,)


def test_ac1_a_damaged_log_row_makes_load_room_raise(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    try:
        drive_room(store, fx01_grid)
    finally:
        store.close()
    corrupt_log_entry(path, 20)

    reopened = RoomStore(path)
    try:
        with pytest.raises(ValidationError):
            reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()


# ---- AC-1: the registry with a store ----


def test_ac1_register_room_records_the_room_in_the_store(
    memory_store: RoomStore, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    room_registry = RoomRegistry(store=memory_store, clock=fake_clock)
    try:
        code = room_registry.register_room(fx01_grid, grid_number=7)
        state = room_registry.room_state(code)

        assert memory_store.has_room(code) is True
        assert state is not None
        assert state.created_at == fake_clock.now
        assert memory_store.load_room(code) == state
        assert memory_store.load_room(code) == new_room(
            code, fx01_grid, fake_clock.now, 7
        )
    finally:
        room_registry.close()


def test_ac1_add_room_records_the_state_in_the_store(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    room_registry = RoomRegistry(store=memory_store)
    try:
        state = two_player_room(fx01_grid)

        room_registry.add_room(state)

        assert memory_store.has_room(ROOM_CODE) is True
        assert memory_store.load_room(ROOM_CODE) == state
    finally:
        room_registry.close()


def test_ac1_a_code_that_is_only_in_the_store_counts_as_taken(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    room_registry = RoomRegistry(store=memory_store)
    try:
        with pytest.raises(ValueError, match=r".+"):
            room_registry.add_room(new_room(ROOM_CODE, fx01_grid, START_TIME))

        assert memory_store.load_room(ROOM_CODE) == two_player_room(fx01_grid)
    finally:
        room_registry.close()


def test_ac1_closing_a_registry_leaves_a_store_it_was_given_open(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    room_registry = RoomRegistry(store=memory_store)
    code = room_registry.register_room(fx01_grid)

    room_registry.close()

    assert memory_store.has_room(code) is True
    assert memory_store.read_log(code) == []


def test_ac1_a_room_found_in_the_store_is_loaded_and_its_players_disconnected(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / "nock.sqlite3"
    first_store = RoomStore(path)
    second_store = RoomStore(path)
    try:
        live = drive_room(first_store, fx01_grid)
        assert live.seq == DRIVE_EVENTS
        # Process one is dropped without a close: process two starts on the file.
        fake_clock.now = LATER
        room_registry = RoomRegistry(
            config=SERVER_CONFIG, clock=fake_clock, store=second_store
        )
        try:
            state = room_registry.room_state(ROOM_CODE)

            assert state is not None
            assert state.seq == DRIVE_EVENTS + 3
            assert grid_state(state) == grid_state(live)
            assert resume_tokens(state) == resume_tokens(live)
            assert [player.player_id for player in state.players] == ["p1", "p2", "p3"]
            for player in state.players:
                assert player.state is PlayerState.DISCONNECTED
                assert player.disconnected_at == LATER
                assert player.selection is None
                assert player.recent_edits == ()
            assert second_store.read_log(ROOM_CODE, after_seq=DRIVE_EVENTS) == [
                LogEntry(
                    at=LATER,
                    event=PlayerStateChanged(
                        seq=DRIVE_EVENTS + index + 1,
                        player_id=f"p{index + 1}",
                        state=PlayerState.DISCONNECTED,
                    ),
                )
                for index in range(3)
            ]
            assert room_registry.find_room(ROOM_CODE) == fx01_grid

            again = room_registry.room_state(ROOM_CODE)
            assert again == state
            assert len(second_store.read_log(ROOM_CODE)) == DRIVE_EVENTS + 3
        finally:
            room_registry.close()
    finally:
        second_store.close()
        first_store.close()


def test_ac1_an_unknown_code_is_still_unknown_with_a_store(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    room_registry = RoomRegistry(store=memory_store)
    try:
        assert room_registry.room_state(OTHER_CODE) is None
        assert room_registry.find_room(OTHER_CODE) is None
    finally:
        room_registry.close()


# ---- AC-1: the app and NOCK_DATABASE ----


def test_ac1_create_app_stores_the_rooms_in_the_file_of_nock_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    dist_dir: Path,
) -> None:
    path = tmp_path / "data.sqlite3"
    monkeypatch.setenv("NOCK_DATABASE", str(path))
    app = create_app(dist_dir=dist_dir, catalogue=catalogue)
    assert not path.exists(), "the store must open when the app starts, not before"

    with TestClient(app) as http_client:
        assert path.exists()
        response = http_client.post(
            "/api/rooms", json={"grid_number": PUBLISHED_NUMBER}
        )
        assert response.status_code == 201
        code = response.json()["code"]

    store = RoomStore(path)
    try:
        assert store.has_room(code) is True
        loaded = store.load_room(code)
    finally:
        store.close()
    assert loaded is not None
    assert loaded.grid_number == PUBLISHED_NUMBER


def test_ac1_create_app_without_nock_database_writes_no_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    dist_dir: Path,
) -> None:
    monkeypatch.delenv("NOCK_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    before = sorted(entry.name for entry in tmp_path.iterdir())

    with TestClient(create_app(dist_dir=dist_dir, catalogue=catalogue)) as http_client:
        response = http_client.post(
            "/api/rooms", json={"grid_number": PUBLISHED_NUMBER}
        )
        assert response.status_code == 201

    after = sorted(entry.name for entry in tmp_path.iterdir())
    assert after == before


def test_ac1_the_app_never_closes_a_registry_it_was_given(
    memory_store: RoomStore, fx01_grid: Grid, dist_dir: Path
) -> None:
    given = RoomRegistry(store=memory_store)
    try:
        with TestClient(create_app(rooms=given, dist_dir=dist_dir)):
            pass

        code = given.register_room(fx01_grid)

        assert memory_store.has_room(code) is True
    finally:
        given.close()


# ---- Helpers for the WebSocket tests ----


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives.

    `on_message` runs in the reader thread as soon as a message is read; an
    exception it raises is reported by the next wait of the test. All waits are
    bounded.
    """

    def __init__(
        self,
        websocket: WebSocketTestSession,
        on_message: Callable[[ServerMessage], None] | None = None,
    ) -> None:
        self._websocket = websocket
        self._on_message = on_message
        self._arrived = threading.Condition()
        self._received: list[ServerMessage] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except BaseException:  # the socket closed at the end of the test
                return
            try:
                message = parse_server_message(text)
            except ValueError as error:
                self._keep_failure(f"unparsable message {text!r}: {error}")
                continue
            if self._on_message is not None:
                try:
                    self._on_message(message)
                except Exception as error:  # reported by the test thread
                    self._keep_failure(f"{message!r}: {error}")
            with self._arrived:
                self._received.append(message)
                self._arrived.notify_all()

    def _keep_failure(self, text: str) -> None:
        with self._arrived:
            self._failures.append(text)
            self._arrived.notify_all()

    def failures(self) -> list[str]:
        with self._arrived:
            return list(self._failures)

    def send(self, message: ClientSend) -> None:
        self._websocket.send_text(message.model_dump_json())

    def messages(self) -> list[ServerMessage]:
        """Every message received so far, the snapshot first."""
        with self._arrived:
            return list(self._received)

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def events(self) -> list[ServerMessage]:
        return self.messages()[1:]

    def you(self) -> str:
        return self.snapshot().you

    def last_seq(self) -> int:
        last = self.snapshot().seq
        for message in self.events():
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

    def letter_events(self) -> list[LetterChanged]:
        found: list[LetterChanged] = []
        for message in self.events():
            if isinstance(message, LetterChanged):
                found.append(message)
        return found

    def errors(self) -> list[ErrorMessage]:
        found: list[ErrorMessage] = []
        for message in self.events():
            if isinstance(message, ErrorMessage):
                found.append(message)
        return found

    def wait_for_messages(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.messages()) >= count, what)

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

    def wait_for_errors(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.errors()) >= count, what)

    def wait_until(self, condition: Callable[[], bool], what: str) -> None:
        """Wait up to WAIT_SECONDS for `condition`, else fail the test."""
        with self._arrived:
            met = self._arrived.wait_for(
                lambda: condition() or len(self._failures) > 0, WAIT_SECONDS
            )
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])
        if not met:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")


def open_peer(
    stack: contextlib.ExitStack,
    http_client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
    on_message: Callable[[ServerMessage], None] | None = None,
) -> Peer:
    """Open a socket, send a join and wait for the answer."""
    websocket = stack.enter_context(
        http_client.websocket_connect(f"/api/rooms/{code}/ws")
    )
    peer = Peer(websocket, on_message)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_for_messages(1, f"the answer to the join of {nickname}")
    return peer


def join_peers(
    stack: contextlib.ExitStack, http_client: TestClient, code: str, names: list[str]
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        peers.append(open_peer(stack, http_client, code, name))
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def grid_of_peer(peer: Peer) -> dict[tuple[int, int], CellValue]:
    """The peer's copy of the grid: its snapshot, then each letter_changed in order."""
    values = grid_values(peer.snapshot().grid)
    for message in peer.events():
        if isinstance(message, LetterChanged):
            author = message.player_id if message.letter is not None else None
            values[(message.row, message.column)] = (
                message.letter,
                message.pencil,
                author,
            )
    return values


def cell_of_peer(peer: Peer, row: int, column: int) -> CellValue:
    return grid_of_peer(peer)[(row, column)]


def server_grid(server: RoomRegistry, code: str) -> dict[tuple[int, int], CellValue]:
    state = server.room_state(code)
    assert state is not None
    return grid_values(grid_state(state))


def settled_server_seq(server: RoomRegistry, code: str) -> int:
    """Return the room's seq once it has not moved for SETTLE_SECONDS."""
    last_seq = -1
    unchanged_since = time.monotonic()
    deadline = unchanged_since + OVERALL_SECONDS
    while time.monotonic() < deadline:
        state = server.room_state(code)
        assert state is not None
        now = time.monotonic()
        if state.seq != last_seq:
            last_seq = state.seq
            unchanged_since = now
        elif now - unchanged_since >= SETTLE_SECONDS:
            return state.seq
        time.sleep(POLL_SECONDS)
    pytest.fail("the room's seq never stopped moving")


def random_plan(
    rng: random.Random, cells: list[tuple[int, int]], count: int
) -> list[Edit]:
    """`count` random edits: 90 % letters A to Z, 10 % erases."""
    edits: list[Edit] = []
    for _ in range(count):
        row, column = rng.choice(cells)
        if rng.random() < 0.1:
            edits.append(Erase(row=row, column=column))
        else:
            letter = rng.choice(string.ascii_uppercase)
            edits.append(EditLetter(row=row, column=column, letter=letter))
    return edits


class Senders:
    """Writer threads: each sends its peer's plan, all released together."""

    def __init__(self, peers: list[Peer], plans: list[list[Edit]]) -> None:
        self._start = threading.Barrier(len(peers), timeout=WAIT_SECONDS)
        self._problems: list[str] = []
        self._threads: list[threading.Thread] = []
        for peer, plan in zip(peers, plans, strict=True):
            thread = threading.Thread(target=self._run, args=(peer, plan), daemon=True)
            self._threads.append(thread)

    def _run(self, peer: Peer, plan: list[Edit]) -> None:
        try:
            self._start.wait()
            for edit in plan:
                peer.send(edit)
        except Exception as error:  # reported by the test thread
            self._problems.append(repr(error))

    def start(self) -> None:
        for thread in self._threads:
            thread.start()

    def finish(self) -> None:
        for thread in self._threads:
            thread.join(timeout=OVERALL_SECONDS)
            assert not thread.is_alive(), "a sender thread did not finish"
        assert self._problems == []


class Process:
    """One server process: a store, a registry and an app on one SQLite file."""

    def __init__(self, path: Path, dist_dir: Path, config: RoomConfig) -> None:
        self.store = RoomStore(path)
        self.registry = RoomRegistry(config=config, store=self.store)
        self.app = create_app(rooms=self.registry, dist_dir=dist_dir)

    def shutdown(self) -> None:
        self.registry.close()
        self.store.close()


def commit_checker(path: Path, code: str) -> Callable[[ServerMessage], None]:
    """A hook for a Peer: each numbered event it reads is already in the file."""

    def check(message: ServerMessage) -> None:
        if isinstance(message, Snapshot):
            return
        seq = getattr(message, "seq", None)
        if not isinstance(seq, int):
            return
        reader = RoomStore(path)
        try:
            logged = reader.read_log(code, after_seq=seq - 1)
        finally:
            reader.close()
        logged_seqs = [entry.event.seq for entry in logged]
        if seq not in logged_seqs:
            raise AssertionError(f"seq {seq} was sent before it was committed")

    return check


def players_all_disconnected(process: Process, code: str) -> bool:
    state = process.registry.room_state(code)
    if state is None:
        return False
    return all(player.state is PlayerState.DISCONNECTED for player in state.players)


# ---- AC-1: WebSocket with a simulated restart ----


def test_ac1_websocket_every_event_received_is_already_in_the_database(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    one = Process(path, dist_dir, SERVER_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        cells = letter_cells(fx01_grid)
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            checker = commit_checker(path, code)
            ana = open_peer(stack, http_client, code, "Ana", on_message=checker)
            bob = open_peer(stack, http_client, code, "Bob", on_message=checker)
            bob.wait_for_seq(2, "both joins")
            for index in range(30):
                row, column = cells[index % len(cells)]
                sender = ana if index % 2 == 0 else bob
                sender.send(
                    EditLetter(
                        row=row, column=column, letter=string.ascii_uppercase[index]
                    )
                )
            bob.wait_for_seq(32, "the 30 letters")
            ana.wait_for_seq(32, "the 30 letters")

            assert bob.failures() == []
            assert ana.failures() == []
            assert len(bob.letter_events()) == 30
    finally:
        one.shutdown()


def test_ac1_websocket_players_reconnect_after_a_restart_to_the_same_grid(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)
    with contextlib.ExitStack() as cleanup:
        one = Process(path, dist_dir, SERVER_CONFIG)
        # Process one is never closed during the test, as a crash would not.
        cleanup.callback(one.shutdown)
        code = one.registry.register_room(fx01_grid)
        first_run = cleanup.enter_context(contextlib.ExitStack())
        first_client = first_run.enter_context(TestClient(one.app))
        ana = open_peer(first_run, first_client, code, "Ana")
        bob = open_peer(first_run, first_client, code, "Bob")
        bob.wait_for_seq(2, "both joins")
        rng = random.Random(18)
        for index in range(30):
            row, column = rng.choice(cells)
            letter = rng.choice(string.ascii_uppercase)
            sender = ana if index % 2 == 0 else bob
            sender.send(EditLetter(row=row, column=column, letter=letter))
        bob.wait_for_seq(32, "the 30 letters on Bob")
        ana.wait_for_seq(32, "the 30 letters on Ana")
        grid_before = grid_of_peer(bob)
        assert grid_before == grid_of_peer(ana)
        ana_id = ana.you()
        bob_id = bob.you()
        ana_token = ana.snapshot().resume_token
        bob_token = bob.snapshot().resume_token
        bob_view_of_players = bob.snapshot().players
        known_seq = bob.last_seq()

        first_run.close()
        wait_for(
            lambda: players_all_disconnected(one, code),
            "process one to log the closing of both sockets",
        )

        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        second_run = cleanup.enter_context(contextlib.ExitStack())
        second_client = second_run.enter_context(TestClient(two.app))
        ana_again = open_peer(second_run, second_client, code, "Ana", ana_token)
        bob_again = open_peer(second_run, second_client, code, "Bob", bob_token)

        for peer, expected_id in ((ana_again, ana_id), (bob_again, bob_id)):
            snapshot = peer.snapshot()
            assert snapshot.you == expected_id
            assert snapshot.seq >= known_seq
            assert [(p.nickname, p.colour) for p in snapshot.players] == [
                (p.nickname, p.colour) for p in bob_view_of_players
            ]
            assert [p.player_id for p in snapshot.players] == [ana_id, bob_id]
            assert grid_values(snapshot.grid) == grid_before
        assert ana_again.errors() == []
        assert bob_again.errors() == []


def test_ac1_websocket_a_new_player_can_join_a_room_that_only_the_store_knows(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    with contextlib.ExitStack() as cleanup:
        seed_store = RoomStore(path)
        cleanup.callback(seed_store.close)
        live = drive_room(seed_store, fx01_grid)
        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        run = cleanup.enter_context(contextlib.ExitStack())
        http_client = run.enter_context(TestClient(two.app))

        newcomer = open_peer(run, http_client, ROOM_CODE, "Dan")

        snapshot = newcomer.snapshot()
        assert grid_values(snapshot.grid) == grid_values(grid_state(live))
        assert [p.nickname for p in snapshot.players] == ["Ana", "Bob", "Cleo", "Dan"]
        assert [p.state for p in snapshot.players[:3]] == [PlayerState.DISCONNECTED] * 3
        assert snapshot.players[3].state is PlayerState.ACTIVE
        assert snapshot.seq == DRIVE_EVENTS + 3 + 1


# ---- AC-1: snapshots made by the hub ----


def test_ac1_hub_saves_a_snapshot_every_100_logged_events(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)
    one = Process(path, dist_dir, SNAPSHOT_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            ana = open_peer(stack, http_client, code, "Ana")
            sent = 0

            def send_edits(count: int) -> None:
                nonlocal sent
                for _ in range(count):
                    row, column = cells[sent % len(cells)]
                    letter = string.ascii_uppercase[sent % 26]
                    ana.send(EditLetter(row=row, column=column, letter=letter))
                    sent += 1

            send_edits(98)
            ana.wait_for_seq(99, "99 events")
            corrupt_log_entry(path, 50)
            time.sleep(SHORT_PAUSE_SECONDS)
            with pytest.raises(ValidationError):
                load_from_file(path, code)

            send_edits(1)
            ana.wait_for_seq(100, "the 100th event")
            at_100 = wait_until_loadable(path, code)
            assert at_100.seq == 100

            send_edits(99)
            ana.wait_for_seq(199, "199 events")
            corrupt_log_entry(path, 150)
            time.sleep(SHORT_PAUSE_SECONDS)
            with pytest.raises(ValidationError):
                load_from_file(path, code)

            send_edits(1)
            ana.wait_for_seq(200, "the 200th event")
            at_200 = wait_until_loadable(path, code)
            assert at_200.seq == 200
            live = one.registry.room_state(code)
            assert live is not None
            assert grid_state(at_200) == grid_state(live)
            assert resume_tokens(at_200) == resume_tokens(live)
    finally:
        one.shutdown()


def test_ac1_hub_saves_a_snapshot_when_the_room_task_stops(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)
    one = Process(path, dist_dir, SNAPSHOT_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            with contextlib.ExitStack() as connection:
                ana = open_peer(connection, http_client, code, "Ana")
                for index in range(10):
                    row, column = cells[index]
                    ana.send(
                        EditLetter(
                            row=row, column=column, letter=string.ascii_uppercase[index]
                        )
                    )
                ana.wait_for_seq(11, "11 events")
                corrupt_log_entry(path, 5)
                time.sleep(SHORT_PAUSE_SECONDS)
                with pytest.raises(ValidationError):
                    load_from_file(path, code)
            # Ana's socket is closed: the room has nobody left and its task stops.
            loaded = wait_until_loadable(path, code)
        assert loaded.seq == 12
        assert loaded.players[0].state is PlayerState.DISCONNECTED
    finally:
        one.shutdown()


# ---- AC-2: a player joining mid-game ----


def check_mid_game_joiner(
    server: RoomRegistry, code: str, joiner: Peer, floor: int
) -> None:
    """Check what the joiner got: a snapshot, then every event once, in order."""
    final_seq = settled_server_seq(server, code)
    joiner.wait_for_seq(final_seq, "the joiner to receive the last seq")

    first = joiner.messages()[0]
    assert isinstance(first, Snapshot)
    snapshot_seq = first.seq
    assert snapshot_seq > floor
    seqs: list[int] = []
    for message in joiner.events():
        assert not isinstance(message, Snapshot)
        assert not isinstance(message, ErrorMessage), message
        seq = getattr(message, "seq", None)
        if isinstance(seq, int):
            seqs.append(seq)
    assert seqs == list(range(snapshot_seq + 1, final_seq + 1))
    assert grid_of_peer(joiner) == server_grid(server, code)
    for message in joiner.events():
        assert not (
            isinstance(message, PlayerJoined)
            and message.player.player_id == joiner.you()
        )
    assert joiner.failures() == []


def test_ac2_websocket_a_joiner_gets_a_snapshot_then_every_event_without_a_gap(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    fx01_grid: Grid,
) -> None:
    cells = letter_cells(fx01_grid)
    rng = random.Random(182)
    plans = [random_plan(rng, cells, EDITS_PER_WRITER) for _ in range(2)]
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        senders = Senders([ana, bob], plans)
        senders.start()
        wait_for(
            lambda: (registry.room_state(room_code) or pytest.fail("room")).seq > 50,
            "the room to pass seq 50",
        )

        cy = open_peer(stack, client, room_code, "Cy")
        senders.finish()

        check_mid_game_joiner(registry, room_code, cy, floor=50)
        final = registry.room_state(room_code)
        assert final is not None
        assert final.seq == 2 + 2 * EDITS_PER_WRITER + 1
        assert [player.nickname for player in final.players] == ["Ana", "Bob", "Cy"]


def test_ac2_websocket_the_joiner_does_not_receive_its_own_player_joined(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        cy = open_peer(stack, client, room_code, "Cy")
        ana.send(EditLetter(row=1, column=0, letter="T"))
        cy.wait_for_seq(4, "the letter after the join")
        ana.wait_for_seq(4, "the letter after the join")

        assert cy.snapshot().seq == 3
        assert [player.nickname for player in cy.snapshot().players] == [
            "Ana",
            "Bob",
            "Cy",
        ]
        assert [type(message).__name__ for message in cy.events()] == ["LetterChanged"]
        # The two others did receive Cy's join, as event 3.
        joins = [m for m in bob.events() if isinstance(m, PlayerJoined)]
        assert [event.seq for event in joins] == [3]


def test_ac2_websocket_the_same_holds_for_a_room_loaded_after_a_restart(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)
    rng = random.Random(183)
    with contextlib.ExitStack() as cleanup:
        one = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(one.shutdown)
        code = one.registry.register_room(fx01_grid)
        first_run = cleanup.enter_context(contextlib.ExitStack())
        first_client = first_run.enter_context(TestClient(one.app))
        ana = open_peer(first_run, first_client, code, "Ana")
        bob = open_peer(first_run, first_client, code, "Bob")
        bob.wait_for_seq(2, "both joins")
        ana_token = ana.snapshot().resume_token
        bob_token = bob.snapshot().resume_token
        before = Senders(
            [ana, bob], [random_plan(rng, cells, 30), random_plan(rng, cells, 30)]
        )
        before.start()
        before.finish()
        settled_server_seq(one.registry, code)
        first_run.close()
        wait_for(lambda: players_all_disconnected(one, code), "both players logged out")

        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        second_run = cleanup.enter_context(contextlib.ExitStack())
        second_client = second_run.enter_context(TestClient(two.app))
        ana_again = open_peer(second_run, second_client, code, "Ana", ana_token)
        bob_again = open_peer(second_run, second_client, code, "Bob", bob_token)
        baseline = settled_server_seq(two.registry, code)
        plans = [random_plan(rng, cells, 100), random_plan(rng, cells, 100)]
        senders = Senders([ana_again, bob_again], plans)
        senders.start()
        wait_for(
            lambda: (two.registry.room_state(code) or pytest.fail("room")).seq
            > baseline + 20,
            "the loaded room to move on",
        )

        cy = open_peer(second_run, second_client, code, "Cy")
        senders.finish()

        check_mid_game_joiner(two.registry, code, cy, floor=baseline + 20)
        final = two.registry.room_state(code)
        assert final is not None
        assert final.seq == baseline + 200 + 1


# ---- AC-3: undo on handle_message ----


def assert_refused_as_nothing_to_undo(outcome: Outcome, before: RoomState) -> None:
    """The undo changed nothing but possibly `last_edit`, and answered the sender."""
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.NOTHING_TO_UNDO
    assert outcome.state.seq == before.seq
    assert outcome.state.cells == before.cells
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac3_an_accepted_edit_records_the_cell_before_it_as_last_edit(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW)

    assert player_record(outcome.state, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=3, letter="B", pencil=True, author="p2"
    )
    assert player_record(outcome.state, "p2").last_edit is None


def test_ac3_an_accepted_edit_in_an_empty_cell_records_an_empty_cell(
    fx01_grid: Grid,
) -> None:
    outcome = handle_message(
        two_player_room(fx01_grid), "p2", EditLetter(row=1, column=0, letter="T"), NOW
    )

    assert player_record(outcome.state, "p2").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter=None, pencil=False, author=None
    )


def test_ac3_an_accepted_erase_records_the_erased_letter_as_last_edit(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    outcome = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)

    assert player_record(outcome.state, "p1").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter="T", pencil=False, author="p2"
    )


def test_ac3_a_later_edit_replaces_last_edit_with_the_latest_one(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    assert player_record(second.state, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=4, letter=None, pencil=False, author=None
    )


def test_ac3_a_refused_edit_leaves_last_edit_alone(fx01_grid: Grid) -> None:
    locked = CellState(
        row=1,
        column=2,
        letter="M",
        author="p2",
        locked=True,
        changed_seq=2,
        changed_by="p2",
    )
    state = with_cell(two_player_room(fx01_grid), locked)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    expected = player_record(first.state, "p1").last_edit
    assert expected is not None

    refused = handle_message(
        first.state, "p1", EditLetter(row=1, column=2, letter="X"), NOW + 1
    )

    assert refused.entries == ()
    assert player_record(refused.state, "p1").last_edit == expected


def test_ac3_undo_of_a_letter_in_an_empty_cell_empties_it_again(
    fx01_grid: Grid,
) -> None:
    typed = handle_message(
        two_player_room(fx01_grid), "p1", EditLetter(row=1, column=0, letter="T"), NOW
    )

    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 0, None, "p1"), undo=True),
    )
    assert undone.reply == ()
    assert undone.state.seq == 4
    assert cell_state(undone.state, 1, 0) == CellState(
        row=1, column=0, changed_seq=4, changed_by="p1"
    )
    assert other_cells(undone.state, 1, 0) == other_cells(typed.state, 1, 0)
    assert player_record(undone.state, "p1").last_edit is None
    assert undone.close_sender is False
    assert undone.disconnects == ()


def test_ac3_undo_over_another_players_letter_brings_it_back_authored_by_me(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=1, letter="B", author="p2", changed_seq=2, changed_by="p2"
        ),
    )
    overwritten = handle_message(
        seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW
    )

    undone = handle_message(overwritten.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 1, "B", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 1) == CellState(
        row=1, column=1, letter="B", author="p1", changed_seq=4, changed_by="p1"
    )
    assert undone.state.seq == 4
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_gives_back_the_pencil_flag_of_the_old_letter(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )
    overwritten = handle_message(
        seeded, "p1", EditLetter(row=1, column=1, letter="A"), NOW
    )

    undone = handle_message(overwritten.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(
            at=NOW + 1,
            event=letter_changed(4, 1, 1, "B", "p1", pencil=True),
            undo=True,
        ),
    )
    assert cell_state(undone.state, 1, 1) == CellState(
        row=1,
        column=1,
        letter="B",
        pencil=True,
        author="p1",
        wrong=False,
        changed_seq=4,
        changed_by="p1",
    )


def test_ac3_undo_of_an_erase_restores_the_erased_letter_authored_by_the_undoer(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )
    erased = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)
    assert cell_state(erased.state, 1, 0).letter is None

    undone = handle_message(erased.state, "p1", Undo(), NOW + 1)

    assert undone.entries == (
        LogEntry(at=NOW + 1, event=letter_changed(4, 1, 0, "T", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 0) == CellState(
        row=1, column=0, letter="T", author="p1", changed_seq=4, changed_by="p1"
    )


def test_ac3_undo_after_another_player_changed_the_cell_is_refused(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    mine = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    theirs = handle_message(
        mine.state, "p2", EditLetter(row=1, column=0, letter="X"), NOW + 1
    )

    undone = handle_message(theirs.state, "p1", Undo(), NOW + 2)

    assert_refused_as_nothing_to_undo(undone, theirs.state)
    assert cell_state(undone.state, 1, 0).letter == "X"
    assert cell_state(undone.state, 1, 0).author == "p2"
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_after_my_own_later_edit_of_the_same_cell_goes_back_one_step(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="U"), NOW + 1
    )

    undone = handle_message(second.state, "p1", Undo(), NOW + 2)

    assert undone.entries == (
        LogEntry(at=NOW + 2, event=letter_changed(5, 1, 0, "T", "p1"), undo=True),
    )
    assert cell_state(undone.state, 1, 0).letter == "T"
    assert cell_state(undone.state, 1, 0).author == "p1"
    again = handle_message(undone.state, "p1", Undo(), NOW + 3)
    assert_refused_as_nothing_to_undo(again, undone.state)
    assert cell_state(again.state, 1, 0).letter == "T"


def test_ac3_a_second_undo_right_after_an_undo_is_refused(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)
    assert undone.entries != ()

    second = handle_message(undone.state, "p1", Undo(), NOW + 2)

    assert_refused_as_nothing_to_undo(second, undone.state)
    assert cell_state(second.state, 1, 0).letter is None


def test_ac3_after_an_undo_a_new_edit_can_be_undone_again(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    undone = handle_message(typed.state, "p1", Undo(), NOW + 1)
    retyped = handle_message(
        undone.state, "p1", EditLetter(row=1, column=0, letter="V"), NOW + 2
    )

    undone_again = handle_message(retyped.state, "p1", Undo(), NOW + 3)

    assert undone_again.entries == (
        LogEntry(at=NOW + 3, event=letter_changed(6, 1, 0, None, "p1"), undo=True),
    )
    assert cell_state(undone_again.state, 1, 0).letter is None


def test_ac3_only_my_latest_edit_can_be_undone_not_the_one_before(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    undone = handle_message(second.state, "p1", Undo(), NOW + 2)
    again = handle_message(undone.state, "p1", Undo(), NOW + 3)

    assert cell_state(undone.state, 1, 1).letter is None
    assert cell_state(undone.state, 1, 0).letter == "T"
    assert_refused_as_nothing_to_undo(again, undone.state)
    assert cell_state(again.state, 1, 0).letter == "T"


@pytest.mark.parametrize("lock_seq", [3, 4])
def test_ac3_undo_on_a_locked_cell_is_refused(fx01_grid: Grid, lock_seq: int) -> None:
    state = two_player_room(fx01_grid)
    typed = handle_message(state, "p1", EditLetter(row=1, column=2, letter="M"), NOW)
    locked_cell = cell_state(typed.state, 1, 2).model_copy(
        update={"locked": True, "changed_seq": lock_seq, "changed_by": None}
    )
    locked = with_cell(typed.state, locked_cell)

    undone = handle_message(locked, "p1", Undo(), NOW + 1)

    assert_refused_as_nothing_to_undo(undone, locked)
    assert cell_state(undone.state, 1, 2).letter == "M"
    assert cell_state(undone.state, 1, 2).locked is True
    assert player_record(undone.state, "p1").last_edit is None


def test_ac3_undo_by_a_player_who_never_edited_is_refused(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)

    undone = handle_message(state, "p1", Undo(), NOW)

    assert_refused_as_nothing_to_undo(undone, state)
    assert undone.state == state


def test_ac3_undo_by_a_player_whose_neighbour_edited_is_still_refused(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    theirs = handle_message(state, "p2", EditLetter(row=1, column=0, letter="X"), NOW)

    undone = handle_message(theirs.state, "p1", Undo(), NOW + 1)

    assert_refused_as_nothing_to_undo(undone, theirs.state)
    assert cell_state(undone.state, 1, 0).letter == "X"
    assert player_record(undone.state, "p2").last_edit is not None


def test_ac3_an_undo_leaves_the_other_players_last_edit_alone(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )
    expected = player_record(second.state, "p1").last_edit
    assert expected is not None

    undone = handle_message(second.state, "p2", Undo(), NOW + 2)

    assert cell_state(undone.state, 1, 1).letter is None
    assert player_record(undone.state, "p1").last_edit == expected
    assert player_record(undone.state, "p2").last_edit is None


def test_ac3_a_cell_changed_by_another_players_undo_cannot_be_undone_by_me(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    mine = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    theirs = handle_message(
        mine.state, "p2", EditLetter(row=1, column=0, letter="X"), NOW + 1
    )
    their_undo = handle_message(theirs.state, "p2", Undo(), NOW + 2)
    assert their_undo.entries != ()
    assert cell_state(their_undo.state, 1, 0).letter == "T"

    undone = handle_message(their_undo.state, "p1", Undo(), NOW + 3)

    assert_refused_as_nothing_to_undo(undone, their_undo.state)


def test_ac3_an_undo_is_not_counted_by_the_rate_limit(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=2)
    state = two_player_room(fx01_grid)
    typed = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )

    undone = handle_message(typed.state, "p1", Undo(), NOW, config)
    retyped = handle_message(
        undone.state, "p1", EditLetter(row=1, column=0, letter="V"), NOW, config
    )

    assert undone.entries != ()
    assert player_record(undone.state, "p1").recent_edits == (NOW,)
    assert retyped.entries != ()
    assert [m for m in retyped.reply if isinstance(m, ErrorMessage)] == []


def test_ac3_an_undo_is_accepted_when_the_player_is_at_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = two_player_room(fx01_grid)
    typed = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )
    blocked = handle_message(
        typed.state, "p1", EditLetter(row=1, column=1, letter="A"), NOW, config
    )
    assert isinstance(blocked.reply[0], ErrorMessage)
    assert blocked.reply[0].code is ErrorCode.RATE_LIMITED

    undone = handle_message(blocked.state, "p1", Undo(), NOW, config)

    assert len(undone.entries) == 1
    assert undone.entries[0].undo is True
    assert undone.reply == ()


# ---- AC-3: undo on the WebSocket ----


def test_ac3_websocket_an_undo_reaches_the_other_client_as_a_letter_changed(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        bob.wait_for_seq(3, "the letter")

        ana.send(Undo())
        bob.wait_for_seq(4, "the undo")
        ana.wait_for_seq(4, "the undo")

        ana_id = ana.you()
        expected = [
            letter_changed(3, 1, 0, "T", ana_id),
            letter_changed(4, 1, 0, None, ana_id),
        ]
        assert bob.letter_events() == expected
        assert ana.letter_events() == expected
        assert cell_of_peer(bob, 1, 0) == (None, False, None)
        assert cell_of_peer(ana, 1, 0) == (None, False, None)
        assert server_grid(registry, room_code)[(1, 0)] == (None, False, None)
        assert ana.errors() == []
        assert bob.errors() == []
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 4
        assert player_record(state, ana_id).last_edit is None


def test_ac3_websocket_an_undo_over_the_other_players_letter_restores_it(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send(EditLetter(row=1, column=1, letter="B"))
        ana.wait_for_seq(3, "Bob's letter")
        ana.send(EditLetter(row=1, column=1, letter="A"))
        bob.wait_for_seq(4, "Ana's letter")

        ana.send(Undo())
        bob.wait_for_seq(5, "the undo")

        assert cell_of_peer(bob, 1, 1) == ("B", False, ana.you())
        assert server_grid(registry, room_code)[(1, 1)] == ("B", False, ana.you())


def test_ac3_websocket_an_undo_after_the_other_player_changed_the_cell_is_refused(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        bob.wait_for_seq(3, "Ana's letter")
        bob.send(EditLetter(row=1, column=0, letter="X"))
        ana.wait_for_seq(4, "Bob's letter")

        ana.send(Undo())
        ana.wait_for_errors(1, "the refusal of the undo")
        # An accepted edit afterwards proves nothing was sent to Bob in between.
        ana.send(EditLetter(row=1, column=1, letter="A"))
        bob.wait_for_seq(5, "the edit after the refusal")
        ana.wait_for_seq(5, "the edit after the refusal")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOTHING_TO_UNDO]
        assert bob.errors() == []
        assert [event.seq for event in bob.letter_events()] == [3, 4, 5]
        assert bob.letter_events()[-1] == letter_changed(5, 1, 1, "A", ana.you())
        assert cell_of_peer(bob, 1, 0) == ("X", False, bob.you())
        assert server_grid(registry, room_code)[(1, 0)] == ("X", False, bob.you())
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 5


def test_ac3_websocket_an_undo_with_nothing_to_undo_answers_only_its_sender(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(Undo())
        ana.wait_for_errors(1, "the refusal")
        bob.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_seq(3, "Bob's letter")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOTHING_TO_UNDO]
        assert bob.errors() == []
        assert [type(message) for message in bob.events()] == [LetterChanged]


# ---- AC-3: the page, with a mocked socket ----


def fr_text(key: str) -> str:
    fr_path = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
    texts = json.loads(fr_path.read_text(encoding="utf-8"))
    value = texts[key]
    assert isinstance(value, str)
    return value


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def undo_count(self) -> int:
        count = 0
        for frame in self.received:
            if isinstance(parse_client_message(frame), Undo):
                count += 1
        return count

    def sent_in_order(self) -> list[str]:
        """The type of each edit_letter, erase and undo received, in order."""
        types: list[str] = []
        for frame in self.received:
            message = parse_client_message(frame)
            if isinstance(message, EditLetter | Erase | Undo):
                types.append(message.type)
        return types


def wait_until_page(page: Page, condition: Callable[[], bool]) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def snapshot_frame(view: GridView, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=(),
        settings=RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def with_letter_cells(view: GridView, changes: ChangeList) -> GridView:
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def start_page(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket; stop at the nickname form."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    expect(page.get_by_test_id("nickname-input")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    return mock


def join_page(
    page: Page,
    mock: MockRoomSocket,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
    seq: int = 5,
) -> None:
    """Join as Ana and answer with a snapshot of FX-01 for `p1` at `seq`."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.received) > 0)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
    seq: int = 5,
) -> MockRoomSocket:
    mock = start_page(page, base_url)
    join_page(page, mock, fx01_grid, changes, seq)
    return mock


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    return letter_changed(seq, row, column, letter, player_id).model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def expect_cell(
    page: Page,
    row: int,
    column: int,
    letter: str,
    unconfirmed: bool,
    author: str | None = None,
) -> None:
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute(
        "data-unconfirmed", "true" if unconfirmed else "false"
    )
    if author is not None:
        expect(cell).to_have_attribute("data-author", author)


def test_ac3_browser_the_undo_button_shows_only_once_joined_with_its_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = start_page(page, live_server)
    expect(page.get_by_test_id("undo-button")).to_be_hidden()

    join_page(page, mock, fx01_grid)

    button = page.get_by_test_id("undo-button")
    expect(button).to_have_count(1)
    expect(button).to_be_visible()
    expect(button).to_have_text(fr_text("room.undo"))
    assert fr_text("room.undo") == "Annuler"


def test_ac3_browser_clicking_the_undo_button_sends_one_undo(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    page.get_by_test_id("undo-button").click()

    wait_until_page(page, lambda: mock.undo_count() >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert mock.undo_count() == 1
    assert '"type":"undo"' in mock.received[-1].replace(" ", "")


@pytest.mark.parametrize("shortcut", ["Control+z", "Meta+z"])
def test_ac3_browser_the_undo_shortcut_with_the_grid_focused_sends_an_undo(
    page: Page, live_server: str, fx01_grid: Grid, shortcut: str
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()

    page.keyboard.press(shortcut)

    wait_until_page(page, lambda: mock.undo_count() >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert mock.undo_count() == 1
    assert mock.sent_in_order() == ["undo"]


@pytest.mark.parametrize("modifier", ["Control", "Meta"])
def test_ac3_browser_the_undo_shortcut_prevents_the_browser_default(
    page: Page, live_server: str, fx01_grid: Grid, modifier: str
) -> None:
    open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()

    prevented = page.get_by_test_id("grid").evaluate(
        """(grid, modifier) => {
            const event = new KeyboardEvent("keydown", {
                key: "z",
                code: "KeyZ",
                ctrlKey: modifier === "Control",
                metaKey: modifier === "Meta",
                bubbles: true,
                cancelable: true,
            });
            grid.dispatchEvent(event);
            return event.defaultPrevented;
        }""",
        modifier,
    )

    assert prevented is True


def test_ac3_browser_the_undo_shortcut_does_nothing_when_the_grid_is_not_focused(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.evaluate(
        "() => { if (document.activeElement instanceof HTMLElement) "
        "document.activeElement.blur(); }"
    )

    page.keyboard.press("Control+z")
    page.wait_for_timeout(SETTLE_MS)

    assert mock.undo_count() == 0


def test_ac3_browser_nothing_to_undo_shows_the_message_for_about_three_seconds(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    message = page.get_by_test_id("undo-message")
    expect(message).to_be_hidden()

    mock.send(error_frame(ErrorCode.NOTHING_TO_UNDO))

    expect(message).to_be_visible()
    expect(message).to_have_text(fr_text("undo.nothing"))
    assert fr_text("undo.nothing") == "Rien à annuler."
    page.wait_for_timeout(1500)
    expect(message).to_be_visible()
    expect(message).to_be_hidden(timeout=(UNDO_MESSAGE_SECONDS + 2) * 1000)


def test_ac3_browser_other_errors_do_not_show_the_undo_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    mock.send(error_frame(ErrorCode.NOT_HOST))
    page.wait_for_timeout(SETTLE_MS)

    expect(page.get_by_test_id("undo-message")).to_be_hidden()


def test_ac3_browser_undo_pressed_while_an_edit_is_pending_goes_after_the_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    page.get_by_test_id("undo-button").click()

    wait_until_page(page, lambda: len(mock.sent_in_order()) >= 2)
    assert mock.sent_in_order() == ["edit_letter", "undo"]


def test_ac3_browser_the_result_of_an_undo_updates_the_grid_from_you(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 0, {"letter": "A", "author": "p1"})],
    )
    expect_cell(page, 1, 0, "A", unconfirmed=False, author="p1")

    mock.send(letter_changed_frame(6, 1, 0, "B", "p1"))

    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p1")
    mock.send(letter_changed_frame(7, 1, 0, None, "p1"))
    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


def test_ac3_browser_an_own_letter_changed_for_another_cell_keeps_the_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 1, "A", "p1"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p1")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac3_browser_an_own_letter_changed_with_another_letter_keeps_the_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 0, "B", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
