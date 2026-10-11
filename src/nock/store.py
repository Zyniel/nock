"""SQLite storage of the rooms: an append-only event log and state snapshots.

One connection is shared by all threads and every call takes a lock, so the
store is safe to call from several threads. Rooms are independent: the lock is
only held for the duration of one short statement or transaction.
"""

from __future__ import annotations

import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path

from nock.room import LogEntry, RoomState, replay

_MEMORY_PATH = ":memory:"

_TABLES = """
CREATE TABLE IF NOT EXISTS rooms (
    code TEXT PRIMARY KEY
);
CREATE TABLE IF NOT EXISTS snapshots (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
CREATE TABLE IF NOT EXISTS log (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    entry_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
"""


class RoomStore:
    """Rooms on disk: an append-only event log per room plus state snapshots.

    A plain class (a service, not data). Safe to call from several threads.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create the SQLite database at `path` and create its tables.

        Args:
            path: A file path, or ":memory:" for an in-memory database. A file
                database uses journal_mode WAL and synchronous FULL.
        """
        self._lock = threading.Lock()
        self._is_closed = False
        # Autocommit mode: the transactions are written out with BEGIN/COMMIT.
        self._connection = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None
        )
        if str(path) != _MEMORY_PATH:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.executescript(_TABLES)

    def create_room(self, state: RoomState) -> None:
        """Record a new room and `state` as its first snapshot.

        Raises:
            ValueError: a room with `state.code` already exists.
        """
        with self._lock:
            if self._room_exists(state.code):
                raise ValueError(f"A room with code {state.code} already exists")
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    "INSERT INTO rooms (code) VALUES (?)", (state.code,)
                )
                self._insert_snapshot(state)
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    def has_room(self, code: str) -> bool:
        """Tell whether room `code` exists in the store."""
        with self._lock:
            return self._room_exists(code)

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        """Append `entries` to the log of room `code`, committed before returning.

        Raises:
            ValueError: unknown room, or the entries' seqs are not exactly
                last_seq + 1, last_seq + 2, ... (last_seq: the room's highest
                logged seq, or its first snapshot's seq when the log is empty).
                Nothing is written then.
        """
        if len(entries) == 0:
            return
        with self._lock:
            if not self._room_exists(code):
                raise ValueError(f"Unknown room {code}")
            expected_seq = self._last_seq(code) + 1
            for entry in entries:
                if entry.event.seq != expected_seq:
                    raise ValueError(
                        f"Room {code}: expected the entry with seq {expected_seq}, "
                        f"got seq {entry.event.seq}"
                    )
                expected_seq += 1
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                for entry in entries:
                    self._connection.execute(
                        "INSERT INTO log (code, seq, entry_json) VALUES (?, ?, ?)",
                        (code, entry.event.seq, entry.model_dump_json()),
                    )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    def read_log(self, code: str, after_seq: int = 0) -> list[LogEntry]:
        """Return the logged entries of room `code` with seq > after_seq.

        Returns:
            The entries in seq order. An unknown room gives [].
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT entry_json FROM log WHERE code = ? AND seq > ? ORDER BY seq",
                (code, after_seq),
            ).fetchall()
        entries: list[LogEntry] = []
        for (entry_json,) in rows:
            entries.append(LogEntry.model_validate_json(entry_json))
        return entries

    def save_snapshot(self, state: RoomState) -> None:
        """Store `state` as a snapshot of room `state.code` at `state.seq`.

        A snapshot at the same seq is replaced. The log is left as it is.

        Raises:
            ValueError: the room is unknown.
        """
        with self._lock:
            if not self._room_exists(state.code):
                raise ValueError(f"Unknown room {state.code}")
            self._insert_snapshot(state)

    def load_room(self, code: str) -> RoomState | None:
        """Return the state of room `code`, or None when it is unknown.

        The state is the snapshot with the highest seq, then `replay` of every
        logged entry after it, in order.

        Raises:
            pydantic.ValidationError: a stored row is damaged.
        """
        with self._lock:
            snapshot_row = self._connection.execute(
                "SELECT state_json FROM snapshots WHERE code = ? "
                "ORDER BY seq DESC LIMIT 1",
                (code,),
            ).fetchone()
        if snapshot_row is None:
            return None
        state = RoomState.model_validate_json(snapshot_row[0])
        for entry in self.read_log(code, after_seq=state.seq):
            state = replay(state, entry)
        return state

    def close(self) -> None:
        """Close the database. Idempotent."""
        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
            self._connection.close()

    def _room_exists(self, code: str) -> bool:
        """Tell whether the room is recorded. The caller holds the lock."""
        row = self._connection.execute(
            "SELECT 1 FROM rooms WHERE code = ?", (code,)
        ).fetchone()
        return row is not None

    def _last_seq(self, code: str) -> int:
        """Return the highest logged seq, or the first snapshot's seq.

        The caller holds the lock and the room exists.
        """
        log_row = self._connection.execute(
            "SELECT MAX(seq) FROM log WHERE code = ?", (code,)
        ).fetchone()
        if log_row[0] is not None:
            return int(log_row[0])
        snapshot_row = self._connection.execute(
            "SELECT MIN(seq) FROM snapshots WHERE code = ?", (code,)
        ).fetchone()
        return int(snapshot_row[0])

    def _insert_snapshot(self, state: RoomState) -> None:
        """Write a snapshot, replacing the one at the same seq. Caller locks."""
        self._connection.execute(
            "INSERT OR REPLACE INTO snapshots (code, seq, state_json) "
            "VALUES (?, ?, ?)",
            (state.code, state.seq, state.model_dump_json()),
        )
