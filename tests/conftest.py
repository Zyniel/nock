"""Shared pytest fixtures."""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import uvicorn

if TYPE_CHECKING:
    from nock.server import RoomRegistry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fx01_text() -> str:
    """Return the JSON text of the FX-01 reference grid."""
    return (FIXTURES_DIR / "fx01.json").read_text(encoding="utf-8")


MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"
SERVER_START_TIMEOUT_SECONDS = 10.0


@pytest.fixture
def room_registry() -> RoomRegistry:
    """Return the empty room registry that the live server serves."""
    from nock.server import RoomRegistry

    return RoomRegistry()


def _bind_free_port() -> socket.socket:
    """Return a socket bound to a free port of 127.0.0.1."""
    free_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    free_socket.bind(("127.0.0.1", 0))
    return free_socket


@pytest.fixture
def live_server(room_registry: RoomRegistry) -> Iterator[str]:
    """Run the real app on a free local port and yield its base URL.

    The app serves the real web/dist and `room_registry`, so a test can register
    rooms after the server started. The test fails (it is not skipped) when the
    client has not been built.
    """
    from nock.server import WEB_DIST_DIR, create_app

    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)

    app = create_app(rooms=room_registry, dist_dir=WEB_DIST_DIR)
    listening_socket = _bind_free_port()
    port = listening_socket.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level="warning"))
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
