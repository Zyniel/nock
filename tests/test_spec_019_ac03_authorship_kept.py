"""Tests of spec 019, AC-3: authorship survives reconnection and is kept.

The spec adds no server change: the room already keeps, sends, resumes and
replays the author of each letter. These tests pin that behaviour in three
layers: the rules (`nock.room`, `nock.store`), the real WebSocket (a resume, then
a simulated restart as in spec 018 AC-1), and two browsers on the live server (a
reload, spec 017 decision 7). The recap that reads these authors is spec 028's
and is not tested here.

The play of the rule tests, by `p1` and `p2` on FX-01, in this order: letters, a
letter written over another player's that stays, a letter written over another
player's then undone (so the undoer becomes the author, spec 018 decision 5), an
erase, a check that locks a cell, and last a reveal (spec 024). Each behaviour is
its own test, so that the reveal, which needs spec 024, fails on its own. The
shared setup of the browser test is in `spec019_harness`.

Refined by spec 045 (the design's Auteurs mode): the browser part reads the
letters' inks, not a band. Ana turns the switch on, her page is reloaded, and the
switch is still on (`localStorage["nock.authors"]`): (1, 0) has the ink of Ana's
colour index and (1, 1) the ink of Bob's, each index read from that player's
`roster-player` `data-colour`, as before the reload. The inks are read with spec
045's readers (`spec045_harness`).
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    Check,
    EditLetter,
    Erase,
    Join,
    LeaveReason,
    LetterCellView,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    Reveal,
    RevealResult,
    ServerMessage,
    Snapshot,
    Undo,
    parse_server_message,
)
from nock.room import (
    LogEntry,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    replay,
    tick,
)
from nock.server import create_app
from nock.store import RoomStore
from spec019_harness import (
    EnterRoom,
    ana_types_t_and_bob_types_a,
    authors_switch,
    cell_at,
    grid_from_text,
    room_page,
    turn_switch_on,
)
from spec045_harness import INKS, finder_problems, read_cell

ROOM_CODE = "ABCDEF"
START_TIME = 1_000_000.0
NOW = 2_000_000.0
FIRST_TOKEN = "first-token-number-0001"
SECOND_TOKEN = "second-token-number-002"
THIRD_TOKEN = "third-token-number-0003"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
WAIT_SECONDS = 10.0
POLL_SECONDS = 0.02
RESUME_WINDOW_SECONDS = 300.0  # spec 017, RoomConfig's default

# A room whose throttle never refuses and that never times a silent socket out.
SERVER_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)

Step = tuple[str, EditLetter | Erase | Undo | Check | Reveal]
Authors = dict[tuple[int, int], str | None]

# The play, after `p1` and `p2` joined (seq 1 and 2). The comments give the seqs.
PLAY: list[Step] = [
    ("p1", EditLetter(row=1, column=0, letter="T")),  # 3
    ("p2", EditLetter(row=1, column=1, letter="A")),  # 4
    ("p1", EditLetter(row=1, column=1, letter="X")),  # 5: over p2's A
    ("p1", Undo()),  # 6: A is back, authored by p1
    ("p2", EditLetter(row=1, column=2, letter="M")),  # 7
    ("p1", EditLetter(row=3, column=3, letter="Q")),  # 8
    ("p2", EditLetter(row=3, column=3, letter="E")),  # 9: over p1's Q, stays
    ("p2", EditLetter(row=2, column=1, letter="V")),  # 10
    ("p1", Erase(row=2, column=1)),  # 11
    ("p2", EditLetter(row=1, column=4, letter="S")),  # 12
    ("p2", Check(target=CellTarget(row=1, column=0))),  # 13, 14: locks (1, 0)
]
REVEAL_STEP: Step = ("p1", Reveal(target=CellTarget(row=1, column=4)))  # 15, 16

# The authors after PLAY (every other letter cell is empty, with no author).
AUTHORS_AFTER_PLAY: Authors = {
    (1, 0): "p1",
    (1, 1): "p1",
    (1, 2): "p2",
    (1, 4): "p2",
    (2, 1): None,
    (3, 3): "p2",
}


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


# ---- Helpers on room states -------------------------------------------------


class Play:
    """A room driven with the rules: the live state and every entry, in order."""

    def __init__(self, grid: Grid) -> None:
        self.grid = grid
        self.state = new_room(ROOM_CODE, grid, START_TIME)
        self.entries: list[LogEntry] = []
        self.join("Ana", "p1", FIRST_TOKEN)
        self.join("Bob", "p2", SECOND_TOKEN)

    def join(self, nickname: str, player_id: str, token: str) -> None:
        join = Join(nickname=nickname, resume_token=None)
        outcome = join_room(self.state, join, NOW, player_id, token)
        self.state = outcome.state
        self.entries.extend(outcome.entries)

    def run(self, step: Step) -> tuple[LogEntry, ...]:
        """Apply one step, check that it was not refused, and keep its entries."""
        player_id, message = step
        outcome = handle_message(self.state, player_id, message, NOW)
        assert outcome.reply == (), f"{step} was refused: {outcome.reply}"
        self.state = outcome.state
        self.entries.extend(outcome.entries)
        return outcome.entries


def played(grid: Grid, with_reveal: bool = False) -> Play:
    """The play of this file, with or without its last step (the reveal)."""
    play = Play(grid)
    for step in PLAY:
        play.run(step)
    if with_reveal:
        play.run(REVEAL_STEP)
    return play


def authors_of(state: RoomState) -> Authors:
    """The author of every letter cell of the state."""
    authors: Authors = {}
    for cell in state.cells:
        authors[(cell.row, cell.column)] = cell.author
    return authors


def expected_authors(changes: Authors) -> Authors:
    """Every FX-01 letter cell mapped to no author, except those in `changes`."""
    authors: Authors = {(0, 1): None}
    for column in range(5):
        authors[(1, column)] = None
    for row in range(2, 5):
        for column in range(1, 5):
            authors[(row, column)] = None
    authors.update(changes)
    return authors


def replayed(grid: Grid, entries: list[LogEntry]) -> RoomState:
    """The entries replayed in order from `new_room` on the same grid."""
    state = new_room(ROOM_CODE, grid, START_TIME)
    for entry in entries:
        state = replay(state, entry)
    return state


def cell_of(state: RoomState, row: int, column: int) -> tuple[str | None, bool, bool]:
    """The (letter, locked, revealed) of a letter cell."""
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell.letter, cell.locked, cell.revealed
    pytest.fail(f"no letter cell at ({row}, {column})")


# ---- AC-3, rules: who is the author ------------------------------------------


def test_ac3_rule_a_cell_locked_by_a_check_keeps_its_author(fx01_grid: Grid) -> None:
    play = played(fx01_grid)

    assert cell_of(play.state, 1, 0) == ("T", True, False)
    assert authors_of(play.state)[(1, 0)] == "p1"


def test_ac3_rule_the_letter_put_back_by_an_undo_is_authored_by_the_undoer(
    fx01_grid: Grid,
) -> None:
    play = played(fx01_grid)

    assert cell_of(play.state, 1, 1) == ("A", False, False)
    assert authors_of(play.state)[(1, 1)] == "p1"


def test_ac3_rule_a_letter_written_over_another_is_authored_by_the_last_writer(
    fx01_grid: Grid,
) -> None:
    play = played(fx01_grid)

    assert cell_of(play.state, 3, 3) == ("E", False, False)
    assert authors_of(play.state)[(3, 3)] == "p2"


def test_ac3_rule_an_erased_cell_has_no_author(fx01_grid: Grid) -> None:
    play = played(fx01_grid)

    assert cell_of(play.state, 2, 1) == (None, False, False)
    assert authors_of(play.state)[(2, 1)] is None


def test_ac3_rule_the_whole_play_gives_the_expected_authors(fx01_grid: Grid) -> None:
    play = played(fx01_grid)

    assert authors_of(play.state) == expected_authors(AUTHORS_AFTER_PLAY)


def test_ac3_rule_a_revealed_cell_has_no_author(fx01_grid: Grid) -> None:
    play = played(fx01_grid)

    entries = play.run(REVEAL_STEP)

    events = [entry.event for entry in entries]
    assert len(events) == 2
    assert isinstance(events[0], RevealResult)
    assert events[1] == CellLocked(seq=16, row=1, column=4, letter="S", revealed=True)
    assert cell_of(play.state, 1, 4) == ("S", True, True)
    assert authors_of(play.state)[(1, 4)] is None


def test_ac3_rule_replaying_the_play_gives_every_cell_the_live_author(
    fx01_grid: Grid,
) -> None:
    play = played(fx01_grid, with_reveal=True)

    state = replayed(fx01_grid, play.entries)

    assert state.seq == play.state.seq
    assert authors_of(state) == authors_of(play.state)
    with_reveal = dict(AUTHORS_AFTER_PLAY)
    with_reveal[(1, 4)] = None
    assert authors_of(state) == expected_authors(with_reveal)


# ---- AC-3, rules: resume, time-out, store -----------------------------------


def test_ac3_rule_a_resumed_player_keeps_its_id_and_its_letters(
    fx01_grid: Grid,
) -> None:
    play = played(fx01_grid)
    gone = disconnect_player(play.state, "p1", NOW + 10).state
    resume = Join(nickname="Ana", resume_token=FIRST_TOKEN)

    outcome = join_room(gone, resume, NOW + 20, "p3", THIRD_TOKEN)

    snapshots = [message for message in outcome.reply if isinstance(message, Snapshot)]
    assert len(snapshots) == 1
    assert snapshots[0].you == "p1"
    assert [player.player_id for player in outcome.state.players] == ["p1", "p2"]
    assert outcome.state.players[0].state == PlayerState.ACTIVE
    assert authors_of(outcome.state) == expected_authors(AUTHORS_AFTER_PLAY)


def test_ac3_rule_a_timed_out_player_keeps_its_letters(fx01_grid: Grid) -> None:
    play = played(fx01_grid)
    gone = disconnect_player(play.state, "p1", NOW + 10).state

    outcome = tick(gone, NOW + 10 + RESUME_WINDOW_SECONDS + 0.5)

    departures: list[tuple[str, LeaveReason]] = []
    for entry in outcome.entries:
        if isinstance(entry.event, PlayerLeft):
            departures.append((entry.event.player_id, entry.event.reason))
    assert departures == [("p1", LeaveReason.TIMED_OUT)]
    assert "p1" not in [player.player_id for player in outcome.state.players]
    assert authors_of(outcome.state)[(1, 0)] == "p1"
    assert authors_of(outcome.state)[(1, 1)] == "p1"
    assert authors_of(outcome.state) == expected_authors(AUTHORS_AFTER_PLAY)


def store_play(store: RoomStore, play: Play, snapshot_at: int | None) -> None:
    """Record the play in `store` as the hub does; save a snapshot at one seq."""
    first = new_room(ROOM_CODE, play.grid, START_TIME)
    store.create_room(first)
    state = first
    for entry in play.entries:
        store.append(ROOM_CODE, [entry])
        state = replay(state, entry)
        if snapshot_at is not None and state.seq == snapshot_at:
            store.save_snapshot(state)


def test_ac3_rule_a_room_loaded_from_its_log_has_the_same_authors(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    play = played(fx01_grid, with_reveal=True)
    store = RoomStore(tmp_path / "nock.sqlite3")
    try:
        store_play(store, play, snapshot_at=None)

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.seq == play.state.seq
    assert authors_of(loaded) == authors_of(play.state)


def test_ac3_rule_a_room_loaded_from_a_snapshot_has_the_same_authors(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    play = played(fx01_grid, with_reveal=True)
    path = tmp_path / "nock.sqlite3"
    writer = RoomStore(path)
    try:
        store_play(writer, play, snapshot_at=9)
    finally:
        writer.close()
    reader = RoomStore(path)
    try:
        loaded = reader.load_room(ROOM_CODE)
    finally:
        reader.close()

    assert loaded is not None
    assert loaded.seq == play.state.seq
    assert authors_of(loaded) == authors_of(play.state)


# ---- Helpers for the WebSocket tests ----------------------------------------


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
                with self._arrived:
                    self._failures.append(f"unparsable message {text!r}: {error}")
                    self._arrived.notify_all()
                continue
            with self._arrived:
                self._received.append(message)
                self._arrived.notify_all()

    def send(self, message: Join | EditLetter) -> None:
        self._websocket.send_text(message.model_dump_json())

    def messages(self) -> list[ServerMessage]:
        with self._arrived:
            return list(self._received)

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

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)


def open_peer(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
) -> Peer:
    """Open a socket in `stack`, send a join and wait for the snapshot."""
    websocket = stack.enter_context(client.websocket_connect(f"/api/rooms/{code}/ws"))
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_until(lambda: len(peer.messages()) > 0, f"the snapshot of {nickname}")
    return peer


def snapshot_author(snapshot: Snapshot, row: int, column: int) -> str | None:
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell.author
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


def saw_disconnection(peer: Peer, player_id: str) -> bool:
    for message in peer.messages():
        if (
            isinstance(message, PlayerStateChanged)
            and message.player_id == player_id
            and message.state == PlayerState.DISCONNECTED
        ):
            return True
    return False


def type_t_and_a(ana: Peer, bob: Peer) -> None:
    """Ana types T at (1, 0) and Bob A at (1, 1); return once both saw both."""
    bob.wait_for_seq(2, "both joins")
    ana.send(EditLetter(row=1, column=0, letter="T"))
    ana.wait_for_seq(3, "Ana's T")
    bob.send(EditLetter(row=1, column=1, letter="A"))
    ana.wait_for_seq(4, "Bob's A on Ana")
    bob.wait_for_seq(4, "Bob's A on Bob")


class Process:
    """One server process: a store, a registry and an app on one SQLite file."""

    def __init__(self, path: Path, dist_dir: Path) -> None:
        self.store = RoomStore(path)
        self.registry = RoomRegistry(config=SERVER_CONFIG, store=self.store)
        self.app: FastAPI = create_app(rooms=self.registry, dist_dir=dist_dir)

    def shutdown(self) -> None:
        self.registry.close()
        self.store.close()

    def everyone_disconnected(self, code: str) -> bool:
        state = self.registry.room_state(code)
        if state is None:
            return False
        return all(player.state == PlayerState.DISCONNECTED for player in state.players)


def wait_for(condition: Callable[[], bool], what: str) -> None:
    """Poll `condition` for up to WAIT_SECONDS, else fail the test."""
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")
        time.sleep(POLL_SECONDS)


# ---- AC-3, WebSocket ----------------------------------------------------------


def test_ac3_websocket_a_resumed_player_gets_both_authors_and_keeps_colour_0(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    registry = RoomRegistry(config=SERVER_CONFIG)
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with contextlib.ExitStack() as stack:
            client = stack.enter_context(TestClient(app))
            ana_socket = stack.enter_context(contextlib.ExitStack())
            ana = open_peer(ana_socket, client, code, "Ana")
            bob = open_peer(stack, client, code, "Bob")
            type_t_and_a(ana, bob)
            ana_id = ana.snapshot().you
            bob_id = bob.snapshot().you
            ana_token = ana.snapshot().resume_token

            ana_socket.close()
            bob.wait_until(
                lambda: saw_disconnection(bob, ana_id), "Ana's disconnection on Bob"
            )
            ana_again = open_peer(stack, client, code, "Ana", ana_token)

            snapshot = ana_again.snapshot()
            assert snapshot.you == ana_id
            assert snapshot_author(snapshot, 1, 0) == ana_id
            assert snapshot_author(snapshot, 1, 1) == bob_id
            colours = {player.player_id: player.colour for player in snapshot.players}
            assert colours[ana_id] == 0
    finally:
        registry.close()


def test_ac3_websocket_after_a_restart_bob_gets_the_same_two_authors(
    tmp_path: Path, fx01_grid: Grid, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    with contextlib.ExitStack() as cleanup:
        one = Process(path, dist_dir)
        # Process one is never closed during the test, as a crash would not.
        cleanup.callback(one.shutdown)
        code = one.registry.register_room(fx01_grid)
        first_run = cleanup.enter_context(contextlib.ExitStack())
        first_client = first_run.enter_context(TestClient(one.app))
        ana = open_peer(first_run, first_client, code, "Ana")
        bob = open_peer(first_run, first_client, code, "Bob")
        type_t_and_a(ana, bob)
        ana_id = ana.snapshot().you
        bob_id = bob.snapshot().you
        bob_token = bob.snapshot().resume_token
        first_run.close()
        wait_for(
            lambda: one.everyone_disconnected(code),
            "process one to log the closing of both sockets",
        )

        two = Process(path, dist_dir)
        cleanup.callback(two.shutdown)
        second_run = cleanup.enter_context(contextlib.ExitStack())
        second_client = second_run.enter_context(TestClient(two.app))
        bob_again = open_peer(second_run, second_client, code, "Bob", bob_token)

        snapshot = bob_again.snapshot()
        assert snapshot.you == bob_id
        assert snapshot_author(snapshot, 1, 0) == ana_id
        assert snapshot_author(snapshot, 1, 1) == bob_id


# ---- AC-3, browser with live server -----------------------------------------


def roster_colour_index(page: Page, player_id: str) -> int:
    """A player's colour index, read from their `roster-player`'s `data-colour`."""
    row = page.locator(f'[data-testid="roster-player"][data-player-id="{player_id}"]')
    found = row.get_attribute("data-colour")
    assert found is not None, f"no data-colour for {player_id}"
    return int(found)


def ink_problems_of_t_and_a(page: Page, ana_id: str, bob_id: str) -> list[str]:
    """(1, 0) in the ink of Ana's colour index, (1, 1) in the ink of Bob's."""
    ana_colour = roster_colour_index(page, ana_id)
    bob_colour = roster_colour_index(page, bob_id)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", str(ana_colour))
    problems = finder_problems(
        "(1, 0)", read_cell(page, 1, 0), str(ana_colour), INKS[ana_colour]
    )
    problems.extend(
        finder_problems(
            "(1, 1)", read_cell(page, 1, 1), str(bob_colour), INKS[bob_colour]
        )
    )
    return problems


def test_ac3_browser_the_inks_and_the_switch_survive_a_reload(
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
        ana_id, bob_id = ana_types_t_and_bob_types_a(
            page, bob_page, f"{live_server}/r/{code}", enter_room
        )
        turn_switch_on(page)
        assert ink_problems_of_t_and_a(page, ana_id, bob_id) == []

        page.reload()

        expect(room_page(page)).to_have_attribute("data-status", "joined")
        expect(room_page(page)).to_have_attribute("data-you", ana_id)
        expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
        expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
        assert ink_problems_of_t_and_a(page, ana_id, bob_id) == []
    finally:
        bob_context.close()
