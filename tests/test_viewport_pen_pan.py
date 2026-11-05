"""Tests of viewport AC-20 (rule 3): a pen pans a zoomed grid as a finger does.

A pen tap selects as a finger's does, a pen drag pans the grid and selects no
cell, and a mouse drag never pans.

The room is AC-11's start (`viewport_harness.open_ac11_start`): FX-02 on a touch
phone held upright, zoomed to 2, the viewport at the grid's top-left corner and
nothing selected. At that zoom a FX-02 cell is about 52.75 px, so (1, 2) and
(1, 3) are whole in view.

Choices where the spec leaves room:

- AC-11's start needs a pinch, which goes through the Chrome DevTools Protocol,
  and Playwright has no pen: the pen and the mouse are real pointers of their
  type sent by the protocol's `Input.dispatchMouseEvent` with `pointerType`
  `pen` or `mouse`, the finger by `Input.dispatchTouchEvent`. The tests run in
  Chromium only.
- A tap and a drag start at the centre of the cell. A drag moves 100 px left
  in 10 equal steps, then lifts where it ends.
- "As a finger's drag does": the same tap and drag by a finger give the same
  result, so the finger is a case of the same test.
- "Scrolls the viewport 100 px across": the scroll across goes from 0 to 100,
  to within 1 px (the scroll is snapped to device pixels), and the scroll down
  stays 0. "Leaves (1, 2) selected": a drag that ends with a click on the cell
  under the pointer would select (1, 3) instead.
- A mouse drag selects or not as it will: AC-20 says only that it leaves the
  scroll unchanged.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec042_harness import cell_at
from viewport_harness import (
    Pointer,
    drag_with,
    expect_selected,
    open_ac11_start,
    read_scroll,
    shown_centre,
    tap_with,
    viewport_of,
    wait_two_frames,
)

SCROLL_TOLERANCE_PX = 1.0
DRAG_LEFT = (-100.0, 0.0)
TAPPED_CELL = (1, 2)
DRAG_START_CELL = (1, 3)

# ---- Fixtures ---------------------------------------------------------------------


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Yield spec 019's `open_window(width, height, touch)`; close its pages after."""
    yield from window_opener(browser, browser_name)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    """The FX-02 grid (13 by 17)."""
    return Grid.model_validate_json(fx02_text)


# ---- AC-20: a pen taps and pans as a finger does, a mouse never pans --------------


@pytest.mark.only_browser("chromium")
@pytest.mark.parametrize("pointer", [Pointer.PEN, Pointer.TOUCH])
def test_ac20_a_tap_selects_1_2_and_a_drag_from_1_3_scrolls_100_px_and_keeps_1_2(
    window: OpenWindow, live_server: str, fx02_grid: Grid, pointer: Pointer
) -> None:
    page = open_ac11_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    tapped_point = shown_centre(page, cell_at(page, *TAPPED_CELL))
    drag_start = shown_centre(page, cell_at(page, *DRAG_START_CELL))

    tap_with(page, pointer, tapped_point)

    expect_selected(page, *TAPPED_CELL, "across")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)

    drag_with(page, pointer, drag_start, DRAG_LEFT)

    wait_two_frames(page)
    left_after, top_after = read_scroll(viewport)
    assert left_after == pytest.approx(100.0, abs=SCROLL_TOLERANCE_PX)
    assert top_after == 0.0
    expect_selected(page, *TAPPED_CELL, "across")


@pytest.mark.only_browser("chromium")
def test_ac20_a_mouse_dragged_100_px_left_from_1_3_leaves_the_scroll_unchanged(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_ac11_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    drag_start = shown_centre(page, cell_at(page, *DRAG_START_CELL))

    drag_with(page, Pointer.MOUSE, drag_start, DRAG_LEFT)

    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)
