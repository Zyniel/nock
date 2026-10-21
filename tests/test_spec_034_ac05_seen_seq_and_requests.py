"""Tests of spec 034, AC-5: the page remembers what it saw and asks only on a return.

Browser with the mocked socket and the mocked catch-up: the room record's
`seen_seq`, the request on a return (after a reconnection too), no request on a
first visit or without new events, a failed request, and an answer dropped
because a newer snapshot came. The waits "within 1 second" and "within 2
seconds" only wait for a change that must not come, so this file runs in the
parallel pass. The shared setup is in `spec034_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from spec034_harness import (
    ROOM_RECORD_KEY,
    WAIT_TIMEOUT_MS,
    CatchUpRoute,
    JsonObject,
    MockRoom,
    catch_up_json,
    caught_up_values,
    cell_at,
    expect_catch_up_applied,
    expect_seq,
    expected_caught_up,
    feed_item_locator,
    grid_from_text,
    letter_frame,
    open_mocked_room,
    reconnect_with_snapshot,
    record_with,
    request_body,
    room_page,
    wait_until,
)

NO_REQUEST_MS = 1_000
NO_RETRY_MS = 2_000
DROPPED_ANSWER_MS = 500


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def stored_record(page: Page) -> object:
    """`nock.room.ABC123` parsed, or None when it is not stored."""
    text = page.evaluate("key => localStorage.getItem(key)", ROOM_RECORD_KEY)
    if text is None:
        return None
    return json.loads(text)


def wait_for_record(page: Page, expected: JsonObject) -> None:
    """Wait until the stored room record parses to `expected`, else fail."""
    waited_ms = 0
    record = stored_record(page)
    while record != expected:
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"the room record is {record}, not {expected}")
        page.wait_for_timeout(50)
        waited_ms += 50
        record = stored_record(page)


def has_sent_t_at_1_0(mock: MockRoom) -> bool:
    """Whether the page sent an `edit_letter` of `T` at (1, 0) on its socket."""
    for edit in mock.latest().edit_letters():
        if (edit.row, edit.column, edit.letter) == (1, 0, "T"):
            return True
    return False


def test_ac5_a_first_visit_sends_no_catch_up_request(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    record = {"grid": 1, "selection": None}
    open_mocked_room(page, live_server, fx01_grid, route, record=record, seq=5)

    expect(room_page(page)).to_have_attribute("data-catch-up", "")
    page.wait_for_timeout(NO_REQUEST_MS)

    assert route.bodies == []
    expect(room_page(page)).to_have_attribute("data-catch-up", "")


def test_ac5_the_record_keeps_the_seen_seq_of_each_snapshot_and_event(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    record = {"grid": 1, "selection": None}
    mock = open_mocked_room(page, live_server, fx01_grid, route, record=record, seq=5)

    wait_for_record(page, {"grid": 1, "selection": None, "seen_seq": 5})
    mock.send(letter_frame(6, 2, 1, "V"))
    mock.send(letter_frame(7, 2, 2, "I"))
    expect_seq(page, 7)

    wait_for_record(page, {"grid": 1, "selection": None, "seen_seq": 7})


def test_ac5_a_page_with_no_room_record_creates_one_for_the_seen_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    open_mocked_room(page, live_server, fx01_grid, route, record=None, seq=5)

    wait_for_record(page, {"grid": None, "selection": None, "seen_seq": 5})


def test_ac5_a_return_sends_one_request_with_the_seen_and_snapshot_seqs(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=9)

    route.wait_for_requests(page, 1)
    page.wait_for_timeout(NO_REQUEST_MS)

    assert route.parsed_bodies() == [request_body(5, 9)]


def test_ac5_a_reconnection_after_new_events_asks_for_their_catch_up(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    record = {"grid": 1, "selection": None}
    mock = open_mocked_room(page, live_server, fx01_grid, route, record=record, seq=5)
    mock.send(letter_frame(6, 2, 1, "V"))
    mock.send(letter_frame(7, 2, 2, "I"))
    expect_seq(page, 7)
    wait_for_record(page, {"grid": 1, "selection": None, "seen_seq": 7})

    reconnect_with_snapshot(mock, fx01_grid, 12)

    route.wait_for_requests(page, 1)
    page.wait_for_timeout(NO_REQUEST_MS)
    assert route.parsed_bodies() == [request_body(7, 12)]


@pytest.mark.parametrize("snapshot_seq", [9, 4], ids=["same-seq", "lower-seq"])
def test_ac5_a_snapshot_with_no_new_event_sends_no_request(
    page: Page, live_server: str, fx01_grid: Grid, snapshot_seq: int
) -> None:
    route = CatchUpRoute()
    open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(9), seq=snapshot_seq
    )

    expect(room_page(page)).to_have_attribute("data-catch-up", "")
    page.wait_for_timeout(NO_REQUEST_MS)

    assert route.bodies == []
    expect(room_page(page)).to_have_attribute("data-catch-up", "")


@pytest.mark.parametrize("seen_seq", ["5", -1, 2.5], ids=["text", "negative", "half"])
def test_ac5_a_stored_seen_seq_that_is_not_a_whole_number_reads_as_absent(
    page: Page, live_server: str, fx01_grid: Grid, seen_seq: object
) -> None:
    route = CatchUpRoute()
    open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(seen_seq), seq=9
    )

    expect(room_page(page)).to_have_attribute("data-catch-up", "")
    page.wait_for_timeout(NO_REQUEST_MS)

    assert route.bodies == []


@pytest.mark.parametrize("failure", ["status-500", "abort"])
def test_ac5_a_failed_request_shows_nothing_and_is_not_retried(
    page: Page, live_server: str, fx01_grid: Grid, failure: str
) -> None:
    route = CatchUpRoute()
    mock = open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(5), seq=9
    )
    route.wait_for_requests(page, 1)

    if failure == "abort":
        route.abort(0)
    else:
        route.answer_status(0, 500)
    page.wait_for_timeout(NO_RETRY_MS)

    assert len(route.bodies) == 1
    assert caught_up_values(page) == expected_caught_up([])
    expect(feed_item_locator(page)).to_have_count(0)
    expect(room_page(page)).to_have_attribute("data-catch-up", "")
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    wait_until(page, lambda: has_sent_t_at_1_0(mock), "the edit_letter of T at (1, 0)")


def test_ac5_an_answer_for_an_older_snapshot_is_dropped(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    mock = open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(5), seq=9
    )
    route.wait_for_requests(page, 1)

    reconnect_with_snapshot(mock, fx01_grid, 15)
    route.wait_for_requests(page, 2)
    assert route.parsed_bodies() == [request_body(5, 9), request_body(9, 15)]

    route.answer_json(0, catch_up_json(5, 9, cells=[(1, 0)]))
    page.wait_for_timeout(DROPPED_ANSWER_MS)
    expect(room_page(page)).to_have_attribute("data-catch-up", "", timeout=1)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-caught-up", "false", timeout=1)

    route.answer_json(1, catch_up_json(9, 15, cells=[(2, 2)]))
    expect_catch_up_applied(page, "9-15")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-caught-up", "true")
