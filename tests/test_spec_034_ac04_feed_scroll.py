"""Tests of spec 034, AC-4: the catch-up lines follow spec 013's feed scroll rules.

Browser with the mocked socket and the mocked catch-up, at 1280 by 720, with the
measures of spec 013's "Feed scroll states": at its end (at most 1 px from it),
settled (two reads of `scrollTop` 100 ms apart are equal) and items in view (a
`feed-item` whose box overlaps the list's by more than 1 px). The checks within
300 ms and 300 ms after `data-catch-up="5-9"` are of the kind of spec 013's
serial file, so this file runs in the serial pass (`SERIAL_TEST_FILES` of
`scripts/gate_browsers.py`). The shared setup is in `spec034_harness`.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from spec034_harness import (
    BOB,
    CY,
    VIDE,
    WAIT_TIMEOUT_MS,
    CatchUpRoute,
    catch_up_json,
    check_line,
    expect_catch_up_applied,
    expect_seq,
    feed_item_locator,
    grid_from_text,
    grid_line_frame,
    open_mocked_room,
    record_with,
    reveal_line,
    word_completed_line,
)

FEED_LIST_SELECTOR = '[data-testid="activity-feed"] ul'
TOLERANCE_PX = 1.0
FOLLOW_MS = 300
END_WATCH_LIMIT_MS = 1000
SETTLED_READ_MS = 100
SETTLED_LIMIT_MS = 2000
FIRST_LIVE_SEQ = 10
LAST_LIVE_SEQ = 25

FEED_SCROLL_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  return {
    scrollTop: list.scrollTop,
    scrollHeight: list.scrollHeight,
    clientHeight: list.clientHeight,
  };
}
"""
SCROLL_TO_MIDDLE_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  list.scrollTop = Math.floor((list.scrollHeight - list.clientHeight) / 2);
}
"""
ITEMS_IN_VIEW_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  const listBox = list.getBoundingClientRect();
  const found = [];
  for (const item of list.querySelectorAll('[data-testid="feed-item"]')) {
    const box = item.getBoundingClientRect();
    const overlap = Math.min(box.bottom, listBox.bottom)
      - Math.max(box.top, listBox.top);
    if (overlap > 1) {
      found.push([item.getAttribute('data-seq'), box.top]);
    }
  }
  return found;
}
"""
ITEM_TOPS_SCRIPT = """
selector => {
  const tops = {};
  const list = document.querySelector(selector);
  for (const item of list.querySelectorAll('[data-testid="feed-item"]')) {
    tops[item.getAttribute('data-seq')] = item.getBoundingClientRect().top;
  }
  return tops;
}
"""
# The end watch: from now on, at every animation frame, note the first frame where
# `room-page` has the `data-catch-up` value, then the first frame from there where
# the feed list is at its end. It gives up `limitMs` after the trigger. Times are
# performance.now() values.
END_WATCH_SCRIPT = """
({selector, value, limitMs, atEndPx}) => {
  const watch = {triggerAt: null, atEndAt: null, last: null, done: false};
  window.catchUpEndWatch = watch;
  const triggered = () => {
    const room = document.querySelector('[data-testid="room-page"]');
    return room !== null && room.getAttribute('data-catch-up') === value;
  };
  const atEnd = () => {
    const list = document.querySelector(selector);
    if (list === null) {
      watch.last = null;
      return false;
    }
    watch.last = {
      scrollTop: list.scrollTop,
      scrollHeight: list.scrollHeight,
      clientHeight: list.clientHeight,
    };
    return list.scrollHeight - list.clientHeight - list.scrollTop <= atEndPx;
  };
  const look = () => {
    const now = performance.now();
    if (watch.triggerAt === null && triggered()) {
      watch.triggerAt = now;
    }
    if (watch.triggerAt !== null) {
      if (atEnd()) {
        watch.atEndAt = now;
        watch.done = true;
        return;
      }
      if (now - watch.triggerAt > limitMs) {
        watch.done = true;
        return;
      }
    }
    requestAnimationFrame(look);
  };
  requestAnimationFrame(look);
}
"""


class FeedScroll(NamedTuple):
    """The measures of the feed list of spec 013's "Client: feed scroll position"."""

    scroll_top: float
    scroll_height: int
    client_height: int

    @property
    def at_end(self) -> bool:
        """At most 1 px from the end; a list that does not scroll is at its end."""
        distance = self.scroll_height - self.client_height - self.scroll_top
        return distance <= TOLERANCE_PX

    @property
    def scrolls(self) -> bool:
        return self.scroll_height > self.client_height


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def absence_lines_json() -> str:
    """AC-4's answer: a word by `p2`, a check by `p2`, a reveal by `p3` (`CY`)."""
    return catch_up_json(
        5,
        9,
        lines=[
            word_completed_line(7, BOB, VIDE),
            check_line(8, BOB),
            reveal_line(9, CY),
        ],
        names=[(CY, "CY")],
    )


def read_feed_scroll(page: Page) -> FeedScroll:
    raw = page.evaluate(FEED_SCROLL_SCRIPT, FEED_LIST_SELECTOR)
    return FeedScroll(
        scroll_top=raw["scrollTop"],
        scroll_height=raw["scrollHeight"],
        client_height=raw["clientHeight"],
    )


def wait_until_settled(page: Page) -> FeedScroll:
    """Read scrollTop every 100 ms until two reads in a row are equal; 2 s at most."""
    previous = read_feed_scroll(page)
    for _ in range(SETTLED_LIMIT_MS // SETTLED_READ_MS):
        page.wait_for_timeout(SETTLED_READ_MS)
        current = read_feed_scroll(page)
        if current.scroll_top == previous.scroll_top:
            return current
        previous = current
    pytest.fail(f"the feed list is not settled after 2 s: {previous}")


def items_in_view(page: Page) -> dict[int, float]:
    """The bounding box top of each feed item in view, by `data-seq`."""
    found = page.evaluate(ITEMS_IN_VIEW_SCRIPT, FEED_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found:
        tops[int(seq)] = float(top)
    return tops


def item_tops(page: Page) -> dict[int, float]:
    found = page.evaluate(ITEM_TOPS_SCRIPT, FEED_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found.items():
        tops[int(seq)] = float(top)
    return tops


def start_end_watch(page: Page, value: str) -> None:
    page.evaluate(
        END_WATCH_SCRIPT,
        {
            "selector": FEED_LIST_SELECTOR,
            "value": value,
            "limitMs": END_WATCH_LIMIT_MS,
            "atEndPx": TOLERANCE_PX,
        },
    )


def assert_at_end_within_300_ms(page: Page) -> None:
    page.wait_for_function("() => window.catchUpEndWatch.done", timeout=WAIT_TIMEOUT_MS)
    watch = page.evaluate("() => window.catchUpEndWatch")
    assert watch["atEndAt"] is not None, (
        f"the feed list is not at its end {END_WATCH_LIMIT_MS} ms after"
        f" data-catch-up: {watch['last']}"
    )
    elapsed_ms = watch["atEndAt"] - watch["triggerAt"]
    assert elapsed_ms <= FOLLOW_MS, (
        f"the feed list reached its end {elapsed_ms:.0f} ms after data-catch-up,"
        f" more than {FOLLOW_MS} ms"
    )


def open_return_with_live_lines(
    page: Page, base_url: str, grid: Grid, route: CatchUpRoute
) -> None:
    """The return of AC-4, its request held while 16 live lines (10 to 25) arrive."""
    mock = open_mocked_room(page, base_url, grid, route, record=record_with(5), seq=9)
    route.wait_for_requests(page, 1)
    for seq in range(FIRST_LIVE_SEQ, LAST_LIVE_SEQ + 1):
        mock.send(grid_line_frame(seq))
    expect_seq(page, LAST_LIVE_SEQ)
    expect(feed_item_locator(page)).to_have_count(16)


def test_ac4_the_newest_catch_up_line_is_in_view_with_the_list_at_its_end(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute(answer=absence_lines_json())
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=9)
    start_end_watch(page, "5-9")

    expect_catch_up_applied(page, "5-9")

    expect(feed_item_locator(page)).to_have_count(3)
    assert_at_end_within_300_ms(page)
    settled = wait_until_settled(page)
    assert settled.at_end, f"the feed list is not at its end: {settled}"
    assert 9 in items_in_view(page)


def test_ac4_after_live_lines_at_its_end_the_list_is_at_its_end_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    open_return_with_live_lines(page, live_server, fx01_grid, route)
    start = wait_until_settled(page)
    assert start.scrolls, f"the case starts with a list that scrolls: {start}"
    assert start.at_end, f"the case starts with the list at its end: {start}"
    start_end_watch(page, "5-9")

    route.answer_json(0, absence_lines_json())

    expect_catch_up_applied(page, "5-9")
    expect(feed_item_locator(page)).to_have_count(19)
    assert_at_end_within_300_ms(page)


def test_ac4_a_reader_scrolled_up_keeps_every_item_in_view_in_its_place(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    open_return_with_live_lines(page, live_server, fx01_grid, route)
    page.evaluate(SCROLL_TO_MIDDLE_SCRIPT, FEED_LIST_SELECTOR)
    start = wait_until_settled(page)
    assert start.scrolls, f"the case starts with a list that scrolls: {start}"
    assert not start.at_end, f"the case starts away from the end: {start}"
    noted = items_in_view(page)
    assert noted != {}, "no feed item in view before the catch-up"

    route.answer_json(0, absence_lines_json())

    expect_catch_up_applied(page, "5-9")
    expect(feed_item_locator(page)).to_have_count(19)
    page.wait_for_timeout(FOLLOW_MS)
    tops_now = item_tops(page)
    out_of_place: list[tuple[int, float, float | None]] = []
    for seq, noted_top in noted.items():
        top_now = tops_now.get(seq)
        if top_now is None or abs(top_now - noted_top) > TOLERANCE_PX:
            out_of_place.append((seq, noted_top, top_now))
    assert out_of_place == []
