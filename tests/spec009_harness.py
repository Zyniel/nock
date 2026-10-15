"""Shared setup of the tests of spec 009: arrow keys, Tab and the in-app keyboard.

This module is not a test file: pytest does not collect it. The tests of spec 009
are in `tests/test_spec_009_*.py`, one file per criterion group.

AC-1 and AC-2 use a mocked socket on FX-01 (AC-1 also a live room on FX-02).
AC-3 and AC-4 use touch contexts. Keys that must not reach the browser's own
behaviour (Tab, Alt+Tab, modifier arrows) are also checked through dispatched
`keydown` events, which report whether the default action was prevented
(`dispatch_key`).

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixture `fx01_grid` is defined in each
file as a thin wrapper around `grid_from_text`: a fixture imported from here
would be an unused import for ruff.
"""

from __future__ import annotations

import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Locator, Page, WebSocketRoute, expect

from nock.grid import Grid
from nock.protocol import (
    CellView,
    GridView,
    HelpMode,
    LetterCellView,
    RevealBudget,
    RoomSettings,
    SelectCell,
    Snapshot,
    grid_view,
    parse_client_message,
)

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 300

# Word ids of FX-01 that several files use; a word id that only one file uses is
# defined in that file.
ACROSS_W1 = "0,0,0"
DOWN_W2 = "0,0,1"
ACROSS_AMEN = "3,0,0"
ACROSS_LEST = "4,0,0"

ChangeList = list[tuple[int, int, dict[str, object]]]


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)


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
    mock = MockRoomSocket()
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


def with_letter_cells(view: GridView, changes: ChangeList) -> GridView:
    """Return `view` with the given letter cells replaced by updated copies."""
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def open_view(page: Page, base_url: str, view: GridView) -> MockRoomSocket:
    """Open a mocked room and show `view` in it."""
    mock = open_mock_room(page, base_url)
    mock.send(snapshot_frame(view, 0))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "0")
    expect(page.get_by_test_id("cell")).to_have_count(view.width * view.height)
    return mock


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
) -> MockRoomSocket:
    """Open a mocked room showing FX-01, with `changes` applied to its letters."""
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    return open_view(page, base_url, view)


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click()


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    """Wait until the grid shows exactly this selection."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


def settle(page: Page) -> None:
    """Give the page time to send a message it should not send."""
    page.wait_for_timeout(SETTLE_MS)


def dispatch_key(
    page: Page,
    key: str,
    ctrl: bool = False,
    alt: bool = False,
    shift: bool = False,
) -> bool:
    """Dispatch a keydown on the grid; return True if it was NOT prevented."""
    script = (
        "([key, init]) => document.querySelector('[data-testid=\"grid\"]')"
        ".dispatchEvent(new KeyboardEvent('keydown',"
        " {key, bubbles: true, cancelable: true, ...init}))"
    )
    init = {"ctrlKey": ctrl, "altKey": alt, "shiftKey": shift}
    return bool(page.evaluate(script, [key, init]))


def sent_messages(mock: MockRoomSocket) -> list[object]:
    """Every frame the page sent, parsed."""
    return [parse_client_message(frame) for frame in mock.received]


def sent_selections(mock: MockRoomSocket) -> list[SelectCell]:
    """The `select_cell` messages the page sent, in order."""
    selections: list[SelectCell] = []
    for message in sent_messages(mock):
        if isinstance(message, SelectCell):
            selections.append(message)
    return selections


def across(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="across")


def down(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="down")
