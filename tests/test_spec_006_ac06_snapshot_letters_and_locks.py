"""Tests of spec 006, AC-6: the grid shows the letters and locks of the snapshot.

The page is tested with spec 040's mocked socket. The shared setup is in
`spec006_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import grid_view
from spec006_harness import (
    cell_at,
    grid_from_text,
    open_mock_room,
    show_snapshot,
    with_letter_cells,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-6: the grid shows the letters and locks of the snapshot --------------


def test_ac6_letters_and_locks_of_the_snapshot_are_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, view, 0)

    first = cell_at(page, 1, 0)
    expect(first).to_have_attribute("data-letter", "T")
    expect(first).to_have_attribute("data-locked", "false")
    expect(first).to_have_text("T")
    locked = cell_at(page, 1, 2)
    expect(locked).to_have_attribute("data-letter", "M")
    expect(locked).to_have_attribute("data-locked", "true")
    expect(locked).to_have_text("M")
    untouched = cell_at(page, 1, 1)
    expect(untouched).to_have_attribute("data-letter", "")
    expect(untouched).to_have_attribute("data-locked", "false")
    expect(untouched).to_have_text("")


def test_ac6_only_the_changed_cells_carry_a_letter_or_a_lock(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, view, 0)

    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.locator('[data-testid="cell"][data-locked="true"]')).to_have_count(1)
    expect(page.locator('[data-testid="cell"][data-locked="false"]')).to_have_count(17)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(16)


def test_ac6_a_second_snapshot_without_the_letter_empties_the_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    with_letters = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )
    show_snapshot(page, mock, with_letters, 0)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    emptied = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 2, {"letter": "M", "locked": True})],
    )

    show_snapshot(page, mock, emptied, 1)

    first = cell_at(page, 1, 0)
    expect(first).to_have_attribute("data-letter", "")
    expect(first).to_have_text("")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")


def test_ac6_a_second_snapshot_replaces_letters_and_locks(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    first_view = with_letter_cells(
        grid_view(fx01_grid), [(1, 2, {"letter": "M", "locked": True})]
    )
    show_snapshot(page, mock, first_view, 0)
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    second_view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 2, {"letter": "N"}), (3, 4, {"letter": "Z", "locked": True})],
    )

    show_snapshot(page, mock, second_view, 1)

    changed = cell_at(page, 1, 2)
    expect(changed).to_have_attribute("data-letter", "N")
    expect(changed).to_have_attribute("data-locked", "false")
    expect(changed).to_have_text("N")
    newly_locked = cell_at(page, 3, 4)
    expect(newly_locked).to_have_attribute("data-letter", "Z")
    expect(newly_locked).to_have_attribute("data-locked", "true")
    expect(page.locator('[data-testid="cell"][data-locked="true"]')).to_have_count(1)


def test_ac6_the_last_grid_stays_on_screen_after_the_socket_closes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    view = with_letter_cells(
        grid_view(fx01_grid),
        [(1, 0, {"letter": "T"}), (1, 2, {"letter": "M", "locked": True})],
    )
    show_snapshot(page, mock, view, 0)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    expect(page.get_by_test_id("grid-viewport")).to_be_visible()
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect(cell_at(page, 1, 2)).to_have_text("M")
