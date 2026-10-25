"""Tests of spec 043, AC-2 to AC-4: the top bar.

AC-2: the phone top bar (360 by 740, and the low column-layout windows 740 by 360
and 568 by 320 of the desktop context) holds the timer and five buttons, each
56 by 53 px with its 22 px icon above its label. AC-3: the computer top bar (1280
by 720) holds the brand, the timer and five buttons, each 38 px high with its
20 px icon beside its label. AC-4: no top-bar button overflows on the narrow and
low windows, and the room's heading and status are visually hidden.

Choices where the spec leaves room:

- "Its children that show": the elements with a test id inside `room-topbar` that
  show (a box, `visibility: visible`), the outermost only, so `chat-unread` in
  `chat-toggle` or `aide-caret` in `aide-button` do not count; a wrapper of the
  timer slot without a test id is not seen.
- A button's label is its text outside its `svg` and outside any `aria-hidden`
  element; its box is the box of the text (a DOM range) and its font values those
  of the element that holds the text. "One `getClientRects()` line" is read on
  that range: all its rectangles have the same top (1 px).
- "The icon's bottom at or above the label's top" and "the icon's right at or left
  of the label's left" have the position tolerance of 1 px.
- The brand is the link « Accueil » to `/` (B-010, `client/hud.md` AC-2): an `A`
  with `href="/"`, role link and name `topbar.home`, no `aria-current`, its Nock
  mark hidden from assistive technology. Its box is larger than its content
  (`foundation.md`, « Brand link »), so "the brand 16 px in" is read on its Nock
  mark. "A click follows with no question": after the click the page is `/` with
  `catalogue-page`, and no dialog (a `beforeunload` question included) showed.
- AC-4's touch context with `nock.keyboard_hidden` seeded `"true"`: refined by
  spec 044 (the design's keyboard), which reads that key: the page there is in
  the column layout with the phone top bar (`keyboard-toggle` in its fourth slot),
  and the test checks that layout before the criterion's checks.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Dialog, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec042_harness import box_of, to_box
from spec043_harness import (
    COMPUTER_BUTTONS,
    COMPUTER_TOP_BAR_HEIGHT,
    H8_TIMER_MS,
    ICON_OF_BUTTON,
    LABEL_KEY_OF_BUTTON,
    LINE,
    LOW_WINDOWS,
    NAVY,
    PHONE_BUTTONS,
    PHONE_TOP_BAR_HEIGHT,
    SPEC043_JS,
    WHITE,
    WORD,
    Reading,
    border_problems,
    colour_matches,
    expect_brand_link,
    expect_colour,
    expect_layout,
    fr_format,
    fr_value,
    fx01_view,
    icon_problems,
    is_clear,
    label_of,
    open_room,
    parts_of,
    pictogram_of,
    players_up_to,
    reading_box,
    same_font_size,
    same_position,
    same_size,
    seed_value,
    shown_items,
    shown_test_ids,
    shows_pictogram,
    snapshot_frame,
    stroke_width_problems,
    style_of,
)

PHONE_BAR_SIZES = [(360, 740), *LOW_WINDOWS]
PHONE_BAR_IDS = [f"{width}x{height}" for width, height in PHONE_BAR_SIZES]
NOCK_MARK = "0,0 10,0 10,14 5,10 0,14"
MIN_BUTTON_WIDTH = 40.0

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_fx01(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    timer_ms: int = 0,
    running: bool = False,
) -> None:
    frame = snapshot_frame(
        fx01_view(grid),
        players_up_to(3),
        timer_elapsed_ms=timer_ms,
        timer_running=running,
    )
    open_room(page, base_url, frame)


def open_at(
    window: OpenWindow, base_url: str, grid: Grid, width: int, height: int
) -> Page:
    page = window(width, height, False)
    open_fx01(page, base_url, grid)
    return page


# ---- Checks of one button --------------------------------------------------------


def label_problems(test_id: str, label: Reading | None, font_size: float) -> list[str]:
    """How a top-bar button's label differs from its text, size, weight and navy."""
    if label is None:
        return [f"{test_id}: no label"]
    problems: list[str] = []
    expected_text = fr_value(LABEL_KEY_OF_BUTTON[test_id])
    if label["text"] != expected_text:
        problems.append(f"{test_id}: label {label['text']!r}, not {expected_text!r}")
    size = float(str(label["fontSize"]).removesuffix("px"))
    if not same_font_size(size, font_size):
        problems.append(f"{test_id}: label size {size}, not {font_size}")
    if label["fontWeight"] != "500":
        problems.append(f"{test_id}: label weight {label['fontWeight']}")
    if not colour_matches(label["colour"], NAVY):
        problems.append(f"{test_id}: label colour {label['colour']}")
    return problems


def one_icon(
    test_id: str, parts: Reading, side: float
) -> tuple[Reading | None, list[str]]:
    """The one `svg` of a button, checked for its side, its icon and `aria-hidden`."""
    svgs: list[Reading] = parts["svgs"]
    if len(svgs) != 1:
        return None, [f"{test_id}: {len(svgs)} svg elements, expected 1"]
    svg = svgs[0]
    problems: list[str] = []
    box = reading_box(svg)
    if not (same_size(box.width, side) and same_size(box.height, side)):
        problems.append(f"{test_id}: icon {box.width} by {box.height}, not {side}")
    if svg["ariaHidden"] != "true":
        problems.append(f"{test_id}: icon aria-hidden {svg['ariaHidden']!r}")
    problems.extend(icon_problems(svg, ICON_OF_BUTTON[test_id]))
    problems.extend(stroke_width_problems(svg, 1.8))
    return svg, problems


def phone_button_problems(page: Page, test_id: str, expanded: bool) -> list[str]:
    """How a phone top-bar button differs from AC-2.

    Args:
        page: The room page.
        test_id: The button.
        expanded: Whether the button must show AC-5's expanded look (`aria-expanded`
            `"true"`, background `WORD`) rather than a transparent background.
    """
    button = page.get_by_test_id(test_id)
    parts = parts_of(button)
    problems: list[str] = []
    if parts["tag"] != "BUTTON" or parts["type"] != "button":
        problems.append(f"{test_id}: a {parts['tag']} of type {parts['type']!r}")
    box = reading_box(parts)
    if not same_size(box.width, 56.0):
        problems.append(f"{test_id}: width {box.width}, not 56")
    if not same_position(box.height, 53.0):
        problems.append(f"{test_id}: height {box.height}, not 53")
    if expanded:
        if button.get_attribute("aria-expanded") != "true":
            problems.append(f"{test_id}: not aria-expanded")
        if not colour_matches(parts["background"], WORD):
            problems.append(f"{test_id}: background {parts['background']}, not WORD")
    elif not is_clear(parts["background"]):
        problems.append(f"{test_id}: background {parts['background']}")
    svg, icon_found = one_icon(test_id, parts, 22.0)
    problems.extend(icon_found)
    label = parts["label"]
    problems.extend(label_problems(test_id, label, 10.88))
    if svg is not None and label is not None:
        icon_box = reading_box(svg)
        label_box = to_box(label["box"])
        if icon_box.bottom > label_box.top + 1.0:
            problems.append(f"{test_id}: icon bottom {icon_box.bottom} under label top")
    return problems


def computer_button_problems(page: Page, test_id: str) -> list[str]:
    """How a computer top-bar button differs from AC-3 (its size, icon and label)."""
    parts = parts_of(page.get_by_test_id(test_id))
    problems: list[str] = []
    if parts["tag"] != "BUTTON" or parts["type"] != "button":
        problems.append(f"{test_id}: a {parts['tag']} of type {parts['type']!r}")
    box = reading_box(parts)
    if not same_size(box.height, 38.0):
        problems.append(f"{test_id}: height {box.height}, not 38")
    if parts["radius"] != "6px":
        problems.append(f"{test_id}: radius {parts['radius']}")
    if parts["paddingLeft"] != "12px" or parts["paddingRight"] != "12px":
        problems.append(
            f"{test_id}: padding {parts['paddingLeft']} {parts['paddingRight']}"
        )
    svg, icon_found = one_icon(test_id, parts, 20.0)
    problems.extend(icon_found)
    label = parts["label"]
    problems.extend(label_problems(test_id, label, 14.72))
    if svg is not None and label is not None:
        icon_box = reading_box(svg)
        label_box = to_box(label["box"])
        if icon_box.right > label_box.left + 1.0:
            problems.append(f"{test_id}: icon right {icon_box.right} past the label")
        if not same_position(icon_box.centre_y, label_box.centre_y):
            problems.append(f"{test_id}: icon and label centres differ")
    return problems


# ---- AC-2: the phone top bar -------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), PHONE_BAR_SIZES, ids=PHONE_BAR_IDS)
def test_ac2_the_phone_top_bar_is_a_white_54_px_header_across_the_window(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)
    top_bar = page.get_by_test_id("room-topbar")

    tag = top_bar.evaluate("element => element.tagName")
    box = box_of(top_bar)

    assert tag == "HEADER"
    assert same_position(box.left, 0.0), box
    assert same_position(box.top, 0.0), box
    assert same_size(box.width, float(width)), box
    assert same_size(box.height, PHONE_TOP_BAR_HEIGHT), box
    expect_colour(top_bar, "backgroundColor", WHITE)
    assert border_problems(top_bar, "Bottom", "1px", "solid", LINE) == []


@pytest.mark.parametrize(("width", "height"), PHONE_BAR_SIZES, ids=PHONE_BAR_IDS)
def test_ac2_the_phone_top_bar_shows_the_timer_then_the_five_buttons(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)

    shown = shown_test_ids(page.get_by_test_id("room-topbar"))

    assert shown == ["timer", *PHONE_BUTTONS]


@pytest.mark.parametrize(("width", "height"), PHONE_BAR_SIZES, ids=PHONE_BAR_IDS)
@pytest.mark.parametrize("test_id", PHONE_BUTTONS)
def test_ac2_each_phone_button_is_56_by_53_with_its_icon_above_its_label(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    test_id: str,
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)
    # In the column layout the Salon is open at load, so « Salon » has AC-5's
    # expanded look there (spec 043 AC-2, decision of 2026-10-22).
    expanded = test_id == "chat-toggle" and (width, height) in LOW_WINDOWS

    assert phone_button_problems(page, test_id, expanded) == []


@pytest.mark.parametrize(("width", "height"), PHONE_BAR_SIZES, ids=PHONE_BAR_IDS)
def test_ac2_the_timer_is_navy_tabular_text_and_the_bar_keeps_its_padding(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)
    timer = page.get_by_test_id("timer")

    size = float(style_of(timer, "fontSize").removesuffix("px"))
    timer_box = box_of(timer)
    menu_box = box_of(page.get_by_test_id("menu-button"))

    assert same_font_size(size, 18.4), size
    assert style_of(timer, "fontWeight") == "600"
    expect_colour(timer, "color", NAVY)
    assert style_of(timer, "fontVariantNumeric") == "tabular-nums"
    assert timer_box.left >= 10.0 - 1.0, timer_box
    assert same_position(menu_box.right, float(width) - 4.0), menu_box


@pytest.mark.parametrize(("width", "height"), LOW_WINDOWS, ids=PHONE_BAR_IDS[1:])
def test_ac2_the_low_desktop_windows_are_the_column_layout(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)

    expect_layout(page, "column")


# ---- AC-3: the computer top bar ------------------------------------------------------


def test_ac3_the_computer_top_bar_is_56_px_high_and_starts_with_the_brand(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    top_bar = page.get_by_test_id("room-topbar")

    box = box_of(top_bar)
    items = shown_items(top_bar)
    mark_box = box_of(page.get_by_test_id("topbar-brand").locator("svg"))

    assert same_size(box.height, COMPUTER_TOP_BAR_HEIGHT), box
    assert same_size(box.width, 1280.0), box
    assert items[0]["testId"] == "topbar-brand", items
    assert same_position(mark_box.left, box.left + 16.0), mark_box


def test_ac3_the_brand_is_the_link_accueil_to_home_with_no_aria_current(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    expect_brand_link(page.get_by_test_id("topbar-brand"), current=False)


def test_ac3_a_click_on_the_brand_loads_home_with_no_question(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    dialogs: list[str] = []

    def record(dialog: Dialog) -> None:
        dialogs.append(dialog.type)
        dialog.accept()

    page.on("dialog", record)
    page.get_by_test_id("topbar-brand").click()

    page.wait_for_url(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-page")).to_be_visible()
    assert dialogs == []


BRAND_SCRIPT = "brand => {\n" + SPEC043_JS + r"""
const svgs = brand.querySelectorAll('svg');
return {count: svgs.length, svg: svgs.length === 1 ? svgOf(svgs[0]) : null};
}"""


def test_ac3_the_brand_draws_the_nock_mark_in_navy(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    found = page.get_by_test_id("topbar-brand").evaluate(BRAND_SCRIPT)

    assert found["count"] == 1, found
    svg = found["svg"]
    box = reading_box(svg)
    assert svg["viewBox"] == "0 0 10 14", svg
    assert same_size(box.width, 12.0), box
    assert same_size(box.height, 18.0), box
    assert len(svg["shapes"]) == 1, svg
    polygon = svg["shapes"][0]
    assert polygon["tag"] == "polygon", polygon
    assert " ".join(str(polygon["attributes"].get("points")).split()) == NOCK_MARK
    assert polygon["fillColour"] is not None, polygon
    assert colour_matches(polygon["fillColour"], NAVY), polygon


def test_ac3_the_brand_text_is_the_app_title_in_navy_700_at_20_8_px(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    label = label_of(page.get_by_test_id("topbar-brand"))

    assert label is not None
    assert label["text"] == fr_value("app.title")
    assert label["fontWeight"] == "700"
    assert same_font_size(float(str(label["fontSize"]).removesuffix("px")), 20.8)
    assert colour_matches(label["colour"], NAVY), label


def test_ac3_the_timer_then_the_five_buttons_come_left_to_right_6_px_apart(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    shown = shown_test_ids(page.get_by_test_id("room-topbar"))
    timer_box = box_of(page.get_by_test_id("timer"))

    boxes = []
    for test_id in COMPUTER_BUTTONS:
        boxes.append(box_of(page.get_by_test_id(test_id)))

    assert shown == ["topbar-brand", "timer", *COMPUTER_BUTTONS]
    assert timer_box.right <= boxes[0].left - 10.0 + 1.0, (timer_box, boxes[0])
    for previous, following in pairwise(boxes):
        assert same_position(following.left - previous.right, 6.0), boxes
    assert same_position(boxes[-1].right, 1280.0 - 16.0), boxes[-1]


@pytest.mark.parametrize("test_id", COMPUTER_BUTTONS)
def test_ac3_each_computer_button_is_38_px_high_with_its_icon_beside_its_label(
    page: Page, live_server: str, fx01_grid: Grid, test_id: str
) -> None:
    open_fx01(page, live_server, fx01_grid)

    assert computer_button_problems(page, test_id) == []


def test_ac3_aide_button_ends_with_its_caret_pictogram(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    caret = page.get_by_test_id("aide-button").get_by_test_id("aide-caret")
    expect(caret).to_have_count(1)

    reading = pictogram_of(caret)

    assert reading["ariaHidden"] == "true"
    assert reading["textNodes"] == 0
    assert shows_pictogram(reading, "\N{BLACK DOWN-POINTING SMALL TRIANGLE}"), reading


@pytest.mark.parametrize(("width", "height"), LOW_WINDOWS, ids=PHONE_BAR_IDS[1:])
def test_ac3_a_low_column_layout_window_has_no_brand_and_a_54_px_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)
    top_bar = page.get_by_test_id("room-topbar")

    shown = shown_test_ids(top_bar)

    assert "topbar-brand" not in shown
    assert same_size(box_of(top_bar).height, PHONE_TOP_BAR_HEIGHT)


# ---- AC-4: no overflow, and the heading and status read but not seen -----------------

# Each case: its id, the window, the timer's value and whether it runs, the context
# and whether `nock.keyboard_hidden` is seeded.
OVERFLOW_CASES = [
    ("320x568-timer-10h", 320, 568, H8_TIMER_MS, True, False, False),
    ("283x640-timer-0", 283, 640, 0, False, False, False),
    ("568x320-desktop", 568, 320, H8_TIMER_MS, True, False, False),
    ("740x360-desktop", 740, 360, H8_TIMER_MS, True, False, False),
    ("568x320-touch-keyboard-hidden", 568, 320, H8_TIMER_MS, True, True, True),
    ("740x360-touch-keyboard-hidden", 740, 360, H8_TIMER_MS, True, True, True),
]

LINE_SCRIPT = r"""
element => {
  const range = document.createRange();
  range.selectNodeContents(element);
  const tops = [];
  for (const rect of range.getClientRects()) {
    if (rect.width === 0 && rect.height === 0) {
      continue;
    }
    if (!tops.some(top => Math.abs(top - rect.top) <= 1)) {
      tops.push(rect.top);
    }
  }
  return tops.length;
}
"""


def overflow_problems(page: Page) -> list[str]:
    """How the top bar breaks AC-4: buttons outside it, too narrow, labels cut."""
    top_bar = page.get_by_test_id("room-topbar")
    bar_box = box_of(top_bar)
    problems: list[str] = []
    for item in shown_items(top_bar):
        if item["tag"] != "BUTTON":
            continue
        test_id = str(item["testId"])
        box = to_box(item["box"])
        inside = (
            box.left >= bar_box.left - 1.0
            and box.right <= bar_box.right + 1.0
            and box.top >= bar_box.top - 1.0
            and box.bottom <= bar_box.bottom + 1.0
        )
        if not inside:
            problems.append(f"{test_id}: {box} is not inside the top bar {bar_box}")
        if box.width < MIN_BUTTON_WIDTH - 0.5:
            problems.append(f"{test_id}: {box.width} px wide")
        label = label_of(page.get_by_test_id(test_id))
        if label is None:
            problems.append(f"{test_id}: no label")
            continue
        if label["scrollWidth"] > label["clientWidth"] + 1:
            problems.append(f"{test_id}: label cut ({label['scrollWidth']})")
        if label["lines"] != 1:
            problems.append(f"{test_id}: label on {label['lines']} lines")
    return problems


@pytest.mark.parametrize(
    ("width", "height", "timer_ms", "running", "touch", "keyboard_hidden"),
    [case[1:] for case in OVERFLOW_CASES],
    ids=[case[0] for case in OVERFLOW_CASES],
)
def test_ac4_no_top_bar_button_overflows_and_the_page_never_scrolls_sideways(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    timer_ms: int,
    running: bool,
    touch: bool,
    keyboard_hidden: bool,
) -> None:
    page = window(width, height, touch)
    if keyboard_hidden:
        seed_value(page, "nock.keyboard_hidden", "true")
    open_fx01(page, live_server, fx01_grid, timer_ms=timer_ms, running=running)
    if keyboard_hidden:
        # Spec 044: with the keyboard hidden, a low window is the column layout.
        expect_layout(page, "column")
    timer = page.get_by_test_id("timer")

    problems = overflow_problems(page)
    timer_lines = timer.evaluate(LINE_SCRIPT)
    timer_box = box_of(timer)
    undo_box = box_of(page.get_by_test_id("undo-button"))
    scroll_width = page.evaluate("() => document.documentElement.scrollWidth")

    assert problems == []
    assert timer_lines == 1
    assert timer_box.right <= undo_box.left + 1.0, (timer_box, undo_box)
    assert scroll_width <= width


HIDDEN_BOX_SCRIPT = r"""
element => {
  const rect = element.getBoundingClientRect();
  return {
    hidden: element.classList.contains('visually-hidden'),
    width: rect.width,
    height: rect.height,
    text: element.textContent.trim(),
  };
}
"""


@pytest.mark.parametrize(("width", "height"), [(1280, 720), (360, 740)])
def test_ac4_the_heading_and_the_status_are_read_but_not_seen(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_at(window, live_server, fx01_grid, width, height)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")

    heading = room.locator("h1").evaluate(HIDDEN_BOX_SCRIPT)
    status = page.get_by_test_id("room-status").evaluate(HIDDEN_BOX_SCRIPT)

    assert heading["hidden"] is True, heading
    assert heading["width"] <= 1.0, heading
    assert heading["height"] <= 1.0, heading
    assert heading["text"] == fr_format("room.heading", code="ABC123")
    assert status["hidden"] is True, status
    assert status["width"] <= 1.0, status
    assert status["height"] <= 1.0, status
    assert status["text"] == fr_value("room.status.joined")
