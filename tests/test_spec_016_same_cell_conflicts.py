"""Tests of spec 016: same-cell conflicts.

AC-1 is checked on `handle_message` (arrival order decides), on the real WebSocket
with two racing clients (50 rounds), and on the page with a mocked socket. AC-2
checks the flash of a replaced letter on the page. AC-3 checks the locked cell on
`handle_message`, on the real WebSocket and on the page.

Locked cells are seeded the way the spec says: `registry.add_room(state)` with a
locked cell, a snapshot with a locked cell, or a mocked `cell_locked` event.

Not tested here: `pencil_edit` and `confirm_pencil` on a locked cell (spec 020),
`nothing_to_undo` on a locked cell (spec 018), who shows who wrote a letter
(spec 019).
"""

from __future__ import annotations

import contextlib
import re
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
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
    ErrorCode,
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
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    CellState,
    RoomConfig,
    RoomState,
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

WAIT_SECONDS = 10.0
ROUNDS = 50
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
FLASH_SECONDS = 1.0
FLASH_MIN_SECONDS = 0.8
FLASH_MAX_SECONDS = 2.0
MID_FLASH_MS = 500

Edit = EditLetter | Erase
ChangeList = list[tuple[int, int, dict[str, object]]]
CellValue = tuple[str | None, str | None]  # letter, author

# ---- Fixtures ---------------------------------------------------------------


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


def cell_state(state: RoomState, row: int, column: int) -> CellState:
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column})")


def locked_cell(
    author: str | None = "p2", revealed: bool = False, changed_by: str | None = "p2"
) -> CellState:
    """The cell (1, 2) holding `M`, locked."""
    return CellState(
        row=1,
        column=2,
        letter="M",
        author=author,
        locked=True,
        revealed=revealed,
        changed_seq=2,
        changed_by=changed_by,
    )


def room_with_locked_cell(grid: Grid) -> RoomState:
    return with_cell(two_player_room(grid), locked_cell())


# ---- AC-1: the last edit received wins (Python) -------------------------------


def test_ac1_python_the_second_edit_received_overwrites_the_first(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=0, letter="B"), NOW
    )

    assert [entry.event.seq for entry in first.entries] == [3]
    assert [entry.event.seq for entry in second.entries] == [4]
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_by, cell.changed_seq) == (
        "B",
        "p2",
        "p2",
        4,
    )


def test_ac1_python_the_other_arrival_order_gives_the_other_winner(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p2", EditLetter(row=1, column=0, letter="B"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="A"), NOW
    )

    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p1", 4)


def test_ac1_python_the_same_letter_twice_gives_two_events_and_the_second_author(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=0, letter="A"), NOW
    )

    assert second.entries[0].event == LetterChanged(
        seq=4, row=1, column=0, letter="A", pencil=False, player_id="p2"
    )
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p2", 4)


def test_ac1_python_an_erase_after_a_letter_leaves_the_cell_empty(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(first.state, "p2", Erase(row=1, column=0), NOW)

    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_by) == (None, None, "p2")


# ---- AC-1: two clients typing in the same cell at once (WebSocket) -------------


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


def send_at_once(first: tuple[Peer, Edit], second: tuple[Peer, Edit]) -> None:
    """Send one edit from each peer, from two threads released by one barrier."""
    start = threading.Barrier(2, timeout=WAIT_SECONDS)
    problems: list[str] = []

    def run(peer: Peer, edit: Edit) -> None:
        try:
            start.wait()
            peer.send(edit)
        except Exception as error:  # reported by the test thread
            problems.append(repr(error))

    threads: list[threading.Thread] = []
    for peer, edit in (first, second):
        thread = threading.Thread(target=run, args=(peer, edit), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(timeout=WAIT_SECONDS)
        assert not thread.is_alive(), "a sender thread did not finish"
    assert problems == []


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


def test_ac1_websocket_both_clients_see_the_same_order_and_the_last_seq_wins(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        a_id = peer_a.you()
        b_id = peer_b.you()
        for round_index in range(ROUNDS):
            send_at_once(
                (peer_a, EditLetter(row=1, column=0, letter="A")),
                (peer_b, EditLetter(row=1, column=0, letter="B")),
            )
            expected_count = 2 * (round_index + 1)
            for peer in (peer_a, peer_b):
                peer.wait_for_letter_events(
                    expected_count, f"both events of round {round_index}"
                )
            events_a = peer_a.letter_events()[expected_count - 2 : expected_count]
            events_b = peer_b.letter_events()[expected_count - 2 : expected_count]
            assert events_a == events_b
            first, second = events_a
            assert second.seq == first.seq + 1
            assert first.seq == 2 + expected_count - 1
            assert {
                (first.player_id, first.letter),
                (second.player_id, second.letter),
            } == {
                (a_id, "A"),
                (b_id, "B"),
            }

            state = registry.room_state(room_code)
            assert state is not None
            server_cell = cell_state(state, 1, 0)
            assert server_cell.letter == second.letter
            assert server_cell.author == second.player_id
            assert server_cell.changed_seq == second.seq
            assert state.seq == second.seq
            expected_value = (second.letter, second.player_id)
            assert view_cell(peer_a, 1, 0) == expected_value
            assert view_cell(peer_b, 1, 0) == expected_value

        assert peer_a.letter_events() == peer_b.letter_events()
        assert peer_a.errors() == []
        assert peer_b.errors() == []


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
    wait_until_page(page, lambda: len(mock.received) > 0)
    view = grid_view(fx01_grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    mock.send(snapshot_frame(view, seq, players))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def sent_edits(mock: MockRoomSocket) -> list[Edit]:
    edits: list[Edit] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | Erase):
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


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def expect_letter(page: Page, row: int, column: int, letter: str) -> None:
    expect(cell_at(page, row, column)).to_have_attribute("data-letter", letter)


def own_letter_in_1_0() -> ChangeList:
    """Cell (1, 0) holds `T`, confirmed, written by `p1` (you)."""
    return [(1, 0, {"letter": "T", "author": "p1"})]


def background_colours(cell: Locator) -> list[str]:
    """The computed background colour of the cell and of every element inside it."""
    found = cell.evaluate(
        "el => [el, ...el.querySelectorAll('*')]"
        ".map(e => getComputedStyle(e).backgroundColor)"
    )
    assert isinstance(found, list)
    colours: list[str] = []
    for colour in found:
        assert isinstance(colour, str)
        colours.append(colour)
    return colours


def swatch_colour(page: Page, player_id: str) -> str:
    """The computed background colour of the roster swatch of `player_id`."""
    item = page.locator(f'[data-testid="roster-player"][data-player-id="{player_id}"]')
    swatch = item.get_by_test_id("roster-colour")
    colour = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
    assert isinstance(colour, str)
    return colour


# ---- AC-1: the page shows the letter of the higher seq ---------------------------


def test_ac1_browser_my_pending_letter_then_the_other_players_later_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))
    mock.send(letter_changed_frame(7, 1, 0, "B", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "B")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "false")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


def test_ac1_browser_my_pending_letter_then_my_later_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "true")
    mock.send(letter_changed_frame(7, 1, 0, "A", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "false")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p1")


def test_ac1_browser_the_same_letter_from_both_shows_the_second_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))
    mock.send(letter_changed_frame(7, 1, 0, "A", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "3")


def test_ac1_browser_my_pending_edit_replaced_by_the_other_flashes_after_my_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    # The other player replaced nothing of mine yet: my letter is only pending.
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "")

    mock.send(letter_changed_frame(7, 1, 0, "A", "p1"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "")
    mock.send(letter_changed_frame(8, 1, 0, "C", "p3"))

    expect_letter(page, 1, 0, "C")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "5")


# ---- AC-2: the flash --------------------------------------------------------------


def test_ac2_a_replaced_letter_flashes_in_the_colour_of_the_replacer_for_a_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "")
    colour_of_p2 = swatch_colour(page, "p2")
    assert colour_of_p2 not in background_colours(cell)

    sent_at = time.monotonic()
    mock.send(letter_changed_frame(6, 1, 0, "A", "p2"))

    expect(cell).to_have_attribute("data-flash", "3")
    assert colour_of_p2 in background_colours(cell)
    page.wait_for_timeout(MID_FLASH_MS)
    assert cell.get_attribute("data-flash") == "3"
    expect(cell).to_have_attribute("data-flash", "", timeout=2000)
    cleared_after = time.monotonic() - sent_at
    assert FLASH_MIN_SECONDS <= cleared_after <= FLASH_MAX_SECONDS
    assert colour_of_p2 not in background_colours(cell)
    expect_letter(page, 1, 0, "A")


def test_ac2_the_flash_uses_a_different_colour_for_each_replacer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(letter_changed_frame(6, 1, 0, "A", "p3"))

    expect(cell).to_have_attribute("data-flash", "5")
    assert swatch_colour(page, "p3") in background_colours(cell)
    assert swatch_colour(page, "p2") not in background_colours(cell)


def test_ac2_erasing_my_letter_flashes_in_the_erasers_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, None, "p2"))

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "3")
    expect_letter(page, 1, 0, "")
    assert swatch_colour(page, "p2") in background_colours(cell)


def test_ac2_the_same_letter_written_by_another_player_flashes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, "T", "p2"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "3")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


def test_ac2_a_player_who_is_gone_flashes_in_colour_index_0(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )

    mock.send(letter_changed_frame(6, 1, 0, "A", "p9"))

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-flash", "0")
    assert swatch_colour(page, "p1") in background_colours(cell)


def test_ac2_a_new_flash_on_the_same_cell_restarts_the_second(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    mock.send(letter_changed_frame(6, 1, 0, "A", "p2"))
    expect(cell).to_have_attribute("data-flash", "3")
    page.wait_for_timeout(600)
    assert cell.get_attribute("data-flash") == "3"

    second_sent_at = time.monotonic()
    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))
    mock.send(letter_changed_frame(8, 1, 0, "X", "p3"))

    expect(cell).to_have_attribute("data-flash", "5")
    page.wait_for_timeout(MID_FLASH_MS)
    # The first flash would have ended by now: only a restart keeps this one.
    assert cell.get_attribute("data-flash") == "5"
    expect(cell).to_have_attribute("data-flash", "", timeout=2000)
    cleared_after = time.monotonic() - second_sent_at
    assert FLASH_MIN_SECONDS <= cleared_after <= FLASH_MAX_SECONDS


@pytest.mark.parametrize(
    ("before", "event_letter", "event_player"),
    [
        pytest.param(("T", "p2"), "A", "p3", id="other-replaces-other"),
        pytest.param((None, None), "A", "p2", id="empty-cell"),
        pytest.param(("T", "p1"), "A", "p1", id="my-own-replacement"),
        pytest.param(("T", "p1"), None, "p1", id="my-own-erase"),
        pytest.param(("T", "p2"), None, "p3", id="other-erases-other"),
        pytest.param((None, None), None, "p2", id="erase-of-an-empty-cell"),
    ],
)
def test_ac2_no_flash_unless_another_player_replaces_my_confirmed_letter(
    page: Page,
    live_server: str,
    fx01_grid: Grid,
    before: tuple[str | None, str | None],
    event_letter: str | None,
    event_player: str,
) -> None:
    letter, author = before
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 0, {"letter": letter, "author": author})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(letter_changed_frame(6, 1, 0, event_letter, event_player))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 0, event_letter or "")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""


def test_ac2_my_own_typed_letter_never_flashes_my_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)
    cell.click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""


def test_ac2_a_cell_locked_on_my_letter_does_not_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=own_letter_in_1_0(),
        players=default_players(),
    )
    cell = cell_at(page, 1, 0)

    mock.send(cell_locked_frame(6, 1, 0, "T", revealed=False))

    expect(cell).to_have_attribute("data-locked", "true")
    assert cell.get_attribute("data-flash") == ""
    page.wait_for_timeout(SETTLE_MS)
    assert cell.get_attribute("data-flash") == ""


# ---- AC-3: a locked cell refuses edits (Python) ------------------------------------

LOCKED_EDITS: list[Edit] = [
    EditLetter(row=1, column=2, letter="X"),
    EditLetter(row=1, column=2, letter="M"),
    Erase(row=1, column=2),
]


@pytest.mark.parametrize("player_id", ["p1", "p2"])
@pytest.mark.parametrize(
    "edit", LOCKED_EDITS, ids=["other-letter", "same-letter", "erase"]
)
def test_ac3_python_a_locked_cell_refuses_the_edit_and_nothing_changes(
    fx01_grid: Grid, edit: Edit, player_id: str
) -> None:
    before = room_with_locked_cell(fx01_grid)

    outcome = handle_message(before, player_id, edit, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


@pytest.mark.parametrize(
    "edit", LOCKED_EDITS, ids=["other-letter", "same-letter", "erase"]
)
def test_ac3_python_a_revealed_locked_cell_without_author_refuses_edits(
    fx01_grid: Grid, edit: Edit
) -> None:
    before = with_cell(
        two_player_room(fx01_grid),
        locked_cell(author=None, revealed=True, changed_by=None),
    )

    outcome = handle_message(before, "p1", edit, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


def test_ac3_python_the_neighbour_of_a_locked_cell_still_accepts_edits(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid)

    outcome = handle_message(before, "p1", EditLetter(row=1, column=1, letter="X"), NOW)

    assert outcome.reply == ()
    assert outcome.state.seq == 3
    assert cell_state(outcome.state, 1, 1).letter == "X"
    assert cell_state(outcome.state, 1, 2) == locked_cell()


def test_ac3_python_a_locked_cell_is_refused_before_the_stale_edit_check(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid)
    edit = EditLetter(row=1, column=2, letter="X", base_seq=0)

    outcome = handle_message(before, "p1", edit, NOW)

    assert outcome.state == before
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


def test_ac3_python_a_locked_cell_is_refused_before_the_solved_check(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid).model_copy(update={"solved": True})

    outcome = handle_message(before, "p1", Erase(row=1, column=2), NOW)

    assert outcome.state == before
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


def test_ac3_python_the_rate_limit_is_checked_before_the_lock(
    fx01_grid: Grid,
) -> None:
    base = room_with_locked_cell(fx01_grid)
    players = []
    for player in base.players:
        if player.player_id == "p1":
            players.append(player.model_copy(update={"recent_edits": (NOW,)}))
        else:
            players.append(player)
    before = base.model_copy(update={"players": tuple(players)})
    config = RoomConfig(max_edits_per_second=1)

    outcome = handle_message(
        before, "p1", EditLetter(row=1, column=2, letter="X"), NOW, config
    )

    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.RATE_LIMITED


# ---- AC-3: a locked cell refuses edits (WebSocket) ----------------------------------


def test_ac3_websocket_both_players_are_refused_on_a_locked_cell(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    registry.add_room(
        with_cell(new_room(ROOM_CODE, fx01_grid, START_TIME), locked_cell())
    )
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, ROOM_CODE, ["Ana", "Bob"])
        seq_before = peer_a.last_seq()
        assert seq_before == 2
        for peer in (peer_a, peer_b):
            peer.send(EditLetter(row=1, column=2, letter="X"))
            peer.send(Erase(row=1, column=2))
        for peer in (peer_a, peer_b):
            peer.wait_for_errors(2, "two errors")

        state = registry.room_state(ROOM_CODE)
        assert state is not None
        assert state.seq == seq_before
        assert cell_state(state, 1, 2) == locked_cell()

        # An accepted edit afterwards proves no letter_changed came before it.
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        for peer in (peer_a, peer_b):
            peer.wait_for_letter_events(1, "the T edit")

        for peer in (peer_a, peer_b):
            codes = [error.code for error in peer.errors()]
            assert codes == [ErrorCode.CELL_LOCKED, ErrorCode.CELL_LOCKED]
            events = peer.letter_events()
            assert [(event.row, event.column) for event in events] == [(1, 0)]
            assert view_cell(peer, 1, 2) == ("M", "p2")
    final = registry.room_state(ROOM_CODE)
    assert final is not None
    assert cell_state(final, 1, 2) == locked_cell()


# ---- AC-3: a locked cell on the page ------------------------------------------


def test_ac3_browser_cell_locked_shows_the_letter_and_the_lock_over_a_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell = cell_at(page, 1, 2)
    cell.click()
    page.keyboard.press("x")
    expect_letter(page, 1, 2, "X")
    expect(cell).to_have_attribute("data-locked", "false")

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-locked", "true")

    page.keyboard.press("e")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(SETTLE_MS)
    sent = sent_edits(mock)
    assert len(sent) == 1
    assert isinstance(sent[0], EditLetter)
    assert (sent[0].row, sent[0].column, sent[0].letter) == (1, 2, "X")
    expect_letter(page, 1, 2, "M")

    mock.send(error_frame(ErrorCode.CELL_LOCKED))

    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
    expect(cell).to_have_attribute("data-locked", "true")


def test_ac3_browser_typing_and_erasing_on_a_locked_cell_of_the_snapshot_send_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "M", "author": "p2", "locked": True})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)
    expect(cell).to_have_attribute("data-locked", "true")
    cell.click()

    page.keyboard.press("e")
    page.keyboard.press("Backspace")
    page.keyboard.press("Delete")
    page.wait_for_timeout(SETTLE_MS)

    assert sent_edits(mock) == []
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def test_ac3_browser_a_revealed_cell_locked_event_clears_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "Q", "author": "p2"})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)
    expect(cell).to_have_attribute("data-author", "p2")

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=True))

    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-author", "")


def test_ac3_browser_a_checked_cell_locked_event_keeps_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "M", "author": "p2"})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect(cell).to_have_attribute("data-locked", "true")
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-author", "p2")


def test_ac3_browser_a_cell_locked_event_replaces_a_different_confirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "Q", "author": "p2"})],
        players=default_players(),
    )

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect_letter(page, 1, 2, "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
