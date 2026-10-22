"""Tests of spec 035: crowded cells (AC-11).

Spec 042 (the design's grid cells) refines AC-11: the "+N" rule of 2026-10-13,
with initials in as many corners as fit and a `+k` label, is replaced by the
design's corner triangles, by order of arrival, at most four, with nothing that
says "+k". The rules are spec 042's "Other players on a cell". In every case each
`remote-selection` lies inside the cell's box (1 px tolerance) with computed
`visibility` `visible`, any two on one cell intersect by at most 1 px in width or
in height, and no cursor holds text. Each case first reads the side `c` of the
cell and fails, reporting it, when `c` is not in the expected tier.

The mocked room, the readers and the switch are spec 042's
(`tests/spec042_harness.py`); the scans are spec 035's.

Choices where the spec leaves room:

- "Joined in that order": the snapshot's players are in that order, each already
  on the cell, so they arrive in roster order (spec 042's snapshot rule).
- FX-02's cell is its first letter cell in row-major order; its players select it
  `down`, the direction of the one word that holds it.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, PlayerView, grid_view
from spec019_harness import MockRoomSocket
from spec024_harness import contrast_problems, language_data, language_problems
from spec042_harness import (
    ACCESS_SWITCH,
    CORNERS,
    DISPLAY_NICKNAMES,
    Box,
    Reading,
    cell_at,
    click_switch,
    corners_on,
    fx01_view,
    letter_cells_of,
    make_catalogue,
    me,
    open_room,
    overlap_px,
    player,
    read_cursors,
    selecting,
    selection_frame,
    to_box,
)

# ---- Fixtures: thin wrappers around the harnesses ----------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers ---------------------------------------------------------------------

EPSILON = 1.0
LARGE_TIER_MIN_PX = 44.0
SMALL_TIER_MIN_PX = 20.0
FX01_CELL = (2, 2)
FIVE_ON_FX01 = {
    "p2": "top-left",
    "p3": "top-right",
    "p4": "bottom-right",
    "p5": "bottom-left",
}


def players_on(
    row: int, column: int, direction: Direction, count: int
) -> list[PlayerView]:
    """`p1`, then `count` players from `p2` (colours 1 on) all on (row, column)."""
    on_cell = selecting(row, column, direction)
    players = [me()]
    for number in range(2, 2 + count):
        players.append(player(f"p{number}", number - 1, selection=on_cell))
    return players


def cursor_layout_problems(cell: Box, cursors: list[Reading]) -> list[str]:
    """Inside the cell, visible, no text, pairwise disjoint (1 px)."""
    problems: list[str] = []
    for cursor in cursors:
        name = str(cursor["playerId"])
        box = to_box(cursor["box"])
        inside = (
            box.left >= cell.left - EPSILON
            and box.top >= cell.top - EPSILON
            and box.right <= cell.right + EPSILON
            and box.bottom <= cell.bottom + EPSILON
        )
        if not inside:
            problems.append(f"{name}: {box} outside the cell {cell}")
        if cursor["visibility"] != "visible":
            problems.append(f"{name}: visibility {cursor['visibility']!r}")
        if cursor["text"] != "":
            problems.append(f"{name}: text {cursor['text']!r}")
    for index, first in enumerate(cursors):
        for second in cursors[index + 1 :]:
            overlap = overlap_px(to_box(first["box"]), to_box(second["box"]))
            if overlap > EPSILON:
                problems.append(
                    f"{first['playerId']} and {second['playerId']} overlap by {overlap}"
                )
    return problems


def check_tier(cell: Box, low: float | None, high: float | None) -> None:
    """Fail, reporting the cell's side, when it is outside [low, high)."""
    side = cell.width
    if (low is not None and side < low) or (high is not None and side >= high):
        pytest.fail(
            f"the cell is {side:.2f} px, outside [{low}, {high}): revisit AC-11"
        )


def four_corners_problems(
    page: Page, row: int, column: int, ids: list[str]
) -> list[str]:
    """The cell holds exactly the cursors of `ids`, one in each corner."""
    corners = corners_on(page, row, column)
    problems: list[str] = []
    if sorted(corners) != sorted(ids):
        problems.append(f"cursors {sorted(corners)}, expected {sorted(ids)}")
    if sorted(str(corner) for corner in corners.values()) != sorted(CORNERS):
        problems.append(f"corners {corners}")
    return problems


# ---- FX-01, large cells ------------------------------------------------------------


def open_fx01_five(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    players = players_on(*FX01_CELL, Direction.ACROSS, 5)
    mock = open_room(page, base_url, fx01_view(grid), players)
    expect(cell_at(page, *FX01_CELL).get_by_test_id("remote-selection")).to_have_count(
        4
    )
    return mock


def test_ac11_a_large_cell_shows_four_cursors_by_order_of_arrival(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01_five(page, live_server, fx01_grid)

    cell, cursors = read_cursors(page, *FX01_CELL)

    check_tier(cell, LARGE_TIER_MIN_PX, None)
    assert corners_on(page, *FX01_CELL) == FIVE_ON_FX01
    assert cursor_layout_problems(cell, cursors) == []


def test_ac11_a_corner_freed_on_a_large_cell_goes_to_the_player_who_waited(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01_five(page, live_server, fx01_grid)

    mock.send(selection_frame("p3", 3, 1, Direction.ACROSS))

    p3 = cell_at(page, 3, 1).locator(
        '[data-testid="remote-selection"][data-player-id="p3"]'
    )
    expect(p3).to_have_count(1)
    assert corners_on(page, *FX01_CELL) == {
        "p2": "top-left",
        "p6": "top-right",
        "p4": "bottom-right",
        "p5": "bottom-left",
    }
    assert corners_on(page, 3, 1) == {"p3": "top-left"}
    cell, cursors = read_cursors(page, *FX01_CELL)
    assert cursor_layout_problems(cell, cursors) == []


# ---- FX-02, small and tiny cells ---------------------------------------------


def open_fx02(
    page: Page, base_url: str, grid: Grid, size: tuple[int, int], count: int
) -> tuple[int, int]:
    """FX-02 at `size` with `count` players from `p2` on its first letter cell."""
    page.set_viewport_size({"width": size[0], "height": size[1]})
    row, column = letter_cells_of(grid)[0]
    open_room(
        page, base_url, grid_view(grid), players_on(row, column, Direction.DOWN, count)
    )
    return (row, column)


@pytest.mark.parametrize("access", [False, True], ids=["access-off", "access-on"])
def test_ac11_a_small_cell_shows_four_of_seven_cursors_one_per_corner(
    page: Page, live_server: str, fx02_grid: Grid, access: bool
) -> None:
    row, column = open_fx02(page, live_server, fx02_grid, (360, 740), 7)
    if access:
        click_switch(page, ACCESS_SWITCH, "true")

    cell, cursors = read_cursors(page, row, column)

    check_tier(cell, SMALL_TIER_MIN_PX, LARGE_TIER_MIN_PX)
    assert four_corners_problems(page, row, column, ["p2", "p3", "p4", "p5"]) == []
    assert cursor_layout_problems(cell, cursors) == []


def test_ac11_a_tiny_cell_shows_four_cursors_one_per_corner(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    row, column = open_fx02(page, live_server, fx02_grid, (568, 320), 4)

    cell, cursors = read_cursors(page, row, column)

    check_tier(cell, None, SMALL_TIER_MIN_PX)
    assert four_corners_problems(page, row, column, ["p2", "p3", "p4", "p5"]) == []
    assert cursor_layout_problems(cell, cursors) == []


# ---- Language and contrast with five cursors -----------------------------------


@pytest.mark.parametrize("access", [False, True], ids=["access-off", "access-on"])
def test_ac11_the_language_scan_finds_no_offender_with_five_cursors(
    page: Page, live_server: str, fx01_grid: Grid, access: bool
) -> None:
    open_fx01_five(page, live_server, fx01_grid)
    if access:
        click_switch(page, ACCESS_SWITCH, "true")

    data = language_data(live_server, DISPLAY_NICKNAMES)

    assert language_problems(page, data) == []


@pytest.mark.parametrize("access", [False, True], ids=["access-off", "access-on"])
def test_ac11_the_contrast_scan_finds_no_offender_with_five_cursors(
    page: Page, live_server: str, fx01_grid: Grid, access: bool
) -> None:
    open_fx01_five(page, live_server, fx01_grid)
    if access:
        click_switch(page, ACCESS_SWITCH, "true")

    assert contrast_problems(page) == []
