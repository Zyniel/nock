"""Shared pytest fixtures."""

from __future__ import annotations

import re
import socket
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import uvicorn
from playwright.sync_api import Page, expect

from fonts_ready import wait_for_fonts

if TYPE_CHECKING:
    from nock.catalogue import Catalogue
    from nock.server import RoomRegistry

# The harness modules (`specNNN_harness.py` and the domains' `<name>_harness.py`)
# hold helpers with plain `assert`s. pytest rewrites the asserts of test files and
# conftests only, so every harness module is registered here: the call has to come
# before the first test module imports them. `sure_click` (2026-10-23) is a shared
# helper with a plain `assert`.
HARNESS_MODULES = sorted(
    path.stem for path in Path(__file__).parent.glob("*_harness.py")
)
pytest.register_assert_rewrite(*HARNESS_MODULES, "sure_click")

FIXTURES_DIR = Path(__file__).parent / "fixtures"

# Spec 038: the operator token. `create_app` reads it when the app starts, and
# `main()` checks it first.
OPERATOR_TOKEN_VARIABLE = "NOCK_OPERATOR_TOKEN"


@pytest.fixture(autouse=True)
def no_operator_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete NOCK_OPERATOR_TOKEN from the environment for every test (spec 038).

    A value left in the shell that runs the tests would otherwise switch the
    operator pages on in every app, or, when it is invalid, stop every app's
    startup and every `main()`. A test that needs the variable sets it itself.
    """
    monkeypatch.delenv(OPERATOR_TOKEN_VARIABLE, raising=False)


class FakeClock:
    """A clock a test moves by hand: a callable returning `now`.

    Pass it as `clock` to `RoomRegistry` (spec 011, "Test harness").
    """

    def __init__(self) -> None:
        self.now: float = 1_000_000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward by `seconds`."""
        self.now += seconds


@pytest.fixture
def fake_clock() -> FakeClock:
    """Return a fresh fake clock starting at 1_000_000.0."""
    return FakeClock()


ENTER_ROOM_TIMEOUT_MS = 10_000


def _enter_room(page: Page, url: str, nickname: str = "Ana") -> None:
    """Open a room page and wait until the player is in the room.

    Waits for `data-status` to be `joined` or `nickname` (spec 012). When it is
    `nickname`, fills `nickname-input` with `nickname`, submits and waits for
    `joined`.
    """
    page.goto(url)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute(
        "data-status", re.compile(r"^(joined|nickname)$"), timeout=ENTER_ROOM_TIMEOUT_MS
    )
    if room.get_attribute("data-status") == "nickname":
        nickname_input = page.get_by_test_id("nickname-input")
        nickname_input.fill(nickname)
        nickname_input.press("Enter")
        expect(room).to_have_attribute(
            "data-status", "joined", timeout=ENTER_ROOM_TIMEOUT_MS
        )
    wait_for_fonts(page)


@pytest.fixture
def fx01_text() -> str:
    """Return the JSON text of the FX-01 reference grid."""
    return (FIXTURES_DIR / "fx01.json").read_text(encoding="utf-8")


@pytest.fixture
def fx02_text() -> str:
    """Return the JSON text of the FX-02 full-size grid (13 by 17)."""
    return (FIXTURES_DIR / "fx02.json").read_text(encoding="utf-8")


MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"
SERVER_START_TIMEOUT_SECONDS = 10.0


@pytest.fixture
def room_registry() -> Iterator[RoomRegistry]:
    """Yield the empty room registry that the live server serves, then close it."""
    from nock.server import RoomRegistry

    registry = RoomRegistry()
    yield registry
    registry.close()


@pytest.fixture
def catalogue() -> Catalogue:
    """Return the catalogue that the live server serves (empty by default).

    A test module that needs grids overrides this fixture with its own.
    """
    from nock.catalogue import Catalogue

    return Catalogue()


def _bind_free_port() -> socket.socket:
    """Return a socket bound to a free port of 127.0.0.1."""
    free_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    free_socket.bind(("127.0.0.1", 0))
    return free_socket


@pytest.fixture
def live_server(room_registry: RoomRegistry, catalogue: Catalogue) -> Iterator[str]:
    """Run the real app on a free local port and yield its base URL.

    The app serves the real web/dist, `room_registry` and `catalogue`, so a test
    can register rooms after the server started. The server is built with
    `nock.server.server_config` (spec 036), so it has the production limits. The
    test fails (it is not skipped) when the client has not been built.
    """
    from nock.server import WEB_DIST_DIR, create_app, server_config

    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)

    app = create_app(rooms=room_registry, dist_dir=WEB_DIST_DIR, catalogue=catalogue)
    listening_socket = _bind_free_port()
    port = listening_socket.getsockname()[1]
    server = uvicorn.Server(server_config(app, log_level="warning"))
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listening_socket]}, daemon=True
    )
    thread.start()

    deadline = time.monotonic() + SERVER_START_TIMEOUT_SECONDS
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=SERVER_START_TIMEOUT_SECONDS)
        listening_socket.close()
        pytest.fail("the live server did not start")

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=SERVER_START_TIMEOUT_SECONDS)
        listening_socket.close()


@pytest.fixture
def enter_room() -> Callable[..., None]:
    """Return `enter_room(page, url, nickname="Ana")`, the helper of spec 011.

    It opens `url`, waits until the room page's `data-status` is `joined` or
    `nickname`, and when it is `nickname` fills `nickname-input`, submits and
    waits for `joined`.
    """
    return _enter_room
