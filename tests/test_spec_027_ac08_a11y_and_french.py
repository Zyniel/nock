"""Tests of spec 027, AC-8 (first part): the timer and its toggle are accessible and
in French.

The page runs on spec 025's mocked socket. The semantics of `timer` (role, no live
region, label), the place of the two elements at the start of `room-toolbar`, the
toggle's text and label, the keyboard (spec 035's `tab_to`: the toggle gets the
focus with spec 035 AC-2's outline and `Enter` hides the timer; the timer is never a
Tab stop), spec 035's contrast and language scans on a snapshot of 36,000,000 ms
running (`10:00:00`), and the five new `fr.json` keys. The layout at every window
size is in `test_spec_027_ac08_layout.py`. The shared setup is in `spec027_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from spec024_harness import (
    contrast_problems,
    grid_from_text,
    language_data,
    language_problems,
    load_fr,
    make_walker,
    open_context_page,
    outline_problems,
)
from spec027_harness import open_timer_room, timer_of
from spec027_toolbar_harness import FIRST_THREE, FOCUS_SHARE_LINK_SCRIPT
from spec035_harness import unknown_texts

NEW_FR_KEYS = {
    "timer.label": "Chrono",
    "timer.minutes_seconds": "{minutes}:{seconds}",
    "timer.hours_minutes_seconds": "{hours}:{minutes}:{seconds}",
    "timer.toggle": "⏱",
    "timer.toggle_label": "Afficher le chrono",
}
TEN_HOURS_MS = 36_000_000
SCAN_SIZES = [(1280, 720), (360, 740)]
LOOSE_LIVE_REGIONS = ["polite", "assertive"]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- The text in fr.json ----


def test_ac8_fr_json_holds_the_five_timer_keys() -> None:
    fr = load_fr()

    for key, value in NEW_FR_KEYS.items():
        assert fr.get(key) == value, key


def test_ac8_the_toggle_symbol_is_the_stopwatch_u23f1() -> None:
    assert load_fr().get("timer.toggle") == "⏱"


def test_ac8_the_time_patterns_do_not_hide_the_untranslated_samples() -> None:
    fr = load_fr()
    assert "timer.minutes_seconds" in fr
    assert "timer.hours_minutes_seconds" in fr
    samples = ["Loading…", "Salon", "Check word"]

    assert unknown_texts(samples, set()) == samples
    assert unknown_texts(["1:05", "1:02:05", "10:00:00", "0:00"], set()) == []


# ---- The semantics of the timer and of its toggle ----


def test_ac8_the_timer_is_a_timer_without_a_live_region_and_has_a_label(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        timer = timer_of(page)

        expect(timer).to_have_attribute("role", "timer")
        expect(timer).to_have_attribute("aria-label", load_fr()["timer.label"])
        assert timer.get_attribute("aria-live") not in LOOSE_LIVE_REGIONS
        assert timer.evaluate("element => element.tabIndex") < 0
        assert timer.get_attribute("data-running") == "true"
    finally:
        close()


def test_ac8_the_timer_and_its_toggle_open_the_toolbar_before_the_chat_toggle(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        script = """
        () => {
          const toolbar = document.querySelector('[data-testid="room-toolbar"]');
          const found = [];
          for (const element of toolbar.querySelectorAll('[data-testid]')) {
            found.push(element.getAttribute('data-testid'));
          }
          return found.slice(0, 3);
        }
        """

        first_three = page.evaluate(script)
    finally:
        close()

    assert first_three == FIRST_THREE


def test_ac8_the_toggle_has_the_symbol_as_text_and_its_own_label(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        toggle = page.get_by_test_id("timer-toggle")

        expect(toggle).to_have_text(fr["timer.toggle"])
        expect(toggle).to_have_attribute("aria-label", fr["timer.toggle_label"])
        assert toggle.evaluate("element => element.tagName") == "BUTTON"
    finally:
        close()


@pytest.mark.parametrize(("width", "height"), [(1280, 720), (360, 740), (320, 568)])
def test_ac8_the_toggle_keeps_its_symbol_at_every_window_size(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )

        expect(page.get_by_test_id("timer-toggle")).to_have_text(
            load_fr()["timer.toggle"]
        )
    finally:
        close()


# ---- The keyboard ----


def test_ac8_tab_gives_the_toggle_the_focus_with_the_outline_and_enter_hides_the_timer(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        walker = make_walker(page)

        walker.tab_to("timer-toggle")
        reached = walker.reached[-1]
        page.keyboard.press("Enter")

        assert reached.test_id == "timer-toggle"
        assert (
            outline_problems(
                reached.outline_style, reached.outline_width, reached.outline_contrast
            )
            == []
        )
        expect(page.get_by_test_id("timer")).to_have_count(0)
        expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "false"
        )
    finally:
        close()


def test_ac8_the_timer_text_is_never_a_tab_stop(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        page.evaluate(FOCUS_SHARE_LINK_SCRIPT)
        visited: list[str] = []
        for _ in range(12):
            page.keyboard.press("Tab")
            focused = page.evaluate(
                "() => document.activeElement"
                " && document.activeElement.getAttribute('data-testid')"
            )
            visited.append(str(focused))
    finally:
        close()

    assert "timer" not in visited
    assert "timer-toggle" in visited
    assert "chat-toggle" in visited
    assert visited.index("timer-toggle") < visited.index("chat-toggle")


# ---- Spec 035's scans ----


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES)
def test_ac8_the_contrast_scan_finds_no_offending_element(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        expect(timer_of(page)).to_be_visible()

        offenders = contrast_problems(page)
    finally:
        close()

    assert offenders == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES)
def test_ac8_the_language_scan_finds_no_text_outside_fr_json_and_the_data(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        expect(timer_of(page)).to_be_visible()
        data = language_data(live_server, ["Ana", "Bob"])
        data.update({"10:00:00", "⏱", "Chrono"})

        unknown = language_problems(page, data)
    finally:
        close()

    assert unknown == []
