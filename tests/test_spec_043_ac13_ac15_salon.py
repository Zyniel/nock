"""Tests of spec 043, AC-13 to AC-15: the Salon.

AC-13: on a wide window the Salon is a 340 px column, open by default and
remembered closed in `nock.salon_closed`. AC-14: on a phone it is a bottom sheet
over the play area, which moves nothing. AC-15: it shows the words' progress and
two tabs, « Discussion » and « Joueurs (N) ».

Also tested, from "Edge cases and errors": with a `localStorage` that throws, the
column opens at load and a click still closes it (AC-13).

Choices where the spec leaves room:

- "The cell side `s` of (1, 1)" is the width of its bounding box; "`s` grows"
  means by more than the 0.5 px of a size.
- AC-15's navy fill is read on painted pixels (a context with a device scale
  factor of 1): the pixel 1.5 px inside the fill's expected right end is navy and
  the pixel 1.5 px past it is the track's word blue. So the fill may be drawn by
  any element or pseudo-element.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec041_harness import shadow_of
from spec042_harness import box_of, colour_of, make_storage_throw, pixel_at
from spec043_harness import (
    HANDLE,
    INK,
    LINE,
    MUTED,
    NAVY,
    WHITE,
    WORD,
    border_problems,
    cell_at,
    colour_matches,
    expect_closed,
    expect_colour,
    fr_format,
    fr_value,
    fx01_view,
    is_clear,
    joined_frame,
    letters_of,
    open_room,
    player,
    players_up_to,
    press_cell,
    reload_room,
    same_box,
    same_font_size,
    same_position,
    same_size,
    seed_value,
    send_and_wait,
    snapshot_frame,
    stored_value,
    style_of,
)

SALON_KEY = "nock.salon_closed"

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def fx01_frame(grid: Grid) -> str:
    return snapshot_frame(fx01_view(grid), players_up_to(3))


def cell_side(page: Page) -> float:
    return box_of(cell_at(page, 1, 1)).width


def salon_inside_focus(page: Page) -> bool:
    found = page.evaluate(
        "() => document.querySelector('[data-testid=\"salon\"]')"
        ".contains(document.activeElement)"
    )
    assert isinstance(found, bool)
    return found


# ---- AC-13: the Salon column ---------------------------------------------------------


def test_ac13_on_a_wide_window_the_salon_is_an_open_340_px_column(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_frame(fx01_grid))
    salon = page.get_by_test_id("salon")
    expect(salon).to_be_visible()

    tag = salon.evaluate("element => element.tagName")
    box = box_of(salon)
    bar_box = box_of(page.get_by_test_id("room-topbar"))

    assert tag == "ASIDE"
    expect(salon).to_have_attribute("aria-label", fr_value("topbar.salon"))
    expect(salon).to_have_attribute("id", "salon")
    assert same_size(box.width, 340.0), box
    assert same_position(box.right, 1280.0), box
    assert same_position(box.top, bar_box.bottom), (box, bar_box)
    assert same_position(box.bottom, 720.0), box
    expect_colour(salon, "backgroundColor", WHITE)
    assert border_problems(salon, "Left", "1px", "solid", LINE) == []


def test_ac13_the_column_opened_at_load_takes_no_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_frame(fx01_grid))

    expect(page.get_by_test_id("chat-toggle")).to_have_attribute(
        "aria-expanded", "true"
    )
    assert salon_inside_focus(page) is False


def test_ac13_closing_the_column_is_remembered_and_gives_its_room_to_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    salon = page.get_by_test_id("salon")
    noted_side = cell_side(page)

    page.get_by_test_id("chat-toggle").click()
    expect_closed(salon)
    assert stored_value(page, SALON_KEY) == "true"
    assert cell_side(page) > noted_side + 0.5

    reload_room(page, mock, frame)
    expect_closed(salon)


def test_ac13_opening_the_column_again_forgets_the_key_and_focuses_the_input(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    noted_side = cell_side(page)
    page.get_by_test_id("chat-toggle").click()
    expect_closed(page.get_by_test_id("salon"))
    reload_room(page, mock, frame)

    page.get_by_test_id("chat-toggle").click()

    expect(page.get_by_test_id("salon")).to_be_visible()
    assert stored_value(page, SALON_KEY) is None
    expect(page.get_by_test_id("chat-input")).to_be_focused()
    assert same_position(cell_side(page), noted_side)


def test_ac13_escape_in_the_column_focuses_chat_toggle_and_leaves_it_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_frame(fx01_grid))
    page.get_by_test_id("chat-input").focus()

    page.keyboard.press("Escape")

    expect(page.get_by_test_id("chat-toggle")).to_be_focused()
    expect(page.get_by_test_id("salon")).to_be_visible()


def test_ac13_with_a_storage_that_throws_the_column_opens_and_still_closes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    make_storage_throw(page)
    open_room(page, live_server, fx01_frame(fx01_grid))
    salon = page.get_by_test_id("salon")
    expect(salon).to_be_visible()

    page.get_by_test_id("chat-toggle").click()

    expect_closed(salon)


# ---- AC-14: the Salon sheet ----------------------------------------------------------


def open_phone(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    page = window(360, 740, False)
    seed_value(page, SALON_KEY, "true")
    open_room(page, base_url, fx01_frame(grid))
    return page


def test_ac14_on_a_phone_the_salon_is_closed_at_load_whatever_the_key(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(360, 740, False)
    open_room(page, live_server, fx01_frame(fx01_grid))

    expect_closed(page.get_by_test_id("salon"))


def test_ac14_the_sheet_rises_from_the_bottom_with_its_corners_and_shadow(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)
    salon = page.get_by_test_id("salon")
    expect_closed(salon)

    page.get_by_test_id("chat-toggle").click()
    expect(salon).to_be_visible()

    box = box_of(salon)
    shadow = shadow_of(salon)
    assert same_position(box.bottom, 740.0), box
    assert same_size(box.width, 360.0), box
    assert same_position(box.height, 0.62 * 740), box
    assert style_of(salon, "borderTopLeftRadius") == "14px"
    assert style_of(salon, "borderTopRightRadius") == "14px"
    assert (shadow.x, shadow.y, shadow.blur, shadow.spread) == (0, -10, 30, -12)
    assert shadow.colour is not None
    assert colour_matches(shadow.colour, INK, 0.45), shadow
    assert style_of(salon, "zIndex") == "8"


def test_ac14_the_sheet_has_its_decorative_handle_8_px_below_its_top(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)
    page.get_by_test_id("chat-toggle").click()
    salon = page.get_by_test_id("salon")
    expect(salon).to_be_visible()
    handle = page.get_by_test_id("salon-handle")

    box = box_of(handle)
    salon_box = box_of(salon)

    assert same_size(box.width, 40.0), box
    assert same_size(box.height, 4.0), box
    expect(handle).to_have_attribute("aria-hidden", "true")
    assert style_of(handle, "borderTopLeftRadius") == "2px"
    expect_colour(handle, "backgroundColor", HANDLE)
    assert same_position(box.centre_x, 180.0), box
    assert same_position(box.top, salon_box.top + 8.0), (box, salon_box)


def test_ac14_opening_the_sheet_focuses_the_input_and_moves_nothing(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)
    viewport_box = box_of(page.get_by_test_id("grid-viewport"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))

    page.get_by_test_id("chat-toggle").click()
    expect(page.get_by_test_id("salon")).to_be_visible()

    expect(page.get_by_test_id("chat-input")).to_be_focused()
    viewport_after = box_of(page.get_by_test_id("grid-viewport"))
    bar_after = box_of(page.get_by_test_id("clue-bar"))
    assert same_box(viewport_after, viewport_box), (viewport_after, viewport_box)
    assert same_box(bar_after, bar_box), (bar_after, bar_box)


def test_ac14_escape_closes_the_sheet_and_focuses_chat_toggle(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)
    page.get_by_test_id("chat-toggle").click()
    expect(page.get_by_test_id("chat-input")).to_be_focused()

    page.keyboard.press("Escape")

    expect_closed(page.get_by_test_id("salon"))
    expect(page.get_by_test_id("chat-toggle")).to_be_focused()


# ---- AC-15: progress and tabs --------------------------------------------------------

TAMIS_AND_VIDE = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 1),
    (2, 2),
    (2, 3),
    (2, 4),
]


def ac15_frame(grid: Grid) -> str:
    """TAMIS and VIDE full, every other letter cell empty, 3 players."""
    view = fx01_view(grid, letters_of(TAMIS_AND_VIDE))
    return snapshot_frame(view, players_up_to(3))


def test_ac15_the_progress_counts_the_full_words_in_navy_tabular_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    text = page.get_by_test_id("salon-progress-text")

    expect(text).to_have_text(fr_format("salon.progress", filled=2, total=8))
    size = float(style_of(text, "fontSize").removesuffix("px"))
    assert same_font_size(size, 13.6), size
    assert style_of(text, "fontWeight") == "600"
    expect_colour(text, "color", NAVY)
    assert style_of(text, "fontVariantNumeric") == "tabular-nums"


def test_ac15_the_progress_bar_is_a_word_blue_track_with_a_navy_fill(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    bar = page.get_by_test_id("salon-progress-bar")

    box = box_of(bar)
    fill_end = box.left + box.width * 2 / 8
    middle = box.centre_y

    assert same_size(box.height, 6.0), box
    assert style_of(bar, "borderTopLeftRadius") == "3px"
    expect_colour(bar, "backgroundColor", WORD)
    expect(bar).to_have_attribute("aria-hidden", "true")
    assert pixel_at(page, fill_end - 1.5, middle) == NAVY
    assert pixel_at(page, fill_end + 1.5, middle) == WORD


def test_ac15_pending_letters_count_in_the_progress(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    press_cell(page, 3, 1)

    for letter in ("A", "M", "E", "N"):
        page.keyboard.press(letter)
    expect(cell_at(page, 3, 4)).to_contain_text("N")

    expect(page.get_by_test_id("salon-progress-text")).to_have_text(
        fr_format("salon.progress", filled=3, total=8)
    )


def test_ac15_the_two_tabs_are_a_tablist_of_equal_widths(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    discussion = page.get_by_test_id("salon-tab-discussion")
    players = page.get_by_test_id("salon-tab-players")

    expect(page.get_by_test_id("salon-tabs")).to_have_attribute("role", "tablist")
    expect(discussion).to_have_attribute("role", "tab")
    expect(players).to_have_attribute("role", "tab")
    expect(discussion).to_have_text(fr_value("chat.heading"))
    expect(players).to_have_text(fr_format("salon.players_tab", count=3))
    assert same_position(box_of(discussion).width, box_of(players).width)


def test_ac15_the_selected_tab_is_navy_and_underlined_the_other_muted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    discussion = page.get_by_test_id("salon-tab-discussion")
    players = page.get_by_test_id("salon-tab-players")

    expect(discussion).to_have_attribute("aria-selected", "true")
    expect(discussion).to_have_attribute("tabindex", "0")
    expect_colour(discussion, "color", NAVY)
    assert border_problems(discussion, "Bottom", "2px", "solid", NAVY) == []
    expect(players).to_have_attribute("aria-selected", "false")
    expect(players).to_have_attribute("tabindex", "-1")
    expect_colour(players, "color", MUTED)
    assert is_clear(colour_of(players, "borderBottomColor"))


def test_ac15_the_panels_are_tabpanels_labelled_by_their_tabs(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))

    for panel, tab in (
        ("chat-panel", "salon-tab-discussion"),
        ("roster", "salon-tab-players"),
    ):
        tab_id = page.get_by_test_id(tab).get_attribute("id")
        assert tab_id is not None, tab
        expect(page.get_by_test_id(panel)).to_have_attribute("role", "tabpanel")
        expect(page.get_by_test_id(panel)).to_have_attribute("aria-labelledby", tab_id)
        expect(page.get_by_test_id(tab)).to_have_attribute(
            "aria-controls", str(page.get_by_test_id(panel).get_attribute("id"))
        )
    expect(page.get_by_test_id("roster")).to_have_attribute("hidden", "")


def test_ac15_arrow_keys_move_between_the_tabs(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))
    discussion = page.get_by_test_id("salon-tab-discussion")
    players = page.get_by_test_id("salon-tab-players")
    discussion.focus()

    page.keyboard.press("ArrowRight")
    expect(players).to_have_attribute("aria-selected", "true")
    expect(players).to_be_focused()
    expect(page.get_by_test_id("roster")).to_be_visible()
    expect_closed(page.get_by_test_id("chat-panel"))

    page.keyboard.press("ArrowLeft")
    expect(discussion).to_have_attribute("aria-selected", "true")
    expect(discussion).to_be_focused()
    expect(page.get_by_test_id("chat-panel")).to_be_visible()
    expect_closed(page.get_by_test_id("roster"))


def test_ac15_a_join_updates_the_players_tab_count(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, ac15_frame(fx01_grid))

    send_and_wait(page, mock, joined_frame(6, player("p4")))

    expect(page.get_by_test_id("salon-tab-players")).to_have_text(
        fr_format("salon.players_tab", count=4)
    )


def test_ac15_a_click_selects_a_tab(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, ac15_frame(fx01_grid))

    page.get_by_test_id("salon-tab-players").click()

    expect(page.get_by_test_id("salon-tab-players")).to_have_attribute(
        "aria-selected", "true"
    )
    expect(page.get_by_test_id("roster")).to_be_visible()
    expect_closed(page.get_by_test_id("chat-panel"))
