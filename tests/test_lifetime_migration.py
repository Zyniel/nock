"""Tests of lobby/lifetime, AC-13: a database below `user_version` 2 is migrated.

The old databases are written by hand with the old schemas of `src/nock/store.py`
(no creator column at `user_version` 0; the creator column and no solve time at
`user_version` 1), holding four rooms of FX-01:

- `S`: solved at `s`; its stored state (the snapshot) says so (`solved_at`);
  its last edit time is later than `s`;
- `V`: solved at `v`, its last edit time later than `v`; its snapshot is older
  than the solving step, whose two log entries (`letter_changed`, `grid_solved`)
  say so; it has a creator at version 1;
- `W`: solved, but its stored state has no `solved_at` and its log is empty, so
  nothing gives a solve time: it gets its last edit time `w`;
- `U`: unsolved, last edited at `u`.

Opening a `RoomStore` migrates them. The tests read the file with `sqlite3`: the
version, the column `solved_at` of `room_times` (the name of `RoomState.solved_at`
and of the glossary), and every other table and column, which must be as it was.
Then a registry on the migrated file, with `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` 24,
expires each solved room 24 hours after its solve time, and not `U`.

The shared setup is in `lifetime_harness`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import schema_version, stored_creator
from lifetime_harness import (
    HOUR,
    LEA_ACCOUNT,
    config_with_lives,
    select_rows,
    stored_solve_time,
)
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import GridSolved
from nock.room import LogEntry, RoomState
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec026_harness import LAST_CELL, NOW, full17, solved_room, write
from spec032_harness import grid_from_text

SOLVED_ROOM = "SOLVED"
LOGGED_ROOM = "LOGGED"
NO_TIME_ROOM = "NOTIME"
UNSOLVED_ROOM = "UNSOLV"

SOLVED_AT = NOW + 754.0  # `solved_room`'s solving letter
LOGGED_SOLVED_AT = NOW + 900.0
SOLVED_LAST_EDIT_AT = SOLVED_AT + 300.0  # after the solve time, to tell them apart
LOGGED_LAST_EDIT_AT = LOGGED_SOLVED_AT + 400.0
NO_TIME_LAST_EDIT_AT = NOW + 1_234.0
UNSOLVED_LAST_EDIT_AT = NOW + 500.0

# The schemas before this change; V0 is the one before the creator column.
SCHEMA_V0 = """
CREATE TABLE rooms (code TEXT PRIMARY KEY);
CREATE TABLE snapshots (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
CREATE TABLE log (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    entry_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
CREATE TABLE share_tokens (
    token TEXT PRIMARY KEY,
    code TEXT NOT NULL REFERENCES rooms (code)
);
CREATE TABLE room_times (
    code TEXT PRIMARY KEY REFERENCES rooms (code),
    created_at REAL NOT NULL,
    last_edit_at REAL NOT NULL
);
"""
SCHEMA_V1_CREATOR_COLUMN = "ALTER TABLE room_times ADD COLUMN creator_account_id TEXT"

# What a migration must leave as it was, table by table.
UNCHANGED_QUERIES = [
    "SELECT code FROM rooms ORDER BY code",
    "SELECT code, seq, state_json FROM snapshots ORDER BY code, seq",
    "SELECT code, seq, entry_json FROM log ORDER BY code, seq",
    "SELECT token, code FROM share_tokens ORDER BY token",
    "SELECT code, created_at, last_edit_at FROM room_times ORDER BY code",
]
CREATOR_QUERY = "SELECT code, creator_account_id FROM room_times ORDER BY code"


class OldRoom(NamedTuple):
    """A room of an old database: its snapshot, its log and its `room_times` row."""

    state: RoomState
    log: tuple[LogEntry, ...]
    last_edit_at: float
    creator: str | None


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def named(state: RoomState, code: str) -> RoomState:
    """The state as room `code`, with its own share token."""
    return state.model_copy(
        update={"code": code, "share_token": f"share-token-of-{code.lower()}"}
    )


def old_rooms(grid: Grid) -> list[OldRoom]:
    """The four rooms of the old databases."""
    solved = named(solved_room(grid), SOLVED_ROOM)
    assert solved.solved_at == SOLVED_AT

    solving_step = write(full17(grid), "p2", LAST_CELL, "T", LOGGED_SOLVED_AT)
    assert isinstance(solving_step.entries[-1].event, GridSolved)
    logged = named(full17(grid), LOGGED_ROOM)

    without_time = solved_room(grid).model_copy(
        update={"solved_at": None, "solved_elapsed_ms": None}
    )
    unsolved = named(full17(grid), UNSOLVED_ROOM)
    return [
        OldRoom(solved, (), SOLVED_LAST_EDIT_AT, None),
        OldRoom(logged, solving_step.entries, LOGGED_LAST_EDIT_AT, LEA_ACCOUNT),
        OldRoom(named(without_time, NO_TIME_ROOM), (), NO_TIME_LAST_EDIT_AT, None),
        OldRoom(unsolved, (), UNSOLVED_LAST_EDIT_AT, None),
    ]


def write_old_database(path: Path, grid: Grid, version: int) -> None:
    """Write the four rooms to a database file of the schema of `version` (0 or 1)."""
    connection = sqlite3.connect(path)
    try:
        connection.executescript(SCHEMA_V0)
        if version == 1:
            connection.execute(SCHEMA_V1_CREATOR_COLUMN)
        for room in old_rooms(grid):
            insert_old_room(connection, room, version)
        connection.execute(f"PRAGMA user_version = {version}")
        connection.commit()
    finally:
        connection.close()


def insert_old_room(
    connection: sqlite3.Connection, room: OldRoom, version: int
) -> None:
    """Insert one room into every table of an old database."""
    state = room.state
    connection.execute("INSERT INTO rooms (code) VALUES (?)", (state.code,))
    connection.execute(
        "INSERT INTO share_tokens (token, code) VALUES (?, ?)",
        (state.share_token, state.code),
    )
    connection.execute(
        "INSERT INTO snapshots (code, seq, state_json) VALUES (?, ?, ?)",
        (state.code, state.seq, state.model_dump_json()),
    )
    for entry in room.log:
        connection.execute(
            "INSERT INTO log (code, seq, entry_json) VALUES (?, ?, ?)",
            (state.code, entry.event.seq, entry.model_dump_json()),
        )
    connection.execute(
        "INSERT INTO room_times (code, created_at, last_edit_at) VALUES (?, ?, ?)",
        (state.code, state.created_at, room.last_edit_at),
    )
    if version == 1:
        connection.execute(
            "UPDATE room_times SET creator_account_id = ? WHERE code = ?",
            (room.creator, state.code),
        )


def unchanged_rows(path: Path, version: int) -> list[list[tuple[object, ...]]]:
    """The rows a migration leaves as they were, one list per query."""
    queries = list(UNCHANGED_QUERIES)
    if version == 1:
        queries.append(CREATOR_QUERY)
    return [select_rows(path, query) for query in queries]


def migrate(path: Path) -> None:
    """Open the database with a `RoomStore`, which migrates it, and close it."""
    store = RoomStore(path)
    store.close()


@pytest.mark.parametrize("version", [1, 0])
def test_ac13_an_old_database_opens_at_version_2_with_the_solve_times(
    tmp_path: Path, fx01_grid: Grid, version: int
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, version)
    assert schema_version(path) == version

    migrate(path)

    assert schema_version(path) == 2
    assert stored_solve_time(path, SOLVED_ROOM) == SOLVED_AT
    assert stored_solve_time(path, LOGGED_ROOM) == LOGGED_SOLVED_AT
    assert stored_solve_time(path, NO_TIME_ROOM) == NO_TIME_LAST_EDIT_AT
    assert stored_solve_time(path, UNSOLVED_ROOM) is None


@pytest.mark.parametrize("version", [1, 0])
def test_ac13_every_other_row_is_as_it_was(
    tmp_path: Path, fx01_grid: Grid, version: int
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, version)
    before = unchanged_rows(path, version)

    migrate(path)

    assert unchanged_rows(path, version) == before


def test_ac13_a_database_at_version_0_opens_with_the_creator_column_too(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, 0)

    migrate(path)

    for code in [SOLVED_ROOM, LOGGED_ROOM, NO_TIME_ROOM, UNSOLVED_ROOM]:
        assert stored_creator(path, code) is None


def test_ac13_a_database_at_version_1_keeps_its_creators(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, 1)

    migrate(path)

    assert stored_creator(path, LOGGED_ROOM) == LEA_ACCOUNT
    assert stored_creator(path, SOLVED_ROOM) is None


def test_ac13_a_migrated_database_is_not_migrated_again(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, 1)
    migrate(path)
    after_the_first = unchanged_rows(path, 1)

    migrate(path)

    assert schema_version(path) == 2
    assert unchanged_rows(path, 1) == after_the_first
    assert stored_solve_time(path, UNSOLVED_ROOM) is None
    assert stored_solve_time(path, SOLVED_ROOM) == SOLVED_AT


@pytest.mark.parametrize("version", [1, 0])
def test_ac13_each_solved_room_expires_24_hours_after_its_solve_time(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, version: int
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_database(path, fx01_grid, version)
    config = config_with_lives(anonymous_solved=24, creator_solved=24)
    solved_rooms = [
        (SOLVED_ROOM, SOLVED_AT),
        (LOGGED_ROOM, LOGGED_SOLVED_AT),
        (NO_TIME_ROOM, NO_TIME_LAST_EDIT_AT),
    ]
    found: list[tuple[str, bool, bool]] = []

    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=config)
    try:
        for code, solved_at in solved_rooms:
            fake_clock.now = solved_at + 24 * HOUR
            open_at_its_life = registry.room_state(code) is not None
            fake_clock.now = solved_at + 24 * HOUR + 1
            open_after = registry.room_state(code) is not None
            found.append((code, open_at_its_life, open_after))
        unsolved_is_kept = store.has_room(UNSOLVED_ROOM)
    finally:
        registry.close()
        store.close()

    assert found == [
        (SOLVED_ROOM, True, False),
        (LOGGED_ROOM, True, False),
        (NO_TIME_ROOM, True, False),
    ]
    assert unsolved_is_kept is True
