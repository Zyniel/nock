"""Shared setup of the tests of spec 024: reveal a letter or a word.

This module is not a test file: pytest does not collect it. The tests of spec 024
are in `tests/test_spec_024_*.py`, one file per criterion group:

- `test_spec_024_ac01_revealed_cell.py`: AC-1 (rule, WebSocket, live pages);
- `test_spec_024_ac02_ac03_budget.py`: AC-2 and AC-3 (rule, WebSocket, page with a
  mocked socket);
- `test_spec_024_ac04_refused_reveals.py`: AC-4 (rule, WebSocket);
- `test_spec_024_ac05_traffic.py`: AC-5 (the extended traffic checker, the full
  game on the WebSocket and in browsers on the live server);
- `test_spec_024_ac06_completion.py`: AC-6 (rule, WebSocket);
- `test_spec_024_ac07_controls.py`: AC-7 (page with a mocked socket);
- `test_spec_024_ac08_toolbar.py`: AC-8 (page with a mocked socket, every window);
- `test_spec_024_ac09_revealed_mark_a11y.py`: AC-9 (page with a mocked socket);
- `test_spec_024_ac10_reload.py`: AC-10 (`replay` and `RoomStore`).

It holds what more than one of those files uses: the rooms `R1` and `FULL17` of
the spec, the simulated WebSocket client with its traffic log, the mocked room
socket, the check of the corner mark, and thin wrappers around spec 035's keyboard
walker and scans and spec 013's desktop and touch contexts (the spec says to reuse
them). What only one file uses stays in that file. The fixtures (`fx01_grid`,
`dist_dir`, `catalogue`, `registry`, `room_code`, `client`) are defined in each
file that asks for them, as thin wrappers around `grid_from_text`,
`make_dist_dir`, `make_catalogue` and `make_registry`: a fixture imported from here
would be an unused import for ruff.

Not tested, as the spec says: pencil letters (spec 020 is not built, so no cell
holds one) and the help mode `vote` (spec 025 changes it).
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    CellView,
    ChangeSettings,
    Check,
    ClientMessage,
    EditLetter,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    Ping,
    PlayerState,
    PlayerView,
    Pong,
    Reveal,
    RevealBudget,
    RevealResult,
    RoomSettings,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    WordTarget,
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
    grid_state,
    handle_message,
    join_room,
    new_room,
)
from spec013_harness import make_page
from spec035_harness import (
    FX01_CLUES,
    LANGUAGE_SCAN_SCRIPT,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    Walker,
    contrast_offenders,
    unknown_texts,
)

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
ROOM_CODE = "ABC123"
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 10.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
QUIET_MS = 300  # "no frame within 300 ms" (AC-3)
KEY_PAUSE_MS = 60

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]
RevealTargetArg = CellTarget | WordTarget

DEFAULT_BUDGET = RevealBudget(letters=5, words=1)
TAMIS = WordTarget(row=0, column=0, clue_index=0)
MIME = WordTarget(row=0, column=2, clue_index=0)
MIME_CELLS: list[Cell] = [(1, 2), (2, 2), (3, 2), (4, 2)]

# The solution of FX-01 (specs/_reference.md), by cell.
SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter
ROW_MAJOR: list[Cell] = sorted(SOLUTION)
LAST_CELL: Cell = (4, 4)
FIRST_17: list[Cell] = [cell for cell in ROW_MAJOR if cell != LAST_CELL]


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


# ---- What the fixtures of the test files are built from ----


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixtures)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_catalogue(grid: Grid) -> Catalogue:
    """A catalogue holding `grid` as published entry 1 (the `catalogue` fixtures)."""
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=grid,
    )
    return Catalogue(entries=(entry,))


def make_registry() -> RoomRegistry:
    """A registry whose throttle never refuses and that never times a socket out."""
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


def load_fr() -> dict[str, str]:
    """Return the French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fr_count(key: str, count: int) -> str:
    """The `fr.json` text of `key` with `{count}` filled in."""
    return load_fr()[key].replace("{count}", str(count))


# ---- Room states for handle_message ----


def joined_room(grid: Grid) -> tuple[RoomState, list[LogEntry]]:
    """A room created at NOW where `p1` (Ana, host) then `p2` (Bob) joined: seq 2.

    Returns:
        The state and the logged entries of the two joins.
    """
    state = new_room(ROOM_CODE, grid, NOW)
    entries: list[LogEntry] = []
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    entries.extend(first.entries)
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    entries.extend(second.entries)
    assert second.state.seq == 2
    return second.state, entries


def two_player_room(grid: Grid) -> RoomState:
    """A FX-01 room with `p1` (host) and `p2`, every cell empty (seq 2)."""
    state, _ = joined_room(grid)
    return state


def write(
    state: RoomState,
    player_id: str,
    row: int,
    column: int,
    letter: str,
    now: float = NOW,
) -> Outcome:
    """Write a letter with `handle_message`, after checking it was accepted."""
    edit = EditLetter(row=row, column=column, letter=letter)
    outcome = handle_message(state, player_id, edit, now)
    assert outcome.reply == (), outcome.reply
    return outcome


R1_EDITS: list[tuple[str, int, int, str]] = [
    ("p1", 1, 0, "T"),
    ("p1", 1, 1, "X"),
    ("p2", 2, 2, "I"),
]


def r1_with_entries(grid: Grid) -> tuple[RoomState, list[LogEntry]]:
    """The room `R1` of the spec (seq 5) and every entry logged to build it."""
    state, entries = joined_room(grid)
    for player_id, row, column, letter in R1_EDITS:
        outcome = write(state, player_id, row, column, letter)
        entries.extend(outcome.entries)
        state = outcome.state
    assert state.seq == 5
    return state, entries


def r1_room(grid: Grid) -> RoomState:
    """The room `R1` of the spec: seq 5, budget 5 letters and 1 word."""
    state, _ = r1_with_entries(grid)
    return state


def full17(grid: Grid, wrong_at: Cell | None = None) -> RoomState:
    """The room `FULL17` of spec 026: `p1` wrote the 17 letters other than (4, 4).

    Args:
        grid: FX-01.
        wrong_at: A cell where `p1` writes `X` instead of its solution letter.
    """
    state = two_player_room(grid)
    for row, column in FIRST_17:
        letter = SOLUTION[(row, column)]
        if (row, column) == wrong_at:
            letter = "X"
        state = write(state, "p1", row, column, letter).state
    assert state.seq == 19
    assert state.solved is False
    return state


def reveal(
    state: RoomState,
    target: RevealTargetArg,
    player_id: str = "p1",
    now: float = NOW,
) -> Outcome:
    """Send `Reveal(target)` from a player with `handle_message`."""
    return handle_message(state, player_id, Reveal(target=target), now)


def accepted_reveal(
    state: RoomState,
    target: RevealTargetArg,
    player_id: str = "p1",
    now: float = NOW,
) -> Outcome:
    """Reveal, after checking the reveal was not refused."""
    outcome = reveal(state, target, player_id, now)
    assert outcome.reply == (), outcome.reply
    return outcome


def events_of(outcome: Outcome) -> list[object]:
    """The event of each log entry of a step, in order."""
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    return events


def refusal_code(outcome: Outcome) -> ErrorCode:
    """The code of the single error answering a step, after checking it is alone."""
    assert len(outcome.reply) == 1, outcome.reply
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def cell_view(state: RoomState, row: int, column: int) -> LetterCellView:
    for cell in grid_state(state).cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell
    pytest.fail(f"no letter cell view at ({row}, {column})")


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


def host_changes(
    state: RoomState,
    help_mode: HelpMode,
    letters: int,
    words: int,
    now: float = NOW,
) -> RoomState:
    """The room after `p1` (host) sent `ChangeSettings`, checked as accepted."""
    change = ChangeSettings(
        help_mode=help_mode, reveal_budget=RevealBudget(letters=letters, words=words)
    )
    outcome = handle_message(state, "p1", change, now)
    assert outcome.reply == (), outcome.reply
    return outcome.state


def check_cell(state: RoomState, row: int, column: int) -> RoomState:
    """The room after `p1` checked one cell (spec 023), checked as accepted."""
    target = CellTarget(row=row, column=column)
    outcome = handle_message(state, "p1", Check(target=target), NOW)
    assert outcome.reply == (), outcome.reply
    return outcome.state


def seen_at(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state with only `last_seen_at` and `last_input_at` of one player set."""
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == player_id:
            player = player.model_copy(
                update={"last_seen_at": now, "last_input_at": now}
            )
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


# ---- Helpers for the WebSocket tests ----


class Earned(NamedTuple):
    """Log item: the test sent `letter` to a cell, so the room may show it."""

    row: int
    column: int
    letter: str


class Received(NamedTuple):
    """Log item: a WebSocket frame reached a client."""

    client: str
    text: str


class HttpBody(NamedTuple):
    """Log item: an HTTP response body reached a browser."""

    source: str
    text: str


TrafficItem = Earned | Received | HttpBody


class TrafficLog:
    """The ordered record of what the test sent and what the browsers received."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[TrafficItem] = []

    def earn(self, row: int, column: int, letter: str) -> None:
        """Record that the test is about to type `letter` at a cell."""
        with self._lock:
            self._items.append(Earned(row, column, letter))

    def receive(self, client: str, text: str) -> None:
        """Record one WebSocket frame received by `client`."""
        with self._lock:
            self._items.append(Received(client, text))

    def http_body(self, source: str, text: str) -> None:
        """Record one HTTP response body."""
        with self._lock:
            self._items.append(HttpBody(source, text))

    def items(self) -> list[TrafficItem]:
        with self._lock:
            return list(self._items)


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives."""

    def __init__(
        self,
        websocket: WebSocketTestSession,
        name: str = "peer",
        log: TrafficLog | None = None,
    ) -> None:
        self._websocket = websocket
        self.name = name
        self._log = log
        self._arrived = threading.Condition()
        self._received: list[ServerMessage] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except BaseException:  # the socket closed at the end of the test
                return
            if self._log is not None:
                self._log.receive(self.name, text)
            try:
                message = parse_server_message(text)
            except ValueError as error:
                self._keep_failure(f"unparsable message {text!r}: {error}")
                continue
            with self._arrived:
                self._received.append(message)
                self._arrived.notify_all()

    def _keep_failure(self, text: str) -> None:
        with self._arrived:
            self._failures.append(text)
            self._arrived.notify_all()

    def send(self, message: ClientMessage) -> None:
        self._websocket.send_text(message.model_dump_json())

    def send_text(self, text: str) -> None:
        self._websocket.send_text(text)

    def messages(self) -> list[ServerMessage]:
        with self._arrived:
            return list(self._received)

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def you(self) -> str:
        return self.snapshot().you

    def last_seq(self) -> int:
        last = self.snapshot().seq
        for message in self.messages()[1:]:
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

    def reveal_results(self) -> list[RevealResult]:
        found: list[RevealResult] = []
        for message in self.messages()[1:]:
            if isinstance(message, RevealResult):
                found.append(message)
        return found

    def cell_locks(self) -> list[CellLocked]:
        found: list[CellLocked] = []
        for message in self.messages()[1:]:
            if isinstance(message, CellLocked):
                found.append(message)
        return found

    def errors(self) -> list[ErrorMessage]:
        found: list[ErrorMessage] = []
        for message in self.messages()[1:]:
            if isinstance(message, ErrorMessage):
                found.append(message)
        return found

    def pong_count(self) -> int:
        count = 0
        for message in self.messages():
            if isinstance(message, Pong):
                count += 1
        return count

    def wait_for_messages(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.messages()) >= count, what)

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

    def wait_until(self, condition: Callable[[], bool], what: str) -> None:
        """Wait up to WAIT_SECONDS for `condition`, else fail the test."""
        with self._arrived:
            met = self._arrived.wait_for(
                lambda: condition() or len(self._failures) > 0, WAIT_SECONDS
            )
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])
        if not met:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")


def connect(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    name: str,
    log: TrafficLog | None = None,
) -> Peer:
    """Open a socket to the room and start its reader; the peer has not joined."""
    websocket = stack.enter_context(client.websocket_connect(f"/api/rooms/{code}/ws"))
    return Peer(websocket, name, log)


def join_one(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    name: str,
    log: TrafficLog | None = None,
) -> Peer:
    """Connect and join one peer; return once its snapshot arrived."""
    peer = connect(stack, client, code, name, log)
    peer.send(Join(nickname=name, resume_token=None))
    peer.wait_for_messages(1, f"the snapshot of {name}")
    return peer


def join_peers(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    names: list[str],
    log: TrafficLog | None = None,
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        peers.append(join_one(stack, client, code, name, log))
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def ping_and_wait(peer: Peer) -> None:
    """Send a ping and wait for its pong: the room handled everything sent before."""
    before = peer.pong_count()
    peer.send(Ping())
    peer.wait_until(lambda: peer.pong_count() > before, "the pong of a ping")


def snapshot_cell(snapshot: Snapshot, row: int, column: int) -> LetterCellView:
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


# ---- Helpers for the browser tests ----


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


def expect_seq(page: Page, seq: int) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the route
    that sent it: without the answer, the page takes 4 s without a frame from the
    server for a lost connection (spec 017, AC-4), so a step that takes longer on a
    slow engine would find the page `reconnecting`.
    """

    def __init__(self) -> None:
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

    def frames_without_pings(self) -> list[str]:
        """The frames the page sent, without its keep-alive `ping` frames.

        The page sends a `ping` every 2 s once the socket is open (spec 017), so
        one can fall between two reads whatever the test does.
        """
        frames: list[str] = []
        for frame in self.received:
            if json.loads(frame)["type"] != "ping":
                frames.append(frame)
        return frames

    def reveals(self) -> list[Reveal]:
        """Every `reveal` the page sent, parsed."""
        found: list[Reveal] = []
        for frame in self.frames_without_pings():
            message = parse_client_message(frame)
            if isinstance(message, Reveal):
                found.append(message)
        return found

    def raw_reveals(self) -> list[object]:
        """Every `reveal` the page sent, as plain JSON values."""
        found: list[object] = []
        for frame in self.frames_without_pings():
            parsed = json.loads(frame)
            if parsed["type"] == "reveal":
                found.append(parsed)
        return found

    def edit_count(self) -> int:
        count = 0
        for frame in self.frames_without_pings():
            if json.loads(frame)["type"] == "edit_letter":
                count += 1
        return count


def wait_until_page(
    page: Page, condition: Callable[[], bool], what: str = "the page"
) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"timed out waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50


def player_view(
    player_id: str, nickname: str, colour: int, *, is_host: bool = False
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


def default_players() -> list[PlayerView]:
    """`p1` (Ana, `you`, host) and `p2` (Bob)."""
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)]


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
    view: GridView,
    seq: int,
    players: list[PlayerView],
    help_mode: HelpMode,
    left: RevealBudget,
    allowance: RevealBudget,
    solved: bool,
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=tuple(players),
        settings=RoomSettings(
            help_mode=help_mode, reveal_budget=allowance, locked=False
        ),
        reveal_budget=left,
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )
    return snapshot.model_dump_json()


def open_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    changes: ChangeList | None = None,
    players: list[PlayerView] | None = None,
    seq: int = 5,
    help_mode: HelpMode = HelpMode.FREE,
    left: RevealBudget = DEFAULT_BUDGET,
    allowance: RevealBudget = DEFAULT_BUDGET,
    solved: bool = False,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and show FX-01 as `p1` at `seq`.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        grid: FX-01.
        changes: Updates of letter cells of the snapshot.
        players: The roster (default: `p1` host and `p2`).
        seq: The snapshot's seq.
        help_mode: The snapshot's help mode.
        left: The snapshot's `reveal_budget` (what is left).
        allowance: The snapshot's `settings.reveal_budget`.
        solved: The snapshot's `solved`.
    """
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.frames_without_pings()) > 0, "the join")
    view = grid_view(grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    shown_players = default_players() if players is None else players
    frame = snapshot_frame(view, seq, shown_players, help_mode, left, allowance, solved)
    mock.send(frame)
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def reveal_result_frame(
    seq: int, target: RevealTargetArg, left: RevealBudget, player_id: str = "p2"
) -> str:
    event = RevealResult(
        seq=seq, player_id=player_id, target=target, reveal_budget=left
    )
    return event.model_dump_json()


def settings_changed_frame(
    seq: int, help_mode: HelpMode, allowance: RevealBudget, left: RevealBudget
) -> str:
    settings = RoomSettings(help_mode=help_mode, reveal_budget=allowance, locked=False)
    event = SettingsChanged(
        seq=seq, player_id="p1", settings=settings, reveal_budget=left
    )
    return event.model_dump_json()


def cell_locked_frame(
    seq: int, row: int, column: int, letter: str, revealed: bool
) -> str:
    event = CellLocked(
        seq=seq, row=row, column=column, letter=letter, revealed=revealed
    )
    return event.model_dump_json()


def computed(locator: Locator, property_name: str) -> str:
    """The computed style property `property_name` (camelCase) of an element."""
    value = locator.evaluate(f"el => getComputedStyle(el).{property_name}")
    assert isinstance(value, str)
    return value


# ---- The corner mark of a revealed cell ("Client: revealed cells") ----

# The colour helpers of spec 035's harness (parseColour, over, contrast, WHITE and
# readFocusOutline), shared with the tests of specs 014 and 035.
COLOUR_CONTRAST_JS = (Path(__file__).parent / "colour_contrast.js").read_text(
    encoding="utf-8"
)

# What the rules of the corner mark need, measured on the `cell` element. A
# translucent colour is composited as spec 035's contrast scan does: the cell's
# computed background over white, the mark's over the cell's.
MARK_SCRIPT = "cell => {\n" + COLOUR_CONTRAST_JS + r"""
  const marks = cell.querySelectorAll('[data-testid="reveal-mark"]');
  const result = {marks: marks.length};
  if (marks.length !== 1) {
    return result;
  }
  const mark = marks[0];
  const cellBox = cell.getBoundingClientRect();
  const markBox = mark.getBoundingClientRect();
  const markStyle = getComputedStyle(mark);
  const cellBackground = over(
    parseColour(getComputedStyle(cell).backgroundColor), WHITE
  );
  const markColour = over(parseColour(markStyle.backgroundColor), cellBackground);
  result.ariaHidden = mark.getAttribute('aria-hidden');
  result.text = mark.textContent;
  result.visibility = markStyle.visibility;
  result.cell = [cellBox.left, cellBox.top, cellBox.right, cellBox.bottom];
  result.mark = [markBox.left, markBox.top, markBox.right, markBox.bottom];
  result.ratio = contrast(markColour, cellBackground);
  return result;
}
"""
MARK_TOLERANCE_PX = 1.0
MARK_EDGE_PX = 4.0
MARK_MIN_PX = 6.0
MARK_MIN_CONTRAST = 3.0


def read_mark(cell: Locator) -> dict[str, Any]:
    """Measure the `reveal-mark` of a cell (a JSON object from the page)."""
    reading = cell.evaluate(MARK_SCRIPT)
    assert isinstance(reading, dict)
    return reading


def mark_contrast(cell: Locator) -> float:
    """The contrast of the cell's mark colour against the cell's background."""
    reading = read_mark(cell)
    assert reading["marks"] == 1, reading
    return float(reading["ratio"])


def mark_problems(cell: Locator) -> list[str]:
    """How the cell's `reveal-mark` breaks the rules of "Client: revealed cells"."""
    reading = read_mark(cell)
    if reading["marks"] != 1:
        return [f"{reading['marks']} reveal-mark elements in the cell"]
    problems: list[str] = []
    if reading["ariaHidden"] != "true":
        problems.append(f"aria-hidden is {reading['ariaHidden']!r}")
    if reading["text"].strip() != "":
        problems.append(f"the mark holds the text {reading['text']!r}")
    if reading["visibility"] != "visible":
        problems.append(f"visibility is {reading['visibility']!r}")
    cell_left, cell_top, cell_right, cell_bottom = reading["cell"]
    mark_left, mark_top, mark_right, mark_bottom = reading["mark"]
    inside = (
        mark_left >= cell_left - MARK_TOLERANCE_PX
        and mark_top >= cell_top - MARK_TOLERANCE_PX
        and mark_right <= cell_right + MARK_TOLERANCE_PX
        and mark_bottom <= cell_bottom + MARK_TOLERANCE_PX
    )
    if not inside:
        problems.append(f"mark {reading['mark']} outside cell {reading['cell']}")
    if abs(cell_right - mark_right) > MARK_EDGE_PX:
        problems.append(f"right edge {mark_right} is far from {cell_right}")
    if abs(mark_top - cell_top) > MARK_EDGE_PX:
        problems.append(f"top edge {mark_top} is far from {cell_top}")
    min_width = max(MARK_MIN_PX, (cell_right - cell_left) / 4)
    min_height = max(MARK_MIN_PX, (cell_bottom - cell_top) / 4)
    if mark_right - mark_left < min_width:
        problems.append(f"width {mark_right - mark_left} below {min_width}")
    if mark_bottom - mark_top < min_height:
        problems.append(f"height {mark_bottom - mark_top} below {min_height}")
    if reading["ratio"] < MARK_MIN_CONTRAST:
        problems.append(f"contrast {reading['ratio']} below 3:1")
    return problems


# ---- Spec 035's keyboard walker and scans, spec 013's contexts (reused) ----


def make_walker(page: Page) -> Walker:
    """Spec 035's keyboard walker (`tab_to`) on a page."""
    return Walker(page)


def outline_problems(style: str, width: float, ratio: float) -> list[str]:
    """How a focus outline breaks spec 035 AC-2 (style, 2 px, 3:1 against white)."""
    problems: list[str] = []
    if style in ("none", "auto"):
        problems.append(f"outline style {style!r}")
    if width < MIN_OUTLINE_PX:
        problems.append(f"outline width {width}")
    if ratio < MIN_FOCUS_CONTRAST:
        problems.append(f"outline contrast {ratio}")
    return problems


def contrast_problems(page: Page) -> list[dict[str, Any]]:
    """Spec 035's contrast scan (AC-8): the elements under 4.5:1."""
    return contrast_offenders(page)


def language_problems(page: Page, data: set[str]) -> list[str]:
    """Spec 035's language scan (AC-9): the texts that are not French or data."""
    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    assert len(texts) > 0, "the language scan found no text at all"
    return unknown_texts(texts, data)


def language_data(base_url: str, nicknames: list[str]) -> set[str]:
    """The data of a room page that the language scan accepts."""
    data: set[str] = {ROOM_CODE, f"{base_url}/r/{ROOM_CODE}", *FX01_CLUES}
    for nickname in nicknames:
        data.add(nickname)
        data.add(nickname[:2].upper())
    return data


def open_context_page(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> tuple[Page, Callable[[], None]]:
    """A desktop or touch page of spec 013's harness; return it and its closer."""
    return make_page(browser, browser_name, width, height, touch)
