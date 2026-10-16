"""Tests of spec 022, AC-19: the chat notes take no room from the panel, fit on one
line and show one at a time.

Browser with spec 025's mocked socket, in desktop contexts. Setup: a FX-01
snapshot with `seq` 25 in which `p2` is host (so `you`, `p1`, is not) and whose
`chat` holds 20 lines from `p2` (seq 3 to 22), with the panel open. Each run starts
on a page of its own, by reading the panel's box (the left, top, width and height of
the bounding box of `chat-panel`) with neither `chat-muted` nor `chat-wait` on the
page, and compares it with the box read once a note shows and once it is gone.

A note is "on one line" when the rectangles of `Range.getClientRects()` for the
contents of the note (`selectNodeContents`) share one `top` and lie inside the
panel's box, each within 1 px.

The runs: "Muted" and "Wait" at the eight window sizes of spec 006 AC-5, and "Both"
at 1280 by 720 and at 320 by 568. The wait runs type `m1` to `m5` with the keyboard
(`press_sequentially` and `press` focus `chat-input` first, so a focus lost on the
way is AC-20's failure, not this one's), the mock answering each with its
`chat_message` from `p1`.

Timing: the page paces in real time (5 messages in 12 s). The wait run only waits
for the note to show, a fraction of a second after its first send, and never for the
12 s to end. The "Both" run has to unmute less than 12 s after its first send, so
that the pacing still holds: its own steps take well under a second, and the test
fails with a message of its own if they took 9 s or more.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import ChatMessage, PlayerMuted
from spec022_harness import (
    SETTLE_MS,
    chat_frame,
    expect_seq,
    open_chat_room,
    open_panel,
    three_players,
    wait_for_frame_count,
)
from spec024_harness import grid_from_text, load_fr, open_context_page
from spec025_harness import MockRoomSocket

WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
BOTH_SIZES = [(1280, 720), (320, 568)]
SNAPSHOT_SEQ = 25
FIRST_LINE_SEQ = 3
LAST_LINE_SEQ = 22  # 20 lines, seq 3 to 22
SEND_COUNT = 5
PACING_SECONDS = 12.0
# The latest moment, after the first send, for the unmute of the "Both" run: the
# pacing holds until 12 s, and the frame needs a moment to reach the page.
UNMUTE_BEFORE_SECONDS = 9.0
NOTE_TIMEOUT_MS = 3000
TOLERANCE_PX = 1.0
BOX_NAMES = ["left", "top", "width", "height"]

PANEL_BOX_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="chat-panel"]');
  if (panel === null) {
    return null;
  }
  const box = panel.getBoundingClientRect();
  return [box.left, box.top, box.width, box.height];
}
"""

# The client rectangles of the contents of a note, and the panel's box
# (left, top, right, bottom).
NOTE_RECTANGLES_SCRIPT = r"""
testId => {
  const note = document.querySelector(`[data-testid="${testId}"]`);
  const panel = document.querySelector('[data-testid="chat-panel"]');
  if (note === null || panel === null) {
    return null;
  }
  const range = document.createRange();
  range.selectNodeContents(note);
  const rectangles = [];
  for (const rect of Array.from(range.getClientRects())) {
    rectangles.push([rect.left, rect.top, rect.right, rect.bottom]);
  }
  const box = panel.getBoundingClientRect();
  return {
    rectangles: rectangles,
    panel: [box.left, box.top, box.right, box.bottom],
  };
}
"""


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def snapshot_chat() -> list[ChatMessage]:
    """The 20 lines from `p2` of the snapshot, seq 3 to 22."""
    lines: list[ChatMessage] = []
    for seq in range(FIRST_LINE_SEQ, LAST_LINE_SEQ + 1):
        lines.append(ChatMessage(seq=seq, player_id="p2", text=f"Ligne {seq}"))
    return lines


def muted_frame(seq: int, muted: bool) -> str:
    """The JSON text of a `player_muted` for `you` (`p1`)."""
    return PlayerMuted(seq=seq, player_id="p1", muted=muted).model_dump_json()


def open_scene(
    browser: Browser,
    browser_name: str,
    live_server: str,
    grid: Grid,
    width: int,
    height: int,
) -> tuple[Page, MockRoomSocket, Callable[[], None]]:
    """A page of its own at one size with the panel open; page, mock and closer."""
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        mock = open_chat_room(
            page,
            live_server,
            grid,
            seq=SNAPSHOT_SEQ,
            players=three_players(host="p2"),
            chat=snapshot_chat(),
        )
        open_panel(page)
        lines = page.get_by_test_id("chat-message")
        expect(lines).to_have_count(LAST_LINE_SEQ - FIRST_LINE_SEQ + 1)
        page.wait_for_timeout(SETTLE_MS)
    except BaseException:
        close()
        raise
    return page, mock, close


def panel_box(page: Page) -> list[float] | None:
    """The left, top, width and height of `chat-panel`; None when it is absent."""
    return page.evaluate(PANEL_BOX_SCRIPT)


def read_start_box(page: Page) -> list[float]:
    """The panel's box, read with neither chat note on the page."""
    expect(page.get_by_test_id("chat-muted")).to_have_count(0)
    expect(page.get_by_test_id("chat-wait")).to_have_count(0)
    box = panel_box(page)
    assert box is not None, "chat-panel is not on the page"
    return box


def box_problems(
    label: str, start: list[float], later: list[float] | None
) -> list[str]:
    """How the panel's box `later` differs from the one read at the start."""
    if later is None:
        return [f"{label}: chat-panel is not on the page"]
    problems: list[str] = []
    for name, was, now in zip(BOX_NAMES, start, later, strict=True):
        if abs(was - now) > TOLERANCE_PX:
            problems.append(f"{label}: the panel's {name} went from {was} to {now}")
    return problems


def one_line_problems(page: Page, test_id: str) -> list[str]:
    """How the note `test_id` breaks "on one line": its rectangles must share one
    top and lie inside the panel's box (1 px tolerance)."""
    reading = page.evaluate(NOTE_RECTANGLES_SCRIPT, test_id)
    if reading is None:
        return [f"{test_id} or chat-panel is not on the page"]
    rectangles = reading["rectangles"]
    if len(rectangles) == 0:
        return [f"{test_id} has no client rectangle"]
    panel_left, panel_top, panel_right, panel_bottom = reading["panel"]
    first_top = rectangles[0][1]
    problems: list[str] = []
    for left, top, right, bottom in rectangles:
        if abs(top - first_top) > TOLERANCE_PX:
            problems.append(f"{test_id} has rectangles with tops {first_top} and {top}")
        if left < panel_left - TOLERANCE_PX or right > panel_right + TOLERANCE_PX:
            note_span = f"{left} to {right}"
            panel_span = f"{panel_left} to {panel_right}"
            problems.append(f"{test_id} is across {note_span}, the panel {panel_span}")
        if top < panel_top - TOLERANCE_PX or bottom > panel_bottom + TOLERANCE_PX:
            note_span = f"{top} to {bottom}"
            panel_span = f"{panel_top} to {panel_bottom}"
            problems.append(f"{test_id} is down {note_span}, the panel {panel_span}")
    return problems


def send_five(page: Page, mock: MockRoomSocket) -> float:
    """The player types `m1` to `m5` with the keyboard, `Enter` after each one.

    The mock answers each frame with its `chat_message` from `p1` (seq 26 to 30).

    Returns:
        The `time.monotonic` value noted just before the first `Enter`, which is
        at most the moment the page sends its first message.
    """
    chat_input = page.get_by_test_id("chat-input")
    first_send = 0.0
    for number in range(1, SEND_COUNT + 1):
        text = f"m{number}"
        chat_input.press_sequentially(text)
        if number == 1:
            first_send = time.monotonic()
        chat_input.press("Enter")
        wait_for_frame_count(page, mock, "chat", number)
        mock.send(chat_frame(SNAPSHOT_SEQ + number, "p1", text))
        expect_seq(page, SNAPSHOT_SEQ + number)
    return first_send


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac19_browser_the_muted_note_leaves_the_panel_box_alone_and_fits_one_line(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    muted_text = load_fr()["chat.muted"]
    page, mock, close = open_scene(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        start = read_start_box(page)
        muted_note = page.get_by_test_id("chat-muted")

        mock.send(muted_frame(SNAPSHOT_SEQ + 1, True))
        expect(muted_note).to_have_text(muted_text)
        problems = box_problems("muted", start, panel_box(page))
        problems += one_line_problems(page, "chat-muted")

        mock.send(muted_frame(SNAPSHOT_SEQ + 2, False))
        expect(muted_note).to_have_count(0)
        problems += box_problems("unmuted", start, panel_box(page))
    finally:
        close()

    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac19_browser_the_wait_note_leaves_the_panel_box_alone_and_fits_one_line(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    wait_text = load_fr()["chat.wait"]
    page, mock, close = open_scene(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        start = read_start_box(page)

        send_five(page, mock)
        expect(page.get_by_test_id("chat-wait")).to_have_text(wait_text)
        problems = box_problems("wait", start, panel_box(page))
        problems += one_line_problems(page, "chat-wait")
    finally:
        close()

    assert problems == [], "\n".join(problems)


@pytest.mark.parametrize(("width", "height"), BOTH_SIZES, ids=size_ids(BOTH_SIZES))
def test_ac19_browser_the_muted_note_wins_and_the_wait_note_comes_back_after_an_unmute(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    fr = load_fr()
    page, mock, close = open_scene(
        browser, browser_name, live_server, fx01_grid, width, height
    )
    try:
        start = read_start_box(page)
        wait_note = page.get_by_test_id("chat-wait")
        muted_note = page.get_by_test_id("chat-muted")

        first_send = send_five(page, mock)
        expect(wait_note).to_have_text(fr["chat.wait"])

        mute_seq = SNAPSHOT_SEQ + SEND_COUNT + 1
        mock.send(muted_frame(mute_seq, True))
        expect(muted_note).to_have_text(fr["chat.muted"])
        waits_while_muted = wait_note.count()
        problems = box_problems("muted while paced", start, panel_box(page))

        elapsed = time.monotonic() - first_send
        if elapsed >= UNMUTE_BEFORE_SECONDS:
            pytest.fail(
                f"the test took {elapsed:.1f} s from its first send to the unmute; "
                f"the pacing ({PACING_SECONDS:.0f} s) must still hold when it comes"
            )
        mock.send(muted_frame(mute_seq + 1, False))
        expect(muted_note).to_have_count(0)
        expect(wait_note).to_have_text(fr["chat.wait"], timeout=NOTE_TIMEOUT_MS)
        problems += box_problems("paced after the unmute", start, panel_box(page))
    finally:
        close()

    assert waits_while_muted == 0, "chat-wait is on the page while chat-muted shows"
    assert problems == [], "\n".join(problems)
