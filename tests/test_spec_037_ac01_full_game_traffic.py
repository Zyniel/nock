"""Tests of spec 037 (integrity), AC-1: no unearned answer letter reaches a browser.

AC-1 inspects all the traffic of a full FX-01 game, on the real WebSocket (three
clients) and in a browser on the live server. The shared setup is in
`spec037_harness`.

Interpretation (see the report): an answer letter is "earned" in the WebSocket and
browser games when the test itself sent it to that cell, because every edit of those
games is accepted.

Not tested here: reveals and chat traffic (specs 022 and 024 extend the checker).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Page, Response, WebSocket, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Erase, Join, LetterCellView, Snapshot
from nock.server import create_app
from spec037_harness import (
    SETTLE_MS,
    Earned,
    Peer,
    TrafficLog,
    connect,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    state_of,
    wait_until_page,
)

KEY_PAUSE_MS = 60

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

# ---- Fixtures -----------------------------------------------------------------


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
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


# ---- The traffic checker ------------------------------------------------------


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
        if isinstance(item, Earned):
            earned.setdefault((item.row, item.column), set()).add(item.letter)
            continue
        for problem in leaks_in(item.text, earned):
            problems.append(f"{item.source} received {problem}: {item.text[:120]}")
    return problems


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
PLAYERS = 3  # Ana, Bob and Cy: three player_joined events


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

        # The last letter completes the grid (spec 026): `grid_solved` follows it,
        # and the leak scan has to see that frame too. The erase of (4, 4) came
        # before the grid was complete, so no edit was refused.
        for peer in (ana, bob, cy):
            peer.wait_for_seq(PLAYERS + EVENTS_OF_THE_GAME + 1, "the grid_solved event")
            assert peer.messages()[-1].type == "grid_solved"

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
