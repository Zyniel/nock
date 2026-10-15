"""Tests of spec 008, AC-1: typing fills the cell and moves along the word.

Across and down words, the last cell, a letter already there, locked cells, keys
with nothing to type into, and a closed socket. The shared setup is in
`spec008_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import SelectCell
from spec008_harness import (
    ACROSS_W1,
    DOWN_W2,
    across,
    dispatch_key,
    expect_edits,
    expect_letter,
    expect_letters,
    expect_selection,
    grid_from_text,
    open_fx01,
    press,
    press_all,
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


def down(row: int, column: int) -> SelectCell:
    return SelectCell(row=row, column=column, direction="down")


# ---- AC-1: typing fills the cell and moves along the word --------------------


def test_ac1_typing_fills_the_word_and_stays_on_its_last_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    press(page, "t")

    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "T")])

    press_all(page, ["a", "m", "i", "s"])

    expect_letters(
        page, {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I", (1, 4): "S"}
    )
    expect_selection(page, 1, 4, "across", ACROSS_W1)

    press(page, "x")

    expect_letter(page, 1, 4, "X")
    expect_selection(page, 1, 4, "across", ACROSS_W1)
    expect_letters(page, {(1, 0): "T", (1, 1): "A", (1, 2): "M", (1, 3): "I"})
    expect_edits(
        page,
        mock,
        [
            put(1, 0, "T"),
            put(1, 1, "A"),
            put(1, 2, "M"),
            put(1, 3, "I"),
            put(1, 4, "S"),
            put(1, 4, "X"),
        ],
    )
    # One select_cell per selection change, none when the cursor stays.
    assert sent_selections(mock) == [
        across(1, 0),
        across(1, 1),
        across(1, 2),
        across(1, 3),
        across(1, 4),
    ]


def test_ac1_the_edit_letter_frame_has_a_null_base_seq_and_an_upper_case_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    press(page, "t")

    wait_until(page, lambda: len(sent_edits(mock)) == 1)
    edit_frames = []
    for frame in mock.received:
        if json.loads(frame)["type"] == "edit_letter":
            edit_frames.append(json.loads(frame))
    assert edit_frames == [
        {
            "type": "edit_letter",
            "row": 1,
            "column": 0,
            "letter": "T",
            "base_seq": None,
        }
    ]


def test_ac1_the_direction_is_kept_when_typing_down_a_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 1)
    tap(page, 1, 1)
    expect_selection(page, 1, 1, "down", DOWN_W2)

    press(page, "x")

    expect_letter(page, 1, 1, "X")
    expect_selection(page, 2, 1, "down", DOWN_W2)

    press_all(page, ["v", "a", "l"])

    expect_letters(page, {(2, 1): "V", (3, 1): "A", (4, 1): "L"})
    expect_selection(page, 4, 1, "down", DOWN_W2)

    press(page, "z")

    expect_letter(page, 4, 1, "Z")
    expect_selection(page, 4, 1, "down", DOWN_W2)
    expect_letters(page, {(1, 1): "X", (2, 1): "V", (3, 1): "A"})
    expect_edits(
        page,
        mock,
        [
            put(1, 1, "X"),
            put(2, 1, "V"),
            put(3, 1, "A"),
            put(4, 1, "L"),
            put(4, 1, "Z"),
        ],
    )
    assert sent_selections(mock) == [
        across(1, 1),
        down(1, 1),
        down(2, 1),
        down(3, 1),
        down(4, 1),
    ]


def test_ac1_typing_the_letter_already_there_sends_nothing_and_moves_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [(1, 0, {"letter": "T"}), (1, 1, {"letter": "A"})],
    )
    tap(page, 1, 0)

    press(page, "t")

    expect_letter(page, 1, 0, "T")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [])

    press(page, "a")

    expect_letter(page, 1, 1, "A")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_edits(page, mock, [])

    press(page, "m")

    expect_letter(page, 1, 2, "M")
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 2, "M")])
    assert sent_selections(mock) == [
        across(1, 0),
        across(1, 1),
        across(1, 2),
        across(1, 3),
    ]


def test_ac1_the_cursor_stays_when_every_later_cell_is_locked(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        [
            (1, 3, {"letter": "I", "locked": True}),
            (1, 4, {"letter": "S", "locked": True}),
        ],
    )
    tap(page, 1, 2)

    press(page, "m")

    expect_letter(page, 1, 2, "M")
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    expect_letters(page, {(1, 3): "I", (1, 4): "S"})
    expect_edits(page, mock, [put(1, 2, "M")])
    assert sent_selections(mock) == [across(1, 2)]


def test_ac1_keys_do_nothing_without_a_selection_or_with_the_focus_elsewhere(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    grid = page.get_by_test_id("grid")
    grid.focus()

    press(page, "a")
    # Not pressed for real: with nothing handling it, WebKit goes back in history.
    dispatch_key(page, "Backspace")

    settle(page)
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(page.locator('[data-testid="cell"][data-letter="A"]')).to_have_count(0)
    assert len(mock.frames_without_pings()) == 1

    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    page.evaluate(
        "() => { const input = document.createElement('input');"
        " input.id = 'other-input'; document.body.append(input); }"
    )
    page.locator("#other-input").focus()
    expect(page.locator("#other-input")).to_be_focused()

    press_all(page, ["b", "c"])

    expect(page.locator("#other-input")).to_have_value("bc")
    page.evaluate("() => document.activeElement.blur()")
    press(page, "d")
    settle(page)
    expect_letter(page, 1, 0, "")
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    assert sent_edits(mock) == []
    assert sent_selections(mock) == [across(1, 0)]


def test_ac1_after_the_socket_closes_cells_change_locally_and_nothing_is_sent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    mock.close(1011)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    sent_before = len(mock.frames_without_pings())

    tap(page, 1, 0)
    press_all(page, ["t", "a"])

    expect_letters(page, {(1, 0): "T", (1, 1): "A"})
    expect_selection(page, 1, 2, "across", ACROSS_W1)
    settle(page)
    assert len(mock.frames_without_pings()) == sent_before
    assert page_errors == []
