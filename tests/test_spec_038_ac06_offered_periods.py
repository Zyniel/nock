"""Tests of operations AC-4 (spec 038 AC-6): the periods the room lives offer.

The dashboard answers `offered_days`, the periods of 1, 7 and 30 days that are no
longer than the shortest room life (`admin/operations.md` rule 12). The app runs
on a registry whose `RoomConfig` sets the lives, on conftest's fake clock, with a
store that holds rooms created 8 days, 7 days and 1 day before `now`. The rest of
the criterion (the 7-day figures, `?days=30`, `?days=2`) is checked in
`test_spec_038_ac06_ops_api.py`.

The answer's `offered_days` is read from the JSON, apart from the figures: the
figures are `DashboardFigures`, which `dashboard_figures(rooms, days, now)` gives.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.room import RoomConfig, new_room
from nock.server import create_app
from spec017_harness import FakeClock
from spec032_harness import make_dist_dir
from spec038_harness import (
    DASHBOARD_PATH,
    DAY,
    OPS_TOKEN,
    Log,
    bearer,
    seed_room,
)

HOURS_PER_DAY = 24


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def seed_three_rooms(registry: RoomRegistry, grid: Grid) -> None:
    """Add the rooms created 8 days, 7 days and 1 day before `now`, one joined."""
    now = registry.clock()
    for code, age_days in [("OLD8DY", 8), ("EDGE7D", 7), ("NEW1DY", 1)]:
        log = Log(now - age_days * DAY + 10)
        log.join("p1", "ANA", 0, f"token-of-ana-{code}")
        seed_room(registry, new_room(code, grid, now - age_days * DAY), log.entries)


def dashboard_with_lives(
    fake_clock: FakeClock,
    dist_dir: Path,
    grid: Grid,
    config: RoomConfig,
    query: str = "",
) -> tuple[int, dict[str, object]]:
    """Ask the dashboard of an app on `config`'s lives; return its status and JSON."""
    registry = RoomRegistry(clock=fake_clock, config=config)
    try:
        seed_three_rooms(registry, grid)
        app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
        with TestClient(app) as client:
            response = client.get(f"{DASHBOARD_PATH}{query}", headers=bearer(OPS_TOKEN))
        body = response.json()
        assert isinstance(body, dict), body
        return response.status_code, body
    finally:
        registry.close()


@pytest.fixture
def default_lives_registry(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid
) -> Iterator[RoomRegistry]:
    """A registry on the default lives with the three rooms; closed afterwards."""
    registry = RoomRegistry(clock=fake_clock)
    seed_three_rooms(registry, fx01_grid)
    yield registry
    registry.close()


def test_ac6_with_the_default_lives_all_three_periods_are_offered(
    default_lives_registry: RoomRegistry, dist_dir: Path
) -> None:
    app = create_app(
        rooms=default_lives_registry, dist_dir=dist_dir, operator_token=OPS_TOKEN
    )

    with TestClient(app) as client:
        response = client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["days"] == 7
    assert body["offered_days"] == [1, 7, 30]
    assert body["rooms_created"] == 2


@pytest.mark.parametrize(
    "variable",
    [
        "creator_solved_room_hours",
        "creator_room_hours",
        "anonymous_solved_room_hours",
        "anonymous_room_hours",
    ],
)
def test_ac6_a_life_of_168_hours_offers_1_and_7_days_whichever_life_it_is(
    fake_clock: FakeClock,
    dist_dir: Path,
    fx01_grid: Grid,
    variable: str,
) -> None:
    config = RoomConfig.model_validate({variable: 7 * HOURS_PER_DAY})

    status, body = dashboard_with_lives(fake_clock, dist_dir, fx01_grid, config)

    assert status == 200, body
    assert body["days"] == 7
    assert body["offered_days"] == [1, 7]
    assert body["rooms_created"] == 2


def test_ac6_a_period_longer_than_the_shortest_life_is_422_as_a_wrong_one(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid
) -> None:
    config = RoomConfig(creator_solved_room_hours=7 * HOURS_PER_DAY)

    status, body = dashboard_with_lives(
        fake_clock, dist_dir, fx01_grid, config, "?days=30"
    )

    assert status == 422, body
    assert list(body) == ["detail"]


def test_ac6_a_period_equal_to_the_shortest_life_is_still_offered(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid
) -> None:
    config = RoomConfig(anonymous_room_hours=7 * HOURS_PER_DAY)

    status, body = dashboard_with_lives(
        fake_clock, dist_dir, fx01_grid, config, "?days=7"
    )

    assert status == 200, body
    assert body["days"] == 7
    assert body["offered_days"] == [1, 7]


def test_ac6_at_24_hours_only_one_day_is_offered_and_it_is_the_default(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid
) -> None:
    config = RoomConfig(creator_solved_room_hours=24)

    status, body = dashboard_with_lives(fake_clock, dist_dir, fx01_grid, config)

    assert status == 200, body
    assert body["days"] == 1
    assert body["offered_days"] == [1]
    assert body["rooms_created"] == 1


@pytest.mark.parametrize("days", ["7", "30"])
def test_ac6_at_24_hours_the_longer_periods_are_422(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid, days: str
) -> None:
    config = RoomConfig(creator_solved_room_hours=24)

    status, body = dashboard_with_lives(
        fake_clock, dist_dir, fx01_grid, config, f"?days={days}"
    )

    assert status == 422, body
    assert list(body) == ["detail"]


def test_ac6_a_life_of_30_days_offers_all_three_periods(
    fake_clock: FakeClock, dist_dir: Path, fx01_grid: Grid
) -> None:
    config = RoomConfig(anonymous_room_hours=30 * HOURS_PER_DAY)

    status, body = dashboard_with_lives(
        fake_clock, dist_dir, fx01_grid, config, "?days=30"
    )

    assert status == 200, body
    assert body["days"] == 30
    assert body["offered_days"] == [1, 7, 30]
