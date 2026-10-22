"""Tests of spec 022, AC-11 and AC-12: the reading position of the chat list, and
its keyboard access.

AC-11 applies spec 013's "Client: feed scroll position" to the chat list, with
the "Chat scroll states" of the spec's "Test harness": spec 013's "Feed scroll
states" with the panel open, `chat-list` for the feed list, `chat-message` for
`feed-item`, and a line event that is a `chat_message` from `p2` with the text
`Ligne <seq>`. The cases of spec 013 AC-7 run in their order on one page per
window size, each from the state the case before it left, as that criterion
says; wherever a case says the list scrolls or is (not) at its end, the test
checks it from the list's measures first. The cases of spec 013 AC-8 run on spec
013 AC-8's setup (1280 by 720, the ten lines of "Filling", the list at its end).
The scripts are those of `tests/test_spec_013_ac07_ac08_feed_scroll.py` with the
chat list's selectors.

AC-12 is keyboard only after its setup (the snapshot, the click that opens the
panel, the lines the mock sends). "Not clipped" and "Not covered" are spec 035's
measures (`FOCUS_BAND_SCRIPT`).

The shared setup is in `spec022_harness`.

Refined for spec 043 (the design's room layout): the chat list is the Salon's
stream, which fills the Salon's height (about 510 px at 1280 by 720, 299 px at 360
by 740), so ten lines no longer make it scroll. "Filling" sends 40 lines (`seq` 6
to 45), the later cases take `seq` 46 to 50, and the full list `seq` 51 to 205, so
it still holds 200 lines, `seq` 6 to 205. In spec 013 AC-8's "Smaller window",
the resize to 360 by 740 turns the column layout into the sheet layout, which
closes the Salon: the test shows the Discussion tab again and checks that the list
is at its end within 300 ms of being shown, as spec 013 AC-8's test does.
"""

from __future__ import annotations

from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerView
from room_panels import show_tab
from spec022_harness import (
    CHAT_LIST_SELECTOR,
    chat_frame,
    chat_seqs,
    expect_seq,
    open_chat_room,
    open_panel,
    three_players,
    wait_for_frame_count,
)
from spec024_harness import (
    grid_from_text,
    load_fr,
    open_context_page,
    player_view,
)
from spec025_harness import MockRoomSocket
from spec035_harness import (
    FOCUS_BAND_SCRIPT,
    FOCUS_OUTLINE_SCRIPT,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
)

CHAT_WINDOWS = [(1280, 720), (360, 740)]
# The `seq` of each case's line (see the module docstring for the count).
FILL_FIRST_SEQ = 6
FILL_LAST_SEQ = 45
AT_END_SEQ = 46
SCROLLED_UP_SEQ = 47
OWN_LINE_SEQ = 48
BACK_AT_END_SEQ = 49
ONE_PX_SEQ = 50
FULL_FIRST_SEQ = 51
FULL_LAST_SEQ = 205
KEYBOARD_SIZES = [(360, 740), (568, 320), (1280, 720)]
TOLERANCE_PX = 1.0
FOLLOW_MS = 300
END_WATCH_LIMIT_MS = 1000
SETTLED_READ_MS = 100
SETTLED_LIMIT_MS = 2000
WAIT_TIMEOUT_MS = 5000
NO_CUT = {"top": 0, "right": 0, "bottom": 0, "left": 0}


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- The chat list's measures ----

LIST_SCROLL_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  return {
    scrollTop: list.scrollTop,
    scrollHeight: list.scrollHeight,
    clientHeight: list.clientHeight,
    overflowY: getComputedStyle(list).overflowY,
  };
}
"""

# Moves the list with a script: to the middle of its range, to its scrollHeight
# (the browser stops it at the end) or 1 px before its end.
SCROLL_LIST_SCRIPT = """
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

# The scroll probe: read the list's scrollTop at every animation frame, and keep
# the value read just before the probe started. A frame without the list reads
# null.
START_PROBE_SCRIPT = """
selector => {
  const probe = {
    start: document.querySelector(selector).scrollTop,
    values: [],
    running: true,
  };
  window.chatScrollProbe = probe;
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
  const probe = window.chatScrollProbe;
  probe.running = false;
  return {start: probe.start, values: probe.values};
}
"""

# The end watch of spec 013's tests, on the chat list and its `chat-message`
# items: note the first frame where the trigger holds, then the first frame from
# there where the list is at its end (for a `seq` trigger, with that seq's line
# last). It gives up `limitMs` after the trigger.
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
  window.chatEndWatch = watch;
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
    const items = list.querySelectorAll('[data-testid="chat-message"]');
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

# "Items in view": the data-seq and box top of each chat-message whose box
# overlaps the list's box vertically by more than 1 px.
ITEMS_IN_VIEW_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  const listBox = list.getBoundingClientRect();
  const found = [];
  for (const item of list.querySelectorAll('[data-testid="chat-message"]')) {
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
  for (const item of list.querySelectorAll('[data-testid="chat-message"]')) {
    tops[item.getAttribute('data-seq')] = item.getBoundingClientRect().top;
  }
  return tops;
}
"""


class ListScroll(NamedTuple):
    """The measures of the chat list that the scroll rules use."""

    scroll_top: float
    scroll_height: int
    client_height: int
    overflow_y: str

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
        """It scrolls (spec 035's term): overflow-y auto or scroll, and taller."""
        taller = self.scroll_height > self.client_height
        return taller and self.overflow_y in ("auto", "scroll")


class ChatScene(NamedTuple):
    """A page of "Chat scroll states" and its mocked socket."""

    page: Page
    mock: MockRoomSocket


def read_list(page: Page) -> ListScroll:
    """Read the chat list's measures now."""
    raw = page.evaluate(LIST_SCROLL_SCRIPT, CHAT_LIST_SELECTOR)
    return ListScroll(
        scroll_top=raw["scrollTop"],
        scroll_height=raw["scrollHeight"],
        client_height=raw["clientHeight"],
        overflow_y=raw["overflowY"],
    )


def send_lines(scene: ChatScene, first_seq: int, last_seq: int) -> None:
    """Send the line events one right after another, then wait for the last."""
    for seq in range(first_seq, last_seq + 1):
        scene.mock.send(chat_frame(seq, "p2", f"Ligne {seq}"))
    expect_seq(scene.page, last_seq)


def wait_until_settled(page: Page) -> ListScroll:
    """Read scrollTop every 100 ms until two reads agree; fail after 2 s."""
    previous = read_list(page)
    for _ in range(SETTLED_LIMIT_MS // SETTLED_READ_MS):
        page.wait_for_timeout(SETTLED_READ_MS)
        current = read_list(page)
        if current.scroll_top == previous.scroll_top:
            return current
        previous = current
    pytest.fail(f"the chat list is not settled after 2 s: {previous}")


def scroll_list_and_settle(page: Page, place: str) -> ListScroll:
    """Move the list with a script, then wait until it is settled."""
    page.evaluate(SCROLL_LIST_SCRIPT, [CHAT_LIST_SELECTOR, place])
    return wait_until_settled(page)


def let_the_case_end(page: Page) -> None:
    """Give the page the 300 ms of a case, then wait until the list is settled."""
    page.wait_for_timeout(FOLLOW_MS)
    wait_until_settled(page)


def start_probe(page: Page) -> None:
    page.evaluate(START_PROBE_SCRIPT, CHAT_LIST_SELECTOR)


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
        f"{case}: the chat list moved away from scrollTop {start} in {len(moved)}"
        f" of {len(values)} frames, for example to {moved[:5]}"
    )


def start_end_watch(page: Page, trigger: str, value: str) -> None:
    """Start the end watch; `trigger` is `seq`, `width` or `font`."""
    page.evaluate(
        END_WATCH_SCRIPT,
        {
            "selector": CHAT_LIST_SELECTOR,
            "trigger": trigger,
            "value": value,
            "limitMs": END_WATCH_LIMIT_MS,
            "atEndPx": TOLERANCE_PX,
        },
    )


def assert_at_end_within_300_ms(page: Page, case: str) -> None:
    """Fail unless the end watch saw the list at its end within 300 ms."""
    page.wait_for_function("() => window.chatEndWatch.done", timeout=WAIT_TIMEOUT_MS)
    watch = page.evaluate("() => window.chatEndWatch")
    trigger = f"{watch['trigger']} {watch['value']}"
    assert watch["atEndAt"] is not None, (
        f"{case}: the chat list is not at its end {END_WATCH_LIMIT_MS} ms after"
        f" {trigger}: {watch['last']}"
    )
    elapsed_ms = watch["atEndAt"] - watch["triggerAt"]
    assert elapsed_ms <= FOLLOW_MS, (
        f"{case}: the chat list reached its end {elapsed_ms:.0f} ms after"
        f" {trigger}, more than {FOLLOW_MS} ms"
    )


def assert_case_starts(
    holds: bool, case: str, expected: str, scroll: ListScroll
) -> None:
    """Fail when the chat list is not in the state that the case starts from."""
    assert holds, f"{case}: the case starts when {expected}, but not here: {scroll}"


def items_in_view(page: Page) -> dict[int, float]:
    """The box top of each chat-message in view, by `data-seq`."""
    found = page.evaluate(ITEMS_IN_VIEW_SCRIPT, CHAT_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found:
        tops[int(seq)] = float(top)
    return tops


def item_tops(page: Page) -> dict[int, float]:
    """The box top of every chat-message, by `data-seq`."""
    found = page.evaluate(ITEM_TOPS_SCRIPT, CHAT_LIST_SELECTOR)
    tops: dict[int, float] = {}
    for seq, top in found.items():
        tops[int(seq)] = float(top)
    return tops


def items_out_of_place(
    noted: dict[int, float], tops_now: dict[int, float]
) -> list[tuple[int, float, float | None]]:
    """The noted items that are gone, or whose top moved by more than 1 px."""
    out_of_place: list[tuple[int, float, float | None]] = []
    for seq, noted_top in noted.items():
        top_now = tops_now.get(seq)
        if top_now is None or abs(top_now - noted_top) > TOLERANCE_PX:
            out_of_place.append((seq, noted_top, top_now))
    return out_of_place


def last_line_seq(page: Page) -> str | None:
    """The `data-seq` of the last `chat-message`."""
    return page.get_by_test_id("chat-message").last.get_attribute("data-seq")


def scene_players() -> list[PlayerView]:
    """Spec 013 AC-5's players: `p1` (`you`, Ana, host) and `p2` (Bob)."""
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)]


def open_scene(page: Page, live_server: str, grid: Grid) -> ChatScene:
    """The page of "Chat scroll states": the snapshot of seq 5, the panel open."""
    mock = open_chat_room(page, live_server, grid, seq=5, players=scene_players())
    open_panel(page)
    return ChatScene(page=page, mock=mock)


# ---- AC-11: spec 013 AC-7's cases on the chat list ----


@pytest.mark.parametrize(("width", "height"), CHAT_WINDOWS, ids=size_ids(CHAT_WINDOWS))
def test_ac11_browser_a_new_line_follows_the_end_and_never_moves_the_reader(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        scene = open_scene(page, live_server, fx01_grid)
        chat_input = page.get_by_test_id("chat-input")

        # Filling.
        start_end_watch(page, "seq", str(FILL_LAST_SEQ))
        send_lines(scene, FILL_FIRST_SEQ, FILL_LAST_SEQ)
        filled = read_list(page)
        assert filled.scrolls, f"Filling: the chat list does not scroll: {filled}"
        assert_at_end_within_300_ms(page, "Filling")
        let_the_case_end(page)

        # At the end.
        start = read_list(page)
        assert_case_starts(start.at_end, "At the end", "the list is at its end", start)
        start_end_watch(page, "seq", str(AT_END_SEQ))
        send_lines(scene, AT_END_SEQ, AT_END_SEQ)
        assert_at_end_within_300_ms(page, "At the end")
        let_the_case_end(page)

        # Scrolled up.
        start = scroll_list_and_settle(page, "middle")
        assert_case_starts(
            not start.at_end, "Scrolled up", "the list is not at its end", start
        )
        start_probe(page)
        send_lines(scene, SCROLLED_UP_SEQ, SCROLLED_UP_SEQ)
        page.wait_for_timeout(FOLLOW_MS)
        assert_probe_stayed_put(page, "Scrolled up")
        assert last_line_seq(page) == str(SCROLLED_UP_SEQ)
        let_the_case_end(page)

        # My own line.
        start = read_list(page)
        assert_case_starts(
            not start.at_end, "My own line", "the list is not at its end", start
        )
        chat_input.fill("moi")
        start_probe(page)
        chat_input.press("Enter")
        wait_for_frame_count(page, scene.mock, "chat", 1)
        scene.mock.send(chat_frame(OWN_LINE_SEQ, "p1", "moi"))
        expect_seq(page, OWN_LINE_SEQ)
        page.wait_for_timeout(FOLLOW_MS)
        assert_probe_stayed_put(page, "My own line")
        assert last_line_seq(page) == str(OWN_LINE_SEQ)
        let_the_case_end(page)

        # Back at the end.
        start = scroll_list_and_settle(page, "end")
        assert_case_starts(
            start.at_end, "Back at the end", "the list is at its end", start
        )
        start_end_watch(page, "seq", str(BACK_AT_END_SEQ))
        send_lines(scene, BACK_AT_END_SEQ, BACK_AT_END_SEQ)
        assert_at_end_within_300_ms(page, "Back at the end")
        let_the_case_end(page)

        # Within 1 px of the end.
        start = scroll_list_and_settle(page, "one_px_before_end")
        assert_case_starts(
            start.at_end, "Within 1 px", "the distance to the end is at most 1", start
        )
        start_end_watch(page, "seq", str(ONE_PX_SEQ))
        send_lines(scene, ONE_PX_SEQ, ONE_PX_SEQ)
        assert_at_end_within_300_ms(page, "Within 1 px of the end")
        let_the_case_end(page)

        # Full list: 200 lines.
        start = read_list(page)
        assert_case_starts(start.at_end, "Full list", "the list is at its end", start)
        start_end_watch(page, "seq", str(FULL_LAST_SEQ))
        send_lines(scene, FULL_FIRST_SEQ, FULL_LAST_SEQ)
        assert chat_seqs(page) == list(range(6, 206))
        assert_at_end_within_300_ms(page, "Full list")
        middle = scroll_list_and_settle(page, "middle")
        assert_case_starts(
            not middle.at_end, "Full list", "the list is not at its end", middle
        )
        noted = items_in_view(page)
        assert noted != {}, f"Full list: no chat-message is in view: {middle}"
        send_lines(scene, 206, 206)
        page.wait_for_timeout(FOLLOW_MS)
        seqs = chat_seqs(page)
        moved = items_out_of_place(noted, item_tops(page))
    finally:
        close()

    assert (seqs[0], seqs[-1]) == (7, 206)
    assert moved == []


# ---- AC-11: spec 013 AC-8's cases on the chat list ----


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


def test_ac11_browser_a_chat_list_at_its_end_stays_there_when_the_layout_changes(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, False)
    try:
        scene = open_scene(page, live_server, fx01_grid)
        send_lines(scene, FILL_FIRST_SEQ, FILL_LAST_SEQ)
        let_the_case_end(page)
        setup = read_list(page)
        assert_case_starts(setup.at_end, "Setup", "the list is at its end", setup)

        # Smaller window: the sheet layout closes the Salon, shown again here.
        resize_window(page, 360, 740)
        show_tab(page, "discussion")
        start_end_watch(page, "width", "360")
        resized = read_list(page)
        assert resized.scrolls, f"Smaller window: no scroll: {resized}"
        assert_at_end_within_300_ms(page, "Smaller window")
        let_the_case_end(page)

        # Larger root font.
        start = read_list(page)
        assert_case_starts(start.at_end, "Larger root font", "at its end", start)
        start_end_watch(page, "font", "20px")
        set_root_font(page, 20)
        assert_at_end_within_300_ms(page, "Larger root font")
        let_the_case_end(page)

        # Larger window.
        start = read_list(page)
        assert_case_starts(start.at_end, "Larger window", "at its end", start)
        start_end_watch(page, "width", "1280")
        resize_window(page, 1280, 720)
        assert_at_end_within_300_ms(page, "Larger window")
    finally:
        close()


# ---- AC-12: the chat list from the keyboard ----

# Watches the list after a key: the first frame where its scrollTop is smaller
# than before the watch started, in ms since then.
START_SCROLL_WATCH_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  const watch = {
    startedAt: performance.now(),
    start: list.scrollTop,
    smallerAt: null,
    done: false,
  };
  window.chatKeyWatch = watch;
  const look = () => {
    if (watch.done) {
      return;
    }
    if (watch.smallerAt === null && list.scrollTop < watch.start) {
      watch.smallerAt = performance.now() - watch.startedAt;
    }
    requestAnimationFrame(look);
  };
  requestAnimationFrame(look);
}
"""
STOP_SCROLL_WATCH_SCRIPT = """
() => {
  const watch = window.chatKeyWatch;
  watch.done = true;
  return {start: watch.start, smallerAt: watch.smallerAt};
}
"""
FOCUS_OUTSIDE_PANEL_SCRIPT = """
() => {
  const panel = document.querySelector('[data-testid="chat-panel"]');
  const focused = document.activeElement;
  return {
    onBody: focused === null || focused === document.body,
    insidePanel: panel !== null && focused !== null && panel.contains(focused),
    testId: focused === null ? null : focused.getAttribute('data-testid'),
  };
}
"""
LONG_LIST_LAST_SEQ = 45  # 40 lines, seq 6 to 45
KEY_WATCH_MS = 400


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=size_ids(KEYBOARD_SIZES)
)
def test_ac12_browser_a_long_chat_list_is_a_tab_stop_that_the_arrow_keys_scroll(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    fr = load_fr()
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        players = three_players(host="p2")
        mock = open_chat_room(page, live_server, fx01_grid, seq=5, players=players)
        open_panel(page)
        scene = ChatScene(page=page, mock=mock)
        send_lines(scene, 6, LONG_LIST_LAST_SEQ)
        wait_until_settled(page)
        chat_list = page.get_by_test_id("chat-list")
        measured = read_list(page)
        assert measured.scrolls, f"the chat list does not scroll: {measured}"
        expect(page.get_by_test_id("chat-moderation")).to_have_count(0)
        expect(chat_list).to_have_attribute("role", "list")
        expect(chat_list).to_have_attribute("tabindex", "0")
        named = page.get_by_role("list", name=fr["chat.heading"], exact=True)
        expect(named).to_have_count(1)
        expect(named).to_have_attribute("data-testid", "chat-list")
        expect(page.get_by_test_id("chat-input")).to_be_focused()

        # Keyboard only from here.
        page.keyboard.press("Shift+Tab")
        expect(chat_list).to_be_focused()
        page.wait_for_timeout(FOLLOW_MS)
        outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
        band = page.evaluate(FOCUS_BAND_SCRIPT)

        page.evaluate(START_SCROLL_WATCH_SCRIPT, CHAT_LIST_SELECTOR)
        page.keyboard.press("ArrowUp")
        page.wait_for_timeout(KEY_WATCH_MS)
        key_watch = page.evaluate(STOP_SCROLL_WATCH_SCRIPT)
        expect(chat_list).to_be_focused()
        before = wait_until_settled(page)

        mock.send(chat_frame(LONG_LIST_LAST_SEQ + 1, "p2", "Une de plus"))
        expect_seq(page, LONG_LIST_LAST_SEQ + 1)
        page.wait_for_timeout(FOLLOW_MS)
        after = read_list(page)
        expect(chat_list).to_be_focused()

        page.keyboard.press("Tab")
        expect(page.get_by_test_id("chat-input")).to_be_focused()
    finally:
        close()

    assert outline["style"] not in ("none", "auto"), outline
    assert outline["width"] >= MIN_OUTLINE_PX, outline
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline
    assert {side: round(px) for side, px in band["cut"].items()} == NO_CUT, band
    assert band["coveredBy"] == {}, band
    assert key_watch["smallerAt"] is not None, key_watch
    assert key_watch["smallerAt"] <= FOLLOW_MS, key_watch
    assert abs(after.scroll_top - before.scroll_top) <= TOLERANCE_PX, (before, after)


@pytest.mark.parametrize(
    ("width", "height"), KEYBOARD_SIZES, ids=size_ids(KEYBOARD_SIZES)
)
def test_ac12_browser_a_short_chat_list_is_not_a_tab_stop(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        players = three_players(host="p2")
        mock = open_chat_room(page, live_server, fx01_grid, seq=5, players=players)
        open_panel(page)
        send_lines(ChatScene(page=page, mock=mock), 6, 7)
        expect(page.get_by_test_id("chat-message")).to_have_count(2)
        page.wait_for_timeout(FOLLOW_MS)
        measured = read_list(page)
        tabindex = page.get_by_test_id("chat-list").get_attribute("tabindex")
        expect(page.get_by_test_id("chat-input")).to_be_focused()

        # Keyboard only from here.
        page.keyboard.press("Shift+Tab")
        focus = page.evaluate(FOCUS_OUTSIDE_PANEL_SCRIPT)
    finally:
        close()

    assert not measured.scrolls, measured
    assert tabindex is None
    assert focus["onBody"] is False, focus
    assert focus["insidePanel"] is False, focus
