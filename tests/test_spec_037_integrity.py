"""Tests of spec 037: integrity.

AC-1 inspects all the traffic of a full FX-01 game, on the real WebSocket (three
clients) and in a browser on the live server. AC-2 checks the edit validation on
`handle_message` and on the WebSocket, and the frame size limit. AC-3 checks the
rate limit on `handle_message` and on the WebSocket with a fake clock. AC-4 checks
the escaping: a static scan of `web/src`, the server's refusal of tags in
nicknames, and the room page with a mocked socket.

Interpretations (see the report): an answer letter is "earned" in the WebSocket and
browser games when the test itself sent it to that cell, because every edit of those
games is accepted; the invalid-frame answer of a joined socket is tested under AC-2.

Not tested here: a removed player's socket being closed (spec 014), reveals and
chat traffic (specs 022 and 024 extend the checker), a text frame whose size in
bytes differs from its size in characters is covered only for a join (Unicode
spaces around the nickname are stripped, so the frame stays valid).
"""

from __future__ import annotations

import contextlib
import json
import re
import threading
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import NamedTuple, Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import (
    Dialog,
    Page,
    Response,
    WebSocket,
    WebSocketRoute,
    expect,
)
from playwright.sync_api import Error as PlaywrightError
from starlette.testclient import WebSocketTestSession

import nock.hub
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    ClueCellView,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    PencilEdit,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    SelectCell,
    ServerMessage,
    Snapshot,
    Undo,
    grid_view,
    parse_server_message,
)
from nock.room import (
    CellState,
    PlayerRecord,
    RoomConfig,
    RoomState,
    grid_state,
    handle_message,
    join_room,
    new_room,
)
from nock.server import create_app

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 5.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
KEY_PAUSE_MS = 60
MAX_FRAME_BYTES = 4096
RATE_LIMIT = 20

ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FORBIDDEN_KEYS = ("answer", "solution")
# Values that are random identifiers: they could by chance spell a short answer.
IDENTIFIER_KEYS = ("resume_token", "player_id", "you", "author", "code")

Cell = tuple[int, int]
Step = tuple[int, int, str | None]  # row, column, letter (None: erase)
ChangeList = list[tuple[int, int, dict[str, object]]]

FX01_SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    FX01_SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        FX01_SOLUTION[(_row, _offset + 1)] = _letter

# ---- Fixtures ---------------------------------------------------------------


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


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        grid=fx01_grid,
    )
    return Catalogue(entries=(entry,))


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    config = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
    room_registry = RoomRegistry(config=config)
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clock_registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on the fake clock, with the default limit of 20 edits a second."""
    config = RoomConfig(silence_timeout_seconds=600)
    assert config.max_edits_per_second == RATE_LIMIT
    room_registry = RoomRegistry(clock=fake_clock, config=config)
    yield room_registry
    room_registry.close()


@pytest.fixture
def clock_room_code(clock_registry: RoomRegistry, fx01_grid: Grid) -> str:
    return clock_registry.register_room(fx01_grid)


@pytest.fixture
def clock_client(clock_registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


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


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def locked_cell() -> CellState:
    """The cell (1, 2) holding `M`, locked."""
    return CellState(
        row=1,
        column=2,
        letter="M",
        author="p2",
        locked=True,
        revealed=False,
        changed_seq=2,
        changed_by="p2",
    )


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


def seen_at(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state with only the `last_seen_at` of the player set to `now`.

    Spec 017: every message sets `last_seen_at`, a refused edit included.
    """
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == player_id:
            player = player.model_copy(update={"last_seen_at": now})
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


def refusal_code(reply: tuple[ServerMessage, ...]) -> ErrorCode:
    """The code of the single error in `reply`."""
    assert len(reply) == 1
    refusal = reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


# ---- Helpers for the WebSocket tests ---------------------------------------------


class _Earned(NamedTuple):
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
        self._items: list[_Earned | _Seen] = []

    def earn(self, row: int, column: int, letter: str) -> None:
        """Record that the test is about to send `letter` to a cell."""
        with self._lock:
            self._items.append(_Earned(row, column, letter))

    def see(self, source: str, text: str) -> None:
        """Record one payload received by `source`."""
        with self._lock:
            self._items.append(_Seen(source, text))

    def items(self) -> list[_Earned | _Seen]:
        with self._lock:
            return list(self._items)


def _keys_of(value: object) -> list[str]:
    """Every key of every object inside a parsed JSON value."""
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(_keys_of(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(_keys_of(child))
    return keys


def _without_identifiers(value: object) -> object:
    """A copy of a parsed JSON value without the random identifier values."""
    if isinstance(value, dict):
        kept: dict[str, object] = {}
        for key, child in value.items():
            if key in IDENTIFIER_KEYS:
                continue
            kept[str(key)] = _without_identifiers(child)
        return kept
    if isinstance(value, list):
        kept_list: list[object] = []
        for child in value:
            kept_list.append(_without_identifiers(child))
        return kept_list
    return value


def _letters_in(value: object) -> list[tuple[int, int, str]]:
    """Every (row, column, letter) a parsed payload shows at a cell.

    That is a `letter_changed`, a `cell_locked` and every `LetterCellView`.
    """
    found: list[tuple[int, int, str]] = []
    if isinstance(value, dict):
        kind = value.get("type")
        row = value.get("row")
        column = value.get("column")
        letter = value.get("letter")
        shows_letter = kind in ("letter_changed", "cell_locked", "letter")
        has_position = isinstance(row, int) and isinstance(column, int)
        if shows_letter and has_position and isinstance(letter, str):
            found.append((row, column, letter))
        for child in value.values():
            found.extend(_letters_in(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_letters_in(child))
    return found


def leaks_in(text: str, earned: dict[Cell, set[str]]) -> list[str]:
    """The rules of "What a browser may receive" that one payload breaks."""
    problems: list[str] = []
    try:
        parsed: object = json.loads(text)
        is_json = True
    except ValueError:
        parsed = None
        is_json = False
    scanned = text
    if is_json:
        for key in _keys_of(parsed):
            if key in FORBIDDEN_KEYS:
                problems.append(f"the key {key!r}")
        scanned = json.dumps(_without_identifiers(parsed))
        for row, column, letter in _letters_in(parsed):
            if letter not in earned.get((row, column), set()):
                problems.append(f"the unearned letter {letter!r} at ({row}, {column})")
    for answer in ANSWERS:
        if answer in scanned:
            problems.append(f"the answer {answer!r}")
    return problems


def replay_problems(log: TrafficLog) -> list[str]:
    """Replay the log in order and list every payload that breaks a rule."""
    earned: dict[Cell, set[str]] = {}
    problems: list[str] = []
    for item in log.items():
        if isinstance(item, _Earned):
            earned.setdefault((item.row, item.column), set()).add(item.letter)
            continue
        for problem in leaks_in(item.text, earned):
            problems.append(f"{item.source} received {problem}: {item.text[:120]}")
    return problems


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


def edit_frame(letter: str, row: int = 1, column: int = 0) -> str:
    """The JSON text of an `edit_letter`, with any `letter` value."""
    return json.dumps(
        {"type": "edit_letter", "row": row, "column": column, "letter": letter}
    )


def erase_frame(row: int, column: int) -> str:
    return json.dumps({"type": "erase", "row": row, "column": column})


def padded_to(text: str, size: int) -> str:
    """`text` followed by JSON whitespace until it is `size` bytes long."""
    assert len(text.encode("utf-8")) <= size
    return text + " " * (size - len(text.encode("utf-8")))


def check_refusal(
    registry: RoomRegistry,
    code: str,
    ana: Peer,
    bob: Peer,
    sender: Peer,
    send_refused: Callable[[], None],
    expected: ErrorCode,
) -> None:
    """Check one refused frame, then one valid edit of Ana.

    The refused frame is answered `expected` to `sender` only, changes neither the
    `seq` nor the grid, and reaches nobody else; the valid `T` at (1, 0) of Ana is
    then accepted, and Bob's whole list of messages is that event alone.
    """
    ana_start = len(ana.messages())
    bob_start = len(bob.messages())
    sender_start = len(sender.messages())
    before = state_of(registry, code)

    send_refused()
    sender.wait_for_messages(sender_start + 1, "the refusal")

    after = state_of(registry, code)
    assert after.seq == before.seq
    assert grid_state(after) == grid_state(before)

    ana.send(EditLetter(row=1, column=0, letter="T"))
    ana.wait_for_letter_events(1, "the valid edit of Ana")
    bob.wait_for_letter_events(1, "the valid edit of Ana, on Bob")

    refusal = sender.messages()[sender_start]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is expected
    accepted = LetterChanged(
        seq=before.seq + 1,
        row=1,
        column=0,
        letter="T",
        pencil=False,
        player_id=ana.you(),
    )
    assert bob.messages()[bob_start:] == [accepted]
    if sender is ana:
        assert ana.messages()[ana_start:] == [refusal, accepted]
    else:
        assert ana.messages()[ana_start:] == [accepted]
        assert sender.messages()[sender_start:] == [refusal]


# ---- AC-1: the traffic of a full game (WebSocket) -------------------------------


def send_steps(peer: Peer, log: TrafficLog, steps: list[Step]) -> None:
    """Send the steps in order, noting each letter as earned before it leaves."""
    for row, column, letter in steps:
        if letter is None:
            peer.send(Erase(row=row, column=column))
        else:
            log.earn(row, column, letter)
            peer.send(EditLetter(row=row, column=column, letter=letter))


def letters_of_snapshot(snapshot: Snapshot) -> dict[Cell, str]:
    """The letters a snapshot holds, by cell."""
    letters: dict[Cell, str] = {}
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and cell.letter is not None:
            letters[(cell.row, cell.column)] = cell.letter
    return letters


WRONG_LETTERS: list[Step] = [(1, 0, "X"), (2, 2, "X"), (4, 4, "X")]
FIRST_NINE_AND_ERASE: list[Step] = [
    (1, 0, "T"),
    (1, 1, "A"),
    (1, 2, "M"),
    (1, 3, "I"),
    (1, 4, "S"),
    (2, 1, "V"),
    (2, 2, "I"),
    (2, 3, "D"),
    (2, 4, "E"),
    (4, 4, None),
]
BOBS_LETTER: list[Step] = [(0, 1, "N")]
ANAS_LAST_WORDS: list[Step] = [
    (3, 1, "A"),
    (3, 2, "M"),
    (3, 3, "E"),
    (3, 4, "N"),
    (4, 1, "L"),
    (4, 2, "E"),
    (4, 3, "S"),
    (4, 4, "T"),
]
FIRST_NINE_LETTERS = {
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
}
EVENTS_BEFORE_CY = len(WRONG_LETTERS) + len(FIRST_NINE_AND_ERASE)
EVENTS_OF_THE_GAME = EVENTS_BEFORE_CY + len(BOBS_LETTER) + len(ANAS_LAST_WORDS)


def test_ac1_websocket_the_traffic_of_a_full_game_carries_only_earned_letters(
    registry: RoomRegistry, client: TestClient
) -> None:
    log = TrafficLog()
    created = client.post("/api/rooms", json={"grid_number": 1})
    assert created.status_code == 201
    log.see("POST /api/rooms", created.text)
    code = created.json()["code"]
    for path in ("/api/grids", "/api/grids/1"):
        listed = client.get(path)
        assert listed.status_code == 200
        log.see(f"GET {path}", listed.text)

    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"], log)

        send_steps(ana, log, WRONG_LETTERS)
        send_steps(ana, log, FIRST_NINE_AND_ERASE)
        for peer in (ana, bob):
            peer.wait_for_letter_events(EVENTS_BEFORE_CY, "the first 13 events")

        cy = connect(stack, client, code, "Cy", log)
        cy.send(Join(nickname="Cy", resume_token=None))
        cy.wait_for_messages(1, "the snapshot of Cy")

        send_steps(bob, log, BOBS_LETTER)
        bob.wait_for_letter_events(EVENTS_BEFORE_CY + 1, "the letter of Bob")
        send_steps(ana, log, ANAS_LAST_WORDS)
        ana.wait_for_letter_events(EVENTS_OF_THE_GAME, "every event, on Ana")
        bob.wait_for_letter_events(EVENTS_OF_THE_GAME, "every event, on Bob")
        cy.wait_for_letter_events(
            EVENTS_OF_THE_GAME - EVENTS_BEFORE_CY, "every later event, on Cy"
        )

        assert letters_of_snapshot(cy.snapshot()) == FIRST_NINE_LETTERS
        assert len(ana.letter_events()) == EVENTS_OF_THE_GAME
        assert ana.errors() == []
        assert bob.errors() == []
        assert cy.errors() == []

    final = state_of(registry, code)
    final_letters: dict[Cell, str] = {}
    for cell in final.cells:
        if cell.letter is not None:
            final_letters[(cell.row, cell.column)] = cell.letter
    assert final_letters == FX01_SOLUTION
    assert replay_problems(log) == []


LEAKY_PAYLOADS = [
    pytest.param(
        '{"type": "snapshot", "grid": {"cells": [{"type": "letter", "answer": 1}]}}',
        "the key 'answer'",
        id="answer-key",
    ),
    pytest.param('{"solution": []}', "the key 'solution'", id="solution-key"),
    pytest.param(
        '{"type": "error", "code": "x", "message": "it is NAVAL"}',
        "the answer 'NAVAL'",
        id="answer-substring",
    ),
    pytest.param(
        '{"type": "letter_changed", "seq": 3, "row": 1, "column": 0, '
        '"letter": "T", "pencil": false, "player_id": "p1"}',
        "the unearned letter 'T' at (1, 0)",
        id="letter-changed-not-earned",
    ),
    pytest.param(
        '{"type": "cell_locked", "seq": 3, "row": 1, "column": 2, '
        '"letter": "M", "revealed": true}',
        "the unearned letter 'M' at (1, 2)",
        id="cell-locked-not-earned",
    ),
    pytest.param(
        '{"type": "snapshot", "grid": {"cells": [{"type": "letter", "row": 2, '
        '"column": 1, "letter": "V"}]}}',
        "the unearned letter 'V' at (2, 1)",
        id="snapshot-letter-not-earned",
    ),
]


@pytest.mark.parametrize(("payload", "expected"), LEAKY_PAYLOADS)
def test_ac1_the_checker_reports_each_kind_of_leak(payload: str, expected: str) -> None:
    assert expected in leaks_in(payload, {})


def test_ac1_the_checker_accepts_a_letter_typed_at_that_cell_only() -> None:
    payload = (
        '{"type": "letter_changed", "seq": 3, "row": 1, "column": 0, '
        '"letter": "T", "pencil": false, "player_id": "p1"}'
    )

    assert leaks_in(payload, {(1, 0): {"X", "T"}}) == []
    assert leaks_in(payload, {(1, 1): {"T"}}) == ["the unearned letter 'T' at (1, 0)"]


# ---- AC-1: the traffic of a full game (browser) ---------------------------------

# The 18 letters word by word: TAMIS, NAVAL, MIME, IDES, SENT, then VIDE, AMEN,
# LEST through the crossing letters; a cell already typed is not typed twice.
BROWSER_GAME: list[tuple[int, int, str]] = [
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
    (4, 4, "t"),
]


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def wait_until_page(page: Page, condition: Callable[[], bool], what: str) -> None:
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"timed out waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50


def is_text_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return "text/" in lowered or "json" in lowered or "javascript" in lowered


def frame_type(text: str) -> str:
    parsed: object = json.loads(text)
    if isinstance(parsed, dict):
        return str(parsed.get("type"))
    return ""


def test_ac1_browser_the_traffic_of_a_full_game_carries_only_earned_letters(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    log = TrafficLog()
    frames: list[str] = []
    responses: list[Response] = []

    def keep_frame(payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        frames.append(text)
        log.see("the page", text)

    def keep_response(response: Response) -> None:
        responses.append(response)

    def watch_socket(websocket: WebSocket) -> None:
        websocket.on("framereceived", keep_frame)

    page.on("websocket", watch_socket)
    page.on("response", keep_response)

    enter_room(page, f"{live_server}/r/{code}", "Ana")
    for row, column, key in BROWSER_GAME:
        page.locator(cell_selector(row, column)).click()
        log.earn(row, column, key.upper())
        page.keyboard.press(key)
        page.wait_for_timeout(KEY_PAUSE_MS)

    def count_of(kind: str) -> int:
        return len([text for text in frames if frame_type(text) == kind])

    wait_until_page(page, lambda: count_of("letter_changed") >= 18, "18 events")
    page.wait_for_timeout(SETTLE_MS)
    for row, column, key in BROWSER_GAME:
        expected = key.upper()
        expect(page.locator(cell_selector(row, column))).to_have_attribute(
            "data-letter", expected
        )

    body_count = 0
    for response in responses:
        content_type = response.headers.get("content-type", "")
        if not is_text_content_type(content_type):
            continue
        try:
            body = response.body().decode("utf-8")
        except PlaywrightError:
            continue  # the browser no longer holds this body (a cancelled request)
        log.see(f"GET {response.url}", body)
        body_count += 1

    assert body_count >= 1
    assert count_of("snapshot") >= 1
    assert count_of("letter_changed") == 18
    assert replay_problems(log) == []


# ---- AC-2: only a letter, on a letter cell, from a member (Python) ----------------

NOT_LETTER_CELLS = [(0, 0), (5, 0), (0, 5), (9, 9), (4, 5), (0, 2)]


@pytest.mark.parametrize(("row", "column"), NOT_LETTER_CELLS)
@pytest.mark.parametrize("kind", ["edit_letter", "erase"])
def test_ac2_python_an_edit_off_a_letter_cell_is_refused_and_changes_nothing(
    fx01_grid: Grid, row: int, column: int, kind: str
) -> None:
    before = two_player_room(fx01_grid)
    message: ClientMessage
    if kind == "edit_letter":
        message = EditLetter(row=row, column=column, letter="T")
    else:
        message = Erase(row=row, column=column)

    outcome = handle_message(before, "p1", message, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac2_python_a_refused_edit_does_not_count_for_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    outcome = handle_message(state, "p1", EditLetter(row=0, column=0, letter="T"), NOW)

    assert player_record(outcome.state, "p1").recent_edits == ()


# ---- AC-2: only a letter, on a letter cell, from a member (WebSocket) --------------


@pytest.mark.parametrize("letter", ["a", "É", "AB", "1", ""])
def test_ac2_websocket_an_edit_with_a_bad_letter_is_an_invalid_message(
    registry: RoomRegistry, client: TestClient, room_code: str, letter: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            lambda: ana.send_text(edit_frame(letter)),
            ErrorCode.INVALID_MESSAGE,
        )


@pytest.mark.parametrize(("row", "column"), [(0, 0), (5, 0), (0, 5), (9, 9)])
@pytest.mark.parametrize("kind", ["edit_letter", "erase"])
def test_ac2_websocket_an_edit_off_a_letter_cell_is_not_a_letter_cell(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    row: int,
    column: int,
    kind: str,
) -> None:
    frame = (
        edit_frame("T", row, column)
        if kind == "edit_letter"
        else erase_frame(row, column)
    )
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            lambda: ana.send_text(frame),
            ErrorCode.NOT_A_LETTER_CELL,
        )


def test_ac2_websocket_an_edit_from_a_socket_that_has_not_joined_is_not_joined(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        stranger = connect(stack, client, room_code, "Stranger")

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            stranger,
            lambda: stranger.send_text(edit_frame("T", 1, 0)),
            ErrorCode.NOT_JOINED,
        )


@pytest.mark.parametrize(
    "message",
    [
        Undo(),
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        Erase(row=1, column=0),
    ],
    ids=["undo", "select_cell", "erase"],
)
def test_ac2_websocket_every_valid_message_before_join_is_not_joined(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    message: ClientMessage,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        stranger = connect(stack, client, room_code, "Stranger")

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            stranger,
            lambda: stranger.send(message),
            ErrorCode.NOT_JOINED,
        )


def test_ac2_websocket_a_valid_edit_of_a_member_is_accepted(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_letter_events(1, "the accepted edit")
        bob.wait_for_letter_events(1, "the accepted edit, on Bob")

        expected = LetterChanged(
            seq=3, row=1, column=0, letter="T", pencil=False, player_id=ana.you()
        )
        assert ana.letter_events() == [expected]
        assert bob.letter_events() == [expected]
        assert state_of(registry, room_code).seq == 3


def test_ac2_websocket_an_edit_reaches_the_players_of_its_room_only(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    other_code = registry.register_room(fx01_grid)
    with contextlib.ExitStack() as stack:
        (ana,) = join_peers(stack, client, room_code, ["Ana"])
        (zed,) = join_peers(stack, client, other_code, ["Zed"])
        zed_start = len(zed.messages())

        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_letter_events(1, "the edit of Ana")
        zed.send(EditLetter(row=2, column=1, letter="V"))
        zed.wait_for_letter_events(1, "the edit of Zed")

        zed_events = zed.messages()[zed_start:]
        assert zed_events == [
            LetterChanged(
                seq=2,
                row=2,
                column=1,
                letter="V",
                pencil=False,
                player_id=zed.you(),
            )
        ]
    other_state = state_of(registry, other_code)
    assert [(c.row, c.column, c.letter) for c in other_state.cells if c.letter] == [
        (2, 1, "V")
    ]


# ---- AC-2: frames over 4096 bytes -------------------------------------------------


def test_ac2_max_frame_bytes_is_4096() -> None:
    assert nock.hub.MAX_FRAME_BYTES == MAX_FRAME_BYTES


@pytest.mark.parametrize("as_bytes", [False, True], ids=["text", "binary"])
def test_ac2_websocket_a_frame_of_4097_bytes_is_an_invalid_message(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    as_bytes: bool,
) -> None:
    # The frame is a valid edit followed by spaces: only its size is wrong.
    frame = padded_to(edit_frame("T"), MAX_FRAME_BYTES + 1)
    assert len(frame.encode("utf-8")) == 4097

    def send_oversized() -> None:
        if as_bytes:
            ana.send_bytes(frame.encode("utf-8"))
        else:
            ana.send_text(frame)

    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        check_refusal(
            registry,
            room_code,
            ana,
            bob,
            ana,
            send_oversized,
            ErrorCode.INVALID_MESSAGE,
        )


@pytest.mark.parametrize("as_bytes", [False, True], ids=["text", "binary"])
def test_ac2_websocket_a_frame_of_exactly_4096_bytes_is_parsed(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    as_bytes: bool,
) -> None:
    frame = padded_to(edit_frame("T"), MAX_FRAME_BYTES)
    assert len(frame.encode("utf-8")) == 4096
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        if as_bytes:
            ana.send_bytes(frame.encode("utf-8"))
        else:
            ana.send_text(frame)
        ana.wait_for_letter_events(1, "the edit in the 4096-byte frame")
        bob.wait_for_letter_events(1, "the edit in the 4096-byte frame, on Bob")

        assert ana.errors() == []
        assert ana.letter_events()[0].letter == "T"
        assert state_of(registry, room_code).seq == 3


def test_ac2_websocket_an_oversized_join_frame_is_an_invalid_message(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    join_text = Join(nickname="Ana", resume_token=None).model_dump_json()
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Ana")

        peer.send_text(padded_to(join_text, MAX_FRAME_BYTES + 1))
        peer.wait_for_messages(1, "the answer to the oversized join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_MESSAGE
        assert state_of(registry, room_code).players == ()

        peer.send_text(padded_to(join_text, MAX_FRAME_BYTES))
        peer.wait_for_messages(2, "the snapshot")
        assert isinstance(peer.messages()[1], Snapshot)


def test_ac2_websocket_a_join_frame_over_4096_bytes_but_few_characters_is_refused(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    # Ana followed by ideographic spaces: valid once stripped, 1457 characters
    # but 4257 bytes, so only a size measured in bytes refuses it.
    nickname = "Ana" + "　" * 1400
    frame = json.dumps(
        {"type": "join", "nickname": nickname, "resume_token": None},
        ensure_ascii=False,
    )
    assert len(frame) < MAX_FRAME_BYTES
    assert len(frame.encode("utf-8")) > MAX_FRAME_BYTES
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Ana")

        peer.send_text(frame)
        peer.wait_for_messages(1, "the answer to the multi-byte join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_MESSAGE
        assert state_of(registry, room_code).players == ()


# ---- AC-3: the rate limit (Python) -------------------------------------------------


def burst_edits(
    state: RoomState,
    player_id: str,
    count: int,
    now: float,
    config: RoomConfig | None = None,
) -> RoomState:
    """Apply `count` accepted edits of `player_id` at `now`; return the new state."""
    for index in range(count):
        edit = EditLetter(row=1, column=index % 5, letter="A")
        if config is None:
            outcome = handle_message(state, player_id, edit, now)
        else:
            outcome = handle_message(state, player_id, edit, now, config)
        assert len(outcome.entries) == 1, f"edit {index + 1} was not accepted"
        state = outcome.state
    return state


def one_more_edit(
    state: RoomState, player_id: str, now: float
) -> tuple[RoomState, bool]:
    """Send one more edit; return the new state and whether it was accepted."""
    edit = EditLetter(row=2, column=1, letter="B")
    outcome = handle_message(state, player_id, edit, now)
    if len(outcome.entries) == 1:
        return outcome.state, True
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED
    assert outcome.state == seen_at(state, player_id, now)
    assert player_record(outcome.state, player_id).last_seen_at == now
    return outcome.state, False


def test_ac3_python_the_21st_edit_at_the_same_time_is_rate_limited(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    entries = []
    for index in range(21):
        edit = EditLetter(row=1, column=index % 5, letter="A")
        outcome = handle_message(state, "p1", edit, NOW)
        entries.extend(outcome.entries)
        if index < 20:
            assert outcome.reply == ()
            state = outcome.state

    assert len(entries) == 20
    for entry in entries:
        assert isinstance(entry.event, LetterChanged)
    assert state.seq == 22
    assert outcome.state == state
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac3_python_the_edit_is_still_refused_half_a_second_later_and_accepted_at_1s(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    state, accepted_at_half = one_more_edit(state, "p1", NOW + 0.5)
    state, accepted_at_one = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_at_half is False
    assert accepted_at_one is True
    assert state.seq == 23


def test_ac3_python_the_window_slides_999_ms_refused_and_1s_accepted(
    fx01_grid: Grid,
) -> None:
    burst = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    _, accepted_at_999_ms = one_more_edit(burst, "p1", NOW + 0.999)
    _, accepted_at_1s = one_more_edit(burst, "p1", NOW + 1.0)

    assert accepted_at_999_ms is False
    assert accepted_at_1s is True


def test_ac3_python_the_window_slides_with_the_age_of_each_edit(
    fx01_grid: Grid,
) -> None:
    # 10 edits at NOW and 10 at NOW + 0.5: at NOW + 1.0 only the first 10 are gone.
    state = burst_edits(two_player_room(fx01_grid), "p1", 10, NOW)
    state = burst_edits(state, "p1", 10, NOW + 0.5)

    state, accepted_at_second = one_more_edit(state, "p1", NOW + 1.0)
    assert accepted_at_second is True
    for _ in range(9):
        state, accepted = one_more_edit(state, "p1", NOW + 1.0)
        assert accepted is True
    _, accepted_after_the_20th = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_after_the_20th is False


def test_ac3_python_refused_edits_do_not_extend_the_limit(fx01_grid: Grid) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    for offset in (0.2, 0.5, 0.9):
        state, accepted = one_more_edit(state, "p1", NOW + offset)
        assert accepted is False
    state, accepted_at_one_second = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_at_one_second is True


def test_ac3_python_a_second_player_is_not_affected_by_the_count_of_the_first(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    outcome = handle_message(state, "p2", EditLetter(row=2, column=1, letter="B"), NOW)

    assert outcome.reply == ()
    assert len(outcome.entries) == 1
    assert player_record(outcome.state, "p2").recent_edits == (NOW,)
    assert player_record(outcome.state, "p1").recent_edits == (NOW,) * 20


def test_ac3_python_an_accepted_edit_adds_now_to_the_recent_edits_of_its_player(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    assert player_record(state, "p1").recent_edits == ()

    state = burst_edits(state, "p1", 1, NOW)
    assert player_record(state, "p1").recent_edits == (NOW,)
    state = burst_edits(state, "p1", 1, NOW + 0.5)
    assert player_record(state, "p1").recent_edits == (NOW, NOW + 0.5)
    state = burst_edits(state, "p1", 1, NOW + 1.2)

    assert player_record(state, "p1").recent_edits == (NOW + 0.5, NOW + 1.2)
    assert player_record(state, "p2").recent_edits == ()


def test_ac3_python_a_refused_edit_leaves_the_recent_edits_as_they_were(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    refused, accepted = one_more_edit(state, "p1", NOW + 0.5)

    assert accepted is False
    assert player_record(refused, "p1").recent_edits == (NOW,) * 20


def test_ac3_python_erase_edits_count_with_letter_edits(fx01_grid: Grid) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 10, NOW)
    for _ in range(10):
        outcome = handle_message(state, "p1", Erase(row=1, column=0), NOW)
        assert len(outcome.entries) == 1
        state = outcome.state

    refused = handle_message(state, "p1", Erase(row=1, column=0), NOW)

    assert refused.state == state
    assert refusal_code(refused.reply) is ErrorCode.RATE_LIMITED


@pytest.mark.parametrize(
    "message",
    [
        PencilEdit(row=1, column=0, letter="A"),
        ConfirmPencil(row=1, column=0),
    ],
    ids=["pencil_edit", "confirm_pencil"],
)
def test_ac3_python_pencil_edits_and_confirmations_are_throttled_too(
    fx01_grid: Grid, message: ClientMessage
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    outcome = handle_message(state, "p1", message, NOW)

    assert outcome.state == state
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


@pytest.mark.parametrize(
    "message",
    [Undo(), SelectCell(row=1, column=0, direction=Direction.ACROSS)],
    ids=["undo", "select_cell"],
)
def test_ac3_python_undo_and_select_cell_are_not_counted(
    fx01_grid: Grid, message: ClientMessage
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 19, NOW)

    in_between = handle_message(state, "p1", message, NOW)
    for reply in in_between.reply:
        if isinstance(reply, ErrorMessage):
            assert reply.code is not ErrorCode.RATE_LIMITED
    twentieth = handle_message(
        in_between.state, "p1", EditLetter(row=2, column=1, letter="B"), NOW
    )

    assert twentieth.reply == ()
    assert len(twentieth.entries) == 1
    assert len(player_record(twentieth.state, "p1").recent_edits) == 20


def test_ac3_python_the_limit_comes_from_the_config(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=3)
    state = burst_edits(two_player_room(fx01_grid), "p1", 3, NOW, config)

    outcome = handle_message(
        state, "p1", EditLetter(row=2, column=1, letter="B"), NOW, config
    )

    assert outcome.state == state
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


def test_ac3_python_a_higher_limit_in_the_config_lets_more_edits_through(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1000)

    state = burst_edits(two_player_room(fx01_grid), "p1", 200, NOW, config)

    assert state.seq == 202
    assert len(player_record(state, "p1").recent_edits) == 200


def test_ac3_python_the_rate_limit_is_checked_before_the_locked_cell(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = with_cell(two_player_room(fx01_grid), locked_cell())
    locked_edit = EditLetter(row=1, column=2, letter="X")
    # Control: a player who has not edited yet is refused for the lock.
    fresh = handle_message(state, "p2", locked_edit, NOW, config)
    assert refusal_code(fresh.reply) is ErrorCode.CELL_LOCKED
    first = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )
    assert len(first.entries) == 1

    outcome = handle_message(first.state, "p1", locked_edit, NOW + 0.1, config)

    assert outcome.state == seen_at(first.state, "p1", NOW + 0.1)
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


def test_ac3_python_the_rate_limit_is_checked_before_the_letter_cell(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = two_player_room(fx01_grid)
    first = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )

    outcome = handle_message(
        first.state, "p1", EditLetter(row=0, column=0, letter="T"), NOW + 0.1, config
    )

    assert outcome.state == seen_at(first.state, "p1", NOW + 0.1)
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


# ---- AC-3: the rate limit (WebSocket, fake clock) -----------------------------------


def burst_frame(index: int) -> EditLetter:
    return EditLetter(row=1, column=index % 5, letter=chr(ord("A") + index % 26))


def test_ac3_websocket_a_burst_of_25_edits_gets_20_events_and_5_rate_limited(
    fake_clock: FakeClock,
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    clock_room_code: str,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, clock_client, clock_room_code, ["Ana", "Bob"])
        seq_before = ana.last_seq()
        ana_start = len(ana.messages())
        bob_start = len(bob.messages())

        for index in range(25):
            ana.send(burst_frame(index))
        ana.wait_for_messages(ana_start + 25, "the 25 answers")
        bob.wait_for_letter_events(20, "the 20 events, on Bob")

        answers = ana.messages()[ana_start:]
        events = [
            answer for answer in answers[:20] if isinstance(answer, LetterChanged)
        ]
        refusals = [
            answer for answer in answers[20:] if isinstance(answer, ErrorMessage)
        ]
        assert len(events) == 20
        assert len(refusals) == 5
        assert [event.seq for event in events] == list(
            range(seq_before + 1, seq_before + 21)
        )
        for refusal in refusals:
            assert refusal.code is ErrorCode.RATE_LIMITED
        assert state_of(clock_registry, clock_room_code).seq == seq_before + 20
        assert bob.messages()[bob_start:] == events

        fake_clock.advance(1.0)
        ana.send(burst_frame(25))
        ana.wait_for_letter_events(21, "the edit after one second")
        bob.wait_for_letter_events(21, "the edit after one second, on Bob")

        newest = ana.letter_events()[20]
        assert newest.seq == seq_before + 21
        assert newest.letter == chr(ord("A") + 25)
        assert bob.letter_events()[20] == newest
        assert len(bob.letter_events()) == 21
        assert len(ana.errors()) == 5
        assert bob.errors() == []


def test_ac3_websocket_a_throttled_client_stays_connected_and_others_are_free(
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    clock_room_code: str,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, clock_client, clock_room_code, ["Ana", "Bob"])
        ana_start = len(ana.messages())
        for index in range(21):
            ana.send(burst_frame(index))
        ana.wait_for_messages(ana_start + 21, "the 21 answers")
        assert len(ana.errors()) == 1

        bob.send(EditLetter(row=2, column=1, letter="V"))
        bob.wait_for_letter_events(21, "the edit of Bob, after the 20 of Ana")

        bobs_event = bob.letter_events()[20]
        assert bobs_event.player_id == bob.you()
        assert bobs_event.seq == 2 + 20 + 1
        assert bob.errors() == []
        assert len(ana.errors()) == 1
        assert state_of(clock_registry, clock_room_code).seq == 23


# ---- AC-4: escaping (static scan) ----------------------------------------------------

WEB_SRC_DIR = Path(__file__).resolve().parents[1] / "web" / "src"
HTML_BLOCK = re.compile(r"\{\s*@html")
RAW_HTML_CALLS = re.compile(
    r"innerHTML|outerHTML|insertAdjacentHTML|document\.write|parseFromString"
    r"|createContextualFragment|setHTMLUnsafe|srcdoc"
)


def banned_constructs(text: str, is_svelte: bool) -> list[str]:
    """The places of `text` that insert HTML instead of text."""
    patterns = [RAW_HTML_CALLS]
    if is_svelte:
        patterns.append(HTML_BLOCK)
    found: list[str] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            number = text.count("\n", 0, match.start()) + 1
            found.append(f"line {number}: {match.group(0)}")
    return found


def test_ac4_static_the_client_never_inserts_html() -> None:
    svelte_files = sorted(WEB_SRC_DIR.rglob("*.svelte"))
    typescript_files = sorted(WEB_SRC_DIR.rglob("*.ts"))
    assert len(svelte_files) >= 1
    assert len(typescript_files) >= 1

    findings: list[str] = []
    for path in svelte_files + typescript_files:
        text = path.read_text(encoding="utf-8")
        for finding in banned_constructs(text, path.suffix == ".svelte"):
            findings.append(f"{path.relative_to(WEB_SRC_DIR)} {finding}")

    assert findings == []


@pytest.mark.parametrize(
    ("text", "is_svelte"),
    [
        ("<p>{@html nickname}</p>", True),
        ("<p>{ @html nickname}</p>", True),
        ("<p>{\n  @html nickname}</p>", True),
        ("new DOMParser().parseFromString(nickname, 'text/html')", False),
        ("range.createContextualFragment(nickname)", False),
        ("element.setHTMLUnsafe(nickname)", False),
        ("frame.srcdoc = nickname", False),
        ("<iframe srcdoc={nickname}></iframe>", True),
        ("element.innerHTML = nickname", False),
        ("element.outerHTML = nickname", True),
        ("element.insertAdjacentHTML('beforeend', nickname)", False),
        ("document.write(nickname)", False),
    ],
)
def test_ac4_static_the_scan_finds_each_banned_construct(
    text: str, is_svelte: bool
) -> None:
    assert len(banned_constructs(text, is_svelte)) == 1


def test_ac4_static_the_html_block_is_only_banned_in_svelte_files() -> None:
    assert banned_constructs("const text = '{@html x}'", False) == []


# ---- AC-4: escaping (WebSocket) ----------------------------------------------


@pytest.mark.parametrize(
    "nickname",
    ["<b>Eve</b>", "Eve<", ">Eve", "Eve&Bob"],
    ids=["tag", "less-than", "greater-than", "ampersand"],
)
def test_ac4_websocket_a_nickname_with_html_characters_is_invalid_nickname(
    registry: RoomRegistry, client: TestClient, room_code: str, nickname: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer = connect(stack, client, room_code, "Eve")

        peer.send(Join(nickname=nickname, resume_token=None))
        peer.wait_for_messages(1, "the answer to the join")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.INVALID_NICKNAME
        assert state_of(registry, room_code).players == ()

        peer.send(Join(nickname="Eve", resume_token=None))
        peer.wait_for_messages(2, "the snapshot after a good nickname")
        assert isinstance(peer.messages()[1], Snapshot)


# ---- AC-4: escaping (browser, mocked socket) ---------------------------------


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


def snapshot_frame(view: GridView, players: tuple[PlayerView, ...]) -> str:
    snapshot = Snapshot(
        seq=5,
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


def open_mock_room(
    page: Page, base_url: str, view: GridView, players: tuple[PlayerView, ...]
) -> list[str]:
    """Open /r/ABC123 on a mocked socket, send `view` and `players` as a snapshot.

    Returns the list that collects the text of every dialog the page opens.
    """
    dialogs: list[str] = []

    def record_dialog(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", record_dialog)
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/ABC123")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until_page(page, lambda: len(mock.received) > 0, "the join of the page")
    mock.send(snapshot_frame(view, players))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return dialogs


def roster_nickname(page: Page, player_id: str) -> str:
    return (
        f'[data-testid="roster-player"][data-player-id="{player_id}"] '
        '[data-testid="roster-nickname"]'
    )


def test_ac4_browser_a_nickname_with_html_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = (
        player_view("p1", "Ana", 0),
        player_view("p2", "<b>Eve</b>", 3),
        player_view("p3", "<img src=x>", 5),
    )

    dialogs = open_mock_room(page, live_server, grid_view(fx01_grid), players)

    expect(page.get_by_test_id("roster-player")).to_have_count(3)
    expect(page.locator(roster_nickname(page, "p1"))).to_have_text("Ana")
    expect(page.locator(roster_nickname(page, "p2"))).to_have_text("<b>Eve</b>")
    expect(page.locator(roster_nickname(page, "p3"))).to_have_text("<img src=x>")
    expect(page.get_by_test_id("roster").locator("b")).to_have_count(0)
    expect(page.get_by_test_id("roster").locator("img")).to_have_count(0)
    expect(page.locator('img[src="x"]')).to_have_count(0)
    page.wait_for_timeout(SETTLE_MS)
    assert dialogs == []


def test_ac4_browser_html_in_a_clue_text_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = grid_view(fx01_grid)
    cells = []
    for cell in view.cells:
        if isinstance(cell, ClueCellView) and (cell.row, cell.column) == (0, 2):
            clue = cell.clues[0].model_copy(update={"text": "<i>Artiste</i> muet"})
            cell = cell.model_copy(update={"clues": (clue,)})
        cells.append(cell)
    view = view.model_copy(update={"cells": tuple(cells)})

    dialogs = open_mock_room(page, live_server, view, (player_view("p1", "Ana", 0),))

    clue_texts = page.get_by_test_id("clue-text").filter(has_text="<i>Artiste</i> muet")
    expect(clue_texts).to_have_count(1)
    expect(clue_texts).to_have_text("<i>Artiste</i> muet")
    expect(page.get_by_test_id("grid").locator("i")).to_have_count(0)
    page.wait_for_timeout(SETTLE_MS)
    assert dialogs == []
