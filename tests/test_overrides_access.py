"""Tests of admin/overrides, AC-8: the token, the throttle and `no-store` on the
three settings routes, and the routes with the operator pages off.

The app is given a registry on the fake clock (`registry_app`), so the throttle's
minute never needs real time. The throttle is `admin/operations.md` rules 8 and 9:
ten refusals under a minute old block an address, a 401 counts, a 422 or a 405
never does. Each request is sent by `TestClient`, so every request comes from the
same address.

The shared setup is in `overrides_harness`; the answers' shapes and the unknown
path are spec 038's (`spec038_harness`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from overrides_harness import (
    DRY_RUN_PATH,
    INTERVAL,
    NO_STORE,
    SETTINGS_PATH,
    registry_app,
)
from spec017_harness import FakeClock
from spec038_harness import (
    NOT_AUTHORIZED,
    NOT_FOUND,
    OPS_TOKEN,
    TOO_MANY_REQUESTS,
    UNKNOWN_API_PATH,
    WRONG_CODE_LIMIT,
    answer_of,
    bearer,
)

CREATOR = "creator_room_hours"
ANONYMOUS = "anonymous_room_hours"
METHOD_NOT_ALLOWED = {"detail": "Method Not Allowed"}  # FastAPI's 405

SAVE_BODY: dict[str, object] = {"name": CREATOR, "value": 48}
DRY_RUN_BODY: dict[str, object] = {"name": ANONYMOUS, "value": 24}

GET_ROUTE = pytest.param("GET", SETTINGS_PATH, None, id="get")
PUT_ROUTE = pytest.param("PUT", SETTINGS_PATH, SAVE_BODY, id="put")
DRY_RUN_ROUTE = pytest.param("POST", DRY_RUN_PATH, DRY_RUN_BODY, id="dry-run")
THREE_ROUTES = [GET_ROUTE, PUT_ROUTE, DRY_RUN_ROUTE]
# The same routes with a body that the token check must come before.
ROUTES_WITH_BAD_BODIES = [
    *THREE_ROUTES,
    pytest.param("PUT", SETTINGS_PATH, {"name": "nope"}, id="put-bad-body"),
    pytest.param(
        "POST", DRY_RUN_PATH, {"name": INTERVAL, "value": 30}, id="dry-run-bad-body"
    ),
]


def send(
    client: TestClient,
    method: str,
    path: str,
    body: dict[str, object] | None,
    headers: dict[str, str] | None = None,
) -> Response:
    """One request to a settings route."""
    return client.request(method, path, json=body, headers=headers)


def refuse(client: TestClient, method: str, path: str, count: int) -> None:
    """Send `count` requests without a token; each must be a 401."""
    for _ in range(count):
        response = send(client, method, path, None)
        assert response.status_code == 401, response.text


# ---- AC-8: the token ----


@pytest.mark.parametrize("headers", [{}, bearer("wrong")], ids=["no-token", "wrong"])
@pytest.mark.parametrize(("method", "path", "body"), ROUTES_WITH_BAD_BODIES)
def test_ac8_each_route_without_the_token_answers_401_before_reading_the_body(
    tmp_path: Path,
    fake_clock: FakeClock,
    method: str,
    path: str,
    body: dict[str, object] | None,
    headers: dict[str, str],
) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        response = send(app.client, method, path, body, headers)

    assert response.status_code == 401, response.text
    assert response.json() == NOT_AUTHORIZED
    assert response.headers.get("www-authenticate") == "Bearer"
    assert response.headers.get("cache-control") == NO_STORE


# ---- AC-8: the throttle ----


@pytest.mark.parametrize(("method", "path", "body"), THREE_ROUTES)
def test_ac8_ten_refusals_of_a_route_throttle_the_right_token_on_the_dry_run(
    tmp_path: Path,
    fake_clock: FakeClock,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        refuse(app.client, method, path, WRONG_CODE_LIMIT)

        response = app.ops.dry_run(ANONYMOUS, 24)

    assert response.status_code == 429, response.text
    assert response.json() == TOO_MANY_REQUESTS


def test_ac8_nine_refusals_do_not_throttle(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        refuse(app.client, "GET", SETTINGS_PATH, WRONG_CODE_LIMIT - 1)

        response = app.ops.dry_run(ANONYMOUS, 24)

    assert response.status_code == 200, response.text


def test_ac8_a_422_on_a_put_or_a_dry_run_counts_nothing(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        for _ in range(WRONG_CODE_LIMIT):
            assert app.ops.put(CREATOR, 23).status_code == 422
            assert app.ops.dry_run(INTERVAL, 30).status_code == 422

        response = app.ops.settings()

    assert response.status_code == 200, response.text


def test_ac8_a_405_counts_nothing(tmp_path: Path, fake_clock: FakeClock) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        for _ in range(WRONG_CODE_LIMIT):
            assert app.client.delete(SETTINGS_PATH).status_code == 405

        response = app.ops.settings()

    assert response.status_code == 200, response.text


# ---- AC-8: no-store ----


def test_ac8_the_200_401_422_429_and_405_answers_carry_no_store(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with registry_app(tmp_path, clock=fake_clock) as app:
        answers = {
            "get 200": app.ops.settings(),
            "put 200": app.ops.put(CREATOR, 48),
            "dry run 200": app.ops.dry_run(ANONYMOUS, 24),
            "put 422": app.ops.put(CREATOR, 23),
            "dry run 422": app.ops.dry_run(INTERVAL, 30),
            "delete 405": app.client.delete(SETTINGS_PATH, headers=bearer(OPS_TOKEN)),
            "get 401": send(app.client, "GET", SETTINGS_PATH, None),
        }
        refuse(app.client, "GET", SETTINGS_PATH, WRONG_CODE_LIMIT - 1)
        answers["get 429"] = app.ops.settings()

    statuses: dict[str, int] = {}
    cache_controls: dict[str, str | None] = {}
    for name, response in answers.items():
        statuses[name] = response.status_code
        cache_controls[name] = response.headers.get("cache-control")
    assert statuses == {
        "get 200": 200,
        "put 200": 200,
        "dry run 200": 200,
        "put 422": 422,
        "dry run 422": 422,
        "delete 405": 405,
        "get 401": 401,
        "get 429": 429,
    }
    assert cache_controls == dict.fromkeys(answers, NO_STORE)
    assert answers["delete 405"].json() == METHOD_NOT_ALLOWED


# ---- AC-8: the pages off ----


@pytest.mark.parametrize(("method", "path", "body"), THREE_ROUTES)
def test_ac8_with_the_variable_unset_the_routes_answer_as_an_unknown_api_path(
    tmp_path: Path,
    fake_clock: FakeClock,
    method: str,
    path: str,
    body: dict[str, object] | None,
) -> None:
    with registry_app(tmp_path, clock=fake_clock, token=None) as app:
        headers = bearer(OPS_TOKEN)
        unknown = send(app.client, method, UNKNOWN_API_PATH, body, headers)

        response = send(app.client, method, path, body, headers)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert "cache-control" not in response.headers
    assert answer_of(response) == answer_of(unknown)
