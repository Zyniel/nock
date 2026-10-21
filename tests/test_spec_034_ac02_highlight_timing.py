"""Tests of spec 034, AC-2: the highlight lasts 5 seconds.

Measured with Playwright's waiting assertions from the moment `room-page` gets its
`data-catch-up` value (spec's "Test harness", "Highlight timing"). The check that
the marks are still there 4,500 ms after it measures a time window, so this file
runs in the serial pass (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`). The
shared setup is in `spec034_harness`.
"""

from __future__ import annotations

import time

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import Direction, Selection
from spec034_harness import (
    CatchUpRoute,
    catch_up_json,
    catch_up_marks,
    caught_up_values,
    cell_at,
    expect_catch_up_applied,
    expected_caught_up,
    grid_from_text,
    marks_by_cell,
    open_mocked_room,
    reconnect_with_snapshot,
    record_with,
    snapshot_players,
)

STILL_ON_MS = 4_500
GONE_BY_MS = 6_000
SECOND_CATCH_UP_DELAY_MS = 2_000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def wait_until_ms_after(page: Page, start: float, milliseconds: int) -> None:
    """Wait until `milliseconds` have passed since the monotonic time `start`.

    The wait is the page's, so that the mocked socket keeps answering pings.
    """
    remaining_ms = (start + milliseconds / 1000 - time.monotonic()) * 1000
    if remaining_ms > 0:
        page.wait_for_timeout(remaining_ms)


def ms_left_until(start: float, milliseconds: int) -> float:
    """The milliseconds left until `milliseconds` after `start` (at least 1)."""
    left = (start + milliseconds / 1000 - time.monotonic()) * 1000
    return max(left, 1.0)


def test_ac2_the_marks_stay_4500_ms_and_are_gone_6000_ms_after_the_catch_up(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute(answer=catch_up_json(5, 9, cells=[(1, 0), (2, 2)]))
    bob_selection = Selection(row=2, column=2, direction=Direction.ACROSS)
    open_mocked_room(
        page,
        live_server,
        fx01_grid,
        route,
        record=record_with(5),
        seq=9,
        players=snapshot_players(bob_selection=bob_selection),
    )
    expect_catch_up_applied(page, "5-9")
    applied_at = time.monotonic()

    wait_until_ms_after(page, applied_at, STILL_ON_MS)
    assert marks_by_cell(page) == {(1, 0): 1, (2, 2): 1}

    expect(catch_up_marks(page)).to_have_count(
        0, timeout=ms_left_until(applied_at, GONE_BY_MS)
    )
    assert caught_up_values(page) == expected_caught_up([])


def test_ac2_a_later_catch_up_starts_the_cells_5000_ms_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    mock = open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(5), seq=9
    )
    route.wait_for_requests(page, 1)
    route.answer_json(0, catch_up_json(5, 9, cells=[(1, 0)]))
    expect_catch_up_applied(page, "5-9")
    page.wait_for_timeout(SECOND_CATCH_UP_DELAY_MS)

    reconnect_with_snapshot(mock, fx01_grid, 15)
    route.wait_for_requests(page, 2)
    route.answer_json(1, catch_up_json(9, 15, cells=[(1, 0)]))
    expect_catch_up_applied(page, "9-15")
    again_at = time.monotonic()

    wait_until_ms_after(page, again_at, STILL_ON_MS)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-caught-up", "true", timeout=1)
    expect(cell_at(page, 1, 0)).to_have_attribute(
        "data-caught-up", "false", timeout=ms_left_until(again_at, GONE_BY_MS)
    )
