"""SQLite storage of the rooms: an append-only event log and state snapshots.

Each room also has its creation time and its last edit time (spec 032), which
its 30-day life runs from, so that the expired rooms are found without loading
them.

One connection is shared by all threads and every call takes a lock, so the
store is safe to call from several threads. Rooms are independent: the lock is
only held for the duration of one short statement or transaction.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from collections.abc import Sequence
from pathlib import Path

from pydantic import ValidationError

from nock.room import LogEntry, RoomState, is_edit, replay

logger = logging.getLogger(__name__)

_MEMORY_PATH = ":memory:"

# A file written before spec 032 holds the first four tables only; opening it
# adds `room_times` and fills it (see `_add_missing_room_times`).
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
CREATE TABLE IF NOT EXISTS share_tokens (
    token TEXT PRIMARY KEY,
    code TEXT NOT NULL REFERENCES rooms (code)
);
CREATE TABLE IF NOT EXISTS room_times (
    code TEXT PRIMARY KEY REFERENCES rooms (code),
    created_at REAL NOT NULL,
    last_edit_at REAL NOT NULL
);
"""

# _JSON_AS_BYTES: the JSON of a snapshot or a log row is read as bytes, CAST(... AS
# BLOB), and given as such to `model_validate_json`. SQLite would refuse a row whose
# bytes are not UTF-8 text with an error of its own that quotes the row; this way
# such a row, like any row that cannot be read, raises pydantic's ValidationError
# (spec 032).

# What `delete_room` runs, in one transaction: every row of the room, in every
# table, the rows that refer to the room before the room itself.
_ROOM_DELETIONS: tuple[str, ...] = (
    "DELETE FROM log WHERE code = ?",
    "DELETE FROM snapshots WHERE code = ?",
    "DELETE FROM share_tokens WHERE code = ?",
    "DELETE FROM room_times WHERE code = ?",
    "DELETE FROM rooms WHERE code = ?",
)


class RoomStore:
    """Rooms on disk: an append-only event log per room plus state snapshots.

    A plain class (a service, not data). Safe to call from several threads.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create the SQLite database at `path` and create its tables.

        A file written before spec 032 is upgraded: each of its rooms gets its
        creation time and its last edit time. A damaged room of it gets the time
        of the upgrade instead, with a warning, and the store opens all the same.

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
        self._add_missing_room_times()

    def create_room(
        self, state: RoomState, *, last_edit_at: float | None = None
    ) -> None:
        """Record a new room, its share token and `state` as its first snapshot.

        The share token (spec 028) is kept apart, so that `code_for_share_token`
        finds the room. The room's creation time is `state.created_at`.

        Args:
            state: The room's first state.
            last_edit_at: Where the room's last edit time starts (spec 032).
                None: at `state.created_at`.

        Raises:
            ValueError: a room with `state.code` already exists, or another room
                has the share token `state.share_token`.
        """
        start = state.created_at if last_edit_at is None else last_edit_at
        with self._lock:
            if self._room_exists(state.code):
                raise ValueError(f"A room with code {state.code} already exists")
            token = state.share_token
            if token is not None and self._code_of_token(token) is not None:
                raise ValueError(f"A room with share token {token} already exists")
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._connection.execute(
                    "INSERT INTO rooms (code) VALUES (?)", (state.code,)
                )
                self._insert_room_times(state.code, state.created_at, start)
                if token is not None:
                    self._connection.execute(
                        "INSERT INTO share_tokens (token, code) VALUES (?, ?)",
                        (token, state.code),
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

    def code_for_share_token(self, token: str) -> str | None:
        """Return the code of the room created with this share token, or None.

        A room created before spec 028 has no share token, so no token finds it.
        """
        with self._lock:
            return self._code_of_token(token)

    def last_edit_at(self, code: str) -> float | None:
        """Return the room's last edit time, which its 30-day life runs from.

        It starts when the room is created and only edits move it (spec 032).

        Args:
            code: The room.

        Returns:
            The time in seconds since the epoch, or None for an unknown room.
        """
        with self._lock:
            row = self._connection.execute(
                "SELECT last_edit_at FROM room_times WHERE code = ?", (code,)
            ).fetchone()
        if row is None:
            return None
        return float(row[0])

    def expired_codes(self, before: float) -> list[str]:
        """Return the codes of the rooms whose last edit time is less than `before`.

        Args:
            before: A clock time; a room whose last edit time equals it is left
                out.

        Returns:
            The codes, in code-point order.
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT code FROM room_times WHERE last_edit_at < ? ORDER BY code",
                (before,),
            ).fetchall()
        codes: list[str] = []
        for (code,) in rows:
            codes.append(str(code))
        return codes

    def delete_room(self, code: str) -> bool:
        """Delete the room, its snapshots, its log and its share token, at once.

        Everything goes in one transaction (spec 032). This is the one exception
        to the rule that the log is never rewritten or truncated (spec 018).

        Returns:
            True when the room existed. Its code is then free for a new room, and
            `code_for_share_token` of its share token returns None (spec 028).
        """
        with self._lock:
            if not self._room_exists(code):
                return False
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                for statement in _ROOM_DELETIONS:
                    self._connection.execute(statement, (code,))
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            return True

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        """Append `entries` to the log of room `code`, committed before returning.

        In the same transaction, the room's last edit time becomes the largest of
        its current value and the time `at` of each edit among the entries
        (`is_edit`, spec 032): it never goes down.

        Raises:
            ValueError: unknown room, or the entries' seqs are not exactly
                last_seq + 1, last_seq + 2, ... (last_seq: the room's highest
                logged seq, or its first snapshot's seq when the log is empty).
                Nothing is written then.
        """
        if len(entries) == 0:
            return
        latest_edit_at = _latest_edit_time(entries)
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
                if latest_edit_at is not None:
                    # SQLite's MAX of two values: the time never goes down.
                    self._connection.execute(
                        "UPDATE room_times SET last_edit_at = MAX(last_edit_at, ?) "
                        "WHERE code = ?",
                        (latest_edit_at, code),
                    )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    def read_log(self, code: str, after_seq: int = 0) -> list[LogEntry]:
        """Return the logged entries of room `code` with seq > after_seq.

        Returns:
            The entries in seq order. An unknown room gives [].

        Raises:
            pydantic.ValidationError: a stored row is damaged, its bytes not
                being UTF-8 text included.
        """
        # Read as bytes (_JSON_AS_BYTES).
        with self._lock:
            rows = self._connection.execute(
                "SELECT CAST(entry_json AS BLOB) FROM log "
                "WHERE code = ? AND seq > ? ORDER BY seq",
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
            pydantic.ValidationError: a stored row is damaged, its bytes not
                being UTF-8 text included.
        """
        # Read as bytes (_JSON_AS_BYTES).
        with self._lock:
            snapshot_row = self._connection.execute(
                "SELECT CAST(state_json AS BLOB) FROM snapshots WHERE code = ? "
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

    def _code_of_token(self, token: str) -> str | None:
        """Return the code of the room with this share token. The caller locks."""
        row = self._connection.execute(
            "SELECT code FROM share_tokens WHERE token = ?", (token,)
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

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

    def _insert_room_times(
        self, code: str, created_at: float, last_edit_at: float
    ) -> None:
        """Record a room's creation and last edit times. The caller locks."""
        self._connection.execute(
            "INSERT INTO room_times (code, created_at, last_edit_at) "
            "VALUES (?, ?, ?)",
            (code, created_at, last_edit_at),
        )

    def _add_missing_room_times(self) -> None:
        """Give each room that has no times its creation and last edit times.

        Only the rooms of a file written before spec 032 have none. They are
        handled one by one (`_times_of_old_room`), so that a damaged room keeps
        its damage to itself and the store still opens. Called while the store
        opens, so no other thread uses the store yet.
        """
        rows = self._connection.execute(
            "SELECT code FROM rooms WHERE code NOT IN (SELECT code FROM room_times) "
            "ORDER BY code"
        ).fetchall()
        if len(rows) == 0:
            return
        upgrade_time = time.time()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            for (code,) in rows:
                created_at, last_edit_at = self._times_of_old_room(code, upgrade_time)
                self._insert_room_times(code, created_at, last_edit_at)
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def _times_of_old_room(self, code: str, upgrade_time: float) -> tuple[float, float]:
        """Return the creation and last edit times of a room written before spec 032.

        The creation time is the `created_at` of the room's first snapshot, and
        the last edit time the largest `at` of its logged edits, or its creation
        time when it has none.

        A room whose times cannot be computed, since it has no snapshot or one of
        its rows cannot be read, gets `upgrade_time` as both, so that it expires
        30 days later, and a warning names it. Its rows are left as they are.

        Args:
            code: The room.
            upgrade_time: The clock time of the upgrade.

        Returns:
            The creation time, then the last edit time.
        """
        try:
            created_at = self._first_snapshot_time(code)
            log = self.read_log(code)
        except ValidationError:
            # The row's text is not logged: it may hold a resume token (spec 038).
            logger.warning(
                "Room %s has a row that cannot be read: its creation and last "
                "edit times are the time of the upgrade",
                code,
            )
            return upgrade_time, upgrade_time
        if created_at is None:
            logger.warning(
                "Room %s has no snapshot: its creation and last edit times are "
                "the time of the upgrade",
                code,
            )
            return upgrade_time, upgrade_time
        last_edit_at = _latest_edit_time(log)
        if last_edit_at is None:
            last_edit_at = created_at
        return created_at, last_edit_at

    def _first_snapshot_time(self, code: str) -> float | None:
        """Return the `created_at` of the room's first snapshot, None without one.

        Raises:
            pydantic.ValidationError: the snapshot cannot be read.
        """
        # Read as bytes (_JSON_AS_BYTES).
        row = self._connection.execute(
            "SELECT CAST(state_json AS BLOB) FROM snapshots WHERE code = ? "
            "ORDER BY seq LIMIT 1",
            (code,),
        ).fetchone()
        if row is None:
            return None
        first_snapshot = RoomState.model_validate_json(row[0])
        return first_snapshot.created_at


def _latest_edit_time(entries: Sequence[LogEntry]) -> float | None:
    """Return the largest `at` of the edits among `entries`, None when none is one."""
    latest: float | None = None
    for entry in entries:
        if not is_edit(entry):
            continue
        if latest is None or entry.at > latest:
            latest = entry.at
    return latest
