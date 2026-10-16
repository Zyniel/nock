"""Tests of spec 035: every action by keyboard, a visible focus (AC-1, AC-2).

The keyboard walk (AC-1, AC-2) uses the live server and the real WebSocket; the
other tests of AC-2 use a mocked socket. The setup the test files of spec 035
share is in `tests/spec035_harness.py`.
"""

from __future__ import annotations

import json
import re
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, WebSocket, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import (
    FEED_LIST_SELECTOR,
    FEED_SIZES,
    FOCUS_BAND_SCRIPT,
    FOCUS_OUTLINE_SCRIPT,
    MAX_TABS,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    ROOM_TIMEOUT_MS,
    SETTLE_MS,
    Walker,
    add_sentinel,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    expect_focus_on_sentinel,
    expect_selected,
    expect_word,
    fill_feed_and_check_it_scrolls,
    load_fr,
    open_k2,
    open_room,
    wait_until,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


ACTIVE_ELEMENT_SCRIPT = r"""
() => {
  const element = document.activeElement;
  if (element === null) {
    return null;
  }
  return {testId: element.getAttribute('data-testid')};
}
"""

LETTER_OUTLINES_SCRIPT = r"""
() => {
  const result = [];
  const cells = document.querySelectorAll(
    '[data-testid="cell"][data-type="letter"]'
  );
  for (const cell of cells) {
    const style = getComputedStyle(cell);
    result.push({
      row: Number(cell.getAttribute('data-row')),
      column: Number(cell.getAttribute('data-column')),
      selected: cell.getAttribute('data-selected') === 'true',
      style: style.outlineStyle,
      width: parseFloat(style.outlineWidth),
    });
  }
  return result;
}
"""


def letter_outlines(page: Page) -> list[dict[str, Any]]:
    outlines = page.evaluate(LETTER_OUTLINES_SCRIPT)
    assert isinstance(outlines, list)
    return outlines


def assert_only_selected_cell_is_outlined(outlines: list[dict[str, Any]]) -> None:
    """The selected cell is `solid` and at least 2 px; the others have no outline."""
    selected = [outline for outline in outlines if outline["selected"]]
    assert len(selected) == 1, outlines
    assert selected[0]["style"] == "solid", selected
    assert selected[0]["width"] >= MIN_OUTLINE_PX, selected
    for outline in outlines:
        if not outline["selected"]:
            assert outline["style"] == "none", outline


# ---- The walk of AC-1 and AC-2 ----------------------------------------------------


class FrameRecorder:
    """The frames a page sends on its room sockets, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[dict[str, Any]] = []
        page.on("websocket", self._on_socket)

    def _on_socket(self, websocket: WebSocket) -> None:
        if websocket.url.endswith("/ws"):
            websocket.on("framesent", self._on_frame)

    def _on_frame(self, payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        self.frames.append(json.loads(text))

    def of_type(self, type_name: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for frame in self.frames:
            if frame["type"] == type_name:
                found.append(frame)
        return found

    def wait_for(self, type_name: str, count: int) -> list[dict[str, Any]]:
        """Wait until `count` frames of that type were sent; return them all."""
        wait_until(self.page, lambda: len(self.of_type(type_name)) >= count)
        return self.of_type(type_name)


class WalkResult(NamedTuple):
    """What the walk of AC-1 left behind."""

    ana: Walker
    recorder: FrameRecorder
    bob_walker: Walker


def press_and_expect_sent(
    walker: Walker, recorder: FrameRecorder, type_name: str, count: int
) -> dict[str, Any]:
    """Press Enter on the focused control; return the new frame of that type."""
    walker.page.keyboard.press("Enter")
    frames = recorder.wait_for(type_name, count)
    return frames[count - 1]


def walk_the_catalogue(walker: Walker, live_server: str) -> None:
    """On `/`: filter by force 1 and start item 1, keyboard only."""
    page = walker.page
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-item").first).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )
    walker.tab_to("force-filter", selector='[data-force="1"]')
    page.keyboard.press("Enter")
    expect(
        page.locator('[data-testid="force-filter"][data-force="1"]')
    ).to_have_attribute("aria-pressed", "true")
    item_one_play = (
        '[data-testid="catalogue-item"][data-number="1"] [data-testid="catalogue-play"]'
    )
    walker.tab_to("catalogue-play", selector=item_one_play)
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/r/[A-Z0-9]{6}$"))
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "joined", timeout=ROOM_TIMEOUT_MS
    )


def walk_the_grid(walker: Walker, recorder: FrameRecorder) -> None:
    """In the room: select, type, move, erase, undo and leave the grid.

    The room is `joined`, so the sentinel is added first: leaving the grid moves
    the focus to it.
    """
    page = walker.page
    add_sentinel(page)
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)
    walker.outlines.append(letter_outlines(page))

    page.keyboard.press("t")
    page.keyboard.press("a")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect_selected(page, 1, 2)

    page.keyboard.press("ArrowDown")
    expect_selected(page, 2, 2)
    page.keyboard.press("ArrowLeft")
    expect_selected(page, 2, 1)
    page.keyboard.press("ArrowUp")
    expect_selected(page, 1, 1)

    page.keyboard.press("Backspace")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    erased = recorder.wait_for("erase", 1)
    assert (erased[0]["row"], erased[0]["column"]) == (1, 1)

    page.keyboard.press("Control+z")
    recorder.wait_for("undo", 1)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    expect_focus_on_sentinel(page)
    walker.outlines.append(letter_outlines(page))


def walk_the_controls(walker: Walker, recorder: FrameRecorder) -> None:
    """Checks, undo, share links, lock and settings, keyboard only."""
    page = walker.page
    expected_scopes = [
        ("check-word", "word"),
        ("check-letter", "letter"),
        ("check-grid", "grid"),
    ]
    for count, (test_id, scope) in enumerate(expected_scopes, start=1):
        walker.tab_to(test_id)
        frame = press_and_expect_sent(walker, recorder, "check", count)
        assert frame["target"]["scope"] == scope

    walker.tab_to("undo-button")
    press_and_expect_sent(walker, recorder, "undo", 2)

    walker.tab_to("copy-link")
    walker.tab_to("share-link")

    lock_room = page.get_by_test_id("lock-room")
    walker.tab_to("lock-room")
    page.keyboard.press("Enter")
    expect(lock_room).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Enter")
    expect(lock_room).to_have_attribute("aria-pressed", "false")
    locks = recorder.wait_for("lock_room", 2)
    assert [frame["locked"] for frame in locks] == [True, False]

    walker.tab_to("help-mode-select")
    page.keyboard.press("ArrowDown")
    walker.tab_to("settings-save")
    saved = press_and_expect_sent(walker, recorder, "change_settings", 1)
    assert saved["help_mode"] == "vote"


def walk_the_removal(
    walker: Walker, recorder: FrameRecorder, browser: Browser
) -> Walker:
    """Bob joins from the keyboard, then Ana removes him; return Bob's walker."""
    page = walker.page
    bob_context = browser.new_context()
    bob_page = bob_context.new_page()
    bob_walker = Walker(bob_page)
    try:
        bob_page.goto(page.url)
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "nickname", timeout=ROOM_TIMEOUT_MS
        )
        bob_walker.tab_to("nickname-input")
        bob_page.keyboard.type("Bob")
        bob_page.keyboard.press("Enter")
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "joined", timeout=ROOM_TIMEOUT_MS
        )

        label = load_fr()["host.remove_label"].replace("{name}", "Bob")
        walker.tab_to("remove-player", selector=f'[aria-label="{label}"]')
        page.keyboard.press("Enter")
        recorder.wait_for("remove_player", 1)
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "removed", timeout=ROOM_TIMEOUT_MS
        )
    finally:
        bob_context.close()
    return bob_walker


def run_keyboard_walk(page: Page, browser: Browser, live_server: str) -> WalkResult:
    """The whole walk of AC-1; every step uses the keyboard only."""
    recorder = FrameRecorder(page)
    walker = Walker(page)
    walk_the_catalogue(walker, live_server)
    walk_the_grid(walker, recorder)
    walk_the_controls(walker, recorder)
    bob_walker = walk_the_removal(walker, recorder, browser)
    return WalkResult(ana=walker, recorder=recorder, bob_walker=bob_walker)


# ---- AC-1: every action is reachable from the keyboard -------------------------


def test_ac1_every_action_is_reachable_from_the_keyboard(
    page: Page, browser: Browser, live_server: str
) -> None:
    result = run_keyboard_walk(page, browser, live_server)

    reached = [step.test_id for step in result.ana.reached]
    expected_in_order = [
        "force-filter",
        "catalogue-play",
        "grid",
        "check-word",
        "check-letter",
        "check-grid",
        "undo-button",
        "copy-link",
        "share-link",
        "lock-room",
        "help-mode-select",
        "settings-save",
        "remove-player",
    ]
    assert reached == expected_in_order
    assert [step.test_id for step in result.bob_walker.reached] == ["nickname-input"]
    letters = result.recorder.of_type("edit_letter")
    typed = [(frame["row"], frame["column"], frame["letter"]) for frame in letters]
    assert typed[:2] == [(1, 0, "T"), (1, 1, "A")]


# ---- AC-2: the focus is always visible -----------------------------------------


def test_ac2_every_element_reached_by_the_walk_shows_a_visible_focus(
    page: Page, browser: Browser, live_server: str
) -> None:
    result = run_keyboard_walk(page, browser, live_server)

    assert len(result.ana.outlines) == 2
    for outlines in result.ana.outlines:
        assert_only_selected_cell_is_outlined(outlines)
    steps = result.ana.reached + result.bob_walker.reached
    assert len(steps) == 14
    assert "grid" in [step.test_id for step in steps]
    for step in steps:
        assert step.outline_style not in ("none", "auto"), step
        assert step.outline_width >= MIN_OUTLINE_PX, step
        assert step.outline_contrast >= MIN_FOCUS_CONTRAST, step


def test_ac2_the_selected_cell_keeps_its_outline_without_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    add_sentinel(page)
    walker = Walker(page)
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_selected(page, 1, 0)
    assert_only_selected_cell_is_outlined(letter_outlines(page))

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect_focus_on_sentinel(page)
    expect_selected(page, 1, 0)
    assert_only_selected_cell_is_outlined(letter_outlines(page))


def test_ac2_no_cell_is_outlined_before_a_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    for outline in letter_outlines(page):
        assert outline["style"] == "none", outline


# Pointer focus must not disturb the host panel's fade (spec 014 AC-7); a keyboard
# focus on a panel control hides it. The probes run in K2 on a 320x568 phone.
# On a pointer focus the page's own code never scrolls the panel, but the browser may
# (WebKit scrolls a partly visible select into view), so the test spies on the
# page's scroll calls instead of comparing the panel's `scrollLeft`.

PHONE_SIZE = {"width": 320, "height": 568}
PANEL_CONTROLS = [
    "lock-room",
    "help-mode-select",
    "reveal-letters-input",
    "reveal-words-input",
]

HOST_PANEL_STATE_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const fade = document.querySelector('[data-testid="host-panel-more"]');
  const fadeStyle = fade === null ? null : getComputedStyle(fade);
  return {
    fade: fadeStyle === null ? null : fadeStyle.visibility,
    fadeDisplay: fadeStyle === null ? null : fadeStyle.display,
    moreToTheRight: panel.scrollLeft + panel.clientWidth < panel.scrollWidth - 1,
  };
}
"""

# Records in `window.panelScrollCalls` each scroll call that the page makes on the
# host panel or on an element inside it: the scroll methods of `Element.prototype`
# (`scrollIntoViewIfNeeded` where the engine has it) and the `scrollLeft` setter. A
# scroll that the browser makes by itself does not go through them.
SCROLL_SPY_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  window.panelScrollCalls = [];
  const record = (name, element) => {
    if (element === panel || panel.contains(element)) {
      window.panelScrollCalls.push(name);
    }
  };
  const methods = [
    'scrollIntoView', 'scrollIntoViewIfNeeded', 'scroll', 'scrollTo', 'scrollBy',
  ];
  for (const name of methods) {
    const originalMethod = Element.prototype[name];
    if (typeof originalMethod !== 'function') {
      continue;
    }
    Element.prototype[name] = function (...args) {
      record(name, this);
      return originalMethod.apply(this, args);
    };
  }
  const scrollLeft = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollLeft');
  Object.defineProperty(Element.prototype, 'scrollLeft', {
    configurable: true,
    enumerable: scrollLeft.enumerable,
    get: scrollLeft.get,
    set(value) {
      record('scrollLeft', this);
      scrollLeft.set.call(this, value);
    },
  });
}
"""

# Put the control in the panel so that it is fully shown ("full") or cut by the
# right edge of the panel ("partial"), without any focus change.
SCROLL_CONTROL_SCRIPT = r"""
([testId, mode]) => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const control = document.querySelector(`[data-testid="${testId}"]`);
  const panelBox = panel.getBoundingClientRect();
  const box = control.getBoundingClientRect();
  const left = box.left - panelBox.left + panel.scrollLeft;
  panel.scrollLeft = mode === 'full'
    ? left - 10
    : left + box.width * 0.6 - panel.clientWidth;
}
"""
FEED_LIST_TEST_ID = "feed list"


def mobile_context(browser: Browser, touch: bool) -> BrowserContext:
    """A 320x568 context; `touch` adds a touch screen like a phone has."""
    is_mobile = touch and browser.browser_type.name != "firefox"
    return browser.new_context(
        viewport=PHONE_SIZE, has_touch=touch, is_mobile=is_mobile
    )


def visible_centre(page: Page, test_id: str) -> tuple[float, float] | None:
    """The centre of the part of a host-panel control that the panel shows."""
    box = page.get_by_test_id(test_id).bounding_box()
    panel = page.get_by_test_id("host-panel").bounding_box()
    assert box is not None
    assert panel is not None
    left = max(box["x"], panel["x"]) + 2
    right = min(box["x"] + box["width"], panel["x"] + panel["width"]) - 2
    if right <= left:
        return None
    return (left + right) / 2, box["y"] + box["height"] / 2


def focused_test_id(page: Page) -> str | None:
    """The `data-testid` of the focused element.

    Args:
        page: The page to inspect.

    Returns:
        The test id of the focused element, or None when nothing is focused or
        the focused element has no test id.
    """
    found = page.evaluate(ACTIVE_ELEMENT_SCRIPT)
    if found is None:
        return None
    return found["testId"]


@pytest.mark.parametrize("scroll_mode", ["partial", "full"])
@pytest.mark.parametrize("target", PANEL_CONTROLS)
@pytest.mark.parametrize("touch", [False, True], ids=["mouse", "touch"])
def test_ac2_a_pointer_focus_keeps_the_host_panel_fade_and_makes_no_scroll_call(
    browser: Browser,
    live_server: str,
    fx01_grid: Grid,
    touch: bool,
    target: str,
    scroll_mode: str,
) -> None:
    context = mobile_context(browser, touch)
    page = context.new_page()
    open_k2(page, live_server, fx01_grid)
    page.evaluate(SCROLL_CONTROL_SCRIPT, [target, scroll_mode])
    page.wait_for_timeout(SETTLE_MS)
    centre = visible_centre(page, target)
    if centre is None:
        context.close()
        pytest.skip(f"{target} has no visible part in mode {scroll_mode}")

    # The spy goes in after the set-up scroll above, which it must not record.
    page.evaluate(SCROLL_SPY_SCRIPT)
    # Raw coordinates: `.click()` scrolls the element into view and hides the bug.
    x, y = centre
    if touch:
        page.touchscreen.tap(x, y)
    else:
        page.mouse.click(x, y)
    page.wait_for_timeout(SETTLE_MS)
    scroll_calls = page.evaluate("window.panelScrollCalls")
    state = page.evaluate(HOST_PANEL_STATE_SCRIPT)
    context.close()

    assert scroll_calls == [], state
    if state["moreToTheRight"]:
        assert state["fade"] == "visible", state
        assert state["fadeDisplay"] != "none", state


@pytest.mark.parametrize("target", PANEL_CONTROLS)
def test_ac2_a_keyboard_focus_in_the_host_panel_hides_the_fade(
    browser: Browser, live_server: str, fx01_grid: Grid, target: str
) -> None:
    context = mobile_context(browser, touch=False)
    page = context.new_page()
    open_k2(page, live_server, fx01_grid)
    page.evaluate("document.activeElement.blur()")
    walker = Walker(page)
    walker.tab_to(target)
    page.wait_for_timeout(SETTLE_MS)
    state = page.evaluate(HOST_PANEL_STATE_SCRIPT)
    context.close()

    assert state["fade"] == "hidden", state


@pytest.mark.parametrize(("width", "height"), FEED_SIZES)
def test_ac2_the_activity_feed_focus_outline_is_fully_visible(
    browser: Browser,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    mock = open_k2(page, live_server, fx01_grid)
    fill_feed_and_check_it_scrolls(page, mock)
    page.evaluate("document.activeElement.blur()")
    reached = False
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        if focused_test_id(page) == "grid":
            page.keyboard.press("Escape")
        is_feed = page.evaluate(
            "selector => document.activeElement.matches(selector)",
            FEED_LIST_SELECTOR,
        )
        if is_feed:
            reached = True
            break
    # No engine is skipped: AC-12 makes the list a Tab stop in every engine.
    if not reached:
        context.close()
    assert reached, f"Tab never reached the {FEED_LIST_TEST_ID} at {width}x{height}"
    page.wait_for_timeout(SETTLE_MS)
    band = page.evaluate(FOCUS_BAND_SCRIPT)
    outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
    context.close()

    assert band["style"] not in ("none", "auto"), band
    assert band["width"] >= MIN_OUTLINE_PX, band
    # The colour, as for every outline of AC-2's walk: 3:1 against white.
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline
    no_cut = {"top": 0, "right": 0, "bottom": 0, "left": 0}
    assert {side: round(px) for side, px in band["cut"].items()} == no_cut, band
    assert band["coveredBy"] == {}, band
