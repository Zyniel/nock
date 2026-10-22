"""Tests of spec 014, AC-7: the host controls stay usable on small screens.

The browser with spec 040's mocked socket.

Refined by spec 043 (the design's room layout): the host's « Couper » and
« Retirer » sit in the other players' rows of the Salon's Joueurs tab, and the
host's settings are the room sheet `host-settings`. Nothing scrolls sideways any
more, so the host panel's fade and its focus rules go; what stays is the 24 px rule
and the reach of each control, the sheet's controls included:

- with the Joueurs tab shown (`show_tab`), each `remove-player` and `mute-player`
  is at least 24 by 24 px and lies inside the Salon once scrolled into view, while
  spec 013 AC-6's layout guarantees hold;
- after `open_host_settings`, the sheet lies inside the window and each of its
  controls is at least 24 px high and reachable by a pointer;
- keyboard only, the sheet opened from `menu-button`, `Tab` reaches the sheet's
  controls in order, each with spec 035 AC-2's outline inside the dialog.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.

Choices where the spec leaves room:

- Sizes have spec 043's tolerance of 0.5 px.
- "`Tab` reaches ... in this order": from the focus the sheet takes when it opens,
  `Tab` is pressed until `settings-save` has the focus (at most 20 presses); the
  test ids met on the way, in order and without repeats, are those five.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from room_panels import open_host_settings, show_tab
from spec014_harness import fx01_grid as fx01_grid
from spec014_harness import joined_mock_room
from spec014_windows_harness import (
    MIN_TARGET_PX,
    WINDOW_IDS,
    WINDOW_SIZES,
    at_least,
    dialog_reading,
    eight_players,
    inside,
    make_page,
    sheet_control_problems,
)
from spec019_harness import layout_problems
from spec024_harness import outline_problems
from spec035_harness import FOCUS_OUTLINE_SCRIPT, Walker

TAP_TIMEOUT_MS = 3000
HOST_BUTTONS = ["mute-player", "remove-player"]
KEYBOARD_WINDOWS = [(320, 568), (1280, 720)]
SHEET_TAB_ORDER = [
    "lock-room",
    "help-mode-option",
    "reveal-letters-input",
    "reveal-words-input",
    "settings-save",
]
MAX_SHEET_TABS = 20

# Each host button's box after `scrollIntoView`, with the Salon's box.
BUTTON_BOXES_SCRIPT = r"""
testId => {
  const salon = document.querySelector('[data-testid="salon"]');
  const found = [];
  for (const button of document.querySelectorAll(`[data-testid="${testId}"]`)) {
    button.scrollIntoView({block: 'nearest', inline: 'nearest'});
    const box = button.getBoundingClientRect();
    const salonBox = salon.getBoundingClientRect();
    found.push({
      box: [box.left, box.top, box.right, box.bottom],
      salon: [salonBox.left, salonBox.top, salonBox.right, salonBox.bottom],
    });
  }
  return found;
}
"""
FOCUSED_BOX_SCRIPT = r"""
() => {
  const element = document.activeElement;
  const style = getComputedStyle(element);
  const grow = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
  const box = element.getBoundingClientRect();
  return {
    testId: element.getAttribute('data-testid'),
    outer: [box.left - grow, box.top - grow, box.right + grow, box.bottom + grow],
  };
}
"""


def tap_a_cell(page: Page, touch: bool) -> None:
    cell = page.locator('[data-testid="cell"][data-row="3"][data-column="1"]')
    if touch:
        cell.tap(timeout=TAP_TIMEOUT_MS)
    else:
        cell.click(timeout=TAP_TIMEOUT_MS)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")


def host_button_problems(page: Page) -> list[str]:
    problems: list[str] = []
    for test_id in HOST_BUTTONS:
        readings = page.evaluate(BUTTON_BOXES_SCRIPT, test_id)
        if len(readings) != 7:
            problems.append(f"{len(readings)} {test_id} buttons, expected 7")
        for index, reading in enumerate(readings):
            left, top, right, bottom = reading["box"]
            if not at_least(right - left, MIN_TARGET_PX):
                problems.append(f"{test_id} {index}: {right - left} px wide")
            if not at_least(bottom - top, MIN_TARGET_PX):
                problems.append(f"{test_id} {index}: {bottom - top} px high")
            if not inside(reading["box"], reading["salon"]):
                problems.append(f"{test_id} {index} is not inside the Salon")
    return problems


# ---- AC-7: the buttons of the Joueurs rows -------------------------------------


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac7_browser_each_host_button_is_24_px_and_inside_the_salon(
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
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        tap_a_cell(page, touch)
        show_tab(page, "players")

        problems = host_button_problems(page)

        assert problems == []
    finally:
        close()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac7_browser_the_grid_keeps_its_room_with_the_joueurs_tab_shown(
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
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        tap_a_cell(page, touch)
        show_tab(page, "players")

        assert layout_problems(page, touch) == []
    finally:
        close()


# ---- AC-7: the host's settings sheet ---------------------------------------------


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac7_browser_the_settings_sheet_fits_and_each_control_is_reachable(
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
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        open_host_settings(page)

        dialog = dialog_reading(page)
        problems = sheet_control_problems(page, min_height=MIN_TARGET_PX)

        assert inside(dialog["box"], dialog["window"]), dialog
        assert problems == []
    finally:
        close()


@pytest.mark.parametrize(("width", "height"), KEYBOARD_WINDOWS)
def test_ac7_browser_from_the_keyboard_tab_walks_the_sheet_in_order(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = make_page(browser, browser_name, width, height, False)
    try:
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        walker = Walker(page)
        walker.tab_to("menu-button")
        page.keyboard.press("Enter")
        expect(page.get_by_test_id("room-menu")).to_be_visible()
        walker.tab_to("host-settings-open")
        page.keyboard.press("Enter")
        expect(page.get_by_test_id("host-settings")).to_have_attribute("open", "")
        dialog_box = dialog_reading(page)["box"]

        met: list[str] = []
        problems: list[str] = []
        for _ in range(MAX_SHEET_TABS):
            focused = page.evaluate(FOCUSED_BOX_SCRIPT)
            test_id = focused["testId"]
            if test_id in SHEET_TAB_ORDER and test_id not in met:
                met.append(test_id)
                outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
                found = outline_problems(
                    outline["style"], outline["width"], outline["ratio"]
                )
                problems.extend(f"{test_id}: {problem}" for problem in found)
                if not inside(focused["outer"], dialog_box):
                    problems.append(f"{test_id}: its ring leaves the dialog")
            if test_id == "settings-save":
                break
            page.keyboard.press("Tab")

        assert met == SHEET_TAB_ORDER
        assert problems == []
    finally:
        close()
