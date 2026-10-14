"""Tests of spec 014, AC-10: the low layout keeps room for one whole button.

The browser with spec 040's mocked socket.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.

Not tested here, with the reason:

- The minimum list width when the roster holds no `remove-player` (AC-10, "Host
  alone, or not host"): the spec only says the minimum does not apply, so there is
  no behaviour to observe.

Choices where the spec leaves room (AC-10, small windows):

- AC-10 runs with one long line in the feed (a `settings_changed` event on top of
  the AC-9 setup): with an empty feed there is no line to cut inside the feed's box.
- AC-10 "cut or end with an ellipsis": each element child of the feed (its heading
  and its line) either holds its content within its width (`scrollWidth` at most
  `clientWidth`, 1 px tolerance) or clips the rest (computed `overflow-x` other
  than `visible`), with or without an ellipsis. So its text never paints outside
  its own box, which lies inside the feed's box.
- AC-10 "the rules apply again" (live) is one scenario of mine: a resize to
  300x480, then root fonts of 20, 24, 12 and 16 px, then a resize back. After each
  step every AC-10 rule must hold within 1 s.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple, Protocol

import pytest
from playwright.sync_api import Page, expect

from nock.protocol import HelpMode, RevealBudget, RoomSettings
from spec014_harness import (
    DEFAULT_ROOT_FONT_PX,
    EPSILON,
    LIVE_CHANGE_MS,
    LIVE_WINDOW,
    NARROW_LOW_IDS,
    NARROW_LOW_WINDOWS,
    POLL_MS,
    REMOVE_BUTTON_COUNT,
    TWO_FRAMES_SCRIPT,
    OpenSmallWindow,
    Window,
    feed_lines,
    panel_shows_a_more_marker,
    room_page,
    set_root_font,
    settings_frame,
)
from spec014_harness import fx01_grid as fx01_grid
from spec014_harness import small_window as small_window

LIST_ROOM_PX = 3  # AC-10: the room after the last item
LOW_LAYOUT_MAX_HEIGHT_PX = 500  # the low layout: window.innerHeight <= 500


# ---- AC-10: the roster list keeps room for one whole button -----------------


LOW_LAYOUT_SCRIPT = """
() => {
  const boxOf = (element) => {
    const box = element.getBoundingClientRect();
    return [box.left, box.top, box.right, box.bottom];
  };
  const byTestId = (id) => document.querySelector('[data-testid="' + id + '"]');
  const childrenOf = (parent) => {
    const children = [];
    for (const child of parent.children) {
      children.push({
        tag: child.tagName,
        box: boxOf(child),
        scrollWidth: child.scrollWidth,
        clientWidth: child.clientWidth,
        overflowX: getComputedStyle(child).overflowX,
      });
    }
    return children;
  };
  const roster = byTestId('roster');
  const feed = byTestId('activity-feed');
  const panel = byTestId('host-panel');
  const widths = [];
  for (const button of document.querySelectorAll('[data-testid="remove-player"]')) {
    widths.push(button.offsetWidth);
  }
  return {
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    scrollWidth: document.documentElement.scrollWidth,
    roster: boxOf(roster),
    feed: boxOf(feed),
    panel: boxOf(panel),
    listWidth: roster.querySelector('ul').clientWidth,
    buttonWidths: widths,
    rosterChildren: childrenOf(roster),
    feedChildren: childrenOf(feed),
    panelHiddenRight: panel.scrollWidth - panel.clientWidth - panel.scrollLeft,
  };
}
"""
# The host changes the settings once, so that the feed holds a long line: the
# longest of spec 013's texts, "Ana a modifié les réglages : aide par vote, ...".
FEED_LINE_SETTINGS = RoomSettings(
    help_mode=HelpMode.VOTE,
    reveal_budget=RevealBudget(letters=3, words=0),
    locked=False,
)


class Box(NamedTuple):
    """The edges of a bounding box in CSS px."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left


class Child(NamedTuple):
    """An element child of `roster` or `activity-feed`, as AC-10 measures it.

    `scroll_width` is the width of its content, text included, and `client_width`
    the width inside its box; both are whole CSS px. `overflow_x` is its computed
    `overflow-x`: anything but `visible` clips what does not fit in the box.
    """

    tag: str
    box: Box
    scroll_width: int
    client_width: int
    overflow_x: str


class LowLayout(NamedTuple):
    """What AC-10 measures in the low layout, read in one go."""

    inner_width: float
    inner_height: float
    scroll_width: float
    roster: Box
    feed: Box
    panel: Box
    list_width: float
    button_widths: list[int]
    roster_children: list[Child]
    feed_children: list[Child]
    panel_hidden_right: float


# Any: the JSON that `page.evaluate` returns, which Playwright types as Any.
def children_of(raw_children: list[dict[str, Any]]) -> list[Child]:
    """Turn the children that LOW_LAYOUT_SCRIPT read into `Child` values."""
    children: list[Child] = []
    for raw in raw_children:
        child = Child(
            tag=raw["tag"],
            box=Box(*raw["box"]),
            scroll_width=raw["scrollWidth"],
            client_width=raw["clientWidth"],
            overflow_x=raw["overflowX"],
        )
        children.append(child)
    return children


def read_low_layout(page: Page) -> LowLayout:
    """Measure the three boxes and what they hold, all at the same moment."""
    raw = page.evaluate(LOW_LAYOUT_SCRIPT)
    roster_children = children_of(raw["rosterChildren"])
    feed_children = children_of(raw["feedChildren"])
    layout = LowLayout(
        inner_width=raw["innerWidth"],
        inner_height=raw["innerHeight"],
        scroll_width=raw["scrollWidth"],
        roster=Box(*raw["roster"]),
        feed=Box(*raw["feed"]),
        panel=Box(*raw["panel"]),
        list_width=raw["listWidth"],
        button_widths=raw["buttonWidths"],
        roster_children=roster_children,
        feed_children=feed_children,
        panel_hidden_right=raw["panelHiddenRight"],
    )
    assert layout.inner_height <= LOW_LAYOUT_MAX_HEIGHT_PX, layout
    return layout


class OpenLowLayout(Protocol):
    """The `low_layout` fixture: open the host's view in a window, feed filled."""

    def __call__(self, window: Window, touch: bool = False) -> Page: ...


@pytest.fixture
def low_layout(small_window: OpenSmallWindow) -> OpenLowLayout:
    """Return `low_layout(window, touch=False)`: `small_window` plus a feed line."""

    def open_layout(window: Window, touch: bool = False) -> Page:
        page, room = small_window(window, touch)
        room.connections[0].send(settings_frame(6, "p1", FEED_LINE_SETTINGS))
        expect(room_page(page)).to_have_attribute("data-seq", "6")
        expect(feed_lines(page, "settings_changed")).to_have_count(1)
        page.evaluate(TWO_FRAMES_SCRIPT)
        return page

    return open_layout


def assert_list_keeps_room_for_a_button(layout: LowLayout) -> None:
    """Minimum: the list is at least one button plus 3 px wide, for every button."""
    assert len(layout.button_widths) == REMOVE_BUTTON_COUNT, layout
    for button_width in layout.button_widths:
        assert layout.list_width >= button_width + LIST_ROOM_PX, layout


def assert_one_row(layout: LowLayout) -> None:
    """One row: roster, feed and host panel, left to right, in that order."""
    assert layout.feed.left >= layout.roster.right - EPSILON, layout
    assert layout.panel.left >= layout.feed.right - EPSILON, layout
    top = max(layout.roster.top, layout.feed.top, layout.panel.top)
    bottom = min(layout.roster.bottom, layout.feed.bottom, layout.panel.bottom)
    assert top < bottom, layout


def assert_host_panel_share(layout: LowLayout) -> None:
    """The host panel keeps a third of the three boxes' widths, minus 1 px."""
    total = layout.roster.width + layout.feed.width + layout.panel.width
    assert layout.panel.width >= total / 3 - EPSILON, layout


def assert_fade_visible(page: Page, layout: LowLayout) -> None:
    """The panel's content is hidden past its right edge, and the fade says so."""
    assert layout.panel_hidden_right > EPSILON, layout
    assert panel_shows_a_more_marker(page), layout


def assert_content_inside_its_box(layout: LowLayout) -> None:
    """Every element child of the roster and of the feed is inside its parent."""
    parents = (
        ("roster", layout.roster, layout.roster_children),
        ("activity-feed", layout.feed, layout.feed_children),
    )
    for name, parent, children in parents:
        for child in children:
            assert child.box.left >= parent.left - EPSILON, (name, child.tag, layout)
            assert child.box.right <= parent.right + EPSILON, (name, child.tag, layout)


def assert_feed_text_is_cut_inside_its_boxes(layout: LowLayout) -> None:
    """The feed's heading and line never paint their text outside their own box.

    Each element child of the feed either holds its content within its width, or
    clips what does not fit (computed `overflow-x` other than `visible`): the
    text is then cut at the edge of its box, with or without an ellipsis. A
    heading that shrinks below its text and lets it overflow would paint it over
    the feed's line or over the host panel.
    """
    for child in layout.feed_children:
        fits = child.scroll_width <= child.client_width + EPSILON
        is_cut = child.overflow_x != "visible"
        assert fits or is_cut, ("activity-feed", child, layout)


def assert_page_fits(layout: LowLayout) -> None:
    """No horizontal scroll, and the three boxes are inside the window."""
    assert layout.scroll_width <= layout.inner_width, layout
    boxes = (
        ("roster", layout.roster),
        ("activity-feed", layout.feed),
        ("host-panel", layout.panel),
    )
    for name, box in boxes:
        assert box.left >= -EPSILON, (name, layout)
        assert box.right <= layout.inner_width + EPSILON, (name, layout)


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_roster_list_keeps_room_for_one_whole_button(
    low_layout: OpenLowLayout, window: Window, context_kind: str
) -> None:
    page = low_layout(window, touch=context_kind == "touch")

    assert_list_keeps_room_for_a_button(read_low_layout(page))


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_roster_the_feed_and_the_host_panel_sit_in_one_row(
    low_layout: OpenLowLayout, window: Window, context_kind: str
) -> None:
    page = low_layout(window, touch=context_kind == "touch")

    assert_one_row(read_low_layout(page))


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_host_panel_keeps_a_third_of_the_row_and_its_fade(
    low_layout: OpenLowLayout, window: Window, context_kind: str
) -> None:
    page = low_layout(window, touch=context_kind == "touch")
    layout = read_low_layout(page)

    assert_host_panel_share(layout)
    assert_fade_visible(page, layout)


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_roster_and_the_feed_keep_their_content_inside_their_boxes(
    low_layout: OpenLowLayout, window: Window, context_kind: str
) -> None:
    page = low_layout(window, touch=context_kind == "touch")
    layout = read_low_layout(page)

    assert_content_inside_its_box(layout)
    assert_feed_text_is_cut_inside_its_boxes(layout)


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_page_has_no_horizontal_scroll_and_the_boxes_fit_the_window(
    low_layout: OpenLowLayout, window: Window, context_kind: str
) -> None:
    page = low_layout(window, touch=context_kind == "touch")

    assert_page_fits(read_low_layout(page))


def check_the_low_layout(page: Page) -> None:
    """Every rule of AC-10, on the page as it is now."""
    layout = read_low_layout(page)
    assert_list_keeps_room_for_a_button(layout)
    assert_one_row(layout)
    assert_host_panel_share(layout)
    assert_fade_visible(page, layout)
    assert_content_inside_its_box(layout)
    assert_feed_text_is_cut_inside_its_boxes(layout)
    assert_page_fits(layout)


def holds_within_a_second(page: Page, step: str, check: Callable[[Page], None]) -> None:
    """Run `check` until it passes, for up to 1 s; then fail with its last failure."""
    waited_ms = 0
    while True:
        try:
            check(page)
            return
        except AssertionError as failure:
            if waited_ms >= LIVE_CHANGE_MS:
                raise AssertionError(f"{step}: {failure}") from failure
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS


def test_ac10_browser_the_rules_apply_again_after_a_resize_and_a_root_font_change(
    low_layout: OpenLowLayout,
) -> None:
    page = low_layout(LIVE_WINDOW)
    holds_within_a_second(page, "at 480x500, 16 px", check_the_low_layout)

    page.set_viewport_size({"width": 300, "height": 480})
    holds_within_a_second(page, "resized to 300x480", check_the_low_layout)

    for size_px in (20, 24, 12, DEFAULT_ROOT_FONT_PX):
        set_root_font(page, size_px)
        step = f"at 300x480, root font {size_px} px"
        holds_within_a_second(page, step, check_the_low_layout)

    page.set_viewport_size({"width": 480, "height": 500})
    holds_within_a_second(page, "resized back to 480x500", check_the_low_layout)
