"""Tests of spec 047, AC-4 and AC-5: how a vote ends.

AC-4: when the page applies a `vote_closed`, `vote-banner` leaves the page within
300 ms and never shows a result; `vote-announcement` says how the vote ended; the
stream gets one muted `vote` line with no pictogram, which lights neither
`salon-dot` nor `chat-unread`; and, while the stream is not shown, that line makes
one 3-second note. The snapshot and a reconnection's snapshot add no such line; a
vote closed after the grid was solved still adds its line. AC-5: notes that
waited during the vote give way to the vote's result.

Readings where the spec leaves room:

- "Within 300 ms" is one deadline from the moment the mock sends the frame: each
  check gets the time left to it.
- "With no pictogram": the note's text content, trimmed, is exactly the value,
  the note holds no `svg`, and neither the note nor any element inside it draws
  a `::before` or `::after` with content.
- "The stream ends with" the line: it is the last element child of `chat-list`
  (spec 043's one list of messages and event lines).
- "No `salon-dot` showed": `salon-dot` is not visible (absent or hidden) once the
  line is in the page, just before `show_tab`.
- The vote closed after the solve (AC-4's last sentence) is read at 360 by 740,
  where the Salon is closed, so the line also makes its note ("Edge cases and
  errors": "the line and the note come at `vote_closed`").
- AC-5's notes are noted in the page by a `MutationObserver` (spec 043 AC-26's
  test does the same), so a note that shows and goes between two reads is not
  missed. The 3,500 ms after the close are an observation window, not a
  measured duration: a slow machine can only make it longer, so the file runs in
  the parallel pass.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridSolved, VoteOutcome
from room_panels import show_tab
from spec019_harness import OpenWindow, window_opener
from spec042_harness import expect_seq, wait_until
from spec043_harness import (
    RoomMock,
    chat_frame,
    chat_line,
    font_size_of,
    fr_format,
    pictograms_in,
    same_font_size,
    send_and_wait,
)
from spec047_harness import (
    COMPUTER,
    FOLLOW_MS,
    MUTED,
    OUTCOME_IDS,
    OUTCOMES,
    PHONE,
    QUIET_MS,
    VOTE,
    closed,
    colour_problem,
    note_shown_under_banner,
    open_vote_room,
    recorded_notes,
    result_text,
    show_vote,
    start_recording_notes,
    vote_lines,
    vote_room_frame,
)

WATCH_AFTER_CLOSE_MS = 3500  # "in the 3,500 ms that follow"
SETTLE_AFTER_MESSAGES_MS = 500
EVENT_FONT_SIZE_PX = 13.12  # spec 043's event look, 0.82rem

# The last element child of the stream: its test id, kind, seq and pictograms.
LAST_LINE_SCRIPT = r"""
() => {
  const list = document.querySelector('[data-testid="chat-list"]');
  const last = list === null ? null : list.lastElementChild;
  if (last === null) {
    return null;
  }
  return {
    testId: last.getAttribute('data-testid'),
    kind: last.getAttribute('data-kind'),
    seq: last.getAttribute('data-seq'),
    text: last.textContent.replace(/\s+/g, ' ').trim(),
  };
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_voted(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int] = PHONE
) -> tuple[Page, RoomMock]:
    """`VOTE_ROOM` at `size` (360 by 740 by default), `VOTE`, a click on yes."""
    page = window(size[0], size[1], False)
    mock = open_vote_room(page, base_url, grid)
    show_vote(page, mock)
    page.get_by_test_id("vote-yes").click()
    expect(page.get_by_test_id("vote-status")).to_be_visible()
    return page, mock


def time_left_ms(deadline: float) -> float:
    """The milliseconds left to `deadline` (`time.monotonic`), at least 1."""
    return max(1.0, (deadline - time.monotonic()) * 1000)


def send_close(page: Page, mock: RoomMock, outcome: VoteOutcome) -> float:
    """The mock sends `CLOSED(outcome)`; return the 300 ms deadline."""
    deadline = time.monotonic() + FOLLOW_MS / 1000
    mock.send(closed(outcome).model_dump_json())
    return deadline


def notes(page: Page) -> Locator:
    return page.get_by_test_id("room-note")


def drawn_pictograms(note: Locator) -> list[str]:
    """The `::before` and `::after` contents the note or its descendants draw."""
    drawn: list[str] = []
    for reading in pictograms_in(note):
        for content in (reading["before"], reading["after"]):
            if content not in ("none", "normal", ""):
                drawn.append(str(content))
    return drawn


def last_line(page: Page) -> dict[str, object]:
    found = page.evaluate(LAST_LINE_SCRIPT)
    assert isinstance(found, dict), "chat-list has no line"
    return found


# ---- AC-4: the banner leaves --------------------------------------------------


@pytest.mark.parametrize("outcome", OUTCOMES, ids=OUTCOME_IDS)
def test_ac4_the_banner_leaves_within_300_ms_and_the_announcement_says_how(
    window: OpenWindow, live_server: str, fx01_grid: Grid, outcome: VoteOutcome
) -> None:
    page, mock = open_voted(window, live_server, fx01_grid)

    deadline = send_close(page, mock, outcome)

    banner = page.get_by_test_id("vote-banner")
    expect(banner).to_have_count(0, timeout=time_left_ms(deadline))
    announcement = page.get_by_test_id("vote-announcement")
    expect(announcement).to_have_text(
        result_text(outcome), timeout=time_left_ms(deadline)
    )
    expect(page.get_by_test_id("vote-result")).to_have_count(0)


@pytest.mark.parametrize("outcome", OUTCOMES, ids=OUTCOME_IDS)
def test_ac4_one_note_shows_the_result_with_no_pictogram(
    window: OpenWindow, live_server: str, fx01_grid: Grid, outcome: VoteOutcome
) -> None:
    page, mock = open_voted(window, live_server, fx01_grid)

    deadline = send_close(page, mock, outcome)

    expect(notes(page)).to_have_count(1, timeout=time_left_ms(deadline))
    note = notes(page)
    expect(note).to_be_visible(timeout=time_left_ms(deadline))
    assert str(note.text_content()).strip() == result_text(outcome)
    expect(note.locator("svg")).to_have_count(0)
    assert drawn_pictograms(note) == []


@pytest.mark.parametrize("outcome", OUTCOMES, ids=OUTCOME_IDS)
def test_ac4_the_stream_ends_with_one_muted_vote_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid, outcome: VoteOutcome
) -> None:
    page, mock = open_voted(window, live_server, fx01_grid)
    mock.send(closed(outcome).model_dump_json())
    expect_seq(page, 7)

    show_tab(page, "discussion")

    lines = vote_lines(page)
    expect(lines).to_have_count(1)
    line = lines.first
    expect(line).to_have_attribute("data-seq", "7")
    expect(line).to_have_text(result_text(outcome))
    assert last_line(page)["testId"] == "feed-item"
    assert last_line(page)["kind"] == "vote"
    expect(line.get_by_test_id("feed-picto")).to_have_count(0)
    assert same_font_size(font_size_of(line), EVENT_FONT_SIZE_PX), font_size_of(line)
    assert colour_problem(line, "vote line", "color", MUTED) == []


@pytest.mark.parametrize("outcome", OUTCOMES, ids=OUTCOME_IDS)
def test_ac4_the_vote_line_lights_neither_the_dot_nor_the_badge(
    window: OpenWindow, live_server: str, fx01_grid: Grid, outcome: VoteOutcome
) -> None:
    page, mock = open_voted(window, live_server, fx01_grid)
    mock.send(closed(outcome).model_dump_json())
    expect_seq(page, 7)
    expect(notes(page)).to_have_count(1)
    page.wait_for_timeout(QUIET_MS)

    expect(page.get_by_test_id("salon-dot")).to_be_hidden()
    expect(page.get_by_test_id("chat-unread")).to_have_count(0)
    show_tab(page, "discussion")
    expect(vote_lines(page)).to_have_count(1)


def test_ac4_with_the_salon_column_on_discussion_the_line_comes_and_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_voted(window, live_server, fx01_grid, COMPUTER)
    expect(page.get_by_test_id("chat-panel")).to_be_visible()

    send_and_wait(page, mock, closed(VoteOutcome.PASSED).model_dump_json())

    lines = vote_lines(page)
    expect(lines).to_have_count(1)
    expect(lines.first).to_have_attribute("data-seq", "7")
    expect(lines.first).to_have_text(result_text(VoteOutcome.PASSED))
    page.wait_for_timeout(QUIET_MS)
    expect(notes(page)).to_have_count(0)


# ---- AC-4: no vote line from a snapshot ----------------------------------------


def test_ac4_a_first_snapshot_with_a_chat_history_holds_no_vote_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    chat = [chat_line(3, "p2", "Salut"), chat_line(4, "p3", "IDES ?")]

    open_vote_room(page, live_server, fx01_grid, chat=chat)
    show_tab(page, "discussion")

    expect(page.get_by_test_id("chat-message")).to_have_count(2)
    page.wait_for_timeout(QUIET_MS)
    expect(vote_lines(page)).to_have_count(0)


def test_ac4_a_snapshot_with_no_vote_after_a_reconnection_adds_no_vote_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    mock = open_vote_room(page, live_server, fx01_grid, open_vote=VOTE)
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    frames_before = len(mock.received)

    mock.close(1011)
    wait_until(page, lambda: mock.has_join_after(frames_before), "the second join")
    mock.send(vote_room_frame(fx01_grid, seq=7))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    expect_seq(page, 7)
    expect(page.get_by_test_id("vote-banner")).to_have_count(0)
    show_tab(page, "discussion")
    page.wait_for_timeout(QUIET_MS)
    expect(vote_lines(page)).to_have_count(0)


# ---- AC-4: a vote closed after the solve ---------------------------------------


def test_ac4_a_vote_closed_after_the_solve_still_adds_its_line_and_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    mock = open_vote_room(page, live_server, fx01_grid)
    show_vote(page, mock)
    send_and_wait(page, mock, GridSolved(seq=7, elapsed_ms=60_000).model_dump_json())
    expect(page.get_by_test_id("vote-banner")).to_have_count(0)

    late = closed(VoteOutcome.REJECTED, seq=8)
    send_and_wait(page, mock, late.model_dump_json())

    expect(notes(page)).to_have_count(1)
    expect(notes(page)).to_have_text(result_text(VoteOutcome.REJECTED))
    show_tab(page, "discussion")
    lines = vote_lines(page)
    expect(lines).to_have_count(1)
    expect(lines.first).to_have_attribute("data-seq", "8")
    expect(lines.first).to_have_text(result_text(VoteOutcome.REJECTED))


# ---- AC-5: notes that waited during the vote ----------------------------------


def open_vote_with_waiting_messages(
    window: OpenWindow, base_url: str, grid: Grid
) -> tuple[Page, RoomMock]:
    """At 360 by 740: `VOTE`, recording the notes, then `un` (7) and `deux` (8)."""
    page = window(PHONE[0], PHONE[1], False)
    mock = open_vote_room(page, base_url, grid)
    show_vote(page, mock)
    start_recording_notes(page)
    send_and_wait(page, mock, chat_frame(7, "p2", "un"))
    send_and_wait(page, mock, chat_frame(8, "p2", "deux"))
    page.wait_for_timeout(SETTLE_AFTER_MESSAGES_MS)
    return page, mock


def test_ac5_messages_during_the_vote_make_no_note(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_vote_with_waiting_messages(window, live_server, fx01_grid)

    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    assert recorded_notes(page) == []
    assert note_shown_under_banner(page) is False


def test_ac5_the_votes_result_is_the_one_note_once_the_banner_is_gone(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_vote_with_waiting_messages(window, live_server, fx01_grid)
    deadline = time.monotonic() + FOLLOW_MS / 1000

    mock.send(closed(VoteOutcome.PASSED, seq=9).model_dump_json())

    expect(page.get_by_test_id("vote-banner")).to_have_count(
        0, timeout=time_left_ms(deadline)
    )
    expect(notes(page)).to_have_count(1, timeout=time_left_ms(deadline))
    expect(notes(page)).to_have_text(result_text(VoteOutcome.PASSED))


def test_ac5_no_waiting_message_shows_as_a_note_after_the_vote(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_vote_with_waiting_messages(window, live_server, fx01_grid)

    mock.send(closed(VoteOutcome.PASSED, seq=9).model_dump_json())
    expect_seq(page, 9)
    page.wait_for_timeout(WATCH_AFTER_CLOSE_MS)

    texts = recorded_notes(page)
    for waiting in ("un", "deux"):
        text = fr_format("note.message", name="Bob", text=waiting)
        assert text not in texts, texts
    assert texts == [result_text(VoteOutcome.PASSED)]
    expect(page.get_by_test_id("chat-unread")).to_have_text("2")
