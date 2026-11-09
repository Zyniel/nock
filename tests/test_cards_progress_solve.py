"""Tests of content/cards, AC-12: a solve writes one key.

Browser with the live server serving `CAT` (accounts off, so the account routes are
answered by `page.route`). The device holds `nock.progress` `{"1": "finished"}`;
Ana, signed in on `/`, taps « Jouer » on card 2, which creates a real room and loads
`/r/<code>`. The room's socket is mocked (spec 010's `MockRoomSocket`), so that the
test sends the `grid_solved` itself.

Choices where the spec leaves room:

- `GET /api/account` is asked once by `/` and once by the room page: the first
  request answers `signed_in`, the second one is the case under test.
- "Has not answered": the room page's request is held, the test sends the solve,
  waits for the page to take it (`data-seq` 1) and for a pause, then reads both
  keys; it then answers `signed_in` and expects the mark.
- "Marks nothing yet": both keys are as the tap left them, `nock.account_progress`
  `{"2": "started"}` and `nock.progress` as seeded.
- "Fails": the request is aborted.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, Route, expect

from cards_harness import (
    ACCOUNT_PROGRESS_KEY,
    PROGRESS_KEY,
    ROOM_SOCKET_PATTERN,
    stored_object,
    tap_play,
    wait_for_stored,
)
from nock.grid import Grid
from nock.protocol import GridSolved
from spec010_harness import MockRoomSocket, send_snapshot, settle
from spec032_harness import seed_storage
from spec042_harness import wait_until
from spec046_harness import (
    ACCOUNT_HISTORY_ROUTE,
    ACCOUNT_ROOMS_ROUTE,
    ACCOUNT_ROUTE,
    SIGNED_IN,
    answer_json,
    fulfil_json,
    open_catalogue,
)

CATALOGUE_KIND = "reference"

FINISHED_ONE = {"1": "finished"}
STARTED_TWO = {"2": "started"}
FAILING_STATUS_ANSWERS = ["401", "404", "500", "request fails"]


class RoomStatus:
    """The answers of `GET /api/account`: `/` is signed in, the room page is `kind`.

    `kind` is `held` (the room page's request waits until `release`), a status code
    in decimal, or `request fails`.
    """

    def __init__(self, page: Page, kind: str) -> None:
        self.kind = kind
        self.asked = 0
        self.held: list[Route] = []
        page.route(ACCOUNT_ROUTE, self.handle)

    def handle(self, route: Route) -> None:
        """Answer the status request (`page.route`'s handler)."""
        if route.request.method != "GET":
            route.fallback()
            return
        self.asked += 1
        if self.kind == "signed in" or self.asked == 1:
            fulfil_json(route, 200, SIGNED_IN)
        elif self.kind == "held":
            self.held.append(route)
        elif self.kind == "request fails":
            route.abort()
        else:
            fulfil_json(route, int(self.kind), {"detail": "no"})

    def release(self) -> None:
        """Answer the held request: signed in."""
        for route in self.held:
            fulfil_json(route, 200, SIGNED_IN)


def solve_a_room_from_a_signed_in_tap(
    page: Page, base_url: str, grid: Grid, status_kind: str
) -> RoomStatus:
    """Tap « Jouer » on card 2 signed in, then send the room's `grid_solved`.

    The room page's status request is answered as `status_kind` says (see
    `RoomStatus`). Returns once the page has taken the solve (`data-seq` 1).
    """
    seed_storage(page, {PROGRESS_KEY: json.dumps(FINISHED_ONE)})
    status = RoomStatus(page, status_kind)
    answer_json(page, ACCOUNT_HISTORY_ROUTE, 200, [])
    answer_json(page, ACCOUNT_ROOMS_ROUTE, 200, [])
    mock = MockRoomSocket(page)
    page.route_web_socket(ROOM_SOCKET_PATTERN, mock.handle)
    open_catalogue(page, base_url)
    expect(page.get_by_test_id("account-open")).to_be_visible()

    tap_play(page, 2)

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, STARTED_TWO)
    mock.first_join()
    send_snapshot(mock, grid)
    mock.send(GridSolved(seq=1, elapsed_ms=1000).model_dump_json())
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "1")
    return status


def test_ac12_signed_in_the_solve_sets_the_account_key_and_leaves_the_device_key(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    solve_a_room_from_a_signed_in_tap(page, live_server, fx01_grid, "signed in")

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, {"2": "finished"})
    assert stored_object(page, PROGRESS_KEY) == FINISHED_ONE


def test_ac12_the_solve_waits_for_the_status_and_the_mark_comes_with_the_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    status = solve_a_room_from_a_signed_in_tap(page, live_server, fx01_grid, "held")
    wait_until(page, lambda: len(status.held) == 1, "the held status request")

    settle(page)
    assert stored_object(page, ACCOUNT_PROGRESS_KEY) == STARTED_TWO
    assert stored_object(page, PROGRESS_KEY) == FINISHED_ONE

    status.release()

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, {"2": "finished"})
    assert stored_object(page, PROGRESS_KEY) == FINISHED_ONE


@pytest.mark.parametrize("kind", FAILING_STATUS_ANSWERS)
def test_ac12_without_a_signed_in_answer_the_solve_sets_the_device_key(
    page: Page, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    solve_a_room_from_a_signed_in_tap(page, live_server, fx01_grid, kind)

    wait_for_stored(page, PROGRESS_KEY, {"1": "finished", "2": "finished"})
    assert stored_object(page, ACCOUNT_PROGRESS_KEY) == STARTED_TWO
