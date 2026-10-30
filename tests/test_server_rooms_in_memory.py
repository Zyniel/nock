"""Tests of platform/server, AC-23 and AC-24: a room is in memory only while played.

Over the room socket of the app of `host_harness` (a fake clock, accounts off, the
rooms' store on a file), reading `RoomRegistry.live_codes()` and the store. The
shared setup is in `server_harness`.

Readings of the spec's wording:

- "Not live" is `code not in registry.live_codes()`; a test waits (bounded, real
  time) for the room to leave memory after a socket closes, as the task ends
  asynchronously, and waits for the room to be live after a socket opens.
- AC-24's "the room's seq" is the seq of the last entry of the room's log; "the
  store's latest snapshot" is the highest seq of its `snapshots` rows. The check
  comes right after the room left memory: a room leaves memory once its snapshot
  is saved (rule 21).
- "The log holds no entry between that seq and her join's": the first entry after
  the snapshot is Ana's `player_state_changed` to `active`, at the snapshot's seq
  plus one.
- The edge cases of AC-24 use a store whose snapshot saving fails, and one that
  counts the snapshots it saves.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from host_harness import (
    SOCKET_CONFIG,
    create_room_as,
    host_app,
    open_member,
    wait_for_message,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    LetterCellView,
    LetterChanged,
    PlayerState,
    PlayerStateChanged,
    Snapshot,
)
from nock.server import create_app
from server_harness import (
    SNAPSHOT_FAILURE_PAUSE_SECONDS,
    SnapshotStore,
    last_logged_seq,
    latest_snapshot_seq,
    wait_until_live,
    wait_until_not_live,
)
from spec014_harness import has_state_change, socket_url
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import DATABASE_FILE_NAME, wait_for

TYPED_ROW = 1
TYPED_COLUMN = 0
TYPED_LETTER = "T"
NO_ROOMS: frozenset[str] = frozenset()


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def letter_in(snapshot: Snapshot, row: int, column: int) -> str | None:
    """The letter that a snapshot shows at (row, column)."""
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell.letter
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


@contextlib.contextmanager
def serving(
    directory: Path, clock: FakeClock, catalogue: Catalogue, store: SnapshotStore
) -> Iterator[tuple[TestClient, RoomRegistry]]:
    """The app on a registry over `store`; the registry is closed by the test.

    The registry is not closed when the block ends: the test closes it where it
    wants the server to stop.
    """
    registry = RoomRegistry(clock=clock, store=store, config=SOCKET_CONFIG)
    app = create_app(rooms=registry, dist_dir=directory, catalogue=catalogue)
    with TestClient(app) as client:
        yield client, registry


# ---- AC-23: created is not live; a socket makes it live ----------------------------


def test_ac23_a_created_room_is_not_live_a_socket_makes_it_live_until_it_closes(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        code = create_room_as(app, None)
        live_after_creation = app.registry.live_codes()
        stored_after_creation = app.store.has_room(code)

        with app.client.websocket_connect(socket_url(code)):
            wait_until_live(app.registry, code)
            live_while_open = app.registry.live_codes()
        wait_until_not_live(app.registry, code)
        live_after_close = app.registry.live_codes()
        stored_after_close = app.store.has_room(code)

    assert live_after_creation == NO_ROOMS
    assert stored_after_creation is True
    assert live_while_open == frozenset({code})
    assert live_after_close == NO_ROOMS
    assert stored_after_close is True


# ---- AC-24: live until the last socket is gone -------------------------------------


def test_ac24_the_room_stays_live_for_the_second_socket_then_is_saved_and_leaves(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(
            tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
        ) as app,
        contextlib.ExitStack() as bob_stack,
    ):
        code = create_room_as(app, None)
        with contextlib.ExitStack() as ana_stack:
            ana = open_member(ana_stack, app.client, code, "Ana")
            bob = open_member(bob_stack, app.client, code, "Bob")
            ana_id = ana.snapshot().you
            ana.send(
                EditLetter(row=TYPED_ROW, column=TYPED_COLUMN, letter=TYPED_LETTER)
            )
            wait_for_message(ana, LetterChanged)
        bob.wait_until(
            lambda: has_state_change(bob, ana_id, PlayerState.DISCONNECTED),
            "Ana's departure",
        )
        live_with_bob = app.registry.live_codes()

        bob_stack.close()
        wait_until_not_live(app.registry, code)
        live_after_bob = app.registry.live_codes()
        room_seq = last_logged_seq(app.store, code)
        snapshot_seq = latest_snapshot_seq(app.database_path, code)

    assert live_with_bob == frozenset({code})
    assert live_after_bob == NO_ROOMS
    assert room_seq == 5  # two joins, one letter, two disconnections
    assert snapshot_seq == room_seq


def test_ac24_ana_finds_her_letter_and_seat_with_nothing_logged_before_her_join(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
    ) as app:
        code = create_room_as(app, None)
        with contextlib.ExitStack() as first_stack:
            ana = open_member(first_stack, app.client, code, "Ana")
            bob = open_member(first_stack, app.client, code, "Bob")
            ana_id = ana.snapshot().you
            ana_token = ana.snapshot().resume_token
            ana.send(
                EditLetter(row=TYPED_ROW, column=TYPED_COLUMN, letter=TYPED_LETTER)
            )
            wait_for_message(bob, LetterChanged)
        wait_until_not_live(app.registry, code)
        snapshot_seq = latest_snapshot_seq(app.database_path, code)

        with contextlib.ExitStack() as second_stack:
            again = open_member(second_stack, app.client, code, "Ana", ana_token)
            letter = letter_in(again.snapshot(), TYPED_ROW, TYPED_COLUMN)
            seat = again.snapshot().you
            after_snapshot = app.store.read_log(code, after_seq=snapshot_seq)

    assert letter == TYPED_LETTER
    assert seat == ana_id
    assert len(after_snapshot) >= 1, "Ana's join logged nothing"
    first_after = after_snapshot[0].event
    assert first_after.seq == snapshot_seq + 1
    assert isinstance(first_after, PlayerStateChanged)
    assert (first_after.player_id, first_after.state) == (ana_id, PlayerState.ACTIVE)


def test_ac24_a_room_whose_snapshot_fails_stays_live_and_is_saved_at_shutdown(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = SnapshotStore(tmp_path / DATABASE_FILE_NAME)
    registry: RoomRegistry | None = None
    try:
        with serving(tmp_path, fake_clock, catalogue, store) as (client, registry):
            code = client.post("/api/rooms", json={"grid_number": 1}).json()["code"]
            store.fail_snapshots = True
            with contextlib.ExitStack() as stack:
                ana = open_member(stack, client, code, "Ana")
                ana.send(
                    EditLetter(row=TYPED_ROW, column=TYPED_COLUMN, letter=TYPED_LETTER)
                )
                wait_for_message(ana, LetterChanged)
            wait_for(store.snapshot_failed.is_set, "the failed snapshot")
            time.sleep(SNAPSHOT_FAILURE_PAUSE_SECONDS)
            live_after_failure = registry.live_codes()
            store.fail_snapshots = False
            saved_before_shutdown = list(store.saved_seqs)
        registry.close()
        room_seq = last_logged_seq(store, code)
        snapshot_seq = latest_snapshot_seq(tmp_path / DATABASE_FILE_NAME, code)
    finally:
        if registry is not None:
            registry.close()
        store.close()

    assert live_after_failure == frozenset({code})
    assert saved_before_shutdown == []
    assert snapshot_seq == room_seq
    assert store.saved_seqs == [room_seq]


def test_ac24_the_shutdown_saves_no_snapshot_of_a_room_that_left_memory(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = SnapshotStore(tmp_path / DATABASE_FILE_NAME)
    registry: RoomRegistry | None = None
    try:
        with serving(tmp_path, fake_clock, catalogue, store) as (client, registry):
            code = client.post("/api/rooms", json={"grid_number": 1}).json()["code"]
            with contextlib.ExitStack() as stack:
                ana = open_member(stack, client, code, "Ana")
                ana.send(
                    EditLetter(row=TYPED_ROW, column=TYPED_COLUMN, letter=TYPED_LETTER)
                )
                wait_for_message(ana, LetterChanged)
            wait_until_not_live(registry, code)
            saved_when_it_left = list(store.saved_seqs)
        registry.close()
        saved_after_shutdown = list(store.saved_seqs)
        room_seq = last_logged_seq(store, code)
    finally:
        if registry is not None:
            registry.close()
        store.close()

    assert saved_when_it_left == [room_seq]
    assert saved_after_shutdown == [room_seq]
