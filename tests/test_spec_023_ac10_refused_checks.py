"""Tests of spec 023, AC-10: a check that cannot apply is refused and changes
nothing.

The rule on `handle_message` and the real WebSocket. Spec 026 adds the refusal
of a check on a solved grid, first in the order of refusals (before
`help_disabled`). The shared setup is in `spec023_harness`.
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
    ChangeSettings,
    Check,
    CheckResult,
    CheckTarget,
    ErrorCode,
    ErrorMessage,
    GridTarget,
    HelpMode,
    RevealBudget,
    ServerMessage,
    WordTarget,
)
from nock.room import (
    PlayerRecord,
    RoomState,
    handle_message,
)
from nock.server import create_app
from spec023_harness import (
    CHECK_NOW,
    NOW,
    TAMIS,
    check,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    refs,
    s1_room,
)

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


def seen_at(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state with only `last_seen_at` and `last_input_at` of one player set."""
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == player_id:
            player = player.model_copy(
                update={"last_seen_at": now, "last_input_at": now}
            )
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


def refusal_code(reply: tuple[ServerMessage, ...]) -> ErrorCode:
    """The code of the single error in `reply`."""
    assert len(reply) == 1
    refusal = reply[0]
    assert isinstance(refusal, ErrorMessage)
    return refusal.code


def host_sets(state: RoomState, help_mode: HelpMode) -> RoomState:
    """The room after `p1` (host) changed the help mode."""
    change = ChangeSettings(
        help_mode=help_mode, reveal_budget=RevealBudget(letters=5, words=1)
    )
    outcome = handle_message(state, "p1", change, NOW)
    assert outcome.reply == ()
    return outcome.state


# ---- AC-10: a check that cannot apply is refused and changes nothing ----


def test_ac10_help_mode_none_refuses_every_kind_of_check(fx01_grid: Grid) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.NONE)
    assert state.seq == 9
    expected_state = seen_at(state, "p1", CHECK_NOW)

    for target in (TAMIS, CellTarget(row=1, column=0), GridTarget()):
        outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

        assert refusal_code(outcome.reply) is ErrorCode.HELP_DISABLED
        assert outcome.entries == ()
        assert outcome.state == expected_state
        assert outcome.state.seq == 9


def test_ac10_help_mode_none_is_answered_before_the_target_is_looked_at(
    fx01_grid: Grid,
) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.NONE)
    bad_targets = (
        CellTarget(row=0, column=0),
        WordTarget(row=9, column=9, clue_index=0),
    )

    for target in bad_targets:
        outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

        assert refusal_code(outcome.reply) is ErrorCode.HELP_DISABLED


@pytest.mark.parametrize(
    "target",
    [CellTarget(row=0, column=0), CellTarget(row=5, column=0)],
    ids=["clue-cell", "outside-the-grid"],
)
def test_ac10_a_letter_target_off_a_letter_cell_is_not_a_letter_cell(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p1", CHECK_NOW)
    assert outcome.state.seq == 8


@pytest.mark.parametrize(
    "target",
    [
        WordTarget(row=1, column=0, clue_index=0),
        WordTarget(row=0, column=2, clue_index=1),
        WordTarget(row=9, column=9, clue_index=0),
    ],
    ids=["letter-cell", "clue-index-out-of-range", "outside-the-grid"],
)
def test_ac10_a_word_target_that_names_no_clue_is_invalid_target(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p1", CHECK_NOW)
    assert outcome.state.seq == 8


def test_ac10_a_refusal_is_for_the_sender_only(fx01_grid: Grid) -> None:
    state = s1_room(fx01_grid)

    outcome = handle_message(
        state, "p1", Check(target=CellTarget(row=0, column=0)), CHECK_NOW
    )

    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac10_help_mode_vote_acts_as_free(fx01_grid: Grid) -> None:
    state = host_sets(s1_room(fx01_grid), HelpMode.VOTE)

    events = check(state, TAMIS)

    assert events == [
        CheckResult(
            seq=10,
            player_id="p1",
            target=TAMIS,
            correct=refs((1, 0), (1, 3), (1, 4)),
            wrong=refs((1, 1)),
        ),
        CellLocked(seq=11, row=1, column=0, letter="T", revealed=False),
        CellLocked(seq=12, row=1, column=3, letter="I", revealed=False),
        CellLocked(seq=13, row=1, column=4, letter="S", revealed=False),
    ]


def test_ac10_websocket_a_refused_check_reaches_only_its_sender(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        ana.send(Check(target=CellTarget(row=0, column=0)))
        ana.wait_until(lambda: len(ana.errors()) == 1, "the refusal")
        bob.send(Check(target=GridTarget()))
        bob.wait_for_seq(3, "the empty check on Bob")

        assert [error.code for error in ana.errors()] == [ErrorCode.NOT_A_LETTER_CELL]
        assert bob.errors() == []
        assert len(bob.check_results()) == 1
        assert bob.check_results()[0].seq == 3


# ---- Spec 026: a check on a solved grid is refused ----


def solved_room(grid: Grid) -> RoomState:
    """`S1` with the `solved` flag set (seq 8)."""
    return s1_room(grid).model_copy(update={"solved": True})


@pytest.mark.parametrize(
    "target",
    [TAMIS, CellTarget(row=1, column=0), GridTarget()],
    ids=["word", "letter", "grid"],
)
def test_ac10_a_solved_grid_refuses_every_kind_of_check(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = solved_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 8
    assert outcome.state.cells == state.cells
    assert outcome.to_others == ()


@pytest.mark.parametrize(
    "target",
    [CellTarget(row=0, column=0), WordTarget(row=9, column=9, clue_index=0)],
    ids=["not-a-letter-cell", "invalid-target"],
)
def test_ac10_grid_solved_is_answered_before_the_target_is_looked_at(
    fx01_grid: Grid, target: CheckTarget
) -> None:
    state = solved_room(fx01_grid)

    outcome = handle_message(state, "p1", Check(target=target), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED


def test_ac10_grid_solved_is_answered_before_help_disabled(fx01_grid: Grid) -> None:
    state = host_sets(solved_room(fx01_grid), HelpMode.NONE)

    outcome = handle_message(state, "p1", Check(target=GridTarget()), CHECK_NOW)

    assert refusal_code(outcome.reply) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
