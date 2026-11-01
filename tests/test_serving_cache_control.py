"""Tests of platform/serving, AC-12 and AC-13: the `Cache-Control` of the client.

The app has a built client, the operator pages on, the accounts on (an
`AccountStore` on a file of the test's folder) and FX-01 as grid 1, so that `/ops`,
`/account` and `/g/1` are page routes that answer. AC-12: the 200 of `index.html`
from each page route of `product.md` ("Stable routes": `/`, `/g/<number>`,
`/r/<code>`, `/account`, `/ops`, and `/recap/<token>` on a stored solved room,
which needs its own app) and of the root file `/favicon.svg` carry
`Cache-Control: no-cache`. AC-13: a file of
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
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from results_harness import shared_page_route, stored_solved_app
from serving_harness import IMMUTABLE_CACHE, NO_CACHE, edge_app
from serving_harness import account_store as account_store
from serving_harness import catalogue as catalogue
from serving_harness import fx01_grid as fx01_grid
from serving_harness import registry as registry
from spec028_harness import SHARE_TOKEN
from spec040_harness import make_dist_dir


@pytest.fixture
def client(
    registry: RoomRegistry,
    catalogue: Catalogue,
    account_store: AccountStore,
    tmp_path: Path,
) -> Iterator[TestClient]:
    """The app with a build, operator pages on, accounts on and FX-01 as grid 1."""
    dist_dir = make_dist_dir(tmp_path)
    app = edge_app(registry, dist_dir, catalogue, account_store=account_store)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def unbuilt_client(registry: RoomRegistry, tmp_path: Path) -> Iterator[TestClient]:
    """The app with no build."""
    app = edge_app(registry, tmp_path / "no-build")
    with TestClient(app) as test_client:
        yield test_client


@pytest.mark.parametrize(
    "path", ["/", "/g/1", "/r/ABC123", "/ops", "/account", "/favicon.svg"]
)
def test_ac12_the_pages_and_the_root_files_are_not_kept_without_asking(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.headers.get("cache-control") == NO_CACHE


def test_ac12_the_shared_recap_page_is_not_kept_without_asking(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    with stored_solved_app(tmp_path, fx01_grid) as app:
        response = app.client.get(shared_page_route(SHARE_TOKEN))

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
