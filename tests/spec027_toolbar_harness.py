"""The room toolbar with the timer: the setup and the readings of AC-8.

This module is not a test file: pytest does not collect it. It is spec 024 AC-8's
toolbar setup (spec 013 AC-6's FX-01 snapshot, `you` host among 8 players, 100 feed
items, (3, 1) tapped, help mode `free`, the budget 5 letters and 1 word) with the
timer at `10:00:00`, and spec 024 AC-8's readings of the toolbar, run on seven
buttons: the six of spec 024 and `timer-toggle`. The scripts are spec 024's, copied
so that this spec does not depend on the test file of another spec. The layout
matrix uses a stopped timer (36,000,000 ms, not running), so that the text stays
`10:00:00`; the timer's semantics (its role, its label, no live region) are checked
in `test_spec_027_ac08_a11y_and_french.py`.
"""

from __future__ import annotations

from collections.abc import Callable

# `Any`: the readings come from `page.evaluate`, which returns JSON of any shape.
from typing import Any

from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    WAIT_TIMEOUT_MS,
    cell_at,
    expect_seq,
    open_context_page,
    outline_problems,
    player_view,
)
from spec027_harness import open_timer_room

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
SMALL_WINDOWS = WINDOW_SIZES[:4]
LARGE_WINDOWS = WINDOW_SIZES[4:]
CONTEXTS = ["desktop", "touch"]
SIX_BUTTONS = [
    "undo-button",
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
]
SEVEN_BUTTONS = ["timer-toggle", *SIX_BUTTONS]
FIRST_THREE = ["timer", "timer-toggle", "chat-toggle"]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
MIN_TARGET_PX = 24.0
EPSILON = 1.0
MAX_TABS = 60
SETTLE_MS = 400
TEN_HOURS_MS = 36_000_000
POINTER_FOCUS_SIZE = (320, 568)
AFTER_PRESS_MS = 300


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    """Readable ids of window sizes for `parametrize`."""
    return [f"{width}x{height}" for width, height in sizes]


# ---- The setup ----


def eight_players() -> list[PlayerView]:
    """`p1` (Ana, `you`, host) among 8 players."""
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        players.append(player_view(f"p{number}", nickname, number - 1))
    return players


def check_frame(seq: int) -> str:
    """A `check_result` event, one feed item."""
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


def open_toolbar_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Open the room of the setup with (3, 1) tapped; return the page and its closer.

    Args:
        browser: The browser of the test.
        browser_name: Its engine's name (`chromium`, `firefox` or `webkit`).
        live_server: The live server's base URL.
        grid: FX-01.
        width: The window's width in CSS px.
        height: The window's height in CSS px.
        touch: Whether the context is a touch one.
    """
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_timer_room(
            page,
            live_server,
            grid,
            elapsed_ms=TEN_HOURS_MS,
            running=False,
            players=eight_players(),
        )
        expect(page.get_by_test_id("room-toolbar")).to_be_visible()
        expect(page.get_by_test_id("reveal-panel")).to_be_visible()
        last_seq = 5 + FEED_ITEMS
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq))
        expect_seq(page, last_seq)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=WAIT_TIMEOUT_MS)
        else:
            cell.click(timeout=WAIT_TIMEOUT_MS)
        bar = page.get_by_test_id("clue-bar")
        expect(bar).to_have_attribute("data-word", "3,0,0")
    except BaseException:
        close()
        raise
    return page, close


# ---- Spec 013 AC-6's layout checks ----


def spec013_layout_problems(page: Page, touch: bool) -> list[str]:
    """How the page breaks spec 013 AC-6's checks (as spec 024 AC-8 runs them)."""
    viewport = page.get_by_test_id("grid-viewport")
    viewport_box = viewport.bounding_box()
    bar_box = page.get_by_test_id("clue-bar").bounding_box()
    grid_box = page.get_by_test_id("grid").bounding_box()
    assert viewport_box is not None
    assert bar_box is not None
    assert grid_box is not None
    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth,"
        " document.documentElement.scrollHeight, window.innerHeight]"
    )
    scroll_width, window_width, scroll_height, window_height = sizes
    problems: list[str] = []

    if viewport_box["height"] < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid viewport too short: {viewport_box}")
    if scroll_width > window_width:
        problems.append(f"horizontal scroll: {scroll_width} > {window_width}")
    if scroll_height > window_height:
        problems.append(f"vertical scroll: {scroll_height} > {window_height}")
    if viewport.get_attribute("data-zoom") != "1":
        problems.append(f"data-zoom is {viewport.get_attribute('data-zoom')}")
    if grid_box["x"] < viewport_box["x"] - EPSILON:
        problems.append("grid starts left of its viewport")
    if grid_box["y"] < viewport_box["y"] - EPSILON:
        problems.append("grid starts above its viewport")
    grid_right = grid_box["x"] + grid_box["width"]
    grid_bottom = grid_box["y"] + grid_box["height"]
    if grid_right > viewport_box["x"] + viewport_box["width"] + EPSILON:
        problems.append("grid ends right of its viewport")
    if grid_bottom > viewport_box["y"] + viewport_box["height"] + EPSILON:
        problems.append("grid ends below its viewport")
    if bar_box["x"] < -EPSILON:
        problems.append("clue bar starts left of the window")
    if bar_box["x"] + bar_box["width"] > window_width + EPSILON:
        problems.append("clue bar ends right of the window")
    if bar_box["y"] < -EPSILON:
        problems.append("clue bar starts above the window")
    bar_bottom = bar_box["y"] + bar_box["height"]
    if bar_bottom > window_height + EPSILON:
        problems.append("clue bar ends below the window")
    if touch:
        keyboard_box = page.get_by_test_id("keyboard").bounding_box()
        assert keyboard_box is not None
        if bar_bottom > keyboard_box["y"] + EPSILON:
            problems.append("clue bar overlaps the keyboard")
        keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
        if keyboard_bottom > window_height + EPSILON:
            problems.append("keyboard ends below the window")
    return problems


# ---- Order, one row, the timer's place, the target size, the hit test ----

TOOLBAR_SCRIPT = """
({sevenIds, sixIds}) => {
  const byTestId = (id) => document.querySelectorAll(`[data-testid="${id}"]`);
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const share = document.querySelector('[data-testid="share-panel"]');
  const header = toolbar.closest('header');
  const counts = {};
  const outside = [];
  for (const id of sevenIds) {
    const found = byTestId(id);
    counts[id] = found.length;
    if (found.length === 1 && !toolbar.contains(found[0])) {
      outside.push(id);
    }
  }
  const outOfOrder = [];
  for (let index = 0; index + 1 < sixIds.length; index += 1) {
    const first = byTestId(sixIds[index])[0];
    const second = byTestId(sixIds[index + 1])[0];
    if (first && second && !follows(first, second)) {
      outOfOrder.push([sixIds[index], sixIds[index + 1]]);
    }
  }
  const revealButtons = [];
  for (const button of toolbar.querySelectorAll('button[data-testid^="reveal-"]')) {
    revealButtons.push(button.getAttribute('data-testid'));
  }
  const firstThree = [];
  for (const child of Array.from(toolbar.children).slice(0, 3)) {
    firstThree.push(child.getAttribute('data-testid'));
  }
  const ranges = [];
  for (const id of sevenIds) {
    const box = byTestId(id)[0].getBoundingClientRect();
    ranges.push([id, box.top, box.bottom]);
  }
  return {
    inHeader: header !== null && share !== null && header.contains(share),
    counts: counts,
    outside: outside,
    outOfOrder: outOfOrder,
    revealButtons: revealButtons,
    firstThree: firstThree,
    ranges: ranges,
    scrollWidth: toolbar.scrollWidth,
    clientWidth: toolbar.clientWidth,
    overflowX: getComputedStyle(toolbar).overflowX,
  };
}
"""
SCROLL_TO_START_SCRIPT = """
() => {
  document.querySelector('[data-testid="room-toolbar"]').scrollLeft = 0;
}
"""
FADE_VISIBLE_SCRIPT = """
() => {
  const fade = document.querySelector('[data-testid="room-toolbar-more"]');
  if (fade === null) {
    return false;
  }
  const style = getComputedStyle(fade);
  return style.visibility === 'visible' && style.display !== 'none';
}
"""
# The timer's box against the toolbar's client area, the number of lines its text
# takes (the distinct tops of the rectangles of its text), and its vertical range
# next to the toggle's.
TIMER_PLACE_SCRIPT = """
() => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const timer = document.querySelector('[data-testid="timer"]');
  const toggle = document.querySelector('[data-testid="timer-toggle"]');
  const toolbarBox = toolbar.getBoundingClientRect();
  const box = timer.getBoundingClientRect();
  const toggleBox = toggle.getBoundingClientRect();
  const range = document.createRange();
  range.selectNodeContents(timer);
  const tops = new Set();
  for (const rect of range.getClientRects()) {
    if (rect.width > 0) {
      tops.add(Math.round(rect.top));
    }
  }
  return {
    area: [
      toolbarBox.left + toolbar.clientLeft,
      toolbarBox.top + toolbar.clientTop,
      toolbarBox.left + toolbar.clientLeft + toolbar.clientWidth,
      toolbarBox.top + toolbar.clientTop + toolbar.clientHeight,
    ],
    box: [box.left, box.top, box.right, box.bottom],
    lines: tops.size,
    timerRange: [box.top, box.bottom],
    toggleRange: [toggleBox.top, toggleBox.bottom],
    scrollLeft: toolbar.scrollLeft,
  };
}
"""
SCROLL_INTO_VIEW_SCRIPT = """
testId => {
  const button = document.querySelector(`[data-testid="${testId}"]`);
  button.scrollIntoView({block: 'nearest', inline: 'nearest'});
}
"""
HIT_AT_CENTRE_SCRIPT = """
testId => {
  const button = document.querySelector(`[data-testid="${testId}"]`);
  const box = button.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    hits: hit !== null && (hit === button || button.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""


def pairs_that_do_not_overlap(ranges: list[list[Any]]) -> list[tuple[str, str]]:
    """The pairs of buttons whose vertical ranges do not overlap."""
    apart: list[tuple[str, str]] = []
    for index, (first_id, first_top, first_bottom) in enumerate(ranges):
        for second_id, second_top, second_bottom in ranges[index + 1 :]:
            overlap_top = max(first_top, second_top)
            overlap_bottom = min(first_bottom, second_bottom)
            if overlap_top >= overlap_bottom:
                apart.append((str(first_id), str(second_id)))
    return apart


def structure_problems(page: Page, small: bool) -> list[str]:
    """How the toolbar breaks the order, one-row and fade rules of AC-8."""
    reading = page.evaluate(
        TOOLBAR_SCRIPT, {"sevenIds": SEVEN_BUTTONS, "sixIds": SIX_BUTTONS}
    )
    page.evaluate(SCROLL_TO_START_SCRIPT)
    page.wait_for_timeout(SETTLE_MS)
    fade_visible = page.evaluate(FADE_VISIBLE_SCRIPT)
    problems: list[str] = []

    if reading["inHeader"] is not True:
        problems.append("the toolbar is not in the room header after share-panel")
    expected_counts = dict.fromkeys(SEVEN_BUTTONS, 1)
    if reading["counts"] != expected_counts:
        problems.append(f"counts: {reading['counts']}")
    if reading["outside"] != []:
        problems.append(f"outside the toolbar: {reading['outside']}")
    if reading["outOfOrder"] != []:
        problems.append(f"six buttons out of order: {reading['outOfOrder']}")
    if reading["revealButtons"] != ["reveal-letter", "reveal-word"]:
        problems.append(f"reveal buttons: {reading['revealButtons']}")
    if reading["firstThree"] != FIRST_THREE:
        problems.append(f"first three children of the toolbar: {reading['firstThree']}")
    if small:
        apart = pairs_that_do_not_overlap(reading["ranges"])
        if apart != []:
            problems.append(f"buttons on different rows: {apart}")
        if reading["scrollWidth"] > reading["clientWidth"] + 1:
            if reading["overflowX"] not in ("auto", "scroll"):
                problems.append(f"overflow-x is {reading['overflowX']}")
            if fade_visible is not True:
                problems.append("room-toolbar-more is not visible")
    elif fade_visible is not False:
        problems.append("room-toolbar-more is visible on a larger window")
    return problems


def timer_place_problems(page: Page) -> list[str]:
    """How the timer breaks AC-8's small-window rules (scrollLeft at 0)."""
    page.evaluate(SCROLL_TO_START_SCRIPT)
    page.wait_for_timeout(SETTLE_MS)
    reading = page.evaluate(TIMER_PLACE_SCRIPT)
    problems: list[str] = []
    left, top, right, bottom = reading["box"]
    area_left, area_top, area_right, area_bottom = reading["area"]
    inside = (
        left >= area_left - EPSILON
        and top >= area_top - EPSILON
        and right <= area_right + EPSILON
        and bottom <= area_bottom + EPSILON
    )
    if reading["scrollLeft"] != 0:
        problems.append(f"scrollLeft is {reading['scrollLeft']}")
    if not inside:
        problems.append(f"timer {reading['box']} outside {reading['area']}")
    if reading["lines"] != 1:
        problems.append(f"the timer text takes {reading['lines']} lines")
    timer_top, timer_bottom = reading["timerRange"]
    toggle_top, toggle_bottom = reading["toggleRange"]
    if max(timer_top, toggle_top) >= min(timer_bottom, toggle_bottom):
        problems.append(
            f"timer {reading['timerRange']} and toggle {reading['toggleRange']}"
            " are on different rows"
        )
    return problems


def toggle_size_problems(page: Page) -> list[str]:
    """How `timer-toggle` breaks the 24 by 24 CSS px minimum."""
    box = page.get_by_test_id("timer-toggle").bounding_box()
    assert box is not None
    problems: list[str] = []
    if box["width"] < MIN_TARGET_PX:
        problems.append(f"width {box['width']}")
    if box["height"] < MIN_TARGET_PX:
        problems.append(f"height {box['height']}")
    return problems


def hit_problems(page: Page) -> list[tuple[str, object]]:
    """The buttons whose centre is not hit, once scrolled into view."""
    misses: list[tuple[str, object]] = []
    for test_id in SEVEN_BUTTONS:
        page.evaluate(SCROLL_INTO_VIEW_SCRIPT, test_id)
        page.wait_for_timeout(SETTLE_MS)
        result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
        if result["hits"] is not True:
            misses.append((test_id, result["hit"]))
    return misses


# ---- Keyboard (desktop context) ----

FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
FOCUS_SHARE_LINK_SCRIPT = """
() => document.querySelector('[data-testid="share-link"]').focus()
"""
FOCUS_IN_TOOLBAR_SCRIPT = "() => {\n" + COLOUR_CONTRAST_JS + r"""
  const element = document.activeElement;
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const fade = document.querySelector('[data-testid="room-toolbar-more"]');
  const box = element.getBoundingClientRect();
  const toolbarBox = toolbar.getBoundingClientRect();
  const area = {
    left: toolbarBox.left + toolbar.clientLeft,
    top: toolbarBox.top + toolbar.clientTop,
    right: toolbarBox.left + toolbar.clientLeft + toolbar.clientWidth,
    bottom: toolbarBox.top + toolbar.clientTop + toolbar.clientHeight,
  };
  const style = getComputedStyle(element);
  const width = parseFloat(style.outlineWidth);
  const offset = parseFloat(style.outlineOffset);
  const grow = offset + width;
  const outer = {
    left: box.left - grow, top: box.top - grow,
    right: box.right + grow, bottom: box.bottom + grow,
  };
  const clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  for (let node = element.parentElement; node; node = node.parentElement) {
    const nodeStyle = getComputedStyle(node);
    const clips = nodeStyle.overflowX !== 'visible'
      || nodeStyle.overflowY !== 'visible';
    if (!clips && node !== toolbar) {
      continue;
    }
    const rect = node.getBoundingClientRect();
    clip.left = Math.max(clip.left, rect.left + node.clientLeft);
    clip.top = Math.max(clip.top, rect.top + node.clientTop);
    clip.right = Math.min(clip.right, rect.left + node.clientLeft + node.clientWidth);
    clip.bottom = Math.min(clip.bottom, rect.top + node.clientTop + node.clientHeight);
  }
  let fadeVisible = false;
  if (fade !== null) {
    const fadeStyle = getComputedStyle(fade);
    fadeVisible = fadeStyle.visibility === 'visible' && fadeStyle.display !== 'none';
  }
  const outline = readFocusOutline();
  return {
    testId: element.getAttribute('data-testid'),
    box: [box.left, box.top, box.right, box.bottom],
    area: [area.left, area.top, area.right, area.bottom],
    cut: {
      top: Math.max(clip.top - outer.top, 0),
      right: Math.max(outer.right - clip.right, 0),
      bottom: Math.max(outer.bottom - clip.bottom, 0),
      left: Math.max(clip.left - outer.left, 0),
    },
    outline: outline,
    fadeVisible: fadeVisible,
  };
}
"""


def keyboard_focus_problems(reading: dict[str, Any]) -> list[str]:
    """How a button with the keyboard focus breaks AC-8's keyboard checks."""
    problems: list[str] = []
    left, top, right, bottom = reading["box"]
    area_left, area_top, area_right, area_bottom = reading["area"]
    inside = (
        left >= area_left - EPSILON
        and top >= area_top - EPSILON
        and right <= area_right + EPSILON
        and bottom <= area_bottom + EPSILON
    )
    if not inside:
        problems.append(f"box {reading['box']} outside {reading['area']}")
    outline = reading["outline"]
    problems.extend(
        outline_problems(outline["style"], outline["width"], outline["ratio"])
    )
    for side, pixels in reading["cut"].items():
        if round(pixels) != 0:
            problems.append(f"outline cut by {pixels} px on the {side}")
    if reading["fadeVisible"] is not False:
        problems.append("room-toolbar-more is visible")
    return problems


def walk_the_toolbar(page: Page) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Press Tab from `share-link` until each of the seven buttons had the focus.

    Args:
        page: A desktop page of the setup.

    Returns:
        The reading of each button while it had the focus, and the `data-testid`
        of every element that had the focus on the way, in order.
    """
    readings: dict[str, dict[str, Any]] = {}
    visited: list[str] = []
    page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
    for _ in range(MAX_TABS):
        if len(readings) == len(SEVEN_BUTTONS):
            break
        page.keyboard.press("Tab")
        focused = page.evaluate(FOCUSED_TEST_ID_SCRIPT)
        visited.append(str(focused))
        if focused in SEVEN_BUTTONS and focused not in readings:
            page.wait_for_timeout(SETTLE_MS)
            reading = page.evaluate(FOCUS_IN_TOOLBAR_SCRIPT)
            assert reading["testId"] == focused, reading
            readings[focused] = reading
    return readings, visited


# ---- Pointer focus (320 by 568, click and tap) ----

CENTRE_ON_RIGHT_EDGE_SCRIPT = """
testId => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const button = document.querySelector(`[data-testid="${testId}"]`);
  const toolbarBox = toolbar.getBoundingClientRect();
  const box = button.getBoundingClientRect();
  const areaLeft = toolbarBox.left + toolbar.clientLeft;
  const centre = box.left + box.width / 2 - areaLeft + toolbar.scrollLeft;
  const largest = Math.max(toolbar.scrollWidth - toolbar.clientWidth, 0);
  toolbar.scrollLeft = Math.min(Math.max(centre - toolbar.clientWidth, 0), largest);
}
"""
TOOLBAR_SCROLL_SPY_SCRIPT = r"""
() => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  window.toolbarScrollCalls = [];
  const record = (name, element) => {
    if (element === toolbar || toolbar.contains(element)) {
      window.toolbarScrollCalls.push(name);
    }
  };
  const methods = [
    'scrollIntoView', 'scrollIntoViewIfNeeded', 'scroll', 'scrollTo', 'scrollBy',
  ];
  for (const name of methods) {
    const originalMethod = Element.prototype[name];
    if (typeof originalMethod !== 'function') {
      continue;
    }
    Element.prototype[name] = function (...args) {
      record(name, this);
      return originalMethod.apply(this, args);
    };
  }
  const scrollLeft = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollLeft');
  Object.defineProperty(Element.prototype, 'scrollLeft', {
    configurable: true,
    enumerable: scrollLeft.enumerable,
    get: scrollLeft.get,
    set(value) {
      record('scrollLeft', this);
      scrollLeft.set.call(this, value);
    },
  });
}
"""
VISIBLE_PART_SCRIPT = """
testId => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const button = document.querySelector(`[data-testid="${testId}"]`);
  const toolbarBox = toolbar.getBoundingClientRect();
  const box = button.getBoundingClientRect();
  const areaLeft = toolbarBox.left + toolbar.clientLeft;
  const areaTop = toolbarBox.top + toolbar.clientTop;
  const left = Math.max(box.left, areaLeft);
  const right = Math.min(box.right, areaLeft + toolbar.clientWidth);
  const top = Math.max(box.top, areaTop);
  const bottom = Math.min(box.bottom, areaTop + toolbar.clientHeight);
  return {
    x: (left + right) / 2,
    y: (top + bottom) / 2,
    width: right - left,
    height: bottom - top,
  };
}
"""
AFTER_PRESS_SCRIPT = """
() => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const fade = document.querySelector('[data-testid="room-toolbar-more"]');
  let fadeVisible = false;
  if (fade !== null) {
    const style = getComputedStyle(fade);
    fadeVisible = style.visibility === 'visible' && style.display !== 'none';
  }
  return {
    calls: window.toolbarScrollCalls,
    hiddenPastRight: toolbar.scrollWidth - toolbar.clientWidth - toolbar.scrollLeft,
    scrollLeft: toolbar.scrollLeft,
    fadeVisible: fadeVisible,
  };
}
"""


def press_partly_hidden_button(page: Page, test_id: str, touch: bool) -> dict[str, Any]:
    """Press the visible part of a button at raw coordinates; read the result.

    The toolbar is scrolled so that the button's centre is on its right edge, the
    page's scroll calls on the toolbar are spied on, and the press is a click or a
    tap at the centre of the button's visible part (a `locator.click()` would
    scroll the button into view first).

    Args:
        page: A page of the setup at 320 by 568.
        test_id: The button.
        touch: Whether to tap (touch context) or click.

    Returns:
        The recorded scroll calls, the content hidden past the right edge and
        whether the edge fade is visible, 300 ms after the press.
    """
    page.evaluate(CENTRE_ON_RIGHT_EDGE_SCRIPT, test_id)
    page.wait_for_timeout(SETTLE_MS)
    part = page.evaluate(VISIBLE_PART_SCRIPT, test_id)
    assert part["width"] > 0, part
    assert part["height"] > 0, part
    page.evaluate(TOOLBAR_SCROLL_SPY_SCRIPT)
    if touch:
        page.touchscreen.tap(part["x"], part["y"])
    else:
        page.mouse.click(part["x"], part["y"])
    page.wait_for_timeout(AFTER_PRESS_MS)
    after = page.evaluate(AFTER_PRESS_SCRIPT)
    assert isinstance(after, dict)
    return after
