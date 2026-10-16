"""Tests of spec 027, AC-2 and AC-3 (browser part): every player reads the same
timer, and the timer does not count the time a player is away.

TIMING-SENSITIVE: these tests run browsers on the live server with the real clock,
so they read the timer a few real seconds after a key press and compare it with
bounds of the spec (2,000 to 4,500 ms after 3 s, at most 1,000 ms between pages).
They hold under a normal load; a machine that stalls a browser for a second can
fail them, so the gate should run this file alone (`SERIAL_TEST_FILES`).

Every player enters through spec 011's `enter_room` in a context of its own; a page
reopened in the same context resumes the same player (spec 012's stored identity).

The last section is the exception: the two tests of a page that loses its socket
(AC-3, "Browser with mocked socket") run on spec 025's mocked socket and
Playwright's page clock, as the tests of AC-5 do, so no machine load can shift what
they read. The shared setup is in `spec027_harness`.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from spec022_harness import new_player_page
from spec024_harness import EnterRoom, cell_at, grid_from_text
from spec025_harness import MockRoomSocket
from spec027_harness import (
    advance_clock,
    advance_until_join,
    advance_until_text,
    clock_seconds,
    elapsed_ms_of,
    new_context_page,
    open_timer_room,
    send_reconnect_snapshot,
    text_of,
    timer_of,
)

# Spec 017: a close with any code but a final one is a lost connection.
LOSS_CLOSE_CODE = 1011
RUNNING_AT_65_S = 65_000
RECONNECT_SNAPSHOT_MS = 62_000
# From the first snapshot (65,000 ms) to `1:10` takes 5 s of the page's clock.
TO_1_10_LIMIT_MS = 6000
# The first reconnection comes 1 s after the loss (spec 017); the test lets the
# page count 500 ms offline first.
OFFLINE_MS = 500
RECONNECT_LIMIT_MS = 3000
# "Within 300 ms" of the reconnect snapshot, on the page's clock.
SNAPSHOT_WINDOW_MS = 300

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def type_t_at_1_0(page: Page) -> float:
    """Tap (1, 0) and type `T`; return the `time.monotonic()` of the key press."""
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    return time.monotonic()


# ---- AC-2: the same reading for every player ----


def test_ac2_two_players_read_the_same_timer_within_one_second(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    closers: list[Callable[[], None]] = []
    try:
        ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
        closers.append(close_ana)
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        closers.append(close_bob)

        for page in (ana, bob):
            expect(timer_of(page)).to_have_text("0:00")
            expect(timer_of(page)).to_have_attribute("data-running", "false")
        ana.wait_for_timeout(2000)
        for page in (ana, bob):
            expect(timer_of(page)).to_have_text("0:00")
            expect(timer_of(page)).to_have_attribute("data-running", "false")

        pressed_at = type_t_at_1_0(ana)
        for page in (ana, bob):
            expect(timer_of(page)).to_have_attribute(
                "data-running", "true", timeout=1000
            )

        wait_ms = 3000 - (time.monotonic() - pressed_at) * 1000
        ana.wait_for_timeout(max(wait_ms, 0))
        ana_elapsed = elapsed_ms_of(ana)
        ana_text = text_of(ana)
        bob_elapsed = elapsed_ms_of(bob)
        bob_text = text_of(bob)

        assert 2000 <= ana_elapsed <= 4500, ana_elapsed
        assert 2000 <= bob_elapsed <= 4500, bob_elapsed
        assert abs(ana_elapsed - bob_elapsed) <= 1000, (ana_elapsed, bob_elapsed)
        assert abs(clock_seconds(ana_text) - clock_seconds(bob_text)) <= 1, (
            ana_text,
            bob_text,
        )
    finally:
        for close in closers:
            close()


def test_ac2_a_player_who_joins_later_reads_the_same_timer(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    closers: list[Callable[[], None]] = []
    try:
        ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
        closers.append(close_ana)
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        closers.append(close_bob)
        pressed_at = type_t_at_1_0(ana)
        for page in (ana, bob):
            expect(timer_of(page)).to_have_attribute(
                "data-running", "true", timeout=1000
            )
        wait_ms = 3000 - (time.monotonic() - pressed_at) * 1000
        ana.wait_for_timeout(max(wait_ms, 0))

        cy, close_cy = new_player_page(browser, live_server, code, "Cy", enter_room)
        closers.append(close_cy)
        expect(cy.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "joined"
        )
        expect(timer_of(cy)).to_have_attribute("data-running", "true", timeout=1000)
        cy_elapsed = elapsed_ms_of(cy)
        ana_elapsed = elapsed_ms_of(ana)

        assert abs(cy_elapsed - ana_elapsed) <= 1000, (cy_elapsed, ana_elapsed)
        assert cy_elapsed >= 2000, cy_elapsed
    finally:
        for close in closers:
            close()


def test_ac1_page_selecting_cells_does_not_start_the_timer(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    closers: list[Callable[[], None]] = []
    try:
        ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
        closers.append(close_ana)
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        closers.append(close_bob)

        cell_at(ana, 1, 0).click()
        cell_at(ana, 2, 2).click()
        ana.wait_for_timeout(1500)

        for page in (ana, bob):
            expect(timer_of(page)).to_have_text("0:00")
            expect(timer_of(page)).to_have_attribute("data-running", "false")
            expect(timer_of(page)).to_have_attribute("data-elapsed-ms", "0")
    finally:
        for close in closers:
            close()


# ---- AC-3: the time away is not counted ----


def test_ac3_the_four_seconds_a_player_was_away_are_not_counted(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        first = context.new_page()
        enter_room(first, url, "Ana")
        type_t_at_1_0(first)
        expect(timer_of(first)).to_have_attribute("data-running", "true", timeout=1000)
        deadline = time.monotonic() + 10.0
        while elapsed_ms_of(first) < 2000:
            assert time.monotonic() < deadline, "the timer never reached 2,000 ms"
            first.wait_for_timeout(50)
        noted = elapsed_ms_of(first)
        first.close()

        time.sleep(4.0)
        second = context.new_page()
        enter_room(second, url, "Ana")
        expect(second.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "joined"
        )
        expect(timer_of(second)).to_have_attribute("data-running", "true", timeout=1000)
        back = elapsed_ms_of(second)

        assert noted <= back <= noted + 1500, (noted, back)
    finally:
        context.close()


def test_ac3_a_room_whose_players_all_left_without_a_letter_stays_at_zero(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        first = context.new_page()
        enter_room(first, url, "Ana")
        expect(timer_of(first)).to_have_text("0:00")
        first.close()

        time.sleep(2.0)
        second = context.new_page()
        enter_room(second, url, "Ana")

        expect(timer_of(second)).to_have_text("0:00")
        expect(timer_of(second)).to_have_attribute("data-running", "false")
    finally:
        context.close()


# ---- AC-3: a page that loses its socket (mocked socket, page clock) ----


def lose_the_socket_at_1_10(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """Show 65,000 ms running; close the socket with 1011 once the timer reads 1:10.

    Returns:
        The mocked socket, once the page shows `data-status="reconnecting"`.
    """
    mock = open_timer_room(
        page,
        live_server,
        grid,
        elapsed_ms=RUNNING_AT_65_S,
        running=True,
        frozen=True,
    )
    advance_until_text(page, "1:10", TO_1_10_LIMIT_MS)
    mock.close(LOSS_CLOSE_CODE)
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "reconnecting"
    )
    return mock


def test_ac3_a_page_that_lost_its_socket_keeps_counting_while_it_is_offline(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        lose_the_socket_at_1_10(page, live_server, fx01_grid)
        counted_at_loss = elapsed_ms_of(page)
        assert counted_at_loss >= 70_000, counted_at_loss

        advance_clock(page, OFFLINE_MS)

        expect(timer_of(page)).to_have_attribute("data-running", "true")
        assert elapsed_ms_of(page) > counted_at_loss
    finally:
        close()


def test_ac3_a_page_that_reconnects_shows_the_snapshot_value_although_it_is_lower(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = lose_the_socket_at_1_10(page, live_server, fx01_grid)
        advance_clock(page, OFFLINE_MS)
        counted_offline = elapsed_ms_of(page)
        assert counted_offline >= 70_000, counted_offline
        advance_until_join(page, mock, 1, RECONNECT_LIMIT_MS)

        send_reconnect_snapshot(mock, fx01_grid, 1, elapsed_ms=RECONNECT_SNAPSHOT_MS)
        expect(page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "joined"
        )
        advance_clock(page, SNAPSHOT_WINDOW_MS)

        expect(timer_of(page)).to_have_text("1:02")
        expect(timer_of(page)).to_have_attribute("data-running", "true")
        shown = elapsed_ms_of(page)
        assert RECONNECT_SNAPSHOT_MS <= shown <= 63_500, shown
    finally:
        close()
