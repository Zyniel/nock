"""Shared setup of the tests of spec 008: letter entry (FX-01, mocked socket).

This module is not a test file: pytest does not collect it. The tests of spec 008
are in `tests/test_spec_008_*.py`, one file per criterion group. It holds what more
than one of those files uses. What only one file uses stays in that file, next to
its tests. The fixture `fx01_grid` is defined in each file as a thin wrapper around
`grid_from_text`: a fixture imported from here would be an unused import for ruff.

Keys: ASCII keys go through `page.keyboard.press`. Playwright cannot press a key
such as "é" (`keyboard.press` raises "Unknown key" and `keyboard.type` sends no
keydown at all, in Chromium and WebKit), so every non-ASCII key is dispatched as a
`keydown` KeyboardEvent with that `key` on the focused `grid` element. That works
the same in every engine.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Locator, Page, WebSocketRoute, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import (
    CellView,
    EditLetter,
    Erase,
    GridView,
    HelpMode,
    LetterCellView,
    Ping,
    Pong,
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

ACROSS_W1 = "0,0,0"
DOWN_W2 = "0,0,1"
ACROSS_W7 = "3,0,0"
ACROSS_W8 = "4,0,0"

ChangeList = list[tuple[int, int, dict[str, object]]]

# ---- Fixtures and helpers ---------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


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
        """The frames the page sent, without its keep-alive `ping` frames.

        The page sends a `ping` every 2 s once the socket is open (spec 017), so
        one can fall between two reads whatever the test does.
        """
        frames: list[str] = []
        for frame in self.received:
            if json.loads(frame)["type"] != "ping":
                frames.append(frame)
        return frames


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
    wait_until(page, lambda: len(mock.frames_without_pings()) > 0)
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


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
) -> MockRoomSocket:
    """Open a mocked room showing FX-01, with `changes` applied to its letters."""
    mock = open_mock_room(page, base_url)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, 0))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "0")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    wait_for_fonts(page)
    return mock


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


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    """Wait until the cell shows `letter` ("" for an empty cell)."""
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)


def expect_letters(page: Page, letters: dict[tuple[int, int], str]) -> None:
    for (row, column), letter in letters.items():
        expect_letter(page, row, column, letter)


def settle(page: Page) -> None:
    """Give the page time to send a message it should not send."""
    page.wait_for_timeout(SETTLE_MS)


def dispatch_key(
    page: Page,
    key: str,
    ctrl: bool = False,
    meta: bool = False,
    alt: bool = False,
    composing: bool = False,
) -> bool:
    """Dispatch a keydown on the grid; return True if it was NOT prevented."""
    script = (
        "([key, init]) => document.querySelector('[data-testid=\"grid\"]')"
        ".dispatchEvent(new KeyboardEvent('keydown',"
        " {key, bubbles: true, cancelable: true, ...init}))"
    )
    init = {
        "ctrlKey": ctrl,
        "metaKey": meta,
        "altKey": alt,
        "isComposing": composing,
    }
    return bool(page.evaluate(script, [key, init]))


def press(page: Page, key: str) -> None:
    """Press one key on the focused grid (see the module docstring)."""
    if key.isascii():
        page.keyboard.press(key)
    else:
        dispatch_key(page, key)


def press_all(page: Page, keys: list[str]) -> None:
    for key in keys:
        press(page, key)


def sent_messages(mock: MockRoomSocket) -> list[object]:
    """Every frame the page sent but its `ping` frames, parsed."""
    return [parse_client_message(frame) for frame in mock.frames_without_pings()]


def sent_edits(mock: MockRoomSocket) -> list[EditLetter | Erase]:
    """The `edit_letter` and `erase` messages the page sent, in order."""
    edits: list[EditLetter | Erase] = []
    for message in sent_messages(mock):
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def sent_selections(mock: MockRoomSocket) -> list[SelectCell]:
    """The `select_cell` messages the page sent, in order."""
    selections: list[SelectCell] = []
    for message in sent_messages(mock):
        if isinstance(message, SelectCell):
            selections.append(message)
    return selections


def across(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="across")


def put(row: int, column: int, letter: str) -> EditLetter:
    return EditLetter(row=row, column=column, letter=letter)


def expect_edits(
    page: Page, mock: MockRoomSocket, expected: list[EditLetter | Erase]
) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    if expected:
        wait_until(page, lambda: len(sent_edits(mock)) >= len(expected))
    settle(page)
    assert sent_edits(mock) == expected
