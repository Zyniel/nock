"""Shared setup of the tests of spec 010: instant solo start.

This module is not a test file: pytest does not collect it. The tests of spec 010
are in `tests/test_spec_010_*.py`, one file per criterion group.

The page is tested against the real app (a live server, the catalogue of FX-01 as
entry 1) and against spec 040's mocked room socket (`MockRoomSocket`).

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid` and `catalogue`
are defined in each file as thin wrappers around `grid_from_text` and
`catalogue_from_grid`: a fixture imported from here would be an unused import for
ruff, and `live_server` needs the `catalogue` of its own file.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from playwright.sync_api import Locator, Page, WebSocket, WebSocketRoute, expect

import nock.room
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.protocol import (
    Join,
    Ping,
    PlayerState,
    PlayerView,
    Pong,
    RevealBudget,
    Snapshot,
    grid_view,
    parse_client_message,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 500
URL_TIMEOUT_MS = 10_000
MOCK_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
MOCK_CODE = "ABC123"
PROGRESS_KEY = "nock.progress"
ROOM_URL_PATTERN = re.compile(r"/r/[A-Z0-9]{6}$")
ROOM_RECORD_KEY = f"nock.room.{MOCK_CODE}"
CATALOGUE_RECORD = json.dumps({"grid": 1, "selection": None})


# ---- Fixtures and helpers ---------------------------------------------------


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def catalogue_from_grid(grid: Grid) -> Catalogue:
    """A catalogue holding `grid` as published entry 1, force 2.

    This is the body of the `catalogue` fixture of each test file.
    """
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=grid,
    )
    return Catalogue(entries=(entry,))


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click()


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to do things that must not happen."""
    page.wait_for_timeout(SETTLE_MS)


def read_storage(page: Page, key: str) -> str | None:
    raw = page.evaluate("key => localStorage.getItem(key)", key)
    if raw is None:
        return None
    assert isinstance(raw, str)
    return raw


def wait_for_storage(page: Page, key: str) -> str:
    """Return the value of `key` once the page has written it."""
    waited_ms = 0
    while waited_ms < WAIT_TIMEOUT_MS:
        value = read_storage(page, key)
        if value is not None:
            return value
        page.wait_for_timeout(50)
        waited_ms += 50
    pytest.fail(f"the page never wrote localStorage[{key!r}]")


def read_json_object(page: Page, key: str) -> dict[str, object]:
    """Return `localStorage[key]` parsed as a JSON object."""
    raw = read_storage(page, key)
    assert raw is not None, f"localStorage[{key!r}] is absent"
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), raw
    return parsed


def seed_local_storage(page: Page, items: dict[str, str]) -> None:
    """Fill absent `localStorage` keys before the page's own scripts run.

    The script runs again on every navigation, so it must not overwrite
    values the client wrote since.
    """
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " if (localStorage.getItem(key) === null) {"
        " localStorage.setItem(key, value); } }"
    )
    page.context.add_init_script(script)


def item_play_button(page: Page, number: int = 1) -> Locator:
    selector = f'[data-testid="catalogue-item"][data-number="{number}"]'
    return page.locator(selector).get_by_test_id("catalogue-play")


def code_from_url(url: str) -> str:
    match = re.search(r"/r/([A-Z0-9]{6})$", url)
    assert match is not None, url
    return match.group(1)


def start_from_catalogue(page: Page, base_url: str) -> str:
    """Click play on item 1 of `/` and return the code of the room it loads."""
    page.goto(f"{base_url}/")
    item_play_button(page).click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    return code_from_url(page.url)


def expect_joined(page: Page) -> Locator:
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined", timeout=URL_TIMEOUT_MS)
    return room


def is_firefox(page: Page) -> bool:
    browser = page.context.browser
    return browser is not None and browser.browser_type.name == "firefox"


def fix_firefox_text(payload: str) -> str:
    """Undo Playwright's Firefox delivering UTF-8 text frames as latin-1."""
    try:
        return payload.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return payload


def without_pings(frames: list[str]) -> list[str]:
    """The frames without the keep-alive `ping` frames of the page.

    The page sends a `ping` every 2 s once the socket is open (spec 017), so one
    can fall between two reads whatever the test does.
    """
    kept: list[str] = []
    for frame in frames:
        if json.loads(frame)["type"] != "ping":
            kept.append(frame)
    return kept


class FrameRecorder:
    """The frames a page sends on its room sockets, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[str] = []
        self.is_firefox = is_firefox(page)
        page.on("websocket", self._on_socket)

    def _on_socket(self, websocket: WebSocket) -> None:
        if websocket.url.endswith("/ws"):
            websocket.on("framesent", self._on_frame)

    def _on_frame(self, payload: str | bytes) -> None:
        if isinstance(payload, str):
            text = fix_firefox_text(payload) if self.is_firefox else payload
        else:
            text = payload.decode("utf-8")
        self.frames.append(text)

    def wait_for_frames(self, count: int) -> None:
        """Wait until the page has sent `count` frames, `ping` frames not counted."""
        wait_until(self.page, lambda: len(without_pings(self.frames)) >= count)

    def first_join(self) -> Join:
        self.wait_for_frames(1)
        first_frame = without_pings(self.frames)[0]
        message = parse_client_message(first_frame)
        assert isinstance(message, Join), first_frame
        return message


# ---- Mocked socket ----------------------------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the route
    that sent it: without the answer, the page takes 4 s without a frame from the
    server for a lost connection (spec 017, AC-4), so a step that takes longer on a
    slow engine would find the page `reconnecting`.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)

        def on_message(message: str | bytes) -> None:
            self._record_and_answer(route, message)

        route.on_message(on_message)

    def _record_and_answer(self, route: WebSocketRoute, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)
        if parse_client_message(text) == Ping():
            route.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def close(self, code: int) -> None:
        self.routes[0].close(code=code)

    def frames_without_pings(self) -> list[str]:
        """The frames the page sent, without its keep-alive `ping` frames."""
        return without_pings(self.received)

    def wait_for_frames(self, count: int) -> None:
        """Wait until the page has sent `count` frames, `ping` frames not counted."""
        wait_until(self.page, lambda: len(self.frames_without_pings()) >= count)

    def first_join(self) -> Join:
        self.wait_for_frames(1)
        first_frame = self.frames_without_pings()[0]
        message = parse_client_message(first_frame)
        assert isinstance(message, Join), first_frame
        return message


def open_mock_room(
    page: Page, base_url: str, items: dict[str, str] | None = None
) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and `localStorage` seeded with `items`."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    if items:
        seed_local_storage(page, items)
    page.goto(f"{base_url}/r/{MOCK_CODE}")
    return mock


def submit_form(page: Page, nickname: str) -> None:
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)


def snapshot_of(grid: Grid, solved: bool = False, seq: int = 0) -> Snapshot:
    you = PlayerView(
        player_id="p1",
        nickname="Ana",
        colour=0,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )
    return Snapshot(
        seq=seq,
        you="p1",
        resume_token=MOCK_TOKEN,
        grid=grid_view(grid),
        players=(you,),
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )


def send_snapshot(mock: MockRoomSocket, grid: Grid, solved: bool = False) -> None:
    mock.send(snapshot_of(grid, solved).model_dump_json())
    expect(mock.page.get_by_test_id("cell")).to_have_count(25)
