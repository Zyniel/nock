"""Tests of spec 024, AC-4: a reveal that cannot apply is refused and changes
nothing.

The rule on `handle_message`, in the order of refusals (solved, help mode `none`,
target, nothing left to reveal, budget), and the real WebSocket. The edge cases
"Two reveals of one cell at once" and "Locked cells in a word" are tested here.
The shared setup is in `spec024_harness`.
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
    CellTarget,
    ErrorCode,
    HelpMode,
    Pong,
    Reveal,
    RevealBudget,
    WordTarget,
)
from nock.room import Outcome, RoomState
from nock.server import create_app
from spec024_harness import (
    LAST_CELL,
    MIME,
    NOW,
    RevealTargetArg,
    accepted_reveal,
    check_cell,
    full17,
    grid_from_text,
    host_changes,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    ping_and_wait,
    r1_room,
    refusal_code,
    reveal,
    seen_at,
    write,
)

LATER = NOW + 10.0

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


# ---- Helpers of the refusal tests ----


def refuse(state: RoomState, target: RevealTargetArg, player_id: str = "p1") -> Outcome:
    """Send a reveal at LATER and check that it changed nothing; return the outcome.

    A refusal returns the state it was given apart from the sender's
    `last_seen_at` and `last_input_at`, with no entry and one `ErrorMessage`.
    """
    outcome = reveal(state, target, player_id, LATER)
    assert len(outcome.reply) == 1, outcome.reply
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, player_id, LATER)
    assert outcome.state.seq == state.seq
    assert outcome.state.reveal_budget == state.reveal_budget
    return outcome


NAMES_NOTHING: list[RevealTargetArg] = [
    CellTarget(row=0, column=0),
    WordTarget(row=9, column=9, clue_index=0),
]
NAMES_SOMETHING: list[RevealTargetArg] = [CellTarget(row=1, column=1), MIME]


def none_room(grid: Grid) -> RoomState:
    """`R1` after the host set help mode `none` (seq 6)."""
    state = host_changes(r1_room(grid), HelpMode.NONE, 5, 1)
    assert state.seq == 6
    return state


def solved_room(grid: Grid) -> RoomState:
    """`FULL17` plus `T` at (4, 4) by `p2`: the grid is solved."""
    row, column = LAST_CELL
    state = write(full17(grid), "p2", row, column, "T", NOW + 754.0).state
    assert state.solved is True
    return state


# ---- AC-4, rule: help mode none ----


@pytest.mark.parametrize(
    "target",
    [*NAMES_SOMETHING, *NAMES_NOTHING],
    ids=["letter", "word", "clue-cell", "outside-the-grid"],
)
def test_ac4_help_mode_none_refuses_every_reveal_with_help_disabled(
    fx01_grid: Grid, target: RevealTargetArg
) -> None:
    outcome = refuse(none_room(fx01_grid), target)

    assert refusal_code(outcome) is ErrorCode.HELP_DISABLED


# ---- AC-4, rule: a target that names nothing ----


@pytest.mark.parametrize(
    "target",
    [CellTarget(row=0, column=0), CellTarget(row=5, column=0)],
    ids=["clue-cell", "outside-the-grid"],
)
def test_ac4_a_letter_target_off_a_letter_cell_is_not_a_letter_cell(
    fx01_grid: Grid, target: RevealTargetArg
) -> None:
    outcome = refuse(r1_room(fx01_grid), target)

    assert refusal_code(outcome) is ErrorCode.NOT_A_LETTER_CELL


@pytest.mark.parametrize(
    "target",
    [
        WordTarget(row=1, column=0, clue_index=0),
        WordTarget(row=0, column=2, clue_index=1),
        WordTarget(row=9, column=9, clue_index=0),
    ],
    ids=["letter-cell", "one-clue-only", "outside-the-grid"],
)
def test_ac4_a_word_target_that_names_no_clue_is_invalid_target(
    fx01_grid: Grid, target: RevealTargetArg
) -> None:
    outcome = refuse(r1_room(fx01_grid), target)

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET


# ---- AC-4, rule: nothing left to reveal ----


def test_ac4_revealing_a_revealed_cell_again_is_invalid_target(
    fx01_grid: Grid,
) -> None:
    state = accepted_reveal(r1_room(fx01_grid), CellTarget(row=1, column=1)).state
    assert state.seq == 7
    assert state.reveal_budget == RevealBudget(letters=4, words=1)

    outcome = refuse(state, CellTarget(row=1, column=1))

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET


def test_ac4_revealing_a_word_whose_cells_are_all_locked_is_invalid_target(
    fx01_grid: Grid,
) -> None:
    raised = host_changes(r1_room(fx01_grid), HelpMode.FREE, 5, 2)
    state = accepted_reveal(raised, MIME).state
    assert state.reveal_budget == RevealBudget(letters=5, words=1)

    outcome = refuse(state, MIME)

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET


# ---- AC-4, rule: the budget, checked after the target ----


def no_letter_allowance(grid: Grid) -> RoomState:
    """`R1` after the host set the allowance to 0 letters and 1 word."""
    state = host_changes(r1_room(grid), HelpMode.FREE, 0, 1)
    assert state.reveal_budget == RevealBudget(letters=0, words=1)
    return state


def test_ac4_a_letter_reveal_with_no_letter_left_is_budget_exhausted(
    fx01_grid: Grid,
) -> None:
    outcome = refuse(no_letter_allowance(fx01_grid), CellTarget(row=1, column=1))

    assert refusal_code(outcome) is ErrorCode.BUDGET_EXHAUSTED


def test_ac4_a_clue_cell_is_still_not_a_letter_cell_with_no_letter_left(
    fx01_grid: Grid,
) -> None:
    outcome = refuse(no_letter_allowance(fx01_grid), CellTarget(row=0, column=0))

    assert refusal_code(outcome) is ErrorCode.NOT_A_LETTER_CELL


def test_ac4_a_locked_cell_is_still_invalid_target_with_no_letter_left(
    fx01_grid: Grid,
) -> None:
    state = check_cell(no_letter_allowance(fx01_grid), 1, 0)

    outcome = refuse(state, CellTarget(row=1, column=0))

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET


# ---- AC-4, rule: the solved grid comes first ----


@pytest.mark.parametrize(
    "target",
    [*NAMES_SOMETHING, *NAMES_NOTHING],
    ids=["letter", "word", "clue-cell", "outside-the-grid"],
)
def test_ac4_a_solved_grid_refuses_every_reveal_with_grid_solved(
    fx01_grid: Grid, target: RevealTargetArg
) -> None:
    outcome = refuse(solved_room(fx01_grid), target)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED


def test_ac4_grid_solved_is_answered_before_help_disabled(fx01_grid: Grid) -> None:
    state = host_changes(solved_room(fx01_grid), HelpMode.NONE, 5, 1)

    outcome = refuse(state, CellTarget(row=1, column=1))

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED


def test_ac4_a_refusal_is_for_the_sender_only(fx01_grid: Grid) -> None:
    outcome = refuse(r1_room(fx01_grid), CellTarget(row=0, column=0), "p2")

    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


# ---- AC-4, WebSocket ----


def test_ac4_websocket_a_refused_reveal_reaches_its_sender_only(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        seen_by_bob = len(bob.messages())

        ana.send(Reveal(target=CellTarget(row=0, column=0)))
        ana.wait_until(lambda: len(ana.errors()) == 1, "the refusal on Ana")
        ping_and_wait(bob)

        assert [error.code for error in ana.errors()] == [ErrorCode.NOT_A_LETTER_CELL]
        assert ana.reveal_results() == []
        assert bob.messages()[seen_by_bob:] == [Pong()]
