"""Tests of platform/realtime AC-24: the selection is sent again after a return.

Rules 20 and 22. Ana and Bob are in a room of the live server, each page behind a
`RoomSocketProxy` (`realtime_harness`). Ana's socket is taken away; offline she
types `T` at (1, 0), her selection moving to (1, 1) across. The server cleared
her selection when her socket closed (`social/presence.md` rule 8), so after her
return Bob must hear where she is before he hears her offline letter.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Direction,
    LetterChanged,
    Selection,
    SelectionMoved,
    ServerMessage,
)
from realtime_harness import (
    Player,
    ProxiedSocket,
    enter_through_proxy,
    expect_reconnecting,
    other_player,
    rejoin,
)
from spec017_harness import cell_at, expect_cell
from spec024_harness import EnterRoom, expect_selection, grid_from_text
from spec042_harness import wait_until

TAMIS_KEY = "0,0,0"  # the word TAMIS, row 1 across, by its clue (`data-word`)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def selection_moved(player_id: str, row: int, column: int) -> SelectionMoved:
    """The `selection_moved` of a player on a cell, across."""
    selection = Selection(row=row, column=column, direction=Direction.ACROSS)
    return SelectionMoved(player_id=player_id, selection=selection)


def wait_for_message(page: Page, socket: ProxiedSocket, wanted: ServerMessage) -> None:
    """Wait until the server sent `wanted` on `socket`."""
    wait_until(page, lambda: wanted in socket.received, f"{wanted!r}")


def is_letter_of(message: ServerMessage, player_id: str) -> bool:
    """Whether a message is a `letter_changed` made by `player_id`."""
    return isinstance(message, LetterChanged) and message.player_id == player_id


def moves_heard(messages: list[ServerMessage], player_id: str) -> list[str]:
    """The selections and letters of one player among messages, up to a letter.

    Each is named `selection_moved <row>,<column> <direction>` or
    `letter_changed <row>,<column> <letter>`; the list ends with the player's
    first letter.
    """
    heard: list[str] = []
    for message in messages:
        if isinstance(message, SelectionMoved) and message.player_id == player_id:
            selection = message.selection
            if selection is None:
                heard.append("selection_moved none")
            else:
                place = f"{selection.row},{selection.column}"
                heard.append(f"selection_moved {place} {selection.direction}")
        if isinstance(message, LetterChanged) and message.player_id == player_id:
            place = f"{message.row},{message.column}"
            heard.append(f"letter_changed {place} {message.letter}")
            return heard
    return heard


def ana_offline_after_t(page: Page, ana: Player, bob: Player) -> None:
    """Ana selects (1, 0), loses her socket, then types `T` offline.

    Returns once Bob heard Ana's selection cleared by her disconnection, and
    Ana's page shows the pending `T` and her selection on (1, 1) across.
    """
    bob_socket = bob.proxy.latest()
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0, "across", TAMIS_KEY)
    wait_for_message(page, bob_socket, selection_moved(ana.player_id, 1, 0))

    ana.proxy.go_offline()
    expect_reconnecting(page)
    cleared = SelectionMoved(player_id=ana.player_id, selection=None)
    wait_for_message(page, bob_socket, cleared)

    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    expect_selection(page, 1, 1, "across", TAMIS_KEY)


def test_ac24_bob_hears_anas_selection_before_her_offline_letter(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    with other_player(browser, live_server, code, "Bob", enter_room) as bob:
        ana = enter_through_proxy(page, live_server, code, "Ana", enter_room)
        ana_offline_after_t(page, ana, bob)
        bob_socket = bob.proxy.latest()
        heard_before = len(bob_socket.received)

        rejoin(ana)

        wait_until(
            page,
            lambda: any(
                is_letter_of(message, ana.player_id)
                for message in bob_socket.received[heard_before:]
            ),
            "the letter_changed of Ana's T on Bob's socket",
        )
        heard = moves_heard(bob_socket.received[heard_before:], ana.player_id)
        assert heard == ["selection_moved 1,1 across", "letter_changed 1,0 T"]
