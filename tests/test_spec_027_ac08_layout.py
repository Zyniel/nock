"""Tests of spec 027, AC-8 (second part): the timer keeps the room's layout at every
window size, in desktop and touch contexts.

The setup is spec 043's `H8` (spec 013 AC-6's FX-01 snapshot, `you` host among 8
players, 100 feed items, (3, 1) tapped, help mode `free`, the timer at
`10:00:00`), at the eight window sizes of spec 006 AC-5. Every check of spec 013
AC-6 holds; `timer` lies inside `room-topbar`'s box, does not overlap
`undo-button` or `topbar-brand`, and its text is on one line; and, with the timer
hidden from the Menu, `timer-show` is at least 24 by 24 CSS px and lies inside
`room-topbar`'s box.

Refined by spec 043 (the design's room layout): the checks of `timer-toggle` in
`room-toolbar` (spec 024 AC-8's toolbar rules) went with the toolbar. The 24 px of
`timer-show` are compared with spec 043's 0.5 px tolerance of a size, which also
ends the sub-pixel failure of the old toggle in Firefox (a width of
23.99999237060547 px at 740 by 360). Boxes are compared with 1 px of tolerance.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from room_panels import open_menu
from spec019_harness import (
    CONTEXT_KINDS,
    WINDOW_IDS,
    WINDOW_SIZES,
    OpenWindow,
    layout_problems,
    window_opener,
)
from spec042_harness import box_of, overlap_px
from spec043_harness import (
    SIZE_TOLERANCE_PX,
    Box,
    box_inside,
    open_h8,
)

MIN_TARGET_PX = 24.0
LINES_SCRIPT = r"""
element => {
  const range = document.createRange();
  range.selectNodeContents(element);
  const tops = [];
  for (const rect of range.getClientRects()) {
    if (rect.width === 0 && rect.height === 0) {
      continue;
    }
    if (!tops.some(top => Math.abs(top - rect.top) <= 1)) {
      tops.push(rect.top);
    }
  }
  return tops.length;
}
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def timer_place_problems(page: Page) -> list[str]:
    """`timer` inside the top bar, clear of `undo-button` and the brand, one line."""
    bar = box_of(page.get_by_test_id("room-topbar"))
    timer = page.get_by_test_id("timer")
    timer_box = box_of(timer)
    problems: list[str] = []
    if not box_inside(timer_box, bar):
        problems.append(f"timer {timer_box} is not inside room-topbar {bar}")
    others: list[tuple[str, Box]] = [
        ("undo-button", box_of(page.get_by_test_id("undo-button")))
    ]
    brand = page.get_by_test_id("topbar-brand")
    if brand.count() == 1 and brand.is_visible():
        others.append(("topbar-brand", box_of(brand)))
    for name, other in others:
        if overlap_px(timer_box, other) > 1.0:
            problems.append(f"timer {timer_box} overlaps {name} {other}")
    lines = timer.evaluate(LINES_SCRIPT)
    if lines != 1:
        problems.append(f"the timer's text is on {lines} lines")
    return problems


def chrono_problems(page: Page) -> list[str]:
    """`timer-show` at least 24 by 24 px, inside the top bar."""
    bar = box_of(page.get_by_test_id("room-topbar"))
    show_box = box_of(page.get_by_test_id("timer-show"))
    problems: list[str] = []
    if show_box.width < MIN_TARGET_PX - SIZE_TOLERANCE_PX:
        problems.append(f"timer-show is {show_box.width} px wide")
    if show_box.height < MIN_TARGET_PX - SIZE_TOLERANCE_PX:
        problems.append(f"timer-show is {show_box.height} px high")
    if not box_inside(show_box, bar):
        problems.append(f"timer-show {show_box} is not inside room-topbar {bar}")
    return problems


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac8_the_timer_keeps_the_rooms_layout_in_the_top_bar(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_h8(page, live_server, fx01_grid, touch)

    layout = layout_problems(page, touch)
    place = timer_place_problems(page)

    assert layout == []
    assert place == []


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac8_with_the_timer_hidden_chrono_is_at_least_24_px_in_the_top_bar(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_h8(page, live_server, fx01_grid, touch)

    open_menu(page)
    page.get_by_test_id("timer-toggle").click()
    expect(page.get_by_test_id("timer-show")).to_be_visible()

    assert chrono_problems(page) == []
