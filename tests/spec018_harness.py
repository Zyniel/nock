"""Shared setup of the tests of spec 018: durable room state.

This module is not a test file: pytest does not collect it. The tests of spec 018
are in `tests/test_spec_018_*.py`, one file per criterion group (AC-1 and AC-3 are
split by what they exercise).

AC-1 is checked in four layers: `RoomStore` on its own (log, snapshots, errors),
`replay` and `after_restart` on their own, a 250-step room driven with the rules
and read back with `load_room`, and the real WebSocket with a simulated restart
(a second store, registry and app on the same SQLite file). AC-2 uses the real
WebSocket with writer threads. AC-3 checks undo on `handle_message`, on the real
WebSocket and on the page with a mocked socket. AC-4 checks that saving comes
first, with a `RoomStore` subclass.

The table layout is the implementer's choice, so the snapshots the hub saves are
observed through `load_room` only: a log row is damaged on purpose, and
`load_room` fails exactly when it has to replay that row, that is when no
snapshot covers it.

Not tested here, by the spec's own decision: a real process kill and a power cut
(`synchronous=FULL` is relied on). Not tested: the `grid_solved` refusal of an
undo (spec 026), the refusal of a removed player's join (spec 014), the README.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`registry`, `client` and `catalogue` are defined in each file that needs them as
thin wrappers around `grid_from_text`, `make_dist_dir`, `make_registry`,
`make_app` and `published_catalogue`: a fixture imported from here would be an
unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import sqlite3
import string
import threading
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    Erase,
    ErrorMessage,
    GridView,
    Join,
    LetterCellView,
    LetterChanged,
    PlayerState,
    ServerMessage,
    Snapshot,
    Undo,
    parse_server_message,
)
from nock.room import (
    CellState,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    UndoEntry,
    grid_state,
    handle_message,
    join_room,
    new_room,
    player_views,
)
from nock.server import create_app
from nock.store import RoomStore

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
OTHER_CODE = "GHJKLM"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
LATER = 3_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
PUBLISHED_NUMBER = 2

WAIT_SECONDS = 10.0
OVERALL_SECONDS = 180.0
POLL_SECONDS = 0.02
SHORT_PAUSE_SECONDS = 0.3
DRIVE_EVENTS = 250
DRIVE_CYCLES = 80

ClientSend = Join | EditLetter | Erase | Undo
CellValue = tuple[str | None, bool, str | None]  # letter, pencil, author
PlayerSummary = tuple[
    str, str, str, int, bool, bool, PlayerState, int, UndoEntry | None
]

# Spec 018, "Test harness": `max_inbound_pending` is lifted above spec 036's
# default (100), so that the writers' bursts do not close their sockets.
SERVER_CONFIG = RoomConfig(
    max_edits_per_second=1000, max_inbound_pending=1000, silence_timeout_seconds=600
)


# ---- Fixture bodies ----


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
    """A registry (default in-memory store) whose throttle never refuses.

    This is the registry of the `registry` fixture, which closes it.
    """
    return RoomRegistry(config=SERVER_CONFIG)


def make_app(registry: RoomRegistry, dist_dir: Path) -> FastAPI:
    """An app serving `registry` (the app of the `client` fixture)."""
    return create_app(rooms=registry, dist_dir=dist_dir)


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def published_catalogue(grid: Grid) -> Catalogue:
    """A catalogue with one published grid, number `PUBLISHED_NUMBER`.

    This is the catalogue of the `catalogue` fixture.
    """
    published = CatalogueEntry(
        number=PUBLISHED_NUMBER,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=grid,
    )
    return Catalogue(entries=(published,))


# ---- Helpers on room states ----


def letter_cells(grid: Grid) -> list[tuple[int, int]]:
    """The letter cells of `grid` in row-major order."""
    positions: list[tuple[int, int]] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


def token_of(index: int) -> str:
    return f"resume-token-number-{index:04d}"


def two_player_room(grid: Grid, code: str = ROOM_CODE) -> RoomState:
    """A room with players `p1` and `p2` (seq 2), every cell empty."""
    state = new_room(code, grid, START_TIME)
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", FIRST_TOKEN
    )
    second = join_room(
        first.state, Join(nickname="Bob", resume_token=None), NOW, "p2", SECOND_TOKEN
    )
    assert second.state.seq == 2
    return second.state


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


def other_cells(state: RoomState, row: int, column: int) -> list[CellState]:
    return [cell for cell in state.cells if (cell.row, cell.column) != (row, column)]


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


def letter_changed(
    seq: int,
    row: int,
    column: int,
    letter: str | None,
    player_id: str,
    pencil: bool = False,
) -> LetterChanged:
    return LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player_id,
    )


def grid_values(view: GridView) -> dict[tuple[int, int], CellValue]:
    """The (letter, pencil, author) of each letter cell of a grid view."""
    values: dict[tuple[int, int], CellValue] = {}
    for cell in view.cells:
        if isinstance(cell, LetterCellView):
            values[(cell.row, cell.column)] = (cell.letter, cell.pencil, cell.author)
    return values


def summarize_players(state: RoomState) -> list[PlayerSummary]:
    """The fields of each player that the log carries."""
    summaries: list[PlayerSummary] = []
    for player in state.players:
        summaries.append(
            (
                player.player_id,
                player.resume_token,
                player.nickname,
                player.colour,
                player.is_host,
                player.muted,
                player.state,
                player.joined_seq,
                player.last_edit,
            )
        )
    return summaries


def resume_tokens(state: RoomState) -> list[str]:
    return [player.resume_token for player in state.players]


def assert_same_room(loaded: RoomState | None, live: RoomState) -> None:
    """Check every field the log carries is the same in `loaded` and `live`."""
    assert loaded is not None
    assert loaded.code == live.code
    assert loaded.seq == live.seq
    assert grid_state(loaded) == grid_state(live)
    assert player_views(loaded) == player_views(live)
    assert resume_tokens(loaded) == resume_tokens(live)
    assert loaded.cells == live.cells
    assert summarize_players(loaded) == summarize_players(live)
    assert loaded.settings == live.settings
    assert loaded.reveal_budget == live.reveal_budget
    assert loaded.removed_tokens == live.removed_tokens
    assert loaded.grid == live.grid


# ---- A 250-step room driven with the rules ----


def commit(store: RoomStore, code: str, outcome: Outcome) -> RoomState:
    """Append the entries of a step, as the hub does, and return its state."""
    if len(outcome.entries) > 0:
        store.append(code, outcome.entries)
    return outcome.state


def drive_room(
    store: RoomStore, grid: Grid, snapshot_at: int | None = None
) -> RoomState:
    """Create FX-01 room `ROOM_CODE` in `store` and play it up to DRIVE_EVENTS.

    Three players join, then each cycle (player after player) is: a letter in a
    cell, another letter over it, an undo (back to the first letter), an erase
    of a second cell, an undo (the erased letter is back). Each step's entries
    are appended. Returns the live state. When the rules cannot reach the
    DRIVE_EVENTS events, the returned state has a smaller seq.
    """
    state = new_room(ROOM_CODE, grid, START_TIME)
    store.create_room(state)
    now = START_TIME
    for index, nickname in enumerate(["Ana", "Bob", "Cleo"]):
        now += 1
        outcome = join_room(
            state,
            Join(nickname=nickname, resume_token=None),
            now,
            f"p{index + 1}",
            token_of(index),
        )
        state = commit(store, ROOM_CODE, outcome)

    # The last cell is never touched, so the grid never fills (spec 026).
    cells = letter_cells(grid)[:-1]
    letters = string.ascii_uppercase
    for cycle in range(DRIVE_CYCLES):
        player_id = f"p{cycle % 3 + 1}"
        first_row, first_column = cells[(cycle * 7) % len(cells)]
        second_row, second_column = cells[(cycle * 7 + 3) % len(cells)]
        messages: list[EditLetter | Erase | Undo] = [
            EditLetter(row=first_row, column=first_column, letter=letters[cycle % 26]),
            EditLetter(
                row=first_row, column=first_column, letter=letters[(cycle + 9) % 26]
            ),
            Undo(),
            Erase(row=second_row, column=second_column),
            Undo(),
        ]
        for message in messages:
            if state.seq >= DRIVE_EVENTS:
                return state
            now += 1
            outcome = handle_message(state, player_id, message, now, SERVER_CONFIG)
            state = commit(store, ROOM_CODE, outcome)
            if snapshot_at is not None and state.seq == snapshot_at:
                store.save_snapshot(state)
    return state


# ---- Helpers on the SQLite file ----


def corrupt_log_entry(path: Path, seq: int) -> None:
    """Replace the stored `letter_changed` log row of `seq` by an invalid JSON.

    The layout is the implementer's choice: every text column of every table is
    tried. Exactly one value must match: the JSON of that log entry.
    """
    connection = sqlite3.connect(path, timeout=WAIT_SECONDS)
    changed = 0
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for (table,) in tables:
            columns = connection.execute(f'PRAGMA table_info("{table}")').fetchall()
            for column_info in columns:
                column = column_info[1]
                cursor = connection.execute(
                    f'UPDATE "{table}" SET "{column}" = ? '
                    f"WHERE typeof(\"{column}\") = 'text' "
                    f'AND "{column}" LIKE ? AND "{column}" LIKE ?',
                    ("{}", '%"type":"letter_changed"%', f'%"seq":{seq},%'),
                )
                changed += cursor.rowcount
        connection.commit()
    finally:
        connection.close()
    assert changed == 1, f"expected to damage one log row, damaged {changed}"


def load_from_file(path: Path, code: str) -> RoomState | None:
    """`load_room` of a fresh store on the file, closed afterwards."""
    store = RoomStore(path)
    try:
        return store.load_room(code)
    finally:
        store.close()


def wait_for(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")
        time.sleep(POLL_SECONDS)


# ---- Helpers for the WebSocket tests ----


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives.

    `on_message` runs in the reader thread as soon as a message is read; an
    exception it raises is reported by the next wait of the test. All waits are
    bounded.
    """

    def __init__(
        self,
        websocket: WebSocketTestSession,
        on_message: Callable[[ServerMessage], None] | None = None,
    ) -> None:
        self._websocket = websocket
        self._on_message = on_message
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
            if self._on_message is not None:
                try:
                    self._on_message(message)
                except Exception as error:  # reported by the test thread
                    self._keep_failure(f"{message!r}: {error}")
            with self._arrived:
                self._received.append(message)
                self._arrived.notify_all()

    def _keep_failure(self, text: str) -> None:
        with self._arrived:
            self._failures.append(text)
            self._arrived.notify_all()

    def failures(self) -> list[str]:
        with self._arrived:
            return list(self._failures)

    def send(self, message: ClientSend) -> None:
        self._websocket.send_text(message.model_dump_json())

    def messages(self) -> list[ServerMessage]:
        """Every message received so far, the snapshot first."""
        with self._arrived:
            return list(self._received)

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def events(self) -> list[ServerMessage]:
        return self.messages()[1:]

    def you(self) -> str:
        return self.snapshot().you

    def last_seq(self) -> int:
        last = self.snapshot().seq
        for message in self.events():
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

    def letter_events(self) -> list[LetterChanged]:
        found: list[LetterChanged] = []
        for message in self.events():
            if isinstance(message, LetterChanged):
                found.append(message)
        return found

    def errors(self) -> list[ErrorMessage]:
        found: list[ErrorMessage] = []
        for message in self.events():
            if isinstance(message, ErrorMessage):
                found.append(message)
        return found

    def wait_for_messages(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.messages()) >= count, what)

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

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


def open_peer(
    stack: contextlib.ExitStack,
    http_client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
    on_message: Callable[[ServerMessage], None] | None = None,
) -> Peer:
    """Open a socket, send a join and wait for the answer."""
    websocket = stack.enter_context(
        http_client.websocket_connect(f"/api/rooms/{code}/ws")
    )
    peer = Peer(websocket, on_message)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_for_messages(1, f"the answer to the join of {nickname}")
    return peer


def join_peers(
    stack: contextlib.ExitStack, http_client: TestClient, code: str, names: list[str]
) -> list[Peer]:
    """Join one peer per name in turn; return once all saw every join."""
    peers: list[Peer] = []
    for name in names:
        peers.append(open_peer(stack, http_client, code, name))
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def grid_of_peer(peer: Peer) -> dict[tuple[int, int], CellValue]:
    """The peer's copy of the grid: its snapshot, then each letter_changed in order."""
    values = grid_values(peer.snapshot().grid)
    for message in peer.events():
        if isinstance(message, LetterChanged):
            author = message.player_id if message.letter is not None else None
            values[(message.row, message.column)] = (
                message.letter,
                message.pencil,
                author,
            )
    return values


def server_grid(server: RoomRegistry, code: str) -> dict[tuple[int, int], CellValue]:
    state = server.room_state(code)
    assert state is not None
    return grid_values(grid_state(state))


class Process:
    """One server process: a store, a registry and an app on one SQLite file."""

    def __init__(self, path: Path, dist_dir: Path, config: RoomConfig) -> None:
        self.store = RoomStore(path)
        self.registry = RoomRegistry(config=config, store=self.store)
        self.app = create_app(rooms=self.registry, dist_dir=dist_dir)

    def shutdown(self) -> None:
        self.registry.close()
        self.store.close()


def players_all_disconnected(process: Process, code: str) -> bool:
    state = process.registry.room_state(code)
    if state is None:
        return False
    return all(player.state is PlayerState.DISCONNECTED for player in state.players)
