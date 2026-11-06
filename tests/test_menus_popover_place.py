"""Tests of `client/menus.md` AC-10: an open menu follows the top bar's change of
form while the layout stays (rule 5).

AC-10: at 1280 by 720 with the Menu open, the window turned to 1280 by 480 (the
column layout kept, the phone top bar) leaves the Menu open at the place of a
Menu opened at 1280 by 480.

Readings where the spec leaves room:

- "Turned to" is a resize of the same window: its width kept, its height
  changed (`set_viewport_size`), not a rotation.
- "The column layout kept" is `data-layout` `column` on `room-page` before and
  after; "the phone top bar" is the class `phone` on `room-topbar`. Both are
  checked, so that the test runs in the case the criterion names.
- "Open" is `room-menu` shown without `hidden`. "The place" is the box of
  `room-menu`, within 1 px on each edge of the box of a Menu opened in a second
  window of 1280 by 480 on the same room. The resized Menu has up to 5 s to get
  there.
- The page hears the resize in one go: its `resize` listeners run one after the
  other with no microtask between them (`IN_ONE_GO_SCRIPT`), as for a `resize`
  event a script dispatches. A browser's own `resize` event lets the page draw
  the new top bar between two listeners, and a menu then placed by its own
  `resize` listener lands at the right place even when the change of form is
  not followed. Heard in one go, a menu placed only in that listener measures
  the computer bar it is leaving, and the menu has to follow the change of form
  itself once the page has drawn the new bar.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from hud_harness import open_fx01_room
from nock.grid import Grid
from room_panels import expect_open, open_menu
from spec019_harness import OpenWindow, window_opener
from spec042_harness import Box, box_of, wait_until
from spec043_harness import COMPUTER, expect_layout, same_box

LOW_COMPUTER = (1280, 480)
PHONE_BAR_CLASS = re.compile(r"\bphone\b")
COMPUTER_BAR_CLASS = re.compile(r"\bcomputer\b")

# Stop each `resize` event of the browser before any listener of the page, and
# dispatch a `resize` event of the page's own in its place, so that the page's
# listeners run in one go (see the module's docstring). It holds in all three
# engines: the init script registers before the page's scripts, and listeners at
# the target run in registration order (the capturing ones first at the target,
# per the DOM spec), so this one runs before any listener of the page.
IN_ONE_GO_SCRIPT = r"""
window.addEventListener('resize', event => {
  if (!event.isTrusted) {
    return
  }
  event.stopImmediatePropagation()
  window.dispatchEvent(new Event('resize'))
}, { capture: true })
"""


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def menu_box(page: Page) -> Box:
    """Return the box of `room-menu`, in page pixels."""
    return box_of(page.get_by_test_id("room-menu"))


def place_of_a_menu_opened_at(
    window: OpenWindow, live_server: str, grid: Grid, size: tuple[int, int]
) -> Box:
    """Open FX-01 in a window of `size`, open the Menu there and return its box."""
    page = window(size[0], size[1], False)
    open_fx01_room(page, live_server, grid)
    expect(page.get_by_test_id("room-topbar")).to_have_class(PHONE_BAR_CLASS)
    expect_layout(page, "column")
    open_menu(page)
    return menu_box(page)


def test_ac10_the_open_menu_follows_the_phone_bar_when_the_window_gets_lower(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    expected_box = place_of_a_menu_opened_at(
        window, live_server, fx01_grid, LOW_COMPUTER
    )
    page = window(COMPUTER[0], COMPUTER[1], False)
    page.add_init_script(IN_ONE_GO_SCRIPT)
    open_fx01_room(page, live_server, fx01_grid)
    topbar = page.get_by_test_id("room-topbar")
    expect(topbar).to_have_class(COMPUTER_BAR_CLASS)
    expect_layout(page, "column")
    open_menu(page)

    page.set_viewport_size({"width": LOW_COMPUTER[0], "height": LOW_COMPUTER[1]})

    expect(topbar).to_have_class(PHONE_BAR_CLASS)
    expect_layout(page, "column")
    menu = page.get_by_test_id("room-menu")
    expect_open(menu)
    wait_until(
        page,
        lambda: same_box(menu_box(page), expected_box),
        "the Menu at the place of one opened at 1280 by 480",
    )
    expect_open(menu)
    assert same_box(menu_box(page), expected_box), (menu_box(page), expected_box)
