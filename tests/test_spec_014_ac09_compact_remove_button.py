"""Tests of spec 014, AC-9: the compact remove button.

The browser with spec 040's mocked socket, and the static text of `fr.json`.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.

Not tested here, with the reason:

- A root font changed by a browser setting (AC-9, "Root font source"): the tests
  change it with a style on `html`, as the spec's harness says.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Page

from spec014_harness import NICKNAMES, load_fr, roster_item
from spec014_harness import fx01_grid as fx01_grid
from spec014_windows_harness import (
    DEFAULT_ROOT_FONT_PX,
    HIT_TEST_BODY,
    LIVE_CHANGE_MS,
    LIVE_WINDOW,
    MIN_HIT_PIXELS,
    MIN_TARGET_PX,
    NARROW_LOW_WINDOWS,
    POLL_MS,
    REMOVE_BUTTON_COUNT,
    TARGET_TOLERANCE_PX,
    WINDOW_SIZES,
    OpenSmallWindow,
    Window,
    read_buttons_state,
    rule_violation,
    set_root_font,
    tab_to_control,
    window_id,
)
from spec014_windows_harness import small_window as small_window
from spec035_harness import unknown_texts

MIN_OUTLINE_PX = 2.0
MIN_FOCUS_CONTRAST = 3.0
MIN_TEXT_CONTRAST = 4.5


def remove_texts() -> tuple[str, str]:
    """Return the full and the compact text of a remove button, from fr.json."""
    fr = load_fr()
    assert "host.remove_short" in fr, "fr.json has no key host.remove_short"
    return fr["host.remove"], fr["host.remove_short"]


# ---- AC-9: the compact remove button ----------------------------------------


MULTIPLICATION_X = chr(0x2715)  # U+2715, the sign of the compact remove button


def test_ac9_fr_json_holds_the_compact_remove_text() -> None:
    fr = load_fr()

    assert fr.get("host.remove_short") == MULTIPLICATION_X
    assert len(fr["host.remove_short"]) == 1


# Where the spec names the form of the buttons: True for the compact `✕`, False
# for "Retirer". At every window size of spec 006 AC-5 the root font is the
# default one.
COMPACT_WINDOWS = [
    Window(300, 480, 16),
    Window(320, 480, 16),
    Window(360, 500, 16),
    Window(400, 480, 16),
    Window(300, 480, 20),
    Window(320, 480, 20),
    Window(360, 500, 20),
    Window(400, 480, 20),
    Window(480, 500, 20),
    Window(300, 480, 12),
    Window(300, 480, 24),
]
FULL_WINDOWS = [
    Window(480, 500, 16),
    Window(740, 360, 20),
    *[Window(width, height, 16) for width, height in WINDOW_SIZES],
]
NAMED_FORMS = [
    *[(window, True) for window in COMPACT_WINDOWS],
    *[(window, False) for window in FULL_WINDOWS],
]
NAMED_FORM_IDS = [window_id(window) for window, _compact in NAMED_FORMS]
# Both forms are checked for the label and the target size: the compact one at
# every narrow and low window it shows at, the full one at 480x500 and 740x360.
LABEL_WINDOWS = [*NARROW_LOW_WINDOWS, Window(740, 360, 20)]
LABEL_IDS = [window_id(window) for window in LABEL_WINDOWS]


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(("window", "compact"), NAMED_FORMS, ids=NAMED_FORM_IDS)
def test_ac9_browser_the_buttons_show_the_form_of_their_window(
    small_window: OpenSmallWindow, window: Window, compact: bool, context_kind: str
) -> None:
    full_text, compact_text = remove_texts()
    page, _room = small_window(window, touch=context_kind == "touch")

    state = read_buttons_state(page)

    assert state.root_font == window.root_font, state
    violation = rule_violation(state, full_text, compact_text)
    assert violation is None, violation
    expected = compact_text if compact else full_text
    assert state.texts == [expected] * REMOVE_BUTTON_COUNT, (window, state)


OWNER_SCRIPT = """
element => {
  const row = element.closest('[data-testid="roster-player"]');
  return row === null ? null : row.getAttribute('data-player-id');
}
"""


def assert_label_and_target(page: Page, player_id: str, nickname: str) -> None:
    """One remove button: its `aria-label`, the way a role query finds it, its size."""
    label = load_fr()["host.remove_label"].replace("{name}", nickname)
    button = roster_item(page, player_id).get_by_test_id("remove-player")
    assert button.get_attribute("aria-label") == label
    named = page.get_by_role("button", name=label, exact=True)
    assert named.count() == 1, label
    assert named.get_attribute("data-testid") == "remove-player", label
    assert named.evaluate(OWNER_SCRIPT) == player_id, label
    box = button.bounding_box()
    assert box is not None, label
    assert box["width"] >= MIN_TARGET_PX - TARGET_TOLERANCE_PX, (label, box)
    assert box["height"] >= MIN_TARGET_PX - TARGET_TOLERANCE_PX, (label, box)


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", LABEL_WINDOWS, ids=LABEL_IDS)
def test_ac9_browser_both_forms_keep_the_label_and_the_24_pixel_target(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    full_text, compact_text = remove_texts()
    page, _room = small_window(window, touch=context_kind == "touch")

    # The checks below must run on the form that this window is meant to show.
    form_text = compact_text if window in COMPACT_WINDOWS else full_text
    state = read_buttons_state(page)
    assert state.texts == [form_text] * REMOVE_BUTTON_COUNT, (window, state)
    for number in range(2, 9):
        assert_label_and_target(page, f"p{number}", NICKNAMES[number - 1])


def wait_for_the_buttons_to_read(page: Page, text: str) -> None:
    """Fail unless the seven buttons all read `text` within 1 s."""
    expected = [text] * REMOVE_BUTTON_COUNT
    waited_ms = 0
    state = read_buttons_state(page)
    while state.texts != expected:
        if waited_ms >= LIVE_CHANGE_MS:
            pytest.fail(f"the buttons do not read {text!r} within 1 s: {state}")
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
        state = read_buttons_state(page)


def test_ac9_browser_the_buttons_switch_live_when_the_root_font_changes(
    small_window: OpenSmallWindow,
) -> None:
    full_text, compact_text = remove_texts()
    page, _room = small_window(LIVE_WINDOW)
    wait_for_the_buttons_to_read(page, full_text)

    set_root_font(page, 20)
    wait_for_the_buttons_to_read(page, compact_text)

    set_root_font(page, DEFAULT_ROOT_FONT_PX)
    wait_for_the_buttons_to_read(page, full_text)


def test_ac9_browser_the_buttons_switch_live_when_the_window_is_resized(
    small_window: OpenSmallWindow,
) -> None:
    full_text, compact_text = remove_texts()
    page, _room = small_window(LIVE_WINDOW)
    wait_for_the_buttons_to_read(page, full_text)

    page.set_viewport_size({"width": 360, "height": 500})
    wait_for_the_buttons_to_read(page, compact_text)

    page.set_viewport_size({"width": 480, "height": 500})
    wait_for_the_buttons_to_read(page, full_text)


# The colour helpers, the contrast scan and the focus outline reader of spec 035's
# "Test harness" are in tests/colour_contrast.js, which the spec 035 tests read
# too, so that both files always measure the same way. That file only declares
# them; each script below wraps it in a function for `page.evaluate` that returns
# one measurement.
COLOUR_CONTRAST_JS = (Path(__file__).parent / "colour_contrast.js").read_text(
    encoding="utf-8"
)
# The outline of the focused element: style, width (px) and ratio (against white).
FOCUS_OUTLINE_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn readFocusOutline();\n}"
)
# Each measurement: text, ratio and removeFor (the player id of the roster row when
# the element is inside a remove button, else None), with tag, testid, rowState
# and opacity.
CONTRAST_SCAN_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn scanTextContrast();\n}"
)
FOCUSED_REMOVE_SCRIPT = """
() => {
  const active = document.activeElement;
  if (active === null || active.getAttribute('data-testid') !== 'remove-player') {
    return null;
  }
  const row = active.closest('[data-testid="roster-player"]');
  return row === null ? null : row.getAttribute('data-player-id');
}
"""
# Resolves when the element has stood still for three animation frames: the page
# scrolls a focused button by itself, and the check waits for that scroll to end.
STILL_SCRIPT = """
element => new Promise(resolve => {
  let previous = '';
  let still = 0;
  let frames = 0;
  const look = () => {
    const box = element.getBoundingClientRect();
    const current = box.left + ',' + box.top;
    still = current === previous ? still + 1 : 0;
    previous = current;
    frames += 1;
    if (still >= 3 || frames >= 120) {
      resolve(frames);
    } else {
      requestAnimationFrame(look);
    }
  };
  requestAnimationFrame(look);
})
"""
# The hit test of a remove button as it stands, once the page scrolled a focused
# button by itself (the check of HIT_TEST_BODY).
HIT_TEST_IN_PLACE_SCRIPT = "button => {" + HIT_TEST_BODY + "}"
FOCUS_WINDOWS = [
    Window(300, 480, 16),
    Window(300, 480, 20),
    Window(360, 500, 16),
    Window(360, 500, 20),
]
FOCUS_IDS = [window_id(window) for window in FOCUS_WINDOWS]


def focus_problems(page: Page, player_id: str, compact_text: str) -> list[str]:
    """Return what is wrong with the focused remove button of `player_id`."""
    button = roster_item(page, player_id).get_by_test_id("remove-player")
    button.evaluate(STILL_SCRIPT)
    problems: list[str] = []
    shown = button.evaluate("element => element.textContent.trim()")
    if shown != compact_text:
        problems.append(f"{player_id} reads {shown!r}, not {compact_text!r}")
    outline = page.evaluate(FOCUS_OUTLINE_SCRIPT)
    if outline["style"] in ("none", "auto"):
        problems.append(f"{player_id} outline style {outline['style']}")
    if outline["width"] < MIN_OUTLINE_PX:
        problems.append(f"{player_id} outline width {outline['width']}")
    if outline["ratio"] < MIN_FOCUS_CONTRAST:
        problems.append(f"{player_id} outline contrast {outline['ratio']}")
    report = button.evaluate(HIT_TEST_IN_PLACE_SCRIPT)
    if report["tested"] < MIN_HIT_PIXELS:
        problems.append(f"{player_id} only {report['tested']} pixels tested")
    if report["missCount"] != 0:
        problems.append(f"{player_id} taps miss it: {report}")
    return problems


@pytest.mark.parametrize("window", FOCUS_WINDOWS, ids=FOCUS_IDS)
def test_ac9_browser_a_focused_compact_button_keeps_its_outline_and_stays_whole(
    small_window: OpenSmallWindow, window: Window
) -> None:
    _full_text, compact_text = remove_texts()
    page, _room = small_window(window)

    tab_to_control(page, "remove-player")
    problems: list[str] = []
    for number in range(2, 2 + REMOVE_BUTTON_COUNT):
        if number > 2:
            page.keyboard.press("Tab")
        player_id = f"p{number}"
        assert page.evaluate(FOCUSED_REMOVE_SCRIPT) == player_id
        problems.extend(focus_problems(page, player_id, compact_text))

    assert problems == []


# The language scan of spec 035's harness, on the remove buttons and what they hold:
# each visible direct text node (trimmed) and each aria-label, title, placeholder
# and alt value.
REMOVE_LANGUAGE_SCAN_SCRIPT = r"""
() => {
  const attributes = ['aria-label', 'title', 'placeholder', 'alt'];
  const found = [];
  for (const button of document.querySelectorAll('[data-testid="remove-player"]')) {
    const scanned = [button, ...button.querySelectorAll('*')];
    for (const element of scanned) {
      const rendered = element.getClientRects().length > 0;
      if (!rendered || getComputedStyle(element).visibility !== 'visible') {
        continue;
      }
      for (const node of element.childNodes) {
        if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== '') {
          found.push(node.textContent.trim());
        }
      }
      for (const name of attributes) {
        const value = element.getAttribute(name);
        if (value !== null && value.trim() !== '') {
          found.push(value.trim());
        }
      }
    }
  }
  return found;
}
"""


class Contrast(NamedTuple):
    """The contrast ratio the scan measured for a text of one remove button."""

    player_id: str
    text: str
    ratio: float


def remove_button_contrasts(page: Page) -> list[Contrast]:
    """Run the contrast scan and keep what it measured inside the remove buttons."""
    found: list[Contrast] = []
    for measurement in page.evaluate(CONTRAST_SCAN_SCRIPT):
        player_id = measurement["removeFor"]
        if player_id is not None:
            found.append(Contrast(player_id, measurement["text"], measurement["ratio"]))
    return found


SCAN_WINDOW = Window(300, 480, DEFAULT_ROOT_FONT_PX)


def test_ac9_browser_the_compact_buttons_pass_the_contrast_scan(
    small_window: OpenSmallWindow,
) -> None:
    _full_text, compact_text = remove_texts()
    page, _room = small_window(SCAN_WINDOW)
    assert read_buttons_state(page).texts == [compact_text] * REMOVE_BUTTON_COUNT

    contrasts = remove_button_contrasts(page)

    scanned_players = sorted(contrast.player_id for contrast in contrasts)
    assert scanned_players == [f"p{number}" for number in range(2, 9)]
    for contrast in contrasts:
        assert contrast.text == compact_text, contrast
        assert contrast.ratio >= MIN_TEXT_CONTRAST, contrast


def test_ac9_browser_the_compact_buttons_pass_the_language_scan(
    small_window: OpenSmallWindow,
) -> None:
    _full_text, compact_text = remove_texts()
    page, _room = small_window(SCAN_WINDOW)
    assert read_buttons_state(page).texts == [compact_text] * REMOVE_BUTTON_COUNT

    texts = page.evaluate(REMOVE_LANGUAGE_SCAN_SCRIPT)

    assert texts.count(compact_text) == REMOVE_BUTTON_COUNT, texts
    label_template = load_fr()["host.remove_label"]
    for number in range(2, 9):
        label = label_template.replace("{name}", NICKNAMES[number - 1])
        assert texts.count(label) == 1, (label, texts)
    assert unknown_texts(texts, set()) == []
