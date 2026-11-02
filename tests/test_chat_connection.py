"""Tests of `social/chat.md` AC-22 and AC-23: « Réagir », « Je bloque » and the
pacing while the page is not joined.

Rules 5, 10 and 13. Ana's page on spec 017's mocked room (`joined_room`, FX-01,
seq 5, 1280 by 720).

AC-22: with MIME selected and the picker open, the socket closes with 1011: within
5 s « Réagir » and « Je bloque » are disabled and the picker is gone, no `react`
or `flag` sent; they stay disabled on the new socket until its snapshot, which
enables both. After a close 4001 both stay disabled, also once the selection
moves to another word.

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

import json

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from reconnection_harness import CONTROL_ALL_SCRIPT, cut_quietly, deliver_close
from spec017_harness import (
    LOSS_BUDGET_MS,
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
from spec022_harness import REACTION_VALUES, open_panel
from spec043_harness import fr_value, press_cell, select_mime

LOST_CLOSE = 1011
REPLACED_CLOSE = 4001
FIRST_DELAY_LATEST_MS = 1200
SENT_BEFORE_THE_CUT = 4
STAYS_DISABLED_MS = 1500  # longer than the first retry delay at its highest


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def react_button(page: Page) -> Locator:
    return page.get_by_test_id("react-button")


def flag_button(page: Page) -> Locator:
    return page.get_by_test_id("flag-button")


def picker(page: Page) -> Locator:
    return page.get_by_test_id("reaction-picker")


def frames_of_kind(connection: MockConnection, kind: str) -> list[str]:
    """The frames of one `type` the page sent on one socket, in order."""
    found: list[str] = []
    for frame in connection.frames:
        if json.loads(frame)["type"] == kind:
            found.append(frame)
    return found


def sent_on_any_socket(room: MockRoom, kind: str) -> int:
    """How many frames of one `type` the page sent, on every socket."""
    count = 0
    for connection in room.connections:
        count += len(frames_of_kind(connection, kind))
    return count


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


# ---- AC-22: disabled while the page is not joined ----------------------------------


def test_ac22_a_loss_disables_both_buttons_and_closes_the_picker_until_a_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    select_mime(page)
    expect(flag_button(page)).to_be_enabled()
    react_button(page).click()
    expect(picker(page)).to_be_visible()

    room.connections[0].close(LOST_CLOSE)

    expect(react_button(page)).to_be_disabled(timeout=LOSS_BUDGET_MS)
    expect(flag_button(page)).to_be_disabled(timeout=LOSS_BUDGET_MS)
    expect(picker(page)).to_have_count(0)
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    settle(page)
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    assert sent_on_any_socket(room, "react") == 0
    assert sent_on_any_socket(room, "flag") == 0

    second.send(snapshot_frame(fx01_grid, 5))

    expect_status(page, "joined")
    expect(react_button(page)).to_be_enabled()
    expect(flag_button(page)).to_be_enabled()


def test_ac22_after_a_close_4001_both_buttons_stay_disabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    select_mime(page)
    expect(react_button(page)).to_be_enabled()

    room.connections[0].close(REPLACED_CLOSE)

    expect_status(page, "replaced")
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    press_cell(page, 1, 0)
    page.wait_for_timeout(STAYS_DISABLED_MS)
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    assert len(room.connections) == 1


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
