"""Tests of spec 021, AC-11: the flag button keeps the room's layout on every
window.

The setup is spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot with `you` host among
8 players, 100 feed items, (3, 1) tapped, help mode `free`) plus `p2`'s flag on
IDES, at the eight window sizes of spec 006 AC-5, in desktop and touch contexts.
One page per window size and context runs every check of the criterion: spec 013
AC-6's layout, the 24 by 24 px target, and spec 024 AC-8's toolbar checks with
`flag-button` among the toolbar's buttons (one row and the edge fade on the small
windows, the fade hidden on the others, the keyboard focus in the desktop context,
the hit at the centre after `scrollIntoView`). Every threshold comes from the spec,
none from what one machine's fonts show. The order of the toolbar is relative
(spec 024 AC-8), so it is checked in AC-6, at 1280 by 720.

The scripts that measure the toolbar are those of
`tests/test_spec_024_ac08_toolbar.py`, so that both specs measure the same way.
The shared setup is in `spec021_harness`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, FlagView, GridTarget, PlayerView, grid_view
from spec021_harness import IDES, open_flag_room
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    cell_at,
    expect_seq,
    grid_from_text,
    make_catalogue,
    open_context_page,
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
CONTEXTS = ["desktop", "touch"]
SIX_BUTTONS = [
    "undo-button",
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
]
FLAG_BUTTON = "flag-button"
TOOLBAR_BUTTONS = [*SIX_BUTTONS, FLAG_BUTTON]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
MIN_TARGET_PX = 24.0
EPSILON = 1.0
MAX_TABS = 60

# ---- Scripts (as in tests/test_spec_024_ac08_toolbar.py) ----

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
FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
FOCUS_SHARE_LINK_SCRIPT = """
() => document.querySelector('[data-testid="share-link"]').focus()
"""
# The focused button's box, the toolbar's client area, the outline (spec 035
# AC-2), how much of the outline's outer edge is cut ("Not clipped", with the
# toolbar always among the clipping ancestors) and whether the edge fade is
# visible.
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
    outline: readFocusOutline(),
    fadeVisible: fadeVisible,
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

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- The setup ----


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


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


def open_layout_room(
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
        flags = [FlagView(player_id="p2", clue=IDES)]
        view = grid_view(grid)
        mock = open_flag_room(
            page, live_server, view, flags=flags, players=eight_players()
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


# ---- The checks ----


def spec013_layout_problems(page: Page, touch: bool) -> list[str]:
    """How the page breaks spec 013 AC-6's checks."""
    viewport_box = page.get_by_test_id("grid-viewport").bounding_box()
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
    zoom = page.get_by_test_id("grid-viewport").get_attribute("data-zoom")

    problems: list[str] = []
    if viewport_box["height"] < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport {viewport_box['height']} px high")
    if scroll_width > window_width or scroll_height > window_height:
        problems.append(f"page scroll {sizes}")
    if zoom != "1":
        problems.append(f"zoom {zoom}")
    grid_inside = (
        grid_box["x"] >= viewport_box["x"] - EPSILON
        and grid_box["y"] >= viewport_box["y"] - EPSILON
        and grid_box["x"] + grid_box["width"]
        <= viewport_box["x"] + viewport_box["width"] + EPSILON
        and grid_box["y"] + grid_box["height"]
        <= viewport_box["y"] + viewport_box["height"] + EPSILON
    )
    if not grid_inside:
        problems.append(f"grid {grid_box} outside grid-viewport {viewport_box}")
    bar_bottom = bar_box["y"] + bar_box["height"]
    bar_inside = (
        bar_box["x"] >= -EPSILON
        and bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        and bar_box["y"] >= -EPSILON
        and bar_bottom <= window_height + EPSILON
    )
    if not bar_inside:
        problems.append(f"clue bar {bar_box} outside the window")
    if touch:
        keyboard_box = page.get_by_test_id("keyboard").bounding_box()
        assert keyboard_box is not None
        keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
        if bar_bottom > keyboard_box["y"] + EPSILON:
            problems.append(f"clue bar {bar_box} below keyboard {keyboard_box}")
        if keyboard_bottom > window_height + EPSILON:
            problems.append(f"keyboard {keyboard_box} outside the window")
    return problems


def rows_that_do_not_overlap(ranges: list[list[Any]]) -> list[tuple[str, str]]:
    """The pairs of buttons whose vertical ranges do not overlap.

    `ranges` comes from the page (id, top, bottom), hence `Any`.
    """
    apart: list[tuple[str, str]] = []
    for index, (first_id, first_top, first_bottom) in enumerate(ranges):
        for second_id, second_top, second_bottom in ranges[index + 1 :]:
            overlap_top = max(first_top, second_top)
            overlap_bottom = min(first_bottom, second_bottom)
            if overlap_top >= overlap_bottom:
                apart.append((str(first_id), str(second_id)))
    return apart


def one_row_problems(page: Page, test_ids: list[str]) -> list[str]:
    """How a small window breaks spec 024 AC-8's "One row" for these buttons."""
    row = page.evaluate(ROW_SCRIPT, test_ids)
    page.evaluate(SCROLL_TO_START_SCRIPT)
    page.wait_for_timeout(SETTLE_MS)
    fade_visible = page.evaluate(FADE_VISIBLE_SCRIPT)
    problems: list[str] = []
    apart = rows_that_do_not_overlap(row["ranges"])
    if apart != []:
        problems.append(f"buttons on different rows: {apart} {row['ranges']}")
    if row["scrollWidth"] > row["clientWidth"] + 1:
        if row["overflowX"] not in ("auto", "scroll"):
            problems.append(f"overflow-x {row['overflowX']!r}")
        if fade_visible is not True:
            problems.append("room-toolbar-more hidden while content is hidden")
    return problems


def keyboard_focus_problems(page: Page, test_id: str) -> list[str]:
    """Tab to a toolbar button from `share-link`; how its focus breaks AC-8's checks.

    Args:
        page: The room page, in the desktop context.
        test_id: The button's test id (`flag-button`).

    Returns:
        The problems found; none when the focus passes every check.
    """
    page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
    focused = None
    presses = 0
    while focused != test_id and presses < MAX_TABS:
        page.keyboard.press("Tab")
        presses += 1
        focused = page.evaluate(FOCUSED_TEST_ID_SCRIPT)
    if focused != test_id:
        return [f"{test_id} not focused in {MAX_TABS} presses of Tab"]
    page.wait_for_timeout(SETTLE_MS)
    reading = page.evaluate(FOCUS_IN_TOOLBAR_SCRIPT)
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
        problems.append(f"box {reading['box']} outside client area {reading['area']}")
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


def hit_problems(page: Page, test_id: str) -> list[str]:
    """Whether `elementFromPoint` finds a button once it is scrolled into view."""
    page.evaluate(SCROLL_INTO_VIEW_SCRIPT, test_id)
    page.wait_for_timeout(SETTLE_MS)
    result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
    if result["hits"] is not True:
        return [f"elementFromPoint at the centre found {result['hit']}"]
    return []


# ---- AC-11 ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac11_browser_the_flag_button_keeps_the_rooms_layout(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    small = (width, height) in SMALL_WINDOWS
    page, close = open_layout_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        button = page.get_by_test_id(FLAG_BUTTON)
        expect(button).to_have_count(1)
        assert spec013_layout_problems(page, touch) == []
        button_box = button.bounding_box()
        assert button_box is not None
        assert button_box["width"] >= MIN_TARGET_PX, button_box
        assert button_box["height"] >= MIN_TARGET_PX, button_box
        if small:
            assert one_row_problems(page, TOOLBAR_BUTTONS) == []
        else:
            assert page.evaluate(FADE_VISIBLE_SCRIPT) is False
        if not touch:
            assert keyboard_focus_problems(page, FLAG_BUTTON) == []
        assert hit_problems(page, FLAG_BUTTON) == []
    finally:
        close()
