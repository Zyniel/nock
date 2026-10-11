"""Tests of spec 006: grid rendering (FX-02, grid viewport, cells and clues)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import (
    Browser,
    ElementHandle,
    FloatRect,
    Locator,
    Page,
    WebSocketRoute,
    expect,
)

from nock.grid import Arrow, ClueCell, EmptyCell, Grid, LetterCell
from nock.grid_import import import_grid
from nock.protocol import (
    GridView,
    HelpMode,
    LetterCellView,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
)
from nock.server import RoomRegistry

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

ZOOM_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
MAX_PINCHES = 5
PINCH_STEPS = 10
SMALL_PINCH_START = 40.0
BIG_PINCH_END = 300.0
EPSILON = 1e-6
FX02_WORD_COUNT = 47
FX02_EMPTY_CELL_COUNT = 56

# The 8 clues of FX-01 with the arrow side of the spec table:
# (row, column, clue index, arrow, side).
FX01_CLUES = [
    (0, 0, 0, "down_then_right", "bottom"),
    (0, 0, 1, "right_then_down", "right"),
    (0, 2, 0, "down", "bottom"),
    (0, 3, 0, "down", "bottom"),
    (0, 4, 0, "down", "bottom"),
    (2, 0, 0, "right", "right"),
    (3, 0, 0, "right", "right"),
    (4, 0, 0, "right", "right"),
]

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


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def phone_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A page in the phone context of the spec (no is_mobile under Firefox)."""
    if browser_name == "firefox":
        context = browser.new_context(
            viewport={"width": 360, "height": 740},
            has_touch=True,
            device_scale_factor=2,
        )
    else:
        context = browser.new_context(
            viewport={"width": 360, "height": 740},
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    try:
        yield context.new_page()
    finally:
        context.close()


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def open_room(page: Page, base_url: str, registry: RoomRegistry, grid: Grid) -> Locator:
    """Register a room on `grid`, open it and return the grid viewport."""
    code = registry.register_room(grid)
    page.goto(f"{base_url}/r/{code}")
    submit_nickname_form(page)
    viewport = page.get_by_test_id("grid-viewport")
    expect(viewport).to_be_visible()
    return viewport


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def box_of(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None, "the element has no box on screen"
    return box


def read_zoom(viewport: Locator) -> float:
    value = viewport.get_attribute("data-zoom")
    assert value is not None
    return float(value)


def read_zoom_max(viewport: Locator) -> float:
    value = viewport.get_attribute("data-zoom-max")
    assert value is not None
    return float(value)


def assert_zoom_format(value: str | None) -> None:
    """Check a zoom attribute: a decimal with at most 2 decimals."""
    assert value is not None
    assert ZOOM_PATTERN.match(value), value


def client_size(viewport: Locator) -> tuple[float, float]:
    sizes = viewport.evaluate("element => [element.clientWidth, element.clientHeight]")
    return float(sizes[0]), float(sizes[1])


def count_clues(grid: Grid) -> int:
    total = 0
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            total += len(cell.clues)
    return total


# ---- Pinch and pan through the Chrome DevTools Protocol (Chromium only) -------


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


def pinch_out(page: Page, viewport: Locator) -> None:
    pinch(page, viewport, SMALL_PINCH_START, BIG_PINCH_END)


def pinch_in(page: Page, viewport: Locator) -> None:
    pinch(page, viewport, BIG_PINCH_END, SMALL_PINCH_START)


def pan(page: Page, viewport: Locator) -> None:
    """Drag one finger from the viewport centre by -200 px in x and y."""
    box = box_of(viewport)
    session = page.context.new_cdp_session(page)
    try:
        session.send(
            "Input.synthesizeScrollGesture",
            {
                "x": box["x"] + box["width"] / 2,
                "y": box["y"] + box["height"] / 2,
                "xDistance": -200,
                "yDistance": -200,
                "gestureSourceType": "touch",
            },
        )
    finally:
        session.detach()


def wait_for_zoom(page: Page, viewport: Locator, condition: str, before: float) -> None:
    """Wait until `data-zoom` satisfies a JS comparison with `before`."""
    handle: ElementHandle | None = viewport.element_handle()
    assert handle is not None
    expression = f"([element, before]) => parseFloat(element.dataset.zoom) {condition}"
    page.wait_for_function(expression, arg=[handle, before], timeout=WAIT_TIMEOUT_MS)


def pinch_out_to_max(page: Page, viewport: Locator) -> int:
    """Pinch out until `data-zoom` equals `data-zoom-max`; return the pinch count."""
    zoom_max = read_zoom_max(viewport)
    pinches = 0
    while abs(read_zoom(viewport) - zoom_max) > EPSILON and pinches < MAX_PINCHES:
        before = read_zoom(viewport)
        pinch_out(page, viewport)
        pinches += 1
        wait_for_zoom(page, viewport, f"> before + {EPSILON}", before)
    assert abs(read_zoom(viewport) - zoom_max) <= EPSILON, "max zoom not reached"
    return pinches


CUT_OFF_SCRIPT = """
() => {
  const failures = [];
  const texts = document.querySelectorAll('[data-testid="clue-text"]');
  for (const element of texts) {
    const cell = element.closest('[data-testid="cell"]');
    const box = element.getBoundingClientRect();
    const cellBox = cell.getBoundingClientRect();
    const style = getComputedStyle(element);
    const problems = [];
    if (element.scrollWidth > element.clientWidth + 1) problems.push('wide');
    if (element.scrollHeight > element.clientHeight + 1) problems.push('high');
    if (box.left < cellBox.left - 1 || box.right > cellBox.right + 1) {
      problems.push('outside the cell horizontally');
    }
    if (box.top < cellBox.top - 1 || box.bottom > cellBox.bottom + 1) {
      problems.push('outside the cell vertically');
    }
    if (style.visibility !== 'visible') problems.push('not visible');
    if (problems.length > 0) {
      const where = cell.dataset.row + ',' + cell.dataset.column;
      failures.push(where + ' ' + element.textContent + ': ' + problems.join());
    }
  }
  return {count: texts.length, failures: failures};
}
"""


# ---- Mocked room socket (browser tests of AC-4 and AC-6) ---------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self, page: Page) -> None:
        self.page = page
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


# ---- FX-02 ---------------------------------------------------------------------


def test_ac1_fx02_imports_and_is_13_wide_by_17_high(fx02_text: str) -> None:
    report = import_grid(fx02_text)

    assert report.grid.width == 13
    assert report.grid.height == 17
    assert report.word_count == FX02_WORD_COUNT
    assert len(report.grid.cells) == 13 * 17


def test_ac1_fx02_uses_four_arrows_and_has_three_two_clue_cells(
    fx02_grid: Grid,
) -> None:
    arrows_used: set[Arrow] = set()
    two_clue_cells = 0
    for cell in fx02_grid.cells:
        if isinstance(cell, ClueCell):
            if len(cell.clues) == 2:
                two_clue_cells += 1
            for clue in cell.clues:
                arrows_used.add(clue.arrow)

    assert arrows_used == set(Arrow)
    assert two_clue_cells >= 3


def test_ac1_fx02_has_a_clue_between_two_letters_in_a_row_and_a_column(
    fx02_grid: Grid,
) -> None:
    in_row = False
    in_column = False
    for cell in fx02_grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        row, column = cell.row, cell.column
        if 0 < column < fx02_grid.width - 1:
            left = fx02_grid.cell_at(row, column - 1)
            right = fx02_grid.cell_at(row, column + 1)
            if isinstance(left, LetterCell) and isinstance(right, LetterCell):
                in_row = True
        if 0 < row < fx02_grid.height - 1:
            above = fx02_grid.cell_at(row - 1, column)
            below = fx02_grid.cell_at(row + 1, column)
            if isinstance(above, LetterCell) and isinstance(below, LetterCell):
                in_column = True

    assert in_row
    assert in_column


def test_ac1_fx02_clue_texts_are_short_and_one_is_long_in_a_two_clue_cell(
    fx02_grid: Grid,
) -> None:
    longest_in_two_clue_cell = 0
    for cell in fx02_grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for clue in cell.clues:
            assert 1 <= len(clue.text) <= 32, clue.text
            if len(cell.clues) == 2:
                longest_in_two_clue_cell = max(longest_in_two_clue_cell, len(clue.text))

    assert longest_in_two_clue_cell >= 24


# ---- AC-1: pan and pinch zoom on a phone, no clue text cut off ----------------


def test_ac1_at_load_zoom_is_minimum_and_the_whole_grid_fits_on_a_phone(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)

    expect(viewport).to_have_attribute("data-zoom-min", "1")
    zoom_text = viewport.get_attribute("data-zoom")
    zoom_max_text = viewport.get_attribute("data-zoom-max")
    assert_zoom_format(zoom_text)
    assert_zoom_format(zoom_max_text)
    assert zoom_text is not None
    assert zoom_max_text is not None
    assert float(zoom_text) == 1.0
    assert float(zoom_max_text) > 1.0

    client_width, client_height = client_size(viewport)
    viewport_box = box_of(viewport)
    grid_box = box_of(phone_page.get_by_test_id("grid"))
    assert grid_box["width"] <= client_width + 1
    assert grid_box["height"] <= client_height + 1
    assert grid_box["x"] >= viewport_box["x"] - 1
    assert grid_box["y"] >= viewport_box["y"] - 1
    assert grid_box["x"] + grid_box["width"] <= viewport_box["x"] + client_width + 1
    assert grid_box["y"] + grid_box["height"] <= viewport_box["y"] + client_height + 1


def test_ac1_at_load_the_phone_page_shows_every_cell_of_fx02(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    open_room(phone_page, live_server, room_registry, fx02_grid)

    expect(phone_page.get_by_test_id("cell")).to_have_count(13 * 17)
    expect(phone_page.get_by_test_id("clue-text")).to_have_count(FX02_WORD_COUNT)


def test_ac1_clue_texts_of_fx02_are_shown_whole(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx02_grid)

    for cell in fx02_grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for index, clue in enumerate(cell.clues):
            selector = f'[data-testid="clue"][data-clue-index="{index}"]'
            clue_locator = cell_at(page, cell.row, cell.column).locator(selector)
            expect(clue_locator.get_by_test_id("clue-text")).to_have_text(clue.text)


@pytest.mark.parametrize("size", [(1280, 800), (1920, 1080)])
def test_ac1_on_desktop_the_grid_fits_and_needs_no_pan(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    size: tuple[int, int],
) -> None:
    page.set_viewport_size({"width": size[0], "height": size[1]})
    viewport = open_room(page, live_server, room_registry, fx02_grid)

    expect(viewport).to_have_attribute("data-zoom", "1")
    scroll_sizes = viewport.evaluate(
        "element => [element.scrollWidth, element.clientWidth,"
        " element.scrollHeight, element.clientHeight]"
    )
    assert scroll_sizes[0] <= scroll_sizes[1] + 1
    assert scroll_sizes[2] <= scroll_sizes[3] + 1
    viewport_box = box_of(viewport)
    grid_box = box_of(page.get_by_test_id("grid"))
    assert grid_box["x"] >= viewport_box["x"] - 1
    assert grid_box["y"] >= viewport_box["y"] - 1
    assert (
        grid_box["x"] + grid_box["width"]
        <= viewport_box["x"] + viewport_box["width"] + 1
    )
    assert (
        grid_box["y"] + grid_box["height"]
        <= viewport_box["y"] + viewport_box["height"] + 1
    )


@pytest.mark.only_browser("chromium")
def test_ac1_pinch_out_raises_the_zoom_up_to_the_maximum(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    zoom_before = read_zoom(viewport)

    pinch_out(phone_page, viewport)

    wait_for_zoom(phone_page, viewport, f"> before + {EPSILON}", zoom_before)
    zoom_after_one_pinch = read_zoom(viewport)
    assert zoom_after_one_pinch > zoom_before
    assert zoom_after_one_pinch <= read_zoom_max(viewport) + EPSILON

    pinches = pinch_out_to_max(phone_page, viewport)

    assert pinches <= MAX_PINCHES
    zoom_text = viewport.get_attribute("data-zoom")
    assert_zoom_format(zoom_text)
    client_width, _ = client_size(viewport)
    grid_box = box_of(phone_page.get_by_test_id("grid"))
    assert grid_box["width"] > client_width


@pytest.mark.only_browser("chromium")
def test_ac1_pan_scrolls_the_zoomed_grid_in_both_directions(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    pinch_out_to_max(phone_page, viewport)
    scroll_before = viewport.evaluate("e => [e.scrollLeft, e.scrollTop]")

    pan(phone_page, viewport)

    handle = viewport.element_handle()
    assert handle is not None
    phone_page.wait_for_function(
        "element => element.scrollLeft > 0 && element.scrollTop > 0",
        arg=handle,
        timeout=WAIT_TIMEOUT_MS,
    )
    scroll_after = viewport.evaluate("e => [e.scrollLeft, e.scrollTop]")
    assert scroll_after[0] > scroll_before[0]
    assert scroll_after[1] > scroll_before[1]
    assert read_zoom(viewport) == pytest.approx(read_zoom_max(viewport))


@pytest.mark.only_browser("chromium")
def test_ac1_no_clue_text_is_cut_off_at_full_zoom(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    pinch_out_to_max(phone_page, viewport)
    pan(phone_page, viewport)

    result = phone_page.evaluate(CUT_OFF_SCRIPT)

    assert result["count"] == FX02_WORD_COUNT
    assert result["failures"] == []


@pytest.mark.only_browser("chromium")
def test_ac1_pinch_in_lowers_the_zoom(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    pinch_out_to_max(phone_page, viewport)
    zoom_before = read_zoom(viewport)

    pinch_in(phone_page, viewport)

    wait_for_zoom(phone_page, viewport, f"< before - {EPSILON}", zoom_before)
    assert read_zoom(viewport) < zoom_before


@pytest.mark.only_browser("chromium")
def test_ac1_pinch_multiplies_the_zoom_by_the_ratio_of_finger_distances(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    zoom_max = read_zoom_max(viewport)

    pinch(phone_page, viewport, 100.0, 150.0)

    expected_zoom = min(1.5, zoom_max)
    wait_for_zoom(phone_page, viewport, f"> 1 + {EPSILON}", 1.0)
    assert read_zoom(viewport) == pytest.approx(expected_zoom, abs=0.06)


@pytest.mark.only_browser("chromium")
def test_ac1_pinch_in_by_a_ratio_scales_the_zoom_down_by_that_ratio(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    pinch_out_to_max(phone_page, viewport)
    zoom_before = read_zoom(viewport)

    pinch(phone_page, viewport, 200.0, 160.0)

    expected_zoom = max(1.0, zoom_before * 0.8)
    wait_for_zoom(phone_page, viewport, f"< before - {EPSILON}", zoom_before)
    assert read_zoom(viewport) == pytest.approx(expected_zoom, abs=0.06)


@pytest.mark.only_browser("chromium")
def test_ac1_a_pinch_beyond_the_limits_stays_at_the_limit(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)
    pinch_in(phone_page, viewport)
    phone_page.wait_for_timeout(SETTLE_MS)
    assert read_zoom(viewport) == 1.0

    pinch_out_to_max(phone_page, viewport)
    pinch_out(phone_page, viewport)
    phone_page.wait_for_timeout(SETTLE_MS)

    assert read_zoom(viewport) == pytest.approx(read_zoom_max(viewport))
    expect(viewport).to_have_attribute("data-zoom-min", "1")


@pytest.mark.only_browser("chromium")
def test_ac1_a_one_finger_drag_never_changes_the_zoom(
    phone_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
) -> None:
    viewport = open_room(phone_page, live_server, room_registry, fx02_grid)

    pan(phone_page, viewport)
    phone_page.wait_for_timeout(SETTLE_MS)
    assert read_zoom(viewport) == 1.0

    pinch_out(phone_page, viewport)
    wait_for_zoom(phone_page, viewport, f"> 1 + {EPSILON}", 1.0)
    zoom_before = read_zoom(viewport)
    pan(phone_page, viewport)
    phone_page.wait_for_timeout(SETTLE_MS)

    assert read_zoom(viewport) == zoom_before


# ---- AC-2: each arrow is drawn on the side of its word's first letter ---------


def assert_arrow_on_side(arrow_box: FloatRect, cell_box: FloatRect, side: str) -> None:
    arrow_x = arrow_box["x"] + arrow_box["width"] / 2
    arrow_y = arrow_box["y"] + arrow_box["height"] / 2
    cell_left = cell_box["x"]
    cell_top = cell_box["y"]
    cell_width = cell_box["width"]
    cell_height = cell_box["height"]
    if side == "right":
        assert arrow_x >= cell_left + cell_width / 2 + cell_width / 4
        assert arrow_x <= cell_left + cell_width + cell_width / 2
        assert cell_top <= arrow_y <= cell_top + cell_height
    else:
        assert arrow_y >= cell_top + cell_height / 2 + cell_height / 4
        assert arrow_y <= cell_top + cell_height + cell_height / 2
        assert cell_left <= arrow_x <= cell_left + cell_width


@pytest.mark.parametrize(
    ("row", "column", "index", "arrow", "side"),
    FX01_CLUES,
    ids=[f"{r}-{c}-clue{i}" for r, c, i, _, _ in FX01_CLUES],
)
def test_ac2_arrow_is_drawn_on_the_side_of_the_first_letter(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    row: int,
    column: int,
    index: int,
    arrow: str,
    side: str,
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, row, column)
    clue = cell.locator(f'[data-testid="clue"][data-clue-index="{index}"]')
    clue_arrow = clue.get_by_test_id("clue-arrow")

    expect(clue).to_have_attribute("data-arrow", arrow)
    expect(clue_arrow).to_have_count(1)
    expect(clue_arrow).to_have_attribute("data-arrow", arrow)
    expect(clue_arrow).to_have_attribute("data-side", side)
    expect(clue_arrow).to_have_attribute("aria-hidden", "true")
    expect(clue_arrow).to_have_text("")
    assert_arrow_on_side(box_of(clue_arrow), box_of(cell), side)


def test_ac2_clue_zero_of_the_double_clue_cell_is_listed_first(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    clues = cell_at(page, 0, 0).get_by_test_id("clue")

    expect(clues).to_have_count(2)
    expect(clues.nth(0)).to_have_attribute("data-clue-index", "0")
    expect(clues.nth(0)).to_have_attribute("data-arrow", "down_then_right")
    expect(clues.nth(1)).to_have_attribute("data-clue-index", "1")
    expect(clues.nth(1)).to_have_attribute("data-arrow", "right_then_down")


def test_ac2_two_arrows_on_the_right_share_the_sides_of_the_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    double_right_cells: list[ClueCell] = []
    for cell in fx02_grid.cells:
        if not isinstance(cell, ClueCell) or len(cell.clues) != 2:
            continue
        arrows = {cell.clues[0].arrow, cell.clues[1].arrow}
        if arrows == {Arrow.RIGHT, Arrow.RIGHT_THEN_DOWN}:
            double_right_cells.append(cell)
    assert len(double_right_cells) >= 2, "FX-02 must hold such cells"

    for cell in double_right_cells:
        cell_locator = cell_at(page, cell.row, cell.column)
        cell_box = box_of(cell_locator)
        for index in (0, 1):
            clue = cell_locator.locator(
                f'[data-testid="clue"][data-clue-index="{index}"]'
            )
            clue_arrow = clue.get_by_test_id("clue-arrow")
            expect(clue_arrow).to_have_attribute("data-side", "right")
            assert_arrow_on_side(box_of(clue_arrow), cell_box, "right")
            arrow_box = box_of(clue_arrow)
            arrow_y = arrow_box["y"] + arrow_box["height"] / 2
            middle = cell_box["y"] + cell_box["height"] / 2
            if index == 0:
                assert cell_box["y"] <= arrow_y <= middle
            else:
                assert middle <= arrow_y <= cell_box["y"] + cell_box["height"]


def test_ac2_every_clue_of_fx02_has_one_arrow_on_the_side_of_its_arrow_type(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    bottom_arrows = page.locator('[data-testid="clue-arrow"][data-side="bottom"]')
    right_arrows = page.locator('[data-testid="clue-arrow"][data-side="right"]')
    expected_bottom = 0
    expected_right = 0
    for cell in fx02_grid.cells:
        if isinstance(cell, ClueCell):
            for clue in cell.clues:
                if clue.arrow in (Arrow.DOWN, Arrow.DOWN_THEN_RIGHT):
                    expected_bottom += 1
                else:
                    expected_right += 1

    expect(bottom_arrows).to_have_count(expected_bottom)
    expect(right_arrows).to_have_count(expected_right)


# ---- AC-3: a two-clue cell shows both clues, separated by a line -------------

SEPARATOR_SCRIPT = """
element => {
  const isClear = colour => colour === 'rgba(0, 0, 0, 0)' || colour === 'transparent';
  const style = getComputedStyle(element);
  const box = element.getBoundingClientRect();
  const topWidth =
    style.borderTopStyle === 'none' ? 0 : parseFloat(style.borderTopWidth);
  const bottomWidth =
    style.borderBottomStyle === 'none' ? 0 : parseFloat(style.borderBottomWidth);
  const lineColours = [];
  if (box.height >= 1 && !isClear(style.backgroundColor)) {
    lineColours.push(style.backgroundColor);
  }
  if (topWidth >= 1) lineColours.push(style.borderTopColor);
  if (bottomWidth >= 1) lineColours.push(style.borderBottomColor);
  let cellBackground = 'rgb(255, 255, 255)';
  let ancestor = element.closest('[data-testid="cell"]');
  while (ancestor) {
    const colour = getComputedStyle(ancestor).backgroundColor;
    if (!isClear(colour)) {
      cellBackground = colour;
      break;
    }
    ancestor = ancestor.parentElement;
  }
  return {
    width: box.width,
    height: box.height,
    thickness: Math.max(box.height, topWidth, bottomWidth),
    lineColours: lineColours,
    cellBackground: cellBackground,
  };
}
"""


def assert_separator_is_a_visible_line(separator: Locator) -> None:
    details = separator.evaluate(SEPARATOR_SCRIPT)
    assert details["width"] > details["height"], "the separator is not horizontal"
    assert details["thickness"] >= 1
    assert len(details["lineColours"]) > 0, "the line has no colour"
    different = [c for c in details["lineColours"] if c != details["cellBackground"]]
    assert different, "the line has the colour of the cell background"


def test_ac3_double_clue_cell_shows_both_clues_in_order(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, 0, 0)

    clues = cell.get_by_test_id("clue")
    expect(clues).to_have_count(2)
    expect(clues.nth(0).get_by_test_id("clue-text")).to_have_text("Passoire fine")
    expect(clues.nth(1).get_by_test_id("clue-text")).to_have_text("De la marine")


def test_ac3_clue_zero_is_stacked_above_clue_one_with_the_line_between(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, 0, 0)
    separator = cell.get_by_test_id("clue-separator")
    expect(separator).to_have_count(1)

    first_text = box_of(cell.get_by_test_id("clue-text").nth(0))
    second_text = box_of(cell.get_by_test_id("clue-text").nth(1))
    separator_box = box_of(separator)
    separator_center = separator_box["y"] + separator_box["height"] / 2

    assert first_text["y"] + first_text["height"] <= second_text["y"] + 0.5
    assert separator_center >= first_text["y"] + first_text["height"] - 0.5
    assert separator_center <= second_text["y"] + 0.5


def test_ac3_separator_is_a_visible_horizontal_line(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    separator = cell_at(page, 0, 0).get_by_test_id("clue-separator")

    assert_separator_is_a_visible_line(separator)


@pytest.mark.parametrize(("row", "column"), [(0, 2), (2, 0)])
def test_ac3_single_clue_cells_have_one_clue_and_no_separator(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    row: int,
    column: int,
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, row, column)

    expect(cell.get_by_test_id("clue")).to_have_count(1)
    expect(cell.get_by_test_id("clue-separator")).to_have_count(0)


def test_ac3_only_the_double_clue_cell_of_fx01_has_a_separator(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    expect(page.get_by_test_id("clue-separator")).to_have_count(1)
    expect(page.get_by_test_id("clue")).to_have_count(8)


def test_ac3_every_double_clue_cell_of_fx02_has_its_own_separator(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    double_cells = []
    for cell in fx02_grid.cells:
        if isinstance(cell, ClueCell) and len(cell.clues) == 2:
            double_cells.append(cell)

    expect(page.get_by_test_id("clue-separator")).to_have_count(len(double_cells))
    for cell in double_cells:
        cell_locator = cell_at(page, cell.row, cell.column)
        separator = cell_locator.get_by_test_id("clue-separator")
        expect(separator).to_have_count(1)
        assert_separator_is_a_visible_line(separator)
        first_text = box_of(cell_locator.get_by_test_id("clue-text").nth(0))
        second_text = box_of(cell_locator.get_by_test_id("clue-text").nth(1))
        separator_box = box_of(separator)
        separator_center = separator_box["y"] + separator_box["height"] / 2
        assert separator_center >= first_text["y"] + first_text["height"] - 0.5
        assert separator_center <= second_text["y"] + 0.5


# ---- AC-4: a new game renders every cell, empty ------------------------------


def test_ac4_fresh_fx01_room_has_25_cells_of_the_right_types(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-width", "5")
    expect(grid).to_have_attribute("data-height", "5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.locator('[data-testid="cell"][data-type="clue"]')).to_have_count(7)
    expect(page.locator('[data-testid="cell"][data-type="letter"]')).to_have_count(18)
    expect(page.locator('[data-testid="cell"][data-type="empty"]')).to_have_count(0)


def test_ac4_each_position_of_fx01_has_the_type_of_the_grid(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    for cell in fx01_grid.cells:
        located = cell_at(page, cell.row, cell.column)
        expect(located).to_have_count(1)
        expect(located).to_have_attribute("data-type", cell.type)


def test_ac4_letter_cells_are_empty_and_unlocked_in_a_fresh_room(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    letter_cells = page.locator('[data-testid="cell"][data-type="letter"]')

    assert letter_cells.count() == 18
    for index in range(letter_cells.count()):
        letter_cell = letter_cells.nth(index)
        expect(letter_cell).to_have_attribute("data-letter", "")
        expect(letter_cell).to_have_attribute("data-locked", "false")
        expect(letter_cell).to_have_text("")
        assert letter_cell.inner_text().strip() == ""


def test_ac4_cells_form_a_table_of_equal_squares_with_zero_zero_top_left(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx01_grid)
    origin = box_of(cell_at(page, 0, 0))
    side = origin["width"]
    assert side >= 10

    for row in range(5):
        for column in range(5):
            box = box_of(cell_at(page, row, column))
            assert box["width"] == pytest.approx(side, abs=1.5)
            assert box["height"] == pytest.approx(side, abs=1.5)
            assert box["x"] == pytest.approx(origin["x"] + column * side, abs=1.5)
            assert box["y"] == pytest.approx(origin["y"] + row * side, abs=1.5)


def test_ac4_fx02_renders_all_221_cells_with_the_type_of_each_position(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx02_grid)

    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-width", "13")
    expect(grid).to_have_attribute("data-height", "17")
    expect(page.get_by_test_id("cell")).to_have_count(13 * 17)
    shown = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-testid=\"cell\"]'))"
        ".map(e => [e.dataset.row, e.dataset.column, e.dataset.type])"
    )
    shown_types = {(int(r), int(c)): t for r, c, t in shown}
    assert len(shown) == 13 * 17
    for cell in fx02_grid.cells:
        assert shown_types[(cell.row, cell.column)] == cell.type


def test_ac4_empty_cells_hold_nothing(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx02_grid)
    empty_cells = page.locator('[data-testid="cell"][data-type="empty"]')

    expect(empty_cells).to_have_count(FX02_EMPTY_CELL_COUNT)
    contents = empty_cells.evaluate_all(
        "elements => elements.map(e => [e.children.length, e.textContent.trim()])"
    )
    for children_count, text in contents:
        assert children_count == 0
        assert text == ""
    for cell in fx02_grid.cells:
        if isinstance(cell, EmptyCell):
            expect(cell_at(page, cell.row, cell.column)).to_have_attribute(
                "data-type", "empty"
            )


def test_ac4_grid_is_labelled_with_the_grid_label(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    assert load_fr()["grid.label"] == "Grille"
    expect(page.get_by_test_id("grid")).to_have_attribute(
        "aria-label", load_fr()["grid.label"]
    )


def test_ac4_grid_sits_inside_the_grid_viewport(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    inside = page.locator(
        '[data-testid="grid-viewport"] [data-testid="grid"] [data-testid="cell"]'
    )

    expect(inside).to_have_count(25)
    expect(page.get_by_test_id("grid-viewport")).to_have_count(1)


def test_ac4_no_grid_before_the_first_snapshot(page: Page, live_server: str) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("grid-viewport")).to_have_count(0)
    expect(page.get_by_test_id("grid")).to_have_count(0)
    expect(page.get_by_test_id("cell")).to_have_count(0)


def test_ac4_a_room_that_is_not_found_never_shows_a_grid(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(page.get_by_test_id("grid-viewport")).to_have_count(0)
    expect(page.get_by_test_id("grid")).to_have_count(0)


# ---- AC-5: responsive from 320 px to desktop ---------------------------------


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_catalogue_page_has_no_horizontal_scroll(
    page: Page, live_server: str, width: int, height: int
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-page")).to_be_visible()

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_has_no_horizontal_scroll(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx02_grid)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_has_a_usable_grid_viewport(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    viewport = open_room(page, live_server, room_registry, fx02_grid)

    window_width = page.evaluate("() => window.innerWidth")
    box = box_of(viewport)
    assert box["x"] >= -1
    assert box["x"] + box["width"] <= window_width + 1
    assert box["width"] >= 100
    assert box["height"] >= 100


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_shows_at_least_one_cell_inside_the_window(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx02_grid)

    cells_inside = page.evaluate("""() => {
          let inside = 0;
          for (const e of document.querySelectorAll('[data-testid="cell"]')) {
            const b = e.getBoundingClientRect();
            if (b.width > 0 && b.height > 0 && b.left >= 0 && b.top >= 0
                && b.right <= window.innerWidth && b.bottom <= window.innerHeight) {
              inside += 1;
            }
          }
          return inside;
        }""")

    assert cells_inside >= 1


# ---- AC-6: the grid shows the letters and locks of the snapshot --------------


def test_ac6_letters_and_locks_of_the_snapshot_are_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, view, 0)

    first = cell_at(page, 1, 0)
    expect(first).to_have_attribute("data-letter", "T")
    expect(first).to_have_attribute("data-locked", "false")
    expect(first).to_have_text("T")
    locked = cell_at(page, 1, 2)
    expect(locked).to_have_attribute("data-letter", "M")
    expect(locked).to_have_attribute("data-locked", "true")
    expect(locked).to_have_text("M")
    untouched = cell_at(page, 1, 1)
    expect(untouched).to_have_attribute("data-letter", "")
    expect(untouched).to_have_attribute("data-locked", "false")
    expect(untouched).to_have_text("")


def test_ac6_only_the_changed_cells_carry_a_letter_or_a_lock(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, view, 0)

    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.locator('[data-testid="cell"][data-locked="true"]')).to_have_count(1)
    expect(page.locator('[data-testid="cell"][data-locked="false"]')).to_have_count(17)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(16)


def test_ac6_a_second_snapshot_without_the_letter_empties_the_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    with_letters = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )
    show_snapshot(page, mock, with_letters, 0)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    emptied = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, emptied, 1)

    first = cell_at(page, 1, 0)
    expect(first).to_have_attribute("data-letter", "")
    expect(first).to_have_text("")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")


def test_ac6_a_second_snapshot_replaces_letters_and_locks(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    first_view = with_letter_cells(
        grid_view(fx01_grid), [(1, 2, {"letter": "M", "locked": True})]
    )
    show_snapshot(page, mock, first_view, 0)
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    second_view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 2, {"letter": "N"}), (3, 4, {"letter": "Z", "locked": True})],
    )

    show_snapshot(page, mock, second_view, 1)

    changed = cell_at(page, 1, 2)
    expect(changed).to_have_attribute("data-letter", "N")
    expect(changed).to_have_attribute("data-locked", "false")
    expect(changed).to_have_text("N")
    newly_locked = cell_at(page, 3, 4)
    expect(newly_locked).to_have_attribute("data-letter", "Z")
    expect(newly_locked).to_have_attribute("data-locked", "true")
    expect(page.locator('[data-testid="cell"][data-locked="true"]')).to_have_count(1)


def test_ac6_the_last_grid_stays_on_screen_after_the_socket_closes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )
    show_snapshot(page, mock, view, 0)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect(cell_at(page, 1, 2)).to_have_text("M")


# ---- AC-7: the room page fits the window -------------------------------------

CELLS_OUTSIDE_SCRIPT = """() => {
  const outside = [];
  for (const e of document.querySelectorAll('[data-testid="cell"]')) {
    const b = e.getBoundingClientRect();
    const inside = b.left >= -1 && b.top >= -1
      && b.right <= window.innerWidth + 1 && b.bottom <= window.innerHeight + 1;
    if (!inside) outside.push(e.dataset.row + ',' + e.dataset.column);
  }
  return outside;
}"""


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_viewport_is_inside_the_window_vertically(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    viewport = open_room(page, live_server, room_registry, fx01_grid)

    expect(viewport).to_have_attribute("data-zoom", "1")
    window_height = page.evaluate("() => window.innerHeight")
    box = box_of(viewport)
    assert box["y"] >= -1
    assert box["y"] + box["height"] <= window_height + 1


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_room_page_has_no_vertical_scroll(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx01_grid)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollHeight, window.innerHeight]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_every_cell_is_inside_the_window(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx01_grid)

    expect(page.get_by_test_id("cell")).to_have_count(25)
    assert page.evaluate(CELLS_OUTSIDE_SCRIPT) == []


# ---- AC-8: a malformed grid in a snapshot is ignored --------------------------

MALFORMED_KINDS = ["duplicate_position", "out_of_range_row", "out_of_range_column"]
MALFORMED_KINDS += ["missing_cell", "extra_cell"]


def malformed_frame(view: GridView, seq: int, kind: str) -> str:
    """A snapshot frame whose grid breaks one rule; it also changes cell (1, 1)."""
    changed = with_letter_cells(view, [(1, 1, {"letter": "Q"})])
    data = json.loads(snapshot_frame(changed, seq))
    cells = data["grid"]["cells"]
    if kind == "duplicate_position":
        cells[1] = dict(cells[0])
    elif kind == "out_of_range_row":
        cells[-1]["row"] = 5
    elif kind == "out_of_range_column":
        cells[-1]["column"] = 5
    elif kind == "missing_cell":
        cells.pop()
    elif kind == "extra_cell":
        cells.append(dict(cells[-1]))
    else:
        pytest.fail(f"unknown kind {kind}")
    return json.dumps(data)


@pytest.mark.parametrize("kind", MALFORMED_KINDS)
def test_ac8_a_malformed_grid_is_ignored_and_the_previous_grid_is_kept(
    page: Page, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    mock = open_mock_room(page, live_server)
    first_view = with_letter_cells(grid_view(fx01_grid), [(1, 0, {"letter": "T"})])
    show_snapshot(page, mock, first_view, 0)

    mock.send(malformed_frame(grid_view(fx01_grid), 1, kind))
    page.wait_for_timeout(SETTLE_MS)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "0")
    expect(room).to_have_attribute("data-status", "joined")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    expect(page.locator('[data-testid="cell"][data-type="clue"]')).to_have_count(7)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-width", "5")
    assert errors == []


@pytest.mark.parametrize("kind", MALFORMED_KINDS)
def test_ac8_a_valid_snapshot_sent_after_a_malformed_one_is_shown(
    page: Page, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, grid_view(fx01_grid), 0)
    mock.send(malformed_frame(grid_view(fx01_grid), 1, kind))
    page.wait_for_timeout(SETTLE_MS)
    next_view = with_letter_cells(grid_view(fx01_grid), [(1, 2, {"letter": "M"})])

    show_snapshot(page, mock, next_view, 2)

    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "M")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    expect(page.get_by_test_id("cell")).to_have_count(25)
