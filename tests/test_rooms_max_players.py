"""Tests of lobby/rooms AC-19: a room and its snapshot hold at most MAX_PLAYERS.

Both models are built directly with `MAX_PLAYERS` and with `MAX_PLAYERS + 1`
players: the first is valid, the second raises `ValidationError`. The limit is
read from the behaviour of the models, not from their field metadata.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nock.grid import Grid
from nock.protocol import RevealBudget, Snapshot, grid_view
from nock.room import (
    DEFAULT_SETTINGS,
    MAX_PLAYERS,
    PlayerRecord,
    RoomState,
    new_room,
)
from spec012_harness import (
    MOCK_TOKEN,
    ROOM_CODE,
    START_TIME,
    active_view,
    grid_from_text,
    make_player,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def room_with_players(grid: Grid, count: int) -> RoomState:
    """Build (and so validate) a `RoomState` holding `count` players."""
    fresh = new_room(ROOM_CODE, grid, START_TIME)
    players: list[PlayerRecord] = []
    for index in range(count):
        players.append(make_player(index, f"PLAYER{index}", is_host=index == 0))
    fields = dict(fresh)
    fields["players"] = tuple(players)
    return RoomState(**fields)


def snapshot_with_players(grid: Grid, count: int) -> Snapshot:
    """Build (and so validate) a `Snapshot` holding `count` players."""
    views = []
    for index in range(count):
        views.append(active_view(f"player{index}", f"PLAYER{index}", index % 8))
    return Snapshot(
        seq=1,
        you="player0",
        resume_token=MOCK_TOKEN,
        grid=grid_view(grid),
        players=tuple(views),
        settings=DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )


def test_ac19_a_room_state_holds_max_players_and_refuses_one_more(
    fx01_grid: Grid,
) -> None:
    full = room_with_players(fx01_grid, MAX_PLAYERS)

    assert len(full.players) == MAX_PLAYERS
    with pytest.raises(ValidationError):
        room_with_players(fx01_grid, MAX_PLAYERS + 1)


def test_ac19_a_snapshot_holds_max_players_and_refuses_one_more(
    fx01_grid: Grid,
) -> None:
    full = snapshot_with_players(fx01_grid, MAX_PLAYERS)

    assert len(full.players) == MAX_PLAYERS
    with pytest.raises(ValidationError):
        snapshot_with_players(fx01_grid, MAX_PLAYERS + 1)
