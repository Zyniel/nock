"""Tests of spec 020, AC-4: `pencil_edit` and `confirm_pencil` go through the edit
checks of spec 015 in their order, and a refused one is not counted.

The checks (spec 037 rate limit, not a letter cell, locked cell, spec 017's stale
rule, solved grid) and their order on `handle_message`, the wake-up of an idle
sender whose message is refused (spec 013's entry first, then the refusal; the
lead's note of 2026-10-15), the shared rate window (spec 037 AC-3), the stale
rule's own-change exception for the two messages (spec 017 left their forms to
this spec), and the WebSocket answer to a refused pencil edit. The shared setup is
in `spec020_harness` and `spec024_harness`.
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
    EditLetter,
    ErrorCode,
    ErrorMessage,
    LetterChanged,
    PlayerState,
    PlayerStateChanged,
    Pong,
)
from nock.room import (
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    handle_message,
    tick,
)
from nock.server import create_app
from spec020_harness import (
    RULE_CONFIG,
    SOLVED_AT,
    accepted_confirm,
    accepted_pencil,
    cell_values,
    confirm,
    locked_room,
    pencil,
    solved_room,
)
from spec024_harness import (
    NOW,
    events_of,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    ping_and_wait,
    player_record,
    refusal_code,
    seen_at,
    two_player_room,
    write,
)

KINDS = ["pencil_edit", "confirm_pencil"]
NOT_LETTER_CELLS = [(0, 0), (5, 0)]
AFTER_SOLVED = SOLVED_AT + 1.0
IDLE_AT = NOW + 120.0  # two minutes without input make a player idle (spec 013)
WOKEN_AT = NOW + 130.0
QUIET = RoomConfig(silence_timeout_seconds=3600)  # nobody is silent at the tick
CLUE_CELL_PENCIL_JSON = (
    '{"type": "pencil_edit", "row": 0, "column": 0, "letter": "T", "base_seq": null}'
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


# ---- Helpers ----


def send_kind(
    kind: str,
    state: RoomState,
    row: int,
    column: int,
    *,
    player_id: str = "p1",
    now: float = NOW,
    base_seq: int | None = None,
    config: RoomConfig = RULE_CONFIG,
) -> Outcome:
    """Send a `PencilEdit` (letter `X`) or a `ConfirmPencil` at a cell."""
    if kind == "pencil_edit":
        return pencil(
            state,
            player_id,
            row,
            column,
            "X",
            now=now,
            base_seq=base_seq,
            config=config,
        )
    return confirm(
        state, player_id, row, column, now=now, base_seq=base_seq, config=config
    )


def assert_refused(
    before: RoomState,
    outcome: Outcome,
    code: ErrorCode,
    player_id: str = "p1",
    now: float = NOW,
) -> None:
    """One error with `code`, no entry, and the state as it was.

    Only `last_seen_at` and `last_input_at` of the sender may change, so `seq`
    and the sender's `recent_edits` are unchanged: the refusal is not counted.
    """
    assert refusal_code(outcome) == code
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, player_id, now)


def idle_locked_room(grid: Grid) -> RoomState:
    """`locked_room` after two minutes without input: both players idle (seq 7)."""
    idle = tick(locked_room(grid), IDLE_AT, QUIET).state
    assert idle.seq == 7
    assert player_record(idle, "p1").state is PlayerState.IDLE
    assert player_record(idle, "p2").state is PlayerState.IDLE
    return idle


def woken(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state after an idle player's input at `now` that was refused.

    Spec 013 wakes the player before the message's own effect: they become active
    with `last_seen_at` and `last_input_at` at `now`, and the wake entry raises
    the seq by one. Nothing else changes, `recent_edits` included.
    """
    seen = seen_at(state, player_id, now)
    players: list[PlayerRecord] = []
    for player in seen.players:
        if player.player_id == player_id:
            player = player.model_copy(update={"state": PlayerState.ACTIVE})
        players.append(player)
    return seen.model_copy(update={"players": tuple(players), "seq": state.seq + 1})


# ---- AC-4: each check ----


@pytest.mark.parametrize(("row", "column"), NOT_LETTER_CELLS)
@pytest.mark.parametrize("kind", KINDS)
def test_ac4_a_cell_that_is_not_a_letter_cell_is_refused_not_a_letter_cell(
    fx01_grid: Grid, kind: str, row: int, column: int
) -> None:
    before = two_player_room(fx01_grid)

    outcome = send_kind(kind, before, row, column)

    assert_refused(before, outcome, ErrorCode.NOT_A_LETTER_CELL)


@pytest.mark.parametrize("kind", KINDS)
def test_ac4_a_locked_cell_is_refused_cell_locked(fx01_grid: Grid, kind: str) -> None:
    before = locked_room(fx01_grid)

    outcome = send_kind(kind, before, 1, 0)

    assert_refused(before, outcome, ErrorCode.CELL_LOCKED)


def test_ac4_a_pencil_edit_older_than_another_players_change_is_refused_stale(
    fx01_grid: Grid,
) -> None:
    before = write(two_player_room(fx01_grid), "p2", 1, 1, "B").state

    outcome = pencil(before, "p1", 1, 1, "A", base_seq=2)

    assert_refused(before, outcome, ErrorCode.STALE_EDIT)


def test_ac4_a_confirmation_older_than_another_players_change_is_refused_stale(
    fx01_grid: Grid,
) -> None:
    before = accepted_pencil(two_player_room(fx01_grid), "p2", 1, 1, "B").state

    outcome = confirm(before, "p1", 1, 1, base_seq=2)

    assert_refused(before, outcome, ErrorCode.STALE_EDIT)


def test_ac4_a_pencil_edit_whose_base_seq_saw_the_change_is_accepted(
    fx01_grid: Grid,
) -> None:
    before = write(two_player_room(fx01_grid), "p2", 1, 1, "B").state

    outcome = pencil(before, "p1", 1, 1, "A", base_seq=3)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=4, row=1, column=1, letter="A", pencil=True, player_id="p1")
    ]


def test_ac4_my_own_later_change_never_makes_my_pencil_edit_stale(
    fx01_grid: Grid,
) -> None:
    before = write(two_player_room(fx01_grid), "p1", 1, 1, "B").state

    outcome = pencil(before, "p1", 1, 1, "A", base_seq=2)

    assert outcome.reply == ()
    assert cell_values(outcome.state)[(1, 1)] == ("A", True, "p1")


def test_ac4_my_own_later_pencil_letter_never_makes_my_confirmation_stale(
    fx01_grid: Grid,
) -> None:
    before = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 1, "B").state

    outcome = confirm(before, "p1", 1, 1, base_seq=2)

    assert outcome.reply == ()
    assert cell_values(outcome.state)[(1, 1)] == ("B", False, "p1")


@pytest.mark.parametrize("kind", KINDS)
def test_ac4_on_a_solved_grid_both_are_refused_grid_solved(
    fx01_grid: Grid, kind: str
) -> None:
    before = solved_room(fx01_grid)

    outcome = send_kind(kind, before, 1, 0, now=AFTER_SOLVED)

    assert_refused(before, outcome, ErrorCode.GRID_SOLVED, now=AFTER_SOLVED)


# ---- AC-4: a refusal still wakes an idle sender (spec 013) ----


def test_ac4_a_refused_pencil_edit_from_an_idle_sender_still_wakes_them(
    fx01_grid: Grid,
) -> None:
    idle = idle_locked_room(fx01_grid)

    outcome = pencil(idle, "p1", 1, 0, "X", now=WOKEN_AT)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=8, player_id="p1", state=PlayerState.ACTIVE)
    ]
    assert refusal_code(outcome) == ErrorCode.CELL_LOCKED
    assert outcome.state.seq == 8
    assert outcome.state == woken(idle, "p1", WOKEN_AT)


def test_ac4_a_refused_confirmation_from_an_idle_sender_still_wakes_them(
    fx01_grid: Grid,
) -> None:
    # (1, 1) is empty: it holds no pencil letter to confirm.
    idle = idle_locked_room(fx01_grid)

    outcome = confirm(idle, "p2", 1, 1, now=WOKEN_AT)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=8, player_id="p2", state=PlayerState.ACTIVE)
    ]
    assert refusal_code(outcome) == ErrorCode.STALE_EDIT
    assert outcome.state.seq == 8
    assert outcome.state == woken(idle, "p2", WOKEN_AT)


# ---- AC-4: the order of the checks ----


def test_ac4_order_the_rate_limit_comes_before_the_lock(fx01_grid: Grid) -> None:
    # `p1` wrote (1, 0) at NOW, so one edit is inside the window at NOW + 0.5.
    before = locked_room(fx01_grid)
    one_a_second = RoomConfig(max_edits_per_second=1)
    later = NOW + 0.5

    outcome = pencil(before, "p1", 1, 0, "X", now=later, config=one_a_second)

    assert_refused(before, outcome, ErrorCode.RATE_LIMITED, now=later)


def test_ac4_order_a_clue_cell_comes_before_the_solved_grid(fx01_grid: Grid) -> None:
    before = solved_room(fx01_grid)

    outcome = pencil(before, "p1", 0, 0, "X", now=AFTER_SOLVED)

    assert_refused(before, outcome, ErrorCode.NOT_A_LETTER_CELL, now=AFTER_SOLVED)


def test_ac4_order_the_lock_comes_before_the_stale_rule(fx01_grid: Grid) -> None:
    # The lock changed (1, 0) at seq 5 with no `changed_by`: base_seq 2 is old.
    before = locked_room(fx01_grid)

    outcome = confirm(before, "p1", 1, 0, base_seq=2)

    assert_refused(before, outcome, ErrorCode.CELL_LOCKED)


def test_ac4_order_the_stale_rule_comes_before_the_solved_grid(
    fx01_grid: Grid,
) -> None:
    # `p1` wrote (1, 0) at seq 3, after p2's base_seq 2.
    before = solved_room(fx01_grid)

    outcome = confirm(before, "p2", 1, 0, base_seq=2, now=AFTER_SOLVED)

    assert_refused(
        before, outcome, ErrorCode.STALE_EDIT, player_id="p2", now=AFTER_SOLVED
    )


def test_ac4_order_the_solved_grid_comes_before_the_missing_pencil_letter(
    fx01_grid: Grid,
) -> None:
    # (1, 0) holds a normal letter: without the solved grid it would be stale_edit.
    before = solved_room(fx01_grid)

    outcome = confirm(before, "p1", 1, 0, now=AFTER_SOLVED)

    assert_refused(before, outcome, ErrorCode.GRID_SOLVED, now=AFTER_SOLVED)


# ---- AC-4: the rate window (spec 037 AC-3) ----


def test_ac4_accepted_pencil_edits_and_confirmations_are_counted(
    fx01_grid: Grid,
) -> None:
    first = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T", now=NOW)
    assert player_record(first.state, "p1").recent_edits == (NOW,)

    second = accepted_confirm(first.state, "p1", 1, 0, now=NOW + 0.25)

    assert player_record(second.state, "p1").recent_edits == (NOW, NOW + 0.25)


def test_ac4_twenty_one_pencil_edits_at_one_time_give_twenty_letters_and_a_refusal(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    letter_count = 0
    codes: list[ErrorCode] = []
    for _ in range(21):
        outcome = pencil(state, "p1", 1, 0, "T")
        for event in events_of(outcome):
            if isinstance(event, LetterChanged):
                letter_count += 1
        for message in outcome.reply:
            if isinstance(message, ErrorMessage):
                codes.append(message.code)
        state = outcome.state

    assert letter_count == 20
    assert codes == [ErrorCode.RATE_LIMITED]
    assert state.seq == 22


def test_ac4_pencil_edits_share_the_rate_window_with_edit_letter(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for _ in range(10):
        state = write(state, "p1", 1, 0, "T").state
    for _ in range(10):
        state = accepted_pencil(state, "p1", 1, 0, "T").state

    pencil_refusal = pencil(state, "p1", 1, 0, "T")
    edit_refusal = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW
    )

    assert_refused(state, pencil_refusal, ErrorCode.RATE_LIMITED)
    assert_refused(state, edit_refusal, ErrorCode.RATE_LIMITED)


def test_ac4_confirmations_count_in_the_same_rate_window(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    for _ in range(9):
        state = accepted_pencil(state, "p1", 1, 0, "T").state
        state = accepted_confirm(state, "p1", 1, 0).state
    state = accepted_pencil(state, "p1", 1, 0, "T").state
    state = accepted_pencil(state, "p1", 1, 0, "A").state

    outcome = confirm(state, "p1", 1, 0)

    assert_refused(state, outcome, ErrorCode.RATE_LIMITED)


# ---- AC-4, WebSocket ----


def test_ac4_websocket_a_pencil_edit_on_a_clue_cell_is_answered_to_its_sender_only(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob_seen_before = len(bob.messages())

        ana.send_text(CLUE_CELL_PENCIL_JSON)
        ana.wait_until(lambda: len(ana.errors()) >= 1, "the refusal on Ana")
        ping_and_wait(ana)
        ping_and_wait(bob)

        ana_codes = [error.code for error in ana.errors()]
        ana_seq = ana.last_seq()
        bob_new = bob.messages()[bob_seen_before:]

    assert ana_codes == [ErrorCode.NOT_A_LETTER_CELL]
    assert ana_seq == 2
    bob_not_pongs = [message for message in bob_new if not isinstance(message, Pong)]
    assert bob_not_pongs == []
