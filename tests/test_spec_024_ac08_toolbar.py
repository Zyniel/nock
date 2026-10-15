"""Tests of spec 024, AC-8: the room toolbar keeps the grid's room on small
windows, and every control in it can be reached.

The setup is spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items,
(3, 1) tapped) with help mode `free` and the budget 5 letters and 1 word, at the
eight window sizes of spec 006 AC-5, in desktop and touch contexts. The layout
checks are spec 013 AC-6's; the outline checks are spec 035 AC-2's. Every
threshold comes from the spec, none from what one machine's fonts show. The shared
setup is in `spec024_harness`.

The order is relative (the lead's note of 2026-10-15): the test checks the order of
the six buttons, not the toolbar's exact children. The edge case "Tab order" (the
toolbar before the roster, the feed, the host panel and the grid) is checked with
the order.

Reading of "the room header": the `header` element that holds `share-panel`
("inside the room header after share-panel").

"Pointer focus" (the lead's refinement of 2026-10-15) is tested as spec 035 tests
the host panel: the test spies on the page's scroll calls on the toolbar instead
of comparing `scrollLeft`, since a scroll that the browser makes by itself is
allowed (spec 035 decision 13).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    cell_at,
    expect_seq,
    grid_from_text,
    make_catalogue,
    open_context_page,
    open_room,
    outline_problems,
    player_view,
)

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
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 1.0
MAX_TABS = 60


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- The setup of spec 013 AC-6 ----


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        players.append(player_view(f"p{number}", nickname, number - 1))
    return players


def check_frame(seq: int) -> str:
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
    """Open the room of the setup with (3, 1) tapped; return the page, its closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_room(page, live_server, grid, players=eight_players())
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


# ---- Layout ----


def assert_spec013_layout(page: Page, touch: bool) -> None:
    """Spec 013 AC-6's checks (as in tests/test_spec_013_ac06_layout.py)."""
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

    assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX, viewport_box
    assert scroll_width <= window_width
    assert scroll_height <= window_height
    expect(viewport).to_have_attribute("data-zoom", "1")
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


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_spec_013_layout_holds_with_the_toolbar_and_the_reveal_panel(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        expect(page.get_by_test_id("room-toolbar")).to_be_visible()
        expect(page.get_by_test_id("reveal-panel")).to_be_visible()
        assert_spec013_layout(page, touch)
    finally:
        close()


# ---- Order ----

ORDER_SCRIPT = """
testIds => {
  const byTestId = (id) => document.querySelectorAll(`[data-testid="${id}"]`);
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const share = document.querySelector('[data-testid="share-panel"]');
  const header = toolbar.closest('header');
  const counts = {};
  const outside = [];
  for (const id of testIds) {
    const found = byTestId(id);
    counts[id] = found.length;
    if (found.length === 1 && !toolbar.contains(found[0])) {
      outside.push(id);
    }
  }
  const outOfOrder = [];
  for (let index = 0; index + 1 < testIds.length; index += 1) {
    const first = byTestId(testIds[index])[0];
    const second = byTestId(testIds[index + 1])[0];
    if (first && second && !follows(first, second)) {
      outOfOrder.push([testIds[index], testIds[index + 1]]);
    }
  }
  const revealButtons = [];
  for (const button of toolbar.querySelectorAll('button[data-testid^="reveal-"]')) {
    revealButtons.push(button.getAttribute('data-testid'));
  }
  const notAfterToolbar = [];
  for (const id of ['roster', 'activity-feed', 'host-panel', 'grid']) {
    const element = document.querySelector(`[data-testid="${id}"]`);
    if (element === null || !follows(toolbar, element)) {
      notAfterToolbar.push(id);
    }
  }
  return {
    inHeader: header !== null && share !== null && header.contains(share),
    shareBefore: share !== null && follows(share, toolbar),
    counts: counts,
    outside: outside,
    outOfOrder: outOfOrder,
    revealButtons: revealButtons,
    notAfterToolbar: notAfterToolbar,
  };
}
"""


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_the_toolbar_holds_the_six_buttons_in_relative_order(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        order = page.evaluate(ORDER_SCRIPT, SIX_BUTTONS)
    finally:
        close()

    assert order["inHeader"] is True, order
    assert order["shareBefore"] is True, order
    assert order["counts"] == dict.fromkeys(SIX_BUTTONS, 1), order
    assert order["outside"] == [], order
    assert order["outOfOrder"] == [], order
    assert order["revealButtons"] == ["reveal-letter", "reveal-word"], order
    assert order["notAfterToolbar"] == [], order


# ---- One row on small windows, and the edge fade ----

ROW_SCRIPT = """
testIds => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const ranges = [];
  for (const id of testIds) {
    const box = document.querySelector(`[data-testid="${id}"]`).getBoundingClientRect();
    ranges.push([id, box.top, box.bottom]);
  }
  return {
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


def rows_that_do_not_overlap(ranges: list[list[object]]) -> list[tuple[str, str]]:
    """The pairs of buttons whose vertical ranges do not overlap."""
    apart: list[tuple[str, str]] = []
    for index, (first_id, first_top, first_bottom) in enumerate(ranges):
        for second_id, second_top, second_bottom in ranges[index + 1 :]:
            assert isinstance(first_top, int | float)
            assert isinstance(first_bottom, int | float)
            assert isinstance(second_top, int | float)
            assert isinstance(second_bottom, int | float)
            overlap_top = max(first_top, second_top)
            overlap_bottom = min(first_bottom, second_bottom)
            if overlap_top >= overlap_bottom:
                apart.append((str(first_id), str(second_id)))
    return apart


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac8_on_a_small_window_the_toolbar_is_one_row_that_scrolls(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        row = page.evaluate(ROW_SCRIPT, SIX_BUTTONS)
        page.evaluate(SCROLL_TO_START_SCRIPT)
        page.wait_for_timeout(SETTLE_MS)
        fade_visible = page.evaluate(FADE_VISIBLE_SCRIPT)
    finally:
        close()

    assert rows_that_do_not_overlap(row["ranges"]) == [], row
    if row["scrollWidth"] > row["clientWidth"] + 1:
        assert row["overflowX"] in ("auto", "scroll"), row
        assert fade_visible is True, row


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), LARGE_WINDOWS, ids=size_ids(LARGE_WINDOWS)
)
def test_ac8_on_a_larger_window_the_edge_fade_is_not_visible(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        expect(page.get_by_test_id("room-toolbar")).to_be_visible()
        fade_visible = page.evaluate(FADE_VISIBLE_SCRIPT)
    finally:
        close()

    assert fade_visible is False


# ---- Keyboard (desktop context) ----

FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
FOCUS_SHARE_LINK_SCRIPT = """
() => document.querySelector('[data-testid="share-link"]').focus()
"""
# The focused button's box, the toolbar's client area, the outline (spec 035
# AC-2), how much of the outline's outer edge is cut ("Not clipped" of spec 035's
# "Focus outline of the feed's scrolling list", with the toolbar always among the
# clipping ancestors) and whether the edge fade is visible.
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


def keyboard_focus_problems(reading: dict[str, object]) -> list[str]:
    """How a button with the keyboard focus breaks AC-8's keyboard checks."""
    problems: list[str] = []
    box = reading["box"]
    area = reading["area"]
    assert isinstance(box, list)
    assert isinstance(area, list)
    left, top, right, bottom = box
    area_left, area_top, area_right, area_bottom = area
    inside = (
        left >= area_left - EPSILON
        and top >= area_top - EPSILON
        and right <= area_right + EPSILON
        and bottom <= area_bottom + EPSILON
    )
    if not inside:
        problems.append(f"box {box} outside the toolbar's client area {area}")
    outline = reading["outline"]
    assert isinstance(outline, dict)
    problems.extend(
        outline_problems(outline["style"], outline["width"], outline["ratio"])
    )
    cut = reading["cut"]
    assert isinstance(cut, dict)
    for side, pixels in cut.items():
        if round(pixels) != 0:
            problems.append(f"outline cut by {pixels} px on the {side}")
    if reading["fadeVisible"] is not False:
        problems.append("room-toolbar-more is visible")
    return problems


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_a_keyboard_focus_keeps_each_button_and_its_outline_in_the_toolbar(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch=False
    )
    readings: dict[str, dict[str, object]] = {}
    try:
        page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
        for _ in range(MAX_TABS):
            if len(readings) == len(SIX_BUTTONS):
                break
            page.keyboard.press("Tab")
            focused = page.evaluate(FOCUSED_TEST_ID_SCRIPT)
            if focused in SIX_BUTTONS and focused not in readings:
                page.wait_for_timeout(SETTLE_MS)
                reading = page.evaluate(FOCUS_IN_TOOLBAR_SCRIPT)
                assert reading["testId"] == focused, reading
                readings[focused] = reading
    finally:
        close()

    missing = [test_id for test_id in SIX_BUTTONS if test_id not in readings]
    assert missing == [], f"not focused in {MAX_TABS} presses of Tab: {missing}"
    for test_id, reading in readings.items():
        assert keyboard_focus_problems(reading) == [], (test_id, reading)


# ---- Pointer ----

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


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_each_button_is_hit_at_its_centre_once_scrolled_into_view(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    misses: list[tuple[str, object]] = []
    try:
        for test_id in SIX_BUTTONS:
            page.evaluate(SCROLL_INTO_VIEW_SCRIPT, test_id)
            page.wait_for_timeout(SETTLE_MS)
            result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
            if result["hits"] is not True:
                misses.append((test_id, result["hit"]))
    finally:
        close()

    assert misses == []


# ---- Pointer focus (320 by 568, click and tap) ----

POINTER_FOCUS_SIZE = (320, 568)
AFTER_PRESS_MS = 300

# Sets the toolbar's `scrollLeft` so that the button's centre is on the toolbar's
# right edge, clamped to the toolbar's scroll range.
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

# Records in `window.toolbarScrollCalls` each scroll call that the page makes on
# `room-toolbar` or on an element inside it: `scrollIntoView`,
# `scrollIntoViewIfNeeded` (where the engine has it), `scroll`, `scrollTo` and
# `scrollBy` of `Element.prototype`, and its `scrollLeft` setter. A scroll that
# the browser makes by itself does not go through them.
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

# The centre of the button's visible part: its box cut to the toolbar's client
# area, with the size of that part.
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

# After the press: the recorded calls, how much toolbar content is hidden past
# the right edge, and whether the edge fade is visible.
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


@pytest.mark.parametrize("test_id", SIX_BUTTONS)
@pytest.mark.parametrize("context_kind", CONTEXTS)
def test_ac8_a_pointer_focus_keeps_the_fade_and_makes_no_scroll_call(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
    test_id: str,
) -> None:
    touch = context_kind == "touch"
    width, height = POINTER_FOCUS_SIZE
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        page.evaluate(CENTRE_ON_RIGHT_EDGE_SCRIPT, test_id)
        page.wait_for_timeout(SETTLE_MS)
        part = page.evaluate(VISIBLE_PART_SCRIPT, test_id)
        assert part["width"] > 0, part
        assert part["height"] > 0, part
        # The spy goes in after the set-up scroll above, which it must not record.
        page.evaluate(TOOLBAR_SCROLL_SPY_SCRIPT)
        # Raw coordinates: `locator.click()` would scroll the button into view.
        if touch:
            page.touchscreen.tap(part["x"], part["y"])
        else:
            page.mouse.click(part["x"], part["y"])
        page.wait_for_timeout(AFTER_PRESS_MS)
        after = page.evaluate(AFTER_PRESS_SCRIPT)
    finally:
        close()

    assert after["calls"] == [], after
    if after["hiddenPastRight"] > 1:
        assert after["fadeVisible"] is True, after
