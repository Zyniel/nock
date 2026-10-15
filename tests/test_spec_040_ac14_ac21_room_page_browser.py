"""Tests of spec 040, AC-14 to AC-21: the pages of the app in a browser.

AC-14 to AC-17 run against the live server (the `live_server` fixture of conftest).
AC-18 to AC-21 replace the room socket with Playwright's `route_web_socket` mock,
send frames built with the `nock.protocol` models, and read the `data-*` attributes
of the room page: the events are applied in `seq` order and a closed socket sets
the status.

The shared setup is in `tests/spec040_harness.py`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Protocol

import pytest
from playwright.sync_api import Page, WebSocketRoute, expect

from nock.grid import Grid
from nock.protocol import (
    Join,
    LetterChanged,
    PlayerState,
    PlayerView,
    RevealBudget,
    Snapshot,
    grid_view,
    parse_client_message,
)
from nock.server import RoomRegistry
from spec040_harness import EXPECTED_SETTINGS, grid_from_text, load_fr

SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Mocked room socket (browser tests) --------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def close(self, code: int) -> None:
        self.routes[0].close(code=code)

    def wait_for_join(self) -> None:
        wait_until(self.page, lambda: len(self.received) > 0)


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to process frames that must change nothing."""
    page.wait_for_timeout(300)


FORM_TIMEOUT_MS = 5000


def submit_nickname_form(page: Page, nickname: str = "Ana") -> None:
    """Fill the nickname form of spec 012 and submit it with Enter."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)


def open_mock_room(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket, submit the form, wait for the join."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    submit_nickname_form(page)
    mock.wait_for_join()
    return mock


def snapshot_frame(grid: Grid, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=grid_view(grid),
        players=(
            PlayerView(
                player_id="p1",
                nickname="Ana",
                colour=0,
                state=PlayerState.ACTIVE,
                is_host=True,
                muted=False,
                selection=None,
            ),
        ),
        settings=EXPECTED_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def event_frame(seq: int) -> str:
    event = LetterChanged(
        seq=seq, row=1, column=0, letter="T", pencil=False, player_id="p1"
    )
    return event.model_dump_json()


def joined_mock_room(page: Page, base_url: str, grid: Grid, seq: int) -> MockRoomSocket:
    """Open /r/ABC123, send a snapshot of `seq` and wait until it is shown."""
    mock = open_mock_room(page, base_url)
    mock.send(snapshot_frame(grid, seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    return mock


# ---- AC-14 to AC-17: browser, live server -----------------------------------


def test_ac14_catalogue_page_is_shown_on_root(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/")

    catalogue = page.get_by_test_id("catalogue-page")
    expect(catalogue).to_be_visible()
    expect(catalogue).to_contain_text(load_fr()["catalogue.heading"])
    expect(catalogue).to_contain_text(load_fr()["catalogue.empty"])
    expect(page.get_by_test_id("room-page")).to_have_count(0)


@pytest.mark.parametrize("path", ["/", "/r/ABC123"])
def test_ac15_title_and_language(page: Page, live_server: str, path: str) -> None:
    page.goto(f"{live_server}{path}")

    expect(page).to_have_title(load_fr()["app.title"])
    expect(page.locator("html")).to_have_attribute("lang", "fr")


def test_ac16_room_page_joins_and_shows_the_grid(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)

    enter_room(page, f"{live_server}/r/{code}")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-room-code", code)
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-seq", "1")
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joined"]
    )
    expected_heading = load_fr()["room.heading"].replace("{code}", code)
    expect(room).to_contain_text(expected_heading)
    expect(page.get_by_test_id("catalogue-page")).to_have_count(0)


def test_ac17_unknown_room_shows_not_found(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(room).to_have_attribute("data-seq", "")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.not_found"]
    )


# ---- AC-18 to AC-21: browser, mocked socket ---------------------------------


def test_ac18_page_shows_the_form_then_sends_the_join_of_the_form(
    page: Page, live_server: str
) -> None:
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{live_server}/r/ABC123")
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    page.wait_for_timeout(300)
    assert mock.received == []

    submit_nickname_form(page, "Ana")

    mock.wait_for_join()
    first_message = parse_client_message(mock.received[0])
    assert first_message == Join(nickname="Ana", resume_token=None)
    assert len(mock.routes) == 1


def test_ac18_before_a_snapshot_the_page_is_joining(
    page: Page, live_server: str
) -> None:
    open_mock_room(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-room-code", "ABC123")
    expect(room).to_have_attribute("data-status", "joining")
    expect(room).to_have_attribute("data-seq", "")
    expect(room).to_have_attribute("data-grid", "")
    expect(room).to_have_attribute("data-pending", "0")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joining"]
    )


def test_ac19_events_are_ordered_and_gaps_buffered(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-grid", "5x5")

    for seq in (4, 5, 7):
        mock.send(event_frame(seq))
    expect(room).to_have_attribute("data-pending", "1")
    expect(room).to_have_attribute("data-seq", "5")

    mock.send(event_frame(6))
    expect(room).to_have_attribute("data-seq", "7")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_next_event_is_applied_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_duplicate_buffered_event_is_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(7))
    mock.send(event_frame(7))
    expect(room).to_have_attribute("data-pending", "1")
    settle(page)

    expect(room).to_have_attribute("data-pending", "1")
    expect(room).to_have_attribute("data-seq", "5")


def test_ac19_a_gap_that_never_fills_keeps_the_buffer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(8))
    mock.send(event_frame(10))
    expect(room).to_have_attribute("data-pending", "2")
    settle(page)

    expect(room).to_have_attribute("data-pending", "2")
    expect(room).to_have_attribute("data-seq", "5")
    assert len(mock.received) == 1


def test_ac19_junk_frames_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send("not json")
    mock.send("[1, 2]")
    mock.send('{"seq": 6}')
    mock.send('{"type": 3, "seq": 6}')
    mock.send("null")
    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")
    expect(room).to_have_attribute("data-status", "joined")


def test_ac19_events_before_the_first_snapshot_are_dropped(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(1))
    mock.send(snapshot_frame(fx01_grid, 0))
    expect(room).to_have_attribute("data-seq", "0")
    settle(page)

    expect(room).to_have_attribute("data-seq", "0")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_second_snapshot_replaces_the_first(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(8))
    expect(room).to_have_attribute("data-pending", "1")
    mock.send(snapshot_frame(fx01_grid, 7))

    expect(room).to_have_attribute("data-seq", "8")
    expect(room).to_have_attribute("data-pending", "0")


def test_ac19_a_second_snapshot_drops_buffered_events_it_includes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")

    mock.send(event_frame(7))
    expect(room).to_have_attribute("data-pending", "1")
    mock.send(snapshot_frame(fx01_grid, 9))

    expect(room).to_have_attribute("data-seq", "9")
    expect(room).to_have_attribute("data-pending", "0")
    settle(page)
    expect(room).to_have_attribute("data-seq", "9")


def test_ac20_events_without_seq_change_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 5)
    room = page.get_by_test_id("room-page")
    selection_moved = (
        '{"type": "selection_moved", "player_id": "p1", "selection": '
        '{"row": 1, "column": 0, "direction": "across"}}'
    )
    reaction = (
        '{"type": "reaction", "player_id": "p2", "clue": '
        '{"row": 0, "column": 3, "clue_index": 0}, "reaction": "wow"}'
    )
    error = '{"type": "error", "code": "cell_locked", "message": "cell is locked"}'

    for frame in (selection_moved, reaction, error):
        mock.send(frame)
    mock.send(event_frame(6))

    expect(room).to_have_attribute("data-seq", "6")
    expect(room).to_have_attribute("data-pending", "0")
    expect(room).to_have_attribute("data-status", "joined")


def test_ac21_other_close_codes_mean_reconnecting(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = joined_mock_room(page, live_server, fx01_grid, 0)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.reconnecting"]
    )
    expect(page.get_by_test_id("connection-banner")).to_be_visible()


def test_ac21_close_before_a_snapshot_keeps_seq_empty(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)

    mock.close(1011)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "connecting")
    expect(room).to_have_attribute("data-seq", "")
    expect(page.get_by_test_id("connection-banner")).to_be_hidden()


def test_ac21_close_4404_means_not_found(page: Page, live_server: str) -> None:
    mock = open_mock_room(page, live_server)

    mock.close(4404)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(room).to_have_attribute("data-seq", "")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.not_found"]
    )
