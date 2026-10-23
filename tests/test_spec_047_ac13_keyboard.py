"""Tests of spec 047, AC-13: the overlays meet spec 035's keyboard rules.

At 1280 by 720, keyboard only (spec 035's harness, its `Walker`). On `VOTE_ROOM`
after `VOTE`: from the `grid`, `Escape` then `Shift+Tab` focuses `vote-no`, whose
focus ring (2 px solid navy at offset 2 px) lies inside the banner. On `SOLVED`
with `RECAP`: `tab_to` `recap-open` shows the same ring, `Enter` opens `recap`,
`Tab` reaches the share link, « Copier le lien » and « Fermer » with that ring and
never leaves the dialog in 10 presses, and `Escape` closes it, the focus back on
`recap-open`.

Readings where the spec leaves room:

- "Its box grown by 4 px on each side (the ring) lies inside `vote-banner`'s box
  (1 px)": `vote-no`'s bounding box grown by 4 px on each side.
- The ring is read on the focused element's computed `outline-width`,
  `outline-style`, `outline-color` and `outline-offset`.
- "No element outside `recap` gets the focus during 10 presses of `Tab`": after
  each press, `document.activeElement` is `recap` or inside it (`body` counts as
  outside). The presses start once the loaded recap shows (`recap-time`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec035_harness import Walker
from spec042_harness import Box, box_of
from spec043_harness import box_inside, focused_test_id
from spec044_harness import solved_frame
from spec047_harness import (
    COMPUTER,
    open_solved,
    open_vote_room,
    ring_problems,
    show_vote,
)

TAB_PRESSES = 10
RING_PX = 4.0
DIALOG_TARGETS = ["recap-share-link", "recap-copy", "recap-close"]

# Where the focus is: its test id, and whether it is `recap` or inside it.
FOCUS_IN_RECAP_SCRIPT = r"""
() => {
  const recap = document.querySelector('[data-testid="recap"]');
  const active = document.activeElement;
  return {
    testId: active === null ? null
      : (active.getAttribute('data-testid') || active.tagName),
    inside: recap !== null && active !== null && recap.contains(active),
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


# ---- Setup -------------------------------------------------------------------------


def open_solved_page(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    """`SOLVED` at 1280 by 720 (desktop) with the route answering `RECAP`."""
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_solved(page, base_url, solved_frame(grid))
    expect(page.get_by_test_id("recap-open")).to_be_visible()
    return page


def open_recap_with_the_keyboard(page: Page) -> None:
    """`tab_to` `recap-open`, then `Enter`; wait for the loaded recap."""
    Walker(page).tab_to("recap-open")
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("recap")).to_have_attribute("open", "")
    expect(page.get_by_test_id("recap-time")).to_be_visible()


def grown(box: Box, by: float) -> Box:
    return Box(box.left - by, box.top - by, box.right + by, box.bottom + by)


# ---- The banner ------------------------------------------------------------------


def test_ac13_shift_tab_from_the_grid_reaches_no_with_the_ring_inside_the_banner(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    mock = open_vote_room(page, live_server, fx01_grid)
    show_vote(page, mock)

    Walker(page).tab_to("grid")
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    no = page.get_by_test_id("vote-no")
    expect(no).to_be_focused()
    assert ring_problems(no, "vote-no") == []
    ring = grown(box_of(no), RING_PX)
    banner_box = box_of(page.get_by_test_id("vote-banner"))
    assert box_inside(ring, banner_box), (ring, banner_box)


# ---- The recap ------------------------------------------------------------------


def test_ac13_tab_reaches_voir_le_bilan_with_the_ring(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_page(window, live_server, fx01_grid)

    Walker(page).tab_to("recap-open")

    button = page.get_by_test_id("recap-open")
    expect(button).to_be_focused()
    assert ring_problems(button, "recap-open") == []


def test_ac13_enter_opens_the_recap_and_tab_reaches_its_three_controls(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_page(window, live_server, fx01_grid)
    open_recap_with_the_keyboard(page)

    reached: list[str] = []
    problems: list[str] = []
    for _ in range(TAB_PRESSES):
        page.keyboard.press("Tab")
        test_id = focused_test_id(page)
        if test_id is None or test_id not in DIALOG_TARGETS:
            continue
        if test_id not in reached:
            reached.append(test_id)
            problems += ring_problems(page.get_by_test_id(test_id), test_id)

    assert sorted(reached) == sorted(DIALOG_TARGETS)
    assert problems == []


def test_ac13_ten_presses_of_tab_never_leave_the_recap(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_page(window, live_server, fx01_grid)
    open_recap_with_the_keyboard(page)

    outside: list[object] = []
    for _ in range(TAB_PRESSES):
        page.keyboard.press("Tab")
        found = page.evaluate(FOCUS_IN_RECAP_SCRIPT)
        assert isinstance(found, dict), found
        if found["inside"] is not True:
            outside.append(found["testId"])

    assert outside == []


def test_ac13_escape_closes_the_recap_and_the_focus_is_on_voir_le_bilan(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_page(window, live_server, fx01_grid)
    open_recap_with_the_keyboard(page)

    page.keyboard.press("Escape")

    # Closed: no open `recap` (the page may also take the closed dialog away).
    expect(page.locator('[data-testid="recap"][open]')).to_have_count(0)
    expect(page.get_by_test_id("recap-open")).to_be_focused()
