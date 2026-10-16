"""Tests of spec 038 (privacy and operations), AC-1 and AC-2: what a guest leaves.

Both run a probe browser context (`user_agent="NockPrivacyProbe/7.3"`,
`extra_http_headers={"X-Nock-Probe": "probe-header-91"}`, `locale="fr-FR"`) on the
live server of the spec's "Test harness": a file database in `tmp_path` and
`operator_token=OPS_TOKEN` (`ops_live_server` of `spec038_harness`). The test
records every request, response and socket of the page.

AC-1 enters a FX-01 room as `Ana` (spec 011's `enter_room`), types `T`, `A`, `M`
from (1, 0) across, then closes the registry (which saves a snapshot) and the
store, and searches the bytes of `nock.sqlite3` and `nock.sqlite3-wal`. AC-2 opens
`/`, starts FX-01 from the catalogue (spec 010), types the 18 letters word by
word, 60 ms apart (spec 037's harness), and waits for `data-solved="true"` (spec
026).

Edge case checked as well: the page's sockets go to the server's origin too
(`ws://127.0.0.1:<port>`), as do each engine's own requests, such as the favicon.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from playwright.sync_api import Browser, Page, Request, Response, WebSocket, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec010_harness import catalogue_from_grid, expect_joined, start_from_catalogue
from spec038_harness import (
    KEY_PAUSE_MS,
    OPS_TIMEOUT_MS,
    OpsServer,
    cell_at,
    database_bytes,
    ops_live_server,
    strings_in,
    type_across,
    wait_for_room_letters,
)

# ---- Values of the spec --------------------------------------------------------------

PROBE_USER_AGENT = "NockPrivacyProbe/7.3"
PROBE_HEADER_NAME = "X-Nock-Probe"
PROBE_HEADER_VALUE = "probe-header-91"
PROBE_LOCALE = "fr-FR"
CLIENT_ADDRESS = "127.0.0.1"
# What the files must not hold: the browser's name, its header, its language and
# the client's address.
PROBE_STRINGS = ["NockPrivacyProbe", PROBE_HEADER_VALUE, PROBE_LOCALE, CLIENT_ADDRESS]
STORED_NICKNAME = "ANA"  # `Ana` as the server stores it (spec 012)

# The 18 letters of FX-01 word by word: TAMIS, NAVAL, MIME, IDES, SENT, then VIDE,
# AMEN and LEST through their crossing letters; a cell already typed is not typed
# again (spec 037's browser game).
FX01_GAME: list[tuple[int, int, str]] = [
    (1, 0, "t"),
    (1, 1, "a"),
    (1, 2, "m"),
    (1, 3, "i"),
    (1, 4, "s"),
    (0, 1, "n"),
    (2, 1, "v"),
    (3, 1, "a"),
    (4, 1, "l"),
    (2, 2, "i"),
    (3, 2, "m"),
    (4, 2, "e"),
    (2, 3, "d"),
    (3, 3, "e"),
    (4, 3, "s"),
    (2, 4, "e"),
    (3, 4, "n"),
    (4, 4, "t"),
]


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


# ---- Fixtures ------------------------------------------------------------------------


class Traffic:
    """What a page asked for and got: request URLs, responses and socket URLs."""

    def __init__(self) -> None:
        self.request_urls: list[str] = []
        self.responses: list[Response] = []
        self.socket_urls: list[str] = []

    def watch(self, page: Page) -> None:
        """Record the requests, responses and sockets of `page` from now on."""
        page.on("request", self.keep_request)
        page.on("response", self.keep_response)
        page.on("websocket", self.keep_socket)

    def keep_request(self, request: Request) -> None:
        self.request_urls.append(request.url)

    def keep_response(self, response: Response) -> None:
        self.responses.append(response)

    def keep_socket(self, websocket: WebSocket) -> None:
        self.socket_urls.append(websocket.url)


class Probe(NamedTuple):
    """The probe context's page and what it records."""

    page: Page
    traffic: Traffic


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (spec 010's catalogue)."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


@pytest.fixture
def probe(browser: Browser) -> Iterator[Probe]:
    """A page in the probe context of the spec's "Test harness", recording."""
    context = browser.new_context(
        user_agent=PROBE_USER_AGENT,
        extra_http_headers={PROBE_HEADER_NAME: PROBE_HEADER_VALUE},
        locale=PROBE_LOCALE,
    )
    try:
        page = context.new_page()
        traffic = Traffic()
        traffic.watch(page)
        yield Probe(page=page, traffic=traffic)
    finally:
        context.close()


# ---- AC-1: a guest is stored as a nickname and a random identifier ------------------


class StoredGuest(NamedTuple):
    """The bytes of the database files once closed, and Ana's player id."""

    data: bytes
    player_id: str


def play_then_close(
    probe: Probe, server: OpsServer, grid: Grid, enter_room: EnterRoom
) -> StoredGuest:
    """Ana enters a FX-01 room and types TAM; then the registry and store close."""
    code = server.registry.register_room(grid)
    enter_room(probe.page, f"{server.base_url}/r/{code}", "Ana")
    player_id = probe.page.get_by_test_id("room-page").get_attribute("data-you")
    assert player_id, "the room page shows no data-you"
    type_across(probe.page, 1, 0, "tam")
    letters = {(1, 0): "T", (1, 1): "A", (1, 2): "M"}
    wait_for_room_letters(server.registry, code, letters)

    server.registry.close()  # saves a snapshot of the room
    server.store.close()
    return StoredGuest(data=database_bytes(server.database_path), player_id=player_id)


def test_ac1_the_files_hold_the_stored_nickname_and_the_player_id(
    probe: Probe, server: OpsServer, fx01_grid: Grid, enter_room: EnterRoom
) -> None:
    stored = play_then_close(probe, server, fx01_grid, enter_room)

    expected = [STORED_NICKNAME, stored.player_id]
    assert strings_in(stored.data, expected) == expected


def test_ac1_the_files_hold_nothing_of_the_browser_and_no_address(
    probe: Probe, server: OpsServer, fx01_grid: Grid, enter_room: EnterRoom
) -> None:
    stored = play_then_close(probe, server, fx01_grid, enter_room)

    assert strings_in(stored.data, PROBE_STRINGS) == []


def test_ac1_the_probe_page_sent_the_probe_header(
    probe: Probe, server: OpsServer
) -> None:
    # The probe reaches the server: without it, AC-1 would show nothing.
    with probe.page.expect_request(f"{server.base_url}/") as caught:
        probe.page.goto(f"{server.base_url}/")

    headers = caught.value.all_headers()
    assert headers.get(PROBE_HEADER_NAME.lower()) == PROBE_HEADER_VALUE
    assert headers.get("user-agent") == PROBE_USER_AGENT


# ---- AC-2: no cookie, and no request to another origin -------------------------------


def solve_from_the_catalogue(page: Page, base_url: str) -> None:
    """Open `/`, start FX-01 from the catalogue and type its 18 letters."""
    start_from_catalogue(page, base_url)
    room = expect_joined(page)
    for row, column, key in FX01_GAME:
        cell_at(page, row, column).click()
        page.keyboard.press(key)
        page.wait_for_timeout(KEY_PAUSE_MS)
    expect(room).to_have_attribute("data-solved", "true", timeout=OPS_TIMEOUT_MS)


def test_ac2_a_whole_game_sets_no_cookie(probe: Probe, server: OpsServer) -> None:
    solve_from_the_catalogue(probe.page, server.base_url)

    responses_with_cookies: list[str] = []
    for response in probe.traffic.responses:
        if "set-cookie" in response.all_headers():
            responses_with_cookies.append(response.url)
    assert len(probe.traffic.responses) > 0
    assert responses_with_cookies == []
    assert probe.page.context.cookies() == []
    assert probe.page.evaluate("() => document.cookie") == ""


def test_ac2_every_request_of_a_whole_game_goes_to_the_servers_origin(
    probe: Probe, server: OpsServer
) -> None:
    solve_from_the_catalogue(probe.page, server.base_url)

    http_origin = f"{server.base_url}/"
    socket_origin = server.base_url.replace("http://", "ws://", 1) + "/"
    elsewhere: list[str] = []
    for url in probe.traffic.request_urls:
        if not url.startswith(http_origin):
            elsewhere.append(url)
    for url in probe.traffic.socket_urls:
        if not url.startswith(socket_origin):
            elsewhere.append(url)
    assert len(probe.traffic.request_urls) > 0
    assert len(probe.traffic.socket_urls) > 0
    assert elsewhere == []
