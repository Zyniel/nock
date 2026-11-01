"""Tests of shell AC-21: the grid's focus ring shows over the edge letter cells.

The criterion reads painted pixels: the ring of the grid focused from the
keyboard (2 px navy, offset -3 px, so it lies 1 px to 3 px inside the grid's
edge) must show over the letter cells of the right and bottom edges, which are
positioned and opaque and so are painted after the grid's own outline.

Setup, as the tests of spec 041 AC-7 do it: spec 035's mocked room on FX-01 in
the default 1280 by 720 window (device scale factor 1, so one pixel of a
screenshot is one CSS pixel), then the keyboard `Walker` puts the focus on the
grid. With nothing selected, a Tab on the grid selects the first unfinished word
in clue order (`gameplay/board.md` rule 13): « Passoire fine », (1, 0) across.
No letter is filled, nobody else has a selection and the mouse never moves, so
no letter, cursor or hover covers the samples.

Choices where the spec leaves room:

- "The 3 px inside the grid's edge": the grid is centred and may sit on a
  fractional pixel, so the band is every whole pixel that meets the 3 px inside
  the edge of the grid's box (`getBoundingClientRect`): 3 pixels on a whole
  edge, 4 on a fractional one. Nothing but the ring is navy there: the cells are
  white or the word's blue, the grid lines rule grey, the page outside them
  light.
- "At the middle of the outer side": the one pixel row (right edge) or column
  (bottom edge) that holds the middle of the cell's side.
- "A pixel of the ring's navy": a pixel whose every channel is within
  `NAVY_TOLERANCE` of #1B2F55. A 2 px ring always covers at least one whole
  pixel, painted exactly, but an engine may blend it a little at a fractional
  edge. 12 lets that through and nothing else of the grid: the nearest other
  colour, the ink #14181F of a letter (none is shown here), differs by 54 in
  blue, and the rule grey by more than 90.
- Deterministic pixels: the picture is taken after the fonts load (in
  `open_room`), once no animation or transition runs and the grid's box stays
  the same over two animation frames.
"""

from __future__ import annotations

import math
from typing import NamedTuple

import pytest
from playwright.sync_api import Page, expect

from board_harness import Picture, take_picture
from nock.grid import Grid
from spec035_harness import Walker, build_fx01_grid, open_room
from spec041_harness import NAVY, WAIT_TIMEOUT_MS, Rgb, cell_at
from spec042_harness import Box, box_of

# How far each channel of a ring pixel may be from the navy, after blending.
NAVY_TOLERANCE = 12
# The depth of the band read inside the grid's edge, in CSS px.
BAND_DEPTH_PX = 3.0
LAST_INDEX = 4

# Resolves once the grid's box is the same at two animation frames in a row.
LAYOUT_SETTLED_SCRIPT = """
element => new Promise(resolve => {
  let previous = '';
  function check() {
    const box = element.getBoundingClientRect();
    const current = [box.left, box.top, box.right, box.bottom].join(',');
    if (current === previous) {
      resolve(true);
      return;
    }
    previous = current;
    requestAnimationFrame(check);
  }
  requestAnimationFrame(check);
})
"""

RUNNING_ANIMATIONS_SCRIPT = "() => document.getAnimations().length"

FOCUS_VISIBLE_SCRIPT = "element => element.matches(':focus-visible')"


class Sample(NamedTuple):
    """One sample of AC-21: a cell and the side of the grid's edge it lies on."""

    row: int
    column: int
    side: str


RIGHT_EDGE_SAMPLES = [Sample(row, LAST_INDEX, "right") for row in range(1, 5)]
BOTTOM_EDGE_SAMPLES = [Sample(LAST_INDEX, column, "bottom") for column in range(1, 5)]
SAMPLES = RIGHT_EDGE_SAMPLES + BOTTOM_EDGE_SAMPLES


# ---- Fixtures -----------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


# ---- Helpers ------------------------------------------------------------------------


def focus_grid_with_first_word(page: Page, base_url: str, grid: Grid) -> None:
    """Open FX-01, Tab to the grid, then Tab on it to select (1, 0) across."""
    open_room(page, base_url, grid)
    Walker(page).tab_to("grid")
    page.keyboard.press("Tab")
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-selected-row", "1")
    expect(grid_element).to_have_attribute("data-selected-column", "0")
    expect(grid_element).to_have_attribute("data-direction", "across")
    expect(grid_element).to_be_focused()
    assert grid_element.evaluate(FOCUS_VISIBLE_SCRIPT) is True


def wait_until_still(page: Page) -> None:
    """Wait until no animation runs and the grid's box no longer moves."""
    waited_ms = 0
    while page.evaluate(RUNNING_ANIMATIONS_SCRIPT) != 0:
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("an animation still runs on the page")
        page.wait_for_timeout(50)
        waited_ms += 50
    page.get_by_test_id("grid").evaluate(LAYOUT_SETTLED_SCRIPT)


def band_pixels(picture: Picture, grid_box: Box, cell_box: Box, side: str) -> list[Rgb]:
    """The pixels of the band inside the grid's edge, at the middle of a cell side.

    Args:
        picture: A picture of the grid.
        grid_box: The grid's box.
        cell_box: The box of an edge cell.
        side: "right" or "bottom", the grid's edge the cell lies on.

    Returns:
        The pixels that meet the 3 px inside the edge, outermost last.
    """
    if side == "right":
        edge = grid_box.right
        middle_line = math.floor(cell_box.centre_y)
    else:
        edge = grid_box.bottom
        middle_line = math.floor(cell_box.centre_x)
    first = math.floor(edge - BAND_DEPTH_PX)
    last = math.ceil(edge) - 1
    pixels: list[Rgb] = []
    for position in range(first, last + 1):
        if side == "right":
            pixels.append(picture.at(position, middle_line))
        else:
            pixels.append(picture.at(middle_line, position))
    return pixels


def is_navy(colour: Rgb) -> bool:
    """Whether every channel is within `NAVY_TOLERANCE` of the ring's navy."""
    for channel, navy_channel in zip(colour, NAVY, strict=True):
        if abs(channel - navy_channel) > NAVY_TOLERANCE:
            return False
    return True


# ---- AC-21: the grid's ring shows over the edge letter cells ----------------------


def test_ac21_grid_ring_shows_over_right_and_bottom_letter_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    focus_grid_with_first_word(page, live_server, fx01_grid)
    wait_until_still(page)
    grid_box = box_of(page.get_by_test_id("grid"))
    picture = take_picture(
        page, grid_box.left, grid_box.top, grid_box.right, grid_box.bottom
    )

    samples_without_ring: list[str] = []
    for sample in SAMPLES:
        cell_box = box_of(cell_at(page, sample.row, sample.column))
        pixels = band_pixels(picture, grid_box, cell_box, sample.side)
        navy_pixels = [colour for colour in pixels if is_navy(colour)]
        if not navy_pixels:
            where = f"({sample.row},{sample.column}) {sample.side}"
            samples_without_ring.append(f"{where}: {pixels}")

    assert samples_without_ring == []
