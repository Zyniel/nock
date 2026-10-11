"""Tests of spec 014: host controls (remove, lock, hand-over, settings).

The rules (`handle_message`, `join_room`, `tick`) are tested directly with exact
clock values. The hub is tested with the real WebSocket, a fake clock and
`tick_seconds=0.05`. The pages are tested twice: against the live server with two
browser contexts (the flows of the criteria), and with spec 040's mocked socket
(the exact messages the page sends, the snapshot updates, the final states and
the layout of the host's view).

Not tested here, with the reason:

- `mute_player` and `PlayerMuted`: no criterion covers them (the spec leaves the
  mute button and its effect to spec 022).
- The `disconnects` entry when the removed player has no open connection: the spec
  says the hub skips it, and does not say whether the rule still returns it.
- The seq of the entries of a refused join that also timed out the member in the
  same step: the spec does not say what a refused join leaves in the log.
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
from playwright.sync_api import Browser, Dialog, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ChangeSettings,
    CheckResult,
    ErrorCode,
    ErrorMessage,
    GridTarget,
    HelpMode,
    HostChanged,
    Join,
    LeaveReason,
    LockRoom,
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
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    tick,
)
from nock.server import create_app

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
FEED_LIMIT = 100
TAP_TIMEOUT_MS = 3000
FORM_TIMEOUT_MS = 5000
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
FORM_WATCHER = (
    "window.__formSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"nickname-form\"]')) {"
    " window.__formSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)

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


Sendable = Join | Ping | RemovePlayer | LockRoom | ChangeSettings


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


# ---- AC-1: remove a player (rules) -------------------------------------------


def test_ac1_fr_json_holds_the_removal_texts() -> None:
    fr = load_fr()

    assert fr["host.remove"] == "Retirer"
    assert fr["host.remove_label"] == "Retirer {name} du salon"
    assert fr["room.status.removed"] == "Vous avez été retiré de ce salon."


def test_ac1_removing_a_player_gives_one_player_left_removed_entry(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert outcome.state.seq == 4
    assert player_ids(outcome.state) == ["p1", "p3"]


def test_ac1_the_removed_token_is_banned_and_only_that_one(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.state.removed_tokens == (token_of(2),)


def test_ac1_the_removed_player_gets_a_disconnect_with_error_removed(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert len(outcome.disconnects) == 1
    disconnect = outcome.disconnects[0]
    assert disconnect.player_id == "p2"
    assert disconnect.close_code == 1000
    assert disconnect.error is not None
    assert disconnect.error.code is ErrorCode.REMOVED


def test_ac1_the_seat_colour_and_nickname_are_freed(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(room, new_guest("Bob"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    snapshot = sole_snapshot(outcome)
    views = {view.player_id: view for view in snapshot.players}
    assert views[NEW_PLAYER_ID].nickname == "Bob"
    assert views[NEW_PLAYER_ID].colour == 1
    assert len(snapshot.players) == 3


def test_ac1_a_full_room_has_a_seat_after_a_removal(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 8))

    outcome = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_snapshot(outcome).you == NEW_PLAYER_ID
    assert len(outcome.state.players) == 8


def test_ac1_the_letters_of_the_removed_player_stay_with_their_author(
    fx01_grid: Grid,
) -> None:
    room = with_cell(
        room_of_players(fx01_grid, 3),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=3,
            changed_by="p2",
        ),
    )

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == ("B", "p2")
    assert outcome.state.cells == room.cells


def test_ac1_a_disconnected_player_can_be_removed(fx01_grid: Grid) -> None:
    room = disconnect_player(room_of_players(fx01_grid, 3), "p2", NOW + 0.5).state

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert player_ids(outcome.state) == ["p1", "p3"]
    assert outcome.state.removed_tokens == (token_of(2),)


def test_ac1_a_player_who_is_not_host_gets_not_host_and_nothing_changes(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = handle_message(room, "p2", RemovePlayer(player_id="p3"), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_non_host_cannot_remove_the_host_either(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = handle_message(room, "p2", RemovePlayer(player_id="p1"), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert_nothing_changed(room, outcome.state)


@pytest.mark.parametrize("target", ["p1", "zz"])
def test_ac1_removing_oneself_or_an_unknown_player_is_an_invalid_target(
    fx01_grid: Grid, target: str
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id=target))

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_player_removed_twice_is_an_invalid_target_the_second_time(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_join_with_the_removed_token_is_refused_as_removed(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_join_without_a_token_after_a_removal_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(room, new_guest("Bob"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is False
    snapshot = sole_snapshot(outcome)
    assert snapshot.you == NEW_PLAYER_ID
    assert snapshot.resume_token == NEW_TOKEN
    assert player_of(outcome.state, NEW_PLAYER_ID).is_host is False


def test_ac1_a_join_with_another_token_after_a_removal_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(
        room,
        new_guest("Bob", "some-other-token-0001"),
        NOW + 2,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == NEW_PLAYER_ID


def test_ac1_removed_is_answered_before_locked_full_and_nickname(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 8))
    refilled = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)
    full_room = refilled.state
    assert len(full_room.players) == 8
    locked_full_room = locked(full_room)

    outcome = join_room(
        locked_full_room,
        new_guest("!", token_of(2)),
        NOW + 3,
        "another-player",
        "another-token-0000000",
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True
    assert outcome.entries == ()


# ---- AC-1: through the real WebSocket ----------------------------------------


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


def host_events(peer: Peer) -> list[HostChanged]:
    found: list[HostChanged] = []
    for message in peer.events():
        if isinstance(message, HostChanged):
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


def test_ac1_websocket_the_host_removes_a_player_who_is_closed_and_banned(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as c_stack,
        contextlib.ExitStack() as again_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        c_id = peer_c.snapshot().you
        b_token = peer_b.snapshot().resume_token

        peer_a.send(RemovePlayer(player_id=b_id))

        removal = PlayerLeft(seq=4, player_id=b_id, reason=LeaveReason.REMOVED)
        peer_a.wait_until(lambda: left_events(peer_a) == [removal], "A told")
        peer_c.wait_until(lambda: left_events(peer_c) == [removal], "C told")
        peer_b.wait_until(
            lambda: peer_b.close_code is not None, "the close of B's socket"
        )
        assert peer_b.close_code == 1000
        assert error_codes(peer_b) == [ErrorCode.REMOVED]
        assert room_players(registry, code) == [a_id, c_id]

        refused = open_refused_peer(again_stack, client, code, "Bob", b_token)

        assert refused.close_code == 1000
        assert len(refused.messages()) == 1
        assert error_codes(refused) == [ErrorCode.REMOVED]
        assert room_players(registry, code) == [a_id, c_id]
        state = registry.room_state(code)
        assert state is not None
        assert state.removed_tokens == (b_token,)


def test_ac1_websocket_a_new_socket_without_a_token_joins_after_a_removal(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as new_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        b_id = peer_b.snapshot().you
        peer_a.send(RemovePlayer(player_id=b_id))
        peer_b.wait_until(lambda: peer_b.close_code is not None, "B closed")

        newcomer = open_peer(new_stack, client, code, "Bob")

        assert newcomer.snapshot().you != b_id
        assert len(room_players(registry, code)) == 2


def test_ac1_websocket_a_non_host_and_bad_targets_are_refused_with_no_event(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you

        peer_b.send(RemovePlayer(player_id=a_id))
        peer_a.send(RemovePlayer(player_id=a_id))
        peer_a.send(RemovePlayer(player_id="zz"))
        ping_and_wait(peer_a)
        ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert error_codes(peer_b) == [ErrorCode.NOT_HOST]
        assert error_codes(peer_a) == [ErrorCode.INVALID_TARGET] * 2
        assert left_events(peer_a) == []
        assert left_events(peer_b) == []
        assert peer_b.close_code is None
        assert room_players(registry, code) == [a_id, b_id]


# ---- AC-2: lock the room (rules) ---------------------------------------------


def test_ac2_fr_json_holds_the_lock_texts() -> None:
    fr = load_fr()

    assert fr["host.lock"] == "Verrouiller le salon"
    assert fr["host.unlock"] == "Déverrouiller le salon"
    assert fr["room.status.locked"] == "Ce salon est verrouillé."


def test_ac2_locking_sets_the_flag_and_announces_settings_changed(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.reply == ()
    assert outcome.state.settings.locked is True
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=3,
            player_id="p1",
            settings=START_SETTINGS.model_copy(update={"locked": True}),
            reveal_budget=START_SETTINGS.reveal_budget,
        )
    ]
    assert outcome.state.seq == 3


def test_ac2_locking_again_produces_no_entry_and_no_reply(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.settings.locked is True
    assert outcome.state.seq == room.seq


def test_ac2_unlocking_announces_settings_changed_with_locked_false(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, LockRoom(locked=False))

    assert outcome.reply == ()
    assert outcome.state.settings.locked is False
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=START_SETTINGS,
            reveal_budget=START_SETTINGS.reveal_budget,
        )
    ]


def test_ac2_unlocking_an_unlocked_room_does_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, LockRoom(locked=False))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.seq == room.seq


def test_ac2_locking_keeps_the_help_mode_and_the_budget(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)
    changed = room.settings.model_copy(
        update={
            "help_mode": HelpMode.VOTE,
            "reveal_budget": RevealBudget(letters=7, words=4),
        }
    )
    room = room.model_copy(
        update={"settings": changed, "reveal_budget": RevealBudget(letters=3, words=2)}
    )

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.state.settings == changed.model_copy(update={"locked": True})
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=2)
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=changed.model_copy(update={"locked": True}),
            reveal_budget=RevealBudget(letters=3, words=2),
        )
    ]


def test_ac2_a_player_who_is_not_host_gets_not_host_on_lock_and_unlock(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    lock_attempt = handle_message(room, "p2", LockRoom(locked=True), NOW + 1)
    locked_room = locked(room)
    unlock_attempt = handle_message(locked_room, "p2", LockRoom(locked=False), NOW + 1)

    assert sole_error(lock_attempt.reply).code is ErrorCode.NOT_HOST
    assert lock_attempt.entries == ()
    assert lock_attempt.state.settings.locked is False
    assert sole_error(unlock_attempt.reply).code is ErrorCode.NOT_HOST
    assert unlock_attempt.entries == ()
    assert unlock_attempt.state.settings.locked is True


def test_ac2_a_locked_room_refuses_a_new_joiner_as_room_locked(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(room, new_guest("Zoe"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


def test_ac2_a_joiner_with_an_unknown_token_is_refused_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(
        room,
        new_guest("Zoe", "an-unknown-token-0001"),
        NOW + 2,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True


def test_ac2_a_member_resumes_in_a_locked_room(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == "p2"
    assert player_ids(outcome.state) == ["p1", "p2"]


def test_ac2_a_disconnected_member_resumes_within_the_window_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))
    room = disconnect_player(room, "p2", NOW + 10).state

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 10 + 299, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == "p2"
    assert player_of(outcome.state, "p2").state is PlayerState.ACTIVE


def test_ac2_a_member_who_timed_out_is_refused_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 3))
    room = disconnect_player(room, "p2", NOW + 10).state
    after_window = NOW + 10 + 300.5
    ticked = tick(keep_seen(room, after_window), after_window, QUIET_RULES)
    assert player_ids(ticked.state) == ["p1", "p3"]

    outcome = join_room(
        ticked.state,
        new_guest("Bob", token_of(2)),
        after_window + 1,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True
    assert player_ids(outcome.state) == ["p1", "p3"]


def test_ac2_locked_is_answered_before_full(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 8))

    outcome = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True


def test_ac2_locked_is_answered_before_the_nickname_check(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(room, new_guest("!"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED


def test_ac2_a_member_resumes_in_a_locked_full_room(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 8))

    outcome = join_room(
        room, new_guest("Hal", token_of(8)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_snapshot(outcome).you == "p8"


def test_ac2_removed_is_answered_before_locked(fx01_grid: Grid) -> None:
    room = locked(removed_bob(room_of_players(fx01_grid, 3)))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True


def test_ac2_after_unlocking_a_new_joiner_is_accepted(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))
    refused = join_room(room, new_guest("Zoe"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)
    assert sole_error(refused.reply).code is ErrorCode.ROOM_LOCKED
    unlocked = host_acts(room, LockRoom(locked=False)).state

    outcome = join_room(unlocked, new_guest("Zoe"), NOW + 3, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == NEW_PLAYER_ID


# ---- AC-2: through the real WebSocket ----------------------------------------


def test_ac2_websocket_lock_refuses_new_sockets_but_not_members(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as b_again_stack,
        contextlib.ExitStack() as refused_stack,
        contextlib.ExitStack() as joiner_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        b_token = peer_b.snapshot().resume_token

        peer_a.send(LockRoom(locked=True))

        for peer in (peer_a, peer_b):
            peer.wait_until(lambda peer=peer: len(settings_events(peer)) == 1, "lock")
            lock_event = settings_events(peer)[0]
            assert lock_event.player_id == a_id
            assert lock_event.settings.locked is True
        refused = open_refused_peer(refused_stack, client, code, "Cy")
        assert refused.close_code == 1000
        assert len(refused.messages()) == 1
        assert error_codes(refused) == [ErrorCode.ROOM_LOCKED]
        assert room_players(registry, code) == [a_id, b_id]

        b_stack.close()
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.DISCONNECTED),
            "B's disconnection",
        )
        peer_b_again = open_peer(b_again_stack, client, code, "Bob", b_token)
        assert peer_b_again.snapshot().you == b_id
        assert peer_b_again.snapshot().settings.locked is True

        peer_a.send(LockRoom(locked=True))
        ping_and_wait(peer_a)
        time.sleep(SETTLE_SECONDS)
        assert len(settings_events(peer_a)) == 1
        assert error_codes(peer_a) == []

        peer_b_again.send(LockRoom(locked=False))
        peer_b_again.wait_until(
            lambda: error_codes(peer_b_again) == [ErrorCode.NOT_HOST], "not_host"
        )
        ping_and_wait(peer_a)
        assert len(settings_events(peer_a)) == 1

        peer_a.send(LockRoom(locked=False))
        peer_a.wait_until(lambda: len(settings_events(peer_a)) == 2, "unlock on A")
        peer_b_again.wait_until(
            lambda: len(settings_events(peer_b_again)) == 1, "unlock on B"
        )
        assert settings_events(peer_a)[1].settings.locked is False
        assert settings_events(peer_b_again)[0].settings.locked is False
        joiner = open_peer(joiner_stack, client, code, "Cy")
        assert joiner.snapshot().settings.locked is False
        assert len(room_players(registry, code)) == 3


# ---- AC-3: host hand-over (rules) --------------------------------------------

LEFT_AT = NOW + 10.0


def host_gone_room(grid: Grid, count: int) -> RoomState:
    """Return `count` players where the host `p1` disconnected at LEFT_AT."""
    room = room_of_players(grid, count)
    return disconnect_player(room, "p1", LEFT_AT).state


def tick_at(room: RoomState, seconds_after: float) -> Outcome:
    """Tick `seconds_after` the host left, every connected player seen then."""
    now = LEFT_AT + seconds_after
    return tick(keep_seen(room, now), now, QUIET_RULES)


def test_ac3_fr_json_holds_the_host_label() -> None:
    assert load_fr()["roster.host"] == "hôte"


def test_ac3_exactly_60_seconds_after_the_host_left_nothing_changes(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)

    outcome = tick_at(room, 60)

    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").is_host is True
    assert player_of(outcome.state, "p2").is_host is False


def test_ac3_after_more_than_60_seconds_the_longest_present_becomes_host(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = with_player(room, "p3", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p2")]
    assert outcome.state.seq == room.seq + 1
    assert player_of(outcome.state, "p2").is_host is True
    assert player_of(outcome.state, "p1").is_host is False
    assert player_of(outcome.state, "p3").is_host is False


def test_ac3_the_delay_is_the_configured_one(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    config = RoomConfig(silence_timeout_seconds=3600, host_handover_seconds=10)
    at_limit = tick(keep_seen(room, LEFT_AT + 10), LEFT_AT + 10, config)
    after_limit = tick(keep_seen(room, LEFT_AT + 10.5), LEFT_AT + 10.5, config)

    assert at_limit.entries == ()
    assert events_of(after_limit.entries) == [
        HostChanged(seq=room.seq + 1, player_id="p2")
    ]


def test_ac3_a_host_who_is_connected_never_hands_the_role_over(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = tick(keep_seen(room, NOW + 5000), NOW + 5000, QUIET_RULES)

    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").is_host is True


def test_ac3_an_idle_player_is_a_candidate_and_the_first_joined_wins(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = with_player(room, "p2", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p2")]


def test_ac3_a_disconnected_player_is_not_a_candidate(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 4)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    room = with_player(room, "p3", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p3")]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p4").is_host is False


def test_ac3_when_every_other_player_is_disconnected_the_host_stays(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    room = disconnect_player(room, "p3", LEFT_AT + 6).state

    first = tick_at(room, 61)
    later = tick_at(first.state, 120)

    assert first.entries == ()
    assert later.entries == ()
    assert player_of(later.state, "p1").is_host is True
    assert player_of(later.state, "p2").is_host is False


def test_ac3_the_rule_is_tried_again_when_someone_comes_back(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    stuck = tick_at(room, 61)
    assert stuck.entries == ()
    back = join_room(
        stuck.state,
        new_guest("Bob", token_of(2)),
        LEFT_AT + 70,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    assert sole_snapshot(back).you == "p2"

    outcome = tick_at(back.state, 71)

    assert events_of(outcome.entries) == [
        HostChanged(seq=back.state.seq + 1, player_id="p2")
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_resume_does_not_change_who_was_there_first(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    back = join_room(
        room, new_guest("Bob", token_of(2)), LEFT_AT + 20, NEW_PLAYER_ID, NEW_TOKEN
    )
    assert sole_snapshot(back).you == "p2"

    outcome = tick_at(back.state, 61)

    assert events_of(outcome.entries) == [
        HostChanged(seq=back.state.seq + 1, player_id="p2")
    ]


def test_ac3_the_hand_over_comes_after_the_idle_step(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    now = LEFT_AT + 130
    seen = with_player(room, "p2", last_seen_at=now)

    outcome = tick(seen, now, QUIET_RULES)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=room.seq + 1, player_id="p2", state=PlayerState.IDLE),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_host_who_comes_back_after_the_hand_over_is_an_ordinary_player(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 2)
    handed = tick_at(room, 61)
    assert player_of(handed.state, "p2").is_host is True

    back = join_room(
        handed.state,
        new_guest("Ana", token_of(1)),
        LEFT_AT + 62,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    snapshot = sole_snapshot(back)
    assert snapshot.you == "p1"
    assert player_of(back.state, "p1").is_host is False
    assert player_of(back.state, "p2").is_host is True
    views = {view.player_id: view for view in snapshot.players}
    assert views["p1"].is_host is False
    assert views["p2"].is_host is True
    later = tick_at(back.state, 200)
    assert later.entries == ()
    assert player_of(later.state, "p2").is_host is True


def test_ac3_the_role_moves_again_when_the_new_host_is_away_too(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    first = tick_at(room, 61)
    assert player_of(first.state, "p2").is_host is True
    away = disconnect_player(first.state, "p2", LEFT_AT + 100).state

    early = tick_at(away, 160)
    late = tick_at(away, 160.5)

    assert early.entries == ()
    assert events_of(late.entries) == [HostChanged(seq=away.seq + 1, player_id="p3")]
    assert player_of(late.state, "p3").is_host is True
    assert player_of(late.state, "p2").is_host is False


def test_ac3_a_returned_ordinary_player_can_be_handed_the_role_again(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    first = tick_at(room, 61)
    back = join_room(
        first.state,
        new_guest("Ana", token_of(1)),
        LEFT_AT + 62,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    away = disconnect_player(back.state, "p2", LEFT_AT + 100).state

    outcome = tick_at(away, 161)

    assert events_of(outcome.entries) == [HostChanged(seq=away.seq + 1, player_id="p1")]
    assert player_of(outcome.state, "p1").is_host is True


def test_ac3_a_player_who_left_after_the_hand_over_leaves_without_a_new_host(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 2)
    handed = tick_at(room, 61)

    outcome = tick_at(handed.state, 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(
            seq=handed.state.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT
        )
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_host_who_times_out_gets_one_hand_over_only(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 3)

    outcome = tick_at(room, 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p2").is_host is True


# ---- AC-3: through the real WebSocket with a fake clock ----------------------


def test_ac3_websocket_after_60_seconds_the_first_joined_becomes_host(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as c_stack,
        contextlib.ExitStack() as a_again_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        c_id = peer_c.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        for peer in (peer_b, peer_c):
            peer.wait_until(
                lambda peer=peer: has_state_change(
                    peer, a_id, PlayerState.DISCONNECTED
                ),
                "A's disconnection",
            )

        fake_clock.advance(59)
        time.sleep(SETTLE_SECONDS)

        assert host_events(peer_b) == []
        assert host_events(peer_c) == []

        fake_clock.advance(2)

        for peer in (peer_b, peer_c):
            peer.wait_until(
                lambda peer=peer: len(host_events(peer)) == 1,
                "the host change",
                timeout=WS_DETECTION_SECONDS,
            )
            assert host_events(peer)[0].player_id == b_id
        time.sleep(SETTLE_SECONDS)
        assert len(host_events(peer_b)) == 1

        peer_b.send(RemovePlayer(player_id=c_id))

        removal = PlayerLeft(
            seq=host_events(peer_b)[0].seq + 1,
            player_id=c_id,
            reason=LeaveReason.REMOVED,
        )
        peer_b.wait_until(lambda: left_events(peer_b) == [removal], "B's removal of C")
        assert error_codes(peer_b) == []
        peer_a_again = open_peer(a_again_stack, client, code, "Ana", a_token)
        assert peer_a_again.snapshot().you == a_id
        views = {view.player_id: view for view in peer_a_again.snapshot().players}
        assert views[a_id].is_host is False
        assert views[b_id].is_host is True
        peer_a_again.send(LockRoom(locked=True))
        peer_a_again.wait_until(
            lambda: error_codes(peer_a_again) == [ErrorCode.NOT_HOST], "A refused"
        )
        state = registry.room_state(code)
        assert state is not None
        assert state.settings.locked is False
        assert room_players(registry, code) == [a_id, b_id]


# ---- AC-4: change settings (rules) -------------------------------------------


def room_with_used_budget(grid: Grid) -> RoomState:
    """Allowance 5 letters and 1 word, 2 letters and 0 words left (3 and 1 used)."""
    room = room_of_players(grid, 2)
    return room.model_copy(update={"reveal_budget": RevealBudget(letters=2, words=0)})


def change(help_mode: HelpMode, letters: int, words: int) -> ChangeSettings:
    return ChangeSettings(
        help_mode=help_mode, reveal_budget=RevealBudget(letters=letters, words=words)
    )


def test_ac4_fr_json_holds_the_settings_texts() -> None:
    fr = load_fr()

    assert fr["settings.heading"] == "Réglages"
    assert fr["settings.help_mode_label"] == "Aide"
    assert fr["settings.reveal_letters_label"] == "Lettres à révéler"
    assert fr["settings.reveal_words_label"] == "Mots à révéler"
    assert fr["settings.save"] == "Enregistrer"


def test_ac4_a_change_announces_the_new_settings_and_the_remaining_budget(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 0))

    expected_settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=3, words=0),
        locked=False,
    )
    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=3,
            player_id="p1",
            settings=expected_settings,
            reveal_budget=RevealBudget(letters=3, words=0),
        )
    ]
    assert outcome.state.settings == expected_settings
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=0)
    assert outcome.state.seq == 3


def test_ac4_the_same_settings_again_produce_nothing(fx01_grid: Grid) -> None:
    room = host_acts(room_of_players(fx01_grid, 2), change(HelpMode.VOTE, 3, 0)).state

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 0))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.seq == room.seq
    assert outcome.state.settings == room.settings


def test_ac4_the_unchanged_allowance_leaves_the_remaining_budget_alone(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 5, 1))

    assert outcome.entries == ()
    assert outcome.state.reveal_budget == RevealBudget(letters=2, words=0)


def test_ac4_a_new_help_mode_alone_is_announced_and_keeps_the_remaining_budget(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.NONE, 5, 1))

    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=RoomSettings(
                help_mode=HelpMode.NONE,
                reveal_budget=RevealBudget(letters=5, words=1),
                locked=False,
            ),
            reveal_budget=RevealBudget(letters=2, words=0),
        )
    ]


def test_ac4_a_new_allowance_alone_is_announced_with_the_help_mode_unchanged(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 6, 1))

    assert outcome.state.settings.help_mode is HelpMode.FREE
    assert outcome.state.settings.reveal_budget == RevealBudget(letters=6, words=1)
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=0)
    assert len(outcome.entries) == 1


def test_ac4_the_remaining_budget_is_the_new_allowance_minus_what_was_used(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 10, 3))

    assert outcome.state.reveal_budget == RevealBudget(letters=7, words=2)
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=RoomSettings(
                help_mode=HelpMode.FREE,
                reveal_budget=RevealBudget(letters=10, words=3),
                locked=False,
            ),
            reveal_budget=RevealBudget(letters=7, words=2),
        )
    ]


def test_ac4_an_allowance_below_what_was_used_leaves_zero_never_less(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 2, 0))

    assert outcome.state.reveal_budget == RevealBudget(letters=0, words=0)
    event = outcome.entries[0].event
    assert isinstance(event, SettingsChanged)
    assert event.reveal_budget == RevealBudget(letters=0, words=0)
    assert event.settings.reveal_budget == RevealBudget(letters=2, words=0)


def test_ac4_letters_and_words_are_computed_separately(fx01_grid: Grid) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 9, 0))

    assert outcome.state.reveal_budget == RevealBudget(letters=6, words=0)


def test_ac4_the_used_count_follows_the_allowance_and_remaining_budget_in_force(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)
    lowered = host_acts(room, change(HelpMode.FREE, 1, 1)).state
    assert lowered.reveal_budget == RevealBudget(letters=0, words=0)

    raised = host_acts(lowered, change(HelpMode.FREE, 10, 5))

    # used = old allowance - old remaining = (1 - 0, 1 - 0)
    assert raised.state.reveal_budget == RevealBudget(letters=9, words=4)


def test_ac4_any_count_from_zero_is_accepted_by_the_server(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, change(HelpMode.FREE, 250, 0))

    assert outcome.reply == ()
    assert outcome.state.settings.reveal_budget == RevealBudget(letters=250, words=0)
    assert outcome.state.reveal_budget == RevealBudget(letters=250, words=0)


def test_ac4_a_change_does_not_touch_the_lock(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 2))

    assert outcome.state.settings.locked is True
    event = outcome.entries[0].event
    assert isinstance(event, SettingsChanged)
    assert event.settings.locked is True
    assert event.settings.help_mode is HelpMode.VOTE


def test_ac4_a_player_who_is_not_host_gets_not_host(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = handle_message(room, "p2", change(HelpMode.VOTE, 3, 0), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


# ---- AC-4: through the real WebSocket ----------------------------------------


def test_ac4_websocket_a_change_reaches_both_players_once_and_only_the_host_may(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        a_id = peer_a.snapshot().you
        new_budget = RevealBudget(letters=3, words=0)
        expected = SettingsChanged(
            seq=3,
            player_id=a_id,
            settings=RoomSettings(
                help_mode=HelpMode.VOTE, reveal_budget=new_budget, locked=False
            ),
            reveal_budget=new_budget,
        )

        peer_a.send(change(HelpMode.VOTE, 3, 0))

        for peer in (peer_a, peer_b):
            peer.wait_until(lambda peer=peer: len(settings_events(peer)) == 1, "change")
            assert settings_events(peer) == [expected]

        peer_a.send(change(HelpMode.VOTE, 3, 0))
        ping_and_wait(peer_a)
        ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)
        assert settings_events(peer_a) == [expected]
        assert settings_events(peer_b) == [expected]
        assert error_codes(peer_a) == []

        peer_b.send(change(HelpMode.NONE, 9, 9))
        peer_b.wait_until(
            lambda: error_codes(peer_b) == [ErrorCode.NOT_HOST], "B refused"
        )
        ping_and_wait(peer_a)
        assert settings_events(peer_a) == [expected]
        state = registry.room_state(code)
        assert state is not None
        assert state.settings == expected.settings
        assert state.reveal_budget == new_budget


# ---- Helpers for the browser -------------------------------------------------


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


def host_frame(seq: int, player_id: str) -> str:
    return HostChanged(seq=seq, player_id=player_id).model_dump_json()


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


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def feed_lines(page: Page, kind: str) -> Locator:
    selector = f'[data-testid="feed-item"][data-kind="{kind}"]'
    return page.get_by_test_id("activity-feed").locator(selector)


def stored_resume_token(page: Page) -> str | None:
    stored = page.evaluate(f"localStorage.getItem({json.dumps(IDENTITY_KEY)})")
    if stored is None:
        return None
    decoded = json.loads(stored)
    return decoded["resume_token"]


# ---- AC-1: browser -----------------------------------------------------------


def test_ac1_browser_the_host_removes_a_player_who_cannot_come_back(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        bob_page.add_init_script(FORM_WATCHER)
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        expect(page.get_by_test_id("roster-player")).to_have_count(2)
        bob_id = room_page(bob_page).get_attribute("data-you")
        assert bob_id
        expect(bob_page.get_by_test_id("remove-player")).to_have_count(0)
        expect(bob_page.get_by_test_id("host-panel")).to_have_count(0)
        expect(page.get_by_test_id("host-panel")).to_be_visible()

        remove_button = roster_item(page, bob_id).get_by_test_id("remove-player")
        expect(remove_button).to_have_text(load_fr()["host.remove"])
        remove_button.click(timeout=FORM_TIMEOUT_MS)

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "removed", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.removed"]
        )
        expect(page.get_by_test_id("roster-player")).to_have_count(1)
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1

        bob_page.evaluate("window.__formSeen = false")
        bob_page.reload()

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "removed", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("nickname-form")).to_have_count(0)
        assert bob_page.evaluate("window.__formSeen") is False
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.removed"]
        )
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1
    finally:
        bob_context.close()


def test_ac1_browser_the_host_sees_a_labelled_button_on_each_other_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    dialogs: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", dismiss)

    expect(page.get_by_test_id("remove-player")).to_have_count(2)
    expect(roster_item(page, "p1").get_by_test_id("remove-player")).to_have_count(0)
    for player_id, name in (("p2", "Bob"), ("p3", "Cleo")):
        button = roster_item(page, player_id).get_by_test_id("remove-player")
        expect(button).to_have_text(load_fr()["host.remove"])
        expect(button).to_have_attribute("aria-label", f"Retirer {name} du salon")

    roster_item(page, "p3").get_by_test_id("remove-player").click(
        timeout=FORM_TIMEOUT_MS
    )

    wait_until(
        page, lambda: len(room.connections[0].messages_of_type("remove_player")) > 0
    )
    settle(page)
    sent = room.connections[0].messages_of_type("remove_player")
    assert sent == [{"type": "remove_player", "player_id": "p3"}]
    assert dialogs == []


def test_ac1_browser_a_player_who_is_not_host_sees_no_host_control(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players("p2"), you="p3")

    expect(roster_item(page, "p2")).to_have_count(1)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("lock-room")).to_have_count(0)
    expect(page.get_by_test_id("settings-form")).to_have_count(0)


@pytest.mark.parametrize("scenario", ["join", "game", "reconnection"])
def test_ac1_browser_removed_is_a_final_status(
    page: Page, live_server: str, fx01_grid: Grid, scenario: str
) -> None:
    room = reach_refusal(page, live_server, fx01_grid, scenario, ErrorCode.REMOVED)

    expect(room_page(page)).to_have_attribute("data-status", "removed")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.removed"]
    )
    expect(banner(page)).to_be_hidden()
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    count = len(room.connections)
    advance_page(page, 20000)
    assert len(room.connections) == count
    expect(room_page(page)).to_have_attribute("data-status", "removed")
    if scenario != "join":
        assert stored_resume_token(page) == SNAPSHOT_TOKEN


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


# ---- AC-2: browser -----------------------------------------------------------


def test_ac2_browser_the_host_locks_the_room_and_a_newcomer_is_refused(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        enter_room(page, url, "Ana")
        lock = page.get_by_test_id("lock-room")
        expect(lock).to_have_attribute("aria-pressed", "false")
        expect(lock).to_have_text(load_fr()["host.lock"])

        lock.click(timeout=FORM_TIMEOUT_MS)

        expect(lock).to_have_attribute("aria-pressed", "true")
        expect(lock).to_have_text(load_fr()["host.unlock"])
        expect(feed_lines(page, "room_locked")).to_have_text(
            "Ana a verrouillé le salon"
        )
        bob_page = bob_context.new_page()
        bob_page.goto(url)
        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "nickname", timeout=LOSS_BUDGET_MS
        )
        nickname_input = bob_page.get_by_test_id("nickname-input")
        nickname_input.fill("Bob", timeout=FORM_TIMEOUT_MS)
        nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "locked", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.locked"]
        )
        expect(bob_page.get_by_test_id("nickname-form")).to_have_count(0)
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1

        lock.click(timeout=FORM_TIMEOUT_MS)

        expect(lock).to_have_attribute("aria-pressed", "false")
        expect(lock).to_have_text(load_fr()["host.lock"])
        expect(feed_lines(page, "room_unlocked")).to_have_text(
            "Ana a déverrouillé le salon"
        )
        bob_page.reload()
        nickname_input = bob_page.get_by_test_id("nickname-input")
        nickname_input.fill("Bob", timeout=FORM_TIMEOUT_MS)
        nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "joined", timeout=LOSS_BUDGET_MS
        )
    finally:
        bob_context.close()


def test_ac2_browser_the_lock_button_sends_the_opposite_of_the_current_state(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]
    lock = page.get_by_test_id("lock-room")
    expect(lock).to_have_attribute("aria-pressed", "false")

    lock.click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("lock_room")) == 1)
    assert connection.messages_of_type("lock_room") == [
        {"type": "lock_room", "locked": True}
    ]
    expect(lock).to_have_attribute("aria-pressed", "false")
    locked_settings = START_SETTINGS.model_copy(update={"locked": True})
    connection.send(settings_frame(6, "p1", locked_settings))
    expect(lock).to_have_attribute("aria-pressed", "true")
    expect(lock).to_have_text(load_fr()["host.unlock"])

    lock.click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("lock_room")) == 2)
    assert connection.messages_of_type("lock_room")[1] == {
        "type": "lock_room",
        "locked": False,
    }
    connection.send(settings_frame(7, "p1", START_SETTINGS))
    expect(lock).to_have_attribute("aria-pressed", "false")
    expect(lock).to_have_text(load_fr()["host.lock"])


def test_ac2_browser_a_locked_snapshot_shows_the_button_pressed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    locked_settings = START_SETTINGS.model_copy(update={"locked": True})
    joined_mock_room(
        page, live_server, fx01_grid, three_players(), settings=locked_settings
    )

    lock = page.get_by_test_id("lock-room")
    expect(lock).to_have_attribute("aria-pressed", "true")
    expect(lock).to_have_text(load_fr()["host.unlock"])


@pytest.mark.parametrize("scenario", ["join", "game", "reconnection"])
def test_ac2_browser_room_locked_is_a_final_status(
    page: Page, live_server: str, fx01_grid: Grid, scenario: str
) -> None:
    room = reach_refusal(page, live_server, fx01_grid, scenario, ErrorCode.ROOM_LOCKED)

    expect(room_page(page)).to_have_attribute("data-status", "locked")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.locked"]
    )
    expect(banner(page)).to_be_hidden()
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    count = len(room.connections)
    advance_page(page, 20000)
    assert len(room.connections) == count
    expect(room_page(page)).to_have_attribute("data-status", "locked")


# ---- AC-3: browser (the page follows host_changed) ---------------------------


def test_ac3_browser_the_host_marker_is_on_the_host_item_only(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players("p2"), you="p3")

    expect(roster_item(page, "p2")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p3")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p2")).to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p1")).not_to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p3")).not_to_contain_text(load_fr()["roster.host"])


def test_ac3_browser_host_changed_moves_the_marker_and_gives_me_the_controls(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players("p1"), you="p3")
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)

    room.connections[0].send(host_frame(6, "p3"))

    expect(roster_item(page, "p3")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p3")).to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p1")).not_to_contain_text(load_fr()["roster.host"])
    expect(page.get_by_test_id("host-panel")).to_be_visible()
    expect(page.get_by_test_id("remove-player")).to_have_count(2)
    expect(roster_item(page, "p3").get_by_test_id("remove-player")).to_have_count(0)


def test_ac3_browser_host_changed_takes_the_controls_away_from_the_old_host(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players("p1"), you="p1")
    expect(page.get_by_test_id("host-panel")).to_be_visible()
    expect(page.get_by_test_id("remove-player")).to_have_count(2)

    room.connections[0].send(host_frame(6, "p2"))

    expect(roster_item(page, "p2")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)


# ---- AC-4: browser -----------------------------------------------------------


def test_ac4_browser_the_host_changes_the_settings_and_both_feeds_say_so(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        expect(bob_page.get_by_test_id("roster-player")).to_have_count(2)
        line = (
            "Ana a modifié les réglages : aide par vote, 3 lettres et 0 mots à révéler"
        )

        page.get_by_test_id("help-mode-select").select_option(
            "vote", timeout=FORM_TIMEOUT_MS
        )
        page.get_by_test_id("reveal-letters-input").fill("3", timeout=FORM_TIMEOUT_MS)
        page.get_by_test_id("reveal-words-input").fill("0", timeout=FORM_TIMEOUT_MS)
        page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)

        expect(feed_lines(bob_page, "settings_changed")).to_have_text(
            line, timeout=LOSS_BUDGET_MS
        )
        expect(feed_lines(page, "settings_changed")).to_have_text(line)
        state = room_registry.room_state(code)
        assert state is not None
        assert state.settings == RoomSettings(
            help_mode=HelpMode.VOTE,
            reveal_budget=RevealBudget(letters=3, words=0),
            locked=False,
        )

        page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)
        settle(page)

        expect(feed_lines(page, "settings_changed")).to_have_count(1)
        expect(feed_lines(bob_page, "settings_changed")).to_have_count(1)
        expect(bob_page.get_by_test_id("settings-form")).to_have_count(0)
    finally:
        bob_context.close()


def test_ac4_browser_the_form_lists_the_modes_and_limits_the_counts(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=3, words=2),
        locked=False,
    )
    joined_mock_room(
        page,
        live_server,
        fx01_grid,
        three_players(),
        settings=settings,
        remaining=RevealBudget(letters=1, words=0),
    )

    form = page.get_by_test_id("settings-form")
    select = page.get_by_test_id("help-mode-select")
    letters = page.get_by_test_id("reveal-letters-input")
    words = page.get_by_test_id("reveal-words-input")
    expect(page.get_by_test_id("host-panel")).to_contain_text(fr["settings.heading"])
    expect(select).to_have_accessible_name(fr["settings.help_mode_label"])
    expect(letters).to_have_accessible_name(fr["settings.reveal_letters_label"])
    expect(words).to_have_accessible_name(fr["settings.reveal_words_label"])
    expect(form.get_by_test_id("settings-save")).to_have_text(fr["settings.save"])
    options = select.locator("option")
    expect(options).to_have_count(3)
    for index, mode in enumerate(["free", "vote", "none"]):
        expect(options.nth(index)).to_have_attribute("value", mode)
        expect(options.nth(index)).to_have_text(fr[f"settings.help_mode.{mode}"])
    for number_input in (letters, words):
        expect(number_input).to_have_attribute("type", "number")
        expect(number_input).to_have_attribute("min", "0")
        expect(number_input).to_have_attribute("max", "99")
    expect(select).to_have_value("vote")
    expect(letters).to_have_value("3")
    expect(words).to_have_value("2")


def test_ac4_browser_the_form_follows_a_settings_changed_event(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    new_settings = RoomSettings(
        help_mode=HelpMode.NONE,
        reveal_budget=RevealBudget(letters=8, words=4),
        locked=False,
    )

    room.connections[0].send(settings_frame(6, "p2", new_settings))

    expect(page.get_by_test_id("help-mode-select")).to_have_value("none")
    expect(page.get_by_test_id("reveal-letters-input")).to_have_value("8")
    expect(page.get_by_test_id("reveal-words-input")).to_have_value("4")


def test_ac4_browser_submitting_sends_the_change_settings_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]

    page.get_by_test_id("help-mode-select").select_option(
        "none", timeout=FORM_TIMEOUT_MS
    )
    page.get_by_test_id("reveal-letters-input").fill("12", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("reveal-words-input").fill("0", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("change_settings")) == 1)
    assert connection.messages_of_type("change_settings") == [
        {
            "type": "change_settings",
            "help_mode": "none",
            "reveal_budget": {"letters": 12, "words": 0},
        }
    ]
    settle(page)
    assert len(connection.messages_of_type("change_settings")) == 1


@pytest.mark.parametrize("bad_value", ["100", "-1", "2.5"])
def test_ac4_browser_the_form_never_sends_a_count_out_of_its_bounds(
    page: Page, live_server: str, fx01_grid: Grid, bad_value: str
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]
    page.get_by_test_id("reveal-letters-input").fill(bad_value, timeout=FORM_TIMEOUT_MS)

    page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)
    settle(page)

    for sent in connection.messages_of_type("change_settings"):
        budget = sent["reveal_budget"]
        assert isinstance(budget, dict)
        letters = budget["letters"]
        assert isinstance(letters, int)
        assert 0 <= letters <= 99


def test_ac4_browser_a_player_who_is_not_host_has_no_settings_form(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players(), you="p2")

    expect(page.get_by_test_id("settings-form")).to_have_count(0)
    expect(page.get_by_test_id("help-mode-select")).to_have_count(0)
    expect(page.get_by_test_id("settings-save")).to_have_count(0)


# ---- Layout of the host's view (spec 013 AC-6 with the host controls) --------


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


def check_frame(seq: int) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac1_browser_the_host_view_keeps_the_grids_room(
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
        room = joined_mock_room(page, live_server, fx01_grid, eight_players())
        last_seq = 5 + FEED_LIMIT
        for seq in range(6, last_seq + 1):
            room.connections[0].send(check_frame(seq))
        expect(room_page(page)).to_have_attribute("data-seq", str(last_seq))
        expect(page.get_by_test_id("remove-player")).to_have_count(7)
        panel = page.get_by_test_id("host-panel")
        expect(panel).to_be_visible()
        expect(page.get_by_test_id("lock-room")).to_be_visible()
        expect(page.get_by_test_id("settings-form")).to_be_visible()

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
        panel_box = panel.bounding_box()
        assert viewport_box is not None
        assert bar_box is not None
        assert panel_box is not None
        sizes = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth,"
            " document.documentElement.scrollHeight, window.innerHeight]"
        )
        scroll_width, window_width, scroll_height, window_height = sizes

        assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
        assert scroll_width <= window_width
        assert scroll_height <= window_height
        expect(viewport).to_have_attribute("data-zoom", "1")
        assert panel_box["x"] >= -EPSILON
        assert panel_box["x"] + panel_box["width"] <= window_width + EPSILON
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
