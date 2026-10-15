"""Shared setup of the tests of spec 023: check a letter, a word or the grid.

This module is not a test file: pytest does not collect it. The tests of spec 023
are in `tests/test_spec_023_*.py`, one file per criterion group:

- `test_spec_023_ac01_ac02_word_letter_grid_rules.py`: AC-1 and AC-2;
- `test_spec_023_ac03_ac04_result_reaches_players.py`: AC-3 and AC-4;
- `test_spec_023_ac05_strike_cleared.py`: AC-5;
- `test_spec_023_ac06_ac07_server_comparison.py`: AC-6 and AC-7;
- `test_spec_023_ac08_ac09_feed_and_controls.py`: AC-8 and AC-9;
- `test_spec_023_ac10_refused_checks.py`: AC-10.

AC-1, AC-2, AC-6 and AC-10 check the rule on `handle_message` (and `replay`). AC-3
and AC-7 check it on the real WebSocket. AC-4 and AC-8 run two browsers on the live
server. AC-5 and AC-9 drive the room page with a mocked socket.

Spec 026 adds to AC-10 the refusal of a check on a solved grid, first in the order
of refusals (before `help_disabled`), and to AC-9 the check buttons disabled once
the grid is solved. Pencil letters (spec 020) are not tested here: no cell holds
one yet.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`catalogue`, `registry`, `room_code` and `client` are defined in each file that
asks for them, as thin wrappers around `grid_from_text`, `make_dist_dir`,
`make_catalogue` and `make_registry`: a fixture imported from here would be an
unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellView,
    Check,
    CheckResult,
    CheckTarget,
    EditLetter,
    Erase,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    Ping,
    PlayerState,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    WordTarget,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    RoomConfig,
    RoomState,
    grid_state,
    handle_message,
    join_room,
    new_room,
)

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
CHECK_NOW = NOW + 10.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 10.0
WAIT_TIMEOUT_MS = 5000

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]

TAMIS = WordTarget(row=0, column=0, clue_index=0)
MIME = WordTarget(row=0, column=2, clue_index=0)


# ---- What the fixtures of the test files are built from ----


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


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


# ---- Room states for handle_message ----


def two_player_room(grid: Grid) -> RoomState:
    """A room with players `p1` and `p2` (seq 2), every cell empty."""
    state = new_room(ROOM_CODE, grid, START_TIME)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    assert second.state.seq == 2
    return second.state


S1_EDITS: list[tuple[str, int, int, str]] = [
    ("p1", 1, 0, "T"),
    ("p1", 1, 1, "X"),
    ("p1", 1, 3, "I"),
    ("p1", 1, 4, "S"),
    ("p2", 2, 1, "V"),
    ("p2", 2, 2, "Q"),
]


def write_letter(
    state: RoomState, player_id: str, row: int, column: int, letter: str
) -> RoomState:
    edit = EditLetter(row=row, column=column, letter=letter)
    outcome = handle_message(state, player_id, edit, NOW)
    assert outcome.reply == ()
    return outcome.state


def s1_room(grid: Grid) -> RoomState:
    """The room `S1` of the spec: seq 8, six letters written."""
    state = two_player_room(grid)
    for player_id, row, column, letter in S1_EDITS:
        state = write_letter(state, player_id, row, column, letter)
    assert state.seq == 8
    return state


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


def refs(*cells: Cell) -> tuple[CellRef, ...]:
    return tuple(CellRef(row=row, column=column) for row, column in cells)


def check(state: RoomState, target: CheckTarget, player_id: str = "p1") -> list[object]:
    """Run a check and return its events, after checking nothing was refused."""
    outcome = handle_message(state, player_id, Check(target=target), CHECK_NOW)
    assert outcome.reply == ()
    return [entry.event for entry in outcome.entries]


# ---- Helpers for the WebSocket tests ----


class Earned(NamedTuple):
    """Log item: the test sent `letter` to a cell, so the room may show it."""

    row: int
    column: int
    letter: str


class Seen(NamedTuple):
    """Log item: a frame reached a client."""

    source: str
    text: str


class TrafficLog:
    """The ordered record of what the test sent and what the clients received."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[Earned | Seen] = []

    def earn(self, row: int, column: int, letter: str) -> None:
        with self._lock:
            self._items.append(Earned(row, column, letter))

    def see(self, source: str, text: str) -> None:
        with self._lock:
            self._items.append(Seen(source, text))

    def items(self) -> list[Earned | Seen]:
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
                self._log.see(self.name, text)
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

    def send(self, message: Join | EditLetter | Erase | Check) -> None:
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

    def check_results(self) -> list[CheckResult]:
        found: list[CheckResult] = []
        for message in self.messages()[1:]:
            if isinstance(message, CheckResult):
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
    websocket = stack.enter_context(client.websocket_connect(f"/api/rooms/{code}/ws"))
    return Peer(websocket, name, log)


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
        peer = connect(stack, client, code, name, log)
        peer.send(Join(nickname=name, resume_token=None))
        peer.wait_for_messages(1, f"the snapshot of {name}")
        peers.append(peer)
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


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


def wait_until_page(page: Page, condition: Callable[[], bool]) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def player_view(player_id: str, nickname: str, colour: int) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=player_id == "p1",
        muted=False,
        selection=None,
    )


def default_players() -> tuple[PlayerView, ...]:
    return (player_view("p1", "Ana", 0), player_view("p2", "Bob", 3))


def snapshot_frame(
    view: GridView,
    seq: int,
    players: tuple[PlayerView, ...],
    help_mode: HelpMode = HelpMode.FREE,
    solved: bool = False,
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=players,
        settings=RoomSettings(
            help_mode=help_mode,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        ),
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )
    return snapshot.model_dump_json()


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


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList | None = None,
    help_mode: HelpMode = HelpMode.FREE,
    seq: int = 5,
    solved: bool = False,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and show FX-01 as `p1` at `seq`."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.received) > 0)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, seq, default_players(), help_mode, solved))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def sent_letters(mock: MockRoomSocket) -> list[EditLetter]:
    edits: list[EditLetter] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter):
            edits.append(message)
    return edits


def strike_through(cell: Locator) -> str:
    """The computed text-decoration-line of a cell element."""
    line = cell.evaluate("el => getComputedStyle(el).textDecorationLine")
    assert isinstance(line, str)
    return line


# ---- A flow of two browsers on the live server (AC-4 and AC-8) ----


def play_ana_checks_the_word(
    page: Page, bob_page: Page, url: str, enter_room: EnterRoom
) -> None:
    enter_room(page, url, "Ana")
    enter_room(bob_page, url, "Bob")
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    page.keyboard.press("x")
    expect(cell_at(bob_page, 1, 1)).to_have_attribute("data-letter", "X")
    page.get_by_test_id("check-word").click()
