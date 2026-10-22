"""Tests of spec 043, AC-1: which layout the room page uses.

`room-page` has `data-layout="column"` on a landscape window at least 900 px wide
and more than 500 px high, or on a landscape window at most 500 px high when the
in-app keyboard is hidden (off a touch screen); `"sheet"` otherwise. It follows a
resize within 300 ms, and a change of layout closes the popovers.

Choices where the spec leaves room:

- "Within 300 ms" is a wait up to that bound for the new value of `data-layout`
  after `page.set_viewport_size` returned; it measures no pace, so the file stays
  in the gate's parallel pass.
- "The Salon takes the state of the new layout" ("Edge cases and errors"): after a
  resize to the sheet layout the Salon is closed, and back in the column layout
  (no `nock.salon_closed`) it is open again.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from room_panels import open_menu
from spec019_harness import OpenWindow, window_opener
from spec043_harness import (
    FOLLOW_MS,
    expect_closed,
    expect_layout,
    fx01_view,
    open_room,
    players_up_to,
    snapshot_frame,
)

# The desktop windows of the criterion and the layout each one has.
DESKTOP_LAYOUTS = [
    (1920, 1080, "column"),
    (1280, 720, "column"),
    (1024, 768, "column"),
    (900, 600, "column"),
    (740, 360, "column"),
    (568, 320, "column"),
    (899, 600, "sheet"),
    (800, 800, "sheet"),
    (768, 1024, "sheet"),
    (360, 740, "sheet"),
    (320, 568, "sheet"),
]
DESKTOP_IDS = [f"{width}x{height}" for width, height, _ in DESKTOP_LAYOUTS]
# In the touch context the in-app keyboard shows, so a low window is a sheet.
TOUCH_LAYOUTS = [(1024, 768, "column"), (740, 360, "sheet"), (568, 320, "sheet")]
TOUCH_IDS = [f"{width}x{height}" for width, height, _ in TOUCH_LAYOUTS]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_fx01(page: Page, base_url: str, grid: Grid) -> None:
    open_room(page, base_url, snapshot_frame(fx01_view(grid), players_up_to(3)))


@pytest.mark.parametrize(
    ("width", "height", "layout"), DESKTOP_LAYOUTS, ids=DESKTOP_IDS
)
def test_ac1_in_the_desktop_context_the_layout_follows_the_window(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    layout: str,
) -> None:
    page = window(width, height, False)

    open_fx01(page, live_server, fx01_grid)

    expect_layout(page, layout)


@pytest.mark.parametrize(("width", "height", "layout"), TOUCH_LAYOUTS, ids=TOUCH_IDS)
def test_ac1_in_the_touch_context_a_low_window_keeps_the_sheet_layout(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    layout: str,
) -> None:
    page = window(width, height, True)

    open_fx01(page, live_server, fx01_grid)

    expect_layout(page, layout)


def test_ac1_a_resize_changes_the_layout_within_300_ms_both_ways(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    expect_layout(page, "column")

    page.set_viewport_size({"width": 360, "height": 740})
    expect_layout(page, "sheet", timeout=FOLLOW_MS)
    page.set_viewport_size({"width": 1280, "height": 720})
    expect_layout(page, "column", timeout=FOLLOW_MS)


def test_ac1_a_change_of_layout_closes_an_open_room_menu(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    room_menu = page.get_by_test_id("room-menu")

    open_menu(page)
    page.set_viewport_size({"width": 360, "height": 740})
    expect_layout(page, "sheet")
    expect_closed(room_menu)

    open_menu(page)
    page.set_viewport_size({"width": 1280, "height": 720})
    expect_layout(page, "column")
    expect_closed(room_menu)


def test_ac1_the_salon_takes_the_state_of_each_new_layout(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    salon = page.get_by_test_id("salon")
    expect(salon).to_be_visible()

    page.set_viewport_size({"width": 360, "height": 740})
    expect_layout(page, "sheet")
    expect_closed(salon)

    page.set_viewport_size({"width": 1280, "height": 720})
    expect_layout(page, "column")
    expect(salon).to_be_visible()
    expect(salon).not_to_have_attribute("hidden", "")
