"""Shared setup of the tests of platform/realtime about the sockets of one address
and the join deadline (AC-21 to AC-23).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_realtime_*.py`:

- `test_realtime_join_deadline.py`: AC-21, the 4408 close of a socket that does
  not join. It measures time windows, so it runs on its own
  (`SERIAL_TEST_FILES`).
- `test_realtime_socket_cap.py`: AC-22, the cap of 50 sockets per address, with a
  registry the test gives the app.
- `test_realtime_sockets_variable.py`: AC-23, the variable
  `NOCK_SOCKETS_PER_ADDRESS`, read by an app that builds its own registry, by
  `main()` and by `python -m nock`.

A socket the tests count is one that stays open and not joined: it is opened, and
one `ping` is sent. The server answers a `pong` (the socket is open and was
counted: the count comes before any frame is read), or closes it (the count was
full, 4503). Sending a frame is how a test knows that the socket reached the
server's loop, whichever way the server counts it.

Every test of these files clears the variables an app reads at its start first
(`lifetime_harness.variables_of`), so that a value left in the shell changes
nothing.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from nock.protocol import Ping, Pong
from spec014_harness import Peer, socket_url

SOCKETS_VARIABLE = "NOCK_SOCKETS_PER_ADDRESS"
DEFAULT_SOCKET_CAP = 50
TOO_MANY_SOCKETS_CLOSE_CODE = 4503
SILENT_CLOSE_CODE = 4408
WRONG_CODE_LIMIT = 10  # the closes 4404 an address gets before 4429
OTHER_ADDRESS = "10.0.0.2"
RETRY_LIMIT_SECONDS = 5.0
RETRY_PAUSE_SECONDS = 0.05
GRID_NUMBER = 1  # the number of the grid of `spec024_harness.make_catalogue`


class OpenSocket(NamedTuple):
    """A socket a test opened: its session, what it received, its own exit stack."""

    websocket: WebSocketTestSession
    peer: Peer
    stack: ExitStack

    def close(self) -> None:
        """Close the socket from the client's side."""
        self.stack.close()


def open_socket(client: TestClient, code: str, parent: ExitStack) -> OpenSocket:
    """Open a socket to room `code`, sending nothing; `parent` closes it at the end."""
    own_stack = ExitStack()
    parent.callback(own_stack.close)
    websocket = own_stack.enter_context(client.websocket_connect(socket_url(code)))
    return OpenSocket(websocket, Peer(websocket), own_stack)


def received_pong(peer: Peer) -> bool:
    """Whether the peer received a `pong`."""
    return any(isinstance(message, Pong) for message in peer.messages())


def try_socket(client: TestClient, code: str, parent: ExitStack) -> OpenSocket:
    """Open a socket, send one ping, and return once it is answered or closed.

    The socket is served when it received a pong and has no close code; it is
    refused when it has a close code.
    """
    socket = open_socket(client, code, parent)
    socket.websocket.send_text(Ping().model_dump_json())
    socket.peer.wait_until(
        lambda: received_pong(socket.peer) or socket.peer.close_code is not None,
        "the pong or the close of the socket",
    )
    return socket


def is_served(socket: OpenSocket) -> bool:
    """Whether a socket of `try_socket` was answered and is still open."""
    return received_pong(socket.peer) and socket.peer.close_code is None


def fill_address(
    client: TestClient, code: str, parent: ExitStack, count: int
) -> list[OpenSocket]:
    """Open `count` sockets that stay open; fail when one of them is not served."""
    sockets: list[OpenSocket] = []
    for number in range(1, count + 1):
        socket = try_socket(client, code, parent)
        assert is_served(
            socket
        ), f"socket {number} of {count} was closed with {socket.peer.close_code}"
        sockets.append(socket)
    return sockets


def try_socket_until_free(
    client: TestClient, code: str, parent: ExitStack
) -> OpenSocket:
    """Try sockets until one is served; a close other than 4503 fails the test.

    A closed socket frees its place when the server notices it, a little later:
    the tries go on for `RETRY_LIMIT_SECONDS`.
    """
    deadline = time.monotonic() + RETRY_LIMIT_SECONDS
    while True:
        socket = try_socket(client, code, parent)
        if is_served(socket):
            return socket
        close_code = socket.peer.close_code
        assert (
            close_code == TOO_MANY_SOCKETS_CLOSE_CODE
        ), f"the socket was closed with {close_code}, not 4503"
        if time.monotonic() >= deadline:
            pytest.fail(f"every socket was still refused after {RETRY_LIMIT_SECONDS} s")
        time.sleep(RETRY_PAUSE_SECONDS)


def client_from_another_address(client: TestClient) -> TestClient:
    """A client of the same running app that comes from `OTHER_ADDRESS`.

    It is not entered as a context: the app is already started by `client`.
    """
    return TestClient(client.app, client=(OTHER_ADDRESS, 50000))
