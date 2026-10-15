"""Shared setup of the window tests of spec 014: AC-7 to AC-10 (small screens).

Pytest does not collect this module (its name does not start with `test_`). It holds
what only the tests of AC-7 to AC-10 share: the window sizes, the scripts run in the
page, the measures of the remove buttons and the `small_window` fixture. The rest of
the shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.

- The fixture `small_window` is defined here once, and each test file that asks for
  it imports it under the same name
  (`from spec014_windows_harness import small_window as small_window`, the form that
  tells ruff the import is meant to stay).
- Before they measure a layout, the window tests wait up to 1 s for the buttons to
  follow the rule of AC-9 (`wait_for_the_form`; the spec lets a text check poll that
  long). A page that never follows it is reported by the AC-9 tests, not by the
  others.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import NamedTuple, Protocol

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerView
from spec014_harness import (
    NICKNAMES,
    WAIT_TIMEOUT_MS,
    MockRoom,
    joined_mock_room,
    load_fr,
    player_view,
)

EPSILON = 1.0
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged
# (the script of spec 009, for the touch contexts of Firefox and WebKit).
COARSE_POINTER_SCRIPT = r"""
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(player_view(f"p{number}", NICKNAMES[number - 1], number - 1))
    return players


# ---- Helpers for the window tests (AC-7 to AC-10) ---------------------------


def make_page(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> tuple[Page, Callable[[], None]]:
    """Open a desktop or touch page (spec 009's harness); return it and its closer."""
    viewport = {"width": width, "height": height}
    if not touch:
        context = browser.new_context(viewport=viewport)
    elif browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if touch and browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context.new_page(), context.close


MIN_TARGET_PX = 24.0
TARGET_TOLERANCE_PX = 0.01


def panel_shows_a_more_marker(page: Page) -> bool:
    """Tell whether `host-panel-more` is visible at an edge of the panel."""
    marker = page.get_by_test_id("host-panel-more")
    if marker.count() == 0 or not marker.first.is_visible():
        return False
    marker_box = marker.first.bounding_box()
    panel_box = page.get_by_test_id("host-panel").bounding_box()
    if marker_box is None or panel_box is None:
        return False
    panel_right = panel_box["x"] + panel_box["width"]
    marker_right = marker_box["x"] + marker_box["width"]
    touches_panel = (
        marker_box["x"] <= panel_right + EPSILON
        and marker_right >= panel_box["x"] - EPSILON
    )
    inside_rows = (
        marker_box["y"] + marker_box["height"] >= panel_box["y"] - EPSILON
        and marker_box["y"] <= panel_box["y"] + panel_box["height"] + EPSILON
    )
    return touches_panel and inside_rows


FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
MAX_TABS = 60


def tab_to_control(page: Page, test_id: str) -> None:
    """Press Tab until the control has the focus; Escape frees Tab from the grid."""
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        focused = page.evaluate(FOCUSED_TEST_ID_SCRIPT)
        if focused == test_id:
            return
        if focused == "grid":
            page.keyboard.press("Escape")
    pytest.fail(f"{test_id} not reached in {MAX_TABS} Tab presses")


# ---- The hit test of a remove button (AC-8, AC-9) ---------------------------


# The check itself, for the button where it stands now. AC-8 scrolls the button into
# view first (HIT_TEST_SCRIPT, in the test file of AC-8); AC-9 runs it as it is
# (HIT_TEST_IN_PLACE_SCRIPT, in the test file of AC-9), once the page scrolled a
# focused button by itself.
HIT_TEST_BODY = """
  const box = button.getBoundingClientRect();
  const misses = [];
  let tested = 0;
  for (let y = Math.ceil(box.top); y + 1 <= box.bottom; y += 1) {
    for (let x = Math.ceil(box.left); x + 1 <= box.right; x += 1) {
      tested += 1;
      const hit = document.elementFromPoint(x + 0.5, y + 0.5);
      if (hit === null || !(hit === button || button.contains(hit))) {
        const name = hit === null ? 'nothing' : (
          hit.getAttribute('data-testid') || hit.tagName
        );
        misses.push([x, y, name]);
      }
    }
  }
  return {
    tested, missCount: misses.length, firstMisses: misses.slice(0, 5),
    size: [box.width, box.height],
  };
"""


# ---- Small windows (AC-8 to AC-10): the windows and what the tests share ----


REMOVE_BUTTON_COUNT = 7
DEFAULT_ROOT_FONT_PX = 16
SWITCH_IN_ROOT_FONTS = 4.5  # AC-9: compact while the list is narrower than 4.5rem
SWITCH_TOLERANCE_PX = 1.0  # AC-9: within 1 px of the threshold, either form passes
LIVE_CHANGE_MS = 1000  # AC-9, AC-10: a change applies "within 1 s"
POLL_MS = 50
MIN_HIT_PIXELS = 24 * 24 - 2 * 24


class Window(NamedTuple):
    """A window size in CSS px, and the root font size in px to run it at."""

    width: int
    height: int
    root_font: int


def window_id(window: Window) -> str:
    return f"{window.width}x{window.height}-{window.root_font}px"


# The narrow and low windows of the spec's "Test harness".
NARROW_LOW_WINDOWS = [
    Window(300, 480, 16),
    Window(300, 480, 20),
    Window(300, 480, 12),
    Window(300, 480, 24),
    Window(320, 480, 16),
    Window(320, 480, 20),
    Window(360, 500, 16),
    Window(360, 500, 20),
    Window(400, 480, 16),
    Window(400, 480, 20),
    Window(480, 500, 16),
    Window(480, 500, 20),
]
NARROW_LOW_IDS = [window_id(window) for window in NARROW_LOW_WINDOWS]

ROOT_FONT_SCRIPT = "size => { document.documentElement.style.fontSize = size; }"
ROOT_FONT_READS_SCRIPT = (
    "size => getComputedStyle(document.documentElement).fontSize === size"
)
TWO_FRAMES_SCRIPT = """
() => new Promise(resolve => {
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
})
"""
# `w` is the clientWidth of the roster list and `r` the computed font size of `html`
# in CSS px (spec 014, "Small windows"), then the text of each remove button.
BUTTONS_STATE_SCRIPT = """
() => {
  const list = document.querySelector('[data-testid="roster"] ul');
  const buttons = document.querySelectorAll('[data-testid="remove-player"]');
  const texts = [];
  for (const button of buttons) {
    texts.push(button.textContent.trim());
  }
  return {
    listWidth: list.clientWidth,
    rootFont: parseFloat(getComputedStyle(document.documentElement).fontSize),
    texts: texts,
  };
}
"""


def wait_for_root_font(page: Page, size_px: int) -> None:
    """Wait until `html` computes that font size, then for two animation frames."""
    page.wait_for_function(
        ROOT_FONT_READS_SCRIPT, arg=f"{size_px}px", timeout=WAIT_TIMEOUT_MS
    )
    page.evaluate(TWO_FRAMES_SCRIPT)


def set_root_font(page: Page, size_px: int) -> None:
    """Set the root font size with a style on `html`, as the spec's harness says."""
    page.evaluate(ROOT_FONT_SCRIPT, f"{size_px}px")
    wait_for_root_font(page, size_px)


def use_root_font(page: Page, size_px: int) -> None:
    """Give the page the root font size of a window.

    16 px is the browser default, so nothing is added for it.
    """
    if size_px == DEFAULT_ROOT_FONT_PX:
        wait_for_root_font(page, size_px)
    else:
        set_root_font(page, size_px)


class ButtonsState(NamedTuple):
    """What AC-9 reads: the list width `w`, the root font `r` and the texts."""

    list_width: float
    root_font: float
    texts: list[str]


def read_buttons_state(page: Page) -> ButtonsState:
    raw = page.evaluate(BUTTONS_STATE_SCRIPT)
    return ButtonsState(
        list_width=raw["listWidth"], root_font=raw["rootFont"], texts=raw["texts"]
    )


def rule_violation(
    state: ButtonsState, full_text: str, compact_text: str
) -> str | None:
    """Return how a state breaks the rule of AC-9, or None when it holds.

    Compact while `w < 4.5 r`, full from `w >= 4.5 r`; within 1 px of `4.5 r`
    either passes; all the buttons show the same one.
    """
    if len(state.texts) != REMOVE_BUTTON_COUNT:
        return f"expected {REMOVE_BUTTON_COUNT} remove buttons: {state}"
    if len(set(state.texts)) != 1:
        return f"the buttons do not all have the same form: {state}"
    threshold = SWITCH_IN_ROOT_FONTS * state.root_font
    if state.list_width < threshold - SWITCH_TOLERANCE_PX:
        allowed = [compact_text]
    elif state.list_width > threshold + SWITCH_TOLERANCE_PX:
        allowed = [full_text]
    else:
        allowed = [compact_text, full_text]
    shown = state.texts[0]
    if shown in allowed:
        return None
    return (
        f"w={state.list_width} and 4.5 x r = {threshold}: the buttons should read "
        f"{allowed} but read {shown!r} ({state})"
    )


def wait_for_the_form(page: Page) -> None:
    """Give the buttons up to 1 s to take the form that AC-9 asks for.

    The tests that measure the layout call this before measuring, so that a page
    that follows a root font change a moment later is not measured half-way. It
    never fails: the AC-9 tests report a wrong form, the other tests measure what
    is there. Without the key `host.remove_short` there is nothing to wait for.
    """
    fr = load_fr()
    compact_text = fr.get("host.remove_short")
    if compact_text is None:
        return
    waited_ms = 0
    while waited_ms < LIVE_CHANGE_MS:
        state = read_buttons_state(page)
        if rule_violation(state, fr["host.remove"], compact_text) is None:
            return
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS


class OpenSmallWindow(Protocol):
    """The `small_window` fixture: open the host's view in a window."""

    def __call__(
        self, window: Window, touch: bool = False
    ) -> tuple[Page, MockRoom]: ...


@pytest.fixture
def small_window(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> Iterator[OpenSmallWindow]:
    """Return `small_window(window, touch=False)`: the host's view in that window.

    The setup of AC-8 (FX-01, `you` host, 8 players, so 7 `remove-player` buttons)
    in a desktop or a touch context of the window's size. The call returns the page
    and the mocked room once the roster is shown, the root font is set and the
    buttons had their moment to follow it. The contexts close after the test.
    """
    closers: list[Callable[[], None]] = []

    def open_window(window: Window, touch: bool = False) -> tuple[Page, MockRoom]:
        page, close = make_page(
            browser, browser_name, window.width, window.height, touch
        )
        closers.append(close)
        room = joined_mock_room(page, live_server, fx01_grid, eight_players())
        buttons = page.get_by_test_id("remove-player")
        expect(buttons).to_have_count(REMOVE_BUTTON_COUNT)
        use_root_font(page, window.root_font)
        wait_for_the_form(page)
        page.evaluate(TWO_FRAMES_SCRIPT)
        return page, room

    yield open_window
    for close in closers:
        close()


LIVE_WINDOW = Window(480, 500, DEFAULT_ROOT_FONT_PX)
