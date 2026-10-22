"""Tests of spec 033, AC-9 (first part): the account item in the room Menu.

The room page runs on spec 040's mocked socket, with `GET /api/account` and the
other account routes answered by `page.route` (the "Browser with mocked routes" of
the "Test harness", `AccountRoutes` of `spec033_harness`). The server is the live
server of the harness, with accounts on.

Layout, at each window size of spec 006 AC-5, in desktop and touch contexts (spec
009's touch harness), with spec 013 AC-6's setup (FX-01, `you` host among 8
players, 100 feed items, (3, 1) tapped): `account-open` is the item of `room-menu`
right after `host-settings-open` and before its `nock-menu-separator`; with the
Menu open (spec 043's `open_menu`) it lies inside the window and `elementFromPoint`
at its centre, after `scrollIntoView({block: "nearest"})`, returns it; and spec
013 AC-6's checks pass.

Keyboard only (desktop context, each window size): `tab_to` `menu-button` and
`Enter` open the Menu, `Tab` reaches `account-open`, which shows spec 035 AC-2's
outline; `Enter` opens `account-dialog` with the focus on `account-email-input`;
during 10 presses of `Tab`, then 10 of `Shift+Tab`, no element outside the dialog
gets the focus (the browser may take it to its own interface: the focus is then on
no element of the page); `Escape` closes the dialog and the focus is on
`menu-button`.

Refined by spec 043 (the design's room layout): this file was
`test_spec_033_ac09_toolbar_layout_and_keyboard.py`, which checked `account-open` as
the last button of `room-toolbar` with spec 024's toolbar rules.

The scans, `/account` and the dialog's edge cases are in
`test_spec_033_ac09_dialog_and_account_page.py`. The shared setup is in
`spec033_harness` and `spec024_harness` (the mocked room, the contexts of spec
013 and the walker of spec 035).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView
from room_panels import open_menu
from spec024_harness import (
    SETTLE_MS,
    cell_at,
    expect_seq,
    make_catalogue,
    make_walker,
    open_context_page,
    open_room,
    outline_problems,
    player_view,
)
from spec032_harness import grid_from_text
from spec033_harness import (
    WAIT_TIMEOUT_MS,
    WINDOW_SIZES,
    AccountRoutes,
    AccountServer,
    account_live_server,
    size_ids,
)

CONTEXTS = ["desktop", "touch"]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 1.0
TRAP_PRESSES = 10


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = make_catalogue(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


# ---- The room page --------------------------------------------------------------


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
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    touch: bool,
) -> tuple[Page, Callable[[], None]]:
    """Spec 013 AC-6's room with accounts on; return the page and its closer."""
    width, height = size
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        AccountRoutes().install(page)
        mock = open_room(page, base_url, grid, players=eight_players())
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
        expect(page.get_by_test_id("account-open")).to_have_count(1)
    except BaseException:
        close()
        raise
    return page, close


# ---- Layout ---------------------------------------------------------------------

# The names of the Menu's items and separators, in document order.
MENU_ORDER_SCRIPT = """
menu => {
  const found = [];
  for (const element of menu.querySelectorAll('*')) {
    const testId = element.getAttribute('data-testid');
    if (element.classList.contains('nock-menu-separator')) {
      found.push('separator');
    } else if (testId !== null && (element.tagName === 'BUTTON'
        || element.tagName === 'A')) {
      found.push(testId);
    }
  }
  return found;
}
"""

ACCOUNT_REACH_SCRIPT = """
() => {
  const account = document.querySelector('[data-testid="account-open"]');
  account.scrollIntoView({block: 'nearest'});
  const box = account.getBoundingClientRect();
  const hit = document.elementFromPoint(box.left + box.width / 2,
    box.top + box.height / 2);
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [innerWidth, innerHeight],
    hits: hit !== null && (hit === account || account.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_account_open_follows_the_host_settings_before_the_separator(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
    context_kind: str,
) -> None:
    page, close = open_layout_room(
        browser,
        browser_name,
        account_server.base_url,
        fx01_grid,
        size,
        context_kind == "touch",
    )
    try:
        order = page.get_by_test_id("room-menu").evaluate(MENU_ORDER_SCRIPT)
    finally:
        close()

    index = order.index("account-open")
    assert order[index - 1] == "host-settings-open", order
    assert order[index + 1] == "separator", order


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_with_the_menu_open_account_open_is_in_the_window_and_reachable(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
    context_kind: str,
) -> None:
    page, close = open_layout_room(
        browser,
        browser_name,
        account_server.base_url,
        fx01_grid,
        size,
        context_kind == "touch",
    )
    try:
        open_menu(page)
        reading = page.evaluate(ACCOUNT_REACH_SCRIPT)
    finally:
        close()

    left, top, right, bottom = reading["box"]
    width, height = reading["window"]
    assert left >= -EPSILON, reading
    assert top >= -EPSILON, reading
    assert right <= width + EPSILON, reading
    assert bottom <= height + EPSILON, reading
    assert reading["hits"] is True, reading


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
@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_spec_013_layout_holds_with_account_open(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_layout_room(
        browser, browser_name, account_server.base_url, fx01_grid, size, touch
    )
    try:
        assert_spec013_layout(page, touch)
    finally:
        close()


# ---- Keyboard only --------------------------------------------------------------


def open_menu_from_the_keyboard(page: Page) -> None:
    """`tab_to` `menu-button`, then `Enter`; wait until `room-menu` is open."""
    make_walker(page).tab_to("menu-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("room-menu")).to_be_visible()


FOCUS_PLACE_SCRIPT = """
() => {
  const dialog = document.querySelector('[data-testid="account-dialog"]');
  const focused = document.activeElement;
  if (focused === null || focused === document.body
      || focused === document.documentElement) {
    return 'none';
  }
  if (dialog !== null && dialog.contains(focused)) {
    return 'inside';
  }
  return focused.getAttribute('data-testid') || focused.tagName;
}
"""


@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_keyboard_tab_reaches_account_open_with_a_visible_outline(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
) -> None:
    page, close = open_layout_room(
        browser, browser_name, account_server.base_url, fx01_grid, size, False
    )
    try:
        open_menu_from_the_keyboard(page)
        walker = make_walker(page)
        walker.tab_to("account-open")
        page.wait_for_timeout(SETTLE_MS)
        walker.record("account-open")
        reached = walker.reached[-1]
    finally:
        close()

    problems = outline_problems(
        reached.outline_style, reached.outline_width, reached.outline_contrast
    )
    assert problems == [], reached


@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_keyboard_enter_opens_the_dialog_with_the_focus_on_the_address(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
) -> None:
    page, close = open_layout_room(
        browser, browser_name, account_server.base_url, fx01_grid, size, False
    )
    try:
        open_menu_from_the_keyboard(page)
        make_walker(page).tab_to("account-open")
        page.keyboard.press("Enter")

        dialog = page.get_by_test_id("account-dialog")
        expect(dialog).to_have_attribute("open", "")
        expect(page.get_by_test_id("account-email-input")).to_be_focused()
    finally:
        close()


@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_keyboard_the_focus_stays_in_the_dialog_and_escape_gives_it_back(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
) -> None:
    page, close = open_layout_room(
        browser, browser_name, account_server.base_url, fx01_grid, size, False
    )
    places: list[str] = []
    try:
        open_menu_from_the_keyboard(page)
        make_walker(page).tab_to("account-open")
        page.keyboard.press("Enter")
        dialog = page.get_by_test_id("account-dialog")
        expect(dialog).to_have_attribute("open", "")
        for key in ["Tab"] * TRAP_PRESSES + ["Shift+Tab"] * TRAP_PRESSES:
            page.keyboard.press(key)
            places.append(str(page.evaluate(FOCUS_PLACE_SCRIPT)))

        page.keyboard.press("Escape")

        expect(dialog).not_to_have_attribute("open", "")
        expect(page.get_by_test_id("menu-button")).to_be_focused()
    finally:
        close()

    outside = [place for place in places if place not in ("inside", "none")]
    assert outside == [], places
    assert "inside" in places
