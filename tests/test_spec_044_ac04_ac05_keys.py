"""Tests of spec 044, AC-4 and AC-5: the keyboard's rows, keys and colours, and its
lower keys on a low window.

AC-4: at 360 by 740 in the touch context the keyboard spans the window under the
clue bar, on its `--nock-keyboard-bg` background, with its three rows (AZERTY,
then ✎ W X C V B N ⇄ ⌫), each key a 44 px `--nock-key` button with its shadow,
the letters in the UI font and the three icons of `ICONS`; at 1024 by 768 (column
layout, Salon open) it spans the play area, 10 px under the clue bar, with 33 px
letter keys and centred rows. AC-5: on a low window (740 by 360, 568 by 320) the
keys are 28 px high and the keyboard 110 px, so the grid keeps 100 px.

Also tested, from "Edge cases and errors": at 320 px wide the letter keys of rows
1 and 2 shrink to 27.8 px, still above 24 px.

Choices where the spec leaves room:

- A key is each `button` of a `keyboard-row`, in document order; "left to right"
  compares the left edges of their boxes.
- "Each letter key shows its letter with ..." reads the computed style of the
  element holding the letter's text (the key itself when the text is its own).
- "The centre of each row" (1024 by 768) is the middle of its keys' span, from
  the first key's left edge to the last key's right edge.
- "The play area's left edge" at 1024 by 768 is the window's left edge: the play
  area is the room left of the Salon (spec 043, "Play area and fit").
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Page

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec041_harness import shadow_of
from spec042_harness import box_of, font_families
from spec043_harness import (
    INK,
    PHONE,
    Reading,
    colour_matches,
    expect_layout,
    press_cell,
    reading_box,
    same_font_size,
    same_position,
    same_size,
    to_box,
)
from spec044_harness import (
    ICON_KEYS,
    KEY_BG,
    KEY_GAP,
    KEY_HEIGHT,
    KEY_SHADOW_ALPHA,
    KEYBOARD_BG,
    KEYBOARD_HEIGHT,
    KEYBOARD_PADDING_BOTTOM,
    KEYBOARD_PADDING_TOP,
    LETTER_ROWS,
    LOW_KEY_HEIGHT,
    LOW_KEYBOARD_HEIGHT,
    LOW_TOUCH_IDS,
    LOW_TOUCH_WINDOWS,
    ROW_GAP,
    ROW_THREE,
    TABLET,
    all_keys,
    expect_keyboard_shows,
    fx01_frame,
    icon_key_problems,
    key_height_problems,
    key_name,
    keyboard_of,
    keys_named,
    open_fx01,
    page_scroll_problems,
    read_keyboard,
    window_height,
)

ROW_LETTER_WIDTH = 31.8  # each key of rows 1 and 2 at 360 by 740
WIDE_KEY_WIDTH = 48.0  # `key-pencil` and `key-delete`
ROW_THREE_WIDTH = 32.3  # the six letter keys of row 3 and `key-swap`
TABLET_LETTER_WIDTH = 33.0
NARROW_LETTER_WIDTH = 27.8  # rows 1 and 2 at 320 px wide (edge case)
CLUE_BAR_GAP = 10.0  # the column layout's keyboard, 10 px under the block above
MIN_GRID_VIEWPORT_PX = 100.0
LETTER_FONT_PX = 20.8  # 1.3rem
NARROW_WINDOW = (320, 568)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_keyboard(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int] = PHONE
) -> tuple[Page, Reading]:
    """A FX-01 snapshot in the touch context; the page and its keyboard's reading."""
    page, _ = open_fx01(window, base_url, fx01_frame(grid), size)
    expect_keyboard_shows(page)
    return page, read_keyboard(page)


def gap_problems(row: Reading, index: int) -> list[str]:
    """How the keys of a row are not 4 px apart, left to right (1 px)."""
    problems: list[str] = []
    boxes = [reading_box(key) for key in row["keys"]]
    for previous, following in pairwise(boxes):
        gap = following.left - previous.right
        if not same_position(gap, KEY_GAP):
            problems.append(f"row {index + 1}: a gap of {gap} px")
    return problems


def width_problems(keys: list[Reading], expected: float) -> list[str]:
    problems: list[str] = []
    for key in keys:
        width = reading_box(key).width
        if not same_size(width, expected):
            problems.append(f"{key_name(key)}: {width} px wide, not {expected}")
    return problems


# ---- AC-4: rows, keys and colours at 360 by 740 ----


def test_ac4_the_keyboard_spans_the_window_from_the_clue_bar_to_the_bottom(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, keyboard = open_keyboard(window, live_server, fx01_grid)

    box = reading_box(keyboard)
    bar_box = box_of(page.get_by_test_id("clue-bar"))

    assert same_size(box.width, 360.0), box
    assert same_position(box.left, 0.0), box
    assert same_position(box.bottom, window_height(page)), box
    assert same_position(box.top, bar_box.bottom), (box, bar_box)


def test_ac4_the_keyboard_has_its_background_and_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)

    assert colour_matches(keyboard["background"], KEYBOARD_BG), keyboard["background"]
    assert keyboard["padding"] == "6px 3px 8px 3px"


def test_ac4_the_three_rows_are_6_px_apart_inside_the_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)
    box = reading_box(keyboard)

    rows = [reading_box(row) for row in keyboard["rows"]]

    assert len(rows) == 3
    assert same_position(rows[0].top, box.top + KEYBOARD_PADDING_TOP), rows
    for previous, following in pairwise(rows):
        assert same_position(following.top, previous.bottom + ROW_GAP), rows
    assert same_position(rows[-1].bottom, box.bottom - KEYBOARD_PADDING_BOTTOM), rows


def test_ac4_rows_one_and_two_hold_the_azerty_letter_keys(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)

    rows: list[str] = []
    for row in keyboard["rows"][:2]:
        letters = ""
        for key in row["keys"]:
            assert key["testId"] == "key", key_name(key)
            letters += str(key["dataKey"])
        rows.append(letters)

    assert rows == LETTER_ROWS[:2]


def test_ac4_row_three_holds_pencil_six_letters_swap_and_delete_in_order(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)
    keys: list[Reading] = keyboard["rows"][2]["keys"]

    in_document_order = [key_name(key) for key in keys]
    by_left_edge = sorted(keys, key=lambda key: reading_box(key).left)
    left_to_right = [key_name(key) for key in by_left_edge]

    assert in_document_order == ROW_THREE
    assert left_to_right == ROW_THREE


def test_ac4_in_each_row_the_keys_are_4_px_apart(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)

    problems: list[str] = []
    for index, row in enumerate(keyboard["rows"]):
        problems.extend(gap_problems(row, index))

    assert problems == []


def test_ac4_every_key_is_a_44_px_button_with_the_key_look(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)
    keys = all_keys(keyboard)

    problems = key_height_problems(keyboard, KEY_HEIGHT)
    for key in keys:
        name = key_name(key)
        if key["tag"] != "BUTTON" or key["type"] != "button":
            problems.append(f"{name}: a {key['tag']} of type {key['type']!r}")
        if key["radius"] != "5px":
            problems.append(f"{name}: radius {key['radius']}")
        if key["borderWidths"] != ["0px", "0px", "0px", "0px"]:
            problems.append(f"{name}: borders {key['borderWidths']}")
        if not colour_matches(key["background"], KEY_BG):
            problems.append(f"{name}: background {key['background']}")

    assert len(keys) == 29
    assert problems == []


def test_ac4_every_key_has_a_1_px_shadow_in_the_key_shadow_colour(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_keyboard(window, live_server, fx01_grid)
    buttons = keyboard_of(page).get_by_test_id("keyboard-row").locator("button")

    problems: list[str] = []
    for index in range(buttons.count()):
        shadow = shadow_of(buttons.nth(index))
        if (shadow.x, shadow.y, shadow.blur) != (0, 1, 0):
            problems.append(f"button {index}: box-shadow {shadow.text}")
        if shadow.colour is None or not colour_matches(
            shadow.colour, INK, KEY_SHADOW_ALPHA
        ):
            problems.append(f"button {index}: shadow colour {shadow.colour}")

    assert buttons.count() == 29
    assert problems == []


def test_ac4_the_keys_have_the_widths_of_their_rows(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)
    rows = keyboard["rows"]
    row_three: list[Reading] = rows[2]["keys"]
    narrow_keys: list[Reading] = []
    for key in row_three:
        if key["testId"] in ("key", "key-swap"):
            narrow_keys.append(key)

    problems = width_problems([*rows[0]["keys"], *rows[1]["keys"]], ROW_LETTER_WIDTH)
    problems.extend(width_problems(keys_named(keyboard, "key-pencil"), WIDE_KEY_WIDTH))
    problems.extend(width_problems(keys_named(keyboard, "key-delete"), WIDE_KEY_WIDTH))
    problems.extend(width_problems(narrow_keys, ROW_THREE_WIDTH))

    assert len(narrow_keys) == 7
    assert problems == []


def test_ac4_each_letter_key_shows_its_letter_in_the_key_font(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)

    problems: list[str] = []
    letters_shown = ""
    for key in all_keys(keyboard):
        if key["testId"] != "key":
            continue
        letters_shown += str(key["text"])
        letter = key["letter"]
        name = key_name(key)
        if key["text"] != key["dataKey"]:
            problems.append(f"{name}: shows {key['text']!r}")
        if not colour_matches(letter["colour"], INK):
            problems.append(f"{name}: colour {letter['colour']}")
        size = float(str(letter["fontSize"]).removesuffix("px"))
        if not same_font_size(size, LETTER_FONT_PX):
            problems.append(f"{name}: font-size {size}")
        if letter["fontWeight"] != "500":
            problems.append(f"{name}: font-weight {letter['fontWeight']}")
        if letter["fontStyle"] != "normal":
            problems.append(f"{name}: font-style {letter['fontStyle']}")
        families = font_families(str(letter["fontFamily"]))
        if families[0] != "Source Sans 3":
            problems.append(f"{name}: font-family {letter['fontFamily']}")

    assert len(letters_shown) == 26
    assert problems == []


@pytest.mark.parametrize("test_id", ICON_KEYS)
def test_ac4_each_icon_key_holds_its_22_px_ink_icon(
    window: OpenWindow, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid)
    keys = keys_named(keyboard, test_id)

    assert len(keys) == 1
    assert icon_key_problems(keys[0], INK) == []


# ---- AC-4: on a touch tablet (column layout) ----


def test_ac4_on_a_touch_tablet_the_keyboard_spans_the_play_area_under_the_clue_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, keyboard = open_keyboard(window, live_server, fx01_grid, TABLET)
    expect_layout(page, "column")

    box = reading_box(keyboard)
    salon_box = box_of(page.get_by_test_id("salon"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))

    assert same_position(box.left, 0.0), box
    assert same_position(box.right, salon_box.left), (box, salon_box)
    assert same_position(box.top, bar_box.bottom + CLUE_BAR_GAP), (box, bar_box)


def test_ac4_on_a_touch_tablet_letter_keys_are_33_px_and_each_row_is_centred(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, keyboard = open_keyboard(window, live_server, fx01_grid, TABLET)
    expect_layout(page, "column")
    box = reading_box(keyboard)

    letters: list[Reading] = []
    problems: list[str] = []
    for index, row in enumerate(keyboard["rows"]):
        keys: list[Reading] = row["keys"]
        for key in keys:
            if key["testId"] == "key":
                letters.append(key)
        span_left = to_box(keys[0]["box"]).left
        span_right = to_box(keys[-1]["box"]).right
        centre = (span_left + span_right) / 2
        if not same_position(centre, box.centre_x):
            problems.append(f"row {index + 1}: centre {centre}, not {box.centre_x}")
    problems.extend(width_problems(letters, TABLET_LETTER_WIDTH))

    assert len(letters) == 26
    assert problems == []


# ---- AC-4: edge case "Key widths on narrow windows" ----


def test_ac4_at_320_px_wide_the_letter_keys_of_rows_one_and_two_are_27_8_px(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    _, keyboard = open_keyboard(window, live_server, fx01_grid, NARROW_WINDOW)
    rows = keyboard["rows"]
    keys: list[Reading] = [*rows[0]["keys"], *rows[1]["keys"]]

    problems = width_problems(keys, NARROW_LETTER_WIDTH)

    assert len(keys) == 20
    assert problems == []


# ---- AC-5: lower keys on a low window ----


def open_low(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    """A FX-01 snapshot in the touch context with (3, 1) tapped."""
    page, _ = open_fx01(window, base_url, fx01_frame(grid), size)
    expect_keyboard_shows(page)
    press_cell(page, 3, 1, touch=True)
    return page


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac5_on_a_low_window_every_key_is_28_px_and_the_keyboard_110_px_high(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_low(window, live_server, fx01_grid, (width, height))

    keyboard = read_keyboard(page)
    box = reading_box(keyboard)

    assert key_height_problems(keyboard, LOW_KEY_HEIGHT) == []
    assert len(all_keys(keyboard)) == 29
    assert same_position(box.height, LOW_KEYBOARD_HEIGHT), box


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac5_on_a_low_window_the_grid_keeps_100_px_and_nothing_scrolls(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_low(window, live_server, fx01_grid, (width, height))

    viewport_box = box_of(page.get_by_test_id("grid-viewport"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    keyboard_box = box_of(keyboard_of(page))

    assert viewport_box.height >= MIN_GRID_VIEWPORT_PX, viewport_box
    assert bar_box.bottom <= keyboard_box.top + 1.0, (bar_box, keyboard_box)
    assert same_position(keyboard_box.bottom, window_height(page)), keyboard_box
    assert page_scroll_problems(page) == []


def test_ac5_at_360_by_740_every_key_is_44_px_and_the_keyboard_158_px_high(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_low(window, live_server, fx01_grid, PHONE)

    keyboard = read_keyboard(page)
    box = reading_box(keyboard)

    assert key_height_problems(keyboard, KEY_HEIGHT) == []
    assert same_position(box.height, KEYBOARD_HEIGHT), box
