"""Tests of spec 042, AC-1 to AC-3: grid lines, cell backgrounds, the tint switch.

On the mocked room of `tests/spec042_harness.py` (spec 040's "Browser with mocked
socket"), 1280 by 720, desktop context, `localStorage` empty unless a test seeds
it. AC-1 reads the borders, the boxes and the clipping of the cells; AC-2 the one
background of each letter cell through taps; AC-3 the « Mots des autres » switch.

Choices where the spec leaves room:

- AC-1, the grid's box "5 s + 1": `s` is read on (2, 2); the grid's own box is
  compared, with the 1 px tolerance of a position.
- AC-2, the edge cases "Flash on my selected cell" and "Two other players' words
  on one cell" are tested here: the first reads the cell during the flash in one
  `page.evaluate`, the second puts `p3` (colour 1) before `p2` (colour 3) in the
  roster, both words holding (3, 2).
- AC-3, the edge cases "Tint off and my word" and "A `localStorage` that throws"
  are tested here; the switch's markup in `room-menu` is AC-19's.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, GridView, LetterChanged, PlayerView, grid_view
from spec007_harness import note_view
from spec019_harness import MockRoomSocket
from spec042_harness import (
    LOCKED,
    QUIET_MS,
    RULE,
    SELECTED,
    TINT_STORAGE_KEY,
    TINT_SWITCH,
    WAIT_TIMEOUT_MS,
    WHITE,
    WORD,
    ChangeList,
    Reading,
    box_of,
    cell_at,
    click_switch,
    colour_of,
    colour_problems,
    fx01_view,
    make_catalogue,
    make_storage_throw,
    me,
    mixed_colour_problems,
    open_room,
    player,
    reload_room,
    seed_value,
    selecting,
    stored_value,
    style_of,
    tap,
    tint_of,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


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


# ---- AC-1: grid lines and empty cells -------------------------------------------

# Each cell's four borders: style, width and parsed colour, and its `overflow`.
CELL_BORDERS_SCRIPT = r"""
() => {
  const found = [];
  for (const cell of document.querySelectorAll('[data-testid="cell"]')) {
    const style = getComputedStyle(cell);
    found.push({
      row: cell.getAttribute('data-row'),
      column: cell.getAttribute('data-column'),
      type: cell.getAttribute('data-type'),
      right: [style.borderRightStyle, style.borderRightWidth, style.borderRightColor],
      bottom: [
        style.borderBottomStyle, style.borderBottomWidth, style.borderBottomColor,
      ],
      leftWidth: style.borderLeftWidth,
      topWidth: style.borderTopWidth,
      overflow: style.overflow,
    });
  }
  return found;
}
"""

RULE_TEXT = f"rgb({RULE[0]}, {RULE[1]}, {RULE[2]})"


def read_cells(page: Page) -> list[Reading]:
    found = page.evaluate(CELL_BORDERS_SCRIPT)
    assert isinstance(found, list)
    return found


def test_ac1_the_grid_has_a_rule_grey_left_and_top_border_only(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    grid = page.get_by_test_id("grid")

    for side in ("Left", "Top"):
        assert style_of(grid, f"border{side}Style") == "solid"
        assert style_of(grid, f"border{side}Width") == "1px"
        assert colour_problems(side, colour_of(grid, f"border{side}Color"), RULE) == []
    assert style_of(grid, "borderRightWidth") == "0px"
    assert style_of(grid, "borderBottomWidth") == "0px"


def test_ac1_every_cell_has_a_rule_grey_right_and_bottom_border_only(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    cells = read_cells(page)

    assert len(cells) == 25
    problems: list[str] = []
    for cell in cells:
        where = f"({cell['row']}, {cell['column']})"
        for side in ("right", "bottom"):
            if cell[side] != ["solid", "1px", RULE_TEXT]:
                problems.append(f"{where} {side}: {cell[side]}")
        if cell["leftWidth"] != "0px" or cell["topWidth"] != "0px":
            problems.append(f"{where} left {cell['leftWidth']} top {cell['topWidth']}")
    assert problems == []


def test_ac1_there_is_no_gap_between_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    centre = box_of(cell_at(page, 2, 2))
    left_neighbour = box_of(cell_at(page, 2, 1))
    top_neighbour = box_of(cell_at(page, 1, 2))

    assert abs(centre.left - left_neighbour.right) <= 0.5
    assert abs(centre.top - top_neighbour.bottom) <= 0.5


def test_ac1_the_grid_box_counts_the_extra_line(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    side = box_of(cell_at(page, 2, 2)).width
    grid_box = box_of(page.get_by_test_id("grid"))

    assert abs(grid_box.width - (5 * side + 1)) <= 1.0, (grid_box, side)
    assert abs(grid_box.height - (5 * side + 1)) <= 1.0, (grid_box, side)


def test_ac1_letter_cells_clip_their_content_and_clue_cells_do_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])

    problems: list[str] = []
    for cell in read_cells(page):
        expected = "visible" if cell["type"] == "clue" else "hidden"
        if cell["overflow"] != expected:
            where = f"({cell['row']}, {cell['column']}) {cell['type']}"
            problems.append(f"{where}: overflow {cell['overflow']}")
    assert problems == []


def test_ac1_the_grid_clips_at_its_outer_edge_on_both_axes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_view(fx01_grid), [me()])
    grid = page.get_by_test_id("grid")

    assert style_of(grid, "overflow") == "clip"
    assert style_of(grid, "overflowX") == "clip"
    assert style_of(grid, "overflowY") == "clip"


DESKTOP_WINDOW = {"width": 1280, "height": 800}


def open_fx02_on_desktop(page: Page, base_url: str, fx02_grid: Grid) -> None:
    """A FX-02 room in a 1280 by 800 window, nothing selected."""
    page.set_viewport_size(DESKTOP_WINDOW)
    open_room(page, base_url, grid_view(fx02_grid), [me()])


def test_ac1_the_fx02_viewport_has_nothing_to_scroll_at_1280_by_800(
    page: Page, live_server: str, fx02_grid: Grid
) -> None:
    open_fx02_on_desktop(page, live_server, fx02_grid)
    viewport = page.get_by_test_id("grid-viewport")

    # A hit test of the part of a clue text outside the grid cannot tell a clipped
    # text from an unclipped one: the viewport (1.1 px taller than the grid) already
    # clips what leaves its own box, so the content that the grid does not clip is
    # not painted but scrolled. The scroll sizes show it (438 against 434 before).

    sizes = viewport.evaluate(
        "element => ({scrollHeight: element.scrollHeight,"
        " clientHeight: element.clientHeight, scrollWidth: element.scrollWidth,"
        " clientWidth: element.clientWidth})"
    )

    assert sizes["scrollHeight"] <= sizes["clientHeight"] + 1, sizes
    assert sizes["scrollWidth"] <= sizes["clientWidth"] + 1, sizes


def test_ac1_an_empty_cell_is_rule_grey_clips_and_holds_no_element(
    page: Page, live_server: str
) -> None:
    open_room(page, live_server, note_view(), [me()])
    empty = cell_at(page, 0, 2)
    expect(empty).to_have_attribute("data-type", "empty")

    assert colour_problems("empty", colour_of(empty, "backgroundColor"), RULE) == []
    assert style_of(empty, "overflow") == "hidden"
    assert empty.evaluate("cell => cell.childElementCount") == 0


# ---- AC-2: one background per letter cell ---------------------------------------


def ac2_changes() -> ChangeList:
    """(1, 0) holds `T` locked and (1, 2) holds `M` locked."""
    return [
        (1, 0, {"letter": "T", "author": "p1", "locked": True}),
        (1, 2, {"letter": "M", "author": "p1", "locked": True}),
    ]


def ac2_players() -> list[PlayerView]:
    """`p1`, and `p2` (colour 3) selecting (2, 2) down (MIME)."""
    return [me(), player("p2", 3, selection=selecting(2, 2, Direction.DOWN))]


def ac2_view(grid: Grid) -> GridView:
    return fx01_view(grid, ac2_changes())


def open_ac2(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    mock = open_room(page, base_url, ac2_view(grid), ac2_players())
    expect(cell_at(page, 3, 2)).to_have_attribute("data-tinted-by", "p2")
    return mock


def background_problems(page: Page, row: int, column: int, expected: str) -> list[str]:
    """The cell's background against one row of the table, by its name."""
    found = colour_of(cell_at(page, row, column), "backgroundColor")
    where = f"({row}, {column})"
    if expected == "tint":
        return mixed_colour_problems(where, found, tint_of(3))
    colours = {"white": WHITE, "selected": SELECTED, "locked": LOCKED, "word": WORD}
    return mixed_colour_problems(where, found, colours[expected])


def tap_1_1_across(page: Page) -> None:
    tap(page, 1, 1)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-direction", "across")
    expect(grid).to_have_attribute("data-word", "0,0,0")


def test_ac2_before_any_tap_the_others_word_is_tinted_and_the_rest_white(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)

    assert background_problems(page, 3, 2, "tint") == []
    assert background_problems(page, 2, 1, "white") == []


def test_ac2_my_cell_my_word_and_locked_cells_take_their_rows_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)

    tap_1_1_across(page)

    expect(cell_at(page, 1, 2)).to_have_attribute("data-tinted-by", "p2")
    problems = background_problems(page, 1, 1, "selected")
    problems += background_problems(page, 1, 0, "locked")
    problems += background_problems(page, 1, 2, "locked")
    problems += background_problems(page, 1, 3, "word")
    problems += background_problems(page, 3, 2, "tint")
    assert problems == []


def test_ac2_my_selected_cell_beats_locked(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)
    tap_1_1_across(page)

    tap(page, 1, 0)

    problems = background_problems(page, 1, 0, "selected")
    problems += background_problems(page, 1, 1, "word")
    assert problems == []


def test_ac2_my_selected_cell_beats_the_tint(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)
    tap_1_1_across(page)
    tap(page, 1, 0)

    tap(page, 3, 2)

    expect(cell_at(page, 3, 2)).to_have_attribute("data-tinted-by", "p2")
    assert background_problems(page, 3, 2, "selected") == []


# Waits until the cell flashes, then reads its `data-flash` and background at once.
FLASH_READING_SCRIPT = r"""
([row, column]) => {
  const cell = document.querySelector(
    `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`
  );
  if (cell === null || cell.getAttribute('data-flash') === '') {
    return false;
  }
  return {
    flash: cell.getAttribute('data-flash'),
    selected: cell.getAttribute('data-selected'),
    background: getComputedStyle(cell).backgroundColor,
  };
}
"""


def test_ac2_a_flash_on_my_selected_cell_comes_first_with_white_under_the_overlay(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    # Spec 016 flashes a cell when another player replaces my letter: (1, 1)
    # holds my `X` first.
    changes = ac2_changes()
    changes.append((1, 1, {"letter": "X", "author": "p1"}))
    mock = open_room(page, live_server, fx01_view(fx01_grid, changes), ac2_players())
    tap_1_1_across(page)
    event = LetterChanged(
        seq=6, row=1, column=1, letter="Y", pencil=False, player_id="p2"
    )

    mock.send(event.model_dump_json())
    handle = page.wait_for_function(
        FLASH_READING_SCRIPT, arg=[1, 1], timeout=WAIT_TIMEOUT_MS
    )
    reading = handle.json_value()

    assert isinstance(reading, dict)
    assert reading["flash"] == "3"
    assert reading["selected"] == "true"
    assert reading["background"] == "rgb(255, 255, 255)"


def test_ac2_a_cell_in_two_others_words_takes_the_tint_of_the_first_in_roster_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        me(),
        player("p3", 1, selection=selecting(3, 1, Direction.ACROSS)),
        player("p2", 3, selection=selecting(2, 2, Direction.DOWN)),
    ]
    open_room(page, live_server, fx01_view(fx01_grid), players)
    shared = cell_at(page, 3, 2)
    expect(shared).to_have_attribute("data-tinted-by", "p3 p2")

    found = colour_of(shared, "backgroundColor")

    assert mixed_colour_problems("(3, 2)", found, tint_of(1)) == []


# ---- AC-3: the « Mots des autres » switch -----------------------------------------


def tint_switch(page: Page) -> Locator:
    return page.get_by_test_id(TINT_SWITCH)


def test_ac3_the_switch_is_on_by_default_and_the_tint_shows(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)

    expect(tint_switch(page)).to_have_attribute("aria-pressed", "true")
    assert background_problems(page, 3, 2, "tint") == []


def test_ac3_a_click_removes_the_tint_keeps_the_data_and_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac2(page, live_server, fx01_grid)
    before = len(mock.frames_without_pings())

    click_switch(page, TINT_SWITCH, "false")
    page.wait_for_timeout(QUIET_MS)

    assert mock.frames_without_pings()[before:] == []
    for row in (3, 4):
        expect(cell_at(page, row, 2)).to_have_attribute("data-tinted-by", "p2")
        assert background_problems(page, row, 2, "white") == []
    assert stored_value(page, TINT_STORAGE_KEY) == "false"


def test_ac3_the_choice_is_kept_after_a_reload(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac2(page, live_server, fx01_grid)
    click_switch(page, TINT_SWITCH, "false")

    reload_room(page, mock, ac2_view(fx01_grid), ac2_players())

    expect(tint_switch(page)).to_have_attribute("aria-pressed", "false")
    expect(cell_at(page, 3, 2)).to_have_attribute("data-tinted-by", "p2")
    assert background_problems(page, 3, 2, "white") == []


def test_ac3_a_second_click_brings_the_tint_back(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)
    click_switch(page, TINT_SWITCH, "false")

    click_switch(page, TINT_SWITCH, "true")

    assert background_problems(page, 3, 2, "tint") == []
    assert stored_value(page, TINT_STORAGE_KEY) == "true"


@pytest.mark.parametrize(
    ("stored", "pressed"),
    [("false", "false"), ("true", "true"), ("off", "true"), ("", "true")],
    ids=["false", "true", "other-value", "empty-text"],
)
def test_ac3_the_switch_starts_from_the_stored_value(
    page: Page, live_server: str, fx01_grid: Grid, stored: str, pressed: str
) -> None:
    seed_value(page, TINT_STORAGE_KEY, stored)

    open_ac2(page, live_server, fx01_grid)

    expect(tint_switch(page)).to_have_attribute("aria-pressed", pressed)
    expected = "tint" if pressed == "true" else "white"
    assert background_problems(page, 3, 2, expected) == []


def test_ac3_with_the_tint_off_my_word_and_my_cell_keep_their_look(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac2(page, live_server, fx01_grid)
    click_switch(page, TINT_SWITCH, "false")

    tap_1_1_across(page)

    problems = background_problems(page, 1, 1, "selected")
    problems += background_problems(page, 1, 3, "word")
    problems += background_problems(page, 1, 2, "locked")
    problems += background_problems(page, 4, 2, "white")
    assert problems == []


def test_ac3_with_a_storage_that_throws_the_switch_starts_on_and_still_flips(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    make_storage_throw(page)
    open_ac2(page, live_server, fx01_grid)
    expect(tint_switch(page)).to_have_attribute("aria-pressed", "true")

    click_switch(page, TINT_SWITCH, "false")

    assert background_problems(page, 3, 2, "white") == []
