"""Tests of `client/hud.md` AC-26 and AC-27: the room page's status region (rules 17
and 18).

AC-26: with the socket opened and the join not answered, the page's first paint
holds the region (`role="status"`, empty, read but not seen), and it is the same
element once joined and again after a socket loss. AC-27: at 1280 by 720 the host's
settings sheet holds its own region, empty at its opening; the socket closes and
the connection band's text goes to the sheet's region while the page's stays empty;
once the sheet is closed, « Annuler » with nothing to undo is announced by the
page's region.

Readings where the spec leaves room:

- The hooks are `data-testid="status-region"` (the page) and
  `data-testid="sheet-status-region"` (inside each room sheet); see `hud_harness`.
- "First paint" is read from a `MutationObserver` installed before the page loads:
  at the first batch of changes after which `room-page` is on the page, the region
  is on the page too, with its role and no text.
- "Still that element" is read from a mark set on the element once the socket is
  opened: it is still on the element after the join and after the loss.
- "Within 5 s" is Playwright's wait of `CONNECTION_LOSS_MS`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from hud_harness import (
    CONNECTION_LOSS_MS,
    OFFLINE_TEXT,
    UNDO_NOTHING_TEXT,
    expect_page_region_reads,
    fx01_frame,
    live_role_problems,
    open_host_sheet,
    page_region,
    press_undo_answered_nothing,
    region_problems,
    sheet_region,
)
from nock.grid import Grid
from spec017_harness import (
    expect_offline,
    expect_status,
    grid_from_text,
    open_room,
    snapshot_frame,
)
from spec019_harness import OpenWindow, window_opener
from spec042_harness import wait_until
from spec043_harness import COMPUTER, show_snapshot

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


# ---- AC-27: the host's sheet holds the messages while it is open ------------------


def test_ac27_a_sheet_takes_the_messages_and_the_page_gets_them_once_it_closes(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    mock = open_host_sheet(page, live_server, fx01_grid)
    sheet = sheet_region(page, "host-settings")
    expect(sheet).to_have_count(1)
    expect(sheet).to_have_text("")
    assert region_problems(sheet) == []
    expect(page_region(page)).to_have_text("")
    frames_before = len(mock.received)

    mock.close(1011)

    expect(sheet).to_have_text(OFFLINE_TEXT, timeout=CONNECTION_LOSS_MS)
    expect(page_region(page)).to_have_text("")
    banner = page.get_by_test_id("connection-banner")
    expect(banner).to_have_text(OFFLINE_TEXT)
    assert live_role_problems(banner) == []

    page.keyboard.press("Escape")
    expect(page.get_by_test_id("host-settings")).not_to_have_attribute("open", "")
    wait_until(page, lambda: mock.has_join_after(frames_before), "the new join")
    show_snapshot(page, mock, fx01_frame(fx01_grid))
    expect(banner).to_have_count(0)
    assert region_problems(page_region(page)) == []

    press_undo_answered_nothing(page, mock)

    expect_page_region_reads(page, UNDO_NOTHING_TEXT)
