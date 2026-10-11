"""Tests of spec 013: presence (idle state, remote selections, activity feed).

The rules (`handle_message`, `tick`, `disconnect_player`) are tested directly with
exact clock values. The hub is tested with the real WebSocket, a fake clock and
`tick_seconds=0.05`. The page is tested with spec 040's mocked socket and the
events built with the `nock.protocol` models.

The feed lines for checks, reveals, flags, lock, settings and host changes are
tested with mocked events only: the server does not produce them yet (specs 014,
021, 023 and 024).

Not tested here: the loss of selections on a server restart (spec 018
`after_restart`), because nothing observable in the public interface of this spec
tells a selection from the other fields of a player there.
"""

from __future__ import annotations

import contextlib
import json
import math
import random
import re
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    Chat,
    Check,
    CheckResult,
    ClueRef,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    Flag,
    FlagChanged,
    GridTarget,
    HelpMode,
    HostChanged,
    Join,
    LeaveReason,
    LetterChanged,
    LockRoom,
    PencilEdit,
    Ping,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    Reveal,
    RevealBudget,
    RevealResult,
    RoomSettings,
    SelectCell,
    Selection,
    SelectionMoved,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    Undo,
    Vote,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    LogEntry,
    PlayerRecord,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    snapshot_for,
    tick,
)
from nock.server import create_app

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
NICKNAMES = ["Ana", "Bob", "Cleo"]
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

IDLE_AFTER_SECONDS = 120.0
TICK_SECONDS = 0.05
SETTLE_SECONDS = 0.3
WS_WAIT_SECONDS = 5.0
WS_DETECTION_SECONDS = 1.0  # the spec: "within one second of real time"
RELAY_P95_SECONDS = 0.1
RELAY_SAMPLES = 100
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
DRAW_BUDGET_MS = 300
FORM_TIMEOUT_MS = 5000
FEED_LIMIT = 100
TAP_TIMEOUT_MS = 3000
MIN_GRID_VIEWPORT_PX = 100.0
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
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]

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

CLUE_FATALES = ClueRef(row=0, column=3, clue_index=0)
CLUE_MARINE = ClueRef(row=0, column=0, clue_index=1)


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


# ---- Helpers for the rules ---------------------------------------------------


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


def with_player(room: RoomState, player_id: str, **update: object) -> RoomState:
    """The room with some fields of one player replaced."""
    players: list[PlayerRecord] = []
    for player in room.players:
        if player.player_id == player_id:
            players.append(player.model_copy(update=update))
        else:
            players.append(player)
    return room.model_copy(update={"players": tuple(players)})


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


def idle_room(grid: Grid) -> RoomState:
    """A two-player room where both players are idle (after 120 s without input)."""
    room = room_of_players(grid, 2)
    outcome = tick(room, NOW + IDLE_AFTER_SECONDS, QUIET_CONFIG)
    assert player_of(outcome.state, "p1").state is PlayerState.IDLE
    return outcome.state


def state_event(seq: int, player_id: str, state: PlayerState) -> PlayerStateChanged:
    return PlayerStateChanged(seq=seq, player_id=player_id, state=state)


# ---- AC-1: the idle state, rules -----------------------------------------------


def test_ac1_tick_just_before_120_seconds_changes_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 119.9, QUIET_CONFIG)

    assert outcome.entries == ()
    assert outcome.state == room
    assert outcome.to_others == ()


def test_ac1_tick_at_120_seconds_makes_the_player_idle(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert len(outcome.entries) == 1
    entry = outcome.entries[0]
    assert entry.event == state_event(2, "p1", PlayerState.IDLE)
    assert entry.at == NOW + 120
    assert player_of(outcome.state, "p1").state is PlayerState.IDLE
    assert outcome.state.seq == 2


def test_ac1_tick_after_the_threshold_is_also_idle(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 500, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_tick_idles_players_in_players_order(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [
        state_event(4, "p1", PlayerState.IDLE),
        state_event(5, "p2", PlayerState.IDLE),
        state_event(6, "p3", PlayerState.IDLE),
    ]


def test_ac1_only_the_players_without_recent_input_turn_idle(fx01_grid: Grid) -> None:
    room = with_player(room_of_players(fx01_grid, 2), "p1", last_input_at=NOW + 100)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(3, "p2", PlayerState.IDLE)]
    assert player_of(outcome.state, "p1").state is PlayerState.ACTIVE


def test_ac1_idleness_counts_from_last_input_not_from_last_seen(
    fx01_grid: Grid,
) -> None:
    room = with_player(room_of_players(fx01_grid, 1), "p1", last_seen_at=NOW + 119)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_the_threshold_is_the_configured_one(fx01_grid: Grid) -> None:
    config = RoomConfig(idle_after_seconds=30, silence_timeout_seconds=3600)
    room = room_of_players(fx01_grid, 1)

    before = tick(room, NOW + 29.9, config)
    at_threshold = tick(room, NOW + 30, config)

    assert before.entries == ()
    assert events_of(at_threshold.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_an_idle_player_does_not_turn_idle_again(fx01_grid: Grid) -> None:
    idle = idle_room(fx01_grid)

    outcome = tick(idle, NOW + 400, QUIET_CONFIG)

    assert outcome.entries == ()
    assert outcome.state == idle


def test_ac1_a_disconnected_player_never_turns_idle(fx01_grid: Grid) -> None:
    room = with_player(
        room_of_players(fx01_grid, 2),
        "p2",
        state=PlayerState.DISCONNECTED,
        disconnected_at=NOW + 10,
    )

    outcome = tick(room, NOW + 200, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(3, "p1", PlayerState.IDLE)]
    assert player_of(outcome.state, "p2").state is PlayerState.DISCONNECTED


def test_ac1_a_select_cell_from_an_idle_player_makes_them_active_first(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)
    selection = Selection(row=1, column=1, direction=Direction.ACROSS)

    outcome = handle_message(
        idle, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 130
    )

    assert events_of(outcome.entries) == [
        state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130
    assert player.selection == selection
    assert player_of(outcome.state, "p2").state is PlayerState.IDLE


@pytest.mark.parametrize("message", [Ping(), Join(nickname="Ana", resume_token=None)])
def test_ac1_ping_and_join_are_not_input(fx01_grid: Grid, message: Ping | Join) -> None:
    idle = idle_room(fx01_grid)

    outcome = handle_message(idle, "p1", message, NOW + 130)

    assert outcome.entries == ()
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.IDLE
    assert player.last_input_at == NOW


InputMessage = (
    SelectCell
    | EditLetter
    | Erase
    | PencilEdit
    | ConfirmPencil
    | Undo
    | Check
    | Reveal
    | Vote
    | Flag
    | Chat
    | LockRoom
)

INPUT_MESSAGES: list[InputMessage] = [
    SelectCell(row=1, column=1, direction=Direction.DOWN),
    EditLetter(row=1, column=0, letter="T"),
    Erase(row=1, column=0),
    PencilEdit(row=1, column=0, letter="T"),
    ConfirmPencil(row=1, column=0),
    Undo(),
    Check(target=GridTarget()),
    Reveal(target=CellTarget(row=1, column=0)),
    Vote(vote_id=1, yes=True),
    Flag(clue=None),
    Chat(text="bonjour"),
    LockRoom(locked=True),
]


@pytest.mark.parametrize("message", INPUT_MESSAGES, ids=lambda m: m.type)
def test_ac1_any_other_message_is_input_and_reactivates_before_its_own_effect(
    fx01_grid: Grid, message: InputMessage
) -> None:
    idle = idle_room(fx01_grid)

    outcome = handle_message(idle, "p1", message, NOW + 130)

    events = events_of(outcome.entries)
    assert events[:1] == [state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)]
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130


def test_ac1_an_input_from_an_active_player_adds_no_entry_and_restarts_the_count(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 1)

    moved = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 50
    )

    assert moved.entries == ()
    assert player_of(moved.state, "p1").last_input_at == NOW + 50
    assert tick(moved.state, NOW + 169.9, QUIET_CONFIG).entries == ()
    late = tick(moved.state, NOW + 170, QUIET_CONFIG)
    assert events_of(late.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_a_resumed_player_starts_active_with_a_fresh_last_input(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)
    away = disconnect_player(idle, "p1", NOW + 130).state

    outcome = join_room(
        away,
        Join(nickname="Ana", resume_token=token_of(1)),
        NOW + 200,
        "new-id",
        "new-token-0000000000",
        QUIET_CONFIG,
    )

    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 200


def test_ac1_a_resumed_idle_player_starts_active_with_an_entry(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)

    outcome = join_room(
        idle,
        Join(nickname="Ana", resume_token=token_of(1)),
        NOW + 130,
        "new-id",
        "new-token-0000000000",
        QUIET_CONFIG,
    )

    assert events_of(outcome.entries) == [
        state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)
    ]
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130
    assert player_of(outcome.state, "p2").state is PlayerState.IDLE
    snapshots = [m for m in outcome.reply if isinstance(m, Snapshot)]
    assert len(snapshots) == 1
    views = {view.player_id: view for view in snapshots[0].players}
    assert views["p1"].state is PlayerState.ACTIVE
    assert views["p2"].state is PlayerState.IDLE


# ---- AC-1: the idle state through the real WebSocket -------------------------


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


def has_state_change(peer: Peer, player_id: str, state: PlayerState) -> bool:
    for message in peer.messages():
        if not isinstance(message, PlayerStateChanged):
            continue
        if message.player_id == player_id and message.state == state:
            return True
    return False


def selection_events(peer: Peer) -> list[SelectionMoved]:
    found: list[SelectionMoved] = []
    for message in peer.events():
        if isinstance(message, SelectionMoved):
            found.append(message)
    return found


def error_events(peer: Peer) -> list[ErrorMessage]:
    found: list[ErrorMessage] = []
    for message in peer.events():
        if isinstance(message, ErrorMessage):
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


def test_ac1_websocket_idle_after_120_seconds_then_active_on_the_next_selection(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    selection = Selection(row=2, column=2, direction=Direction.ACROSS)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you

        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.IDLE),
            "B idle on A",
            WS_DETECTION_SECONDS,
        )
        peer_a.send(SelectCell(row=2, column=2, direction=Direction.ACROSS))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")

        assert peer_b.events() == [
            state_event(3, a_id, PlayerState.IDLE),
            state_event(4, b_id, PlayerState.IDLE),
            state_event(5, a_id, PlayerState.ACTIVE),
            SelectionMoved(player_id=a_id, selection=selection),
        ]
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []
        assert has_state_change(peer_a, a_id, PlayerState.ACTIVE)


def test_ac1_websocket_nothing_changes_before_120_seconds(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you

        fake_clock.advance(119)
        time.sleep(SETTLE_SECONDS)
        assert peer_b.events() == []

        fake_clock.advance(1)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )


def test_ac1_websocket_a_ping_does_not_wake_an_idle_player(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )

        ping_and_wait(peer_a)
        time.sleep(SETTLE_SECONDS)

        assert not has_state_change(peer_b, a_id, PlayerState.ACTIVE)
        assert not has_state_change(peer_a, a_id, PlayerState.ACTIVE)


def open_resumed_peer(
    stack: contextlib.ExitStack, client: TestClient, code: str, token: str
) -> Peer:
    """Open a new socket that resumes with `token`; return once its snapshot came."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    peer = Peer(websocket)
    peer.send(Join(nickname="Ana", resume_token=token))
    peer.wait_until(
        lambda: any(isinstance(m, Snapshot) for m in peer.messages()),
        "the snapshot of the resumed player",
    )
    return peer


def test_ac1_websocket_a_resumed_idle_player_is_active_on_a_new_socket(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as resumed_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )
        fake_clock.advance(10)

        resumed = open_resumed_peer(resumed_stack, client, code, a_token)

        assert resumed.snapshot().you == a_id
        views = {view.player_id: view for view in resumed.snapshot().players}
        assert views[a_id].state is PlayerState.ACTIVE
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.ACTIVE),
            "A active again on B",
            WS_DETECTION_SECONDS,
        )
        state = registry.room_state(code)
        assert state is not None
        player = player_of(state, a_id)
        assert player.state is PlayerState.ACTIVE
        assert player.last_input_at == fake_clock.now


# ---- AC-1: the roster in the browser -------------------------------------------


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
        if parse_client_message(text) == Ping():
            self.routes[0].send(Pong().model_dump_json())

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


def three_states_players() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1, state=PlayerState.IDLE),
        player_view("p3", "Cleo", 2, state=PlayerState.DISCONNECTED),
    ]


def test_ac1_browser_the_roster_shows_colour_and_state_of_each_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, three_states_players())

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)
    expected = [
        ("p1", "0", "active", "actif"),
        ("p2", "1", "idle", "inactif"),
        ("p3", "2", "disconnected", "déconnecté"),
    ]
    for position, (player_id, colour, state, text) in enumerate(expected):
        item = items.nth(position)
        expect(item).to_have_attribute("data-player-id", player_id)
        expect(item).to_have_attribute("data-colour", colour)
        expect(item).to_have_attribute("data-state", state)
        expect(item.get_by_test_id("roster-state")).to_have_text(text)


def test_ac1_browser_the_state_texts_come_from_fr_json(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    open_room(page, live_server, fx01_grid, three_states_players())

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items.nth(0).get_by_test_id("roster-state")).to_have_text(
        fr["presence.active"]
    )
    expect(items.nth(1).get_by_test_id("roster-state")).to_have_text(
        fr["presence.idle"]
    )
    expect(items.nth(2).get_by_test_id("roster-state")).to_have_text(
        fr["presence.disconnected"]
    )


def test_ac1_browser_the_three_colours_differ_on_screen(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, three_states_players())
    expect(page.get_by_test_id("roster-player")).to_have_count(3)

    backgrounds = [swatch_colour(page, player) for player in ["p1", "p2", "p3"]]

    assert "rgba(0, 0, 0, 0)" not in backgrounds
    assert len(set(backgrounds)) == 3


def test_ac1_browser_a_state_change_updates_the_item_of_that_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_states_players())
    item = roster_item(page, "p2")
    expect(item).to_have_attribute("data-state", "idle")

    mock.send(state_frame(4, "p2", PlayerState.ACTIVE))

    expect(item).to_have_attribute("data-state", "active")
    expect(item.get_by_test_id("roster-state")).to_have_text("actif")
    expect(roster_item(page, "p1")).to_have_attribute("data-state", "active")
    expect(roster_item(page, "p3")).to_have_attribute("data-state", "disconnected")

    mock.send(state_frame(5, "p1", PlayerState.IDLE))

    first = roster_item(page, "p1")
    expect(first).to_have_attribute("data-state", "idle")
    expect(first.get_by_test_id("roster-state")).to_have_text("inactif")
    expect(item).to_have_attribute("data-state", "active")


def test_ac1_browser_the_items_keep_the_join_order_after_a_change(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_states_players())

    mock.send(state_frame(4, "p3", PlayerState.ACTIVE))

    expect(roster_item(page, "p3")).to_have_attribute("data-state", "active")
    items = page.get_by_test_id("roster-player")
    expect(items.nth(0)).to_have_attribute("data-player-id", "p1")
    expect(items.nth(1)).to_have_attribute("data-player-id", "p2")
    expect(items.nth(2)).to_have_attribute("data-player-id", "p3")


def test_ac1_fr_json_has_the_presence_texts() -> None:
    fr = load_fr()

    assert fr["presence.active"] == "actif"
    assert fr["presence.idle"] == "inactif"
    assert fr["presence.disconnected"] == "déconnecté"


# ---- AC-2: selections, rules -----------------------------------------------------


@pytest.mark.parametrize(
    ("row", "column"),
    [(0, 0), (0, 2), (0, 3), (2, 0), (4, 0), (5, 1), (1, 5), (50, 50)],
    ids=[
        "clue_00",
        "clue_02",
        "clue_03",
        "clue_20",
        "clue_40",
        "below",
        "right",
        "far",
    ],
)
def test_ac2_a_selection_outside_the_letter_cells_is_refused(
    fx01_grid: Grid, row: int, column: int
) -> None:
    room = room_of_players(fx01_grid, 2)
    first = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.DOWN), NOW + 1
    )
    kept = Selection(row=1, column=1, direction=Direction.DOWN)

    outcome = handle_message(
        first.state,
        "p1",
        SelectCell(row=row, column=column, direction=Direction.ACROSS),
        NOW + 2,
    )

    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, ErrorMessage)
    assert reply.code is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.to_others == ()
    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").selection == kept


@pytest.mark.parametrize("direction", [Direction.ACROSS, Direction.DOWN])
@pytest.mark.parametrize(("row", "column"), [(0, 1), (1, 0), (2, 2), (4, 4)])
def test_ac2_a_selection_on_a_letter_cell_is_stored_and_relayed(
    fx01_grid: Grid, row: int, column: int, direction: Direction
) -> None:
    room = room_of_players(fx01_grid, 2)
    selection = Selection(row=row, column=column, direction=direction)

    outcome = handle_message(
        room, "p1", SelectCell(row=row, column=column, direction=direction), NOW + 1
    )

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    assert player_of(outcome.state, "p1").selection == selection
    assert player_of(outcome.state, "p2").selection is None
    assert outcome.state.seq == room.seq


def test_ac2_a_selection_equal_to_the_current_one_is_relayed_again(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    message = SelectCell(row=3, column=3, direction=Direction.DOWN)
    selection = Selection(row=3, column=3, direction=Direction.DOWN)
    first = handle_message(room, "p1", message, NOW + 1)

    second = handle_message(first.state, "p1", message, NOW + 2)

    assert second.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    assert player_of(second.state, "p1").selection == selection


def test_ac2_a_later_selection_replaces_the_earlier_one(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)
    first = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 1
    )

    second = handle_message(
        first.state,
        "p1",
        SelectCell(row=4, column=4, direction=Direction.DOWN),
        NOW + 2,
    )

    expected = Selection(row=4, column=4, direction=Direction.DOWN)
    assert player_of(second.state, "p1").selection == expected


def test_ac2_the_snapshot_carries_the_selections_of_the_others(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW + 1
    )

    snapshot = snapshot_for(moved.state, "p2")

    views = {view.player_id: view for view in snapshot.players}
    assert views["p1"].selection == Selection(row=2, column=3, direction=Direction.DOWN)
    assert views["p2"].selection is None


def test_ac2_disconnecting_clears_the_selection_and_relays_the_clearing(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW + 1
    )

    outcome = disconnect_player(moved.state, "p1", NOW + 5)

    assert events_of(outcome.entries) == [
        state_event(moved.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=None),)
    player = player_of(outcome.state, "p1")
    assert player.selection is None
    assert player.state is PlayerState.DISCONNECTED


def test_ac2_disconnecting_without_a_selection_relays_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = disconnect_player(room, "p1", NOW + 5)

    assert events_of(outcome.entries) == [
        state_event(3, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == ()


def test_ac2_an_idle_player_keeps_their_selection(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=2, direction=Direction.ACROSS), NOW
    )

    outcome = tick(moved.state, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]
    assert outcome.to_others == ()
    assert player_of(outcome.state, "p1").selection == Selection(
        row=2, column=2, direction=Direction.ACROSS
    )


def test_ac2_a_tick_disconnecting_a_silent_player_clears_and_relays_the_selection(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW
    )
    awake = handle_message(moved.state, "p2", Ping(), NOW + 3)

    outcome = tick(awake.state, NOW + 6, config)

    assert events_of(outcome.entries) == [
        state_event(awake.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=None),)
    silent = player_of(outcome.state, "p1")
    assert silent.state is PlayerState.DISCONNECTED
    assert silent.selection is None
    assert player_of(outcome.state, "p2").state is PlayerState.ACTIVE


def test_ac2_a_tick_disconnecting_a_silent_player_without_selection_relays_nothing(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
    room = room_of_players(fx01_grid, 2)
    awake = handle_message(room, "p2", Ping(), NOW + 3)

    outcome = tick(awake.state, NOW + 6, config)

    assert events_of(outcome.entries) == [
        state_event(awake.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == ()


# ---- AC-2: selections through the real WebSocket -------------------------------------


def test_ac2_websocket_100_selections_are_relayed_to_the_other_player_only(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    cells = letter_cells_of_fx01()
    generator = random.Random(13)
    relay_seconds: list[float] = []
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        sent: list[Selection] = []

        for number in range(1, RELAY_SAMPLES + 1):
            row, column = generator.choice(cells)
            direction = generator.choice([Direction.ACROSS, Direction.DOWN])
            sent.append(Selection(row=row, column=column, direction=direction))
            started = time.monotonic()
            peer_a.send(SelectCell(row=row, column=column, direction=direction))
            peer_b.wait_until(
                lambda target=number: len(selection_events(peer_b)) >= target,
                f"selection number {number} on B",
            )
            relay_seconds.append(time.monotonic() - started)

        received = selection_events(peer_b)
        expected = [SelectionMoved(player_id=a_id, selection=s) for s in sent]
        assert received == expected
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []
    ordered = sorted(relay_seconds)
    percentile_95 = ordered[math.ceil(0.95 * RELAY_SAMPLES) - 1]
    assert percentile_95 <= RELAY_P95_SECONDS


def test_ac2_websocket_a_selection_on_a_clue_cell_is_refused_and_not_relayed(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        peer_a.send(SelectCell(row=0, column=0, direction=Direction.ACROSS))
        peer_a.wait_until(lambda: len(error_events(peer_a)) == 1, "A's refusal")

        assert error_events(peer_a)[0].code is ErrorCode.NOT_A_LETTER_CELL
        time.sleep(SETTLE_SECONDS)
        assert peer_b.events() == []
        assert selection_events(peer_a) == []


def test_ac2_websocket_a_joiner_sees_the_current_selections_and_a_leaver_clears_it(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    selection = Selection(row=3, column=2, direction=Direction.DOWN)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as c_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        peer_a.send(SelectCell(row=3, column=2, direction=Direction.DOWN))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")

        peer_c = open_peer(c_stack, client, code, "Cleo")
        views = {view.player_id: view for view in peer_c.snapshot().players}
        assert views[a_id].selection == selection
        assert views[a_id].state is PlayerState.ACTIVE

        a_stack.close()
        peer_b.wait_until(
            lambda: len(selection_events(peer_b)) == 2, "the clearing of A's selection"
        )

        tail = peer_b.events()[-2:]
        assert tail == [
            PlayerStateChanged(seq=4, player_id=a_id, state=PlayerState.DISCONNECTED),
            SelectionMoved(player_id=a_id, selection=None),
        ]
        peer_d_stack = contextlib.ExitStack()
        with peer_d_stack:
            peer_d = open_peer(peer_d_stack, client, code, "Dan")
            view_of_a = {v.player_id: v for v in peer_d.snapshot().players}[a_id]
            assert view_of_a.selection is None
            assert view_of_a.state is PlayerState.DISCONNECTED


def test_ac2_websocket_a_silent_player_has_their_selection_cleared_for_the_others(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, config) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        peer_a.send(SelectCell(row=3, column=2, direction=Direction.DOWN))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")
        fake_clock.advance(3)
        ping_and_wait(peer_b)

        fake_clock.advance(3)

        peer_b.wait_until(
            lambda: len(selection_events(peer_b)) == 2,
            "the clearing of A's selection",
            WS_DETECTION_SECONDS,
        )
        tail = peer_b.events()[-2:]
        assert tail == [
            PlayerStateChanged(seq=3, player_id=a_id, state=PlayerState.DISCONNECTED),
            SelectionMoved(player_id=a_id, selection=None),
        ]
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []


# ---- AC-2, AC-3, AC-4: selections in the browser ----


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


def border_of(locator: Locator) -> tuple[str, str, float]:
    """The top border (style, colour, width in px) of an element."""
    script = (
        "el => { const s = getComputedStyle(el);"
        " return [s.borderTopStyle, s.borderTopColor, s.borderTopWidth]; }"
    )
    style, colour, width = locator.evaluate(script)
    return style, colour, float(width.removesuffix("px"))


def start_outline_log(page: Page, selector: str) -> None:
    """Record in the page the time at which `selector` first matches an element."""
    page.evaluate(
        """selector => {
            window.__outlineDrawnAt = null;
            const observer = new MutationObserver(() => {
                const drawn = document.querySelector(selector) !== null;
                if (drawn && window.__outlineDrawnAt === null) {
                    window.__outlineDrawnAt = performance.now();
                }
            });
            observer.observe(document.body, { subtree: true, childList: true });
        }""",
        selector,
    )


def test_ac2_browser_the_outline_appears_within_300_ms_of_the_move(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    selector = (
        '[data-testid="cell"][data-row="2"][data-column="2"] '
        '[data-testid="remote-selection"]'
    )
    expect(page.locator(selector)).to_have_count(0)
    start_outline_log(page, selector)
    sent_at = float(page.evaluate("() => performance.now()"))

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))

    expect(page.locator(selector)).to_have_count(1, timeout=WAIT_TIMEOUT_MS)
    drawn_at = page.evaluate("() => window.__outlineDrawnAt")
    assert drawn_at is not None
    assert float(drawn_at) - sent_at <= DRAW_BUDGET_MS


def test_ac2_browser_the_selection_of_another_player_is_outlined_and_tinted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))

    outline = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p2")
    expect(outline).to_have_attribute("data-colour", "3")
    style, colour, width = border_of(outline)
    assert style == "dashed"
    assert width >= 2
    assert colour == swatch_colour(page, "p2")
    assert all_remote_selections(page) == 1
    expect(cell_at(page, 2, 4)).to_have_attribute("data-tinted-by", "p2")
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))
    assert background_of(cell_at(page, 2, 1)) != background_of(cell_at(page, 1, 1))


def test_ac2_browser_the_outline_colour_is_the_colour_of_that_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True),
            player_view("p2", "Bob", 1),
            player_view("p3", "Cleo", 5),
        ],
    )

    mock.send(selection_frame("p3", 4, 4, Direction.ACROSS))

    outline = cell_at(page, 4, 4).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p3")
    expect(outline).to_have_attribute("data-colour", "5")
    assert border_of(outline)[1] == swatch_colour(page, "p3")
    assert border_of(outline)[1] != swatch_colour(page, "p2")


def test_ac2_browser_the_tint_follows_the_direction_of_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )

    mock.send(selection_frame("p2", 4, 4, Direction.DOWN))

    expect(cell_at(page, 1, 4)).to_have_attribute("data-tinted-by", "p2")
    column_4_word = [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(column_4_word, "p2"))
    assert remote_players_on(page, 4, 4) == [("p2", "1")]
    assert all_remote_selections(page) == 1


def test_ac2_browser_a_null_selection_removes_the_outline_and_the_tint(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(clear_frame("p2"))

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})


def test_ac2_browser_a_new_selection_moves_the_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(selection_frame("p2", 3, 3, Direction.ACROSS))

    expect(cell_at(page, 3, 3).get_by_test_id("remote-selection")).to_have_count(1)
    expect(page.get_by_test_id("remote-selection")).to_have_count(1)
    row_3_word = [(3, 1), (3, 2), (3, 3), (3, 4)]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(row_3_word, "p2"))


def test_ac2_browser_the_same_selection_sent_again_draws_the_same_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    settle(page)

    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert all_remote_selections(page) == 1
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_the_selections_of_the_snapshot_are_drawn(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    selection = Selection(row=2, column=2, direction=Direction.ACROSS)
    open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True),
            player_view("p2", "Bob", 3, selection=selection),
        ],
    )

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)
    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_an_idle_player_keeps_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(state_frame(4, "p2", PlayerState.IDLE))

    expect(roster_item(page, "p2")).to_have_attribute("data-state", "idle")
    settle(page)
    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_a_disconnected_player_loses_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(state_frame(4, "p2", PlayerState.DISCONNECTED))

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})


def test_ac2_browser_a_player_who_leaves_loses_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    left = PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.LEFT)
    mock.send(left.model_dump_json())

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})


# ---- AC-3: two outlines on one cell ------------------------------------------------


def three_player_snapshot() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1),
        player_view("p3", "Cleo", 2),
    ]


def open_shared_cell(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Open a room where `p2` (across) and `p3` (down) select (1, 1)."""
    mock = open_room(page, base_url, grid, three_player_snapshot())
    mock.send(selection_frame("p2", 1, 1, Direction.ACROSS))
    mock.send(selection_frame("p3", 1, 1, Direction.DOWN))
    expect(cell_at(page, 1, 1).get_by_test_id("remote-selection")).to_have_count(2)
    return mock


def test_ac3_browser_two_outlines_on_one_cell_are_both_visible_and_distinct(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]
    outlines = cell_at(page, 1, 1).get_by_test_id("remote-selection")
    first = outlines.nth(0)
    second = outlines.nth(1)
    expect(first).to_be_visible()
    expect(second).to_be_visible()
    first_box = first.bounding_box()
    second_box = second.bounding_box()
    assert first_box is not None
    assert second_box is not None
    assert first_box != second_box
    first_style, first_colour, _ = border_of(first)
    second_style, second_colour, _ = border_of(second)
    assert first_style == "dashed"
    assert second_style == "dashed"
    assert first_colour != second_colour
    assert first_colour == swatch_colour(page, "p2")
    assert second_colour == swatch_colour(page, "p3")


def test_ac3_browser_the_cell_lists_both_players_in_roster_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p2 p3")
    row_1 = {(1, 0): "p2", (1, 2): "p2", (1, 3): "p2", (1, 4): "p2"}
    column_1 = {(0, 1): "p3", (2, 1): "p3", (3, 1): "p3", (4, 1): "p3"}
    expected = {**row_1, **column_1, (1, 1): "p2 p3"}
    assert tinted_by_map(page) == expected_tints(expected)


def test_ac3_browser_the_overlapping_tint_is_the_one_of_the_first_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)

    shared = background_of(cell_at(page, 1, 1))
    only_first = background_of(cell_at(page, 1, 0))
    only_second = background_of(cell_at(page, 0, 1))
    assert shared == only_first
    assert only_first != only_second


def test_ac3_browser_the_order_follows_the_roster_not_the_order_of_arrival(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_player_snapshot())

    mock.send(selection_frame("p3", 1, 1, Direction.DOWN))
    mock.send(selection_frame("p2", 1, 1, Direction.ACROSS))

    expect(cell_at(page, 1, 1).get_by_test_id("remote-selection")).to_have_count(2)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p2 p3")
    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]


def test_ac3_browser_the_outlines_stay_when_i_select_the_same_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_shared_cell(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 1)

    cell.click(timeout=WAIT_TIMEOUT_MS)

    expect(cell).to_have_attribute("data-selected", "true")
    assert remote_players_on(page, 1, 1) == [("p2", "1"), ("p3", "2")]
    outlines = cell.get_by_test_id("remote-selection")
    expect(outlines.nth(0)).to_be_visible()
    expect(outlines.nth(1)).to_be_visible()
    first_box = outlines.nth(0).bounding_box()
    second_box = outlines.nth(1).bounding_box()
    assert first_box is not None
    assert second_box is not None
    assert first_box != second_box
    expect(cell).to_have_attribute("data-tinted-by", "p2 p3")


def test_ac3_browser_one_player_leaving_leaves_the_other_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_shared_cell(page, live_server, fx01_grid)

    mock.send(clear_frame("p2"))

    outline = cell_at(page, 1, 1).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p3")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-tinted-by", "p3")


# ---- AC-4: my selection looks different ----------------------------------------------


def border_styles_in(cell: Locator) -> list[str]:
    """The four border styles of a cell and of each of its descendants."""
    script = (
        "el => [el, ...el.querySelectorAll('*')].flatMap(e => {"
        " const s = getComputedStyle(e);"
        " return [s.borderTopStyle, s.borderRightStyle,"
        " s.borderBottomStyle, s.borderLeftStyle]; })"
    )
    styles = cell.evaluate(script)
    assert isinstance(styles, list)
    return styles


def open_with_p2_on_2_2(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    mock = open_room(
        page,
        base_url,
        grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)
    return mock


def test_ac4_browser_my_cell_is_selected_and_has_no_remote_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)

    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)

    mine = cell_at(page, 3, 1)
    expect(mine).to_have_attribute("data-selected", "true")
    expect(mine.get_by_test_id("remote-selection")).to_have_count(0)
    expect(
        page.locator('[data-testid="remote-selection"][data-player-id="p1"]')
    ).to_have_count(0)
    assert remote_players_on(page, 2, 2) == [("p2", "1")]


def test_ac4_browser_my_selection_is_never_dashed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    mine = cell_at(page, 3, 1)
    expect(mine).to_have_attribute("data-selected", "true")

    styles = border_styles_in(mine)

    assert styles != []
    assert "dashed" not in styles
    theirs = border_of(cell_at(page, 2, 2).get_by_test_id("remote-selection"))
    assert theirs[0] == "dashed"


def test_ac4_browser_my_background_differs_from_the_others(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_with_p2_on_2_2(page, live_server, fx01_grid)
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    expect(cell_at(page, 3, 1)).to_have_attribute("data-selected", "true")
    expect(cell_at(page, 2, 3)).to_have_attribute("data-tinted-by", "p2")

    mine = background_of(cell_at(page, 3, 1))

    assert mine != background_of(cell_at(page, 2, 2))
    assert mine != background_of(cell_at(page, 2, 3))


def test_ac4_browser_the_page_never_draws_an_outline_for_me(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_with_p2_on_2_2(page, live_server, fx01_grid)

    mock.send(selection_frame("p1", 4, 4, Direction.ACROSS))
    settle(page)

    expect(
        page.locator('[data-testid="remote-selection"][data-player-id="p1"]')
    ).to_have_count(0)
    assert all_remote_selections(page) == 1
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac4_browser_a_selection_of_mine_in_the_snapshot_draws_no_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mine = Selection(row=4, column=4, direction=Direction.ACROSS)
    open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True, selection=mine),
            player_view("p2", "Bob", 1),
        ],
    )

    settle(page)

    assert all_remote_selections(page) == 0
    assert tinted_by_map(page) == expected_tints({})


def test_ac4_browser_a_cell_of_my_word_keeps_my_highlight_when_also_tinted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )
    cell_at(page, 3, 1).click(timeout=WAIT_TIMEOUT_MS)
    expect(cell_at(page, 3, 1)).to_have_attribute("data-selected", "true")

    mock.send(selection_frame("p2", 4, 2, Direction.DOWN))

    shared = cell_at(page, 3, 2)
    own_only = cell_at(page, 3, 3)
    expect(shared).to_have_attribute("data-tinted-by", "p2")
    expect(shared).to_have_attribute("data-in-word", "true")
    expect(own_only).to_have_attribute("data-in-word", "true")
    expect(own_only).to_have_attribute("data-tinted-by", "")
    assert background_of(shared) == background_of(own_only)


# ---- AC-5: the activity feed ----


def feed_snapshot_players() -> list[PlayerView]:
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)]


def joined_frame(seq: int, player_id: str, nickname: str, colour: int) -> str:
    event = PlayerJoined(seq=seq, player=player_view(player_id, nickname, colour))
    return event.model_dump_json()


def left_frame(seq: int, player_id: str, reason: LeaveReason) -> str:
    return PlayerLeft(seq=seq, player_id=player_id, reason=reason).model_dump_json()


def check_frame(
    seq: int, player_id: str, target: CellTarget | GridTarget | WordTarget
) -> str:
    event = CheckResult(
        seq=seq, player_id=player_id, target=target, correct=(), wrong=()
    )
    return event.model_dump_json()


def reveal_frame(seq: int, player_id: str, target: CellTarget | WordTarget) -> str:
    event = RevealResult(
        seq=seq,
        player_id=player_id,
        target=target,
        reveal_budget=RevealBudget(letters=4, words=1),
    )
    return event.model_dump_json()


def flag_frame(seq: int, player_id: str, clue: ClueRef | None) -> str:
    return FlagChanged(seq=seq, player_id=player_id, clue=clue).model_dump_json()


def settings_frame(
    seq: int,
    player_id: str,
    help_mode: HelpMode,
    letters: int,
    words: int,
    locked: bool,
) -> str:
    settings = RoomSettings(
        help_mode=help_mode,
        reveal_budget=RevealBudget(letters=letters, words=words),
        locked=locked,
    )
    event = SettingsChanged(
        seq=seq,
        player_id=player_id,
        settings=settings,
        reveal_budget=RevealBudget(letters=0, words=0),
    )
    return event.model_dump_json()


def host_frame(seq: int, player_id: str) -> str:
    return HostChanged(seq=seq, player_id=player_id).model_dump_json()


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


NONE_SETTINGS_TEXT = (
    "Ana a modifié les réglages : aide désactivée, 3 lettres et 2 mots à révéler"
)

SPEC_EXAMPLE_ITEMS = [
    ("player_joined", "6", "Cy a rejoint le salon"),
    ("check", "7", "Bob a vérifié un mot"),
    ("reveal", "8", "Cy a révélé une lettre"),
    ("flag", "9", "Bob bloque sur « Fatales à César »"),
    (
        "settings_changed",
        "10",
        "Ana a modifié les réglages : aide par vote, 5 lettres et 1 mots à révéler",
    ),
    ("room_locked", "11", "Ana a verrouillé le salon"),
    ("player_removed", "12", "Cy a été retiré du salon"),
]


def spec_example_frames() -> list[str]:
    return [
        joined_frame(6, "p3", "Cy", 2),
        check_frame(7, "p2", WordTarget(row=0, column=3, clue_index=0)),
        reveal_frame(8, "p3", CellTarget(row=1, column=0)),
        flag_frame(9, "p2", CLUE_FATALES),
        settings_frame(10, "p1", HelpMode.VOTE, 5, 1, False),
        settings_frame(11, "p1", HelpMode.VOTE, 5, 1, True),
        left_frame(12, "p3", LeaveReason.REMOVED),
    ]


def test_ac5_browser_the_feed_lists_the_events_of_the_spec_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    expect(page.get_by_test_id("activity-feed")).to_be_visible()
    assert feed_items(page) == []

    for frame in spec_example_frames():
        mock.send(frame)

    expect(feed_locator(page)).to_have_count(7)
    assert feed_items(page) == SPEC_EXAMPLE_ITEMS


def test_ac5_browser_events_sent_out_of_order_are_listed_by_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    frames = spec_example_frames()
    sending_order = [0, 1, 3, 2, 4, 6, 5]

    for index in sending_order:
        mock.send(frames[index])

    expect(feed_locator(page)).to_have_count(7)
    assert feed_items(page) == SPEC_EXAMPLE_ITEMS


def test_ac5_browser_the_feed_has_its_heading_and_no_item_from_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    feed = page.get_by_test_id("activity-feed")
    expect(feed).to_contain_text("Activité")
    expect(feed).to_contain_text(load_fr()["feed.heading"])
    expect(feed_locator(page)).to_have_count(0)
    settle(page)
    assert feed_items(page) == []


def test_ac5_browser_the_other_kinds_of_departure_check_reveal_and_settings(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    frames = [
        joined_frame(6, "p3", "Cy", 2),
        left_frame(7, "p3", LeaveReason.LEFT),
        check_frame(8, "p3", GridTarget()),
        left_frame(9, "p2", LeaveReason.TIMED_OUT),
        reveal_frame(10, "p1", WordTarget(row=0, column=0, clue_index=1)),
        flag_frame(11, "p1", CLUE_MARINE),
        settings_frame(12, "p1", HelpMode.FREE, 5, 1, True),
        settings_frame(13, "p1", HelpMode.FREE, 5, 1, False),
        settings_frame(14, "p1", HelpMode.NONE, 3, 2, False),
        settings_frame(15, "p1", HelpMode.NONE, 3, 2, False),
        settings_frame(16, "p1", HelpMode.FREE, 3, 2, True),
        host_frame(17, "p1"),
        check_frame(18, "p1", CellTarget(row=1, column=0)),
    ]

    for frame in frames:
        mock.send(frame)

    expect(feed_locator(page)).to_have_count(13)
    assert feed_items(page) == [
        ("player_joined", "6", "Cy a rejoint le salon"),
        ("player_left", "7", "Cy a quitté le salon"),
        ("check", "8", "Cy a vérifié la grille"),
        ("player_timed_out", "9", "Bob est parti (déconnecté trop longtemps)"),
        ("reveal", "10", "Ana a révélé un mot"),
        ("flag", "11", "Ana bloque sur « De la marine »"),
        ("room_locked", "12", "Ana a verrouillé le salon"),
        ("room_unlocked", "13", "Ana a déverrouillé le salon"),
        (
            "settings_changed",
            "14",
            NONE_SETTINGS_TEXT,
        ),
        (
            "settings_changed",
            "15",
            NONE_SETTINGS_TEXT,
        ),
        (
            "settings_changed",
            "16",
            "Ana a modifié les réglages : aide libre, 3 lettres et 2 mots à révéler",
        ),
        ("host_changed", "17", "Ana est maintenant l'hôte"),
        ("check", "18", "Ana a vérifié une lettre"),
    ]


def test_ac5_browser_the_settings_are_compared_with_the_snapshot_settings(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    locked_settings = RoomSettings(
        help_mode=HelpMode.FREE,
        reveal_budget=RevealBudget(letters=5, words=1),
        locked=True,
    )
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        feed_snapshot_players(),
        seq=5,
        settings=locked_settings,
    )

    mock.send(settings_frame(6, "p1", HelpMode.FREE, 5, 1, False))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("room_unlocked", "6", "Ana a déverrouillé le salon")]


def test_ac5_browser_events_without_a_line_add_no_item(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)
    silent_frames = [
        LetterChanged(
            seq=6, row=1, column=0, letter="T", pencil=False, player_id="p2"
        ).model_dump_json(),
        CellLocked(
            seq=7, row=1, column=0, letter="T", revealed=False
        ).model_dump_json(),
        state_frame(8, "p2", PlayerState.IDLE),
        flag_frame(9, "p2", None),
    ]

    for frame in silent_frames:
        mock.send(frame)
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    mock.send(check_frame(10, "p2", GridTarget()))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("check", "10", "Bob a vérifié la grille")]


def test_ac5_browser_an_unknown_player_is_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(check_frame(6, "p9", WordTarget(row=0, column=3, clue_index=0)))
    mock.send(left_frame(7, "p9", LeaveReason.TIMED_OUT))
    mock.send(check_frame(8, "p2", GridTarget()))

    expect(feed_locator(page)).to_have_count(3)
    assert feed_items(page) == [
        ("check", "6", "Quelqu'un a vérifié un mot"),
        ("player_timed_out", "7", "Quelqu'un est parti (déconnecté trop longtemps)"),
        ("check", "8", "Bob a vérifié la grille"),
    ]


def test_ac5_browser_the_feed_keeps_the_last_100_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    for seq in range(6, 6 + FEED_LIMIT):
        mock.send(check_frame(seq, "p2", GridTarget()))
    expect(feed_locator(page)).to_have_count(FEED_LIMIT)
    assert feed_items(page)[0][1] == "6"

    mock.send(check_frame(6 + FEED_LIMIT, "p2", GridTarget()))

    last_seq = 6 + FEED_LIMIT
    expect(feed_locator(page).last).to_have_attribute("data-seq", str(last_seq))
    items = feed_items(page)
    assert len(items) == FEED_LIMIT
    seqs = [int(seq) for _, seq, _ in items]
    assert seqs == list(range(7, last_seq + 1))


def test_ac5_browser_a_departed_player_keeps_their_nickname_in_later_items(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(joined_frame(6, "p3", "Cy", 2))
    mock.send(left_frame(7, "p3", LeaveReason.REMOVED))
    mock.send(reveal_frame(8, "p3", CellTarget(row=1, column=0)))

    expect(feed_locator(page)).to_have_count(3)
    assert feed_items(page)[1:] == [
        ("player_removed", "7", "Cy a été retiré du salon"),
        ("reveal", "8", "Cy a révélé une lettre"),
    ]


def test_ac5_browser_a_nickname_is_inserted_as_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, feed_snapshot_players(), seq=5)

    mock.send(joined_frame(6, "p3", "<b>Eve</b>", 2))

    expect(feed_locator(page)).to_have_count(1)
    assert feed_items(page) == [("player_joined", "6", "<b>Eve</b> a rejoint le salon")]
    expect(feed_locator(page).locator("b")).to_have_count(0)


def test_ac5_fr_json_has_the_feed_texts() -> None:
    fr = load_fr()

    assert fr["feed.heading"] == "Activité"
    assert fr["feed.someone"] == "Quelqu'un"
    assert fr["feed.player_joined"] == "{name} a rejoint le salon"
    assert fr["feed.player_left"] == "{name} a quitté le salon"
    assert fr["feed.player_removed"] == "{name} a été retiré du salon"
    assert fr["feed.player_timed_out"] == "{name} est parti (déconnecté trop longtemps)"
    assert fr["feed.check.letter"] == "{name} a vérifié une lettre"
    assert fr["feed.check.word"] == "{name} a vérifié un mot"
    assert fr["feed.check.grid"] == "{name} a vérifié la grille"
    assert fr["feed.reveal.letter"] == "{name} a révélé une lettre"
    assert fr["feed.reveal.word"] == "{name} a révélé un mot"
    assert fr["feed.flag"] == "{name} bloque sur « {clue} »"
    assert fr["feed.room_locked"] == "{name} a verrouillé le salon"
    assert fr["feed.room_unlocked"] == "{name} a déverrouillé le salon"
    assert fr["feed.settings_changed"] == (
        "{name} a modifié les réglages : aide {help_mode}, "
        "{letters} lettres et {words} mots à révéler"
    )
    assert fr["feed.host_changed"] == "{name} est maintenant l'hôte"
    assert fr["settings.help_mode.free"] == "libre"
    assert fr["settings.help_mode.vote"] == "par vote"
    assert fr["settings.help_mode.none"] == "désactivée"


# ---- AC-6: the roster and the feed keep the grid's room ----


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


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(
            player_view(f"p{number}", EIGHT_NICKNAMES[number - 1], number - 1)
        )
    return players


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac6_browser_the_roster_and_the_feed_keep_the_grids_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        last_seq = 5 + FEED_LIMIT
        mock = open_room(page, live_server, fx01_grid, eight_players(), seq=5)
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq, "p2", GridTarget()))
        expect(page.get_by_test_id("room-page")).to_have_attribute(
            "data-seq", str(last_seq)
        )

        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=TAP_TIMEOUT_MS)
        else:
            cell.click(timeout=TAP_TIMEOUT_MS)

        bar = page.get_by_test_id("clue-bar")
        expect(bar).to_have_attribute("data-word", "3,0,0")
        viewport = page.get_by_test_id("grid-viewport")
        viewport_box = viewport.bounding_box()
        bar_box = bar.bounding_box()
        assert viewport_box is not None
        assert bar_box is not None
        sizes = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth,"
            " document.documentElement.scrollHeight, window.innerHeight]"
        )
        scroll_width, window_width, scroll_height, window_height = sizes

        assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
        assert scroll_width <= window_width
        assert scroll_height <= window_height
        expect(viewport).to_have_attribute("data-zoom", "1")
        grid_box = page.get_by_test_id("grid").bounding_box()
        assert grid_box is not None
        assert grid_box["x"] >= viewport_box["x"] - EPSILON
        assert grid_box["y"] >= viewport_box["y"] - EPSILON
        grid_right = grid_box["x"] + grid_box["width"]
        grid_bottom = grid_box["y"] + grid_box["height"]
        assert grid_right <= viewport_box["x"] + viewport_box["width"] + EPSILON
        assert grid_bottom <= viewport_box["y"] + viewport_box["height"] + EPSILON
        assert bar_box["x"] >= -EPSILON
        assert bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        assert bar_box["y"] >= -EPSILON
        bar_bottom = bar_box["y"] + bar_box["height"]
        assert bar_bottom <= window_height + EPSILON
        if touch:
            keyboard_box = page.get_by_test_id("keyboard").bounding_box()
            assert keyboard_box is not None
            assert bar_bottom <= keyboard_box["y"] + EPSILON
            keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
            assert keyboard_bottom <= window_height + EPSILON
    finally:
        close()
