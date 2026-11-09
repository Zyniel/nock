"""Viewport AC-10: my selection beside a hyphen edge, and the tap and letters.

On the mocked room of `tests/spec042_harness.py`, desktop context, FX-01 with
`VI-DE` and `NA-VAL`. The tests read what the page paints, decoded from
screenshots by `tests/viewport_harness.py`, against `specs/_design/cells.md`
« Hyphen edges ».

Choices where the spec leaves room:

- My selection border: the rows of its top and bottom sides (2 px at each
  end of the right side) belong to those sides and are not read as the dashed
  side; its three other sides are read 3 px away from the corners. Rule 5's
  "whatever the state of the two cells" also reads the band with my selected
  cell after the edge ((2, 3), and (2, 1) below `NA-VAL`), where the line's
  pixel is in the cell before, and on the down hyphen with (1, 1) selected.
- The tap and the letters: the same tap and keys on FX-01 as published give
  the same cells and letters.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import grid_view
from spec042_harness import (
    NAVY,
    SELECTED,
    WHITE,
    WORD,
    Rgb,
    cell_at,
    tap,
)
from viewport_harness import (
    HYPHEN,
    MEDIUM_SIDES,
    MEDIUM_WINDOW,
    NAVAL_EDGE,
    VIDE_EDGE,
    Cell,
    EdgeReading,
    Run,
    Side,
    dash_thickness,
    expected_runs,
    grid_picture,
    open_fx01,
    read_edge,
    require_side,
    run_problems,
    runs_of,
    thickness_offsets,
)
from viewport_harness import hyphen_grid as hyphen_grid

CATALOGUE_KIND = "published_force_1"


# ---- AC-10: my selection border beside the hyphen ---------------------------------

BORDER_PX = 2
CORNER_PX = 3


def open_selected_vide(page: Page, base_url: str, grid: Grid) -> None:
    """FX-01 with hyphens at 700 by 400, (2, 2) tapped: my cell, VIDE my word."""
    open_fx01(page, base_url, grid_view(grid), MEDIUM_WINDOW)
    require_side(page, VIDE_EDGE, MEDIUM_SIDES)
    tap(page, *VIDE_EDGE)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-direction", "across")


class BorderCase(NamedTuple):
    """My selected cell beside a hyphen edge, and where the edge's pixels lie.

    Attributes:
        tapped: My selected cell, selected across by a tap.
        cell: The cell whose right or bottom edge is the hyphen edge.
        side: That edge.
        reference: The cell whose plain line finds the edge's line pixel.
        band: The offsets of the dashed band: the border's 2 px and the line's
            pixel.
        beside: The offset of the next pixel in the other cell of the edge.
        background: That cell's background.
    """

    tapped: Cell
    cell: Cell
    side: Side
    reference: Cell
    band: tuple[int, ...]
    beside: int
    background: Rgb


BEFORE_BAND = (-2, -1, 0)
AFTER_BAND = (0, 1, 2)

BORDER_CASES = {
    "before-vi-de": BorderCase(
        VIDE_EDGE, VIDE_EDGE, Side.RIGHT, (3, 2), BEFORE_BAND, 1, WORD
    ),
    "after-vi-de": BorderCase(
        (2, 3), VIDE_EDGE, Side.RIGHT, (3, 2), AFTER_BAND, -1, WORD
    ),
    "above-na-val": BorderCase(
        NAVAL_EDGE, NAVAL_EDGE, Side.BOTTOM, (1, 2), BEFORE_BAND, 1, WHITE
    ),
    "below-na-val": BorderCase(
        (2, 1), NAVAL_EDGE, Side.BOTTOM, (1, 2), AFTER_BAND, -1, WHITE
    ),
}


def band_dashes(reading: EdgeReading) -> list[Run]:
    """The navy dashes of the band on the line's pixel.

    A navy run that lies wholly in the rows of the border's top and bottom
    sides (`BORDER_PX` at each end) belongs to those sides and is left out.
    """
    dashes: list[Run] = []
    for start, end in runs_of(reading.inner(0), NAVY):
        in_first_side = end <= BORDER_PX
        in_last_side = start >= reading.length - BORDER_PX
        if not in_first_side and not in_last_side:
            dashes.append((start, end))
    return dashes


def border_problems(reading: EdgeReading, case: BorderCase) -> list[str]:
    """How the band and the pixels beside it differ from « Hyphen edges ».

    The line's pixel holds the formula's dashes in navy; every offset of the
    band holds the same dashes, with gaps in the selected blue, between the rows
    of the border's top and bottom sides. The next pixel in the other cell is
    that cell's background, with the same dashes in hyphen grey when the
    hyphen's thickness reaches it.
    """
    dashes = band_dashes(reading)
    problems = run_problems(dashes, expected_runs(reading.cell_side))
    dash_rows: set[int] = set()
    for start, end in dashes:
        dash_rows.update(range(start, end))
    for offset in case.band:
        pixels = reading.inner(offset)
        for index in range(BORDER_PX, reading.length - BORDER_PX):
            expected = NAVY if index in dash_rows else SELECTED
            if pixels[index] != expected:
                problems.append(f"offset {offset}, pixel {index}: {pixels[index]}")
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    for index, colour in enumerate(reading.inner(case.beside)):
        expected = case.background
        if case.beside in covered and index in dash_rows:
            expected = HYPHEN
        if colour != expected:
            problems.append(f"offset {case.beside}, pixel {index}: {colour}")
    return problems


@pytest.mark.parametrize("case_name", list(BORDER_CASES))
def test_ac10_my_selected_cells_border_is_dashed_navy_on_its_hyphen_side(
    page: Page, live_server: str, hyphen_grid: Grid, case_name: str
) -> None:
    case = BORDER_CASES[case_name]
    open_fx01(page, live_server, grid_view(hyphen_grid), MEDIUM_WINDOW)
    require_side(page, case.cell, MEDIUM_SIDES)
    tap(page, *case.tapped)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-direction", "across")

    picture = grid_picture(page)
    reading = read_edge(page, picture, case.cell, case.side, case.reference)

    assert border_problems(reading, case) == []


def solid_problems(reading: EdgeReading, offsets: tuple[int, ...]) -> list[str]:
    """Pixels of a border side that are not navy, 3 px away from its corners."""
    problems: list[str] = []
    for offset in offsets:
        pixels = reading.inner(offset)
        for index in range(CORNER_PX, reading.length - CORNER_PX):
            if pixels[index] != NAVY:
                problems.append(f"offset {offset}, pixel {index}: {pixels[index]}")
    return problems


def test_ac10_my_selected_cells_three_other_sides_stay_solid_navy(
    page: Page, live_server: str, hyphen_grid: Grid
) -> None:
    open_selected_vide(page, live_server, hyphen_grid)
    picture = grid_picture(page)

    left_side = read_edge(page, picture, (2, 1), Side.RIGHT, (3, 1))
    top_side = read_edge(page, picture, (1, 2), Side.BOTTOM, (1, 3))
    bottom_side = read_edge(page, picture, VIDE_EDGE, Side.BOTTOM, (2, 1))

    assert solid_problems(left_side, (1, 2)) == []
    assert solid_problems(top_side, (1, 2)) == []
    assert solid_problems(bottom_side, (-2, -1)) == []


VIDE_CELLS: list[Cell] = [(2, 1), (2, 2), (2, 3), (2, 4)]
# Board rule 10 from (2, 2): V and I fill (2, 2) and (2, 3), D then E the last cell.
TYPED_LETTERS = ["", "V", "I", "E"]


@pytest.mark.parametrize("grid_name", ["vi-de-na-val", "published"])
def test_ac10_a_tap_selects_vides_four_cells_and_letters_fill_them_as_published(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    hyphen_grid: Grid,
    grid_name: str,
) -> None:
    grid = hyphen_grid if grid_name == "vi-de-na-val" else fx01_grid
    open_fx01(page, live_server, grid_view(grid), MEDIUM_WINDOW)

    tap(page, *VIDE_EDGE)

    expect(page.locator('[data-testid="cell"][data-in-word="true"]')).to_have_count(4)
    for cell in VIDE_CELLS:
        expect(cell_at(page, *cell)).to_have_attribute("data-in-word", "true")
    for key in "vide":
        page.keyboard.press(key)
    for cell, letter in zip(VIDE_CELLS, TYPED_LETTERS, strict=True):
        expect(cell_at(page, *cell)).to_have_attribute("data-letter", letter)
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-selected-column", "4")
