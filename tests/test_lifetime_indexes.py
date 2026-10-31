"""Tests of lobby/lifetime, AC-17: the indexes of `room_times` (migration 3).

A database "at `user_version` 2" is a database that the store made, from which the
test drops the indexes and sets the version back to 2: the tables are the ones of
the store, and nothing depends on how the indexes are named.

The query plans are those of the SQL the store really runs: the test traces the
statements of `codes_created_since` and `codes_created_by` (`trace_new_connections`
of `lifetime_harness`) and asks SQLite for the plan of each one. A plan that reads
an index shows `SEARCH room_times USING ... INDEX`; a scan of the table shows
`SCAN room_times`, even when it walks the index of the primary key.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import schema_version
from lifetime_harness import (
    LEA_ACCOUNT,
    drop_created_indexes,
    plan_scans,
    plan_searches,
    query_plan,
    set_schema_version,
    stored_room,
    table_rows,
    trace_new_connections,
)
from nock.grid import Grid
from nock.store import RoomStore
from spec032_harness import T0, grid_from_text

CREATED_ROOMS = ["AAAAAA", "BBBBBB", "CCCCCC"]
LEAS_ROOM = "BBBBBB"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def add_rooms(store: RoomStore, grid: Grid) -> None:
    """Three rooms created at t0; Lea created the second."""
    for position, code in enumerate(CREATED_ROOMS):
        creator = LEA_ACCOUNT if code == LEAS_ROOM else None
        stored_room(store, grid, code, T0 + 10 + position, creator)


def write_version_2_database(path: Path, grid: Grid) -> None:
    """A database with the three rooms, with no created index, at `user_version` 2."""
    store = RoomStore(path)
    add_rooms(store, grid)
    store.close()
    drop_created_indexes(path)
    set_schema_version(path, 2)
    assert schema_version(path) == 2


class Lookup(NamedTuple):
    """A lookup of the store on `room_times`, and the rows it must give."""

    ask: Callable[[RoomStore], object]
    expected: object


def rooms_created_since_t0(store: RoomStore) -> object:
    """`codes_created_since` for t0, in code-point order."""
    return sorted(store.codes_created_since(T0))


def rooms_of_lea(store: RoomStore) -> object:
    """`codes_created_by` for Lea."""
    return store.codes_created_by(LEA_ACCOUNT)


LOOKUPS = {
    "rooms created since a time": Lookup(
        rooms_created_since_t0, [(code, T0) for code in CREATED_ROOMS]
    ),
    "rooms of a creator": Lookup(rooms_of_lea, [LEAS_ROOM]),
}


def test_ac17_a_version_2_database_opens_at_version_3_with_every_row_as_it_was(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    write_version_2_database(path, fx01_grid)
    before = table_rows(path)

    RoomStore(path).close()

    assert schema_version(path) == 3
    assert table_rows(path) == before
    assert len(before["room_times"]) == len(CREATED_ROOMS)
    assert len(before["snapshots"]) == len(CREATED_ROOMS)


@pytest.mark.parametrize("database", ["new", "migrated from version 2"])
@pytest.mark.parametrize("lookup_name", list(LOOKUPS))
def test_ac17_each_lookup_of_room_times_reads_an_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    database: str,
    lookup_name: str,
) -> None:
    path = tmp_path / "nock.sqlite3"
    statements = trace_new_connections(monkeypatch)
    if database != "new":
        write_version_2_database(path, fx01_grid)
    store = RoomStore(path)
    try:
        if database == "new":
            add_rooms(store, fx01_grid)
        lookup = LOOKUPS[lookup_name]
        first_statement = len(statements)

        found = lookup.ask(store)
        plan = query_plan(path, statements[first_statement:])
    finally:
        store.close()

    assert found == lookup.expected
    assert plan_scans(plan, "room_times") == []
    assert len(plan_searches(plan, "room_times")) == 1
