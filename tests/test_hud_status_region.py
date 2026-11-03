"""Tests of `client/hud.md` AC-26 and AC-27: the room page's status region (rules 17
and 18).

AC-26: with the socket opened and the join not answered, the page's first paint
holds the region (`role="status"`, empty, read but not seen), and it is the same
element once joined and again after a socket loss. Joined, « Rien à annuler. » is
held in it 5 s after it was last written: a second « Annuler » 4 s after the first
writes it again and starts the 5 s again. AC-27: at 1280 by 720 the host's settings
sheet holds its own region, empty at its opening; the socket closes and the
connection band's text goes to the sheet's region, which empties 5 s later, while
the page's region gets nothing; once the sheet is closed, « Annuler » with nothing
to undo is announced by the page's region, and « Copier le lien » 1 s later
replaces it with « Lien copié ».

Readings where the spec leaves room:

- The hooks are `data-testid="status-region"` (the page) and
  `data-testid="sheet-status-region"` (inside each room sheet); see `hud_harness`.
- "First paint" is read from a `MutationObserver` installed before the page loads:
  at the first batch of changes after which `room-page` is on the page, the region
  is on the page too, with its role and no text.
- "Still that element" is read from a mark set on the element once the socket is
  opened: it is still on the element after the join and after the loss.
- The 5 s of `MESSAGE_HOLD_MS` are read on Playwright's page clock, installed
  before the page loads and frozen once the room shows (for AC-27, once the sheet
  is open); the test then moves it by hand, with a real pause after each step so
  that the mocked socket's pongs reach the page. Each reading is exact: nothing
  moves the page's timers between two steps.
- "Makes it read" and "replaces the one there at once": the region reads the
  message once the page clock has moved at most `WRITE_LIMIT_MS` after the answer
  or the click, in steps of `WRITE_STEP_MS`. The moment the region first reads it
  is the moment the message was written (to the step).
- "Empty 5 s after it": the region is empty `MESSAGE_HOLD_MS` of page clock after
  the moment its last message was written (rule 17), which comes a few ms after
  the press since the page empties the region first.
- "A repeated text is still announced": the page's region, recorded after each
  batch of changes (`hud_harness.record_region_texts`), went from « Rien à
  annuler. » to empty and back before the second press's 5 s ran.
- "The page's region gets none": that recorder, started before the socket closes,
  records no change of the page's region while the sheet is open.
- "Within 5 s" (AC-27) is `CONNECTION_LOSS_MS` of page clock.
- « Copier le lien » is pressed with a clipboard that accepts every write (an init
  script), so that the copy succeeds in every engine.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import (
    CONNECTION_LOSS_MS,
    OFFLINE_TEXT,
    UNDO_NOTHING_TEXT,
    announcements_of,
    expect_page_region_reads,
    fx01_frame,
    live_role_problems,
    open_fx01_room,
    page_region,
    press_undo_answered_nothing,
    record_region_texts,
    recorded_region_texts,
    region_problems,
    sheet_region,
)
from nock.grid import Grid
from room_panels import open_host_settings, show_tab
from spec017_harness import (
    expect_offline,
    expect_status,
    grid_from_text,
    open_room,
    snapshot_frame,
)
from spec019_harness import OpenWindow, window_opener
from spec027_harness import advance_clock, freeze_clock
from spec042_harness import wait_until
from spec043_harness import COMPUTER, fr_value, show_snapshot

# What the page holds at the first batch of changes with `room-page` on it.
FIRST_SIGHT_SCRIPT = r"""
(() => {
  window.__regionAtFirstSight = null;
  const look = () => {
    if (window.__regionAtFirstSight !== null) return;
    const room = document.querySelector('[data-testid="room-page"]');
    if (room === null) return;
    const region = document.querySelector('[data-testid="status-region"]');
    window.__regionAtFirstSight = region === null
      ? {present: false}
      : {present: true, role: region.getAttribute('role'), text: region.textContent};
  };
  new MutationObserver(look).observe(document, {childList: true, subtree: true});
})();
"""
MARK_REGION_SCRIPT = "element => { element.__markedByTest = true; }"
READ_MARK_SCRIPT = "element => element.__markedByTest === true"
# A clipboard that takes every link, so that « Copier le lien » succeeds anywhere.
ACCEPTING_CLIPBOARD_SCRIPT = (
    "Object.defineProperty(navigator, 'clipboard', "
    "{value: {writeText: () => Promise.resolve()}});"
)

MESSAGE_HOLD_MS = 5000  # `MESSAGE_HOLD_MS`: a message stays 5 s after it was written
PRESS_GAP_MS = 4000  # AC-26: "pressed again 4 s later", "4 s after that press"
COPY_GAP_MS = 1000  # AC-27: « Copier le lien » "1 s later"
WRITE_LIMIT_MS = 500  # the most page clock a message may take to be written
WRITE_STEP_MS = 10
REAL_PAUSE_MS = 10  # the real pause after each step, for the pongs
COPIED_TEXT = fr_value("room.share.copied")  # « Lien copié »


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def is_marked(page: Page) -> bool:
    """Whether the page's region is still the element that was marked."""
    marked = page_region(page).evaluate(READ_MARK_SCRIPT)
    assert isinstance(marked, bool), marked
    return marked


# ---- The page clock ---------------------------------------------------------------


def page_clock_ms(page: Page) -> int:
    """Return the page's clock, `Date.now()`, in milliseconds."""
    found = page.evaluate("() => Date.now()")
    assert isinstance(found, int | float), found
    return int(found)


def advance_clock_to(page: Page, target_ms: int) -> None:
    """Move the frozen page clock to `target_ms` exactly, in spec 027's steps."""
    left_ms = target_ms - page_clock_ms(page)
    assert left_ms >= 0, f"the page clock is already {-left_ms} ms past {target_ms}"
    advance_clock(page, left_ms)


def advance_until(
    page: Page, condition: Callable[[], bool], what: str, limit_ms: int
) -> int:
    """Move the frozen page clock in small steps until `condition` holds.

    Args:
        page: The page, with a frozen clock.
        condition: What the test waits for, read after each step.
        what: What the condition means, for the failure message.
        limit_ms: The most the clock may move.

    Returns:
        The page clock at the first step after which the condition held.
    """
    moved_ms = 0
    while not condition():
        if moved_ms >= limit_ms:
            pytest.fail(f"{what}: not after {limit_ms} ms of page clock")
        page.clock.run_for(WRITE_STEP_MS)
        page.wait_for_timeout(REAL_PAUSE_MS)
        moved_ms += WRITE_STEP_MS
    return page_clock_ms(page)


def region_text(region: Locator) -> str:
    """Return the text a status region holds, without surrounding white space."""
    text = region.text_content()
    assert text is not None, "the region has no text node"
    return text.strip()


def advance_until_it_reads(page: Page, region: Locator, text: str) -> int:
    """Move the frozen page clock until `region` reads `text`; return that moment."""
    return advance_until(
        page,
        lambda: region_text(region) == text,
        f"the region reads {text!r}",
        WRITE_LIMIT_MS,
    )


# ---- AC-26: the region from the first paint, the same element for the page's life --


def test_ac26_the_region_is_there_at_the_first_paint_and_stays_the_same_element(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = open_room(page, live_server, init_script=FIRST_SIGHT_SCRIPT)
    expect_status(page, "joining")

    first_sight = page.evaluate("() => window.__regionAtFirstSight")
    assert first_sight == {"present": True, "role": "status", "text": ""}
    region = page_region(page)
    expect(region).to_have_count(1)
    expect(region).to_have_text("")
    assert region_problems(region) == []
    region.evaluate(MARK_REGION_SCRIPT)

    room.connections[0].send(snapshot_frame(fx01_grid, 5))
    expect_status(page, "joined")
    assert is_marked(page)

    room.connections[0].close(1011)
    expect_offline(page)
    assert is_marked(page)
    assert region_problems(page_region(page)) == []


# ---- AC-26: a message stays 5 s after the last one was written ----------------------


def test_ac26_a_second_message_is_announced_again_and_starts_the_5_s_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    page.clock.install()
    mock = open_fx01_room(page, live_server, fx01_grid)
    freeze_clock(page)
    region = page_region(page)
    expect(region).to_have_text("")
    record_region_texts(page)

    first_press_at = page_clock_ms(page)
    press_undo_answered_nothing(page, mock)
    advance_until_it_reads(page, region, UNDO_NOTHING_TEXT)
    advance_clock_to(page, first_press_at + PRESS_GAP_MS)
    expect(region).to_have_text(UNDO_NOTHING_TEXT)

    second_press_at = page_clock_ms(page)
    press_undo_answered_nothing(page, mock)
    written_at = advance_until(
        page,
        lambda: announcements_of(recorded_region_texts(page))
        == [UNDO_NOTHING_TEXT, "", UNDO_NOTHING_TEXT],
        "the region empties and reads « Rien à annuler. » again",
        WRITE_LIMIT_MS,
    )

    advance_clock_to(page, second_press_at + PRESS_GAP_MS)
    expect(region).to_have_text(UNDO_NOTHING_TEXT)
    advance_clock_to(page, written_at + MESSAGE_HOLD_MS - WRITE_STEP_MS)
    expect(region).to_have_text(UNDO_NOTHING_TEXT)
    advance_clock_to(page, written_at + MESSAGE_HOLD_MS)
    expect(region).to_have_text("")


# ---- AC-27: the host's sheet holds the messages while it is open ------------------


def test_ac27_a_sheet_takes_the_messages_and_the_page_gets_them_once_it_closes(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    page.add_init_script(ACCEPTING_CLIPBOARD_SCRIPT)
    page.clock.install()
    mock = open_fx01_room(page, live_server, fx01_grid)
    show_tab(page, "players")
    open_host_settings(page)
    sheet = sheet_region(page, "host-settings")
    expect(sheet).to_have_count(1)
    expect(sheet).to_have_text("")
    assert region_problems(sheet) == []
    expect(page_region(page)).to_have_text("")
    freeze_clock(page)
    record_region_texts(page)
    frames_before = len(mock.received)

    mock.close(1011)

    came_at = advance_until(
        page,
        lambda: region_text(sheet) == OFFLINE_TEXT,
        "the sheet's region reads the connection band",
        CONNECTION_LOSS_MS,
    )
    expect(page_region(page)).to_have_text("")
    banner = page.get_by_test_id("connection-banner")
    expect(banner).to_have_text(OFFLINE_TEXT)
    assert live_role_problems(banner) == []
    advance_clock_to(page, came_at + MESSAGE_HOLD_MS)
    expect(sheet).to_have_text("")
    assert recorded_region_texts(page) == [], "the page's region got a message"

    page.keyboard.press("Escape")
    expect(page.get_by_test_id("host-settings")).not_to_have_attribute("open", "")
    wait_until(page, lambda: mock.has_join_after(frames_before), "the new join")
    show_snapshot(page, mock, fx01_frame(fx01_grid))
    expect(banner).to_have_count(0)
    assert region_problems(page_region(page)) == []

    undo_pressed_at = page_clock_ms(page)
    press_undo_answered_nothing(page, mock)

    advance_until_it_reads(page, page_region(page), UNDO_NOTHING_TEXT)
    expect_page_region_reads(page, UNDO_NOTHING_TEXT)

    advance_clock_to(page, undo_pressed_at + COPY_GAP_MS)
    page.get_by_test_id("copy-link").click()

    advance_until_it_reads(page, page_region(page), COPIED_TEXT)
    expect_page_region_reads(page, COPIED_TEXT)
