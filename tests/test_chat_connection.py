"""Tests of `social/chat.md` AC-23: the pacing of « Réagir » and the chat while the
page is not joined.

Rule 13. Ana's page on spec 017's mocked room (`joined_room`, FX-01, seq 5,
1280 by 720). The helpers of the page's buttons are in
`spec022_harness.py`, shared with `test_reactions_connection.py`.

AC-23: the page clock is frozen, so the 12 seconds of the pacing never run out and
no ping nor silence check runs. Every socket is a controlled stand-in
(`reconnection_harness.CONTROL_ALL_SCRIPT`): `cut_quietly` takes the socket away
without telling the page, which stays joined; `deliver_close` then gives it the
close event. Four reactions (or chat messages) go out on the first socket; a fifth
chosen in that state reaches the mocked server nowhere; once the page is joined
on the next socket, the picker's options (or « Envoyer ») are still enabled, and
a fifth that goes out disables them, the note « Patientez avant d'envoyer. »
showing for the chat.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from reconnection_harness import CONTROL_ALL_SCRIPT, cut_quietly, deliver_close
from spec017_harness import (
    STORED_JOIN,
    MockConnection,
    MockRoom,
    advance_page,
    expect_offline,
    expect_status,
    first_join,
    grid_from_text,
    joined_room,
    settle,
    snapshot_frame,
    wait_until,
)
from spec022_harness import (
    REACTION_VALUES,
    frames_of_kind,
    open_panel,
    picker,
    react_button,
)
from spec043_harness import fr_value, select_mime

FIRST_DELAY_LATEST_MS = 1200
SENT_BEFORE_THE_CUT = 4


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def expect_options_enabled(page: Page, enabled: bool) -> None:
    """Every option of the open picker is enabled, or every one disabled."""
    options = page.get_by_test_id("reaction-option")
    expect(options).to_have_count(len(REACTION_VALUES))
    for index in range(len(REACTION_VALUES)):
        if enabled:
            expect(options.nth(index)).to_be_enabled()
        else:
            expect(options.nth(index)).to_be_disabled()


def choose_reaction(page: Page, value: str) -> None:
    """Open the picker with « Réagir » and choose one reaction."""
    react_button(page).click()
    expect(picker(page)).to_be_visible()
    picker(page).locator(f'[data-reaction="{value}"]').click()
    expect(picker(page)).to_have_count(0)


def send_chat(page: Page, text: str) -> None:
    """Type a message in the box and send it with Enter."""
    chat_input = page.get_by_test_id("chat-input")
    chat_input.fill(text)
    expect(chat_input).to_have_value(text)
    chat_input.press("Enter")
    expect(chat_input).to_have_value("")


def rejoin_on_the_next_socket(page: Page, room: MockRoom, grid: Grid) -> MockConnection:
    """Give the page the close of its socket, then answer its next join."""
    deliver_close(page)
    expect_offline(page)
    advance_page(page, FIRST_DELAY_LATEST_MS)
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    second.send(snapshot_frame(grid, 5))
    expect_status(page, "joined")
    return second


# ---- AC-23: only what went out on an open socket counts ------------------------------


def test_ac23_a_reaction_chosen_on_a_socket_no_longer_open_does_not_count(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=CONTROL_ALL_SCRIPT
    )
    first = room.connections[0]
    select_mime(page)
    for value in REACTION_VALUES[:SENT_BEFORE_THE_CUT]:
        choose_reaction(page, value)
    wait_until(page, lambda: len(frames_of_kind(first, "react")) == SENT_BEFORE_THE_CUT)
    cut_quietly(page)

    react_button(page).click()
    expect_options_enabled(page, True)
    picker(page).locator(f'[data-reaction="{REACTION_VALUES[4]}"]').click()
    settle(page)
    expect_status(page, "joined")
    assert len(frames_of_kind(first, "react")) == SENT_BEFORE_THE_CUT

    second = rejoin_on_the_next_socket(page, room, fx01_grid)
    react_button(page).click()
    expect_options_enabled(page, True)
    picker(page).locator(f'[data-reaction="{REACTION_VALUES[0]}"]').click()
    wait_until(page, lambda: len(frames_of_kind(second, "react")) == 1)
    react_button(page).click()
    expect(picker(page)).to_be_visible()
    expect_options_enabled(page, False)


def test_ac23_a_chat_message_sent_on_a_socket_no_longer_open_does_not_count(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=CONTROL_ALL_SCRIPT
    )
    first = room.connections[0]
    open_panel(page)
    for number in range(1, SENT_BEFORE_THE_CUT + 1):
        send_chat(page, f"m{number}")
    wait_until(page, lambda: len(frames_of_kind(first, "chat")) == SENT_BEFORE_THE_CUT)
    cut_quietly(page)

    send_chat(page, "m5")
    settle(page)
    expect_status(page, "joined")
    assert len(frames_of_kind(first, "chat")) == SENT_BEFORE_THE_CUT

    second = rejoin_on_the_next_socket(page, room, fx01_grid)
    send = page.get_by_test_id("chat-send")
    page.get_by_test_id("chat-input").fill("m6")
    expect(send).to_be_enabled()
    send_chat(page, "m6")
    wait_until(page, lambda: len(frames_of_kind(second, "chat")) == 1)
    page.get_by_test_id("chat-input").fill("m7")
    expect(send).to_be_disabled()
    expect(page.get_by_test_id("chat-wait")).to_have_text(fr_value("chat.wait"))
