"""Tests of spec 043, AC-28: everything stays inside the window and the grid keeps
its room, whatever is open.

With `H8`, at each window size of spec 006 AC-5, in the desktop and touch
contexts, and at 568 by 320 and 740 by 360 also in the touch context with
`nock.keyboard_hidden` seeded `"true"`, one page goes through the four states of
the criterion in this order: the Salon open on Discussion, `aide-menu` open,
`room-menu` open, all closed (the column layout's Salon closed by a click on
`chat-toggle`). In each state: spec 013 AC-6's checks, the top bar, the clue bar
and what is open inside the window, the hit tests, and the timer on one line; in
the sheet layout `grid-viewport` keeps one box in the four states; in the column
layout, with the Salon open, three more line events leave the grid's box as it
was.

Choices where the spec leaves room:

- In the sheet layout, the clue bar's buttons cannot be hit while the Salon sheet
  or a popover is open: the Salon sheet, or the popover's `room-scrim` from 54 px
  below the window's top ("Popovers: shared rules"), covers the bar. These are the
  exceptions the criterion names (refined 2026-10-22). They are read from the page
  (the Salon or `aide-menu` or `room-menu` without `hidden`), not from the state's
  name. In the column layout the clue bar's hit tests run in every state, and in
  the sheet layout in the state where nothing is open.
- "Each item of an open popover" is each `button` and `a` inside it.
- The touch context with `nock.keyboard_hidden`: refined by spec 044 (the
  design's keyboard), which reads that key, so the page there is in the column
  layout (checked) with the phone top bar, whose `keyboard-toggle` is among the
  top-bar buttons that the hit tests read.
- Spec 013 AC-6's keyboard check runs whenever `keyboard` is on the page.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page

from nock.grid import Grid
from room_panels import open_aide, open_menu, show_tab
from spec019_harness import (
    MIN_GRID_VIEWPORT_PX,
    WINDOW_SIZES,
    OpenWindow,
    window_opener,
)
from spec042_harness import box_of, expect_seq
from spec043_harness import (
    CLUE_BAR_BUTTONS,
    H8_LAST_SEQ,
    PHONE_TOP_BAR_HEIGHT,
    Box,
    RoomMock,
    box_inside,
    check_frame,
    expect_closed,
    expect_layout,
    hit_problem,
    is_open,
    layout_of,
    open_h8,
    same_box,
    same_size,
    seed_value,
    shown_items,
    shown_test_ids,
    window_box,
)

# Each case: its window, whether the context is touch, and whether
# `nock.keyboard_hidden` is seeded.
FIT_CASES: list[tuple[int, int, bool, bool]] = []
FIT_IDS: list[str] = []
for _width, _height in WINDOW_SIZES:
    for _touch in (False, True):
        FIT_CASES.append((_width, _height, _touch, False))
        FIT_IDS.append(f"{_width}x{_height}-{'touch' if _touch else 'desktop'}")
for _width, _height in ((568, 320), (740, 360)):
    FIT_CASES.append((_width, _height, True, True))
    FIT_IDS.append(f"{_width}x{_height}-touch-keyboard-hidden")

STATES = ["salon", "aide", "menu", "closed"]
POPOVER_OF_STATE = {"aide": "aide-menu", "menu": "room-menu"}
TIMER_LINES_SCRIPT = r"""
element => {
  const range = document.createRange();
  range.selectNodeContents(element);
  const tops = [];
  for (const rect of range.getClientRects()) {
    if (rect.width === 0 && rect.height === 0) {
      continue;
    }
    if (!tops.some(top => Math.abs(top - rect.top) <= 1)) {
      tops.push(rect.top);
    }
  }
  return tops.length;
}
"""
PAGE_SIZES_SCRIPT = (
    "() => [document.documentElement.scrollWidth, window.innerWidth,"
    " document.documentElement.scrollHeight, window.innerHeight]"
)
ITEM_HIT_SCRIPT = r"""
item => {
  item.scrollIntoView({block: 'nearest'});
  const box = item.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
    box.top + box.height / 2);
  return {
    hits: hit !== null && (hit === item || item.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- States and checks -------------------------------------------------------------


def set_state(page: Page, state: str) -> None:
    """Put the page in one of the four states of AC-28."""
    if state == "salon":
        show_tab(page, "discussion")
    elif state == "aide":
        open_aide(page)
    elif state == "menu":
        open_menu(page)
    else:
        page.keyboard.press("Escape")
        expect_closed(page.get_by_test_id("room-menu"))
        salon = page.get_by_test_id("salon")
        if is_open(salon):
            page.get_by_test_id("chat-toggle").click()
        expect_closed(salon)
        expect_closed(page.get_by_test_id("aide-menu"))


def grid_room_problems(page: Page) -> list[str]:
    """Spec 013 AC-6's checks, the keyboard's whenever it is on the page."""
    problems: list[str] = []
    viewport = page.get_by_test_id("grid-viewport")
    viewport_box = box_of(viewport)
    grid_box = box_of(page.get_by_test_id("grid"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    scroll_width, window_width, scroll_height, window_height = page.evaluate(
        PAGE_SIZES_SCRIPT
    )
    if viewport_box.height < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport is {viewport_box.height} px high")
    if scroll_width > window_width:
        problems.append(f"page scrolls sideways: {scroll_width} > {window_width}")
    if scroll_height > window_height:
        problems.append(f"page scrolls down: {scroll_height} > {window_height}")
    if viewport.get_attribute("data-zoom") != "1":
        problems.append(f"data-zoom is {viewport.get_attribute('data-zoom')}")
    if not box_inside(grid_box, viewport_box):
        problems.append(f"grid {grid_box} is not inside the viewport {viewport_box}")
    keyboard = page.get_by_test_id("keyboard")
    if keyboard.count() == 1 and keyboard.is_visible():
        keyboard_box = box_of(keyboard)
        if bar_box.bottom > keyboard_box.top + 1.0:
            problems.append(f"clue-bar {bar_box} goes below the keyboard's top")
    return problems


def inside_window_problems(page: Page, state: str) -> list[str]:
    window = window_box(page)
    problems: list[str] = []
    names = ["room-topbar", "clue-bar"]
    if state in POPOVER_OF_STATE:
        names.append(POPOVER_OF_STATE[state])
    if is_open(page.get_by_test_id("salon")):
        names.append("salon")
    for name in names:
        box = box_of(page.get_by_test_id(name))
        if not box_inside(box, window):
            problems.append(f"{name} {box} is not inside the window {window}")
    return problems


def top_bar_buttons(page: Page) -> list[str]:
    buttons: list[str] = []
    for item in shown_items(page.get_by_test_id("room-topbar")):
        if item["tag"] == "BUTTON":
            buttons.append(str(item["testId"]))
    return buttons


def clue_bar_is_covered(page: Page) -> bool:
    """Tell whether the open Salon sheet or a popover's scrim covers the clue bar.

    Only the sheet layout has them over the bar; the column layout's Salon is a
    column beside the grid and its popovers leave the bar alone.
    """
    if layout_of(page) != "sheet":
        return False
    if is_open(page.get_by_test_id("salon")):
        return True
    for popover in POPOVER_OF_STATE.values():
        if is_open(page.get_by_test_id(popover)):
            return True
    return False


def hit_problems(page: Page) -> list[str]:
    """The hit tests of the top bar's and the clue bar's buttons."""
    problems: list[str] = []
    for test_id in top_bar_buttons(page):
        found = hit_problem(page, test_id)
        if found is not None:
            problems.append(found)
    if not clue_bar_is_covered(page):
        for test_id in CLUE_BAR_BUTTONS:
            found = hit_problem(page, test_id)
            if found is not None:
                problems.append(found)
    return problems


def popover_item_problems(popover: Locator) -> list[str]:
    problems: list[str] = []
    items = popover.locator("button, a")
    for index in range(items.count()):
        item = items.nth(index)
        found = item.evaluate(ITEM_HIT_SCRIPT)
        if found["hits"] is not True:
            name = item.get_attribute("data-testid")
            problems.append(f"{name}: elementFromPoint at its centre is {found['hit']}")
    return problems


def timer_problems(page: Page) -> list[str]:
    timer = page.get_by_test_id("timer")
    text = timer.text_content()
    lines = timer.evaluate(TIMER_LINES_SCRIPT)
    problems: list[str] = []
    if text is None or not text.strip().startswith("10:00:"):
        problems.append(f"timer reads {text!r}")
    if lines != 1:
        problems.append(f"timer on {lines} lines")
    return problems


def low_window_problems(page: Page) -> list[str]:
    """On a window at most 500 px high the top bar is the phone top bar."""
    top_bar = page.get_by_test_id("room-topbar")
    problems: list[str] = []
    height = box_of(top_bar).height
    if not same_size(height, PHONE_TOP_BAR_HEIGHT):
        problems.append(f"room-topbar is {height} px high")
    if "topbar-brand" in shown_test_ids(top_bar):
        problems.append("topbar-brand shows")
    return problems


def state_problems(page: Page, state: str, height: int) -> list[str]:
    problems = grid_room_problems(page)
    problems.extend(inside_window_problems(page, state))
    problems.extend(hit_problems(page))
    if state in POPOVER_OF_STATE:
        problems.extend(
            popover_item_problems(page.get_by_test_id(POPOVER_OF_STATE[state]))
        )
    problems.extend(timer_problems(page))
    if height <= 500:
        problems.extend(low_window_problems(page))
    return [f"{state}: {problem}" for problem in problems]


def grid_keeps_its_box(page: Page, mock: RoomMock) -> list[str]:
    """With the Salon column open, three more line events leave the grid's box."""
    show_tab(page, "discussion")
    before = box_of(page.get_by_test_id("grid"))
    for seq in range(H8_LAST_SEQ + 1, H8_LAST_SEQ + 4):
        mock.send(check_frame(seq, "p2"))
    expect_seq(page, H8_LAST_SEQ + 3)
    after = box_of(page.get_by_test_id("grid"))
    if same_box(before, after):
        return []
    return [f"the grid moved from {before} to {after} after 3 line events"]


# ---- AC-28 ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("width", "height", "touch", "keyboard_hidden"), FIT_CASES, ids=FIT_IDS
)
def test_ac28_everything_stays_in_the_window_in_the_four_states(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    touch: bool,
    keyboard_hidden: bool,
) -> None:
    page = window(width, height, touch)
    if keyboard_hidden:
        seed_value(page, "nock.keyboard_hidden", "true")
    mock = open_h8(page, live_server, fx01_grid, touch)
    if keyboard_hidden:
        # Spec 044: with the keyboard hidden, a low window is the column layout.
        expect_layout(page, "column")
    layout = layout_of(page)

    problems: list[str] = []
    viewport_boxes: list[Box] = []
    for state in STATES:
        set_state(page, state)
        problems.extend(state_problems(page, state, height))
        viewport_boxes.append(box_of(page.get_by_test_id("grid-viewport")))
    if layout == "sheet":
        for state, box in zip(STATES, viewport_boxes, strict=True):
            if not same_box(box, viewport_boxes[0]):
                problems.append(
                    f"{state}: grid-viewport {box}, not {viewport_boxes[0]}"
                )
    else:
        problems.extend(grid_keeps_its_box(page, mock))

    assert layout in ("sheet", "column")
    assert problems == []
