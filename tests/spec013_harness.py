"""Shared setup of the tests of spec 013: presence.

This module is not a test file: pytest does not collect it. The tests of spec 013
are in `tests/test_spec_013_*.py`, one file per criterion group.

The rules (`handle_message`, `tick`, `disconnect_player`) are tested directly with
exact clock values. The hub is tested with the real WebSocket, a fake clock and
`tick_seconds=0.05`. The page is tested with spec 040's mocked socket and the
events built with the `nock.protocol` models.

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
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    CheckResult,
    Direction,
    GridTarget,
    HelpMode,
    Join,
    Ping,
    PlayerJoined,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    SelectCell,
    Selection,
    SelectionMoved,
    ServerMessage,
    Snapshot,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import LogEntry, PlayerRecord, RoomConfig, RoomState, join_room, new_room
from nock.server import create_app

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
NICKNAMES = ["Ana", "Bob", "Cleo"]
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

TICK_SECONDS = 0.05
SETTLE_SECONDS = 0.3
WS_WAIT_SECONDS = 5.0
WS_DETECTION_SECONDS = 1.0  # the spec: "within one second of real time"
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
FORM_TIMEOUT_MS = 5000
FEED_LIMIT = 100

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

# A room that never times a silent socket out, so that only idleness changes.
QUIET_CONFIG = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=3600)

DEFAULT_ROOM_SETTINGS = RoomSettings(
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


def letter_cells_of_fx01() -> list[tuple[int, int]]:
    """The 18 letter cells of FX-01 as (row, column)."""
    cells = [(0, 1)]
    for column in range(5):
        cells.append((1, column))
    for row in range(2, 5):
        for column in range(1, 5):
            cells.append((row, column))
    return cells


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixture)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Helpers for the rules --------------------------------------------------


def token_of(number: int) -> str:
    return f"player-token-number-{number:02d}"


def room_of_players(grid: Grid, count: int) -> RoomState:
    """A room where `p1` to `p<count>` joined at NOW, seq `count`; `p1` is host."""
    state = new_room(ROOM_CODE, grid, NOW)
    for number in range(1, count + 1):
        join = Join(nickname=NICKNAMES[number - 1], resume_token=None)
        outcome = join_room(state, join, NOW, f"p{number}", token_of(number))
        state = outcome.state
    assert state.seq == count
    return state


def player_of(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id} in the room")


def events_of(entries: tuple[LogEntry, ...]) -> list[object]:
    """The event of each log entry."""
    events: list[object] = []
    for entry in entries:
        events.append(entry.event)
    return events


def state_event(seq: int, player_id: str, state: PlayerState) -> PlayerStateChanged:
    return PlayerStateChanged(seq=seq, player_id=player_id, state=state)


# ---- Helpers for the real WebSocket -----------------------------------------


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives.

    All waits are bounded.
    """

    def __init__(self, websocket: WebSocketTestSession) -> None:
        self._websocket = websocket
        self._changed = threading.Condition()
        self._messages: list[ServerMessage] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except WebSocketDisconnect:
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

    def send(self, message: Join | Ping | SelectCell) -> None:
        self._websocket.send_text(message.model_dump_json())

    def messages(self) -> list[ServerMessage]:
        with self._changed:
            return list(self._messages)

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


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def open_peer(
    stack: contextlib.ExitStack, client: TestClient, code: str, nickname: str
) -> Peer:
    """Open a socket in `stack`, join, and return once the snapshot arrived."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=None))
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


def selection_events(peer: Peer) -> list[SelectionMoved]:
    found: list[SelectionMoved] = []
    for message in peer.events():
        if isinstance(message, SelectionMoved):
            found.append(message)
    return found


def pong_count(peer: Peer) -> int:
    count = 0
    for message in peer.messages():
        if isinstance(message, Pong):
            count += 1
    return count


def ping_and_wait(peer: Peer) -> None:
    """Send a ping and wait for its pong: the room has handled the ping."""
    before = pong_count(peer)
    peer.send(Ping())
    peer.wait_until(lambda: pong_count(peer) > before, "the pong of a ping")


# ---- Helpers for the browser, with the mocked socket ------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the route
    that sent it: without the answer, the page takes 4 s without a frame from the
    server for a lost connection (spec 017, AC-4), so a step that takes longer on a
    slow engine would find the page `reconnecting`.
    """

    def __init__(self, page: Page) -> None:
        self.page = page
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)

        def on_message(message: str | bytes) -> None:
            self._record_and_answer(route, message)

        route.on_message(on_message)

    def _record_and_answer(self, route: WebSocketRoute, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)
        if parse_client_message(text) == Ping():
            route.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)


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


def player_view(
    player_id: str,
    nickname: str,
    colour: int,
    *,
    state: PlayerState = PlayerState.ACTIVE,
    is_host: bool = False,
    selection: Selection | None = None,
) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=state,
        is_host=is_host,
        muted=False,
        selection=selection,
    )


def snapshot_frame(
    grid: Grid,
    players: list[PlayerView],
    seq: int,
    settings: RoomSettings = DEFAULT_ROOM_SETTINGS,
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=grid_view(grid),
        players=tuple(players),
        settings=settings,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_room(
    page: Page,
    base_url: str,
    grid: Grid,
    players: list[PlayerView],
    seq: int = 3,
    settings: RoomSettings = DEFAULT_ROOM_SETTINGS,
) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket, join as `p1` and show a snapshot."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
    wait_until(page, lambda: len(mock.received) > 0)
    mock.send(snapshot_frame(grid, players, seq, settings))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    wait_for_fonts(page)
    return mock


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def roster_item(page: Page, player_id: str) -> Locator:
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    return page.locator(selector)


def background_of(locator: Locator) -> str:
    background = locator.evaluate("el => getComputedStyle(el).backgroundColor")
    assert isinstance(background, str)
    return background


def swatch_colour(page: Page, player_id: str) -> str:
    """The computed background colour of the `roster-colour` of a player."""
    return background_of(roster_item(page, player_id).get_by_test_id("roster-colour"))


def state_frame(seq: int, player_id: str, state: PlayerState) -> str:
    return state_event(seq, player_id, state).model_dump_json()


def selection_frame(player_id: str, row: int, column: int, direction: Direction) -> str:
    selection = Selection(row=row, column=column, direction=direction)
    return SelectionMoved(player_id=player_id, selection=selection).model_dump_json()


def clear_frame(player_id: str) -> str:
    return SelectionMoved(player_id=player_id, selection=None).model_dump_json()


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


# ---- Helpers for the selections in the browser (AC-2, AC-3, AC-4) -----------


def remote_players_on(page: Page, row: int, column: int) -> list[tuple[str, str]]:
    """The (player id, colour) of each `remote-selection` of a cell, in DOM order."""
    script = (
        "el => Array.from(el.querySelectorAll('[data-testid=\"remote-selection\"]'))"
        ".map(e => [e.getAttribute('data-player-id'), e.getAttribute('data-colour')])"
    )
    found = cell_at(page, row, column).evaluate(script)
    return [(player_id, colour) for player_id, colour in found]


def all_remote_selections(page: Page) -> int:
    return page.get_by_test_id("remote-selection").count()


def tinted_by_map(page: Page) -> dict[tuple[int, int], str | None]:
    """The `data-tinted-by` value of every letter cell (None: no attribute)."""
    script = (
        "() => Array.from(document.querySelectorAll("
        '\'[data-testid="cell"][data-type="letter"]\'))'
        ".map(e => [Number(e.dataset.row), Number(e.dataset.column),"
        " e.getAttribute('data-tinted-by')])"
    )
    found = page.evaluate(script)
    result: dict[tuple[int, int], str | None] = {}
    for row, column, value in found:
        result[(row, column)] = value
    return result


def expected_tints(tinted: dict[tuple[int, int], str]) -> dict[tuple[int, int], str]:
    """Every FX-01 letter cell mapped to its tint, `""` when it is not in `tinted`."""
    result: dict[tuple[int, int], str] = {}
    for cell in letter_cells_of_fx01():
        result[cell] = tinted.get(cell, "")
    return result


ROW_2_WORD = [(2, 1), (2, 2), (2, 3), (2, 4)]


def triangle_fill(locator: Locator) -> str | None:
    """The computed `fill` of a `remote-selection`'s polygon (None: no polygon).

    Spec 042 draws another player's selected cell as a corner triangle: an `svg`
    holding one `polygon` filled with the player's colour.
    """
    script = (
        "el => { const polygon = el.querySelector('polygon');"
        " return polygon === null ? null : getComputedStyle(polygon).fill; }"
    )
    fill = locator.evaluate(script)
    assert fill is None or isinstance(fill, str)
    return fill


# ---- Helpers for the activity feed (AC-5, AC-6, AC-7, AC-8) -----------------


def feed_snapshot_players() -> list[PlayerView]:
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)]


def check_frame(
    seq: int, player_id: str, target: CellTarget | GridTarget | WordTarget
) -> str:
    event = CheckResult(
        seq=seq, player_id=player_id, target=target, correct=(), wrong=()
    )
    return event.model_dump_json()


def feed_items(page: Page) -> list[tuple[str, str, str]]:
    """The (kind, seq, text) of each feed item, oldest first."""
    script = (
        "() => Array.from(document.querySelectorAll("
        '\'[data-testid="activity-feed"] [data-testid="feed-item"]\'))'
        ".map(e => [e.getAttribute('data-kind'), e.getAttribute('data-seq'),"
        " e.textContent.trim()])"
    )
    found = page.evaluate(script)
    return [(kind, seq, text) for kind, seq, text in found]


def feed_locator(page: Page) -> Locator:
    return page.get_by_test_id("activity-feed").get_by_test_id("feed-item")
