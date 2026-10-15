"""Shared setup of the tests of spec 017: disconnection and reconnection.

This module is not a test file: pytest does not collect it. The tests of spec 017
are in `tests/test_spec_017_*.py`, one file per criterion.

The rules (`handle_message`, `tick`, `join_room`) are tested directly with exact
clock values. The hub is tested with the real WebSocket, a fake clock and
`tick_seconds=0.05`, so the 6-second and 5-minute values keep their defaults and
pass in milliseconds. The page is tested with spec 040's mocked socket: the handler
is called again for each socket the page opens, so a test counts the connections,
answers pings (or not), closes a socket and sends snapshots.

Time-based client behaviour has two kinds of tests. The bounds the spec states in
real seconds (the banner within 5,000 ms) are measured with Playwright's waiting
assertions. The constants (ping every 2,000 ms, 4,000 ms of silence, the reconnect
delays) are tested without long waits on Playwright's page clock, which is frozen
before the page loads and moved by hand with `advance_page`.

Not tested in spec 017: the close 4408 reaching only the silent socket of a player
(a player has one live socket, the older one being replaced by a resume), the
`pencil_edit` and `confirm_pencil` forms of the stale rule (spec 020), the locked
room refusing the join of a timed-out player (spec 014), a real network cut (spec
decision 7) and the pending edits lost by a reload (not observable).

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid` and `dist_dir` are
defined in each file as thin wrappers around `grid_from_text` and `make_dist_dir`:
a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    Ping,
    PlayerJoined,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    LogEntry,
    PlayerRecord,
    RoomConfig,
    RoomState,
    join_room,
    new_room,
)
from nock.server import create_app

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eva", "Fay", "Gus", "Hal"]
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
STORED_IDENTITY = json.dumps(
    {"player_id": "p1", "resume_token": SNAPSHOT_TOKEN, "nickname": "Ana"}
)
STORED_JOIN = Join(nickname="Ana", resume_token=SNAPSHOT_TOKEN)

TICK_SECONDS = 0.05
SETTLE_SECONDS = 0.3
WS_WAIT_SECONDS = 5.0
WS_DETECTION_SECONDS = 1.0  # the spec: "within one second of real time"
LOSS_BUDGET_MS = 5000
WAIT_TIMEOUT_MS = 5000
STEP_SETTLE_MS = 120
SETTLE_MS = 400
NO_RECONNECTION_MS = 1500

ChangeList = list[tuple[int, int, dict[str, object]]]
Edit = EditLetter | Erase
Sendable = Join | Ping | EditLetter | Erase


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixture)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


# ---- Helpers for the rules ---------------------------------------------------


def token_of(number: int) -> str:
    """Return the resume token of player `p<number>`."""
    return f"player-token-number-{number:02d}"


def room_of_players(grid: Grid, count: int) -> RoomState:
    """Return a room where `p1` to `p<count>` joined at NOW, seq `count`.

    `p1` is the host. Their nicknames are `NICKNAMES` in order.
    """
    state = new_room(ROOM_CODE, grid, NOW)
    for number in range(1, count + 1):
        join = Join(nickname=NICKNAMES[number - 1], resume_token=None)
        outcome = join_room(state, join, NOW, f"p{number}", token_of(number))
        state = outcome.state
    assert state.seq == count
    return state


def two_player_room(grid: Grid) -> RoomState:
    return room_of_players(grid, 2)


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def player_of(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id} in the room")


def with_player(room: RoomState, player_id: str, **update: object) -> RoomState:
    """Return the room with some fields of one player replaced."""
    players: list[PlayerRecord] = []
    for player in room.players:
        if player.player_id == player_id:
            players.append(player.model_copy(update=update))
        else:
            players.append(player)
    return room.model_copy(update={"players": tuple(players)})


def keep_seen(state: RoomState, now: float) -> RoomState:
    """Return the state where each connected player was seen and active `now`."""
    seen = state
    for player in state.players:
        if player.state != PlayerState.DISCONNECTED:
            seen = with_player(
                seen, player.player_id, last_seen_at=now, last_input_at=now
            )
    return seen


def events_of(entries: tuple[LogEntry, ...]) -> list[object]:
    """Return the event of each log entry."""
    events: list[object] = []
    for entry in entries:
        events.append(entry.event)
    return events


def sole_error(reply: tuple[ServerMessage, ...]) -> ErrorMessage:
    assert len(reply) == 1
    error = reply[0]
    assert isinstance(error, ErrorMessage)
    return error


# ---- Helpers for the WebSocket tests -----------------------------------------


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives.

    All waits are bounded.
    """

    def __init__(self, websocket: WebSocketTestSession) -> None:
        self._websocket = websocket
        self._changed = threading.Condition()
        self._messages: list[ServerMessage] = []
        self._close_code: int | None = None
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except WebSocketDisconnect as closed:
                with self._changed:
                    self._close_code = closed.code
                    self._changed.notify_all()
                return
            except BaseException:  # the socket was closed by the test
                return
            try:
                message = parse_server_message(text)
            except ValueError as error:
                with self._changed:
                    self._failures.append(f"unparsable message {text!r}: {error}")
                    self._changed.notify_all()
                continue
            with self._changed:
                self._messages.append(message)
                self._changed.notify_all()

    def send(self, message: Sendable) -> None:
        self._websocket.send_text(message.model_dump_json())

    def send_raw(self, text: str) -> None:
        self._websocket.send_text(text)

    def messages(self) -> list[ServerMessage]:
        with self._changed:
            return list(self._messages)

    @property
    def close_code(self) -> int | None:
        with self._changed:
            return self._close_code

    def snapshot(self) -> Snapshot:
        for message in self.messages():
            if isinstance(message, Snapshot):
                return message
        pytest.fail("no snapshot received")

    def events(self) -> list[ServerMessage]:
        """Every message after the snapshot."""
        messages = self.messages()
        for index, message in enumerate(messages):
            if isinstance(message, Snapshot):
                return messages[index + 1 :]
        return []

    def wait_until(
        self,
        condition: Callable[[], bool],
        what: str,
        timeout: float = WS_WAIT_SECONDS,
    ) -> None:
        """Wait up to `timeout` seconds for `condition`, else fail the test."""
        with self._changed:
            met = self._changed.wait_for(
                lambda: condition() or len(self._failures) > 0, timeout
            )
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])
        if not met:
            pytest.fail(f"timed out after {timeout}s waiting for {what}")


def has_state_change(peer: Peer, player_id: str, state: PlayerState) -> bool:
    for message in peer.messages():
        if not isinstance(message, PlayerStateChanged):
            continue
        if message.player_id == player_id and message.state == state:
            return True
    return False


def error_events(peer: Peer) -> list[ErrorMessage]:
    found: list[ErrorMessage] = []
    for message in peer.events():
        if isinstance(message, ErrorMessage):
            found.append(message)
    return found


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def open_peer(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
) -> Peer:
    """Open a socket in `stack`, join, and return once the snapshot arrived."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_until(
        lambda: any(isinstance(m, Snapshot) for m in peer.messages()),
        f"the snapshot of {nickname}",
    )
    return peer


def has_player_joined(peer: Peer, player_id: str) -> bool:
    for message in peer.events():
        if isinstance(message, PlayerJoined) and message.player.player_id == player_id:
            return True
    return False


def join_two(
    first_stack: contextlib.ExitStack,
    second_stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
) -> tuple[Peer, Peer]:
    """Join `Ana` (in the first stack) then `Bob`; return once Ana saw Bob."""
    peer_a = open_peer(first_stack, client, code, "Ana")
    peer_b = open_peer(second_stack, client, code, "Bob")
    bob_id = peer_b.snapshot().you
    peer_a.wait_until(lambda: has_player_joined(peer_a, bob_id), "Bob's join on Ana")
    return peer_a, peer_b


@contextlib.contextmanager
def running_room(
    grid: Grid, dist_dir: Path, clock: FakeClock, config: RoomConfig
) -> Iterator[tuple[TestClient, RoomRegistry, str]]:
    """Yield a client, its registry and the code of one room; close it all."""
    registry = RoomRegistry(clock=clock, config=config)
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            yield client, registry, code
    finally:
        registry.close()


LONG_SILENCE_CONFIG = RoomConfig(
    tick_seconds=TICK_SECONDS, silence_timeout_seconds=3600
)


# ---- Helpers for the browser -------------------------------------------------


class MockConnection:
    """One socket the page opened, seen from the mock server."""

    def __init__(self, route: WebSocketRoute, room: MockRoom) -> None:
        self.route = route
        self.room = room
        self.frames: list[str] = []
        route.on_message(self._on_message)

    def _on_message(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.frames.append(text)
        if self.room.answer_pings and parse_client_message(text) == Ping():
            self.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.room.last_sent_at = time.monotonic()
        self.route.send(frame)

    def close(self, code: int) -> None:
        self.route.close(code=code)

    def ping_count(self) -> int:
        count = 0
        for frame in self.frames:
            if parse_client_message(frame) == Ping():
                count += 1
        return count

    def edits(self) -> list[Edit]:
        found: list[Edit] = []
        for frame in self.frames:
            message = parse_client_message(frame)
            if isinstance(message, EditLetter | Erase):
                found.append(message)
        return found


class MockRoom:
    """The server side of /r/ABC123: every socket the page opens, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.connections: list[MockConnection] = []
        self.answer_pings = True
        self.last_sent_at = time.monotonic()

    def handle(self, route: WebSocketRoute) -> None:
        self.connections.append(MockConnection(route, self))

    def wait_for_connections(self, count: int) -> None:
        wait_until(self.page, lambda: len(self.connections) >= count)


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def first_join(page: Page, connection: MockConnection) -> Join:
    """Wait for the first frame of a socket and return it, which must be a join."""
    wait_until(page, lambda: len(connection.frames) > 0)
    message = parse_client_message(connection.frames[0])
    assert isinstance(message, Join)
    return message


def settle(page: Page) -> None:
    page.wait_for_timeout(SETTLE_MS)


def advance_page(page: Page, milliseconds: int) -> None:
    """Move the frozen page clock, letting frames reach the page around it."""
    page.wait_for_timeout(STEP_SETTLE_MS)
    page.clock.run_for(milliseconds)
    page.wait_for_timeout(STEP_SETTLE_MS)


def seed_local_storage(page: Page, items: dict[str, str]) -> None:
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " localStorage.setItem(key, value); }"
    )
    page.context.add_init_script(script)


def player_view(
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


def two_player_views() -> list[PlayerView]:
    return [player_view("p1", "Ana", 0, True), player_view("p2", "Bob", 1)]


def with_letter_cells(view: GridView, changes: ChangeList) -> GridView:
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def snapshot_frame(
    grid: Grid,
    seq: int,
    changes: ChangeList | None = None,
    players: list[PlayerView] | None = None,
) -> str:
    view = grid_view(grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    views = players if players is not None else two_player_views()
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=view,
        players=tuple(views),
        settings=RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
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


def open_room(
    page: Page,
    base_url: str,
    *,
    frozen: bool = False,
    identity: bool = True,
    answer_pings: bool = True,
    init_script: str | None = None,
) -> MockRoom:
    """Open /r/ABC123 on a mocked socket and wait for the first socket.

    With `identity` the stored identity of spec 012 is seeded and the page joins
    at once; without it the nickname form is shown. With `frozen` the page clock
    stands still until a test moves it with `advance_page`. An `init_script` is
    added after the mock, so it wraps the mocked `WebSocket`.
    """
    room = MockRoom(page)
    room.answer_pings = answer_pings
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), room.handle)
    if init_script is not None:
        page.add_init_script(init_script)
    if identity:
        seed_local_storage(page, {"nock.identity.ABC123": STORED_IDENTITY})
    if frozen:
        page.clock.install(time=0)
        page.clock.pause_at(1)
    page.goto(f"{base_url}/r/ABC123")
    room.wait_for_connections(1)
    if identity:
        wait_until(page, lambda: len(room.connections[0].frames) > 0)
    return room


def joined_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    seq: int = 5,
    frozen: bool = False,
    answer_pings: bool = True,
    init_script: str | None = None,
    changes: ChangeList | None = None,
) -> MockRoom:
    """Open the room, answer the join with a snapshot and wait until shown."""
    room = open_room(
        page,
        base_url,
        frozen=frozen,
        answer_pings=answer_pings,
        init_script=init_script,
    )
    room.connections[0].send(snapshot_frame(grid, seq, changes))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    return room


def room_page(page: Page) -> Locator:
    return page.get_by_test_id("room-page")


def banner(page: Page) -> Locator:
    return page.get_by_test_id("connection-banner")


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def expect_cell(
    page: Page,
    row: int,
    column: int,
    letter: str,
    unconfirmed: bool,
    author: str | None = None,
) -> None:
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute(
        "data-unconfirmed", "true" if unconfirmed else "false"
    )
    if author is not None:
        expect(cell).to_have_attribute("data-author", author)


def expect_offline(page: Page) -> None:
    expect(room_page(page)).to_have_attribute(
        "data-status", "reconnecting", timeout=LOSS_BUDGET_MS
    )
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)


def expect_status(page: Page, status: str) -> None:
    expect(room_page(page)).to_have_attribute("data-status", status)


def expect_new_connection_after(page: Page, room: MockRoom, delay_ms: int) -> None:
    """The next socket opens after `delay_ms` of page time, not before."""
    count = len(room.connections)
    advance_page(page, delay_ms - 1)
    assert len(room.connections) == count
    advance_page(page, 1)
    wait_until(page, lambda: len(room.connections) > count)
    assert len(room.connections) == count + 1
