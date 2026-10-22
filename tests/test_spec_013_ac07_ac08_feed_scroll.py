"""Tests of spec 013, AC-7 and AC-8: the scroll position of the activity feed.

The scripts and the helpers that measure and move the feed list are used by these
two criteria only, so they stay in this file. The shared setup is in
`spec013_harness`.

Refined by spec 043 (the design's room layout): the feed list is the Salon's
stream list (the one `ul` of `activity-feed`), so each page shows the Discussion
tab first with spec 043's `show_tab`, and measures the list once it returned.
`lock-room` is in the host's settings sheet (`open_host_settings`). Two places
follow spec 043's layout:

- AC-8's "Smaller window" turns the column layout into the sheet layout, which
  closes the Salon ("Which layout"); the test shows the Discussion tab again
  after the resize and checks that the list is at its end within 300 ms of
  being shown ("Edge cases and errors": the stream keeps spec 013's rules, so it
  shows the newest line when it was at its end).
- AC-7's "Filling" sends 40 line events (`seq` 6 to 45) where it sent ten: the
  stream fills the Salon's height (about 510 px at 1280 by 720, 299 px at 360 by
  740), so ten lines no longer make it scroll. The later cases take the next
  `seq` values (46 to 50), and "Full feed" sends `seq` 51 to 105, so it still ends
  with 100 items, `seq` 6 to 105.
- AC-7's "My own action" runs at 1280 by 720 only. At 360 by 740 (the sheet
  layout) opening the Menu to reach the host's settings closes the Salon (one
  overlay at a time), so the list is not on screen while the lock is clicked and
  "the probe stays put" cannot be read; this is reported to the lead. The later
  cases replay the action at both sizes and show the Discussion tab again after
  it.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import (
    GridTarget,
    LockRoom,
    RevealBudget,
    SettingsChanged,
    parse_client_message,
)
from room_panels import open_host_settings, show_tab
from spec013_harness import (
    DEFAULT_ROOM_SETTINGS,
    FORM_TIMEOUT_MS,
    WAIT_TIMEOUT_MS,
    MockRoomSocket,
    check_frame,
    feed_items,
    feed_locator,
    feed_snapshot_players,
    grid_from_text,
    make_page,
    open_room,
    wait_until,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-7 and AC-8: the feed's scroll position ----
#
# The spec runs the cases of AC-7, and those of AC-8, in a fixed order on one page,
# each from the state the case before it left. Here each case is its own test, so
# that each rule passes or fails on its own. A test replays the cases before its
# own (their events, scrolls and clicks, without their checks), then checks from
# the list's measures the state its own case starts from, and fails if that state
# does not hold. It then acts and checks what its case says.

FEED_LIST_SELECTOR = '[data-testid="activity-feed"] ul'
FEED_WINDOWS = [(1280, 720), (360, 740)]
FEED_WINDOW_IDS = ["1280x720", "360x740"]
TOLERANCE_PX = 1.0  # at its end, stays put, keeps its place: all within 1 px
FOLLOW_MS = 300  # "within 300 ms" and "300 ms after"
END_WATCH_LIMIT_MS = 1000  # an end watch gives up 1 s after its trigger
SETTLED_READ_MS = 100  # "settled": reads of scrollTop 100 ms apart
SETTLED_LIMIT_MS = 2000  # "It fails after 2 s."
LOCKED_LINE = "Ana a verrouillé le salon"

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

# Moves the feed list with a script, as AC-7 does: to the middle of its range
# ("middle"), to its scrollHeight ("end", where the browser stops it at the end)
# or 1 px before its end ("one_px_before_end").
SCROLL_FEED_SCRIPT = """
([selector, place]) => {
  const list = document.querySelector(selector);
  const range = list.scrollHeight - list.clientHeight;
  if (place === 'middle') {
    list.scrollTop = Math.floor(range / 2);
  } else if (place === 'end') {
    list.scrollTop = list.scrollHeight;
  } else if (place === 'one_px_before_end') {
    list.scrollTop = range - 1;
  } else {
    throw new Error('unknown place: ' + place);
  }
}
"""

# The scroll probe of the harness: from now on, read the list's scrollTop at every
# animation frame, and keep the value read just before the probe started. A frame
# without a feed list reads null.
START_PROBE_SCRIPT = """
selector => {
  const probe = {
    start: document.querySelector(selector).scrollTop,
    values: [],
    running: true,
  };
  window.feedScrollProbe = probe;
  const look = () => {
    if (!probe.running) {
      return;
    }
    const list = document.querySelector(selector);
    probe.values.push(list === null ? null : list.scrollTop);
    requestAnimationFrame(look);
  };
  requestAnimationFrame(look);
}
"""
STOP_PROBE_SCRIPT = """
() => {
  const probe = window.feedScrollProbe;
  probe.running = false;
  return {start: probe.start, values: probe.values};
}
"""

# The end watch: from now on, at every animation frame, note the first frame where
# the trigger holds (`seq`: the room page has that data-seq; `width`:
# window.innerWidth reads that value; `font`: the computed font-size of html reads
# that value), then the first frame from there where the feed list is at its end.
# For a `seq` trigger, the line of that seq must also be the last feed-item. The
# watch gives up `limitMs` after the trigger. Times are performance.now() values.
END_WATCH_SCRIPT = """
({selector, trigger, value, limitMs, atEndPx}) => {
  const watch = {
    trigger: trigger,
    value: value,
    triggerAt: null,
    atEndAt: null,
    last: null,
    done: false,
  };
  window.feedEndWatch = watch;
  const triggered = () => {
    if (trigger === 'seq') {
      const room = document.querySelector('[data-testid="room-page"]');
      return room !== null && room.getAttribute('data-seq') === value;
    }
    if (trigger === 'width') {
      return String(window.innerWidth) === value;
    }
    return getComputedStyle(document.documentElement).fontSize === value;
  };
  const atEnd = () => {
    const list = document.querySelector(selector);
    if (list === null) {
      watch.last = null;
      return false;
    }
    const items = list.querySelectorAll('[data-testid="feed-item"]');
    const lastItem = items[items.length - 1];
    const lastSeq = lastItem === undefined ? null : lastItem.getAttribute('data-seq');
    watch.last = {
      scrollTop: list.scrollTop,
      scrollHeight: list.scrollHeight,
      clientHeight: list.clientHeight,
      lastSeq: lastSeq,
    };
    if (trigger === 'seq' && lastSeq !== value) {
      return false;
    }
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

# "Items in view": the data-seq and the bounding box top of each feed-item whose
# box overlaps the list's box vertically by more than 1 px.
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
# The bounding box top of every feed-item, by data-seq.
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


class FeedScroll(NamedTuple):
    """The measures of the feed list that "Client: feed scroll position" uses."""

    scroll_top: float
    scroll_height: int
    client_height: int

    @property
    def distance_to_end(self) -> float:
        """`scrollHeight - clientHeight - scrollTop`."""
        return self.scroll_height - self.client_height - self.scroll_top

    @property
    def at_end(self) -> bool:
        """At most 1 px from the end; a list that does not scroll is at its end."""
        return self.distance_to_end <= TOLERANCE_PX

    @property
    def scrolls(self) -> bool:
        """Its items do not fit, so it scrolls."""
        return self.scroll_height > self.client_height


class FeedScene(NamedTuple):
    """A page of "Feed scroll states" and its mocked socket."""

    page: Page
    mock: MockRoomSocket


def read_feed_scroll(page: Page) -> FeedScroll:
    """Read the feed list's scrollTop, scrollHeight and clientHeight now."""
    raw = page.evaluate(FEED_SCROLL_SCRIPT, FEED_LIST_SELECTOR)
    return FeedScroll(
        scroll_top=raw["scrollTop"],
        scroll_height=raw["scrollHeight"],
        client_height=raw["clientHeight"],
    )


def line_frame(seq: int) -> str:
    """A line event of the harness: Bob checks the grid, with empty lists."""
    return check_frame(seq, "p2", GridTarget())


def wait_for_seq(page: Page, seq: int) -> None:
    """Wait until `room-page` has `data-seq` `seq` (spec 040)."""
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def send_lines(scene: FeedScene, first_seq: int, last_seq: int) -> None:
    """Send the line events one right after another, then wait for the last one."""
    for seq in range(first_seq, last_seq + 1):
        scene.mock.send(line_frame(seq))
    wait_for_seq(scene.page, last_seq)


def wait_until_settled(page: Page) -> FeedScroll:
    """Read scrollTop every 100 ms until two reads in a row are equal (harness).

    Fails when the list is not settled after 2 s.
    """
    previous = read_feed_scroll(page)
    for _ in range(SETTLED_LIMIT_MS // SETTLED_READ_MS):
        page.wait_for_timeout(SETTLED_READ_MS)
        current = read_feed_scroll(page)
        if current.scroll_top == previous.scroll_top:
            return current
        previous = current
    pytest.fail(f"the feed list is not settled after 2 s: {previous}")


def scroll_feed_and_settle(page: Page, place: str) -> FeedScroll:
    """Move the list with a script, then wait until it is settled (harness)."""
    page.evaluate(SCROLL_FEED_SCRIPT, [FEED_LIST_SELECTOR, place])
    return wait_until_settled(page)


def let_the_case_end(page: Page) -> None:
    """Give the page the 300 ms of a case, then wait until the list is settled."""
    page.wait_for_timeout(FOLLOW_MS)
    wait_until_settled(page)


def start_probe(page: Page) -> None:
    """Start the scroll probe; it reads every frame until it is checked."""
    page.evaluate(START_PROBE_SCRIPT, FEED_LIST_SELECTOR)


def assert_probe_stayed_put(page: Page, case: str) -> None:
    """Every value the probe read is within 1 px of the value before it started."""
    probe = page.evaluate(STOP_PROBE_SCRIPT)
    start = probe["start"]
    values = probe["values"]
    moved: list[float | None] = []
    for value in values:
        if value is None or abs(value - start) > TOLERANCE_PX:
            moved.append(value)
    assert values != [], f"{case}: the probe read no frame"
    assert moved == [], (
        f"{case}: the feed list moved away from scrollTop {start} in {len(moved)}"
        f" of {len(values)} frames, for example to {moved[:5]}"
    )


def start_end_watch(page: Page, trigger: str, value: str) -> None:
    """Start the end watch; `trigger` is `seq`, `width` or `font`."""
    page.evaluate(
        END_WATCH_SCRIPT,
        {
            "selector": FEED_LIST_SELECTOR,
            "trigger": trigger,
            "value": value,
            "limitMs": END_WATCH_LIMIT_MS,
            "atEndPx": TOLERANCE_PX,
        },
    )


def assert_at_end_within_300_ms(page: Page, case: str) -> None:
    """Fail unless the end watch saw the list at its end within 300 ms.

    The 300 ms are counted from the first frame where the watch's trigger held.
    The test calls this once it has seen the trigger hold.
    """
    page.wait_for_function("() => window.feedEndWatch.done", timeout=WAIT_TIMEOUT_MS)
    watch = page.evaluate("() => window.feedEndWatch")
    trigger = f"{watch['trigger']} {watch['value']}"
    assert watch["atEndAt"] is not None, (
        f"{case}: the feed list is not at its end {END_WATCH_LIMIT_MS} ms after"
        f" {trigger}: {watch['last']}"
    )
    elapsed_ms = watch["atEndAt"] - watch["triggerAt"]
    assert elapsed_ms <= FOLLOW_MS, (
        f"{case}: the feed list reached its end {elapsed_ms:.0f} ms after"
        f" {trigger}, more than {FOLLOW_MS} ms"
    )


def assert_case_starts(
    holds: bool, case: str, expected: str, scroll: FeedScroll
) -> None:
    """Fail when the feed list is not in the state that the case starts from."""
    assert holds, f"{case}: the case starts when {expected}, but not here: {scroll}"


def has_sent_lock_room(mock: MockRoomSocket) -> bool:
    """Whether the page has sent `lock_room` with `locked` true."""
    for frame in mock.received:
        if parse_client_message(frame) == LockRoom(locked=True):
            return True
    return False


def locked_settings_frame(seq: int) -> str:
    """`settings_changed` by `p1`: the snapshot's settings with `locked` true."""
    settings = DEFAULT_ROOM_SETTINGS.model_copy(update={"locked": True})
    event = SettingsChanged(
        seq=seq,
        player_id="p1",
        settings=settings,
        reveal_budget=RevealBudget(letters=5, words=1),
    )
    return event.model_dump_json()


def open_the_lock(scene: FeedScene) -> None:
    """Open the host's settings, where `lock-room` is (spec 043)."""
    open_host_settings(scene.page)


def lock_from_the_page(scene: FeedScene) -> None:
    """Click `lock-room`; once the page has sent `lock_room`, answer it.

    The host's settings are already open (`open_the_lock`).
    """
    scene.page.get_by_test_id("lock-room").click(timeout=FORM_TIMEOUT_MS)
    wait_until(scene.page, lambda: has_sent_lock_room(scene.mock))
    scene.mock.send(locked_settings_frame(OWN_ACTION_SEQ))


def feed_seqs(page: Page) -> list[int]:
    """The `data-seq` of each feed item, oldest first."""
    seqs: list[int] = []
    for _, seq, _ in feed_items(page):
        seqs.append(int(seq))
    return seqs


def items_in_view(page: Page) -> dict[int, float]:
    """The bounding box top of each feed item in view, by `data-seq` (harness)."""
    found = page.evaluate(ITEMS_IN_VIEW_SCRIPT, FEED_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found:
        tops[int(seq)] = float(top)
    return tops


def item_tops(page: Page) -> dict[int, float]:
    """The bounding box top of every feed item, by `data-seq`."""
    found = page.evaluate(ITEM_TOPS_SCRIPT, FEED_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found.items():
        tops[int(seq)] = float(top)
    return tops


def items_out_of_place(
    noted: dict[int, float], tops_now: dict[int, float]
) -> list[tuple[int, float, float | None]]:
    """The noted items that are gone, or whose top moved by more than 1 px.

    Each one is `(seq, noted top, top now)`, with None as the top of a gone item.
    """
    out_of_place: list[tuple[int, float, float | None]] = []
    for seq, noted_top in noted.items():
        top_now = tops_now.get(seq)
        if top_now is None or abs(top_now - noted_top) > TOLERANCE_PX:
            out_of_place.append((seq, noted_top, top_now))
    return out_of_place


# The `seq` of each case's line event (see the module docstring for the count).
FILL_FIRST_SEQ = 6
FILL_LAST_SEQ = 45
AT_END_SEQ = 46
SCROLLED_UP_SEQ = 47
OWN_ACTION_SEQ = 48
BACK_AT_END_SEQ = 49
ONE_PX_SEQ = 50
FULL_FIRST_SEQ = 51
FULL_LAST_SEQ = 105

# The cases of AC-7 without their checks, replayed before a later case. Each one
# ends once the page has applied its last event, 300 ms have passed and the list
# is settled.


def replay_filling(scene: FeedScene) -> None:
    """AC-7 "Filling" without its checks: lines 6 to 45."""
    send_lines(scene, FILL_FIRST_SEQ, FILL_LAST_SEQ)
    let_the_case_end(scene.page)


def replay_at_the_end(scene: FeedScene) -> None:
    """AC-7 "At the end" without its checks: line 46."""
    send_lines(scene, AT_END_SEQ, AT_END_SEQ)
    let_the_case_end(scene.page)


def replay_scrolled_up(scene: FeedScene) -> None:
    """AC-7 "Scrolled up" without its checks: to the middle, then line 47."""
    scroll_feed_and_settle(scene.page, "middle")
    send_lines(scene, SCROLLED_UP_SEQ, SCROLLED_UP_SEQ)
    let_the_case_end(scene.page)


def replay_my_own_action(scene: FeedScene) -> None:
    """AC-7 "My own action" without its checks: the lock and its line 48.

    The host's settings are closed again and the Discussion tab shown again, which
    the sheet layout closed while the settings were open (spec 043).
    """
    open_the_lock(scene)
    lock_from_the_page(scene)
    wait_for_seq(scene.page, OWN_ACTION_SEQ)
    scene.page.keyboard.press("Escape")
    show_tab(scene.page, "discussion")
    let_the_case_end(scene.page)


def replay_back_at_the_end(scene: FeedScene) -> None:
    """AC-7 "Back at the end" without its checks: to the end, then line 49."""
    scroll_feed_and_settle(scene.page, "end")
    send_lines(scene, BACK_AT_END_SEQ, BACK_AT_END_SEQ)
    let_the_case_end(scene.page)


def replay_within_1_px_of_the_end(scene: FeedScene) -> None:
    """AC-7 "Within 1 px of the end" without its checks: 1 px short, line 50."""
    scroll_feed_and_settle(scene.page, "one_px_before_end")
    send_lines(scene, ONE_PX_SEQ, ONE_PX_SEQ)
    let_the_case_end(scene.page)


@pytest.fixture(params=FEED_WINDOWS, ids=FEED_WINDOW_IDS)
def feed_scene(
    request: pytest.FixtureRequest,
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
) -> Iterator[FeedScene]:
    """The page of "Feed scroll states" at 1280 by 720 and at 360 by 740."""
    width, height = request.param
    page, close = make_page(browser, browser_name, width, height, touch=False)
    try:
        mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
        show_tab(page, "discussion")
        yield FeedScene(page=page, mock=mock)
    finally:
        close()


@pytest.fixture
def computer_feed_scene(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> Iterator[FeedScene]:
    """The page of "Feed scroll states" at 1280 by 720 only (see the docstring)."""
    page, close = make_page(browser, browser_name, 1280, 720, touch=False)
    try:
        mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
        show_tab(page, "discussion")
        yield FeedScene(page=page, mock=mock)
    finally:
        close()


def test_ac7_browser_filling_brings_the_list_to_its_end(feed_scene: FeedScene) -> None:
    page = feed_scene.page
    start_end_watch(page, "seq", str(FILL_LAST_SEQ))

    send_lines(feed_scene, FILL_FIRST_SEQ, FILL_LAST_SEQ)

    filled = read_feed_scroll(page)
    assert filled.scrolls, f"Filling: the feed list does not scroll: {filled}"
    assert_at_end_within_300_ms(page, "Filling")


def test_ac7_browser_at_the_end_a_new_line_keeps_the_list_at_its_end(
    feed_scene: FeedScene,
) -> None:
    page = feed_scene.page
    replay_filling(feed_scene)
    start = read_feed_scroll(page)
    assert_case_starts(start.at_end, "At the end", "the list is at its end", start)
    start_end_watch(page, "seq", str(AT_END_SEQ))

    send_lines(feed_scene, AT_END_SEQ, AT_END_SEQ)

    assert_at_end_within_300_ms(page, "At the end")


def test_ac7_browser_scrolled_up_a_new_line_leaves_the_list_in_place(
    feed_scene: FeedScene,
) -> None:
    page = feed_scene.page
    replay_filling(feed_scene)
    replay_at_the_end(feed_scene)
    start = scroll_feed_and_settle(page, "middle")
    assert_case_starts(
        not start.at_end, "Scrolled up", "the list is not at its end", start
    )
    start_probe(page)

    send_lines(feed_scene, SCROLLED_UP_SEQ, SCROLLED_UP_SEQ)

    page.wait_for_timeout(FOLLOW_MS)
    assert_probe_stayed_put(page, "Scrolled up")
    expect(feed_locator(page).last).to_have_attribute("data-seq", str(SCROLLED_UP_SEQ))


def test_ac7_browser_my_own_lock_line_leaves_the_list_in_place(
    computer_feed_scene: FeedScene,
) -> None:
    feed_scene = computer_feed_scene
    page = feed_scene.page
    replay_filling(feed_scene)
    replay_at_the_end(feed_scene)
    replay_scrolled_up(feed_scene)
    open_the_lock(feed_scene)
    start = read_feed_scroll(page)
    assert_case_starts(
        not start.at_end,
        "My own action",
        "the list is still where Scrolled up left it, not at its end",
        start,
    )
    start_probe(page)

    lock_from_the_page(feed_scene)

    wait_for_seq(page, OWN_ACTION_SEQ)
    page.wait_for_timeout(FOLLOW_MS)
    assert_probe_stayed_put(page, "My own action")
    last_item = feed_locator(page).last
    expect(last_item).to_have_attribute("data-seq", str(OWN_ACTION_SEQ))
    expect(last_item).to_have_text(LOCKED_LINE)


def test_ac7_browser_back_at_the_end_the_list_follows_new_lines_again(
    feed_scene: FeedScene,
) -> None:
    page = feed_scene.page
    replay_filling(feed_scene)
    replay_at_the_end(feed_scene)
    replay_scrolled_up(feed_scene)
    replay_my_own_action(feed_scene)
    start = scroll_feed_and_settle(page, "end")
    assert_case_starts(start.at_end, "Back at the end", "the list is at its end", start)
    start_end_watch(page, "seq", str(BACK_AT_END_SEQ))

    send_lines(feed_scene, BACK_AT_END_SEQ, BACK_AT_END_SEQ)

    assert_at_end_within_300_ms(page, "Back at the end")


def test_ac7_browser_within_1_px_of_the_end_counts_as_the_end(
    feed_scene: FeedScene,
) -> None:
    page = feed_scene.page
    replay_filling(feed_scene)
    replay_at_the_end(feed_scene)
    replay_scrolled_up(feed_scene)
    replay_my_own_action(feed_scene)
    replay_back_at_the_end(feed_scene)
    start = scroll_feed_and_settle(page, "one_px_before_end")
    assert_case_starts(
        start.at_end,
        "Within 1 px of the end",
        "the distance to the end is at most 1 px",
        start,
    )
    start_end_watch(page, "seq", str(ONE_PX_SEQ))

    send_lines(feed_scene, ONE_PX_SEQ, ONE_PX_SEQ)

    assert_at_end_within_300_ms(page, "Within 1 px of the end")


def test_ac7_browser_full_feed_the_items_in_view_keep_their_place(
    feed_scene: FeedScene,
) -> None:
    page = feed_scene.page
    replay_filling(feed_scene)
    replay_at_the_end(feed_scene)
    replay_scrolled_up(feed_scene)
    replay_my_own_action(feed_scene)
    replay_back_at_the_end(feed_scene)
    replay_within_1_px_of_the_end(feed_scene)
    start = read_feed_scroll(page)
    assert_case_starts(
        start.at_end,
        "Full feed",
        "the list is at its end, where Within 1 px of the end left it",
        start,
    )
    start_end_watch(page, "seq", str(FULL_LAST_SEQ))
    send_lines(feed_scene, FULL_FIRST_SEQ, FULL_LAST_SEQ)
    assert feed_seqs(page) == list(range(6, 106))
    assert_at_end_within_300_ms(page, "Full feed")
    middle = scroll_feed_and_settle(page, "middle")
    assert_case_starts(
        not middle.at_end, "Full feed", "the list is not at its end", middle
    )
    noted = items_in_view(page)
    assert noted != {}, f"Full feed: no feed item is in view: {middle}"

    send_lines(feed_scene, 106, 106)

    page.wait_for_timeout(FOLLOW_MS)
    seqs = feed_seqs(page)
    assert (seqs[0], seqs[-1]) == (7, 106)
    assert items_out_of_place(noted, item_tops(page)) == []


def resize_window(page: Page, width: int, height: int) -> None:
    """Resize the window, then wait until the page reads the new width."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_function(
        "width => window.innerWidth === width", arg=width, timeout=WAIT_TIMEOUT_MS
    )


def set_root_font(page: Page, size_px: int) -> None:
    """Set the root font as spec 014's harness does, and wait until it applies."""
    size = f"{size_px}px"
    page.evaluate("size => { document.documentElement.style.fontSize = size; }", size)
    page.wait_for_function(
        "size => getComputedStyle(document.documentElement).fontSize === size",
        arg=size,
        timeout=WAIT_TIMEOUT_MS,
    )


def replay_smaller_window(scene: FeedScene) -> None:
    """AC-8 "Smaller window" without its checks: the window becomes 360 by 740.

    The sheet layout closes the Salon, so the Discussion tab is shown again.
    """
    resize_window(scene.page, 360, 740)
    show_tab(scene.page, "discussion")
    let_the_case_end(scene.page)


def replay_larger_root_font(scene: FeedScene) -> None:
    """AC-8 "Larger root font" without its checks: the root font becomes 20 px."""
    set_root_font(scene.page, 20)
    let_the_case_end(scene.page)


@pytest.fixture
def filled_feed_scene(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> Iterator[FeedScene]:
    """AC-8's setup: "Feed scroll states" at 1280 by 720 with lines 6 to 45."""
    page, close = make_page(browser, browser_name, 1280, 720, touch=False)
    try:
        mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
        show_tab(page, "discussion")
        scene = FeedScene(page=page, mock=mock)
        replay_filling(scene)
        yield scene
    finally:
        close()


def assert_setup_at_end(page: Page) -> None:
    """AC-8's setup ends with the list at its end, which the test checks."""
    setup = read_feed_scroll(page)
    assert_case_starts(setup.at_end, "Setup", "the list is at its end", setup)


def test_ac8_browser_a_smaller_window_keeps_the_list_at_its_end(
    filled_feed_scene: FeedScene,
) -> None:
    page = filled_feed_scene.page
    assert_setup_at_end(page)
    resize_window(page, 360, 740)

    show_tab(page, "discussion")
    start_end_watch(page, "width", "360")

    resized = read_feed_scroll(page)
    assert resized.scrolls, f"Smaller window: the feed list does not scroll: {resized}"
    assert_at_end_within_300_ms(page, "Smaller window")


def test_ac8_browser_a_larger_root_font_keeps_the_list_at_its_end(
    filled_feed_scene: FeedScene,
) -> None:
    page = filled_feed_scene.page
    assert_setup_at_end(page)
    replay_smaller_window(filled_feed_scene)
    start = read_feed_scroll(page)
    assert_case_starts(
        start.at_end,
        "Larger root font",
        "the list is at its end, where Smaller window left it",
        start,
    )
    start_end_watch(page, "font", "20px")

    set_root_font(page, 20)

    assert_at_end_within_300_ms(page, "Larger root font")


def test_ac8_browser_a_larger_window_keeps_the_list_at_its_end(
    filled_feed_scene: FeedScene,
) -> None:
    page = filled_feed_scene.page
    assert_setup_at_end(page)
    replay_smaller_window(filled_feed_scene)
    replay_larger_root_font(filled_feed_scene)
    start = read_feed_scroll(page)
    assert_case_starts(
        start.at_end,
        "Larger window",
        "the list is at its end, where Larger root font left it",
        start,
    )
    start_end_watch(page, "width", "1280")

    resize_window(page, 1280, 720)

    assert_at_end_within_300_ms(page, "Larger window")
