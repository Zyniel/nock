"""Shared setup of the tests of spec 037: integrity.

This module is not a test file: pytest does not collect it. The tests of spec 037
are in `tests/test_spec_037_*.py`, one file per criterion.

It holds what more than one of those files uses: the constants of the two-player
room, the waiting times, the simulated client (`Peer`) with its traffic log, the
helpers that join players and read the room, and the builders of the fixtures.
What only one file uses stays in that file, next to its tests.

The fixtures `fx01_grid`, `dist_dir`, `catalogue`, `registry` and the like are
defined in each file that needs them, as thin wrappers around `grid_from_text`,
`make_dist_dir`, `make_catalogue` and `make_registry`: a fixture imported from here
would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    ErrorCode,
    ErrorMessage,
    Join,
    LetterChanged,
    ServerMessage,
    Snapshot,
    parse_server_message,
)
from nock.room import PlayerRecord, RoomConfig, RoomState, join_room, new_room

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"

WAIT_SECONDS = 5.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

# ---- Builders of the fixtures -------------------------------------------------


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(text)


def make_dist_dir(root: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixture)."""
    dist = root / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_catalogue(grid: Grid) -> Catalogue:
    """A catalogue holding `grid` as published entry 1 (the `catalogue` fixture)."""
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
    """A registry whose throttle never refuses and that never times a socket out.

    This is the registry of the `registry` fixture. The caller closes it.
    """
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    return RoomRegistry(config=config)


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


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


def refusal_code(reply: tuple[ServerMessage, ...]) -> ErrorCode:
    """The code of the single error in `reply`."""
    assert len(reply) == 1
    refusal = reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


# ---- Helpers for the WebSocket tests ---------------------------------------------


class Earned(NamedTuple):
    """Log item: the test sent `letter` to a cell, so the room may show it."""

    row: int
    column: int
    letter: str


class _Seen(NamedTuple):
    """Log item: a payload (WebSocket frame or HTTP body) reached a browser."""

    source: str
    text: str


class TrafficLog:
    """The ordered record of what the test sent and what the clients received."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[Earned | _Seen] = []

    def earn(self, row: int, column: int, letter: str) -> None:
        """Record that the test is about to send `letter` to a cell."""
        with self._lock:
            self._items.append(Earned(row, column, letter))

    def see(self, source: str, text: str) -> None:
        """Record one payload received by `source`."""
        with self._lock:
            self._items.append(_Seen(source, text))

    def items(self) -> list[Earned | _Seen]:
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

    def send(self, message: ClientMessage) -> None:
        self._websocket.send_text(message.model_dump_json())

    def send_text(self, text: str) -> None:
        self._websocket.send_text(text)

    def send_bytes(self, data: bytes) -> None:
        self._websocket.send_bytes(data)

    def messages(self) -> list[ServerMessage]:
        """Every message received so far."""
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
        for message in self.messages():
            if isinstance(message, LetterChanged):
                found.append(message)
        return found

    def errors(self) -> list[ErrorMessage]:
        found: list[ErrorMessage] = []
        for message in self.messages():
            if isinstance(message, ErrorMessage):
                found.append(message)
        return found

    def wait_for_messages(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.messages()) >= count, what)

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

    def wait_for_letter_events(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.letter_events()) >= count, what)

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


def state_of(registry: RoomRegistry, code: str) -> RoomState:
    state = registry.room_state(code)
    assert state is not None
    return state


# ---- Helpers for the browser tests --------------------------------------------


def wait_until_page(page: Page, condition: Callable[[], bool], what: str) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"timed out waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50
