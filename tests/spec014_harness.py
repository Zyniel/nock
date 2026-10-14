"""Shared setup of the tests of spec 014: host controls (remove, lock, hand-over,
settings).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_spec_014_ac*.py`, one file per criterion, and import from
here what more than one criterion uses: the constants, the helpers for the rules,
for the real WebSocket and for the browser, the scripts run in the page and the
helpers of the small windows (AC-7 to AC-10). What only one criterion uses stays
in its file.

How the tests are built:

- The rules (`handle_message`, `join_room`, `tick`) are tested directly with exact
  clock values. The hub is tested with the real WebSocket, a fake clock and
  `tick_seconds=0.05`. The pages are tested twice: against the live server with two
  browser contexts (the flows of the criteria), and with spec 040's mocked socket
  (the exact messages the page sends, the snapshot updates, the final states and
  the layout of the host's view).
- Pytest finds a fixture by name in the module of the test. The fixtures
  `fx01_grid`, `dist_dir` and `small_window` are defined here once, and each test
  file that asks for them imports them under the same name
  (`from spec014_harness import fx01_grid as fx01_grid`, the form that tells ruff
  the import is meant to stay).
- Before they measure a layout, the window tests wait up to 1 s for the buttons to
  follow the rule of AC-9 (`wait_for_the_form`; the spec lets a text check poll that
  long). A page that never follows it is reported by the AC-9 tests, not by the
  others.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

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
    {"player_id": "p1", "resume_token": SNAPSHOT_TOKEN, "nickname": "Ana"}
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
EPSILON = 1.0
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged
# (the script of spec 009, for the touch contexts of Firefox and WebKit).
COARSE_POINTER_SCRIPT = r"""
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""

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


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(player_view(f"p{number}", NICKNAMES[number - 1], number - 1))
    return players


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


# ---- Helpers for the window tests (AC-7 to AC-10) ---------------------------


def make_page(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> tuple[Page, Callable[[], None]]:
    """Open a desktop or touch page (spec 009's harness); return it and its closer."""
    viewport = {"width": width, "height": height}
    if not touch:
        context = browser.new_context(viewport=viewport)
    elif browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if touch and browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context.new_page(), context.close


MIN_TARGET_PX = 24.0
TARGET_TOLERANCE_PX = 0.01


def panel_shows_a_more_marker(page: Page) -> bool:
    """Tell whether `host-panel-more` is visible at an edge of the panel."""
    marker = page.get_by_test_id("host-panel-more")
    if marker.count() == 0 or not marker.first.is_visible():
        return False
    marker_box = marker.first.bounding_box()
    panel_box = page.get_by_test_id("host-panel").bounding_box()
    if marker_box is None or panel_box is None:
        return False
    panel_right = panel_box["x"] + panel_box["width"]
    marker_right = marker_box["x"] + marker_box["width"]
    touches_panel = (
        marker_box["x"] <= panel_right + EPSILON
        and marker_right >= panel_box["x"] - EPSILON
    )
    inside_rows = (
        marker_box["y"] + marker_box["height"] >= panel_box["y"] - EPSILON
        and marker_box["y"] <= panel_box["y"] + panel_box["height"] + EPSILON
    )
    return touches_panel and inside_rows


FOCUSED_TEST_ID_SCRIPT = (
    "() => document.activeElement && document.activeElement.getAttribute('data-testid')"
)
MAX_TABS = 60


def tab_to_control(page: Page, test_id: str) -> None:
    """Press Tab until the control has the focus; Escape frees Tab from the grid."""
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        focused = page.evaluate(FOCUSED_TEST_ID_SCRIPT)
        if focused == test_id:
            return
        if focused == "grid":
            page.keyboard.press("Escape")
    pytest.fail(f"{test_id} not reached in {MAX_TABS} Tab presses")


# ---- The hit test of a remove button (AC-8, AC-9) ---------------------------


# The check itself, for the button where it stands now. AC-8 scrolls the button into
# view first (HIT_TEST_SCRIPT); AC-9 runs it as it is (HIT_TEST_IN_PLACE_SCRIPT),
# once the page scrolled a focused button by itself.
HIT_TEST_BODY = """
  const box = button.getBoundingClientRect();
  const misses = [];
  let tested = 0;
  for (let y = Math.ceil(box.top); y + 1 <= box.bottom; y += 1) {
    for (let x = Math.ceil(box.left); x + 1 <= box.right; x += 1) {
      tested += 1;
      const hit = document.elementFromPoint(x + 0.5, y + 0.5);
      if (hit === null || !(hit === button || button.contains(hit))) {
        const name = hit === null ? 'nothing' : (
          hit.getAttribute('data-testid') || hit.tagName
        );
        misses.push([x, y, name]);
      }
    }
  }
  return {
    tested, missCount: misses.length, firstMisses: misses.slice(0, 5),
    size: [box.width, box.height],
  };
"""
HIT_TEST_SCRIPT = (
    "button => { button.scrollIntoView({block: 'nearest', inline: 'nearest'});"
    + HIT_TEST_BODY
    + "}"
)
HIT_TEST_IN_PLACE_SCRIPT = "button => {" + HIT_TEST_BODY + "}"


# ---- Small windows (AC-8 to AC-10): the windows and what the tests share ----


REMOVE_BUTTON_COUNT = 7
DEFAULT_ROOT_FONT_PX = 16
SWITCH_IN_ROOT_FONTS = 4.5  # AC-9: compact while the list is narrower than 4.5rem
SWITCH_TOLERANCE_PX = 1.0  # AC-9: within 1 px of the threshold, either form passes
LIVE_CHANGE_MS = 1000  # AC-9, AC-10: a change applies "within 1 s"
POLL_MS = 50
MIN_HIT_PIXELS = 24 * 24 - 2 * 24


class Window(NamedTuple):
    """A window size in CSS px, and the root font size in px to run it at."""

    width: int
    height: int
    root_font: int


def window_id(window: Window) -> str:
    return f"{window.width}x{window.height}-{window.root_font}px"


# The narrow and low windows of the spec's "Test harness".
NARROW_LOW_WINDOWS = [
    Window(300, 480, 16),
    Window(300, 480, 20),
    Window(300, 480, 12),
    Window(300, 480, 24),
    Window(320, 480, 16),
    Window(320, 480, 20),
    Window(360, 500, 16),
    Window(360, 500, 20),
    Window(400, 480, 16),
    Window(400, 480, 20),
    Window(480, 500, 16),
    Window(480, 500, 20),
]
NARROW_LOW_IDS = [window_id(window) for window in NARROW_LOW_WINDOWS]

ROOT_FONT_SCRIPT = "size => { document.documentElement.style.fontSize = size; }"
ROOT_FONT_READS_SCRIPT = (
    "size => getComputedStyle(document.documentElement).fontSize === size"
)
TWO_FRAMES_SCRIPT = """
() => new Promise(resolve => {
  requestAnimationFrame(() => requestAnimationFrame(() => resolve(true)));
})
"""
# `w` is the clientWidth of the roster list and `r` the computed font size of `html`
# in CSS px (spec 014, "Small windows"), then the text of each remove button.
BUTTONS_STATE_SCRIPT = """
() => {
  const list = document.querySelector('[data-testid="roster"] ul');
  const buttons = document.querySelectorAll('[data-testid="remove-player"]');
  const texts = [];
  for (const button of buttons) {
    texts.push(button.textContent.trim());
  }
  return {
    listWidth: list.clientWidth,
    rootFont: parseFloat(getComputedStyle(document.documentElement).fontSize),
    texts: texts,
  };
}
"""


def wait_for_root_font(page: Page, size_px: int) -> None:
    """Wait until `html` computes that font size, then for two animation frames."""
    page.wait_for_function(
        ROOT_FONT_READS_SCRIPT, arg=f"{size_px}px", timeout=WAIT_TIMEOUT_MS
    )
    page.evaluate(TWO_FRAMES_SCRIPT)


def set_root_font(page: Page, size_px: int) -> None:
    """Set the root font size with a style on `html`, as the spec's harness says."""
    page.evaluate(ROOT_FONT_SCRIPT, f"{size_px}px")
    wait_for_root_font(page, size_px)


def use_root_font(page: Page, size_px: int) -> None:
    """Give the page the root font size of a window.

    16 px is the browser default, so nothing is added for it.
    """
    if size_px == DEFAULT_ROOT_FONT_PX:
        wait_for_root_font(page, size_px)
    else:
        set_root_font(page, size_px)


class ButtonsState(NamedTuple):
    """What AC-9 reads: the list width `w`, the root font `r` and the texts."""

    list_width: float
    root_font: float
    texts: list[str]


def read_buttons_state(page: Page) -> ButtonsState:
    raw = page.evaluate(BUTTONS_STATE_SCRIPT)
    return ButtonsState(
        list_width=raw["listWidth"], root_font=raw["rootFont"], texts=raw["texts"]
    )


def rule_violation(
    state: ButtonsState, full_text: str, compact_text: str
) -> str | None:
    """Return how a state breaks the rule of AC-9, or None when it holds.

    Compact while `w < 4.5 r`, full from `w >= 4.5 r`; within 1 px of `4.5 r`
    either passes; all the buttons show the same one.
    """
    if len(state.texts) != REMOVE_BUTTON_COUNT:
        return f"expected {REMOVE_BUTTON_COUNT} remove buttons: {state}"
    if len(set(state.texts)) != 1:
        return f"the buttons do not all have the same form: {state}"
    threshold = SWITCH_IN_ROOT_FONTS * state.root_font
    if state.list_width < threshold - SWITCH_TOLERANCE_PX:
        allowed = [compact_text]
    elif state.list_width > threshold + SWITCH_TOLERANCE_PX:
        allowed = [full_text]
    else:
        allowed = [compact_text, full_text]
    shown = state.texts[0]
    if shown in allowed:
        return None
    return (
        f"w={state.list_width} and 4.5 x r = {threshold}: the buttons should read "
        f"{allowed} but read {shown!r} ({state})"
    )


def wait_for_the_form(page: Page) -> None:
    """Give the buttons up to 1 s to take the form that AC-9 asks for.

    The tests that measure the layout call this before measuring, so that a page
    that follows a root font change a moment later is not measured half-way. It
    never fails: the AC-9 tests report a wrong form, the other tests measure what
    is there. Without the key `host.remove_short` there is nothing to wait for.
    """
    fr = load_fr()
    compact_text = fr.get("host.remove_short")
    if compact_text is None:
        return
    waited_ms = 0
    while waited_ms < LIVE_CHANGE_MS:
        state = read_buttons_state(page)
        if rule_violation(state, fr["host.remove"], compact_text) is None:
            return
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS


class OpenSmallWindow(Protocol):
    """The `small_window` fixture: open the host's view in a window."""

    def __call__(
        self, window: Window, touch: bool = False
    ) -> tuple[Page, MockRoom]: ...


@pytest.fixture
def small_window(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> Iterator[OpenSmallWindow]:
    """Return `small_window(window, touch=False)`: the host's view in that window.

    The setup of AC-8 (FX-01, `you` host, 8 players, so 7 `remove-player` buttons)
    in a desktop or a touch context of the window's size. The call returns the page
    and the mocked room once the roster is shown, the root font is set and the
    buttons had their moment to follow it. The contexts close after the test.
    """
    closers: list[Callable[[], None]] = []

    def open_window(window: Window, touch: bool = False) -> tuple[Page, MockRoom]:
        page, close = make_page(
            browser, browser_name, window.width, window.height, touch
        )
        closers.append(close)
        room = joined_mock_room(page, live_server, fx01_grid, eight_players())
        buttons = page.get_by_test_id("remove-player")
        expect(buttons).to_have_count(REMOVE_BUTTON_COUNT)
        use_root_font(page, window.root_font)
        wait_for_the_form(page)
        page.evaluate(TWO_FRAMES_SCRIPT)
        return page, room

    yield open_window
    for close in closers:
        close()


LIVE_WINDOW = Window(480, 500, DEFAULT_ROOT_FONT_PX)
