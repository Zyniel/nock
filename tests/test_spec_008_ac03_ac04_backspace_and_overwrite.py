"""Tests of spec 008, AC-3 and AC-4: Backspace and typing over letters.

AC-3: Backspace clears the cell, then moves back (and the locked cells it meets).
AC-4: typing replaces a letter, unless the cell is locked. The shared setup is in
`spec008_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import Erase
from spec008_harness import (
    ACROSS_W1,
    DOWN_W2,
    across,
    cell_at,
    dispatch_key,
    expect_edits,
    expect_letter,
    expect_letters,
    expect_selection,
    grid_from_text,
    open_fx01,
    press,
    put,
    sent_edits,
    sent_selections,
    settle,
    tap,
    wait_until,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def rub(row: int, column: int) -> Erase:
    return Erase(row=row, column=column)


# ---- AC-3: Backspace clears, then moves back ---------------------------------


def test_ac3_backspace_clears_the_cell_then_moves_back_and_clears(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A"})],
    )
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    press(page, "Backspace")

    expect_letter(page, 1, 1, "")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "T")
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "")
    expect_edits(page, mock, [rub(1, 1), rub(1, 0)])

    # First cell of the word and empty: nothing changes, nothing is sent.
    assert dispatch_key(page, "Backspace") is False
    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "", (1, 1): ""})
    expect_edits(page, mock, [rub(1, 1), rub(1, 0)])
    assert sent_selections(mock) == [across(1, 1), across(1, 0)]


def test_ac3_the_erase_frame_has_a_null_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 1, {"letter": "A"})])
    tap(page, 1, 1)

    press(page, "Backspace")

    wait_until(page, lambda: len(sent_edits(mock)) == 1)
    erase_frames = []
    for frame in mock.received:
        if json.loads(frame)["type"] == "erase":
            erase_frames.append(json.loads(frame))
    assert erase_frames == [{"type": "erase", "row": 1, "column": 1, "base_seq": None}]


def test_ac3_backspace_on_an_empty_cell_moves_back_without_sending_for_an_empty_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 1, {"letter": "A"})])
    tap(page, 1, 2)

    press(page, "Backspace")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letter(page, 1, 1, "")
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_edits(page, mock, [rub(1, 1)])
    assert sent_selections(mock) == [across(1, 2), across(1, 1), across(1, 0)]


def test_ac3_backspace_moves_back_along_a_down_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(0, 1, {"letter": "N"})])
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    press(page, "Backspace")

    expect_selection(page, 0, 1, "down", DOWN_W2)
    expect_letter(page, 0, 1, "")
    expect_edits(page, mock, [rub(0, 1)])


def test_ac3_backspace_on_a_locked_cell_moves_back_and_never_clears_a_locked_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 0, {"letter": "T", "locked": True}),
            (1, 1, {"letter": "A"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 2)
    expect_selection(page, 1, 2, "across", ACROSS_W1)

    press(page, "Backspace")

    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_letters(page, {(1, 1): "", (1, 2): "M", (1, 0): "T"})
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "T", (1, 2): "M"})
    expect_edits(page, mock, [rub(1, 1)])

    press(page, "Backspace")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 0, "T")
    expect_edits(page, mock, [rub(1, 1)])
    assert sent_selections(mock) == [across(1, 2), across(1, 1), across(1, 0)]


# ---- AC-4: typing over a letter, unless the cell is locked -------------------


def test_ac4_typing_replaces_a_letter_and_skips_over_a_locked_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 1, {"letter": "A", "author": "p2"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "across", ACROSS_W1)

    press(page, "e")

    expect_letter(page, 1, 1, "E")
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_letter(page, 1, 2, "M")
    expect_edits(page, mock, [put(1, 1, "E")])
    assert sent_selections(mock) == [across(1, 1), across(1, 3)]


def test_ac4_typing_on_a_locked_cell_changes_nothing_sends_nothing_and_stays(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 1, {"letter": "A", "author": "p2"}),
            (1, 2, {"letter": "M", "locked": True}),
        ],
    )
    tap(page, 1, 2)
    expect_selection(page, 1, 2, "across", ACROSS_W1)

    press(page, "x")
    press(page, "m")

    settle(page)
    expect_letter(page, 1, 2, "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_edits(page, mock, [])
    assert sent_selections(mock) == [across(1, 2)]


def test_ac4_a_snapshot_lock_on_a_first_cell_blocks_typing_there(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T", "locked": True})],
    )
    tap(page, 1, 0)

    press(page, "z")

    settle(page)
    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect_letter(page, 1, 1, "")
    expect_edits(page, mock, [])
