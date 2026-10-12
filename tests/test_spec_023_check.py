"""Tests of spec 023: check a letter, a word or the grid.

AC-1, AC-2, AC-6 and AC-10 check the rule on `handle_message` (and `replay`). AC-3
and AC-7 check it on the real WebSocket. AC-4 and AC-8 run two browsers on the live
server. AC-5 and AC-9 drive the room page with a mocked socket.

Spec 026 adds to AC-10 the refusal of a check on a solved grid, first in the order
of refusals (before `help_disabled`), and to AC-9 the check buttons disabled once
the grid is solved. Pencil letters (spec 020) are not tested here: no cell holds
one yet.
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
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    CellView,
    ChangeSettings,
    Check,
    CheckResult,
    CheckTarget,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridSolved,
    GridTarget,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
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
    PlayerRecord,
    RoomConfig,
    RoomState,
    grid_state,
    handle_message,
    join_room,
    new_room,
    replay,
    tick,
)
from nock.server import create_app

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
CHECK_NOW = NOW + 10.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 10.0
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

Cell = tuple[int, int]
Step = tuple[int, int, str | None]  # row, column, letter (None: erase)
ChangeList = list[tuple[int, int, dict[str, object]]]

TAMIS = WordTarget(row=0, column=0, clue_index=0)
MIME = WordTarget(row=0, column=2, clue_index=0)

# ---- Fixtures ----


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


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
        **credits(),
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


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


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


def player_record(state: RoomState, player_id: str) -> PlayerRecord:
    for player in state.players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id}")


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


def refs(*cells: Cell) -> tuple[CellRef, ...]:
    return tuple(CellRef(row=row, column=column) for row, column in cells)


def check(state: RoomState, target: CheckTarget, player_id: str = "p1") -> list[object]:
    """Run a check and return its events, after checking nothing was refused."""
    outcome = handle_message(state, player_id, Check(target=target), CHECK_NOW)
    assert outcome.reply == ()
    return [entry.event for entry in outcome.entries]


def refusal_code(reply: tuple[ServerMessage, ...]) -> ErrorCode:
    """The code of the single error in `reply`."""
    assert len(reply) == 1
    refusal = reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


def host_sets(state: RoomState, help_mode: HelpMode) -> RoomState:
    """The room after `p1` (host) changed the help mode."""
    change = ChangeSettings(
        help_mode=help_mode, reveal_budget=RevealBudget(letters=5, words=1)
    )
    outcome = handle_message(state, "p1", change, NOW)
    assert outcome.reply == ()
    return outcome.state


# ---- AC-1: a word check marks the wrong letters and locks the correct ones ----


def test_ac1_checking_a_word_gives_a_result_then_one_lock_per_correct_cell(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW)

    assert outcome.reply == ()
    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=10, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=11, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=12, row=1, column=4, letter="S", revealed=False),
    ]


def test_ac1_the_target_is_returned_as_received(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    target = WordTarget(row=0, column=0, clue_index=0)

    events = check(state, target)

    assert isinstance(events[0], CheckResult)
    assert events[0].target == target


def test_ac1_correct_cells_are_locked_and_keep_letter_and_author(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    assert after.seq == 12
    assert cell_state(after, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        author="p1",
        locked=True,
        wrong=False,
        changed_seq=10,
        changed_by=None,
    )
    assert cell_state(after, 1, 3) == CellState(
        row=1,
        column=3,
        letter="I",
        author="p1",
        locked=True,
        changed_seq=11,
        changed_by=None,
    )
    assert cell_state(after, 1, 4) == CellState(
        row=1,
        column=4,
        letter="S",
        author="p1",
        locked=True,
        changed_seq=12,
        changed_by=None,
    )


def test_ac1_a_wrong_cell_is_marked_and_keeps_letter_author_and_changed_seq(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    before = cell_state(state, 1, 1)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    assert cell_state(after, 1, 1) == before.model_copy(update={"wrong": True})
    assert cell_state(after, 1, 1).letter == "X"
    assert cell_state(after, 1, 1).author == "p1"
    assert cell_state(after, 1, 1).locked is False


def test_ac1_the_cells_outside_the_word_are_unchanged(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    for row, column in [(2, 1), (2, 2), (1, 2), (3, 1), (4, 4)]:
        assert cell_state(after, row, column) == cell_state(state, row, column)


def test_ac1_grid_state_shows_the_same_values(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    locked_t = cell_view(after, 1, 0)
    assert (locked_t.letter, locked_t.author, locked_t.locked, locked_t.wrong) == (
        "T",
        "p1",
        True,
        False,
    )
    assert locked_t.revealed is False
    for column, letter in ((3, "I"), (4, "S")):
        view = cell_view(after, 1, column)
        assert (view.letter, view.author, view.locked, view.wrong) == (
            letter,
            "p1",
            True,
            False,
        )
    struck = cell_view(after, 1, 1)
    assert (struck.letter, struck.author, struck.locked, struck.wrong) == (
        "X",
        "p1",
        False,
        True,
    )


def test_ac1_replaying_the_entries_gives_the_cells_of_the_live_step(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    outcome = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW)

    replayed = state
    for entry in outcome.entries:
        assert isinstance(entry, LogEntry)
        replayed = replay(replayed, entry)

    assert replayed.cells == outcome.state.cells
    assert replayed.seq == outcome.state.seq == 12
    assert cell_state(replayed, 1, 1).wrong is True


def test_ac1_checking_again_a_wrong_cell_lists_it_again(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    first = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    events = check(first, TAMIS)

    assert events == [
        CheckResult(
            seq=13,
            player_id="p1",
            target=TAMIS,
            correct=(),
            wrong=refs((1, 1)),
        )
    ]


def test_ac1_any_player_checks_the_letters_of_another(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    events = check(state, TAMIS, player_id="p2")

    assert isinstance(events[0], CheckResult)
    assert events[0].player_id == "p2"
    assert events[0].correct == refs((1, 0), (1, 3), (1, 4))
    assert events[0].wrong == refs((1, 1))


def test_ac1_a_check_is_input_but_not_an_edit_for_the_rate_limit(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    before = player_record(state, "p1")

    after = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    record = player_record(after, "p1")
    assert record.recent_edits == before.recent_edits
    assert record.last_input_at == CHECK_NOW
    assert record.last_seen_at == CHECK_NOW


def test_ac1_a_check_by_p2_does_not_change_the_other_player(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p2", Check(target=TAMIS), CHECK_NOW).state

    assert player_record(after, "p1") == player_record(state, "p1")


def idle_room(grid: Grid) -> RoomState:
    """`S1` after two minutes of silence: `p1` then `p2` turned idle (seq 10)."""
    config = RoomConfig(silence_timeout_seconds=3600)
    outcome = tick(s1_room(grid), NOW + 120, config)
    assert outcome.state.seq == 10
    assert player_record(outcome.state, "p1").state is PlayerState.IDLE
    assert player_record(outcome.state, "p2").state is PlayerState.IDLE
    return outcome.state


def test_ac1_a_check_wakes_an_idle_player_before_its_own_entries(
    fx01_grid: Grid,
) -> None:
    state = idle_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=TAMIS), NOW + 130)

    assert outcome.reply == ()
    assert [entry.event for entry in outcome.entries] == [
        PlayerStateChanged(seq=11, player_id="p1", state=PlayerState.ACTIVE),
        CheckResult(
            seq=12,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=13, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=14, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=15, row=1, column=4, letter="S", revealed=False),
    ]
    assert outcome.state.seq == 15
    assert player_record(outcome.state, "p1").state is PlayerState.ACTIVE
    assert player_record(outcome.state, "p1").last_input_at == NOW + 130
    assert player_record(outcome.state, "p2").state is PlayerState.IDLE


def test_ac1_a_grid_check_wakes_an_idle_player_even_when_it_finds_nothing(
    fx01_grid: Grid,
) -> None:
    state = tick(
        two_player_room(fx01_grid), NOW + 120, RoomConfig(silence_timeout_seconds=3600)
    ).state
    assert state.seq == 4

    outcome = handle_message(state, "p2", Check(target=GridTarget()), NOW + 130)

    assert [entry.event for entry in outcome.entries] == [
        PlayerStateChanged(seq=5, player_id="p2", state=PlayerState.ACTIVE),
        CheckResult(seq=6, player_id="p2", target=GridTarget(), correct=(), wrong=()),
    ]
    assert player_record(outcome.state, "p1").state is PlayerState.IDLE


# ---- AC-2: a letter check and a grid check apply the same rule ----


def test_ac2_checking_a_wrong_letter_marks_it_and_locks_nothing(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    target = CellTarget(row=2, column=2)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9, player_id="p1", target=target, correct=(), wrong=refs((2, 2))
        )
    ]
    assert outcome.state.seq == 9
    assert cell_state(outcome.state, 2, 2).wrong is True
    assert cell_state(outcome.state, 2, 2).letter == "Q"
    assert cell_state(outcome.state, 2, 2).locked is False


def test_ac2_checking_a_correct_letter_locks_it(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    target = CellTarget(row=2, column=1)

    events = check(state, target)

    assert events == [
        CheckResult(
            seq=9, player_id="p1", target=target, correct=refs((2, 1)), wrong=()
        ),
        CellLocked(seq=10, row=2, column=1, letter="V", revealed=False),
    ]


def test_ac2_checking_the_grid_covers_every_letter_cell_in_state_order(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    target = GridTarget()

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9,
            player_id="p1",
            target=target,
            correct=refs((1, 0), (1, 3), (1, 4), (2, 1)),
            wrong=refs((1, 1), (2, 2)),
        ),
        CellLocked(seq=10, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=11, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=12, row=1, column=4, letter="S", revealed=False),
        CellLocked(seq=13, row=2, column=1, letter="V", revealed=False),
    ]
    assert outcome.state.seq == 13
    assert cell_state(outcome.state, 1, 1).wrong is True
    assert cell_state(outcome.state, 2, 2).wrong is True
    assert cell_state(outcome.state, 2, 1).locked is True


def test_ac2_empty_cells_of_the_grid_are_not_touched_by_a_grid_check(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW).state

    for cell in after.cells:
        if cell.letter is None:
            assert cell == CellState(row=cell.row, column=cell.column)


def test_ac2_locked_cells_are_left_out_and_not_locked_again(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    first = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW).state

    outcome = handle_message(first, "p1", Check(target=GridTarget()), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=14,
            player_id="p1",
            target=GridTarget(),
            correct=(),
            wrong=refs((1, 1), (2, 2)),
        )
    ]
    assert cell_state(outcome.state, 1, 0) == cell_state(first, 1, 0)


def test_ac2_a_word_of_locked_letters_gives_empty_lists(fx01_grid: Grid) -> None:
    state = write_letter(s1_room(fx01_grid), "p2", 1, 1, "A")
    first = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state
    assert cell_state(first, 1, 1).locked is True

    events = check(first, TAMIS)

    assert events == [
        CheckResult(
            seq=first.seq + 1, player_id="p1", target=TAMIS, correct=(), wrong=()
        )
    ]


def test_ac2_replaying_a_grid_check_gives_the_cells_of_the_live_step(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    outcome = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW)

    replayed = state
    for entry in outcome.entries:
        replayed = replay(replayed, entry)

    assert replayed.cells == outcome.state.cells
    assert replayed.seq == 13


def test_ac2_replaying_a_lock_clears_the_wrong_mark(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    marked = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state
    assert cell_state(marked, 1, 1).wrong is True
    fixed = write_letter(marked, "p2", 1, 1, "A")
    assert cell_state(fixed, 1, 1).wrong is False
    # Mark it again by hand, then replay a lock: the lock must clear the mark.
    struck = fixed.model_copy(
        update={
            "cells": tuple(
                (
                    cell.model_copy(update={"wrong": True})
                    if (cell.row, cell.column) == (1, 1)
                    else cell
                )
                for cell in fixed.cells
            )
        }
    )
    lock = LogEntry(
        at=CHECK_NOW,
        event=CellLocked(
            seq=struck.seq + 1, row=1, column=1, letter="A", revealed=False
        ),
    )

    replayed = replay(struck, lock)

    assert cell_state(replayed, 1, 1).locked is True
    assert cell_state(replayed, 1, 1).wrong is False


# ---- Helpers for the WebSocket tests ----


class _Earned(NamedTuple):
    """Log item: the test sent `letter` to a cell, so the room may show it."""

    row: int
    column: int
    letter: str


class _Seen(NamedTuple):
    """Log item: a frame reached a client."""

    source: str
    text: str


class TrafficLog:
    """The ordered record of what the test sent and what the clients received."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: list[_Earned | _Seen] = []

    def earn(self, row: int, column: int, letter: str) -> None:
        with self._lock:
            self._items.append(_Earned(row, column, letter))

    def see(self, source: str, text: str) -> None:
        with self._lock:
            self._items.append(_Seen(source, text))

    def items(self) -> list[_Earned | _Seen]:
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


def state_of(registry: RoomRegistry, code: str) -> RoomState:
    state = registry.room_state(code)
    assert state is not None
    return state


def snapshot_cell(snapshot: Snapshot, row: int, column: int) -> LetterCellView:
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


# ---- AC-3: the result reaches all players, and a later joiner sees it ----


def test_ac3_websocket_both_players_get_the_result_then_the_lock(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.send(EditLetter(row=1, column=1, letter="X"))
        ana.wait_for_seq(4, "the two letters on Ana")
        bob.wait_for_seq(4, "the two letters on Bob")

        ana.send_text(
            '{"type": "check", "target": {"scope": "word", "row": 0, '
            '"column": 0, "clue_index": 0}}'
        )

        for peer in (ana, bob):
            peer.wait_for_seq(6, f"the check events on {peer.name}")
            assert peer.errors() == []
            assert peer.check_results() == [
                CheckResult(
                    seq=5,
                    player_id=ana.you(),
                    target=TAMIS,
                    correct=refs((1, 0)),
                    wrong=refs((1, 1)),
                )
            ]
            assert peer.cell_locks() == [
                CellLocked(seq=6, row=1, column=0, letter="T", revealed=False)
            ]
            tail = peer.messages()[-2:]
            assert [message.type for message in tail] == ["check_result", "cell_locked"]


def test_ac3_websocket_a_later_joiner_sees_the_lock_and_the_strike(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.send(EditLetter(row=1, column=1, letter="X"))
        ana.send(Check(target=TAMIS))
        bob.wait_for_seq(6, "the check events on Bob")

        cy = connect(stack, client, room_code, "Cy")
        cy.send(Join(nickname="Cy", resume_token=None))
        cy.wait_for_messages(1, "the snapshot of Cy")

        snapshot = cy.snapshot()
        locked = snapshot_cell(snapshot, 1, 0)
        assert (locked.letter, locked.locked, locked.wrong) == ("T", True, False)
        struck = snapshot_cell(snapshot, 1, 1)
        assert (struck.letter, struck.locked, struck.wrong) == ("X", False, True)


def test_ac3_websocket_a_check_does_not_use_the_edit_rate_limit(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        (ana,) = join_peers(stack, client, room_code, ["Ana"])
        for _ in range(30):
            ana.send(Check(target=GridTarget()))
        ana.wait_for_seq(31, "thirty empty checks")

        assert ana.errors() == []
        assert len(ana.check_results()) == 30
        assert ana.cell_locks() == []


# ---- Helpers for the browser tests ----


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


def sent_checks(mock: MockRoomSocket) -> list[Check]:
    checks: list[Check] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, Check):
            checks.append(message)
    return checks


def sent_letters(mock: MockRoomSocket) -> list[EditLetter]:
    edits: list[EditLetter] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter):
            edits.append(message)
    return edits


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


def check_result_frame(
    seq: int,
    target: CheckTarget,
    correct: tuple[CellRef, ...],
    wrong: tuple[CellRef, ...],
) -> str:
    event = CheckResult(
        seq=seq, player_id="p2", target=target, correct=correct, wrong=wrong
    )
    return event.model_dump_json()


def settings_frame(seq: int, help_mode: HelpMode) -> str:
    settings = RoomSettings(
        help_mode=help_mode,
        reveal_budget=RevealBudget(letters=5, words=1),
        locked=False,
    )
    event = SettingsChanged(
        seq=seq,
        player_id="p1",
        settings=settings,
        reveal_budget=RevealBudget(letters=5, words=1),
    )
    return event.model_dump_json()


def strike_through(cell: Locator) -> str:
    """The computed text-decoration-line of a cell element."""
    line = cell.evaluate("el => getComputedStyle(el).textDecorationLine")
    assert isinstance(line, str)
    return line


def expect_selection(
    page: Page, row: int, column: int, direction: str, word: str
) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)
    expect(grid).to_have_attribute("data-word", word)


def check_items(page: Page) -> Locator:
    feed = page.get_by_test_id("activity-feed")
    return feed.locator('[data-testid="feed-item"][data-kind="check"]')


def feed_text(key: str, name: str) -> str:
    return load_fr()[key].replace("{name}", name)


# ---- AC-4: every player sees the strike and the lock (live server) ----


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


def test_ac4_both_pages_show_the_strike_and_the_lock(
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
        play_ana_checks_the_word(page, bob_page, f"{live_server}/r/{code}", enter_room)

        for watcher in (page, bob_page):
            struck = cell_at(watcher, 1, 1)
            expect(struck).to_have_attribute("data-wrong", "true")
            assert "line-through" in strike_through(struck)
            locked = cell_at(watcher, 1, 0)
            expect(locked).to_have_attribute("data-locked", "true")
            expect(locked).to_have_attribute("data-wrong", "false")
            expect(locked).to_have_attribute("data-letter", "T")
    finally:
        bob_context.close()


# ---- AC-5: the strike is cleared by a new letter or a lock ----


def struck_x_and_plain_q() -> ChangeList:
    return [
        (1, 1, {"letter": "X", "author": "p2", "wrong": True}),
        (2, 2, {"letter": "Q", "author": "p2", "wrong": False}),
    ]


def test_ac5_the_snapshot_strikes_the_cell_flagged_wrong(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    struck = cell_at(page, 1, 1)
    expect(struck).to_have_attribute("data-wrong", "true")
    assert "line-through" in strike_through(struck)
    plain = cell_at(page, 2, 2)
    expect(plain).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(plain)


def test_ac5_a_check_result_strikes_the_cells_of_its_wrong_list(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    mock.send(check_result_frame(6, MIME, correct=(), wrong=refs((2, 2))))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "true")
    assert "line-through" in strike_through(cell_at(page, 2, 2))
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "true")


def test_ac5_a_new_letter_clears_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())

    mock.send(letter_changed_frame(6, 1, 1, "A", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(cell_at(page, 1, 1))


def test_ac5_a_lock_clears_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())
    mock.send(check_result_frame(6, MIME, correct=(), wrong=refs((2, 2))))
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "true")

    mock.send(letter_changed_frame(7, 1, 1, "A", "p2"))
    mock.send(cell_locked_frame(8, 2, 2, "I", revealed=True))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "8")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-wrong", "false")
    expect(cell_at(page, 2, 2)).to_have_attribute("data-locked", "true")


def test_ac5_a_pending_edit_of_mine_hides_the_strike(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, changes=struck_x_and_plain_q())
    cell_at(page, 1, 1).click()
    page.keyboard.press("b")

    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    expect(cell).to_have_attribute("data-wrong", "false")
    assert "line-through" not in strike_through(cell)
    wait_until_page(page, lambda: len(sent_letters(mock)) == 1)


# ---- AC-6: empty cells in the scope are ignored ----


def test_ac6_a_word_with_one_letter_only_reports_that_letter(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=MIME), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(
            seq=9,
            player_id="p1",
            target=MIME,
            correct=(),
            wrong=refs((2, 2)),
        )
    ]
    assert outcome.state.seq == 9


def test_ac6_the_empty_cells_of_the_word_are_unchanged(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    after = handle_message(state, "p1", Check(target=MIME), CHECK_NOW).state

    for row, column in [(1, 2), (3, 2), (4, 2)]:
        cell = cell_state(after, row, column)
        assert (cell.letter, cell.locked, cell.wrong) == (None, False, False)
        assert cell == cell_state(state, row, column)


def test_ac6_checking_an_empty_letter_cell_still_logs_an_empty_result(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    target = CellTarget(row=1, column=2)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert [entry.event for entry in outcome.entries] == [
        CheckResult(seq=9, player_id="p1", target=target, correct=(), wrong=())
    ]
    assert outcome.state.seq == 9
    assert cell_state(outcome.state, 1, 2) == cell_state(state, 1, 2)


def test_ac6_a_grid_check_of_an_empty_room_gives_an_empty_result(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    events = check(state, GridTarget())

    assert events == [
        CheckResult(seq=3, player_id="p1", target=GridTarget(), correct=(), wrong=())
    ]


# ---- AC-7: the server decides from the letters in place, and sends no answer ----


def test_ac7_rule_the_result_uses_the_letter_in_place_when_the_check_runs(
    fx01_grid: Grid,
) -> None:
    state = write_letter(s1_room(fx01_grid), "p2", 1, 1, "A")
    assert state.seq == 9

    events = check(state, TAMIS)

    assert events == [
        CheckResult(
            seq=10,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 1), (1, 3), (1, 4)),
            wrong=(),
        ),
        CellLocked(seq=11, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=12, row=1, column=1, letter="A", revealed=False),
        CellLocked(seq=13, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=14, row=1, column=4, letter="S", revealed=False),
    ]


def test_ac7_rule_a_new_letter_on_a_wrong_cell_clears_the_mark(
    fx01_grid: Grid,
) -> None:
    state = s1_room(fx01_grid)
    marked = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state
    assert cell_state(marked, 1, 1).wrong is True

    fixed = write_letter(marked, "p2", 1, 1, "B")

    assert cell_state(fixed, 1, 1).letter == "B"
    assert cell_state(fixed, 1, 1).wrong is False
    assert cell_view(fixed, 1, 1).wrong is False


def test_ac7_rule_an_erase_of_a_wrong_cell_clears_the_mark(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)
    marked = handle_message(state, "p1", Check(target=TAMIS), CHECK_NOW).state

    outcome = handle_message(marked, "p2", Erase(row=1, column=1), NOW)

    assert outcome.reply == ()
    assert cell_state(outcome.state, 1, 1).letter is None
    assert cell_state(outcome.state, 1, 1).wrong is False


ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FORBIDDEN_KEYS = ("answer", "solution")
# Values that are random identifiers: they could by chance spell a short answer.
IDENTIFIER_KEYS = ("resume_token", "player_id", "you", "author", "code")


def keys_of(value: object) -> list[str]:
    """Every key of every object inside a parsed JSON value."""
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(keys_of(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(keys_of(child))
    return keys


def without_identifiers(value: object) -> object:
    """A copy of a parsed JSON value without the random identifier values."""
    if isinstance(value, dict):
        kept: dict[str, object] = {}
        for key, child in value.items():
            if key in IDENTIFIER_KEYS:
                continue
            kept[str(key)] = without_identifiers(child)
        return kept
    if isinstance(value, list):
        kept_list: list[object] = []
        for child in value:
            kept_list.append(without_identifiers(child))
        return kept_list
    return value


def letters_in(value: object) -> list[tuple[int, int, str]]:
    """Every (row, column, letter) a frame shows at a cell."""
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
            found.extend(letters_in(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(letters_in(child))
    return found


def leaks_in(text: str, earned: dict[Cell, set[str]]) -> list[str]:
    """The rules of "What a browser may receive" that one frame breaks."""
    problems: list[str] = []
    parsed: object = json.loads(text)
    for key in keys_of(parsed):
        if key in FORBIDDEN_KEYS:
            problems.append(f"the key {key!r}")
    scanned = json.dumps(without_identifiers(parsed))
    for row, column, letter in letters_in(parsed):
        if letter not in earned.get((row, column), set()):
            problems.append(f"the unearned letter {letter!r} at ({row}, {column})")
    for answer in ANSWERS:
        if answer in scanned:
            problems.append(f"the answer {answer!r}")
    return problems


def replay_problems(log: TrafficLog) -> list[str]:
    """Replay the log in order and list every frame that breaks a rule."""
    earned: dict[Cell, set[str]] = {}
    problems: list[str] = []
    for item in log.items():
        if isinstance(item, _Earned):
            earned.setdefault((item.row, item.column), set()).add(item.letter)
            continue
        for problem in leaks_in(item.text, earned):
            problems.append(f"{item.source} received {problem}: {item.text[:120]}")
    return problems


def send_steps(peer: Peer, log: TrafficLog, steps: list[Step]) -> None:
    """Send the steps in order, noting each letter as earned before it leaves."""
    for row, column, letter in steps:
        if letter is None:
            peer.send(Erase(row=row, column=column))
        else:
            log.earn(row, column, letter)
            peer.send(EditLetter(row=row, column=column, letter=letter))


FX01_SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    FX01_SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        FX01_SOLUTION[(_row, _offset + 1)] = _letter

# A correct letter, then the three wrong letters of spec 037, then the grid check.
CORRECT_BEFORE_CHECK: list[Step] = [(1, 1, "A")]
WRONG_LETTERS: list[Step] = [(1, 0, "X"), (2, 2, "X"), (4, 4, "X")]
# The check locked (1, 1): the later edits skip that cell. With the letter before
# the check, the game types all 18 letters, and keeps the erase of spec 037.
AFTER_CHECK_FIRST: list[Step] = [
    (1, 0, "T"),
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
SEQ_AFTER_CHECK = 2 + len(CORRECT_BEFORE_CHECK) + len(WRONG_LETTERS) + 2
# The last letter of Ana completes the grid: one more entry, `grid_solved` (026).
FINAL_SEQ = (
    SEQ_AFTER_CHECK
    + 1
    + len(AFTER_CHECK_FIRST)
    + len(BOBS_LETTER)
    + len(ANAS_LAST_WORDS)
    + 1
)


def test_ac7_websocket_a_game_with_a_grid_check_carries_only_earned_letters(
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

        send_steps(ana, log, CORRECT_BEFORE_CHECK)
        send_steps(ana, log, WRONG_LETTERS)
        ana.send(Check(target=GridTarget()))
        for peer in (ana, bob):
            peer.wait_for_seq(SEQ_AFTER_CHECK, f"the check events on {peer.name}")

        cy = connect(stack, client, code, "Cy", log)
        cy.send(Join(nickname="Cy", resume_token=None))
        cy.wait_for_messages(1, "the snapshot of Cy")
        locked = snapshot_cell(cy.snapshot(), 1, 1)
        assert (locked.letter, locked.locked, locked.wrong) == ("A", True, False)
        for row, column in ((1, 0), (2, 2), (4, 4)):
            struck = snapshot_cell(cy.snapshot(), row, column)
            assert (struck.letter, struck.locked, struck.wrong) == ("X", False, True)

        send_steps(ana, log, AFTER_CHECK_FIRST)
        send_steps(bob, log, BOBS_LETTER)
        send_steps(ana, log, ANAS_LAST_WORDS)
        for peer in (ana, bob, cy):
            peer.wait_for_seq(FINAL_SEQ, f"every event on {peer.name}")

        for peer in (ana, bob, cy):
            assert peer.errors() == []
        for peer in (ana, bob):
            results = peer.check_results()
            assert len(results) == 1
            assert results[0].seq == SEQ_AFTER_CHECK - 1
            assert results[0].correct == refs((1, 1))
            assert results[0].wrong == refs((1, 0), (2, 2), (4, 4))
            assert peer.cell_locks() == [
                CellLocked(
                    seq=SEQ_AFTER_CHECK, row=1, column=1, letter="A", revealed=False
                )
            ]

    final = state_of(registry, code)
    final_letters: dict[Cell, str] = {}
    locked_cells: list[Cell] = []
    for cell in final.cells:
        if cell.letter is not None:
            final_letters[(cell.row, cell.column)] = cell.letter
        if cell.locked:
            locked_cells.append((cell.row, cell.column))
    assert final_letters == FX01_SOLUTION
    assert locked_cells == [(1, 1)]
    assert replay_problems(log) == []


# ---- AC-8: each check adds a line to the activity feed (live server) ----


def test_ac8_each_check_adds_a_feed_line_with_the_player_and_the_scope(
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
        play_ana_checks_the_word(page, bob_page, f"{live_server}/r/{code}", enter_room)
        word_line = feed_text("feed.check.word", "Ana")
        for watcher in (page, bob_page):
            expect(check_items(watcher)).to_have_text([word_line])
            expect(check_items(watcher).first).to_have_attribute("data-kind", "check")

        cell_at(bob_page, 2, 1).click()
        bob_page.get_by_test_id("check-letter").click()
        bob_page.get_by_test_id("check-grid").click()

        expected = [
            word_line,
            feed_text("feed.check.letter", "Bob"),
            feed_text("feed.check.grid", "Bob"),
        ]
        for watcher in (page, bob_page):
            expect(check_items(watcher)).to_have_text(expected)
    finally:
        bob_context.close()


# ---- AC-9: the check controls ----


def test_ac9_the_new_fr_json_keys_have_the_texts_of_the_spec() -> None:
    texts = load_fr()

    assert texts["check.label"] == "Vérifier"
    assert texts["check.letter"] == "Lettre"
    assert texts["check.word"] == "Mot"
    assert texts["check.grid"] == "Grille"
    assert texts["check.letter_label"] == "Vérifier la lettre"
    assert texts["check.word_label"] == "Vérifier le mot"
    assert texts["check.grid_label"] == "Vérifier la grille"


def test_ac9_the_panel_holds_three_labelled_buttons_in_order(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    texts = load_fr()

    panel = page.get_by_test_id("check-panel")
    expect(panel).to_have_attribute("role", "group")
    expect(panel).to_have_attribute("aria-label", texts["check.label"])
    identifiers = panel.evaluate(
        "el => Array.from(el.querySelectorAll('button'))"
        ".map(b => b.getAttribute('data-testid'))"
    )
    assert identifiers == ["check-letter", "check-word", "check-grid"]
    for scope in ("letter", "word", "grid"):
        button = page.get_by_test_id(f"check-{scope}")
        expect(button).to_have_text(texts[f"check.{scope}"])
        expect(button).to_have_attribute("aria-label", texts[f"check.{scope}_label"])


def test_ac9_with_nothing_selected_only_the_grid_button_is_enabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)

    expect(page.get_by_test_id("check-letter")).to_be_disabled()
    expect(page.get_by_test_id("check-word")).to_be_disabled()
    expect(page.get_by_test_id("check-grid")).to_be_enabled()


def test_ac9_the_grid_button_sends_one_grid_check(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)

    page.get_by_test_id("check-grid").click()

    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)
    assert sent_checks(mock) == [Check(target=GridTarget())]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [{"type": "check", "target": {"scope": "grid"}}]


def test_ac9_the_letter_and_word_buttons_send_the_selected_cell_and_word(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2, "down", "0,2,0")
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()

    page.get_by_test_id("check-letter").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.get_by_test_id("check-word").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 2)
    page.wait_for_timeout(SETTLE_MS)

    assert sent_checks(mock) == [
        Check(target=CellTarget(row=2, column=2)),
        Check(target=MIME),
    ]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [
        {"type": "check", "target": {"scope": "letter", "row": 2, "column": 2}},
        {
            "type": "check",
            "target": {"scope": "word", "row": 0, "column": 2, "clue_index": 0},
        },
    ]
    expect_selection(page, 2, 2, "down", "0,2,0")


def test_ac9_pressing_a_button_does_not_guess_the_result(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 1, {"letter": "X", "author": "p2"})],
    )

    page.get_by_test_id("check-grid").click()
    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)

    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")


def test_ac9_a_help_mode_none_in_the_snapshot_disables_all_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, help_mode=HelpMode.NONE)
    cell_at(page, 2, 2).click()

    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()


def test_ac9_settings_changed_to_none_disables_all_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()
    expect(page.get_by_test_id("check-grid")).to_be_enabled()

    mock.send(settings_frame(6, HelpMode.NONE))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()


@pytest.mark.parametrize(
    ("taps", "row", "column", "word"),
    [(1, 0, 1, "0,0,1"), (2, 1, 1, "0,0,1")],
    ids=["tap-n-once", "tap-a-twice"],
)
def test_ac9_the_word_button_sends_the_clue_index_of_the_second_clue(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    taps: int,
    row: int,
    column: int,
    word: str,
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    for _ in range(taps):
        cell_at(page, row, column).click()
    expect_selection(page, row, column, "down", word)

    page.get_by_test_id("check-word").click()

    wait_until_page(page, lambda: len(sent_checks(mock)) >= 1)
    page.wait_for_timeout(SETTLE_MS)
    naval = WordTarget(row=0, column=0, clue_index=1)
    assert sent_checks(mock) == [Check(target=naval)]
    raw_checks = [
        json.loads(frame)
        for frame in mock.received
        if json.loads(frame).get("type") == "check"
    ]
    assert raw_checks == [
        {
            "type": "check",
            "target": {"scope": "word", "row": 0, "column": 0, "clue_index": 1},
        }
    ]
    expect_selection(page, row, column, "down", word)


@pytest.mark.parametrize(
    "code",
    [ErrorCode.HELP_DISABLED, ErrorCode.INVALID_TARGET],
    ids=["help-disabled", "invalid-target"],
)
def test_ac9_a_refused_check_leaves_the_pending_edit_alone(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 1).click()
    page.keyboard.press("b")
    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: len(sent_letters(mock)) == 1)

    mock.send(ErrorMessage(code=code, message="refused").model_dump_json())
    page.wait_for_timeout(SETTLE_MS)

    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")
    # Control: an edit answer still drops the pending edit, so it was there.
    locked_answer = ErrorMessage(code=ErrorCode.CELL_LOCKED, message="locked")
    mock.send(locked_answer.model_dump_json())
    expect(cell).to_have_attribute("data-letter", "")
    expect(cell).to_have_attribute("data-unconfirmed", "false")


# ---- AC-10: a check that cannot apply is refused and changes nothing ----


def test_ac10_help_mode_none_refuses_every_kind_of_check(fx01_grid: Grid) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.NONE)
    assert state.seq == 9
    expected_state = seen_at(state, "p1", CHECK_NOW)

    for target in (TAMIS, CellTarget(row=1, column=0), GridTarget()):
        outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

        assert refusal_code(outcome.reply) is ErrorCode.HELP_DISABLED
        assert outcome.entries == ()
        assert outcome.state == expected_state
        assert outcome.state.seq == 9


def test_ac10_help_mode_none_is_answered_before_the_target_is_looked_at(
    fx01_grid: Grid,
) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.NONE)
    bad_targets = (
        CellTarget(row=0, column=0),
        WordTarget(row=9, column=9, clue_index=0),
    )

    for target in bad_targets:
        outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

        assert refusal_code(outcome.reply) is ErrorCode.HELP_DISABLED


@pytest.mark.parametrize(
    "target",
    [CellTarget(row=0, column=0), CellTarget(row=5, column=0)],
    ids=["clue-cell", "outside-the-grid"],
)
def test_ac10_a_letter_target_off_a_letter_cell_is_not_a_letter_cell(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p1", CHECK_NOW)
    assert outcome.state.seq == 8


@pytest.mark.parametrize(
    "target",
    [
        WordTarget(row=1, column=0, clue_index=0),
        WordTarget(row=0, column=2, clue_index=1),
        WordTarget(row=9, column=9, clue_index=0),
    ],
    ids=["letter-cell", "clue-index-out-of-range", "outside-the-grid"],
)
def test_ac10_a_word_target_that_names_no_clue_is_invalid_target(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p1", CHECK_NOW)
    assert outcome.state.seq == 8


def test_ac10_a_refusal_is_for_the_sender_only(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(
        state, "p1", Check(target=CellTarget(row=0, column=0)), CHECK_NOW
    )

    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac10_help_mode_vote_acts_as_free(fx01_grid: Grid) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.VOTE)

    events = check(state, TAMIS)

    assert events == [
        CheckResult(
            seq=10,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=11, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=12, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=13, row=1, column=4, letter="S", revealed=False),
    ]


def test_ac10_websocket_a_refused_check_reaches_only_its_sender(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(Check(target=CellTarget(row=0, column=0)))
        ana.wait_until(lambda: len(ana.errors()) == 1, "the refusal")
        bob.send(Check(target=GridTarget()))
        bob.wait_for_seq(3, "the empty check on Bob")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOT_A_LETTER_CELL]
        assert bob.errors() == []
        assert len(bob.check_results()) == 1
        assert bob.check_results()[0].seq == 3


# ---- Spec 026: a check on a solved grid is refused ----


def solved_room(grid: Grid) -> RoomState:
    """`S1` with the `solved` flag set (seq 8)."""
    return s1_room(grid).model_copy(update={"solved": True})


@pytest.mark.parametrize(
    "target",
    [TAMIS, CellTarget(row=1, column=0), GridTarget()],
    ids=["word", "letter", "grid"],
)
def test_ac10_a_solved_grid_refuses_every_kind_of_check(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = solved_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 8
    assert outcome.state.cells == state.cells
    assert outcome.to_others == ()


@pytest.mark.parametrize(
    "target",
    [CellTarget(row=0, column=0), WordTarget(row=9, column=9, clue_index=0)],
    ids=["not-a-letter-cell", "invalid-target"],
)
def test_ac10_grid_solved_is_answered_before_the_target_is_looked_at(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = solved_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED


def test_ac10_grid_solved_is_answered_before_help_disabled(fx01_grid: Grid) -> None:
    state = host_sets(solved_room(fx01_grid), HelpMode.NONE)

    outcome = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()


# ---- Spec 026: the check buttons are disabled once solved ----


def test_ac9_a_solved_snapshot_disables_the_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, solved=True)
    cell_at(page, 2, 2).click()

    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()
    page.wait_for_timeout(SETTLE_MS)
    assert sent_checks(mock) == []


def test_ac9_a_grid_solved_event_disables_the_three_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("check-letter")).to_be_enabled()
    expect(page.get_by_test_id("check-word")).to_be_enabled()
    expect(page.get_by_test_id("check-grid")).to_be_enabled()

    mock.send(GridSolved(seq=6, elapsed_ms=1000).model_dump_json())

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    for scope in ("letter", "word", "grid"):
        expect(page.get_by_test_id(f"check-{scope}")).to_be_disabled()
