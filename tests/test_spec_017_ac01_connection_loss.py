"""Tests of spec 017, AC-1: the banner, the heartbeat and the reconnection.

The page is tested with spec 040's mocked socket: a test counts the sockets the
page opens, answers pings (or not), closes a socket and sends snapshots. The
bounds the spec states in real seconds (the banner within 5,000 ms) are measured
with Playwright's waiting assertions; the constants (ping every 2,000 ms, 4,000 ms
of silence, the reconnect delays) on the page clock, which is frozen before the
page loads and moved by hand with `advance_page`. The shared setup is in
`spec017_harness`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import ErrorCode
from spec017_harness import (
    LOSS_BUDGET_MS,
    SETTLE_MS,
    STEP_SETTLE_MS,
    STORED_JOIN,
    advance_page,
    banner,
    cell_at,
    error_frame,
    expect_cell,
    expect_new_connection_after,
    expect_offline,
    expect_status,
    first_join,
    grid_from_text,
    joined_room,
    open_room,
    room_page,
    settle,
    snapshot_frame,
    wait_until,
)

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
SELECTION_MOVED_FRAME = (
    '{"type": "selection_moved", "player_id": "p2", "selection": '
    '{"row": 1, "column": 0, "direction": "across"}}'
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- fr.json (AC-1) ----------------------------------------------------------


def test_ac1_fr_json_holds_the_reconnection_texts() -> None:
    messages = load_fr()

    assert messages["room.status.reconnecting"] == "Reconnexion…"
    assert messages["room.banner.offline"] == (
        "Connexion perdue. Vous pouvez continuer : vos lettres seront "
        "envoyées au retour du réseau."
    )


# ---- AC-1: the banner and typing offline (real time) -------------------------


def test_ac1_a_socket_closed_with_1011_shows_the_banner_and_typing_goes_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    first = room.connections[0]

    first.close(1011)

    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    expect(banner(page)).to_have_attribute("role", "status")
    expect_status(page, "reconnecting")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.reconnecting"]
    )
    frames_at_loss = len(first.frames)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    settle(page)
    assert len(first.frames) == frames_at_loss
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    assert second.edits() == []

    second.send(snapshot_frame(fx01_grid, 5))

    expect(banner(page)).to_be_hidden()
    expect_status(page, "joined")


def test_ac1_a_silent_socket_shows_the_banner_within_5_seconds_of_the_last_frame(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    first = room.connections[0]
    wait_until(page, lambda: first.ping_count() >= 1)
    room.answer_pings = False
    answered_until = room.last_sent_at
    elapsed_ms = int((time.monotonic() - answered_until) * 1000)
    remaining_ms = max(1, LOSS_BUDGET_MS - elapsed_ms)

    expect(banner(page)).to_be_visible(timeout=remaining_ms)

    expect_status(page, "reconnecting")
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    room.wait_for_connections(2)
    room.connections[1].send(snapshot_frame(fx01_grid, 5))
    expect(banner(page)).to_be_hidden()
    expect_status(page, "joined")


# ---- AC-1: heartbeat and loss detection (page clock) -------------------------


def test_ac1_the_page_pings_every_2_seconds_while_the_socket_is_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]
    pings_before = connection.ping_count()

    advance_page(page, 1999)
    assert connection.ping_count() == pings_before

    advance_page(page, 1)
    wait_until(page, lambda: connection.ping_count() > pings_before)
    assert connection.ping_count() == pings_before + 1
    for expected_more in (2, 3, 4):
        advance_page(page, 2000)
        assert connection.ping_count() == pings_before + expected_more
    expect_status(page, "joined")
    assert len(room.connections) == 1


def test_ac1_a_ping_in_the_wire_format_of_spec_039(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]

    advance_page(page, 2000)
    wait_until(page, lambda: connection.ping_count() >= 1)

    ping_frames = [f for f in connection.frames if json.loads(f)["type"] == "ping"]
    assert [json.loads(frame) for frame in ping_frames] == [{"type": "ping"}]


def test_ac1_answered_pings_keep_the_connection_open_for_a_long_time(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    for _ in range(10):
        advance_page(page, 2000)

    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    assert len(room.connections) == 1


def test_ac1_a_socket_silent_for_4_seconds_is_given_up_and_lost(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True, answer_pings=False)

    advance_page(page, 3900)
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()

    # The last frame (the snapshot) arrived at page time 1, so the 4 s of
    # silence end at page time 4001, the end of this advance (timers fire
    # inclusively at the end of an advance).
    advance_page(page, 100)

    expect_offline(page)
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    assert len(room.connections) == 1
    expect_new_connection_after(page, room, 1000)


def test_ac1_a_frame_of_any_kind_restarts_the_4_seconds_of_silence(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True, answer_pings=False)
    advance_page(page, 3000)
    room.connections[0].send(SELECTION_MOVED_FRAME)
    page.wait_for_timeout(STEP_SETTLE_MS)

    advance_page(page, 3000)
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()

    advance_page(page, 1500)

    expect_offline(page)


# ---- AC-1: reconnect delays (page clock) -------------------------------------


def test_ac1_the_delays_are_1_2_4_8_then_8_seconds(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)

    for index, delay_ms in enumerate([1000, 2000, 4000, 8000, 8000, 8000]):
        expect_new_connection_after(page, room, delay_ms)
        assert first_join(page, room.connections[index + 1]) == STORED_JOIN
        room.connections[index + 1].close(1011)
        page.wait_for_timeout(STEP_SETTLE_MS)

    expect_status(page, "reconnecting")


def test_ac1_the_delays_start_again_from_the_first_after_a_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    expect_new_connection_after(page, room, 1000)
    room.connections[1].close(1011)
    page.wait_for_timeout(STEP_SETTLE_MS)
    expect_new_connection_after(page, room, 2000)

    room.connections[2].send(snapshot_frame(fx01_grid, 5))
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    room.connections[2].close(1011)
    expect_offline(page)

    expect_new_connection_after(page, room, 1000)


def test_ac1_the_online_event_reconnects_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    page.wait_for_timeout(STEP_SETTLE_MS)
    assert len(room.connections) == 1

    page.evaluate("window.dispatchEvent(new Event('online'))")

    room.wait_for_connections(2)
    assert first_join(page, room.connections[1]) == STORED_JOIN


@pytest.mark.parametrize("code", [1000, 1001, 1011, 4408])
def test_ac1_any_other_close_code_is_a_lost_connection(
    page: Page, live_server: str, fx01_grid: Grid, code: int
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    room.connections[0].close(code)

    expect_offline(page)
    expect_new_connection_after(page, room, 1000)


# ---- AC-1: final states ------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "status"),
    [(4404, "not_found"), (4429, "throttled"), (4001, "replaced")],
)
def test_ac1_a_final_close_code_ends_the_attempts(
    page: Page, live_server: str, fx01_grid: Grid, code: int, status: str
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    room.connections[0].close(code)

    expect_status(page, status)
    expect(banner(page)).to_be_hidden()
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect_status(page, status)
    expect(banner(page)).to_be_hidden()


def test_ac1_a_close_that_follows_room_full_ends_the_attempts(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(ErrorCode.ROOM_FULL))
    connection.close(1000)

    expect_status(page, "full")
    expect(banner(page)).to_be_hidden()
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect_status(page, "full")


@pytest.mark.parametrize("error_code", [ErrorCode.ROOM_LOCKED, ErrorCode.REMOVED])
def test_ac1_a_close_that_follows_locked_or_removed_ends_the_attempts(
    page: Page, live_server: str, error_code: ErrorCode
) -> None:
    """The status value is spec 014's (not built yet): only the end is checked."""
    room = open_room(page, live_server, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(error_code))
    connection.close(1000)

    page.wait_for_timeout(STEP_SETTLE_MS)
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).not_to_have_attribute("data-status", "reconnecting")
    expect(room_page(page)).not_to_have_attribute("data-status", "connecting")
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect(banner(page)).to_be_hidden()


def test_ac1_a_close_after_an_error_that_is_not_final_is_a_lost_connection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(ErrorCode.CELL_LOCKED))
    connection.close(1011)

    expect_offline(page)
    expect_new_connection_after(page, room, 1000)


# ---- AC-1: before the first snapshot -----------------------------------------


def test_ac1_a_loss_before_the_first_snapshot_retries_without_a_banner(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)

    room.connections[0].close(1011)

    expect_status(page, "connecting")
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).to_have_attribute("data-seq", "")
    expect_new_connection_after(page, room, 1000)
    assert first_join(page, room.connections[1]) == STORED_JOIN
    expect(banner(page)).to_be_hidden()


def test_ac1_before_the_first_snapshot_the_delays_grow_too(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)
    room.connections[0].close(1011)
    expect_status(page, "connecting")

    expect_new_connection_after(page, room, 1000)
    room.connections[1].close(1011)
    page.wait_for_timeout(STEP_SETTLE_MS)

    expect_new_connection_after(page, room, 2000)
    expect(banner(page)).to_be_hidden()


def test_ac1_the_nickname_form_stays_when_the_socket_is_lost_before_a_join(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True, identity=False)
    expect(page.get_by_test_id("nickname-form")).to_be_visible()

    room.connections[0].close(1011)
    page.wait_for_timeout(SETTLE_MS)

    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(banner(page)).to_be_hidden()
    expect_new_connection_after(page, room, 1000)
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
