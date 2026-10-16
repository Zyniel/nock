"""Tests of spec 028, AC-9: the share token and the recap survive a restart.

A `RoomStore` on a file holds a FX-01 room created with a share token and `PLAY_R`'s
entries; a new `RoomStore` on the same file and a new `RoomRegistry` on it stand for
the restarted server. The token rules (`register_room`, `add_room`, no token in a
snapshot) are tested here too.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pydantic
import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.recap import SHARE_PATH_PREFIX, build_recap, public_recap
from nock.room import new_room, snapshot_for
from nock.server import create_app
from nock.store import RoomStore
from spec011_harness import JOIN_TEXT, receive_text_or_fail
from spec024_harness import NOW, ROOM_CODE, make_dist_dir
from spec028_harness import (
    SHARE_TOKEN,
    TOKEN_PATTERN,
    UNKNOWN_TOKEN,
    Game,
    after_play_r,
    make_http_registry,
    play_r,
    stored_play_r,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "rooms.db"


@pytest.fixture
def restarted_store(db_path: Path, fx01_grid: Grid) -> Iterator[RoomStore]:
    stored_play_r(db_path, fx01_grid)
    store = RoomStore(db_path)
    yield store
    store.close()


def test_ac9_the_store_finds_the_code_of_a_share_token(
    restarted_store: RoomStore,
) -> None:
    assert restarted_store.code_for_share_token(SHARE_TOKEN) == ROOM_CODE


def test_ac9_the_store_returns_none_for_an_unknown_token(
    restarted_store: RoomStore,
) -> None:
    assert restarted_store.code_for_share_token(UNKNOWN_TOKEN) is None


def test_ac9_a_new_registry_gives_the_recap_of_the_stored_room(
    restarted_store: RoomStore, fx01_grid: Grid
) -> None:
    game = play_r(fx01_grid)
    registry = RoomRegistry(store=restarted_store, clock=after_play_r)
    try:
        recap = registry.room_recap(ROOM_CODE)
    finally:
        registry.close()

    assert recap == build_recap(game.state, game.log)
    assert recap is not None
    assert recap.share_path == SHARE_PATH_PREFIX + SHARE_TOKEN


def test_ac9_a_new_registry_gives_the_public_recap_of_the_stored_room(
    restarted_store: RoomStore, fx01_grid: Grid
) -> None:
    game = play_r(fx01_grid)
    registry = RoomRegistry(store=restarted_store, clock=after_play_r)
    try:
        shared = registry.shared_recap(SHARE_TOKEN)
    finally:
        registry.close()

    assert shared == public_recap(build_recap(game.state, game.log))


def test_ac9_shared_recap_is_none_for_an_unknown_or_malformed_token(
    restarted_store: RoomStore,
) -> None:
    registry = RoomRegistry(store=restarted_store, clock=after_play_r)
    try:
        assert registry.shared_recap(UNKNOWN_TOKEN) is None
        assert registry.shared_recap("a b") is None
    finally:
        registry.close()


def test_ac9_the_stored_room_is_solved_after_the_restart(
    restarted_store: RoomStore,
) -> None:
    registry = RoomRegistry(store=restarted_store, clock=after_play_r)
    try:
        state = registry.room_state(ROOM_CODE)
    finally:
        registry.close()

    assert state is not None
    assert state.solved is True
    assert state.share_token == SHARE_TOKEN


def test_ac9_a_registered_room_is_found_by_its_token_after_a_restart(
    db_path: Path, fx01_grid: Grid
) -> None:
    first_store = RoomStore(db_path)
    registry = RoomRegistry(store=first_store)
    try:
        code = registry.register_room(fx01_grid, grid_number=1)
        state = registry.room_state(code)
    finally:
        registry.close()
        first_store.close()
    assert state is not None
    assert state.share_token is not None

    second_store = RoomStore(db_path)
    try:
        assert second_store.code_for_share_token(state.share_token) == code
    finally:
        second_store.close()


def test_ac9_register_room_gives_distinct_tokens_that_are_not_the_code(
    fx01_grid: Grid,
) -> None:
    registry = make_http_registry()
    tokens: set[str] = set()
    try:
        for _ in range(20):
            code = registry.register_room(fx01_grid)
            state = registry.room_state(code)
            assert state is not None
            token = state.share_token
            assert token is not None
            assert TOKEN_PATTERN.fullmatch(token) is not None
            assert len(token) == 22
            assert token != code
            tokens.add(token)
    finally:
        registry.close()

    assert len(tokens) == 20


def test_ac9_add_room_keeps_the_token_of_the_state_it_is_given(
    fx01_grid: Grid,
) -> None:
    registry = make_http_registry()
    try:
        registry.add_room(new_room(ROOM_CODE, fx01_grid, NOW, share_token=SHARE_TOKEN))
        state = registry.room_state(ROOM_CODE)
    finally:
        registry.close()

    assert state is not None
    assert state.share_token == SHARE_TOKEN


def test_ac9_a_room_without_a_token_has_no_share_path(fx01_grid: Grid) -> None:
    game = Game(fx01_grid, share_token=None)
    game.finish("p1")

    recap = build_recap(game.state, game.log)

    assert game.state.share_token is None
    assert recap.share_path is None


def test_ac9_new_room_has_no_token_by_default(fx01_grid: Grid) -> None:
    assert new_room(ROOM_CODE, fx01_grid, NOW).share_token is None


def test_ac9_a_share_token_that_breaks_the_pattern_is_refused(
    fx01_grid: Grid,
) -> None:
    with pytest.raises(pydantic.ValidationError, match="share_token"):
        new_room(ROOM_CODE, fx01_grid, NOW, share_token="too short")


def test_ac9_room_recap_is_none_without_a_room_or_a_solved_grid(
    fx01_grid: Grid,
) -> None:
    registry = make_http_registry()
    try:
        code = registry.register_room(fx01_grid, grid_number=1)
        assert registry.room_recap("ZZZZZZ") is None
        assert registry.room_recap(code) is None
    finally:
        registry.close()


def test_ac9_a_snapshot_never_holds_the_token(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)

    snapshot = snapshot_for(game.state, "p1")

    assert SHARE_TOKEN not in snapshot.model_dump_json()


def test_ac9_no_snapshot_sent_over_the_socket_holds_the_token(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    registry = make_http_registry()
    try:
        code = registry.register_room(fx01_grid, grid_number=1)
        state = registry.room_state(code)
        assert state is not None
        token = state.share_token
        assert token is not None
        app = create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))
        url = f"/api/rooms/{code}/ws"
        with TestClient(app) as client, client.websocket_connect(url) as websocket:
            websocket.send_text(JOIN_TEXT)
            text = receive_text_or_fail(websocket)
    finally:
        registry.close()

    assert '"type":"snapshot"' in text.replace(" ", "")
    assert token not in text
