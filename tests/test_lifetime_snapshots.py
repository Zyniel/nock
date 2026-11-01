"""Tests of lobby/lifetime, AC-18: migration 4 keeps two snapshots per room.

A database "at `user_version` 3" is written by a `RoomStore` and then adjusted with
`sqlite3`, so that its tables are the store's own:

- `R` (`spec034_harness.CODE`): Ana joined and typed up to seq 350 through the
  rules; the store holds its log whole and its first snapshot (seq 0). Snapshots
  at seq 100 and 300 (the states the play had then) and at seq 200 (damaged JSON,
  which no `RoomState` can be read from) are inserted by hand;
- `S`: one snapshot, at seq 0;
- `T`: two snapshots, at seq 0 and 80.

The version is then set to 3. Opening a `RoomStore` migrates the file. The test
reads the file with `sqlite3`. The damaged snapshot is among the rows to delete: a
migration that read or rewrote a snapshot would fail on it, or would leave a trace
of it in the rows that stay.

The shared setup is in `lifetime_harness`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from host_harness import schema_version
from lifetime_harness import select_rows, set_schema_version, table_rows
from nock.grid import Grid
from nock.room import RoomState, new_room
from nock.store import RoomStore
from server_harness import snapshot_seqs
from spec018_harness import letter_cells
from spec032_harness import grid_from_text
from spec034_harness import ANA, CODE, TA, Play, T

OTHER_ROOM = "SSSSSS"
TWO_SNAPSHOTS_ROOM = "TTTTTT"
SNAPSHOT_SEQS = (100, 300)
DAMAGED_SEQ = 200
DAMAGED_JSON = '{"code": "ABC123", "seq": 200, "cells": [broken'
LAST_SEQ = 350
MIDDLE_SEQ = 150
SECOND_SNAPSHOT_SEQ = 80
LETTERS = "QXZ"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def play_room_r(grid: Grid, store: RoomStore) -> Play:
    """Ana joins room R, then types up to seq 350; every step is in the store."""
    cells = letter_cells(grid)
    play = Play(grid, store)
    play.join("Ana", ANA, TA)
    while play.state.seq < LAST_SEQ:
        number = play.state.seq
        row, column = cells[number % len(cells)]
        letter = LETTERS[(number // len(cells)) % len(LETTERS)]
        play.write(ANA, row, column, letter, now=T + number)
    return play


def insert_snapshot(path: Path, code: str, seq: int, state_json: str) -> None:
    """Insert a snapshot row by hand."""
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO snapshots (code, seq, state_json) VALUES (?, ?, ?)",
            (code, seq, state_json),
        )
        connection.commit()
    finally:
        connection.close()


def write_version_3_database(path: Path, grid: Grid) -> Play:
    """Write R, S and T as described in the module's docstring, at version 3."""
    store = RoomStore(path)
    try:
        play = play_room_r(grid, store)
        other = new_room(OTHER_ROOM, grid, T, share_token="share-token-of-s-0001")
        store.create_room(other)
        two = new_room(TWO_SNAPSHOTS_ROOM, grid, T, share_token="share-token-of-t-0001")
        store.create_room(two)
    finally:
        store.close()
    for seq in SNAPSHOT_SEQS:
        insert_snapshot(path, CODE, seq, play.states[seq].model_dump_json())
    insert_snapshot(path, CODE, DAMAGED_SEQ, DAMAGED_JSON)
    second = two.model_copy(update={"seq": SECOND_SNAPSHOT_SEQ})
    insert_snapshot(
        path, TWO_SNAPSHOTS_ROOM, SECOND_SNAPSHOT_SEQ, second.model_dump_json()
    )
    set_schema_version(path, 3)
    return play


def migrate(path: Path) -> None:
    """Open the database with a `RoomStore`, which migrates it, and close it."""
    RoomStore(path).close()


def room_summary(state: RoomState) -> tuple[object, ...]:
    """The seq, the cells and the (id, nickname) of each player of a state."""
    players: list[tuple[str, str]] = []
    for player in state.players:
        players.append((player.player_id, player.nickname))
    return (state.seq, state.cells, players)


def test_ac18_a_version_3_database_opens_at_version_4_with_two_snapshots_of_r(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_version_3_database(path, fx01_grid)
    assert schema_version(path) == 3
    assert snapshot_seqs(path, CODE) == [0, 100, DAMAGED_SEQ, 300]

    migrate(path)

    assert schema_version(path) == 4
    assert snapshot_seqs(path, CODE) == [0, 300]
    assert snapshot_seqs(path, OTHER_ROOM) == [0]
    assert snapshot_seqs(path, TWO_SNAPSHOTS_ROOM) == [0, SECOND_SNAPSHOT_SEQ]


def test_ac18_every_other_row_is_as_it_was(tmp_path: Path, fx01_grid: Grid) -> None:
    path = tmp_path / "old.sqlite3"
    write_version_3_database(path, fx01_grid)
    before = table_rows(path)
    kept_snapshots = []
    for row in before["snapshots"]:
        if row[0] == CODE and row[1] in (100, DAMAGED_SEQ):
            continue
        kept_snapshots.append(row)

    migrate(path)

    after = table_rows(path)
    for table, rows in before.items():
        if table != "snapshots":
            assert after[table] == rows, table
    assert after["snapshots"] == kept_snapshots
    assert len(before["log"]) == LAST_SEQ


def test_ac18_the_latest_state_and_the_state_at_150_read_as_before(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    play = write_version_3_database(path, fx01_grid)
    migrate(path)

    store = RoomStore(path)
    try:
        latest = store.load_room(CODE)
        middle = store.load_room_at(CODE, MIDDLE_SEQ)
    finally:
        store.close()

    assert latest is not None
    assert middle is not None
    assert room_summary(latest) == room_summary(play.states[LAST_SEQ])
    assert room_summary(middle) == room_summary(play.states[MIDDLE_SEQ])


def test_ac18_a_migrated_database_is_not_migrated_again(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_version_3_database(path, fx01_grid)
    migrate(path)
    after_the_first = select_rows(
        path, "SELECT code, seq, state_json FROM snapshots ORDER BY code, seq"
    )

    migrate(path)

    assert schema_version(path) == 4
    assert (
        select_rows(
            path, "SELECT code, seq, state_json FROM snapshots ORDER BY code, seq"
        )
        == after_the_first
    )
