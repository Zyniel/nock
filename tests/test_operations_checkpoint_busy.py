"""Tests of admin/operations, AC-24 and AC-25: a checkpoint that stays busy.

A second connection to the database file holds a read transaction open
(`holding_a_read` of `operations_harness`), which makes a `TRUNCATE` checkpoint
report busy. These tests measure real time, so the file runs in the serial pass
(`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`):

- AC-25: `checkpoint_wal` on a connection whose busy timeout is 5 s returns False
  in under a second and leaves the 5 s timeout in place.
- AC-24: a room expires, a lookup deletes it while the file is held; the lookup
  returns in under a second, the room is gone, one WARNING is logged and the WAL is
  not empty. Once the reader is gone, the next sweep, which deletes nothing,
  empties the WAL and no byte of the room stays in the files.

The deleted room is the one of spec 038 AC-4's helper: Zélie and Bob, who chat
`chat-busy-6610`. Time is measured with `time.monotonic`, in real seconds, and the
rooms' clock is the fake clock of `conftest`.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path

import pytest

import nock.store
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Chat
from nock.store import RoomStore
from operations_harness import (
    LOGGER_PREFIX,
    holding_a_read,
    wal_size,
    warnings_logged,
    write_room,
)
from spec017_harness import FakeClock
from spec032_harness import LIFE, NO_TICK_CONFIG, T0, Run, grid_from_text
from spec033_harness import database_bytes, strings_in

CODE_A = "QJ7WXK"  # occurs nowhere else in the file
CHAT = "chat-busy-6610"
LOOKUP_BOUND_SECONDS = 1.0
BUSY_TIMEOUT_SECONDS = 5.0
BUSY_TIMEOUT_MS = 5000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def test_ac25_a_checkpoint_blocked_by_a_reader_gives_up_at_once_and_keeps_the_timeout(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nock.sqlite3"
    connection = sqlite3.connect(
        path, timeout=BUSY_TIMEOUT_SECONDS, isolation_level=None
    )
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("CREATE TABLE rooms (code TEXT)")
        connection.execute("INSERT INTO rooms (code) VALUES ('AAAAAA')")
        with holding_a_read(path):
            connection.execute("INSERT INTO rooms (code) VALUES ('BBBBBB')")
            started = time.monotonic()
            emptied = nock.store.checkpoint_wal(connection)
            elapsed = time.monotonic() - started
        timeout_row = connection.execute("PRAGMA busy_timeout").fetchone()
    finally:
        connection.close()

    assert emptied is False
    assert elapsed < LOOKUP_BOUND_SECONDS
    assert timeout_row[0] == BUSY_TIMEOUT_MS


def test_ac24_a_lookup_deletes_an_expired_room_without_waiting_for_a_reader(
    tmp_path: Path,
    fx01_grid: Grid,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "nock.sqlite3"
    room = Run(fx01_grid, code=CODE_A, grid_number=None, config=NO_TICK_CONFIG)
    room.join_new("Zélie", "pZ", "zelie-resume-token-0001", T0)
    room.join_new("Bob", "pB", "bob-resume-token-000002", T0)
    room.send("pZ", Chat(text=CHAT), T0 + 1)
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=NO_TICK_CONFIG)
    try:
        write_room(store, room)
        assert strings_in(database_bytes(path), [CHAT, CODE_A]) == [CHAT, CODE_A]
        fake_clock.now = T0 + LIFE + 1
        caplog.set_level(logging.WARNING, logger=LOGGER_PREFIX)

        with holding_a_read(path):
            started = time.monotonic()
            found = registry.room_state(CODE_A)
            elapsed = time.monotonic() - started
            code_is_known = store.has_room(CODE_A)
            wal_while_held = wal_size(path)
            warnings = warnings_logged(caplog)

        swept = registry.expire_rooms()
        wal_after_sweep = wal_size(path)
        left_in_files = strings_in(database_bytes(path), [CHAT, CODE_A])
    finally:
        registry.close()
        store.close()

    assert found is None
    assert code_is_known is False
    assert elapsed < LOOKUP_BOUND_SECONDS
    assert [record.levelno for record in warnings] == [logging.WARNING]
    assert warnings[0].name.startswith(LOGGER_PREFIX)
    assert wal_while_held > 0
    assert swept == []
    assert wal_after_sweep == 0
    assert left_in_files == []
