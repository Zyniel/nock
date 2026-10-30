"""Shared setup of the tests of platform/server about the rooms in memory (AC-23,
AC-24) and of the tests that read which rooms are live.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_server_*.py`:

- `test_server_rooms_in_memory.py`: AC-23 and AC-24, over the room socket, with the
  app of `host_harness` (a fake clock, the rooms' store on a file).
- `test_server_engine_time.py`: rule 20, which has its own setup.
- `test_server_socket_responsiveness.py`: AC-25, a socket whose lookup is slow
  (`SlowConnectRegistry`) delays nobody. It measures durations, so it runs on its
  own (`SERIAL_TEST_FILES`).
- `test_server_socket_loads.py`: AC-26, the store reads of a socket's lookup
  (`CountingStore`).

A room is live when `RoomRegistry.live_codes()` holds its code. `state_of` (and
every `room_state` lookup) loads a room and so makes it live: a test that reads
whether a room is live reads the room with `peek_room` or from the store, never
with `state_of`, before it has asked.

The store's latest snapshot is read from the database file with a connection of
its own (`snapshots` has one row per saved seq).
"""

from __future__ import annotations

import asyncio
import contextlib
import sqlite3
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from fastapi.testclient import TestClient

from nock.catalogue import Catalogue
from nock.hub import RoomConnection, RoomRegistry
from nock.room import RoomConfig, RoomState
from nock.server import create_app
from nock.store import RoomStore
from spec033_harness import wait_for

SNAPSHOT_FAILURE_PAUSE_SECONDS = 0.3
HOLD_LIMIT_SECONDS = 10.0
CONNECT_DELAY_SECONDS = 1.0


@contextlib.contextmanager
def serving(
    store: RoomStore,
    clock: Callable[[], float],
    catalogue: Catalogue,
    config: RoomConfig,
) -> Iterator[tuple[TestClient, RoomRegistry]]:
    """Run the app on a registry over `store`, on `clock`; yield the client and it.

    The registry is closed on the way out; the store is the test's to close.
    """
    registry = RoomRegistry(clock=clock, store=store, config=config)
    try:
        app = create_app(rooms=registry, catalogue=catalogue)
        with TestClient(app) as client:
            yield client, registry
    finally:
        registry.close()


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
    """A file store whose `save_snapshot` the test can make fail or hold, and counts.

    While `hold_next_snapshot` is set, the next `save_snapshot` sets
    `snapshot_held` and waits (bounded) for `release_snapshot`.

    `saved_seqs` holds the seq of each snapshot saved through `save_snapshot`
    (the room's first snapshot is written by `create_room` and is not in it).
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.fail_snapshots = False
        self.snapshot_failed = threading.Event()
        self.hold_next_snapshot = threading.Event()
        self.snapshot_held = threading.Event()
        self.release_snapshot = threading.Event()
        self.saved_seqs: list[int] = []

    def save_snapshot(self, state: RoomState) -> None:
        """Save the snapshot, or raise `OSError` while `fail_snapshots` is set."""
        if self.fail_snapshots:
            self.snapshot_failed.set()
            raise OSError("the disk is full")
        if self.hold_next_snapshot.is_set():
            self.hold_next_snapshot.clear()
            self.snapshot_held.set()
            self.release_snapshot.wait(HOLD_LIMIT_SECONDS)
        super().save_snapshot(state)
        self.saved_seqs.append(state.seq)


class SlowConnectRegistry(RoomRegistry):
    """A registry whose `connect` takes `CONNECT_DELAY_SECONDS` for some rooms.

    `slow_codes` holds the rooms concerned; the test fills it once the rooms
    exist. While a slow lookup waits, `connect_started` is set, so that a test
    sends its other requests only once the wait has begun, in whatever thread or
    loop the socket route runs `connect`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.slow_codes: set[str] = set()
        self.connect_started = threading.Event()

    def connect(
        self,
        code: str,
        account_id: str | None = None,
        *,
        owner_loop: asyncio.AbstractEventLoop | None = None,
    ) -> RoomConnection | None:
        """Wait when the room is slow, then open the connection as usual."""
        if code in self.slow_codes:
            self.connect_started.set()
            time.sleep(CONNECT_DELAY_SECONDS)
        return super().connect(code, account_id, owner_loop=owner_loop)


class CountingStore(RoomStore):
    """A file store that records each `load_room` read that found a room.

    `loaded` holds the code of each such read, in order; a read of an unknown
    code finds nothing and is not recorded. A room is loaded when the store
    returns its snapshot with the log replayed.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.loaded: list[str] = []

    def load_room(self, code: str) -> RoomState | None:
        """Load the room as usual and record the read when it found the room."""
        state = super().load_room(code)
        if state is not None:
            self.loaded.append(code)
        return state
