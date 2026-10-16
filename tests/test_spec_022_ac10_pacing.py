"""Tests of spec 022, AC-10: the page paces its own chat messages and reactions
under the server's limit.

Browser with a mocked socket, in real time ("Test harness": real time or
Playwright's page clock). The test notes `time.monotonic()` just before its first
send, which is at most the moment the page sends, so "still disabled" read 11.5 s
after that note is read before the page's 12 s are over. "Enabled again 12 seconds
after the first" is read with PACING_SLACK_SECONDS of slack for the page's timer
and the test's own steps. "Sends nothing" leaves the heartbeat `ping` frames aside
(the lead's note of 2026-10-15). The mock sends no `error` in this test.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from spec021_harness import IDES, select_word
from spec022_harness import (
    REACTION_VALUES,
    assert_sends_nothing,
    chat_frame,
    expect_seq,
    frames_of_type,
    open_chat_room,
    open_panel,
    remaining_ms,
    wait_for_frame_count,
)
from spec024_harness import grid_from_text, load_fr

PACE_COUNT = 5
PACE_SECONDS = 12.0
STILL_PACED_AT_SECONDS = 11.5
PACING_SLACK_SECONDS = 0.75


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def wait_until_elapsed(page: Page, started: float, seconds: float) -> None:
    """Let the page run until `seconds` have passed since `started`."""
    left_ms = (started + seconds - time.monotonic()) * 1000
    if left_ms > 0:
        page.wait_for_timeout(left_ms)


def all_disabled(options: Locator) -> bool:
    """Whether every `reaction-option` is disabled."""
    states = [options.nth(index).is_disabled() for index in range(options.count())]
    return all(states)


def test_ac10_browser_the_page_paces_its_chat_messages_and_reactions(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid, seq=5)
    select_word(page, IDES)
    open_panel(page)
    chat_input = page.get_by_test_id("chat-input")
    send = page.get_by_test_id("chat-send")
    wait = page.get_by_test_id("chat-wait")

    # Five chat messages, each answered by the mock.
    first_chat = time.monotonic()
    for number in range(1, PACE_COUNT + 1):
        chat_input.fill(f"m{number}")
        chat_input.press("Enter")
        wait_for_frame_count(page, mock, "chat", number)
        mock.send(chat_frame(5 + number, "p1", f"m{number}"))
        expect_seq(page, 5 + number)
    chats_sent = frames_of_type(mock, "chat")
    expect(send).to_be_disabled()
    expect(wait).to_have_text(fr["chat.wait"])
    chat_input.fill("m6")
    assert_sends_nothing(page, mock, lambda: chat_input.press("Enter"))
    wait_until_elapsed(page, first_chat, STILL_PACED_AT_SECONDS)
    still_paced = send.is_disabled()
    deadline = first_chat + PACE_SECONDS + PACING_SLACK_SECONDS
    expect(send).to_be_enabled(timeout=remaining_ms(deadline))
    expect(wait).to_have_count(0, timeout=remaining_ms(deadline))

    # Five reactions chosen in the picker.
    page.keyboard.press("Escape")
    expect(page.get_by_test_id("chat-panel")).to_have_count(0)
    button = page.get_by_test_id("react-button")
    picker = page.get_by_test_id("reaction-picker")
    first_reaction = time.monotonic()
    for number, value in enumerate(REACTION_VALUES, start=1):
        button.click()
        picker.locator(f'[data-reaction="{value}"]').click()
        wait_for_frame_count(page, mock, "react", number)
    reactions_sent = frames_of_type(mock, "react")
    button.click()
    expect(picker).to_be_visible()
    options = page.get_by_test_id("reaction-option")
    expect(options).to_have_count(len(REACTION_VALUES))
    for index in range(len(REACTION_VALUES)):
        expect(options.nth(index)).to_be_disabled()
    wait_until_elapsed(page, first_reaction, STILL_PACED_AT_SECONDS)
    reactions_still_paced = all_disabled(options)
    deadline = first_reaction + PACE_SECONDS + PACING_SLACK_SECONDS
    for index in range(len(REACTION_VALUES)):
        expect(options.nth(index)).to_be_enabled(timeout=remaining_ms(deadline))

    texts = [frame["text"] for frame in chats_sent]
    assert texts == [f"m{number}" for number in range(1, PACE_COUNT + 1)]
    assert len(frames_of_type(mock, "chat")) == PACE_COUNT
    assert still_paced is True
    assert len(reactions_sent) == PACE_COUNT
    assert reactions_still_paced is True
