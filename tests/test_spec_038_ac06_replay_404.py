"""Tests of spec 038 (privacy and operations), AC-6: a replay 404 is not counted.

"Operator access" says that a 404 of `GET /api/ops/rooms/<code>/edits` is not a
refused request of rule 2. The ops API runs on `TestClient(create_app(rooms=registry,
dist_dir=tmp_path, operator_token=OPS_TOKEN))`, with a registry on conftest's fake
clock, as in `test_spec_038_ac06_ops_api.py`. Every request here carries the right
token and the clock never moves by more than a few seconds, so the 60 seconds of
the throttle's window never pass.

The codes are a code that breaks `ROOM_CODE_PATTERN` (`abc`), a code of no room,
and the code of an expired room (spec 032). For each kind, and for the three
together, 10 replay requests all answer 404, and the next dashboard request
answers 200, not 429.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.room import new_room
from nock.server import create_app
from spec017_harness import FakeClock
from spec038_harness import (
    DASHBOARD_PATH,
    LIFE,
    NOT_FOUND,
    OPS_TOKEN,
    WRONG_CODE_LIMIT,
    WRONG_CODE_WINDOW_SECONDS,
    Log,
    bearer,
    edits_path,
    seed_room,
)

# ---- Values of the test harness ------------------------------------------------------

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
BREAKING_CODE = "abc"  # breaks ROOM_CODE_PATTERN
UNKNOWN_ROOM = "ZZZZZZ"
EXPIRED_ROOM = "EXPIRD"
LIVE_ROOM = "LIVE22"
SECONDS_BETWEEN_REQUESTS = 2  # 10 requests span 18 s, well within 60 s


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    """`tmp_path` with an `index.html`, the `dist_dir` of the "Test harness"."""
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on conftest's fake clock, with its own in-memory store."""
    room_registry = RoomRegistry(clock=fake_clock)
    yield room_registry
    room_registry.close()


@pytest.fixture
def ops_client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """The app with the operator pages on: `operator_token=OPS_TOKEN`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def rooms_in_store(
    registry: RoomRegistry, fx01_grid: Grid, fake_clock: FakeClock
) -> FakeClock:
    """Seed a room that expires and a room that stays live; return the clock.

    Each room holds a join. `EXPIRED_ROOM` is seeded first, then the clock is
    moved past the life of a room (spec 032), then `LIVE_ROOM` is seeded: when
    the test starts, the first has expired and the second has not.
    """
    for code in (EXPIRED_ROOM, LIVE_ROOM):
        if code == LIVE_ROOM:
            fake_clock.now = fake_clock() + LIFE + 1
        created_at = fake_clock()
        log = Log(created_at + 1)
        log.join("p1", "ANA", 0, "token-of-ana-0001")
        seed_room(registry, new_room(code, fx01_grid, created_at), log.entries)
    return fake_clock


# ---- Helpers -------------------------------------------------------------------------


def replay_404s(
    client: TestClient, codes: list[str], clock: FakeClock, requests: int
) -> None:
    """Send `requests` replay requests with the right token, cycling over `codes`.

    Each must answer 404 with `{"detail": "Not Found"}`. The clock moves by
    SECONDS_BETWEEN_REQUESTS after each request.
    """
    started = clock()
    for index in range(requests):
        code = codes[index % len(codes)]
        response = client.get(edits_path(code), headers=bearer(OPS_TOKEN))
        assert response.status_code == 404, (code, response.text)
        assert response.json() == NOT_FOUND, code
        clock.advance(SECONDS_BETWEEN_REQUESTS)
    assert clock() - started < WRONG_CODE_WINDOW_SECONDS


def assert_dashboard_answers_200(client: TestClient) -> None:
    """The dashboard with the right token answers 200, not 429."""
    response = client.get(DASHBOARD_PATH, headers=bearer(OPS_TOKEN))
    assert response.status_code == 200, response.text


# ---- AC-6: a replay 404 is not counted -----------------------------------------------


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(BREAKING_CODE, id="breaks-the-code-pattern"),
        pytest.param(UNKNOWN_ROOM, id="unknown-room"),
        pytest.param(EXPIRED_ROOM, id="expired-room"),
    ],
)
def test_ac6_ten_replay_404s_of_one_kind_do_not_throttle_the_dashboard(
    ops_client: TestClient, rooms_in_store: FakeClock, code: str
) -> None:
    replay_404s(ops_client, [code], rooms_in_store, WRONG_CODE_LIMIT)

    assert_dashboard_answers_200(ops_client)


def test_ac6_ten_replay_404s_of_the_three_kinds_do_not_throttle_the_dashboard(
    ops_client: TestClient, rooms_in_store: FakeClock
) -> None:
    codes = [BREAKING_CODE, UNKNOWN_ROOM, EXPIRED_ROOM]

    replay_404s(ops_client, codes, rooms_in_store, WRONG_CODE_LIMIT)

    assert_dashboard_answers_200(ops_client)


def test_ac6_replay_404s_do_not_throttle_the_replay_route_either(
    ops_client: TestClient, rooms_in_store: FakeClock
) -> None:
    codes = [BREAKING_CODE, UNKNOWN_ROOM, EXPIRED_ROOM]
    replay_404s(ops_client, codes, rooms_in_store, WRONG_CODE_LIMIT)

    response = ops_client.get(edits_path(LIVE_ROOM), headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text


def test_ac6_replay_404s_do_not_add_to_the_refusals_already_counted(
    ops_client: TestClient, rooms_in_store: FakeClock
) -> None:
    # Nine refusals (401) leave the address one short of the limit; 404s on top
    # of them must not tip it over.
    for _ in range(WRONG_CODE_LIMIT - 1):
        assert ops_client.get(DASHBOARD_PATH).status_code == 401
    codes = [BREAKING_CODE, UNKNOWN_ROOM, EXPIRED_ROOM]

    replay_404s(ops_client, codes, rooms_in_store, WRONG_CODE_LIMIT)

    assert_dashboard_answers_200(ops_client)
