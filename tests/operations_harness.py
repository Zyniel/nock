"""Shared setup of the tests of admin/operations, AC-22 to AC-25: the WAL checkpoint.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_operations_*.py`:

- `test_operations_checkpoint.py`: AC-22, AC-23 and AC-25's busy timeout, with no
  timing: `checkpoint_wal` on a connection that fakes its answers, and the five
  deletions and erasures that call it.
- `test_operations_checkpoint_busy.py`: AC-24 and AC-25, a second connection that
  holds a read open, and the time bounds. It measures durations (a busy timeout
  of 5 s against a bound of 1 s), so it runs in the serial pass
  (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

The same helpers serve `tests/test_account_erasure_busy.py` (account/account
AC-22). This module holds the two ways to look at a busy database: a second
connection that holds a read open, which makes a `TRUNCATE` checkpoint report
busy, and the size of the WAL file.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from collections.abc import Iterator
from pathlib import Path

import pytest

from nock.store import RoomStore
from spec032_harness import Run

LOGGER_PREFIX = "nock"


@contextlib.contextmanager
def holding_a_read(database_path: Path) -> Iterator[None]:
    """Hold a read transaction open on the database file, on a connection of its own.

    A `TRUNCATE` checkpoint cannot empty the WAL while a reader uses it, so every
    checkpoint of the other connections to the file is busy until the block ends.
    """
    reader = sqlite3.connect(database_path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM rooms").fetchall()
        yield
    finally:
        reader.close()


def wal_size(database_path: Path) -> int:
    """The size in bytes of the WAL file, 0 for a WAL that was emptied or is absent."""
    wal_path = database_path.with_name(database_path.name + "-wal")
    if not wal_path.exists():
        return 0
    return wal_path.stat().st_size


def write_room(store: RoomStore, room: Run) -> None:
    """Write a played room to the store: first state, log, then its last state."""
    store.create_room(room.initial)
    store.append(room.initial.code, room.log)
    store.save_snapshot(room.state)


def warnings_logged(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The records captured at WARNING or above, whatever logger wrote them."""
    records: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.levelno >= logging.WARNING:
            records.append(record)
    return records
