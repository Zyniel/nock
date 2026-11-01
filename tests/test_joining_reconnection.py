"""Tests of lobby/joining AC-22 and AC-23: the page's join after a loss.

AC-22 (rules 8.1 and 10): the page rejoins with the identity of its last
snapshot, held in memory, even when the browser refuses storage, and even when
another tab stored a different identity for the same code meanwhile. AC-23 (rule
9): a nickname form kept after a loss has its submit disabled until the next
socket opens.

The page runs on spec 017's mocked socket (`spec017_harness.open_room`), with its
clock frozen before it loads: a new socket opens only when the test moves the
clock by the first retry delay, 1 second (`platform/realtime.md` rule 21), so
what the test does between the loss and the next socket is always done in time.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import ClientMessage, Join, parse_client_message
from spec017_harness import (
    SNAPSHOT_TOKEN,
    MockConnection,
    MockRoom,
    advance_page,
    expect_status,
    grid_from_text,
    open_room,
    player_view,
    snapshot_frame,
    wait_until,
)
from spec035_harness import load_fr
from spec042_harness import make_storage_throw, stored_value

ROOM_CODE = "ABC123"
LOST_CLOSE_CODE = 1011
FIRST_RETRY_MS = 1000  # the first retry delay (`platform/realtime.md` rule 21)
SNAPSHOT_SEQ = 5
WAIT_TIMEOUT_MS = 5000
# The identity another tab stores for the same code while Ana is disconnected.
OTHER_IDENTITY = json.dumps(
    {"player_id": "p7", "resume_token": "other-tab-token-0000007", "nickname": "ZOE"}
)
ANAS_REJOIN = Join(nickname="ANA", resume_token=SNAPSHOT_TOKEN)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def first_frame(page: Page, connection: MockConnection) -> ClientMessage:
    """The first frame the page sent on a socket; fail when it sends none."""
    waited_ms = 0
    while not connection.frames:
        if waited_ms >= WAIT_TIMEOUT_MS:
            status = page.get_by_test_id("room-page").get_attribute("data-status")
            pytest.fail(f"the new socket got no frame; the page status is {status}")
        page.wait_for_timeout(50)
        waited_ms += 50
    return parse_client_message(connection.frames[0])


def enter_from_the_form(page: Page, room: MockRoom, grid: Grid) -> None:
    """Ana enters as `Ana` from the form; the server's snapshot names her `ANA`."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    first = room.connections[0]
    assert first_frame(page, first) == Join(nickname="ANA", resume_token=None)
    players = [player_view("p1", "ANA", 0, True), player_view("p2", "Bob", 1)]
    first.send(snapshot_frame(grid, SNAPSHOT_SEQ, players=players))
    expect_status(page, "joined")


def lose_the_socket(page: Page, room: MockRoom) -> None:
    """Close the page's socket as a loss; return once the page knows it."""
    room.connections[-1].close(LOST_CLOSE_CODE)
    expect_status(page, "reconnecting")


def store_from_another_tab(page: Page, base_url: str, key: str, value: str) -> None:
    """Store `value` under `key` from another tab of the same browser and origin."""
    other_tab = page.context.new_page()
    try:
        other_tab.goto(f"{base_url}/")
        other_tab.evaluate(
            "([key, value]) => localStorage.setItem(key, value)", [key, value]
        )
    finally:
        other_tab.close()


def next_socket(page: Page, room: MockRoom) -> MockConnection:
    """Move the frozen clock by the first retry delay; return the new socket."""
    count = len(room.connections)
    advance_page(page, FIRST_RETRY_MS)
    wait_until(page, lambda: len(room.connections) > count)
    return room.connections[-1]


# ---- AC-22 ----


def test_ac22_a_browser_that_refuses_storage_rejoins_as_ana_after_a_drop(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    make_storage_throw(page)
    room = open_room(page, live_server, frozen=True, identity=False)
    enter_from_the_form(page, room, fx01_grid)
    lose_the_socket(page, room)

    second = next_socket(page, room)

    assert first_frame(page, second) == ANAS_REJOIN
    expect(page.get_by_test_id("nickname-form")).to_be_hidden()


def test_ac22_an_identity_another_tab_stored_meanwhile_does_not_replace_anas(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = open_room(page, live_server, frozen=True, identity=False)
    enter_from_the_form(page, room, fx01_grid)
    lose_the_socket(page, room)
    identity_key = f"nock.identity.{ROOM_CODE}"
    store_from_another_tab(page, live_server, identity_key, OTHER_IDENTITY)
    assert stored_value(page, identity_key) == OTHER_IDENTITY

    second = next_socket(page, room)

    assert first_frame(page, second) == ANAS_REJOIN


# ---- AC-23 ----


def test_ac23_a_kept_form_disables_its_submit_until_the_next_socket_opens(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True, identity=False)
    submit = page.get_by_test_id("nickname-submit")
    expect(submit).to_have_text(load_fr()["join.submit"])
    expect(submit).to_be_enabled()

    room.connections[0].close(LOST_CLOSE_CODE)

    expect_status(page, "connecting")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(submit).to_have_text(load_fr()["join.submit"])
    expect(submit).to_be_disabled()
    advance_page(page, FIRST_RETRY_MS - 1)
    assert len(room.connections) == 1
    expect(submit).to_be_disabled()
    advance_page(page, 1)
    wait_until(page, lambda: len(room.connections) == 2)
    expect(submit).to_be_enabled()
