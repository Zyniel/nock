"""Tests of spec 014, AC-10: the host's settings sheet fits narrow and low windows
and large root fonts.

The browser with spec 040's mocked socket.

Refined by spec 043 (the design's room layout): the low layout's row of roster,
feed and host panel is gone, and the settings it held are the room sheet
`host-settings`. Setup as AC-9 (the host's view of 8 players, the Joueurs tab
shown), then spec 043's `open_host_settings`, at every narrow and low window of
"Test harness" at each of its root fonts, in desktop and touch contexts.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built, and for the windows in `tests/spec014_windows_harness.py`.

Choices where the spec leaves room:

- The two number fields "keep their 64 px width" with spec 043's 0.5 px tolerance.
"""

from __future__ import annotations

import pytest

from room_panels import open_host_settings
from spec014_harness import fx01_grid as fx01_grid
from spec014_windows_harness import (
    NARROW_LOW_IDS,
    NARROW_LOW_WINDOWS,
    SIZE_TOLERANCE_PX,
    OpenSmallWindow,
    Window,
    dialog_reading,
    inside,
    sheet_control_problems,
)
from spec014_windows_harness import small_window as small_window

NUMBER_FIELD_WIDTH_PX = 64.0
WIDTH_SCRIPT = "element => element.getBoundingClientRect().width"


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_sheet_lies_inside_the_window_without_a_sideways_scroll(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")
    open_host_settings(page)

    reading = dialog_reading(page)

    assert inside(reading["box"], reading["window"]), reading
    assert reading["scrollWidth"] <= reading["clientWidth"] + 1, reading
    assert reading["pageScrollWidth"] <= window.width, reading


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_each_control_of_the_sheet_is_inside_it_and_reachable(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")
    open_host_settings(page)

    assert sheet_control_problems(page, min_height=None) == []


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize("window", NARROW_LOW_WINDOWS, ids=NARROW_LOW_IDS)
def test_ac10_browser_the_number_fields_keep_their_64_px(
    small_window: OpenSmallWindow, window: Window, context_kind: str
) -> None:
    page, _room = small_window(window, touch=context_kind == "touch")
    open_host_settings(page)

    for test_id in ("reveal-letters-input", "reveal-words-input"):
        width = page.get_by_test_id(test_id).evaluate(WIDTH_SCRIPT)
        assert abs(width - NUMBER_FIELD_WIDTH_PX) <= SIZE_TOLERANCE_PX, (test_id, width)
