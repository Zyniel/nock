"""Tests of spec 029, AC-1: a finished room's summary carries its date and its time.

Python: in spec 026 AC-1's play (`FULL17`, then `T` at (4, 4) at `NOW + 754.0`),
the new state has `solved_at == NOW + 754.0` and `solved_elapsed_ms == 754000`;
replaying the play's entries from `new_room` gives the same two values;
`room_summary` of that state has `finished_at` equal to `NOW + 754.0` in UTC and
`elapsed_ms == 754000`, and that of an unsolved room has both None.

HTTP: `POST /api/rooms/summaries` answers a solved room's summary with those
`finished_at` and `elapsed_ms`, and an unsolved one's with both null. A room stored
before this spec, whose latest snapshot has `solved` true without the two fields,
gets the values of its `grid_solved` log entry, from `RoomRegistry.room_summaries`
and over HTTP. The test writes that snapshot through `RoomStore.save_snapshot` of
a state built from JSON without the keys `solved_at` and `solved_elapsed_ms`.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.room import RoomKey, RoomState
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec026_harness import FIRST_TOKEN, NOW, ROOM_CODE, SECOND_TOKEN
from spec029_harness import (
    SOLVE_MS,
    SOLVE_SECONDS,
    Play,
    Player,
    parse_time,
    play_fx01,
)
from spec032_harness import (
    NO_TICK_CONFIG,
    grid_from_text,
    make_dist_dir,
    post_summaries,
    utc,
)

UNSOLVED_CODE = "OPEN01"
PLAYERS = [Player("Ana", "p1", FIRST_TOKEN), Player("Bob", "p2", SECOND_TOKEN)]
# The two fields of this spec: a room stored before it has neither.
NEW_FIELDS = ("solved_at", "solved_elapsed_ms")


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def spec_026_play(grid: Grid) -> Play:
    """Spec 026 AC-1's play: p1 writes 17 letters at NOW, p2 `T` at NOW + 754.0."""
    return play_fx01(grid, ROOM_CODE, PLAYERS, start=NOW)


def unsolved_play(grid: Grid, code: str = UNSOLVED_CODE) -> Play:
    """A FX-01 room where Ana and Bob joined at NOW, and nothing else."""
    return play_fx01(grid, code, PLAYERS, start=NOW, solved_after=None)


def replayed(play: Play) -> RoomState:
    """The room rebuilt from `new_room` by `replay` of every entry of the play."""
    state = play.initial
    for entry in play.log:
        state = nock.room.replay(state, entry)
    return state


def without_new_fields(state: RoomState) -> RoomState:
    """The state as a room stored before this spec holds it: no two new fields."""
    data = json.loads(state.model_dump_json())
    for name in NEW_FIELDS:
        data.pop(name, None)
    return RoomState.model_validate_json(json.dumps(data))


@contextlib.contextmanager
def summaries_client(
    tmp_path: Path, clock: FakeClock
) -> Iterator[tuple[TestClient, RoomRegistry, RoomStore]]:
    """An app on a registry on a store file, its registry and its store."""
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=clock, store=store, config=NO_TICK_CONFIG)
    try:
        app = create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))
        with TestClient(app) as client:
            yield client, registry, store
    finally:
        registry.close()
        store.close()


def store_legacy_room(store: RoomStore, play: Play, clock: FakeClock) -> None:
    """Write a room as before this spec: its log, then its solved snapshot.

    The snapshot has `solved` True and neither `solved_at` nor
    `solved_elapsed_ms`; the log holds the play's `grid_solved` entry.
    """
    store.create_room(play.initial, last_edit_at=clock())
    store.append(play.initial.code, play.log)
    legacy = without_new_fields(play.state)
    assert legacy.solved is True
    store.save_snapshot(legacy)


# ---- Python: the state --------------------------------------------------------


def test_ac1_the_solving_step_sets_solved_at(fx01_grid: Grid) -> None:
    play = spec_026_play(fx01_grid)

    assert play.state.solved_at == NOW + SOLVE_SECONDS


def test_ac1_the_solving_step_sets_solved_elapsed_ms(fx01_grid: Grid) -> None:
    play = spec_026_play(fx01_grid)

    assert play.state.solved_elapsed_ms == SOLVE_MS


def test_ac1_replaying_the_play_gives_the_same_two_values(fx01_grid: Grid) -> None:
    play = spec_026_play(fx01_grid)

    state = replayed(play)

    assert state.solved is True
    assert state.solved_at == NOW + SOLVE_SECONDS
    assert state.solved_elapsed_ms == SOLVE_MS


def test_ac1_an_unsolved_room_has_neither_value(fx01_grid: Grid) -> None:
    play = unsolved_play(fx01_grid)

    assert play.state.solved_at is None
    assert play.state.solved_elapsed_ms is None


# ---- Python: the summary ------------------------------------------------------


def test_ac1_the_summary_of_the_solved_room_carries_its_date_and_time(
    fx01_grid: Grid,
) -> None:
    play = spec_026_play(fx01_grid)

    summary = nock.room.room_summary(play.state, NOW + SOLVE_SECONDS)

    assert summary.finished_at == utc(NOW + SOLVE_SECONDS)
    assert summary.elapsed_ms == SOLVE_MS


def test_ac1_the_summary_of_an_unsolved_room_has_both_none(fx01_grid: Grid) -> None:
    play = unsolved_play(fx01_grid)

    summary = nock.room.room_summary(play.state, NOW)

    assert summary.finished_at is None
    assert summary.elapsed_ms is None


# ---- HTTP: POST /api/rooms/summaries ------------------------------------------


def test_ac1_the_summaries_route_answers_a_solved_rooms_date_and_time(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    play = spec_026_play(fx01_grid)
    with summaries_client(tmp_path, fake_clock) as (client, registry, _):
        registry.add_room(play.state)

        response = post_summaries(client, [(ROOM_CODE, FIRST_TOKEN)])

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["solved"] is True
    assert parse_time(body[0]["finished_at"]) == utc(NOW + SOLVE_SECONDS)
    assert body[0]["elapsed_ms"] == SOLVE_MS


def test_ac1_the_summaries_route_answers_null_for_an_unsolved_room(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    play = unsolved_play(fx01_grid)
    with summaries_client(tmp_path, fake_clock) as (client, registry, _):
        registry.add_room(play.state)

        response = post_summaries(client, [(UNSOLVED_CODE, FIRST_TOKEN)])

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["solved"] is False
    assert "finished_at" in body[0]
    assert body[0]["finished_at"] is None
    assert "elapsed_ms" in body[0]
    assert body[0]["elapsed_ms"] is None


# ---- A room stored before this spec -------------------------------------------


def test_ac1_a_room_stored_before_this_spec_loads_without_solved_at(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    play = spec_026_play(fx01_grid)
    with summaries_client(tmp_path, fake_clock) as (_, _, store):
        store_legacy_room(store, play, fake_clock)

        loaded = store.load_room(ROOM_CODE)

    assert loaded is not None
    assert loaded.solved is True
    assert loaded.solved_at is None


def test_ac1_room_summaries_reads_a_stored_rooms_values_from_its_log(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    play = spec_026_play(fx01_grid)
    with summaries_client(tmp_path, fake_clock) as (_, registry, store):
        store_legacy_room(store, play, fake_clock)
        key = RoomKey(code=ROOM_CODE, resume_token=FIRST_TOKEN)

        summaries = registry.room_summaries([key])

    assert len(summaries) == 1
    assert summaries[0].finished_at == utc(NOW + SOLVE_SECONDS)
    assert summaries[0].elapsed_ms == SOLVE_MS


def test_ac1_the_summaries_route_answers_a_stored_rooms_values_from_its_log(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    play = spec_026_play(fx01_grid)
    with summaries_client(tmp_path, fake_clock) as (client, _, store):
        store_legacy_room(store, play, fake_clock)

        response = post_summaries(client, [(ROOM_CODE, SECOND_TOKEN)])

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert parse_time(body[0]["finished_at"]) == utc(NOW + SOLVE_SECONDS)
    assert body[0]["elapsed_ms"] == SOLVE_MS
