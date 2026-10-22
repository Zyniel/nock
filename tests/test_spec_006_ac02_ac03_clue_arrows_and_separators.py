"""Tests of spec 006, AC-2 and AC-3: how a clue cell draws its clues.

AC-2: each arrow is drawn on the side of its word's first letter. AC-3: a cell with
two clues shows both, separated by a line. The shared setup is in `spec006_harness`.

Spec 042 (the design's grid cells) refines AC-2: each `clue-arrow` is a child of
its word's first letter cell, found there by its `data-clue-row`,
`data-clue-column` and `data-clue-index`, no longer inside its `clue`; the box
rule is unchanged. Of a → and a ↴ from one cell, the ↴ is in the top half and
the → in the bottom half, whatever their indexes.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import FloatRect, Locator, Page, expect

from nock.grid import Arrow, ClueCell, Grid
from nock.server import RoomRegistry
from spec006_harness import box_of, cell_at, grid_from_text, open_room

# The 8 clues of FX-01 with the arrow side of the spec table:
# (row, column, clue index, arrow, side).
FX01_CLUES = [
    (0, 0, 0, "down_then_right", "bottom"),
    (0, 0, 1, "right_then_down", "right"),
    (0, 2, 0, "down", "bottom"),
    (0, 3, 0, "down", "bottom"),
    (0, 4, 0, "down", "bottom"),
    (2, 0, 0, "right", "right"),
    (3, 0, 0, "right", "right"),
    (4, 0, 0, "right", "right"),
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


# ---- AC-2: each arrow is drawn on the side of its word's first letter ---------


def assert_arrow_on_side(arrow_box: FloatRect, cell_box: FloatRect, side: str) -> None:
    arrow_x = arrow_box["x"] + arrow_box["width"] / 2
    arrow_y = arrow_box["y"] + arrow_box["height"] / 2
    cell_left = cell_box["x"]
    cell_top = cell_box["y"]
    cell_width = cell_box["width"]
    cell_height = cell_box["height"]
    if side == "right":
        assert arrow_x >= cell_left + cell_width / 2 + cell_width / 4
        assert arrow_x <= cell_left + cell_width + cell_width / 2
        assert cell_top <= arrow_y <= cell_top + cell_height
    else:
        assert arrow_y >= cell_top + cell_height / 2 + cell_height / 4
        assert arrow_y <= cell_top + cell_height + cell_height / 2
        assert cell_left <= arrow_x <= cell_left + cell_width


CLUE_ARROW = '[data-testid="clue-arrow"]'


def first_letter_of(row: int, column: int, side: str) -> tuple[int, int]:
    """The word's first letter cell: right of the clue cell, or below it."""
    if side == "right":
        return (row, column + 1)
    return (row + 1, column)


def arrow_of_clue(page: Page, row: int, column: int, index: int) -> Locator:
    """The `clue-arrow` named by its clue's `data-clue-*` (spec 042)."""
    return page.locator(
        f'{CLUE_ARROW}[data-clue-row="{row}"][data-clue-column="{column}"]'
        f'[data-clue-index="{index}"]'
    )


def is_child_of(arrow: Locator, row: int, column: int, side: str) -> bool:
    """Tell whether the arrow's parent is the word's first letter cell."""
    letter_row, letter_column = first_letter_of(row, column, side)
    parent = arrow.evaluate(
        "e => [e.parentElement.getAttribute('data-testid'),"
        " e.parentElement.getAttribute('data-row'),"
        " e.parentElement.getAttribute('data-column'),"
        " e.parentElement.getAttribute('data-type')]"
    )
    return parent == ["cell", str(letter_row), str(letter_column), "letter"]


@pytest.mark.parametrize(
    ("row", "column", "index", "arrow", "side"),
    FX01_CLUES,
    ids=[f"{r}-{c}-clue{i}" for r, c, i, _, _ in FX01_CLUES],
)
def test_ac2_arrow_is_drawn_on_the_side_of_the_first_letter(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    row: int,
    column: int,
    index: int,
    arrow: str,
    side: str,
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, row, column)
    clue = cell.locator(f'[data-testid="clue"][data-clue-index="{index}"]')
    # Spec 042: the arrow is a child of the word's first letter cell.
    clue_arrow = arrow_of_clue(page, row, column, index)

    expect(clue).to_have_attribute("data-arrow", arrow)
    expect(clue_arrow).to_have_count(1)
    assert is_child_of(clue_arrow, row, column, side)
    expect(clue_arrow).to_have_attribute("data-arrow", arrow)
    expect(clue_arrow).to_have_attribute("data-side", side)
    expect(clue_arrow).to_have_attribute("aria-hidden", "true")
    expect(clue_arrow).to_have_text("")
    assert_arrow_on_side(box_of(clue_arrow), box_of(cell), side)


def test_ac2_clue_zero_of_the_double_clue_cell_is_listed_first(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    clues = cell_at(page, 0, 0).get_by_test_id("clue")

    expect(clues).to_have_count(2)
    expect(clues.nth(0)).to_have_attribute("data-clue-index", "0")
    expect(clues.nth(0)).to_have_attribute("data-arrow", "down_then_right")
    expect(clues.nth(1)).to_have_attribute("data-clue-index", "1")
    expect(clues.nth(1)).to_have_attribute("data-arrow", "right_then_down")


def test_ac2_two_arrows_on_the_right_share_the_sides_of_the_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    double_right_cells: list[ClueCell] = []
    for cell in fx02_grid.cells:
        if not isinstance(cell, ClueCell) or len(cell.clues) != 2:
            continue
        arrows = {cell.clues[0].arrow, cell.clues[1].arrow}
        if arrows == {Arrow.RIGHT, Arrow.RIGHT_THEN_DOWN}:
            double_right_cells.append(cell)
    assert len(double_right_cells) >= 2, "FX-02 must hold such cells"

    for cell in double_right_cells:
        cell_locator = cell_at(page, cell.row, cell.column)
        cell_box = box_of(cell_locator)
        for index in (0, 1):
            # Spec 042: the arrow is found by its clue attributes, in the letter
            # cell; the ↴ is in the top half and the → in the bottom half,
            # whatever their indexes.
            clue_arrow = arrow_of_clue(page, cell.row, cell.column, index)
            expect(clue_arrow).to_have_count(1)
            expect(clue_arrow).to_have_attribute("data-side", "right")
            assert is_child_of(clue_arrow, cell.row, cell.column, "right")
            assert_arrow_on_side(box_of(clue_arrow), cell_box, "right")
            arrow_box = box_of(clue_arrow)
            arrow_y = arrow_box["y"] + arrow_box["height"] / 2
            middle = cell_box["y"] + cell_box["height"] / 2
            if cell.clues[index].arrow == Arrow.RIGHT_THEN_DOWN:
                assert cell_box["y"] <= arrow_y <= middle
            else:
                assert middle <= arrow_y <= cell_box["y"] + cell_box["height"]


def test_ac2_every_clue_of_fx02_has_one_arrow_on_the_side_of_its_arrow_type(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    bottom_arrows = page.locator('[data-testid="clue-arrow"][data-side="bottom"]')
    right_arrows = page.locator('[data-testid="clue-arrow"][data-side="right"]')
    expected_bottom = 0
    expected_right = 0
    for cell in fx02_grid.cells:
        if isinstance(cell, ClueCell):
            for clue in cell.clues:
                if clue.arrow in (Arrow.DOWN, Arrow.DOWN_THEN_RIGHT):
                    expected_bottom += 1
                else:
                    expected_right += 1

    expect(bottom_arrows).to_have_count(expected_bottom)
    expect(right_arrows).to_have_count(expected_right)


# ---- AC-3: a two-clue cell shows both clues, separated by a line -------------

SEPARATOR_SCRIPT = """
element => {
  const isClear = colour => colour === 'rgba(0, 0, 0, 0)' || colour === 'transparent';
  const style = getComputedStyle(element);
  const box = element.getBoundingClientRect();
  const topWidth =
    style.borderTopStyle === 'none' ? 0 : parseFloat(style.borderTopWidth);
  const bottomWidth =
    style.borderBottomStyle === 'none' ? 0 : parseFloat(style.borderBottomWidth);
  const lineColours = [];
  if (box.height >= 1 && !isClear(style.backgroundColor)) {
    lineColours.push(style.backgroundColor);
  }
  if (topWidth >= 1) lineColours.push(style.borderTopColor);
  if (bottomWidth >= 1) lineColours.push(style.borderBottomColor);
  let cellBackground = 'rgb(255, 255, 255)';
  let ancestor = element.closest('[data-testid="cell"]');
  while (ancestor) {
    const colour = getComputedStyle(ancestor).backgroundColor;
    if (!isClear(colour)) {
      cellBackground = colour;
      break;
    }
    ancestor = ancestor.parentElement;
  }
  return {
    width: box.width,
    height: box.height,
    thickness: Math.max(box.height, topWidth, bottomWidth),
    lineColours: lineColours,
    cellBackground: cellBackground,
  };
}
"""


def assert_separator_is_a_visible_line(separator: Locator) -> None:
    details = separator.evaluate(SEPARATOR_SCRIPT)
    assert details["width"] > details["height"], "the separator is not horizontal"
    assert details["thickness"] >= 1
    assert len(details["lineColours"]) > 0, "the line has no colour"
    different = [c for c in details["lineColours"] if c != details["cellBackground"]]
    assert different, "the line has the colour of the cell background"


def test_ac3_double_clue_cell_shows_both_clues_in_order(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, 0, 0)

    clues = cell.get_by_test_id("clue")
    expect(clues).to_have_count(2)
    expect(clues.nth(0).get_by_test_id("clue-text")).to_have_text("Passoire fine")
    expect(clues.nth(1).get_by_test_id("clue-text")).to_have_text("De la marine")


def test_ac3_clue_zero_is_stacked_above_clue_one_with_the_line_between(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, 0, 0)
    separator = cell.get_by_test_id("clue-separator")
    expect(separator).to_have_count(1)

    first_text = box_of(cell.get_by_test_id("clue-text").nth(0))
    second_text = box_of(cell.get_by_test_id("clue-text").nth(1))
    separator_box = box_of(separator)
    separator_center = separator_box["y"] + separator_box["height"] / 2

    assert first_text["y"] + first_text["height"] <= second_text["y"] + 0.5
    assert separator_center >= first_text["y"] + first_text["height"] - 0.5
    assert separator_center <= second_text["y"] + 0.5


def test_ac3_separator_is_a_visible_horizontal_line(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    separator = cell_at(page, 0, 0).get_by_test_id("clue-separator")

    assert_separator_is_a_visible_line(separator)


@pytest.mark.parametrize(("row", "column"), [(0, 2), (2, 0)])
def test_ac3_single_clue_cells_have_one_clue_and_no_separator(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    row: int,
    column: int,
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    cell = cell_at(page, row, column)

    expect(cell.get_by_test_id("clue")).to_have_count(1)
    expect(cell.get_by_test_id("clue-separator")).to_have_count(0)


def test_ac3_only_the_double_clue_cell_of_fx01_has_a_separator(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    expect(page.get_by_test_id("clue-separator")).to_have_count(1)
    expect(page.get_by_test_id("clue")).to_have_count(8)


def test_ac3_every_double_clue_cell_of_fx02_has_its_own_separator(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    # The separator is required in every two-clue cell at any zoom; zoom 1 is read.
    # The "each text on its own side" check is not made on FX-02 (spec 006 AC-3,
    # note of 2026-10-22): measured at full zoom (`data-zoom == data-zoom-max`, 5),
    # in a 360 px phone context, 4 of FX-02's 7 two-clue cells still do not fit
    # their texts, a 3-line text of 61.1 px in a half cell of 59.5 px: the text
    # spills 2 px over the separator, as in (1, 0), (6, 8) and (8, 0).
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx02_grid)
    double_cells = []
    for cell in fx02_grid.cells:
        if isinstance(cell, ClueCell) and len(cell.clues) == 2:
            double_cells.append(cell)

    expect(page.get_by_test_id("clue-separator")).to_have_count(len(double_cells))
    for cell in double_cells:
        cell_locator = cell_at(page, cell.row, cell.column)
        separator = cell_locator.get_by_test_id("clue-separator")
        expect(separator).to_have_count(1)
        assert_separator_is_a_visible_line(separator)
