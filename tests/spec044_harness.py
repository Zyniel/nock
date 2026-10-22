"""Shared setup of the tests of spec 044: the keyboard.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 044 uses: the values of the spec, the
snapshots of its "Test harness" (`SOLVED`, `FULL_WRONG`), the helpers that open
the room in the touch or the desktop context, and the readers of the keyboard,
its keys and the top-bar buttons. The tests are in these files, one per group of
criteria:

- `test_spec_044_ac01_ac03_clavier.py`: AC-1 to AC-3 (« Clavier »).
- `test_spec_044_ac04_ac05_keys.py`: AC-4 and AC-5 (rows, keys, low windows).
- `test_spec_044_ac06_ac08_pencil_swap_delete.py`: AC-6 to AC-8 (✎, ⇄, ⌫).
- `test_spec_044_ac09_ac11_solved_status_scans.py`: AC-9 to AC-11.

It reuses spec 043's harness ("Browser with mocked socket": the mocked room, its
FX-01 snapshots, the box, colour and label readers) and spec 019's desktop and
touch windows, which are the contexts of spec 044's "Test harness". Every helper
that opens or reloads a page waits for the fonts before it returns (spec 041's
rule).
"""

from __future__ import annotations

import time
from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridSolved
from spec019_harness import OpenWindow
from spec042_harness import box_of
from spec043_harness import (
    FX01_SOLUTION,
    MUTED,
    NAVY,
    PHONE,
    SPEC043_JS,
    WORD,
    Box,
    Reading,
    RoomMock,
    colour_matches,
    fr_value,
    fx01_view,
    icon_problems,
    is_clear,
    letter_frame,
    letters_of,
    open_room,
    parts_of,
    players_up_to,
    reading_box,
    same_font_size,
    same_position,
    same_size,
    seed_value,
    shown_items,
    snapshot_frame,
    stroke_width_problems,
    to_box,
)

# ---- Values of the spec ------------------------------------------------------------

KEYBOARD_HIDDEN_KEY = "nock.keyboard_hidden"
TABLET = (1024, 768)
COMPUTER = (1280, 720)
LOW_TOUCH_WINDOWS = [(740, 360), (568, 320)]
LOW_TOUCH_IDS = ["740x360", "568x320"]

# The colours of the criteria (`_design.md` section 2, spec 041's tokens).
KEYBOARD_BG = (217, 222, 230)
KEY_BG = (233, 236, 241)
PENCIL = (85, 91, 103)
KEY_SHADOW_ALPHA = 0.25
PEN_FILL_ALPHA = 0.35

# The rows of the keyboard: the `data-key` values of their `key` elements.
LETTER_ROWS = ["AZERTYUIOP", "QSDFGHJKLM", "WXCVBN"]
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
# The keys of row 3 in order: `key-pencil`, six letter keys, `key-swap`,
# `key-delete` (a letter key is named by its letter here).
ROW_THREE = ["key-pencil", "W", "X", "C", "V", "B", "N", "key-swap", "key-delete"]
ICON_OF_KEY = {"key-pencil": "crayon", "key-swap": "swap", "key-delete": "effacer"}
ICON_KEYS = list(ICON_OF_KEY)

KEY_HEIGHT = 44.0
LOW_KEY_HEIGHT = 28.0
KEYBOARD_HEIGHT = 158.0
LOW_KEYBOARD_HEIGHT = 110.0
KEY_GAP = 4.0
ROW_GAP = 6.0
KEYBOARD_PADDING_TOP = 6.0
KEYBOARD_PADDING_BOTTOM = 8.0
ICON_SIDE = 22.0
ICON_STROKE = 1.8

# The phone top bar of a touch screen, after `timer` (AC-1).
TOUCH_PHONE_BUTTONS = [
    "undo-button",
    "aide-button",
    "chat-toggle",
    "keyboard-toggle",
    "menu-button",
]
# The computer top bar of a touch screen, left to right (AC-1).
TOUCH_COMPUTER_BUTTONS = [
    "undo-button",
    "pencil-toggle",
    "aide-button",
    "chat-toggle",
    "keyboard-toggle",
    "menu-button",
]
# The top-bar items that are not one of its five or six buttons.
NOT_BAR_BUTTONS = ("timer", "timer-show", "topbar-brand")

# ---- Snapshots ---------------------------------------------------------------------

# `FULL_WRONG`'s wrong cell: (4, 4) holds `X`, its solution being `T`.
WRONG_CELL = (4, 4)


def fx01_frame(grid: Grid) -> str:
    """A FX-01 snapshot with no letter: `seq` 5, `you` `p1` among `p1` to `p3`."""
    return snapshot_frame(fx01_view(grid), players_up_to(3))


def solved_frame(grid: Grid) -> str:
    """`SOLVED`: the 18 letter cells hold their solution, `solved` true."""
    view = fx01_view(grid, letters_of(list(FX01_SOLUTION)))
    return snapshot_frame(view, players_up_to(3), solved=True)


def full_wrong_frame(grid: Grid) -> str:
    """`FULL_WRONG`: as `SOLVED` with `X` at (4, 4), `solved` false."""
    changes = letters_of(list(FX01_SOLUTION))
    row, column = WRONG_CELL
    changes.append((row, column, {"letter": "X", "author": "p1"}))
    return snapshot_frame(fx01_view(grid, changes), players_up_to(3))


def solve_frames() -> list[str]:
    """`p2` writes `T` at (4, 4) (seq 6), then the grid is solved (seq 7)."""
    row, column = WRONG_CELL
    return [
        letter_frame(6, row, column, "T", "p2"),
        GridSolved(seq=7, elapsed_ms=60_000).model_dump_json(),
    ]


# ---- Opening the room --------------------------------------------------------------


def open_fx01(
    window: OpenWindow,
    base_url: str,
    frame: str,
    size: tuple[int, int] = PHONE,
    *,
    touch: bool = True,
    keyboard_hidden: bool = False,
) -> tuple[Page, RoomMock]:
    """Open the room on a snapshot, by default in the touch context at 360 by 740.

    Args:
        window: The `window` fixture (spec 019's desktop and touch contexts).
        base_url: The live server.
        frame: The snapshot (`fx01_frame`, `solved_frame`, `full_wrong_frame`).
        size: The window, as (width, height).
        touch: Whether the context is the touch context.
        keyboard_hidden: Whether `nock.keyboard_hidden` is seeded `"true"` before
            the first load.

    Returns:
        The page, once it shows the snapshot and its fonts, and the mocked socket.
    """
    width, height = size
    page = window(width, height, touch)
    if keyboard_hidden:
        seed_value(page, KEYBOARD_HIDDEN_KEY, "true")
    mock = open_room(page, base_url, frame)
    return page, mock


def keyboard_of(page: Page) -> Locator:
    return page.get_by_test_id("keyboard")


def key_of(page: Page, letter: str) -> Locator:
    """The letter key `letter` (`data-testid="key"`, `data-key`)."""
    return page.locator(f'[data-testid="key"][data-key="{letter}"]')


def expect_keyboard_shows(page: Page) -> None:
    """Wait until `keyboard` is on the page and shows."""
    expect(keyboard_of(page)).to_be_visible()


def expect_no_keyboard(page: Page, timeout: int = 5000) -> None:
    """Wait until no `keyboard` element is on the page."""
    expect(keyboard_of(page)).to_have_count(0, timeout=timeout)


def tap_toggle(page: Page) -> float:
    """Tap `keyboard-toggle`; return the moment the tap was done (`time.monotonic`)."""
    page.get_by_test_id("keyboard-toggle").tap()
    return time.monotonic()


def cell_side(page: Page, row: int, column: int) -> float:
    """The width of a cell's box."""
    cell = page.locator(
        f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    )
    return box_of(cell).width


def height_of(page: Page, test_id: str) -> float:
    return box_of(page.get_by_test_id(test_id)).height


FOLLOW_MS = 300  # "within 300 ms" (AC-2, AC-3: the layout and the grid's fit)
POLL_MS = 50


def settled_value(
    page: Page,
    read: Callable[[], float],
    accept: Callable[[float], bool],
    tapped_at: float,
) -> float:
    """Read a measure until `accept` takes it, up to 300 ms after the tap.

    The grid refits as on a resize (spec 006), a moment after the layout changes,
    so a measure of the grid is read again until it settles, which keeps the check
    from depending on a synchronous refit. `tapped_at` is the `time.monotonic()`
    that `tap_toggle` returned; the last reading is made when the 300 ms of AC-2
    and AC-3 are over. The caller asserts on the value returned, so a measure that
    has not settled by then fails there.

    Returns:
        The first reading that `accept` takes, else the last reading.
    """
    deadline = tapped_at + FOLLOW_MS / 1000
    value = read()
    while not accept(value):
        remaining_ms = (deadline - time.monotonic()) * 1000
        if remaining_ms <= 0:
            break
        page.wait_for_timeout(min(POLL_MS, remaining_ms))
        value = read()
    return value


def window_height(page: Page) -> float:
    height = page.evaluate("() => innerHeight")
    assert isinstance(height, int | float), height
    return float(height)


def page_scroll_problems(page: Page) -> list[str]:
    """How the page scrolls: vertically or horizontally (empty when it does not)."""
    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, innerWidth,"
        " document.documentElement.scrollHeight, innerHeight]"
    )
    assert isinstance(sizes, list), sizes
    scroll_width, inner_width, scroll_height, inner_height = sizes
    problems: list[str] = []
    if scroll_width > inner_width:
        problems.append(f"the page scrolls sideways: {scroll_width} > {inner_width}")
    if scroll_height > inner_height:
        problems.append(f"the page scrolls down: {scroll_height} > {inner_height}")
    return problems


# ---- The keyboard's readings -------------------------------------------------------

# The keyboard: its box, background and padding, then each `keyboard-row` with its
# box and each of its buttons in document order. A key's `letter` is the style of
# the element holding its text (the key itself when the text is its own).
KEYBOARD_SCRIPT = "keyboard => {\n" + SPEC043_JS + r"""
function keyOf(element) {
  const style = getComputedStyle(element);
  const svgs = [];
  for (const svg of element.querySelectorAll('svg')) {
    const reading = svgOf(svg);
    const widths = [];
    for (const child of svg.children) {
      widths.push(getComputedStyle(child).strokeWidth);
    }
    reading.strokeWidths = widths;
    svgs.push(reading);
  }
  const nodes = labelNodes(element);
  const holder = nodes.length === 0 ? element : nodes[0].parentElement;
  const letterStyle = getComputedStyle(holder);
  return {
    testId: element.getAttribute('data-testid'),
    dataKey: element.getAttribute('data-key'),
    tag: element.tagName,
    type: element.getAttribute('type'),
    text: element.textContent.trim(),
    box: boxOf(element),
    radius: style.borderTopLeftRadius,
    borderWidths: [style.borderTopWidth, style.borderRightWidth,
      style.borderBottomWidth, style.borderLeftWidth],
    background: parseColour(style.backgroundColor),
    colour: parseColour(style.color),
    fontStyle: style.fontStyle,
    letter: {
      colour: parseColour(letterStyle.color),
      fontSize: letterStyle.fontSize,
      fontWeight: letterStyle.fontWeight,
      fontStyle: letterStyle.fontStyle,
      fontFamily: letterStyle.fontFamily,
    },
    svgs: svgs,
  };
}
const style = getComputedStyle(keyboard);
const rows = [];
for (const row of keyboard.querySelectorAll('[data-testid="keyboard-row"]')) {
  const keys = [];
  for (const button of row.querySelectorAll('button')) {
    keys.push(keyOf(button));
  }
  rows.push({box: boxOf(row), keys: keys});
}
return {
  box: boxOf(keyboard),
  background: parseColour(style.backgroundColor),
  padding: [style.paddingTop, style.paddingRight, style.paddingBottom,
    style.paddingLeft].join(' '),
  rows: rows,
};
}"""


def read_keyboard(page: Page) -> Reading:
    """The keyboard's box, background, padding, rows and keys (`KEYBOARD_SCRIPT`)."""
    found = keyboard_of(page).evaluate(KEYBOARD_SCRIPT)
    assert isinstance(found, dict), found
    return found


def all_keys(keyboard: Reading) -> list[Reading]:
    """Every key of a keyboard reading, row after row."""
    keys: list[Reading] = []
    for row in keyboard["rows"]:
        keys.extend(row["keys"])
    return keys


def key_name(key: Reading) -> str:
    """A key's name in `ROW_THREE`'s terms: its letter, or its test id."""
    if key["testId"] == "key":
        return str(key["dataKey"])
    return str(key["testId"])


def letter_keys(keyboard: Reading) -> list[Reading]:
    """The 26 letter keys (`data-testid="key"`) of a keyboard reading."""
    found: list[Reading] = []
    for key in all_keys(keyboard):
        if key["testId"] == "key":
            found.append(key)
    return found


def keys_named(keyboard: Reading, test_id: str) -> list[Reading]:
    found: list[Reading] = []
    for key in all_keys(keyboard):
        if key["testId"] == test_id:
            found.append(key)
    return found


def key_height_problems(keyboard: Reading, expected: float) -> list[str]:
    """How the keys' heights differ from `expected` (0.5 px)."""
    problems: list[str] = []
    for key in all_keys(keyboard):
        box = reading_box(key)
        if not same_size(box.height, expected):
            problems.append(f"{key_name(key)}: {box.height} px high, not {expected}")
    return problems


def icon_key_problems(key: Reading, stroke: tuple[int, int, int]) -> list[str]:
    """How an icon key's one `svg` differs from its 22 px icon stroked in `stroke`."""
    name = key_name(key)
    svgs: list[Reading] = key["svgs"]
    if len(svgs) != 1:
        return [f"{name}: {len(svgs)} svg elements, expected 1"]
    svg = svgs[0]
    problems: list[str] = []
    box = reading_box(svg)
    if not (same_size(box.width, ICON_SIDE) and same_size(box.height, ICON_SIDE)):
        problems.append(f"{name}: icon {box.width} by {box.height}")
    if svg["ariaHidden"] != "true":
        problems.append(f"{name}: icon aria-hidden {svg['ariaHidden']!r}")
    problems.extend(icon_problems(svg, ICON_OF_KEY[name]))
    problems.extend(stroke_width_problems(svg, ICON_STROKE))
    for shape in svg["shapes"]:
        colour = shape["strokeColour"]
        if colour is None or not colour_matches(colour, stroke):
            problems.append(f"{name}: {shape['tag']} stroke {shape['stroke']}")
    return problems


# ---- Top-bar buttons ---------------------------------------------------------------


def bar_buttons(page: Page) -> list[Reading]:
    """The top bar's buttons that show (not the timer), in document order."""
    found: list[Reading] = []
    for item in shown_items(page.get_by_test_id("room-topbar")):
        if item["tag"] != "BUTTON" or item["testId"] in NOT_BAR_BUTTONS:
            continue
        found.append(item)
    return found


def bar_button_ids_left_to_right(page: Page) -> list[str]:
    """The test ids of the top bar's buttons that show, sorted by their left edge."""
    buttons = bar_buttons(page)
    buttons.sort(key=lambda item: to_box(item["box"]).left)
    return [str(item["testId"]) for item in buttons]


def clavier_label_problems(label: Reading | None, font_size: float) -> list[str]:
    """How `keyboard-toggle`'s label differs from « Clavier », 500, navy."""
    if label is None:
        return ["keyboard-toggle: no label"]
    problems: list[str] = []
    expected_text = fr_value("keyboard.label")
    if label["text"] != expected_text:
        problems.append(f"label {label['text']!r}, not {expected_text!r}")
    size = float(str(label["fontSize"]).removesuffix("px"))
    if not same_font_size(size, font_size):
        problems.append(f"label size {size}, not {font_size}")
    if label["fontWeight"] != "500":
        problems.append(f"label weight {label['fontWeight']}")
    if not colour_matches(label["colour"], NAVY):
        problems.append(f"label colour {label['colour']}")
    return problems


def clavier_icon(parts: Reading, side: float) -> tuple[Box | None, list[str]]:
    """The box of `keyboard-toggle`'s one `svg`, checked against `ICONS.clavier`."""
    svgs: list[Reading] = parts["svgs"]
    if len(svgs) != 1:
        return None, [f"{len(svgs)} svg elements, expected 1"]
    svg = svgs[0]
    box = reading_box(svg)
    problems: list[str] = []
    if not (same_size(box.width, side) and same_size(box.height, side)):
        problems.append(f"icon {box.width} by {box.height}, not {side}")
    if svg["ariaHidden"] != "true":
        problems.append(f"icon aria-hidden {svg['ariaHidden']!r}")
    problems.extend(icon_problems(svg, "clavier"))
    problems.extend(stroke_width_problems(svg, ICON_STROKE))
    return box, problems


def phone_clavier_problems(page: Page) -> list[str]:
    """How `keyboard-toggle` differs from a phone top-bar button (AC-1).

    A `BUTTON` of type `button`, 56 px wide (0.5 px) and 53 px high (1 px), its
    22 px `clavier` icon above its 10.88 px label.
    """
    parts = parts_of(page.get_by_test_id("keyboard-toggle"))
    problems: list[str] = []
    if parts["tag"] != "BUTTON" or parts["type"] != "button":
        problems.append(f"a {parts['tag']} of type {parts['type']!r}")
    box = reading_box(parts)
    if not same_size(box.width, 56.0):
        problems.append(f"width {box.width}, not 56")
    if not same_position(box.height, 53.0):
        problems.append(f"height {box.height}, not 53")
    icon_box, found = clavier_icon(parts, ICON_SIDE)
    problems.extend(found)
    label = parts["label"]
    problems.extend(clavier_label_problems(label, 10.88))
    if icon_box is not None and label is not None:
        label_box = to_box(label["box"])
        if icon_box.bottom > label_box.top + 1.0:
            problems.append(f"icon bottom {icon_box.bottom} under the label's top")
    return problems


def computer_clavier_problems(page: Page) -> list[str]:
    """How `keyboard-toggle` differs from a computer top-bar button (AC-1).

    38 px high (0.5 px), its 20 px `clavier` icon left of its 14.72 px label.
    """
    parts = parts_of(page.get_by_test_id("keyboard-toggle"))
    problems: list[str] = []
    if parts["tag"] != "BUTTON" or parts["type"] != "button":
        problems.append(f"a {parts['tag']} of type {parts['type']!r}")
    box = reading_box(parts)
    if not same_size(box.height, 38.0):
        problems.append(f"height {box.height}, not 38")
    icon_box, found = clavier_icon(parts, 20.0)
    problems.extend(found)
    label = parts["label"]
    problems.extend(clavier_label_problems(label, 14.72))
    if icon_box is not None and label is not None:
        label_box = to_box(label["box"])
        if icon_box.right > label_box.left + 1.0:
            problems.append(f"icon right {icon_box.right} past the label's left")
    return problems


def pressed_problems(page: Page, pressed: bool) -> list[str]:
    """`keyboard-toggle`'s `aria-pressed` and background: word blue or clear."""
    toggle = page.get_by_test_id("keyboard-toggle")
    problems: list[str] = []
    expected = "true" if pressed else "false"
    actual = toggle.get_attribute("aria-pressed")
    if actual != expected:
        problems.append(f"aria-pressed {actual!r}, not {expected!r}")
    background = parts_of(toggle)["background"]
    if pressed and not colour_matches(background, WORD):
        problems.append(f"background {background}, not word blue")
    if not pressed and not is_clear(background):
        problems.append(f"background {background}, not transparent")
    return problems


def disabled_clavier_problems(page: Page) -> list[str]:
    """How `keyboard-toggle` differs from spec 043's disabled top-bar look."""
    toggle = page.get_by_test_id("keyboard-toggle")
    parts = parts_of(toggle)
    problems: list[str] = []
    if parts["disabled"] is not True:
        problems.append("keyboard-toggle is not disabled")
    if toggle.get_attribute("aria-pressed") != "false":
        problems.append(f"aria-pressed {toggle.get_attribute('aria-pressed')!r}")
    label = parts["label"]
    if label is None or not colour_matches(label["colour"], MUTED):
        problems.append(f"label {label}")
    return problems
