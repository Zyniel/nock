"""Tests of platform/server AC-29: an undo keeps its place among offline edits.

Rule 9, with `platform/realtime.md` rules 20 and 22. Ana and Bob are in a room of
the live server, each page behind a `RoomSocketProxy` (`realtime_harness`).
Ana's socket is taken away; offline she types `T`, `A`, `M` from (1, 0) and
presses Control+z: after `M`, between `A` and `M`, or 50 ms after the snapshot of
her return. The undo must reach the server after the edits pending when it was
made and before any later one, which decides what every page ends with.

The "50 ms" is page time: Ana's page clock is installed before the room opens.
The proxy holds the snapshot of her return; the clock is paused, the snapshot
passed on, the clock moved by 50 ms and Control+z pressed, so the resend (one
edit every 100 ms) cannot move on meanwhile; the clock then runs again.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import ClientMessage, EditLetter, LetterChanged, Undo
from realtime_harness import (
    Player,
    ProxiedSocket,
    enter_through_proxy,
    expect_reconnecting,
    other_player,
    page_seq,
    rejoin,
    wait_for_requests,
)
from spec017_harness import cell_at, expect_cell
from spec024_harness import EnterRoom, expect_selection, grid_from_text
from spec042_harness import wait_until

TAMIS_KEY = "0,0,0"  # the word TAMIS, row 1 across, by its clue (`data-word`)
PAUSE_AHEAD_MS = 1  # how far ahead of its time the page clock is paused
MS_PER_SECOND = 1000
UNDO_DELAY_MS = 50  # "50 ms after her reconnection snapshot"


class UndoCase(NamedTuple):
    """When Ana presses Control+z, and what follows.

    Attributes:
        typed_before: The letters typed offline before the Control+z.
        typed_after: The letters typed offline after it.
        is_after_snapshot: True when the Control+z comes 50 ms after the
            snapshot of her return instead of offline.
        order: The requests the server receives, edits named by their letter.
        row_one: What every page ends with at (1, 0), (1, 1) and (1, 2).
    """

    typed_before: str
    typed_after: str
    is_after_snapshot: bool
    order: list[str]
    row_one: tuple[str, str, str]


CASES = {
    "offline_after_m": UndoCase(
        "tam", "", False, ["T", "A", "M", "undo"], ("T", "A", "")
    ),
    "offline_between_a_and_m": UndoCase(
        "ta", "m", False, ["T", "A", "undo", "M"], ("T", "", "M")
    ),
    "50_ms_after_the_snapshot": UndoCase(
        "tam", "", True, ["T", "A", "M", "undo"], ("T", "A", "")
    ),
}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def expected_requests(order: list[str], base_seq: int) -> list[ClientMessage]:
    """The requests of `order`: letters typed from (1, 0) across, and undos."""
    requests: list[ClientMessage] = []
    column = 0
    for name in order:
        if name == "undo":
            requests.append(Undo())
            continue
        edit = EditLetter(row=1, column=column, letter=name, base_seq=base_seq)
        requests.append(edit)
        column += 1
    return requests


def letters_of(socket: ProxiedSocket, player_id: str) -> int:
    """How many `letter_changed` made by `player_id` reached a socket."""
    count = 0
    for message in socket.received:
        if isinstance(message, LetterChanged) and message.player_id == player_id:
            count += 1
    return count


def type_keys(page: Page, keys: str) -> None:
    """Press each key of `keys` in turn."""
    for key in keys:
        page.keyboard.press(key)


def pause_page_clock(page: Page) -> None:
    """Stop the page's installed clock, just ahead of where it is.

    `pause_at` reads a number as seconds since the epoch, `Date.now()` gives ms.
    """
    now_ms = page.evaluate("() => Date.now()")
    assert isinstance(now_ms, int | float), now_ms
    page.clock.pause_at((now_ms + PAUSE_AHEAD_MS) / MS_PER_SECOND)


def go_offline_at_1_0(page: Page, ana: Player) -> int:
    """Ana selects (1, 0) and loses her socket; return the seq her page holds."""
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0, "across", TAMIS_KEY)
    base_seq = page_seq(page)
    ana.proxy.go_offline()
    expect_reconnecting(page)
    return base_seq


def come_back_and_undo(page: Page, ana: Player, case: UndoCase) -> ProxiedSocket:
    """Bring Ana back; press Control+z 50 ms after the snapshot when the case says."""
    if not case.is_after_snapshot:
        return rejoin(ana)
    socket = ana.proxy.come_back(is_holding=True)
    wait_until(page, socket.has_snapshot, "the snapshot of Ana's return")
    pause_page_clock(page)
    socket.release()
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    page.clock.run_for(UNDO_DELAY_MS)
    page.keyboard.press("Control+z")
    page.clock.resume()
    return socket


@pytest.mark.parametrize("case_name", list(CASES))
def test_ac29_an_offline_undo_reaches_the_server_in_its_place(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
    case_name: str,
) -> None:
    case = CASES[case_name]
    code = room_registry.register_room(fx01_grid)
    page.clock.install()
    with other_player(browser, live_server, code, "Bob", enter_room) as bob:
        ana = enter_through_proxy(page, live_server, code, "Ana", enter_room)
        base_seq = go_offline_at_1_0(page, ana)
        bob_letters_before = letters_of(bob.proxy.latest(), ana.player_id)

        type_keys(page, case.typed_before)
        if not case.is_after_snapshot:
            page.keyboard.press("Control+z")
        type_keys(page, case.typed_after)
        expect_cell(page, 1, 2, "M", unconfirmed=True)
        socket = come_back_and_undo(page, ana, case)

        wait_for_requests(page, socket, len(case.order))
        assert socket.requests() == expected_requests(case.order, base_seq)
        wait_until(
            page,
            lambda: letters_of(socket, ana.player_id) >= len(case.order),
            "the server's answers to Ana's requests",
        )
        wait_until(
            page,
            lambda: letters_of(bob.proxy.latest(), ana.player_id)
            >= bob_letters_before + len(case.order),
            "Ana's letters on Bob's socket",
        )
        for player_page in (page, bob.page):
            for column, letter in enumerate(case.row_one):
                expect_cell(player_page, 1, column, letter, unconfirmed=False)
        assert socket.requests() == expected_requests(case.order, base_seq)
