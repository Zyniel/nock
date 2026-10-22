"""Tests of spec 014, AC-9: a remove button always reads « Retirer » and stays
inside the Joueurs tab.

The browser with spec 040's mocked socket, and the static text of `fr.json`.

Refined by spec 043 (the design's room layout): the compact `✕` form goes, since
the Joueurs rows have room for « Retirer » at every window. The setup shows the
Salon's Joueurs tab with spec 043's `show_tab`.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.

Not tested here, with the reason:

- A root font changed by a browser setting ("Root font source"): the tests change
  it with a style on `html`, as the spec's harness says.

Choices where the spec leaves room:

- "Inside the box of its `roster-player` row and of `salon` horizontally": the
  button's left and right edges, 1 px tolerance; sizes have spec 043's 0.5 px.
- Focus: the `Tab` presses run from `salon-tab-players` until the first
  `remove-player` has the focus, then on until each of the seven had it; the
  `mute-player` of each row comes between them.
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
    EPSILON,
    HIT_TEST_BODY,
    MIN_HIT_PIXELS,
    MIN_TARGET_PX,
    NARROW_LOW_WINDOWS,
    REMOVE_BUTTON_COUNT,
    WINDOW_SIZES,
    OpenSmallWindow,
    Window,
    at_least,
    window_id,
)
from spec014_windows_harness import small_window as small_window
from spec035_harness import unknown_texts

MIN_OUTLINE_PX = 2.0
MIN_FOCUS_CONTRAST = 3.0
MIN_TEXT_CONTRAST = 4.5
MAX_TABS = 60

# The narrow and low windows, then the window sizes of spec 006 AC-5 at the default
# root font.
RULE_WINDOWS = [
    *NARROW_LOW_WINDOWS,
    *[Window(width, height, DEFAULT_ROOT_FONT_PX) for width, height in WINDOW_SIZES],
]
RULE_IDS = [window_id(window) for window in RULE_WINDOWS]

# Each remove button after `scrollIntoView`: its player, text, label, box, its
# row's box and the Salon's; then whether the Joueurs panel scrolls sideways.
BUTTONS_SCRIPT = r"""
() => {
  const salon = document.querySelector('[data-testid="salon"]');
  const panel = document.querySelector('[data-testid="roster"]');
  const buttons = [];
  for (const button of document.querySelectorAll('[data-testid="remove-player"]')) {
    button.scrollIntoView({block: 'nearest', inline: 'nearest'});
    const row = button.closest('[data-testid="roster-player"]');
    const box = button.getBoundingClientRect();
    const rowBox = row.getBoundingClientRect();
    const salonBox = salon.getBoundingClientRect();
    buttons.push({
      playerId: row.getAttribute('data-player-id'),
      text: button.textContent.trim(),
      label: button.getAttribute('aria-label'),
      box: [box.left, box.top, box.right, box.bottom],
      row: [rowBox.left, rowBox.right],
      salon: [salonBox.left, salonBox.right],
    });
  }
  return {buttons: buttons,
    panelScrolls: panel.scrollWidth > panel.clientWidth + 1};
}
"""


def expected_label(player_id: str) -> str:
    number = int(player_id.removeprefix("p"))
    return load_fr()["host.remove_label"].replace("{name}", NICKNAMES[number - 1])


def rule_problems(page: Page) -> list[str]:
    """How the remove buttons break the rule of AC-9 (empty: none)."""
    found = page.evaluate(BUTTONS_SCRIPT)
    text = load_fr()["host.remove"]
    problems: list[str] = []
    if len(found["buttons"]) != REMOVE_BUTTON_COUNT:
        problems.append(f"{len(found['buttons'])} remove buttons")
    for button in found["buttons"]:
        player_id = button["playerId"]
        label = expected_label(player_id)
        if button["text"] != text:
            problems.append(f"{player_id}: reads {button['text']!r}")
        if button["label"] != label:
            problems.append(f"{player_id}: aria-label {button['label']!r}")
        named = page.get_by_role("button", name=label, exact=True)
        if named.count() != 1:
            problems.append(f"{player_id}: {named.count()} buttons named {label!r}")
        left, top, right, bottom = button["box"]
        if not at_least(right - left, MIN_TARGET_PX):
            problems.append(f"{player_id}: {right - left} px wide")
        if not at_least(bottom - top, MIN_TARGET_PX):
            problems.append(f"{player_id}: {bottom - top} px high")
        for name, (outer_left, outer_right) in (
            ("row", button["row"]),
            ("salon", button["salon"]),
        ):
            if left < outer_left - EPSILON or right > outer_right + EPSILON:
                problems.append(f"{player_id}: outside its {name} sideways")
    if found["panelScrolls"]:
        problems.append("the Joueurs panel scrolls sideways")
    return problems


# ---- AC-9: the rule ----------------------------------------------------------------


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", RULE_WINDOWS, ids=RULE_IDS)
def test_ac9_browser_each_remove_button_reads_retirer_and_stays_in_its_row(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")

    assert rule_problems(page) == []


# ---- AC-9: the focus ---------------------------------------------------------------

# The colour helpers, the contrast scan and the focus outline reader of spec 035's
# "Test harness" are in tests/colour_contrast.js, which the spec 035 tests read
# too, so that both files always measure the same way.
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


def focus_problems(page: Page, player_id: str) -> list[str]:
    """Return what is wrong with the focused remove button of `player_id`."""
    button = roster_item(page, player_id).get_by_test_id("remove-player")
    button.evaluate(STILL_SCRIPT)
    problems: list[str] = []
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


def tab_to_next_remove_button(page: Page) -> str:
    """Press `Tab` until a remove button has the focus; return its player id."""
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        player_id = page.evaluate(FOCUSED_REMOVE_SCRIPT)
        if player_id is not None:
            return str(player_id)
    pytest.fail(f"no remove-player reached in {MAX_TABS} Tab presses")


@pytest.mark.parametrize("window", FOCUS_WINDOWS, ids=FOCUS_IDS)
def test_ac9_browser_a_focused_remove_button_keeps_its_outline_and_stays_whole(
    small_window: OpenSmallWindow, window: Window
) -> None:
    page, _room = small_window(window)
    page.evaluate(
        "() => document.querySelector('[data-testid=\"salon-tab-players\"]').focus()"
    )

    reached: list[str] = []
    problems: list[str] = []
    for _ in range(REMOVE_BUTTON_COUNT):
        player_id = tab_to_next_remove_button(page)
        reached.append(player_id)
        problems.extend(focus_problems(page, player_id))

    assert reached == [f"p{number}" for number in range(2, 9)]
    assert problems == []


# ---- AC-9: the scans ---------------------------------------------------------------

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


def test_ac9_browser_the_remove_buttons_pass_the_contrast_scan(
    small_window: OpenSmallWindow,
) -> None:
    page, _room = small_window(SCAN_WINDOW)
    text = load_fr()["host.remove"]

    contrasts = remove_button_contrasts(page)

    scanned_players = sorted(contrast.player_id for contrast in contrasts)
    assert scanned_players == [f"p{number}" for number in range(2, 9)]
    for contrast in contrasts:
        assert contrast.text == text, contrast
        assert contrast.ratio >= MIN_TEXT_CONTRAST, contrast


def test_ac9_browser_the_remove_buttons_pass_the_language_scan(
    small_window: OpenSmallWindow,
) -> None:
    page, _room = small_window(SCAN_WINDOW)
    text = load_fr()["host.remove"]

    texts = page.evaluate(REMOVE_LANGUAGE_SCAN_SCRIPT)

    assert texts.count(text) == REMOVE_BUTTON_COUNT, texts
    for number in range(2, 9):
        label = expected_label(f"p{number}")
        assert texts.count(label) == 1, (label, texts)
    assert unknown_texts(texts, set()) == []


# ---- AC-9: static ---------------------------------------------------------------


def test_ac9_fr_json_holds_neither_the_compact_text_nor_the_unlock_label() -> None:
    fr = load_fr()

    assert "host.remove_short" not in fr
    assert "host.unlock" not in fr
