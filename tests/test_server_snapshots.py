"""Tests of platform/server, AC-27 and AC-28: a room keeps two snapshots.

AC-27 runs Ana over the room socket of `server_harness.serving` (a file store, a
fake clock that never moves, an edit limit that never refuses): she types 250
letters, one `letter_changed` each. The snapshots are read from the database file
(`snapshot_seqs`). The edge cases of the criterion, a room whose first and newest
snapshots are one row and the rooms that a save does not touch, run on
`RoomStore.save_snapshot` itself.

AC-28 plays a room with the rules (`spec034_harness.Play`, on a store file): Ana
and Bob join, Ana types, and between seq 150 and 250 Bob types `VIDE`, checks the
word and Ana reveals a cell. The snapshots a hub would save (seq 100, 200 and the
room's seq 250 when its task ends) are saved by hand with `save_snapshot`, one
stage at a time. At each stage, Ana's catch-up from seq 150 to 250 and the room's
state at seq 150 are read through `RoomRegistry.catch_up` and
`RoomStore.load_room_at`, and compared with each other and with the truth the play
keeps: the state it had at seq 150 and `build_catch_up` on its own log.

Readings of the spec's wording:

- "The room's seq" is the seq of the last entry of the room's log.
- "The log whole" is every entry from seq 1 to the room's seq, none missing.
- "Every letter" is the letter each typed cell ends with, read in the loaded room.
- "The state at or before the first snapshot's seq" is `load_room_at(code, 0)`: a
  room's first snapshot is at seq 0.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import open_member
from nock.catalogue import Catalogue
from nock.catch_up import CatchUp, build_catch_up
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import CellTarget, Check, Reveal, WordTarget
from nock.room import LogEntry, RoomState, new_room
from nock.store import RoomStore
from server_harness import (
    TYPING_CONFIG,
    last_logged_seq,
    serving,
    snapshot_seqs,
    type_letters,
    wait_until_not_live,
)
from spec017_harness import FakeClock
from spec018_harness import letter_cells
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import DATABASE_FILE_NAME
from spec034_harness import ANA, BOB, CODE, TA, TB, Play, T, registry_catch_up

TYPED_COUNT = 250
SNAPSHOT_EVERY = 100
OTHER_CODE = "OTHER1"
OTHER_SNAPSHOT_SEQ = 100


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


# ---- AC-27: over the room socket ---------------------------------------------------


def seqs_of(entries: list[LogEntry]) -> list[int]:
    """The seq of each log entry, in order."""
    seqs: list[int] = []
    for entry in entries:
        seqs.append(entry.event.seq)
    return seqs


def test_ac27_ana_types_250_letters_and_the_store_keeps_two_snapshots(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    store = RoomStore(path)
    try:
        with serving(store, fake_clock, catalogue, TYPING_CONFIG) as (
            client,
            registry,
        ):
            code = client.post("/api/rooms", json={"grid_number": 1}).json()["code"]
            with contextlib.ExitStack() as stack:
                ana = open_member(stack, client, code, "Ana")
                typed = type_letters(ana, fx01_grid, TYPED_COUNT)
                seqs_while_open = snapshot_seqs(path, code)
            wait_until_not_live(registry, code)
            seqs_after_close = snapshot_seqs(path, code)
            room_seq = last_logged_seq(store, code)
            logged_seqs = seqs_of(store.read_log(code))
            loaded = store.load_room(code)
    finally:
        store.close()

    assert seqs_while_open == [0, 2 * SNAPSHOT_EVERY]
    assert seqs_after_close == [0, room_seq]
    assert room_seq > 2 * SNAPSHOT_EVERY
    assert logged_seqs == list(range(1, room_seq + 1))
    assert loaded is not None
    assert loaded.seq == room_seq
    loaded_letters: dict[tuple[int, int], str | None] = {}
    for cell in loaded.cells:
        loaded_letters[(cell.row, cell.column)] = cell.letter
    for position, letter in typed.items():
        assert loaded_letters[position] == letter


def test_ac27_the_shutdown_with_her_socket_open_leaves_the_first_and_the_room_seq(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    store = RoomStore(path)
    try:
        with serving(store, fake_clock, catalogue, TYPING_CONFIG) as (
            client,
            registry,
        ):
            code = client.post("/api/rooms", json={"grid_number": 1}).json()["code"]
            with contextlib.ExitStack() as stack:
                ana = open_member(stack, client, code, "Ana")
                type_letters(ana, fx01_grid, TYPED_COUNT)
                seqs_before_shutdown = snapshot_seqs(path, code)
                registry.close()
                seqs_after_shutdown = snapshot_seqs(path, code)
                room_seq = last_logged_seq(store, code)
    finally:
        store.close()

    assert seqs_before_shutdown == [0, 2 * SNAPSHOT_EVERY]
    assert seqs_after_shutdown == [0, room_seq]
    assert room_seq > 2 * SNAPSHOT_EVERY


# ---- AC-27: the saves of RoomStore -------------------------------------------------


@pytest.fixture
def file_store(tmp_path: Path) -> Iterator[RoomStore]:
    store = RoomStore(tmp_path / DATABASE_FILE_NAME)
    yield store
    store.close()


def at_seq(state: RoomState, seq: int) -> RoomState:
    """The state with another seq, as a save of a later moment of the room."""
    return state.model_copy(update={"seq": seq})


@pytest.mark.parametrize(
    ("saved", "kept"),
    [
        pytest.param([], [0], id="a new room holds its first snapshot only"),
        pytest.param([0], [0], id="a save at the first's seq replaces it"),
        pytest.param([100], [0, 100], id="a second snapshot is kept"),
        pytest.param([100, 100], [0, 100], id="a save at the newest's seq replaces it"),
        pytest.param([100, 200], [0, 200], id="a third deletes the one between"),
        pytest.param([100, 200, 300, 400], [0, 400], id="each save deletes the others"),
        pytest.param([100, 0], [0], id="a save at the first's seq deletes the newest"),
    ],
)
def test_ac27_each_save_leaves_the_rooms_first_and_newest_snapshots(
    file_store: RoomStore,
    tmp_path: Path,
    fx01_grid: Grid,
    saved: list[int],
    kept: list[int],
) -> None:
    first = new_room(CODE, fx01_grid, T)
    file_store.create_room(first)

    for seq in saved:
        file_store.save_snapshot(at_seq(first, seq))

    assert snapshot_seqs(tmp_path / DATABASE_FILE_NAME, CODE) == kept


def test_ac27_a_save_deletes_no_snapshot_of_another_room(
    file_store: RoomStore, tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    first = new_room(CODE, fx01_grid, T)
    other = new_room(OTHER_CODE, fx01_grid, T, share_token="share-token-of-other")
    file_store.create_room(first)
    file_store.create_room(other)
    file_store.save_snapshot(at_seq(other, OTHER_SNAPSHOT_SEQ))

    for seq in (100, 200, 300):
        file_store.save_snapshot(at_seq(first, seq))

    assert snapshot_seqs(path, CODE) == [0, 300]
    assert snapshot_seqs(path, OTHER_CODE) == [0, OTHER_SNAPSHOT_SEQ]


# ---- AC-28: a catch-up does not depend on the snapshots saved since ----------------

ABSENCE_FROM_SEQ = 150
ABSENCE_UNTIL_SEQ = 250
BOB_CHECKS_AT = T + 160
ANA_REVEALS_AT = T + 170
BOB_AND_REVEAL_CELLS = {(2, 1), (2, 2), (2, 3), (2, 4), (1, 1)}
FILLER_LETTERS = "QXZ"


def filler_cells(grid: Grid) -> list[tuple[int, int]]:
    """The letter cells Ana types over: those that Bob and the reveal leave alone."""
    cells: list[tuple[int, int]] = []
    for position in letter_cells(grid):
        if position not in BOB_AND_REVEAL_CELLS:
            cells.append(position)
    return cells


def filler_edit(play: Play, cells: list[tuple[int, int]]) -> None:
    """Ana types the next filler letter: one entry, a letter that changes its cell."""
    number = play.state.seq
    row, column = cells[number % len(cells)]
    letter = FILLER_LETTERS[(number // len(cells)) % len(FILLER_LETTERS)]
    play.write(ANA, row, column, letter, now=T + number)


def play_to_seq_250(grid: Grid, store: RoomStore) -> Play:
    """Play the room to seq 250 in `store`.

    Seq 1 and 2 are the joins of Ana and Bob. Ana types filler letters up to seq
    150. Bob then types `VIDE` and checks the word, Ana reveals the cell (1, 1),
    and Ana types filler letters up to seq 250.
    """
    cells = filler_cells(grid)
    play = Play(grid, store)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    while play.state.seq < ABSENCE_FROM_SEQ:
        filler_edit(play, cells)
    for offset, letter in enumerate("VIDE"):
        play.write(BOB, 2, 1 + offset, letter, now=T + play.state.seq)
    play.send(
        BOB, Check(target=WordTarget(row=2, column=0, clue_index=0)), BOB_CHECKS_AT
    )
    play.send(ANA, Reveal(target=CellTarget(row=1, column=1)), ANA_REVEALS_AT)
    while play.state.seq < ABSENCE_UNTIL_SEQ:
        filler_edit(play, cells)
    assert play.state.seq == ABSENCE_UNTIL_SEQ
    return play


class Reading(NamedTuple):
    """What the store gave at one stage: its snapshots, a catch-up, a state."""

    snapshot_seqs: list[int]
    catch_up: CatchUp
    state_at_150: RoomState


def read_stage(
    registry: RoomRegistry, store: RoomStore, path: Path, code: str
) -> Reading:
    """Ana's catch-up from seq 150 to 250 and the room's state at seq 150."""
    answer = registry_catch_up(registry, ABSENCE_FROM_SEQ, ABSENCE_UNTIL_SEQ, TA)
    assert answer is not None, "no catch-up"
    state = store.load_room_at(code, ABSENCE_FROM_SEQ)
    assert state is not None, "no state at seq 150"
    return Reading(snapshot_seqs(path, code), answer, state)


def room_summary(state: RoomState) -> tuple[object, ...]:
    """The seq, the cells and the (id, nickname) of each player of a state."""
    players: list[tuple[str, str]] = []
    for player in state.players:
        players.append((player.player_id, player.nickname))
    return (state.seq, state.cells, players)


def test_ac28_the_catch_up_and_the_state_at_150_are_the_same_at_each_stage(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    play_store = RoomStore(path)
    store = RoomStore(path)
    registry = RoomRegistry(clock=lambda: T + 1_000.0, store=store)
    try:
        play = play_to_seq_250(fx01_grid, play_store)
        readings: list[Reading] = []
        for saved_seq in (100, 200, ABSENCE_UNTIL_SEQ):
            play_store.save_snapshot(play.states[saved_seq])
            readings.append(read_stage(registry, store, path, CODE))
        truth = build_catch_up(
            ABSENCE_FROM_SEQ,
            ABSENCE_UNTIL_SEQ,
            play.states[ABSENCE_FROM_SEQ],
            play.entries_after(ABSENCE_FROM_SEQ),
        )
    finally:
        registry.close()
        store.close()
        play_store.close()

    assert [reading.snapshot_seqs for reading in readings] == [
        [0, 100],
        [0, 200],
        [0, 250],
    ]
    for reading in readings:
        assert reading.catch_up == truth
        assert room_summary(reading.state_at_150) == room_summary(
            play.states[ABSENCE_FROM_SEQ]
        )
    assert len(truth.lines) > 0
    named = sorted((name.player_id, name.nickname) for name in truth.names)
    assert named == [(ANA, "ANA"), (BOB, "BOB")]


def test_ac28_the_state_at_the_first_snapshots_seq_is_the_first_snapshot(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    store = RoomStore(path)
    try:
        play = play_to_seq_250(fx01_grid, store)
        for saved_seq in (100, 200, ABSENCE_UNTIL_SEQ):
            store.save_snapshot(play.states[saved_seq])
        first = store.load_room_at(CODE, 0)
    finally:
        store.close()

    assert first is not None
    assert room_summary(first) == room_summary(play.states[0])
    assert first.players == ()
