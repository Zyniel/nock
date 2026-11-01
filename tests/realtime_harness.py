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

The second part of this module, "A page's socket passed to the live server", is
the setup of the tests of what a page sends after a reconnection (rules 20 and
22): `test_realtime_reconnection_selection.py` (AC-24),
`test_server_offline_undo.py` (`platform/server.md` AC-29) and
`test_hints_offline_requests.py` (`gameplay/hints.md` AC-24). Each page's room
socket goes through Playwright's `route_web_socket` to the live server, and the
proxy keeps every frame of both ways. A test takes a page's socket away with
`go_offline`: the proxy closes it on both sides, as a loss, and closes every new
socket of the page at once until `come_back`, which lets the next one through and
fires the browser's `online` event, so the page tries at once (rule 21). What the
page does offline is so never sent too early, whatever the speed of the machine.
`come_back(is_holding=True)` also holds what the server sends on the new socket
until the test releases it, so a test can pause the page clock before the page
reads its snapshot. A page whose clock is paused must not open a socket that the
proxy refuses: the close would wait for the page's timers.
"""

from __future__ import annotations

import contextlib
import re
import time
from collections.abc import Iterator
from contextlib import ExitStack
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.protocol import (
    Check,
    ClientMessage,
    EditLetter,
    Erase,
    Ping,
    Pong,
    Reveal,
    ServerMessage,
    Snapshot,
    Undo,
    parse_client_message,
    parse_server_message,
)
from spec014_harness import Peer, socket_url
from spec024_harness import EnterRoom
from spec042_harness import wait_until

SOCKETS_VARIABLE = "NOCK_SOCKETS_PER_ADDRESS"
DEFAULT_SOCKET_CAP = 50
TOO_MANY_SOCKETS_CLOSE_CODE = 4503
SILENT_CLOSE_CODE = 4408
ROOM_NOT_FOUND_CLOSE_CODE = 4404
THROTTLED_CLOSE_CODE = 4429
WRONG_CODE_LIMIT = 10  # the closes 4404 an address gets before 4429
WRONG_CODE_WINDOW_SECONDS = 60.0  # the minute of the throttle (`lobby/rooms.md`)
UNKNOWN_CODE = "ZZZZZZ"
OTHER_ADDRESS = "10.0.0.2"
RETRY_LIMIT_SECONDS = 5.0
RETRY_PAUSE_SECONDS = 0.05


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


def try_socket_until_counted(
    client: TestClient, code: str, parent: ExitStack
) -> OpenSocket:
    """Try sockets until one is not closed with 4503; return that one.

    The socket returned is served or closed with another code. A closed socket
    frees its place when the server notices it, a little later: the tries go on
    for `RETRY_LIMIT_SECONDS`, then fail the test.
    """
    deadline = time.monotonic() + RETRY_LIMIT_SECONDS
    while True:
        socket = try_socket(client, code, parent)
        if socket.peer.close_code != TOO_MANY_SOCKETS_CLOSE_CODE:
            return socket
        if time.monotonic() >= deadline:
            pytest.fail(
                f"every socket was still closed with 4503 after {RETRY_LIMIT_SECONDS} s"
            )
        time.sleep(RETRY_PAUSE_SECONDS)


def try_socket_until_free(
    client: TestClient, code: str, parent: ExitStack
) -> OpenSocket:
    """Try sockets until one is served; a close other than 4503 fails the test.

    The tries are those of `try_socket_until_counted`.
    """
    socket = try_socket_until_counted(client, code, parent)
    assert is_served(
        socket
    ), f"the socket was closed with {socket.peer.close_code}, not 4503"
    return socket


def client_from_another_address(client: TestClient) -> TestClient:
    """A client of the same running app that comes from `OTHER_ADDRESS`.

    It is not entered as a context: the app is already started by `client`.
    """
    return TestClient(client.app, client=(OTHER_ADDRESS, 50000))


# ---- A page's socket passed to the live server ----------------------------------

LOST_CLOSE_CODE = 1011  # a close that is a loss (rule 19): the page tries again
PLAYER_VIEWPORT = {"width": 1280, "height": 720}
REQUESTS_WAIT_MS = 5000
REQUESTS_POLL_MS = 50
# The messages that rule 22 sends again, or keeps, in the order they were made.
OFFLINE_REQUEST_TYPES = (EditLetter, Erase, Undo, Check, Reveal)


def frame_text(frame: str | bytes) -> str:
    """The text of a WebSocket frame; a binary frame is read as UTF-8."""
    if isinstance(frame, str):
        return frame
    return frame.decode("utf-8")


class ProxiedSocket:
    """One socket of a page, connected to the live server, both ways recorded.

    A socket that holds keeps what the server sends from the page, in order,
    until `release`; it records it all the same.

    Attributes:
        sent: Every message the page sent on it, in order, pings included.
        received: Every message the server sent on it, in order.
    """

    def __init__(self, route: WebSocketRoute, is_holding: bool) -> None:
        self._route = route
        self._server = route.connect_to_server()
        self._is_holding = is_holding
        self._held: list[str] = []
        self.sent: list[ClientMessage] = []
        self.received: list[ServerMessage] = []
        route.on_message(self._from_page)
        self._server.on_message(self._from_server)

    def _from_page(self, frame: str | bytes) -> None:
        text = frame_text(frame)
        self.sent.append(parse_client_message(text))
        self._server.send(text)

    def _from_server(self, frame: str | bytes) -> None:
        text = frame_text(frame)
        self.received.append(parse_server_message(text))
        if self._is_holding:
            self._held.append(text)
            return
        self._route.send(text)

    def release(self) -> None:
        """Pass to the page what the socket held, in order, and stop holding."""
        self._is_holding = False
        for text in self._held:
            self._route.send(text)
        self._held = []

    def drop(self) -> None:
        """Close the socket on both sides: the page sees a loss, the server a close."""
        self._route.close(code=LOST_CLOSE_CODE)
        self._server.close()

    def requests(self) -> list[ClientMessage]:
        """The edits, erases, undos, checks and reveals the page sent, in order."""
        found: list[ClientMessage] = []
        for message in self.sent:
            if isinstance(message, OFFLINE_REQUEST_TYPES):
                found.append(message)
        return found

    def has_snapshot(self) -> bool:
        """Whether the server answered a join on this socket with a snapshot."""
        return any(isinstance(message, Snapshot) for message in self.received)


class RoomSocketProxy:
    """Every room socket a page opens, passed to the live server, in order.

    Created before the page opens the room. While the proxy refuses, it closes a
    new socket at once with `LOST_CLOSE_CODE`, without reaching the server. A
    page whose clock is paused must not open a socket the proxy refuses: the
    close would wait for the page's timers.
    """

    def __init__(self, page: Page, code: str) -> None:
        self._page = page
        self._is_refusing = False
        self._is_holding_next = False
        self.sockets: list[ProxiedSocket] = []
        pattern = re.compile(rf".*/api/rooms/{code}/ws$")
        page.route_web_socket(pattern, self._handle)

    def _handle(self, route: WebSocketRoute) -> None:
        if self._is_refusing:
            route.close(code=LOST_CLOSE_CODE)
            return
        self.sockets.append(ProxiedSocket(route, self._is_holding_next))
        self._is_holding_next = False

    def latest(self) -> ProxiedSocket:
        """The page's newest socket that reached the server."""
        assert self.sockets, "the page opened no socket to the server"
        return self.sockets[-1]

    def go_offline(self) -> None:
        """Drop the page's socket and refuse its new ones until `come_back`."""
        self._is_refusing = True
        self.latest().drop()

    def come_back(self, is_holding: bool = False) -> ProxiedSocket:
        """Let the next socket through, make the page try at once, and return it.

        Args:
            is_holding: True to hold what the server sends on the new socket
                until the test calls its `release`.

        Returns:
            The page's new socket, once it reached the server. Its join and the
            snapshot that answers it may still be on their way.
        """
        count = len(self.sockets)
        self._is_holding_next = is_holding
        self._is_refusing = False
        self._page.evaluate("() => window.dispatchEvent(new Event('online'))")
        wait_until(
            self._page,
            lambda: len(self.sockets) > count,
            "the page's socket after its return",
        )
        return self.latest()


class Player(NamedTuple):
    """A player's page in a room of the live server, its socket proxy and its id."""

    page: Page
    proxy: RoomSocketProxy
    player_id: str


def enter_through_proxy(
    page: Page, live_server: str, code: str, nickname: str, enter: EnterRoom
) -> Player:
    """Open room `code` on `page` behind a `RoomSocketProxy` and enter it.

    Args:
        page: A fresh page.
        live_server: The live server's base URL.
        code: The room's code.
        nickname: The nickname typed in the form.
        enter: The `enter_room` fixture of conftest.

    Returns:
        The player, once the page shows the room as joined.
    """
    proxy = RoomSocketProxy(page, code)
    enter(page, f"{live_server}/r/{code}", nickname)
    player_id = page.get_by_test_id("room-page").get_attribute("data-you")
    assert player_id, "the joined page names no player of its own"
    return Player(page=page, proxy=proxy, player_id=player_id)


@contextlib.contextmanager
def other_player(
    browser: Browser, live_server: str, code: str, nickname: str, enter: EnterRoom
) -> Iterator[Player]:
    """Yield a second player, on a page of its own context; close it on the way out.

    Args:
        browser: The browser of the test.
        live_server: The live server's base URL.
        code: The room's code.
        nickname: The nickname typed in the form.
        enter: The `enter_room` fixture of conftest.
    """
    context = browser.new_context(viewport=PLAYER_VIEWPORT)
    try:
        page = context.new_page()
        yield enter_through_proxy(page, live_server, code, nickname, enter)
    finally:
        context.close()


def page_seq(page: Page) -> int:
    """The seq the room page has applied (`data-seq`)."""
    seq = page.get_by_test_id("room-page").get_attribute("data-seq")
    assert seq, "the room page has no seq"
    return int(seq)


def expect_reconnecting(page: Page) -> None:
    """Wait until the page knows its socket is lost (rule 20)."""
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "reconnecting"
    )


def rejoin(player: Player) -> ProxiedSocket:
    """Bring a player's page back after `go_offline`; return once it is joined.

    Returns:
        The new socket, once the server answered its join with a snapshot and the
        page shows the room as joined.
    """
    socket = player.proxy.come_back()
    wait_until(player.page, socket.has_snapshot, "the snapshot of the return")
    expect(player.page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "joined"
    )
    return socket


def wait_for_requests(page: Page, socket: ProxiedSocket, count: int) -> None:
    """Wait until the page sent `count` edits, undos, checks or reveals on `socket`.

    Fails with the requests sent so far when fewer came.
    """
    waited_ms = 0
    while len(socket.requests()) < count:
        if waited_ms >= REQUESTS_WAIT_MS:
            pytest.fail(
                f"the page sent {socket.requests()} after its return,"
                f" not {count} requests"
            )
        page.wait_for_timeout(REQUESTS_POLL_MS)
        waited_ms += REQUESTS_POLL_MS
