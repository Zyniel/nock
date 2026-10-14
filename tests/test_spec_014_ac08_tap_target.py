"""Tests of spec 014, AC-8: the whole box of each remove button can be tapped.

The browser with spec 040's mocked socket, at the window sizes of spec 006 AC-5 and
then at the narrow and low windows.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from spec014_harness import (
    HIT_TEST_SCRIPT,
    MIN_HIT_PIXELS,
    NARROW_LOW_IDS,
    NARROW_LOW_WINDOWS,
    REMOVE_BUTTON_COUNT,
    WINDOW_SIZES,
    OpenSmallWindow,
    Window,
    eight_players,
    joined_mock_room,
    make_page,
)
from spec014_harness import fx01_grid as fx01_grid
from spec014_harness import small_window as small_window

# ---- AC-8: the whole box of each remove button can be tapped ----------------


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac8_browser_every_pixel_of_a_remove_button_hits_the_button(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        buttons = page.get_by_test_id("remove-player")
        expect(buttons).to_have_count(7)

        for index in range(7):
            report = buttons.nth(index).evaluate(HIT_TEST_SCRIPT)
            assert report["tested"] >= 24 * 24 - 2 * 24, report
            assert report["missCount"] == 0, (index, report)
    finally:
        close()


# ---- AC-8 (extended): the narrow and low windows ----------------------------


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac8_browser_every_pixel_of_a_remove_button_hits_it_at_narrow_and_low_windows(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")

    buttons = page.get_by_test_id("remove-player")
    for index in range(REMOVE_BUTTON_COUNT):
        report = buttons.nth(index).evaluate(HIT_TEST_SCRIPT)
        assert report["tested"] >= MIN_HIT_PIXELS, report
        assert report["missCount"] == 0, (window, index, report)
