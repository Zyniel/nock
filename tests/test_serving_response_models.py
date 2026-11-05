"""Tests of platform/serving, AC-15: every /api route declares its answer's type.

The app is the HTTP edge tests' one: the operator pages on and the accounts on, so
that every route under `/api/` exists. The test walks `app.routes` and reads the
`response_model` that each HTTP route declares; FastAPI also derives one from a
return annotation, so `dict[str, object]` is what a route written without a model
shows, and the test refuses it by what it must be instead.

Choices where the spec leaves room:

- "A route that answers 204" is a route declared with `status_code=204`.
- "A model" is a subclass of pydantic's `BaseModel`; "a list of models" is
  `list[Model]`; the progress route's map is
  `dict[str, Literal["started", "finished"]]`.
- The WebSocket route is no HTTP route and is not walked.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal, get_args, get_origin

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute
from pydantic import BaseModel

from nock.accounts import AccountStore
from nock.catalogue import Catalogue
from nock.hub import RoomRegistry
from serving_harness import account_store as account_store
from serving_harness import edge_app
from serving_harness import registry as registry

CATALOGUE_KIND = "published"

API_PREFIX = "/api/"
NO_MODEL_ROUTE = ("GET", "/api/rooms")
PROGRESS_ROUTE = ("GET", "/api/account/progress")
PROGRESS_MODEL = dict[str, Literal["started", "finished"]]
NO_CONTENT = 204


@pytest.fixture
def app(
    registry: RoomRegistry,
    catalogue: Catalogue,
    account_store: AccountStore,
    tmp_path: Path,
) -> FastAPI:
    """The app with operator pages on, accounts on and FX-01 as grid 1."""
    return edge_app(registry, tmp_path / "no-build", catalogue, account_store)


def api_routes(app: FastAPI) -> dict[tuple[str, str], APIRoute]:
    """The HTTP routes under `/api/`, by (method, path)."""
    routes: dict[tuple[str, str], APIRoute] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute) or not route.path.startswith(API_PREFIX):
            continue
        methods = route.methods if route.methods is not None else set()
        for method in sorted(methods):
            routes[(method, route.path)] = route
    return routes


def is_model(declared: object) -> bool:
    """True when `declared` is a pydantic model class."""
    return isinstance(declared, type) and issubclass(declared, BaseModel)


def is_list_of_models(declared: object) -> bool:
    """True when `declared` is `list[Model]`."""
    if get_origin(declared) is not list:
        return False
    (item,) = get_args(declared)
    return is_model(item)


def test_ac15_each_api_route_that_answers_a_body_declares_a_model(
    app: FastAPI,
) -> None:
    refused: list[str] = []
    for (method, path), route in api_routes(app).items():
        if route.status_code == NO_CONTENT or (method, path) == NO_MODEL_ROUTE:
            continue
        declared = route.response_model
        allowed = is_model(declared) or is_list_of_models(declared)
        if (method, path) == PROGRESS_ROUTE:
            allowed = declared == PROGRESS_MODEL
        if not allowed:
            refused.append(f"{method} {path}: {declared!r}")

    assert refused == []


def test_ac15_the_routes_of_the_criterion_are_among_those_walked(
    app: FastAPI,
) -> None:
    routes = api_routes(app)

    assert ("GET", "/api/ops/settings") in routes
    assert ("GET", "/api/grids") in routes
    assert ("GET", "/api/rooms") in routes
    assert ("DELETE", "/api/account") in routes
    assert ("GET", "/api/account/progress") in routes


def test_ac15_get_ops_settings_declares_a_model(app: FastAPI) -> None:
    declared = api_routes(app)[("GET", "/api/ops/settings")].response_model

    assert is_model(declared), declared


def test_ac15_get_grids_declares_a_list_of_a_model(app: FastAPI) -> None:
    declared = api_routes(app)[("GET", "/api/grids")].response_model

    assert is_list_of_models(declared), declared


def test_ac15_the_progress_route_declares_a_map_to_started_or_finished(
    app: FastAPI,
) -> None:
    declared = api_routes(app)[PROGRESS_ROUTE].response_model

    assert declared == PROGRESS_MODEL


@pytest.mark.parametrize(
    ("method", "path"),
    [NO_MODEL_ROUTE, ("DELETE", "/api/account")],
    ids=["get-rooms", "delete-account"],
)
def test_ac15_get_rooms_and_the_204_of_delete_account_declare_none(
    app: FastAPI, method: str, path: str
) -> None:
    declared = api_routes(app)[(method, path)].response_model

    assert declared is None
