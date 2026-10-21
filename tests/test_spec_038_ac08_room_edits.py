"""Tests of spec 038 (privacy and operations), AC-8: the ordered edits of a room.

Python: `room_edits` reads a hand-made log of a FX-01 room (`Log` of
`spec038_harness`) where `Ana` (`p1`) and `Bob` (`p2`) type, erase, undo, and a
check and a reveal lock cells, with joins, chat and presence entries in between.
The nicknames come from the `player_joined` entries, which hold them in capitals
(`ANA`, `BOB`), as the server stores them.

HTTP: the replay route on `TestClient(create_app(rooms=registry, dist_dir=tmp_path,
operator_token=OPS_TOKEN))`, with the room registered by `add_room` and its log
appended to the store.

Edge cases checked as well, from "Kinds of `room_edits`", the `nickname` paragraph
and "Edges cases and errors": an undo that empties its cell, a confirmed pencil
letter, a player seated back whose later edits take the nickname of their new
`player_joined`, an edit with no `player_joined` before it, entries given in a
slice of the log, and a room only in the store, which the replay reads without
making it live.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    EditLetter,
    Join,
    LeaveReason,
    LetterChanged,
    PlayerState,
    grid_view,
)
from nock.room import LogEntry, handle_message, join_room, new_room
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec038_harness import (
    FX01_ANSWERS,
    LIFE,
    NOT_FOUND,
    OPS_TOKEN,
    Log,
    bearer,
    edits_path,
    seed_room,
    utc,
)

if TYPE_CHECKING:
    from nock.operations import RoomEdit, RoomReplay

# ---- Values of the spec --------------------------------------------------------------

ROOM_CODE = "QJ7WXK"
ANA_ID = "p1"
BOB_ID = "p2"
CY_ID = "p3"
ANA = "ANA"  # the nicknames as the server stores them (spec 012)
BOB = "BOB"

# ---- Values of the test harness ------------------------------------------------------

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
UNKNOWN_ROOM = "ZZZZZZ"
EMPTY_ROOM = "EMPTY1"


# ---- The room of the criterion -------------------------------------------------------


class PlayedRoom(NamedTuple):
    """The log of the criterion's room and the entries of its seven edits."""

    entries: list[LogEntry]
    edits: list[LogEntry]


def played_room(start: float) -> PlayedRoom:
    """Ana and Bob type, erase, undo; a check and a reveal lock two cells.

    Joins, a chat message and presence entries come in between.
    """
    log = Log(start)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    log.join(BOB_ID, BOB, 1, "token-of-bob-0002")
    ana_t = log.letter(ANA_ID, 1, 0, "T")
    log.chat(BOB_ID, "Salut")
    bob_a = log.letter(BOB_ID, 1, 1, "A")
    log.join(CY_ID, "CY", 2, "token-of-cy-00003")
    log.presence(ANA_ID, PlayerState.IDLE)
    bob_m = log.letter(BOB_ID, 1, 2, "M", pencil=True)
    ana_erase = log.letter(ANA_ID, 1, 0, None)
    log.presence(ANA_ID, PlayerState.ACTIVE)
    ana_undo = log.letter(ANA_ID, 1, 0, "T", undo=True)
    log.check(BOB_ID, 1, 1)
    check_lock = log.lock(1, 1, "A", revealed=False)
    log.reveal(ANA_ID, 1, 2)
    reveal_lock = log.lock(1, 2, "M", revealed=True)
    log.presence(CY_ID, PlayerState.DISCONNECTED)
    edits = [ana_t, bob_a, bob_m, ana_erase, ana_undo, check_lock, reveal_lock]
    return PlayedRoom(entries=log.entries, edits=edits)


def cell_of(entry: LogEntry) -> tuple[int, int]:
    """The (row, column) of an edit entry: a letter_changed or a cell_locked."""
    event = entry.event
    assert isinstance(event, LetterChanged | CellLocked), event
    return event.row, event.column


def room_edits_of(entries: list[LogEntry]) -> tuple[RoomEdit, ...]:
    """`room_edits(entries)`."""
    from nock.operations import room_edits

    return room_edits(entries)


def edit(
    entry: LogEntry,
    kind: str,
    letter: str | None,
    player_id: str | None,
    nickname: str | None,
    *,
    pencil: bool = False,
) -> RoomEdit:
    """The `RoomEdit` of one edit entry, with its seq, time and cell."""
    from nock.operations import RoomEdit

    row, column = cell_of(entry)
    return RoomEdit.model_validate(
        {
            "seq": entry.event.seq,
            "at": utc(entry.at),
            "kind": kind,
            "row": row,
            "column": column,
            "letter": letter,
            "pencil": pencil,
            "player_id": player_id,
            "nickname": nickname,
        }
    )


def expected_edits(room: PlayedRoom) -> tuple[RoomEdit, ...]:
    """The seven edits of the criterion, in seq order."""
    ana_t, bob_a, bob_m, ana_erase, ana_undo, check_lock, reveal_lock = room.edits
    return (
        edit(ana_t, "typed", "T", ANA_ID, ANA),
        edit(bob_a, "typed", "A", BOB_ID, BOB),
        edit(bob_m, "typed", "M", BOB_ID, BOB, pencil=True),
        edit(ana_erase, "erased", None, ANA_ID, ANA),
        edit(ana_undo, "undone", "T", ANA_ID, ANA),
        edit(check_lock, "locked", "A", None, None),
        edit(reveal_lock, "revealed", "M", None, None),
    )


START = 1_800_000_000.0


# ---- AC-8: room_edits ----------------------------------------------------------------


def test_ac8_room_edits_returns_the_seven_edits_in_seq_order() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    assert result == expected_edits(room)


def test_ac8_the_kinds_of_the_seven_edits() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    kinds = [found.kind for found in result]
    assert kinds == [
        "typed",
        "typed",
        "typed",
        "erased",
        "undone",
        "locked",
        "revealed",
    ]


def test_ac8_each_edit_keeps_the_seq_time_and_cell_of_its_entry() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    found_places: list[tuple[int, datetime, int, int]] = []
    for found in result:
        found_places.append((found.seq, found.at, found.row, found.column))
    expected_places: list[tuple[int, datetime, int, int]] = []
    for entry in room.edits:
        row, column = cell_of(entry)
        expected_places.append((entry.event.seq, utc(entry.at), row, column))
    assert found_places == expected_places


def test_ac8_the_time_of_each_edit_is_in_utc() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    for found in result:
        assert found.at.utcoffset() == timedelta(0)


def test_ac8_letters_pencil_flags_and_players_of_the_edits() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    letters = [found.letter for found in result]
    pencils = [found.pencil for found in result]
    players = [found.player_id for found in result]
    assert letters == ["T", "A", "M", None, "T", "A", "M"]
    assert pencils == [False, False, True, False, False, False, False]
    assert players == [ANA_ID, BOB_ID, BOB_ID, ANA_ID, ANA_ID, None, None]


def test_ac8_the_nicknames_come_from_the_player_joined_entries_in_capitals() -> None:
    room = played_room(START)

    result = room_edits_of(room.entries)

    nicknames = [found.nickname for found in result]
    assert nicknames == [ANA, BOB, BOB, ANA, ANA, None, None]


# ---- AC-8: edge cases ----------------------------------------------------------------


def test_ac8_an_undo_that_empties_its_cell_is_undone_with_no_letter() -> None:
    log = Log(START)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    log.letter(ANA_ID, 1, 0, "T")
    undo = log.letter(ANA_ID, 1, 0, None, undo=True)

    result = room_edits_of(log.entries)

    assert result[-1] == edit(undo, "undone", None, ANA_ID, ANA)


def test_ac8_a_confirmed_pencil_letter_is_typed_without_pencil() -> None:
    log = Log(START)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    pencil = log.letter(ANA_ID, 1, 0, "T", pencil=True)
    confirmed = log.letter(ANA_ID, 1, 0, "T")

    result = room_edits_of(log.entries)

    assert result == (
        edit(pencil, "typed", "T", ANA_ID, ANA, pencil=True),
        edit(confirmed, "typed", "T", ANA_ID, ANA),
    )


def test_ac8_a_player_seated_back_takes_the_nickname_of_the_latest_join() -> None:
    log = Log(START)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    before = log.letter(ANA_ID, 1, 0, "T")
    log.presence(ANA_ID, PlayerState.DISCONNECTED)
    log.leave(ANA_ID, LeaveReason.TIMED_OUT)
    # A new player takes the name, so Ana is seated back as `ANA 2` (spec 032
    # decision 12), with the same player id.
    log.join(CY_ID, ANA, 1, "token-of-cy-00003")
    log.join(ANA_ID, "ANA 2", 0, "token-of-ana-0001")
    after = log.letter(ANA_ID, 1, 1, "A")
    other = log.letter(CY_ID, 1, 2, "M")

    result = room_edits_of(log.entries)

    assert result == (
        edit(before, "typed", "T", ANA_ID, ANA),
        edit(after, "typed", "A", ANA_ID, "ANA 2"),
        edit(other, "typed", "M", CY_ID, ANA),
    )


def test_ac8_a_removed_players_edits_keep_their_nickname() -> None:
    log = Log(START)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    log.join(BOB_ID, BOB, 1, "token-of-bob-0002")
    typed = log.letter(BOB_ID, 1, 0, "T")
    log.leave(BOB_ID, LeaveReason.REMOVED)

    result = room_edits_of(log.entries)

    assert result == (edit(typed, "typed", "T", BOB_ID, BOB),)


def test_ac8_an_edit_with_no_player_joined_before_it_has_no_nickname() -> None:
    room = played_room(START)
    without_the_joins = room.entries[2:]  # from Ana's T on: no player_joined of p1

    result = room_edits_of(without_the_joins)

    assert result[0] == edit(room.edits[0], "typed", "T", ANA_ID, None)
    assert result[1] == edit(room.edits[1], "typed", "A", BOB_ID, None)


def test_ac8_a_log_without_edits_gives_no_edit() -> None:
    log = Log(START)
    log.join(ANA_ID, ANA, 0, "token-of-ana-0001")
    log.chat(ANA_ID, "Bonjour")

    assert room_edits_of(log.entries) == ()


# ---- AC-8: the replay route ----------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return tmp_path


@pytest.fixture
def registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    room_registry = RoomRegistry(clock=fake_clock)
    yield room_registry
    room_registry.close()


@pytest.fixture
def ops_client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def played(registry: RoomRegistry, fx01_grid: Grid) -> PlayedRoom:
    """The criterion's room, registered and logged, created at the clock's time."""
    now = registry.clock()
    room = played_room(now + 1)
    seed_room(registry, new_room(ROOM_CODE, fx01_grid, now), room.entries)
    return room


def replay_of(text: str) -> RoomReplay:
    from nock.operations import RoomReplay

    return RoomReplay.model_validate_json(text)


def keys_in(value: object) -> list[str]:
    """Every key of every object inside a parsed JSON value."""
    keys: list[str] = []
    if isinstance(value, dict):
        for key, child in value.items():
            keys.append(str(key))
            keys.extend(keys_in(child))
    elif isinstance(value, list):
        for child in value:
            keys.extend(keys_in(child))
    return keys


def test_ac8_http_the_replay_answers_200_with_the_room_replay(
    registry: RoomRegistry,
    ops_client: TestClient,
    played: PlayedRoom,
    fx01_grid: Grid,
) -> None:
    response = ops_client.get(edits_path(ROOM_CODE), headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text
    replay = replay_of(response.text)
    assert replay.code == ROOM_CODE
    assert replay.grid == grid_view(fx01_grid)
    assert replay.edits == room_edits_of(registry.store.read_log(ROOM_CODE))


def test_ac8_http_the_replay_holds_the_seven_edits_of_the_log(
    ops_client: TestClient, played: PlayedRoom
) -> None:
    response = ops_client.get(edits_path(ROOM_CODE), headers=bearer(OPS_TOKEN))

    assert replay_of(response.text).edits == expected_edits(played)


def test_ac8_http_the_replay_holds_no_answer_of_fx01_and_no_answer_key(
    ops_client: TestClient, played: PlayedRoom
) -> None:
    response = ops_client.get(edits_path(ROOM_CODE), headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text
    answers_found = [answer for answer in FX01_ANSWERS if answer in response.text]
    assert answers_found == []
    assert "answer" not in keys_in(json.loads(response.text))


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(UNKNOWN_ROOM, id="unknown-code"),
        pytest.param("abc", id="breaks-the-code-pattern"),
        pytest.param("QJ7WX", id="five-characters"),
        pytest.param("qj7wxk", id="lowercase"),
    ],
)
def test_ac8_http_a_code_with_no_room_answers_404(
    ops_client: TestClient, played: PlayedRoom, code: str
) -> None:
    response = ops_client.get(edits_path(code), headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac8_http_an_expired_room_answers_404(
    registry: RoomRegistry,
    ops_client: TestClient,
    played: PlayedRoom,
    fake_clock: FakeClock,
) -> None:
    last_edit_at = registry.store.last_edit_at(ROOM_CODE)
    assert last_edit_at is not None
    fake_clock.now = last_edit_at + LIFE + 1  # spec 032: expired

    response = ops_client.get(edits_path(ROOM_CODE), headers=bearer(OPS_TOKEN))

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac8_http_a_room_with_no_edit_has_an_empty_replay(
    registry: RoomRegistry, ops_client: TestClient, fx01_grid: Grid
) -> None:
    registry.add_room(new_room(EMPTY_ROOM, fx01_grid, registry.clock()))

    response = ops_client.get(edits_path(EMPTY_ROOM), headers=bearer(OPS_TOKEN))

    assert response.status_code == 200, response.text
    replay = replay_of(response.text)
    assert replay.edits == ()
    assert replay.grid == grid_view(fx01_grid)


def test_ac8_http_the_replay_reads_a_room_only_in_the_store_without_making_it_live(
    fake_clock: FakeClock, fx01_grid: Grid, dist_dir: Path
) -> None:
    # Ana joined and wrote T; only the store holds the room. Making it live would
    # log her disconnection (spec 018's `after_restart`).
    store = RoomStore(":memory:")
    now = fake_clock()
    state = new_room(ROOM_CODE, fx01_grid, now)
    store.create_room(state)
    joined = join_room(
        state,
        Join(nickname="Ana", resume_token=None),
        now + 1,
        ANA_ID,
        "token-of-ana-0001",
    )
    store.append(ROOM_CODE, joined.entries)
    typed = handle_message(
        joined.state, ANA_ID, EditLetter(row=1, column=0, letter="T"), now + 2
    )
    store.append(ROOM_CODE, typed.entries)
    log_before = store.read_log(ROOM_CODE)
    registry = RoomRegistry(clock=fake_clock, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=dist_dir, operator_token=OPS_TOKEN)
        with TestClient(app) as client:
            response = client.get(edits_path(ROOM_CODE), headers=bearer(OPS_TOKEN))
        log_after = store.read_log(ROOM_CODE)
    finally:
        registry.close()
        store.close()

    assert response.status_code == 200, response.text
    edits = replay_of(response.text).edits
    assert [(found.kind, found.letter, found.nickname) for found in edits] == [
        ("typed", "T", ANA)
    ]
    assert log_after == log_before
