"""Tests of spec 014, AC-8: the whole box of each host button can be tapped.

The browser with spec 040's mocked socket, at the window sizes of spec 006 AC-5 and
then at the narrow and low windows.

Refined by spec 043 (the design's room layout): `remove-player` and `mute-player`
sit in the other players' rows of the Salon's Joueurs tab, which the tests show
first with spec 043's `show_tab`, and the check runs on both. A button that sticks
out of the Joueurs panel (which scrolls vertically) fails, because the panel clips
the part outside it.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from room_panels import show_tab
from spec014_harness import fx01_grid as fx01_grid
from spec014_harness import joined_mock_room
from spec014_windows_harness import (
    HIT_TEST_BODY,
    MIN_HIT_PIXELS,
    NARROW_LOW_IDS,
    NARROW_LOW_WINDOWS,
    REMOVE_BUTTON_COUNT,
    WINDOW_IDS,
    WINDOW_SIZES,
    OpenSmallWindow,
    Window,
    eight_players,
    make_page,
)
from spec014_windows_harness import small_window as small_window

# The hit test of a button: it scrolls the button into view first, then runs the
# check of HIT_TEST_BODY.
HIT_TEST_SCRIPT = (
    "button => { button.scrollIntoView({block: 'nearest', inline: 'nearest'});"
    + HIT_TEST_BODY
    + "}"
)
HOST_BUTTONS = ["remove-player", "mute-player"]

# ---- AC-8: the whole box of each host button can be tapped ---------------------


@pytest.mark.parametrize("test_id", HOST_BUTTONS)
@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac8_browser_every_pixel_of_a_host_button_hits_the_button(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
    test_id: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        joined_mock_room(page, live_server, fx01_grid, eight_players())
        show_tab(page, "players")
        buttons = page.get_by_test_id(test_id)
        expect(buttons).to_have_count(REMOVE_BUTTON_COUNT)

        for index in range(REMOVE_BUTTON_COUNT):
            report = buttons.nth(index).evaluate(HIT_TEST_SCRIPT)
            assert report["tested"] >= MIN_HIT_PIXELS, report
            assert report["missCount"] == 0, (index, report)
    finally:
        close()


# ---- AC-8 (extended): the narrow and low windows ----------------------------


@pytest.mark.parametrize("test_id", HOST_BUTTONS)
@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac8_browser_every_pixel_of_a_host_button_hits_it_at_narrow_and_low_windows(
    small_window: OpenSmallWindow, window: Window, context_kind: str, test_id: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")

    buttons = page.get_by_test_id(test_id)
    expect(buttons).to_have_count(REMOVE_BUTTON_COUNT)
    for index in range(REMOVE_BUTTON_COUNT):
        report = buttons.nth(index).evaluate(HIT_TEST_SCRIPT)
        assert report["tested"] >= MIN_HIT_PIXELS, report
        assert report["missCount"] == 0, (window, index, report)
