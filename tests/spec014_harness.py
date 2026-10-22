"""Shared setup of the tests of spec 014: host controls (remove, lock, hand-over,
settings).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_spec_014_ac*.py`, one file per criterion, and import from
here what more than one criterion uses: the constants, the helpers for the rules,
for the real WebSocket and for the browser. What only one criterion uses stays in
its file. The helpers that only the window tests (AC-7 to AC-10) share are in
`tests/spec014_windows_harness.py`, which imports from this module; this module
never imports from it.

How the tests are built:

- The rules (`handle_message`, `join_room`, `tick`) are tested directly with exact
  clock values. The hub is tested with the real WebSocket, a fake clock and
  `tick_seconds=0.05`. The pages are tested twice: against the live server with two
  browser contexts (the flows of the criteria), and with spec 040's mocked socket
  (the exact messages the page sends, the snapshot updates, the final states and
  the layout of the host's view).
- Pytest finds a fixture by name in the module of the test. The fixtures
  `fx01_grid` and `dist_dir` are defined here once, and each test file that asks
  for them imports them under the same name
  (`from spec014_harness import fx01_grid as fx01_grid`, the form that tells ruff
  the import is meant to stay).
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ChangeSettings,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    HelpMode,
    Join,
    LockRoom,
    MutePlayer,
    Ping,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RemovePlayer,
    RevealBudget,
    RoomSettings,
    SelectCell,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    LogEntry,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    handle_message,
    join_room,
    new_room,
)
from nock.server import create_app
from nock.store import RoomStore

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eva", "Fay", "Gus", "Hal"]
NEW_PLAYER_ID = "new-player"
NEW_TOKEN = "new-player-token-0000"
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
STORED_IDENTITY = json.dumps(
    {"player_id": "p1", "resume_token": SNAPSHOT_TOKEN, "nickname": "ANA"}
)
IDENTITY_KEY = "nock.identity.ABC123"

TICK_SECONDS = 0.05
SETTLE_SECONDS = 0.3
WS_WAIT_SECONDS = 5.0
WS_DETECTION_SECONDS = 1.0  # the spec: "within one second of real time"
WAIT_TIMEOUT_MS = 5000
STEP_SETTLE_MS = 120
SETTLE_MS = 400
LOSS_BUDGET_MS = 5000
FORM_TIMEOUT_MS = 5000

# A room that never times a silent socket out, so that only the host rules act.
QUIET_CONFIG = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=3600)
QUIET_RULES = RoomConfig(silence_timeout_seconds=3600)

START_SETTINGS = RoomSettings(
    help_mode=HelpMode.FREE,
    reveal_budget=RevealBudget(letters=5, words=1),
    locked=False,
)


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


Sendable = (
    Join
    | Ping
    | RemovePlayer
    | LockRoom
    | ChangeSettings
    | EditLetter
    | MutePlayer
    | SelectCell
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Helpers for the rules --------------------------------------------------


def token_of(number: int) -> str:
    """Return the resume token of player `p<number>`."""
    return f"player-token-number-{number:02d}"


def room_of_players(grid: Grid, count: int) -> RoomState:
    """Return a room where `p1` to `p<count>` joined at NOW, seq `count`.

    `p1` is the host. Their nicknames are `NICKNAMES` in order, their colours
    0, 1, 2... and the room starts with the settings `START_SETTINGS`.
    """
    state = new_room(ROOM_CODE, grid, NOW)
    for number in range(1, count + 1):
        join = Join(nickname=NICKNAMES[number - 1], resume_token=None)
        outcome = join_room(state, join, NOW, f"p{number}", token_of(number))
        state = outcome.state
    assert state.seq == count
    settings = state.settings.model_copy(
        update={"reveal_budget": START_SETTINGS.reveal_budget}
    )
    return state.model_copy(
        update={"settings": settings, "reveal_budget": START_SETTINGS.reveal_budget}
    )


def player_of(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id} in the room")


def player_ids(state: RoomState) -> list[str]:
    ids: list[str] = []
    for player in state.players:
        ids.append(player.player_id)
    return ids


def with_player(room: RoomState, player_id: str, **update: object) -> RoomState:
    """Return the room with some fields of one player replaced."""
    players: list[PlayerRecord] = []
    for player in room.players:
        if player.player_id == player_id:
            players.append(player.model_copy(update=update))
        else:
            players.append(player)
    return room.model_copy(update={"players": tuple(players)})


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


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


def sole_snapshot(outcome: Outcome) -> Snapshot:
    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    return snapshot


def assert_nothing_changed(before: RoomState, after: RoomState) -> None:
    """Assert the roster, the bans, the settings and the seq are the same."""
    assert after.seq == before.seq
    assert player_ids(after) == player_ids(before)
    assert after.removed_tokens == before.removed_tokens
    assert after.settings == before.settings
    assert after.reveal_budget == before.reveal_budget


def host_acts(
    room: RoomState, message: RemovePlayer | LockRoom | ChangeSettings
) -> Outcome:
    return handle_message(room, "p1", message, NOW + 1)


def locked(room: RoomState) -> RoomState:
    """Return the room locked by its host."""
    outcome = host_acts(room, LockRoom(locked=True))
    assert outcome.state.settings.locked is True
    return outcome.state


def removed_bob(room: RoomState) -> RoomState:
    """Return the room after the host removed `p2`."""
    outcome = host_acts(room, RemovePlayer(player_id="p2"))
    remaining: list[str] = []
    for player_id in player_ids(room):
        if player_id != "p2":
            remaining.append(player_id)
    assert player_ids(outcome.state) == remaining
    return outcome.state


def new_guest(nickname: str = "Zoe", token: str | None = None) -> Join:
    return Join(nickname=nickname, resume_token=token)


# ---- Helpers for the real WebSocket -----------------------------------------


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


def error_codes(peer: Peer) -> list[ErrorCode]:
    """The code of each error the peer received, in order."""
    codes: list[ErrorCode] = []
    for message in peer.messages():
        if isinstance(message, ErrorMessage):
            codes.append(message.code)
    return codes


def left_events(peer: Peer) -> list[PlayerLeft]:
    found: list[PlayerLeft] = []
    for message in peer.events():
        if isinstance(message, PlayerLeft):
            found.append(message)
    return found


def settings_events(peer: Peer) -> list[SettingsChanged]:
    found: list[SettingsChanged] = []
    for message in peer.events():
        if isinstance(message, SettingsChanged):
            found.append(message)
    return found


def has_state_change(peer: Peer, player_id: str, state: PlayerState) -> bool:
    for message in peer.messages():
        if not isinstance(message, PlayerStateChanged):
            continue
        if message.player_id == player_id and message.state == state:
            return True
    return False


def has_player_joined(peer: Peer, player_id: str) -> bool:
    for message in peer.events():
        if isinstance(message, PlayerJoined) and message.player.player_id == player_id:
            return True
    return False


def pong_count(peer: Peer) -> int:
    count = 0
    for message in peer.messages():
        if isinstance(message, Pong):
            count += 1
    return count


def ping_and_wait(peer: Peer) -> None:
    """Send a ping and wait for its pong: the room has handled what came before."""
    before = pong_count(peer)
    peer.send(Ping())
    peer.wait_until(lambda: pong_count(peer) > before, "the pong of a ping")


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


def open_refused_peer(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
) -> Peer:
    """Open a socket, join, and return once the server closed it."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_until(lambda: peer.close_code is not None, f"the close of {nickname}")
    return peer


def join_in_order(
    stacks: list[contextlib.ExitStack], client: TestClient, code: str
) -> list[Peer]:
    """Join `Ana`, `Bob`, `Cleo`... one per stack; return once each was seen."""
    peers: list[Peer] = []
    for index, stack in enumerate(stacks):
        peer = open_peer(stack, client, code, NICKNAMES[index])
        peers.append(peer)
        new_id = peer.snapshot().you
        for earlier in peers[:-1]:
            earlier.wait_until(
                lambda earlier=earlier, new_id=new_id: has_player_joined(
                    earlier, new_id
                ),
                f"the join of {NICKNAMES[index]}",
            )
    return peers


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


def room_players(registry: RoomRegistry, code: str) -> list[str]:
    state = registry.room_state(code)
    assert state is not None
    return player_ids(state)


def change(help_mode: HelpMode, letters: int, words: int) -> ChangeSettings:
    return ChangeSettings(
        help_mode=help_mode, reveal_budget=RevealBudget(letters=letters, words=words)
    )


@contextlib.contextmanager
def stored_room(
    grid: Grid, dist_dir: Path, clock: FakeClock
) -> Iterator[tuple[TestClient, RoomStore, RoomRegistry, str]]:
    """Yield a client, the store the room is written to, its registry and code."""
    store = RoomStore(":memory:")
    registry = RoomRegistry(clock=clock, config=QUIET_CONFIG, store=store)
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            yield client, store, registry, code
    finally:
        registry.close()
        store.close()


# ---- Helpers for the browser ------------------------------------------------


def seed_identity(page: Page) -> None:
    key = json.dumps(IDENTITY_KEY)
    value = json.dumps(STORED_IDENTITY)
    script = f"localStorage.setItem({key}, {value});"
    page.context.add_init_script(script)


class MockConnection:
    """One socket the page opened, seen from the mock server."""

    def __init__(self, route: WebSocketRoute) -> None:
        self.route = route
        self.frames: list[str] = []
        route.on_message(self._on_message)

    def _on_message(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.frames.append(text)
        if parse_client_message(text) == Ping():
            self.route.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.route.send(frame)

    def close(self, code: int) -> None:
        self.route.close(code=code)

    def messages_of_type(self, type_name: str) -> list[dict[str, object]]:
        """The frames the page sent whose `type` is `type_name`, decoded."""
        found: list[dict[str, object]] = []
        for frame in self.frames:
            decoded = json.loads(frame)
            if decoded["type"] == type_name:
                found.append(decoded)
        return found


class MockRoom:
    """The server side of /r/ABC123: every socket the page opens, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.connections: list[MockConnection] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.connections.append(MockConnection(route))

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


def settle(page: Page) -> None:
    page.wait_for_timeout(SETTLE_MS)


def advance_page(page: Page, milliseconds: int) -> None:
    """Move the frozen page clock, letting frames reach the page around it."""
    page.wait_for_timeout(STEP_SETTLE_MS)
    page.clock.run_for(milliseconds)
    page.wait_for_timeout(STEP_SETTLE_MS)


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


def three_players(host: str = "p1") -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, host == "p1"),
        player_view("p2", "Bob", 1, host == "p2"),
        player_view("p3", "Cleo", 2, host == "p3"),
    ]


def snapshot_frame(
    grid: Grid,
    players: list[PlayerView],
    you: str = "p1",
    seq: int = 5,
    settings: RoomSettings = START_SETTINGS,
    remaining: RevealBudget = START_SETTINGS.reveal_budget,
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you=you,
        resume_token=SNAPSHOT_TOKEN,
        grid=grid_view(grid),
        players=tuple(players),
        settings=settings,
        reveal_budget=remaining,
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def settings_frame(seq: int, player_id: str, settings: RoomSettings) -> str:
    event = SettingsChanged(
        seq=seq,
        player_id=player_id,
        settings=settings,
        reveal_budget=settings.reveal_budget,
    )
    return event.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def open_mock_room(
    page: Page,
    base_url: str,
    *,
    frozen: bool = False,
    identity: bool = True,
) -> MockRoom:
    """Open /r/ABC123 on a mocked socket and wait for the first socket.

    With `identity` the stored identity of spec 012 is seeded and the page joins at
    once. With `frozen` the page clock stands still until `advance_page`.
    """
    room = MockRoom(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), room.handle)
    if identity:
        seed_identity(page)
    if frozen:
        page.clock.install(time=0)
        page.clock.pause_at(1)
    page.goto(f"{base_url}/r/ABC123")
    room.wait_for_connections(1)
    if identity:
        wait_until(page, lambda: len(room.connections[0].frames) > 0)
    return room


def joined_mock_room(
    page: Page,
    base_url: str,
    grid: Grid,
    players: list[PlayerView],
    *,
    you: str = "p1",
    settings: RoomSettings = START_SETTINGS,
    remaining: RevealBudget = START_SETTINGS.reveal_budget,
    frozen: bool = False,
) -> MockRoom:
    """Open the room, answer the join with a snapshot and wait until shown."""
    room = open_mock_room(page, base_url, frozen=frozen)
    frame = snapshot_frame(grid, players, you, 5, settings, remaining)
    room.connections[0].send(frame)
    expect(room_page(page)).to_have_attribute("data-seq", "5")
    expect(room_page(page)).to_have_attribute("data-status", "joined")
    wait_for_fonts(page)
    return room


def room_page(page: Page) -> Locator:
    return page.get_by_test_id("room-page")


def banner(page: Page) -> Locator:
    return page.get_by_test_id("connection-banner")


def roster_item(page: Page, player_id: str) -> Locator:
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    return page.locator(selector)


def feed_lines(page: Page, kind: str) -> Locator:
    selector = f'[data-testid="feed-item"][data-kind="{kind}"]'
    return page.get_by_test_id("activity-feed").locator(selector)


def reach_refusal(
    page: Page, base_url: str, grid: Grid, scenario: str, code: ErrorCode
) -> MockRoom:
    """Drive the mocked server until the page got `code` in `scenario`.

    `join`: the refusal answers the nickname form. `game`: it comes while the
    page is joined. `reconnection`: it answers the join of a reconnection.
    The server then closes the socket with 1000. The page clock is frozen.
    """
    if scenario == "join":
        room = open_mock_room(page, base_url, frozen=True, identity=False)
        nickname_input = page.get_by_test_id("nickname-input")
        nickname_input.fill("Ana", timeout=FORM_TIMEOUT_MS)
        nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
        wait_until(page, lambda: len(room.connections[0].frames) > 0)
        refused = room.connections[0]
    else:
        room = open_mock_room(page, base_url, frozen=True)
        room.connections[0].send(snapshot_frame(grid, three_players()))
        expect(room_page(page)).to_have_attribute("data-status", "joined")
        refused = room.connections[0]
        if scenario == "reconnection":
            refused.close(1011)
            expect(room_page(page)).to_have_attribute(
                "data-status", "reconnecting", timeout=LOSS_BUDGET_MS
            )
            expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
            advance_page(page, 1000)
            room.wait_for_connections(2)
            refused = room.connections[1]
            wait_until(page, lambda: len(refused.frames) > 0)
    refused.send(error_frame(code))
    refused.close(1000)
    return room
