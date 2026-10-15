"""Tests of spec 009, AC-1: the arrow keys.

The page is tested with a mocked socket on FX-01 and, for the clue cells of the
full-size grid, with a live room on FX-02. Modifier arrows, which must be left
to the browser, are also checked through dispatched `keydown` events, which
report whether the default action was prevented. The shared setup is in
`spec009_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import ClueCell, Grid, LetterCell
from nock.protocol import CellView, EmptyCellView, GridView, grid_view
from nock.server import RoomRegistry
from spec009_harness import (
    ACROSS_AMEN,
    ACROSS_LEST,
    ACROSS_W1,
    DOWN_W2,
    across,
    dispatch_key,
    down,
    expect_selection,
    grid_from_text,
    open_fx01,
    open_view,
    sent_selections,
    settle,
    submit_nickname_form,
    tap,
)

DOWN_MIME = "0,2,0"
ACROSS_VIDE = "2,0,0"


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


def with_empty_cell(view: GridView, row: int, column: int) -> GridView:
    """Return `view` with the cell at (row, column) turned into an empty cell."""
    new_cells: list[CellView] = []
    for cell in view.cells:
        if cell.row == row and cell.column == column:
            new_cells.append(EmptyCellView(row=row, column=column))
        else:
            new_cells.append(cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def expect_cell_selection(page: Page, row: int, column: int, direction: str) -> None:
    """Like `expect_selection`, without the word (cell and direction only)."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)


# ---- AC-1: arrow keys --------------------------------------------------------


def test_ac1_arrows_follow_the_spec_walk_on_fx01(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    page.keyboard.press("ArrowDown")
    expect_selection(page, 2, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowRight")
    expect_selection(page, 2, 2, "across", ACROSS_VIDE)

    page.keyboard.press("ArrowUp")
    expect_selection(page, 1, 2, "down", DOWN_MIME)

    assert sent_selections(mock) == [
        across(1, 1),
        down(2, 1),
        across(2, 2),
        down(1, 2),
    ]


def test_ac1_arrow_left_from_a_cell_with_only_clue_cells_to_its_left_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("ArrowLeft")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_arrow_up_at_the_top_edge_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowUp")

    settle(page)
    expect_selection(page, 0, 1, "down", DOWN_W2)
    assert sent_selections(mock) == [down(0, 1)]


def test_ac1_arrow_at_the_right_and_bottom_edges_does_not_wrap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 4, 4)
    expect_selection(page, 4, 4, "across", ACROSS_LEST)

    page.keyboard.press("ArrowRight")
    page.keyboard.press("ArrowDown")

    settle(page)
    expect_selection(page, 4, 4, "across", ACROSS_LEST)
    assert sent_selections(mock) == [across(4, 4)]


def test_ac1_arrow_down_from_a_cell_with_only_clue_cells_below_does_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("ArrowDown")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_arrow_right_from_the_first_cell_selects_the_next_one_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("ArrowRight")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0), across(1, 1)]


def test_ac1_arrow_up_onto_a_cell_with_one_word_selects_it_down(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)

    page.keyboard.press("ArrowUp")

    expect_selection(page, 0, 1, "down", DOWN_W2)
    assert sent_selections(mock) == [across(1, 1), down(0, 1)]


def test_ac1_arrow_left_while_down_onto_an_across_only_cell_switches_to_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowLeft")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1), down(1, 1), across(1, 0)]


def test_ac1_arrow_down_while_across_switches_to_down_and_arrow_left_back(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", ACROSS_VIDE)

    page.keyboard.press("ArrowDown")
    expect_selection(page, 3, 2, "down", DOWN_MIME)

    page.keyboard.press("ArrowLeft")
    expect_selection(page, 3, 1, "across", ACROSS_AMEN)

    assert sent_selections(mock) == [
        across(2, 2),
        down(3, 2),
        across(3, 1),
    ]


def test_ac1_arrows_skip_an_empty_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # With (1, 1) empty, TAMIS ends before it, so (1, 2) has no across word
    # (specs 002 and 007); only MIME is left and step 2 of the spec picks it.
    view = with_empty_cell(grid_view(fx01_grid), 1, 1)
    mock = open_view(page, live_server, view)
    tap(page, 1, 0)
    expect_cell_selection(page, 1, 0, "across")

    page.keyboard.press("ArrowRight")

    expect_selection(page, 1, 2, "down", DOWN_MIME)
    assert sent_selections(mock)[-1] == down(1, 2)


def test_ac1_arrow_down_skips_an_empty_cell_and_uses_the_only_word_left(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # With (2, 1) empty, NAVAL ends before it, so (3, 1) has no down word and
    # the walk lands on its across word AMEN.
    view = with_empty_cell(grid_view(fx01_grid), 2, 1)
    mock = open_view(page, live_server, view)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    page.keyboard.press("ArrowDown")

    expect_selection(page, 3, 1, "across", ACROSS_AMEN)
    assert sent_selections(mock)[-1] == across(3, 1)


def test_ac1_arrows_do_nothing_without_a_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    grid.focus()
    frames_before = len(mock.received)

    for key in ["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"]:
        page.keyboard.press(key)

    settle(page)
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")
    assert len(mock.received) == frames_before


def test_ac1_a_handled_arrow_is_prevented_and_a_modified_one_is_left_alone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    assert dispatch_key(page, "ArrowRight", ctrl=True) is True
    assert dispatch_key(page, "ArrowRight", alt=True) is True
    page.keyboard.press("Control+ArrowRight")
    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]

    assert dispatch_key(page, "ArrowRight") is False
    expect_selection(page, 1, 2, "across", ACROSS_W1)


def find_letter_clue_letter_in_a_row(grid: Grid) -> tuple[int, int]:
    """Return (row, column) of a letter cell followed by a clue, then a letter."""
    for cell in grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        if cell.column + 2 >= grid.width:
            continue
        middle = grid.cell_at(cell.row, cell.column + 1)
        right = grid.cell_at(cell.row, cell.column + 2)
        if isinstance(middle, ClueCell) and isinstance(right, LetterCell):
            return cell.row, cell.column
    pytest.fail("FX-02 has no letter, clue, letter pattern in a row")


def find_letter_clue_letter_in_a_column(grid: Grid) -> tuple[int, int]:
    """Return (row, column) of a letter cell above a clue, then a letter."""
    for cell in grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        if cell.row + 2 >= grid.height:
            continue
        middle = grid.cell_at(cell.row + 1, cell.column)
        below = grid.cell_at(cell.row + 2, cell.column)
        if isinstance(middle, ClueCell) and isinstance(below, LetterCell):
            return cell.row, cell.column
    pytest.fail("FX-02 has no letter, clue, letter pattern in a column")


def test_ac1_fx02_arrow_right_jumps_over_a_clue_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    row, column = find_letter_clue_letter_in_a_row(fx02_grid)
    code = room_registry.register_room(fx02_grid)
    page.goto(f"{live_server}/r/{code}")
    submit_nickname_form(page)
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    tap(page, row, column)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-column", str(column))

    page.keyboard.press("ArrowRight")

    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column + 2))


def test_ac1_fx02_arrow_down_jumps_over_a_clue_cell(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    row, column = find_letter_clue_letter_in_a_column(fx02_grid)
    code = room_registry.register_room(fx02_grid)
    page.goto(f"{live_server}/r/{code}")
    submit_nickname_form(page)
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    tap(page, row, column)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))

    page.keyboard.press("ArrowDown")

    expect(grid).to_have_attribute("data-selected-row", str(row + 2))
    expect(grid).to_have_attribute("data-selected-column", str(column))
