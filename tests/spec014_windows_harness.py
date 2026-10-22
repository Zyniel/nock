"""Shared setup of the window tests of spec 014: AC-7 to AC-10 (small screens).

Pytest does not collect this module (its name does not start with `test_`). It holds
what only the tests of AC-7 to AC-10 share: the window sizes, the scripts run in the
page, the measures of the host's buttons and sheet, and the `small_window` fixture.
The rest of the shared setup is in `tests/spec014_harness.py`, whose docstring says
how the tests are built.

Refined by spec 043 (the design's room layout): `remove-player` and `mute-player`
sit in the other players' rows of the Salon's Joueurs tab, which the tests show
with spec 043's `show_tab`, and always read « Retirer »; the host panel is the room
sheet `host-settings`, opened with `open_host_settings`. The host panel's fade,
the compact button and the low layout are gone, with their helpers.

- The fixture `small_window` is defined here once, and each test file that asks for
  it imports it under the same name
  (`from spec014_windows_harness import small_window as small_window`, the form that
  tells ruff the import is meant to stay).
- Sizes are compared with spec 043's tolerance of 0.5 px, so a box of 23.99999 px
  (sub-pixel float error) still counts as 24 px.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, NamedTuple, Protocol

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import PlayerView
from room_panels import show_tab
from spec014_harness import (
    NICKNAMES,
    WAIT_TIMEOUT_MS,
    MockRoom,
    joined_mock_room,
    player_view,
)

EPSILON = 1.0
SIZE_TOLERANCE_PX = 0.5
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
WINDOW_IDS = [f"{width}x{height}" for width, height in WINDOW_SIZES]

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

# A reading from the page: its values are the page's (numbers, texts and lists
# mixed), so their type is not known here.
Reading = dict[str, Any]


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


def at_least(size: float, minimum: float) -> bool:
    """A size of at least `minimum`, with the 0.5 px tolerance of a size."""
    return size >= minimum - SIZE_TOLERANCE_PX


# ---- The hit test of a button (AC-8, AC-9) ------------------------------------


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


# ---- The host's settings sheet (AC-7, AC-10) ------------------------------------

# The controls of the sheet that AC-7 names, in this order: `lock-room`, the labels
# of the three `help-mode-option` radios, the two number fields and `settings-save`.
# For each: its name, its box after `scrollIntoView({block: "nearest"})`, whether
# `elementFromPoint` at its centre returns it or one of its descendants, and the
# dialog's box.
SHEET_CONTROLS_SCRIPT = r"""
() => {
  const dialog = document.querySelector('[data-testid="host-settings"]');
  const byId = id => document.querySelector(`[data-testid="${id}"]`);
  const controls = [['lock-room', byId('lock-room')]];
  for (const radio of document.querySelectorAll('[data-testid="help-mode-option"]')) {
    controls.push([`help-mode-option ${radio.value} label`, radio.labels[0]]);
  }
  for (const id of ['reveal-letters-input', 'reveal-words-input', 'settings-save']) {
    controls.push([id, byId(id)]);
  }
  const found = [];
  for (const [name, element] of controls) {
    if (element === null || element === undefined) {
      found.push({name: name, missing: true});
      continue;
    }
    element.scrollIntoView({block: 'nearest'});
    const box = element.getBoundingClientRect();
    const dialogBox = dialog.getBoundingClientRect();
    const hit = document.elementFromPoint(box.left + box.width / 2,
      box.top + box.height / 2);
    found.push({
      name: name,
      missing: false,
      box: [box.left, box.top, box.right, box.bottom],
      dialog: [dialogBox.left, dialogBox.top, dialogBox.right, dialogBox.bottom],
      hits: hit !== null && (hit === element || element.contains(hit)),
      hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
    });
  }
  return found;
}
"""
SHEET_CONTROL_COUNT = 7


def sheet_controls(page: Page) -> list[Reading]:
    """Each control of AC-7 in the open sheet: its box, the dialog's, its hit."""
    found = page.evaluate(SHEET_CONTROLS_SCRIPT)
    assert isinstance(found, list), found
    return found


def inside(box: list[float], outer: list[float]) -> bool:
    """Tell whether `box` lies inside `outer` (`[left, top, right, bottom]`), 1 px."""
    return (
        box[0] >= outer[0] - EPSILON
        and box[1] >= outer[1] - EPSILON
        and box[2] <= outer[2] + EPSILON
        and box[3] <= outer[3] + EPSILON
    )


def sheet_control_problems(page: Page, *, min_height: float | None) -> list[str]:
    """How the sheet's controls break AC-7 or AC-10 (empty: none).

    Each control is reachable (`elementFromPoint` after `scrollIntoView`) and lies
    inside the dialog; with `min_height`, it is at least that high.
    """
    problems: list[str] = []
    controls = sheet_controls(page)
    if len(controls) != SHEET_CONTROL_COUNT:
        problems.append(f"{len(controls)} controls, expected {SHEET_CONTROL_COUNT}")
    for control in controls:
        name = control["name"]
        if control["missing"]:
            problems.append(f"{name} is missing")
            continue
        box = control["box"]
        if min_height is not None and not at_least(box[3] - box[1], min_height):
            problems.append(f"{name} is {box[3] - box[1]} px high")
        if not control["hits"]:
            problems.append(
                f"{name}: elementFromPoint at its centre is {control['hit']}"
            )
        if not inside(box, control["dialog"]):
            problems.append(
                f"{name} {box} is not inside the dialog {control['dialog']}"
            )
    return problems


DIALOG_SCRIPT = r"""
() => {
  const dialog = document.querySelector('[data-testid="host-settings"]');
  const box = dialog.getBoundingClientRect();
  return {
    box: [box.left, box.top, box.right, box.bottom],
    window: [0, 0, innerWidth, innerHeight],
    scrollWidth: dialog.scrollWidth,
    clientWidth: dialog.clientWidth,
    pageScrollWidth: document.documentElement.scrollWidth,
  };
}
"""


def dialog_reading(page: Page) -> Reading:
    found = page.evaluate(DIALOG_SCRIPT)
    assert isinstance(found, dict), found
    return found


# ---- Small windows (AC-8 to AC-10): the windows and what the tests share ----


REMOVE_BUTTON_COUNT = 7
DEFAULT_ROOT_FONT_PX = 16
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
    in a desktop or a touch context of the window's size, with the Salon on its
    Joueurs tab (spec 043's `show_tab`). The call returns the page and the mocked
    room once the rows are shown and the root font is set. The contexts close after
    the test.
    """
    closers: list[Callable[[], None]] = []

    def open_window(window: Window, touch: bool = False) -> tuple[Page, MockRoom]:
        page, close = make_page(
            browser, browser_name, window.width, window.height, touch
        )
        closers.append(close)
        room = joined_mock_room(page, live_server, fx01_grid, eight_players())
        show_tab(page, "players")
        buttons = page.get_by_test_id("remove-player")
        expect(buttons).to_have_count(REMOVE_BUTTON_COUNT)
        use_root_font(page, window.root_font)
        page.evaluate(TWO_FRAMES_SCRIPT)
        return page, room

    yield open_window
    for close in closers:
        close()
