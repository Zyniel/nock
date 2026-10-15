"""Tests of spec 006, AC-1: pan and pinch zoom on a phone, no clue text cut off.

AC-1 starts with the shape of FX-02 (the fixture grid), then opens a room on it: the
at-load checks run in all three engines, the pinch and pan checks in Chromium only
(touch input through the Chrome DevTools Protocol). The shared setup is in
`spec006_harness`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, ElementHandle, Locator, Page, expect

from nock.grid import Arrow, ClueCell, Grid, LetterCell
from nock.grid_import import import_grid
from nock.server import RoomRegistry
from spec006_harness import (
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    box_of,
    cell_at,
    grid_from_text,
    open_room,
)

ZOOM_PATTERN = re.compile(r"^\d+(\.\d{1,2})?$")
MAX_PINCHES = 5
PINCH_STEPS = 10
SMALL_PINCH_START = 40.0
BIG_PINCH_END = 300.0
EPSILON = 1e-6
FX02_WORD_COUNT = 47

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


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
