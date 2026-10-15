"""Tests of spec 006, AC-4: a new game renders every cell, empty.

The grid is tested on FX-01 and FX-02 through a live server, and before the first
snapshot through the mocked socket. The shared setup is in `spec006_harness`.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from nock.grid import EmptyCell, Grid
from nock.server import RoomRegistry
from spec006_harness import (
    box_of,
    cell_at,
    grid_from_text,
    open_mock_room,
    open_room,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

FX02_EMPTY_CELL_COUNT = 56


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- AC-4: a new game renders every cell, empty ------------------------------


def test_ac4_fresh_fx01_room_has_25_cells_of_the_right_types(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-width", "5")
    expect(grid).to_have_attribute("data-height", "5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.locator('[data-testid="cell"][data-type="clue"]')).to_have_count(7)
    expect(page.locator('[data-testid="cell"][data-type="letter"]')).to_have_count(18)
    expect(page.locator('[data-testid="cell"][data-type="empty"]')).to_have_count(0)


def test_ac4_each_position_of_fx01_has_the_type_of_the_grid(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    for cell in fx01_grid.cells:
        located = cell_at(page, cell.row, cell.column)
        expect(located).to_have_count(1)
        expect(located).to_have_attribute("data-type", cell.type)


def test_ac4_letter_cells_are_empty_and_unlocked_in_a_fresh_room(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    letter_cells = page.locator('[data-testid="cell"][data-type="letter"]')

    assert letter_cells.count() == 18
    for index in range(letter_cells.count()):
        letter_cell = letter_cells.nth(index)
        expect(letter_cell).to_have_attribute("data-letter", "")
        expect(letter_cell).to_have_attribute("data-locked", "false")
        expect(letter_cell).to_have_text("")
        assert letter_cell.inner_text().strip() == ""


def test_ac4_cells_form_a_table_of_equal_squares_with_zero_zero_top_left(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_room(page, live_server, room_registry, fx01_grid)
    origin = box_of(cell_at(page, 0, 0))
    side = origin["width"]
    assert side >= 10

    for row in range(5):
        for column in range(5):
            box = box_of(cell_at(page, row, column))
            assert box["width"] == pytest.approx(side, abs=1.5)
            assert box["height"] == pytest.approx(side, abs=1.5)
            assert box["x"] == pytest.approx(origin["x"] + column * side, abs=1.5)
            assert box["y"] == pytest.approx(origin["y"] + row * side, abs=1.5)


def test_ac4_fx02_renders_all_221_cells_with_the_type_of_each_position(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx02_grid)

    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-width", "13")
    expect(grid).to_have_attribute("data-height", "17")
    expect(page.get_by_test_id("cell")).to_have_count(13 * 17)
    shown = page.evaluate(
        "() => Array.from(document.querySelectorAll('[data-testid=\"cell\"]'))"
        ".map(e => [e.dataset.row, e.dataset.column, e.dataset.type])"
    )
    shown_types = {(int(r), int(c)): t for r, c, t in shown}
    assert len(shown) == 13 * 17
    for cell in fx02_grid.cells:
        assert shown_types[(cell.row, cell.column)] == cell.type


def test_ac4_empty_cells_hold_nothing(
    page: Page, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx02_grid)
    empty_cells = page.locator('[data-testid="cell"][data-type="empty"]')

    expect(empty_cells).to_have_count(FX02_EMPTY_CELL_COUNT)
    contents = empty_cells.evaluate_all(
        "elements => elements.map(e => [e.children.length, e.textContent.trim()])"
    )
    for children_count, text in contents:
        assert children_count == 0
        assert text == ""
    for cell in fx02_grid.cells:
        if isinstance(cell, EmptyCell):
            expect(cell_at(page, cell.row, cell.column)).to_have_attribute(
                "data-type", "empty"
            )


def test_ac4_grid_is_labelled_with_the_grid_label(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)

    assert load_fr()["grid.label"] == "Grille"
    expect(page.get_by_test_id("grid")).to_have_attribute(
        "aria-label", load_fr()["grid.label"]
    )


def test_ac4_grid_sits_inside_the_grid_viewport(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    open_room(page, live_server, room_registry, fx01_grid)
    inside = page.locator(
        '[data-testid="grid-viewport"] [data-testid="grid"] [data-testid="cell"]'
    )

    expect(inside).to_have_count(25)
    expect(page.get_by_test_id("grid-viewport")).to_have_count(1)


def test_ac4_no_grid_before_the_first_snapshot(page: Page, live_server: str) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("grid-viewport")).to_have_count(0)
    expect(page.get_by_test_id("grid")).to_have_count(0)
    expect(page.get_by_test_id("cell")).to_have_count(0)


def test_ac4_a_room_that_is_not_found_never_shows_a_grid(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(page.get_by_test_id("grid-viewport")).to_have_count(0)
    expect(page.get_by_test_id("grid")).to_have_count(0)
