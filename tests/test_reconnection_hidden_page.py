"""Tests of `platform/reconnection.md` AC-6: a hidden page the browser held back.

Rules 3 and 6. Ana's joined page (spec 017's mocked room, `joined_room`) is hidden,
then its page clock jumps 5 seconds with the timers that came due meanwhile fired
once, late (`page.clock.fast_forward`), while the mocked server keeps the socket
open and sends nothing. The browser holds back the worker's timers too: the frozen
page is loaded without `Worker` (`joined_room`), so no timer runs outside the page
clock. Made visible again, the page sends `ping` at once (the
page clock still frozen) and keeps its socket with no band; on a socket that then
gets no frame, the band shows within 5 seconds of the return. A page made visible
while a retry waits on the 8-second delay opens a socket at once.

The readings of "hidden" and "timers run late" are `reconnection_harness`'s. The
5 seconds are page-clock time, so this file runs in the parallel pass.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from nock.grid import Grid
from reconnection_harness import VISIBILITY_SCRIPT, set_page_hidden
from spec017_harness import (
    STEP_SETTLE_MS,
    STORED_JOIN,
    MockRoom,
    advance_page,
    banner,
    expect_offline,
    expect_status,
    first_join,
    joined_room,
    settle,
    wait_until,
)

LATE_TIMERS_MS = 5000  # how long the hidden page's timers ran late
BAND_WITHIN_MS = 5000  # the band shows within 5 s of the return
PING_INTERVAL_MS = 2000
KEPT_FOR_PINGS = 4  # the answered pings that show the socket is kept
LOST_CLOSE = 1011
# The first three retry delays (1, 2, 4 s) at their highest, 20 % above.
FIRST_THREE_DELAYS_LATEST_MS = [1200, 2400, 4800]
EIGHT_SECOND_DELAY_LATEST_MS = 9600
WAIT_WHILE_HIDDEN_MS = 1000  # well short of the 8-second delay's 6.4 s


def hide_while_timers_run_late(page: Page) -> None:
    """Hide the page, then jump its clock 5 s, firing the due timers once, late.

    It returns once what those late timers sent has reached the mocked server.
    """
    set_page_hidden(page, True)
    page.clock.fast_forward(LATE_TIMERS_MS)
    settle(page)


def expect_still_joined_on_the_first_socket(page: Page, room: MockRoom) -> None:
    """The page is joined, shows no band and has opened no other socket."""
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    assert len(room.connections) == 1


def test_ac6_made_visible_it_pings_at_once_and_keeps_the_same_socket(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=VISIBILITY_SCRIPT,
    )
    connection = room.connections[0]
    hide_while_timers_run_late(page)
    pings_before = connection.ping_count()
    room.answer_pings = True

    set_page_hidden(page, False)

    wait_until(page, lambda: connection.ping_count() > pings_before)
    page.wait_for_timeout(STEP_SETTLE_MS)
    assert connection.ping_count() == pings_before + 1
    expect_still_joined_on_the_first_socket(page, room)
    for _ in range(KEPT_FOR_PINGS):
        advance_page(page, PING_INTERVAL_MS)
    expect_still_joined_on_the_first_socket(page, room)


def test_ac6_made_visible_on_a_socket_that_gets_no_frame_it_shows_the_band(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=VISIBILITY_SCRIPT,
    )
    hide_while_timers_run_late(page)

    set_page_hidden(page, False)
    page.wait_for_timeout(STEP_SETTLE_MS)
    expect_still_joined_on_the_first_socket(page, room)

    advance_page(page, BAND_WITHIN_MS)

    expect_offline(page)


def test_ac6_made_visible_while_a_try_waits_on_the_8_second_delay_it_opens_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=VISIBILITY_SCRIPT
    )
    room.connections[0].close(LOST_CLOSE)
    expect_offline(page)
    for latest_ms in FIRST_THREE_DELAYS_LATEST_MS:
        count = len(room.connections)
        advance_page(page, latest_ms)
        room.wait_for_connections(count + 1)
        room.connections[-1].close(LOST_CLOSE)
        page.wait_for_timeout(STEP_SETTLE_MS)
    # Four losses: the next try waits on the 8-second delay.
    set_page_hidden(page, True)
    advance_page(page, WAIT_WHILE_HIDDEN_MS)
    assert len(room.connections) == 4

    set_page_hidden(page, False)

    room.wait_for_connections(5)
    assert first_join(page, room.connections[4]) == STORED_JOIN
    for _ in range(EIGHT_SECOND_DELAY_LATEST_MS // PING_INTERVAL_MS + 1):
        advance_page(page, PING_INTERVAL_MS)
    assert len(room.connections) == 5
