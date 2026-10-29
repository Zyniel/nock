"""Tests of admin/overrides, AC-6 and AC-7: the dry run.

The rooms are written to the store of `host_harness`'s app (accounts off, a file
database, a fake clock) as `lifetime_harness` does: a hand-made letter at a chosen
time, or a letter then `grid_solved` for a solved room. Room A also has a socket,
opened while it was still open (`T0`), before the clock moves 50 hours on, so that
it is expired by the current value but not yet met by a sweep or a lookup. The
sweep interval of the app is the default hour of real time, so no sweep runs
during a test.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Generator
from pathlib import Path

import pytest

from host_harness import open_member
from lifetime_harness import config_with_lives, stored_room
from nock.catalogue import Catalogue
from nock.grid import Grid
from overrides_harness import (
    CODE_C,
    INTERVAL,
    OpsHostApp,
    assert_socket_stays_open,
    env_app,
    hours_after_t0,
    ops_host_app,
    solved_stored_room,
)
from spec014_harness import Peer
from spec017_harness import FakeClock
from spec032_harness import CODE_A, CODE_B, T0, grid_from_text

ANONYMOUS = "anonymous_room_hours"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@contextlib.contextmanager
def rooms_a_b_and_c(
    directory: Path,
    clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    grid: Grid,
) -> Generator[tuple[OpsHostApp, Peer]]:
    """AC-6's rooms, 50 hours after A's last edit, under `anonymous_room_hours` 48.

    A: last edited at `T0`, a socket open. B: last edited 30 hours ago. C: solved
    30 hours ago. Yields the app and A's socket.
    """
    config = config_with_lives(anonymous=48)
    with (
        ops_host_app(directory, clock, monkeypatch, config, catalogue) as running,
        contextlib.ExitStack() as stack,
    ):
        store = running.app.store
        stored_room(store, grid, CODE_A, T0)
        owner = open_member(stack, running.app.client, CODE_A, "Ana")
        stored_room(store, grid, CODE_B, hours_after_t0(20))
        solved_stored_room(store, grid, CODE_C, hours_after_t0(20))
        clock.now = hours_after_t0(50)
        yield running, owner


# ---- AC-6: the count ----


@pytest.mark.parametrize(("proposed", "rooms"), [(24, 2), (96, 0)])
def test_ac6_the_dry_run_counts_the_rooms_the_proposed_life_would_delete(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
    proposed: int,
    rooms: int,
) -> None:
    with rooms_a_b_and_c(tmp_path, fake_clock, monkeypatch, catalogue, fx01_grid) as (
        running,
        _owner,
    ):
        response = running.ops.dry_run(ANONYMOUS, proposed)

    assert response.status_code == 200, response.text
    assert response.json() == {"rooms": rooms}


def test_ac6_a_dry_run_saves_nothing_deletes_nothing_and_closes_nothing(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> None:
    with rooms_a_b_and_c(tmp_path, fake_clock, monkeypatch, catalogue, fx01_grid) as (
        running,
        owner,
    ):
        running.ops.dry_run(ANONYMOUS, 24)
        running.ops.dry_run(ANONYMOUS, 96)
        row = running.ops.row(ANONYMOUS)
        store = running.app.store
        stored = [store.has_room(code) for code in (CODE_A, CODE_B, CODE_C)]

        assert_socket_stays_open(owner)

    assert stored == [True, True, True]
    assert row["override"] is None
    assert row["value"] == 48
    assert running.app.registry.config.anonymous_room_hours == 48


# ---- AC-7: a reset's dry run, and what is refused ----


def test_ac7_the_dry_run_of_a_reset_uses_the_value_the_reset_falls_back_to(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> None:
    config = config_with_lives(anonymous=24)
    with ops_host_app(tmp_path, fake_clock, monkeypatch, config, catalogue) as running:
        stored_room(running.app.store, fx01_grid, CODE_B, T0)
        fake_clock.now = hours_after_t0(30)
        saved = running.ops.put(ANONYMOUS, 720)

        response = running.ops.dry_run_body({"name": ANONYMOUS, "value": None})

    assert saved.status_code == 200, saved.text
    assert response.status_code == 200, response.text
    assert response.json() == {"rooms": 1}


REFUSED_DRY_RUNS = [
    pytest.param({"name": INTERVAL, "value": 30}, id="interval"),
    pytest.param({"name": INTERVAL, "value": None}, id="interval-reset"),
    pytest.param({"name": ANONYMOUS, "value": 23}, id="below-the-bounds"),
    pytest.param({"name": ANONYMOUS, "value": 8761}, id="above-the-bounds"),
    pytest.param({"name": ANONYMOUS, "value": 24.5}, id="not-whole"),
    pytest.param({"name": ANONYMOUS, "value": "24"}, id="text"),
    pytest.param({"name": "room_hours", "value": 48}, id="unknown-name"),
    pytest.param({"name": ANONYMOUS}, id="no-value"),
]


@pytest.mark.parametrize("body", REFUSED_DRY_RUNS)
def test_ac7_the_dry_run_refuses_the_interval_and_any_body_put_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: dict[str, object]
) -> None:
    with env_app(tmp_path, monkeypatch) as ops:
        response = ops.dry_run_body(body)

    assert response.status_code == 422, response.text
