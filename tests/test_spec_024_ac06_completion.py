"""Tests of spec 024, AC-6: a reveal that fills the grid completes it.

The rule on `handle_message` (spec 026's completion entry after the last revealed
letter) and the real WebSocket. The shared setup is in `spec024_harness`.
"""

from __future__ import annotations

import contextlib
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
    EditLetter,
    ErrorCode,
    GridFullWrong,
    GridSolved,
    Reveal,
    RevealBudget,
    RevealResult,
)
from nock.room import RoomState
from nock.server import create_app
from spec024_harness import (
    FIRST_17,
    MIME,
    MIME_CELLS,
    NOW,
    ROW_MAJOR,
    SOLUTION,
    RevealTargetArg,
    accepted_reveal,
    events_of,
    full17,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    refusal_code,
    reveal,
    two_player_room,
    write,
)

LAST = CellTarget(row=4, column=4)
SOLVE_AT = NOW + 754.0

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
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-6, rule ----


def last_letter_result() -> RevealResult:
    return RevealResult(
        seq=20,
        player_id="p2",
        target=LAST,
        reveal_budget=RevealBudget(letters=4, words=1),
    )


def test_ac6_revealing_the_last_cell_solves_the_grid(fx01_grid: Grid) -> None:
    outcome = accepted_reveal(full17(fx01_grid), LAST, "p2", SOLVE_AT)

    assert events_of(outcome) == [
        last_letter_result(),
        CellLocked(seq=21, row=4, column=4, letter="T", revealed=True),
        GridSolved(seq=22, elapsed_ms=754000),
    ]
    assert outcome.state.solved is True
    assert outcome.state.seq == 22


def test_ac6_revealing_the_last_cell_of_a_wrong_grid_gives_grid_full_wrong(
    fx01_grid: Grid,
) -> None:
    state = full17(fx01_grid, wrong_at=(1, 1))

    outcome = accepted_reveal(state, LAST, "p2", SOLVE_AT)

    assert events_of(outcome) == [
        last_letter_result(),
        CellLocked(seq=21, row=4, column=4, letter="T", revealed=True),
        GridFullWrong(seq=22),
    ]
    assert outcome.state.solved is False


def all_but_mime(grid: Grid) -> RoomState:
    """A FX-01 room where `p1` wrote every right letter but the four of MIME."""
    state = two_player_room(grid)
    for row, column in ROW_MAJOR:
        if (row, column) in MIME_CELLS:
            continue
        state = write(state, "p1", row, column, SOLUTION[(row, column)]).state
    assert state.seq == 16
    return state


def test_ac6_revealing_the_last_word_solves_the_grid(fx01_grid: Grid) -> None:
    outcome = accepted_reveal(all_but_mime(fx01_grid), MIME, "p1", NOW + 100.0)

    assert events_of(outcome) == [
        RevealResult(
            seq=17,
            player_id="p1",
            target=MIME,
            reveal_budget=RevealBudget(letters=5, words=0),
        ),
        CellLocked(seq=18, row=1, column=2, letter="M", revealed=True),
        CellLocked(seq=19, row=2, column=2, letter="I", revealed=True),
        CellLocked(seq=20, row=3, column=2, letter="M", revealed=True),
        CellLocked(seq=21, row=4, column=2, letter="E", revealed=True),
        GridSolved(seq=22, elapsed_ms=100000),
    ]
    assert outcome.state.solved is True


@pytest.mark.parametrize(
    "target",
    [LAST, CellTarget(row=1, column=1), MIME, CellTarget(row=0, column=0)],
    ids=["revealed-cell", "letter", "word", "clue-cell"],
)
def test_ac6_a_reveal_on_the_grid_solved_by_a_reveal_is_refused(
    fx01_grid: Grid, target: RevealTargetArg
) -> None:
    solved = accepted_reveal(full17(fx01_grid), LAST, "p2", SOLVE_AT).state
    assert solved.solved is True

    outcome = reveal(solved, target, "p1", SOLVE_AT + 1)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == solved.seq
    assert outcome.state.reveal_budget == solved.reveal_budget


# ---- AC-6, WebSocket ----


def test_ac6_websocket_a_reveal_of_the_last_cell_ends_the_game_for_everyone(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _ = peers
        for row, column in FIRST_17[:9]:
            letter = SOLUTION[(row, column)]
            ana.send(EditLetter(row=row, column=column, letter=letter))
        for peer in peers:
            peer.wait_for_seq(3 + 9, f"Ana's 9 letters on {peer.name}")
        for row, column in FIRST_17[9:]:
            letter = SOLUTION[(row, column)]
            bob.send(EditLetter(row=row, column=column, letter=letter))
        for peer in peers:
            peer.wait_for_seq(3 + 17, f"Bob's 8 letters on {peer.name}")

        bob.send(Reveal(target=LAST))

        for peer in peers:
            peer.wait_for_seq(23, f"the end of the game on {peer.name}")
            assert peer.errors() == []
            tail = peer.messages()[-3:]
            assert [message.type for message in tail] == [
                "reveal_result",
                "cell_locked",
                "grid_solved",
            ]
            assert [getattr(message, "seq", None) for message in tail] == [21, 22, 23]
            assert tail[1] == CellLocked(
                seq=22, row=4, column=4, letter="T", revealed=True
            )
