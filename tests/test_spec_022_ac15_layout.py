"""Tests of spec 022, AC-15: the chat and reaction controls keep the room's layout
on every window.

The setup is spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot with `you` host among
8 players, 100 feed items, (3, 1) tapped, help mode `free`), then 100 chat lines
from `p2`, at the eight window sizes of spec 006 AC-5, in desktop and touch
contexts. One page per window size and context runs every check of the criterion,
in its order: "Collapsed", "Targets", "Open" (the panel, then the picker after a
tap on the clue cell (0, 3)), "Votes" and the place of `chat-input`. Every
threshold comes from the spec, none from what one machine's fonts show.

Spec 024 AC-8's toolbar checks are the ones the criterion names: one row on the
four small windows (with spec 024's edge fade while content is hidden), the
keyboard focus inside the toolbar's client area with its outline not clipped (in
the desktop context, as spec 024 runs it), and `elementFromPoint` at the centre
after `scrollIntoView`; they run for `chat-toggle` and `react-button`, the
buttons this spec adds. The scripts are those of
`tests/test_spec_021_ac11_layout.py`, so that the specs measure the same way.

In "Votes", the panel and the picker are opened with a dispatched `click` event:
the criterion checks that they leave the vote buttons uncovered, not where the
vote banner sits, so the test does not depend on whether the banner covers a
toolbar button.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from spec021_harness import IDES, select_word
from spec022_harness import (
    SETTLE_MS,
    chat_frame,
    expect_seq,
    open_chat_room,
    open_panel,
)
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    cell_at,
    grid_from_text,
    load_fr,
    open_context_page,
    player_view,
)
from spec025_harness import GRID_CHECK, MockRoomSocket, opened

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
NEW_BUTTONS = ["chat-toggle", "react-button"]
TOOLBAR_BUTTONS = ["chat-toggle", *SIX_BUTTONS, "flag-button", "react-button"]
# The toolbar controls of specs 018 to 024: none may come before `chat-toggle`.
EARLIER_CONTROLS = [
    "undo-button",
    "pencil-toggle",
    "confirm-pencil",
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
    "flag-button",
    "react-button",
    "authors-switch",
]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
CHAT_LINES = 100
LAST_FEED_SEQ = 5 + FEED_ITEMS
LAST_CHAT_SEQ = LAST_FEED_SEQ + CHAT_LINES
VOTE_SEQ = LAST_CHAT_SEQ + 1
MIN_GRID_VIEWPORT_PX = 100.0
MIN_TARGET_PX = 24.0
EPSILON = 1.0
MAX_TABS = 60

# ---- Scripts (as in tests/test_spec_021_ac11_layout.py) ----

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
# The focused button's box, the toolbar's client area, and how much of the
# outline's outer edge is cut (spec 035's "Not clipped", with the toolbar always
# among the clipping ancestors).
FOCUS_IN_TOOLBAR_SCRIPT = "() => {\n" + COLOUR_CONTRAST_JS + r"""
  const element = document.activeElement;
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
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
  if (button === null) {
    return {hits: false, hit: 'no element'};
  }
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

# ---- Scripts of this criterion ----

TOGGLE_ORDER_SCRIPT = r"""
testIds => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const toggle = document.querySelector('[data-testid="chat-toggle"]');
  const undo = document.querySelector('[data-testid="undo-button"]');
  if (toolbar === null || toggle === null) {
    return null;
  }
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const before = [];
  for (const id of testIds) {
    for (const element of document.querySelectorAll(`[data-testid="${id}"]`)) {
      if (!follows(toggle, element)) {
        before.push(id);
      }
    }
  }
  return {
    inToolbar: toolbar.contains(toggle),
    beforeUndo: undo !== null && follows(toggle, undo),
    controlsBefore: before,
  };
}
"""
UNREAD_IN_TOOLBAR_SCRIPT = r"""
() => {
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const unread = document.querySelector('[data-testid="chat-unread"]');
  if (unread === null) {
    return null;
  }
  const box = unread.getBoundingClientRect();
  const toolbarBox = toolbar.getBoundingClientRect();
  const left = toolbarBox.left + toolbar.clientLeft;
  const top = toolbarBox.top + toolbar.clientTop;
  return {
    scrollLeft: toolbar.scrollLeft,
    box: [box.left, box.top, box.right, box.bottom],
    area: [left, top, left + toolbar.clientWidth, top + toolbar.clientHeight],
  };
}
"""
PLACEMENT_SCRIPT = r"""
testId => {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  if (element === null) {
    return null;
  }
  const box = element.getBoundingClientRect();
  const root = document.documentElement;
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [innerWidth, innerHeight],
    insideToolbar: toolbar !== null && toolbar.contains(element),
    scroll: [root.scrollWidth, innerWidth, root.scrollHeight, innerHeight],
  };
}
"""
TARGET_SIZES_SCRIPT = r"""
testId => {
  const sizes = [];
  for (const element of document.querySelectorAll(`[data-testid="${testId}"]`)) {
    const box = element.getBoundingClientRect();
    sizes.push([box.width, box.height]);
  }
  return sizes;
}
"""
EXACT_HIT_SCRIPT = r"""
testId => {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  if (element === null) {
    return {hits: false, hit: 'no element'};
  }
  const box = element.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    hits: hit === element,
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""
INPUT_INSIDE_SCRIPT = r"""
() => {
  const input = document.querySelector('[data-testid="chat-input"]');
  const inside = [];
  for (const id of ['grid-viewport', 'clue-bar', 'keyboard', 'grid']) {
    if (input.closest(`[data-testid="${id}"]`) !== null) {
      inside.push(id);
    }
  }
  return inside;
}
"""


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- The setup ----


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
) -> tuple[Page, MockRoomSocket, Callable[[], None]]:
    """Open the room of the setup with 100 unread chat lines; page, mock, closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_chat_room(page, live_server, grid, players=eight_players())
        expect(page.get_by_test_id("room-toolbar")).to_be_visible()
        expect(page.get_by_test_id("reveal-panel")).to_be_visible()
        for seq in range(6, LAST_FEED_SEQ + 1):
            mock.send(check_frame(seq))
        expect_seq(page, LAST_FEED_SEQ)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap()
        else:
            cell.click()
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
        for seq in range(LAST_FEED_SEQ + 1, LAST_CHAT_SEQ + 1):
            mock.send(chat_frame(seq, "p2", f"Ligne {seq}"))
        expect_seq(page, LAST_CHAT_SEQ)
    except BaseException:
        close()
        raise
    return page, mock, close


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


def order_problems(page: Page) -> list[str]:
    """How `chat-toggle`'s place in the toolbar breaks "Collapsed"."""
    order = page.evaluate(TOGGLE_ORDER_SCRIPT, EARLIER_CONTROLS)
    if order is None:
        return ["no chat-toggle in a room-toolbar"]
    problems: list[str] = []
    if order["inToolbar"] is not True:
        problems.append("chat-toggle is outside room-toolbar")
    if order["beforeUndo"] is not True:
        problems.append("chat-toggle does not come before undo-button")
    if order["controlsBefore"] != []:
        problems.append(f"controls before chat-toggle: {order['controlsBefore']}")
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


def one_row_problems(page: Page) -> list[str]:
    """How a small window breaks spec 024 AC-8's "One row" for the buttons."""
    row = page.evaluate(ROW_SCRIPT, TOOLBAR_BUTTONS)
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


def box_inside(box: list[float], area: list[float]) -> bool:
    """Whether a box (left, top, right, bottom) lies in an area, 1 px tolerance."""
    left, top, right, bottom = box
    area_left, area_top, area_right, area_bottom = area
    return (
        left >= area_left - EPSILON
        and top >= area_top - EPSILON
        and right <= area_right + EPSILON
        and bottom <= area_bottom + EPSILON
    )


def unread_problems(page: Page) -> list[str]:
    """With the toolbar's scrollLeft at 0, `chat-unread` in its client area."""
    page.evaluate(SCROLL_TO_START_SCRIPT)
    page.wait_for_timeout(SETTLE_MS)
    reading = page.evaluate(UNREAD_IN_TOOLBAR_SCRIPT)
    if reading is None:
        return ["no chat-unread"]
    if not box_inside(reading["box"], reading["area"]):
        return [f"chat-unread {reading['box']} outside {reading['area']}"]
    return []


def keyboard_focus_problems(page: Page, test_id: str) -> list[str]:
    """Tab to a toolbar button from `share-link`; how its focus breaks AC-8."""
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
    if not box_inside(reading["box"], reading["area"]):
        problems.append(
            f"{test_id} box {reading['box']} outside client area {reading['area']}"
        )
    for side, pixels in reading["cut"].items():
        if round(pixels) != 0:
            problems.append(f"{test_id} outline cut by {pixels} px on the {side}")
    return problems


def hit_problems(page: Page, test_id: str) -> list[str]:
    """Whether `elementFromPoint` finds a button once it is scrolled into view."""
    page.evaluate(SCROLL_INTO_VIEW_SCRIPT, test_id)
    page.wait_for_timeout(SETTLE_MS)
    result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
    if result["hits"] is not True:
        return [f"{test_id}: elementFromPoint at the centre found {result['hit']}"]
    return []


def target_problems(page: Page, test_ids: list[str]) -> list[str]:
    """The elements of these test ids under 24 by 24 CSS px, or missing."""
    problems: list[str] = []
    for test_id in test_ids:
        sizes = page.evaluate(TARGET_SIZES_SCRIPT, test_id)
        if sizes == []:
            problems.append(f"no {test_id}")
        for width, height in sizes:
            if width < MIN_TARGET_PX or height < MIN_TARGET_PX:
                problems.append(f"{test_id} is {width} by {height} px")
    return problems


def layout_boxes(page: Page, touch: bool) -> dict[str, list[float]]:
    """The boxes of `grid-viewport`, `clue-bar` and, when touch, `keyboard`."""
    test_ids = ["grid-viewport", "clue-bar"]
    if touch:
        test_ids.append("keyboard")
    boxes: dict[str, list[float]] = {}
    for test_id in test_ids:
        box = page.get_by_test_id(test_id).bounding_box()
        assert box is not None, test_id
        boxes[test_id] = [box["x"], box["y"], box["width"], box["height"]]
    return boxes


def moved_boxes(
    before: dict[str, list[float]], after: dict[str, list[float]]
) -> list[str]:
    """The elements whose box changed by more than 1 px."""
    moved: list[str] = []
    for test_id, box in before.items():
        for old, new in zip(box, after[test_id], strict=True):
            if abs(old - new) > EPSILON:
                moved.append(f"{test_id} {box} -> {after[test_id]}")
                break
    return moved


def open_state_problems(
    page: Page,
    popover: str,
    opener: str,
    before: dict[str, list[float]],
    touch: bool,
) -> list[str]:
    """How an open panel or picker breaks "Open"."""
    placement = page.evaluate(PLACEMENT_SCRIPT, popover)
    if placement is None:
        return [f"no {popover}"]
    problems: list[str] = []
    width, height = placement["window"]
    if not box_inside(placement["box"], [0, 0, width, height]):
        problems.append(f"{popover} {placement['box']} outside the window")
    if placement["insideToolbar"] is not False:
        problems.append(f"{popover} is inside room-toolbar")
    scroll_width, window_width, scroll_height, window_height = placement["scroll"]
    if scroll_width > window_width or scroll_height > window_height:
        problems.append(f"page scroll {placement['scroll']} with {popover} open")
    hit = page.evaluate(HIT_AT_CENTRE_SCRIPT, opener)
    if hit["hits"] is not True:
        problems.append(f"{opener} covered by {hit['hit']} with {popover} open")
    for moved in moved_boxes(before, layout_boxes(page, touch)):
        problems.append(f"{popover} moved {moved}")
    return problems


def vote_problems(page: Page, popover: str) -> list[str]:
    """Whether `elementFromPoint` finds each vote button with `popover` open."""
    problems: list[str] = []
    for test_id in ("vote-yes", "vote-no"):
        result = page.evaluate(EXACT_HIT_SCRIPT, test_id)
        if result["hits"] is not True:
            problems.append(f"{test_id} covered by {result['hit']} with {popover}")
    return problems


def press(page: Page, test_id: str, touch: bool) -> None:
    """Click, or in a touch context tap, the element of a test id."""
    element = page.get_by_test_id(test_id)
    if touch:
        element.tap()
    else:
        element.click()


# ---- AC-15 ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac15_browser_the_chat_and_reaction_controls_keep_the_rooms_layout(
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
    problems: dict[str, list[str]] = {}
    page, mock, close = open_layout_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        panel = page.get_by_test_id("chat-panel")
        picker = page.get_by_test_id("reaction-picker")

        # Collapsed.
        expect(page.get_by_test_id("chat-unread")).to_have_text(
            load_fr()["chat.unread_many"]
        )
        collapsed = spec013_layout_problems(page, touch) + order_problems(page)
        if small:
            collapsed += one_row_problems(page) + unread_problems(page)
        if not touch:
            for test_id in NEW_BUTTONS:
                collapsed += keyboard_focus_problems(page, test_id)
        for test_id in NEW_BUTTONS:
            collapsed += hit_problems(page, test_id)
        problems["collapsed"] = collapsed
        targets = target_problems(page, NEW_BUTTONS)

        # Open: the panel, with a non-empty input.
        page.evaluate(SCROLL_TO_START_SCRIPT)
        page.wait_for_timeout(SETTLE_MS)
        before = layout_boxes(page, touch)
        open_panel(page, touch)
        page.get_by_test_id("chat-input").fill("Bonjour")
        page.wait_for_timeout(SETTLE_MS)
        problems["panel"] = open_state_problems(
            page, "chat-panel", "chat-toggle", before, touch
        )
        targets += target_problems(page, ["mute-player", "chat-send"])
        input_inside = page.evaluate(INPUT_INSIDE_SCRIPT)
        page.keyboard.press("Escape")
        expect(panel).to_have_count(0)

        # Open: the picker, after a tap on the clue cell (0, 3).
        select_word(page, IDES, touch)
        before = layout_boxes(page, touch)
        press(page, "react-button", touch)
        expect(picker).to_be_visible()
        page.wait_for_timeout(SETTLE_MS)
        problems["picker"] = open_state_problems(
            page, "reaction-picker", "react-button", before, touch
        )
        targets += target_problems(page, ["reaction-option"])
        problems["targets"] = targets
        page.keyboard.press("Escape")
        expect(picker).to_have_count(0)

        # Votes: the banner of a grid check by `p2`, then the panel, then the picker.
        mock.send(opened(VOTE_SEQ, 1, "p2", GRID_CHECK, 8).model_dump_json())
        expect(page.get_by_test_id("vote-yes")).to_be_visible()
        expect(page.get_by_test_id("vote-no")).to_be_visible()
        page.get_by_test_id("chat-toggle").dispatch_event("click")
        expect(panel).to_be_visible()
        page.wait_for_timeout(SETTLE_MS)
        votes = vote_problems(page, "chat-panel")
        page.get_by_test_id("chat-toggle").dispatch_event("click")
        expect(panel).to_have_count(0)
        page.get_by_test_id("react-button").dispatch_event("click")
        expect(picker).to_be_visible()
        page.wait_for_timeout(SETTLE_MS)
        votes += vote_problems(page, "reaction-picker")
        problems["votes"] = votes
    finally:
        close()

    assert problems == {
        "collapsed": [],
        "panel": [],
        "picker": [],
        "targets": [],
        "votes": [],
    }
    assert input_inside == []
