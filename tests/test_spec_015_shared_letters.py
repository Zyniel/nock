"""Tests of spec 015: shared letters.

AC-1 measures the relay of the server on localhost (p95 at most 100 ms) and the
browser on localhost (a letter within 300 ms). AC-2 and AC-4 check the page with
a mocked socket. AC-3 and AC-4 drive the real WebSocket with Python clients, each
with one reader thread. `handle_message` is also tested directly, under AC-3,
for the fields of an accepted edit.

Spec 026 adds `grid_full_wrong` events, which take seqs: the random runs of AC-1
and AC-3 and the 36 edits of AC-4 fill FX-01, so those tests count them.

Not tested here: the order and the effect of the checks of specs 016, 017, 026
and 037, the `last_edit` and `recent_edits` fields of an accepted edit (specs 018
and 037), and the `wrong` flag on the page (spec 023 owns its attribute).
"""

from __future__ import annotations

import contextlib
import random
import re
import string
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridFullWrong,
    GridSolved,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
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
    LogEntry,
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

WAIT_SECONDS = 10.0
STALL_SECONDS = 5.0
OVERALL_SECONDS = 180.0
SETTLE_SECONDS = 0.5
POLL_SECONDS = 0.02
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400
MAX_RELAY_P95_SECONDS = 0.100
RELAY_SAMPLES = 200
P95_INDEX = 189  # the 190th smallest of 200 (spec: "95th percentile")
BROWSER_BUDGET_MS = 300
CLIENT_COUNT = 4
EDITS_PER_CLIENT = 250
ERASE_SHARE = 0.1

Edit = EditLetter | Erase
Triple = tuple[int, int, str | None]
CellValue = tuple[str | None, bool, str | None]  # letter, pencil, author
ChangeList = list[tuple[int, int, dict[str, object]]]

# ---- Fixtures ---------------------------------------------------------------


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
    """A registry whose throttle never refuses and that never times a socket out.

    AC-1 and AC-3 send bursts of about 1,000 edits, so each client receives about
    1,000 letter_changed: as many as the default outbound bound. A reader that
    falls behind for a moment would be closed with 4507, so the bound is lifted.
    """
    config = RoomConfig(
        max_edits_per_second=1000,
        max_inbound_pending=1000,
        max_outbound_messages=5000,
        silence_timeout_seconds=600,
    )
    room_registry = RoomRegistry(config=config)
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving the room `room_code`."""
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- Helpers for the WebSocket tests -----------------------------------------


def letter_cells(grid: Grid) -> list[tuple[int, int]]:
    """The letter cells of `grid` in row-major order."""
    positions: list[tuple[int, int]] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


def answer_of(edit: Edit) -> Triple:
    """The (row, column, letter) of the `letter_changed` that answers `edit`."""
    if isinstance(edit, EditLetter):
        return (edit.row, edit.column, edit.letter)
    return (edit.row, edit.column, None)


class Peer:
    """A simulated client: one socket, one reader thread that keeps what arrives.

    Every message is kept with the `time.monotonic()` taken when the reader got
    its text. All waits are bounded.
    """

    def __init__(self, websocket: WebSocketTestSession) -> None:
        self._websocket = websocket
        self._arrived = threading.Condition()
        self._received: list[tuple[float, ServerMessage]] = []
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
                self._received.append((received_at, message))
                self._arrived.notify_all()

    def _keep_failure(self, text: str) -> None:
        with self._arrived:
            self._failures.append(text)
            self._arrived.notify_all()

    def send(self, message: Join | EditLetter | Erase) -> None:
        self._websocket.send_text(message.model_dump_json())

    def timed_messages(self) -> list[tuple[float, ServerMessage]]:
        with self._arrived:
            return list(self._received)

    def messages(self) -> list[ServerMessage]:
        """Every message received so far, the snapshot first."""
        return [message for _, message in self.timed_messages()]

    def snapshot(self) -> Snapshot:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first

    def events(self) -> list[ServerMessage]:
        """Every message after the snapshot."""
        return self.messages()[1:]

    def you(self) -> str:
        return self.snapshot().you

    def last_seq(self) -> int:
        """The snapshot's seq, then the seq of the last numbered event."""
        last = self.snapshot().seq
        for message in self.events():
            seq = getattr(message, "seq", None)
            if isinstance(seq, int):
                last = seq
        return last

    def full_wrong_seqs(self) -> list[int]:
        """The seq of every `grid_full_wrong` event received (spec 026)."""
        found: list[int] = []
        for message in self.events():
            if isinstance(message, GridFullWrong):
                found.append(message.seq)
        return found

    def solved_seqs(self) -> list[int]:
        """The seq of every `grid_solved` event received (spec 026)."""
        found: list[int] = []
        for message in self.events():
            if isinstance(message, GridSolved):
                found.append(message.seq)
        return found

    def answers(self) -> list[LetterChanged | ErrorMessage]:
        """The messages that answer this client's own edits."""
        you = self.you()
        answered: list[LetterChanged | ErrorMessage] = []
        for message in self.events():
            if isinstance(message, ErrorMessage):
                answered.append(message)
                continue
            if isinstance(message, LetterChanged) and message.player_id == you:
                answered.append(message)
        return answered

    def wait_for_message_count(self, count: int, what: str) -> None:
        self.wait_until(lambda: len(self.messages()) >= count, what)

    def wait_for_seq(self, seq: int, what: str) -> None:
        self.wait_until(lambda: self.last_seq() >= seq, what)

    def wait_until(
        self,
        condition: Callable[[], bool],
        what: str,
        timeout: float = WAIT_SECONDS,
    ) -> None:
        """Wait up to `timeout` seconds for `condition`, else fail the test."""
        with self._arrived:
            met = self._arrived.wait_for(
                lambda: condition() or len(self._failures) > 0, timeout
            )
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])
        if not met:
            pytest.fail(f"timed out after {timeout}s waiting for {what}")


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
        peer.wait_for_message_count(1, f"the snapshot of {name}")
        peers.append(peer)
    for peer in peers:
        peer.wait_for_seq(len(names), "every player_joined event")
    return peers


def grid_of_view(view: GridView) -> dict[tuple[int, int], CellValue]:
    """The (letter, pencil, author) of each letter cell of a grid view."""
    values: dict[tuple[int, int], CellValue] = {}
    for cell in view.cells:
        if isinstance(cell, LetterCellView):
            values[(cell.row, cell.column)] = (cell.letter, cell.pencil, cell.author)
    return values


def grid_of_peer(peer: Peer) -> dict[tuple[int, int], CellValue]:
    """The peer's copy of the grid: its snapshot, then each letter_changed in order."""
    values = grid_of_view(peer.snapshot().grid)
    for message in peer.events():
        if isinstance(message, LetterChanged):
            author = message.player_id if message.letter is not None else None
            values[(message.row, message.column)] = (
                message.letter,
                message.pencil,
                author,
            )
    return values


def server_grid(registry: RoomRegistry, code: str) -> dict[tuple[int, int], CellValue]:
    state = registry.room_state(code)
    assert state is not None
    return grid_of_view(grid_state(state))


def seqs_after_snapshot(peer: Peer) -> list[int]:
    seqs: list[int] = []
    for message in peer.events():
        seq = getattr(message, "seq", None)
        assert isinstance(seq, int), message
        seqs.append(seq)
    return seqs


def errors_received(peer: Peer) -> list[ErrorMessage]:
    errors: list[ErrorMessage] = []
    for message in peer.events():
        if isinstance(message, ErrorMessage):
            errors.append(message)
    return errors


def send_edits_together(peers: list[Peer], plans: list[list[Edit]]) -> None:
    """Send each peer's plan from its own thread, all starting together."""
    start = threading.Barrier(len(peers), timeout=WAIT_SECONDS)
    problems: list[str] = []

    def run(peer: Peer, plan: list[Edit]) -> None:
        try:
            start.wait()
            for edit in plan:
                peer.send(edit)
        except Exception as error:  # reported by the test thread
            problems.append(repr(error))

    threads: list[threading.Thread] = []
    for peer, plan in zip(peers, plans, strict=True):
        thread = threading.Thread(target=run, args=(peer, plan), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(timeout=OVERALL_SECONDS)
        assert not thread.is_alive(), "a sender thread did not finish"
    assert problems == []


def wait_with_progress(peers: list[Peer], done: Callable[[], bool], what: str) -> None:
    """Wait for `done`, failing when no peer receives anything for a while."""
    started = time.monotonic()
    last_total = -1
    last_change = started
    while not done():
        now = time.monotonic()
        total = sum(len(peer.messages()) for peer in peers)
        if total != last_total:
            last_total = total
            last_change = now
        if now - last_change > STALL_SECONDS:
            pytest.fail(
                f"nothing received for {STALL_SECONDS}s while waiting for {what}"
            )
        if now - started > OVERALL_SECONDS:
            pytest.fail(f"timed out after {OVERALL_SECONDS}s waiting for {what}")
        time.sleep(POLL_SECONDS)


def settled_server_seq(registry: RoomRegistry, code: str) -> int:
    """Return the room's seq once it has not moved for SETTLE_SECONDS."""
    last_seq = -1
    unchanged_since = time.monotonic()
    deadline = unchanged_since + OVERALL_SECONDS
    while time.monotonic() < deadline:
        state = registry.room_state(code)
        assert state is not None
        now = time.monotonic()
        if state.seq != last_seq:
            last_seq = state.seq
            unchanged_since = now
        elif now - unchanged_since >= SETTLE_SECONDS:
            return state.seq
        time.sleep(POLL_SECONDS)
    pytest.fail("the room's seq never stopped moving")


def random_edits(rng: random.Random, cells: list[tuple[int, int]]) -> list[Edit]:
    """EDITS_PER_CLIENT random edits: 90 % letters A to Z, 10 % erases."""
    edits: list[Edit] = []
    for _ in range(EDITS_PER_CLIENT):
        row, column = rng.choice(cells)
        if rng.random() < ERASE_SHARE:
            edits.append(Erase(row=row, column=column))
        else:
            letter = rng.choice(string.ascii_uppercase)
            edits.append(EditLetter(row=row, column=column, letter=letter))
    return edits


# ---- AC-1: relay to the others -----------------------------------------------


def test_ac1_server_relay_p95_is_at_most_100_ms(
    client: TestClient,
    room_code: str,
    fx01_grid: Grid,
    record_property: Callable[[str, object], None],
) -> None:
    """A sends 200 edits one by one; time from A's send to B's receipt of it."""
    cells = letter_cells(fx01_grid)
    rng = random.Random(15)
    edits: list[EditLetter] = []
    sent_at: list[float] = []
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        for index in range(RELAY_SAMPLES):
            row, column = rng.choice(cells)
            letter = rng.choice(string.ascii_uppercase)
            edit = EditLetter(row=row, column=column, letter=letter)
            edits.append(edit)
            sent_at.append(time.monotonic())
            peer_a.send(edit)
            peer_a.wait_until(
                lambda: len(peer_a.answers()) >= len(edits),
                f"the answer to edit {index + 1}",
            )
        a_id = peer_a.you()
        peer_b.wait_until(
            lambda: len(relayed_from(peer_b, a_id)) >= RELAY_SAMPLES,
            "all the letter_changed events on B",
        )
        relayed = relayed_from(peer_b, a_id)
        full_wrong_seqs = peer_b.full_wrong_seqs()

    assert len(relayed) == RELAY_SAMPLES
    first_seq = relayed[0][1].seq
    relay_times: list[float] = []
    for index, (received_at, event) in enumerate(relayed):
        edit = edits[index]
        # A `grid_full_wrong` (spec 026) takes the seq after the edit that fills
        # the grid: the later letter_changed events are shifted by it.
        shift = len([seq for seq in full_wrong_seqs if seq < event.seq])
        assert event.seq == first_seq + index + shift
        assert (event.row, event.column, event.letter) == answer_of(edit)
        assert event.pencil is False
        relay_times.append(received_at - sent_at[index])
    relay_times.sort()
    p95 = relay_times[P95_INDEX]
    record_property("relay_p95_ms", round(p95 * 1000, 2))
    record_property("relay_max_ms", round(relay_times[-1] * 1000, 2))
    print(f"AC-1 relay: p95 {p95 * 1000:.1f} ms, max {relay_times[-1] * 1000:.1f} ms")
    assert p95 <= MAX_RELAY_P95_SECONDS, (
        f"p95 (190th smallest) of {RELAY_SAMPLES} relay times, from A's send_text "
        f"to B's reader getting the matching letter_changed, localhost TestClient: "
        f"{p95 * 1000:.1f} ms, limit 100 ms (max {relay_times[-1] * 1000:.1f} ms)"
    )


def relayed_from(peer: Peer, author_id: str) -> list[tuple[float, LetterChanged]]:
    """The `letter_changed` events of `author_id` on `peer`, with receipt times."""
    found: list[tuple[float, LetterChanged]] = []
    for received_at, message in peer.timed_messages():
        if isinstance(message, LetterChanged) and message.player_id == author_id:
            found.append((received_at, message))
    return found


def test_ac1_the_author_receives_its_own_letter_changed_too(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        peer_a.wait_until(lambda: len(peer_a.answers()) == 1, "A's own answer")
        peer_b.wait_for_seq(3, "B's copy")

        expected = LetterChanged(
            seq=3, row=1, column=0, letter="T", pencil=False, player_id=peer_a.you()
        )
        assert peer_a.answers() == [expected]
        assert peer_b.events()[-1] == expected


def test_ac1_a_letter_typed_by_ana_shows_on_bobs_page_within_300_ms(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        page.locator(cell_selector(1, 0)).click()
        for column, letter in enumerate("TAMIS"):
            page.keyboard.press(letter.lower())
            bob_cell = bob_page.locator(cell_selector(1, column))
            expect(bob_cell).to_have_attribute(
                "data-letter", letter, timeout=BROWSER_BUDGET_MS
            )
    finally:
        bob_context.close()


# ---- AC-2: my letter appears at once (browser, mocked socket) ----------------


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


def snapshot_frame(view: GridView, seq: int) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=(),
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
    seq: int = 5,
    changes: ChangeList | None = None,
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
    mock.send(snapshot_frame(view, seq))
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


def expect_edits(page: Page, mock: MockRoomSocket, expected: list[Edit]) -> None:
    """Wait for the expected edits, give time for extra ones, then compare."""
    wait_until_page(page, lambda: len(sent_edits(mock)) >= len(expected))
    page.wait_for_timeout(SETTLE_MS)
    assert sent_edits(mock) == expected


def expect_cell(
    page: Page,
    row: int,
    column: int,
    letter: str,
    unconfirmed: bool,
    author: str | None = None,
) -> None:
    """Wait until the cell shows `letter`; then check the other attributes."""
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute(
        "data-unconfirmed", "true" if unconfirmed else "false"
    )
    if author is not None:
        expect(cell).to_have_attribute("data-author", author)


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


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def type_key(page: Page, key: str) -> None:
    page.keyboard.press(key)


def test_ac2_my_letter_shows_at_once_and_stays_unconfirmed_until_my_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()

    type_key(page, "t")

    expect_cell(page, 1, 0, "T", unconfirmed=True, author="")
    expect_edits(page, mock, [EditLetter(row=1, column=0, letter="T")])

    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True, author="p2")

    mock.send(letter_changed_frame(7, 1, 0, "T", "p1"))

    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_a_refused_edit_shows_the_confirmed_letter_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(error_frame(ErrorCode.CELL_LOCKED))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


@pytest.mark.parametrize(
    "code",
    [
        ErrorCode.RATE_LIMITED,
        ErrorCode.NOT_A_LETTER_CELL,
        ErrorCode.CELL_LOCKED,
        ErrorCode.STALE_EDIT,
        ErrorCode.GRID_SOLVED,
    ],
)
def test_ac2_each_edit_error_removes_the_oldest_pending_edit_only(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    mock.send(error_frame(code))

    expect_cell(page, 1, 0, "", unconfirmed=False)
    expect_cell(page, 1, 1, "A", unconfirmed=True)


@pytest.mark.parametrize(
    "code",
    [ErrorCode.NOT_HOST, ErrorCode.NOTHING_TO_UNDO, ErrorCode.INVALID_MESSAGE],
)
def test_ac2_other_errors_leave_the_pending_queue_unchanged(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    expect_cell(page, 1, 1, "A", unconfirmed=True)

    mock.send(error_frame(code))
    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))

    # The answer matched the oldest edit, (1, 0): the error took nothing off the queue.
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
    expect_cell(page, 1, 1, "A", unconfirmed=True)


def test_ac2_answers_match_the_pending_edits_first_in_first_out(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    type_key(page, "a")
    type_key(page, "m")

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")
    expect_cell(page, 1, 1, "A", unconfirmed=True)
    expect_cell(page, 1, 2, "M", unconfirmed=True)

    mock.send(error_frame(ErrorCode.RATE_LIMITED))
    expect_cell(page, 1, 1, "", unconfirmed=False)
    expect_cell(page, 1, 2, "M", unconfirmed=True)

    mock.send(letter_changed_frame(7, 1, 2, "M", "p1"))
    expect_cell(page, 1, 2, "M", unconfirmed=False, author="p1")


def test_ac2_the_newest_pending_edit_of_a_cell_is_the_one_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    cell_at(page, 1, 0).click()
    type_key(page, "x")
    expect_cell(page, 1, 0, "X", unconfirmed=True)
    expect_edits(
        page,
        mock,
        [
            EditLetter(row=1, column=0, letter="T"),
            EditLetter(row=1, column=0, letter="X"),
        ],
    )

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1"))

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p1")
    expect_cell(page, 1, 0, "X", unconfirmed=True)

    mock.send(letter_changed_frame(7, 1, 0, "X", "p1"))

    expect_cell(page, 1, 0, "X", unconfirmed=False, author="p1")


def test_ac2_my_erase_shows_an_empty_cell_and_the_answer_clears_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        seq=5,
        changes=[(1, 0, {"letter": "T", "author": "p2"})],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p2")
    cell_at(page, 1, 0).click()

    type_key(page, "Backspace")

    expect_cell(page, 1, 0, "", unconfirmed=True, author="p2")
    expect_edits(page, mock, [Erase(row=1, column=0)])

    mock.send(letter_changed_frame(6, 1, 0, None, "p1"))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


def test_ac2_another_players_erase_empties_the_cell_and_its_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        seq=5,
        changes=[(1, 0, {"letter": "T", "author": "p2"})],
    )
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p2")

    mock.send(letter_changed_frame(6, 1, 0, None, "p3"))

    expect_cell(page, 1, 0, "", unconfirmed=False, author="")


# ---- AC-3: four clients, 1,000 edits (WebSocket) -----------------------------


def test_ac3_four_clients_sending_1000_edits_end_with_the_same_grid(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    cells = letter_cells(fx01_grid)
    rng = random.Random(15)
    plans = [random_edits(rng, cells) for _ in range(CLIENT_COUNT)]
    names = ["Ana", "Bob", "Cleo", "Dan"]
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, names)
        send_edits_together(peers, plans)
        wait_with_progress(
            peers,
            lambda: all(len(peer.answers()) >= EDITS_PER_CLIENT for peer in peers),
            "every client's 250 answers",
        )
        final_seq = settled_server_seq(registry, room_code)
        wait_with_progress(
            peers,
            lambda: all(peer.last_seq() >= final_seq for peer in peers),
            "every client to receive the last seq",
        )

        expected_grid = server_grid(registry, room_code)
        for peer, plan in zip(peers, plans, strict=True):
            assert errors_received(peer) == []
            own_answers = peer.answers()
            assert len(own_answers) == EDITS_PER_CLIENT
            answered: list[Triple] = []
            for answer in own_answers:
                assert isinstance(answer, LetterChanged)
                assert answer.pencil is False
                answered.append((answer.row, answer.column, answer.letter))
            assert answered == [answer_of(edit) for edit in plan]
            assert grid_of_peer(peer) == expected_grid
            first_expected = peer.snapshot().seq + 1
            assert seqs_after_snapshot(peer) == list(
                range(first_expected, final_seq + 1)
            )

    # Spec 026: each `grid_full_wrong` and `grid_solved` takes one seq, and every
    # client got it. No edit was refused (no error above), so all 1000 were
    # accepted and each took one seq.
    full_wrong_count = len(peers[0].full_wrong_seqs())
    solved_count = len(peers[0].solved_seqs())
    accepted_edits = CLIENT_COUNT * EDITS_PER_CLIENT
    expected_seq = CLIENT_COUNT + accepted_edits + full_wrong_count + solved_count
    assert final_seq == expected_seq
    for peer in peers:
        assert peer.full_wrong_seqs() == peers[0].full_wrong_seqs()
        assert peer.solved_seqs() == peers[0].solved_seqs()
    filled = [value for value in expected_grid.values() if value[0] is not None]
    assert len(filled) > 0
    for letter, pencil, author in expected_grid.values():
        assert pencil is False
        assert (author is None) == (letter is None)


def test_ac3_every_edit_gets_one_letter_changed_in_order_even_when_nothing_changes(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    edits: list[Edit] = [
        EditLetter(row=1, column=0, letter="A"),
        EditLetter(row=1, column=0, letter="A"),
        Erase(row=1, column=1),
        Erase(row=1, column=0),
        Erase(row=1, column=0),
    ]
    with contextlib.ExitStack() as stack:
        (peer,) = join_peers(stack, client, room_code, ["Ana"])
        for edit in edits:
            peer.send(edit)
        peer.wait_until(lambda: len(peer.answers()) >= len(edits), "five answers")
        settled_server_seq(registry, room_code)

        answers = peer.answers()
        you = peer.you()
        assert answers == [
            LetterChanged(
                seq=index + 2,
                row=edit.row,
                column=edit.column,
                letter=answer_of(edit)[2],
                pencil=False,
                player_id=you,
            )
            for index, edit in enumerate(edits)
        ]
        assert seqs_after_snapshot(peer) == [2, 3, 4, 5, 6]
        final = grid_of_peer(peer)
        assert set(final.values()) == {(None, False, None)}
        assert final == server_grid(registry, room_code)
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 6


def test_ac3_an_edit_before_join_gets_not_joined_and_changes_nothing(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with client.websocket_connect(f"/api/rooms/{room_code}/ws") as websocket:
        peer = Peer(websocket)
        peer.send(EditLetter(row=1, column=0, letter="A"))
        peer.wait_until(lambda: len(peer.messages()) >= 1, "the answer to the edit")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.NOT_JOINED
    state = registry.room_state(room_code)
    assert state is not None
    assert state.seq == 0
    assert state.players == ()
    assert [cell.letter for cell in state.cells] == [None] * len(state.cells)


# ---- AC-3: the accepted edit, directly on handle_message ---------------------


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


def other_cells(state: RoomState, row: int, column: int) -> list[CellState]:
    return [cell for cell in state.cells if (cell.row, cell.column) != (row, column)]


def test_ac3_an_accepted_edit_writes_the_letter_and_numbers_the_event(
    fx01_grid: Grid,
) -> None:
    before = two_player_room(fx01_grid)

    outcome = handle_message(before, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p1",
        locked=False,
        revealed=False,
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )
    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter="T", pencil=False, player_id="p1"
            ),
        ),
    )
    assert other_cells(outcome.state, 1, 0) == other_cells(before, 1, 0)
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac3_an_edit_replaces_the_letter_the_author_and_clears_pencil_and_wrong(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p1",
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )


def test_ac3_the_same_letter_again_is_accepted_and_numbered(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    outcome = handle_message(seeded, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter="T", pencil=False, player_id="p1"
            ),
        ),
    )
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("T", "p1", 3)
    assert cell.changed_by == "p1"


def test_ac3_an_erase_empties_the_cell_and_its_author(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=0,
            letter="T",
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    outcome = handle_message(seeded, "p1", Erase(row=1, column=0), NOW)

    assert cell_state(outcome.state, 1, 0) == CellState(
        row=1,
        column=0,
        letter=None,
        pencil=False,
        author=None,
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )
    assert outcome.state.seq == 3
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=0, letter=None, pencil=False, player_id="p1"
            ),
        ),
    )


def test_ac3_erasing_an_empty_cell_is_accepted_and_changes_nothing_else(
    fx01_grid: Grid,
) -> None:
    before = two_player_room(fx01_grid)

    outcome = handle_message(before, "p2", Erase(row=1, column=1), NOW)

    assert outcome.state.seq == 3
    assert cell_state(outcome.state, 1, 1) == CellState(
        row=1, column=1, changed_seq=3, changed_by="p2"
    )
    assert other_cells(outcome.state, 1, 1) == other_cells(before, 1, 1)
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=LetterChanged(
                seq=3, row=1, column=1, letter=None, pencil=False, player_id="p2"
            ),
        ),
    )


def test_ac3_successive_edits_get_successive_seqs(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=1, letter="A"), NOW + 1
    )

    assert [entry.event.seq for entry in first.entries] == [3]
    assert [entry.event.seq for entry in second.entries] == [4]
    assert second.entries[0].at == NOW + 1
    assert second.state.seq == 4
    assert cell_state(second.state, 1, 0).changed_seq == 3
    assert cell_state(second.state, 1, 1).changed_seq == 4
    assert cell_state(second.state, 1, 1).author == "p2"


# ---- AC-4: edits to different cells never interfere --------------------------


def test_ac4_two_clients_editing_different_cells_at_once_lose_nothing(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    cells = letter_cells(fx01_grid)
    assert len(cells) == 18
    plan_a: list[Edit] = []
    plan_b: list[Edit] = []
    for row, column in cells:
        plan_a.append(EditLetter(row=row, column=column, letter="A"))
    for row, column in reversed(cells):
        plan_b.append(EditLetter(row=row, column=column, letter="B"))
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        send_edits_together([peer_a, peer_b], [plan_a, plan_b])
        wait_with_progress(
            [peer_a, peer_b],
            lambda: all(len(letter_events(peer)) >= 36 for peer in (peer_a, peer_b)),
            "36 letter_changed events on both clients",
        )
        final_seq = settled_server_seq(registry, room_code)
        wait_with_progress(
            [peer_a, peer_b],
            lambda: all(peer.last_seq() >= final_seq for peer in (peer_a, peer_b)),
            "both clients to receive the last seq",
        )

        events_a = letter_events(peer_a)
        events_b = letter_events(peer_b)
        assert events_a == events_b
        assert len(events_a) == 36
        assert errors_received(peer_a) == []
        assert errors_received(peer_b) == []
        a_cells: list[tuple[int, int]] = []
        b_cells: list[tuple[int, int]] = []
        last_letter: dict[tuple[int, int], str | None] = {}
        for event in sorted(events_a, key=lambda event: event.seq):
            position = (event.row, event.column)
            last_letter[position] = event.letter
            if event.player_id == peer_a.you():
                assert event.letter == "A"
                a_cells.append(position)
            else:
                assert event.player_id == peer_b.you()
                assert event.letter == "B"
                b_cells.append(position)
        # Each sender's own edits were applied in the order it sent them.
        assert a_cells == cells
        assert b_cells == list(reversed(cells))
        expected_grid = server_grid(registry, room_code)
        for position in cells:
            assert expected_grid[position][0] == last_letter[position]
        assert grid_of_peer(peer_a) == expected_grid
        assert grid_of_peer(peer_b) == expected_grid
        state = registry.room_state(room_code)
        assert state is not None
        # The grid becomes full once, with wrong letters: one `grid_full_wrong`.
        assert state.seq == 2 + 36 + 1
        assert peer_a.full_wrong_seqs() == peer_b.full_wrong_seqs()
        assert len(peer_a.full_wrong_seqs()) == 1


def letter_events(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.events():
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def test_ac4_a_pending_edit_stays_when_another_cell_changes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 1, "A", "p2"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True)


# ---- AC-2: pending edits and the other specs, snapshots, locked cells ---------

SOLVED_LETTERS: dict[tuple[int, int], str] = {
    (0, 1): "N",
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
    (3, 1): "A",
    (3, 2): "M",
    (3, 3): "E",
    (3, 4): "N",
    (4, 1): "L",
    (4, 2): "E",
    (4, 3): "S",
    (4, 4): "T",
}


def solved_except(empty: list[tuple[int, int]]) -> ChangeList:
    """Confirmed letters for every FX-01 letter cell but the `empty` ones."""
    changes: ChangeList = []
    for position, letter in SOLVED_LETTERS.items():
        if position not in empty:
            changes.append((position[0], position[1], {"letter": letter}))
    return changes


def clue_named(page: Page, text: str) -> Locator:
    """The `clue` element whose text is exactly `text`."""
    clue_text = page.get_by_test_id("clue-text").get_by_text(text, exact=True)
    return page.get_by_test_id("clue").filter(has=clue_text)


def expect_selected_cell(page: Page, row: int, column: int) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


def test_ac2_tab_skips_a_word_whose_last_cell_holds_my_unconfirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Guards specs 009 and 007 under pending edits: a cell shows my letter.

    Only (1, 4) is empty, so typing `s` there finishes the only unfinished word
    as shown. The mock never answers, so the letter stays pending. Tab must then
    find no unfinished word and leave the selection where it is.
    """
    mock = open_fx01(page, live_server, fx01_grid, changes=solved_except([(1, 4)]))
    cell_at(page, 1, 4).click()
    type_key(page, "s")
    expect_cell(page, 1, 4, "S", unconfirmed=True)
    cell_at(page, 1, 3).click()
    expect_selected_cell(page, 1, 3)
    frames_before_tab = len(mock.received)

    page.keyboard.press("Tab")
    page.wait_for_timeout(SETTLE_MS)

    expect_selected_cell(page, 1, 3)
    assert len(mock.received) == frames_before_tab


def test_ac2_a_clue_tap_skips_a_cell_that_shows_my_unconfirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    """Guards specs 007 and 009 under pending edits: a cell shows my letter.

    The mock never answers, so the `T` typed in (1, 0) stays pending. Tapping
    the clue of that word must select (1, 1), the first cell unfilled as shown.
    """
    open_fx01(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    clue_named(page, "Artiste muet").click()
    expect_selected_cell(page, 1, 2)

    clue_named(page, "Passoire fine").click()

    expect_selected_cell(page, 1, 1)


def test_ac2_a_snapshot_after_a_reconnection_keeps_the_pending_edits(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    view = with_letter_cells(
        grid_view(fx01_grid), [(1, 1, {"letter": "A", "author": "p2"})]
    )

    mock.send(snapshot_frame(view, 9))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "9")
    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    mock.send(letter_changed_frame(10, 1, 0, "T", "p1"))
    expect_cell(page, 1, 0, "T", unconfirmed=False, author="p1")


def test_ac2_a_locked_cell_shows_its_confirmed_letter_over_a_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
    locked_cell: dict[str, object] = {"letter": "B", "author": "p2", "locked": True}
    view = with_letter_cells(grid_view(fx01_grid), [(1, 0, locked_cell)])

    mock.send(snapshot_frame(view, 9))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "9")
    expect_cell(page, 1, 0, "B", unconfirmed=False, author="p2")
