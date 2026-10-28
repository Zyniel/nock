"""Tests of lobby/host, AC-9: which rooms have a creator, and what is stored.

Over HTTP, with the app of `host_harness` (accounts on or off, the fake clock, both
stores on one database file). The creator is read from the live room
(`RoomState.creator_account_id`) and from the stored row (`room_times`).
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
from pathlib import Path

import pytest

from host_harness import (
    LEA_EMAIL,
    HostApp,
    create_room_as,
    host_app,
    lea_creates_a_room,
    open_member,
    schema_version,
    sign_in_as,
    stored_creator,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.room import new_room
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import ROOMS_PATH, SESSION_LIFE, room_key, state_of, with_session


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def test_ac9_a_signed_in_post_stores_the_account_as_the_creator(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        room = lea_creates_a_room(app)
        live_creator = state_of(app.registry, room.code).creator_account_id

    assert live_creator == room.account_id
    assert stored_creator(app.database_path, room.code) == room.account_id
    assert schema_version(app.database_path) == 1


def assert_anonymous_room(app: HostApp, code: str) -> None:
    """The live room and the stored row name no creator."""
    assert state_of(app.registry, code).creator_account_id is None
    assert stored_creator(app.database_path, code) is None


@pytest.mark.parametrize("cookie", ["none", "unknown", "expired"])
def test_ac9_a_post_without_a_valid_session_makes_an_anonymous_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
    cookie: str,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        session = sign_in_as(app, LEA_EMAIL)
        sent: str | None = None
        if cookie == "unknown":
            sent = "u" * len(session)
        if cookie == "expired":
            fake_clock.advance(SESSION_LIFE + 1)
            sent = session
        code = create_room_as(app, sent)

        assert_anonymous_room(app, code)


def test_ac9_a_post_with_accounts_off_ignores_the_cookie(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as accounts_on:
        session = sign_in_as(accounts_on, LEA_EMAIL)

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as accounts_off:
        code = create_room_as(accounts_off, session)

        assert_anonymous_room(accounts_off, code)


def test_ac9_a_host_who_signs_in_later_does_not_become_the_creator(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        code = create_room_as(app, None)
        with contextlib.ExitStack() as stack:
            lea = open_member(stack, app.client, code, "Lea")
            session = sign_in_as(app, LEA_EMAIL)
            key = room_key(code, lea.snapshot().resume_token)

            put = app.client.put(ROOMS_PATH, json=key, headers=with_session(session))

        assert put.status_code == 204
        assert_anonymous_room(app, code)


# The schema of `src/nock/store.py` as it is before the creator column.
OLD_SCHEMA = """
CREATE TABLE rooms (code TEXT PRIMARY KEY);
CREATE TABLE snapshots (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    state_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
CREATE TABLE log (
    code TEXT NOT NULL REFERENCES rooms (code),
    seq INTEGER NOT NULL,
    entry_json TEXT NOT NULL,
    PRIMARY KEY (code, seq)
);
CREATE TABLE share_tokens (
    token TEXT PRIMARY KEY,
    code TEXT NOT NULL REFERENCES rooms (code)
);
CREATE TABLE room_times (
    code TEXT PRIMARY KEY REFERENCES rooms (code),
    created_at REAL NOT NULL,
    last_edit_at REAL NOT NULL
);
"""
OLD_CODE = "OLDAAA"
OLD_CREATED_AT = 1_000.0
OLD_LAST_EDIT_AT = 5_000.0
OLD_SHARE_TOKEN = "old-share-token-0001"


def write_old_store(path: Path, grid: Grid) -> None:
    """Write a database file of the old schema, `user_version` 0, with one room."""
    state = new_room(OLD_CODE, grid, OLD_CREATED_AT, 1, OLD_SHARE_TOKEN)
    # The old snapshots have no creator key.
    state_json = json.loads(state.model_dump_json())
    state_json.pop("creator_account_id", None)
    connection = sqlite3.connect(path)
    try:
        connection.executescript(OLD_SCHEMA)
        connection.execute("INSERT INTO rooms (code) VALUES (?)", (OLD_CODE,))
        connection.execute(
            "INSERT INTO room_times (code, created_at, last_edit_at) VALUES (?, ?, ?)",
            (OLD_CODE, OLD_CREATED_AT, OLD_LAST_EDIT_AT),
        )
        connection.execute(
            "INSERT INTO share_tokens (token, code) VALUES (?, ?)",
            (OLD_SHARE_TOKEN, OLD_CODE),
        )
        connection.execute(
            "INSERT INTO snapshots (code, seq, state_json) VALUES (?, 0, ?)",
            (OLD_CODE, json.dumps(state_json)),
        )
        connection.commit()
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 0
    finally:
        connection.close()


def test_ac9_a_database_written_before_the_column_opens_with_it_added(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "old.sqlite3"
    write_old_store(path, fx01_grid)

    store = RoomStore(path)
    try:
        loaded = store.load_room(OLD_CODE)
        last_edit_at = store.last_edit_at(OLD_CODE)
        share_code = store.code_for_share_token(OLD_SHARE_TOKEN)
    finally:
        store.close()

    assert schema_version(path) == 1
    assert stored_creator(path, OLD_CODE) is None
    assert loaded is not None
    assert loaded.creator_account_id is None
    assert (loaded.code, loaded.grid_number, loaded.created_at) == (
        OLD_CODE,
        1,
        OLD_CREATED_AT,
    )
    assert loaded.share_token == OLD_SHARE_TOKEN
    assert last_edit_at == OLD_LAST_EDIT_AT
    assert share_code == OLD_CODE
