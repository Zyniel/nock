"""Tests of spec 046, AC-22: every page of this spec fits every window.

At each window size of spec 006 AC-5, in six states: `/` with `CAT` (live),
`ROOMS2` with 8 players of 20 characters in `XYZ789`, `HIST2` with 7 team-mates
of 20 characters in `XYZ789`, and accounts on, signed out (mocked routes); `/g/2`;
`/r/ABC123` showing the nickname card with `nickname-error`; showing the `full`
card; `/r/ZZZZZZ` showing the `not_found` card; and the opening of AC-20 (mocked
socket). In each, the page has no horizontal scroll, its top bar lies inside the
window, and every row, card and grid card lies inside its column horizontally,
with each of its buttons and links inside its own box.

Choices where the spec leaves room:

- "Its column": `catalogue-column` for `catalogue-item`, `my-room` and
  `history-item`; `page-column` for a card, which is each element child of
  `page-column` other than the room code line (`h1`).
- "Inside the window" for the top bar: its box within the window's box (1 px).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec006_harness import WINDOW_SIZES
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec046_harness import (
    SIGNED_OUT,
    WAIT_TIMEOUT_MS,
    Box,
    OpenWindow,
    Reading,
    accounts_on,
    expect_history_count,
    expect_my_rooms_ready,
    inside,
    inside_horizontally,
    long_names,
    open_catalogue,
    open_nickname_card,
    open_opening,
    open_status_card,
    open_unknown_room,
    seed_hist2,
    seed_rooms2,
    show_nickname_error,
    to_box,
    window_opener,
)

STATES = ["catalogue", "grid-page", "nickname-error", "full", "not-found", "opening"]

# The page's sizes, its top bar, and each column with its items and their
# buttons and links, as boxes.
FIT_SCRIPT = r"""
() => {
  function boxOf(element) {
    const rect = element.getBoundingClientRect();
    return [rect.left, rect.top, rect.right, rect.bottom];
  }
  function shows(element) {
    return element.getClientRects().length > 0;
  }
  function itemOf(element, name) {
    const controls = [];
    for (const control of element.querySelectorAll('button, a')) {
      if (shows(control)) {
        controls.push({name: control.getAttribute('data-testid') || control.tagName,
          box: boxOf(control)});
      }
    }
    return {name: name, box: boxOf(element), controls: controls};
  }
  const groups = [];
  const catalogueColumn = document.querySelector('[data-testid="catalogue-column"]');
  if (catalogueColumn !== null) {
    const items = [];
    const selector = '[data-testid="catalogue-item"], [data-testid="my-room"],'
      + ' [data-testid="history-item"]';
    for (const item of catalogueColumn.querySelectorAll(selector)) {
      if (shows(item)) {
        items.push(itemOf(item, item.getAttribute('data-testid')));
      }
    }
    groups.push({name: 'catalogue-column', box: boxOf(catalogueColumn), items: items});
  }
  const pageColumn = document.querySelector('[data-testid="page-column"]');
  if (pageColumn !== null) {
    const items = [];
    for (const child of pageColumn.children) {
      if (child.tagName !== 'H1' && shows(child)) {
        items.push(itemOf(child, child.getAttribute('data-testid') || 'card'));
      }
    }
    groups.push({name: 'page-column', box: boxOf(pageColumn), items: items});
  }
  const bar = document.querySelector('[data-testid="page-topbar"]')
    || document.querySelector('[data-testid="room-topbar"]');
  return {
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    bar: bar === null ? null : boxOf(bar),
    groups: groups,
  };
}
"""

# What each state shows, so that a check never passes on an empty page: the three
# grid cards, the two rooms and `HIST2`'s two finished grids, or the one card.
ITEMS_OF_STATE = {
    "catalogue": 3 + 2 + 2,
    "grid-page": 1,
    "nickname-error": 1,
    "full": 1,
    "not-found": 1,
    "opening": 0,
}
CASES = [(size, state) for size in WINDOW_SIZES for state in STATES]
CASE_IDS = [f"{w}x{h}-{state}" for (w, h), state in CASES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_state(page: Page, base_url: str, state: str) -> None:
    """Open one of AC-22's six states and wait until it shows with its fonts."""
    if state == "catalogue":
        accounts_on(page, SIGNED_OUT)
        seed_rooms2(page, players=long_names(8))
        seed_hist2(page, teammates=long_names(7))
        open_catalogue(page, base_url)
        expect_my_rooms_ready(page, 2)
        expect(page.get_by_test_id("account-open")).to_be_visible()
        expect_history_count(page, 2)
    elif state == "grid-page":
        page.goto(f"{base_url}/g/2")
        expect(page.get_by_test_id("grid-page")).to_have_attribute(
            "data-state", "ready", timeout=WAIT_TIMEOUT_MS
        )
    elif state == "nickname-error":
        open_nickname_card(page, base_url)
        show_nickname_error(page)
    elif state == "full":
        open_status_card(page, base_url, "room_full")
    elif state == "not-found":
        open_unknown_room(page, base_url)
    else:
        open_opening(page, base_url)
    wait_for_fonts(page)


def item_count(found: Reading) -> int:
    """How many rows, cards and grid cards the page showed to `FIT_SCRIPT`."""
    count = 0
    for group in found["groups"]:
        count += len(group["items"])
    return count


def fit_problems(found: Reading) -> list[str]:
    """How a page read by `FIT_SCRIPT` breaks AC-22."""
    problems: list[str] = []
    if found["scrollWidth"] > found["innerWidth"]:
        problems.append(f"scrollWidth {found['scrollWidth']} > {found['innerWidth']}")
    window = Box(0.0, 0.0, float(found["innerWidth"]), float(found["innerHeight"]))
    if found["bar"] is None:
        problems.append("no top bar")
    elif not inside(to_box(found["bar"]), window):
        problems.append(f"top bar {found['bar']} outside the window")
    for group in found["groups"]:
        column = to_box(group["box"])
        for item in group["items"]:
            item_box = to_box(item["box"])
            if not inside_horizontally(item_box, column):
                problems.append(f"{item['name']} {item_box} out of {group['name']}")
            for control in item["controls"]:
                if not inside(to_box(control["box"]), item_box):
                    problems.append(f"{control['name']} out of {item['name']}")
    return problems


@pytest.mark.parametrize(("size", "state"), CASES, ids=CASE_IDS)
def test_ac22_each_page_fits_the_window_and_its_rows_fit_their_column(
    window: OpenWindow, live_server: str, size: tuple[int, int], state: str
) -> None:
    page = window(*size)
    open_state(page, live_server, state)

    found = page.evaluate(FIT_SCRIPT)

    assert isinstance(found, dict), found
    assert item_count(found) == ITEMS_OF_STATE[state], found
    assert fit_problems(found) == []
