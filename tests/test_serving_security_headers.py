"""Tests of platform/serving, AC-10: the three security headers on every answer.

One parametrized test sends each request of the criterion to the app (built, the
operator pages on, FX-01 as grid 1) or, for the unbuilt case, to an app whose
client folder holds no build. The route that raises is added in the test, first
in the app's routes (the root-file route `/{file_name}` would answer it
otherwise); the client then returns the 500 instead of raising its error.

Each answer must carry the three headers of rule 12 with their exact values and
no `X-Frame-Options`. The status of each request is checked too, so that a case
cannot drift into another kind of answer.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from serving_harness import (
    BODY_LIMIT,
    EDGE_HEADERS,
    ROOM_REQUEST_HEADERS,
    edge_app,
    padded_room_request,
)
from spec010_harness import catalogue_from_grid
from spec040_harness import make_dist_dir

RAISING_PATH = "/raises-an-error"


class Request(NamedTuple):
    """One request of the criterion and the status it gets."""

    method: str
    path: str
    status: int
    built: bool = True
    content: bytes | None = None
    headers: dict[str, str] | None = None


REQUESTS = [
    pytest.param(Request("GET", "/", 200), id="root"),
    pytest.param(Request("GET", "/assets/app.js", 200), id="asset"),
    pytest.param(Request("GET", "/api/grids", 200), id="grids"),
    pytest.param(Request("GET", "/api/nope", 404), id="404"),
    pytest.param(Request("POST", "/", 405), id="405"),
    pytest.param(
        Request(
            "POST",
            "/api/rooms",
            413,
            content=padded_room_request(BODY_LIMIT + 1),
            headers=ROOM_REQUEST_HEADERS,
        ),
        id="413",
    ),
    pytest.param(
        Request("POST", "/api/rooms", 422, content=b"{}", headers=ROOM_REQUEST_HEADERS),
        id="422",
    ),
    pytest.param(Request("GET", "/api/ops/dashboard", 401), id="401"),
    pytest.param(Request("GET", "/", 503, built=False), id="503-no-build"),
    pytest.param(Request("GET", RAISING_PATH, 500), id="500"),
]


def raising_route() -> None:
    """The handler of the route that fails: an unhandled error."""
    raise RuntimeError("a route that raises, for the 500 of AC-10")


def add_raising_route(app: FastAPI) -> None:
    """Make `RAISING_PATH` the first route of the app, so that it answers."""
    app.router.routes.insert(0, APIRoute(RAISING_PATH, raising_route))


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.mark.parametrize("request_made", REQUESTS)
def test_ac10_every_answer_carries_the_security_headers(
    request_made: Request,
    registry: RoomRegistry,
    catalogue: Catalogue,
    tmp_path: Path,
) -> None:
    built_dir = make_dist_dir(tmp_path)
    dist_dir = built_dir if request_made.built else tmp_path / "no-build"
    app = edge_app(registry, dist_dir, catalogue)
    add_raising_route(app)

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.request(
            request_made.method,
            request_made.path,
            content=request_made.content,
            headers=request_made.headers,
        )

    carried = {name: response.headers.get(name) for name in EDGE_HEADERS}
    assert response.status_code == request_made.status
    assert carried == EDGE_HEADERS
    assert "x-frame-options" not in response.headers
