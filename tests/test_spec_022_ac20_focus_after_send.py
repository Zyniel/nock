"""Tests of spec 022, AC-20: after a chat message is sent, the focus is on
`chat-input`, whichever way it was sent (`Enter`, a keyboard activation of
`chat-send`, a click or a tap), and also when the send starts the pacing.

Browser with spec 025's mocked socket, on a FX-01 snapshot with `seq` 5 (the players
of the harness, `p1` host) and the panel open. At 1280 by 720 and at 360 by 740 in a
desktop context the player sends `m1` to `m5` in this order, the mock answering each
with its `chat_message` from `p1` (seq 6 to 10): `m1` with `Enter` in `chat-input`;
`m2` with one `Tab` (the focus is on `chat-send`, which is enabled) then `Enter`;
`m3` with a click on `chat-send`; `m4` as `m2`; `m5` as `m3`. The text is typed with
the keyboard into whatever has the focus (`page.keyboard.type`), never set on
`chat-input` directly, so a focus that was lost fails the test at the next send.

"Within 300 ms of the key or the click" is counted from the moment the call of the
key or of the click returns (the call itself, with its checks that the element can
be acted on, is the test's own time). Every part of a reading must hold together at
some moment before the deadline, or at the last reading made at it: the single
`chat` frame the mock received, an empty `chat-input`, the focus on `chat-input`
and, for `m5`, a disabled `chat-send` and `chat-wait` showing.

In a touch context at 360 by 740 the panel is opened by a tap on `chat-toggle`, the
player types `t1` and taps `chat-send`.

Timing: the 300 ms are the criterion's and are counted on the test's side. A reading
holds within about 2 to 40 ms of the key or the click once the focus rule is met,
but a heavy load can break the bound: the file is a candidate for the gate's serial
pass.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec022_harness import (
    POLL_MS,
    chat_frame,
    expect_seq,
    frames_of_type,
    open_chat_room,
    open_panel,
)
from spec024_harness import grid_from_text, load_fr, open_context_page
from spec025_harness import MockRoomSocket

SIZES = [(1280, 720), (360, 740)]
SNAPSHOT_SEQ = 5
WITHIN_MS = 300

ENTER = "Enter in chat-input"
TAB_THEN_ENTER = "Tab then Enter on chat-send"
CLICK = "a click on chat-send"
# The five sends of the criterion, in order: `m1` to `m5`.
WAYS = [ENTER, TAB_THEN_ENTER, CLICK, TAB_THEN_ENTER, CLICK]

# What the criterion reads after a send: the focus (`data-testid`, else tag name),
# the input's value, the state of `chat-send` and the text of `chat-wait`.
READING_SCRIPT = r"""
() => {
  const active = document.activeElement;
  const input = document.querySelector('[data-testid="chat-input"]');
  const send = document.querySelector('[data-testid="chat-send"]');
  const wait = document.querySelector('[data-testid="chat-wait"]');
  return {
    active: active === null
      ? null : (active.getAttribute('data-testid') || active.tagName),
    value: input === null ? null : input.value,
    sendDisabled: send === null ? null : send.disabled,
    wait: wait === null ? null : wait.textContent.trim(),
  };
}
"""


def size_ids() -> list[str]:
    return [f"{width}x{height}" for width, height in SIZES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def read_page_and_mock(
    page: Page, mock: MockRoomSocket, keys: list[str]
) -> dict[str, object]:
    """The page's reading and the `chat` frames the mock received, cut to `keys`.

    The values are what the page holds, so their types are the page's.
    """
    reading: dict[str, object] = page.evaluate(READING_SCRIPT)
    reading["chat_frames"] = frames_of_type(mock, "chat")
    cut: dict[str, object] = {}
    for key in keys:
        cut[key] = reading[key]
    return cut


def read_until(
    page: Page, mock: MockRoomSocket, expected: dict[str, object], deadline: float
) -> dict[str, object]:
    """Read until the reading is `expected` or the deadline passes.

    Returns:
        The last reading, with the keys of `expected` only.
    """
    keys = list(expected)
    reading = read_page_and_mock(page, mock, keys)
    while reading != expected and time.monotonic() < deadline:
        page.wait_for_timeout(POLL_MS)
        reading = read_page_and_mock(page, mock, keys)
    return reading


def expected_after(sent_texts: list[str]) -> dict[str, object]:
    """What the criterion expects within 300 ms of the latest send.

    Args:
        sent_texts: The texts sent so far, the latest one last.
    """
    sent_frames: list[dict[str, str]] = []
    for text in sent_texts:
        sent_frames.append({"type": "chat", "text": text})
    return {"chat_frames": sent_frames, "value": "", "active": "chat-input"}


def activate_send(page: Page, way: str) -> None:
    """Send the text typed in `chat-input`: the key or the click of `way`.

    The `Tab` of the keyboard way comes first, and the focus on the enabled
    `chat-send` is checked before the `Enter`.
    """
    send = page.get_by_test_id("chat-send")
    if way == ENTER:
        page.keyboard.press("Enter")
    elif way == TAB_THEN_ENTER:
        page.keyboard.press("Tab")
        expect(send).to_be_focused()
        expect(send).to_be_enabled()
        page.keyboard.press("Enter")
    elif way == CLICK:
        send.click()
    else:
        pytest.fail(f"no such way of sending: {way}")


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids())
def test_ac20_browser_the_focus_is_on_chat_input_after_each_way_of_sending(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    wait_text = load_fr()["chat.wait"]
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        mock = open_chat_room(page, live_server, fx01_grid, seq=SNAPSHOT_SEQ)
        open_panel(page)
        expect(page.get_by_test_id("chat-input")).to_be_focused()

        sent_texts: list[str] = []
        for number, way in enumerate(WAYS, start=1):
            text = f"m{number}"
            page.keyboard.type(text)
            activate_send(page, way)
            deadline = time.monotonic() + WITHIN_MS / 1000

            sent_texts.append(text)
            expected = expected_after(sent_texts)
            if number == len(WAYS):
                # The fifth send starts the pacing.
                expected["sendDisabled"] = True
                expected["wait"] = wait_text
            reading = read_until(page, mock, expected, deadline)
            assert reading == expected, f"after {text} sent by {way}"

            mock.send(chat_frame(SNAPSHOT_SEQ + number, "p1", text))
            expect_seq(page, SNAPSHOT_SEQ + number)
    finally:
        close()


def test_ac20_browser_a_tap_on_chat_send_puts_the_focus_on_chat_input(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 360, 740, True)
    try:
        mock = open_chat_room(page, live_server, fx01_grid, seq=SNAPSHOT_SEQ)
        open_panel(page, touch=True)
        chat_input = page.get_by_test_id("chat-input")
        expect(chat_input).to_be_focused()
        page.keyboard.type("t1")
        send = page.get_by_test_id("chat-send")
        expect(send).to_be_enabled()

        send.tap()
        deadline = time.monotonic() + WITHIN_MS / 1000

        expected = expected_after(["t1"])
        reading = read_until(page, mock, expected, deadline)
        assert reading == expected, "after t1 sent by a tap on chat-send"

        mock.send(chat_frame(SNAPSHOT_SEQ + 1, "p1", "t1"))
        expect_seq(page, SNAPSHOT_SEQ + 1)
    finally:
        close()
