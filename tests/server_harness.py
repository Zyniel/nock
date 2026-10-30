"""Shared setup of the tests of platform/server about the rooms in memory (AC-23,
AC-24) and of the tests that read which rooms are live.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_server_*.py`:

- `test_server_rooms_in_memory.py`: AC-23 and AC-24, over the room socket, with the
  app of `host_harness` (a fake clock, the rooms' store on a file).
- `test_server_engine_time.py`: rule 20, which has its own setup.

A room is live when `RoomRegistry.live_codes()` holds its code. `state_of` (and
every `room_state` lookup) loads a room and so makes it live: a test that reads
whether a room is live reads the room with `peek_room` or from the store, never
with `state_of`, before it has asked.

The store's latest snapshot is read from the database file with a connection of
its own (`snapshots` has one row per saved seq).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path

from nock.hub import RoomRegistry
from nock.room import RoomState
from nock.store import RoomStore
from spec033_harness import wait_for

SNAPSHOT_FAILURE_PAUSE_SECONDS = 0.3


def wait_until_live(registry: RoomRegistry, code: str) -> None:
    """Wait (bounded, real time) until the room `code` is live."""
    wait_for(lambda: code in registry.live_codes(), f"room {code} to be live")


def wait_until_not_live(registry: RoomRegistry, code: str) -> None:
    """Wait (bounded, real time) until the room `code` is not live."""
    wait_for(lambda: code not in registry.live_codes(), f"room {code} to leave memory")


def latest_snapshot_seq(database_path: Path, code: str) -> int:
    """The seq of the store's latest snapshot of the room, read from the file."""
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT MAX(seq) FROM snapshots WHERE code = ?", (code,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, f"no snapshot of {code}"
    assert row[0] is not None, f"no snapshot of {code}"
    return int(row[0])


def last_logged_seq(store: RoomStore, code: str) -> int:
    """The seq of the last log entry of the room."""
    log = store.read_log(code)
    assert len(log) > 0, f"the log of {code} is empty"
    return log[-1].event.seq


class SnapshotStore(RoomStore):
    """A file store whose `save_snapshot` the test can make fail, and that counts.

    `saved_seqs` holds the seq of each snapshot saved through `save_snapshot`
    (the room's first snapshot is written by `create_room` and is not in it).
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.fail_snapshots = False
        self.snapshot_failed = threading.Event()
        self.saved_seqs: list[int] = []

    def save_snapshot(self, state: RoomState) -> None:
        """Save the snapshot, or raise `OSError` while `fail_snapshots` is set."""
        if self.fail_snapshots:
            self.snapshot_failed.set()
            raise OSError("the disk is full")
        super().save_snapshot(state)
        self.saved_seqs.append(state.seq)
