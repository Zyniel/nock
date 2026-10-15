"""Tests of spec 018, AC-3: undo on the page, with a mocked socket.

The undo button and the `Control+z` / `Meta+z` shortcut, the `undo-message` after
a `nothing_to_undo` error, and the pending queue matching of an own
`letter_changed`. The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

import pytest
from playwright.sync_api import Locator, Page, WebSocketRoute, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    CellView,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    LetterCellView,
    Ping,
    Pong,
    RevealBudget,
    RoomSettings,
    Snapshot,
    Undo,
    grid_view,
    parse_client_message,
)
from spec018_harness import grid_from_text, letter_changed, published_catalogue

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
UNDO_MESSAGE_SECONDS = 3

ChangeList = list[tuple[int, int, dict[str, object]]]


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return published_catalogue(fx01_grid)


# ---- AC-3: the page, with a mocked socket ----


def fr_text(key: str) -> str:
    fr_path = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
    texts = json.loads(fr_path.read_text(encoding="utf-8"))
    value = texts[key]
    assert isinstance(value, str)
    return value


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the route
    that sent it: without the answer, the page takes 4 s without a frame from the
    server for a lost connection (spec 017, AC-4), so a step that takes longer on a
    slow engine would find the page `reconnecting`.
    """

    def __init__(self) -> None:
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

    def undo_count(self) -> int:
        count = 0
        for frame in self.received:
            if isinstance(parse_client_message(frame), Undo):
                count += 1
        return count

    def sent_in_order(self) -> list[str]:
        """The type of each edit_letter, erase and undo received, in order."""
        types: list[str] = []
        for frame in self.received:
            message = parse_client_message(frame)
            if isinstance(message, EditLetter | Erase | Undo):
                types.append(message.type)
        return types


def wait_until_page(page: Page, condition: Callable[[], bool]) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


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
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def start_page(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket; stop at the nickname form."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    expect(page.get_by_test_id("nickname-input")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    return mock


def join_page(
    page: Page,
    mock: MockRoomSocket,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
    seq: int = 5,
) -> None:
    """Join as Ana and answer with a snapshot of FX-01 for `p1` at `seq`."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.received) > 0)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
    seq: int = 5,
) -> MockRoomSocket:
    mock = start_page(page, base_url)
    join_page(page, mock, fx01_grid, changes, seq)
    return mock


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    return letter_changed(seq, row, column, letter, player_id).model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def expect_cell(
    page: Page,
    row: int,
    column: int,
    letter: str,
    unconfirmed: bool,
    author: str | None = None,
) -> None:
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute(
        "data-unconfirmed", "true" if unconfirmed else "false"
    )
    if author is not None:
        expect(cell).to_have_attribute("data-author", author)


def test_ac3_browser_the_undo_button_shows_only_once_joined_with_its_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = start_page(page, live_server)
    expect(page.get_by_test_id("undo-button")).to_be_hidden()

    join_page(page, mock, fx01_grid)

    button = page.get_by_test_id("undo-button")
    expect(button).to_have_count(1)
    expect(button).to_be_visible()
    expect(button).to_have_text(fr_text("room.undo"))
    assert fr_text("room.undo") == "Annuler"


def test_ac3_browser_clicking_the_undo_button_sends_one_undo(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    page.get_by_test_id("undo-button").click()

    wait_until_page(page, lambda: mock.undo_count() >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert mock.undo_count() == 1
    assert '"type":"undo"' in mock.received[-1].replace(" ", "")


@pytest.mark.parametrize("shortcut", ["Control+z", "Meta+z"])
def test_ac3_browser_the_undo_shortcut_with_the_grid_focused_sends_an_undo(
    page: Page, live_server: str, fx01_grid: Grid, shortcut: str
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()

    page.keyboard.press(shortcut)

    wait_until_page(page, lambda: mock.undo_count() >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert mock.undo_count() == 1
    assert mock.sent_in_order() == ["undo"]


@pytest.mark.parametrize("modifier", ["Control", "Meta"])
def test_ac3_browser_the_undo_shortcut_prevents_the_browser_default(
    page: Page, live_server: str, fx01_grid: Grid, modifier: str
) -> None:
    open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()

    prevented = page.get_by_test_id("grid").evaluate(
        """(grid, modifier) => {
            const event = new KeyboardEvent("keydown", {
                key: "z",
                code: "KeyZ",
                ctrlKey: modifier === "Control",
                metaKey: modifier === "Meta",
                bubbles: true,
                cancelable: true,
            });
            grid.dispatchEvent(event);
            return event.defaultPrevented;
        }""",
        modifier,
    )

    assert prevented is True


def test_ac3_browser_the_undo_shortcut_does_nothing_when_the_grid_is_not_focused(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.evaluate(
        "() => { if (document.activeElement instanceof HTMLElement) "
        "document.activeElement.blur(); }"
    )

    page.keyboard.press("Control+z")
    page.wait_for_timeout(SETTLE_MS)

    assert mock.undo_count() == 0


def test_ac3_browser_nothing_to_undo_shows_the_message_for_about_three_seconds(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    message = page.get_by_test_id("undo-message")
    expect(message).to_be_hidden()

    mock.send(error_frame(ErrorCode.NOTHING_TO_UNDO))

    expect(message).to_be_visible()
    expect(message).to_have_text(fr_text("undo.nothing"))
    assert fr_text("undo.nothing") == "Rien à annuler."
    page.wait_for_timeout(1500)
    expect(message).to_be_visible()
    expect(message).to_be_hidden(timeout=(UNDO_MESSAGE_SECONDS + 2) * 1000)


def test_ac3_browser_other_errors_do_not_show_the_undo_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    mock.send(error_frame(ErrorCode.NOT_HOST))
    page.wait_for_timeout(SETTLE_MS)

    expect(page.get_by_test_id("undo-message")).to_be_hidden()


def test_ac3_browser_undo_pressed_while_an_edit_is_pending_goes_after_the_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    page.get_by_test_id("undo-button").click()

    wait_until_page(page, lambda: len(mock.sent_in_order()) >= 2)
    assert mock.sent_in_order() == ["edit_letter", "undo"]


def test_ac3_browser_the_result_of_an_undo_updates_the_grid_from_you(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 0, {"letter": "A", "author": "p1"})],
    )
    expect_cell(page, 1, 0, "A", unconfirmed=False, author="p1")

    mock.send(letter_changed_frame(6, 1, 0, "B", "p1"))

    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p1")
    mock.send(letter_changed_frame(7, 1, 0, None, "p1"))
    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


def test_ac3_browser_an_own_letter_changed_for_another_cell_keeps_the_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 1, "A", "p1"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p1")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac3_browser_an_own_letter_changed_with_another_letter_keeps_the_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 0, "B", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
