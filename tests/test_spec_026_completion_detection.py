"""Tests of spec 026: completion detection.

AC-1, AC-4, AC-6 (rule part), AC-8 and AC-9 check the rule on `handle_message`,
`replay` and `RoomStore`. AC-2 and AC-6 (WebSocket part) use the real WebSocket
with three simulated clients. AC-3 and AC-7 (live part) run two browsers on the
live server. AC-5 and AC-7 (mocked part) drive the room page with a mocked socket.

Not tested here: the completion by a reveal (spec 024 is not built) and the effect
of pencil letters (spec 020 is not built). The completion by an undo is tested
because spec 018 is built.

Reading of AC-5: tapping a cell sends a `select_cell` frame (selection is not
locked), so "sends no frame" is checked as "sends no frame after the tap".
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

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    Check,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridFullWrong,
    GridSolved,
    GridTarget,
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
    SelectionMoved,
    ServerMessage,
    Snapshot,
    Undo,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    handle_message,
    join_room,
    new_room,
    replay,
    snapshot_for,
)
from nock.server import create_app
from nock.store import RoomStore

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
QUIET_MS = 300
KEY_PAUSE_MS = 60
SOLVED_BUDGET_SECONDS = 1.0
SOLVED_BUDGET_MS = 1000

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

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged.
COARSE_POINTER_SCRIPT = """
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\\s/g, '') !== '(pointer:coarse)') {
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

# ---- Fixtures ----


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
def client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


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


# ---- AC-1: the last empty cell filled right solves the grid ----


def test_ac1_the_last_right_letter_is_followed_by_grid_solved(fx01_grid: Grid) -> None:
    before = full17(fx01_grid)

    outcome = write(before, "p2", LAST_CELL, "T", NOW + 754.0)

    assert events_of(outcome) == [
        LetterChanged(
            seq=20, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=21, elapsed_ms=754000),
    ]
    assert outcome.state.solved is True
    assert outcome.state.seq == 21


def test_ac1_the_snapshot_of_a_solved_room_says_so(fx01_grid: Grid) -> None:
    state = solved_room(fx01_grid)

    assert snapshot_for(state, "p1").solved is True
    assert snapshot_for(full17(fx01_grid), "p1").solved is False


def test_ac1_the_entries_are_logged_entries_of_the_step(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW + 754.0)

    assert len(outcome.entries) == 2
    for entry in outcome.entries:
        assert isinstance(entry, LogEntry)


@pytest.mark.parametrize(
    ("seconds", "elapsed_ms"),
    [(0.0, 0), (1.2346, 1235), (1.2344, 1234), (3600.0, 3_600_000)],
)
def test_ac1_elapsed_ms_is_the_rounded_time_since_the_creation(
    fx01_grid: Grid, seconds: float, elapsed_ms: int
) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW + seconds)

    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=elapsed_ms)


def test_ac1_elapsed_ms_is_never_negative(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW - 5.0)

    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=0)


def test_ac1_an_undo_that_puts_back_the_last_right_letter_completes_the_grid(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p1", (4, 3), "X").state
    state = write(state, "p2", LAST_CELL, "T").state
    assert state.seq == 22
    assert state.solved is False

    outcome = handle_message(state, "p1", Undo(), NOW + 10.0)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(
            seq=23, row=4, column=3, letter="S", pencil=False, player_id="p1"
        ),
        GridSolved(seq=24, elapsed_ms=10000),
    ]
    assert outcome.state.solved is True


def test_ac1_a_grid_whose_cells_are_all_locked_by_checks_is_solved_by_the_last_edit(
    fx01_grid: Grid,
) -> None:
    checked = handle_message(
        full17(fx01_grid), "p1", Check(target=GridTarget()), NOW + 1.0
    )
    assert checked.reply == ()
    assert checked.state.solved is False
    assert checked.state.seq == 19 + 1 + 17
    for entry in checked.entries:
        assert not isinstance(entry.event, GridSolved | GridFullWrong)

    outcome = write(checked.state, "p2", LAST_CELL, "T", NOW + 2.0)

    assert events_of(outcome) == [
        LetterChanged(
            seq=38, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=39, elapsed_ms=2000),
    ]
    assert outcome.state.solved is True


def test_ac1_a_check_of_a_full_wrong_grid_adds_no_completion_entry(
    fx01_grid: Grid,
) -> None:
    full_wrong = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    assert full_wrong.seq == 21

    outcome = handle_message(full_wrong, "p1", Check(target=GridTarget()), NOW + 1.0)

    assert outcome.reply == ()
    for entry in outcome.entries:
        assert not isinstance(entry.event, GridSolved | GridFullWrong)
    assert outcome.state.solved is False


def test_ac1_a_second_grid_solved_is_never_produced(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert outcome.entries == ()
    assert outcome.state.seq == 21


# ---- AC-2: all players learn it within 1 second (WebSocket) ----


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


def test_ac2_websocket_all_players_get_grid_solved_right_after_the_last_letter(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _ = peers
        type_17_letters(ana, bob, peers)

        sent_at = time.monotonic()
        bob.send(EditLetter(row=4, column=4, letter="T"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_solved on {peer.name}")

        for peer in peers:
            tail = peer.received()[-2:]
            letter_event = tail[0][2]
            solved_event = tail[1][2]
            assert isinstance(letter_event, LetterChanged)
            assert (letter_event.row, letter_event.column) == (4, 4)
            assert letter_event.letter == "T"
            assert letter_event.seq == 3 + 18
            assert isinstance(solved_event, GridSolved)
            assert solved_event.seq == letter_event.seq + 1
            assert solved_event.elapsed_ms >= 0
            for received_at, _, _ in tail:
                assert received_at - sent_at <= SOLVED_BUDGET_SECONDS
            assert peer.errors() == []


# ---- AC-3: every page shows the solved grid (live server) ----


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


def test_ac3_both_pages_show_the_solved_grid_within_a_second(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        play_live_game(page, bob_page, f"{live_server}/r/{code}", enter_room, "t")

        for watcher in (page, bob_page):
            expect(watcher.get_by_test_id("room-page")).to_have_attribute(
                "data-solved", "true", timeout=SOLVED_BUDGET_MS
            )
            status = watcher.get_by_test_id("grid-status")
            expect(status).to_have_attribute(
                "data-state", "solved", timeout=SOLVED_BUDGET_MS
            )
            expect(status).to_have_text(load_fr()["completion.solved"])
            expect(status).to_have_attribute("role", "status")
    finally:
        bob_context.close()


def test_ac3_the_solved_text_in_fr_json() -> None:
    assert load_fr()["completion.solved"] == "Grille terminée, bravo !"


# ---- AC-4: input is locked on the server once solved ----


@pytest.mark.parametrize(
    "message",
    [
        EditLetter(row=1, column=0, letter="A"),
        Erase(row=1, column=0),
        PencilEdit(row=1, column=0, letter="A"),
        ConfirmPencil(row=1, column=0),
        Check(target=GridTarget()),
    ],
    ids=["edit_letter", "erase", "pencil_edit", "confirm_pencil", "check"],
)
def test_ac4_a_solved_room_refuses_input_of_p1(
    fx01_grid: Grid,
    message: EditLetter | Erase | PencilEdit | ConfirmPencil | Check,
) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p1", message, NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 21
    assert outcome.state.solved is True
    assert outcome.state.cells == solved.cells
    assert outcome.to_others == ()
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac4_a_solved_room_refuses_the_undo_of_p2(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p2", Undo(), NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 21
    assert outcome.state.cells == solved.cells


def test_ac4_nothing_to_undo_is_answered_before_grid_solved(fx01_grid: Grid) -> None:
    state = full17(fx01_grid)
    solved = write(state, "p1", LAST_CELL, "T").state
    assert solved.solved is True

    outcome = handle_message(solved, "p2", Undo(), NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.NOTHING_TO_UNDO


def test_ac4_the_edit_checks_one_to_four_come_before_grid_solved(
    fx01_grid: Grid,
) -> None:
    solved = solved_room(fx01_grid)

    on_a_clue_cell = handle_message(
        solved, "p1", EditLetter(row=0, column=0, letter="A"), NOW + 755.0
    )

    assert refusal_code(on_a_clue_cell) is ErrorCode.NOT_A_LETTER_CELL


def test_ac4_a_selection_is_still_accepted(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(
        solved,
        "p1",
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        NOW + 755.0,
    )

    assert outcome.reply == ()
    assert outcome.entries == ()
    assert len(outcome.to_others) == 1
    assert isinstance(outcome.to_others[0], SelectionMoved)
    assert outcome.to_others[0].player_id == "p1"


def test_ac4_websocket_an_edit_after_the_solution_is_refused_to_its_sender_only(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, cy = peers
        type_17_letters(ana, bob, peers)
        bob.send(EditLetter(row=4, column=4, letter="T"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_solved on {peer.name}")

        cy.send(EditLetter(row=1, column=0, letter="A"))
        cy.wait_until(lambda: len(cy.errors()) == 1, "the refusal on Cy")
        ana.send(Undo())
        ana.wait_until(lambda: len(ana.errors()) == 1, "the refusal on Ana")

        assert [error.code for error in cy.errors()] == [ErrorCode.GRID_SOLVED]
        assert [error.code for error in ana.errors()] == [ErrorCode.GRID_SOLVED]
        assert bob.errors() == []
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 3 + 18 + 1
        assert state.solved is True
        for peer in peers:
            assert peer.last_seq() == 3 + 18 + 1


# ---- Helpers for the browser tests with a mocked socket ----


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

    def sent_types(self) -> list[str]:
        types: list[str] = []
        for frame in self.received:
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
    wait_until_page(page, lambda: len(mock.received) > 0)
    view = with_letter_cells(grid_view(fx01_grid), changes)
    mock.send(snapshot_frame(view, seq, solved))
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


def grid_solved_frame(seq: int) -> str:
    return GridSolved(seq=seq, elapsed_ms=1000).model_dump_json()


def grid_full_wrong_frame(seq: int) -> str:
    return GridFullWrong(seq=seq).model_dump_json()


def expect_seq(page: Page, seq: int) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def expect_selection(page: Page, row: int, column: int) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


GRID_CONTENT_SCRIPT = """
grid => Array.from(grid.querySelectorAll('*')).map(element => {
    const data = {};
    for (const attribute of element.attributes) {
        if (attribute.name.startsWith('data-')) {
            data[attribute.name] = attribute.value;
        }
    }
    const ownText = Array.from(element.childNodes)
        .filter(node => node.nodeType === Node.TEXT_NODE)
        .map(node => node.textContent.trim())
        .join('');
    return [element.tagName, ownText, data];
})
"""


def grid_content(page: Page) -> list[object]:
    """Letters and data-* attributes of every element of the grid.

    Style and sizing are left out: the grid may be resized when a banner shows.
    """
    content = page.get_by_test_id("grid").evaluate(GRID_CONTENT_SCRIPT)
    assert isinstance(content, list)
    return content


# ---- AC-5: input is locked on the page once solved ----

SOLVED_WAYS = ["grid_solved_event", "solved_snapshot"]


def open_solved_page(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> MockRoomSocket:
    """A page on a full, right grid that is solved, by an event or by a snapshot."""
    changes = letters_except([])
    if way == "solved_snapshot":
        return open_fx01(page, live_server, fx01_grid, changes, seq=5, solved=True)
    mock = open_fx01(page, live_server, fx01_grid, changes, seq=5)
    mock.send(grid_solved_frame(6))
    expect_seq(page, 6)
    return mock


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_letters_erase_and_undo_keys_send_nothing_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    mock = open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)
    page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    for key in ("b", "Backspace", "Control+z", "Meta+z"):
        page.keyboard.press(key)
    page.wait_for_timeout(QUIET_MS)

    assert mock.received[already_sent:] == []
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect_selection(page, 1, 0)


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_undo_and_check_buttons_are_disabled_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()

    for identifier in ("undo-button", "check-letter", "check-word", "check-grid"):
        expect(page.get_by_test_id(identifier)).to_be_disabled()


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_arrow_keys_and_taps_still_move_the_selection_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)

    page.keyboard.press("ArrowRight")
    expect_selection(page, 1, 1)
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2)


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_the_page_shows_the_solved_attribute_and_status(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    status = page.get_by_test_id("grid-status")
    expect(status).to_have_attribute("data-state", "solved")
    expect(status).to_have_text(load_fr()["completion.solved"])


def test_ac5_control_an_unsolved_page_sends_the_same_keys(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([(1, 0)]))
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)
    page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    page.keyboard.press("b")
    page.keyboard.press("Control+z")

    wait_until_page(page, lambda: "undo" in mock.sent_types()[already_sent:])
    page.wait_for_timeout(SETTLE_MS)
    sent = mock.sent_types()[already_sent:]
    assert [kind for kind in sent if kind != "select_cell"] == ["edit_letter", "undo"]
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page; its pointer is coarse, so the keyboard shows."""
    viewport = {"width": 360, "height": 740}
    if browser_name == "firefox":
        context = browser.new_context(viewport=viewport, has_touch=True)
    else:
        context = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    try:
        yield context.new_page()
    finally:
        context.close()


def test_ac5_the_in_app_keyboard_sends_nothing_once_solved(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        touch_page, live_server, fx01_grid, letters_except([]), seq=5, solved=True
    )
    cell_at(touch_page, 1, 0).tap()
    expect_selection(touch_page, 1, 0)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    touch_page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    touch_page.locator('[data-testid="key"][data-key="B"]').tap()
    touch_page.get_by_test_id("key-delete").tap()
    touch_page.wait_for_timeout(QUIET_MS)

    assert mock.received[already_sent:] == []
    expect(cell_at(touch_page, 1, 0)).to_have_attribute("data-letter", "T")


# ---- AC-6: a full grid with a wrong letter ----


def test_ac6_a_full_wrong_grid_is_followed_by_grid_full_wrong(
    fx01_grid: Grid,
) -> None:
    before = full17(fx01_grid)

    outcome = write(before, "p2", LAST_CELL, "X")

    assert events_of(outcome) == [
        LetterChanged(
            seq=20, row=4, column=4, letter="X", pencil=False, player_id="p2"
        ),
        GridFullWrong(seq=21),
    ]
    assert outcome.state.solved is False
    assert outcome.state.seq == 21


def test_ac6_the_event_carries_nothing_but_its_type_and_seq(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "X")

    event = events_of(outcome)[1]
    assert isinstance(event, GridFullWrong)
    assert json.loads(event.model_dump_json()) == {
        "type": "grid_full_wrong",
        "seq": 21,
    }


def test_ac6_rewriting_a_letter_of_a_full_wrong_grid_adds_no_event(
    fx01_grid: Grid,
) -> None:
    full_wrong = write(full17(fx01_grid), "p2", LAST_CELL, "X").state

    outcome = write(full_wrong, "p2", LAST_CELL, "Y")

    assert events_of(outcome) == [
        LetterChanged(seq=22, row=4, column=4, letter="Y", pencil=False, player_id="p2")
    ]
    assert outcome.state.solved is False


def test_ac6_a_wrong_letter_fixed_while_another_stays_wrong_adds_no_event(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p1", (1, 2), "N").state
    state = write(state, "p2", LAST_CELL, "X").state
    assert state.seq == 22

    outcome = write(state, "p2", LAST_CELL, "T")

    assert events_of(outcome) == [
        LetterChanged(seq=23, row=4, column=4, letter="T", pencil=False, player_id="p2")
    ]
    assert outcome.state.solved is False


def test_ac6_erasing_then_filling_the_grid_again_sends_a_new_event(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    erased = handle_message(state, "p2", Erase(row=4, column=4), NOW)
    assert erased.reply == ()
    assert events_of(erased) == [
        LetterChanged(
            seq=22, row=4, column=4, letter=None, pencil=False, player_id="p2"
        )
    ]

    outcome = write(erased.state, "p2", LAST_CELL, "X")

    assert events_of(outcome) == [
        LetterChanged(
            seq=23, row=4, column=4, letter="X", pencil=False, player_id="p2"
        ),
        GridFullWrong(seq=24),
    ]


def test_ac6_an_edit_that_leaves_the_grid_not_full_adds_nothing(
    fx01_grid: Grid,
) -> None:
    outcome = write(full17(fx01_grid), "p1", (1, 2), "N")

    assert len(outcome.entries) == 1
    assert outcome.state.solved is False


def test_ac6_websocket_each_client_gets_grid_full_wrong_right_after_the_letter(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _ = peers
        type_17_letters(ana, bob, peers)

        bob.send(EditLetter(row=4, column=4, letter="X"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_full_wrong on {peer.name}")

        for peer in peers:
            frames = peer.received()
            letter_index = len(frames) - 2
            letter_event = frames[letter_index][2]
            assert isinstance(letter_event, LetterChanged)
            assert letter_event.letter == "X"
            frame_text = frames[letter_index + 1][1]
            assert json.loads(frame_text) == {
                "type": "grid_full_wrong",
                "seq": letter_event.seq + 1,
            }
            assert set(json.loads(frame_text)) == {"type", "seq"}
            assert peer.errors() == []


# ---- AC-7: all players see "grid full, not yet correct" ----

FULL_WRONG_CHANGES: ChangeList = [
    *letters_except([LAST_CELL]),
    (4, 4, {"letter": "X", "author": "p2"}),
]


def status_locator(page: Page) -> Locator:
    return page.get_by_test_id("grid-status")


def wrong_cells(page: Page) -> Locator:
    return page.locator('[data-testid="cell"][data-wrong="true"]')


def test_ac7_the_banner_follows_the_full_wrong_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    expect(status_locator(page)).to_have_count(0)

    mock.send(letter_changed_frame(6, 4, 4, "X", "p2"))
    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    status = status_locator(page)
    expect(status).to_have_attribute("data-state", "full_wrong")
    expect(status).to_have_attribute("role", "status")
    expect(status).to_have_text(load_fr()["completion.full_wrong"])
    expect(wrong_cells(page)).to_have_count(0)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")

    mock.send(letter_changed_frame(8, 4, 4, None, "p2"))

    expect_seq(page, 8)
    expect(status_locator(page)).to_have_count(0)


def test_ac7_grid_full_wrong_changes_no_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    mock.send(letter_changed_frame(6, 4, 4, "X", "p2"))
    expect_seq(page, 6)
    before = grid_content(page)

    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    assert grid_content(page) == before


def test_ac7_a_page_that_joins_a_full_wrong_grid_shows_the_banner_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, FULL_WRONG_CHANGES)

    status = status_locator(page)
    expect(status).to_have_attribute("data-state", "full_wrong")
    expect(status).to_have_text(load_fr()["completion.full_wrong"])
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


def test_ac7_a_pending_letter_does_not_count_for_the_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    cell_at(page, 4, 4).click()
    page.keyboard.press("x")
    expect(cell_at(page, 4, 4)).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: "edit_letter" in mock.sent_types())
    page.wait_for_timeout(SETTLE_MS)
    expect(status_locator(page)).to_have_count(0)

    mock.send(letter_changed_frame(6, 4, 4, "X", "p1"))
    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")


def test_ac7_the_banner_stays_while_a_wrong_letter_is_fixed_and_another_remains(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [
        *FULL_WRONG_CHANGES,
        (1, 2, {"letter": "N", "author": "p2"}),
    ]
    mock = open_fx01(page, live_server, fx01_grid, changes)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")

    mock.send(letter_changed_frame(6, 4, 4, "T", "p2"))

    expect_seq(page, 6)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")


def test_ac7_an_unsolved_page_with_empty_cells_has_no_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [])

    expect(status_locator(page)).to_have_count(0)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


def test_ac7_both_live_pages_show_full_wrong_when_the_last_letter_is_wrong(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        play_live_game(page, bob_page, f"{live_server}/r/{code}", enter_room, "x")

        for watcher in (page, bob_page):
            status = status_locator(watcher)
            expect(status).to_have_attribute(
                "data-state", "full_wrong", timeout=WAIT_TIMEOUT_MS
            )
            expect(status).to_have_text(load_fr()["completion.full_wrong"])
            expect(watcher.get_by_test_id("room-page")).to_have_attribute(
                "data-solved", "false"
            )
            expect(wrong_cells(watcher)).to_have_count(0)
    finally:
        bob_context.close()


def test_ac7_the_full_wrong_text_in_fr_json() -> None:
    assert (
        load_fr()["completion.full_wrong"] == "Grille complète, mais pas encore juste."
    )


# ---- AC-8: the 18 letters of FX-01 ----


def write_all_in_row_major(
    state: RoomState, replaced: dict[Cell, str]
) -> tuple[RoomState, list[list[object]]]:
    """`p1` writes the 18 letters (with `replaced`); return the events by edit."""
    events_by_edit: list[list[object]] = []
    for position in ROW_MAJOR:
        letter = replaced.get(position, SOLUTION[position])
        outcome = write(state, "p1", position, letter)
        events_by_edit.append(events_of(outcome))
        state = outcome.state
    return state, events_by_edit


def test_ac8_the_18_solution_letters_produce_exactly_one_grid_solved(
    fx01_grid: Grid,
) -> None:
    state, events_by_edit = write_all_in_row_major(two_player_room(fx01_grid), {})

    for events in events_by_edit[:-1]:
        assert len(events) == 1
        assert isinstance(events[0], LetterChanged)
    last = events_by_edit[-1]
    assert len(last) == 2
    assert isinstance(last[0], LetterChanged)
    assert isinstance(last[1], GridSolved)
    assert last[1].seq == last[0].seq + 1
    assert state.solved is True


def test_ac8_a_wrong_letter_at_1_2_gives_grid_full_wrong_then_the_fix_solves(
    fx01_grid: Grid,
) -> None:
    state, events_by_edit = write_all_in_row_major(
        two_player_room(fx01_grid), {(1, 2): "N"}
    )

    last = events_by_edit[-1]
    assert len(last) == 2
    assert isinstance(last[1], GridFullWrong)
    for events in events_by_edit:
        for event in events:
            assert not isinstance(event, GridSolved)
    assert state.solved is False

    outcome = write(state, "p1", (1, 2), "M")

    events = events_of(outcome)
    assert len(events) == 2
    assert isinstance(events[0], LetterChanged)
    assert isinstance(events[1], GridSolved)
    assert outcome.state.solved is True


# ---- AC-9: the solved state survives a reload ----


def play_solved_game(grid: Grid) -> tuple[RoomState, list[LogEntry]]:
    """Joins, 18 edits and `grid_solved`: the final state and every entry."""
    state = new_room(ROOM_CODE, grid, NOW)
    entries: list[LogEntry] = []
    joins = [
        ("p1", "Ana", FIRST_TOKEN),
        ("p2", "Bob", SECOND_TOKEN),
    ]
    for player_id, nickname, token in joins:
        join = Join(nickname=nickname, resume_token=None)
        joined = join_room(state, join, NOW, player_id, token)
        entries.extend(joined.entries)
        state = joined.state
    for position in ROW_MAJOR:
        outcome = write(state, "p1", position, SOLUTION[position], NOW + 100.0)
        entries.extend(outcome.entries)
        state = outcome.state
    assert state.solved is True
    return state, entries


def test_ac9_replaying_the_whole_play_gives_the_live_solved_seq_and_cells(
    fx01_grid: Grid,
) -> None:
    live, entries = play_solved_game(fx01_grid)
    assert isinstance(entries[-1].event, GridSolved)

    replayed = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in entries:
        replayed = replay(replayed, entry)

    assert replayed.solved is True
    assert replayed.seq == live.seq == 2 + 18 + 1
    assert replayed.cells == live.cells


def test_ac9_replaying_grid_full_wrong_only_moves_the_seq(fx01_grid: Grid) -> None:
    state = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    next_seq = state.seq + 1

    replayed = replay(state, LogEntry(at=NOW, event=GridFullWrong(seq=next_seq)))

    assert replayed.seq == next_seq
    assert replayed.solved is False
    assert replayed.cells == state.cells


def test_ac9_replaying_grid_solved_sets_solved(fx01_grid: Grid) -> None:
    state = full17(fx01_grid)
    entry = LogEntry(at=NOW, event=GridSolved(seq=state.seq + 1, elapsed_ms=5))

    replayed = replay(state, entry)

    assert replayed.solved is True
    assert replayed.seq == state.seq + 1


def test_ac9_a_stored_solved_room_loads_solved_and_still_refuses_edits(
    fx01_grid: Grid,
) -> None:
    live, entries = play_solved_game(fx01_grid)
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, entries)

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.solved is True
    assert loaded.seq == live.seq
    assert loaded.cells == live.cells
    refused = handle_message(
        loaded, "p1", EditLetter(row=1, column=0, letter="A"), NOW + 200.0
    )
    assert refusal_code(refused) is ErrorCode.GRID_SOLVED
    assert refused.entries == ()
