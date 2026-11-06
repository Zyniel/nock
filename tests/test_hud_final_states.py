"""Tests of `client/hud.md` AC-28 to AC-31: a final status after the room showed
makes the grid read-only (rule 19).

Ana's page at 1280 by 720 on spec 043's mocked room (`hud_harness.open_fx01_room`,
or `open_room` with AC-29's snapshot), joined on FX-01 at seq 5.

AC-28: with the empty (1, 0) selected, the socket closes with 4001: the band under
the top bar (`room-status`, not visually hidden, its top on the top bar's bottom)
reads « Ce salon est ouvert dans un autre onglet. », a typed `t` leaves (1, 0)
empty, and `clue-next` selects NAVAL on (0, 1), the next unfinished word. After
`removed` (its `error`, then a close 1000) a typed `t` leaves (1, 0) empty alike.
Reconnecting with `T` typed at (1, 0) and not yet answered, the new socket's join
answered by `room_locked` and a close 1000 leaves (1, 0) empty and nothing pending.

AC-29: AC-29's snapshot holds Bob's pencil `T` at (1, 0) and Bob's `I` at (2, 2), so
that with MIME selected on (2, 2) every Aide item is enabled before the close (the
test checks it). After a close 4001, « Annuler » and the five items of « Vérifier »
and « Révéler » are disabled with the disabled look (their label in
`--nock-muted`, `_design/foundation.md` « Components »), and a forced press on any
sends nothing and leaves the Aide menu open (rule 9); with (1, 0) selected, the
confirm item is disabled alike.

AC-30: Ana's page on AC-29's snapshot with MIME selected on Bob's `I` at (2, 2),
after a close 4001. Backspace leaves `I` and the selection on (2, 2); ArrowDown
selects the empty (3, 2), where `t` then Backspace leave it empty and selected; a
press on (1, 0) selects it. At 360 by 740 on a touch screen, a tap on the in-app
keyboard's `T` and on ⌫ leaves `I` and the selection on (2, 2) alike.

AC-31: reconnecting (the socket lost, the band showing), « Annuler » pressed and
« Vérifier » « La lettre » and « Révéler » « La lettre » chosen on MIME, a rejoin
answered by `room_locked` and a close 1000 never sends the undo, the check or the
reveal (the mock got none since the loss, 300 ms after the close). Answered by a
snapshot instead, the same page sends them after it, in the order they were made:
the undo, the check of the letter (2, 2), the reveal of the letter (2, 2).

"A typed letter changes nothing" is read 300 ms after the key (`QUIET_MS`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import (
    CONNECTION_LOSS_MS,
    LOST_CLOSE_CODE,
    open_fx01_room,
    reconnect_with_t_pending,
)
from nock.grid import Grid
from nock.protocol import CellTarget, Check, ErrorCode, Reveal, Undo
from room_panels import open_aide
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of, wait_until
from spec043_harness import (
    COMPUTER,
    MUTED,
    PHONE,
    QUIET_MS,
    RoomMock,
    cell_at,
    colour_matches,
    error_frame,
    expect_selected,
    expect_word,
    fr_value,
    frames_sent_after,
    fx01_view,
    label_of,
    open_room,
    players_up_to,
    press_cell,
    same_position,
    select_mime,
    snapshot_frame,
)

REPLACED_CLOSE = 4001
SERVER_CLOSE = 1000
NAVAL_KEY = "0,0,1"
AIDE_ITEMS = [
    "check-letter",
    "check-word",
    "check-grid",
    "reveal-letter",
    "reveal-word",
]
AC29_CHANGES: list[tuple[int, int, dict[str, object]]] = [
    (1, 0, {"letter": "T", "pencil": True, "author": "p2"}),
    (2, 2, {"letter": "I", "author": "p2"}),
]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def computer_page(window: OpenWindow) -> Page:
    """A desktop page of 1280 by 720."""
    return window(COMPUTER[0], COMPUTER[1], False)


def expect_room_status(page: Page, status: str) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", status)


def expect_typed_t_leaves_1_0_empty(page: Page) -> None:
    """A `t` typed on the focused grid leaves (1, 0) empty."""
    expect(page.get_by_test_id("grid")).to_be_focused()
    page.keyboard.press("t")
    page.wait_for_timeout(QUIET_MS)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "")


def expect_disabled_look(item: Locator) -> None:
    """The item is disabled, its label in `--nock-muted`."""
    expect(item).to_be_disabled()
    label = label_of(item)
    assert label is not None
    assert colour_matches(label["colour"], MUTED), label["colour"]


def ac29_frame(grid: Grid) -> str:
    """AC-29's snapshot: Bob's pencil `T` at (1, 0) and his `I` at (2, 2)."""
    return snapshot_frame(fx01_view(grid, AC29_CHANGES), players_up_to(3))


def open_ac29(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """AC-29's room: Bob's pencil `T` at (1, 0) and his `I` at (2, 2)."""
    return open_room(page, base_url, ac29_frame(grid))


def close_with_4001(page: Page, mock: RoomMock) -> None:
    mock.close(REPLACED_CLOSE)
    expect_room_status(page, "replaced")


def expect_press_sends_nothing(page: Page, mock: RoomMock, item: Locator) -> None:
    """A forced press on a disabled item sends nothing and leaves the menu open."""
    frames = frames_sent_after(page, mock, lambda: item.click(force=True))
    assert frames == []
    expect(page.get_by_test_id("aide-menu")).to_be_visible()


# ---- AC-28: the grid is read-only after a final status -------------------------------


def test_ac28_after_a_close_4001_the_band_shows_t_changes_nothing_and_next_moves(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_fx01_room(page, live_server, fx01_grid)
    press_cell(page, 1, 0)

    mock.close(REPLACED_CLOSE)

    expect_room_status(page, "replaced")
    status = page.get_by_test_id("room-status")
    expect(status).to_be_visible()
    expect(status).to_have_text(fr_value("room.status.replaced"))
    assert "visually-hidden" not in str(status.get_attribute("class")).split()
    status_top = box_of(status).top
    bar_bottom = box_of(page.get_by_test_id("room-topbar")).bottom
    assert same_position(status_top, bar_bottom), (status_top, bar_bottom)
    expect_typed_t_leaves_1_0_empty(page)
    page.get_by_test_id("clue-next").click()
    expect_selected(page, 0, 1)
    expect_word(page, NAVAL_KEY)


def test_ac28_after_removed_a_typed_t_leaves_the_cell_empty(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_fx01_room(page, live_server, fx01_grid)
    press_cell(page, 1, 0)

    mock.send(error_frame(ErrorCode.REMOVED))
    mock.close(SERVER_CLOSE)

    expect_room_status(page, "removed")
    expect_typed_t_leaves_1_0_empty(page)


def test_ac28_a_rejoin_refused_with_room_locked_drops_the_pending_t(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_fx01_room(page, live_server, fx01_grid)
    reconnect_with_t_pending(page, mock)

    mock.send(error_frame(ErrorCode.ROOM_LOCKED))
    mock.close(SERVER_CLOSE)

    expect_room_status(page, "locked")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-pending", "0")


# ---- AC-29: « Annuler » and the Aide items are disabled ------------------------------


def test_ac29_after_a_close_4001_annuler_and_the_aide_items_are_disabled(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_ac29(page, live_server, fx01_grid)
    select_mime(page)
    open_aide(page)
    for test_id in AIDE_ITEMS:
        expect(page.get_by_test_id(test_id)).to_be_enabled()
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("undo-button")).to_be_enabled()

    close_with_4001(page, mock)
    open_aide(page)

    undo = page.get_by_test_id("undo-button")
    expect_disabled_look(undo)
    for test_id in AIDE_ITEMS:
        expect_disabled_look(page.get_by_test_id(test_id))
    for test_id in AIDE_ITEMS:
        expect_press_sends_nothing(page, mock, page.get_by_test_id(test_id))
    frames = frames_sent_after(page, mock, lambda: undo.click(force=True))
    assert frames == []


def test_ac29_after_a_close_4001_the_pencil_confirm_item_is_disabled(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_ac29(page, live_server, fx01_grid)
    press_cell(page, 1, 0)
    open_aide(page)
    expect(page.get_by_test_id("confirm-pencil")).to_be_enabled()
    page.keyboard.press("Escape")

    close_with_4001(page, mock)
    open_aide(page)

    confirm = page.get_by_test_id("confirm-pencil")
    expect_disabled_look(confirm)
    expect_press_sends_nothing(page, mock, confirm)


# ---- AC-30: the selection still moves, no key changes a cell -------------------------


def expect_cell_keeps(page: Page, row: int, column: int, letter: str) -> None:
    """Wait QUIET_MS, then expect the cell to hold `letter` and to be selected."""
    page.wait_for_timeout(QUIET_MS)
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)
    expect_selected(page, row, column)


def test_ac30_after_a_close_4001_the_keys_change_no_cell_and_the_selection_moves(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = computer_page(window)
    mock = open_ac29(page, live_server, fx01_grid)
    select_mime(page)
    close_with_4001(page, mock)
    expect(page.get_by_test_id("grid")).to_be_focused()

    page.keyboard.press("Backspace")

    expect_cell_keeps(page, 2, 2, "I")
    page.keyboard.press("ArrowDown")
    expect_selected(page, 3, 2)
    page.keyboard.press("t")
    expect_cell_keeps(page, 3, 2, "")
    page.keyboard.press("Backspace")
    expect_cell_keeps(page, 3, 2, "")
    press_cell(page, 1, 0)


def test_ac30_after_a_close_4001_the_in_app_keyboard_changes_no_cell(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], True)
    mock = open_ac29(page, live_server, fx01_grid)
    select_mime(page, touch=True)
    close_with_4001(page, mock)
    keyboard = page.get_by_test_id("keyboard")
    expect(keyboard).to_be_visible()

    keyboard.locator('[data-testid="key"][data-key="T"]').tap()

    expect_cell_keeps(page, 2, 2, "I")
    keyboard.get_by_test_id("key-delete").tap()
    expect_cell_keeps(page, 2, 2, "I")


# ---- AC-31: kept requests are never sent ---------------------------------------------


MIME_LETTER = CellTarget(row=2, column=2)
KEPT_REQUESTS: list[object] = [
    Undo(),
    Check(target=MIME_LETTER),
    Reveal(target=MIME_LETTER),
]


def kept_requests_sent(mock: RoomMock, sent_before: int) -> list[object]:
    """The undos, checks and reveals the mock got after its first `sent_before`
    frames, in order."""
    kept: list[object] = []
    for frame in mock.parsed_frames_after(sent_before):
        if isinstance(frame, (Undo, Check, Reveal)):
            kept.append(frame)
    return kept


def pick_aide_item(page: Page, test_id: str) -> None:
    """Open the Aide menu and choose one item, which closes the menu."""
    open_aide(page)
    page.get_by_test_id(test_id).click()
    expect(page.get_by_test_id("aide-menu")).to_be_hidden()


@pytest.mark.parametrize("rejoin_refused", [False, True], ids=["snapshot", "locked"])
def test_ac31_kept_requests_go_after_a_snapshot_and_never_after_room_locked(
    window: OpenWindow, live_server: str, fx01_grid: Grid, rejoin_refused: bool
) -> None:
    page = computer_page(window)
    mock = open_ac29(page, live_server, fx01_grid)
    select_mime(page)
    sent_before = len(mock.frames_without_pings())
    received_before = len(mock.received)
    mock.close(LOST_CLOSE_CODE)
    expect(page.get_by_test_id("connection-banner")).to_be_visible(
        timeout=CONNECTION_LOSS_MS
    )
    page.get_by_test_id("undo-button").click()
    pick_aide_item(page, "check-letter")
    pick_aide_item(page, "reveal-letter")
    wait_until(page, lambda: mock.has_join_after(received_before), "the new join")

    if rejoin_refused:
        mock.send(error_frame(ErrorCode.ROOM_LOCKED))
        mock.close(SERVER_CLOSE)
        expect_room_status(page, "locked")
        page.wait_for_timeout(QUIET_MS)
        assert kept_requests_sent(mock, sent_before) == []
    else:
        mock.send(ac29_frame(fx01_grid))
        wait_until(
            page,
            lambda: len(kept_requests_sent(mock, sent_before)) == len(KEPT_REQUESTS),
            "the kept requests",
        )
        assert kept_requests_sent(mock, sent_before) == KEPT_REQUESTS
