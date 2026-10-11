"""Tests of spec 017: disconnection and reconnection.

The rules (`handle_message`, `tick`, `join_room`) are tested directly with
exact clock values. The hub is tested with the real WebSocket, a fake clock and
`tick_seconds=0.05`, so the 6-second and 5-minute values keep their defaults and
pass in milliseconds. The page is tested with spec 040's mocked socket: the
handler is called again for each socket the page opens, so a test counts the
connections, answers pings (or not), closes a socket and sends snapshots.

Time-based client behaviour has two kinds of tests. The bounds the spec states
in real seconds (the banner within 5,000 ms) are measured with Playwright's
waiting assertions. The constants (ping every 2,000 ms, 4,000 ms of silence,
the reconnect delays) are tested without long waits on Playwright's page clock,
which is frozen before the page loads and moved by hand with `run_for`.

Not tested here: the close 4408 reaching only the silent socket of a player (a
player has one live socket, the older one being replaced by a resume), the
`pencil_edit` and `confirm_pencil` forms of the stale rule (spec 020), the locked
room refusing the join of a timed-out player (spec 014), a real network cut
(spec decision 7) and the pending edits lost by a reload (not observable).
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
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

import nock.hub
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    HostChanged,
    Join,
    LeaveReason,
    LetterCellView,
    LetterChanged,
    Ping,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    SelectCell,
    ServerMessage,
    Snapshot,
    Undo,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    Disconnect,
    LogEntry,
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

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
NOW = 2_000_000.0
SILENCE_CLOSE = 4408
NEW_PLAYER_ID = "new-player"
NEW_TOKEN = "new-player-token-0000"
NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eva", "Fay", "Gus", "Hal"]
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
STORED_IDENTITY = json.dumps(
    {"player_id": "p1", "resume_token": SNAPSHOT_TOKEN, "nickname": "Ana"}
)
STORED_JOIN = Join(nickname="Ana", resume_token=SNAPSHOT_TOKEN)
SELECTION_MOVED_FRAME = (
    '{"type": "selection_moved", "player_id": "p2", "selection": '
    '{"row": 1, "column": 0, "direction": "across"}}'
)
FORM_WATCHER = (
    "window.__formSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"nickname-form\"]')) {"
    " window.__formSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)

TICK_SECONDS = 0.05
SETTLE_SECONDS = 0.3
WS_WAIT_SECONDS = 5.0
WS_DETECTION_SECONDS = 1.0  # the spec: "within one second of real time"
LOSS_BUDGET_MS = 5000
ROSTER_BUDGET_MS = 300
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


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


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


def player_ids(state: RoomState) -> list[str]:
    ids: list[str] = []
    for player in state.players:
        ids.append(player.player_id)
    return ids


def events_of(entries: tuple[LogEntry, ...]) -> list[object]:
    """Return the event of each log entry."""
    events: list[object] = []
    for entry in entries:
        events.append(entry.event)
    return events


def stale_room(grid: Grid) -> RoomState:
    """Two players, seq 10; `p2` wrote `B` at (1, 0) with seq 8."""
    room = with_cell(
        two_player_room(grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=8,
            changed_by="p2",
        ),
    )
    return room.model_copy(update={"seq": 10})


def sole_error(reply: tuple[ServerMessage, ...]) -> ErrorMessage:
    assert len(reply) == 1
    error = reply[0]
    assert isinstance(error, ErrorMessage)
    return error


# ---- fr.json (AC-1) ----------------------------------------------------------


def test_ac1_fr_json_holds_the_reconnection_texts() -> None:
    messages = load_fr()

    assert messages["room.status.reconnecting"] == "Reconnexion…"
    assert messages["room.banner.offline"] == (
        "Connexion perdue. Vous pouvez continuer : vos lettres seront "
        "envoyées au retour du réseau."
    )


# ---- AC-2: the stale rule on handle_message ----------------------------------


def test_ac2_an_edit_on_a_cell_changed_since_by_someone_else_is_refused(
    fx01_grid: Grid,
) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert sole_error(outcome.reply).code is ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    assert outcome.state.seq == 10
    assert outcome.state.cells == room.cells
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("B", "p2", 8)


def test_ac2_a_base_seq_equal_to_the_changed_seq_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=8), NOW
    )

    assert outcome.reply == ()
    assert outcome.state.seq == 11
    assert events_of(outcome.entries) == [
        LetterChanged(seq=11, row=1, column=0, letter="T", pencil=False, player_id="p1")
    ]
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("T", "p1", 11)


@pytest.mark.parametrize("changed_seq", [0, 7])
def test_ac2_a_cell_unchanged_since_the_base_seq_is_applied(
    fx01_grid: Grid, changed_seq: int
) -> None:
    room = stale_room(fx01_grid)
    if changed_seq > 0:
        room = with_cell(
            room,
            CellState(
                row=1,
                column=1,
                letter="Z",
                author="p2",
                changed_seq=changed_seq,
                changed_by="p2",
            ),
        )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=1, letter="A", base_seq=7), NOW
    )

    assert outcome.reply == ()
    assert outcome.state.seq == 11
    cell = cell_state(outcome.state, 1, 1)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p1", 11)


def test_ac2_my_own_later_change_never_makes_my_edit_stale(fx01_grid: Grid) -> None:
    room = with_cell(
        stale_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="X",
            author="p1",
            changed_seq=9,
            changed_by="p1",
        ),
    )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_a_live_edit_is_never_stale(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=None), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_a_base_seq_beyond_the_room_seq_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=99), NOW
    )

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 0).letter == "T"
    assert outcome.state.seq == 11


def test_ac2_resending_offline_edits_to_one_cell_keeps_the_last(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)

    first = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=2), NOW
    )
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="X", base_seq=2), NOW
    )

    assert first.reply == ()
    assert second.reply == ()
    assert second.state.seq == 4
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("X", "p1", 4)


def test_ac2_an_offline_erase_that_is_stale_is_refused(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(room, "p1", Erase(row=1, column=0, base_seq=7), NOW)

    assert sole_error(outcome.reply).code is ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("B", "p2", 8)


def test_ac2_an_offline_erase_that_is_not_stale_is_applied(fx01_grid: Grid) -> None:
    room = stale_room(fx01_grid)

    outcome = handle_message(room, "p1", Erase(row=1, column=0, base_seq=8), NOW)

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        LetterChanged(
            seq=11, row=1, column=0, letter=None, pencil=False, player_id="p1"
        )
    ]
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == (None, None)


def test_ac2_a_locked_cell_is_refused_as_locked_before_staleness(
    fx01_grid: Grid,
) -> None:
    room = with_cell(
        stale_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            locked=True,
            changed_seq=8,
            changed_by="p2",
        ),
    )

    outcome = handle_message(
        room, "p1", EditLetter(row=1, column=0, letter="T", base_seq=7), NOW
    )

    assert sole_error(outcome.reply).code is ErrorCode.CELL_LOCKED


def test_ac2_the_rate_limit_is_checked_before_staleness(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=1)
    room = stale_room(fx01_grid)
    first = handle_message(
        room, "p1", EditLetter(row=1, column=1, letter="A"), NOW, config
    )
    assert first.reply == ()

    outcome = handle_message(
        first.state,
        "p1",
        EditLetter(row=1, column=0, letter="T", base_seq=7),
        NOW,
        config,
    )

    assert sole_error(outcome.reply).code is ErrorCode.RATE_LIMITED


# ---- AC-2: the stale rule through the real WebSocket -------------------------


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


def player_left_events(peer: Peer) -> list[PlayerLeft]:
    found: list[PlayerLeft] = []
    for message in peer.messages():
        if isinstance(message, PlayerLeft):
            found.append(message)
    return found


def letter_events(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.events():
        if isinstance(message, LetterChanged):
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
DEFAULT_SILENCE_CONFIG = RoomConfig(tick_seconds=TICK_SECONDS)


def test_ac2_websocket_an_offline_edit_on_a_changed_cell_gets_stale_edit(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        a_token = peer_a.snapshot().resume_token
        assert peer_a.snapshot().seq == 1
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )
        peer_b.send(EditLetter(row=1, column=0, letter="B"))
        peer_b.wait_until(lambda: len(letter_events(peer_b)) == 1, "B's own letter")
        written_seq = letter_events(peer_b)[0].seq
        assert written_seq == 4

        with contextlib.ExitStack() as second_a_stack:
            second_a = open_peer(second_a_stack, client, code, "Ana", a_token)
            assert second_a.snapshot().you == a_id
            assert second_a.snapshot().seq == 5
            second_a.send(EditLetter(row=1, column=0, letter="T", base_seq=2))
            second_a.send(EditLetter(row=1, column=1, letter="A", base_seq=2))
            second_a.wait_until(
                lambda: len(error_events(second_a)) == 1
                and len(letter_events(second_a)) == 1,
                "the refusal and the applied letter",
            )
            peer_b.wait_until(
                lambda: len(letter_events(peer_b)) == 2, "A's applied letter on B"
            )
            time.sleep(SETTLE_SECONDS)

            assert error_events(second_a)[0].code is ErrorCode.STALE_EDIT
            applied = LetterChanged(
                seq=6, row=1, column=1, letter="A", pencil=False, player_id=a_id
            )
            first_event = second_a.events()[0]
            assert isinstance(first_event, ErrorMessage)
            assert letter_events(second_a) == [applied]
            written_by_b = LetterChanged(
                seq=4, row=1, column=0, letter="B", pencil=False, player_id=b_id
            )
            assert letter_events(peer_b) == [written_by_b, applied]
            assert error_events(peer_b) == []
            state = registry.room_state(code)
            assert state is not None
            assert cell_state(state, 1, 0).letter == "B"
            assert cell_state(state, 1, 1).letter == "A"
            assert state.seq == 6


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


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return event.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def state_changed_frame(seq: int, player_id: str, state: PlayerState) -> str:
    event = PlayerStateChanged(seq=seq, player_id=player_id, state=state)
    return event.model_dump_json()


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


def wait_for_edits(
    page: Page, connection: MockConnection, expected: list[Edit]
) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    wait_until(page, lambda: len(connection.edits()) >= len(expected))
    settle(page)
    assert connection.edits() == expected


def expect_offline(page: Page) -> None:
    expect(room_page(page)).to_have_attribute(
        "data-status", "reconnecting", timeout=LOSS_BUDGET_MS
    )
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)


def expect_status(page: Page, status: str) -> None:
    expect(room_page(page)).to_have_attribute("data-status", status)


# ---- AC-1: the banner and typing offline (real time) -------------------------


def test_ac1_a_socket_closed_with_1011_shows_the_banner_and_typing_goes_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    first = room.connections[0]

    first.close(1011)

    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    expect(banner(page)).to_have_attribute("role", "status")
    expect_status(page, "reconnecting")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.reconnecting"]
    )
    frames_at_loss = len(first.frames)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    settle(page)
    assert len(first.frames) == frames_at_loss
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    assert second.edits() == []

    second.send(snapshot_frame(fx01_grid, 5))

    expect(banner(page)).to_be_hidden()
    expect_status(page, "joined")


def test_ac1_a_silent_socket_shows_the_banner_within_5_seconds_of_the_last_frame(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    first = room.connections[0]
    wait_until(page, lambda: first.ping_count() >= 1)
    room.answer_pings = False
    answered_until = room.last_sent_at
    elapsed_ms = int((time.monotonic() - answered_until) * 1000)
    remaining_ms = max(1, LOSS_BUDGET_MS - elapsed_ms)

    expect(banner(page)).to_be_visible(timeout=remaining_ms)

    expect_status(page, "reconnecting")
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    room.wait_for_connections(2)
    room.connections[1].send(snapshot_frame(fx01_grid, 5))
    expect(banner(page)).to_be_hidden()
    expect_status(page, "joined")


# ---- AC-1: heartbeat and loss detection (page clock) -------------------------


def test_ac1_the_page_pings_every_2_seconds_while_the_socket_is_open(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]
    pings_before = connection.ping_count()

    advance_page(page, 1999)
    assert connection.ping_count() == pings_before

    advance_page(page, 1)
    wait_until(page, lambda: connection.ping_count() > pings_before)
    assert connection.ping_count() == pings_before + 1
    for expected_more in (2, 3, 4):
        advance_page(page, 2000)
        assert connection.ping_count() == pings_before + expected_more
    expect_status(page, "joined")
    assert len(room.connections) == 1


def test_ac1_a_ping_in_the_wire_format_of_spec_039(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]

    advance_page(page, 2000)
    wait_until(page, lambda: connection.ping_count() >= 1)

    ping_frames = [f for f in connection.frames if json.loads(f)["type"] == "ping"]
    assert [json.loads(frame) for frame in ping_frames] == [{"type": "ping"}]


def test_ac1_answered_pings_keep_the_connection_open_for_a_long_time(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    for _ in range(10):
        advance_page(page, 2000)

    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    assert len(room.connections) == 1


def test_ac1_a_socket_silent_for_4_seconds_is_given_up_and_lost(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True, answer_pings=False)

    advance_page(page, 3900)
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()

    # The last frame (the snapshot) arrived at page time 1, so the 4 s of
    # silence end at page time 4001, the end of this advance (timers fire
    # inclusively at the end of an advance).
    advance_page(page, 100)

    expect_offline(page)
    expect(banner(page)).to_have_text(load_fr()["room.banner.offline"])
    assert len(room.connections) == 1
    expect_new_connection_after(page, room, 1000)


def test_ac1_a_frame_of_any_kind_restarts_the_4_seconds_of_silence(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True, answer_pings=False)
    advance_page(page, 3000)
    room.connections[0].send(SELECTION_MOVED_FRAME)
    page.wait_for_timeout(STEP_SETTLE_MS)

    advance_page(page, 3000)
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()

    advance_page(page, 1500)

    expect_offline(page)


# ---- AC-1: reconnect delays (page clock) -------------------------------------


def expect_new_connection_after(page: Page, room: MockRoom, delay_ms: int) -> None:
    """The next socket opens after `delay_ms` of page time, not before."""
    count = len(room.connections)
    advance_page(page, delay_ms - 1)
    assert len(room.connections) == count
    advance_page(page, 1)
    wait_until(page, lambda: len(room.connections) > count)
    assert len(room.connections) == count + 1


def test_ac1_the_delays_are_1_2_4_8_then_8_seconds(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)

    for index, delay_ms in enumerate([1000, 2000, 4000, 8000, 8000, 8000]):
        expect_new_connection_after(page, room, delay_ms)
        assert first_join(page, room.connections[index + 1]) == STORED_JOIN
        room.connections[index + 1].close(1011)
        page.wait_for_timeout(STEP_SETTLE_MS)

    expect_status(page, "reconnecting")


def test_ac1_the_delays_start_again_from_the_first_after_a_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    expect_new_connection_after(page, room, 1000)
    room.connections[1].close(1011)
    page.wait_for_timeout(STEP_SETTLE_MS)
    expect_new_connection_after(page, room, 2000)

    room.connections[2].send(snapshot_frame(fx01_grid, 5))
    expect_status(page, "joined")
    expect(banner(page)).to_be_hidden()
    room.connections[2].close(1011)
    expect_offline(page)

    expect_new_connection_after(page, room, 1000)


def test_ac1_the_online_event_reconnects_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    page.wait_for_timeout(STEP_SETTLE_MS)
    assert len(room.connections) == 1

    page.evaluate("window.dispatchEvent(new Event('online'))")

    room.wait_for_connections(2)
    assert first_join(page, room.connections[1]) == STORED_JOIN


@pytest.mark.parametrize("code", [1000, 1001, 1011, 4408])
def test_ac1_any_other_close_code_is_a_lost_connection(
    page: Page, live_server: str, fx01_grid: Grid, code: int
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    room.connections[0].close(code)

    expect_offline(page)
    expect_new_connection_after(page, room, 1000)


# ---- AC-1: final states ------------------------------------------------------


@pytest.mark.parametrize(
    ("code", "status"),
    [(4404, "not_found"), (4429, "throttled"), (4001, "replaced")],
)
def test_ac1_a_final_close_code_ends_the_attempts(
    page: Page, live_server: str, fx01_grid: Grid, code: int, status: str
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)

    room.connections[0].close(code)

    expect_status(page, status)
    expect(banner(page)).to_be_hidden()
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect_status(page, status)
    expect(banner(page)).to_be_hidden()


def test_ac1_a_close_that_follows_room_full_ends_the_attempts(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(ErrorCode.ROOM_FULL))
    connection.close(1000)

    expect_status(page, "full")
    expect(banner(page)).to_be_hidden()
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect_status(page, "full")


@pytest.mark.parametrize("error_code", [ErrorCode.ROOM_LOCKED, ErrorCode.REMOVED])
def test_ac1_a_close_that_follows_locked_or_removed_ends_the_attempts(
    page: Page, live_server: str, error_code: ErrorCode
) -> None:
    """The status value is spec 014's (not built yet): only the end is checked."""
    room = open_room(page, live_server, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(error_code))
    connection.close(1000)

    page.wait_for_timeout(STEP_SETTLE_MS)
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).not_to_have_attribute("data-status", "reconnecting")
    expect(room_page(page)).not_to_have_attribute("data-status", "connecting")
    advance_page(page, 20000)
    assert len(room.connections) == 1
    expect(banner(page)).to_be_hidden()


def test_ac1_a_close_after_an_error_that_is_not_final_is_a_lost_connection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, frozen=True)
    connection = room.connections[0]

    connection.send(error_frame(ErrorCode.CELL_LOCKED))
    connection.close(1011)

    expect_offline(page)
    expect_new_connection_after(page, room, 1000)


# ---- AC-1: before the first snapshot -----------------------------------------


def test_ac1_a_loss_before_the_first_snapshot_retries_without_a_banner(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)

    room.connections[0].close(1011)

    expect_status(page, "connecting")
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).to_have_attribute("data-seq", "")
    expect_new_connection_after(page, room, 1000)
    assert first_join(page, room.connections[1]) == STORED_JOIN
    expect(banner(page)).to_be_hidden()


def test_ac1_before_the_first_snapshot_the_delays_grow_too(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True)
    room.connections[0].close(1011)
    expect_status(page, "connecting")

    expect_new_connection_after(page, room, 1000)
    room.connections[1].close(1011)
    page.wait_for_timeout(STEP_SETTLE_MS)

    expect_new_connection_after(page, room, 2000)
    expect(banner(page)).to_be_hidden()


def test_ac1_the_nickname_form_stays_when_the_socket_is_lost_before_a_join(
    page: Page, live_server: str
) -> None:
    room = open_room(page, live_server, frozen=True, identity=False)
    expect(page.get_by_test_id("nickname-form")).to_be_visible()

    room.connections[0].close(1011)
    page.wait_for_timeout(SETTLE_MS)

    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(banner(page)).to_be_hidden()
    expect_new_connection_after(page, room, 1000)
    expect(page.get_by_test_id("nickname-form")).to_be_visible()


# ---- AC-2: offline edits resent with their base_seq (browser) ----------------


def test_ac2_offline_letters_are_resent_with_base_seq_and_the_server_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    page.keyboard.press("a")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    assert second.edits() == []
    changes: ChangeList = [(1, 0, {"letter": "B", "author": "p2"})]
    second.send(snapshot_frame(fx01_grid, 9, changes))

    expect(room_page(page)).to_have_attribute("data-seq", "9")
    expect(banner(page)).to_be_hidden()
    wait_for_edits(
        page,
        second,
        [
            EditLetter(row=1, column=0, letter="T", base_seq=5),
            EditLetter(row=1, column=1, letter="A", base_seq=5),
        ],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    second.send(error_frame(ErrorCode.STALE_EDIT))

    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    second.send(letter_changed_frame(10, 1, 1, "A", "p1"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p1")
    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")


def test_ac2_an_edit_sent_before_the_loss_is_resent_with_its_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    first = room.connections[0]
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    wait_for_edits(page, first, [EditLetter(row=1, column=0, letter="T")])
    first.close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 9))

    wait_for_edits(page, second, [EditLetter(row=1, column=0, letter="T", base_seq=5)])
    second.send(letter_changed_frame(10, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_an_offline_erase_is_resent_with_its_base_seq(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p2"})]
    room = joined_room(page, live_server, fx01_grid, seq=5, changes=changes)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    cell_at(page, 1, 0).click()
    page.keyboard.press("Backspace")
    expect_cell(page, 1, 0, "", unconfirmed=True)

    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 7, changes))

    wait_for_edits(page, second, [Erase(row=1, column=0, base_seq=5)])


def test_ac2_edits_typed_after_the_reconnection_are_sent_live(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect(banner(page)).to_be_visible(timeout=LOSS_BUDGET_MS)
    room.wait_for_connections(2)
    second = room.connections[1]
    second.send(snapshot_frame(fx01_grid, 9))
    expect(banner(page)).to_be_hidden()
    expect(room_page(page)).to_have_attribute("data-seq", "9")
    cell_at(page, 1, 0).click()

    page.keyboard.press("t")

    wait_for_edits(page, second, [EditLetter(row=1, column=0, letter="T")])


# ---- AC-3: the 300 s window on the rules -------------------------------------

DISCONNECTED_AT = NOW + 10.0


def room_with_bob_disconnected(grid: Grid) -> RoomState:
    """Two players; `p2` (Bob, colour 1) wrote `B` at (1, 0) and left at t."""
    room = with_cell(
        two_player_room(grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=2,
            changed_by="p2",
        ),
    )
    return disconnect_player(room, "p2", DISCONNECTED_AT).state


def test_ac3_a_join_with_the_token_exactly_300_seconds_later_resumes_the_player(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    resume = Join(nickname="Autre", resume_token=token_of(2))

    outcome = join_room(room, resume, DISCONNECTED_AT + 300, NEW_PLAYER_ID, NEW_TOKEN)

    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "p2"
    views = {view.player_id: view for view in snapshot.players}
    assert sorted(views) == ["p1", "p2"]
    assert (views["p2"].nickname, views["p2"].colour) == ("Bob", 1)
    assert views["p2"].state == PlayerState.ACTIVE
    for event in events_of(outcome.entries):
        assert not isinstance(event, PlayerLeft | PlayerJoined)
    assert player_ids(outcome.state) == ["p1", "p2"]
    assert cell_state(outcome.state, 1, 0).author == "p2"


def test_ac3_a_join_with_the_token_after_300_seconds_times_the_player_out(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    join = Join(nickname="Bob", resume_token=token_of(2))

    outcome = join_room(room, join, DISCONNECTED_AT + 300.5, NEW_PLAYER_ID, NEW_TOKEN)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT),
        PlayerJoined(seq=5, player=player_view(NEW_PLAYER_ID, "Bob", 1)),
    ]
    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID
    assert player_ids(outcome.state) == ["p1", NEW_PLAYER_ID]
    new_player = player_of(outcome.state, NEW_PLAYER_ID)
    assert new_player.resume_token == NEW_TOKEN
    assert new_player.is_host is False
    old_cell = cell_state(outcome.state, 1, 0)
    assert (old_cell.letter, old_cell.author) == ("B", "p2")


def test_ac3_the_new_player_after_a_time_out_takes_the_nickname_of_the_join(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    join = Join(nickname="Zoe", resume_token=token_of(2))

    outcome = join_room(room, join, DISCONNECTED_AT + 300.5, NEW_PLAYER_ID, NEW_TOKEN)

    assert player_of(outcome.state, NEW_PLAYER_ID).nickname == "Zoe"


def test_ac3_a_tick_exactly_300_seconds_after_the_disconnection_keeps_the_player(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 300)

    outcome = tick(room, DISCONNECTED_AT + 300)

    assert outcome.entries == ()
    assert outcome.state == room
    assert player_ids(outcome.state) == ["p1", "p2"]


def test_ac3_a_tick_after_300_seconds_removes_the_player_and_keeps_their_letters(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 300.5)

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT)
    ]
    assert outcome.state.seq == 4
    assert player_ids(outcome.state) == ["p1"]
    assert outcome.disconnects == ()
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == ("B", "p2")


def test_ac3_the_window_follows_the_configuration(fx01_grid: Grid) -> None:
    config = RoomConfig(resume_window_seconds=20.0)
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 20.5)

    at_limit = tick(keep_seen(room, DISCONNECTED_AT + 20), DISCONNECTED_AT + 20, config)
    after_limit = tick(room, DISCONNECTED_AT + 20.5, config)

    assert at_limit.entries == ()
    assert events_of(after_limit.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT)
    ]


def test_ac3_a_host_who_times_out_hands_the_role_over_at_once(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(two_player_room(fx01_grid), "p1", DISCONNECTED_AT).state
    room = keep_seen(room, DISCONNECTED_AT + 300.5)

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=5, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2"]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_when_nobody_is_left_the_next_joiner_becomes_host(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(room_of_players(fx01_grid, 1), "p1", DISCONNECTED_AT).state

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=3, player_id="p1", reason=LeaveReason.TIMED_OUT)
    ]
    assert outcome.state.players == ()
    joined = join_room(
        outcome.state,
        Join(nickname="Ana", resume_token=None),
        DISCONNECTED_AT + 301,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    assert player_of(joined.state, NEW_PLAYER_ID).is_host is True


def host_timing_out_room(
    grid: Grid, count: int, disconnected_players: list[str]
) -> RoomState:
    """Return `count` players where the host `p1` is ready to time out.

    `p1` disconnected at DISCONNECTED_AT; each player of `disconnected_players`
    disconnected 250 seconds later (inside their window and under the 60 seconds
    of spec 014's hand-over at the time-out tick); the others are active and
    seen at the time-out tick.
    """
    room = disconnect_player(room_of_players(grid, count), "p1", DISCONNECTED_AT).state
    for player_id in disconnected_players:
        room = disconnect_player(room, player_id, DISCONNECTED_AT + 250).state
    return keep_seen(room, DISCONNECTED_AT + 300.5)


def test_ac3_a_timed_out_host_hands_over_to_a_connected_player_not_a_disconnected(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 3, ["p2"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p3"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p2").is_host is False


def test_ac3_a_timed_out_host_hands_over_to_the_longest_present_connected_player(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 4, ["p2"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p3"),
    ]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p4").is_host is False


def test_ac3_a_timed_out_host_hands_over_to_the_longest_present_when_all_are_away(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 3, ["p2", "p3"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p2").is_host is True
    assert player_of(outcome.state, "p3").is_host is False


def test_ac3_a_disconnected_player_keeps_the_seat_for_the_whole_window(
    fx01_grid: Grid,
) -> None:
    full_room = disconnect_player(
        room_of_players(fx01_grid, 8), "p8", DISCONNECTED_AT
    ).state
    ninth = Join(nickname="Ivy", resume_token=None)

    outcome = join_room(
        full_room, ninth, DISCONNECTED_AT + 100, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_FULL
    assert outcome.state.players == full_room.players


def test_ac3_after_the_time_out_the_seat_is_free_again(fx01_grid: Grid) -> None:
    full_room = disconnect_player(
        room_of_players(fx01_grid, 8), "p8", DISCONNECTED_AT
    ).state
    after_window = DISCONNECTED_AT + 300.5
    ticked = tick(keep_seen(full_room, after_window), after_window)
    assert player_ids(ticked.state) == [f"p{n}" for n in range(1, 8)]

    outcome = join_room(
        ticked.state,
        Join(nickname="Ivy", resume_token=None),
        after_window,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID
    assert len(outcome.state.players) == 8


def test_ac3_a_timed_out_token_no_longer_resumes_after_the_tick(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 301)
    ticked = tick(room, DISCONNECTED_AT + 301)

    outcome = join_room(
        ticked.state,
        Join(nickname="Bob", resume_token=token_of(2)),
        DISCONNECTED_AT + 302,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID


# ---- AC-3: the 300 s window through the real WebSocket -----------------------


def test_ac3_websocket_a_return_within_299_seconds_resumes_the_same_player(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(299)
        time.sleep(SETTLE_SECONDS)

        assert player_left_events(peer_b) == []
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Autre", a_token)
            snapshot = second_a.snapshot()
            assert snapshot.you == a_id
            views = {view.player_id: view for view in snapshot.players}
            assert (views[a_id].nickname, views[a_id].colour) == ("Ana", 0)
            assert len(snapshot.players) == 2
            peer_b.wait_until(
                lambda: has_state_change(peer_b, a_id, PlayerState.ACTIVE),
                "A back to active on B",
            )


def test_ac3_websocket_a_return_exactly_300_seconds_later_still_resumes(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(300)
        time.sleep(SETTLE_SECONDS)

        assert player_left_events(peer_b) == []
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Autre", a_token)
            assert second_a.snapshot().you == a_id


def test_ac3_websocket_after_301_seconds_the_player_times_out_and_the_token_is_new(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(301)

        peer_b.wait_until(
            lambda: len(player_left_events(peer_b)) == 1,
            "A's time-out on B",
            timeout=WS_DETECTION_SECONDS,
        )
        assert player_left_events(peer_b) == [
            PlayerLeft(seq=4, player_id=a_id, reason=LeaveReason.TIMED_OUT)
        ]
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Ana", a_token)
            snapshot = second_a.snapshot()
            assert snapshot.you != a_id
            ids = [view.player_id for view in snapshot.players]
            assert a_id not in ids
            assert len(ids) == 2
            new_view = next(v for v in snapshot.players if v.player_id == snapshot.you)
            assert (new_view.nickname, new_view.colour) == ("Ana", 0)


def test_ac3_websocket_the_hub_gives_its_resume_window_to_the_join(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    """A short window in the config: the join, not only the tick, applies it.

    The tick period is an hour of real time, so no tick runs: only the join of
    the returning player can time the absent one out.
    """
    config = RoomConfig(
        tick_seconds=3600.0, silence_timeout_seconds=3600, resume_window_seconds=10.0
    )
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
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(11)

        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Ana", a_token)
            assert second_a.snapshot().you != a_id
            peer_b.wait_until(
                lambda: len(player_left_events(peer_b)) == 1,
                "A's time-out on B",
            )
            assert player_left_events(peer_b) == [
                PlayerLeft(seq=4, player_id=a_id, reason=LeaveReason.TIMED_OUT)
            ]


# ---- AC-3: a reload on the live server ---------------------------------------


def test_ac3_browser_a_reload_resumes_the_same_player_without_the_form(
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
        room = room_page(page)
        you_before = room.get_attribute("data-you")
        assert you_before
        cell_at(page, 1, 0).click()
        page.keyboard.press("t")
        expect_cell(page, 1, 0, "T", unconfirmed=False, author=you_before)
        ana_item = page.get_by_test_id("roster-player").filter(
            has=page.get_by_test_id("roster-nickname").get_by_text("Ana", exact=True)
        )
        colour_before = ana_item.get_attribute("data-colour")
        assert colour_before is not None
        page.add_init_script(FORM_WATCHER)

        page.reload()

        expect(room).to_have_attribute("data-status", "joined")
        expect(room).to_have_attribute("data-you", you_before)
        assert page.evaluate("window.__formSeen") is False
        expect(page.get_by_test_id("nickname-form")).to_have_count(0)
        expect(ana_item).to_have_attribute("data-colour", colour_before)
        expect_cell(page, 1, 0, "T", unconfirmed=False, author=you_before)
        bob_roster = bob_page.get_by_test_id("roster-player")
        expect(bob_roster).to_have_count(2)
        bob_view_of_ana = bob_roster.filter(
            has=bob_page.get_by_test_id("roster-nickname").get_by_text(
                "Ana", exact=True
            )
        )
        expect(bob_view_of_ana).to_have_attribute("data-state", "active")
        expect(bob_view_of_ana).to_have_attribute("data-player-id", you_before)
        expect(bob_roster).to_have_count(2)
    finally:
        bob_context.close()


# ---- AC-4: the rules ---------------------------------------------------------


def silent_room(grid: Grid) -> RoomState:
    """Two players; `p1` last seen at NOW, `p2` seen 5 seconds later."""
    return with_player(two_player_room(grid), "p2", last_seen_at=NOW + 5.0)


def test_ac4_the_silence_close_code_is_4408_in_the_hub_and_the_server() -> None:
    assert nock.hub.SILENCE_CLOSE_CODE == SILENCE_CLOSE
    assert nock.server.SILENCE_CLOSE_CODE == SILENCE_CLOSE


def test_ac4_a_tick_5_9_seconds_after_the_last_frame_changes_nothing(
    fx01_grid: Grid,
) -> None:
    room = silent_room(fx01_grid)

    outcome = tick(room, NOW + 5.9)

    assert outcome.state == room
    assert outcome.entries == ()
    assert outcome.disconnects == ()


def test_ac4_a_tick_6_seconds_after_the_last_frame_disconnects_the_player(
    fx01_grid: Grid,
) -> None:
    room = silent_room(fx01_grid)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED)
    ]
    assert outcome.disconnects == (Disconnect(player_id="p1", close_code=4408),)
    assert outcome.state == disconnect_player(room, "p1", NOW + 6.0).state
    silent = player_of(outcome.state, "p1")
    assert silent.state == PlayerState.DISCONNECTED
    assert silent.disconnected_at == NOW + 6.0
    assert player_of(outcome.state, "p2").state == PlayerState.ACTIVE


def test_ac4_an_idle_player_is_disconnected_by_silence_too(fx01_grid: Grid) -> None:
    room = with_player(silent_room(fx01_grid), "p1", state=PlayerState.IDLE)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED)
    ]
    assert outcome.disconnects == (Disconnect(player_id="p1", close_code=4408),)


def test_ac4_a_player_already_disconnected_is_not_disconnected_again(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(silent_room(fx01_grid), "p2", NOW + 1.0).state
    room = keep_seen(room, NOW + 100.0)

    outcome = tick(room, NOW + 100.0)

    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert outcome.state == room


def test_ac4_the_silence_timeout_follows_the_configuration(fx01_grid: Grid) -> None:
    config = RoomConfig(silence_timeout_seconds=2.0)
    room = silent_room(fx01_grid)

    before = tick(room, NOW + 1.75, config)
    at_limit = tick(room, NOW + 2.0, config)

    assert before.entries == ()
    assert at_limit.disconnects == (Disconnect(player_id="p1", close_code=4408),)


def test_ac4_two_silent_players_are_disconnected_in_players_order(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED),
        PlayerStateChanged(seq=4, player_id="p2", state=PlayerState.DISCONNECTED),
    ]
    assert outcome.disconnects == (
        Disconnect(player_id="p1", close_code=4408),
        Disconnect(player_id="p2", close_code=4408),
    )


def test_ac4_a_ping_answers_with_a_pong_and_only_refreshes_last_seen_at(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)
    later = NOW + 4.0

    outcome = handle_message(room, "p1", Ping(), later)

    assert outcome.reply == (Pong(),)
    assert outcome.entries == ()
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False
    assert outcome.state.seq == room.seq
    assert outcome.state.cells == room.cells
    pinged = player_of(outcome.state, "p1")
    assert pinged.last_seen_at == later
    assert pinged.last_input_at == NOW
    assert pinged.state == PlayerState.ACTIVE
    assert player_of(outcome.state, "p2") == player_of(room, "p2")


@pytest.mark.parametrize(
    "message",
    [
        EditLetter(row=1, column=0, letter="T"),
        Erase(row=1, column=1),
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        Undo(),
        Ping(),
    ],
    ids=["edit_letter", "erase", "select_cell", "undo", "ping"],
)
def test_ac4_every_message_of_a_joined_player_sets_last_seen_at(
    fx01_grid: Grid,
    message: EditLetter | Erase | SelectCell | Undo | Ping,
) -> None:
    room = two_player_room(fx01_grid)
    later = NOW + 4.0

    outcome = handle_message(room, "p1", message, later)

    assert player_of(outcome.state, "p1").last_seen_at == later
    assert player_of(outcome.state, "p2").last_seen_at == NOW


def test_ac4_a_player_who_pings_is_not_silent_at_the_tick(fx01_grid: Grid) -> None:
    room = two_player_room(fx01_grid)
    pinged = handle_message(room, "p1", Ping(), NOW + 4.0).state
    pinged = handle_message(pinged, "p2", Ping(), NOW + 4.0).state

    outcome = tick(pinged, NOW + 8.0)

    assert outcome.entries == ()
    assert outcome.disconnects == ()


# ---- AC-4: the hub with a fake clock -----------------------------------------


def test_ac4_websocket_a_ping_before_the_join_gets_a_pong_not_not_joined(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
        peer = Peer(websocket)

        peer.send(Ping())

        peer.wait_until(lambda: len(peer.messages()) >= 1, "the answer to the ping")
        time.sleep(SETTLE_SECONDS)
        assert peer.messages() == [Pong()]
        state = registry.room_state(code)
        assert state is not None
        assert state.players == ()
        peer.send(Join(nickname="Ana", resume_token=None))
        peer.wait_until(lambda: len(peer.messages()) >= 2, "the snapshot")
        assert isinstance(peer.messages()[1], Snapshot)


def test_ac4_websocket_a_ping_after_the_join_gets_a_pong(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        peer = open_peer(stack, client, code, "Ana")

        ping_and_wait(peer)

        assert peer.events() == [Pong()]


def test_ac4_websocket_a_silent_player_is_disconnected_and_their_socket_closed(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(3)
        ping_and_wait(peer_b)

        fake_clock.advance(3)

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's silence on B",
            timeout=WS_DETECTION_SECONDS,
        )
        peer_a.wait_until(
            lambda: peer_a.close_code is not None,
            "the close of A's silent socket",
            timeout=WS_DETECTION_SECONDS,
        )
        assert peer_a.close_code == SILENCE_CLOSE
        assert peer_b.close_code is None
        ping_and_wait(peer_b)
        assert not has_state_change(
            peer_b, peer_b.snapshot().you, PlayerState.DISCONNECTED
        )
        state = registry.room_state(code)
        assert state is not None
        assert player_of(state, a_id).state == PlayerState.DISCONNECTED


def test_ac4_websocket_5_75_seconds_of_silence_changes_nothing_6_does(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(3)
        ping_and_wait(peer_b)
        fake_clock.advance(2.75)
        time.sleep(SETTLE_SECONDS)

        assert not has_state_change(peer_b, a_id, PlayerState.DISCONNECTED)
        assert peer_a.close_code is None

        fake_clock.advance(0.25)

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's silence on B",
            timeout=WS_DETECTION_SECONDS,
        )


def test_ac4_websocket_players_who_ping_every_3_seconds_are_never_disconnected(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(4):
            fake_clock.advance(3)
            ping_and_wait(peer_a)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for peer in (peer_a, peer_b):
            for message in peer.events():
                assert not isinstance(message, PlayerStateChanged)


def send_invalid_frame_and_wait(peer: Peer) -> None:
    """Send a frame that is not a message and wait for the error it gets."""
    errors_before = len(error_events(peer))
    peer.send_raw("this is not a message")
    peer.wait_until(
        lambda: len(error_events(peer)) > errors_before,
        "the error answering an invalid frame",
    )


def test_ac4_websocket_a_player_sending_only_invalid_frames_is_not_silent(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(3):
            fake_clock.advance(3)
            send_invalid_frame_and_wait(peer_a)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for message in peer_b.events():
            assert not isinstance(message, PlayerStateChanged)


def test_ac4_websocket_a_player_sending_only_repeated_joins_is_not_silent(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(3):
            fake_clock.advance(3)
            peer_a.send(Join(nickname="Ana", resume_token=None))
            time.sleep(SETTLE_SECONDS)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for message in peer_b.events():
            assert not isinstance(message, PlayerStateChanged)


def test_ac4_websocket_a_socket_closed_by_the_client_is_seen_without_the_clock(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you

        a_stack.close()

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's closed socket on B",
            timeout=WS_DETECTION_SECONDS,
        )


# ---- AC-4: the roster in the browser -----------------------------------------


def test_ac4_browser_a_state_change_shows_in_the_roster_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    connection = room.connections[0]
    bob = page.locator('[data-testid="roster-player"][data-player-id="p2"]')
    ana = page.locator('[data-testid="roster-player"][data-player-id="p1"]')
    expect(bob).to_have_attribute("data-state", "active")

    connection.send(state_changed_frame(6, "p2", PlayerState.DISCONNECTED))

    expect(bob).to_have_attribute(
        "data-state", "disconnected", timeout=ROSTER_BUDGET_MS
    )
    expect(ana).to_have_attribute("data-state", "active")

    connection.send(state_changed_frame(7, "p2", PlayerState.ACTIVE))

    expect(bob).to_have_attribute("data-state", "active", timeout=ROSTER_BUDGET_MS)


# ---- AC-5: offline edits survive a long absence (browser) --------------------

OFFLINE_EDIT_COUNT = 30
RESEND_PER_WINDOW = 10
RESEND_WINDOW_MS = 1000
SAMPLE_STEP_MS = 100
SAMPLE_SETTLE_MS = 60
RESEND_SPAN_LIMIT_MS = 4000
# Two page-side stand-ins for what Playwright's mocked socket cannot do (its
# `on_close` handler raises a KeyError when the page closes without a code, and
# a mocked socket always opens at once). Both are off unless a test switches
# them on, and other sockets are the real (mocked) ones.
# - `window.__hangNext`: the next socket stays CONNECTING for ever.
# - `window.__deafClose`: `close()` is recorded in `window.__pageCloses` and
#   goes no further: the server side never sees it and the page never gets a
#   `close` event, while messages still arrive (as on a dead network).
SOCKET_STAND_INS_SCRIPT = """
(() => {
  const RealWebSocket = window.WebSocket;
  window.__hangNext = false;
  window.__deafClose = false;
  window.__hung = 0;
  window.__pageCloses = [];
  class HangingSocket extends EventTarget {
    constructor(url) {
      super();
      this.url = String(url);
      this.readyState = 0;
      this.protocol = '';
      this.extensions = '';
      this.bufferedAmount = 0;
      this.binaryType = 'blob';
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
    }
    send() { throw new DOMException('not open', 'InvalidStateError'); }
    close() { this.readyState = 2; }
  }
  class DeafCloseSocket extends EventTarget {
    constructor(url, protocols) {
      super();
      this._ws = protocols === undefined
        ? new RealWebSocket(url) : new RealWebSocket(url, protocols);
      this._closedByPage = false;
      this.onopen = null;
      this.onmessage = null;
      this.onerror = null;
      this.onclose = null;
      for (const type of ['open', 'message', 'error', 'close']) {
        this._ws.addEventListener(type, (event) => this._forward(type, event));
      }
    }
    _forward(type, event) {
      if (type === 'close' && this._closedByPage) { return; }
      let copy = new Event(type);
      if (type === 'message') {
        copy = new MessageEvent('message', { data: event.data });
      }
      if (type === 'close') {
        copy = new CloseEvent('close', { code: event.code, reason: event.reason });
      }
      this.dispatchEvent(copy);
      const handler = this['on' + type];
      if (typeof handler === 'function') { handler.call(this, copy); }
    }
    get url() { return this._ws.url; }
    get protocol() { return this._ws.protocol; }
    get extensions() { return this._ws.extensions; }
    get bufferedAmount() { return this._ws.bufferedAmount; }
    get binaryType() { return this._ws.binaryType; }
    set binaryType(value) { this._ws.binaryType = value; }
    get readyState() { return this._closedByPage ? 2 : this._ws.readyState; }
    send(data) { this._ws.send(data); }
    close(code) {
      this._closedByPage = true;
      window.__pageCloses.push(code === undefined ? null : code);
    }
  }
  function PatchedWebSocket(url, protocols) {
    if (window.__hangNext) {
      window.__hung += 1;
      return new HangingSocket(url);
    }
    if (window.__deafClose) { return new DeafCloseSocket(url, protocols); }
    if (protocols === undefined) { return new RealWebSocket(url); }
    return new RealWebSocket(url, protocols);
  }
  PatchedWebSocket.prototype = RealWebSocket.prototype;
  PatchedWebSocket.CONNECTING = 0;
  PatchedWebSocket.OPEN = 1;
  PatchedWebSocket.CLOSING = 2;
  PatchedWebSocket.CLOSED = 3;
  window.WebSocket = PatchedWebSocket;
})();
"""
DEAF_CLOSE_SCRIPT = SOCKET_STAND_INS_SCRIPT + "window.__deafClose = true;"


def offline_letter(index: int) -> str:
    """Return the letter of the `index`-th offline edit (never twice in a row)."""
    return chr(ord("A") + index % 26)


def edit_summaries(edits: list[Edit]) -> list[tuple[str, int, int, str | None]]:
    """Return (kind, row, column, letter) of each edit, without the base_seq."""
    summaries: list[tuple[str, int, int, str | None]] = []
    for edit in edits:
        if isinstance(edit, EditLetter):
            summaries.append(("edit_letter", edit.row, edit.column, edit.letter))
        else:
            summaries.append(("erase", edit.row, edit.column, None))
    return summaries


def test_ac5_a_silence_loss_does_not_wait_for_the_close_event(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=DEAF_CLOSE_SCRIPT,
    )

    advance_page(page, 4000)

    expect_offline(page)
    assert page.evaluate("window.__pageCloses.length") == 1
    assert len(room.connections) == 1
    expect_new_connection_after(page, room, 1000)
    assert first_join(page, room.connections[1]) == STORED_JOIN


def test_ac5_the_silent_socket_is_detached_and_late_frames_change_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page,
        live_server,
        fx01_grid,
        frozen=True,
        answer_pings=False,
        init_script=DEAF_CLOSE_SCRIPT,
    )
    advance_page(page, 4000)
    expect_offline(page)

    room.connections[0].send(snapshot_frame(fx01_grid, 8))
    page.wait_for_timeout(SETTLE_MS)

    expect_status(page, "reconnecting")
    expect(banner(page)).to_be_visible()
    expect(room_page(page)).to_have_attribute("data-seq", "5")


def test_ac5_the_online_event_forces_a_try_while_a_new_socket_is_connecting(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(
        page, live_server, fx01_grid, frozen=True, init_script=SOCKET_STAND_INS_SCRIPT
    )
    room.connections[0].close(1011)
    expect_offline(page)
    page.evaluate("window.__hangNext = true")

    advance_page(page, 1000)

    wait_until(page, lambda: page.evaluate("window.__hung") == 1)
    assert len(room.connections) == 1
    page.evaluate("window.__hangNext = false")
    page.evaluate("window.dispatchEvent(new Event('online'))")

    room.wait_for_connections(2)
    assert first_join(page, room.connections[1]) == STORED_JOIN
    assert page.evaluate("window.__hung") == 1


def type_offline_edits(page: Page) -> list[Edit]:
    """Type the offline edits on (1, 0) and return the edits expected on the wire."""
    expected: list[Edit] = []
    for index in range(OFFLINE_EDIT_COUNT):
        letter = offline_letter(index)
        cell_at(page, 1, 0).click()
        page.keyboard.press(letter.lower())
        expected.append(EditLetter(row=1, column=0, letter=letter, base_seq=5))
    return expected


def test_ac5_thirty_offline_edits_are_resent_in_order_at_most_10_per_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    expected = type_offline_edits(page)
    expect_new_connection_after(page, room, 1000)
    second = room.connections[1]
    assert second.edits() == []
    # Time 0 is just before the snapshot; the first sample follows it by 1 ms.
    samples: list[tuple[int, int]] = [(0, 0)]
    second.send(snapshot_frame(fx01_grid, 9))
    expect(room_page(page)).to_have_attribute("data-seq", "9")
    page.wait_for_timeout(SETTLE_MS)
    elapsed_ms = 1
    samples.append((elapsed_ms, len(second.edits())))
    while len(second.edits()) < OFFLINE_EDIT_COUNT:
        assert elapsed_ms < RESEND_SPAN_LIMIT_MS, "the 30 edits did not all arrive"
        page.clock.run_for(SAMPLE_STEP_MS)
        page.wait_for_timeout(SAMPLE_SETTLE_MS)
        elapsed_ms += SAMPLE_STEP_MS
        samples.append((elapsed_ms, len(second.edits())))
    advance_page(page, 1000)

    assert second.edits() == expected
    for start_ms, start_count in samples:
        for end_ms, end_count in samples:
            if 0 < end_ms - start_ms <= RESEND_WINDOW_MS:
                sent_in_window = end_count - start_count
                assert sent_in_window <= RESEND_PER_WINDOW, (
                    f"{sent_in_window} edits between {start_ms} and {end_ms} ms "
                    "after the snapshot"
                )
    assert elapsed_ms >= 2500, "the 30 edits were not spread over about 3 seconds"


def test_ac5_the_resend_waits_for_the_snapshot_and_keeps_pending_edits_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5, frozen=True)
    room.connections[0].close(1011)
    expect_offline(page)
    type_offline_edits(page)
    expect_new_connection_after(page, room, 1000)
    second = room.connections[1]

    advance_page(page, 3000)

    assert second.edits() == []
    expect_cell(page, 1, 0, offline_letter(OFFLINE_EDIT_COUNT - 1), unconfirmed=True)


def test_ac5_no_edit_is_sent_between_the_new_socket_and_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    room.connections[0].close(1011)
    expect_offline(page)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN

    page.keyboard.press("a")

    expect_cell(page, 1, 1, "A", unconfirmed=True)
    settle(page)
    assert second.edits() == []
    second.send(snapshot_frame(fx01_grid, 9))
    wait_until(page, lambda: len(second.edits()) >= 2)
    settle(page)
    sent = second.edits()
    assert edit_summaries(sent) == [
        ("edit_letter", 1, 0, "T"),
        ("edit_letter", 1, 1, "A"),
    ]
    assert sent[0] == EditLetter(row=1, column=0, letter="T", base_seq=5)
