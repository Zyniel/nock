"""Tests of spec 023, AC-6 and AC-7: what the server compares and what it sends.

AC-6: empty cells in the scope are ignored (the rule on `handle_message`). AC-7:
the server decides from the letters in place (the rule) and sends no answer (the
real WebSocket). The shared setup is in `spec023_harness`.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    Check,
    CheckResult,
    EditLetter,
    Erase,
    GridTarget,
    Join,
)
from nock.room import (
    RoomState,
    handle_message,
)
from nock.server import create_app
from spec023_harness import (
    CHECK_NOW,
    MIME,
    NOW,
    TAMIS,
    Cell,
    Earned,
    Peer,
    TrafficLog,
    cell_state,
    cell_view,
    check,
    connect,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    refs,
    s1_room,
    snapshot_cell,
    two_player_room,
    write_letter,
)

Step = tuple[int, int, str | None]  # row, column, letter (None: erase)


# ---- Fixtures ----


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
        if isinstance(item, Earned):
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


def state_of(registry: RoomRegistry, code: str) -> RoomState:
    state = registry.room_state(code)
    assert state is not None
    return state


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
