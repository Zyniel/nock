"""Tests of spec 027, AC-4: each player can hide the timer on their own screen.

The page runs on spec 025's mocked socket (it answers each ping with a pong and
follows a reconnection). The hiding is a per-browser choice stored in
`localStorage["nock.timer_hidden"]`: hidden, the key holds `true` and no `timer`
element is on the page; shown, the key is absent, and a key holding anything else
counts as absent. The lead's note of 2026-10-15 applies: the heartbeat `ping`
frames of spec 017 are not counted as frames the page sends. The shared setup is in
`spec027_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from spec024_harness import grid_from_text
from spec027_harness import (
    QUIET_MS,
    clock_seconds,
    local_storage_value,
    new_context_page,
    open_timer_room,
    send_reconnect_snapshot,
    text_of,
    timer_of,
)

KEY = "nock.timer_hidden"
# Another room of the same browser: its code is one the context never opened, so the
# page shows the nickname form (spec 012's stored identity is per room).
OTHER_ROOM_CODE = "DEF456"
RUNNING_AT_65_S = 65_000

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-4 ----


def test_ac4_both_pages_show_the_timer_and_a_pressed_toggle(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    first, close_first = new_context_page(browser)
    second, close_second = new_context_page(browser)
    try:
        open_timer_room(
            first, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        open_timer_room(
            second, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )

        for page in (first, second):
            expect(timer_of(page)).to_be_visible()
            expect(page.get_by_test_id("timer-toggle")).to_be_visible()
            expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
                "aria-pressed", "true"
            )
    finally:
        close_first()
        close_second()


def test_ac4_a_click_hides_the_timer_on_this_page_only_and_sends_nothing(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    first, close_first = new_context_page(browser)
    second, close_second = new_context_page(browser)
    try:
        mock = open_timer_room(
            first, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        open_timer_room(
            second, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        frames_before = len(mock.frames_without_pings())

        first.get_by_test_id("timer-toggle").click()
        first.wait_for_timeout(QUIET_MS)

        expect(first.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "false"
        )
        expect(first.get_by_test_id("timer")).to_have_count(0)
        assert len(mock.frames_without_pings()) == frames_before
        expect(timer_of(second)).to_be_visible()
        expect(second.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "true"
        )
    finally:
        close_first()
        close_second()


def test_ac4_the_choice_holds_after_a_reload(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        page.get_by_test_id("timer-toggle").click()
        expect(page.get_by_test_id("timer")).to_have_count(0)

        page.reload()
        send_reconnect_snapshot(mock, fx01_grid, 1, elapsed_ms=RUNNING_AT_65_S)
        expect(page.get_by_test_id("cell")).to_have_count(25)

        expect(page.get_by_test_id("timer")).to_have_count(0)
        expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "false"
        )
        assert local_storage_value(page, KEY) == "true"
    finally:
        close()


def test_ac4_a_second_click_shows_the_timer_again_and_removes_the_key(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        page.get_by_test_id("timer-toggle").click()
        page.reload()
        send_reconnect_snapshot(mock, fx01_grid, 1, elapsed_ms=RUNNING_AT_65_S)
        expect(page.get_by_test_id("cell")).to_have_count(25)
        expect(page.get_by_test_id("timer")).to_have_count(0)

        page.get_by_test_id("timer-toggle").click()

        expect(page.get_by_test_id("timer")).to_be_visible()
        assert clock_seconds(text_of(page)) >= 65
        expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "true"
        )
        assert local_storage_value(page, KEY) is None
    finally:
        close()


def test_ac4_hiding_stores_true_and_showing_removes_the_key_without_a_reload(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        assert local_storage_value(page, KEY) is None

        page.get_by_test_id("timer-toggle").click()
        assert local_storage_value(page, KEY) == "true"

        page.get_by_test_id("timer-toggle").click()
        expect(page.get_by_test_id("timer")).to_be_visible()
        assert local_storage_value(page, KEY) is None
    finally:
        close()


def test_ac4_the_choice_holds_for_every_room_opened_in_this_browser(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        first = context.new_page()
        open_timer_room(
            first, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )
        first.get_by_test_id("timer-toggle").click()
        expect(first.get_by_test_id("timer")).to_have_count(0)

        other = context.new_page()
        open_timer_room(
            other,
            live_server,
            fx01_grid,
            elapsed_ms=RUNNING_AT_65_S,
            running=True,
            room_code=OTHER_ROOM_CODE,
        )

        expect(other.get_by_test_id("timer")).to_have_count(0)
        expect(other.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "false"
        )
    finally:
        context.close()


def test_ac4_a_key_holding_true_at_load_hides_the_timer(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        context.add_init_script(f"window.localStorage.setItem('{KEY}', 'true')")
        page = context.new_page()

        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )

        expect(page.get_by_test_id("timer")).to_have_count(0)
        expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "false"
        )
    finally:
        context.close()


@pytest.mark.parametrize("stored", ["false", "yes", "True", "1", ""])
def test_ac4_a_key_holding_anything_else_counts_as_absent(
    browser: Browser, live_server: str, fx01_grid: Grid, stored: str
) -> None:
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        context.add_init_script(f"window.localStorage.setItem('{KEY}', '{stored}')")
        page = context.new_page()

        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=RUNNING_AT_65_S, running=True
        )

        expect(timer_of(page)).to_be_visible()
        expect(page.get_by_test_id("timer-toggle")).to_have_attribute(
            "aria-pressed", "true"
        )
    finally:
        context.close()
