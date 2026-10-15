"""Shared setup of the tests of spec 007: word selection and direction.

This module is not a test file: pytest does not collect it. The tests of spec 007
are in `tests/test_spec_007_*.py`, one file per criterion group.

The page is tested with spec 040's mocked socket on `/r/ABC123`: the test sends
an FX-01 snapshot (or a hand-built view) and reads every frame the page sent.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixture `fx01_grid` is defined in each
file as a thin wrapper around `grid_from_text`: a fixture imported from here would
be an unused import for ruff.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, WebSocketRoute, expect

from nock.grid import Arrow, Grid
from nock.protocol import (
    ClueCellView,
    ClueView,
    EmptyCellView,
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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 300
FORM_TIMEOUT_MS = 5000


def grid_from_text(text: str) -> Grid:
    """Parse the JSON text of the FX-01 grid (the `fx01_text` fixture)."""
    return Grid.model_validate_json(text)


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def clue_named(page: Page, text: str) -> Locator:
    """The `clue` element whose text is exactly `text`."""
    clue_text = page.get_by_test_id("clue-text").get_by_text(text, exact=True)
    return page.get_by_test_id("clue").filter(has=clue_text)


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


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: list[tuple[int, int, dict[str, object]]] | None = None,
) -> MockRoomSocket:
    """Open a mocked room showing FX-01, with `changes` applied to its letters."""
    mock = open_mock_room(page, base_url)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    show_snapshot(page, mock, view, 0)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def note_view() -> GridView:
    """The 3 by 1 grid of the spec: clue "Note", an empty letter cell, empty."""
    clue_cell = ClueCellView(
        row=0,
        column=0,
        clues=(ClueView(text="Note", arrow=Arrow.RIGHT),),
    )
    letter_cell = LetterCellView(
        row=0,
        column=1,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )
    empty_cell = EmptyCellView(row=0, column=2)
    return GridView(width=3, height=1, cells=(clue_cell, letter_cell, empty_cell))


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


def positions_with(page: Page, attribute: str) -> list[tuple[int, int]]:
    """Positions of the letter cells whose `attribute` is "true", sorted."""
    script = (
        "attribute => Array.from(document.querySelectorAll("
        '\'[data-testid="cell"][data-type="letter"]\'))'
        ".filter(e => e.getAttribute(attribute) === 'true')"
        ".map(e => [Number(e.dataset.row), Number(e.dataset.column)])"
    )
    found = page.evaluate(script, attribute)
    positions = [(row, column) for row, column in found]
    return sorted(positions)


def active_clue_texts(page: Page) -> list[str]:
    script = (
        "() => Array.from(document.querySelectorAll('[data-testid=\"clue\"]'))"
        ".filter(e => e.getAttribute('data-active') === 'true')"
        ".map(e => e.querySelector('[data-testid=\"clue-text\"]').textContent)"
    )
    return page.evaluate(script)


def sent_messages(mock: MockRoomSocket) -> list[object]:
    """Every frame the page sent but its `ping` frames, parsed."""
    return [parse_client_message(frame) for frame in mock.frames_without_pings()]


def sent_selections(mock: MockRoomSocket) -> list[SelectCell]:
    """The `select_cell` messages the page sent, in order."""
    selections: list[SelectCell] = []
    for message in sent_messages(mock):
        if isinstance(message, SelectCell):
            selections.append(message)
    return selections


def select_cell_message(row: int, column: int, direction: str) -> SelectCell:
    return SelectCell(row=row, column=column, direction=direction)


def settle(page: Page) -> None:
    """Give the page time to send a message it should not send."""
    page.wait_for_timeout(SETTLE_MS)
