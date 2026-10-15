"""Tests of spec 018, AC-1: the real WebSocket with a simulated restart.

Process one is a store, a registry and an app on a SQLite file; process two is a
new store, registry and app on the same file. Also the snapshots that the hub
saves: the table layout is the implementer's choice, so they are observed through
`load_room` only. A log row is damaged on purpose, and `load_room` fails exactly
when it has to replay that row, that is when no snapshot covers it. The shared
setup is in `spec018_harness`.
"""

from __future__ import annotations

import contextlib
import random
import string
import time
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from nock.grid import Grid
from nock.protocol import EditLetter, PlayerState, ServerMessage, Snapshot
from nock.room import RoomConfig, RoomState, grid_state
from nock.store import RoomStore
from spec018_harness import (
    DRIVE_EVENTS,
    POLL_SECONDS,
    ROOM_CODE,
    SERVER_CONFIG,
    SHORT_PAUSE_SECONDS,
    WAIT_SECONDS,
    Process,
    corrupt_log_entry,
    drive_room,
    grid_from_text,
    grid_of_peer,
    grid_values,
    letter_cells,
    load_from_file,
    make_dist_dir,
    open_peer,
    players_all_disconnected,
    resume_tokens,
    wait_for,
)

SNAPSHOT_CONFIG = RoomConfig(
    max_edits_per_second=1000, silence_timeout_seconds=600, snapshot_every=100
)


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- Helpers on the SQLite file ----


def wait_until_loadable(path: Path, code: str) -> RoomState:
    """Poll `load_room` until it stops failing on the damaged row."""
    deadline = time.monotonic() + WAIT_SECONDS
    while True:
        try:
            loaded = load_from_file(path, code)
        except ValidationError:
            if time.monotonic() > deadline:
                pytest.fail("the damaged row is still replayed: no snapshot covers it")
            time.sleep(POLL_SECONDS)
            continue
        assert loaded is not None
        return loaded


# ---- Helpers for the WebSocket tests ----


def commit_checker(path: Path, code: str) -> Callable[[ServerMessage], None]:
    """A hook for a Peer: each numbered event it reads is already in the file."""

    def check(message: ServerMessage) -> None:
        if isinstance(message, Snapshot):
            return
        seq = getattr(message, "seq", None)
        if not isinstance(seq, int):
            return
        reader = RoomStore(path)
        try:
            logged = reader.read_log(code, after_seq=seq - 1)
        finally:
            reader.close()
        logged_seqs = [entry.event.seq for entry in logged]
        if seq not in logged_seqs:
            raise AssertionError(f"seq {seq} was sent before it was committed")

    return check


# ---- AC-1: WebSocket with a simulated restart ----


def test_ac1_websocket_every_event_received_is_already_in_the_database(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    one = Process(path, dist_dir, SERVER_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        cells = letter_cells(fx01_grid)[:-1]  # never full
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            checker = commit_checker(path, code)
            ana = open_peer(stack, http_client, code, "Ana", on_message=checker)
            bob = open_peer(stack, http_client, code, "Bob", on_message=checker)
            bob.wait_for_seq(2, "both joins")
            for index in range(30):
                row, column = cells[index % len(cells)]
                sender = ana if index % 2 == 0 else bob
                sender.send(
                    EditLetter(
                        row=row,
                        column=column,
                        letter=string.ascii_uppercase[index % 26],
                    )
                )
            bob.wait_for_seq(32, "the 30 letters")
            ana.wait_for_seq(32, "the 30 letters")

            assert bob.failures() == []
            assert ana.failures() == []
            assert len(bob.letter_events()) == 30
    finally:
        one.shutdown()


def test_ac1_websocket_players_reconnect_after_a_restart_to_the_same_grid(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)[:-1]  # never full
    with contextlib.ExitStack() as cleanup:
        one = Process(path, dist_dir, SERVER_CONFIG)
        # Process one is never closed during the test, as a crash would not.
        cleanup.callback(one.shutdown)
        code = one.registry.register_room(fx01_grid)
        first_run = cleanup.enter_context(contextlib.ExitStack())
        first_client = first_run.enter_context(TestClient(one.app))
        ana = open_peer(first_run, first_client, code, "Ana")
        bob = open_peer(first_run, first_client, code, "Bob")
        bob.wait_for_seq(2, "both joins")
        rng = random.Random(18)
        for index in range(30):
            row, column = rng.choice(cells)
            letter = rng.choice(string.ascii_uppercase)
            sender = ana if index % 2 == 0 else bob
            sender.send(EditLetter(row=row, column=column, letter=letter))
        bob.wait_for_seq(32, "the 30 letters on Bob")
        ana.wait_for_seq(32, "the 30 letters on Ana")
        grid_before = grid_of_peer(bob)
        assert grid_before == grid_of_peer(ana)
        ana_id = ana.you()
        bob_id = bob.you()
        ana_token = ana.snapshot().resume_token
        bob_token = bob.snapshot().resume_token
        bob_view_of_players = bob.snapshot().players
        known_seq = bob.last_seq()

        first_run.close()
        wait_for(
            lambda: players_all_disconnected(one, code),
            "process one to log the closing of both sockets",
        )

        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        second_run = cleanup.enter_context(contextlib.ExitStack())
        second_client = second_run.enter_context(TestClient(two.app))
        ana_again = open_peer(second_run, second_client, code, "Ana", ana_token)
        bob_again = open_peer(second_run, second_client, code, "Bob", bob_token)

        for peer, expected_id in ((ana_again, ana_id), (bob_again, bob_id)):
            snapshot = peer.snapshot()
            assert snapshot.you == expected_id
            assert snapshot.seq >= known_seq
            assert [(p.nickname, p.colour) for p in snapshot.players] == [
                (p.nickname, p.colour) for p in bob_view_of_players
            ]
            assert [p.player_id for p in snapshot.players] == [ana_id, bob_id]
            assert grid_values(snapshot.grid) == grid_before
        assert ana_again.errors() == []
        assert bob_again.errors() == []


def test_ac1_websocket_a_new_player_can_join_a_room_that_only_the_store_knows(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    with contextlib.ExitStack() as cleanup:
        seed_store = RoomStore(path)
        cleanup.callback(seed_store.close)
        live = drive_room(seed_store, fx01_grid)
        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        run = cleanup.enter_context(contextlib.ExitStack())
        http_client = run.enter_context(TestClient(two.app))

        newcomer = open_peer(run, http_client, ROOM_CODE, "Dan")

        snapshot = newcomer.snapshot()
        assert grid_values(snapshot.grid) == grid_values(grid_state(live))
        assert [p.nickname for p in snapshot.players] == ["Ana", "Bob", "Cleo", "Dan"]
        assert [p.state for p in snapshot.players[:3]] == [PlayerState.DISCONNECTED] * 3
        assert snapshot.players[3].state is PlayerState.ACTIVE
        assert snapshot.seq == DRIVE_EVENTS + 3 + 1


# ---- AC-1: snapshots made by the hub ----


def test_ac1_hub_saves_a_snapshot_every_100_logged_events(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)[:-1]  # never full
    one = Process(path, dist_dir, SNAPSHOT_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            ana = open_peer(stack, http_client, code, "Ana")
            sent = 0

            def send_edits(count: int) -> None:
                nonlocal sent
                for _ in range(count):
                    row, column = cells[sent % len(cells)]
                    letter = string.ascii_uppercase[sent % 26]
                    ana.send(EditLetter(row=row, column=column, letter=letter))
                    sent += 1

            send_edits(98)
            ana.wait_for_seq(99, "99 events")
            corrupt_log_entry(path, 50)
            time.sleep(SHORT_PAUSE_SECONDS)
            with pytest.raises(ValidationError):
                load_from_file(path, code)

            send_edits(1)
            ana.wait_for_seq(100, "the 100th event")
            at_100 = wait_until_loadable(path, code)
            assert at_100.seq == 100

            send_edits(99)
            ana.wait_for_seq(199, "199 events")
            corrupt_log_entry(path, 150)
            time.sleep(SHORT_PAUSE_SECONDS)
            with pytest.raises(ValidationError):
                load_from_file(path, code)

            send_edits(1)
            ana.wait_for_seq(200, "the 200th event")
            at_200 = wait_until_loadable(path, code)
            assert at_200.seq == 200
            live = one.registry.room_state(code)
            assert live is not None
            assert grid_state(at_200) == grid_state(live)
            assert resume_tokens(at_200) == resume_tokens(live)
    finally:
        one.shutdown()


def test_ac1_hub_saves_a_snapshot_when_the_room_task_stops(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)[:-1]  # never full
    one = Process(path, dist_dir, SNAPSHOT_CONFIG)
    try:
        code = one.registry.register_room(fx01_grid)
        with contextlib.ExitStack() as stack:
            http_client = stack.enter_context(TestClient(one.app))
            with contextlib.ExitStack() as connection:
                ana = open_peer(connection, http_client, code, "Ana")
                for index in range(10):
                    row, column = cells[index]
                    ana.send(
                        EditLetter(
                            row=row,
                            column=column,
                            letter=string.ascii_uppercase[index % 26],
                        )
                    )
                ana.wait_for_seq(11, "11 events")
                corrupt_log_entry(path, 5)
                time.sleep(SHORT_PAUSE_SECONDS)
                with pytest.raises(ValidationError):
                    load_from_file(path, code)
            # Ana's socket is closed: the room has nobody left and its task stops.
            loaded = wait_until_loadable(path, code)
        assert loaded.seq == 12
        assert loaded.players[0].state is PlayerState.DISCONNECTED
    finally:
        one.shutdown()
