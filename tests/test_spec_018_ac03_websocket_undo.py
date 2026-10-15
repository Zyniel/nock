"""Tests of spec 018, AC-3: undo on the real WebSocket.

Two clients: the other one receives the undo's `letter_changed` and nothing for a
refused undo. The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, ErrorCode, LetterChanged, Undo
from spec018_harness import (
    CellValue,
    Peer,
    grid_from_text,
    grid_of_peer,
    join_peers,
    letter_changed,
    make_app,
    make_dist_dir,
    make_registry,
    player_record,
    server_grid,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry (default in-memory store) whose throttle never refuses."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- Helpers for the WebSocket tests ----


def cell_of_peer(peer: Peer, row: int, column: int) -> CellValue:
    return grid_of_peer(peer)[(row, column)]


# ---- AC-3: undo on the WebSocket ----


def test_ac3_websocket_an_undo_reaches_the_other_client_as_a_letter_changed(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        bob.wait_for_seq(3, "the letter")

        ana.send(Undo())
        bob.wait_for_seq(4, "the undo")
        ana.wait_for_seq(4, "the undo")

        ana_id = ana.you()
        expected = [
            letter_changed(3, 1, 0, "T", ana_id),
            letter_changed(4, 1, 0, None, ana_id),
        ]
        assert bob.letter_events() == expected
        assert ana.letter_events() == expected
        assert cell_of_peer(bob, 1, 0) == (None, False, None)
        assert cell_of_peer(ana, 1, 0) == (None, False, None)
        assert server_grid(registry, room_code)[(1, 0)] == (None, False, None)
        assert ana.errors() == []
        assert bob.errors() == []
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 4
        assert player_record(state, ana_id).last_edit is None


def test_ac3_websocket_an_undo_over_the_other_players_letter_restores_it(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send(EditLetter(row=1, column=1, letter="B"))
        ana.wait_for_seq(3, "Bob's letter")
        ana.send(EditLetter(row=1, column=1, letter="A"))
        bob.wait_for_seq(4, "Ana's letter")

        ana.send(Undo())
        bob.wait_for_seq(5, "the undo")

        assert cell_of_peer(bob, 1, 1) == ("B", False, ana.you())
        assert server_grid(registry, room_code)[(1, 1)] == ("B", False, ana.you())


def test_ac3_websocket_an_undo_after_the_other_player_changed_the_cell_is_refused(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        bob.wait_for_seq(3, "Ana's letter")
        bob.send(EditLetter(row=1, column=0, letter="X"))
        ana.wait_for_seq(4, "Bob's letter")

        ana.send(Undo())
        ana.wait_for_errors(1, "the refusal of the undo")
        # An accepted edit afterwards proves nothing was sent to Bob in between.
        ana.send(EditLetter(row=1, column=1, letter="A"))
        bob.wait_for_seq(5, "the edit after the refusal")
        ana.wait_for_seq(5, "the edit after the refusal")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOTHING_TO_UNDO]
        assert bob.errors() == []
        assert [event.seq for event in bob.letter_events()] == [3, 4, 5]
        assert bob.letter_events()[-1] == letter_changed(5, 1, 1, "A", ana.you())
        assert cell_of_peer(bob, 1, 0) == ("X", False, bob.you())
        assert server_grid(registry, room_code)[(1, 0)] == ("X", False, bob.you())
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 5


def test_ac3_websocket_an_undo_with_nothing_to_undo_answers_only_its_sender(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(Undo())
        ana.wait_for_errors(1, "the refusal")
        bob.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_for_seq(3, "Bob's letter")
        bob.wait_for_seq(3, "Bob's letter")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOTHING_TO_UNDO]
        assert bob.errors() == []
        assert [type(message) for message in bob.events()] == [LetterChanged]
