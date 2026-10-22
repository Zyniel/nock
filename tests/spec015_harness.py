"""Shared setup of the tests of spec 015: shared letters.

This module is not a test file: pytest does not collect it. The tests of spec 015
are in `tests/test_spec_015_*.py`, one file per criterion group.

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

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir`,
`registry`, `room_code` and `client` are defined in each file that needs them, as
thin wrappers around `grid_from_text`, `make_dist_dir`, `make_registry` and
`make_app` (`room_code` is one line): a fixture imported from here would be an
unused import for ruff.
"""

from __future__ import annotations

import contextlib
import re
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession

from fonts_ready import wait_for_fonts
from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    EditLetter,
    Erase,
    ErrorMessage,
    GridFullWrong,
    GridSolved,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    Ping,
    Pong,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import RoomConfig, grid_state
from nock.server import create_app

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_SECONDS = 10.0
STALL_SECONDS = 5.0
OVERALL_SECONDS = 180.0
SETTLE_SECONDS = 0.5
POLL_SECONDS = 0.02
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 400

Edit = EditLetter | Erase
Triple = tuple[int, int, str | None]
CellValue = tuple[str | None, bool, str | None]  # letter, pencil, author
ChangeList = list[tuple[int, int, dict[str, object]]]


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
    return RoomRegistry(config=config)


def make_app(registry: RoomRegistry, dist_dir: Path) -> FastAPI:
    """An app serving `registry` (the app of the `client` fixture)."""
    return create_app(rooms=registry, dist_dir=dist_dir)


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


# ---- Helpers for the page tests (mocked socket) ------------------------------


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


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
    wait_for_fonts(page)
    return mock


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


def type_key(page: Page, key: str) -> None:
    page.keyboard.press(key)
