"""Tests of account/account, AC-6: the wrong methods on the account routes.

HTTP, on the app of spec 033's "Test harness". The pointer's own cases (the
right methods, accounts off or on) are proven by `test_spec_033_ac08_*`; these
two requests are the wrong methods that it leaves out: `GET` to
`/api/account/link` and `POST` to `/account`.

- Accounts off: both answer 404 `{"detail": "Not Found"}`.
- Accounts on: both answer 405 `{"detail": "Method Not Allowed"}`, and the `GET`
  to `link` carries `Cache-Control: no-store`, since it is an answer under
  `/api/account`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.hub import RoomRegistry
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec032_harness import make_dist_dir
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    LINK_PATH,
    NOT_FOUND,
    account_app,
)

NO_STORE = "no-store"
METHOD_NOT_ALLOWED = {"detail": "Method Not Allowed"}

WRONG_METHODS = [
    pytest.param("GET", LINK_PATH, id="get-link"),
    pytest.param("POST", ACCOUNT_PAGE_PATH, id="post-account-page"),
]


@contextlib.contextmanager
def accounts_off_client(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The app of "Accounts off" in the "Test harness", with a built client."""
    monkeypatch.delenv("NOCK_PUBLIC_URL", raising=False)
    monkeypatch.delenv("NOCK_SMTP_HOST", raising=False)
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=clock, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))
        with TestClient(app) as client:
            yield client
    finally:
        registry.close()
        store.close()


@pytest.mark.parametrize(("method", "path"), WRONG_METHODS)
def test_ac6_with_accounts_off_a_wrong_method_answers_404(
    tmp_path: Path,
    fake_clock: FakeClock,
    monkeypatch: pytest.MonkeyPatch,
    method: str,
    path: str,
) -> None:
    with accounts_off_client(tmp_path, fake_clock, monkeypatch) as client:
        response = client.request(method, path)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


@pytest.mark.parametrize(("method", "path"), WRONG_METHODS)
def test_ac6_with_accounts_on_a_wrong_method_answers_405(
    tmp_path: Path, fake_clock: FakeClock, method: str, path: str
) -> None:
    with account_app(tmp_path, fake_clock, dist_dir=make_dist_dir(tmp_path)) as app:
        response = app.client.request(method, path)

    assert response.status_code == 405
    assert response.json() == METHOD_NOT_ALLOWED


def test_ac6_with_accounts_on_the_get_to_link_is_not_stored(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = app.client.get(LINK_PATH)

    assert response.status_code == 405
    assert response.headers["cache-control"] == NO_STORE
