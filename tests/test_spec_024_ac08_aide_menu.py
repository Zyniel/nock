"""Tests of spec 024, AC-8: the Aide menu keeps the grid's room on small windows,
and every item in it can be reached.

The setup is spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items,
(3, 1) tapped) with help mode `free` and the budget 5 letters and 1 word, at the
eight window sizes of spec 006 AC-5, in desktop and touch contexts, with
`aide-menu` open (spec 043's `open_aide`). The layout checks are spec 013 AC-6's;
the outline checks are spec 035 AC-2's. Every threshold comes from the spec, none
from what one machine's fonts show. The shared setup is in `spec024_harness`.

Refined by spec 043 (the design's room layout): this criterion read "The room
toolbar keeps the grid's room on small windows, and every control in it can be
reached", with spec 024's toolbar checks (order, one row, the fade, the pointer
focus); the reveal and check items now live in the Aide menu, whose checks replace
them. The file was `test_spec_024_ac08_toolbar.py`.

Choices where the spec leaves room:

- "Inside `aide-menu`'s client area" is the menu's box less its borders and its
  scrollbars (`clientLeft`, `clientTop`, `clientWidth`, `clientHeight`).
- The keyboard walk starts on the item that takes the focus when the menu opens
  (its first enabled item, spec 043 AC-12), then presses `Tab` until each of the
  five has had the focus (at most 20 presses).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from room_panels import open_aide
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    WAIT_TIMEOUT_MS,
    cell_at,
    expect_seq,
    grid_from_text,
    make_catalogue,
    make_walker,
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
CONTEXTS = ["desktop", "touch"]
FIVE_ITEMS = [
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
MAX_MENU_TABS = 20

# The menu's box, the document order of the five items, and every button whose
# test id starts with `reveal-`.
MENU_SCRIPT = r"""
ids => {
  const menu = document.querySelector('[data-testid="aide-menu"]');
  const box = menu.getBoundingClientRect();
  const order = [];
  for (const element of menu.querySelectorAll('[data-testid]')) {
    const testId = element.getAttribute('data-testid');
    if (ids.includes(testId)) {
      order.push(testId);
    }
  }
  const reveals = [];
  for (const button of menu.querySelectorAll('button')) {
    const testId = button.getAttribute('data-testid') || '';
    if (testId.startsWith('reveal-')) {
      reveals.push(testId);
    }
  }
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [0, 0, innerWidth, innerHeight],
    order: order,
    reveals: reveals,
  };
}
"""
ITEM_HIT_SCRIPT = r"""
testId => {
  const item = document.querySelector(`[data-testid="${testId}"]`);
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
# The focused item's box against `aide-menu`'s client area, spec 035's "Not
# clipped" measure with `aide-menu` among the clipping ancestors, and the outline.
FOCUS_IN_MENU_SCRIPT = "() => {\n" + COLOUR_CONTRAST_JS + r"""
  const element = document.activeElement;
  const menu = document.querySelector('[data-testid="aide-menu"]');
  const box = element.getBoundingClientRect();
  const menuBox = menu.getBoundingClientRect();
  const area = [
    menuBox.left + menu.clientLeft, menuBox.top + menu.clientTop,
    menuBox.left + menu.clientLeft + menu.clientWidth,
    menuBox.top + menu.clientTop + menu.clientHeight,
  ];
  const style = getComputedStyle(element);
  const grow = parseFloat(style.outlineOffset) + parseFloat(style.outlineWidth);
  const outer = {
    left: box.left - grow, top: box.top - grow,
    right: box.right + grow, bottom: box.bottom + grow,
  };
  const clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  for (let node = element.parentElement; node; node = node.parentElement) {
    const nodeStyle = getComputedStyle(node);
    const clips = nodeStyle.overflowX !== 'visible'
      || nodeStyle.overflowY !== 'visible';
    if (!clips && node !== menu) {
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
    area: area,
    cut: {
      top: Math.max(clip.top - outer.top, 0),
      right: Math.max(outer.right - clip.right, 0),
      bottom: Math.max(outer.bottom - clip.bottom, 0),
      left: Math.max(clip.left - outer.left, 0),
    },
    outline: readFocusOutline(),
  };
}
"""


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


def open_setup_room(
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
        last_seq = 5 + FEED_ITEMS
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq))
        expect_seq(page, last_seq)
        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=WAIT_TIMEOUT_MS)
        else:
            cell.click(timeout=WAIT_TIMEOUT_MS)
        expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
    except BaseException:
        close()
        raise
    return page, close


# ---- Checks ----


def inside(box: list[float], area: list[float]) -> bool:
    return (
        box[0] >= area[0] - EPSILON
        and box[1] >= area[1] - EPSILON
        and box[2] <= area[2] + EPSILON
        and box[3] <= area[3] + EPSILON
    )


def spec013_layout_problems(page: Page, touch: bool) -> list[str]:
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
    problems: list[str] = []
    if viewport_box["height"] < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport {viewport_box['height']} px high")
    if scroll_width > window_width or scroll_height > window_height:
        problems.append(f"page scroll {sizes}")
    if viewport.get_attribute("data-zoom") != "1":
        problems.append(f"zoom {viewport.get_attribute('data-zoom')}")
    grid_area = [
        viewport_box["x"],
        viewport_box["y"],
        viewport_box["x"] + viewport_box["width"],
        viewport_box["y"] + viewport_box["height"],
    ]
    grid_edges = [
        grid_box["x"],
        grid_box["y"],
        grid_box["x"] + grid_box["width"],
        grid_box["y"] + grid_box["height"],
    ]
    if not inside(grid_edges, grid_area):
        problems.append(f"grid {grid_box} outside grid-viewport {viewport_box}")
    bar_edges = [
        bar_box["x"],
        bar_box["y"],
        bar_box["x"] + bar_box["width"],
        bar_box["y"] + bar_box["height"],
    ]
    if not inside(bar_edges, [0, 0, window_width, window_height]):
        problems.append(f"clue bar {bar_box} outside the window")
    if touch:
        keyboard_box = page.get_by_test_id("keyboard").bounding_box()
        assert keyboard_box is not None
        if bar_edges[3] > keyboard_box["y"] + EPSILON:
            problems.append(f"clue bar {bar_box} below keyboard {keyboard_box}")
    return problems


def menu_problems(page: Page) -> list[str]:
    """`aide-menu` inside the window, the five items in order, each reachable."""
    found = page.evaluate(MENU_SCRIPT, FIVE_ITEMS)
    problems: list[str] = []
    if not inside(found["box"], found["window"]):
        problems.append(f"aide-menu {found['box']} outside the window")
    if found["order"] != FIVE_ITEMS:
        problems.append(f"the items come as {found['order']}")
    if found["reveals"] != ["reveal-letter", "reveal-word"]:
        problems.append(f"reveal buttons {found['reveals']}")
    for test_id in FIVE_ITEMS:
        hit = page.evaluate(ITEM_HIT_SCRIPT, test_id)
        if hit["hits"] is not True:
            problems.append(
                f"{test_id}: elementFromPoint at its centre is {hit['hit']}"
            )
    return problems


# ---- AC-8 ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_the_open_aide_menu_keeps_the_grid_room_and_reaches_each_item(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_setup_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        open_aide(page)
        layout = spec013_layout_problems(page, touch)
        menu = menu_problems(page)
    finally:
        close()

    assert layout == []
    assert menu == []


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_from_the_keyboard_tab_walks_the_five_items_inside_the_menu(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_setup_room(
        browser, browser_name, live_server, fx01_grid, width, height, False
    )
    try:
        make_walker(page).tab_to("aide-button")
        page.keyboard.press("Enter")
        expect(page.get_by_test_id("aide-menu")).to_be_visible()
        met: list[str] = []
        problems: list[str] = []
        for _ in range(MAX_MENU_TABS):
            reading = page.evaluate(FOCUS_IN_MENU_SCRIPT)
            test_id = reading["testId"]
            if test_id in FIVE_ITEMS and test_id not in met:
                met.append(test_id)
                if not inside(reading["box"], reading["area"]):
                    problems.append(f"{test_id} outside aide-menu's client area")
                outline = reading["outline"]
                found = outline_problems(
                    outline["style"], outline["width"], outline["ratio"]
                )
                problems.extend(f"{test_id}: {problem}" for problem in found)
                for side, pixels in reading["cut"].items():
                    if round(pixels) != 0:
                        problems.append(f"{test_id}: outline cut on the {side}")
            if len(met) == len(FIVE_ITEMS):
                break
            page.keyboard.press("Tab")
    finally:
        close()

    assert met == FIVE_ITEMS
    assert problems == []
