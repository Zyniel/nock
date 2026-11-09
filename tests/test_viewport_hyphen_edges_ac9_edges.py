"""Viewport AC-9: the dashed edge of a compound word's hyphen, edge by edge.

On the mocked room of `tests/spec042_harness.py`, desktop context, FX-01 with
`VI-DE` and `NA-VAL` (the right edge of (2, 2) and the bottom edge of (1, 1) are
hyphen edges) and FX-02 with `ORE-ILLE` (the right edge of (1, 4)). The tests
read what the page paints, decoded from screenshots by `tests/viewport_harness.py`,
against `specs/_design/cells.md` « Hyphen edges ». This file reads the edge at
rest (no one on it): its dashes, its corners, its thickness and colour, and that
every other edge between two letters is the plain line. The edge in each state
of the cells and under a revealed notch is in
`test_viewport_hyphen_edges_ac9_states.py`.

Choices where the spec leaves room:

- "About 56 px": FX-01 at 700 by 400, whose cells are about 57.4 px, a
  fractional size with fractional positions. "At 568 by 320, at 18 px": FX-02 at
  568 by 320 in a desktop context has cells of about 12.1 px, not 18; the test
  keeps the window the criterion names, where the section gives the same 1 px
  and 3 dashes as at 18 px. The tests fail, naming the size, when a window no
  longer gives such cells.
- Dash ends: each within 1 px of the formula, which reads the fractional cell
  side while the pixels count whole lines. "On a whole pixel": every pixel the
  dashes cover is `--nock-hyphen` or the background, none blended.
- The crossing grid lines stay plain: their pixels at the ends of the edge are
  rule grey across the dashes' thickness where the crossing line is plain. At
  about 57 px the thickness (the line's pixel and the next one) reaches only
  plain crossing lines, even at the bottom right corner pixel of (1, 1) in FX-01
  with `TA-MIS` and `NA-VAL`, where both its edges end; rule 5's "whatever the
  state of the two cells" includes that cell with both marks. Where the crossing
  line is itself a hyphen edge, its pixels are those of AC-21.
"""

from __future__ import annotations

import json
from typing import NamedTuple

import pytest
from playwright.sync_api import Page, ViewportSize

from grids_harness import grid_with_answers
from nock.grid import Grid, LetterCell
from nock.protocol import grid_view
from spec042_harness import (
    RULE,
    WHITE,
    me,
    open_room,
    show_snapshot,
    snapshot_frame,
)
from viewport_harness import (
    FX02_EDGE,
    HYPHEN,
    MEDIUM_SIDES,
    MEDIUM_WINDOW,
    NAVAL_EDGE,
    SMALL_SIDES,
    SMALL_WINDOW,
    TAMIS_EDGE,
    VIDE_EDGE,
    Cell,
    EdgeReading,
    Side,
    SideRange,
    dash_count,
    dash_thickness,
    expected_runs,
    grid_picture,
    hyphen_positions,
    plain_edge_problems,
    read_edge,
    require_side,
    run_problems,
    runs_of,
    thickness_offsets,
)
from viewport_harness import hyphen_grid as hyphen_grid

CATALOGUE_KIND = "published_force_1"


# ---- Fixtures ------------------------------------------------------------


@pytest.fixture
def fx02_hyphen_grid(fx02_text: str) -> Grid:
    """FX-02 with one hyphen: `ORE-ILLE` across from (1, 2), after (1, 4)."""
    return grid_with_answers(fx02_text, {"OREILLE": "ORE-ILLE"})


@pytest.fixture
def both_marks_grid(fx01_text: str) -> Grid:
    """FX-01 with `TA-MIS` and `NA-VAL`: (1, 1) has both marks."""
    return grid_with_answers(fx01_text, {"TAMIS": "TA-MIS", "NAVAL": "NA-VAL"})


@pytest.fixture
def case_grids(
    hyphen_grid: Grid, fx02_hyphen_grid: Grid, both_marks_grid: Grid
) -> dict[str, Grid]:
    """The grids of the edge cases, by the name a case gives."""
    return {"fx01": hyphen_grid, "fx02": fx02_hyphen_grid, "both": both_marks_grid}


# ---- AC-9: count, ends, corners, thickness and colour ------------------------------


class EdgeCase(NamedTuple):
    """One hyphen edge of AC-9 and how to open its page."""

    grid_name: str
    window: ViewportSize
    sides: SideRange
    cell: Cell
    side: Side
    reference: Cell


EDGE_CASES = {
    "vi-de-right-57px": EdgeCase(
        "fx01", MEDIUM_WINDOW, MEDIUM_SIDES, VIDE_EDGE, Side.RIGHT, (3, 2)
    ),
    "na-val-bottom-57px": EdgeCase(
        "fx01", MEDIUM_WINDOW, MEDIUM_SIDES, NAVAL_EDGE, Side.BOTTOM, (1, 2)
    ),
    "fx02-right-12px": EdgeCase(
        "fx02", SMALL_WINDOW, SMALL_SIDES, FX02_EDGE, Side.RIGHT, (7, 4)
    ),
}

# (1, 1) with both marks: its two hyphen edges meet at its bottom right corner,
# the pixel where the crossing lines of both edges end.
CORNER_CASES = EDGE_CASES | {
    "ta-mis-right-beside-na-val": EdgeCase(
        "both", MEDIUM_WINDOW, MEDIUM_SIDES, TAMIS_EDGE, Side.RIGHT, (2, 1)
    ),
    "na-val-bottom-beside-ta-mis": EdgeCase(
        "both", MEDIUM_WINDOW, MEDIUM_SIDES, NAVAL_EDGE, Side.BOTTOM, (1, 2)
    ),
}


def read_case(
    page: Page, base_url: str, case: EdgeCase, grids: dict[str, Grid]
) -> EdgeReading:
    """Open a case's grid, no one on it, and read its hyphen edge."""
    grid = grids[case.grid_name]
    page.set_viewport_size(case.window)
    open_room(page, base_url, grid_view(grid), [me()])
    require_side(page, case.cell, case.sides)
    picture = grid_picture(page)
    return read_edge(page, picture, case.cell, case.side, case.reference)


@pytest.mark.parametrize("case_name", list(EDGE_CASES))
def test_ac9_a_hyphen_edge_has_the_dashes_of_the_design(
    page: Page,
    live_server: str,
    case_grids: dict[str, Grid],
    case_name: str,
) -> None:
    case = EDGE_CASES[case_name]
    reading = read_case(page, live_server, case, case_grids)

    found = runs_of(reading.inner(0), HYPHEN)

    assert len(found) == dash_count(reading.cell_side), found
    assert run_problems(found, expected_runs(reading.cell_side)) == []


@pytest.mark.parametrize("case_name", list(CORNER_CASES))
def test_ac9_a_hyphen_edge_leaves_its_corners_open_and_the_crossing_lines_plain(
    page: Page,
    live_server: str,
    case_grids: dict[str, Grid],
    case_name: str,
) -> None:
    case = CORNER_CASES[case_name]
    reading = read_case(page, live_server, case, case_grids)
    covered = thickness_offsets(dash_thickness(reading.cell_side))

    found = runs_of(reading.inner(0), HYPHEN)

    assert len(found) >= 3, found
    first_start = found[0][0]
    last_end = found[-1][1]
    assert first_start >= 1, f"the first dash touches the crossing line: {found}"
    assert last_end <= reading.length - 1, f"the last dash touches it: {found}"
    for offset in covered:
        assert reading.crossings(offset) == (RULE, RULE), offset


@pytest.mark.parametrize("case_name", list(EDGE_CASES))
def test_ac9_a_hyphen_edge_has_its_thickness_in_hyphen_grey_none_blended(
    page: Page,
    live_server: str,
    case_grids: dict[str, Grid],
    case_name: str,
) -> None:
    case = EDGE_CASES[case_name]
    reading = read_case(page, live_server, case, case_grids)
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    dashes = hyphen_positions(reading)

    assert len(runs_of(reading.inner(0), HYPHEN)) == dash_count(reading.cell_side)
    problems: list[str] = []
    for offset in range(-3, 4):
        for index, colour in enumerate(reading.inner(offset)):
            allowed = (HYPHEN, WHITE) if offset in covered else (WHITE,)
            if colour not in allowed:
                problems.append(f"offset {offset}, pixel {index}: {colour}")
        if offset in covered and dashes[offset] != dashes[0]:
            problems.append(f"offset {offset}: dashes {dashes[offset]}")
    assert problems == []


# ---- AC-9: every other edge is the plain line ---------------------------------------


def letter_edges(grid: Grid) -> list[tuple[Cell, Side]]:
    """Every edge between two letter cells: a right or a bottom edge of a cell."""
    letters: set[Cell] = set()
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            letters.add((cell.row, cell.column))
    edges: list[tuple[Cell, Side]] = []
    for row, column in sorted(letters):
        if (row, column + 1) in letters:
            edges.append(((row, column), Side.RIGHT))
        if (row + 1, column) in letters:
            edges.append(((row, column), Side.BOTTOM))
    return edges


FX01_HYPHEN_EDGES = [(VIDE_EDGE, Side.RIGHT), (NAVAL_EDGE, Side.BOTTOM)]


def without_marks(frame: str) -> str:
    """A snapshot frame whose letter cells hold no `hyphen_*` key at all."""
    data = json.loads(frame)
    for cell in data["grid"]["cells"]:
        cell.pop("hyphen_right", None)
        cell.pop("hyphen_down", None)
    return json.dumps(data)


@pytest.mark.parametrize("grid_name", ["vi-de-na-val", "published", "marks-absent"])
def test_ac9_every_other_edge_between_two_letters_is_the_plain_line(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    hyphen_grid: Grid,
    grid_name: str,
) -> None:
    page.set_viewport_size(MEDIUM_WINDOW)
    shown = fx01_grid if grid_name == "published" else hyphen_grid
    if grid_name == "marks-absent":
        # A snapshot written without the marks follows FX-01's first snapshot.
        mock = open_room(page, live_server, grid_view(fx01_grid), [me()])
        frame = snapshot_frame(grid_view(hyphen_grid), [me()], seq=6)
        show_snapshot(page, mock, without_marks(frame), 6, 25)
    else:
        open_room(page, live_server, grid_view(shown), [me()])
    hyphens = FX01_HYPHEN_EDGES if grid_name == "vi-de-na-val" else []
    picture = grid_picture(page)

    problems: list[str] = []
    checked = 0
    for cell, side in letter_edges(hyphen_grid):
        if (cell, side) in hyphens:
            continue
        reading = read_edge(page, picture, cell, side, cell)
        for problem in plain_edge_problems(reading):
            problems.append(f"{cell} {side}: {problem}")
        checked += 1

    assert checked == 26 - len(hyphens)
    assert problems == []
