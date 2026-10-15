"""Tests of spec 007, AC-1 and AC-2: tapping a letter cell.

AC-1: the tapped cell and its whole word are selected and highlighted, with the
direction rules, the cells and taps that change nothing, and a second snapshot.
AC-2: tapping the selected cell again switches between its two words.
The shared setup is in `spec007_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import grid_view
from spec007_harness import (
    active_clue_texts,
    cell_at,
    clue_named,
    expect_selection,
    grid_from_text,
    note_view,
    open_fx01,
    open_mock_room,
    positions_with,
    select_cell_message,
    sent_selections,
    settle,
    show_snapshot,
    tap,
    with_letter_cells,
)

FX01_LETTER_CELL_COUNT = 18

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def touch_page(browser: Browser) -> Iterator[Page]:
    """A page in a touch context, for locator.tap()."""
    context = browser.new_context(has_touch=True)
    try:
        yield context.new_page()
    finally:
        context.close()


def expect_nothing_selected(page: Page) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")
    expect(grid).to_have_attribute("data-direction", "")
    expect(grid).to_have_attribute("data-word", "")


def background_of(locator: Locator) -> str:
    return locator.evaluate("element => getComputedStyle(element).backgroundColor")


# ---- AC-1: tapping a letter cell selects it and highlights its word ----------


def test_ac1_nothing_is_selected_at_start(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    expect_nothing_selected(page)
    assert positions_with(page, "data-selected") == []
    assert positions_with(page, "data-in-word") == []
    assert active_clue_texts(page) == []
    expect(page.locator('[data-testid="cell"][data-selected="false"]')).to_have_count(
        FX01_LETTER_CELL_COUNT
    )
    assert sent_selections(mock) == []


def test_ac1_tapping_a_letter_cell_selects_its_across_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-selected", "true")
    assert positions_with(page, "data-selected") == [(2, 2)]
    assert positions_with(page, "data-in-word") == [(2, 1), (2, 2), (2, 3), (2, 4)]
    expect(page.locator('[data-testid="cell"][data-in-word="false"]')).to_have_count(
        FX01_LETTER_CELL_COUNT - 4
    )
    assert active_clue_texts(page) == ["Sans contenu"]


def test_ac1_selected_word_other_cells_and_outside_cells_have_three_colours(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    selected = background_of(cell_at(page, 2, 2))
    in_word = background_of(cell_at(page, 2, 3))
    other_in_word = background_of(cell_at(page, 2, 1))
    outside = background_of(cell_at(page, 3, 3))
    assert in_word == other_in_word
    assert len({selected, in_word, outside}) == 3


def test_ac1_active_clue_has_another_background_than_an_inactive_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    inactive_before = background_of(clue_named(page, "Sans contenu"))

    tap(page, 2, 2)

    expect(clue_named(page, "Sans contenu")).to_have_attribute("data-active", "true")
    active = background_of(clue_named(page, "Sans contenu"))
    inactive = background_of(clue_named(page, "Fin de prière"))
    assert active != inactive
    assert active != inactive_before
    expect(clue_named(page, "Fin de prière")).to_have_attribute("data-active", "false")


def test_ac1_a_touch_tap_selects_the_cell(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(touch_page, live_server, fx01_grid)

    cell_at(touch_page, 2, 2).tap()

    expect_selection(touch_page, 2, 2, "across", "2,0,0")
    assert positions_with(touch_page, "data-in-word") == [
        (2, 1),
        (2, 2),
        (2, 3),
        (2, 4),
    ]


def test_ac1_first_tap_on_a_cell_with_only_a_down_word_selects_down(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 0, 1)

    expect_selection(page, 0, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert positions_with(page, "data-selected") == [(0, 1)]
    assert active_clue_texts(page) == ["De la marine"]


def test_ac1_first_tap_on_a_cell_with_only_an_across_word_selects_across(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 0)

    expect_selection(page, 1, 0, "across", "0,0,0")
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]
    assert active_clue_texts(page) == ["Passoire fine"]


def test_ac1_the_current_direction_is_kept_on_a_cell_with_a_word_in_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "down", "0,2,0")
    assert active_clue_texts(page) == ["Artiste muet"]
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]

    tap(page, 2, 1)
    expect_selection(page, 2, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]


def test_ac1_across_is_kept_when_it_is_the_current_direction(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    tap(page, 1, 1)

    expect_selection(page, 1, 1, "across", "0,0,0")


def test_ac1_the_direction_is_forced_when_the_cell_has_no_word_in_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")

    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")


def test_ac1_selecting_a_cell_gives_keyboard_focus_to_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("tabindex", "0")

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(grid).to_be_focused()


def test_ac1_locked_cells_are_selectable(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(2, 2, {"letter": "I", "locked": True})],
    )

    tap(page, 2, 2)

    expect_selection(page, 2, 2, "across", "2,0,0")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-selected", "true")


def test_ac1_tapping_an_empty_cell_changes_nothing_and_sends_nothing(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, note_view(), 0)
    expect(page.get_by_test_id("cell")).to_have_count(3)

    cell_at(page, 0, 2).click()
    settle(page)
    expect_nothing_selected(page)
    assert sent_selections(mock) == []

    cell_at(page, 0, 1).click()
    expect_selection(page, 0, 1, "across", "0,0,0")
    cell_at(page, 0, 2).click()
    settle(page)
    expect_selection(page, 0, 1, "across", "0,0,0")
    assert sent_selections(mock) == [select_cell_message(0, 1, "across")]


def test_ac1_tapping_the_only_word_cell_again_changes_nothing(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, note_view(), 0)

    cell_at(page, 0, 1).click()
    expect_selection(page, 0, 1, "across", "0,0,0")
    cell_at(page, 0, 1).click()
    settle(page)

    expect_selection(page, 0, 1, "across", "0,0,0")
    assert sent_selections(mock) == [select_cell_message(0, 1, "across")]


def test_ac1_tapping_a_clue_separator_changes_nothing_and_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    separator = cell_at(page, 0, 0).get_by_test_id("clue-separator")

    separator.dispatch_event("click")
    settle(page)
    expect_nothing_selected(page)

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    separator.dispatch_event("click")
    settle(page)

    expect_selection(page, 2, 2, "across", "2,0,0")
    assert positions_with(page, "data-in-word") == [(2, 1), (2, 2), (2, 3), (2, 4)]
    assert sent_selections(mock) == [select_cell_message(2, 2, "across")]


def test_ac1_tapping_outside_the_grid_changes_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    page.mouse.click(2, 2)
    page.get_by_test_id("clue-bar").click()
    settle(page)

    expect_selection(page, 2, 2, "across", "2,0,0")
    assert sent_selections(mock) == [select_cell_message(2, 2, "across")]


def test_ac1_a_second_snapshot_keeps_a_selection_that_still_has_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    next_view = with_letter_cells(
        grid_view(fx01_grid), [(1, 1, {"letter": "A"}), (2, 2, {"letter": "I"})]
    )

    show_snapshot(page, mock, next_view, 1)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    settle(page)

    expect_selection(page, 1, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert active_clue_texts(page) == ["De la marine"]
    assert len(sent_selections(mock)) == 2


def test_ac1_a_second_snapshot_clears_a_selection_without_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")

    show_snapshot(page, mock, note_view(), 1)
    settle(page)

    expect_nothing_selected(page)
    assert positions_with(page, "data-selected") == []
    assert positions_with(page, "data-in-word") == []
    assert sent_selections(mock) == [select_cell_message(0, 1, "down")]


# ---- AC-2: tapping the selected cell switches direction ----------------------


def test_ac2_tapping_the_selected_cell_switches_between_its_two_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]
    assert active_clue_texts(page) == ["Passoire fine"]

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    assert positions_with(page, "data-in-word") == [
        (0, 1),
        (1, 1),
        (2, 1),
        (3, 1),
        (4, 1),
    ]
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["De la marine"]

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]


def test_ac2_tapping_a_cell_with_a_down_word_only_leaves_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")
    tap(page, 0, 1)
    settle(page)

    expect_selection(page, 0, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]
    assert positions_with(page, "data-selected") == [(0, 1)]


def test_ac2_tapping_a_cell_with_an_across_word_only_leaves_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")
    tap(page, 1, 0)
    settle(page)

    expect_selection(page, 1, 0, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]
    assert positions_with(page, "data-selected") == [(1, 0)]


def test_ac2_switching_works_on_another_two_word_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    tap(page, 2, 2)

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    assert active_clue_texts(page) == ["Artiste muet"]
