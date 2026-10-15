"""Tests of spec 007, AC-5 and AC-6: the `select_cell` message, and nested runs.

AC-5: each selection change sends one `select_cell`.
AC-6: the selected word is the word that was chosen, even when its clue starts
inside a longer run of the same direction (hand-built view), and the clue bar is
a labelled region.
The shared setup is in `spec007_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Arrow, Grid
from nock.protocol import (
    ClueCellView,
    ClueView,
    EmptyCellView,
    GridView,
    Join,
    LetterCellView,
)
from spec007_harness import (
    MockRoomSocket,
    active_clue_texts,
    clue_named,
    expect_selection,
    grid_from_text,
    load_fr,
    open_fx01,
    open_mock_room,
    positions_with,
    select_cell_message,
    sent_messages,
    sent_selections,
    settle,
    show_snapshot,
    tap,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-5: one select_cell per selection change ------------------------------


def test_ac5_each_selection_change_sends_one_select_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", "0,0,0")
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")
    tap(page, 0, 1)
    expect_selection(page, 0, 1, "down", "0,0,1")
    tap(page, 0, 1)
    settle(page)

    messages = sent_messages(mock)
    assert isinstance(messages[0], Join)
    assert messages[1:] == [
        select_cell_message(1, 1, "across"),
        select_cell_message(1, 1, "down"),
        select_cell_message(0, 1, "down"),
    ]


def test_ac5_nothing_is_sent_before_a_selection_change(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    settle(page)

    messages = sent_messages(mock)
    assert len(messages) == 1
    assert isinstance(messages[0], Join)


def test_ac5_a_move_to_a_cell_with_a_forced_direction_is_sent_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,1")

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", "0,0,0")
    settle(page)

    assert sent_selections(mock) == [
        select_cell_message(1, 1, "across"),
        select_cell_message(1, 1, "down"),
        select_cell_message(1, 0, "across"),
    ]


def test_ac5_a_clue_tap_that_changes_the_selection_sends_its_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])

    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    settle(page)

    assert sent_selections(mock) == [select_cell_message(2, 2, "down")]


def test_ac5_selecting_still_works_locally_when_the_socket_is_closed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    mock.close(1011)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    sent_before = len(mock.frames_without_pings())

    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "down", "0,2,0")
    settle(page)

    assert len(mock.frames_without_pings()) == sent_before
    assert sent_selections(mock) == []
    assert page_errors == []
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Artiste muet")


# ---- AC-6: a clue tap selects its own word, even inside a longer run ---------


def letter_cell_view(row: int, column: int) -> LetterCellView:
    """An empty letter cell."""
    return LetterCellView(
        row=row,
        column=column,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )


def nested_run_view() -> GridView:
    """A 2 by 4 grid whose column 1 holds two down words ending on the same cell.

    "Long" starts at (0, 1) and runs to (3, 1). "Court" starts at (1, 1), in the
    middle of that run, and ends on the same cell.
    """
    long_clue_cell = ClueCellView(
        row=0,
        column=0,
        clues=(ClueView(text="Long", arrow=Arrow.RIGHT_THEN_DOWN),),
    )
    short_clue_cell = ClueCellView(
        row=1,
        column=0,
        clues=(ClueView(text="Court", arrow=Arrow.RIGHT_THEN_DOWN),),
    )
    cells = (
        long_clue_cell,
        letter_cell_view(0, 1),
        short_clue_cell,
        letter_cell_view(1, 1),
        EmptyCellView(row=2, column=0),
        letter_cell_view(2, 1),
        EmptyCellView(row=3, column=0),
        letter_cell_view(3, 1),
    )
    return GridView(width=2, height=4, cells=cells)


LONG_WORD_CELLS = [(0, 1), (1, 1), (2, 1), (3, 1)]
SHORT_WORD_CELLS = [(1, 1), (2, 1), (3, 1)]


def open_nested_run(page: Page, base_url: str) -> MockRoomSocket:
    mock = open_mock_room(page, base_url)
    show_snapshot(page, mock, nested_run_view(), 0)
    expect(page.get_by_test_id("cell")).to_have_count(8)
    return mock


def test_ac6_tapping_the_clue_of_a_word_inside_a_longer_run_selects_its_own_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    clue_named(page, "Court").click()

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert positions_with(page, "data-in-word") == SHORT_WORD_CELLS
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["Court"]


def test_ac6_the_clue_bar_shows_the_clue_that_was_tapped(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    clue_named(page, "Court").click()

    expect_selection(page, 1, 1, "down", "1,0,0")
    bar = page.get_by_test_id("clue-bar")
    expect(bar).to_have_attribute("data-word", "1,0,0")
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Court")


def test_ac6_tapping_the_clue_of_the_longer_word_selects_the_longer_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    clue_named(page, "Long").click()

    expect_selection(page, 0, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert active_clue_texts(page) == ["Long"]


def test_ac6_tapping_another_cell_of_the_run_applies_the_longest_word_rule(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    tap(page, 2, 1)

    expect_selection(page, 2, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert active_clue_texts(page) == ["Long"]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Long")


def test_ac6_tapping_the_selected_cell_keeps_the_word_chosen_by_its_clue(
    page: Page, live_server: str
) -> None:
    mock = open_nested_run(page, live_server)
    clue_named(page, "Court").click()
    expect_selection(page, 1, 1, "down", "1,0,0")

    tap(page, 1, 1)
    settle(page)

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert positions_with(page, "data-in-word") == SHORT_WORD_CELLS
    assert active_clue_texts(page) == ["Court"]
    assert sent_selections(mock) == [select_cell_message(1, 1, "down")]


def test_ac6_a_change_of_word_alone_sends_no_second_select_cell(
    page: Page, live_server: str
) -> None:
    mock = open_nested_run(page, live_server)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", "0,0,0")

    clue_named(page, "Court").click()
    settle(page)

    expect_selection(page, 1, 1, "down", "1,0,0")
    assert active_clue_texts(page) == ["Court"]
    assert sent_selections(mock) == [select_cell_message(1, 1, "down")]


def test_ac6_a_shared_cell_tapped_with_no_clue_involved_selects_the_longest_word(
    page: Page, live_server: str
) -> None:
    open_nested_run(page, live_server)

    tap(page, 1, 1)

    expect_selection(page, 1, 1, "down", "0,0,0")
    assert positions_with(page, "data-in-word") == LONG_WORD_CELLS
    assert positions_with(page, "data-selected") == [(1, 1)]
    assert active_clue_texts(page) == ["Long"]
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Long")


def test_ac6_the_clue_bar_is_a_labelled_region(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    bar = page.get_by_test_id("clue-bar")

    expect(bar).to_have_attribute("role", "region")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
