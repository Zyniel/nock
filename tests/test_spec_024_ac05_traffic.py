"""Tests of spec 024, AC-5: no payload sent to a browser shows a revealed letter
before the room revealed it.

This file holds its own copy of spec 037's traffic checker (spec 037's AC-1
file), extended with the reveal rule of "What a browser may receive", as spec 024's
"Test harness" asks. Spec 037's tests are left as they are. The checker is tested
on hand-made logs, then run on the full game with reveals on the real WebSocket
and in three browsers on the live server. The shared setup (the traffic log, the
simulated client) is in `spec024_harness`.

How the checker reads the reveal rule: a letter typed at a cell stays earned there
for every later payload (spec 037). A letter revealed at a cell is earned there by
its `cell_locked` frame (`revealed` true) with seq `s`: that frame itself, a
snapshot whose `seq` is `s` or more, and, for a client, every other frame it
received after its own copy of that frame or such a snapshot. A snapshot is judged
by its `seq` alone. An HTTP body never earns a revealed letter.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, Response, WebSocket, expect
from playwright.sync_api import Error as PlaywrightError

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import CellLocked, CellTarget, EditLetter, Reveal
from nock.server import create_app
from spec024_harness import (
    KEY_PAUSE_MS,
    MIME,
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    Cell,
    Earned,
    EnterRoom,
    HttpBody,
    Peer,
    Received,
    TrafficItem,
    TrafficLog,
    cell_at,
    expect_selection,
    grid_from_text,
    join_one,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    snapshot_cell,
    wait_until_page,
)

ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
FORBIDDEN_KEYS = ("answer", "solution")
# Values that are random identifiers: they could by chance spell a short answer.
IDENTIFIER_KEYS = ("resume_token", "player_id", "you", "author", "code")

Shown = tuple[int, int, str]  # a letter shown at a cell: row, column, letter

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- The traffic checker (spec 037's, with the reveal rule) ----


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


def _letters_in(value: object) -> list[Shown]:
    """Every letter a parsed payload shows at a cell.

    That is a `letter_changed`, a `cell_locked` and every `LetterCellView`.
    """
    found: list[Shown] = []
    if isinstance(value, dict):
        kind = value.get("type")
        row = value.get("row")
        column = value.get("column")
        letter = value.get("letter")
        shows_letter = kind in ("letter_changed", "cell_locked", "letter")
        has_position = isinstance(row, int) and isinstance(column, int)
        if shows_letter and has_position and isinstance(letter, str):
            assert isinstance(row, int)
            assert isinstance(column, int)
            found.append((row, column, letter))
        for child in value.values():
            found.extend(_letters_in(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_letters_in(child))
    return found


def _parse(text: str) -> object | None:
    """The parsed JSON of a payload, or None when it is not JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return None


class RevealingFrame(NamedTuple):
    """A `cell_locked` frame with `revealed` true: the letter it shows and its seq."""

    shown: Shown
    seq: int


def revealing_frame(text: str) -> RevealingFrame | None:
    """The revealing frame a payload is, or None."""
    parsed = _parse(text)
    if not isinstance(parsed, dict):
        return None
    if parsed.get("type") != "cell_locked" or parsed.get("revealed") is not True:
        return None
    row = parsed.get("row")
    column = parsed.get("column")
    letter = parsed.get("letter")
    seq = parsed.get("seq")
    if not (isinstance(row, int) and isinstance(column, int)):
        return None
    if not (isinstance(letter, str) and isinstance(seq, int)):
        return None
    return RevealingFrame((row, column, letter), seq)


def snapshot_seq(text: str) -> int | None:
    """The `seq` of a snapshot payload, or None for any other payload."""
    parsed = _parse(text)
    if not isinstance(parsed, dict) or parsed.get("type") != "snapshot":
        return None
    seq = parsed.get("seq")
    return seq if isinstance(seq, int) else None


def revealing_seqs(items: list[TrafficItem]) -> dict[Shown, int]:
    """For each revealed letter, the seq of its revealing frame (any client's)."""
    seqs: dict[Shown, int] = {}
    for item in items:
        if not isinstance(item, Received):
            continue
        frame = revealing_frame(item.text)
        if frame is None:
            continue
        known = seqs.get(frame.shown)
        if known is None or frame.seq < known:
            seqs[frame.shown] = frame.seq
    return seqs


class Earnings(NamedTuple):
    """What one payload may show, besides the letters typed so far."""

    typed: dict[Cell, set[str]]
    revealed_to_client: set[Shown]  # empty for an HTTP body
    reveal_seqs: dict[Shown, int]
    is_frame: bool


def is_earned_by_reveal(text: str, shown: Shown, earnings: Earnings) -> bool:
    """Tell whether the reveal rule lets this payload show this letter."""
    if not earnings.is_frame:
        return False
    seq_of_snapshot = snapshot_seq(text)
    if seq_of_snapshot is not None:
        revealed_at = earnings.reveal_seqs.get(shown)
        return revealed_at is not None and seq_of_snapshot >= revealed_at
    own = revealing_frame(text)
    if own is not None and own.shown == shown:
        return True
    return shown in earnings.revealed_to_client


def leaks_in(text: str, earnings: Earnings) -> list[str]:
    """The rules of "What a browser may receive" that one payload breaks."""
    problems: list[str] = []
    parsed = _parse(text)
    scanned = text
    if parsed is not None:
        for key in _keys_of(parsed):
            if key in FORBIDDEN_KEYS:
                problems.append(f"the key {key!r}")
        scanned = json.dumps(_without_identifiers(parsed))
        for row, column, letter in _letters_in(parsed):
            if letter in earnings.typed.get((row, column), set()):
                continue
            if is_earned_by_reveal(text, (row, column, letter), earnings):
                continue
            problems.append(f"the unearned letter {letter!r} at ({row}, {column})")
    for answer in ANSWERS:
        if answer in scanned:
            problems.append(f"the answer {answer!r}")
    return problems


def note_reveals_seen(
    text: str, seen: set[Shown], reveal_seqs: dict[Shown, int]
) -> None:
    """Add to `seen` the revealed letters a client may show from now on."""
    own = revealing_frame(text)
    if own is not None:
        seen.add(own.shown)
    seq_of_snapshot = snapshot_seq(text)
    if seq_of_snapshot is None:
        return
    for shown, revealed_at in reveal_seqs.items():
        if revealed_at <= seq_of_snapshot:
            seen.add(shown)


def replay_problems(log: TrafficLog) -> list[str]:
    """Replay the log in order and list every payload that breaks a rule."""
    items = log.items()
    reveal_seqs = revealing_seqs(items)
    typed: dict[Cell, set[str]] = {}
    seen_by_client: dict[str, set[Shown]] = {}
    problems: list[str] = []
    for item in items:
        if isinstance(item, Earned):
            typed.setdefault((item.row, item.column), set()).add(item.letter)
            continue
        if isinstance(item, HttpBody):
            earnings = Earnings(typed, set(), reveal_seqs, is_frame=False)
            for problem in leaks_in(item.text, earnings):
                problems.append(f"{item.source} sent {problem}: {item.text[:120]}")
            continue
        seen = seen_by_client.setdefault(item.client, set())
        earnings = Earnings(typed, seen, reveal_seqs, is_frame=True)
        for problem in leaks_in(item.text, earnings):
            problems.append(f"{item.client} received {problem}: {item.text[:120]}")
        note_reveals_seen(item.text, seen, reveal_seqs)
    return problems


# ---- AC-5: the checker on hand-made logs ----


def revealing_t(seq: int = 9) -> str:
    """The revealing frame of `T` at (4, 4)."""
    event = CellLocked(seq=seq, row=4, column=4, letter="T", revealed=True)
    return event.model_dump_json()


def letter_changed_t(seq: int) -> str:
    return json.dumps(
        {
            "type": "letter_changed",
            "seq": seq,
            "row": 4,
            "column": 4,
            "letter": "T",
            "pencil": False,
            "player_id": "p2",
        }
    )


def payload_with_cell(kind: str, seq: int, row: int, column: int, letter: str) -> str:
    """A snapshot-like payload whose grid shows one letter at a cell."""
    cell = {
        "type": "letter",
        "row": row,
        "column": column,
        "letter": letter,
        "pencil": False,
        "author": None,
        "locked": True,
        "revealed": True,
        "wrong": False,
    }
    return json.dumps({"type": kind, "seq": seq, "grid": {"cells": [cell]}})


def test_ac5_the_checker_reports_a_snapshot_older_than_the_revealing_frame() -> None:
    log = TrafficLog()
    log.receive("Ana", revealing_t(9))
    log.receive("Dee", payload_with_cell("snapshot", 8, 4, 4, "T"))

    problems = replay_problems(log)

    assert len(problems) == 1, problems
    assert problems[0].startswith("Dee received the unearned letter 'T' at (4, 4)")


def test_ac5_the_checker_accepts_that_snapshot_with_the_revealing_frames_seq() -> None:
    log = TrafficLog()
    log.receive("Ana", revealing_t(9))
    log.receive("Dee", payload_with_cell("snapshot", 9, 4, 4, "T"))

    assert replay_problems(log) == []


def test_ac5_the_checker_reports_a_frame_received_before_the_revealing_frame() -> None:
    log = TrafficLog()
    log.receive("Cy", letter_changed_t(8))
    log.receive("Cy", revealing_t(9))

    problems = replay_problems(log)

    assert len(problems) == 1, problems
    assert problems[0].startswith("Cy received the unearned letter 'T' at (4, 4)")


def test_ac5_the_checker_keys_on_each_clients_own_revealing_frame() -> None:
    log = TrafficLog()
    log.receive("Ana", revealing_t(9))
    log.receive("Cy", letter_changed_t(10))
    log.receive("Cy", revealing_t(9))

    problems = replay_problems(log)

    assert len(problems) == 1, problems
    assert problems[0].startswith("Cy received the unearned letter 'T' at (4, 4)")


def test_ac5_the_checker_accepts_a_frame_after_the_clients_revealing_frame() -> None:
    log = TrafficLog()
    log.receive("Cy", revealing_t(9))
    log.receive("Cy", letter_changed_t(10))

    assert replay_problems(log) == []


def test_ac5_the_checker_reports_an_http_body_that_shows_a_revealed_letter() -> None:
    log = TrafficLog()
    log.receive("Ana", revealing_t(9))
    log.http_body("GET /api/grids/1", payload_with_cell("grid", 9, 4, 4, "T"))

    problems = replay_problems(log)

    assert len(problems) == 1, problems
    assert problems[0].startswith(
        "GET /api/grids/1 sent the unearned letter 'T' at (4, 4)"
    )


def test_ac5_the_checker_still_accepts_a_typed_letter_anywhere_later() -> None:
    log = TrafficLog()
    log.earn(1, 0, "T")
    log.receive("Cy", payload_with_cell("snapshot", 3, 1, 0, "T"))
    log.http_body("GET /api/grids/1", payload_with_cell("grid", 3, 1, 0, "T"))

    assert replay_problems(log) == []


# ---- AC-5: the full game with reveals (WebSocket) ----

BOBS_VIDE: list[tuple[int, int, str]] = [
    (2, 1, "V"),
    (2, 2, "I"),
    (2, 3, "D"),
    (2, 4, "E"),
]
ANAS_FIVE: list[tuple[int, int, str]] = [
    (0, 1, "N"),
    (1, 0, "T"),
    (1, 1, "A"),
    (1, 3, "I"),
    (1, 4, "S"),
]
BOBS_FIVE: list[tuple[int, int, str]] = [
    (3, 1, "A"),
    (3, 3, "E"),
    (3, 4, "N"),
    (4, 1, "L"),
    (4, 3, "S"),
]
FIVE_REVEALING_FRAMES = [
    CellLocked(seq=9, row=4, column=4, letter="T", revealed=True),
    CellLocked(seq=11, row=1, column=2, letter="M", revealed=True),
    CellLocked(seq=12, row=2, column=2, letter="I", revealed=True),
    CellLocked(seq=13, row=3, column=2, letter="M", revealed=True),
    CellLocked(seq=14, row=4, column=2, letter="E", revealed=True),
]
REVEALED_LETTERS: dict[Cell, str] = {
    (4, 4): "T",
    (1, 2): "M",
    (2, 2): "I",
    (3, 2): "M",
    (4, 2): "E",
}
FINAL_SEQ = 26  # 4 joins, 4 + 10 letters, 2 + 5 reveal entries, grid_solved


class WebSocketGame(NamedTuple):
    """What the WebSocket game recorded."""

    log: TrafficLog
    peers: dict[str, Peer]


def type_letters(
    peer: Peer, log: TrafficLog, steps: list[tuple[int, int, str]]
) -> None:
    """Type each letter, noting it as earned before it leaves."""
    for row, column, letter in steps:
        log.earn(row, column, letter)
        peer.send(EditLetter(row=row, column=column, letter=letter))


def record_http(client: TestClient, log: TrafficLog) -> None:
    for path in ("/api/grids", "/api/grids/1"):
        listed = client.get(path)
        assert listed.status_code == 200
        log.http_body(f"GET {path}", listed.text)


def play_the_websocket_game(client: TestClient) -> WebSocketGame:
    """The full game with reveals of spec 024's "Test harness"."""
    log = TrafficLog()
    created = client.post("/api/rooms", json={"grid_number": 1})
    assert created.status_code == 201
    log.http_body("POST /api/rooms", created.text)
    code = created.json()["code"]
    record_http(client, log)

    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"], log)
        type_letters(bob, log, BOBS_VIDE)
        for peer in (ana, bob):
            peer.wait_for_seq(6, f"VIDE on {peer.name}")
        cy = join_one(stack, client, code, "Cy", log)
        first_three = [ana, bob, cy]
        for peer in first_three:
            peer.wait_for_seq(7, f"the join of Cy on {peer.name}")

        ana.send(Reveal(target=CellTarget(row=4, column=4)))
        for peer in first_three:
            peer.wait_for_seq(9, f"the letter reveal on {peer.name}")
        ana.send(Reveal(target=MIME))
        for peer in first_three:
            peer.wait_for_seq(14, f"the word reveal on {peer.name}")

        dee = join_one(stack, client, code, "Dee", log)
        everyone = [ana, bob, cy, dee]
        for peer in everyone:
            peer.wait_for_seq(15, f"the join of Dee on {peer.name}")
        record_http(client, log)

        type_letters(ana, log, ANAS_FIVE)
        for peer in everyone:
            peer.wait_for_seq(20, f"Ana's five letters on {peer.name}")
        type_letters(bob, log, BOBS_FIVE)
        for peer in everyone:
            peer.wait_for_seq(FINAL_SEQ, f"the end of the game on {peer.name}")

    peers = {"Ana": ana, "Bob": bob, "Cy": cy, "Dee": dee}
    return WebSocketGame(log=log, peers=peers)


def test_ac5_websocket_every_payload_of_the_game_passes_the_rules(
    client: TestClient,
) -> None:
    game = play_the_websocket_game(client)

    for peer in game.peers.values():
        assert peer.errors() == [], peer.name
    assert replay_problems(game.log) == []


def test_ac5_websocket_the_snapshot_before_the_reveals_holds_no_revealed_letter(
    client: TestClient,
) -> None:
    game = play_the_websocket_game(client)

    snapshot = game.peers["Cy"].snapshot()
    for row, column in [(4, 4), (1, 2), (3, 2), (4, 2)]:
        assert snapshot_cell(snapshot, row, column).letter is None, (row, column)


def test_ac5_websocket_the_snapshot_after_the_reveals_holds_the_revealed_letters(
    client: TestClient,
) -> None:
    game = play_the_websocket_game(client)

    snapshot = game.peers["Dee"].snapshot()
    for (row, column), letter in REVEALED_LETTERS.items():
        cell = snapshot_cell(snapshot, row, column)
        assert (cell.letter, cell.revealed, cell.author) == (letter, True, None)


def test_ac5_websocket_the_first_three_players_got_the_five_revealing_frames(
    client: TestClient,
) -> None:
    game = play_the_websocket_game(client)

    for name in ("Ana", "Bob", "Cy"):
        revealing: list[CellLocked] = []
        for lock in game.peers[name].cell_locks():
            if lock.revealed:
                revealing.append(lock)
        assert revealing == FIVE_REVEALING_FRAMES, name


def test_ac5_websocket_the_game_ends_with_grid_solved(client: TestClient) -> None:
    game = play_the_websocket_game(client)

    for peer in game.peers.values():
        last = peer.messages()[-1]
        assert last.type == "grid_solved", peer.name
        assert peer.last_seq() == FINAL_SEQ


# ---- AC-5: the browser game with reveals (live server) ----

ANAS_VIDE_KEYS: list[tuple[int, int, str]] = [
    (2, 1, "v"),
    (2, 2, "i"),
    (2, 3, "d"),
    (2, 4, "e"),
]
ANAS_TEN_KEYS: list[tuple[int, int, str]] = [
    (0, 1, "n"),
    (1, 0, "t"),
    (1, 1, "a"),
    (1, 3, "i"),
    (1, 4, "s"),
    (3, 1, "a"),
    (3, 3, "e"),
    (3, 4, "n"),
    (4, 1, "l"),
    (4, 3, "s"),
]


def is_text_content_type(content_type: str) -> bool:
    lowered = content_type.lower()
    return "text/" in lowered or "json" in lowered or "javascript" in lowered


def frame_type(text: str) -> str:
    parsed = _parse(text)
    if isinstance(parsed, dict):
        return str(parsed.get("type"))
    return ""


class PageRecorder:
    """Every frame a page receives (into the log) and every response it gets."""

    def __init__(self, page: Page, name: str, log: TrafficLog) -> None:
        self.name = name
        self.log = log
        self.frames: list[str] = []
        self.responses: list[Response] = []
        page.on("websocket", self._watch)
        page.on("response", self._keep_response)

    def _keep_response(self, response: Response) -> None:
        self.responses.append(response)

    def _watch(self, websocket: WebSocket) -> None:
        websocket.on("framereceived", self._keep)

    def _keep(self, payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        self.frames.append(text)
        self.log.receive(self.name, text)

    def count_of(self, kind: str) -> int:
        return len([text for text in self.frames if frame_type(text) == kind])

    def revealing_count(self) -> int:
        return len([text for text in self.frames if revealing_frame(text) is not None])

    def record_bodies(self) -> int:
        """Log every text response body the page still holds; return the count."""
        count = 0
        for response in self.responses:
            content_type = response.headers.get("content-type", "")
            if not is_text_content_type(content_type):
                continue
            try:
                body = response.body().decode("utf-8")
            except PlaywrightError:
                continue  # the browser no longer holds this body
            self.log.http_body(f"{self.name} GET {response.url}", body)
            count += 1
        return count


def press_keys(page: Page, log: TrafficLog, steps: list[tuple[int, int, str]]) -> None:
    """Tap each cell and type its letter, 60 ms or more between keys."""
    for row, column, key in steps:
        cell_at(page, row, column).click()
        log.earn(row, column, key.upper())
        page.keyboard.press(key)
        page.wait_for_timeout(KEY_PAUSE_MS)


def play_the_browser_game(
    page: Page,
    browser: Browser,
    url: str,
    enter_room: EnterRoom,
    log: TrafficLog,
) -> dict[str, PageRecorder]:
    """The browser game with reveals; return each page's recorder, Ana's first."""
    cy_context = browser.new_context()
    dee_context = browser.new_context()
    try:
        cy_page = cy_context.new_page()
        dee_page = dee_context.new_page()
        recorders = {
            "Ana": PageRecorder(page, "Ana", log),
            "Cy": PageRecorder(cy_page, "Cy", log),
            "Dee": PageRecorder(dee_page, "Dee", log),
        }
        ana = recorders["Ana"]

        enter_room(page, url, "Ana")
        press_keys(page, log, ANAS_VIDE_KEYS)
        wait_until_page(page, lambda: ana.count_of("letter_changed") >= 4, "VIDE")
        enter_room(cy_page, url, "Cy")

        cell_at(page, 4, 4).click()
        page.get_by_test_id("reveal-letter").click(timeout=WAIT_TIMEOUT_MS)
        expect(cell_at(page, 4, 4)).to_have_attribute("data-revealed", "true")
        cell_at(page, 2, 2).click()
        cell_at(page, 2, 2).click()
        expect_selection(page, 2, 2, "down", "0,2,0")
        page.get_by_test_id("reveal-word").click(timeout=WAIT_TIMEOUT_MS)
        for watcher in (page, cy_page):
            expect(cell_at(watcher, 4, 2)).to_have_attribute("data-revealed", "true")

        enter_room(dee_page, url, "Dee")
        press_keys(page, log, ANAS_TEN_KEYS)
        for watcher in (page, cy_page, dee_page):
            expect(watcher.get_by_test_id("room-page")).to_have_attribute(
                "data-solved", "true", timeout=WAIT_TIMEOUT_MS
            )
        page.wait_for_timeout(SETTLE_MS)

        body_count = 0
        for recorder in recorders.values():
            body_count += recorder.record_bodies()
        assert body_count >= 1
        return recorders
    finally:
        cy_context.close()
        dee_context.close()


def test_ac5_browser_every_frame_and_body_of_the_game_passes_the_rules(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    log = TrafficLog()

    play_the_browser_game(page, browser, f"{live_server}/r/{code}", enter_room, log)

    assert replay_problems(log) == []


def test_ac5_browser_anas_page_received_the_snapshot_and_the_reveal_frames(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    log = TrafficLog()

    recorders = play_the_browser_game(
        page, browser, f"{live_server}/r/{code}", enter_room, log
    )

    ana = recorders["Ana"]
    assert ana.count_of("snapshot") >= 1
    assert ana.count_of("reveal_result") >= 2
    assert ana.revealing_count() >= 5
