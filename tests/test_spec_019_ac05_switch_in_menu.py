"""Tests of spec 019, AC-5: the authors switch meets spec 035 and keeps the room.

The setup is spec 013 AC-6's (FX-01, `you` host among 8 players, 100 feed items,
(3, 1) tapped), with letters by four of the players and the switch on, at the
window sizes of spec 006 AC-5 in desktop and touch contexts. A separate
keyboard-only run uses spec 035's `tab_to`, and spec 035's contrast and language
scans run with the switch on. The shared setup is in `spec019_harness`.

Refined by spec 043 (the design's room layout): `authors-switch` is the first item
of `room-menu`, and with the Menu open spec 043 AC-28's checks hold for it (inside
the window; `elementFromPoint` at its centre returns it); the keyboard-only run
opens the Menu with `tab_to` `menu-button` and `Enter`, which puts the focus on the
switch. The rules of spec 024 AC-8's toolbar (one row, the toolbar's client area,
the fade) went with the toolbar.

Choices where the spec leaves room:

- "The first item of `room-menu`": the first `button` or `a` inside it.
- The keyboard-only run uses the setup's snapshot and feed, with no tap and the
  switch off at first.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget, PlayerView, grid_view
from room_panels import open_menu
from spec019_harness import (
    CONTEXT_KINDS,
    LAYOUT_EPSILON_PX,
    ROOM_CODE,
    WINDOW_IDS,
    WINDOW_SIZES,
    ChangeList,
    MockRoomSocket,
    OpenWindow,
    authors_switch,
    cell_at,
    expect_seq,
    grid_from_text,
    layout_problems,
    open_room,
    player_view,
    press,
    turn_switch_on,
    wait_until,
    window_opener,
    with_letter_cells,
)
from spec035_harness import unknown_texts

EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_LIMIT = 100
SCAN_WINDOWS = [(1280, 720), (360, 740)]
MAX_TABS = 60
MIN_OUTLINE_PX = 2.0
MIN_FOCUS_CONTRAST = 3.0
MIN_TEXT_CONTRAST = 4.5

FX01_CLUES = [
    "Passoire fine",
    "De la marine",
    "Artiste muet",
    "Fatales à César",
    "Flaire",
    "Sans contenu",
    "Fin de prière",
    "Alourdit le ballon",
]

COLOUR_CONTRAST_JS = (Path(__file__).parent / "colour_contrast.js").read_text(
    encoding="utf-8"
)
CONTRAST_SCAN_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn scanTextContrast();\n}"
)
FOCUS_OUTLINE_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn readFocusOutline();\n}"
)

LANGUAGE_SCAN_SCRIPT = r"""
() => {
  const skippedTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TITLE', 'HEAD']);
  const attributes = ['aria-label', 'title', 'placeholder', 'alt'];
  const found = [];
  for (const element of document.body.querySelectorAll('*')) {
    if (skippedTags.has(element.tagName)) {
      continue;
    }
    let rendered = element.getClientRects().length > 0;
    if (element.tagName === 'OPTION') {
      const select = element.closest('select');
      rendered = select !== null && select.getClientRects().length > 0;
    }
    if (!rendered || getComputedStyle(element).visibility !== 'visible') {
      continue;
    }
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== '') {
        found.push(node.textContent.trim());
      }
    }
    for (const name of attributes) {
      const value = element.getAttribute(name);
      if (value !== null && value.trim() !== '') {
        found.push(value.trim());
      }
    }
  }
  return found;
}
"""

HIT_SCRIPT = """
() => {
  const authors = document.querySelector('[data-testid="authors-switch"]');
  authors.scrollIntoView({block: 'nearest'});
  const box = authors.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    box: [box.left, box.top, box.right, box.bottom],
    hits: hit !== null && (hit === authors || authors.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""

FIRST_ITEM_SCRIPT = """
menu => {
  const first = menu.querySelector('button, a');
  return first === null ? null : first.getAttribute('data-testid');
}
"""

TAB_TARGET_SCRIPT = r"""
testId => {
  const targets = document.querySelectorAll(`[data-testid="${testId}"]`);
  const grid = document.querySelector('[data-testid="grid"]');
  const focused = document.activeElement;
  const state = {
    matches: targets.length,
    onTarget: false,
    onGrid: focused !== null && focused === grid,
    targetIsBefore: false,
  };
  if (targets.length === 1 && focused !== null) {
    state.onTarget = focused === targets[0];
    const position = focused.compareDocumentPosition(targets[0]);
    state.targetIsBefore = (position & Node.DOCUMENT_POSITION_PRECEDING) !== 0;
  }
  return state;
}
"""


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- The setup --------------------------------------------------------------


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        players.append(player_view(f"p{number}", nickname, number - 1))
    return players


def letters_by_four_players() -> ChangeList:
    return [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p2"}),
        (2, 1, {"letter": "V", "author": "p3"}),
        (3, 1, {"letter": "A", "author": "p4"}),
    ]


def open_setup_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot (seq 5) and the 100 feed items (seq 6 to 105), no tap."""
    view = with_letter_cells(grid_view(grid), letters_by_four_players())
    mock = open_room(page, base_url, view, eight_players(), seq=5)
    last_seq = 5 + FEED_LIMIT
    for seq in range(6, last_seq + 1):
        result = CheckResult(
            seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
        )
        mock.send(result.model_dump_json())
    expect_seq(page, last_seq)
    return mock


def open_setup(page: Page, base_url: str, grid: Grid, touch: bool) -> None:
    """The setup of AC-5: room, feed, (3, 1) tapped, then the switch on."""
    open_setup_room(page, base_url, grid)
    press(cell_at(page, 3, 1), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "3,0,0")
    turn_switch_on(page, touch)


def outline_problems(page: Page) -> list[str]:
    """How the focused element's outline breaks spec 035 AC-2 (empty: none)."""
    outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
    problems: list[str] = []
    if outline["style"] in ("none", "auto"):
        problems.append(f"outline style {outline['style']}")
    if outline["width"] < MIN_OUTLINE_PX:
        problems.append(f"outline {outline['width']} px wide")
    if outline["ratio"] < MIN_FOCUS_CONTRAST:
        problems.append(f"outline contrast {outline['ratio']} against white")
    return problems


def tab_to(page: Page, test_id: str) -> None:
    """Spec 035's `tab_to`: Tab or Shift+Tab until the target has the focus."""
    presses = 0
    while True:
        state = page.evaluate(TAB_TARGET_SCRIPT, test_id)
        if state["matches"] != 1:
            pytest.fail(f"{state['matches']} elements match {test_id}")
        if state["onTarget"]:
            return
        if presses == MAX_TABS:
            pytest.fail(f"{test_id} not reached in {MAX_TABS} presses")
        if state["onGrid"]:
            page.keyboard.press("Escape")
        page.keyboard.press("Shift+Tab" if state["targetIsBefore"] else "Tab")
        presses += 1


# ---- AC-5: at every window size, desktop and touch --------------------------


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac5_the_grid_keeps_its_room_with_the_switch_on(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)

    open_setup(page, live_server, fx01_grid, touch)

    assert layout_problems(page, touch) == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac5_the_switch_is_the_first_item_of_the_menu(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_setup(page, live_server, fx01_grid, touch)

    open_menu(page)

    first = page.get_by_test_id("room-menu").evaluate(FIRST_ITEM_SCRIPT)
    assert first == "authors-switch"


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac5_with_the_menu_open_the_switch_is_in_the_window_and_reachable(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_setup(page, live_server, fx01_grid, touch)
    open_menu(page)

    hit = page.evaluate(HIT_SCRIPT)

    left, top, right, bottom = hit["box"]
    assert left >= -LAYOUT_EPSILON_PX, hit
    assert top >= -LAYOUT_EPSILON_PX, hit
    assert right <= width + LAYOUT_EPSILON_PX, hit
    assert bottom <= height + LAYOUT_EPSILON_PX, hit
    assert hit["hits"] is True, f"elementFromPoint found {hit['hit']}"


# ---- AC-5: keyboard only, at 1280 by 720 ------------------------------------


def test_ac5_keyboard_only_enter_turns_the_switch_on_then_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(1280, 720, False)
    open_setup_room(page, live_server, fx01_grid)
    switch = authors_switch(page)
    expect(switch).to_have_attribute("aria-pressed", "false")

    tab_to(page, "menu-button")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    expect(switch).to_be_focused()
    assert outline_problems(page) == []
    page.keyboard.press("Enter")
    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(switch).to_be_focused()
    assert outline_problems(page) == []
    page.keyboard.press("Enter")

    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(switch).to_be_focused()
    assert outline_problems(page) == []


# ---- AC-5: contrast and language scans with the switch on -------------------


def scan_data(base_url: str) -> set[str]:
    """The test's own data that the language scan accepts (spec 035)."""
    data = set(EIGHT_NICKNAMES)
    data.update(FX01_CLUES)
    data.add(ROOM_CODE)
    data.add(f"{base_url}/r/{ROOM_CODE}")
    return data


@pytest.mark.parametrize(
    ("width", "height"), SCAN_WINDOWS, ids=[f"{w}x{h}" for w, h in SCAN_WINDOWS]
)
def test_ac5_the_contrast_scan_finds_no_offender_with_the_switch_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_setup(page, live_server, fx01_grid, False)
    expect(page.get_by_test_id("clue-bar-author")).to_have_count(1)

    measurements: list[dict[str, Any]] = page.evaluate(CONTRAST_SCAN_SCRIPT)

    offenders = [item for item in measurements if item["ratio"] < MIN_TEXT_CONTRAST]
    assert offenders == []


@pytest.mark.parametrize(
    ("width", "height"), SCAN_WINDOWS, ids=[f"{w}x{h}" for w, h in SCAN_WINDOWS]
)
def test_ac5_the_language_scan_finds_no_offender_with_the_switch_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height, False)
    open_setup(page, live_server, fx01_grid, False)
    expect(page.get_by_test_id("clue-bar-author")).to_have_count(1)
    wait_until(page, lambda: page.evaluate("document.documentElement.lang") == "fr")

    texts: list[str] = page.evaluate(LANGUAGE_SCAN_SCRIPT)

    assert unknown_texts(texts, scan_data(live_server)) == []
