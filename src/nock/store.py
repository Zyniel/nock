"""SQLite storage of the rooms: an append-only event log and state snapshots.

Each room also has its creation time, its last edit time and its solve time
(`lobby/lifetime.md`), which its room life runs from, so that the expired rooms
are found without loading them, and its creator, the account that created it
(`lobby/host.md` rule 11), kept in `room_times` only: the snapshots hold no
creator.

The table `overrides` holds the settings saved from `/ops`
(`admin/overrides.md` rule 7); a room's deletion never touches it.

One connection is shared by all threads and every call takes a lock, so the
store is safe to call from several threads. Rooms are independent: the lock is
only held for the duration of one short statement or transaction.

A deleted room leaves no copy behind (spec 038): SQLite overwrites deleted rows
with zeros (`secure_delete`), and in a file database a checkpoint then empties
the write-ahead log (`checkpoint_wal`, `admin/operations.md` rule 20). A deletion
outside a sweep ends with one, and so does erasing a player's nickname (spec
033); a sweep deletes its rooms without one and calls `RoomStore.checkpoint`
once after them.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from collections.abc import Sequence
from pathlib import Path

from nock.protocol import GridSolved
from nock.room import (
    LogEntry,
    RoomState,
    RoomTimes,
    entry_with_player_erased,
    is_edit,
    replay,
    with_player_erased,
)

logger = logging.getLogger(__name__)

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
CREATE TABLE IF NOT EXISTS share_tokens (
    token TEXT PRIMARY KEY,
    code TEXT NOT NULL REFERENCES rooms (code)
);
CREATE TABLE IF NOT EXISTS room_times (
    code TEXT PRIMARY KEY REFERENCES rooms (code),
    created_at REAL NOT NULL,
    last_edit_at REAL NOT NULL,
    creator_account_id TEXT,
    solved_at REAL
);
CREATE TABLE IF NOT EXISTS overrides (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
"""

# `PRAGMA user_version` of a database that has the creator column (1), the solve
# time column (2), the indexes of `room_times` (3) and two snapshots per room (4).
_SCHEMA_VERSION = 4
# The version that brought the solve times, which a database below it is given.
_SOLVE_TIME_VERSION = 2
# The columns a database below that version may lack, with their SQL types.
_ADDED_COLUMNS: dict[str, str] = {"creator_account_id": "TEXT", "solved_at": "REAL"}

# The indexes of `room_times` (version 3): the rooms created since a time and the
# rooms of a creator. `IF NOT EXISTS`, since a store opens over a database that
# may have them.
_ROOM_TIMES_INDEXES: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS room_times_by_created_at ON room_times (created_at)",
    "CREATE INDEX IF NOT EXISTS room_times_by_creator "
    "ON room_times (creator_account_id)",
)

# A checkpoint is tried this many times before it is given up (rule 20).
_CHECKPOINT_TRIES = 2

# The columns `RoomTimes` is read from, in the order `_room_times_of` expects.
_ROOM_TIMES_COLUMNS = "code, last_edit_at, solved_at, creator_account_id"

# What `delete_room` runs, in one transaction: every row of the room, in every
# table, the rows that refer to the room before the room itself.
_ROOM_DELETIONS: tuple[str, ...] = (
    "DELETE FROM log WHERE code = ?",
    "DELETE FROM snapshots WHERE code = ?",
    "DELETE FROM share_tokens WHERE code = ?",
    "DELETE FROM room_times WHERE code = ?",
    "DELETE FROM rooms WHERE code = ?",
)


def checkpoint_wal(connection: sqlite3.Connection) -> bool:
    """Copy the write-ahead log into the database file and empty it.

    Runs `PRAGMA wal_checkpoint(TRUNCATE)` (`admin/operations.md` rule 20). A try
    never waits on SQLite's busy handler: the connection's busy timeout is 0
    during the checkpoint and is restored after it. A checkpoint that reports
    busy is tried once more at once; when it is busy again, one WARNING is logged
    and the log keeps the deleted rows' old pages until a later checkpoint.

    Args:
        connection: A connection to a database file in WAL mode.

    Returns:
        True when the log was emptied, False when it stayed busy after the second
        try.
    """
    timeout_row = connection.execute("PRAGMA busy_timeout").fetchone()
    saved_timeout_ms = int(timeout_row[0])
    connection.execute("PRAGMA busy_timeout = 0")
    try:
        for _ in range(_CHECKPOINT_TRIES):
            result_row = connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            ).fetchone()
            is_busy = int(result_row[0]) != 0
            if not is_busy:
                return True
    finally:
        connection.execute(f"PRAGMA busy_timeout = {saved_timeout_ms}")
    logger.warning(
        "The write-ahead log checkpoint stayed busy after %d tries; "
        "the next one will empty it",
        _CHECKPOINT_TRIES,
    )
    return False


class RoomStore:
    """Rooms on disk: an append-only event log per room plus state snapshots.

    A plain class (a service, not data). Safe to call from several threads.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create the SQLite database at `path` and create its tables.

        Args:
            path: A file path, or ":memory:" for an in-memory database. A file
                database uses journal_mode WAL and synchronous FULL. Both
                overwrite deleted rows with zeros (secure_delete, spec 038).
        """
        self._lock = threading.Lock()
        self._is_closed = False
        self._is_file = str(path) != _MEMORY_PATH
        # Autocommit mode: the transactions are written out with BEGIN/COMMIT.
        self._connection = sqlite3.connect(
            str(path), check_same_thread=False, isolation_level=None
        )
        if self._is_file:
            self._connection.execute("PRAGMA journal_mode = WAL")
            self._connection.execute("PRAGMA synchronous = FULL")
        self._connection.execute("PRAGMA secure_delete = ON")
        self._connection.executescript(_TABLES)
        self._migrate()

    @property
    def is_durable(self) -> bool:
        """Whether the database is a file, so that its rows survive a restart."""
        return self._is_file

    def read_overrides(self) -> list[tuple[str, object]]:
        """Return the rows of the table `overrides` (`admin/overrides.md` rule 7).

        Returns:
            One (name, value) per row, by name. The value is what the row holds,
            which may be anything SQLite stored: the caller checks it.
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT name, value FROM overrides ORDER BY name"
            ).fetchall()
        saved: list[tuple[str, object]] = []
        for name, value in rows:
            saved.append((str(name), value))
        return saved

    def save_override(self, name: str, value: int) -> None:
        """Save the override of a setting, replacing the one it had.

        Args:
            name: The setting.
            value: Its new override.
        """
        with self._lock:
            self._connection.execute(
                "INSERT OR REPLACE INTO overrides (name, value) VALUES (?, ?)",
                (name, value),
            )

    def delete_override(self, name: str) -> None:
        """Remove the override of a setting; nothing happens when it has none."""
        with self._lock:
            self._connection.execute("DELETE FROM overrides WHERE name = ?", (name,))

    def create_room(
        self, state: RoomState, *, last_edit_at: float | None = None
    ) -> None:
        """Record a new room, its share token and `state` as its first snapshot.

        The share token (spec 028) is kept apart, so that `code_for_share_token`
        finds the room. The room's creation time is `state.created_at`. A room
        that is already solved has its last edit time as its solve time.

        Args:
            state: The room's first state.
            last_edit_at: Where the room's last edit time starts (spec 032).
                None: at `state.created_at`.

        Raises:
            ValueError: a room with `state.code` already exists, or another room
                has the share token `state.share_token`.
        """
        start = state.created_at if last_edit_at is None else last_edit_at
        # A solved room's solve time equals its last edit time (`lobby/lifetime.md`
        # rule 2).
        solved_at = start if state.solved else None
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
                self._connection.execute(
                    "INSERT INTO room_times "
                    "(code, created_at, last_edit_at, creator_account_id, solved_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        state.code,
                        state.created_at,
                        start,
                        state.creator_account_id,
                        solved_at,
                    ),
                )
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
        """Return the room's last edit time, which its room life runs from.

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

    def read_room_times(self) -> list[RoomTimes]:
        """Return the times and the creator of every room.

        Returns:
            One `RoomTimes` per room, in code-point order.
        """
        with self._lock:
            rows = self._connection.execute(
                f"SELECT {_ROOM_TIMES_COLUMNS} FROM room_times ORDER BY code"
            ).fetchall()
        all_times: list[RoomTimes] = []
        for row in rows:
            all_times.append(_room_times_of(row))
        return all_times

    def room_times(self, code: str) -> RoomTimes | None:
        """Return the times and the creator of a room, None for an unknown room."""
        with self._lock:
            row = self._connection.execute(
                f"SELECT {_ROOM_TIMES_COLUMNS} FROM room_times WHERE code = ?",
                (code,),
            ).fetchone()
        if row is None:
            return None
        return _room_times_of(row)

    def codes_created_since(self, since: float) -> list[tuple[str, float]]:
        """Return the rooms created at `since` or later, with their creation times.

        The operator's dashboard reads its rooms with it (spec 038): one read
        gives each room with its creation time, so no room can go between two
        reads.

        Args:
            since: A clock time; a room created exactly then is included.

        Returns:
            A `(code, created_at)` pair per room, in no particular order.
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT code, created_at FROM room_times WHERE created_at >= ?",
                (since,),
            ).fetchall()
        pairs: list[tuple[str, float]] = []
        for code, created_at in rows:
            pairs.append((str(code), float(created_at)))
        return pairs

    def codes_created_by(self, account_id: str) -> list[str]:
        """Return the codes of the rooms whose creator is the account.

        Args:
            account_id: The account.

        Returns:
            The codes, in code-point order.
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT code FROM room_times WHERE creator_account_id = ? "
                "ORDER BY code",
                (account_id,),
            ).fetchall()
        codes: list[str] = []
        for (code,) in rows:
            codes.append(str(code))
        return codes

    def delete_room(self, code: str, *, checkpoint: bool = True) -> bool:
        """Delete the room, its snapshots, its log and its share token, at once.

        Everything goes in one transaction (spec 032). This is the one exception
        to the rule that the log is never rewritten or truncated (spec 018).
        The deleted rows are overwritten with zeros, and in a file database the
        write-ahead log is then checkpointed (`checkpoint_wal`); a busy
        checkpoint leaves it to a later one (spec 038).

        Args:
            code: The room.
            checkpoint: False for a sweep's deletion, which runs no checkpoint:
                the sweep calls `checkpoint` once after its last deletion.

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
            if checkpoint and self._is_file:
                checkpoint_wal(self._connection)
            return True

    def checkpoint(self) -> None:
        """Empty the write-ahead log of a file database; nothing in memory.

        A sweep calls it once after its deletions, and when it deleted nothing,
        so that a log left by a busy checkpoint is emptied at the latest by the
        next sweep. A busy checkpoint is logged and does not fail
        (`checkpoint_wal`).
        """
        if not self._is_file:
            return
        with self._lock:
            checkpoint_wal(self._connection)

    def erase_player(self, code: str, player_id: str) -> bool:
        """Replace the nickname of `player_id` with FORMER_PLAYER_NICKNAME.

        In every stored snapshot of the room (its record in `players` or
        `past_players`) and in every logged `player_joined` of that player, in
        one transaction (spec 033). Seqs, order and everything else stay. This
        is the second exception to the rule that the log is never rewritten
        (spec 018). In a file database the write-ahead log is then checkpointed
        (`checkpoint_wal`); a busy checkpoint leaves it to a later one.

        Args:
            code: The room.
            player_id: The player whose account was deleted.

        Returns:
            True when the room exists.
        """
        with self._lock:
            if not self._room_exists(code):
                return False
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._erase_in_snapshots(code, player_id)
                self._erase_in_log(code, player_id)
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            if self._is_file:
                checkpoint_wal(self._connection)
            return True

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        """Append `entries` to the log of room `code`, committed before returning.

        In the same transaction, the room's last edit time becomes the largest of
        its current value and the time `at` of each edit among the entries
        (`is_edit`, spec 032): it never goes down. A `grid_solved` among the
        entries gives the room its solve time, its `at`, unless it has one.

        Raises:
            ValueError: unknown room, or the entries' seqs are not exactly
                last_seq + 1, last_seq + 2, ... (last_seq: the room's highest
                logged seq, or its first snapshot's seq when the log is empty).
                Nothing is written then.
        """
        if len(entries) == 0:
            return
        latest_edit_at = _latest_edit_time(entries)
        solve_time = _logged_solve_time(entries)
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
                if solve_time is not None:
                    self._connection.execute(
                        "UPDATE room_times SET solved_at = COALESCE(solved_at, ?) "
                        "WHERE code = ?",
                        (solve_time, code),
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

        A snapshot at the same seq is replaced. The log is left as it is. The
        room keeps two snapshots, the ones at its lowest and highest seq: the
        others are deleted in the same transaction (`platform/server.md` rule 4).

        Raises:
            ValueError: the room is unknown.
        """
        with self._lock:
            if not self._room_exists(state.code):
                raise ValueError(f"Unknown room {state.code}")
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._insert_snapshot(state)
                self._keep_first_and_newest_snapshots(state)
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

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
            creator = self._creator_of(code)
        if snapshot_row is None:
            return None
        state = RoomState.model_validate_json(snapshot_row[0])
        state = state.model_copy(update={"creator_account_id": creator})
        for entry in self.read_log(code, after_seq=state.seq):
            state = replay(state, entry)
        return state

    def load_room_at(self, code: str, seq: int) -> RoomState | None:
        """Return the room's state just after its event `seq`.

        The snapshot with the highest seq at most `seq`, then `replay` of the
        logged entries after it whose seq is at most `seq`. So a `seq` at or above
        the room's last logged seq gives the room's latest stored state, as
        `load_room` does.

        Returns:
            The state, or None when no snapshot of the room has a seq at most
            `seq`: an unknown room, or a room whose first snapshot came after
            `seq` (only a room added in a later state, as `add_room` allows).

        Raises:
            pydantic.ValidationError: a stored row is damaged.
        """
        with self._lock:
            snapshot_row = self._connection.execute(
                "SELECT state_json FROM snapshots WHERE code = ? AND seq <= ? "
                "ORDER BY seq DESC LIMIT 1",
                (code, seq),
            ).fetchone()
            creator = self._creator_of(code)
        if snapshot_row is None:
            return None
        state = RoomState.model_validate_json(snapshot_row[0])
        state = state.model_copy(update={"creator_account_id": creator})
        for entry in self.read_log(code, after_seq=state.seq):
            if entry.event.seq > seq:
                break
            state = replay(state, entry)
        return state

    def close(self) -> None:
        """Close the database. Idempotent."""
        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
            self._connection.close()

    def _erase_in_snapshots(self, code: str, player_id: str) -> None:
        """Rewrite each snapshot of the room with the player erased. Caller locks."""
        rows = self._connection.execute(
            "SELECT seq, state_json FROM snapshots WHERE code = ?", (code,)
        ).fetchall()
        for seq, state_json in rows:
            state = RoomState.model_validate_json(state_json)
            erased = with_player_erased(state, player_id)
            self._connection.execute(
                "UPDATE snapshots SET state_json = ? WHERE code = ? AND seq = ?",
                (_snapshot_json(erased), code, seq),
            )

    def _erase_in_log(self, code: str, player_id: str) -> None:
        """Rewrite each logged `player_joined` of the player. Caller locks."""
        rows = self._connection.execute(
            "SELECT seq, entry_json FROM log WHERE code = ?", (code,)
        ).fetchall()
        for seq, entry_json in rows:
            entry = LogEntry.model_validate_json(entry_json)
            erased = entry_with_player_erased(entry, player_id)
            if erased is None:
                continue
            self._connection.execute(
                "UPDATE log SET entry_json = ? WHERE code = ? AND seq = ?",
                (erased.model_dump_json(), code, seq),
            )

    def _migrate(self) -> None:
        """Bring a database below `_SCHEMA_VERSION` to it, once, at open.

        The missing columns of `room_times` are added, each solved room gets its
        solve time (see `_store_solve_times`), the missing indexes are created,
        each room's extra snapshots are deleted (see `_delete_extra_snapshots`),
        and the version is set. The rooms' other data stays.
        """
        # One transaction, so that two processes opening the same old file at
        # once do not both migrate it: the second waits, then sees the new version.
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            version_row = self._connection.execute("PRAGMA user_version").fetchone()
            version = int(version_row[0])
            if version < _SCHEMA_VERSION:
                self._add_missing_columns()
                if version < _SOLVE_TIME_VERSION:
                    self._store_solve_times()
                for index_statement in _ROOM_TIMES_INDEXES:
                    self._connection.execute(index_statement)
                self._delete_extra_snapshots()
                self._connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        except BaseException:
            self._connection.execute("ROLLBACK")
            raise
        self._connection.execute("COMMIT")

    def _delete_extra_snapshots(self) -> None:
        """Delete each room's snapshots but its lowest and its highest seq.

        Plain SQL: no snapshot is read, so a damaged one does not fail the open.
        """
        self._connection.execute(
            "DELETE FROM snapshots WHERE seq NOT IN ("
            "SELECT MIN(seq) FROM snapshots AS kept WHERE kept.code = snapshots.code"
            ") AND seq NOT IN ("
            "SELECT MAX(seq) FROM snapshots AS kept WHERE kept.code = snapshots.code)"
        )

    def _add_missing_columns(self) -> None:
        """Add to `room_times` each column of `_ADDED_COLUMNS` that it lacks."""
        column_rows = self._connection.execute(
            "PRAGMA table_info(room_times)"
        ).fetchall()
        column_names: list[str] = []
        for column_row in column_rows:
            column_names.append(str(column_row[1]))
        for column, column_type in _ADDED_COLUMNS.items():
            if column not in column_names:
                self._connection.execute(
                    f"ALTER TABLE room_times ADD COLUMN {column} {column_type}"
                )

    def _store_solve_times(self) -> None:
        """Give each solved room its solve time, for a database being migrated.

        A room is solved when its latest snapshot says so or its log holds a
        `grid_solved`. The time is the snapshot's `solved_at`, else the `at` of
        the logged `grid_solved`, else the room's last edit time. An unsolved
        room keeps none.

        The snapshot and the log are read as plain JSON, without the checks of
        `RoomState` and `LogEntry`: a migration must not fail on a field that a
        later rule tightened.
        """
        rows = self._connection.execute(
            "SELECT code, last_edit_at FROM room_times"
        ).fetchall()
        for code, last_edit_at in rows:
            snapshot_is_solved, snapshot_solved_at = self._snapshot_solve_time(code)
            logged_solved_at = self._logged_solved_at(code)
            if not snapshot_is_solved and logged_solved_at is None:
                continue
            solved_at = snapshot_solved_at
            if solved_at is None:
                solved_at = logged_solved_at
            if solved_at is None:
                solved_at = float(last_edit_at)
            self._connection.execute(
                "UPDATE room_times SET solved_at = ? WHERE code = ?",
                (solved_at, code),
            )

    def _logged_solved_at(self, code: str) -> float | None:
        """Read the `at` of the room's first logged `grid_solved`, as plain JSON.

        Returns:
            The time, or None when the log holds no `grid_solved`.
        """
        rows = self._connection.execute(
            "SELECT entry_json FROM log WHERE code = ? ORDER BY seq", (code,)
        ).fetchall()
        for (entry_json,) in rows:
            stored = json.loads(entry_json)
            if stored.get("event", {}).get("type") == "grid_solved":
                return float(stored["at"])
        return None

    def _snapshot_solve_time(self, code: str) -> tuple[bool, float | None]:
        """Read, in the room's latest snapshot, whether it is solved and when.

        Returns:
            Whether the snapshot says the room is solved, and its `solved_at`
            (None when it holds none, or when the room has no snapshot).
        """
        row = self._connection.execute(
            "SELECT state_json FROM snapshots WHERE code = ? ORDER BY seq DESC LIMIT 1",
            (code,),
        ).fetchone()
        if row is None:
            return False, None
        stored = json.loads(row[0])
        solved_at = stored.get("solved_at")
        if solved_at is not None:
            solved_at = float(solved_at)
        return stored.get("solved") is True, solved_at

    def _creator_of(self, code: str) -> str | None:
        """Return the creator of a room, None for an anonymous or unknown room.

        The caller holds the lock.
        """
        row = self._connection.execute(
            "SELECT creator_account_id FROM room_times WHERE code = ?", (code,)
        ).fetchone()
        if row is None or row[0] is None:
            return None
        return str(row[0])

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
        """Write a snapshot, replacing the one at the same seq.

        The caller holds the lock and has opened a transaction, which it commits
        with its other writes: `create_room` with the room's rows, `save_snapshot`
        with the deletion of the older snapshots.
        """
        self._connection.execute(
            "INSERT OR REPLACE INTO snapshots (code, seq, state_json) "
            "VALUES (?, ?, ?)",
            (state.code, state.seq, _snapshot_json(state)),
        )

    def _keep_first_and_newest_snapshots(self, state: RoomState) -> None:
        """Delete the room's snapshots but the ones at its lowest and highest seq.

        The caller holds the lock and has just written the snapshot of `state`,
        so a save below the newest snapshot never deletes the newest. No
        checkpoint follows (`admin/operations.md` rule 2).
        """
        self._connection.execute(
            "DELETE FROM snapshots WHERE code = ? "
            "AND seq != (SELECT MIN(seq) FROM snapshots WHERE code = ?) "
            "AND seq != (SELECT MAX(seq) FROM snapshots WHERE code = ?)",
            (state.code, state.code, state.code),
        )


def _snapshot_json(state: RoomState) -> str:
    """Return the JSON of a snapshot: the state without its creator.

    The creator is kept in `room_times` only, so that one place holds it.
    """
    anonymous = state.model_copy(update={"creator_account_id": None})
    return anonymous.model_dump_json()


def _latest_edit_time(entries: Sequence[LogEntry]) -> float | None:
    """Return the largest `at` of the edits among `entries`, None when none is one."""
    latest: float | None = None
    for entry in entries:
        if not is_edit(entry):
            continue
        if latest is None or entry.at > latest:
            latest = entry.at
    return latest


def _logged_solve_time(entries: Sequence[LogEntry]) -> float | None:
    """Return the `at` of the first `grid_solved` among `entries`, None if none."""
    for entry in entries:
        if isinstance(entry.event, GridSolved):
            return entry.at
    return None


def _room_times_of(row: Sequence[object]) -> RoomTimes:
    """Build the `RoomTimes` of a row of `_ROOM_TIMES_COLUMNS`."""
    code, last_edit_at, solved_at, creator = row
    return RoomTimes.model_validate(
        {
            "code": code,
            "last_edit_at": last_edit_at,
            "solved_at": solved_at,
            "creator_account_id": creator,
        }
    )
