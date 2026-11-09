"""Viewport AC-21: the pixels around where two hyphen edges meet.

On the mocked room of `tests/spec042_harness.py`, desktop context, FX-01 with
two hyphens whose edges meet at a crossing of grid lines. The tests read what
the page paints, decoded from screenshots by `tests/viewport_harness.py`, against
`specs/_design/cells.md` « Hyphen edges ».

"Cells of 72 px or more": FX-01 at 1024 by 768, about 130.6 px, where the dashes
are 3 px. The crossing pixel is where each of the two edges, read as AC-9 reads
it, meets its crossing line: the row of one, the column of the other. Each of
the 3 by 3 pixels is exactly rule grey or white.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Page

from grids_harness import grid_with_answers
from nock.protocol import grid_view
from spec042_harness import RULE, WHITE, Rgb
from viewport_harness import (
    LARGE_SIDES,
    LARGE_WINDOW,
    Cell,
    EdgeReading,
    Picture,
    Side,
    dash_thickness,
    grid_picture,
    open_fx01,
    read_edge,
    require_side,
)

CATALOGUE_KIND = "published_force_1"


# ---- AC-21: the pixels around where two hyphen edges meet -------------------------

# The 3 by 3 pixels centred on a crossing pixel, top row first, left to right.
PixelSquare = tuple[tuple[Rgb, Rgb, Rgb], ...]


class MeetingCase(NamedTuple):
    """Two hyphen edges of FX-01 that meet at a crossing of grid lines.

    Attributes:
        answers: FX-01's answers written with their hyphens.
        right_edge: The cell whose right edge is the across hyphen edge, and the
            cell whose plain right line finds that line's pixel.
        right_edge_ends: True when the right edge ends at the crossing, False
            when it starts there.
        bottom_edge: The cell whose bottom edge is the down hyphen edge, and the
            cell whose plain bottom line finds that line's pixel.
        bottom_edge_ends: True when the bottom edge ends at the crossing, False
            when it starts there.
        expected: The 3 by 3 pixels around the crossing pixel.
    """

    answers: dict[str, str]
    right_edge: tuple[Cell, Cell]
    right_edge_ends: bool
    bottom_edge: tuple[Cell, Cell]
    bottom_edge_ends: bool
    expected: PixelSquare


MEETING_CASES = {
    # Both edges of (1, 1) end at its bottom right corner: the centre and the
    # pixels right of it and below it are rule grey.
    "ta-mis-and-na-val-at-the-corner-of-1-1": MeetingCase(
        {"TAMIS": "TA-MIS", "NAVAL": "NA-VAL"},
        ((1, 1), (2, 1)),
        True,
        ((1, 1), (1, 2)),
        True,
        (
            (WHITE, WHITE, WHITE),
            (WHITE, RULE, RULE),
            (WHITE, RULE, WHITE),
        ),
    ),
    # The right edge of (2, 2) ends where the bottom edge of (2, 3) starts: the
    # centre and the pixels left of it and below it are rule grey.
    "vi-de-ends-where-id-es-starts": MeetingCase(
        {"VIDE": "VI-DE", "IDES": "ID-ES"},
        ((2, 2), (3, 2)),
        True,
        ((2, 3), (2, 4)),
        False,
        (
            (WHITE, WHITE, WHITE),
            (RULE, RULE, WHITE),
            (WHITE, RULE, WHITE),
        ),
    ),
}


def crossing_along(reading: EdgeReading, at_end: bool) -> int:
    """The page coordinate along an edge of the crossing line at one of its ends.

    Args:
        reading: The edge, read by `read_edge`.
        at_end: True for the crossing line after the edge's last pixel, False
            for the one before its first pixel.

    Returns:
        A y for a right edge, an x for a bottom edge.
    """
    if at_end:
        return reading.first_inner + reading.length
    return reading.first_inner - 1


def pixels_around(picture: Picture, x: int, y: int) -> PixelSquare:
    """The 3 by 3 pixels centred on (x, y), top row first, left to right."""
    rows: list[tuple[Rgb, Rgb, Rgb]] = []
    for row_y in (y - 1, y, y + 1):
        row = (picture.at(x - 1, row_y), picture.at(x, row_y), picture.at(x + 1, row_y))
        rows.append(row)
    return tuple(rows)


@pytest.mark.parametrize("case_name", list(MEETING_CASES))
def test_ac21_the_pixels_around_where_two_hyphen_edges_meet(
    page: Page, live_server: str, fx01_text: str, case_name: str
) -> None:
    case = MEETING_CASES[case_name]
    grid = grid_with_answers(fx01_text, case.answers)
    open_fx01(page, live_server, grid_view(grid), LARGE_WINDOW)
    right_cell, right_reference = case.right_edge
    bottom_cell, bottom_reference = case.bottom_edge
    side = require_side(page, right_cell, LARGE_SIDES)
    assert dash_thickness(side) == 3
    picture = grid_picture(page)

    right_edge = read_edge(page, picture, right_cell, Side.RIGHT, right_reference)
    bottom_edge = read_edge(page, picture, bottom_cell, Side.BOTTOM, bottom_reference)
    # The right edge meets the crossing's row, the bottom edge its column.
    crossing_y = crossing_along(right_edge, case.right_edge_ends)
    crossing_x = crossing_along(bottom_edge, case.bottom_edge_ends)

    assert pixels_around(picture, crossing_x, crossing_y) == case.expected
