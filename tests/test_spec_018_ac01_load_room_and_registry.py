"""Tests of spec 018, AC-1: `load_room`, the registry with a store and the app.

A 250-step room driven with the rules and read back with `load_room` (with and
without a snapshot, after a crash, with a removed player, with a damaged log row),
the registry that records its rooms in the store and loads the one it finds there,
and `create_app` with `NOCK_DATABASE`. The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    LeaveReason,
    LetterChanged,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
)
from nock.room import LogEntry, grid_state, new_room
from nock.server import create_app
from nock.store import RoomStore
from spec018_harness import (
    DRIVE_EVENTS,
    LATER,
    OTHER_CODE,
    PUBLISHED_NUMBER,
    ROOM_CODE,
    SERVER_CONFIG,
    START_TIME,
    assert_same_room,
    corrupt_log_entry,
    drive_room,
    grid_from_text,
    grid_values,
    make_dist_dir,
    published_catalogue,
    resume_tokens,
    token_of,
    two_player_room,
)

# ---- Fixtures ----


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def memory_store() -> Iterator[RoomStore]:
    store = RoomStore(":memory:")
    yield store
    store.close()


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return published_catalogue(fx01_grid)


# ---- AC-1: load_room after 250 steps ----


def test_ac1_the_drive_reaches_250_events_with_real_undos(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)

    assert live.seq == DRIVE_EVENTS
    log = memory_store.read_log(ROOM_CODE)
    assert [entry.event.seq for entry in log] == list(range(1, DRIVE_EVENTS + 1))
    undo_entries = [entry for entry in log if entry.undo]
    assert len(undo_entries) >= 40
    for entry in undo_entries:
        assert isinstance(entry.event, LetterChanged)
    assert log[0].resume_token == token_of(0)
    assert [entry.resume_token for entry in log[:3]] == [token_of(i) for i in range(3)]
    assert all(entry.resume_token is None for entry in log[3:])


def test_ac1_load_room_replays_250_steps_to_the_live_state(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)

    loaded = memory_store.load_room(ROOM_CODE)

    assert live.seq == DRIVE_EVENTS
    assert_same_room(loaded, live)
    assert loaded is not None
    assert loaded.seq == DRIVE_EVENTS
    assert resume_tokens(loaded) == [token_of(0), token_of(1), token_of(2)]
    letters = [value[0] for value in grid_values(grid_state(loaded)).values()]
    assert any(letter is not None for letter in letters)


def test_ac1_load_room_after_a_snapshot_at_seq_100_gives_the_same_state(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid, snapshot_at=100)

    loaded = memory_store.load_room(ROOM_CODE)

    assert live.seq == DRIVE_EVENTS
    assert_same_room(loaded, live)
    assert loaded is not None
    assert len(loaded.players) == 3


def test_ac1_load_room_in_a_file_survives_a_crash_without_close(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    crashed = RoomStore(path)
    try:
        live = drive_room(crashed, fx01_grid)
        # The first store is neither closed nor given a last snapshot, as in a crash.
        restarted = RoomStore(path)
        try:
            assert_same_room(restarted.load_room(ROOM_CODE), live)
            assert len(restarted.read_log(ROOM_CODE)) == DRIVE_EVENTS
        finally:
            restarted.close()
    finally:
        crashed.close()


def test_ac1_a_removed_player_is_gone_after_load_and_their_token_is_banned(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    live = drive_room(memory_store, fx01_grid)
    second_token = token_of(1)
    removal = LogEntry(
        at=LATER,
        event=PlayerLeft(seq=live.seq + 1, player_id="p2", reason=LeaveReason.REMOVED),
    )
    memory_store.append(ROOM_CODE, [removal])

    loaded = memory_store.load_room(ROOM_CODE)

    assert loaded is not None
    assert loaded.seq == DRIVE_EVENTS + 1
    assert [player.player_id for player in loaded.players] == ["p1", "p3"]
    assert loaded.removed_tokens == (second_token,)


def test_ac1_a_damaged_log_row_makes_load_room_raise(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    store = RoomStore(path)
    try:
        drive_room(store, fx01_grid)
    finally:
        store.close()
    corrupt_log_entry(path, 20)

    reopened = RoomStore(path)
    try:
        with pytest.raises(ValidationError):
            reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()


# ---- AC-1: the registry with a store ----


def test_ac1_register_room_records_the_room_in_the_store(
    memory_store: RoomStore, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    room_registry = RoomRegistry(store=memory_store, clock=fake_clock)
    try:
        code = room_registry.register_room(fx01_grid, grid_number=7)
        state = room_registry.room_state(code)

        assert memory_store.has_room(code) is True
        assert state is not None
        assert state.created_at == fake_clock.now
        assert memory_store.load_room(code) == state
        # Spec 028: register_room gives every room a share token.
        assert state.share_token is not None
        assert memory_store.load_room(code) == new_room(
            code, fx01_grid, fake_clock.now, 7, share_token=state.share_token
        )
    finally:
        room_registry.close()


def test_ac1_add_room_records_the_state_in_the_store(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    room_registry = RoomRegistry(store=memory_store)
    try:
        state = two_player_room(fx01_grid)

        room_registry.add_room(state)

        assert memory_store.has_room(ROOM_CODE) is True
        assert memory_store.load_room(ROOM_CODE) == state
    finally:
        room_registry.close()


def test_ac1_a_code_that_is_only_in_the_store_counts_as_taken(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    room_registry = RoomRegistry(store=memory_store)
    try:
        with pytest.raises(ValueError, match=r".+"):
            room_registry.add_room(new_room(ROOM_CODE, fx01_grid, START_TIME))

        assert memory_store.load_room(ROOM_CODE) == two_player_room(fx01_grid)
    finally:
        room_registry.close()


def test_ac1_closing_a_registry_leaves_a_store_it_was_given_open(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    room_registry = RoomRegistry(store=memory_store)
    code = room_registry.register_room(fx01_grid)

    room_registry.close()

    assert memory_store.has_room(code) is True
    assert memory_store.read_log(code) == []


def test_ac1_a_room_found_in_the_store_is_loaded_and_its_players_disconnected(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / "nock.sqlite3"
    first_store = RoomStore(path)
    second_store = RoomStore(path)
    try:
        live = drive_room(first_store, fx01_grid)
        assert live.seq == DRIVE_EVENTS
        # Process one is dropped without a close: process two starts on the file.
        fake_clock.now = LATER
        room_registry = RoomRegistry(
            config=SERVER_CONFIG, clock=fake_clock, store=second_store
        )
        try:
            state = room_registry.room_state(ROOM_CODE)

            assert state is not None
            assert state.seq == DRIVE_EVENTS + 3
            assert grid_state(state) == grid_state(live)
            assert resume_tokens(state) == resume_tokens(live)
            assert [player.player_id for player in state.players] == ["p1", "p2", "p3"]
            for player in state.players:
                assert player.state is PlayerState.DISCONNECTED
                assert player.disconnected_at == LATER
                assert player.selection is None
                assert player.recent_edits == ()
            assert second_store.read_log(ROOM_CODE, after_seq=DRIVE_EVENTS) == [
                LogEntry(
                    at=LATER,
                    event=PlayerStateChanged(
                        seq=DRIVE_EVENTS + index + 1,
                        player_id=f"p{index + 1}",
                        state=PlayerState.DISCONNECTED,
                    ),
                )
                for index in range(3)
            ]
            assert room_registry.find_room(ROOM_CODE) == fx01_grid

            again = room_registry.room_state(ROOM_CODE)
            assert again == state
            assert len(second_store.read_log(ROOM_CODE)) == DRIVE_EVENTS + 3
        finally:
            room_registry.close()
    finally:
        second_store.close()
        first_store.close()


def test_ac1_an_unknown_code_is_still_unknown_with_a_store(
    memory_store: RoomStore, fx01_grid: Grid
) -> None:
    memory_store.create_room(two_player_room(fx01_grid))
    room_registry = RoomRegistry(store=memory_store)
    try:
        assert room_registry.room_state(OTHER_CODE) is None
        assert room_registry.find_room(OTHER_CODE) is None
    finally:
        room_registry.close()


# ---- AC-1: the app and NOCK_DATABASE ----


def test_ac1_create_app_stores_the_rooms_in_the_file_of_nock_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    dist_dir: Path,
) -> None:
    path = tmp_path / "data.sqlite3"
    monkeypatch.setenv("NOCK_DATABASE", str(path))
    app = create_app(dist_dir=dist_dir, catalogue=catalogue)
    assert not path.exists(), "the store must open when the app starts, not before"

    with TestClient(app) as http_client:
        assert path.exists()
        response = http_client.post(
            "/api/rooms", json={"grid_number": PUBLISHED_NUMBER}
        )
        assert response.status_code == 201
        code = response.json()["code"]

    store = RoomStore(path)
    try:
        assert store.has_room(code) is True
        loaded = store.load_room(code)
    finally:
        store.close()
    assert loaded is not None
    assert loaded.grid_number == PUBLISHED_NUMBER


def test_ac1_create_app_without_nock_database_writes_no_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    dist_dir: Path,
) -> None:
    monkeypatch.delenv("NOCK_DATABASE", raising=False)
    monkeypatch.chdir(tmp_path)
    before = sorted(entry.name for entry in tmp_path.iterdir())

    with TestClient(create_app(dist_dir=dist_dir, catalogue=catalogue)) as http_client:
        response = http_client.post(
            "/api/rooms", json={"grid_number": PUBLISHED_NUMBER}
        )
        assert response.status_code == 201

    after = sorted(entry.name for entry in tmp_path.iterdir())
    assert after == before


def test_ac1_the_app_never_closes_a_registry_it_was_given(
    memory_store: RoomStore, fx01_grid: Grid, dist_dir: Path
) -> None:
    given = RoomRegistry(store=memory_store)
    try:
        with TestClient(create_app(rooms=given, dist_dir=dist_dir)):
            pass

        code = given.register_room(fx01_grid)

        assert memory_store.has_room(code) is True
    finally:
        given.close()
