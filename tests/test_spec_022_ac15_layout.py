"""Tests of spec 022, AC-15: the chat and reaction controls keep the room's layout
on every window.

The setup is spec 043's `H8` (spec 013 AC-6's FX-01 snapshot with `you` host among
8 players, 100 feed items, (3, 1) tapped, help mode `free`), at the eight window
sizes of spec 006 AC-5, in desktop and touch contexts. One page per window size
and context runs every check of the criterion, in its order: "Collapsed" (the
Salon closed and 100 unread lines), "Targets", "Open" (the Salon on Discussion
with a non-empty `chat-input`; the picker after a tap on the clue cell (0, 3);
in the column layout both), "Votes" and the place of `chat-input`. Every
threshold comes from the spec, none from what one machine's fonts show.

Refined by spec 043 (the design's room layout): `chat-toggle` is in `room-topbar`
with its badge, `react-button` in `clue-bar`, and the Salon replaces the floating
chat panel; spec 024 AC-8's toolbar checks went with the toolbar. In the sheet
layout the picker and the Salon are never open together (one at a time), so the
"both open" state runs in the column layout only. In "Votes", `react-button` is
disabled while the banner shows, and a picker open before `vote_opened` closes
within 300 ms of it (spec 043's Decision 10).

Choices where the spec leaves room:

- "Opening the Salon changes no box of `room-topbar`": the boxes of `room-topbar`
  and of each of its test-id'd elements that show, 1 px each.
- In the second "Open" state the Salon is closed first, so that the picker is
  measured on its own.
- Sizes have spec 043's tolerance of 0.5 px.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from room_panels import show_tab
from spec021_harness import IDES, select_word
from spec022_harness import (
    SETTLE_MS,
    chat_frame,
    expect_seq,
    open_chat_room,
    open_panel,
)
from spec024_harness import (
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
CONTEXTS = ["desktop", "touch"]
NEW_BUTTONS = ["chat-toggle", "react-button"]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
CHAT_LINES = 100
LAST_FEED_SEQ = 5 + FEED_ITEMS
LAST_CHAT_SEQ = LAST_FEED_SEQ + CHAT_LINES
VOTE_SEQ = LAST_CHAT_SEQ + 1
# Spec 043's 3-second note for `p2`'s last line covers the top row while it shows
# (a tap on it opens the Salon); it leaves the page 3,350 ms after it showed.
NOTE_GONE_TIMEOUT_MS = 5000
MIN_GRID_VIEWPORT_PX = 100.0
MIN_TARGET_PX = 24.0
SIZE_TOLERANCE_PX = 0.5
EPSILON = 1.0
PICKER_CLOSE_MS = 300

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
# Where `chat-toggle` and its badge are: inside `room-topbar`, the badge's box
# against the top bar's; and whether `react-button` is inside `clue-bar`.
COLLAPSED_PLACE_SCRIPT = r"""
() => {
  const byId = (id) => document.querySelector(`[data-testid="${id}"]`);
  const bar = byId('room-topbar');
  const toggle = byId('chat-toggle');
  const unread = byId('chat-unread');
  const clueBar = byId('clue-bar');
  const react = byId('react-button');
  const boxOf = (element) => {
    const box = element.getBoundingClientRect();
    return [box.left, box.top, box.right, box.bottom];
  };
  return {
    toggleInTopBar: bar !== null && toggle !== null && bar.contains(toggle),
    unread: unread === null ? null : boxOf(unread),
    topBar: bar === null ? null : boxOf(bar),
    reactInClueBar: clueBar !== null && react !== null && clueBar.contains(react),
  };
}
"""
PLACEMENT_SCRIPT = r"""
testId => {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  if (element === null) {
    return null;
  }
  const box = element.getBoundingClientRect();
  const root = document.documentElement;
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [innerWidth, innerHeight],
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
# The boxes of `room-topbar` and of its test-id'd elements that show.
TOP_BAR_BOXES_SCRIPT = r"""
() => {
  const bar = document.querySelector('[data-testid="room-topbar"]');
  const boxes = {};
  for (const element of [bar, ...bar.querySelectorAll('[data-testid]')]) {
    if (element.getClientRects().length === 0) {
      continue;
    }
    const box = element.getBoundingClientRect();
    boxes[element.getAttribute('data-testid')] = [box.x, box.y, box.width,
      box.height];
  }
  return boxes;
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


def press(page: Page, test_id: str, touch: bool) -> None:
    """Click, or in a touch context tap, the element of a test id."""
    element = page.get_by_test_id(test_id)
    if touch:
        element.tap()
    else:
        element.click()


def close_salon(page: Page, touch: bool) -> None:
    """Close the Salon when it is open (the column layout opens it at load)."""
    salon = page.get_by_test_id("salon")
    if salon.get_attribute("hidden") is None:
        press(page, "chat-toggle", touch)
    expect(salon).to_be_hidden()


def open_layout_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
    touch: bool,
) -> tuple[Page, MockRoomSocket, Callable[[], None]]:
    """`H8` with the Salon closed and 100 unread lines; page, mock, closer."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        mock = open_chat_room(page, live_server, grid, players=eight_players())
        for seq in range(6, LAST_FEED_SEQ + 1):
            mock.send(check_frame(seq))
        expect_seq(page, LAST_FEED_SEQ)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap()
        else:
            cell.click()
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
        close_salon(page, touch)
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


def hit_problems(page: Page, test_id: str) -> list[str]:
    """Whether `elementFromPoint` at the element's centre finds it."""
    result = page.evaluate(HIT_AT_CENTRE_SCRIPT, test_id)
    if result["hits"] is not True:
        return [f"{test_id}: elementFromPoint at the centre found {result['hit']}"]
    return []


def collapsed_problems(page: Page) -> list[str]:
    """`chat-toggle` and its badge in the top bar, `react-button` in the clue bar."""
    place = page.evaluate(COLLAPSED_PLACE_SCRIPT)
    problems: list[str] = []
    if place["toggleInTopBar"] is not True:
        problems.append("chat-toggle is not in room-topbar")
    if place["unread"] is None or place["topBar"] is None:
        problems.append("no chat-unread or no room-topbar")
    elif not box_inside(place["unread"], place["topBar"]):
        problems.append(f"chat-unread {place['unread']} outside {place['topBar']}")
    if place["reactInClueBar"] is not True:
        problems.append("react-button is not in clue-bar")
    for test_id in NEW_BUTTONS:
        problems += hit_problems(page, test_id)
    return problems


def target_problems(page: Page, test_ids: list[str]) -> list[str]:
    """The elements of these test ids under 24 by 24 CSS px, or missing."""
    problems: list[str] = []
    for test_id in test_ids:
        sizes = page.evaluate(TARGET_SIZES_SCRIPT, test_id)
        if sizes == []:
            problems.append(f"no {test_id}")
        for width, height in sizes:
            too_small = (
                width < MIN_TARGET_PX - SIZE_TOLERANCE_PX
                or height < MIN_TARGET_PX - SIZE_TOLERANCE_PX
            )
            if too_small:
                problems.append(f"{test_id} is {width} by {height} px")
    return problems


def boxes_of(page: Page, test_ids: list[str]) -> dict[str, list[float]]:
    """The boxes (x, y, width, height) of the elements of these test ids."""
    boxes: dict[str, list[float]] = {}
    for test_id in test_ids:
        box = page.get_by_test_id(test_id).bounding_box()
        assert box is not None, test_id
        boxes[test_id] = [box["x"], box["y"], box["width"], box["height"]]
    return boxes


def layout_boxes(page: Page, touch: bool) -> dict[str, list[float]]:
    """The boxes of `grid-viewport`, `clue-bar` and, when touch, `keyboard`."""
    test_ids = ["grid-viewport", "clue-bar"]
    if touch:
        test_ids.append("keyboard")
    return boxes_of(page, test_ids)


def moved_boxes(
    before: dict[str, list[float]], after: dict[str, list[float]]
) -> list[str]:
    """The elements whose box changed by more than 1 px, or went away."""
    moved: list[str] = []
    for test_id, box in before.items():
        if test_id not in after:
            moved.append(f"{test_id} is gone")
            continue
        for old, new in zip(box, after[test_id], strict=True):
            if abs(old - new) > EPSILON:
                moved.append(f"{test_id} {box} -> {after[test_id]}")
                break
    return moved


def top_bar_boxes(page: Page) -> dict[str, list[float]]:
    found = page.evaluate(TOP_BAR_BOXES_SCRIPT)
    assert isinstance(found, dict), found
    return found


def placement_problems(page: Page, test_id: str) -> list[str]:
    """The Salon or the picker inside the window, and no page scroll."""
    placement = page.evaluate(PLACEMENT_SCRIPT, test_id)
    if placement is None:
        return [f"no {test_id}"]
    problems: list[str] = []
    width, height = placement["window"]
    if not box_inside(placement["box"], [0, 0, width, height]):
        problems.append(f"{test_id} {placement['box']} outside the window")
    scroll_width, window_width, scroll_height, window_height = placement["scroll"]
    if scroll_width > window_width or scroll_height > window_height:
        problems.append(f"page scroll {placement['scroll']} with {test_id} open")
    return problems


def is_sheet(page: Page) -> bool:
    return page.get_by_test_id("room-page").get_attribute("data-layout") == "sheet"


def overlap_problems(page: Page) -> list[str]:
    """Whether `salon` and `reaction-picker` overlap by more than 1 px each way."""
    boxes = boxes_of(page, ["salon", "reaction-picker"])
    salon_x, salon_y, salon_width, salon_height = boxes["salon"]
    picker_x, picker_y, picker_width, picker_height = boxes["reaction-picker"]
    left = max(salon_x, picker_x)
    right = min(salon_x + salon_width, picker_x + picker_width)
    top = max(salon_y, picker_y)
    bottom = min(salon_y + salon_height, picker_y + picker_height)
    if right - left <= EPSILON or bottom - top <= EPSILON:
        return []
    return [f"salon and reaction-picker overlap: {boxes}"]


def vote_problems(page: Page) -> list[str]:
    """Whether `elementFromPoint` finds each vote button."""
    problems: list[str] = []
    for test_id in ("vote-yes", "vote-no"):
        result = page.evaluate(EXACT_HIT_SCRIPT, test_id)
        if result["hits"] is not True:
            problems.append(f"{test_id} covered by {result['hit']}")
    return problems


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
    problems: dict[str, list[str]] = {}
    page, mock, close = open_layout_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        salon = page.get_by_test_id("salon")
        picker = page.get_by_test_id("reaction-picker")
        sheet = is_sheet(page)

        # Collapsed.
        expect(page.get_by_test_id("chat-unread")).to_have_text(
            load_fr()["chat.unread_many"]
        )
        problems["collapsed"] = spec013_layout_problems(page, touch)
        problems["collapsed"] += collapsed_problems(page)
        targets = target_problems(page, NEW_BUTTONS)

        # Open: the Salon on Discussion, with a non-empty input.
        before = layout_boxes(page, touch)
        bar_before = top_bar_boxes(page)
        open_panel(page, touch)
        page.get_by_test_id("chat-input").fill("Bonjour")
        page.wait_for_timeout(SETTLE_MS)
        salon_open = placement_problems(page, "salon")
        salon_open += hit_problems(page, "chat-toggle")
        if sheet:
            salon_open += moved_boxes(before, layout_boxes(page, touch))
        else:
            # Showing the stream reads the messages (spec 043 AC-17): the badge
            # goes, and the rest of the top bar stays put.
            bar_after = top_bar_boxes(page)
            if "chat-unread" in bar_after:
                salon_open.append("chat-unread still shows with the stream shown")
            bar_before.pop("chat-unread", None)
            salon_open += moved_boxes(bar_before, bar_after)
        problems["salon"] = salon_open
        targets += target_problems(page, ["chat-send"])
        input_inside = page.evaluate(INPUT_INSIDE_SCRIPT)
        show_tab(page, "players")
        targets += target_problems(page, ["mute-player"])
        show_tab(page, "discussion")
        close_salon(page, touch)

        # Open: the picker, after a tap on the clue cell (0, 3).
        expect(page.get_by_test_id("room-note")).to_have_count(
            0, timeout=NOTE_GONE_TIMEOUT_MS
        )
        select_word(page, IDES, touch)
        before = layout_boxes(page, touch)
        press(page, "react-button", touch)
        expect(picker).to_be_visible()
        page.wait_for_timeout(SETTLE_MS)
        picker_open = placement_problems(page, "reaction-picker")
        picker_open += hit_problems(page, "react-button")
        picker_open += moved_boxes(before, layout_boxes(page, touch))
        problems["picker"] = picker_open
        targets += target_problems(page, ["reaction-option"])
        problems["targets"] = targets
        page.keyboard.press("Escape")
        expect(picker).to_have_count(0)

        # Open: both, in the column layout only.
        both: list[str] = []
        if not sheet:
            before = layout_boxes(page, touch)
            open_panel(page, touch)
            page.get_by_test_id("chat-input").fill("Bonjour")
            page.wait_for_timeout(SETTLE_MS)
            salon_before = boxes_of(page, ["salon"])
            press(page, "react-button", touch)
            expect(picker).to_be_visible()
            expect(salon).to_be_visible()
            page.wait_for_timeout(SETTLE_MS)
            both += placement_problems(page, "salon")
            both += placement_problems(page, "reaction-picker")
            for test_id in NEW_BUTTONS:
                both += hit_problems(page, test_id)
            both += overlap_problems(page)
            both += moved_boxes(salon_before, boxes_of(page, ["salon"]))
            page.keyboard.press("Escape")
            expect(picker).to_have_count(0)
        problems["both"] = both

        # Votes: a picker open before the banner closes; then the Salon is
        # opened on Discussion with the banner showing.
        close_salon(page, touch)
        press(page, "react-button", touch)
        expect(picker).to_be_visible()
        mock.send(opened(VOTE_SEQ, 1, "p2", GRID_CHECK, 8).model_dump_json())
        expect(picker).to_have_count(0, timeout=PICKER_CLOSE_MS)
        expect(page.get_by_test_id("vote-yes")).to_be_visible()
        expect(page.get_by_test_id("vote-no")).to_be_visible()
        expect(page.get_by_test_id("react-button")).to_be_disabled()
        page.get_by_test_id("chat-toggle").dispatch_event("click")
        expect(page.get_by_test_id("chat-panel")).to_be_visible()
        page.wait_for_timeout(SETTLE_MS)
        problems["votes"] = vote_problems(page)
    finally:
        close()

    assert problems == {
        "collapsed": [],
        "salon": [],
        "picker": [],
        "targets": [],
        "both": [],
        "votes": [],
    }
    assert input_inside == []
