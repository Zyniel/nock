"""Tests of gameplay/hints AC-24: a check and a reveal made offline keep their place.

Rule 11, with `platform/realtime.md` rules 20 and 22. Ana is in a room of the live
server (help `free`), her page behind a `RoomSocketProxy` (`realtime_harness`).
Her socket is taken away; offline she types `T`, `X` from (1, 0), then picks
« Vérifier » « Le mot » and « Révéler » « La lettre » with the selection on
(1, 2). After her return the server must receive the two edits, the check of
TAMIS, then the reveal of (1, 2).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import CellTarget, Check, ClientMessage, EditLetter, Reveal
from realtime_harness import (
    enter_through_proxy,
    expect_reconnecting,
    page_seq,
    rejoin,
    wait_for_requests,
)
from room_panels import open_aide
from spec017_harness import cell_at, expect_cell
from spec024_harness import TAMIS, EnterRoom, expect_selection, grid_from_text

TAMIS_KEY = "0,0,0"  # the word TAMIS, row 1 across, by its clue (`data-word`)
WAIT_TIMEOUT_MS = 5000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def pick_aide_item(page: Page, test_id: str) -> None:
    """Open the Aide menu and click one of its items, which closes it."""
    open_aide(page)
    page.get_by_test_id(test_id).click(timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("aide-menu")).to_be_hidden()


def test_ac24_offline_edits_a_check_and_a_reveal_reach_the_server_in_order(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    ana = enter_through_proxy(page, live_server, code, "Ana", enter_room)
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0, "across", TAMIS_KEY)
    base_seq = page_seq(page)
    ana.proxy.go_offline()
    expect_reconnecting(page)

    page.keyboard.press("t")
    page.keyboard.press("x")
    expect_cell(page, 1, 1, "X", unconfirmed=True)
    expect_selection(page, 1, 2, "across", TAMIS_KEY)
    pick_aide_item(page, "check-word")
    pick_aide_item(page, "reveal-letter")
    socket = rejoin(ana)

    expected: list[ClientMessage] = [
        EditLetter(row=1, column=0, letter="T", base_seq=base_seq),
        EditLetter(row=1, column=1, letter="X", base_seq=base_seq),
        Check(target=TAMIS),
        Reveal(target=CellTarget(row=1, column=2)),
    ]
    wait_for_requests(page, socket, len(expected))
    assert socket.requests() == expected
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "true")
