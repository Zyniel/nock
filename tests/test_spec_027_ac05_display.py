"""Tests of spec 027, AC-5: the timer shows the room's time in minutes and seconds,
then in hours, and follows the room's events.

The page runs on spec 025's mocked socket. Where the criterion reads a running timer
("`1:05` within 300 ms", "`1:06` within 1,300 ms of the first reading"), the page is
opened with Playwright's page clock (see `spec027_harness`): `performance.now()` is
frozen when the snapshot arrives and the test moves it by hand, so that the bounds of
the spec are bounds of the page's own time and no machine load can break them. A
window of "within T ms" is T ms of the page's clock. The static texts (a timer that
is not running) need no clock.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from nock.protocol import GridSolved, LetterChanged
from spec024_harness import expect_seq, grid_from_text
from spec027_harness import (
    advance_clock,
    advance_until_text,
    elapsed_ms_of,
    new_context_page,
    open_timer_room,
    timer_of,
)

# The refresh test moves the clock by 50 ms and accepts a value that stays the same
# for 250 ms at most ("refreshed at least every 250 ms"), plus one step because a
# refresh is seen at the end of the step that holds it.
REFRESH_STEP_MS = 50
WATCH_MS = 1500
MAX_WAIT_MS = 250 + REFRESH_STEP_MS

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def letter_frame(seq: int, letter: str | None, player_id: str = "p2") -> str:
    """A `letter_changed` of (1, 0) from a player."""
    event = LetterChanged(
        seq=seq, row=1, column=0, letter=letter, pencil=False, player_id=player_id
    )
    return event.model_dump_json()


def solved_frame(seq: int, elapsed_ms: int) -> str:
    """A `grid_solved` event."""
    return GridSolved(seq=seq, elapsed_ms=elapsed_ms).model_dump_json()


# ---- The format of the text ----


@pytest.mark.parametrize(
    ("elapsed_ms", "text"),
    [
        (0, "0:00"),
        (999, "0:00"),
        (1000, "0:01"),
        (59_999, "0:59"),
        (60_000, "1:00"),
        (65_000, "1:05"),
        (754_000, "12:34"),
        (3_599_999, "59:59"),
        (3_600_000, "1:00:00"),
        (3_725_000, "1:02:05"),
        (36_000_000, "10:00:00"),
    ],
)
def test_ac5_a_stopped_timer_shows_its_time_in_whole_seconds_rounded_down(
    browser: Browser, live_server: str, fx01_grid: Grid, elapsed_ms: int, text: str
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=elapsed_ms, running=False
        )

        expect(timer_of(page)).to_have_text(text)
        expect(timer_of(page)).to_have_attribute("data-running", "false")
        expect(timer_of(page)).to_have_attribute("data-elapsed-ms", str(elapsed_ms))
    finally:
        close()


# ---- The runs of the criterion ----


def test_ac5_a_timer_at_zero_does_not_move_then_follows_the_first_letter(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page, live_server, fx01_grid, elapsed_ms=0, running=False, frozen=True
        )
        expect(timer_of(page)).to_have_text("0:00")
        expect(timer_of(page)).to_have_attribute("data-running", "false")
        advance_clock(page, 2000)
        expect(timer_of(page)).to_have_text("0:00")
        expect(timer_of(page)).to_have_attribute("data-running", "false")

        mock.send(letter_frame(6, None))
        expect_seq(page, 6)
        advance_clock(page, 1500)
        expect(timer_of(page)).to_have_text("0:00")
        expect(timer_of(page)).to_have_attribute("data-running", "false")

        mock.send(letter_frame(7, "T"))
        expect_seq(page, 7)
        expect(timer_of(page)).to_have_attribute("data-running", "true")
        moved = advance_until_text(page, "0:01", 1500)
        assert moved <= 1500
    finally:
        close()


def test_ac5_a_running_timer_reads_1_05_then_1_06_and_grows_while_it_runs(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=65_000,
            running=True,
            frozen=True,
        )
        advance_clock(page, 250)
        expect(timer_of(page)).to_have_text("1:05")
        expect(timer_of(page)).to_have_attribute("data-running", "true")

        moved = advance_until_text(page, "1:06", 1300)

        assert moved <= 1300
    finally:
        close()


def test_ac5_the_elapsed_value_is_refreshed_at_least_every_250_ms_while_running(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=65_000,
            running=True,
            frozen=True,
        )
        # The clock moves by hand in steps of 50 ms. The test never compares a
        # reading with the instant of the snapshot (a real delay before the clock
        # froze would shift every value); it reads the value at the freeze, then
        # watches how it follows the clock.
        value_at_freeze = elapsed_ms_of(page)
        last_value = value_at_freeze
        last_change_at = 0
        longest_wait = 0
        for moved in range(REFRESH_STEP_MS, WATCH_MS + 1, REFRESH_STEP_MS):
            advance_clock(page, REFRESH_STEP_MS)
            value = elapsed_ms_of(page)
            assert value >= last_value, (moved, last_value, value)
            if value != last_value:
                longest_wait = max(longest_wait, moved - last_change_at)
                last_change_at = moved
                last_value = value
        longest_wait = max(longest_wait, WATCH_MS - last_change_at)

        assert value_at_freeze >= 65_000, value_at_freeze
        assert longest_wait <= MAX_WAIT_MS, longest_wait
        grown = last_value - value_at_freeze
        assert WATCH_MS - 300 <= grown <= WATCH_MS + 300, grown
    finally:
        close()


def test_ac5_a_running_timer_shows_ten_hours(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=36_000_000,
            running=True,
            frozen=True,
        )

        expect(timer_of(page)).to_have_text("10:00:00")
        expect(timer_of(page)).to_have_attribute("data-running", "true")
        advance_clock(page, 100)
        expect(timer_of(page)).to_have_text("10:00:00")
    finally:
        close()


def test_ac5_a_running_timer_passes_from_minutes_to_hours(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=3_599_000,
            running=True,
            frozen=True,
        )
        advance_clock(page, 100)
        expect(timer_of(page)).to_have_text("59:59")

        moved = advance_until_text(page, "1:00:00", 1300)

        assert moved <= 1300
    finally:
        close()


def test_ac5_a_solved_room_shows_its_final_time_and_does_not_move(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=3_725_000,
            running=False,
            solved=True,
            frozen=True,
        )

        expect(timer_of(page)).to_have_text("1:02:05")
        advance_clock(page, 2000)
        expect(timer_of(page)).to_have_text("1:02:05")
        expect(timer_of(page)).to_have_attribute("data-running", "false")
    finally:
        close()


def test_ac5_grid_solved_stops_the_timer_on_the_logged_time(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=750_000,
            running=True,
            frozen=True,
        )
        expect(timer_of(page)).to_have_text("12:30")

        mock.send(solved_frame(6, 754_000))
        expect_seq(page, 6)

        expect(timer_of(page)).to_have_text("12:34")
        expect(timer_of(page)).to_have_attribute("data-running", "false")
        expect(timer_of(page)).to_have_attribute("data-elapsed-ms", "754000")
        advance_clock(page, 2000)
        expect(timer_of(page)).to_have_text("12:34")
        expect(timer_of(page)).to_have_attribute("data-elapsed-ms", "754000")
    finally:
        close()


# ---- Letters that must not move the timer ----


def test_ac5_a_letter_while_the_timer_runs_does_not_restart_it(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=65_000,
            running=True,
            frozen=True,
        )

        mock.send(letter_frame(6, "T"))
        expect_seq(page, 6)
        advance_clock(page, 100)

        expect(timer_of(page)).to_have_text("1:05")
        assert elapsed_ms_of(page) >= 65_000
    finally:
        close()


def test_ac5_a_letter_does_not_start_a_timer_that_already_counted_time(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=30_000,
            running=False,
            frozen=True,
        )

        mock.send(letter_frame(6, "T"))
        expect_seq(page, 6)
        advance_clock(page, 2000)

        expect(timer_of(page)).to_have_text("0:30")
        expect(timer_of(page)).to_have_attribute("data-running", "false")
    finally:
        close()


def test_ac5_a_letter_does_not_start_the_timer_of_a_solved_room(
    browser: Browser, live_server: str, fx01_grid: Grid
) -> None:
    page, close = new_context_page(browser)
    try:
        mock = open_timer_room(
            page,
            live_server,
            fx01_grid,
            elapsed_ms=0,
            running=False,
            solved=True,
            frozen=True,
        )

        mock.send(letter_frame(6, "T"))
        expect_seq(page, 6)
        advance_clock(page, 2000)

        expect(timer_of(page)).to_have_text("0:00")
        expect(timer_of(page)).to_have_attribute("data-running", "false")
    finally:
        close()
