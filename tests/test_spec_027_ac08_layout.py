"""Tests of spec 027, AC-8 (second part): the timer and its toggle keep the room's
layout at every window size, in desktop and touch contexts.

The setup is spec 024 AC-8's (spec 013 AC-6's FX-01 snapshot, `you` host among 8
players, 100 feed items, (3, 1) tapped, help mode `free`) with the timer at
`10:00:00` (stopped, so that the text does not change), at the eight window sizes of
spec 006 AC-5. Every check of spec 013 AC-6 holds; `timer-toggle` is at least 24 by
24 CSS px; spec 024 AC-8's toolbar checks (order, one row and edge fade, keyboard,
hit at the centre, pointer focus) hold with `timer-toggle` among the toolbar's
buttons; and on the four small windows, with the toolbar's `scrollLeft` at 0, `timer`
lies inside the toolbar's client area and its text is on one line. Every threshold
comes from the spec. The setup and the readings are in `spec027_toolbar_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser

from nock.grid import Grid
from spec024_harness import grid_from_text
from spec027_toolbar_harness import (
    CONTEXTS,
    LARGE_WINDOWS,
    POINTER_FOCUS_SIZE,
    SEVEN_BUTTONS,
    SMALL_WINDOWS,
    WINDOW_SIZES,
    hit_problems,
    keyboard_focus_problems,
    open_toolbar_room,
    press_partly_hidden_button,
    size_ids,
    spec013_layout_problems,
    structure_problems,
    timer_place_problems,
    toggle_size_problems,
    walk_the_toolbar,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Spec 013 AC-6's checks ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_spec_013_layout_holds_with_the_timer_in_the_toolbar(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        timer_is_there = page.get_by_test_id("timer").count()
        problems = spec013_layout_problems(page, touch)
    finally:
        close()

    assert timer_is_there == 1
    assert problems == []


# ---- The toggle's size ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_the_toggle_is_at_least_24_by_24_css_px(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        problems = toggle_size_problems(page)
    finally:
        close()

    assert problems == []


# ---- The toolbar: order, one row, edge fade ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac8_on_a_small_window_the_toolbar_with_the_toggle_is_one_row_that_scrolls(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        problems = structure_problems(page, small=True)
    finally:
        close()

    assert problems == []


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), LARGE_WINDOWS, ids=size_ids(LARGE_WINDOWS)
)
def test_ac8_on_a_larger_window_the_toolbar_with_the_toggle_has_no_edge_fade(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        problems = structure_problems(page, small=False)
    finally:
        close()

    assert problems == []


# ---- The timer on the small windows ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac8_on_a_small_window_the_timer_shows_in_the_toolbar_on_one_line(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        problems = timer_place_problems(page)
    finally:
        close()

    assert problems == []


# ---- Keyboard (desktop context) ----


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_a_keyboard_focus_keeps_the_seven_buttons_and_outlines_in_the_toolbar(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch=False
    )
    try:
        readings, visited = walk_the_toolbar(page)
    finally:
        close()

    missing = [test_id for test_id in SEVEN_BUTTONS if test_id not in readings]
    assert missing == [], f"not focused in 60 presses of Tab: {missing}"
    for test_id, reading in readings.items():
        assert keyboard_focus_problems(reading) == [], (test_id, reading)
    assert "timer" not in visited


# ---- Pointer ----


@pytest.mark.parametrize("context_kind", CONTEXTS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac8_each_of_the_seven_buttons_is_hit_at_its_centre_once_scrolled_into_view(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        misses = hit_problems(page)
    finally:
        close()

    assert misses == []


@pytest.mark.parametrize("test_id", SEVEN_BUTTONS)
@pytest.mark.parametrize("context_kind", CONTEXTS)
def test_ac8_a_pointer_focus_keeps_the_fade_and_makes_no_scroll_call(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    context_kind: str,
    test_id: str,
) -> None:
    touch = context_kind == "touch"
    width, height = POINTER_FOCUS_SIZE
    page, close = open_toolbar_room(
        browser, browser_name, live_server, fx01_grid, width, height, touch
    )
    try:
        after = press_partly_hidden_button(page, test_id, touch)
    finally:
        close()

    assert after["calls"] == [], after
    if after["hiddenPastRight"] > 1:
        assert after["fadeVisible"] is True, after
