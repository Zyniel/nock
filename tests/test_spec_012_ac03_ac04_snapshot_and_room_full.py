"""Tests of spec 012, AC-3 and AC-4: the snapshot at once, and a full room.

AC-3: the snapshot answers a join within a second, with the letters, the timer and
the hint budget. AC-4: a ninth player is refused. The rules, the real WebSocket
and the browser. The shared setup is in `spec012_harness`.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    LetterCellView,
    PlayerState,
    PlayerStateChanged,
    RevealBudget,
    Snapshot,
)
from nock.room import (
    MAX_PLAYERS,
    CellState,
    PlayerRecord,
    RoomState,
    grid_state,
    new_room,
    player_views,
    snapshot_for,
)
from nock.server import create_app
from spec012_harness import (
    RECENT_DISCONNECT,
    ROOM_CODE,
    START_TIME,
    close_code_of_next_read,
    error_frame,
    expect_joined_seqs,
    grid_from_text,
    join_as,
    join_text,
    load_fr,
    make_app,
    make_dist_dir,
    make_player,
    make_registry,
    make_state,
    only_error_code,
    open_mock_room,
    receive_error_code,
    receive_message,
    receive_snapshot,
    run_join,
    settle,
    socket_url,
    submit_form,
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


def eight_players(
    state: PlayerState = PlayerState.ACTIVE,
    disconnected_at: float = RECENT_DISCONNECT,
) -> list[PlayerRecord]:
    players: list[PlayerRecord] = []
    for index in range(MAX_PLAYERS):
        players.append(
            make_player(
                index,
                f"Player{index}",
                state=state,
                is_host=index == 0,
                disconnected_at=disconnected_at,
            )
        )
    return players


# ---- AC-3: the snapshot at once ------------------------------------------------


def seeded_room(grid: Grid) -> RoomState:
    """A FX-01 room with T and A written by `p9`, and a budget of 3 and 1."""
    fresh = new_room(ROOM_CODE, grid, START_TIME)
    cells: list[CellState] = []
    for cell in fresh.cells:
        if (cell.row, cell.column) == (1, 0):
            cell = cell.model_copy(update={"letter": "T", "author": "p9"})
        if (cell.row, cell.column) == (1, 1):
            cell = cell.model_copy(update={"letter": "A", "author": "p9"})
        cells.append(cell)
    return fresh.model_copy(
        update={
            "cells": tuple(cells),
            "reveal_budget": RevealBudget(letters=3, words=1),
        }
    )


def letter_view_at(snapshot: Snapshot, row: int, column: int) -> LetterCellView:
    for cell in snapshot.grid.cells:
        if (
            isinstance(cell, LetterCellView)
            and cell.row == row
            and cell.column == column
        ):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


def test_ac3_snapshot_arrives_within_a_second_with_letters_timer_and_budget(
    registry: RoomRegistry, fx01_grid: Grid, dist_dir: Path
) -> None:
    registry.add_room(seeded_room(fx01_grid))
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with (
        TestClient(app) as client,
        client.websocket_connect(socket_url(ROOM_CODE)) as websocket,
    ):
        started = time.monotonic()
        websocket.send_text(join_text("Ana"))
        snapshot = receive_snapshot(websocket)
        elapsed = time.monotonic() - started

    assert elapsed < 1.0
    # The snapshot answers a real join: it counts the joiner and the join itself.
    assert snapshot.seq == 1
    assert [view.player_id for view in snapshot.players] == [snapshot.you]
    state = registry.room_state(ROOM_CODE)
    assert state is not None
    assert snapshot.grid == grid_state(state)
    first = letter_view_at(snapshot, 1, 0)
    assert (first.letter, first.author) == ("T", "p9")
    second = letter_view_at(snapshot, 1, 1)
    assert (second.letter, second.author) == ("A", "p9")
    assert snapshot.reveal_budget == RevealBudget(letters=3, words=1)
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac3_snapshot_for_fills_every_field_from_the_room(fx01_grid: Grid) -> None:
    state = seeded_room(fx01_grid).model_copy(
        update={
            "players": (make_player(0, "Ana", is_host=True), make_player(1, "Bob")),
            "seq": 7,
            "solved": True,
        }
    )

    snapshot = snapshot_for(state, "player1")

    assert snapshot == Snapshot(
        seq=7,
        you="player1",
        resume_token="resume-token-number-1",
        grid=grid_state(state),
        players=player_views(state),
        settings=state.settings,
        reveal_budget=RevealBudget(letters=3, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=True,
    )


def test_ac3_snapshot_for_an_unknown_player_raises_key_error(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True)])

    with pytest.raises(KeyError):
        snapshot_for(state, "nobody")


# ---- AC-4: room full ------------------------------------------------------------


def test_ac4_join_room_refuses_a_ninth_player(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players())

    outcome = run_join(state, "Zoe", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert outcome.state == state


def test_ac4_disconnected_players_still_hold_their_seats(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players(PlayerState.DISCONNECTED))

    outcome = run_join(state, "Zoe", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True
    assert outcome.state == state


def test_ac4_a_full_room_answers_room_full_even_to_a_bad_nickname(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, eight_players())

    outcome = run_join(state, "--", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True


def test_ac4_a_room_of_seven_still_takes_one_more(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players()[:7])

    outcome = run_join(state, "Zoe", 9)

    assert len(outcome.state.players) == 8
    assert outcome.close_sender is False
    assert isinstance(outcome.reply[0], Snapshot)


def test_ac4_a_resume_is_accepted_in_a_full_room(fx01_grid: Grid) -> None:
    players = eight_players()
    players[3] = make_player(3, "Player3", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Zoe", 9, token="resume-token-number-3")

    assert outcome.close_sender is False
    assert len(outcome.state.players) == 8
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "player3"


def test_ac4_websocket_a_ninth_join_is_refused_then_the_socket_closes(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as last_stack:
        first, _ = join_as(stack, ws_client, room_code, "Player1")
        for number in range(2, 8):
            join_as(stack, ws_client, room_code, f"Player{number}")
        _, eighth_snapshot = join_as(last_stack, ws_client, room_code, "Player8")
        expect_joined_seqs(first, [2, 3, 4, 5, 6, 7, 8])

        with ws_client.websocket_connect(socket_url(room_code)) as ninth:
            ninth.send_text(join_text("Zo\u00e9"))

            assert receive_error_code(ninth) == ErrorCode.ROOM_FULL
            assert close_code_of_next_read(ninth) == 1000

        state = registry.room_state(room_code)
        assert state is not None
        assert len(state.players) == 8
        assert state.seq == 8
        # The next thing the first client hears is the eighth leaving: the
        # refused join produced no event.
        last_stack.close()
        assert receive_message(first) == PlayerStateChanged(
            seq=9, player_id=eighth_snapshot.you, state=PlayerState.DISCONNECTED
        )


def eight_disconnected_room(grid: Grid) -> RoomState:
    # The live server runs on the real clock: the players left 10 s ago.
    left_at = time.time() - 10.0
    return make_state(grid, eight_players(PlayerState.DISCONNECTED, left_at))


def test_ac4_browser_a_full_room_shows_room_full(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    room_registry.add_room(eight_disconnected_room(fx01_grid))
    page.goto(f"{live_server}/r/{ROOM_CODE}")
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")

    submit_form(page, "Zo\u00e9")

    expect(room).to_have_attribute("data-status", "full")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.full"]
    )
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    state = room_registry.room_state(ROOM_CODE)
    assert state is not None
    assert len(state.players) == 8


def test_ac4_browser_room_full_is_final_even_after_the_close(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Zo\u00e9")
    mock.wait_for_frames(1)
    room = page.get_by_test_id("room-page")

    mock.send(error_frame(ErrorCode.ROOM_FULL))
    mock.close(1000)

    expect(room).to_have_attribute("data-status", "full")
    settle(page)
    expect(room).to_have_attribute("data-status", "full")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    assert len(mock.frames_without_pings()) == 1
    assert len(mock.routes) == 1


def test_ac4_fr_json_has_the_room_full_text() -> None:
    assert load_fr()["room.status.full"] == "Ce salon est complet (8 joueurs)."
