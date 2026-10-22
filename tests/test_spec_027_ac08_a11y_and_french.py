"""Tests of spec 027, AC-8 (first part): the timer and its toggle are accessible and
in French.

The page runs on spec 025's mocked socket. The semantics of `timer` (role, no live
region, label, never a Tab stop), its place in `room-topbar`, the Menu's
`timer-toggle` and the top bar's `timer-show` from the keyboard (spec 035's
`tab_to`, with spec 035 AC-2's outline), spec 035's contrast and language scans on
a snapshot of 36,000,000 ms running (`10:00:00`), and the `fr.json` keys. The
layout at every window size is in `test_spec_027_ac08_layout.py`. The shared setup
is in `spec027_harness`.

Refined by spec 043 (the design's room layout): this read "`timer`,
`timer-toggle` and `chat-toggle` are the first three elements of `room-toolbar`",
the toggle was the `⏱` button with an `aria-label`, and the scan accepted `⏱`.
Now `timer` is in `room-topbar` before `undo-button` (the first element of the
phone top bar that shows, right after `topbar-brand` in the computer top bar), the
hide control is the Menu's `timer-toggle` (`fr.json["timer.hide"]`), and the show
control is `timer-show` (« Chrono »); `timer.toggle` is removed from `fr.json`, and
spec 035 AC-9's flagged sample `Salon` became `Salle`.
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
from spec035_harness import unknown_texts
from spec043_harness import shown_test_ids

KEPT_FR_KEYS = {
    "timer.label": "Chrono",
    "timer.minutes_seconds": "{minutes}:{seconds}",
    "timer.hours_minutes_seconds": "{hours}:{minutes}:{seconds}",
    "timer.toggle_label": "Afficher le chrono",
    "timer.hide": "Masquer le chrono",
}
TEN_HOURS_MS = 36_000_000
SCAN_SIZES = [(1280, 720), (360, 740)]
LOOSE_LIVE_REGIONS = ["polite", "assertive"]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- The text in fr.json ----


def test_ac8_fr_json_holds_the_timer_keys() -> None:
    fr = load_fr()

    for key, value in KEPT_FR_KEYS.items():
        assert fr.get(key) == value, key
    assert "timer.toggle" not in fr


def test_ac8_the_time_patterns_do_not_hide_the_untranslated_samples() -> None:
    fr = load_fr()
    assert "timer.minutes_seconds" in fr
    assert "timer.hours_minutes_seconds" in fr
    # The time patterns need digits on both sides of each `:`, not a `:` alone
    # (spec 027, "New `fr.json` keys"): `Error: connection lost` holds a `:` too.
    samples = ["Loading…", "Salle", "Check word", "Error: connection lost", "Score: 3"]

    assert unknown_texts(samples, set()) == samples
    assert unknown_texts(["1:05", "1:02:05", "10:00:00", "0:00"], set()) == []


# ---- The semantics of the timer ----


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


@pytest.mark.parametrize(
    ("width", "height", "before_timer"),
    [(1280, 720, ["topbar-brand"]), (360, 740, [])],
    ids=["1280x720", "360x740"],
)
def test_ac8_the_timer_is_in_the_top_bar_before_undo(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    before_timer: list[str],
) -> None:
    page, close = open_context_page(browser, browser_name, width, height, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        shown = shown_test_ids(page.get_by_test_id("room-topbar"))
    finally:
        close()

    assert shown[: len(before_timer) + 2] == [*before_timer, "timer", "undo-button"]


def test_ac8_the_hide_item_is_in_the_menu_with_its_text(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        toggle = page.get_by_test_id("timer-toggle")
        in_menu = toggle.evaluate(
            "item => item.closest('[data-testid=\"room-menu\"]') !== null"
        )

        expect(toggle).to_have_text(load_fr()["timer.hide"])
        assert in_menu is True
    finally:
        close()


# ---- The keyboard ----


def test_ac8_from_the_keyboard_the_menu_item_hides_and_chrono_shows_the_timer(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    page, close = open_context_page(browser, browser_name, 1280, 720, touch=False)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=TEN_HOURS_MS, running=True
        )
        walker = make_walker(page)

        walker.tab_to("menu-button")
        page.keyboard.press("Enter")
        expect(page.get_by_test_id("room-menu")).to_be_visible()
        walker.tab_to("timer-toggle")
        page.keyboard.press("Enter")
        expect(page.get_by_test_id("timer")).to_have_count(0)
        show = page.get_by_test_id("timer-show")
        expect(show).to_have_text(fr["timer.label"])
        expect(show).to_have_attribute("aria-label", fr["timer.toggle_label"])
        walker.tab_to("timer-show")
        page.keyboard.press("Enter")

        expect(timer_of(page)).to_be_visible()
        reached = {step.test_id: step for step in walker.reached}
        for test_id in ("timer-toggle", "timer-show"):
            step = reached[test_id]
            problems = outline_problems(
                step.outline_style, step.outline_width, step.outline_contrast
            )
            assert problems == [], (test_id, problems)
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
        page.evaluate("() => document.body.focus()")
        visited: list[str] = []
        for _ in range(8):
            page.keyboard.press("Tab")
            focused = page.evaluate(
                "() => document.activeElement"
                " && document.activeElement.getAttribute('data-testid')"
            )
            visited.append(str(focused))
    finally:
        close()

    assert "timer" not in visited
    assert "undo-button" in visited


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
        data.update({"10:00:00", "Chrono"})

        unknown = language_problems(page, data)
    finally:
        close()

    assert unknown == []
