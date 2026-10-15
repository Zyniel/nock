"""Tests of spec 023, AC-5: the strike is cleared by a new letter or a lock.

The page is driven with spec 040's mocked socket. The shared setup is in
`spec023_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellRef,
    CheckResult,
    CheckTarget,
    LetterChanged,
)
from spec023_harness import (
    MIME,
    ChangeList,
    cell_at,
    grid_from_text,
    make_catalogue,
    open_fx01,
    refs,
    sent_letters,
    strike_through,
    wait_until_page,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers for the page tests ----


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return event.model_dump_json()


def cell_locked_frame(
    seq: int, row: int, column: int, letter: str, revealed: bool
) -> str:
    event = CellLocked(
        seq=seq, row=row, column=column, letter=letter, revealed=revealed
    )
    return event.model_dump_json()


def check_result_frame(
    seq: int,
    target: CheckTarget,
    correct: tuple[CellRef, ...],
    wrong: tuple[CellRef, ...],
) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=target, correct=correct, wrong=wrong
    )
    return event.model_dump_json()


# ---- AC-5: the strike is cleared by a new letter or a lock ----


def struck_x_and_plain_q() -> ChangeList:
    return [
        (1, 1, {"letter": "X", "author": "p2", "wrong": True}),
        (2, 2, {"letter": "Q", "author": "p2", "wrong": False}),
    ]


def test_ac5_the_snapshot_strikes_the_cell_flagged_wrong(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    struck = cell_at(page, 1, 1)
    expect(struck).to_have_attribute("data-wrong", "true")
    assert "line-through" in strike_through(struck)
    plain = cell_at(page, 2, 2)
    expect(plain).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(plain)


def test_ac5_a_check_result_strikes_the_cells_of_its_wrong_list(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    mock.send(check_result_frame(6, MIME, correct=(), wrong=refs((2, 2))))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "true")
    assert "line-through" in strike_through(cell_at(page, 2, 2))
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "true")


def test_ac5_a_new_letter_clears_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    mock.send(letter_changed_frame(6, 1, 1, "A", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(cell_at(page, 1, 1))


def test_ac5_a_lock_clears_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())
    mock.send(check_result_frame(6, MIME, correct=(), wrong=refs((2, 2))))
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "true")

    mock.send(letter_changed_frame(7, 1, 1, "A", "p2"))
    mock.send(cell_locked_frame(8, 2, 2, "I", revealed=True))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "8")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-locked", "true")


def test_ac5_a_pending_edit_of_mine_hides_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())
    cell_at(page, 1, 1).click()
    page.keyboard.press("b")

    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    expect(cell).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(cell)
    wait_until_page(page, lambda: len(sent_letters(mock)) == 1)
