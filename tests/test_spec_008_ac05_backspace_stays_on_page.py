"""Tests of spec 008, AC-5: Backspace never leaves the page.

The grid has the focus and no cell is selected, reached with Tab or by a snapshot
that removed the selected word. The shared setup is in `spec008_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import CellView, EmptyCellView, grid_view
from spec008_harness import (
    ACROSS_W1,
    MockRoomSocket,
    dispatch_key,
    expect_selection,
    grid_from_text,
    open_fx01,
    sent_edits,
    settle,
    snapshot_frame,
    tap,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-5: Backspace never leaves the page -----------------------------------


def focus_grid_by_tab(page: Page, mock: MockRoomSocket) -> None:
    """Focus the grid with the Tab key, with no cell selected."""
    page.keyboard.press("Tab")
    grid = page.get_by_test_id("grid")
    for _ in range(10):
        if grid.evaluate("(element) => element === document.activeElement"):
            break
        page.keyboard.press("Tab")
    expect(grid).to_be_focused()
    expect(grid).to_have_attribute("data-selected-row", "")


def focus_grid_after_word_removed(
    page: Page, mock: MockRoomSocket, fx01_grid: Grid
) -> None:
    """Select (1, 0), then send a snapshot where that cell is no longer a letter."""
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    view = grid_view(fx01_grid)
    new_cells: list[CellView] = []
    for cell in view.cells:
        if cell.row == 1 and cell.column == 0:
            new_cells.append(EmptyCellView(row=1, column=0))
        else:
            new_cells.append(cell)
    mock.send(snapshot_frame(view.model_copy(update={"cells": tuple(new_cells)}), 1))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "1")
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_be_focused()


def letters_shown(page: Page) -> list[str]:
    """The data-letter of every cell, in document order."""
    script = (
        "() => Array.from(document.querySelectorAll('[data-testid=\"cell\"]'))"
        ".map((cell) => cell.getAttribute('data-letter') ?? '')"
    )
    return list(page.evaluate(script))


@pytest.fixture(params=["tab", "word_removed"])
def unselected_focused_grid(
    request: pytest.FixtureRequest,
    page: Page,
    live_server: str,
    fx01_grid: Grid,
) -> MockRoomSocket:
    """A room whose grid has the focus and no selected cell."""
    mock = open_fx01(page, live_server, fx01_grid)
    if request.param == "tab":
        focus_grid_by_tab(page, mock)
    else:
        focus_grid_after_word_removed(page, mock, fx01_grid)
    return mock


def test_ac5_a_dispatched_backspace_with_no_selection_is_prevented(
    page: Page, unselected_focused_grid: MockRoomSocket
) -> None:
    assert dispatch_key(page, "Backspace") is False


def test_ac5_a_dispatched_backspace_with_no_selection_changes_nothing(
    page: Page, unselected_focused_grid: MockRoomSocket
) -> None:
    mock = unselected_focused_grid
    letters_before = letters_shown(page)
    frames_before = len(mock.received)

    dispatch_key(page, "Backspace")

    settle(page)
    assert letters_shown(page) == letters_before
    assert page.get_by_test_id("grid").get_attribute("data-selected-row") == ""
    assert sent_edits(mock) == []
    assert len(mock.received) == frames_before


def test_ac5_a_dispatched_backspace_with_no_selection_keeps_the_room_url(
    page: Page, live_server: str, unselected_focused_grid: MockRoomSocket
) -> None:
    dispatch_key(page, "Backspace")

    settle(page)
    assert page.url == f"{live_server}/r/ABC123"


def test_ac5_a_real_backspace_with_no_selection_keeps_the_room_url(
    page: Page, live_server: str, unselected_focused_grid: MockRoomSocket
) -> None:
    mock = unselected_focused_grid
    frames_before = len(mock.received)

    page.keyboard.press("Backspace")

    settle(page)
    assert page.url == f"{live_server}/r/ABC123"
    assert sent_edits(mock) == []
    assert len(mock.received) == frames_before
