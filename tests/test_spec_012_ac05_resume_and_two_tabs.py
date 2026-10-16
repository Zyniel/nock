"""Tests of spec 012, AC-5: disconnection, resume and two tabs.

Reloading the page keeps the same player. The rules (`disconnect_player` and
`join_room` with a token), the real WebSocket and the browser, with the live server
and with spec 040's mocked socket. The shared setup is in `spec012_harness`.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

import nock.hub
import nock.room
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    PlayerJoined,
    PlayerState,
    PlayerStateChanged,
    Snapshot,
)
from nock.room import (
    LogEntry,
    disconnect_player,
    snapshot_for,
)
from spec012_harness import (
    NOW,
    OTHER_TOKEN,
    active_view,
    close_code_of_next_read,
    expect_joined_seqs,
    grid_from_text,
    join_as,
    load_fr,
    make_app,
    make_dist_dir,
    make_player,
    make_registry,
    make_state,
    open_mock_room,
    receive_message,
    run_join,
    settle,
    snapshot_frame,
    submit_form,
    three_players,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry that ticks fast and never times a silent socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def ws_client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One client, one event loop, on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as client:
        yield client


SETTLE_SECONDS = 0.4
SESSION_REPLACED = 4001


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


# ---- AC-5: disconnection, resume, two tabs ---------------------------------------


def test_ac5_disconnect_player_keeps_the_seat_and_tells_the_others(
    fx01_grid: Grid,
) -> None:
    host = make_player(0, "ANA", is_host=True)
    other = make_player(1, "BOB")
    state = make_state(fx01_grid, [host, other])

    outcome = disconnect_player(state, "player0", NOW)

    assert outcome.state.seq == 3
    assert outcome.state.players[0] == host.model_copy(
        update={"state": PlayerState.DISCONNECTED, "disconnected_at": NOW}
    )
    assert outcome.state.players[1] == other
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=PlayerStateChanged(
                seq=3, player_id="player0", state=PlayerState.DISCONNECTED
            ),
        ),
    )


def test_ac5_disconnecting_an_idle_player_marks_them_disconnected(
    fx01_grid: Grid,
) -> None:
    idle = make_player(1, "BOB", state=PlayerState.IDLE)
    state = make_state(fx01_grid, [make_player(0, "ANA", is_host=True), idle])

    outcome = disconnect_player(state, "player1", NOW)

    assert outcome.state.players[1].state is PlayerState.DISCONNECTED
    assert outcome.state.players[1].disconnected_at == NOW
    assert len(outcome.entries) == 1


def test_ac5_disconnecting_twice_or_an_unknown_player_changes_nothing(
    fx01_grid: Grid,
) -> None:
    away = make_player(1, "BOB", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [make_player(0, "ANA", is_host=True), away])

    again = disconnect_player(state, "player1", NOW)
    unknown = disconnect_player(state, "nobody", NOW)

    for outcome in (again, unknown):
        assert outcome.state == state
        assert outcome.entries == ()


def test_ac5_resume_of_a_disconnected_player_brings_them_back(
    fx01_grid: Grid,
) -> None:
    host = make_player(0, "ANA", is_host=True)
    away = make_player(1, "BOB", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host, away])

    outcome = run_join(state, "Autre", 9, token="resume-token-number-1")

    assert outcome.state.seq == 3
    assert outcome.state.players[0] == host
    assert outcome.state.players[1] == away.model_copy(
        update={
            "state": PlayerState.ACTIVE,
            "disconnected_at": None,
            "last_seen_at": NOW,
            "last_input_at": NOW,
        }
    )
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=PlayerStateChanged(
                seq=3, player_id="player1", state=PlayerState.ACTIVE
            ),
        ),
    )
    assert outcome.reply == (snapshot_for(outcome.state, "player1"),)
    assert outcome.close_sender is False
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.seq == 3
    assert snapshot.you == "player1"
    assert snapshot.resume_token == "resume-token-number-1"
    assert [view.nickname for view in snapshot.players] == ["ANA", "BOB"]


def test_ac5_resume_of_a_connected_player_makes_no_event(fx01_grid: Grid) -> None:
    host = make_player(0, "ANA", is_host=True)
    still_open = make_player(1, "BOB")
    state = make_state(fx01_grid, [host, still_open])

    outcome = run_join(state, "Autre", 9, token="resume-token-number-1")

    assert outcome.entries == ()
    assert outcome.state.seq == state.seq
    assert outcome.state.players[0] == host
    assert outcome.state.players[1] == still_open.model_copy(
        update={"last_seen_at": NOW, "last_input_at": NOW}
    )
    assert outcome.reply == (snapshot_for(outcome.state, "player1"),)
    assert outcome.close_sender is False


def test_ac5_resume_ignores_the_nickname_of_the_join(fx01_grid: Grid) -> None:
    away = make_player(0, "ANA", is_host=True, state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [away])

    outcome = run_join(state, "!!", 9, token="resume-token-number-0")

    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "player0"
    assert snapshot.players[0].nickname == "ANA"
    assert snapshot.players[0].is_host is True
    assert snapshot.players[0].colour == 0
    assert outcome.state.players[0].joined_seq == away.joined_seq


def test_ac5_an_unknown_token_is_ignored_and_the_join_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "ANA", is_host=True)])

    outcome = run_join(state, "Cy", 9, token=OTHER_TOKEN)

    assert len(outcome.state.players) == 2
    newcomer = outcome.state.players[1]
    assert newcomer.player_id == "joiner9"
    assert newcomer.nickname == "CY"
    assert newcomer.resume_token == "joiner-token-number-9"
    assert len(outcome.entries) == 1


def test_ac5_websocket_a_closed_player_resumes_with_the_token(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack_b:
        with contextlib.ExitStack() as stack_a:
            _, snapshot_a = join_as(stack_a, ws_client, room_code, "Ana")
            socket_b, snapshot_b = join_as(stack_b, ws_client, room_code, "Bob")

        assert receive_message(socket_b) == PlayerStateChanged(
            seq=3, player_id=snapshot_a.you, state=PlayerState.DISCONNECTED
        )
        state = registry.room_state(room_code)
        assert state is not None
        assert len(state.players) == 2
        assert state.players[0].state is PlayerState.DISCONNECTED
        assert state.players[0].is_host is True
        assert state.players[1].is_host is False

        _, resumed = join_as(
            stack_b, ws_client, room_code, "Autre", resume_token=snapshot_a.resume_token
        )

        assert resumed.you == snapshot_a.you
        assert resumed.resume_token == snapshot_a.resume_token
        assert resumed.seq == 4
        assert resumed.players == (
            active_view(snapshot_a.you, "ANA", 0, True),
            active_view(snapshot_b.you, "BOB", 1),
        )
        assert receive_message(socket_b) == PlayerStateChanged(
            seq=4, player_id=snapshot_a.you, state=PlayerState.ACTIVE
        )
    final_state = registry.room_state(room_code)
    assert final_state is not None
    assert len(final_state.players) == 2


def test_ac5_websocket_an_unknown_token_makes_a_new_player(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        _, snapshot = join_as(
            stack, ws_client, room_code, "Cy", resume_token=OTHER_TOKEN
        )

    assert snapshot.resume_token != OTHER_TOKEN
    assert [view.nickname for view in snapshot.players] == ["CY"]
    assert snapshot.players[0].is_host is True


def test_ac5_websocket_a_second_tab_takes_over_and_the_first_is_closed(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as second_tab_stack:
        first_tab, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        other, _ = join_as(stack, ws_client, room_code, "Bob")
        expect_joined_seqs(first_tab, [2])

        second_tab, second_snapshot = join_as(
            second_tab_stack,
            ws_client,
            room_code,
            "Ana",
            resume_token=first_snapshot.resume_token,
        )

        assert second_snapshot.you == first_snapshot.you
        assert second_snapshot.seq == 2
        assert close_code_of_next_read(first_tab) == SESSION_REPLACED
        time.sleep(SETTLE_SECONDS)
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 2
        assert state.players[0].state is PlayerState.ACTIVE
        _, third_snapshot = join_as(stack, ws_client, room_code, "Cy")
        third_view = active_view(third_snapshot.you, "CY", 2)
        assert receive_message(other) == PlayerJoined(seq=3, player=third_view)
        assert receive_message(second_tab) == PlayerJoined(seq=3, player=third_view)


def test_ac5_websocket_closing_the_new_tab_disconnects_the_player(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as second_tab_stack:
        first_tab, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        other, _ = join_as(stack, ws_client, room_code, "Bob")
        expect_joined_seqs(first_tab, [2])
        join_as(
            second_tab_stack,
            ws_client,
            room_code,
            "Ana",
            resume_token=first_snapshot.resume_token,
        )
        assert close_code_of_next_read(first_tab) == SESSION_REPLACED

        second_tab_stack.close()

        assert receive_message(other) == PlayerStateChanged(
            seq=3, player_id=first_snapshot.you, state=PlayerState.DISCONNECTED
        )


def test_ac5_session_replaced_close_code_is_4001() -> None:
    assert nock.server.SESSION_REPLACED_CLOSE_CODE == SESSION_REPLACED
    assert nock.hub.SESSION_REPLACED_CLOSE_CODE == SESSION_REPLACED


def test_ac5_browser_reloading_keeps_the_same_player(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    enter_room(page, f"{live_server}/r/{code}")
    room = page.get_by_test_id("room-page")
    player_id = room.get_attribute("data-you")
    assert player_id

    page.reload()

    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-you", player_id)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("roster").get_by_test_id("roster-player")).to_have_count(
        1
    )
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1
    assert state.players[0].player_id == player_id


def test_ac5_browser_a_second_tab_replaces_the_first(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    enter_room(page, url)
    first_room = page.get_by_test_id("room-page")
    player_id = first_room.get_attribute("data-you")
    assert player_id
    second_page = page.context.new_page()

    enter_room(second_page, url)

    second_room = second_page.get_by_test_id("room-page")
    expect(second_room).to_have_attribute("data-status", "joined")
    expect(second_room).to_have_attribute("data-you", player_id)
    expect(first_room).to_have_attribute("data-status", "replaced")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.replaced"]
    )
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1


def test_ac5_browser_close_4001_means_replaced_and_is_final(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, [active_view("p1", "Ana", 0, True)]))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")

    mock.close(SESSION_REPLACED)

    expect(room).to_have_attribute("data-status", "replaced")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.replaced"]
    )
    settle(page)
    expect(room).to_have_attribute("data-status", "replaced")
    assert len(mock.routes) == 1


def test_ac5_browser_player_state_changed_updates_the_roster(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)

    away = PlayerStateChanged(
        seq=4, player_id="p2", state=PlayerState.DISCONNECTED
    ).model_dump_json()
    mock.send(away)

    expect(items.nth(2)).to_have_attribute("data-state", "disconnected")
    expect(items.nth(0)).to_have_attribute("data-state", "active")
    expect(items.nth(1)).to_have_attribute("data-state", "active")
    back = PlayerStateChanged(
        seq=5, player_id="p2", state=PlayerState.ACTIVE
    ).model_dump_json()
    mock.send(back)

    expect(items.nth(2)).to_have_attribute("data-state", "active")


def test_ac5_fr_json_has_the_replaced_text() -> None:
    assert (
        load_fr()["room.status.replaced"] == "Ce salon est ouvert dans un autre onglet."
    )
