"""Tests of spec 014, AC-7: the host controls on small screens.

The browser with spec 040's mocked socket: the size of each remove button, the
host panel that shows when there is more to scroll to, the layout guarantees of
the grid, and the fade that hides while a panel control has the keyboard focus.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.

`test_ac1_browser_the_host_view_keeps_the_grids_room` is here although its name
says AC-1: it checks that spec 013 AC-6's layout guarantees still hold with the
host controls, which the spec ties to AC-7. Its name is kept as it was.
"""

from __future__ import annotations

import sys
from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget
from spec014_harness import fx01_grid as fx01_grid
from spec014_harness import joined_mock_room, room_page
from spec014_windows_harness import (
    EPSILON,
    FOCUSED_TEST_ID_SCRIPT,
    MIN_TARGET_PX,
    PANEL_HAS_FOCUS_SCRIPT,
    TARGET_TOLERANCE_PX,
    WINDOW_SIZES,
    eight_players,
    make_page,
    panel_shows_a_more_marker,
    tab_to_control,
)

FEED_LIMIT = 100
TAP_TIMEOUT_MS = 3000
MIN_GRID_VIEWPORT_PX = 100.0


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


# ---- Layout of the host's view (spec 013 AC-6 with the host controls) -------


def check_frame(seq: int) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac1_browser_the_host_view_keeps_the_grids_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        room = joined_mock_room(page, live_server, fx01_grid, eight_players())
        last_seq = 5 + FEED_LIMIT
        for seq in range(6, last_seq + 1):
            room.connections[0].send(check_frame(seq))
        expect(room_page(page)).to_have_attribute("data-seq", str(last_seq))
        expect(page.get_by_test_id("remove-player")).to_have_count(7)
        panel = page.get_by_test_id("host-panel")
        expect(panel).to_be_visible()
        expect(page.get_by_test_id("lock-room")).to_be_visible()
        expect(page.get_by_test_id("settings-form")).to_be_visible()

        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=TAP_TIMEOUT_MS)
        else:
            cell.click(timeout=TAP_TIMEOUT_MS)

        bar = page.get_by_test_id("clue-bar")
        expect(bar).to_have_attribute("data-word", "3,0,0")
        viewport = page.get_by_test_id("grid-viewport")
        viewport_box = viewport.bounding_box()
        bar_box = bar.bounding_box()
        panel_box = panel.bounding_box()
        assert viewport_box is not None
        assert bar_box is not None
        assert panel_box is not None
        sizes = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth,"
            " document.documentElement.scrollHeight, window.innerHeight]"
        )
        scroll_width, window_width, scroll_height, window_height = sizes

        assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
        assert scroll_width <= window_width
        assert scroll_height <= window_height
        expect(viewport).to_have_attribute("data-zoom", "1")
        assert panel_box["x"] >= -EPSILON
        assert panel_box["x"] + panel_box["width"] <= window_width + EPSILON
        grid_box = page.get_by_test_id("grid").bounding_box()
        assert grid_box is not None
        assert grid_box["x"] >= viewport_box["x"] - EPSILON
        assert grid_box["y"] >= viewport_box["y"] - EPSILON
        grid_right = grid_box["x"] + grid_box["width"]
        grid_bottom = grid_box["y"] + grid_box["height"]
        assert grid_right <= viewport_box["x"] + viewport_box["width"] + EPSILON
        assert grid_bottom <= viewport_box["y"] + viewport_box["height"] + EPSILON
        assert bar_box["x"] >= -EPSILON
        assert bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        assert bar_box["y"] >= -EPSILON
        bar_bottom = bar_box["y"] + bar_box["height"]
        assert bar_bottom <= window_height + EPSILON
        if touch:
            keyboard_box = page.get_by_test_id("keyboard").bounding_box()
            assert keyboard_box is not None
            assert bar_bottom <= keyboard_box["y"] + EPSILON
            keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
            assert keyboard_bottom <= window_height + EPSILON
    finally:
        close()


# ---- AC-7: the host controls on small screens -------------------------------


PANEL_INFO_SCRIPT = """
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const style = getComputedStyle(panel);
  let webkit = null;
  try {
    const bar = getComputedStyle(panel, '::-webkit-scrollbar');
    webkit = { display: bar.display, width: bar.width, height: bar.height };
  } catch (error) {
    webkit = null;
  }
  return {
    scrollWidth: panel.scrollWidth,
    clientWidth: panel.clientWidth,
    overflowX: style.overflowX,
    scrollbarWidth: style.scrollbarWidth === undefined
      ? 'auto' : style.scrollbarWidth,
    webkit: webkit,
  };
}
"""


def open_full_host_view(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Open the host's view with 8 players and a full feed; return page, closer."""
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        room = joined_mock_room(page, live_server, grid, eight_players())
        last_seq = 5 + FEED_LIMIT
        for seq in range(6, last_seq + 1):
            room.connections[0].send(check_frame(seq))
        expect(room_page(page)).to_have_attribute("data-seq", str(last_seq))
        expect(page.get_by_test_id("remove-player")).to_have_count(7)
        expect(page.get_by_test_id("host-panel")).to_be_visible()
    except BaseException:
        close()
        raise
    return page, close


def panel_shows_a_scrollbar(info: dict[str, object], browser_name: str) -> bool:
    """Tell whether the panel's computed style leaves a scrollbar visible."""
    if info["overflowX"] not in ("auto", "scroll"):
        return False
    if info["scrollbarWidth"] == "none":
        return False
    webkit = info["webkit"]
    if browser_name == "firefox" or not isinstance(webkit, dict):
        return True
    if webkit["display"] == "none":
        return False
    return webkit["width"] != "0px" and webkit["height"] != "0px"


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_browser_every_remove_button_is_at_least_24_by_24_pixels(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        buttons = page.get_by_test_id("remove-player").all()
        assert len(buttons) == 7
        for button in buttons:
            box = button.bounding_box()
            assert box is not None
            assert box["width"] >= MIN_TARGET_PX - TARGET_TOLERANCE_PX
            assert box["height"] >= MIN_TARGET_PX - TARGET_TOLERANCE_PX
    finally:
        close()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_browser_a_host_panel_wider_than_its_box_shows_that_there_is_more(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        info = page.evaluate(PANEL_INFO_SCRIPT)
        overflows = info["scrollWidth"] > info["clientWidth"]
        if overflows:
            shows_scrollbar = panel_shows_a_scrollbar(info, browser_name)
            shows_marker = panel_shows_a_more_marker(page)
            assert shows_scrollbar or shows_marker, info
    finally:
        close()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
def test_ac7_browser_the_narrowest_window_really_overflows_and_says_so(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, 320, 568, touch
    )
    try:
        info = page.evaluate(PANEL_INFO_SCRIPT)
        assert info["scrollWidth"] > info["clientWidth"], info
        shows_scrollbar = panel_shows_a_scrollbar(info, browser_name)
        shows_marker = panel_shows_a_more_marker(page)
        assert shows_scrollbar or shows_marker, info
    finally:
        close()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_browser_the_layout_guarantees_of_the_grid_still_hold(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=TAP_TIMEOUT_MS)
        else:
            cell.click(timeout=TAP_TIMEOUT_MS)
        bar = page.get_by_test_id("clue-bar")
        expect(bar).to_have_attribute("data-word", "3,0,0")
        viewport_box = page.get_by_test_id("grid-viewport").bounding_box()
        bar_box = bar.bounding_box()
        assert viewport_box is not None
        assert bar_box is not None
        sizes = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth,"
            " document.documentElement.scrollHeight, window.innerHeight]"
        )
        scroll_width, window_width, scroll_height, window_height = sizes

        assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
        assert scroll_width <= window_width
        assert scroll_height <= window_height
        assert bar_box["x"] >= -EPSILON
        assert bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        assert bar_box["y"] >= -EPSILON
        bar_bottom = bar_box["y"] + bar_box["height"]
        assert bar_bottom <= window_height + EPSILON
        if touch:
            keyboard_box = page.get_by_test_id("keyboard").bounding_box()
            assert keyboard_box is not None
            assert bar_bottom <= keyboard_box["y"] + EPSILON
    finally:
        close()


# ---- AC-7 (amended): the fade hides while a panel control has the keyboard focus ----


FADE_STATE_SCRIPT = """
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const fade = document.querySelector('[data-testid="host-panel-more"]');
  const style = getComputedStyle(fade);
  return {
    hidden: style.visibility === 'hidden' || style.display === 'none',
    hiddenPastRightEdge:
      panel.scrollWidth - panel.clientWidth - panel.scrollLeft > 1,
  };
}
"""


FOCUS_LEAVING_PLATFORMS = ("win32", "darwin")


def engine_drops_the_focus_after_a_press(browser_name: str) -> bool:
    """Tell whether a click or tap takes the focus off the button (spec 014 AC-7).

    That is WebKit on Windows and macOS. Every other pair of engine and operating
    system (`sys.platform`) keeps the focus on the clicked button.
    """
    return browser_name == "webkit" and sys.platform in FOCUS_LEAVING_PLATFORMS


def press_at_centre(page: Page, test_id: str, touch: bool) -> None:
    """Click or tap the centre of a control without scrolling it into view."""
    box = page.get_by_test_id(test_id).bounding_box()
    assert box is not None
    x = box["x"] + box["width"] / 2
    y = box["y"] + box["height"] / 2
    if touch:
        page.touchscreen.tap(x, y)
    else:
        page.mouse.click(x, y)


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
def test_ac7_browser_a_keyboard_focus_in_the_host_panel_hides_the_fade(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, 320, 568, touch
    )
    try:
        before = page.evaluate(FADE_STATE_SCRIPT)
        assert before["hiddenPastRightEdge"] is True, before
        assert before["hidden"] is False, before

        for control in ("lock-room", "help-mode-select", "settings-save"):
            tab_to_control(page, control)
            page.wait_for_timeout(300)
            state = page.evaluate(FADE_STATE_SCRIPT)
            assert state["hidden"] is True, (control, state)
    finally:
        close()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
def test_ac7_browser_a_pointer_focus_in_the_host_panel_keeps_the_fade(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_full_host_view(
        browser, browser_name, live_server, fx01_grid, 320, 568, touch
    )
    try:
        tab_to_control(page, "lock-room")
        page.wait_for_timeout(300)
        assert page.evaluate(FADE_STATE_SCRIPT)["hidden"] is True

        press_at_centre(page, "lock-room", touch)
        page.wait_for_timeout(300)

        if engine_drops_the_focus_after_a_press(browser_name):
            assert page.evaluate(PANEL_HAS_FOCUS_SCRIPT) is False
        else:
            assert page.evaluate(FOCUSED_TEST_ID_SCRIPT) == "lock-room"
        state = page.evaluate(FADE_STATE_SCRIPT)
        assert state["hiddenPastRightEdge"] is True, state
        assert state["hidden"] is False, state
        assert panel_shows_a_more_marker(page)
    finally:
        close()
