"""Tests of spec 009, AC-2: Tab and Shift+Tab walk the unfinished words.

The page is tested with a mocked socket on FX-01. Tab and Alt+Tab, whose default
action the page prevents or leaves to the browser, are also checked through
dispatched `keydown` events, which report whether the default action was
prevented. The shared setup is in `spec009_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid, LetterCell
from spec009_harness import (
    ACROSS_LEST,
    ACROSS_W1,
    DOWN_W2,
    ChangeList,
    across,
    dispatch_key,
    down,
    expect_selection,
    grid_from_text,
    open_fx01,
    sent_selections,
    settle,
    tap,
)

DOWN_IDES = "0,3,0"


# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def all_filled(
    fx01_grid: Grid,
    empty: list[tuple[int, int]],
    locked: list[tuple[int, int]],
) -> ChangeList:
    """Changes filling every letter cell of FX-01 except those in `empty`."""
    changes: ChangeList = []
    for cell in fx01_grid.cells:
        if not isinstance(cell, LetterCell):
            continue
        position = (cell.row, cell.column)
        if position in empty:
            continue
        update: dict[str, object] = {"letter": "A"}
        if position in locked:
            update["locked"] = True
        changes.append((cell.row, cell.column, update))
    return changes


# ---- AC-2: Tab and Shift+Tab -------------------------------------------------

MIME_FINISHED: ChangeList = [
    (1, 2, {"letter": "M"}),
    (2, 2, {"letter": "I"}),
    (3, 2, {"letter": "M"}),
    (4, 2, {"letter": "E"}),
]


def test_ac2_tab_and_shift_tab_walk_the_unfinished_words_with_wrap(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("Tab")
    expect_selection(page, 1, 3, "down", DOWN_IDES)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 0, 1, "down", DOWN_W2)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("Shift+Tab")
    expect_selection(page, 4, 1, "across", ACROSS_LEST)

    assert sent_selections(mock) == [
        down(0, 1),
        down(1, 3),
        down(0, 1),
        across(1, 0),
        across(4, 1),
    ]
    expect(page.get_by_test_id("grid")).to_be_focused()


def test_ac2_tab_wraps_from_the_last_word_to_the_first(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    tap(page, 4, 1)
    expect_selection(page, 4, 1, "across", ACROSS_LEST)

    page.keyboard.press("Tab")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(4, 1), across(1, 0)]


def test_ac2_tab_with_nothing_selected_starts_at_the_first_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    page.get_by_test_id("grid").focus()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "")

    page.keyboard.press("Tab")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 0)]


def test_ac2_shift_tab_with_nothing_selected_starts_after_the_last_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, MIME_FINISHED)
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Shift+Tab")

    expect_selection(page, 4, 1, "across", ACROSS_LEST)
    assert sent_selections(mock) == [across(4, 1)]


def test_ac2_tab_lands_on_the_first_unfilled_cell_not_the_first_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A", "locked": True})],
    )
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Tab")

    expect_selection(page, 1, 2, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 2)]


def test_ac2_tab_reselects_the_only_unfinished_word_on_its_unfilled_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[(1, 0)], locked=[])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    tap(page, 1, 3)
    expect_selection(page, 1, 3, "across", ACROSS_W1)

    page.keyboard.press("Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    tap(page, 1, 2)
    page.keyboard.press("Shift+Tab")
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    assert sent_selections(mock) == [
        across(1, 3),
        across(1, 0),
        across(1, 2),
        across(1, 0),
    ]


def test_ac2_when_every_word_is_finished_tab_changes_nothing_and_keeps_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[], locked=[(1, 0), (3, 3), (4, 4)])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    grid = page.get_by_test_id("grid")

    page.keyboard.press("Tab")
    expect(grid).to_be_focused()
    page.keyboard.press("Shift+Tab")
    expect(grid).to_be_focused()

    assert dispatch_key(page, "Tab") is False
    assert dispatch_key(page, "Tab", shift=True) is False

    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect(grid).to_be_focused()
    assert sent_selections(mock) == [across(1, 1)]
    assert len(mock.received) == 2


def test_ac2_a_word_whose_remaining_cells_are_locked_or_filled_is_finished(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes = all_filled(fx01_grid, empty=[(4, 1)], locked=[(1, 0), (1, 1), (1, 3)])
    mock = open_fx01(page, live_server, fx01_grid, changes)
    page.get_by_test_id("grid").focus()

    page.keyboard.press("Tab")

    # (4, 1) is the last cell of NAVAL (0,0,1) and the first of LEST (4,0,0):
    # only those two words are unfinished, in clue order.
    expect_selection(page, 4, 1, "down", DOWN_W2)
    page.keyboard.press("Tab")
    expect_selection(page, 4, 1, "across", ACROSS_LEST)
    assert sent_selections(mock) == [down(4, 1), across(4, 1)]


def test_ac2_tab_with_the_focus_on_another_control_moves_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    page.evaluate(
        "() => { for (const name of ['first', 'second']) {"
        " const button = document.createElement('button');"
        " button.id = name; document.body.append(button); } }"
    )
    page.locator("#first").focus()

    page.keyboard.press("Tab")

    expect(page.locator("#second")).to_be_focused()
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]


def test_ac2_handled_tab_is_prevented_and_alt_tab_is_left_to_the_browser(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)

    assert dispatch_key(page, "Tab", alt=True) is True
    assert dispatch_key(page, "Tab", ctrl=True) is True
    settle(page)
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    assert sent_selections(mock) == [across(1, 1)]

    assert dispatch_key(page, "Tab") is False
    assert dispatch_key(page, "Tab", shift=True) is False
