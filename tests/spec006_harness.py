"""Shared setup of the tests of spec 006: grid rendering.

This module is not a test file: pytest does not collect it. The tests of spec 006
are in `tests/test_spec_006_*.py`, one file per criterion group.

It holds what more than one of those files uses: the timeouts, the window sizes of
AC-5 and AC-7, the helpers that open a room on a live server (`open_room`) or on
the mocked socket (`open_mock_room`), the snapshot builders of AC-4, AC-6 and
AC-8, and AC-1's pinch through CDP (`pinch`, also used by the tests of
`client/shell.md` AC-25). What only one file uses stays in that file, next to its
tests. The fixtures
`fx01_grid` and `fx02_grid` are defined in each file as thin wrappers around
`grid_from_text`: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from playwright.sync_api import FloatRect, Locator, Page, WebSocketRoute, expect

from fonts_ready import wait_for_fonts
from nock.grid import ClueCell, Grid
from nock.protocol import (
    GridView,
    HelpMode,
    LetterCellView,
    Ping,
    Pong,
    RevealBudget,
    RoomSettings,
    Snapshot,
    parse_client_message,
)
from nock.server import RoomRegistry

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]

# ---- Fixtures and helpers ---------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the grid fixtures)."""
    return Grid.model_validate_json(text)


def open_room(page: Page, base_url: str, registry: RoomRegistry, grid: Grid) -> Locator:
    """Register a room on `grid`, open it and return the grid viewport."""
    code = registry.register_room(grid)
    page.goto(f"{base_url}/r/{code}")
    submit_nickname_form(page)
    viewport = page.get_by_test_id("grid-viewport")
    expect(viewport).to_be_visible()
    wait_for_fonts(page)
    return viewport


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def box_of(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None, "the element has no box on screen"
    return box


# ---- Pinch through the Chrome DevTools Protocol (Chromium only) -------------

PINCH_STEPS = 10


def pinch(page: Page, viewport: Locator, start: float, end: float) -> None:
    """Pinch around the viewport centre, finger distance `start` to `end`."""
    box = box_of(viewport)
    center_x = box["x"] + box["width"] / 2
    center_y = box["y"] + box["height"] / 2

    def two_fingers(distance: float) -> list[dict[str, float]]:
        half = distance / 2
        return [
            {"x": center_x - half, "y": center_y, "id": 0},
            {"x": center_x + half, "y": center_y, "id": 1},
        ]

    session = page.context.new_cdp_session(page)
    try:
        session.send(
            "Input.dispatchTouchEvent",
            {"type": "touchStart", "touchPoints": two_fingers(start)},
        )
        for step in range(1, PINCH_STEPS + 1):
            distance = start + (end - start) * step / PINCH_STEPS
            session.send(
                "Input.dispatchTouchEvent",
                {"type": "touchMove", "touchPoints": two_fingers(distance)},
            )
        session.send(
            "Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}
        )
    finally:
        session.detach()


def count_clues(grid: Grid) -> int:
    total = 0
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            total += len(cell.clues)
    return total


# ---- Mocked room socket (browser tests of AC-4, AC-6 and AC-8) ---------------


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


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


FORM_TIMEOUT_MS = 5000


def submit_nickname_form(page: Page, nickname: str = "Ana") -> None:
    """Fill the nickname form of spec 012 and submit it with Enter."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)


def open_mock_room(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and wait for the page's join."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    submit_nickname_form(page)
    wait_until(page, lambda: len(mock.received) > 0)
    return mock


def snapshot_frame(view: GridView, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=(),
        settings=RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def with_letter_cells(
    view: GridView, changes: list[tuple[int, int, dict[str, object]]]
) -> GridView:
    """Return `view` with the given letter cells replaced by updated copies."""
    new_cells = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def show_snapshot(page: Page, mock: MockRoomSocket, view: GridView, seq: int) -> None:
    """Send a snapshot and wait until the room page shows its `seq`."""
    mock.send(snapshot_frame(view, seq))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", str(seq))
    wait_for_fonts(page)
