"""Tests of admin/operations, AC-21: the Bearer scheme in any case.

The ops API runs on `TestClient(create_app(rooms=registry, dist_dir=tmp_path,
operator_token=OPS_TOKEN))`, as in spec 038's tests. Each spelling of the scheme
(`bearer`, `BEARER`, `bEaReR`) is sent 12 times in a row with the right token from
the one address of the test client: every request gets the dashboard's 200, none a
401 and none a 429 (a refused request counts against the address, 10 of them
block it for 60 seconds, so a spelling the API refuses shows as a 401 and, from
the eleventh, a 429).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.hub import RoomRegistry
from nock.server import create_app
from spec038_harness import DASHBOARD_PATH, OPS_TOKEN

REQUESTS_IN_A_ROW = 12
OK = 200


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def ops_client(registry: RoomRegistry, tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(rooms=registry, dist_dir=tmp_path, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        yield client


@pytest.mark.parametrize("scheme", ["bearer", "BEARER", "bEaReR"])
def test_ac21_the_scheme_is_accepted_in_any_case_without_throttling(
    ops_client: TestClient, scheme: str
) -> None:
    statuses: list[int] = []
    for _ in range(REQUESTS_IN_A_ROW):
        response = ops_client.get(
            DASHBOARD_PATH, headers={"Authorization": f"{scheme} {OPS_TOKEN}"}
        )
        statuses.append(response.status_code)

    assert statuses == [OK] * REQUESTS_IN_A_ROW
