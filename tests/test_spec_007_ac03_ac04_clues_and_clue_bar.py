"""Tests of spec 007, AC-3 and AC-4: tapping a clue, and the clue bar.

AC-3: tapping a clue selects the first empty cell of its word.
AC-4: the clue bar repeats the selected word's clue, at 14 px or more, inside the
window of a phone.
The shared setup is in `spec007_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, FloatRect, Locator, Page, expect

from nock.grid import Grid
from spec007_harness import (
    active_clue_texts,
    clue_named,
    expect_selection,
    grid_from_text,
    load_fr,
    note_view,
    open_fx01,
    open_mock_room,
    positions_with,
    select_cell_message,
    sent_selections,
    settle,
    show_snapshot,
    tap,
)

MIN_BAR_FONT_SIZE_PX = 14.0

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def phone_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 640 phone page (no is_mobile under Firefox)."""
    if browser_name == "firefox":
        context = browser.new_context(
            viewport={"width": 360, "height": 640},
            has_touch=True,
            device_scale_factor=2,
        )
    else:
        context = browser.new_context(
            viewport={"width": 360, "height": 640},
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    try:
        yield context.new_page()
    finally:
        context.close()


def box_of(locator: Locator) -> FloatRect:
    box = locator.bounding_box()
    assert box is not None, "the element has no box on screen"
    return box


# ---- AC-3: tapping a clue selects the first empty cell of its word -----------


def test_ac3_tapping_a_clue_selects_the_first_empty_cell_of_its_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])

    clue_named(page, "Artiste muet").click()

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert positions_with(page, "data-selected") == [(2, 2)]
    assert positions_with(page, "data-in-word") == [(1, 2), (2, 2), (3, 2), (4, 2)]
    assert active_clue_texts(page) == ["Artiste muet"]


def test_ac3_each_half_of_a_two_clue_cell_selects_its_own_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])
    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")

    clue_named(page, "Passoire fine").click()
    expect_selection(page, 1, 0, "across", "0,0,0")
    assert active_clue_texts(page) == ["Passoire fine"]
    assert positions_with(page, "data-in-word") == [
        (1, 0),
        (1, 1),
        (1, 2),
        (1, 3),
        (1, 4),
    ]

    clue_named(page, "De la marine").click()
    expect_selection(page, 0, 1, "down", "0,0,1")
    assert active_clue_texts(page) == ["De la marine"]
    assert positions_with(page, "data-selected") == [(0, 1)]


def test_ac3_a_clue_sets_the_direction_of_its_word_over_the_current_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "across", "2,0,0")

    clue_named(page, "Flaire").click()
    expect_selection(page, 1, 4, "down", "0,4,0")

    clue_named(page, "Alourdit le ballon").click()
    expect_selection(page, 4, 1, "across", "4,0,0")
    assert active_clue_texts(page) == ["Alourdit le ballon"]


def test_ac3_a_word_with_every_cell_filled_selects_its_first_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: list[tuple[int, int, dict[str, object]]] = [
        (1, 3, {"letter": "I"}),
        (2, 3, {"letter": "D"}),
        (3, 3, {"letter": "E"}),
        (4, 3, {"letter": "S"}),
    ]
    open_fx01(page, live_server, fx01_grid, changes)

    clue_named(page, "Fatales à César").click()

    expect_selection(page, 1, 3, "down", "0,3,0")
    assert positions_with(page, "data-in-word") == [(1, 3), (2, 3), (3, 3), (4, 3)]


def test_ac3_a_locked_cell_counts_as_filled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(2, 1, {"letter": "V", "locked": True})],
    )

    clue_named(page, "Sans contenu").click()

    expect_selection(page, 2, 2, "across", "2,0,0")


def test_ac3_the_first_unfilled_cell_is_chosen_when_later_cells_are_filled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(
        page,
        live_server,
        fx01_grid,
        [(3, 1, {"letter": "A"}), (3, 3, {"letter": "E"})],
    )

    clue_named(page, "Fin de prière").click()

    expect_selection(page, 3, 2, "across", "3,0,0")


def test_ac3_tapping_the_active_clue_again_selects_the_first_unfilled_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, [(1, 2, {"letter": "M"})])
    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    tap(page, 3, 2)
    expect_selection(page, 3, 2, "down", "0,2,0")

    clue_named(page, "Artiste muet").click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    clue_named(page, "Artiste muet").click()
    settle(page)

    expect_selection(page, 2, 2, "down", "0,2,0")
    assert sent_selections(mock) == [
        select_cell_message(2, 2, "down"),
        select_cell_message(3, 2, "down"),
        select_cell_message(2, 2, "down"),
    ]


def test_ac3_tapping_a_clue_gives_keyboard_focus_to_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    clue_named(page, "Sans contenu").click()

    expect_selection(page, 2, 1, "across", "2,0,0")
    expect(page.get_by_test_id("grid")).to_be_focused()


# ---- AC-4: the clue bar stays visible, at 14 px or more ----------------------


def window_height(page: Page) -> float:
    return float(page.evaluate("() => window.innerHeight"))


def expect_bar_inside_window(page: Page) -> None:
    bar = page.get_by_test_id("clue-bar")
    expect(bar).to_be_visible()
    box = box_of(bar)
    assert box["height"] > 0
    assert box["y"] >= 0
    assert box["y"] + box["height"] <= window_height(page)


def test_ac4_fr_json_holds_the_clue_bar_texts() -> None:
    fr = load_fr()

    assert fr["clue_bar.label"] == "Définition en cours"
    assert fr["clue_bar.empty"] == "Touchez une case ou une définition."


def test_ac4_there_is_no_clue_bar_before_the_first_snapshot(
    page: Page, live_server: str
) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("clue-bar")).to_have_count(0)
    expect(page.get_by_test_id("clue-bar-text")).to_have_count(0)


def test_ac4_the_bar_is_shown_with_the_empty_text_before_any_tap(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    bar = phone_page.get_by_test_id("clue-bar")
    expect(bar).to_be_visible()
    expect(bar).to_have_attribute("data-word", "")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
    text = phone_page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text(load_fr()["clue_bar.empty"])
    expect_bar_inside_window(phone_page)


def test_ac4_the_bar_repeats_the_clue_of_the_selected_word_on_a_phone(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    tap(phone_page, 3, 1)

    expect_selection(phone_page, 3, 1, "across", "3,0,0")
    bar = phone_page.get_by_test_id("clue-bar")
    text = phone_page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text("Fin de prière")
    expect(bar).to_have_attribute("data-word", "3,0,0")
    expect(bar).to_have_attribute("aria-label", load_fr()["clue_bar.label"])
    font_size = text.evaluate(
        "element => parseFloat(getComputedStyle(element).fontSize)"
    )
    assert font_size >= MIN_BAR_FONT_SIZE_PX
    expect_bar_inside_window(phone_page)


def test_ac4_the_bar_stays_inside_the_window_after_scrolling(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)
    tap(phone_page, 3, 1)
    expect(phone_page.get_by_test_id("clue-bar-text")).to_have_text("Fin de prière")

    phone_page.evaluate("() => window.scrollTo(0, 10000)")
    expect_bar_inside_window(phone_page)
    expect(phone_page.get_by_test_id("clue-bar-text")).to_have_text("Fin de prière")

    viewport = phone_page.get_by_test_id("grid-viewport")
    viewport.evaluate(
        "element => element.scrollTo(element.scrollWidth, element.scrollHeight)"
    )
    expect_bar_inside_window(phone_page)
    bar = phone_page.get_by_test_id("clue-bar")
    expect(bar).to_have_attribute("data-word", "3,0,0")


def test_ac4_the_bar_is_outside_the_scrolling_grid_viewport(
    phone_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(phone_page, live_server, fx01_grid)

    expect(phone_page.get_by_test_id("clue-bar")).to_have_count(1)
    inside = phone_page.locator(
        '[data-testid="grid-viewport"] [data-testid="clue-bar"]'
    )
    expect(inside).to_have_count(0)


def test_ac4_the_bar_follows_the_selection_and_the_direction(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    bar = page.get_by_test_id("clue-bar")
    text = page.get_by_test_id("clue-bar-text")

    tap(page, 1, 1)
    expect(text).to_have_text("Passoire fine")
    expect(bar).to_have_attribute("data-word", "0,0,0")

    tap(page, 1, 1)
    expect(text).to_have_text("De la marine")
    expect(bar).to_have_attribute("data-word", "0,0,1")

    tap(page, 2, 2)
    expect(text).to_have_text("Artiste muet")
    expect(bar).to_have_attribute("data-word", "0,2,0")

    clue_named(page, "Sans contenu").click()
    expect(text).to_have_text("Sans contenu")
    expect(bar).to_have_attribute("data-word", "2,0,0")
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "2,0,0")


def test_ac4_the_bar_shows_the_empty_text_again_when_the_selection_is_cleared(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 0, 1)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("De la marine")

    show_snapshot(page, mock, note_view(), 1)

    text = page.get_by_test_id("clue-bar-text")
    expect(text).to_have_text(load_fr()["clue_bar.empty"])
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "")
