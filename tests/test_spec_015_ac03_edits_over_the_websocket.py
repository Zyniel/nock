"""Tests of spec 015, AC-3: four clients, 1,000 edits, one grid (WebSocket).

Python clients drive the real WebSocket, each with one reader thread. Spec 026
adds `grid_full_wrong` events, which take seqs: the random run fills FX-01, so
the test counts them. The shared setup is in `spec015_harness`.
"""

from __future__ import annotations

import contextlib
import random
import string
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Erase, ErrorCode, ErrorMessage, LetterChanged
from spec015_harness import (
    Edit,
    Peer,
    Triple,
    answer_of,
    errors_received,
    grid_from_text,
    grid_of_peer,
    join_peers,
    letter_cells,
    make_app,
    make_dist_dir,
    make_registry,
    send_edits_together,
    server_grid,
    settled_server_seq,
    wait_with_progress,
)

CLIENT_COUNT = 4
EDITS_PER_CLIENT = 250
ERASE_SHARE = 0.1


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
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


# ---- Helpers of the WebSocket tests ------------------------------------------


def seqs_after_snapshot(peer: Peer) -> list[int]:
    seqs: list[int] = []
    for message in peer.events():
        seq = getattr(message, "seq", None)
        assert isinstance(seq, int), message
        seqs.append(seq)
    return seqs


def random_edits(rng: random.Random, cells: list[tuple[int, int]]) -> list[Edit]:
    """EDITS_PER_CLIENT random edits: 90 % letters A to Z, 10 % erases."""
    edits: list[Edit] = []
    for _ in range(EDITS_PER_CLIENT):
        row, column = rng.choice(cells)
        if rng.random() < ERASE_SHARE:
            edits.append(Erase(row=row, column=column))
        else:
            letter = rng.choice(string.ascii_uppercase)
            edits.append(EditLetter(row=row, column=column, letter=letter))
    return edits


# ---- AC-3: four clients, 1,000 edits (WebSocket) -----------------------------


def test_ac3_four_clients_sending_1000_edits_end_with_the_same_grid(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    cells = letter_cells(fx01_grid)
    rng = random.Random(15)
    plans = [random_edits(rng, cells) for _ in range(CLIENT_COUNT)]
    names = ["Ana", "Bob", "Cleo", "Dan"]
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, names)
        send_edits_together(peers, plans)
        wait_with_progress(
            peers,
            lambda: all(len(peer.answers()) >= EDITS_PER_CLIENT for peer in peers),
            "every client's 250 answers",
        )
        final_seq = settled_server_seq(registry, room_code)
        wait_with_progress(
            peers,
            lambda: all(peer.last_seq() >= final_seq for peer in peers),
            "every client to receive the last seq",
        )

        expected_grid = server_grid(registry, room_code)
        for peer, plan in zip(peers, plans, strict=True):
            assert errors_received(peer) == []
            own_answers = peer.answers()
            assert len(own_answers) == EDITS_PER_CLIENT
            answered: list[Triple] = []
            for answer in own_answers:
                assert isinstance(answer, LetterChanged)
                assert answer.pencil is False
                answered.append((answer.row, answer.column, answer.letter))
            assert answered == [answer_of(edit) for edit in plan]
            assert grid_of_peer(peer) == expected_grid
            first_expected = peer.snapshot().seq + 1
            assert seqs_after_snapshot(peer) == list(
                range(first_expected, final_seq + 1)
            )

    # Spec 026: each `grid_full_wrong` and `grid_solved` takes one seq, and every
    # client got it. No edit was refused (no error above), so all 1000 were
    # accepted and each took one seq.
    full_wrong_count = len(peers[0].full_wrong_seqs())
    solved_count = len(peers[0].solved_seqs())
    accepted_edits = CLIENT_COUNT * EDITS_PER_CLIENT
    expected_seq = CLIENT_COUNT + accepted_edits + full_wrong_count + solved_count
    assert final_seq == expected_seq
    for peer in peers:
        assert peer.full_wrong_seqs() == peers[0].full_wrong_seqs()
        assert peer.solved_seqs() == peers[0].solved_seqs()
    filled = [value for value in expected_grid.values() if value[0] is not None]
    assert len(filled) > 0
    for letter, pencil, author in expected_grid.values():
        assert pencil is False
        assert (author is None) == (letter is None)


def test_ac3_every_edit_gets_one_letter_changed_in_order_even_when_nothing_changes(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    edits: list[Edit] = [
        EditLetter(row=1, column=0, letter="A"),
        EditLetter(row=1, column=0, letter="A"),
        Erase(row=1, column=1),
        Erase(row=1, column=0),
        Erase(row=1, column=0),
    ]
    with contextlib.ExitStack() as stack:
        (peer,) = join_peers(stack, client, room_code, ["Ana"])
        for edit in edits:
            peer.send(edit)
        peer.wait_until(lambda: len(peer.answers()) >= len(edits), "five answers")
        settled_server_seq(registry, room_code)

        answers = peer.answers()
        you = peer.you()
        assert answers == [
            LetterChanged(
                seq=index + 2,
                row=edit.row,
                column=edit.column,
                letter=answer_of(edit)[2],
                pencil=False,
                player_id=you,
            )
            for index, edit in enumerate(edits)
        ]
        assert seqs_after_snapshot(peer) == [2, 3, 4, 5, 6]
        final = grid_of_peer(peer)
        assert set(final.values()) == {(None, False, None)}
        assert final == server_grid(registry, room_code)
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 6


def test_ac3_an_edit_before_join_gets_not_joined_and_changes_nothing(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with client.websocket_connect(f"/api/rooms/{room_code}/ws") as websocket:
        peer = Peer(websocket)
        peer.send(EditLetter(row=1, column=0, letter="A"))
        peer.wait_until(lambda: len(peer.messages()) >= 1, "the answer to the edit")

        refusal = peer.messages()[0]
        assert isinstance(refusal, ErrorMessage)
        assert refusal.code is ErrorCode.NOT_JOINED
    state = registry.room_state(room_code)
    assert state is not None
    assert state.seq == 0
    assert state.players == ()
    assert [cell.letter for cell in state.cells] == [None] * len(state.cells)
