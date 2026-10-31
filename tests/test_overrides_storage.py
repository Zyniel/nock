"""Tests of admin/overrides, AC-9 and AC-10: the table `overrides`.

A "restart" is a second app on the same database file, started after the first
one stopped and closed its registry and store (`registry_app`). The table is read
with `sqlite3` on the file, as `lifetime_harness` reads `room_times`. Rows that
exist before the start are written by `insert_override_rows`, which creates the
table with the spec's own `CREATE TABLE IF NOT EXISTS`, so that the test does not
depend on how the store creates it.

Readings taken where the spec leaves room:

- Rule 7 ("created with the other tables, with no migration of its own; a room's
  deletion never touches it") is checked under AC-9: the table's columns by
  `PRAGMA table_info`, the version by `PRAGMA user_version` (3, since the
  migration of `lobby/lifetime.md` rule 8 adds no table), and a deletion by the
  sweep of an expired room.
- Rule 8 ("before its first sweep") is checked under AC-10: a stored override of
  24 hours deletes a room 30 hours old at the very first sweep of the app, whose
  interval is the default hour of real time.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from host_harness import schema_version
from lifetime_harness import select_rows, stored_room, wait_until_deleted
from nock.grid import Grid
from nock.store import RoomStore
from overrides_harness import (
    SCHEMA_VERSION,
    body_of,
    env_app,
    hours_after_t0,
    insert_override_rows,
    names_row,
    overrides_records,
    registry_app,
    stored_overrides,
)
from spec017_harness import FakeClock
from spec032_harness import CODE_A, T0, grid_from_text
from spec033_harness import DATABASE_FILE_NAME

CREATOR = "creator_room_hours"
INTERVAL = "expiry_sweep_minutes"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-9: a file keeps the overrides, memory does not ----


def test_ac9_on_a_database_file_an_override_survives_a_restart(tmp_path: Path) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    with registry_app(tmp_path, database=path) as first:
        saved = first.ops.put(CREATOR, 48)

    with registry_app(tmp_path, database=path) as second:
        row = second.ops.row(CREATOR)
        durable = body_of(second.ops.settings())["durable"]
        config = second.registry.config

    assert saved.status_code == 200, saved.text
    assert (row["value"], row["source"], row["override"]) == (48, "override", 48)
    assert durable is True
    assert config.creator_room_hours == 48


def test_ac9_in_memory_the_overrides_go_with_the_process(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with env_app(tmp_path, monkeypatch) as first:
        saved = first.put(CREATOR, 48)

    with env_app(tmp_path, monkeypatch) as second:
        row = second.row(CREATOR)

    assert saved.status_code == 200, saved.text
    assert (row["value"], row["source"], row["override"]) == (720, "default", None)


def test_ac9_the_table_holds_one_row_per_override_and_a_reset_removes_it(
    tmp_path: Path,
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    with registry_app(tmp_path, database=path) as running:
        running.ops.put(CREATOR, 48)
        running.ops.put(INTERVAL, 5)
        running.ops.put(CREATOR, 96)
        both = stored_overrides(path)

        running.ops.put(CREATOR, None)
        remaining = stored_overrides(path)

    assert both == [(CREATOR, 96), (INTERVAL, 5)]
    assert remaining == [(INTERVAL, 5)]
    assert schema_version(path) == SCHEMA_VERSION


def test_ac9_the_store_creates_the_table_with_the_other_tables(tmp_path: Path) -> None:
    path = tmp_path / DATABASE_FILE_NAME

    RoomStore(path).close()

    columns = select_rows(path, "PRAGMA table_info(overrides)")
    assert columns == [
        (0, "name", "TEXT", 0, None, 1),
        (1, "value", "INTEGER", 1, None, 0),
    ]
    assert schema_version(path) == SCHEMA_VERSION


def test_ac9_the_deletion_of_a_room_never_touches_the_overrides(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    with registry_app(tmp_path, clock=fake_clock, database=path) as running:
        stored_room(running.store, fx01_grid, CODE_A, T0)
        running.ops.put(CREATOR, 48)
        fake_clock.now = hours_after_t0(800)

        deleted = running.registry.expire_rooms()

    assert deleted == [CODE_A]
    assert stored_overrides(path) == [(CREATOR, 48)]


# ---- AC-10: the table is read at the start ----


def test_ac10_a_stored_row_with_an_unknown_name_or_a_bad_value_is_dropped_and_logged(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    insert_override_rows(
        path,
        [
            ("room_hours", 48),
            (CREATOR, 23),
            ("anonymous_room_hours", "abc"),
            ("anonymous_solved_room_hours", 48),
        ],
    )
    caplog.set_level(logging.INFO)

    with registry_app(tmp_path, database=path) as running:
        config = running.registry.config
        kept = stored_overrides(path)

    warnings = overrides_records(caplog.records, logging.WARNING)
    messages = [record.getMessage() for record in warnings]
    assert len(warnings) == 3, messages
    for name, value in [
        ("room_hours", "48"),
        (CREATOR, "23"),
        ("anonymous_room_hours", "abc"),
    ]:
        naming = [message for message in messages if names_row(message, name, value)]
        assert len(naming) == 1, (name, messages)
    assert kept == [("anonymous_solved_room_hours", 48)]
    assert config.anonymous_solved_room_hours == 48
    assert config.creator_room_hours == 720
    assert config.anonymous_room_hours == 720


def test_ac10_the_stored_overrides_apply_before_the_first_sweep(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    store = RoomStore(path)
    stored_room(store, fx01_grid, CODE_A, T0)
    store.close()
    insert_override_rows(path, [("anonymous_room_hours", 24)])
    fake_clock.now = hours_after_t0(30)

    with registry_app(tmp_path, clock=fake_clock, database=path) as running:
        wait_until_deleted(running.store, CODE_A)

        assert running.registry.config.anonymous_room_hours == 24
