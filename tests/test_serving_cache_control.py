"""Tests of platform/serving, AC-12 and AC-13: the `Cache-Control` of the client.

The app has a built client, the operator pages on and the accounts on (an
`AccountStore` on a file of the test's folder), so that `/ops` and `/account` are
page routes that answer. AC-12: the 200 of `index.html` from each page route and
of the root file `/favicon.svg` carry `Cache-Control: no-cache`. AC-13: a file of
`assets/` carries `public, max-age=31536000, immutable`.

Choices where the spec leaves room:

- Rule 13's "A 404 or 503 of these routes has no `Cache-Control`" is checked on
  the criterion's `/assets/missing.js`, on a missing root file (`/missing.svg`)
  and on `/` with no build (503): none of them carries the header.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.accounts import AccountStore
from nock.hub import RoomRegistry
from serving_harness import IMMUTABLE_CACHE, NO_CACHE, edge_app
from spec040_harness import make_dist_dir


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def account_store(tmp_path: Path) -> Iterator[AccountStore]:
    store = AccountStore(tmp_path / "accounts.sqlite3")
    yield store
    store.close()


@pytest.fixture
def client(
    registry: RoomRegistry, account_store: AccountStore, tmp_path: Path
) -> Iterator[TestClient]:
    """The app with a build, operator pages on and accounts on."""
    dist_dir = make_dist_dir(tmp_path)
    app = edge_app(registry, dist_dir, account_store=account_store)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def unbuilt_client(registry: RoomRegistry, tmp_path: Path) -> Iterator[TestClient]:
    """The app with no build."""
    app = edge_app(registry, tmp_path / "no-build")
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize("path", ["/", "/r/ABC123", "/ops", "/account", "/favicon.svg"])
def test_ac12_the_pages_and_the_root_files_are_not_kept_without_asking(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers.get("cache-control") == NO_CACHE


def test_ac13_a_hashed_asset_is_kept_for_a_year(client: TestClient) -> None:
    response = client.get("/assets/app.js")

    assert response.status_code == 200
    assert response.headers.get("cache-control") == IMMUTABLE_CACHE


@pytest.mark.parametrize(
    ("path", "status"),
    [
        pytest.param("/assets/missing.js", 404, id="missing-asset"),
        pytest.param("/missing.svg", 404, id="missing-root-file"),
    ],
)
def test_ac13_a_missing_file_has_no_cache_control(
    client: TestClient, path: str, status: int
) -> None:
    response = client.get(path)

    assert response.status_code == status
    assert "cache-control" not in response.headers


def test_ac13_the_503_with_no_build_has_no_cache_control(
    unbuilt_client: TestClient,
) -> None:
    response = unbuilt_client.get("/")

    assert response.status_code == 503
    assert "cache-control" not in response.headers
