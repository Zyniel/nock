"""Tests of spec 009: arrow keys, Tab and the in-app keyboard.

AC-1 and AC-2 use a mocked socket on FX-01 (AC-1 also a live room on FX-02).
AC-3 and AC-4 use touch contexts. In Chromium the touch emulation alone makes
`(pointer: coarse)` true; in Firefox and WebKit the touch contexts also run an
init script that makes `window.matchMedia("(pointer: coarse)")` report a match.
Keys that must not reach the browser's own behaviour (Tab, Alt+Tab, modifier
arrows) are also checked through dispatched `keydown` events, which report
whether the default action was prevented.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect

from nock.grid import ClueCell, Grid, LetterCell
from nock.protocol import (
    CellView,
    EditLetter,
    EmptyCellView,
    Erase,
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
from nock.server import RoomRegistry

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 300
MIN_CLUE_FONT_PX = 14.0
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 0.01

ACROSS_W1 = "0,0,0"
DOWN_W2 = "0,0,1"
DOWN_MIME = "0,2,0"
DOWN_IDES = "0,3,0"
ACROSS_VIDE = "2,0,0"
ACROSS_AMEN = "3,0,0"
ACROSS_LEST = "4,0,0"

KEYBOARD_ROWS = ["AZERTYUIOP", "QSDFGHJKLM", "WXCVBN"]

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged.
COARSE_POINTER_SCRIPT = """
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""

ChangeList = list[tuple[int, int, dict[str, object]]]

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


def make_touch_page(
    browser: Browser, browser_name: str, width: int, height: int
) -> tuple[Page, Callable[[], None]]:
    """Open a touch page of the spec's harness; return it and its closer."""
    viewport = {"width": width, "height": height}
    if browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context.new_page(), context.close


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page."""
    page, close = make_touch_page(browser, browser_name, 360, 740)
    try:
        yield page
    finally:
        close()


@pytest.fixture(params=[(360, 740), (740, 360)], ids=["portrait", "landscape"])
def oriented_touch_page(
    request: pytest.FixtureRequest, browser: Browser, browser_name: str
) -> Iterator[Page]:
    """A touch page in portrait (360 by 740) and in landscape (740 by 360)."""
    width, height = request.param
    page, close = make_touch_page(browser, browser_name, width, height)
    try:
        yield page
    finally:
        close()


@pytest.fixture
def narrow_desktop_page(browser: Browser) -> Iterator[Page]:
    """A narrow window with a fine pointer: no touch, no init script."""
    context = browser.new_context(viewport={"width": 360, "height": 740})
    try:
        yield context.new_page()
    finally:
        context.close()


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


def open_mock_room(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and wait for the page's join."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
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


def with_empty_cell(view: GridView, row: int, column: int) -> GridView:
    """Return `view` with the cell at (row, column) turned into an empty cell."""
    new_cells: list[CellView] = []
    for cell in view.cells:
        if cell.row == row and cell.column == column:
            new_cells.append(EmptyCellView(row=row, column=column))
        else:
            new_cells.append(cell)
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


def all_filled(
    fx01_grid: Grid,
    empty: list[tuple[int, int]],
    locked: list[tuple[int, int]],
) -> ChangeList:
    """Changes filling every letter cell of FX-01 except those in `empty`."""
    changes: ChangeList = []
    for cell in fx01_grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        position = (cell.row, cell.column)
        if position in empty:
            continue
        update: dict[str, object] = {"letter": "A"}
        if position in locked:
            update["locked"] = True
        changes.append((cell.row, cell.column, update))
    return changes


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click()


def touch_tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).tap()


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    """Wait until the grid shows exactly this selection."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


def expect_cell_selection(page: Page, row: int, column: int, direction: str) -> None:
    """Like `expect_selection`, without the word (cell and direction only)."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)


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


def sent_edits(mock: MockRoomSocket) -> list[EditLetter | Erase]:
    """The `edit_letter` and `erase` messages the page sent, in order."""
    edits: list[EditLetter | Erase] = []
    for message in sent_messages(mock):
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def across(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="across")


def down(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="down")


def put(row: int, column: int, letter: str) -> EditLetter:
    return EditLetter(row=row, column=column, letter=letter)


def rub(row: int, column: int) -> Erase:
    return Erase(row=row, column=column)


# ---- AC-1: arrow keys --------------------------------------------------------


def test_ac1_arrows_follow_the_spec_walk_on_fx01(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    page.keyboard.press("ArrowDown")
    expect_selection(page, 2, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowRight")
    expect_selection(page, 2, 2, "across", ACROSS_VIDE)

    page.keyboard.press("ArrowUp")
    expect_selection(page, 1, 2, "down", DOWN_MIME)

    assert sent_selections(mock) == [
        across(1, 1),
        down(2, 1),
        across(2, 2),
        down(1, 2),
    ]


def test_ac1_arrow_left_from_a_cell_with_only_clue_cells_to_its_left_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("ArrowLeft")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_arrow_up_at_the_top_edge_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowUp")

    settle(page)
    expect_selection(page, 0, 1, "down", DOWN_W2)
    assert sent_selections(mock) == [down(0, 1)]


def test_ac1_arrow_at_the_right_and_bottom_edges_does_not_wrap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 4, 4)
    expect_selection(page, 4, 4, "across", ACROSS_LEST)

    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")

    settle(page)
    expect_selection(page, 4, 4, "across", ACROSS_LEST)
    assert sent_selections(mock) == [across(4, 4)]


def test_ac1_arrow_down_from_a_cell_with_only_clue_cells_below_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("ArrowDown")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_arrow_right_from_the_first_cell_selects_the_next_one_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("ArrowRight")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0), across(1, 1)]


def test_ac1_arrow_up_onto_a_cell_with_one_word_selects_it_down(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)

    page.keyboard.press("ArrowUp")

    expect_selection(page, 0, 1, "down", DOWN_W2)
    assert sent_selections(mock) == [across(1, 1), down(0, 1)]


def test_ac1_arrow_left_while_down_onto_an_across_only_cell_switches_to_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowLeft")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1), down(1, 1), across(1, 0)]


def test_ac1_arrow_down_while_across_switches_to_down_and_arrow_left_back(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", ACROSS_VIDE)

    page.keyboard.press("ArrowDown")
    expect_selection(page, 3, 2, "down", DOWN_MIME)

    page.keyboard.press("ArrowLeft")
    expect_selection(page, 3, 1, "across", ACROSS_AMEN)

    assert sent_selections(mock) == [
        across(2, 2),
        down(3, 2),
        across(3, 1),
    ]


def test_ac1_arrows_skip_an_empty_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # With (1, 1) empty, TAMIS ends before it, so (1, 2) has no across word
    # (specs 002 and 007); only MIME is left and step 2 of the spec picks it.
    view = with_empty_cell(grid_view(fx01_grid), 1, 1)
    mock = open_view(page, live_server, view)
    tap(page, 1, 0)
    expect_cell_selection(page, 1, 0, "across")

    page.keyboard.press("ArrowRight")

    expect_selection(page, 1, 2, "down", DOWN_MIME)
    assert sent_selections(mock)[-1] == down(1, 2)


def test_ac1_arrow_down_skips_an_empty_cell_and_uses_the_only_word_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # With (2, 1) empty, NAVAL ends before it, so (3, 1) has no down word and
    # the walk lands on its across word AMEN.
    view = with_empty_cell(grid_view(fx01_grid), 2, 1)
    mock = open_view(page, live_server, view)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowDown")

    expect_selection(page, 3, 1, "across", ACROSS_AMEN)
    assert sent_selections(mock)[-1] == across(3, 1)


def test_ac1_arrows_do_nothing_without_a_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    grid.focus()
    frames_before = len(mock.received)

    for key in ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"]:
        page.keyboard.press(key)

    settle(page)
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")
    assert len(mock.received) == frames_before


def test_ac1_a_handled_arrow_is_prevented_and_a_modified_one_is_left_alone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    assert dispatch_key(page, "ArrowRight", ctrl=True) is True
    assert dispatch_key(page, "ArrowRight", alt=True) is True
    page.keyboard.press("Control+ArrowRight")
    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]

    assert dispatch_key(page, "ArrowRight") is False
    expect_selection(page, 1, 2, "across", ACROSS_W1)


def find_letter_clue_letter_in_a_row(grid: Grid) -> tuple[int, int]:
    """Return (row, column) of a letter cell followed by a clue, then a letter."""
    for cell in grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        if cell.column + 2 >= grid.width:
            continue
        middle = grid.cell_at(cell.row, cell.column + 1)
        right = grid.cell_at(cell.row, cell.column + 2)
        if isinstance(middle, ClueCell) and isinstance(right, LetterCell):
            return cell.row, cell.column
    pytest.fail("FX-02 has no letter, clue, letter pattern in a row")


def find_letter_clue_letter_in_a_column(grid: Grid) -> tuple[int, int]:
    """Return (row, column) of a letter cell above a clue, then a letter."""
    for cell in grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        if cell.row + 2 >= grid.height:
            continue
        middle = grid.cell_at(cell.row + 1, cell.column)
        below = grid.cell_at(cell.row + 2, cell.column)
        if isinstance(middle, ClueCell) and isinstance(below, LetterCell):
            return cell.row, cell.column
    pytest.fail("FX-02 has no letter, clue, letter pattern in a column")


def test_ac1_fx02_arrow_right_jumps_over_a_clue_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    row, column = find_letter_clue_letter_in_a_row(fx02_grid)
    code = room_registry.register_room(fx02_grid)
    page.goto(f"{live_server}/r/{code}")
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    tap(page, row, column)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-column", str(column))

    page.keyboard.press("ArrowRight")

    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column + 2))


def test_ac1_fx02_arrow_down_jumps_over_a_clue_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    row, column = find_letter_clue_letter_in_a_column(fx02_grid)
    code = room_registry.register_room(fx02_grid)
    page.goto(f"{live_server}/r/{code}")
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    tap(page, row, column)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))

    page.keyboard.press("ArrowDown")

    expect(grid).to_have_attribute("data-selected-row", str(row + 2))
    expect(grid).to_have_attribute("data-selected-column", str(column))


# ---- AC-2: Tab and Shift+Tab -------------------------------------------------

MIME_FINISHED: ChangeList = [
    (1, 2, {"letter": "M"}),
    (2, 2, {"letter": "I"}),
    (3, 2, {"letter": "M"}),
    (4, 2, {"letter": "E"}),
]


def test_ac2_tab_and_shift_tab_walk_the_unfinished_words_with_wrap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("Tab")
    expect_selection(page, 1, 3, "down", DOWN_IDES)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 4, 1, "across", ACROSS_LEST)

    assert sent_selections(mock) == [
        down(0, 1),
        down(1, 3),
        down(0, 1),
        across(1, 0),
        across(4, 1),
    ]
    expect(page.get_by_test_id("grid")).to_be_focused()


def test_ac2_tab_wraps_from_the_last_word_to_the_first(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    tap(page, 4, 1)
    expect_selection(page, 4, 1, "across", ACROSS_LEST)

    page.keyboard.press("Tab")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(4, 1), across(1, 0)]


def test_ac2_tab_with_nothing_selected_starts_at_the_first_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    page.get_by_test_id("grid").focus()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "")

    page.keyboard.press("Tab")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac2_shift_tab_with_nothing_selected_starts_after_the_last_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Shift+Tab")

    expect_selection(page, 4, 1, "across", ACROSS_LEST)
    assert sent_selections(mock) == [across(4, 1)]


def test_ac2_tab_lands_on_the_first_unfilled_cell_not_the_first_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A", "locked": True})],
    )
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Tab")

    expect_selection(page, 1, 2, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 2)]


def test_ac2_tab_reselects_the_only_unfinished_word_on_its_unfilled_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[(1, 0)], locked=[])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    tap(page, 1, 3)
    expect_selection(page, 1, 3, "across", ACROSS_W1)

    page.keyboard.press("Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    tap(page, 1, 2)
    page.keyboard.press("Shift+Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    assert sent_selections(mock) == [
        across(1, 3),
        across(1, 0),
        across(1, 2),
        across(1, 0),
    ]


def test_ac2_when_every_word_is_finished_tab_changes_nothing_and_keeps_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[], locked=[(1, 0), (3, 3), (4, 4)])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    page.keyboard.press("Tab")
    page.keyboard.press("Shift+Tab")

    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect(page.get_by_test_id("grid")).to_be_focused()
    assert sent_selections(mock) == [across(1, 1)]
    assert len(mock.received) == 2


def test_ac2_a_word_whose_remaining_cells_are_locked_or_filled_is_finished(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[(4, 1)], locked=[(1, 0), (1, 1), (1, 3)])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Tab")

    # (4, 1) is the last cell of NAVAL (0,0,1) and the first of LEST (4,0,0):
    # only those two words are unfinished, in clue order.
    expect_selection(page, 4, 1, "down", DOWN_W2)
    page.keyboard.press("Tab")
    expect_selection(page, 4, 1, "across", ACROSS_LEST)
    assert sent_selections(mock) == [down(4, 1), across(4, 1)]


def test_ac2_tab_with_the_focus_on_another_control_moves_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    page.evaluate(
        "() => { for (const name of ['first', 'second']) {"
        " const button = document.createElement('button');"
        " button.id = name; document.body.append(button); } }"
    )
    page.locator("#first").focus()

    page.keyboard.press("Tab")

    expect(page.locator("#second")).to_be_focused()
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]


def test_ac2_handled_tab_is_prevented_and_alt_tab_is_left_to_the_browser(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)

    assert dispatch_key(page, "Tab", alt=True) is True
    assert dispatch_key(page, "Tab", ctrl=True) is True
    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]

    assert dispatch_key(page, "Tab") is False
    assert dispatch_key(page, "Tab", shift=True) is False


# ---- AC-3: the in-app keyboard -----------------------------------------------


def keys_of_row(row: Locator) -> str:
    """The `data-key` values of the keys of a row, joined."""
    script = "(elements) => elements.map((e) => e.getAttribute('data-key')).join('')"
    return str(row.locator('[data-testid="key"]').evaluate_all(script))


def key_named(page: Page, letter: str) -> Locator:
    return page.locator(f'[data-testid="key"][data-key="{letter}"]')


def active_element_is_editable(page: Page) -> bool:
    script = (
        "() => { const e = document.activeElement;"
        " if (!e) { return false; }"
        " return ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.tagName)"
        " || e.isContentEditable; }"
    )
    return bool(page.evaluate(script))


def count_editable_in_page_areas(page: Page) -> int:
    """Count editable elements in the grid area, the clue bar and the keyboard."""
    script = (
        "() => { let total = 0;"
        " for (const id of ['grid-viewport', 'clue-bar', 'keyboard', 'grid']) {"
        ' const area = document.querySelector(`[data-testid="${id}"]`);'
        " if (!area) { continue; }"
        " total += area.querySelectorAll("
        "'input, textarea, select, [contenteditable]').length; }"
        " return total; }"
    )
    return int(page.evaluate(script))


def test_ac3_touch_context_shows_the_azerty_keyboard(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)

    keyboard = touch_page.get_by_test_id("keyboard")
    expect(keyboard).to_be_visible()
    expect(keyboard).to_have_attribute("aria-label", "Clavier")
    rows = touch_page.get_by_test_id("keyboard-row")
    expect(rows).to_have_count(3)
    for index, expected_keys in enumerate(KEYBOARD_ROWS):
        assert keys_of_row(rows.nth(index)) == expected_keys
    expect(touch_page.get_by_test_id("key")).to_have_count(26)
    expect(touch_page.get_by_test_id("key-delete")).to_have_count(1)
    expect(keyboard.get_by_test_id("key-delete")).to_have_count(1)


def test_ac3_keys_are_buttons_showing_their_letter(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()

    script = (
        "(elements) => elements.map((e) => [e.tagName,"
        " e.getAttribute('data-key'), e.textContent.trim()])"
    )
    keys = touch_page.get_by_test_id("key").evaluate_all(script)

    assert len(keys) == 26
    for tag, data_key, text in keys:
        assert tag == "BUTTON"
        assert text == data_key


def test_ac3_the_delete_key_is_an_icon_button_after_the_last_letters(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    delete_key = touch_page.get_by_test_id("key-delete")

    expect(delete_key).to_be_visible()
    expect(delete_key).to_have_attribute("aria-label", "Effacer")
    assert delete_key.evaluate("(element) => element.tagName") == "BUTTON"
    assert delete_key.evaluate("(element) => element.textContent.trim()") == ""
    third_row = touch_page.get_by_test_id("keyboard-row").nth(2)
    last_testid = third_row.evaluate(
        "(row) => row.lastElementChild.getAttribute('data-testid')"
    )
    assert last_testid == "key-delete"
    assert third_row.get_by_test_id("key-delete").count() == 1


def test_ac3_tapping_keys_types_then_delete_erases_through_spec_008_rules(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    grid = touch_page.get_by_test_id("grid")
    touch_tap(touch_page, 1, 0)
    expect_selection(touch_page, 1, 0, "across", ACROSS_W1)

    key_named(touch_page, "T").tap()
    expect_letter(touch_page, 1, 0, "T")
    expect_selection(touch_page, 1, 1, "across", ACROSS_W1)
    expect(grid).to_be_focused()

    key_named(touch_page, "A").tap()
    expect_letter(touch_page, 1, 1, "A")
    expect_selection(touch_page, 1, 2, "across", ACROSS_W1)
    expect(grid).to_be_focused()
    assert sent_edits(mock) == [put(1, 0, "T"), put(1, 1, "A")]

    touch_page.get_by_test_id("key-delete").tap()

    expect_letter(touch_page, 1, 1, "")
    expect_letter(touch_page, 1, 0, "T")
    expect_selection(touch_page, 1, 1, "across", ACROSS_W1)
    expect(grid).to_be_focused()
    wait_until(touch_page, lambda: len(sent_edits(mock)) == 3)
    assert sent_edits(mock) == [put(1, 0, "T"), put(1, 1, "A"), rub(1, 1)]


def test_ac3_each_tap_on_the_same_key_is_one_letter(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    touch_tap(touch_page, 1, 0)

    key_named(touch_page, "E").tap()
    key_named(touch_page, "E").tap()
    key_named(touch_page, "E").tap()

    expect_letter(touch_page, 1, 2, "E")
    expect_letter(touch_page, 1, 0, "E")
    expect_letter(touch_page, 1, 1, "E")
    expect_selection(touch_page, 1, 3, "across", ACROSS_W1)
    settle(touch_page)
    assert sent_edits(mock) == [put(1, 0, "E"), put(1, 1, "E"), put(1, 2, "E")]


def test_ac3_keys_do_nothing_without_a_selection(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    frames_before = len(mock.received)

    key_named(touch_page, "Q").tap()
    touch_page.get_by_test_id("key-delete").tap()

    settle(touch_page)
    expect(touch_page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert len(mock.received) == frames_before


def test_ac3_focus_is_never_on_an_editable_element_and_none_exists(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    assert count_editable_in_page_areas(touch_page) == 0
    assert active_element_is_editable(touch_page) is False

    touch_tap(touch_page, 1, 0)
    assert active_element_is_editable(touch_page) is False
    for letter in ["T", "A", "M"]:
        key_named(touch_page, letter).tap()
        assert active_element_is_editable(touch_page) is False
    touch_page.get_by_test_id("key-delete").tap()
    assert active_element_is_editable(touch_page) is False
    touch_page.get_by_test_id("clue-bar").tap()
    assert active_element_is_editable(touch_page) is False
    assert count_editable_in_page_areas(touch_page) == 0


def test_ac3_desktop_context_has_no_keyboard(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    settle(page)
    expect(page.get_by_test_id("keyboard")).to_have_count(0)
    expect(page.get_by_test_id("key")).to_have_count(0)
    expect(page.get_by_test_id("key-delete")).to_have_count(0)
    page.keyboard.press("T")
    expect_letter(page, 1, 0, "T")


def test_ac3_a_narrow_window_with_a_fine_pointer_has_no_keyboard(
    narrow_desktop_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(narrow_desktop_page, live_server, fx01_grid)

    settle(narrow_desktop_page)
    expect(narrow_desktop_page.get_by_test_id("keyboard")).to_have_count(0)
    expect(narrow_desktop_page.get_by_test_id("key")).to_have_count(0)


def test_ac3_no_keyboard_before_the_first_snapshot_then_it_appears(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(touch_page, live_server)
    settle(touch_page)
    expect(touch_page.get_by_test_id("keyboard")).to_have_count(0)

    mock.send(snapshot_frame(grid_view(fx01_grid), 0))

    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    expect(touch_page.get_by_test_id("key")).to_have_count(26)


# ---- AC-4: the clue bar stays above the keyboard -----------------------------


def test_ac4_clue_bar_is_above_the_keyboard_inside_the_window(
    oriented_touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    page = oriented_touch_page
    open_fx01(page, live_server, fx01_grid)
    keyboard = page.get_by_test_id("keyboard")
    expect(keyboard).to_be_visible()

    touch_tap(page, 3, 1)

    bar = page.get_by_test_id("clue-bar")
    text = page.get_by_test_id("clue-bar-text")
    expect(bar).to_have_attribute("data-word", ACROSS_AMEN)
    expect(text).to_be_visible()
    expect(text).to_have_text("Fin de prière")
    bar_box = bar.bounding_box()
    keyboard_box = keyboard.bounding_box()
    viewport_box = page.get_by_test_id("grid-viewport").bounding_box()
    assert bar_box is not None
    assert keyboard_box is not None
    assert viewport_box is not None
    window_height = float(page.evaluate("() => window.innerHeight"))
    font_size = str(text.evaluate("(e) => getComputedStyle(e).fontSize"))

    assert bar_box["y"] + bar_box["height"] <= keyboard_box["y"] + EPSILON
    assert keyboard_box["y"] + keyboard_box["height"] <= window_height + EPSILON
    assert bar_box["y"] >= 0
    assert float(font_size.removesuffix("px")) >= MIN_CLUE_FONT_PX
    assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
