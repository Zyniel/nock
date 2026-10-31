"""Tests of lobby/lifetime, AC-16: a sweep checkpoints once, after its deletions.

A file store holds expired rooms and 2 open ones (anonymous rooms of the default
life, 720 hours, edited at different times). `nock.store.checkpoint_wal` is wrapped
for the test: each call is recorded with the number of rooms that the file held at
that moment, read by a connection of its own that is closed before the real
checkpoint runs, so a call "after the 50th deletion" holds 2. The real checkpoint
still runs.

A sweep is `RoomRegistry.expire_rooms()`; a lookup that deletes an expired room is
`room_state`. The rooms are stored, not live, and accounts are off.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

import nock.store
from lifetime_harness import HOUR, config_with_lives, stored_room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec032_harness import T0, grid_from_text

EXPIRED_COUNT = 50
EXPIRED_LAST_EDIT_AT = T0 + 10
OPEN_CODES = ["OPENAA", "OPENBB"]
OPEN_LAST_EDIT_AT = T0 + 100 * HOUR
LIFE_HOURS = 720  # the default life of each kind of room
NOW = EXPIRED_LAST_EDIT_AT + LIFE_HOURS * HOUR + 1  # the expired ones, not the 2


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def expired_codes(count: int) -> list[str]:
    """The codes of `count` expired rooms, in code-point order."""
    codes: list[str] = []
    for number in range(count):
        codes.append(f"E{number:05d}")
    return codes


def rooms_in_file(database_path: Path) -> int:
    """How many rooms the database file holds, read on a connection of its own."""
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute("SELECT COUNT(*) FROM rooms").fetchone()
    finally:
        connection.close()
    return int(row[0])


def record_checkpoints(
    monkeypatch: pytest.MonkeyPatch, database_path: Path
) -> list[int]:
    """Wrap `checkpoint_wal`; the list gets, per call, the rooms the file then held."""
    rooms_at_each_call: list[int] = []
    real_checkpoint = nock.store.checkpoint_wal

    def counting_checkpoint(connection: sqlite3.Connection) -> bool:
        rooms_at_each_call.append(rooms_in_file(database_path))
        return real_checkpoint(connection)

    monkeypatch.setattr("nock.store.checkpoint_wal", counting_checkpoint)
    return rooms_at_each_call


def store_rooms(store: RoomStore, grid: Grid, expired: int) -> None:
    """Store `expired` expired rooms and the two open ones."""
    for code in expired_codes(expired):
        stored_room(store, grid, code, EXPIRED_LAST_EDIT_AT)
    for code in OPEN_CODES:
        stored_room(store, grid, code, OPEN_LAST_EDIT_AT)


def test_ac16_a_sweep_deletes_the_expired_rooms_then_runs_one_checkpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    fake_clock: FakeClock,
) -> None:
    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=config_with_lives())
    try:
        store_rooms(store, fx01_grid, EXPIRED_COUNT)
        rooms_at_each_call = record_checkpoints(monkeypatch, path)
        fake_clock.now = NOW

        swept = registry.expire_rooms()
        kept = store.has_room(OPEN_CODES[0]) and store.has_room(OPEN_CODES[1])
    finally:
        registry.close()
        store.close()

    assert swept == expired_codes(EXPIRED_COUNT)
    assert kept is True
    assert rooms_at_each_call == [len(OPEN_CODES)]


def test_ac16_a_sweep_that_finds_no_expired_room_runs_one_checkpoint_too(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    fake_clock: FakeClock,
) -> None:
    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=config_with_lives())
    try:
        store_rooms(store, fx01_grid, 0)
        rooms_at_each_call = record_checkpoints(monkeypatch, path)
        fake_clock.now = NOW

        swept = registry.expire_rooms()
    finally:
        registry.close()
        store.close()

    assert swept == []
    assert rooms_at_each_call == [len(OPEN_CODES)]


def test_ac16_a_lookup_that_deletes_an_expired_room_runs_a_checkpoint_of_its_own(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    fake_clock: FakeClock,
) -> None:
    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=config_with_lives())
    try:
        store_rooms(store, fx01_grid, 2)
        rooms_at_each_call = record_checkpoints(monkeypatch, path)
        fake_clock.now = NOW

        found = registry.room_state(expired_codes(2)[0])
    finally:
        registry.close()
        store.close()

    assert found is None
    assert rooms_at_each_call == [len(OPEN_CODES) + 1]
