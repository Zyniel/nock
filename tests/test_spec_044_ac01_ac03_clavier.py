"""Tests of spec 044, AC-1 to AC-3: « Clavier » in the top bar.

AC-1: on a touch screen `keyboard-toggle` takes the phone top bar's fourth slot
(no `pencil-toggle` there) and comes after « Salon » in the computer top bar; off
a touch screen there is none. AC-2: a tap hides the keyboard and gives its room to
the grid, the browser remembers it, and the keyboard alone works it too. AC-3: a
phone held sideways is in the column layout while its keyboard is hidden.

Also tested, from "Edge cases and errors" and the rules of « Clavier »: a
`localStorage` that throws (the choice holds for the page's life), and a keyboard
activation on a phone held sideways, which changes the layout and keeps the focus
on `keyboard-toggle`.

Choices where the spec leaves room:

- "The buttons, left to right" (AC-1 at 1024 by 768) are the top bar's buttons
  that show, the timer and the brand left aside, sorted by their left edge.
- "`salon` is the open side column" (AC-3): `salon` shows without `hidden`, 340 px
  wide (0.5 px), its right edge on the window's right edge (1 px).
- "Nothing differs from an empty `localStorage`" (AC-2, desktop context): no
  `keyboard`, no `keyboard-toggle`, the same top-bar items that show and the same
  `data-layout` as a page opened with an empty `localStorage`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from room_panels import is_closed
from spec019_harness import OpenWindow, window_opener
from spec035_harness import Walker
from spec042_harness import box_of, colour_of, make_storage_throw
from spec043_harness import (
    NAVY,
    PHONE,
    PHONE_TOP_BAR_HEIGHT,
    colour_matches,
    expect_layout,
    focused_test_id,
    frames_sent_after,
    layout_of,
    open_room,
    reload_room,
    same_position,
    same_size,
    shown_test_ids,
    stored_value,
    style_of,
)
from spec044_harness import (
    COMPUTER,
    KEYBOARD_HIDDEN_KEY,
    LOW_TOUCH_IDS,
    LOW_TOUCH_WINDOWS,
    TABLET,
    TOUCH_COMPUTER_BUTTONS,
    TOUCH_PHONE_BUTTONS,
    bar_button_ids_left_to_right,
    cell_side,
    computer_clavier_problems,
    expect_keyboard_shows,
    expect_no_keyboard,
    fx01_frame,
    height_of,
    open_fx01,
    phone_clavier_problems,
    pressed_problems,
    settled_value,
    tap_toggle,
    window_height,
)

FOLLOW_MS = 300  # "within 300 ms"
SALON_WIDTH = 340.0

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_touch(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int] = PHONE,
) -> Page:
    """A FX-01 snapshot in the touch context, the keyboard shown."""
    page, _ = open_fx01(window, base_url, fx01_frame(grid), size)
    expect_keyboard_shows(page)
    return page


def larger_side(page: Page, side_before: float) -> float:
    """The side of (1, 1) once the grid has refitted to a larger side (5 s at most)."""
    return settled_value(
        page, lambda: cell_side(page, 1, 1), lambda side: side > side_before
    )


# ---- AC-1: « Clavier » in the top bar, on touch screens only ----


def test_ac1_the_phone_top_bar_of_a_touch_screen_has_clavier_in_its_fourth_slot(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid)

    shown = shown_test_ids(page.get_by_test_id("room-topbar"))

    assert shown == ["timer", *TOUCH_PHONE_BUTTONS]
    expect(page.get_by_test_id("pencil-toggle")).to_have_count(0)


def test_ac1_clavier_is_a_56_by_53_button_with_its_icon_above_its_label(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid)

    assert phone_clavier_problems(page) == []


def test_ac1_clavier_is_pressed_in_word_blue_while_the_keyboard_shows(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid)

    assert pressed_problems(page, pressed=True) == []


def test_ac1_on_a_touch_tablet_clavier_comes_between_salon_and_menu(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid, TABLET)
    expect_layout(page, "column")

    order = bar_button_ids_left_to_right(page)

    assert order == TOUCH_COMPUTER_BUTTONS


def test_ac1_on_a_touch_tablet_clavier_is_38_px_high_with_its_icon_beside_its_label(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid, TABLET)
    expect_layout(page, "column")

    assert computer_clavier_problems(page) == []
    assert pressed_problems(page, pressed=True) == []


@pytest.mark.parametrize(
    ("width", "height", "before"),
    [(360, 740, "chat-toggle"), (1280, 720, "undo-button")],
    ids=["360x740", "1280x720"],
)
def test_ac1_the_desktop_context_has_no_clavier_and_keeps_crayon_in_its_place(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    before: str,
) -> None:
    page, _ = open_fx01(
        window, live_server, fx01_frame(fx01_grid), (width, height), touch=False
    )

    shown = shown_test_ids(page.get_by_test_id("room-topbar"))

    expect(page.get_by_test_id("keyboard-toggle")).to_have_count(0)
    assert "pencil-toggle" in shown, shown
    assert shown[shown.index("pencil-toggle") - 1] == before, shown


# ---- AC-2: « Clavier » hides and shows the keyboard ----


def test_ac2_a_tap_on_clavier_hides_the_keyboard_and_gives_its_room_to_the_grid(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_fx01(window, live_server, fx01_frame(fx01_grid))
    expect_keyboard_shows(page)
    keyboard_height = height_of(page, "keyboard")
    viewport_height = height_of(page, "grid-viewport")

    sent = frames_sent_after(page, mock, lambda: tap_toggle(page))

    expect_no_keyboard(page, timeout=FOLLOW_MS)
    assert sent == []
    assert pressed_problems(page, pressed=False) == []
    assert stored_value(page, KEYBOARD_HIDDEN_KEY) == "true"
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    assert same_position(bar_box.bottom, window_height(page)), bar_box
    expected_height = viewport_height + keyboard_height
    new_height = settled_value(
        page,
        lambda: height_of(page, "grid-viewport"),
        lambda value: same_position(value, expected_height),
    )
    assert same_position(new_height, expected_height), (
        viewport_height,
        keyboard_height,
        new_height,
    )


def test_ac2_after_a_reload_the_keyboard_stays_hidden(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    frame = fx01_frame(fx01_grid)
    page, mock = open_fx01(window, live_server, frame)
    expect_keyboard_shows(page)
    tap_toggle(page)
    expect_no_keyboard(page)

    reload_room(page, mock, frame)

    expect_no_keyboard(page)
    expect(page.get_by_test_id("keyboard-toggle")).to_have_attribute(
        "aria-pressed", "false"
    )


def test_ac2_a_second_tap_shows_the_keyboard_again_and_removes_the_choice(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    frame = fx01_frame(fx01_grid)
    page, mock = open_fx01(window, live_server, frame)
    expect_keyboard_shows(page)
    viewport_height = height_of(page, "grid-viewport")
    tap_toggle(page)
    expect_no_keyboard(page)
    reload_room(page, mock, frame)
    expect_no_keyboard(page)

    tap_toggle(page)

    expect(page.locator('[data-testid="keyboard"]')).to_be_visible(timeout=FOLLOW_MS)
    expect(page.get_by_test_id("keyboard-toggle")).to_have_attribute(
        "aria-pressed", "true"
    )
    assert stored_value(page, KEYBOARD_HIDDEN_KEY) is None
    new_height = settled_value(
        page,
        lambda: height_of(page, "grid-viewport"),
        lambda value: same_position(value, viewport_height),
    )
    assert same_position(new_height, viewport_height), (viewport_height, new_height)


def test_ac2_clavier_reached_with_tab_shows_the_navy_ring(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid)
    toggle = page.get_by_test_id("keyboard-toggle")

    Walker(page).tab_to("keyboard-toggle")

    assert focused_test_id(page) == "keyboard-toggle"
    assert style_of(toggle, "outlineStyle") == "solid"
    assert style_of(toggle, "outlineWidth") == "2px"
    outline_colour = colour_of(toggle, "outlineColor")
    assert colour_matches(outline_colour, NAVY), outline_colour


def test_ac2_enter_hides_then_shows_the_keyboard_and_keeps_the_focus_on_clavier(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid)
    toggle = page.get_by_test_id("keyboard-toggle")
    Walker(page).tab_to("keyboard-toggle")

    page.keyboard.press("Enter")
    expect_no_keyboard(page, timeout=FOLLOW_MS)
    expect(toggle).to_be_focused()

    page.keyboard.press("Enter")
    expect_keyboard_shows(page)
    expect(toggle).to_be_focused()


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac2_on_a_phone_held_sideways_enter_and_space_keep_the_focus_on_clavier(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    # "After an activation from the keyboard (`Enter` or `Space`), the focus is on
    # `keyboard-toggle`, also when the layout changed."
    page = open_touch(window, live_server, fx01_grid, (width, height))
    toggle = page.get_by_test_id("keyboard-toggle")
    Walker(page).tab_to("keyboard-toggle")

    page.keyboard.press("Enter")
    expect_layout(page, "column")
    expect(toggle).to_be_focused()

    page.keyboard.press("Space")
    expect_layout(page, "sheet")
    expect_keyboard_shows(page)
    expect(toggle).to_be_focused()


@pytest.mark.parametrize(
    ("width", "height"), [PHONE, COMPUTER], ids=["360x740", "1280x720"]
)
def test_ac2_a_seeded_choice_changes_nothing_in_the_desktop_context(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    frame = fx01_frame(fx01_grid)
    plain, _ = open_fx01(window, live_server, frame, (width, height), touch=False)
    seeded, _ = open_fx01(
        window, live_server, frame, (width, height), touch=False, keyboard_hidden=True
    )

    plain_items = shown_test_ids(plain.get_by_test_id("room-topbar"))
    seeded_items = shown_test_ids(seeded.get_by_test_id("room-topbar"))

    for page in (plain, seeded):
        expect(page.get_by_test_id("keyboard")).to_have_count(0)
        expect(page.get_by_test_id("keyboard-toggle")).to_have_count(0)
    assert seeded_items == plain_items
    assert layout_of(seeded) == layout_of(plain)


def test_ac2_with_a_storage_that_throws_the_keyboard_shows_and_still_hides(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], True)
    make_storage_throw(page)
    open_room(page, live_server, fx01_frame(fx01_grid))
    expect_keyboard_shows(page)

    tap_toggle(page)
    expect_no_keyboard(page, timeout=FOLLOW_MS)
    tap_toggle(page)

    expect_keyboard_shows(page)


# ---- AC-3: a phone held sideways ----


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac3_a_phone_held_sideways_goes_to_the_column_layout_when_it_hides_the_keyboard(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_touch(window, live_server, fx01_grid, (width, height))
    expect_layout(page, "sheet")
    side_before = cell_side(page, 1, 1)

    tap_toggle(page)

    expect_layout(page, "column", timeout=FOLLOW_MS)
    expect_no_keyboard(page, timeout=FOLLOW_MS)
    salon = page.get_by_test_id("salon")
    expect(salon).to_be_visible()
    assert not is_closed(salon)
    salon_box = box_of(salon)
    assert same_size(salon_box.width, SALON_WIDTH), salon_box
    assert same_position(salon_box.right, float(width)), salon_box
    assert larger_side(page, side_before) > side_before


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac3_with_the_keyboard_hidden_sideways_the_top_bar_stays_the_phone_bar(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_touch(window, live_server, fx01_grid, (width, height))
    top_bar = page.get_by_test_id("room-topbar")

    tap_toggle(page)
    expect_layout(page, "column", timeout=FOLLOW_MS)

    shown = shown_test_ids(top_bar)
    assert same_size(box_of(top_bar).height, PHONE_TOP_BAR_HEIGHT)
    assert "topbar-brand" not in shown
    assert shown == ["timer", *TOUCH_PHONE_BUTTONS]
    expect(page.get_by_test_id("pencil-toggle")).to_have_count(0)
    expect(page.get_by_test_id("keyboard-toggle")).to_have_attribute(
        "aria-pressed", "false"
    )


@pytest.mark.parametrize(("width", "height"), LOW_TOUCH_WINDOWS, ids=LOW_TOUCH_IDS)
def test_ac3_a_second_tap_sideways_brings_back_the_sheet_layout_and_the_keyboard(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = open_touch(window, live_server, fx01_grid, (width, height))
    tap_toggle(page)
    expect_layout(page, "column")

    tap_toggle(page)

    expect_layout(page, "sheet", timeout=FOLLOW_MS)
    expect(page.locator('[data-testid="keyboard"]')).to_be_visible(timeout=FOLLOW_MS)


def test_ac3_on_a_touch_tablet_hiding_the_keyboard_keeps_the_column_and_grows_the_cells(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_touch(window, live_server, fx01_grid, TABLET)
    expect_layout(page, "column")
    side_before = cell_side(page, 1, 1)

    tap_toggle(page)
    expect_no_keyboard(page, timeout=FOLLOW_MS)

    expect_layout(page, "column")
    assert larger_side(page, side_before) > side_before
