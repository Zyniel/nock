"""Tests of `client/hud.md` AC-28 and AC-29: a final status after the room showed
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

"A typed letter changes nothing" is read 300 ms after the key (`QUIET_MS`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import open_fx01_room, reconnect_with_t_pending
from nock.grid import Grid
from nock.protocol import ErrorCode
from room_panels import open_aide
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of
from spec043_harness import (
    COMPUTER,
    MUTED,
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
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def computer_page(window: OpenWindow) -> Page:
    """A desktop page of 1280 by 720."""
    return window(COMPUTER[0], COMPUTER[1], False)


def expect_room_status(page: Page, status: str) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", status)


def expect_typed_t_leaves_1_0_empty(page: Page) -> None:
    """A `t` typed on the grid leaves (1, 0) empty."""
    page.keyboard.press("t")
    page.wait_for_timeout(QUIET_MS)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "")


def expect_disabled_look(item: Locator) -> None:
    """The item is disabled, its label in `--nock-muted`."""
    expect(item).to_be_disabled()
    label = label_of(item)
    assert label is not None
    assert colour_matches(label["colour"], MUTED), label["colour"]


def open_ac29(page: Page, base_url: str, grid: Grid) -> RoomMock:
    """AC-29's room: Bob's pencil `T` at (1, 0) and his `I` at (2, 2)."""
    frame = snapshot_frame(fx01_view(grid, AC29_CHANGES), players_up_to(3))
    return open_room(page, base_url, frame)


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
