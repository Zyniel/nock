"""Tests of spec 041, AC-15: today's room elements take the token colours.

On the mocked room of spec 035's harness, with the FX-01 snapshot of the
criterion: `you` `p1` (colour 0) and `p2` (colour 3); (1, 0) holds `T` locked,
(1, 1) holds `X` with `wrong` true, (2, 3) holds `D` as a pencil letter of `p1`,
and `p2` selects (3, 1) `across`. The player then taps (2, 2), which selects
VIDE across. The tests only read computed colours and styles, so they need no
wait for the fonts. The shared setup is in `tests/spec041_harness.py`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, Selection
from spec035_harness import (
    ChangeList,
    build_fx01_grid,
    build_reference_catalogue,
    open_room,
    player_view,
)
from spec041_harness import (
    CLUE_BG,
    CLUE_INK,
    INK,
    LOCKED,
    NAVY,
    PENCIL,
    RED,
    RULE,
    SELECTED,
    STYLE_READERS_JS,
    WORD,
    assert_colour,
    assert_mixed_colour,
    cell_at,
    colour_of,
    px,
    style_of,
    to_colour,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- The room of AC-15 ------------------------------------------------------------

# `--player-colour-3` (#6838E0) at 16 % over white.
P2_TINT = (231, 223, 250)

# The parsed right border colour of every cell, with its row and column.
ALL_CELLS_RIGHT_BORDER_SCRIPT = "() => {\n" + STYLE_READERS_JS + r"""
const found = [];
for (const cell of document.querySelectorAll('[data-testid="cell"]')) {
  found.push({
    row: cell.getAttribute('data-row'),
    column: cell.getAttribute('data-column'),
    colour: readColour(cell, 'borderRightColor'),
  });
}
return found;
}"""


def open_ac15_room(page: Page, base_url: str, grid: Grid) -> None:
    """Open the room of AC-15, then tap (2, 2)."""
    p2_selection = Selection(row=3, column=1, direction=Direction.ACROSS)
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 3, selection=p2_selection),
    ]
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": "p1", "locked": True}),
        (1, 1, {"letter": "X", "author": "p1", "wrong": True}),
        (2, 3, {"letter": "D", "author": "p1", "pencil": True}),
    ]
    open_room(page, base_url, grid, changes=changes, players=players)
    cell_at(page, 2, 2).click()
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-selected-row", "2")
    expect(grid_element).to_have_attribute("data-selected-column", "2")
    expect(grid_element).to_have_attribute("data-direction", "across")
    expect(cell_at(page, 3, 2)).to_have_attribute("data-tinted-by", "p2")


def test_ac15_selected_cell_has_the_selected_background(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)

    assert_colour(colour_of(cell_at(page, 2, 2), "backgroundColor"), SELECTED)


def test_ac15_selected_cell_outline_is_2px_solid_navy_inside(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    cell = cell_at(page, 2, 2)

    assert style_of(cell, "outlineStyle") == "solid"
    assert px(style_of(cell, "outlineWidth")) == 2.0
    assert_colour(colour_of(cell, "outlineColor"), NAVY)
    assert px(style_of(cell, "outlineOffset")) == -2.0


def test_ac15_cell_of_my_word_has_the_word_background(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    cell = cell_at(page, 2, 1)
    expect(cell).to_have_attribute("data-in-word", "true")

    assert_colour(colour_of(cell, "backgroundColor"), WORD)


def test_ac15_locked_cell_has_the_locked_background(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-locked", "true")

    assert_colour(colour_of(cell, "backgroundColor"), LOCKED)


def test_ac15_wrong_letter_strike_is_red(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-wrong", "true")

    assert_colour(colour_of(cell, "textDecorationColor"), RED)


def test_ac15_pencil_letter_in_my_word_is_pencil_grey(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    cell = cell_at(page, 2, 3)
    expect(cell).to_have_attribute("data-pencil", "true")
    expect(cell).to_have_attribute("data-in-word", "true")

    assert_colour(colour_of(cell, "color"), PENCIL)


def test_ac15_cell_of_another_players_word_has_the_16_percent_tint(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)

    assert_mixed_colour(colour_of(cell_at(page, 3, 2), "backgroundColor"), P2_TINT)


def test_ac15_every_cell_has_a_rule_grey_right_border(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)

    found = page.evaluate(ALL_CELLS_RIGHT_BORDER_SCRIPT)

    assert isinstance(found, list)
    assert len(found) == 25
    offenders: list[str] = []
    for cell in found:
        colour = to_colour(cell["colour"])
        if colour != (RULE[0], RULE[1], RULE[2], 1.0):
            offenders.append(f"({cell['row']}, {cell['column']}): {colour}")
    assert offenders == []


def test_ac15_clue_cell_has_the_clue_background(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)

    assert_colour(colour_of(cell_at(page, 0, 2), "backgroundColor"), CLUE_BG)


def test_ac15_clue_text_is_clue_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    clue_text = cell_at(page, 0, 2).get_by_test_id("clue-text")

    assert_colour(colour_of(clue_text, "color"), CLUE_INK)


def test_ac15_down_arrow_of_the_clue_is_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac15_room(page, live_server, fx01_grid)
    arrow = cell_at(page, 0, 2).get_by_test_id("clue-arrow")
    expect(arrow).to_have_attribute("data-side", "bottom")

    assert_colour(colour_of(arrow, "borderTopColor"), INK)
