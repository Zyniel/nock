"""Tests of spec 037 (integrity), AC-3: the rate limit.

AC-3 checks the rate limit on `handle_message` and on the WebSocket with a fake
clock. The shared setup is in `spec037_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ClientMessage,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    LetterChanged,
    PencilEdit,
    SelectCell,
    Undo,
)
from nock.room import CellState, PlayerRecord, RoomConfig, RoomState, handle_message
from nock.server import create_app
from spec037_harness import (
    NOW,
    grid_from_text,
    join_peers,
    make_dist_dir,
    player_record,
    refusal_code,
    state_of,
    two_player_room,
)

RATE_LIMIT = 20

# ---- Fixtures -----------------------------------------------------------------


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
def clock_registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on the fake clock, with the default limit of 20 edits a second."""
    config = RoomConfig(silence_timeout_seconds=600)
    assert config.max_edits_per_second == RATE_LIMIT
    room_registry = RoomRegistry(clock=fake_clock, config=config)
    yield room_registry
    room_registry.close()


@pytest.fixture
def clock_room_code(clock_registry: RoomRegistry, fx01_grid: Grid) -> str:
    return clock_registry.register_room(fx01_grid)


@pytest.fixture
def clock_client(clock_registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- Room states for handle_message ------------------------------------------


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def locked_cell() -> CellState:
    """The cell (1, 2) holding `M`, locked."""
    return CellState(
        row=1,
        column=2,
        letter="M",
        author="p2",
        locked=True,
        revealed=False,
        changed_seq=2,
        changed_by="p2",
    )


def seen_at(state: RoomState, player_id: str, now: float) -> RoomState:
    """The state with only `last_seen_at` and `last_input_at` set to `now`.

    Spec 017: every message sets `last_seen_at`. Spec 013: every message except
    join and ping sets `last_input_at`. Both hold for a refused edit too.
    """
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == player_id:
            player = player.model_copy(
                update={"last_seen_at": now, "last_input_at": now}
            )
        players.append(player)
    return state.model_copy(update={"players": tuple(players)})


# ---- AC-3: the rate limit (Python) -------------------------------------------------


def burst_edits(
    state: RoomState,
    player_id: str,
    count: int,
    now: float,
    config: RoomConfig | None = None,
) -> RoomState:
    """Apply `count` accepted edits of `player_id` at `now`; return the new state."""
    for index in range(count):
        edit = EditLetter(row=1, column=index % 5, letter="A")
        if config is None:
            outcome = handle_message(state, player_id, edit, now)
        else:
            outcome = handle_message(state, player_id, edit, now, config)
        assert len(outcome.entries) == 1, f"edit {index + 1} was not accepted"
        state = outcome.state
    return state


def one_more_edit(
    state: RoomState, player_id: str, now: float
) -> tuple[RoomState, bool]:
    """Send one more edit; return the new state and whether it was accepted."""
    edit = EditLetter(row=2, column=1, letter="B")
    outcome = handle_message(state, player_id, edit, now)
    if len(outcome.entries) == 1:
        return outcome.state, True
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED
    assert outcome.state == seen_at(state, player_id, now)
    refused = player_record(outcome.state, player_id)
    assert refused.last_seen_at == now
    assert refused.last_input_at == now
    return outcome.state, False


def test_ac3_python_the_21st_edit_at_the_same_time_is_rate_limited(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    entries = []
    for index in range(21):
        edit = EditLetter(row=1, column=index % 5, letter="A")
        outcome = handle_message(state, "p1", edit, NOW)
        entries.extend(outcome.entries)
        if index < 20:
            assert outcome.reply == ()
            state = outcome.state

    assert len(entries) == 20
    for entry in entries:
        assert isinstance(entry.event, LetterChanged)
    assert state.seq == 22
    assert outcome.state == state
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


def test_ac3_python_the_edit_is_still_refused_half_a_second_later_and_accepted_at_1s(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    state, accepted_at_half = one_more_edit(state, "p1", NOW + 0.5)
    state, accepted_at_one = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_at_half is False
    assert accepted_at_one is True
    assert state.seq == 23


def test_ac3_python_the_window_slides_999_ms_refused_and_1s_accepted(
    fx01_grid: Grid,
) -> None:
    burst = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    _, accepted_at_999_ms = one_more_edit(burst, "p1", NOW + 0.999)
    _, accepted_at_1s = one_more_edit(burst, "p1", NOW + 1.0)

    assert accepted_at_999_ms is False
    assert accepted_at_1s is True


def test_ac3_python_the_window_slides_with_the_age_of_each_edit(
    fx01_grid: Grid,
) -> None:
    # 10 edits at NOW and 10 at NOW + 0.5: at NOW + 1.0 only the first 10 are gone.
    state = burst_edits(two_player_room(fx01_grid), "p1", 10, NOW)
    state = burst_edits(state, "p1", 10, NOW + 0.5)

    state, accepted_at_second = one_more_edit(state, "p1", NOW + 1.0)
    assert accepted_at_second is True
    for _ in range(9):
        state, accepted = one_more_edit(state, "p1", NOW + 1.0)
        assert accepted is True
    _, accepted_after_the_20th = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_after_the_20th is False


def test_ac3_python_refused_edits_do_not_extend_the_limit(fx01_grid: Grid) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    for offset in (0.2, 0.5, 0.9):
        state, accepted = one_more_edit(state, "p1", NOW + offset)
        assert accepted is False
    state, accepted_at_one_second = one_more_edit(state, "p1", NOW + 1.0)

    assert accepted_at_one_second is True


def test_ac3_python_a_second_player_is_not_affected_by_the_count_of_the_first(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    outcome = handle_message(state, "p2", EditLetter(row=2, column=1, letter="B"), NOW)

    assert outcome.reply == ()
    assert len(outcome.entries) == 1
    assert player_record(outcome.state, "p2").recent_edits == (NOW,)
    assert player_record(outcome.state, "p1").recent_edits == (NOW,) * 20


def test_ac3_python_an_accepted_edit_adds_now_to_the_recent_edits_of_its_player(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    assert player_record(state, "p1").recent_edits == ()

    state = burst_edits(state, "p1", 1, NOW)
    assert player_record(state, "p1").recent_edits == (NOW,)
    state = burst_edits(state, "p1", 1, NOW + 0.5)
    assert player_record(state, "p1").recent_edits == (NOW, NOW + 0.5)
    state = burst_edits(state, "p1", 1, NOW + 1.2)

    assert player_record(state, "p1").recent_edits == (NOW + 0.5, NOW + 1.2)
    assert player_record(state, "p2").recent_edits == ()


def test_ac3_python_a_refused_edit_leaves_the_recent_edits_as_they_were(
    fx01_grid: Grid,
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    refused, accepted = one_more_edit(state, "p1", NOW + 0.5)

    assert accepted is False
    assert player_record(refused, "p1").recent_edits == (NOW,) * 20


def test_ac3_python_erase_edits_count_with_letter_edits(fx01_grid: Grid) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 10, NOW)
    for _ in range(10):
        outcome = handle_message(state, "p1", Erase(row=1, column=0), NOW)
        assert len(outcome.entries) == 1
        state = outcome.state

    refused = handle_message(state, "p1", Erase(row=1, column=0), NOW)

    assert refused.state == state
    assert refusal_code(refused.reply) is ErrorCode.RATE_LIMITED


@pytest.mark.parametrize(
    "message",
    [
        PencilEdit(row=1, column=0, letter="A"),
        ConfirmPencil(row=1, column=0),
    ],
    ids=["pencil_edit", "confirm_pencil"],
)
def test_ac3_python_pencil_edits_and_confirmations_are_throttled_too(
    fx01_grid: Grid, message: ClientMessage
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 20, NOW)

    outcome = handle_message(state, "p1", message, NOW)

    assert outcome.state == state
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


@pytest.mark.parametrize(
    "message",
    [Undo(), SelectCell(row=1, column=0, direction=Direction.ACROSS)],
    ids=["undo", "select_cell"],
)
def test_ac3_python_undo_and_select_cell_are_not_counted(
    fx01_grid: Grid, message: ClientMessage
) -> None:
    state = burst_edits(two_player_room(fx01_grid), "p1", 19, NOW)

    in_between = handle_message(state, "p1", message, NOW)
    for reply in in_between.reply:
        if isinstance(reply, ErrorMessage):
            assert reply.code is not ErrorCode.RATE_LIMITED
    twentieth = handle_message(
        in_between.state, "p1", EditLetter(row=2, column=1, letter="B"), NOW
    )

    assert twentieth.reply == ()
    assert len(twentieth.entries) == 1
    assert len(player_record(twentieth.state, "p1").recent_edits) == 20


def test_ac3_python_the_limit_comes_from_the_config(fx01_grid: Grid) -> None:
    config = RoomConfig(max_edits_per_second=3)
    state = burst_edits(two_player_room(fx01_grid), "p1", 3, NOW, config)

    outcome = handle_message(
        state, "p1", EditLetter(row=2, column=1, letter="B"), NOW, config
    )

    assert outcome.state == state
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


def test_ac3_python_a_higher_limit_in_the_config_lets_more_edits_through(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1000)

    state = burst_edits(two_player_room(fx01_grid), "p1", 200, NOW, config)

    assert state.seq == 202
    assert len(player_record(state, "p1").recent_edits) == 200


def test_ac3_python_the_rate_limit_is_checked_before_the_locked_cell(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = with_cell(two_player_room(fx01_grid), locked_cell())
    locked_edit = EditLetter(row=1, column=2, letter="X")
    # Control: a player who has not edited yet is refused for the lock.
    fresh = handle_message(state, "p2", locked_edit, NOW, config)
    assert refusal_code(fresh.reply) is ErrorCode.CELL_LOCKED
    first = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )
    assert len(first.entries) == 1

    outcome = handle_message(first.state, "p1", locked_edit, NOW + 0.1, config)

    assert outcome.state == seen_at(first.state, "p1", NOW + 0.1)
    assert outcome.entries == ()
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


def test_ac3_python_the_rate_limit_is_checked_before_the_letter_cell(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(max_edits_per_second=1)
    state = two_player_room(fx01_grid)
    first = handle_message(
        state, "p1", EditLetter(row=1, column=0, letter="T"), NOW, config
    )

    outcome = handle_message(
        first.state, "p1", EditLetter(row=0, column=0, letter="T"), NOW + 0.1, config
    )

    assert outcome.state == seen_at(first.state, "p1", NOW + 0.1)
    assert refusal_code(outcome.reply) is ErrorCode.RATE_LIMITED


# ---- AC-3: the rate limit (WebSocket, fake clock) -----------------------------------


def burst_frame(index: int) -> EditLetter:
    return EditLetter(row=1, column=index % 5, letter=chr(ord("A") + index % 26))


def test_ac3_websocket_a_burst_of_25_edits_gets_20_events_and_5_rate_limited(
    fake_clock: FakeClock,
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    clock_room_code: str,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, clock_client, clock_room_code, ["Ana", "Bob"])
        seq_before = ana.last_seq()
        ana_start = len(ana.messages())
        bob_start = len(bob.messages())

        for index in range(25):
            ana.send(burst_frame(index))
        ana.wait_for_messages(ana_start + 25, "the 25 answers")
        bob.wait_for_letter_events(20, "the 20 events, on Bob")

        answers = ana.messages()[ana_start:]
        events = [
            answer for answer in answers[:20] if isinstance(answer, LetterChanged)
        ]
        refusals = [
            answer for answer in answers[20:] if isinstance(answer, ErrorMessage)
        ]
        assert len(events) == 20
        assert len(refusals) == 5
        assert [event.seq for event in events] == list(
            range(seq_before + 1, seq_before + 21)
        )
        for refusal in refusals:
            assert refusal.code is ErrorCode.RATE_LIMITED
        assert state_of(clock_registry, clock_room_code).seq == seq_before + 20
        assert bob.messages()[bob_start:] == events

        fake_clock.advance(1.0)
        ana.send(burst_frame(25))
        ana.wait_for_letter_events(21, "the edit after one second")
        bob.wait_for_letter_events(21, "the edit after one second, on Bob")

        newest = ana.letter_events()[20]
        assert newest.seq == seq_before + 21
        assert newest.letter == chr(ord("A") + 25)
        assert bob.letter_events()[20] == newest
        assert len(bob.letter_events()) == 21
        assert len(ana.errors()) == 5
        assert bob.errors() == []


def test_ac3_websocket_a_throttled_client_stays_connected_and_others_are_free(
    clock_registry: RoomRegistry,
    clock_client: TestClient,
    clock_room_code: str,
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, clock_client, clock_room_code, ["Ana", "Bob"])
        ana_start = len(ana.messages())
        for index in range(21):
            ana.send(burst_frame(index))
        ana.wait_for_messages(ana_start + 21, "the 21 answers")
        assert len(ana.errors()) == 1

        bob.send(EditLetter(row=2, column=1, letter="V"))
        bob.wait_for_letter_events(21, "the edit of Bob, after the 20 of Ana")

        bobs_event = bob.letter_events()[20]
        assert bobs_event.player_id == bob.you()
        assert bobs_event.seq == 2 + 20 + 1
        assert bob.errors() == []
        assert len(ana.errors()) == 1
        assert state_of(clock_registry, clock_room_code).seq == 23
