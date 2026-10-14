"""Tests of spec 013, AC-3 and AC-4: the outlines of the page.

AC-3: two outlines on one cell. AC-4: my own selection looks different. The page is
tested with spec 040's mocked socket. The shared setup is in `spec013_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, PlayerView, Selection
from spec013_harness import (
    ROW_2_WORD,
    WAIT_TIMEOUT_MS,
    MockRoomSocket,
    all_remote_selections,
    background_of,
    border_of,
    cell_at,
    clear_frame,
    expected_tints,
    grid_from_text,
    open_room,
    player_view,
    remote_players_on,
    selection_frame,
    settle,
    swatch_colour,
    tinted_by_map,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-3: two outlines on one cell ------------------------------------------------


def three_player_snapshot() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1),
        player_view("p3", "Cleo", 2),
    ]


def open_shared_cell(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Open a room where `p2` (across) and `p3` (down) select (1, 1)."""
    mock = open_room(page, base_url, grid, three_player_snapshot())
    mock.send(selection_frame("p2", 1, 1, Direction.ACROSS))
    mock.send(selection_frame("p3", 1, 1, Direction.DOWN))
    expect(cell_at(page, 1, 1).get_by_test_id("remote-selection")).to_have_count(2)
    return mock


def test_ac3_browser_two_outlines_on_one_cell_are_both_visible_and_distinct(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]
    outlines = cell_at(page, 1, 1).get_by_test_id("remote-selection")
    first = outlines.nth(0)
    second = outlines.nth(1)
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    first_box = first.bounding_box()
    second_box = second.bounding_box()
    assert first_box is not None
    assert second_box is not None
    assert first_box != second_box
    first_style, first_colour, _ = border_of(first)
    second_style, second_colour, _ = border_of(second)
    assert first_style == "dashed"
    assert second_style == "dashed"
    assert first_colour != second_colour
    assert first_colour == swatch_colour(page, "p2")
    assert second_colour == swatch_colour(page, "p3")


def test_ac3_browser_the_cell_lists_both_players_in_roster_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p2 p3")
    row_1 = {(1, 0): "p2", (1, 2): "p2", (1, 3): "p2", (1, 4): "p2"}
    column_1 = {(0, 1): "p3", (2, 1): "p3", (3, 1): "p3", (4, 1): "p3"}
    expected = {**row_1, **column_1, (1, 1): "p2 p3"}
    assert tinted_by_map(page) == expected_tints(expected)


def test_ac3_browser_the_overlapping_tint_is_the_one_of_the_first_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    shared = background_of(cell_at(page, 1, 1))
    only_first = background_of(cell_at(page, 1, 0))
    only_second = background_of(cell_at(page, 0, 1))
    assert shared == only_first
    assert only_first != only_second


def test_ac3_browser_the_order_follows_the_roster_not_the_order_of_arrival(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_player_snapshot())

    mock.send(selection_frame("p3", 1, 1, Direction.DOWN))
    mock.send(selection_frame("p2", 1, 1, Direction.ACROSS))

    expect(cell_at(page, 1, 1).get_by_test_id("remote-selection")).to_have_count(2)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p2 p3")
    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]


def test_ac3_browser_the_outlines_stay_when_i_select_the_same_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 1)

    cell.click(timeout=WAIT_TIMEOUT_MS)

    expect(cell).to_have_attribute("data-selected", "true")
    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]
    outlines = cell.get_by_test_id("remote-selection")
    expect(outlines.nth(0)).to_be_visible()
    expect(outlines.nth(1)).to_be_visible()
    first_box = outlines.nth(0).bounding_box()
    second_box = outlines.nth(1).bounding_box()
    assert first_box is not None
    assert second_box is not None
    assert first_box != second_box
    expect(cell).to_have_attribute("data-tinted-by", "p2 p3")


def test_ac3_browser_one_player_leaving_leaves_the_other_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_shared_cell(page, live_server, fx01_grid)

    mock.send(clear_frame("p2"))

    outline = cell_at(page, 1, 1).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p3")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p3")


# ---- AC-4: my selection looks different ----------------------------------------------


def border_styles_in(cell: Locator) -> list[str]:
    """The four border styles of a cell and of each of its descendants."""
    script = (
        "el => [el, ...el.querySelectorAll('*')].flatMap(e => {"
        " const s = getComputedStyle(e);"
        " return [s.borderTopStyle, s.borderRightStyle,"
        " s.borderBottomStyle, s.borderLeftStyle]; })"
    )
    styles = cell.evaluate(script)
    assert isinstance(styles, list)
    return styles


def open_with_p2_on_2_2(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    mock = open_room(
        page,
        base_url,
        grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)
    return mock


def test_ac4_browser_my_cell_is_selected_and_has_no_remote_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)

    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)

    mine = cell_at(page, 3, 1)
    expect(mine).to_have_attribute("data-selected", "true")
    expect(mine.get_by_test_id("remote-selection")).to_have_count(0)
    expect(
        page.locator('[data-testid="remote-selection"][data-player-id="p1"]')
    ).to_have_count(0)
    assert remote_players_on(page, 2, 2) == [("p2", "1")]


def test_ac4_browser_my_selection_is_never_dashed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    mine = cell_at(page, 3, 1)
    expect(mine).to_have_attribute("data-selected", "true")

    styles = border_styles_in(mine)

    assert styles != []
    assert "dashed" not in styles
    theirs = border_of(cell_at(page, 2, 2).get_by_test_id("remote-selection"))
    assert theirs[0] == "dashed"


def test_ac4_browser_my_background_differs_from_the_others(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    expect(cell_at(page, 3, 1)).to_have_attribute("data-selected", "true")
    expect(cell_at(page, 2, 3)).to_have_attribute("data-tinted-by", "p2")

    mine = background_of(cell_at(page, 3, 1))

    assert mine != background_of(cell_at(page, 2, 2))
    assert mine != background_of(cell_at(page, 2, 3))


def test_ac4_browser_the_page_never_draws_an_outline_for_me(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_p2_on_2_2(page, live_server, fx01_grid)

    mock.send(selection_frame("p1", 4, 4, Direction.ACROSS))
    settle(page)

    expect(
        page.locator('[data-testid="remote-selection"][data-player-id="p1"]')
    ).to_have_count(0)
    assert all_remote_selections(page) == 1
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac4_browser_a_selection_of_mine_in_the_snapshot_draws_no_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mine = Selection(row=4, column=4, direction=Direction.ACROSS)
    open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True, selection=mine),
            player_view("p2", "Bob", 1),
        ],
    )

    settle(page)

    assert all_remote_selections(page) == 0
    assert tinted_by_map(page) == expected_tints({})


def test_ac4_browser_a_cell_of_my_word_keeps_my_highlight_when_also_tinted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    expect(cell_at(page, 3, 1)).to_have_attribute("data-selected", "true")

    mock.send(selection_frame("p2", 4, 2, Direction.DOWN))

    shared = cell_at(page, 3, 2)
    own_only = cell_at(page, 3, 3)
    expect(shared).to_have_attribute("data-tinted-by", "p2")
    expect(shared).to_have_attribute("data-in-word", "true")
    expect(own_only).to_have_attribute("data-in-word", "true")
    expect(own_only).to_have_attribute("data-tinted-by", "")
    assert background_of(shared) == background_of(own_only)
