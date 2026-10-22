"""Tests of spec 035: a list that scrolls is a Tab stop (AC-12).

The setup the test files of spec 035 share is in `tests/spec035_harness.py`.

Refined by spec 043 (the design's room layout): the feed list is the Salon's
stream list (`chat-list`, inside `activity-feed`, named « Discussion »), and the
players' list never scrolls on its own. In each case the Discussion tab is shown
first (`show_tab`, setup), and the Tab walk starts with `focus()` on
`salon-tab-discussion` and stops at `chat-input`. The roster's cases (its Tab
stop, its `tabindex="-1"`, its `ArrowRight`, its resize, the host-role changes and
"Focus kept") are gone.

Choices where the spec leaves room:

- AC-12, setups: where the criterion says the stream list does not scroll, the
  test also checks that from the list's measures, as it does where it says the
  list scrolls, so that a changed layout is reported as such.
- AC-12, "Name": a tab panel that is not selected has the `hidden` attribute
  (spec 043), so it is out of the accessibility tree. Each list's name is read
  with its own tab shown: the players' list with the Joueurs tab, the stream list
  with the Discussion tab.
- AC-12, "a Tab walk from `salon-tab-players`": `focus()` on that tab, then `Tab`
  until the focus leaves the Salon (or reaches `document.body`), at most 60
  presses. It also stops when a press leaves the focus on the element it was
  on: past the page's last Tab stop, Firefox under automation keeps the focus
  there.
- AC-12, visible focus: the "Not clipped" and "Not covered" measures run on the
  stream list; they repeat AC-2's check.
- AC-12, arrow keys: after a key scrolled the list, the test lets the scroll stand
  still before the next key, since a smooth scroll may still be moving.
- AC-12, new lines: after each event, the test also waits for the stream to hold
  the new line before it reads the list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, PlayerState, PlayerView, WordTarget
from room_panels import Tab, show_tab
from spec035_harness import (
    EPSILON,
    FEED_SIZES,
    FOCUS_BAND_SCRIPT,
    FOCUS_OUTLINE_SCRIPT,
    MAX_TABS,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    WAIT_TIMEOUT_MS,
    MockRoomSocket,
    build_fx01_grid,
    build_reference_catalogue,
    fill_feed_and_check_it_scrolls,
    load_fr,
    open_k2,
    open_room,
    page_factory,
    player_view,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    yield from page_factory(browser)


# ---- AC-12: a list that scrolls with no control inside is a Tab stop -------------

STREAM_LIST_SELECTOR = '[data-testid="activity-feed"] [data-testid="chat-list"]'
ROSTER_LIST_SELECTOR = '[data-testid="roster"] ul'
LIST_SELECTORS = {"stream": STREAM_LIST_SELECTOR, "players": ROSTER_LIST_SELECTOR}
LIST_FOLLOW_MS = 300  # the attribute follows every change within 300 ms
POLL_MS = 25
NO_CUT = {"top": 0, "right": 0, "bottom": 0, "left": 0}
FIRST_LIVE_SEQ = 11
MAX_LIVE_EVENTS = 20

# One list of "Scrolling lists": whether it scrolls (the spec's terms), its
# `tabindex` attribute, whether it has the focus, where it is scrolled to, and the
# measures behind "scrolls".
LIST_STATE_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  const style = getComputedStyle(list);
  const canScroll = value => value === 'auto' || value === 'scroll';
  const scrollsSideways = canScroll(style.overflowX)
    && list.scrollWidth > list.clientWidth;
  const scrollsDown = canScroll(style.overflowY)
    && list.scrollHeight > list.clientHeight;
  return {
    scrolls: scrollsSideways || scrollsDown,
    tabindex: list.getAttribute('tabindex'),
    focused: document.activeElement === list,
    scrollTop: list.scrollTop,
    measures: {
      overflowX: style.overflowX,
      overflowY: style.overflowY,
      scrollWidth: list.scrollWidth,
      clientWidth: list.clientWidth,
      scrollHeight: list.scrollHeight,
      clientHeight: list.clientHeight,
    },
  };
}
"""

# What has the focus: its test id, which list of AC-12 it is (or null), the player
# of the roster row that holds it (or null), and whether it is inside the Salon.
FOCUS_STEP_SCRIPT = """
([streamSelector, rosterSelector]) => {
  const element = document.activeElement;
  if (element === null || element === document.body) {
    return {testId: null, list: null, playerId: null, inSalon: false};
  }
  let list = null;
  if (element === document.querySelector(streamSelector)) {
    list = 'stream';
  } else if (element === document.querySelector(rosterSelector)) {
    list = 'players';
  }
  const row = element.closest('[data-testid="roster-player"]');
  const salon = document.querySelector('[data-testid="salon"]');
  return {
    testId: element.getAttribute('data-testid'),
    list: list,
    playerId: row === null ? null : row.getAttribute('data-player-id'),
    inSalon: salon !== null && salon.contains(element),
  };
}
"""

# Resolves once the list's scroll position has stood still for three animation
# frames: an arrow key can start a smooth scroll that is still moving.
SCROLL_SETTLED_SCRIPT = """
selector => new Promise(resolve => {
  const list = document.querySelector(selector);
  let previous = '';
  let stillFrames = 0;
  let frames = 0;
  const look = () => {
    const current = list.scrollTop + ',' + list.scrollLeft;
    stillFrames = current === previous ? stillFrames + 1 : 0;
    previous = current;
    frames += 1;
    if (stillFrames >= 3 || frames >= 120) {
      resolve(true);
    } else {
      requestAnimationFrame(look);
    }
  };
  requestAnimationFrame(look);
})
"""

IS_THE_ELEMENT_SCRIPT = (
    "(element, selector) => element === document.querySelector(selector)"
)


class ListState(NamedTuple):
    """One list of AC-12 as the page shows it now."""

    scrolls: bool
    tabindex: str | None  # the attribute
    focused: bool
    scroll_top: float
    measures: dict[str, Any]

    @property
    def distance_to_end(self) -> float:
        """`scrollHeight - clientHeight - scrollTop`, as spec 013 defines it."""
        scroll_height = self.measures["scrollHeight"]
        client_height = self.measures["clientHeight"]
        return scroll_height - client_height - self.scroll_top


class FocusStep(NamedTuple):
    """The element that had the focus after one press of a Tab walk."""

    test_id: str | None
    list_name: str | None
    player_id: str | None
    in_salon: bool


def read_list_state(page: Page, list_name: str) -> ListState:
    raw = page.evaluate(LIST_STATE_SCRIPT, LIST_SELECTORS[list_name])
    return ListState(
        scrolls=raw["scrolls"],
        tabindex=raw["tabindex"],
        focused=raw["focused"],
        scroll_top=raw["scrollTop"],
        measures=raw["measures"],
    )


def read_focus_step(page: Page) -> FocusStep:
    raw = page.evaluate(FOCUS_STEP_SCRIPT, [STREAM_LIST_SELECTOR, ROSTER_LIST_SELECTOR])
    return FocusStep(
        test_id=raw["testId"],
        list_name=raw["list"],
        player_id=raw["playerId"],
        in_salon=raw["inSalon"],
    )


def assert_scrolls(state: ListState) -> None:
    """Fail when the stream list, which the setup must make scroll, does not."""
    assert state.scrolls, (
        f"the stream list does not scroll ({state.measures}): the setup no"
        " longer shows what it should"
    )


def assert_does_not_scroll(state: ListState) -> None:
    """Fail when the stream list, which the setup must leave still, scrolls."""
    assert not state.scrolls, (
        f"the stream list scrolls ({state.measures}): the setup no longer"
        " shows what it should"
    )


def has_no_tabindex(state: ListState) -> bool:
    return state.tabindex is None


def tabindex_follows_scroll(state: ListState) -> bool:
    """`tabindex="0"` while the list scrolls, no attribute while it does not."""
    if state.scrolls:
        return state.tabindex == "0"
    return state.tabindex is None


def wait_for_list(
    page: Page, list_name: str, condition: Callable[[ListState], bool]
) -> ListState:
    """Fail unless the list meets `condition` within 300 ms; return its state."""
    waited_ms = 0
    state = read_list_state(page, list_name)
    while not condition(state):
        if waited_ms >= LIST_FOLLOW_MS:
            pytest.fail(
                f"the {list_name} list does not meet {condition.__name__} within"
                f" {LIST_FOLLOW_MS} ms: {state}"
            )
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
        state = read_list_state(page, list_name)
    return state


def focus_on(page: Page, test_id: str) -> None:
    """Put the focus on an element with `focus()` (setup of a Tab walk)."""
    element = page.get_by_test_id(test_id)
    element.evaluate("element => element.focus()")
    expect(element).to_be_focused()


def tab_walk_to_the_chat_input(page: Page) -> list[FocusStep]:
    """The Tab walk of AC-12: from `salon-tab-discussion`, Tab until `chat-input`.

    Returns:
        What had the focus after each press, `chat-input` last.
    """
    focus_on(page, "salon-tab-discussion")
    steps: list[FocusStep] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        step = read_focus_step(page)
        steps.append(step)
        if step.test_id == "chat-input":
            return steps
    pytest.fail(f"the Tab walk did not reach chat-input in {MAX_TABS} presses: {steps}")


def tab_walk_to_the_stream_list(page: Page) -> None:
    """The Tab walk of AC-12, stopped as soon as the stream list has the focus."""
    focus_on(page, "salon-tab-discussion")
    steps: list[FocusStep] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        step = read_focus_step(page)
        steps.append(step)
        if step.list_name == "stream":
            return
        if step.test_id == "chat-input":
            break
    pytest.fail(f"the Tab walk never focused the stream list: {steps}")


def tab_walk_through_the_players_tab(page: Page) -> list[FocusStep]:
    """From `salon-tab-players`, Tab until the focus leaves the Salon.

    The walk also ends when a press leaves the focus where it was. The Salon's
    last Tab stop (`copy-link`) is the page's last one, and past it Firefox under
    automation keeps the focus there, where Chromium and WebKit move it out of
    the document (spec 035, "Nothing focusable after the grid").

    Returns:
        What had the focus after each press inside the Salon.
    """
    focus_on(page, "salon-tab-players")
    steps: list[FocusStep] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        step = read_focus_step(page)
        if not step.in_salon:
            return steps
        if steps != [] and step == steps[-1]:
            return steps
        steps.append(step)
    pytest.fail(f"the Tab walk did not leave the Salon in {MAX_TABS} presses")


def times_focused(steps: list[FocusStep], list_name: str) -> int:
    count = 0
    for step in steps:
        if step.list_name == list_name:
            count += 1
    return count


def s1_players() -> list[PlayerView]:
    """S1: `p1` (`you`, not host), `p2` (host), `p3` (idle), `p4` (disconnected)."""
    return [
        player_view("p1", "Ana", 0),
        player_view("p2", "Bob", 1, is_host=True),
        player_view("p3", "Cleo", 2, state=PlayerState.IDLE),
        player_view("p4", "Dan", 3, state=PlayerState.DISCONNECTED),
    ]


def open_s1(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """State S1 with the Discussion tab shown: a guest's room, an empty stream."""
    mock = open_room(page, live_server, grid, players=s1_players(), seq=10)
    show_tab(page, "discussion")
    expect(page.get_by_test_id("feed-item")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)
    return mock


def open_k2_on_discussion(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """State K2 with the Discussion tab shown."""
    mock = open_k2(page, live_server, grid)
    show_tab(page, "discussion")
    return mock


def open_s2(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """State S2 with the Discussion tab shown: K2, then lines `seq` 14 to 53."""
    mock = open_k2_on_discussion(page, live_server, grid)
    fill_feed_and_check_it_scrolls(page, mock)
    return mock


SCROLL_STATES: dict[str, Callable[[Page, str, Grid], MockRoomSocket]] = {
    "s1": open_s1,
    "s2": open_s2,
    "k2": open_k2_on_discussion,
}


def check_result_frame(seq: int) -> str:
    """A `check_result` like K2's: by `p2` on the word `0,2,0`, empty lists."""
    result = CheckResult(
        seq=seq,
        player_id="p2",
        target=WordTarget(row=0, column=2, clue_index=0),
        correct=(),
        wrong=(),
    )
    return result.model_dump_json()


def resize_to(page: Page, width: int, height: int) -> None:
    """Resize the window, then wait until the page reads the new width."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_function(
        "width => window.innerWidth === width", arg=width, timeout=WAIT_TIMEOUT_MS
    )


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


S2_SIZES = FEED_SIZES  # 360 by 740, 568 by 320 and 1280 by 720
S1_STILL_SIZES = [(568, 320), (320, 568), (1280, 720)]
SMALL_WINDOWS = [(568, 320), (320, 568)]
NAME_CASES = [("s1", 568, 320), ("s1", 1280, 720), ("k2", 568, 320), ("k2", 1280, 720)]
# (list, tab, heading id, fr.json key, the name it gives).
LIST_NAMES: list[tuple[str, Tab, str, str, str]] = [
    ("players", "players", "roster-heading", "roster.heading", "Joueurs"),
    ("stream", "discussion", "chat-heading", "chat.heading", "Discussion"),
]
PANEL_OF_TAB: dict[Tab, str] = {"players": "roster", "discussion": "chat-panel"}
# The arrow keys of the stream list, in order, and the sign of `scrollTop`'s change.
STREAM_ARROWS = [("ArrowUp", -1), ("ArrowDown", 1)]


@pytest.mark.parametrize(("width", "height"), S2_SIZES, ids=size_ids(S2_SIZES))
def test_ac12_the_scrolling_stream_list_is_a_tab_stop(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_s2(page, live_server, fx01_grid)
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, "stream")
    assert_scrolls(shown)

    steps = tab_walk_to_the_chat_input(page)

    assert shown.tabindex == "0", shown
    assert times_focused(steps, "stream") == 1, steps


@pytest.mark.parametrize(
    ("width", "height"), S1_STILL_SIZES, ids=size_ids(S1_STILL_SIZES)
)
def test_ac12_the_empty_stream_list_is_not_a_tab_stop(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_s1(page, live_server, fx01_grid)
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, "stream")
    assert_does_not_scroll(shown)

    steps = tab_walk_to_the_chat_input(page)

    assert shown.tabindex is None, shown
    assert times_focused(steps, "stream") == 0, steps


@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac12_the_players_list_never_scrolls_and_its_remove_buttons_are_tab_stops(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)
    show_tab(page, "players")
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, "players")
    measures = shown.measures

    assert measures["scrollHeight"] <= measures["clientHeight"] + EPSILON, shown
    assert measures["scrollWidth"] <= measures["clientWidth"] + EPSILON, shown
    assert shown.tabindex is None, shown
    steps = tab_walk_through_the_players_tab(page)
    button_owners: list[str] = []
    for step in steps:
        if step.test_id == "remove-player" and step.player_id is not None:
            button_owners.append(step.player_id)
    assert sorted(button_owners) == ["p2", "p3", "p4", "p5"], steps
    assert times_focused(steps, "players") == 0, steps


@pytest.mark.parametrize(
    ("state", "width", "height"),
    NAME_CASES,
    ids=[f"{state}-{width}x{height}" for state, width, height in NAME_CASES],
)
def test_ac12_each_list_is_named_by_the_hidden_heading_of_its_tab_panel(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    SCROLL_STATES[state](page, live_server, fx01_grid)
    fr_json = load_fr()

    for list_name, tab, heading_id, key, name in LIST_NAMES:
        show_tab(page, tab)
        assert fr_json[key] == name
        by_role = page.get_by_role("list", name=name, exact=True)
        expect(by_role, name).to_have_count(1)
        selector = LIST_SELECTORS[list_name]
        assert by_role.evaluate(IS_THE_ELEMENT_SCRIPT, selector) is True, name
        named_list = page.locator(selector)
        expect(named_list).to_have_attribute("role", "list")
        expect(named_list).to_have_attribute("aria-labelledby", heading_id)
        heading = page.get_by_test_id(PANEL_OF_TAB[tab]).locator(f"h2#{heading_id}")
        expect(heading).to_have_count(1)
        expect(heading).to_have_text(fr_json[key])


def press_and_expect_a_scroll(page: Page, key: str, sign: int) -> None:
    """Press an arrow key; fail unless the focused stream list scrolls in 300 ms.

    Args:
        page: The room page, with the focus on the stream list.
        key: The arrow key to press.
        sign: 1 when `scrollTop` must grow, -1 when it must shrink.
    """
    before = read_list_state(page, "stream")
    page.keyboard.press(key)
    waited_ms = 0
    while True:
        now = read_list_state(page, "stream")
        assert now.focused, (key, now)
        change = now.scroll_top - before.scroll_top
        if change * sign > 0:
            break
        if waited_ms >= LIST_FOLLOW_MS:
            pytest.fail(
                f"{key} did not scroll the stream list within"
                f" {LIST_FOLLOW_MS} ms: {before} then {now}"
            )
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
    page.evaluate(SCROLL_SETTLED_SCRIPT, STREAM_LIST_SELECTOR)
    assert read_list_state(page, "stream").focused, key


@pytest.mark.parametrize(("width", "height"), S2_SIZES, ids=size_ids(S2_SIZES))
def test_ac12_the_arrow_keys_scroll_the_focused_stream_list(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_s2(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "stream"))
    tab_walk_to_the_stream_list(page)

    for key, sign in STREAM_ARROWS:
        press_and_expect_a_scroll(page, key, sign)


@pytest.mark.parametrize(("width", "height"), S2_SIZES, ids=size_ids(S2_SIZES))
def test_ac12_the_focused_stream_list_shows_its_whole_focus_outline(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_s2(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "stream"))
    tab_walk_to_the_stream_list(page)
    page.wait_for_timeout(LIST_FOLLOW_MS)

    outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
    band = page.evaluate(FOCUS_BAND_SCRIPT)

    assert outline["style"] not in ("none", "auto"), outline
    assert outline["width"] >= MIN_OUTLINE_PX, outline
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline
    assert {side: round(px) for side, px in band["cut"].items()} == NO_CUT, band
    assert band["coveredBy"] == {}, band


def test_ac12_the_stream_list_tab_stop_follows_new_lines_and_a_resize(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(568, 320)
    mock = open_s1(page, live_server, fx01_grid)
    wait_for_list(page, "stream", has_no_tabindex)

    scrolls = False
    line_count = 0
    while not scrolls and line_count < MAX_LIVE_EVENTS:
        seq = FIRST_LIVE_SEQ + line_count
        line_count += 1
        mock.send(check_result_frame(seq))
        expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
        expect(page.get_by_test_id("feed-item")).to_have_count(line_count)
        shown = wait_for_list(page, "stream", tabindex_follows_scroll)
        scrolls = shown.scrolls
    assert scrolls, f"{MAX_LIVE_EVENTS} new lines do not make the stream list scroll"

    resize_to(page, 1280, 720)
    wait_for_list(page, "stream", tabindex_follows_scroll)

    resize_to(page, 568, 320)
    wait_for_list(page, "stream", tabindex_follows_scroll)


STILL_READ_MS = 100
STILL_READ_LIMIT = 20  # 2 s of reads, 100 ms apart
NEW_LINE_SEQ = 54
FEED_ITEMS_AFTER_NEW_LINE = 44


def wait_for_a_still_scroll_top(page: Page) -> ListState:
    """Read the stream list every 100 ms until two reads give one `scrollTop`."""
    previous = read_list_state(page, "stream")
    for _ in range(STILL_READ_LIMIT):
        page.wait_for_timeout(STILL_READ_MS)
        current = read_list_state(page, "stream")
        if current.scroll_top == previous.scroll_top:
            return current
        previous = current
    pytest.fail(f"the stream list kept scrolling for 2 s: {previous}")


@pytest.mark.parametrize(("width", "height"), S2_SIZES, ids=size_ids(S2_SIZES))
def test_ac12_a_new_line_leaves_the_focused_stream_list_where_the_keys_put_it(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    mock = open_s2(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "stream"))
    tab_walk_to_the_stream_list(page)
    page.keyboard.press("ArrowUp")
    before = wait_for_a_still_scroll_top(page)
    assert before.distance_to_end > 1, f"ArrowUp left the list at its end: {before}"

    mock.send(check_result_frame(NEW_LINE_SEQ))
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-seq", str(NEW_LINE_SEQ)
    )
    page.wait_for_timeout(LIST_FOLLOW_MS)
    after = read_list_state(page, "stream")

    expect(page.get_by_test_id("feed-item")).to_have_count(FEED_ITEMS_AFTER_NEW_LINE)
    assert abs(after.scroll_top - before.scroll_top) <= EPSILON, (before, after)
    assert after.focused, after
