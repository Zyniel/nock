"""Tests of spec 047, AC-2: the banner counts the seconds left of a vote the page
saw open, and shows no count for a vote it only learned from a snapshot.

On `VOTE_ROOM` at 1280 by 720, Playwright's page clock is installed before the page
opens (`page.clock.install()`, as "Test harness" says), then frozen once the
snapshot shows (spec 027's `freeze_clock`), so that the moment the page applies
`VOTE` and every later reading are exact: no real delay can shift a value. The
clock then moves with `page.clock.run_for` in steps of 100 ms with a real pause of
10 ms between them (spec 027's `advance_clock`), so that the mocked socket's pong
to each of the page's `ping` frames (spec 017) reaches the page before its next
silence check. Nothing here depends on how fast the machine is, so the file runs
in the parallel pass.

Readings where the spec leaves room:

- "The fill is 0.75 of the bar's width (1 px)": the bounding-box width of
  `vote-timebar-fill` is within 1 px of 0.75 times that of `vote-timebar`; "as wide
  as the bar" is 1 times, "0 px wide" is within 1 px of 0.
- The run with reduced motion is the same run on a page that called
  `page.emulate_media(reduced_motion="reduce")` before it opened.
- Reconnection: after the close (code 1011) the clock moves on in the same steps
  until the page sends its next join (spec 017's retry timers run on the page's
  clock), then the mock answers with the snapshot. "Never `20 s`" is read with a
  `MutationObserver` that notes each text of `vote-seconds` from just before the
  close until the page is `joined` again and the test has read the count.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec027_harness import advance_clock, freeze_clock
from spec042_harness import box_of
from spec043_harness import RoomMock, style_of
from spec047_harness import (
    COMPUTER,
    VOTE,
    VOTE_QUESTION,
    open_vote_room,
    seconds_shown,
    seconds_text,
    show_vote,
    vote_room_frame,
)

MOTIONS = [False, True]
MOTION_IDS = ["motion", "reduced-motion"]
CLOCK_STEP_MS = 100
RECONNECT_LIMIT_MS = 15_000
WIDTH_TOLERANCE_PX = 1.0

# Note each new text of `vote-seconds` in `window.spec047Seconds`.
RECORD_SECONDS_SCRIPT = r"""
() => {
  const texts = [];
  let last = null;
  const record = () => {
    const seconds = document.querySelector('[data-testid="vote-seconds"]');
    const text = seconds === null ? null : seconds.textContent.trim();
    if (text !== null && text !== last) {
      texts.push(text);
    }
    last = text;
  };
  window.spec047Seconds = texts;
  new MutationObserver(record).observe(document.body,
    {childList: true, subtree: true, characterData: true});
  record();
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


def open_counting(
    window: OpenWindow, base_url: str, grid: Grid, reduced_motion: bool = False
) -> tuple[Page, RoomMock]:
    """`VOTE_ROOM` at 1280 by 720 on the page clock, frozen, then `VOTE`."""
    page = window(COMPUTER[0], COMPUTER[1], False)
    if reduced_motion:
        page.emulate_media(reduced_motion="reduce")
    page.clock.install()
    mock = open_vote_room(page, base_url, grid)
    freeze_clock(page)
    show_vote(page, mock)
    return page, mock


def seconds_of(page: Page) -> Locator:
    return page.get_by_test_id("vote-seconds")


def fill_problems(page: Page, share: float) -> list[str]:
    """How the fill's width differs from `share` of the bar's width (1 px)."""
    bar = page.get_by_test_id("vote-timebar")
    bar_width = box_of(bar).width
    fill_width = box_of(bar.get_by_test_id("vote-timebar-fill")).width
    expected = bar_width * share
    if abs(fill_width - expected) <= WIDTH_TOLERANCE_PX:
        return []
    return [f"fill {fill_width} px of a {bar_width} px bar, not {share} of it"]


def expect_reading(page: Page, count: int, share: float) -> None:
    """Fail unless `vote-seconds` reads `count` s and the fill is `share` wide."""
    expect(seconds_of(page)).to_have_text(seconds_text(count))
    assert fill_problems(page, share) == []


# ---- The count and the bar --------------------------------------------------------


@pytest.mark.parametrize("reduced_motion", MOTIONS, ids=MOTION_IDS)
def test_ac2_the_count_starts_at_20_s_with_a_full_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, reduced_motion: bool
) -> None:
    page, _ = open_counting(window, live_server, fx01_grid, reduced_motion)

    assert seconds_text(20) == "20 s"
    expect_reading(page, 20, 1.0)


@pytest.mark.parametrize("reduced_motion", MOTIONS, ids=MOTION_IDS)
def test_ac2_five_seconds_later_it_reads_15_s_and_the_bar_is_three_quarters(
    window: OpenWindow, live_server: str, fx01_grid: Grid, reduced_motion: bool
) -> None:
    page, _ = open_counting(window, live_server, fx01_grid, reduced_motion)

    advance_clock(page, 5000)

    expect_reading(page, 15, 0.75)


@pytest.mark.parametrize("reduced_motion", MOTIONS, ids=MOTION_IDS)
def test_ac2_at_the_deadline_it_reads_0_s_with_an_empty_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, reduced_motion: bool
) -> None:
    page, _ = open_counting(window, live_server, fx01_grid, reduced_motion)
    advance_clock(page, 5000)
    expect_reading(page, 15, 0.75)

    advance_clock(page, 15_000)

    expect_reading(page, 0, 0.0)


@pytest.mark.parametrize("reduced_motion", MOTIONS, ids=MOTION_IDS)
def test_ac2_after_the_deadline_the_banner_stays_at_0_s_until_vote_closed(
    window: OpenWindow, live_server: str, fx01_grid: Grid, reduced_motion: bool
) -> None:
    page, _ = open_counting(window, live_server, fx01_grid, reduced_motion)
    advance_clock(page, 20_000)
    expect_reading(page, 0, 0.0)

    advance_clock(page, 5000)

    expect_reading(page, 0, 0.0)
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    # "Edge cases and errors": the buttons stay enabled at « 0 s ».
    expect(page.get_by_test_id("vote-yes")).to_be_enabled()
    expect(page.get_by_test_id("vote-no")).to_be_enabled()


def test_ac2_the_countdown_sends_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    """ "The countdown is the page's own: nothing is sent" (pings left out)."""
    page, mock = open_counting(window, live_server, fx01_grid)
    frames_before = len(mock.frames_without_pings())

    advance_clock(page, 5000)

    expect(seconds_of(page)).to_have_text(seconds_text(15))
    assert mock.frames_without_pings()[frames_before:] == []


@pytest.mark.parametrize("reduced_motion", MOTIONS, ids=MOTION_IDS)
def test_ac2_the_fill_has_no_transition(
    window: OpenWindow, live_server: str, fx01_grid: Grid, reduced_motion: bool
) -> None:
    page, _ = open_counting(window, live_server, fx01_grid, reduced_motion)

    fill = page.get_by_test_id("vote-timebar-fill")

    expect(fill).to_have_count(1)
    assert style_of(fill, "transitionDuration") == "0s"


# ---- A reconnection keeps the page's own count ---------------------------------


def test_ac2_a_reconnection_keeps_the_pages_own_count(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_counting(window, live_server, fx01_grid)
    advance_clock(page, 5000)
    expect(seconds_of(page)).to_have_text(seconds_text(15))
    page.evaluate(RECORD_SECONDS_SCRIPT)
    frames_before = len(mock.received)

    mock.close(1011)
    moved = 0
    while not mock.has_join_after(frames_before):
        if moved >= RECONNECT_LIMIT_MS:
            pytest.fail("the page did not join again")
        advance_clock(page, CLOCK_STEP_MS)
        moved += CLOCK_STEP_MS
    mock.send(vote_room_frame(fx01_grid, seq=6, open_vote=VOTE))

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(page.get_by_test_id("vote-banner")).to_be_visible()
    expect(seconds_of(page)).to_have_count(1)
    count = seconds_shown(str(seconds_of(page).text_content()))
    recorded = page.evaluate("() => window.spec047Seconds")
    assert count is not None, seconds_of(page).text_content()
    assert count <= 15, count
    assert isinstance(recorded, list), recorded
    assert seconds_text(20) not in recorded, recorded


# ---- A vote known only from a snapshot -------------------------------------------


def test_ac2_a_vote_known_only_from_a_snapshot_shows_no_seconds_and_no_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)

    open_vote_room(page, live_server, fx01_grid, open_vote=VOTE)

    banner = page.get_by_test_id("vote-banner")
    expect(banner).to_be_visible()
    expect(banner.get_by_test_id("vote-question")).to_have_text(VOTE_QUESTION)
    expect(banner.get_by_test_id("vote-yes")).to_be_visible()
    expect(banner.get_by_test_id("vote-no")).to_be_visible()
    expect(page.get_by_test_id("vote-seconds")).to_have_count(0)
    expect(page.get_by_test_id("vote-timebar")).to_have_count(0)
