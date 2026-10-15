"""Shared setup of the tests of spec 016: same-cell conflicts.

This module is not a test file: pytest does not collect it. The tests of spec 016
are in `tests/test_spec_016_*.py`, one file per criterion group.

AC-1 is checked on `handle_message` (arrival order decides), on the real WebSocket
with two racing clients and on the page with a mocked socket. AC-2 checks the flash
of a replaced letter on the page. AC-3 checks the locked cell on `handle_message`,
on the real WebSocket and on the page.

Not tested here: `pencil_edit` and `confirm_pencil` on a locked cell (spec 020),
`nothing_to_undo` on a locked cell (spec 018), who shows who wrote a letter
(spec 019).

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`registry` and `client` are defined in each file that needs them as thin wrappers
around `grid_from_text`, `make_dist_dir`, `make_registry` and `make_app`: a fixture
imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellView,
    EditLetter,
    Erase,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    grid_view,
    parse_server_message,
)
from nock.room import CellState, RoomConfig, RoomState, join_room, new_room
from nock.server import create_app

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 10.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

Edit = EditLetter | Erase
ChangeList = list[tuple[int, int, dict[str, object]]]
CellValue = tuple[str | None, str | None]  # letter, author


# ---- Fixture bodies ---------------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixture)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_registry() -> RoomRegistry:
    """A registry whose throttle never refuses and that never times a socket out.

    This is the registry of the `registry` fixture, which closes it.
    """
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


def make_app(registry: RoomRegistry, dist_dir: Path) -> FastAPI:
    """An app serving `registry` (the app of the `client` fixture)."""
    return create_app(rooms=registry, dist_dir=dist_dir)


# ---- Room states for handle_message ------------------------------------------


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


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


# ---- Simulated WebSocket clients ----------------------------------------------


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives."""

    def __init__(self, websocket: WebSocketTestSession) -> None:
        self._websocket = websocket
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

    def send(self, message: Join | EditLetter | Erase) -> None:
        self._websocket.send_text(message.model_dump_json())

    def messages(self) -> list[ServerMessage]:
        """Every message received so far, the snapshot first."""
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

    def letter_events(self) -> list[LetterChanged]:
        found: list[LetterChanged] = []
        for message in self.messages()[1:]:
            if isinstance(message, LetterChanged):
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

    def wait_for_letter_events(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.letter_events()) >= count, what)

    def wait_for_errors(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.errors()) >= count, what)

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


def join_peers(
    stack: contextlib.ExitStack, client: TestClient, code: str, names: list[str]
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        websocket = stack.enter_context(
            client.websocket_connect(f"/api/rooms/{code}/ws")
        )
        peer = Peer(websocket)
        peer.send(Join(nickname=name, resume_token=None))
        peer.wait_for_messages(1, f"the snapshot of {name}")
        peers.append(peer)
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def view_cell(peer: Peer, row: int, column: int) -> CellValue:
    """The peer's copy of a cell: its snapshot, then each letter_changed in order."""
    value: CellValue = (None, None)
    for cell in peer.snapshot().grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            value = (cell.letter, cell.author)
    for event in peer.letter_events():
        if (event.row, event.column) == (row, column):
            author = event.player_id if event.letter is not None else None
            value = (event.letter, author)
    return value


# ---- Browser helpers (mocked socket) --------------------------------------------


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self) -> None:
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
    """`p1` (you, colour 0), `p2` (colour 3) and `p3` (colour 5)."""
    return (
        player_view("p1", "Ana", 0),
        player_view("p2", "Bob", 3),
        player_view("p3", "Cleo", 5),
    )


def snapshot_frame(
    view: GridView, seq: int, players: tuple[PlayerView, ...] = ()
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=players,
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
    players: tuple[PlayerView, ...] = (),
    seq: int = 5,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and show FX-01 as `p1` at `seq`."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.frames_without_pings()) > 0)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, seq, players))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


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


def cell_locked_frame(
    seq: int, row: int, column: int, letter: str, revealed: bool
) -> str:
    event = CellLocked(
        seq=seq, row=row, column=column, letter=letter, revealed=revealed
    )
    return event.model_dump_json()


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)
