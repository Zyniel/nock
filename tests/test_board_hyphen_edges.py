"""Tests of board AC-21 and AC-22: the dashed edge of a compound word's hyphen.

On the mocked room of `tests/spec042_harness.py`, desktop context, FX-01 with
`VI-DE` and `NA-VAL` (the right edge of (2, 2) and the bottom edge of (1, 1) are
hyphen edges) and FX-02 with `ORE-ILLE` (the right edge of (1, 4)). The tests
read what the page paints, decoded from screenshots by `tests/board_harness.py`,
against `specs/_design/cells.md` « Hyphen edges ».

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
  rule grey across the dashes' thickness. Rule 20's "whatever the state of the
  two cells" includes a cell with both marks: FX-01 with `TA-MIS` and `NA-VAL`,
  where both edges of (1, 1) end at its bottom right corner pixel.
- "The same in every state": the same look by the formula for the cell's
  current size. Before and after the state, the dashes match the formula at the
  side read then (Auteurs mode shows its legend under the grid, which refits it
  from about 57.4 to 49.8 px, 7 dashes to 6); every pixel row (or column) of the
  thickness holds the same dashes; while the side is unchanged, the hyphen grey
  pixels are exactly those of before. Each other pixel the dashes cover is the
  background of one of the two cells (read 4 px from the line), never the rule
  grey. The flash is read in the screenshot that shows its colour.
- The revealed notch over a down hyphen: at 56 px the dashes (2 px, the line's
  pixel and the next one down) do not reach into (1, 1), so the notch is read on
  72 px cells and more (1024 by 768, about 130 px), where the dashes are 3 px
  and their top pixel row is the bottom row of (1, 1).
- AC-22, my selection border: the rows of its top and bottom sides (2 px at each
  end of the right side) belong to those sides and are not read as the dashed
  side; its three other sides are read 3 px away from the corners. Rule 20's
  "whatever the state of the two cells" also reads the band with my selected
  cell after the edge ((2, 3), and (2, 1) below `NA-VAL`), where the line's
  pixel is in the cell before, and on the down hyphen with (1, 1) selected.
- AC-22, the tap and the letters: the same tap and keys on FX-01 as published
  give the same cells and letters.
"""

from __future__ import annotations

import json
from typing import NamedTuple

import pytest
from playwright.sync_api import Page, ViewportSize, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from board_harness import (
    HYPHEN,
    INTERIOR_OFFSET,
    EdgeReading,
    Run,
    Side,
    dash_count,
    dash_thickness,
    expected_runs,
    grid_picture,
    hyphen_positions,
    plain_edge_problems,
    read_edge,
    run_problems,
    runs_of,
    thickness_offsets,
)
from grids_harness import FX01_HYPHENS, grid_with_answers
from nock.catalogue import Catalogue
from nock.grid import Grid, LetterCell
from nock.protocol import (
    CellRef,
    CheckResult,
    Direction,
    GridView,
    WordTarget,
    grid_view,
)
from spec019_harness import (
    MockRoomSocket,
    cell_locked_frame,
    letter_changed_frame,
    turn_switch_on,
)
from spec042_harness import (
    CELL_SELECTOR,
    NAVY,
    RULE,
    SELECTED,
    WAIT_TIMEOUT_MS,
    WHITE,
    WORD,
    ChangeList,
    Rgb,
    box_of,
    cell_at,
    flash_composite,
    fx01_view,
    make_catalogue,
    me,
    open_room,
    player,
    selection_frame,
    show_snapshot,
    snapshot_frame,
    tap,
)

# ---- Fixtures -----------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def hyphen_grid(fx01_text: str) -> Grid:
    """FX-01 with `VI-DE` and `NA-VAL`."""
    return grid_with_answers(fx01_text, FX01_HYPHENS)


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


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Windows and cell sizes -------------------------------------------------------

MEDIUM_WINDOW = ViewportSize(width=700, height=400)  # FX-01 cells of about 57.4 px
SMALL_WINDOW = ViewportSize(width=568, height=320)  # FX-02 cells of about 12.1 px
LARGE_WINDOW = ViewportSize(width=1024, height=768)  # FX-01 cells of about 130.6 px

Cell = tuple[int, int]
SideRange = tuple[float, float]
MEDIUM_SIDES: SideRange = (50.0, 64.0)
SMALL_SIDES: SideRange = (10.0, 20.0)
LARGE_SIDES: SideRange = (72.0, 200.0)

VIDE_EDGE: Cell = (2, 2)  # its right edge
NAVAL_EDGE: Cell = (1, 1)  # its bottom edge
TAMIS_EDGE: Cell = (1, 1)  # its right edge
FX02_EDGE: Cell = (1, 4)  # its right edge


# True once the cell's side is fractional and in [low, high).
SIDE_SCRIPT = """
([selector, low, high]) => {
  const cell = document.querySelector(selector);
  if (cell === null) {
    return false;
  }
  const side = cell.getBoundingClientRect().width;
  return low <= side && side < high && side !== Math.trunc(side);
}
"""


def require_side(page: Page, cell: Cell, sides: SideRange) -> float:
    """The cell's side, once it is fractional and in `sides`.

    The grid fits its area after the snapshot shows, so the side is polled; the
    test fails, naming the side, when it is not such a side in time.
    """
    row, column = cell
    low, high = sides
    selector = CELL_SELECTOR.format(row=row, column=column)
    try:
        page.wait_for_function(
            SIDE_SCRIPT, arg=[selector, low, high], timeout=WAIT_TIMEOUT_MS
        )
    except PlaywrightTimeoutError:
        side = box_of(cell_at(page, *cell)).width
        pytest.fail(f"cells of {side} px, expected a fractional side in {sides}")
    return box_of(cell_at(page, *cell)).width


def open_fx01(page: Page, base_url: str, view: GridView, window: ViewportSize) -> None:
    """Open FX-01's room at `window`, `p1` alone, on a view."""
    page.set_viewport_size(window)
    open_room(page, base_url, view, [me()])


# ---- AC-21: count, ends, corners, thickness and colour ------------------------------


class EdgeCase(NamedTuple):
    """One hyphen edge of AC-21 and how to open its page."""

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
def test_ac21_a_hyphen_edge_has_the_dashes_of_the_design(
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
def test_ac21_a_hyphen_edge_leaves_its_corners_open_and_the_crossing_lines_plain(
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
def test_ac21_a_hyphen_edge_has_its_thickness_in_hyphen_grey_none_blended(
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


# ---- AC-21: every other edge is the plain line ---------------------------------------


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
def test_ac21_every_other_edge_between_two_letters_is_the_plain_line(
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


# ---- AC-21: the same dashes in every state ----------------------------------------

STATE_SEQ = 5
P2_COLOUR = 5  # Magenta, the darkest flash


def state_view(grid: Grid) -> GridView:
    """FX-01 with `X` by `p1` at (2, 2) and `D` by `p2` at (2, 3)."""
    changes: ChangeList = [
        (2, 2, {"letter": "X", "author": "p1"}),
        (2, 3, {"letter": "D", "author": "p2"}),
    ]
    return fx01_view(grid, changes)


def read_vide_edge(page: Page) -> EdgeReading:
    return read_edge(page, grid_picture(page), VIDE_EDGE, Side.RIGHT, (3, 2))


FLASH_SCRIPT = """
() => {
  const cell = document.querySelector(
    '[data-testid="cell"][data-row="2"][data-column="2"]'
  );
  return cell !== null && cell.getAttribute('data-flash') !== '';
}
"""


def apply_state(page: Page, mock: MockRoomSocket, state: str) -> None:
    """Put the room in one state of AC-21, and wait until the page shows it."""
    mock_send = mock.send
    vide_cell = cell_at(page, *VIDE_EDGE)
    if state == "tint":
        mock_send(selection_frame("p2", 2, 1, Direction.ACROSS))
        expect(vide_cell).to_have_attribute("data-tinted-by", "p2")
    elif state == "locked":
        mock_send(cell_locked_frame(STATE_SEQ + 1, 2, 2, "I", revealed=False))
        expect(vide_cell).to_have_attribute("data-locked", "true")
    elif state == "wrong":
        result = CheckResult(
            seq=STATE_SEQ + 1,
            player_id="p1",
            target=WordTarget(row=2, column=0, clue_index=0),
            correct=(),
            wrong=(CellRef(row=2, column=2),),
        )
        mock_send(result.model_dump_json())
        expect(vide_cell).to_have_attribute("data-wrong", "true")
    elif state == "flash":
        mock_send(letter_changed_frame(STATE_SEQ + 1, 2, 2, "Y", "p2"))
        page.wait_for_function(FLASH_SCRIPT, timeout=WAIT_TIMEOUT_MS)
    elif state == "authors":
        turn_switch_on(page)
    else:
        raise ValueError(f"unknown state {state!r}")


def close_to(colour: Rgb, expected: tuple[float, float, float]) -> bool:
    """Each channel within 2 of the expected one."""
    for channel, wanted in zip(colour, expected, strict=True):
        if abs(channel - wanted) > 2:
            return False
    return True


def gap_problems(reading: EdgeReading) -> list[str]:
    """Pixels the dashes cover that are neither hyphen grey nor a cell's background.

    A cell's background is read 4 px from the line, in the same row (or column).
    """
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    before_cell = reading.inner(-INTERIOR_OFFSET)
    after_cell = reading.inner(INTERIOR_OFFSET)
    problems: list[str] = []
    for offset in covered:
        for index, colour in enumerate(reading.inner(offset)):
            backgrounds: list[Rgb] = []
            if offset <= 0:
                backgrounds.append(before_cell[index])
            if offset >= 0:
                backgrounds.append(after_cell[index])
            if colour != HYPHEN and (colour == RULE or colour not in backgrounds):
                problems.append(f"offset {offset}, pixel {index}: {colour}")
    return problems


def dash_problems(reading: EdgeReading) -> list[str]:
    """How an edge's dashes differ from the formula at the side it was read at.

    Each offset of the thickness holds the formula's dashes in hyphen grey, the
    same at every offset, and no offset outside the thickness holds any.
    """
    covered = thickness_offsets(dash_thickness(reading.cell_side))
    expected = expected_runs(reading.cell_side)
    dashes = hyphen_positions(reading)
    problems: list[str] = []
    for offset in covered:
        for problem in run_problems(runs_of(reading.inner(offset), HYPHEN), expected):
            problems.append(f"offset {offset}: {problem}")
        if dashes[offset] != dashes[0]:
            problems.append(f"offset {offset}: dashes {dashes[offset]}")
    for offset, indexes in dashes.items():
        if offset not in covered and indexes:
            problems.append(f"offset {offset} outside the thickness: {indexes}")
    return problems


@pytest.mark.parametrize("state", ["tint", "locked", "wrong", "flash", "authors"])
def test_ac21_the_dashes_read_the_same_in_every_state_of_the_two_cells(
    page: Page, live_server: str, hyphen_grid: Grid, state: str
) -> None:
    page.set_viewport_size(MEDIUM_WINDOW)
    players = [me(), player("p2", P2_COLOUR)]
    mock = open_room(page, live_server, state_view(hyphen_grid), players)
    require_side(page, VIDE_EDGE, MEDIUM_SIDES)
    before = read_vide_edge(page)
    assert len(runs_of(before.inner(0), HYPHEN)) == dash_count(before.cell_side)

    apply_state(page, mock, state)
    after = read_vide_edge(page)

    if state == "flash":
        inside = after.inner(-INTERIOR_OFFSET)[after.length // 2]
        assert close_to(inside, flash_composite(P2_COLOUR)), "read after the flash"
    assert dash_problems(before) == []
    assert dash_problems(after) == []
    if after.cell_side == before.cell_side:
        assert hyphen_positions(after) == hyphen_positions(before)
    assert gap_problems(after) == []


# ---- AC-21: the revealed notch over a down hyphen ---------------------------------

NOTCH_MARGIN_PX = 3


def test_ac21_a_revealed_cell_puts_its_notch_over_the_down_hyphens_dashes(
    page: Page, live_server: str, hyphen_grid: Grid
) -> None:
    changes: ChangeList = [
        (1, 1, {"letter": "A", "author": None, "locked": True, "revealed": True})
    ]
    open_fx01(page, live_server, fx01_view(hyphen_grid, changes), LARGE_WINDOW)
    side = require_side(page, NAVAL_EDGE, LARGE_SIDES)
    expect(cell_at(page, *NAVAL_EDGE).get_by_test_id("reveal-mark")).to_have_count(1)
    notch = box_of(cell_at(page, *NAVAL_EDGE).get_by_test_id("reveal-mark"))

    reading = read_edge(page, grid_picture(page), NAVAL_EDGE, Side.BOTTOM, (1, 2))

    assert dash_thickness(side) == 3
    dashes = hyphen_positions(reading)
    assert run_problems(runs_of(reading.inner(0), HYPHEN), expected_runs(side)) == []
    assert dashes[1] == dashes[0]
    under_notch: list[int] = []
    beside_notch: list[int] = []
    for index in dashes[0]:
        x = reading.first_inner + index
        if notch.left + NOTCH_MARGIN_PX <= x <= notch.right - NOTCH_MARGIN_PX:
            under_notch.append(index)
        elif x < notch.left - 1 or x > notch.right + 1:
            beside_notch.append(index)
    assert under_notch, (dashes[0], notch)
    in_the_cell = reading.inner(-1)
    for index in under_notch:
        assert in_the_cell[index] != HYPHEN, f"pixel {index} shows a dash"
    for index in beside_notch:
        assert in_the_cell[index] == HYPHEN, f"pixel {index}: {in_the_cell[index]}"


# ---- AC-22: my selection border beside the hyphen ---------------------------------

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
def test_ac22_my_selected_cells_border_is_dashed_navy_on_its_hyphen_side(
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


def test_ac22_my_selected_cells_three_other_sides_stay_solid_navy(
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
# Rule 10 from (2, 2): V and I fill (2, 2) and (2, 3), D then E the last cell.
TYPED_LETTERS = ["", "V", "I", "E"]


@pytest.mark.parametrize("grid_name", ["vi-de-na-val", "published"])
def test_ac22_a_tap_selects_vides_four_cells_and_letters_fill_them_as_published(
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
