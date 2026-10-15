"""Tests of spec 026, AC-8 and AC-9: the 18 letters and the reload.

Both check the rule on `handle_message`, `replay` and `RoomStore`. The shared setup
is in `spec026_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import (
    EditLetter,
    ErrorCode,
    GridFullWrong,
    GridSolved,
    Join,
    LetterChanged,
)
from nock.room import LogEntry, RoomState, handle_message, join_room, new_room, replay
from nock.store import RoomStore
from spec026_harness import (
    FIRST_TOKEN,
    LAST_CELL,
    NOW,
    ROOM_CODE,
    ROW_MAJOR,
    SECOND_TOKEN,
    SOLUTION,
    Cell,
    events_of,
    full17,
    grid_from_text,
    refusal_code,
    two_player_room,
    write,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-8: the 18 letters of FX-01 ----


def write_all_in_row_major(
    state: RoomState, replaced: dict[Cell, str]
) -> tuple[RoomState, list[list[object]]]:
    """`p1` writes the 18 letters (with `replaced`); return the events by edit."""
    events_by_edit: list[list[object]] = []
    for position in ROW_MAJOR:
        letter = replaced.get(position, SOLUTION[position])
        outcome = write(state, "p1", position, letter)
        events_by_edit.append(events_of(outcome))
        state = outcome.state
    return state, events_by_edit


def test_ac8_the_18_solution_letters_produce_exactly_one_grid_solved(
    fx01_grid: Grid,
) -> None:
    state, events_by_edit = write_all_in_row_major(two_player_room(fx01_grid), {})

    for events in events_by_edit[:-1]:
        assert len(events) == 1
        assert isinstance(events[0], LetterChanged)
    last = events_by_edit[-1]
    assert len(last) == 2
    assert isinstance(last[0], LetterChanged)
    assert isinstance(last[1], GridSolved)
    assert last[1].seq == last[0].seq + 1
    assert state.solved is True


def test_ac8_a_wrong_letter_at_1_2_gives_grid_full_wrong_then_the_fix_solves(
    fx01_grid: Grid,
) -> None:
    state, events_by_edit = write_all_in_row_major(
        two_player_room(fx01_grid), {(1, 2): "N"}
    )

    last = events_by_edit[-1]
    assert len(last) == 2
    assert isinstance(last[1], GridFullWrong)
    for events in events_by_edit:
        for event in events:
            assert not isinstance(event, GridSolved)
    assert state.solved is False

    outcome = write(state, "p1", (1, 2), "M")

    events = events_of(outcome)
    assert len(events) == 2
    assert isinstance(events[0], LetterChanged)
    assert isinstance(events[1], GridSolved)
    assert outcome.state.solved is True


# ---- AC-9: the solved state survives a reload ----


def play_solved_game(grid: Grid) -> tuple[RoomState, list[LogEntry]]:
    """Joins, 18 edits and `grid_solved`: the final state and every entry."""
    state = new_room(ROOM_CODE, grid, NOW)
    entries: list[LogEntry] = []
    joins = [
        ("p1", "Ana", FIRST_TOKEN),
        ("p2", "Bob", SECOND_TOKEN),
    ]
    for player_id, nickname, token in joins:
        join = Join(nickname=nickname, resume_token=None)
        joined = join_room(state, join, NOW, player_id, token)
        entries.extend(joined.entries)
        state = joined.state
    for position in ROW_MAJOR:
        outcome = write(state, "p1", position, SOLUTION[position], NOW + 100.0)
        entries.extend(outcome.entries)
        state = outcome.state
    assert state.solved is True
    return state, entries


def test_ac9_replaying_the_whole_play_gives_the_live_solved_seq_and_cells(
    fx01_grid: Grid,
) -> None:
    live, entries = play_solved_game(fx01_grid)
    assert isinstance(entries[-1].event, GridSolved)

    replayed = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in entries:
        replayed = replay(replayed, entry)

    assert replayed.solved is True
    assert replayed.seq == live.seq == 2 + 18 + 1
    assert replayed.cells == live.cells


def test_ac9_replaying_grid_full_wrong_only_moves_the_seq(fx01_grid: Grid) -> None:
    state = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    next_seq = state.seq + 1

    replayed = replay(state, LogEntry(at=NOW, event=GridFullWrong(seq=next_seq)))

    assert replayed.seq == next_seq
    assert replayed.solved is False
    assert replayed.cells == state.cells


def test_ac9_replaying_grid_solved_sets_solved(fx01_grid: Grid) -> None:
    state = full17(fx01_grid)
    entry = LogEntry(at=NOW, event=GridSolved(seq=state.seq + 1, elapsed_ms=5))

    replayed = replay(state, entry)

    assert replayed.solved is True
    assert replayed.seq == state.seq + 1


def test_ac9_a_stored_solved_room_loads_solved_and_still_refuses_edits(
    fx01_grid: Grid,
) -> None:
    live, entries = play_solved_game(fx01_grid)
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, entries)

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.solved is True
    assert loaded.seq == live.seq
    assert loaded.cells == live.cells
    refused = handle_message(
        loaded, "p1", EditLetter(row=1, column=0, letter="A"), NOW + 200.0
    )
    assert refusal_code(refused) is ErrorCode.GRID_SOLVED
    assert refused.entries == ()


def test_ac9_a_stored_full_wrong_room_loads_unsolved_and_can_still_be_solved(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    entries: list[LogEntry] = []
    for position in ROW_MAJOR:
        letter = "N" if position == LAST_CELL else SOLUTION[position]
        outcome = write(state, "p1", position, letter, NOW + 100.0)
        entries.extend(outcome.entries)
        state = outcome.state
    assert isinstance(entries[-2].event, LetterChanged)
    assert isinstance(entries[-1].event, GridFullWrong)
    assert state.solved is False
    joins = [
        ("p1", "Ana", FIRST_TOKEN),
        ("p2", "Bob", SECOND_TOKEN),
    ]
    join_entries: list[LogEntry] = []
    replay_state = new_room(ROOM_CODE, fx01_grid, NOW)
    for player_id, nickname, token in joins:
        join = Join(nickname=nickname, resume_token=None)
        joined = join_room(replay_state, join, NOW, player_id, token)
        join_entries.extend(joined.entries)
        replay_state = joined.state

    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, join_entries + entries)

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.solved is False
    assert loaded.seq == state.seq
    assert loaded.cells == state.cells
    fixed = handle_message(
        loaded, "p1", EditLetter(row=4, column=4, letter="T"), NOW + 754.0
    )
    assert fixed.reply == ()
    assert events_of(fixed)[-1] == GridSolved(seq=state.seq + 2, elapsed_ms=754000)
