"""Shared setup of the tests of spec 012: guest join, nicknames, colours, resume.

This module is not a test file: pytest does not collect it. The tests of spec 012
are in `tests/test_spec_012_ac*.py`, one file per criterion group.

The rules (`normalize_nickname`, `join_room`, `disconnect_player`) are tested
directly. The hub is tested with the real WebSocket (`TestClient`). The page is
tested with the live server and with spec 040's mocked socket and the messages
built with the `nock.protocol` models.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`registry`, `room_code` and `ws_client` are defined in each file that needs them,
as thin wrappers around `grid_from_text`, `make_dist_dir`, `make_registry` and
`make_app`: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import queue
import re
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Page, WebSocketRoute
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

import nock.hub
import nock.room
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    Join,
    Ping,
    PlayerJoined,
    PlayerState,
    PlayerView,
    RevealBudget,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    join_room,
    new_room,
)
from nock.server import create_app

# ---- Constants -----------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
OLD_TIME = 1_500_000.0
RECENT_DISCONNECT = NOW - 10.0  # recent: well under the 300 s time-out
START_TIME = 1_000_000.0
RECEIVE_TIMEOUT_SECONDS = 5.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 500
FORM_TIMEOUT_MS = 5000
MOCK_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
OTHER_TOKEN = "q3Wm8xYo2vB4tY1zW9nR"


# ---- Helpers for the fixtures --------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """Return the grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """Return a `dist` directory with a minimal `index.html` (`dist_dir`)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_registry() -> RoomRegistry:
    """Return a registry that ticks fast and never times a silent socket out."""
    config = RoomConfig(tick_seconds=0.05, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


def make_app(registry: RoomRegistry, dist_dir: Path) -> FastAPI:
    """Return an app serving `registry` (the app of the `ws_client` fixture)."""
    return create_app(rooms=registry, dist_dir=dist_dir)


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Helpers for the rules -----------------------------------------------------


def active_view(
    player_id: str, nickname: str, colour: int, is_host: bool = False
) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=is_host,
        muted=False,
        selection=None,
    )


def make_player(
    index: int,
    nickname: str,
    *,
    colour: int | None = None,
    state: PlayerState = PlayerState.ACTIVE,
    is_host: bool = False,
    disconnected_at: float = RECENT_DISCONNECT,
) -> PlayerRecord:
    """A player of a seeded room: ids and tokens are derived from `index`.

    A disconnected player left `disconnected_at`, recent enough (spec 017) not
    to be timed out.
    """
    return PlayerRecord(
        player_id=f"player{index}",
        resume_token=f"resume-token-number-{index}",
        nickname=nickname,
        colour=index if colour is None else colour,
        is_host=is_host,
        state=state,
        joined_seq=index + 1,
        last_input_at=OLD_TIME,
        last_seen_at=OLD_TIME,
        disconnected_at=(
            disconnected_at if state is PlayerState.DISCONNECTED else None
        ),
    )


def make_state(grid: Grid, players: list[PlayerRecord]) -> RoomState:
    """A room holding `players`; `seq` is the number of players."""
    fresh = new_room(ROOM_CODE, grid, START_TIME)
    return fresh.model_copy(update={"players": tuple(players), "seq": len(players)})


def run_join(
    state: RoomState, nickname: str, number: int = 1, token: str | None = None
) -> Outcome:
    """Apply a join with fresh ids derived from `number`."""
    message = Join(nickname=nickname, resume_token=token)
    return join_room(
        state, message, NOW, f"joiner{number}", f"joiner-token-number-{number}"
    )


def only_error_code(outcome: Outcome) -> ErrorCode:
    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, ErrorMessage)
    return reply.code


# ---- Helpers for the real WebSocket --------------------------------------------


def receive_text_or_fail(websocket: WebSocketTestSession) -> str:
    """Return the next text of the socket, failing instead of waiting forever."""
    received: queue.Queue[str | BaseException] = queue.Queue()

    def read() -> None:
        try:
            received.put(websocket.receive_text())
        except BaseException as error:  # handed to the test thread, re-raised there
            received.put(error)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        outcome = received.get(timeout=RECEIVE_TIMEOUT_SECONDS)
    except queue.Empty:
        pytest.fail(f"nothing received from the socket in {RECEIVE_TIMEOUT_SECONDS}s")
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def receive_message(websocket: WebSocketTestSession) -> object:
    return parse_server_message(receive_text_or_fail(websocket))


def receive_snapshot(websocket: WebSocketTestSession) -> Snapshot:
    message = receive_message(websocket)
    assert isinstance(message, Snapshot), message
    return message


def receive_error_code(websocket: WebSocketTestSession) -> ErrorCode:
    message = receive_message(websocket)
    assert isinstance(message, ErrorMessage), message
    return message.code


def close_code_of_next_read(websocket: WebSocketTestSession) -> int:
    """Return the close code the socket receives; fail if a message comes first."""
    try:
        text = receive_text_or_fail(websocket)
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail(f"the socket should have closed, but it received: {text}")


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def join_text(nickname: str, resume_token: str | None = None) -> str:
    return Join(nickname=nickname, resume_token=resume_token).model_dump_json()


def join_as(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
) -> tuple[WebSocketTestSession, Snapshot]:
    """Open a socket in `stack`, join, and return the socket and its snapshot."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    websocket.send_text(join_text(nickname, resume_token))
    return websocket, receive_snapshot(websocket)


def expect_joined_seqs(websocket: WebSocketTestSession, seqs: list[int]) -> None:
    """Read one `player_joined` per seq of `seqs`, in order."""
    for seq in seqs:
        message = receive_message(websocket)
        assert isinstance(message, PlayerJoined), message
        assert message.seq == seq


# ---- Helpers for the browser ---------------------------------------------------


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

    def frames_without_pings(self) -> list[str]:
        """The frames received so far, spec 017's heartbeat `ping` frames left aside.

        The page pings every 2 s from the opening of the socket, also before a
        join, so a slow engine can send a `ping` at any point of a test.
        """
        frames: list[str] = []
        for frame in self.received:
            if parse_client_message(frame) != Ping():
                frames.append(frame)
        return frames

    def wait_for_frames(self, count: int) -> None:
        """Wait for `count` frames, the heartbeat `ping` frames not counted."""
        wait_until(self.page, lambda: len(self.frames_without_pings()) >= count)

    def joins(self) -> list[Join]:
        """The frames received so far, each parsed as a Join, pings left aside."""
        parsed: list[Join] = []
        for frame in self.frames_without_pings():
            message = parse_client_message(frame)
            assert isinstance(message, Join), frame
            parsed.append(message)
        return parsed


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to do things that must not happen."""
    page.wait_for_timeout(SETTLE_MS)


def seed_local_storage(page: Page, items: dict[str, str]) -> None:
    """Fill `localStorage` before the page's own scripts run."""
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " localStorage.setItem(key, value); }"
    )
    page.context.add_init_script(script)


def open_mock_room(
    page: Page, base_url: str, items: dict[str, str] | None = None
) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and `localStorage` seeded with `items`."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    if items:
        seed_local_storage(page, items)
    page.goto(f"{base_url}/r/ABC123")
    return mock


def submit_form(page: Page, nickname: str) -> None:
    """Fill the nickname form and submit it with Enter."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)


def snapshot_frame(
    grid: Grid,
    players: list[PlayerView],
    you: str = "p1",
    resume_token: str = MOCK_TOKEN,
    seq: int = 1,
) -> str:
    snapshot_players = tuple(players)
    snapshot = Snapshot(
        seq=seq,
        you=you,
        resume_token=resume_token,
        grid=grid_view(grid),
        players=snapshot_players,
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def three_players() -> list[PlayerView]:
    return [
        active_view("p0", "Ana", 0, True),
        active_view("p1", "Ana 2", 1),
        active_view("p2", "Bob", 2),
    ]
