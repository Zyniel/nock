"""Tests of spec 020, AC-6: pending pencil edits and confirmations are matched and
resent by their kind.

The page with a mocked socket. The matching (the refinement of spec 018's "Pending
queue matching": an own `letter_changed` answers the oldest pending edit only with
the same cell, letter and pencil flag) and the resend after a reconnection (spec
017 AC-2: each pending edit sent again as the message of its kind, oldest first,
with its recorded `base_seq`) use spec 017's reconnection mock; the edit errors use
spec 024's mocked socket. The shared setup is in `spec020_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import ConfirmPencil, ErrorCode, PencilEdit
from spec017_harness import (
    LOSS_BUDGET_MS,
    STORED_JOIN,
    MockConnection,
    banner,
    first_join,
    joined_room,
    room_page,
)
from spec017_harness import snapshot_frame as reconnect_snapshot_frame
from spec020_harness import (
    click_confirm,
    error_frame,
    expect_cell_shows,
    letter_changed_frame,
    tap,
    turn_pencil_mode_on,
    wait_for_edit_messages,
)
from spec024_harness import (
    ChangeList,
    expect_selection,
    expect_seq,
    grid_from_text,
    make_catalogue,
    open_room,
)

WORD_W1 = "0,0,0"

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- The first steps of AC-6 ----


def pencil_t_answered_by_its_kind(page: Page, connection: MockConnection) -> None:
    """Type a pencil `T` at (1, 0); answer it with pencil false (seq 6), then true.

    The `letter_changed` with `pencil` false (the shape of an undo's result) does
    not answer the pending pencil edit; the one with `pencil` true (seq 7) does.
    """
    turn_pencil_mode_on(page)
    tap(page, 1, 0)
    page.keyboard.press("t")
    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)
    sent = wait_for_edit_messages(page, lambda: connection.frames, 1)
    assert sent == [PencilEdit(row=1, column=0, letter="T")]

    connection.send(letter_changed_frame(6, 1, 0, "T", "p1", pencil=False))
    expect(room_page(page)).to_have_attribute("data-seq", "6")
    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)

    connection.send(letter_changed_frame(7, 1, 0, "T", "p1", pencil=True))
    expect(room_page(page)).to_have_attribute("data-seq", "7")
    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=False)


# ---- AC-6 ----


def test_ac6_only_an_own_letter_changed_with_the_pencil_flag_answers_a_pencil_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)

    pencil_t_answered_by_its_kind(page, room.connections[0])

    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=False)


def test_ac6_offline_pencil_edits_and_confirmations_are_resent_by_their_kind(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    first = room.connections[0]
    pencil_t_answered_by_its_kind(page, first)

    first.close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    expect_selection(page, 1, 1, "across", WORD_W1)
    page.keyboard.press("a")
    expect_cell_shows(page, 1, 1, "A", pencil=True, unconfirmed=True)
    tap(page, 1, 0)
    click_confirm(page)
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    still_pencil: ChangeList = [(1, 0, {"letter": "T", "pencil": True, "author": "p1"})]
    second.send(reconnect_snapshot_frame(fx01_grid, 9, still_pencil))
    expect(room_page(page)).to_have_attribute("data-seq", "9")

    resent = wait_for_edit_messages(page, lambda: second.frames, 2)
    assert resent == [
        PencilEdit(row=1, column=1, letter="A", base_seq=7),
        ConfirmPencil(row=1, column=0, base_seq=7),
    ]


def test_ac6_an_own_letter_changed_with_pencil_true_does_not_answer_a_confirmation(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "pencil": True, "author": "p1"})]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    tap(page, 1, 0)
    click_confirm(page)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [ConfirmPencil(row=1, column=0, base_seq=5)]

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1", pencil=True))
    expect_seq(page, 6)
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)

    mock.send(letter_changed_frame(7, 1, 0, "T", "p1", pencil=False))
    expect_seq(page, 7)
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)


def test_ac6_an_edit_error_removes_a_pending_pencil_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)
    page.keyboard.press("t")
    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [PencilEdit(row=1, column=0, letter="T")]

    mock.send(error_frame(ErrorCode.STALE_EDIT))

    expect_cell_shows(page, 1, 0, "", pencil=False, unconfirmed=False)
