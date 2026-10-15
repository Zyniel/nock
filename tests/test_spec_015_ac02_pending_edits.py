"""Tests of spec 015, AC-2: my own letter appears at once.

The page is checked in the browser with a mocked socket: the letter is shown
before the server confirms it, and each answer of the server (a confirmation, a
refusal, a snapshot) settles the pending edits. The shared setup is in
`spec015_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import (
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    grid_view,
    parse_client_message,
)
from spec015_harness import (
    SETTLE_MS,
    ChangeList,
    Edit,
    MockRoomSocket,
    cell_at,
    expect_cell,
    grid_from_text,
    letter_changed_frame,
    open_fx01,
    snapshot_frame,
    type_key,
    wait_until_page,
    with_letter_cells,
)

# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-2: my letter appears at once (browser, mocked socket) ----------------


def sent_edits(mock: MockRoomSocket) -> list[Edit]:
    edits: list[Edit] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def expect_edits(page: Page, mock: MockRoomSocket, expected: list[Edit]) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    wait_until_page(page, lambda: len(sent_edits(mock)) >= len(expected))
    page.wait_for_timeout(SETTLE_MS)
    assert sent_edits(mock) == expected


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def test_ac2_my_letter_shows_at_once_and_stays_unconfirmed_until_my_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()

    type_key(page, "t")

    expect_cell(page, 1, 0, "T", unconfirmed=True, author="")
    expect_edits(page, mock, [EditLetter(row=1, column=0, letter="T")])

    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True, author="p2")

    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))

    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_a_refused_edit_shows_the_confirmed_letter_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(error_frame(ErrorCode.CELL_LOCKED))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.RATE_LIMITED,
        ErrorCode.NOT_A_LETTER_CELL,
        ErrorCode.CELL_LOCKED,
        ErrorCode.STALE_EDIT,
        ErrorCode.GRID_SOLVED,
    ],
)
def test_ac2_each_edit_error_removes_the_oldest_pending_edit_only(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    mock.send(error_frame(code))

    expect_cell(page, 1, 0, "", unconfirmed=False)
    expect_cell(page, 1, 1, "A", unconfirmed=True)


@pytest.mark.parametrize(
    "code",
    [ErrorCode.NOT_HOST, ErrorCode.NOTHING_TO_UNDO, ErrorCode.INVALID_MESSAGE],
)
def test_ac2_other_errors_leave_the_pending_queue_unchanged(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    mock.send(error_frame(code))
    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))

    # The answer matched the oldest edit, (1, 0): the error took nothing off the queue.
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
    expect_cell(page, 1, 1, "A", unconfirmed=True)


def test_ac2_answers_match_the_pending_edits_first_in_first_out(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    type_key(page, "m")

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
    expect_cell(page, 1, 1, "A", unconfirmed=True)
    expect_cell(page, 1, 2, "M", unconfirmed=True)

    mock.send(error_frame(ErrorCode.RATE_LIMITED))
    expect_cell(page, 1, 1, "", unconfirmed=False)
    expect_cell(page, 1, 2, "M", unconfirmed=True)

    mock.send(letter_changed_frame(7, 1, 2, "M", "p1"))
    expect_cell(page, 1, 2, "M", unconfirmed=False, author="p1")


def test_ac2_the_newest_pending_edit_of_a_cell_is_the_one_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    cell_at(page, 1, 0).click()
    type_key(page, "x")
    expect_cell(page, 1, 0, "X", unconfirmed=True)
    expect_edits(
        page,
        mock,
        [
            EditLetter(row=1, column=0, letter="T"),
            EditLetter(row=1, column=0, letter="X"),
        ],
    )

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p1")
    expect_cell(page, 1, 0, "X", unconfirmed=True)

    mock.send(letter_changed_frame(7, 1, 0, "X", "p1"))

    expect_cell(page, 1, 0, "X", unconfirmed=False, author="p1")


def test_ac2_my_erase_shows_an_empty_cell_and_the_answer_clears_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        seq=5,
        changes=[(1, 0, {"letter": "T", "author": "p2"})],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p2")
    cell_at(page, 1, 0).click()

    type_key(page, "Backspace")

    expect_cell(page, 1, 0, "", unconfirmed=True, author="p2")
    expect_edits(page, mock, [Erase(row=1, column=0)])

    mock.send(letter_changed_frame(6, 1, 0, None, "p1"))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


def test_ac2_another_players_erase_empties_the_cell_and_its_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        seq=5,
        changes=[(1, 0, {"letter": "T", "author": "p2"})],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p2")

    mock.send(letter_changed_frame(6, 1, 0, None, "p3"))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


# ---- AC-2: pending edits and the other specs, snapshots, locked cells ---------


SOLVED_LETTERS: dict[tuple[int, int], str] = {
    (0, 1): "N",
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
    (3, 1): "A",
    (3, 2): "M",
    (3, 3): "E",
    (3, 4): "N",
    (4, 1): "L",
    (4, 2): "E",
    (4, 3): "S",
    (4, 4): "T",
}


def solved_except(empty: list[tuple[int, int]]) -> ChangeList:
    """Confirmed letters for every FX-01 letter cell but the `empty` ones."""
    changes: ChangeList = []
    for position, letter in SOLVED_LETTERS.items():
        if position not in empty:
            changes.append((position[0], position[1], {"letter": letter}))
    return changes


def clue_named(page: Page, text: str) -> Locator:
    """The `clue` element whose text is exactly `text`."""
    clue_text = page.get_by_test_id("clue-text").get_by_text(text, exact=True)
    return page.get_by_test_id("clue").filter(has=clue_text)


def expect_selected_cell(page: Page, row: int, column: int) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


def test_ac2_tab_skips_a_word_whose_last_cell_holds_my_unconfirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Guards specs 009 and 007 under pending edits: a cell shows my letter.

    Only (1, 4) is empty, so typing `s` there finishes the only unfinished word
    as shown. The mock never answers, so the letter stays pending. Tab must then
    find no unfinished word and leave the selection where it is.
    """
    mock = open_fx01(page, live_server, fx01_grid, changes=solved_except([(1, 4)]))
    cell_at(page, 1, 4).click()
    type_key(page, "s")
    expect_cell(page, 1, 4, "S", unconfirmed=True)
    cell_at(page, 1, 3).click()
    expect_selected_cell(page, 1, 3)
    frames_before_tab = len(mock.received)

    page.keyboard.press("Tab")
    page.wait_for_timeout(SETTLE_MS)

    expect_selected_cell(page, 1, 3)
    assert len(mock.received) == frames_before_tab


def test_ac2_a_clue_tap_skips_a_cell_that_shows_my_unconfirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Guards specs 007 and 009 under pending edits: a cell shows my letter.

    The mock never answers, so the `T` typed in (1, 0) stays pending. Tapping
    the clue of that word must select (1, 1), the first cell unfilled as shown.
    """
    open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    clue_named(page, "Artiste muet").click()
    expect_selected_cell(page, 1, 2)

    clue_named(page, "Passoire fine").click()

    expect_selected_cell(page, 1, 1)


def test_ac2_a_snapshot_after_a_reconnection_keeps_the_pending_edits(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    view = with_letter_cells(
        grid_view(fx01_grid), [(1, 1, {"letter": "A", "author": "p2"})]
    )

    mock.send(snapshot_frame(view, 9))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "9")
    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(10, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_a_locked_cell_shows_its_confirmed_letter_over_a_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    locked_cell: dict[str, object] = {"letter": "B", "author": "p2", "locked": True}
    view = with_letter_cells(grid_view(fx01_grid), [(1, 0, locked_cell)])

    mock.send(snapshot_frame(view, 9))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "9")
    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")
