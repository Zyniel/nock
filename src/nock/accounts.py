"""Optional accounts (spec 033): e-mail addresses, sign-in links and sessions.

An account is an e-mail address and a random id. It is created the first time a
sign-in link sent to that address is used. A signed-in browser holds a session
cookie, and the account keeps the room identities its player linked, so that
another device can get them.

An account also keeps a record of each finished grid of its rooms (spec 029), so
that its history stays listed after the room is deleted.

`AccountStore` keeps the accounts in the database file of the rooms. Link tokens
and session values are stored as their SHA-256 hex digests only, so a copy of
the database cannot sign anybody in.
"""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
import string
import threading
from collections.abc import Sequence
from pathlib import Path
from typing import NamedTuple

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from nock.protocol import Nickname, PlayerId, ResumeToken
from nock.room import (
    FORMER_PLAYER_NICKNAME,
    RoomCode,
    RoomKey,
    RoomState,
    member_id,
    utc_datetime,
)

SESSION_COOKIE: str = "nock_session"
LINK_LIFE_SECONDS: float = 1_800.0  # 30 minutes (decision 11)
SESSION_LIFE_SECONDS: float = 7_776_000.0  # 90 days (decision 11)
LINKS_PER_EMAIL_PER_HOUR: int = 3  # decision 11
LINKS_PER_ADDRESS_PER_HOUR: int = 10  # decision 11
EMAIL_MAX_LENGTH: int = 254

LOCAL_PART_MAX_LENGTH: int = 64
DOMAIN_LABEL_MAX_LENGTH: int = 63
# A local part takes RFC 5322's `atext` characters and the dot (decision 15): the
# ASCII letters, the digits and these 19 characters.
LOCAL_PART_CHARACTERS: frozenset[str] = frozenset(
    string.ascii_letters + string.digits + "!#$%&'*+-/=?^_`{|}~."
)
# The characters of a domain label: ASCII letters (lower case once normalised),
# ASCII digits and the hyphen.
DOMAIN_LABEL_CHARACTERS: frozenset[str] = frozenset(
    string.ascii_letters + string.digits + "-"
)
TOKEN_BYTES: int = 32  # secrets.token_urlsafe(32): 43 characters
ACCOUNT_ID_BYTES: int = 16

_MEMORY_PATH = ":memory:"

# The tables of the accounts, in the database file of the rooms. Their names
# start with "account" so that they cannot meet a table of the rooms.
_TABLES = """
CREATE TABLE IF NOT EXISTS accounts (
    account_id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS account_sessions (
    session_hash TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts (account_id),
    started_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS account_links (
    token_hash TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    room_code TEXT,
    room_resume_token TEXT,
    asked_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS account_identities (
    account_id TEXT NOT NULL REFERENCES accounts (account_id),
    code TEXT NOT NULL,
    player_id TEXT NOT NULL,
    resume_token TEXT NOT NULL,
    nickname TEXT NOT NULL,
    linked_at REAL NOT NULL,
    PRIMARY KEY (account_id, code, player_id)
);
CREATE TABLE IF NOT EXISTS account_history (
    account_id TEXT NOT NULL REFERENCES accounts (account_id),
    code TEXT NOT NULL,
    grid_number INTEGER,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    finished_at REAL NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    PRIMARY KEY (account_id, code)
);
CREATE TABLE IF NOT EXISTS account_history_teammates (
    account_id TEXT NOT NULL,
    code TEXT NOT NULL,
    position INTEGER NOT NULL,
    player_id TEXT NOT NULL,
    nickname TEXT NOT NULL,
    PRIMARY KEY (account_id, code, position)
);
"""


def normalize_email(text: str) -> str:
    """Return the address as stored: `strip()`ped, then lower-cased.

    Rules, on the result: at most EMAIL_MAX_LENGTH characters; exactly one `@`; a
    local part of 1 to 64 characters, each an ASCII letter, an ASCII digit, `.` or
    one of these 19 characters: ! # $ % & ' * + - / = ? ^ _ ` { | } ~ (with the
    letters and digits, RFC 5322's `atext`; decision 15); a domain of two or more
    labels separated by `.`, each 1 to 63 ASCII letters, digits and hyphens, not
    starting or ending with a hyphen.

    Args:
        text: The address as the player typed it.

    Returns:
        The normalised address.

    Raises:
        ValueError: a rule is broken; the message names the rule, not the address.
    """
    address = text.strip().lower()
    if len(address) > EMAIL_MAX_LENGTH:
        raise ValueError(f"An e-mail address has at most {EMAIL_MAX_LENGTH} characters")
    if address.count("@") != 1:
        raise ValueError("An e-mail address has exactly one '@'")
    local_part, domain = address.split("@")
    if not _is_local_part(local_part):
        raise ValueError(
            f"The part before '@' must have 1 to {LOCAL_PART_MAX_LENGTH} ASCII "
            "letters, digits, dots or these characters: !#$%&'*+-/=?^_`{|}~"
        )
    if not _is_domain(domain):
        raise ValueError(
            "The part after '@' must be two or more labels separated by '.', each "
            f"of 1 to {DOMAIN_LABEL_MAX_LENGTH} ASCII letters, digits and hyphens, "
            "not starting or ending with a hyphen"
        )
    return address


def _is_local_part(local_part: str) -> bool:
    """Tell whether the part before "@" keeps the rule of `normalize_email`."""
    if len(local_part) < 1 or len(local_part) > LOCAL_PART_MAX_LENGTH:
        return False
    return all(character in LOCAL_PART_CHARACTERS for character in local_part)


def _is_domain(domain: str) -> bool:
    """Tell whether the part after "@" keeps the rule of `normalize_email`."""
    labels = domain.split(".")
    if len(labels) < 2:
        return False
    return all(_is_domain_label(label) for label in labels)


def _is_domain_label(label: str) -> bool:
    """Tell whether one label of a domain keeps the rule of `normalize_email`."""
    if len(label) < 1 or len(label) > DOMAIN_LABEL_MAX_LENGTH:
        return False
    if label.startswith("-") or label.endswith("-"):
        return False
    return all(character in DOMAIN_LABEL_CHARACTERS for character in label)


class AccountModel(BaseModel):
    """Base of the account models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RoomIdentity(AccountModel):
    """An account's identity in a room, as a device stores it (spec 012)."""

    code: RoomCode
    player_id: PlayerId
    resume_token: ResumeToken
    nickname: Nickname


class Account(AccountModel):
    """An account: its random id and its normalised address."""

    account_id: str
    email: str


class AccountStatus(AccountModel):
    """The answer of GET /api/account."""

    signed_in: StrictBool
    email: str | None  # None when signed_in is False


class SignInLinkRequest(AccountModel):
    """The body of POST /api/account/link."""

    # Checked by normalize_email only, so every refused address gets one answer.
    email: str
    room: RoomKey | None = None  # the room the player asks from (spec 032 RoomKey)


class SignInRequest(AccountModel):
    """The body of POST /api/account/sign-in."""

    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


class SignInResult(AccountModel):
    """The answer of POST /api/account/sign-in."""

    email: str
    room_code: RoomCode | None  # the room the link was asked from, when linked
    rooms: tuple[RoomIdentity, ...]  # as GET /api/account/rooms


class LinkUse(AccountModel):
    """What a sign-in link was asked for: an address, and maybe a room."""

    email: str
    room: RoomKey | None  # the room the link was asked from


class SessionStart(AccountModel):
    """A new session of an account."""

    account_id: str
    session: str  # the raw cookie value; only its SHA-256 is stored


class HistoryRecord(AccountModel):
    """One finished grid of an account (spec 029)."""

    code: RoomCode
    grid_number: int | None
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    finished_at: AwareDatetime
    elapsed_ms: int = Field(ge=0, strict=True)
    teammates: tuple[Nickname, ...]  # in team_nicknames order


class _Teammate(NamedTuple):
    """A team-mate of a history record, kept with the player id for erasure."""

    player_id: str
    nickname: str


def _digest(secret: str) -> str:
    """Return the SHA-256 hex digest of a link token or a session value."""
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


class AccountStore:
    """Accounts on disk, in the database file of the rooms (NOCK_DATABASE).

    A plain class (a service). Safe to call from several threads: one connection
    is shared, and every call takes a lock. It uses its own connection with
    secure_delete ON and, on a file database, journal_mode WAL and synchronous
    FULL, like RoomStore (specs 018, 038). Link and session tokens are stored as
    their SHA-256 only; addresses, room keys and identities are stored as given.
    """

    def __init__(self, path: str | Path) -> None:
        """Open or create the account tables of the SQLite database at `path`.

        Args:
            path: A file path, or ":memory:" for an in-memory database.
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

    def add_link(self, email: str, room: RoomKey | None, now: float) -> str:
        """Record a sign-in link for `email` and the room it was asked from.

        Args:
            email: The address, normalised by the caller.
            room: The room key of the request, or None.
            now: Clock time of the request.

        Returns:
            The raw token of the link, 43 characters. Only its digest is stored.
        """
        token = secrets.token_urlsafe(TOKEN_BYTES)
        room_code = None if room is None else room.code
        room_resume_token = None if room is None else room.resume_token
        with self._lock:
            self._connection.execute(
                "INSERT INTO account_links "
                "(token_hash, email, room_code, room_resume_token, asked_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (_digest(token), email, room_code, room_resume_token, now),
            )
        return token

    def use_link(self, token: str, now: float) -> LinkUse | None:
        """Delete the link and return it.

        Args:
            token: The raw token of the link.
            now: Clock time of the sign-in.

        Returns:
            What the link was asked for; None when the token is unknown or the
            link is older than LINK_LIFE_SECONDS.
        """
        token_hash = _digest(token)
        with self._lock:
            row = self._connection.execute(
                "SELECT email, room_code, room_resume_token, asked_at "
                "FROM account_links WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
            if row is None:
                return None
            self._connection.execute(
                "DELETE FROM account_links WHERE token_hash = ?", (token_hash,)
            )
        email, room_code, room_resume_token, asked_at = row
        if now - float(asked_at) > LINK_LIFE_SECONDS:
            return None
        room = None
        if room_code is not None:
            room = RoomKey(code=room_code, resume_token=room_resume_token)
        return LinkUse(email=email, room=room)

    def sign_in(self, email: str, now: float) -> SessionStart:
        """Create the account of `email` when there is none, then a session.

        Args:
            email: The normalised address of a link just used.
            now: Clock time of the sign-in, when the session starts.

        Returns:
            The account's id and the raw value of the new session.
        """
        session = secrets.token_urlsafe(TOKEN_BYTES)
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                account_id = self._account_id_of(email)
                if account_id is None:
                    account_id = secrets.token_urlsafe(ACCOUNT_ID_BYTES)
                    self._connection.execute(
                        "INSERT INTO accounts (account_id, email) VALUES (?, ?)",
                        (account_id, email),
                    )
                self._connection.execute(
                    "INSERT INTO account_sessions "
                    "(session_hash, account_id, started_at) VALUES (?, ?, ?)",
                    (_digest(session), account_id, now),
                )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
        return SessionStart(account_id=account_id, session=session)

    def account_of_session(self, session: str, now: float) -> Account | None:
        """Return the account of a session.

        Args:
            session: The raw value of the session cookie.
            now: Clock time of the request.

        Returns:
            The account of a session that exists and is not older than
            SESSION_LIFE_SECONDS; None otherwise.
        """
        with self._lock:
            row = self._connection.execute(
                "SELECT accounts.account_id, accounts.email, "
                "account_sessions.started_at "
                "FROM account_sessions JOIN accounts "
                "ON accounts.account_id = account_sessions.account_id "
                "WHERE account_sessions.session_hash = ?",
                (_digest(session),),
            ).fetchone()
        if row is None:
            return None
        account_id, email, started_at = row
        if now - float(started_at) > SESSION_LIFE_SECONDS:
            return None
        return Account(account_id=account_id, email=email)

    def end_session(self, session: str) -> None:
        """Delete a session. An unknown session changes nothing.

        Args:
            session: The raw value of the session cookie.
        """
        with self._lock:
            self._connection.execute(
                "DELETE FROM account_sessions WHERE session_hash = ?",
                (_digest(session),),
            )

    def link_identity(
        self, account_id: str, identity: RoomIdentity, now: float
    ) -> bool:
        """Link an identity to the account, while the account exists.

        Linking the same player again updates its token and nickname and makes it
        the newest.

        Args:
            account_id: The account.
            identity: The member of a room, as the room holds them.
            now: Clock time of the link.

        Returns:
            True when the identity is linked. False, with nothing written, when the
            account does not exist (it was deleted).
        """
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                account_row = self._connection.execute(
                    "SELECT account_id FROM accounts WHERE account_id = ?",
                    (account_id,),
                ).fetchone()
                if account_row is None:
                    self._connection.execute("ROLLBACK")
                    return False
                # Deleted, then inserted again: the new row is the newest one.
                self._connection.execute(
                    "DELETE FROM account_identities "
                    "WHERE account_id = ? AND code = ? AND player_id = ?",
                    (account_id, identity.code, identity.player_id),
                )
                self._connection.execute(
                    "INSERT INTO account_identities "
                    "(account_id, code, player_id, resume_token, nickname, linked_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        account_id,
                        identity.code,
                        identity.player_id,
                        identity.resume_token,
                        identity.nickname,
                        now,
                    ),
                )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            return True

    def save_history(self, account_id: str, state: RoomState) -> None:
        """Save the record of the solved room `state` for the account, once.

        A record already saved for that account and room code is kept as it is.

        Only the account's identities with code `state.code` whose resume token
        is a member's of `state` count (`member_id(state, identity.resume_token)`
        of spec 032 is not None); an identity of an older room that had the same
        code does not. Does nothing when the room is not solved or when no
        identity counts. Team-mates are the members of `state` whose player id
        is not that of an identity that counts, kept with their player ids (for
        erasure).

        Args:
            account_id: The account.
            state: The room's latest state.
        """
        solved_at = state.solved_at
        elapsed_ms = state.solved_elapsed_ms
        if not state.solved or solved_at is None or elapsed_ms is None:
            return
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                # Read inside the transaction: an erasure cannot come in between.
                identities = self._read_identities(account_id)
                own_player_ids = _counting_player_ids(identities, state)
                is_saved = self._has_record(account_id, state.code)
                if len(own_player_ids) == 0 or is_saved:
                    self._connection.execute("ROLLBACK")
                    return
                self._insert_record(account_id, state, solved_at, elapsed_ms)
                teammates = _teammates_of(state, own_player_ids)
                self._insert_teammates(account_id, state.code, teammates)
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")

    def history(self, account_id: str) -> list[HistoryRecord]:
        """Return the account's records, `finished_at` newest first, then code.

        Args:
            account_id: The account.

        Returns:
            The records. The team-mates of each are in the order they were
            saved, a nickname equal to an earlier one left out, as
            `team_nicknames` does.
        """
        with self._lock:
            record_rows = self._connection.execute(
                "SELECT code, grid_number, width, height, finished_at, elapsed_ms "
                "FROM account_history WHERE account_id = ? "
                "ORDER BY finished_at DESC, code",
                (account_id,),
            ).fetchall()
            teammate_rows = self._connection.execute(
                "SELECT code, nickname FROM account_history_teammates "
                "WHERE account_id = ? ORDER BY code, position",
                (account_id,),
            ).fetchall()
        teammates_by_code: dict[str, list[str]] = {}
        for code, nickname in teammate_rows:
            if code not in teammates_by_code:
                teammates_by_code[code] = []
            if nickname not in teammates_by_code[code]:
                teammates_by_code[code].append(nickname)
        records: list[HistoryRecord] = []
        for code, grid_number, width, height, finished_at, elapsed_ms in record_rows:
            record = HistoryRecord(
                code=code,
                grid_number=grid_number,
                width=width,
                height=height,
                finished_at=utc_datetime(finished_at),
                elapsed_ms=elapsed_ms,
                teammates=tuple(teammates_by_code.get(code, [])),
            )
            records.append(record)
        return records

    def accounts_of_room(self, code: str) -> list[str]:
        """Return the ids of the accounts that hold an identity with code `code`.

        The identity may be of this room or of an older room that had the same
        code (save_history skips the latter).

        Args:
            code: The room code.

        Returns:
            The account ids, each once, in code-point order.
        """
        with self._lock:
            rows = self._connection.execute(
                "SELECT DISTINCT account_id FROM account_identities "
                "WHERE code = ? ORDER BY account_id",
                (code,),
            ).fetchall()
        account_ids: list[str] = []
        for (account_id,) in rows:
            account_ids.append(str(account_id))
        return account_ids

    def identities(self, account_id: str) -> list[RoomIdentity]:
        """Return the account's identity of each of its rooms.

        Args:
            account_id: The account.

        Returns:
            The latest identity linked in each room, newest link first.
        """
        latest_per_room: list[RoomIdentity] = []
        rooms_seen: set[str] = set()
        for identity in self._all_identities(account_id):
            if identity.code in rooms_seen:
                continue
            rooms_seen.add(identity.code)
            latest_per_room.append(identity)
        return latest_per_room

    def delete_account(self, account_id: str) -> list[RoomIdentity]:
        """Delete the account and everything it holds, at once.

        The account, its sessions, its identities, its history records and every
        sign-in link of its address go in one transaction. In the same
        transaction, each team-mate of another account's record whose room code
        and player id are an identity of this account gets the nickname
        FORMER_PLAYER_NICKNAME (spec 029). On a file database the write-ahead log
        is then checkpointed and emptied, so no copy of the address or of the
        nickname stays in the database files (spec 038).

        Args:
            account_id: The account.

        Returns:
            Every identity the account held (not only the latest of each room),
            newest link first.
        """
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                # Read inside the transaction: a link made before it is erased.
                held_identities = self._read_identities(account_id)
                row = self._connection.execute(
                    "SELECT email FROM accounts WHERE account_id = ?", (account_id,)
                ).fetchone()
                if row is not None:
                    self._connection.execute(
                        "DELETE FROM account_links WHERE email = ?", (row[0],)
                    )
                self._erase_from_history(account_id, held_identities)
                self._connection.execute(
                    "DELETE FROM account_identities WHERE account_id = ?",
                    (account_id,),
                )
                self._connection.execute(
                    "DELETE FROM account_sessions WHERE account_id = ?",
                    (account_id,),
                )
                self._connection.execute(
                    "DELETE FROM accounts WHERE account_id = ?", (account_id,)
                )
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            if self._is_file:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()
        return held_identities

    def erase_players_from_history(self, identities: Sequence[RoomIdentity]) -> None:
        """Make the players of `identities` former players in every history.

        In the records of every account, each team-mate whose room code and
        player id are those of one of `identities` gets the nickname
        FORMER_PLAYER_NICKNAME (spec 029). `DELETE /api/account` calls it once
        the rooms are erased. On a file database the write-ahead log is then
        checkpointed and emptied, as by `delete_account`.

        Args:
            identities: The identities of a deleted account.
        """
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                self._mark_former_players(identities)
            except BaseException:
                self._connection.execute("ROLLBACK")
                raise
            self._connection.execute("COMMIT")
            if self._is_file:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()

    def purge(self, now: float) -> None:
        """Delete the links and the sessions that are too old to be used.

        On a file database the write-ahead log is then checkpointed and emptied,
        so no deleted row stays in the database files.

        Args:
            now: Clock time of the sweep. A link older than LINK_LIFE_SECONDS and
                a session older than SESSION_LIFE_SECONDS are deleted.
        """
        with self._lock:
            self._connection.execute(
                "DELETE FROM account_links WHERE asked_at < ?",
                (now - LINK_LIFE_SECONDS,),
            )
            self._connection.execute(
                "DELETE FROM account_sessions WHERE started_at < ?",
                (now - SESSION_LIFE_SECONDS,),
            )
            if self._is_file:
                self._connection.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchall()

    def close(self) -> None:
        """Close the database. Idempotent."""
        with self._lock:
            if self._is_closed:
                return
            self._is_closed = True
            self._connection.close()

    def _has_record(self, account_id: str, code: str) -> bool:
        """Tell whether the account has a record of room `code`. The caller locks."""
        row = self._connection.execute(
            "SELECT 1 FROM account_history WHERE account_id = ? AND code = ?",
            (account_id, code),
        ).fetchone()
        return row is not None

    def _insert_record(
        self, account_id: str, state: RoomState, solved_at: float, elapsed_ms: int
    ) -> None:
        """Insert the record of a solved room, without its team-mates.

        The caller holds the lock and runs the transaction.
        """
        self._connection.execute(
            "INSERT INTO account_history "
            "(account_id, code, grid_number, width, height, finished_at, elapsed_ms) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                account_id,
                state.code,
                state.grid_number,
                state.grid.width,
                state.grid.height,
                solved_at,
                elapsed_ms,
            ),
        )

    def _insert_teammates(
        self, account_id: str, code: str, teammates: list[_Teammate]
    ) -> None:
        """Insert the team-mates of a record, in their order.

        The caller holds the lock and runs the transaction.
        """
        for position, teammate in enumerate(teammates):
            self._connection.execute(
                "INSERT INTO account_history_teammates "
                "(account_id, code, position, player_id, nickname) "
                "VALUES (?, ?, ?, ?, ?)",
                (account_id, code, position, teammate.player_id, teammate.nickname),
            )

    def _erase_from_history(
        self, account_id: str, held_identities: list[RoomIdentity]
    ) -> None:
        """Delete the account's records, and erase its players from the others'.

        The caller holds the lock and runs the transaction.
        """
        self._mark_former_players(held_identities)
        self._connection.execute(
            "DELETE FROM account_history_teammates WHERE account_id = ?",
            (account_id,),
        )
        self._connection.execute(
            "DELETE FROM account_history WHERE account_id = ?", (account_id,)
        )

    def _mark_former_players(self, identities: Sequence[RoomIdentity]) -> None:
        """Give FORMER_PLAYER_NICKNAME to each team-mate matching an identity.

        A team-mate matches when its room code and player id are the identity's.
        The caller holds the lock and runs the transaction.
        """
        for identity in identities:
            self._connection.execute(
                "UPDATE account_history_teammates SET nickname = ? "
                "WHERE code = ? AND player_id = ?",
                (FORMER_PLAYER_NICKNAME, identity.code, identity.player_id),
            )

    def _account_id_of(self, email: str) -> str | None:
        """Return the id of the account of `email`, or None. The caller locks."""
        row = self._connection.execute(
            "SELECT account_id FROM accounts WHERE email = ?", (email,)
        ).fetchone()
        if row is None:
            return None
        return str(row[0])

    def _all_identities(self, account_id: str) -> list[RoomIdentity]:
        """Return every identity of the account, newest link first.

        Two links made at the same clock time are told apart by their row id:
        a row inserted later has a larger one.
        """
        with self._lock:
            return self._read_identities(account_id)

    def _read_identities(self, account_id: str) -> list[RoomIdentity]:
        """Read `_all_identities` without taking the lock: the caller holds it."""
        rows = self._connection.execute(
            "SELECT code, player_id, resume_token, nickname "
            "FROM account_identities WHERE account_id = ? "
            "ORDER BY linked_at DESC, rowid DESC",
            (account_id,),
        ).fetchall()
        found: list[RoomIdentity] = []
        for code, player_id, resume_token, nickname in rows:
            identity = RoomIdentity(
                code=code,
                player_id=player_id,
                resume_token=resume_token,
                nickname=nickname,
            )
            found.append(identity)
        return found


def _counting_player_ids(identities: list[RoomIdentity], state: RoomState) -> set[str]:
    """Return the player ids of the identities that count for a room's record.

    An identity counts when its code is the room's and its resume token is a
    member's of the room (spec 032's `member_id`), so an identity of an older
    room that had the same code does not.
    """
    player_ids: set[str] = set()
    for identity in identities:
        if identity.code != state.code:
            continue
        player_id = member_id(state, identity.resume_token)
        if player_id is not None:
            player_ids.add(player_id)
    return player_ids


def _teammates_of(state: RoomState, own_player_ids: set[str]) -> list[_Teammate]:
    """Return the room's members other than the account's own players.

    They come in `team_nicknames` order: the past players in the order they
    left, then the players in `players` order.
    """
    teammates: list[_Teammate] = []
    for past_player in state.past_players:
        if past_player.player_id not in own_player_ids:
            teammates.append(_Teammate(past_player.player_id, past_player.nickname))
    for player in state.players:
        if player.player_id not in own_player_ids:
            teammates.append(_Teammate(player.player_id, player.nickname))
    return teammates
