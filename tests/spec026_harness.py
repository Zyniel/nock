"""Shared setup of the tests of spec 026: completion detection.

This module is not a test file: pytest does not collect it. The tests of spec 026
are in `tests/test_spec_026_*.py`, one file per criterion group:

- `test_spec_026_ac01_ac03_grid_solved.py`: the grid becomes solved (rule,
  WebSocket, live pages).
- `test_spec_026_ac04_ac05_input_locked.py`: input is locked once solved (rule,
  WebSocket, page with a mocked socket).
- `test_spec_026_ac06_ac07_grid_full_wrong.py`: a full grid with a wrong letter
  (rule, WebSocket, page with a mocked socket, live pages).
- `test_spec_026_ac08_ac09_letters_and_reload.py`: the 18 letters of FX-01 and
  the solved state after a reload (rule, `replay`, `RoomStore`).

AC-1, AC-4, AC-6 (rule part), AC-8 and AC-9 check the rule on `handle_message`,
`replay` and `RoomStore`. AC-2 and AC-6 (WebSocket part) use the real WebSocket
with three simulated clients. AC-3 and AC-7 (live part) run two browsers on the
live server. AC-5 and AC-7 (mocked part) drive the room page with a mocked socket.

Not tested here: the completion by a reveal (spec 024 is not built) and the effect
of pencil letters (spec 020 is not built). The completion by an undo is tested
because spec 018 is built.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`registry`, `room_code` and `client` are defined in each file that needs them, as
thin wrappers around `grid_from_text`, `make_dist_dir`, `make_registry` and
`make_client`: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    Check,
    EditLetter,
    Erase,
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
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    Undo,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    Outcome,
    RoomConfig,
    RoomState,
    handle_message,
    join_room,
    new_room,
)
from nock.server import create_app

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
KEY_PAUSE_MS = 60

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]

# The solution of FX-01 (specs/_reference.md), in row-major order.
SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter
LAST_CELL: Cell = (4, 4)
ROW_MAJOR: list[Cell] = sorted(SOLUTION)
FIRST_17: list[Cell] = [position for position in ROW_MAJOR if position != LAST_CELL]
assert len(ROW_MAJOR) == 18
assert ROW_MAJOR[-1] == LAST_CELL

# Keys of a browser game, in the order of spec 037: the 17 letters other than
# (4, 4), typed word by word.
BROWSER_FIRST_17: list[tuple[int, int, str]] = [
    (1, 0, "t"),
    (1, 1, "a"),
    (1, 2, "m"),
    (1, 3, "i"),
    (1, 4, "s"),
    (0, 1, "n"),
    (2, 1, "v"),
    (3, 1, "a"),
    (4, 1, "l"),
    (2, 2, "i"),
    (3, 2, "m"),
    (4, 2, "e"),
    (2, 3, "d"),
    (3, 3, "e"),
    (4, 3, "s"),
    (2, 4, "e"),
    (3, 4, "n"),
]


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


# ---- Fixture helpers: the fixtures themselves are in the test files ----


def grid_from_text(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def make_dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_registry() -> RoomRegistry:
    """A registry whose throttle never refuses and that never times a socket out."""
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


def make_client(registry: RoomRegistry, dist_dir: Path) -> TestClient:
    """A TestClient (one event loop) on an app serving `registry`.

    The caller enters it with `with`, so the app runs for the length of the test.
    """
    app = create_app(rooms=registry, dist_dir=dist_dir)
    return TestClient(app)


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Room states for handle_message ----


def two_player_room(grid: Grid) -> RoomState:
    """A room created at NOW with players `p1` and `p2` (seq 2), all cells empty."""
    state = new_room(ROOM_CODE, grid, NOW)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    assert second.state.seq == 2
    return second.state


def write(
    state: RoomState,
    player_id: str,
    position: Cell,
    letter: str,
    now: float = NOW,
) -> Outcome:
    """Write a letter with `handle_message`, after checking it was accepted."""
    edit = EditLetter(row=position[0], column=position[1], letter=letter)
    outcome = handle_message(state, player_id, edit, now)
    assert outcome.reply == ()
    return outcome


def events_of(outcome: Outcome) -> list[object]:
    return [entry.event for entry in outcome.entries]


def full17(grid: Grid) -> RoomState:
    """The room `FULL17`: `p1` wrote the 17 right letters other than (4, 4)."""
    state = two_player_room(grid)
    for position in FIRST_17:
        state = write(state, "p1", position, SOLUTION[position]).state
    assert state.seq == 19
    assert state.solved is False
    return state


def solved_room(grid: Grid) -> RoomState:
    """The solved state of AC-1: `p2` wrote `T` at (4, 4) (seq 21)."""
    state = write(full17(grid), "p2", LAST_CELL, "T", NOW + 754.0).state
    assert state.solved is True
    assert state.seq == 21
    return state


def refusal_code(outcome: Outcome) -> ErrorCode:
    """The code of the single error answering a step, after checking it is alone."""
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


# ---- WebSocket clients: AC-2, AC-4 and AC-6 ----


class Peer:
    """A simulated client: one socket, one reader thread keeping what arrives."""

    def __init__(self, websocket: WebSocketTestSession, name: str) -> None:
        self._websocket = websocket
        self.name = name
        self._arrived = threading.Condition()
        self._received: list[tuple[float, str, ServerMessage]] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except BaseException:  # the socket closed at the end of the test
                return
            received_at = time.monotonic()
            try:
                message = parse_server_message(text)
            except ValueError as error:
                self._keep_failure(f"unparsable message {text!r}: {error}")
                continue
            with self._arrived:
                self._received.append((received_at, text, message))
                self._arrived.notify_all()

    def _keep_failure(self, text: str) -> None:
        with self._arrived:
            self._failures.append(text)
            self._arrived.notify_all()

    def send(self, message: Join | EditLetter | Erase | Undo | Check) -> None:
        self._websocket.send_text(message.model_dump_json())

    def received(self) -> list[tuple[float, str, ServerMessage]]:
        with self._arrived:
            return list(self._received)

    def messages(self) -> list[ServerMessage]:
        return [message for _, _, message in self.received()]

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def last_seq(self) -> int:
        last = self.snapshot().seq
        for message in self.messages()[1:]:
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

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


def join_peers(
    stack: contextlib.ExitStack, client: TestClient, code: str, names: list[str]
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        websocket = stack.enter_context(
            client.websocket_connect(f"/api/rooms/{code}/ws")
        )
        peer = Peer(websocket, name)
        peer.send(Join(nickname=name, resume_token=None))
        peer.wait_for_messages(1, f"the snapshot of {name}")
        peers.append(peer)
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def type_17_letters(ana: Peer, bob: Peer, peers: list[Peer]) -> None:
    """Ana types the first 9 right letters and Bob the next 8, each batch awaited."""
    for position in FIRST_17[:9]:
        row, column = position
        ana.send(EditLetter(row=row, column=column, letter=SOLUTION[position]))
    for peer in peers:
        peer.wait_for_seq(3 + 9, f"Ana's 9 letters on {peer.name}")
    for position in FIRST_17[9:]:
        row, column = position
        bob.send(EditLetter(row=row, column=column, letter=SOLUTION[position]))
    for peer in peers:
        peer.wait_for_seq(3 + 17, f"Bob's 8 letters on {peer.name}")


# ---- Browsers on the live server: AC-3 and AC-7 ----


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


def play_live_game(
    page: Page, bob_page: Page, url: str, enter_room: EnterRoom, last_key: str
) -> None:
    """Ana types the 17 letters; Bob taps (4, 4) and types `last_key`."""
    enter_room(page, url, "Ana")
    enter_room(bob_page, url, "Bob")
    for row, column, key in BROWSER_FIRST_17:
        cell_at(page, row, column).click()
        page.keyboard.press(key)
        page.wait_for_timeout(KEY_PAUSE_MS)
    expect(cell_at(bob_page, 3, 4)).to_have_attribute(
        "data-letter", "N", timeout=WAIT_TIMEOUT_MS
    )
    cell_at(bob_page, 4, 4).click()
    bob_page.keyboard.press(last_key)


# ---- Browser with a mocked socket: AC-5 and AC-7 ----


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

    def sent_types(self) -> list[str]:
        """The `type` of every frame the page sent but its `ping` frames."""
        types: list[str] = []
        for frame in self.frames_without_pings():
            parsed = parse_client_message(frame)
            types.append(parsed.type)
        return types


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


def snapshot_frame(view: GridView, seq: int, solved: bool) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=(player_view("p1", "Ana", 0), player_view("p2", "Bob", 3)),
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


def letters_except(empty: list[Cell]) -> ChangeList:
    """Confirmed right letters (by `p2`) for every FX-01 letter cell but `empty`."""
    changes: ChangeList = []
    for position in ROW_MAJOR:
        if position not in empty:
            update: dict[str, object] = {"letter": SOLUTION[position], "author": "p2"}
            changes.append((position[0], position[1], update))
    return changes


def open_fx01(
    page: Page,
    base_url: str,
    fx01_grid: Grid,
    changes: ChangeList,
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
    wait_until_page(page, lambda: len(mock.frames_without_pings()) > 0)
    view = with_letter_cells(grid_view(fx01_grid), changes)
    mock.send(snapshot_frame(view, seq, solved))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def expect_seq(page: Page, seq: int) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
