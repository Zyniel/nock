"""Tests of spec 040, AC-7 to AC-13: the room registry and the room WebSocket.

AC-7 tests `RoomRegistry` directly. AC-8 to AC-13 connect to
`/api/rooms/{code}/ws` with `fastapi.testclient.TestClient`: the snapshot that a
join gets, the 4404 close of an unknown room, and the errors sent before the join.

The shared setup is in `tests/spec040_harness.py`.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    Join,
    PlayerState,
    PlayerView,
    RevealBudget,
    Snapshot,
    grid_view,
    parse_server_message,
)
from nock.server import (
    ROOM_CODE_PATTERN,
    ROOM_NOT_FOUND_CLOSE_CODE,
    RoomRegistry,
    create_app,
)
from spec040_harness import (
    EXPECTED_SETTINGS,
    grid_from_text,
    make_dist_dir,
    socket_url,
)

JOIN_TEXT = '{"type": "join", "nickname": "Ana", "resume_token": null}'
ROOM_CODE_REGEX = re.compile(r"^[A-Z0-9]{6}$")


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def empty_client(dist_dir: Path, registry: RoomRegistry) -> TestClient:
    """A client on an app with a built dist and no room."""
    return TestClient(create_app(rooms=registry, dist_dir=dist_dir))


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def room_client(registry: RoomRegistry, room_code: str, dist_dir: Path) -> TestClient:
    """A client on an app that serves the room `room_code` (FX-01)."""
    return TestClient(create_app(rooms=registry, dist_dir=dist_dir))


def join_and_get_snapshot(client: TestClient, code: str) -> Snapshot:
    with client.websocket_connect(socket_url(code)) as websocket:
        websocket.send_text(JOIN_TEXT)
        message = parse_server_message(websocket.receive_text())
    assert isinstance(message, Snapshot)
    return message


def close_code_on_first_read(
    client: TestClient, code: str, first_message: str | None
) -> int:
    """Connect, optionally send a message, and return the close code received."""
    try:
        with client.websocket_connect(socket_url(code)) as websocket:
            if first_message is not None:
                websocket.send_text(first_message)
            websocket.receive_text()
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail("the server sent a message instead of closing the socket")


# ---- AC-7: RoomRegistry -----------------------------------------------------


def test_ac7_register_room_gives_distinct_valid_codes(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    first = registry.register_room(fx01_grid)
    second = registry.register_room(fx01_grid)

    assert ROOM_CODE_REGEX.match(first)
    assert ROOM_CODE_REGEX.match(second)
    assert first != second
    assert registry.find_room(first) == fx01_grid
    assert registry.find_room(second) == fx01_grid


def test_ac7_find_room_returns_none_for_unknown_code(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    registry.register_room(fx01_grid)
    other_registry = RoomRegistry()

    try:
        assert registry.find_room("abc123") is None
        assert other_registry.find_room("ABC123") is None
    finally:
        other_registry.close()


def test_ac7_many_codes_are_all_distinct(
    registry: RoomRegistry, fx01_grid: Grid
) -> None:
    codes = [registry.register_room(fx01_grid) for _ in range(200)]

    assert len(set(codes)) == 200


def test_ac7_constants_of_the_interface() -> None:
    assert ROOM_CODE_PATTERN == r"^[A-Z0-9]{6}$"
    assert ROOM_NOT_FOUND_CLOSE_CODE == 4404


# ---- AC-8 to AC-13: WebSocket -----------------------------------------------


def test_ac8_join_gets_the_snapshot_of_the_room(
    room_client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    snapshot = join_and_get_snapshot(room_client, room_code)

    assert snapshot.seq == 1
    assert snapshot.grid == grid_view(fx01_grid)
    assert snapshot.players == (
        PlayerView(
            player_id=snapshot.you,
            nickname="Ana",
            colour=0,
            state=PlayerState.ACTIVE,
            is_host=True,
            muted=False,
            selection=None,
        ),
    )
    assert snapshot.settings == EXPECTED_SETTINGS
    assert snapshot.reveal_budget == RevealBudget(letters=5, words=1)
    assert snapshot.flags == ()
    assert snapshot.chat == ()
    assert snapshot.open_vote is None
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False
    assert snapshot.solved is False


def test_ac8_binary_join_frame_is_handled_like_text(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(JOIN_TEXT.encode("utf-8"))
        message = parse_server_message(websocket.receive_text())

    assert isinstance(message, Snapshot)
    assert message.seq == 1


def test_ac8_resume_token_of_the_join_is_ignored(
    room_client: TestClient, room_code: str
) -> None:
    sent_token = "A" * 24
    join_text = Join(nickname="Ana", resume_token=sent_token).model_dump_json()

    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(join_text)
        message = parse_server_message(websocket.receive_text())

    assert isinstance(message, Snapshot)
    assert message.resume_token != sent_token


def test_ac9_snapshot_text_holds_no_answer(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(JOIN_TEXT)
        raw_text = websocket.receive_text()

    assert isinstance(parse_server_message(raw_text), Snapshot)
    forbidden = ["answer", "TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE"]
    forbidden += ["AMEN", "LEST"]
    for word in forbidden:
        assert word not in raw_text


def test_ac10_two_clients_get_different_identities(
    room_client: TestClient, room_code: str
) -> None:
    url = socket_url(room_code)
    with (
        room_client.websocket_connect(url) as first_socket,
        room_client.websocket_connect(url) as second_socket,
    ):
        first_socket.send_text(JOIN_TEXT)
        second_socket.send_text(JOIN_TEXT)
        first = parse_server_message(first_socket.receive_text())
        second = parse_server_message(second_socket.receive_text())

    assert isinstance(first, Snapshot)
    assert isinstance(second, Snapshot)
    assert first.you != second.you
    assert first.resume_token != second.resume_token


@pytest.mark.parametrize("code", ["ZZZZZZ", "abc"])
def test_ac11_unknown_room_closes_with_4404_and_no_message(
    empty_client: TestClient, code: str
) -> None:
    assert close_code_on_first_read(empty_client, code, None) == 4404


def test_ac11_unknown_room_closes_even_when_another_room_exists(
    room_client: TestClient,
) -> None:
    assert close_code_on_first_read(room_client, "ZZZZZZ", JOIN_TEXT) == 4404


@pytest.mark.parametrize(
    "bad_message",
    ["not json", '{"type": "join", "nickname": "A"}', '{"type": "nope"}'],
)
def test_ac12_invalid_message_gets_invalid_message_error(
    room_client: TestClient, room_code: str, bad_message: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(bad_message)
        error = parse_server_message(websocket.receive_text())
        websocket.send_text(JOIN_TEXT)
        snapshot = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.INVALID_MESSAGE
    assert error.message != ""
    assert isinstance(snapshot, Snapshot)


def test_ac12_invalid_binary_frame_gets_invalid_message_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(b"not json")
        error = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.INVALID_MESSAGE


def test_ac13_message_before_join_gets_not_joined_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text('{"type": "undo"}')
        error = parse_server_message(websocket.receive_text())
        websocket.send_text(JOIN_TEXT)
        snapshot = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.NOT_JOINED
    assert error.message != ""
    assert isinstance(snapshot, Snapshot)


def test_ac13_binary_message_before_join_gets_not_joined_error(
    room_client: TestClient, room_code: str
) -> None:
    with room_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_bytes(b'{"type": "undo"}')
        error = parse_server_message(websocket.receive_text())

    assert isinstance(error, ErrorMessage)
    assert error.code == ErrorCode.NOT_JOINED
