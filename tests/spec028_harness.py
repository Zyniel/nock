"""Shared setup of the tests of spec 028: the end-of-game recap.

This module is not a test file: pytest does not collect it. The tests of spec 028
are in `tests/test_spec_028_*.py`, one file per criterion group:

- `test_spec_028_ac01_ac04_rules.py`: AC-1 to AC-4 and AC-8 (`build_recap` and
  `public_recap` on plays of the rules);
- `test_spec_028_ac01_ac08_http.py`: AC-1, AC-4, AC-5, AC-6 and AC-8 (the routes,
  games played over the room socket, the fake clock);
- `test_spec_028_ac09_share_token_and_store.py`: AC-9 (`RoomStore`, `RoomRegistry`,
  the share token);
- `test_spec_028_ac01_ac02_ac07_dialog.py`: AC-1, AC-2, AC-5 (copy button) and AC-7
  (the dialog, page with a mocked socket);
- `test_spec_028_ac05_ac06_live_pages.py`: AC-5 and AC-6 (browsers on the live
  server);
- `test_spec_028_ac10_a11y_and_layout.py`: AC-10 (accessibility, the eight window
  sizes, the scans, `fr.json`).

Nothing here imports `nock.recap`: a browser test must fail on a missing page
element, not on a missing module, and the page tests answer the recap route with
plain JSON built by `recap_body`. The Python and HTTP files import `nock.recap`
themselves.

Real time. The tests of this spec use no tight real-time bound. The HTTP throttle
cases use spec 011's fake clock. The browser tests wait on page state; the only
fixed waits are the "nothing happens" pauses (`QUIET_MS`).

The fixtures (`fx01_grid`, `dist_dir`, `catalogue`, `registry`...) are defined in
each test file as thin wrappers: a fixture imported from here would be an unused
import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, Route

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    ChangeSettings,
    Check,
    ClientMessage,
    EditLetter,
    Erase,
    GridSolved,
    GridTarget,
    HelpMode,
    Join,
    PencilEdit,
    RemovePlayer,
    Reveal,
    RevealBudget,
    Undo,
    WordTarget,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    handle_message,
    join_room,
    new_room,
)
from nock.store import RoomStore
from spec024_harness import (
    FIRST_17,
    FIRST_TOKEN,
    LAST_CELL,
    NOW,
    ROOM_CODE,
    ROW_MAJOR,
    SECOND_TOKEN,
    SOLUTION,
    Peer,
    join_peers,
    ping_and_wait,
)

SHARE_TOKEN = "tok_ABCDEFGHIJKLMNOP"
UNKNOWN_TOKEN = "tok_unknown_0123456789"
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{16,64}$")
THIRD_TOKEN = "third-token-number-0003"
QUIET_MS = 400
TAMIS = WordTarget(row=0, column=0, clue_index=0)
LEST = WordTarget(row=4, column=0, clue_index=0)
ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FORBIDDEN_KEYS = ("answer", "solution")
IDENTIFIER_KEYS = ("resume_token", "player_id", "you", "author", "code", "share_path")
RECAP_ROUTE = "**/api/rooms/ABC123/recap"
SOCKET_WAIT_SECONDS = 10.0

Cell = tuple[int, int]
HTTP_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)
FAKE_CLOCK_CONFIG = RoomConfig(
    tick_seconds=0.05, silence_timeout_seconds=600, max_edits_per_second=1000
)


def format_time(elapsed_ms: int) -> str:
    """Write a duration as spec 027 writes the timer: `12:34`, `1:02:05`."""
    seconds = elapsed_ms // 1000
    hours, rest = divmod(seconds, 3600)
    minutes, secs = divmod(rest, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


# ---- Plays of the rules ----


class Game:
    """A FX-01 room played with `handle_message`, and every entry it logged.

    The room is the one of "Test harness" in the spec: `new_room("ABC123", grid,
    NOW, grid_number=1, share_token=SHARE_TOKEN)`, then `p1` (Ana, host) and `p2`
    (Bob) joined at NOW (seq 2).
    """

    def __init__(self, grid: Grid, share_token: str | None = SHARE_TOKEN) -> None:
        self.state: RoomState = new_room(
            ROOM_CODE, grid, NOW, grid_number=1, share_token=share_token
        )
        self.log: list[LogEntry] = []
        self.states_by_seq: dict[int, RoomState] = {}
        self.join("Ana", "p1", FIRST_TOKEN)
        self.join("Bob", "p2", SECOND_TOKEN)
        assert self.state.seq == 2

    def keep(self, outcome: Outcome) -> None:
        """Keep a step: its state and its entries."""
        self.state = outcome.state
        self.log.extend(outcome.entries)
        self.states_by_seq[outcome.state.seq] = outcome.state

    def join(self, nickname: str, player_id: str, token: str) -> None:
        """Join a new player at NOW."""
        join = Join(nickname=nickname, resume_token=None)
        self.keep(join_room(self.state, join, NOW, player_id, token))

    def send(self, player_id: str, message: ClientMessage, now: float = NOW) -> None:
        """Send a message with `handle_message`; the step must not be refused."""
        outcome = handle_message(self.state, player_id, message, now)
        assert outcome.reply == (), outcome.reply
        self.keep(outcome)

    def write(self, player_id: str, cell: Cell, letter: str, now: float = NOW) -> None:
        """Write a letter."""
        edit = EditLetter(row=cell[0], column=cell[1], letter=letter)
        self.send(player_id, edit, now)

    def write_all(self, player_id: str, cells: list[Cell], now: float = NOW) -> None:
        """Write the right letter in each cell."""
        for cell in cells:
            self.write(player_id, cell, SOLUTION[cell], now)

    def finish(self, player_id: str, now: float = NOW + 500.0) -> None:
        """Write the right letter in every cell that does not hold it, in row order.

        The last write solves the grid.
        """
        for cell in ROW_MAJOR:
            current = self.letter_at(cell)
            if current != SOLUTION[cell]:
                self.write(player_id, cell, SOLUTION[cell], now)
        assert self.state.solved is True

    def letter_at(self, cell: Cell) -> str | None:
        """The letter the room holds at a cell."""
        for cell_state in self.state.cells:
            if (cell_state.row, cell_state.column) == cell:
                return cell_state.letter
        pytest.fail(f"no letter cell at {cell}")


def play_r(grid: Grid) -> Game:
    """`PLAY_R` of the spec: checks and reveals; the grid is solved at seq 34."""
    game = Game(grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3), (1, 4)])
    game.send("p1", Check(target=TAMIS), NOW + 10.0)
    game.send("p2", Reveal(target=CellTarget(row=0, column=1)), NOW + 20.0)
    game.send("p2", Reveal(target=LEST), NOW + 30.0)
    game.write_all("p2", [(2, 1), (2, 2), (2, 3), (2, 4)], NOW + 100.0)
    game.send("p1", Check(target=GridTarget()), NOW + 200.0)
    game.write_all("p1", [(3, 1), (3, 2), (3, 3)], NOW + 300.0)
    game.write("p2", (3, 4), "N", NOW + 754.0)
    assert game.state.solved is True
    assert game.state.seq == 34
    return game


def play_w(grid: Grid, undo_variant: bool = False) -> Game:
    """`PLAY_W` of the spec: word completions; the grid is solved at seq 23.

    With `undo_variant`, right after `p1`'s first four letters `p2` writes `X` at
    (1, 1) and undoes it, so the cell gets back `A` with `p2` as its author.
    """
    game = Game(grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3)])
    if undo_variant:
        game.write("p2", (1, 1), "X")
        game.send("p2", undo_message())
    game.write_all("p2", [(2, 4), (3, 4), (4, 4)])
    game.write("p2", (1, 4), "S")
    game.write_all("p1", [(0, 1), (2, 1), (3, 1), (4, 1)])
    game.write_all("p2", [(2, 2), (2, 3)])
    game.write_all("p1", [(3, 2), (3, 3)])
    game.send("p1", erase_message(3, 3))
    game.write("p2", (3, 3), "E")
    game.write("p2", (4, 2), "E")
    game.write("p1", (4, 3), "S")
    assert game.state.solved is True
    expected_seq = 25 if undo_variant else 23
    assert game.state.seq == expected_seq, game.state.seq
    return game


def undo_message() -> ClientMessage:
    """An `undo` message."""
    return Undo()


def erase_message(row: int, column: int) -> ClientMessage:
    """An `erase` message."""
    return Erase(row=row, column=column)


def pencil_message(cell: Cell, letter: str) -> ClientMessage:
    """A `pencil_edit` message."""
    return PencilEdit(row=cell[0], column=cell[1], letter=letter)


def vote_mode_message() -> ClientMessage:
    """The host's `change_settings` to the help mode `vote`."""
    return ChangeSettings(
        help_mode=HelpMode.VOTE, reveal_budget=RevealBudget(letters=5, words=1)
    )


def remove_message(player_id: str) -> ClientMessage:
    """The host's `remove_player`."""
    return RemovePlayer(player_id=player_id)


def renumbered(entries: list[LogEntry]) -> list[LogEntry]:
    """The entries with seq 1, 2, 3... in order (a log with an entry cut out)."""
    renumbered_entries: list[LogEntry] = []
    for number, entry in enumerate(entries, start=1):
        event = entry.event.model_copy(update={"seq": number})
        renumbered_entries.append(entry.model_copy(update={"event": event}))
    return renumbered_entries


# ---- Games over the room socket ----


def make_http_registry() -> RoomRegistry:
    """A registry whose throttle never refuses and that never times a socket out."""
    return RoomRegistry(config=HTTP_CONFIG)


def type_cells(peer: Peer, cells: list[Cell]) -> None:
    """Send the right letter of each cell from a peer, then wait for the room."""
    for row, column in cells:
        peer.send(EditLetter(row=row, column=column, letter=SOLUTION[(row, column)]))
    ping_and_wait(peer)


def wait_for_solved(peers: list[Peer]) -> int:
    """Wait until every peer received `grid_solved`; return its `elapsed_ms`."""
    elapsed: list[int] = []
    for peer in peers:
        peer.wait_until(lambda p=peer: solved_events(p) != [], "the grid_solved event")
        elapsed.append(solved_events(peer)[0].elapsed_ms)
    assert len(set(elapsed)) == 1, elapsed
    return elapsed[0]


def solved_events(peer: Peer) -> list[GridSolved]:
    """Every `grid_solved` a peer received."""
    found: list[GridSolved] = []
    for message in peer.messages():
        if isinstance(message, GridSolved):
            found.append(message)
    return found


def solve_with_a_check(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[list[Peer], int]:
    """Ana and Bob solve a room; Ana sends one grid check after five letters.

    Returns:
        The two peers and the `elapsed_ms` of the `grid_solved` both received.
    """
    peers = join_peers(stack, client, code, ["Ana", "Bob"])
    ana, bob = peers
    type_cells(ana, FIRST_17[:5])
    ana.send(Check(target=GridTarget()))
    ping_and_wait(ana)
    type_cells(ana, FIRST_17[5:])
    type_cells(bob, [LAST_CELL])
    return peers, wait_for_solved(peers)


def solve_with_a_reveal(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[list[Peer], int]:
    """Bob reveals (0, 1); Ana and Bob type the 17 other letters."""
    peers = join_peers(stack, client, code, ["Ana", "Bob"])
    ana, bob = peers
    bob.send(Reveal(target=CellTarget(row=0, column=1)))
    ping_and_wait(bob)
    others = [cell for cell in ROW_MAJOR if cell != (0, 1)]
    type_cells(ana, others[:9])
    type_cells(bob, others[9:])
    return peers, wait_for_solved(peers)


def solve_after_a_removal(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[list[Peer], int]:
    """Ana (host), Bob and Cy join; Ana removes Cy; Ana and Bob solve the grid."""
    peers = join_peers(stack, client, code, ["Ana", "Bob", "Cy"])
    ana, bob, cy = peers
    ana.send(RemovePlayer(player_id=cy.you()))
    ana.wait_until(lambda: removal_seen(ana), "Cy's removal")
    type_cells(ana, ROW_MAJOR[:9])
    type_cells(bob, ROW_MAJOR[9:])
    return peers, wait_for_solved([ana, bob])


def removal_seen(peer: Peer) -> bool:
    """Whether a peer received a `player_left` for a removed player."""
    for message in peer.messages():
        if getattr(message, "type", "") == "player_left":
            return True
    return False


# ---- The traffic rules of spec 037 for a payload with no earned letter ----


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
    """Every (row, column, letter) a parsed payload shows at a cell."""
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


def traffic_problems(text: str) -> list[str]:
    """The rules of spec 037 that one payload breaks, no letter being earned."""
    problems: list[str] = []
    scanned = text
    try:
        parsed: object = json.loads(text)
    except ValueError:
        parsed = None
    else:
        for key in keys_of(parsed):
            if key in FORBIDDEN_KEYS:
                problems.append(f"the key {key!r}")
        scanned = json.dumps(without_identifiers(parsed))
        for row, column, letter in letters_in(parsed):
            problems.append(f"the letter {letter!r} at ({row}, {column})")
    for answer in ANSWERS:
        if answer in scanned:
            problems.append(f"the answer {answer!r}")
    return problems


# ---- Pages with a mocked socket ----


def recap_player(
    player_id: str,
    nickname: str | None,
    letters: int,
    words: int,
    removed: bool = False,
) -> dict[str, Any]:
    """One `players` item of a `Recap` as JSON."""
    return {
        "player_id": player_id,
        "nickname": nickname,
        "letters": letters,
        "words": words,
        "removed": removed,
    }


def recap_body(
    players: list[dict[str, Any]] | None = None,
    share_path: str | None = None,
    elapsed_ms: int = 754_000,
    checks: int = 2,
    letter_reveals: int = 1,
    word_reveals: int = 1,
    revealed_letters: int = 5,
) -> dict[str, Any]:
    """A `Recap` as JSON: by default the recap of AC-2 (Ana 8 and 4, Bob 5 and 3)."""
    shown = players
    if shown is None:
        shown = [recap_player("p1", "Ana", 8, 4), recap_player("p2", "Bob", 5, 3)]
    return {
        "grid_number": 1,
        "elapsed_ms": elapsed_ms,
        "checks": checks,
        "letter_reveals": letter_reveals,
        "word_reveals": word_reveals,
        "revealed_letters": revealed_letters,
        "letter_cells": 18,
        "word_count": 8,
        "players": shown,
        "share_path": share_path,
    }


class RecapRoute:
    """The answers of `GET /api/rooms/ABC123/recap` of a page, and its requests."""

    def __init__(self, body: object, status: int = 200) -> None:
        self.body = body
        self.status = status
        self.requests: list[str] = []

    def handle(self, route: Route) -> None:
        """Answer one request of the page (the handler of `page.route`)."""
        self.requests.append(route.request.url)
        route.fulfill(
            status=self.status,
            content_type="application/json",
            body=json.dumps(self.body),
        )


def serve_recap(page: Page, body: object, status: int = 200) -> RecapRoute:
    """Answer the recap route of /r/ABC123 on a page with `body`; call before goto."""
    route = RecapRoute(body, status)
    page.route(RECAP_ROUTE, route.handle)
    return route


def share_route(page: Page, token: str, body: object, status: int = 200) -> None:
    """Answer `GET /api/recaps/<token>` on a page with `body`."""

    def answer(route: Route) -> None:
        route.fulfill(
            status=status, content_type="application/json", body=json.dumps(body)
        )

    page.route(f"**/api/recaps/{token}", answer)


class OpenedPage(NamedTuple):
    """A solved room page on a mocked socket and its recap route."""

    mock: Any  # spec 025's MockRoomSocket
    route: RecapRoute


def open_solved_page(
    page: Page,
    base_url: str,
    grid: Grid,
    body: object,
    status: int = 200,
    solved: bool = True,
) -> OpenedPage:
    """Open /r/ABC123 as Ana on a mocked socket, the recap route answering `body`.

    Args:
        page: A fresh page.
        base_url: The live server.
        grid: FX-01.
        body: What the recap route answers, as JSON.
        status: The status of the answer.
        solved: Whether the first snapshot is solved. The grid is always full and
            right, as the spec's "solved FX-01 snapshot" says.

    Returns:
        The mocked socket and the recap route.
    """
    from spec027_harness import open_timer_room

    route = serve_recap(page, body, status)
    mock = open_timer_room(
        page, base_url, grid, elapsed_ms=754_000, running=False, solved=solved
    )
    return OpenedPage(mock, route)


def stored_play_r(path: Path, grid: Grid) -> Game:
    """Write a room and `PLAY_R`'s entries to a file store, then close the store.

    The room is created with `SHARE_TOKEN`; a `RoomRegistry` on a new `RoomStore`
    of the same file then loads it, solved, as after a restart.
    """
    game = play_r(grid)
    store = RoomStore(path)
    initial = new_room(ROOM_CODE, grid, NOW, grid_number=1, share_token=SHARE_TOKEN)
    store.create_room(initial)
    store.append(ROOM_CODE, game.log)
    store.close()
    return game
