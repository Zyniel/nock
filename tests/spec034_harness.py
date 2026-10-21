"""Shared setup of the tests of spec 034: catching up after an absence.

This module is not a test file: pytest does not collect it. The tests of spec 034
are in `tests/test_spec_034_*.py`, one file per criterion group:

- `test_spec_034_ac01_changed_cells.py`: AC-1 in Python (`load_room_at`,
  `RoomRegistry.catch_up`, `build_catch_up`) and over HTTP.
- `test_spec_034_ac03_lines_and_names.py`: AC-3 in Python and over HTTP.
- `test_spec_034_ac02_highlight.py`: AC-2 with the mocked socket and catch-up,
  without its timing.
- `test_spec_034_ac02_highlight_timing.py`: AC-2's highlight timing (still on at
  4.5 s, gone at 6 s, started again by a later catch-up). It measures a time
  window, so it runs in the serial pass (`SERIAL_TEST_FILES`).
- `test_spec_034_ac04_feed_lines.py`: AC-4's feed items and texts with the mocked
  socket and catch-up, and the form of the mocked answers.
- `test_spec_034_ac04_feed_scroll.py`: AC-4's scroll checks (at its end, within
  300 ms, items in view within 1 px). They are of the kind of spec 013's serial
  file, so this file runs in the serial pass too.
- `test_spec_034_ac02_ac04_live_server.py`: AC-2 and AC-4 with two browsers on
  the live server.
- `test_spec_034_ac05_seen_seq_and_requests.py`: AC-5.

Python criteria play the reference absence "ABSENCE" of the spec's harness with
the rules, appending each step's entries to a store file, then read it through a
second store and a registry on that file (`absence_rooms`).

The names that this spec adds (`nock.catch_up`, `RoomStore.load_room_at`,
`RoomRegistry.catch_up`) are imported or used inside the functions that need
them, never at the top of a module: until they exist, each test fails on the
name it needs, and no file fails to load. The browser tests import nothing that
this spec adds: they answer the catch-up route with plain JSON (`catch_up_json`),
whose form `test_spec_034_ac04_feed_lines.py` checks against `CatchUp`, and they
compare the request bodies with plain JSON objects, which is what
`CatchUpRequest` (immutable, unknown fields rejected) parses.

Nicknames: the server sends them in capitals (`ANA`, `BOB`, `CY`), and a page
shows them through spec 040's `displayNickname` (`Ana`, `Bob`, `Cy`).

The fixtures (`fx01_grid`, ...) are defined in each test file as thin wrappers:
a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, Route, WebSocketRoute, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellRef,
    CellTarget,
    Check,
    CheckResult,
    ClientMessage,
    ClueRef,
    EditLetter,
    GridTarget,
    HelpMode,
    Join,
    LetterChanged,
    Ping,
    PlayerState,
    PlayerView,
    Pong,
    Reveal,
    RevealBudget,
    RevealResult,
    RoomSettings,
    Selection,
    Snapshot,
    WordTarget,
    grid_view,
    parse_client_message,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    tick,
)
from nock.server import create_app
from nock.store import RoomStore

if TYPE_CHECKING:
    from nock.catch_up import CatchUp

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
COLOUR_CONTRAST_JS = (Path(__file__).parent / "colour_contrast.js").read_text(
    encoding="utf-8"
)

# ---- The values of the spec's "Test harness" -------------------------------------

CODE = "ABC123"
UNKNOWN_CODE = "ZZZZZZ"
T = 1_000_000.0  # `t`: the room's creation and every step of ABSENCE but the tick
TICK_AT = T + 301  # the tick that times Ana and Bob out, and the registry's clock
ANA = "p1"
BOB = "p2"
CY = "p3"
TA = "token-of-ana-0001"  # matches ResumeToken
TB = "token-of-bob-0002"
NOBODYS_TOKEN = "Z" * 24  # matches ResumeToken; no player ever had it
ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")

VIDE = ClueRef(row=2, column=0, clue_index=0)
NAVAL = ClueRef(row=0, column=0, clue_index=1)
SENT = ClueRef(row=0, column=4, clue_index=0)

# ---- Fixture bodies ----------------------------------------------------------------


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def load_fr() -> dict[str, str]:
    """The French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


# ---- Plays of the rules --------------------------------------------------------------


class Play:
    """A FX-01 room played with the rules, and every entry it logged.

    Each step applies one rule function to the current state, keeps its state
    and appends its entries to `entries` (and to `store`, when one is given, as
    the hub does). `states` maps each seq reached to the state just after it.
    """

    def __init__(self, grid: Grid, store: RoomStore | None = None) -> None:
        self.state: RoomState = new_room(CODE, grid, T)
        self.store = store
        self.entries: list[LogEntry] = []
        self.states: dict[int, RoomState] = {0: self.state}
        if store is not None:
            store.create_room(self.state)

    def apply(self, outcome: Outcome) -> Outcome:
        """Keep the outcome's state and entries; fail on a refusal."""
        for message in outcome.reply:
            assert message.type != "error", f"the rules refused a step: {message}"
        if self.store is not None and len(outcome.entries) > 0:
            self.store.append(CODE, outcome.entries)
        self.entries.extend(outcome.entries)
        self.state = outcome.state
        self.states[self.state.seq] = self.state
        return outcome

    def join(self, nickname: str, player_id: str, token: str, now: float = T) -> None:
        join = Join(nickname=nickname, resume_token=None)
        self.apply(join_room(self.state, join, now, player_id, token))

    def send(self, player_id: str, message: ClientMessage, now: float = T) -> None:
        self.apply(handle_message(self.state, player_id, message, now))

    def write(
        self, player_id: str, row: int, column: int, letter: str, now: float = T
    ) -> None:
        self.send(player_id, EditLetter(row=row, column=column, letter=letter), now)

    def close_socket(self, player_id: str, now: float = T) -> None:
        self.apply(disconnect_player(self.state, player_id, now))

    def tick(self, now: float) -> None:
        self.apply(tick(self.state, now))

    def entries_after(self, seq: int) -> list[LogEntry]:
        """The entries with a seq greater than `seq`, in seq order."""
        found: list[LogEntry] = []
        for entry in self.entries:
            if entry.event.seq > seq:
                found.append(entry)
        return found

    def entry_of(self, seq: int) -> LogEntry:
        for entry in self.entries:
            if entry.event.seq == seq:
                return entry
        pytest.fail(f"no entry with seq {seq}")


def play_absence(play: Play) -> None:
    """Play the reference absence ABSENCE of the spec's harness (seq 1 to 22)."""
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    play.write(ANA, 1, 0, "T")  # seq 3
    play.close_socket(ANA)  # seq 4
    for offset, letter in enumerate("VIDE"):
        play.write(BOB, 2, 1 + offset, letter)  # seq 5 to 8
    play.send(BOB, Check(target=WordTarget(row=2, column=0, clue_index=0)))
    play.send(BOB, Reveal(target=CellTarget(row=1, column=1)))  # seq 14, 15
    play.write(BOB, 3, 1, "A")  # seq 16
    play.write(BOB, 4, 1, "L")  # seq 17
    play.write(BOB, 0, 1, "N")  # seq 18
    play.close_socket(BOB)  # seq 19
    play.tick(TICK_AT)  # seq 20, 21, 22
    assert play.state.seq == 22, f"ABSENCE ends at seq {play.state.seq}, not 22"


class AbsenceRooms(NamedTuple):
    """ABSENCE in a store file, and the registry and HTTP client that read it."""

    play: Play  # the rules' play, with its own store on the file
    store: RoomStore  # the registry's store, on the same file
    registry: RoomRegistry
    client: TestClient


@contextlib.contextmanager
def absence_rooms(tmp_path: Path, grid: Grid) -> Iterator[AbsenceRooms]:
    """Play ABSENCE into `tmp_path / "nock.sqlite3"`; yield what reads it.

    The registry's clock stands at `t + 301`, so the room, last edited at `t`, is
    far from its expiry (spec 032). Everything is closed afterwards.
    """
    path = tmp_path / "nock.sqlite3"
    play_store = RoomStore(path)
    store = RoomStore(path)
    registry = RoomRegistry(clock=lambda: TICK_AT, store=store)
    try:
        play = Play(grid, play_store)
        play_absence(play)
        app = create_app(rooms=registry, dist_dir=tmp_path)
        with TestClient(app) as client:
            yield AbsenceRooms(play=play, store=store, registry=registry, client=client)
    finally:
        registry.close()
        store.close()
        play_store.close()


def registry_catch_up(
    registry: RoomRegistry,
    after_seq: int,
    until_seq: int,
    token: str = TA,
    code: str = CODE,
) -> CatchUp | None:
    """`registry.catch_up(code, CatchUpRequest(...))` for a token and two seqs."""
    from nock.catch_up import CatchUpRequest

    request = CatchUpRequest(
        resume_token=token, after_seq=after_seq, until_seq=until_seq
    )
    return registry.catch_up(code, request)


def known_catch_up(
    registry: RoomRegistry, after_seq: int, until_seq: int, token: str = TA
) -> CatchUp:
    """The catch-up that the registry gives; fails when it gives None."""
    answer = registry_catch_up(registry, after_seq, until_seq, token)
    assert answer is not None, f"no catch-up for after_seq {after_seq}"
    return answer


def cell_refs(positions: list[tuple[int, int]]) -> tuple[CellRef, ...]:
    """The `CellRef` of each (row, column), in the order given."""
    refs: list[CellRef] = []
    for row, column in positions:
        refs.append(CellRef(row=row, column=column))
    return tuple(refs)


def catch_up_path(code: str = CODE) -> str:
    return f"/api/rooms/{code}/catch-up"


# ---- The browser with the mocked socket and the mocked catch-up --------------------

SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
IDENTITY_KEY = f"nock.identity.{CODE}"
ROOM_RECORD_KEY = f"nock.room.{CODE}"
STORED_IDENTITY = {"player_id": ANA, "resume_token": SNAPSHOT_TOKEN, "nickname": "ANA"}
CATCH_UP_ROUTE = f"**/api/rooms/{CODE}/catch-up"
WAIT_TIMEOUT_MS = 10_000
SETTLE_MS = 400
CLOSE_FOR_RECONNECTION = 1011  # spec 017: the page reconnects after 1,000 ms

DEFAULT_SETTINGS = RoomSettings(
    help_mode=HelpMode.FREE,
    reveal_budget=RevealBudget(letters=5, words=1),
    locked=False,
)

JsonObject = dict[str, Any]  # a JSON object read from the page or a request body


def fx01_letter_cells() -> list[tuple[int, int]]:
    """The 18 letter cells of FX-01 as (row, column), in row-major order."""
    cells = [(0, 1)]
    for column in range(5):
        cells.append((1, column))
    for row in range(2, 5):
        for column in range(1, 5):
            cells.append((row, column))
    return cells


def player_view(
    player_id: str,
    nickname: str,
    colour: int,
    *,
    is_host: bool = False,
    selection: Selection | None = None,
) -> PlayerView:
    """An active, unmuted player of a snapshot's roster."""
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=is_host,
        muted=False,
        selection=selection,
    )


def snapshot_players(bob_selection: Selection | None = None) -> list[PlayerView]:
    """`p1` (`ANA`, colour 0, host) and `p2` (`BOB`, colour 1)."""
    return [
        player_view(ANA, "ANA", 0, is_host=True),
        player_view(BOB, "BOB", 1, selection=bob_selection),
    ]


def snapshot_frame(grid: Grid, seq: int, players: list[PlayerView]) -> str:
    """The JSON text of a FX-01 snapshot for `p1` at `seq`, every cell empty."""
    snapshot = Snapshot(
        seq=seq,
        you=ANA,
        resume_token=SNAPSHOT_TOKEN,
        grid=grid_view(grid),
        players=tuple(players),
        settings=DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def letter_frame(seq: int, row: int, column: int, letter: str) -> str:
    """A `letter_changed` of `p2`."""
    event = LetterChanged(
        seq=seq, row=row, column=column, letter=letter, pencil=False, player_id=BOB
    )
    return event.model_dump_json()


def check_line(
    seq: int, player_id: str, target: CellTarget | WordTarget | None = None
) -> CheckResult:
    """A `check_result` with empty lists (a word check of VIDE by default)."""
    checked = (
        target if target is not None else WordTarget(row=2, column=0, clue_index=0)
    )
    return CheckResult(
        seq=seq, player_id=player_id, target=checked, correct=(), wrong=()
    )


def grid_line_frame(seq: int) -> str:
    """The line event of spec 013's "Feed scroll states": Bob checks the grid."""
    event = CheckResult(
        seq=seq, player_id=BOB, target=GridTarget(), correct=(), wrong=()
    )
    return event.model_dump_json()


def reveal_line(seq: int, player_id: str) -> RevealResult:
    """A `reveal_result` of the letter (1, 1), 4 letters and 1 word left."""
    return RevealResult(
        seq=seq,
        player_id=player_id,
        target=CellTarget(row=1, column=1),
        reveal_budget=RevealBudget(letters=4, words=1),
    )


def word_completed_line(seq: int, player_id: str, clue: ClueRef) -> JsonObject:
    """A `word_completed` line, as `WordCompleted(...).model_dump(mode="json")`."""
    return {
        "type": "word_completed",
        "seq": seq,
        "player_id": player_id,
        "clue": {"row": clue.row, "column": clue.column, "clue_index": clue.clue_index},
    }


CatchUpLineArg = CheckResult | RevealResult | JsonObject


def catch_up_body(
    after_seq: int,
    until_seq: int,
    cells: Sequence[tuple[int, int]] = (),
    lines: Sequence[CatchUpLineArg] = (),
    names: Sequence[tuple[str, str]] = (),
) -> JsonObject:
    """A catch-up as the JSON object that `CatchUp(...).model_dump(mode="json")` is.

    Args:
        after_seq: The catch-up's `after_seq`.
        until_seq: The catch-up's `until_seq`.
        cells: The (row, column) of each changed cell.
        lines: The lines: protocol events, or `word_completed_line` objects.
        names: The (player id, nickname) of each name.

    Returns:
        The JSON object.
    """
    cell_objects: list[JsonObject] = []
    for row, column in cells:
        cell_objects.append({"row": row, "column": column})
    line_objects: list[JsonObject] = []
    for line in lines:
        if isinstance(line, dict):
            line_objects.append(line)
        else:
            line_objects.append(line.model_dump(mode="json"))
    name_objects: list[JsonObject] = []
    for player_id, nickname in names:
        name_objects.append({"player_id": player_id, "nickname": nickname})
    return {
        "after_seq": after_seq,
        "until_seq": until_seq,
        "cells": cell_objects,
        "lines": line_objects,
        "names": name_objects,
    }


def catch_up_json(
    after_seq: int,
    until_seq: int,
    cells: Sequence[tuple[int, int]] = (),
    lines: Sequence[CatchUpLineArg] = (),
    names: Sequence[tuple[str, str]] = (),
) -> str:
    """The JSON text of `catch_up_body`, the body the mocked route answers with."""
    return json.dumps(catch_up_body(after_seq, until_seq, cells, lines, names))


def request_body(
    after_seq: int, until_seq: int, token: str = SNAPSHOT_TOKEN
) -> JsonObject:
    """A request body as the page must send it (a `CatchUpRequest`)."""
    return {"resume_token": token, "after_seq": after_seq, "until_seq": until_seq}


class MockConnection:
    """One socket the page opened, seen from the mocked server.

    It records every frame and answers each `ping` with a `pong`, as the real
    server does (spec 017), so that a slow step does not look like a lost
    connection.
    """

    def __init__(self, route: WebSocketRoute) -> None:
        self.route = route
        self.frames: list[str] = []
        route.on_message(self._on_message)

    def _on_message(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.frames.append(text)
        if parse_client_message(text) == Ping():
            self.route.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.route.send(frame)

    def close(self, code: int) -> None:
        self.route.close(code=code)

    def messages(self) -> list[ClientMessage]:
        """Every frame the page sent on this socket but its `ping` frames, parsed."""
        found: list[ClientMessage] = []
        for frame in self.frames:
            message = parse_client_message(frame)
            if message != Ping():
                found.append(message)
        return found

    def has_join(self) -> bool:
        return any(isinstance(message, Join) for message in self.messages())

    def edit_letters(self) -> list[EditLetter]:
        found: list[EditLetter] = []
        for message in self.messages():
            if isinstance(message, EditLetter):
                found.append(message)
        return found


class MockRoom:
    """The server side of the room socket of /r/ABC123: every socket, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.connections: list[MockConnection] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.connections.append(MockConnection(route))

    def latest(self) -> MockConnection:
        return self.connections[-1]

    def send(self, frame: str) -> None:
        """Send a frame on the latest socket."""
        self.latest().send(frame)

    def wait_for_join(self, count: int) -> MockConnection:
        """Wait until the page has opened `count` sockets and joined on the last."""
        wait_until(
            self.page,
            lambda: len(self.connections) >= count
            and self.connections[count - 1].has_join(),
            f"the join on socket {count}",
        )
        return self.connections[count - 1]


class CatchUpRoute:
    """The mocked `POST /api/rooms/ABC123/catch-up`.

    It records each request. With `answer`, it answers at once with that JSON
    text; without it, the request is held until the test answers it.
    """

    def __init__(self, answer: str | None = None) -> None:
        self.answer = answer
        self.routes: list[Route] = []
        self.bodies: list[str] = []

    def handle(self, route: Route) -> None:
        self.routes.append(route)
        self.bodies.append(route.request.post_data or "")
        if self.answer is not None:
            route.fulfill(status=200, content_type="application/json", body=self.answer)

    def parsed_bodies(self) -> list[object]:
        found: list[object] = []
        for body in self.bodies:
            found.append(json.loads(body))
        return found

    def answer_json(self, index: int, body: str) -> None:
        self.routes[index].fulfill(
            status=200, content_type="application/json", body=body
        )

    def answer_status(self, index: int, status: int) -> None:
        self.routes[index].fulfill(status=status, body="")

    def abort(self, index: int) -> None:
        self.routes[index].abort()

    def wait_for_requests(self, page: Page, count: int) -> None:
        wait_until(page, lambda: len(self.routes) >= count, f"catch-up request {count}")


def wait_until(page: Page, condition: Callable[[], bool], what: str) -> None:
    """Let Playwright run its callbacks until `condition` holds, else fail."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"timed out waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50


def seed_storage(page: Page, record: JsonObject | None) -> None:
    """Seed `nock.identity.ABC123`, and `nock.room.ABC123` unless `record` is None."""
    items: dict[str, str] = {IDENTITY_KEY: json.dumps(STORED_IDENTITY)}
    if record is not None:
        items[ROOM_RECORD_KEY] = json.dumps(record)
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " localStorage.setItem(key, value); }"
    )
    page.context.add_init_script(script)


def record_with(seen_seq: object) -> JsonObject:
    """The seeded record `{"grid": null, "selection": null}` plus `seen_seq`."""
    record: JsonObject = {"grid": None, "selection": None}
    if seen_seq is not None:
        record["seen_seq"] = seen_seq
    return record


def room_page(page: Page) -> Locator:
    return page.get_by_test_id("room-page")


def expect_seq(page: Page, seq: int) -> None:
    expect(room_page(page)).to_have_attribute("data-seq", str(seq))


def open_mocked_room(
    page: Page,
    base_url: str,
    grid: Grid,
    route: CatchUpRoute,
    *,
    record: JsonObject | None,
    seq: int,
    players: list[PlayerView] | None = None,
) -> MockRoom:
    """Open /r/ABC123 with the mocked socket and catch-up, and show a snapshot.

    Args:
        page: A fresh page (1280 by 720).
        base_url: The live server, which serves the built client.
        grid: FX-01.
        route: The mocked catch-up route.
        record: The seeded room record; None seeds none.
        seq: The snapshot's seq.
        players: The roster (default: `snapshot_players()`).

    Returns:
        The mocked socket, once the page shows the snapshot.
    """
    mock = MockRoom(page)
    page.route(CATCH_UP_ROUTE, route.handle)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    seed_storage(page, record)
    page.goto(f"{base_url}/r/{CODE}")
    mock.wait_for_join(1)
    shown_players = players if players is not None else snapshot_players()
    mock.send(snapshot_frame(grid, seq, shown_players))
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def reconnect_with_snapshot(
    mock: MockRoom, grid: Grid, seq: int, players: list[PlayerView] | None = None
) -> None:
    """Close the latest socket with 1011, then answer the next join at `seq`."""
    count = len(mock.connections)
    mock.latest().close(CLOSE_FOR_RECONNECTION)
    connection = mock.wait_for_join(count + 1)
    shown_players = players if players is not None else snapshot_players()
    connection.send(snapshot_frame(grid, seq, shown_players))
    expect_seq(mock.page, seq)


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def caught_up_values(page: Page) -> dict[tuple[int, int], str | None]:
    """The `data-caught-up` of every letter cell (None: no attribute)."""
    script = (
        "() => Array.from(document.querySelectorAll("
        '\'[data-testid="cell"][data-type="letter"]\'))'
        ".map(e => [Number(e.dataset.row), Number(e.dataset.column),"
        " e.getAttribute('data-caught-up')])"
    )
    found = page.evaluate(script)
    values: dict[tuple[int, int], str | None] = {}
    for row, column, value in found:
        values[(row, column)] = value
    return values


def expected_caught_up(
    highlighted: list[tuple[int, int]],
) -> dict[tuple[int, int], str]:
    """Every FX-01 letter cell mapped to `"true"` when highlighted, else `"false"`."""
    values: dict[tuple[int, int], str] = {}
    for cell in fx01_letter_cells():
        values[cell] = "true" if cell in highlighted else "false"
    return values


def marks_by_cell(page: Page) -> dict[tuple[int, int], int]:
    """The number of `catch-up-mark` elements in each cell that holds one."""
    script = (
        "() => Array.from(document.querySelectorAll('[data-testid=\"cell\"]'))"
        ".map(e => [Number(e.dataset.row), Number(e.dataset.column),"
        " e.querySelectorAll('[data-testid=\"catch-up-mark\"]').length])"
        ".filter(item => item[2] > 0)"
    )
    found = page.evaluate(script)
    counts: dict[tuple[int, int], int] = {}
    for row, column, count in found:
        counts[(row, column)] = count
    return counts


def catch_up_marks(page: Page) -> Locator:
    return page.get_by_test_id("catch-up-mark")


def feed_items(page: Page) -> list[tuple[str, str, str]]:
    """The (kind, seq, text) of each feed item, oldest first."""
    script = (
        "() => Array.from(document.querySelectorAll("
        '\'[data-testid="activity-feed"] [data-testid="feed-item"]\'))'
        ".map(e => [e.getAttribute('data-kind'), e.getAttribute('data-seq'),"
        " e.textContent.trim()])"
    )
    found = page.evaluate(script)
    return [(kind, seq, text) for kind, seq, text in found]


def feed_item_locator(page: Page) -> Locator:
    return page.get_by_test_id("activity-feed").get_by_test_id("feed-item")


def expect_catch_up_applied(page: Page, value: str) -> None:
    expect(room_page(page)).to_have_attribute(
        "data-catch-up", value, timeout=WAIT_TIMEOUT_MS
    )
