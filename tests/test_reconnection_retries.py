"""Tests of `platform/reconnection.md` AC-7 and AC-8: the connect limit and the jitter
of the retry delays.

Rule 6. Spec 017's mocked room (`joined_room`) on the frozen page clock, with the
socket stand-ins of `reconnection_harness`, which note the page clock at the
creation of every socket (`window.__socketTimes`): a test reads exactly when each
try came.

AC-7: after a loss, a socket the network never answers (`window.__hangNext`) is
dropped (the page closes it) 6 seconds after it was created, not 1 ms before, and
the next socket comes
after the second delay, 1.6 to 2.4 seconds later. A socket whose `open` the test
holds (`window.__holdOpenNext`) and lets go 5 seconds after its creation is kept:
it joins, takes its snapshot and is still the page's socket past the 6 seconds.

AC-8: with `Math.random` at its lowest or highest (`reconnection_harness`'s
reading), five losses in a row are each followed by a try exactly 0.8, 1.6, 3.2,
6.4, 6.4 or 1.2, 2.4, 4.8, 9.6, 9.6 seconds later (to the millisecond); after a
snapshot the next loss is followed by a try after the first delay again.

All durations are page-clock time, so this file runs in the parallel pass.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from reconnection_harness import (
    RANDOM_AT_HIGHEST_SCRIPT,
    RANDOM_AT_LOWEST_SCRIPT,
    SOCKET_STAND_INS_SCRIPT,
    advance_page_short_of,
    advance_page_to,
    page_number,
    page_time,
    release_open,
    socket_times,
)
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
    snapshot_frame,
    wait_until,
)

LOST_CLOSE = 1011
CONNECT_LIMIT_MS = 6000
OPENS_AFTER_MS = 5000  # AC-7's slow socket opens 5 s after it was created
PAST_THE_LIMIT_MS = 2000  # how far past the opening the kept socket is watched
FIRST_DELAY_LATEST_MS = 1200
SECOND_DELAY_EARLIEST_MS = 1600
SECOND_DELAY_LATEST_MS = 2400
LOWEST_DELAYS_MS = [800, 1600, 3200, 6400, 6400]
HIGHEST_DELAYS_MS = [1200, 2400, 4800, 9600, 9600]
DRAWS = [
    pytest.param(RANDOM_AT_LOWEST_SCRIPT, LOWEST_DELAYS_MS, id="lowest"),
    pytest.param(RANDOM_AT_HIGHEST_SCRIPT, HIGHEST_DELAYS_MS, id="highest"),
]


def lose_the_first_socket(page: Page, room: MockRoom) -> None:
    """Close the joined page's socket with 1011 and wait until the page shows it."""
    room.connections[0].close(LOST_CLOSE)
    expect_offline(page)


def next_try_after(page: Page, room: MockRoom, delay_ms: int) -> float:
    """Move the page clock `delay_ms` past a loss; return when the next try came.

    Args:
        page: The page, its clock frozen at the moment of the loss.
        room: Its mocked room.
        delay_ms: How far to move the page clock, in milliseconds.

    Returns:
        How long after the loss the one new socket was created, in page ms.
    """
    count = len(room.connections)
    lost_at = page_time(page)
    advance_page(page, delay_ms + 1)
    room.wait_for_connections(count + 1)
    assert len(room.connections) == count + 1
    return socket_times(page)[-1] - lost_at


def close_newest(page: Page, room: MockRoom) -> None:
    """Close the newest socket with 1011: one more loss."""
    room.connections[-1].close(LOST_CLOSE)
    page.wait_for_timeout(STEP_SETTLE_MS)


# ---- AC-7: the 6-second connect limit ---------------------------------------------


def test_ac7_a_socket_never_answered_is_dropped_at_6_seconds_then_the_second_delay(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=SOCKET_STAND_INS_SCRIPT
    )
    lose_the_first_socket(page, room)
    page.evaluate("window.__hangNext = true")
    advance_page(page, FIRST_DELAY_LATEST_MS)
    wait_until(page, lambda: page_number(page, "window.__hung") == 1)
    page.evaluate("window.__hangNext = false")
    created_at = socket_times(page)[-1]

    advance_page_short_of(page, created_at + CONNECT_LIMIT_MS - 1)
    assert page_number(page, "window.__hungCloses") == 0
    advance_page_to(page, created_at + CONNECT_LIMIT_MS)
    assert page_number(page, "window.__hungCloses") == 1
    dropped_at = page_number(page, "window.__hungClosedAt")
    assert round(dropped_at - created_at) == CONNECT_LIMIT_MS
    assert len(room.connections) == 1

    advance_page_to(page, dropped_at + SECOND_DELAY_LATEST_MS)

    room.wait_for_connections(2)
    times = socket_times(page)
    assert len(times) == 3
    assert SECOND_DELAY_EARLIEST_MS <= times[2] - dropped_at <= SECOND_DELAY_LATEST_MS
    assert first_join(page, room.connections[1]) == STORED_JOIN


def test_ac7_a_socket_that_opens_5_seconds_after_it_was_created_is_kept_and_joins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=SOCKET_STAND_INS_SCRIPT
    )
    lose_the_first_socket(page, room)
    page.evaluate("window.__holdOpenNext = true")
    advance_page(page, FIRST_DELAY_LATEST_MS)
    room.wait_for_connections(2)
    slow = room.connections[1]
    created_at = socket_times(page)[-1]
    advance_page_to(page, created_at + OPENS_AFTER_MS)
    assert slow.frames == []

    release_open(page)

    assert first_join(page, slow) == STORED_JOIN
    slow.send(snapshot_frame(fx01_grid, 5))
    expect_status(page, "joined")
    advance_page(page, PAST_THE_LIMIT_MS)
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    assert len(room.connections) == 2
    assert page.evaluate("window.__pageCloses") == []


# ---- AC-8: the jitter of the retry delays -------------------------------------------


@pytest.mark.parametrize(("draw_script", "delays_ms"), DRAWS)
def test_ac8_the_tries_after_successive_losses_follow_the_random_draw(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    draw_script: str,
    delays_ms: list[int],
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        init_script=SOCKET_STAND_INS_SCRIPT + draw_script,
    )
    lose_the_first_socket(page, room)

    measured_ms: list[int] = []
    for delay_ms in delays_ms:
        measured_ms.append(round(next_try_after(page, room, delay_ms)))
        close_newest(page, room)

    assert measured_ms == delays_ms
    expect_status(page, "reconnecting")


@pytest.mark.parametrize(("draw_script", "delays_ms"), DRAWS)
def test_ac8_after_a_snapshot_the_next_loss_waits_the_first_delay_again(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    draw_script: str,
    delays_ms: list[int],
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        init_script=SOCKET_STAND_INS_SCRIPT + draw_script,
    )
    lose_the_first_socket(page, room)
    next_try_after(page, room, delays_ms[0])
    close_newest(page, room)
    next_try_after(page, room, delays_ms[1])
    room.connections[-1].send(snapshot_frame(fx01_grid, 5))
    expect_status(page, "joined")
    close_newest(page, room)
    expect_offline(page)

    measured_ms = round(next_try_after(page, room, delays_ms[0]))

    assert measured_ms == delays_ms[0]
