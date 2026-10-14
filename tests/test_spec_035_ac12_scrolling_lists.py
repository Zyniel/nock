"""Tests of spec 035: a list that scrolls is a Tab stop (AC-12).

The setup the test files of spec 035 share is in `tests/spec035_harness.py`.

Choices where the spec leaves room:

- AC-12, setups: where the criterion says a list does not scroll, the test also
  checks that from the list's measures, as it does where it says a list scrolls,
  so that a changed layout is reported as such.
- AC-12, "No `fr.json` key is added": not observable as such. The test checks that
  each list's name is the text of its section's `h2`, through `aria-labelledby`.
- AC-12, visible focus: the "Not clipped" and "Not covered" measures run on both
  lists; for the feed list they repeat AC-2's check.
- AC-12, arrow keys: after a key scrolled the list, the test lets the scroll stand
  still before the next key, since a smooth scroll may still be moving.
- AC-12, new feed lines: after each event, the test also waits for the feed to
  hold the new line before it reads the list.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CheckResult, HostChanged, PlayerState, PlayerView, WordTarget
from spec035_harness import (
    EPSILON,
    FEED_LIST_SELECTOR,
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

ROSTER_LIST_SELECTOR = '[data-testid="roster"] ul'
LIST_SELECTORS = {"roster": ROSTER_LIST_SELECTOR, "feed": FEED_LIST_SELECTOR}
LIST_FOLLOW_MS = 300  # the attribute follows every change within 300 ms
POLL_MS = 25
NO_CUT = {"top": 0, "right": 0, "bottom": 0, "left": 0}

# One list of "Scrolling lists": whether it scrolls (the spec's terms), its
# `tabindex` attribute, whether it has the focus, where it is scrolled to, how
# many remove buttons it holds, and the measures behind "scrolls".
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
    tabIndex: list.tabIndex,
    focused: document.activeElement === list,
    scrollTop: list.scrollTop,
    scrollLeft: list.scrollLeft,
    removeButtons: list.querySelectorAll('[data-testid="remove-player"]').length,
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

# What has the focus: its test id, which list of AC-12 it is (or null), and the
# player of the roster row that holds it (or null).
FOCUS_STEP_SCRIPT = """
() => {
  const element = document.activeElement;
  if (element === null) {
    return {testId: null, list: null, playerId: null};
  }
  let list = null;
  if (element === document.querySelector('[data-testid="roster"] ul')) {
    list = 'roster';
  } else if (element === document.querySelector('[data-testid="activity-feed"] ul')) {
    list = 'feed';
  }
  const row = element.closest('[data-testid="roster-player"]');
  return {
    testId: element.getAttribute('data-testid'),
    list: list,
    playerId: row === null ? null : row.getAttribute('data-player-id'),
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
    tab_index: int  # the `tabIndex` property
    focused: bool
    scroll_top: float
    scroll_left: float
    remove_buttons: int
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


def read_list_state(page: Page, list_name: str) -> ListState:
    raw = page.evaluate(LIST_STATE_SCRIPT, LIST_SELECTORS[list_name])
    return ListState(
        scrolls=raw["scrolls"],
        tabindex=raw["tabindex"],
        tab_index=raw["tabIndex"],
        focused=raw["focused"],
        scroll_top=raw["scrollTop"],
        scroll_left=raw["scrollLeft"],
        remove_buttons=raw["removeButtons"],
        measures=raw["measures"],
    )


def read_focus_step(page: Page) -> FocusStep:
    raw = page.evaluate(FOCUS_STEP_SCRIPT)
    return FocusStep(
        test_id=raw["testId"], list_name=raw["list"], player_id=raw["playerId"]
    )


def assert_scrolls(state: ListState, list_name: str) -> None:
    """Fail when a list that the setup must make scroll does not."""
    assert state.scrolls, (
        f"the {list_name} list does not scroll ({state.measures}): the setup no"
        " longer shows what it should"
    )


def assert_does_not_scroll(state: ListState, list_name: str) -> None:
    """Fail when a list that the setup must leave still scrolls."""
    assert not state.scrolls, (
        f"the {list_name} list scrolls ({state.measures}): the setup no longer"
        " shows what it should"
    )


def has_tab_stop(state: ListState) -> bool:
    return state.tabindex == "0"


def has_no_tabindex(state: ListState) -> bool:
    return state.tabindex is None


def has_tabindex_minus_one(state: ListState) -> bool:
    return state.tabindex == "-1"


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


def start_tab_walk(page: Page) -> None:
    """Put the focus on `share-link`, where every Tab walk of AC-12 starts."""
    share_link = page.get_by_test_id("share-link")
    share_link.evaluate("element => element.focus()")
    expect(share_link).to_be_focused()


def tab_walk_to_the_grid(page: Page) -> list[FocusStep]:
    """The Tab walk of the harness: from `share-link`, Tab until the grid.

    Returns:
        What had the focus after each press, the grid last.
    """
    start_tab_walk(page)
    steps: list[FocusStep] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        step = read_focus_step(page)
        steps.append(step)
        if step.test_id == "grid":
            return steps
    pytest.fail(f"the Tab walk did not reach the grid in {MAX_TABS} presses: {steps}")


def tab_walk_to_the_list(page: Page, list_name: str) -> None:
    """The Tab walk of the harness, stopped as soon as the list has the focus."""
    start_tab_walk(page)
    steps: list[FocusStep] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        step = read_focus_step(page)
        steps.append(step)
        if step.list_name == list_name:
            return
        if step.test_id == "grid":
            break
    pytest.fail(f"the Tab walk never focused the {list_name} list: {steps}")


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
    """State S1 of the harness: the room page of a guest, with an empty feed."""
    mock = open_room(page, live_server, grid, players=s1_players(), seq=10)
    expect(page.get_by_test_id("feed-item")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    return mock


def open_s2(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """State S2 of the harness: K2, then 40 more feed lines (`seq` 14 to 53)."""
    mock = open_k2(page, live_server, grid)
    fill_feed_and_check_it_scrolls(page, mock)
    return mock


SCROLL_STATES: dict[str, Callable[[Page, str, Grid], MockRoomSocket]] = {
    "s1": open_s1,
    "s2": open_s2,
    "k2": open_k2,
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


def host_changed_frame(seq: int, player_id: str) -> str:
    return HostChanged(seq=seq, player_id=player_id).model_dump_json()


def resize_to(page: Page, width: int, height: int) -> None:
    """Resize the window, then wait until the page reads the new width."""
    page.set_viewport_size({"width": width, "height": height})
    page.wait_for_function(
        "width => window.innerWidth === width", arg=width, timeout=WAIT_TIMEOUT_MS
    )


def size_ids(cases: list[tuple[str, str, int, int]]) -> list[str]:
    return [f"{state}-{name}-{width}x{height}" for state, name, width, height in cases]


# (state, list, width, height): a list that scrolls with no control inside.
SCROLLING_LIST_CASES = [
    ("s2", "feed", 360, 740),
    ("s2", "feed", 568, 320),
    ("s2", "feed", 1280, 720),
    ("s1", "roster", 568, 320),
    ("s1", "roster", 320, 568),
]
SCROLLING_LIST_IDS = size_ids(SCROLLING_LIST_CASES)
# In S1: a list that does not scroll.
STILL_LIST_CASES = [
    ("s1", "feed", 568, 320),
    ("s1", "feed", 320, 568),
    ("s1", "feed", 1280, 720),
    ("s1", "roster", 1280, 720),
]
STILL_LIST_IDS = size_ids(STILL_LIST_CASES)
SMALL_WINDOWS = [(568, 320), (320, 568)]
NAME_CASES = [("s1", 568, 320), ("s1", 1280, 720), ("k2", 568, 320), ("k2", 1280, 720)]
# (list, section, heading id, fr.json key, the name it gives).
LIST_NAMES = [
    ("roster", "roster", "roster-heading", "roster.heading", "Joueurs"),
    ("feed", "activity-feed", "feed-heading", "feed.heading", "Activité"),
]
# The arrow keys of each list, in order: the key, the scroll position it changes
# ("top" or "left") and the sign of the change.
LIST_ARROWS = {
    "feed": [("ArrowUp", "top", -1), ("ArrowDown", "top", 1)],
    "roster": [("ArrowRight", "left", 1), ("ArrowLeft", "left", -1)],
}


@pytest.mark.parametrize(
    ("state", "list_name", "width", "height"),
    SCROLLING_LIST_CASES,
    ids=SCROLLING_LIST_IDS,
)
def test_ac12_a_scrolling_list_with_no_control_inside_is_a_tab_stop(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    list_name: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    SCROLL_STATES[state](page, live_server, fx01_grid)
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, list_name)
    assert_scrolls(shown, list_name)

    steps = tab_walk_to_the_grid(page)

    assert shown.tabindex == "0", shown
    assert times_focused(steps, list_name) == 1, steps


@pytest.mark.parametrize(
    ("state", "list_name", "width", "height"), STILL_LIST_CASES, ids=STILL_LIST_IDS
)
def test_ac12_a_list_that_does_not_scroll_is_not_a_tab_stop(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    list_name: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    SCROLL_STATES[state](page, live_server, fx01_grid)
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, list_name)
    assert_does_not_scroll(shown, list_name)

    steps = tab_walk_to_the_grid(page)

    assert shown.tabindex is None, shown
    assert times_focused(steps, list_name) == 0, steps


@pytest.mark.parametrize(("width", "height"), SMALL_WINDOWS, ids=["568x320", "320x568"])
def test_ac12_the_hosts_roster_list_with_remove_buttons_is_not_a_tab_stop(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)
    page.wait_for_timeout(LIST_FOLLOW_MS)
    shown = read_list_state(page, "roster")
    assert_scrolls(shown, "roster")

    assert shown.remove_buttons == 4, shown
    assert shown.tabindex == "-1", shown
    assert shown.tab_index == -1, shown
    steps = tab_walk_to_the_grid(page)
    button_owners: list[str] = []
    for step in steps:
        if step.test_id == "remove-player" and step.player_id is not None:
            button_owners.append(step.player_id)
    assert sorted(button_owners) == ["p2", "p3", "p4", "p5"], steps
    assert times_focused(steps, "roster") == 0, steps


@pytest.mark.parametrize(
    ("state", "width", "height"),
    NAME_CASES,
    ids=[f"{state}-{width}x{height}" for state, width, height in NAME_CASES],
)
def test_ac12_each_list_is_named_by_the_heading_of_its_section(
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

    for list_name, section, heading_id, key, name in LIST_NAMES:
        assert fr_json[key] == name
        by_role = page.get_by_role("list", name=name, exact=True)
        expect(by_role, name).to_have_count(1)
        selector = LIST_SELECTORS[list_name]
        assert by_role.evaluate(IS_THE_ELEMENT_SCRIPT, selector) is True, name
        named_list = page.locator(selector)
        expect(named_list).to_have_attribute("role", "list")
        expect(named_list).to_have_attribute("aria-labelledby", heading_id)
        heading = page.get_by_test_id(section).locator("h2")
        expect(heading).to_have_attribute("id", heading_id)
        expect(heading).to_have_text(fr_json[key])


def press_and_expect_a_scroll(
    page: Page, list_name: str, key: str, axis: str, sign: int
) -> None:
    """Press an arrow key; fail unless the focused list scrolls that way in 300 ms.

    Args:
        page: The room page, with the focus on the list.
        list_name: `roster` or `feed`.
        key: The arrow key to press.
        axis: `top` for `scrollTop`, `left` for `scrollLeft`.
        sign: 1 when the position must grow, -1 when it must shrink.
    """
    before = read_list_state(page, list_name)
    page.keyboard.press(key)
    waited_ms = 0
    while True:
        now = read_list_state(page, list_name)
        assert now.focused, (key, now)
        if axis == "top":
            change = now.scroll_top - before.scroll_top
        else:
            change = now.scroll_left - before.scroll_left
        if change * sign > 0:
            break
        if waited_ms >= LIST_FOLLOW_MS:
            pytest.fail(
                f"{key} did not scroll the {list_name} list within"
                f" {LIST_FOLLOW_MS} ms: {before} then {now}"
            )
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
    page.evaluate(SCROLL_SETTLED_SCRIPT, LIST_SELECTORS[list_name])
    assert read_list_state(page, list_name).focused, key


@pytest.mark.parametrize(
    ("state", "list_name", "width", "height"),
    SCROLLING_LIST_CASES,
    ids=SCROLLING_LIST_IDS,
)
def test_ac12_the_arrow_keys_scroll_the_focused_list(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    list_name: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    SCROLL_STATES[state](page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, list_name), list_name)
    tab_walk_to_the_list(page, list_name)

    for key, axis, sign in LIST_ARROWS[list_name]:
        press_and_expect_a_scroll(page, list_name, key, axis, sign)


@pytest.mark.parametrize(
    ("state", "list_name", "width", "height"),
    SCROLLING_LIST_CASES,
    ids=SCROLLING_LIST_IDS,
)
def test_ac12_a_focused_scrolling_list_shows_its_whole_focus_outline(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    list_name: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    SCROLL_STATES[state](page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, list_name), list_name)
    tab_walk_to_the_list(page, list_name)
    page.wait_for_timeout(LIST_FOLLOW_MS)

    outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
    band = page.evaluate(FOCUS_BAND_SCRIPT)

    assert outline["style"] not in ("none", "auto"), outline
    assert outline["width"] >= MIN_OUTLINE_PX, outline
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline
    assert {side: round(px) for side, px in band["cut"].items()} == NO_CUT, band
    assert band["coveredBy"] == {}, band


def test_ac12_the_roster_list_tab_stop_follows_a_resize(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(568, 320)
    open_s1(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "roster"), "roster")
    wait_for_list(page, "roster", has_tab_stop)

    resize_to(page, 1280, 720)
    wait_for_list(page, "roster", has_no_tabindex)

    resize_to(page, 568, 320)
    wait_for_list(page, "roster", has_tab_stop)


def test_ac12_the_feed_list_tab_stop_follows_new_lines(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(568, 320)
    mock = open_s1(page, live_server, fx01_grid)
    wait_for_list(page, "feed", has_no_tabindex)

    for line_count, seq in enumerate((11, 12, 13), start=1):
        mock.send(check_result_frame(seq))
        expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
        expect(page.get_by_test_id("feed-item")).to_have_count(line_count)
        shown = wait_for_list(page, "feed", tabindex_follows_scroll)
        if line_count >= 2:
            assert_scrolls(shown, "feed")


def test_ac12_the_roster_list_tab_stop_follows_the_host_role(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(568, 320)
    mock = open_s1(page, live_server, fx01_grid)
    remove_buttons = page.get_by_test_id("remove-player")

    mock.send(host_changed_frame(11, "p1"))
    expect(remove_buttons.first).to_be_visible()
    assert_scrolls(read_list_state(page, "roster"), "roster")
    wait_for_list(page, "roster", has_tabindex_minus_one)

    mock.send(host_changed_frame(12, "p2"))
    expect(remove_buttons).to_have_count(0)
    assert_scrolls(read_list_state(page, "roster"), "roster")
    wait_for_list(page, "roster", has_tab_stop)


def test_ac12_a_focused_list_keeps_its_tab_stop_until_the_focus_leaves(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(568, 320)
    mock = open_s1(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "roster"), "roster")
    tab_walk_to_the_list(page, "roster")

    mock.send(host_changed_frame(11, "p1"))
    expect(page.get_by_test_id("remove-player").first).to_be_visible()
    page.wait_for_timeout(LIST_FOLLOW_MS)
    kept = read_list_state(page, "roster")
    page.keyboard.press("Tab")
    step = read_focus_step(page)

    assert kept.focused, kept
    assert kept.tabindex == "0", kept
    assert (step.test_id, step.player_id) == ("remove-player", "p2"), step
    wait_for_list(page, "roster", has_tabindex_minus_one)


STILL_READ_MS = 100
STILL_READ_LIMIT = 20  # 2 s of reads, 100 ms apart
NEW_LINE_SEQ = 54
FEED_ITEMS_AFTER_NEW_LINE = 44


def wait_for_a_still_scroll_top(page: Page, list_name: str) -> ListState:
    """Read the list every 100 ms until two reads in a row give one `scrollTop`."""
    previous = read_list_state(page, list_name)
    for _ in range(STILL_READ_LIMIT):
        page.wait_for_timeout(STILL_READ_MS)
        current = read_list_state(page, list_name)
        if current.scroll_top == previous.scroll_top:
            return current
        previous = current
    pytest.fail(f"the {list_name} list kept scrolling for 2 s: {previous}")


@pytest.mark.parametrize(("width", "height"), FEED_SIZES)
def test_ac12_a_new_line_leaves_the_focused_feed_list_where_the_keys_put_it(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    mock = open_s2(page, live_server, fx01_grid)
    assert_scrolls(read_list_state(page, "feed"), "feed")
    tab_walk_to_the_list(page, "feed")
    page.keyboard.press("ArrowUp")
    before = wait_for_a_still_scroll_top(page, "feed")
    assert before.distance_to_end > 1, f"ArrowUp left the list at its end: {before}"

    mock.send(check_result_frame(NEW_LINE_SEQ))
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-seq", str(NEW_LINE_SEQ)
    )
    page.wait_for_timeout(LIST_FOLLOW_MS)
    after = read_list_state(page, "feed")

    expect(page.get_by_test_id("feed-item")).to_have_count(FEED_ITEMS_AFTER_NEW_LINE)
    assert abs(after.scroll_top - before.scroll_top) <= EPSILON, (before, after)
    assert after.focused, after
