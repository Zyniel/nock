"""Tests of spec 021, AC-11: the flag button keeps the room's layout on every
window.

The setup is spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot with `you` host among
8 players, 100 feed items, (3, 1) tapped, help mode `free`) plus `p2`'s flag on
IDES, at the eight window sizes of spec 006 AC-5, in desktop and touch contexts.
One page per window size and context runs every check of the criterion: spec 013
AC-6's layout, the 24 by 24 px target inside `clue-bar` on the row of
`clue-bar-text`, the keyboard focus in the desktop context (spec 035 AC-2's
outline, not clipped with `clue-bar` among the clipping ancestors), and the hit
at the button's centre with the Salon closed.

Refined by spec 043 (the design's room layout): `flag-button` sits in the navy
clue bar; it read "spec 024 AC-8's toolbar checks hold with `flag-button` among
the toolbar's buttons". The shared setup is in `spec021_harness`.

Choices where the spec leaves room:

- "With the Salon closed": in the column layout, where the page opens the Salon
  at load, it is closed with a click on `chat-toggle` before the checks.
- Sizes have spec 043's tolerance of 0.5 px; positions 1 px.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, FlagView, GridTarget, PlayerView, grid_view
from spec019_harness import layout_problems
from spec021_harness import IDES, open_flag_room
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    WAIT_TIMEOUT_MS,
    cell_at,
    expect_seq,
    grid_from_text,
    make_catalogue,
    make_walker,
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
CONTEXTS = ["desktop", "touch"]
FLAG_BUTTON = "flag-button"
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FEED_ITEMS = 100
MIN_TARGET_PX = 24.0
SIZE_TOLERANCE_PX = 0.5
EPSILON = 1.0

# The button's box, the boxes of `clue-bar` and `clue-bar-text`, and the hit at
# the button's centre.
PLACE_SCRIPT = """
() => {
  const boxOf = (id) => {
    const box = document.querySelector(`[data-testid="${id}"]`).getBoundingClientRect();
    return [box.left, box.top, box.right, box.bottom];
  };
  const button = document.querySelector('[data-testid="flag-button"]');
  const box = button.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    button: boxOf('flag-button'),
    bar: boxOf('clue-bar'),
    text: boxOf('clue-bar-text'),
    hits: hit !== null && (hit === button || button.contains(hit)),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""

# Spec 035's "Not clipped" measure of the focused element's outline, with
# `clue-bar` always among the clipping ancestors, and spec 035 AC-2's outline.
FOCUS_SCRIPT = "() => {\n" + COLOUR_CONTRAST_JS + r"""
  const element = document.activeElement;
  const bar = document.querySelector('[data-testid="clue-bar"]');
  const box = element.getBoundingClientRect();
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
    if (!clips && node !== bar) {
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
    """Open the room of the setup with (3, 1) tapped and the Salon closed."""
    page, close = open_context_page(browser, browser_name, width, height, touch)
    try:
        flags = [FlagView(player_id="p2", clue=IDES)]
        mock = open_flag_room(
            page, live_server, grid_view(grid), flags=flags, players=eight_players()
        )
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
        salon = page.get_by_test_id("salon")
        if salon.get_attribute("hidden", timeout=WAIT_TIMEOUT_MS) is None:
            page.get_by_test_id("chat-toggle").click(timeout=WAIT_TIMEOUT_MS)
        expect(salon).to_be_hidden()
    except BaseException:
        close()
        raise
    return page, close


# ---- The checks ----


def place_problems(page: Page) -> list[str]:
    """The 24 px target inside `clue-bar`, on the row of `clue-bar-text`, and hit."""
    found = page.evaluate(PLACE_SCRIPT)
    left, top, right, bottom = found["button"]
    bar_left, bar_top, bar_right, bar_bottom = found["bar"]
    _, text_top, _, text_bottom = found["text"]
    problems: list[str] = []
    if right - left < MIN_TARGET_PX - SIZE_TOLERANCE_PX:
        problems.append(f"flag-button is {right - left} px wide")
    if bottom - top < MIN_TARGET_PX - SIZE_TOLERANCE_PX:
        problems.append(f"flag-button is {bottom - top} px high")
    inside = (
        left >= bar_left - EPSILON
        and top >= bar_top - EPSILON
        and right <= bar_right + EPSILON
        and bottom <= bar_bottom + EPSILON
    )
    if not inside:
        problems.append(
            f"flag-button {found['button']} outside clue-bar {found['bar']}"
        )
    if not (top < text_bottom and text_top < bottom):
        problems.append("flag-button is not on the row of clue-bar-text")
    if found["hits"] is not True:
        problems.append(f"elementFromPoint at its centre is {found['hit']}")
    return problems


def focus_problems(page: Page) -> list[str]:
    """`tab_to` the button, then spec 035 AC-2's outline, not clipped."""
    make_walker(page).tab_to(FLAG_BUTTON)
    found = page.evaluate(FOCUS_SCRIPT)
    outline = found["outline"]
    problems = outline_problems(outline["style"], outline["width"], outline["ratio"])
    for side, pixels in found["cut"].items():
        if round(pixels) != 0:
            problems.append(f"outline cut by {pixels} px on the {side}")
    return problems


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac11_the_flag_button_keeps_the_room_layout_in_the_clue_bar(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_layout_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        layout = layout_problems(page, touch)
        place = place_problems(page)
        focus = [] if touch else focus_problems(page)
    finally:
        close()

    assert layout == []
    assert place == []
    assert focus == []
