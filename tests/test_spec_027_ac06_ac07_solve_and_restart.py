"""Tests of spec 027, AC-6 and AC-7: the solving time is the shared timer, which stops
at the solve, and the timer survives a reload and a server restart.

AC-6 is checked on `handle_message`, `join_room` and `disconnect_player` over the
play of the spec (two players, a pause of 240 s in the middle). AC-7 replays that
play with `replay` and loads it from a `RoomStore`. The shared setup is in
`spec027_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Chat,
    EditLetter,
    GridSolved,
    HelpMode,
    LetterChanged,
    Reveal,
)
from nock.room import (
    LogEntry,
    after_restart,
    disconnect_player,
    handle_message,
    new_room,
    replay,
    snapshot_for,
    timer_value_ms,
)
from nock.store import RoomStore
from spec024_harness import (
    FIRST_TOKEN,
    NOW,
    ROOM_CODE,
    ROW_MAJOR,
    SECOND_TOKEN,
    grid_from_text,
    host_changes,
    two_player_room,
)
from spec026_harness import SOLUTION, full17, solved_room
from spec027_harness import (
    THIRD_TOKEN,
    Play,
    events_of,
    join_new,
    play_of_ac6,
    rejoin,
    snapshot_in,
    timer_fields,
    type_letter,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def play(fx01_grid: Grid) -> Play:
    return play_of_ac6(fx01_grid)


# ---- AC-6: the play of the spec ----


def test_ac6_the_timer_starts_with_the_first_letter_of_the_play(play: Play) -> None:
    after_joins = play.state_after_seq(2)
    after_first_letter = play.state_after_seq(3)

    assert timer_fields(after_joins) == (False, 0, None)
    assert timer_fields(after_first_letter) == (True, 0, NOW + 100.0)
    assert timer_fields(play.state_after_seq(19)) == (True, 0, NOW + 100.0)


def test_ac6_the_timer_pauses_when_both_players_have_left(play: Play) -> None:
    assert timer_fields(play.state_after_seq(20)) == (True, 0, NOW + 100.0)
    assert timer_fields(play.state_after_seq(21)) == (True, 60000, None)


def test_ac6_the_timer_resumes_at_the_first_return(play: Play) -> None:
    assert timer_fields(play.state_after_seq(22)) == (True, 60000, NOW + 400.0)
    assert timer_fields(play.state_after_seq(23)) == (True, 60000, NOW + 400.0)


def test_ac6_the_last_step_logs_the_letter_then_the_solving_time(play: Play) -> None:
    last_step = play.steps[-1]

    events = [entry.event for entry in last_step.entries]

    assert events == [
        LetterChanged(
            seq=24, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=25, elapsed_ms=114000),
    ]


def test_ac6_the_solved_room_holds_the_final_time_and_no_run(play: Play) -> None:
    final = play.final

    assert final.solved is True
    assert final.timer_elapsed_ms == 114000
    assert final.timer_resumed_at is None


def test_ac6_the_snapshot_of_the_solved_room_is_stopped_at_the_final_time(
    play: Play,
) -> None:
    snapshot = snapshot_for(play.final, "p1", NOW + 2000.0)

    assert snapshot.timer_elapsed_ms == 114000
    assert snapshot.timer_running is False
    assert snapshot.solved is True


def test_ac6_a_third_player_joining_the_solved_room_leaves_it_stopped(
    play: Play,
) -> None:
    outcome = join_new(play.final, "Cy", "p3", THIRD_TOKEN, NOW + 2000.0)

    snapshot = snapshot_in(outcome)
    assert snapshot.timer_elapsed_ms == 114000
    assert snapshot.timer_running is False
    assert timer_fields(outcome.state) == timer_fields(play.final)


def test_ac6_leaving_and_returning_after_the_solve_do_not_move_the_timer(
    play: Play,
) -> None:
    state = disconnect_player(play.final, "p1", NOW + 3000.0).state
    state = disconnect_player(state, "p2", NOW + 3000.0).state
    returned = rejoin(state, "Ana", FIRST_TOKEN, NOW + 3100.0)

    assert timer_fields(state) == timer_fields(play.final)
    assert timer_fields(returned.state) == timer_fields(play.final)
    assert snapshot_in(returned).timer_elapsed_ms == 114000
    assert snapshot_in(returned).timer_running is False
    assert timer_value_ms(returned.state, NOW + 9000.0) == 114000


def test_ac6_chat_after_the_solve_does_not_move_the_timer(play: Play) -> None:
    chatted = handle_message(play.final, "p1", Chat(text="Bravo"), NOW + 3000.0)

    assert len(chatted.entries) == 1
    assert timer_fields(chatted.state) == timer_fields(play.final)


def test_ac6_a_refused_edit_after_the_solve_does_not_move_the_timer(
    play: Play,
) -> None:
    refused = handle_message(
        play.final, "p1", EditLetter(row=1, column=0, letter="X"), NOW + 3000.0
    )

    assert refused.entries == ()
    assert timer_fields(refused.state) == timer_fields(play.final)


# ---- AC-6: the solving time of spec 026's rooms ----


def test_ac6_the_eighteenth_letter_still_gives_754_seconds_in_full17(
    fx01_grid: Grid,
) -> None:
    outcome = handle_message(
        full17(fx01_grid),
        "p2",
        EditLetter(row=4, column=4, letter="T"),
        NOW + 754.0,
    )

    assert outcome.reply == ()
    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=754000)
    assert outcome.state.timer_elapsed_ms == 754000
    assert outcome.state.timer_resumed_at is None


def test_ac6_the_solved_room_of_spec_026_is_stopped_at_754_seconds(
    fx01_grid: Grid,
) -> None:
    state = solved_room(fx01_grid)

    snapshot = snapshot_for(state, "p1", NOW + 5000.0)

    assert snapshot.timer_elapsed_ms == 754000
    assert snapshot.timer_running is False


def test_ac6_the_time_is_the_timer_not_the_age_of_the_room(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    for row, column in ROW_MAJOR[:-1]:
        state = type_letter(
            state, "p1", row, column, SOLUTION[(row, column)], NOW + 100.0
        ).state

    outcome = handle_message(
        state, "p2", EditLetter(row=4, column=4, letter="T"), NOW + 754.0
    )

    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=654000)


def test_ac6_the_first_letter_that_solves_the_grid_gives_zero(fx01_grid: Grid) -> None:
    state = host_changes(two_player_room(fx01_grid), HelpMode.FREE, 18, 1)
    for row, column in ROW_MAJOR[:-1]:
        target = CellTarget(row=row, column=column)
        revealed = handle_message(state, "p1", Reveal(target=target), NOW + 10.0)
        assert revealed.reply == ()
        state = revealed.state
    assert state.timer_started is False
    assert state.solved is False

    outcome = handle_message(
        state, "p2", EditLetter(row=4, column=4, letter="T"), NOW + 500.0
    )

    events = events_of(outcome)
    assert isinstance(events[0], LetterChanged)
    assert events[-1] == GridSolved(seq=state.seq + 2, elapsed_ms=0)
    assert outcome.state.timer_started is True
    assert outcome.state.timer_elapsed_ms == 0
    assert outcome.state.timer_resumed_at is None
    snapshot = snapshot_for(outcome.state, "p1", NOW + 600.0)
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac6_a_grid_solved_only_by_reveals_ends_with_zero(fx01_grid: Grid) -> None:
    state = host_changes(two_player_room(fx01_grid), HelpMode.FREE, 18, 1)
    last_outcome = None
    for row, column in ROW_MAJOR:
        target = CellTarget(row=row, column=column)
        last_outcome = handle_message(state, "p1", Reveal(target=target), NOW + 600.0)
        assert last_outcome.reply == ()
        state = last_outcome.state

    assert last_outcome is not None
    assert events_of(last_outcome)[-1] == GridSolved(seq=state.seq, elapsed_ms=0)
    assert state.solved is True
    assert state.timer_elapsed_ms == 0
    assert state.timer_resumed_at is None
    snapshot = snapshot_for(state, "p2", NOW + 900.0)
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


# ---- AC-7: replay gives the timer of the live play ----


def test_ac7_replay_gives_the_live_timer_after_each_step(
    fx01_grid: Grid, play: Play
) -> None:
    replayed = new_room(ROOM_CODE, fx01_grid, NOW)

    for step in play.steps:
        for entry in step.entries:
            replayed = replay(replayed, entry)
        assert replayed.seq == step.state.seq
        assert timer_fields(replayed) == timer_fields(step.state), step.state.seq


def test_ac7_replay_uses_the_time_logged_with_each_entry(
    fx01_grid: Grid, play: Play
) -> None:
    replayed = new_room(ROOM_CODE, fx01_grid, NOW)

    for entry in play.entries_up_to(23):
        replayed = replay(replayed, entry)

    assert timer_fields(replayed) == (True, 60000, NOW + 400.0)


def test_ac7_replay_of_the_whole_play_stops_the_timer_at_the_solve(
    fx01_grid: Grid, play: Play
) -> None:
    replayed = new_room(ROOM_CODE, fx01_grid, NOW)

    for entry in play.entries_up_to(25):
        replayed = replay(replayed, entry)

    assert replayed.solved is True
    assert replayed.timer_elapsed_ms == 114000
    assert replayed.timer_resumed_at is None


def test_ac7_a_logged_grid_solved_keeps_the_time_it_was_logged_with(
    play: Play,
) -> None:
    running = play.state_after_seq(19)
    entry = LogEntry(at=NOW + 500.0, event=GridSolved(seq=20, elapsed_ms=777))

    replayed = replay(running, entry)

    assert replayed.timer_elapsed_ms == 777
    assert replayed.timer_resumed_at is None
    assert replayed.solved is True


# ---- AC-7: the store ----


def test_ac7_a_store_holding_the_play_up_to_seq_23_loads_the_timer(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(23))

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.seq == 23
    assert loaded.timer_started is True
    assert loaded.timer_resumed_at == NOW + 400.0
    assert loaded.timer_elapsed_ms == 60000


def test_ac7_a_restart_pauses_the_loaded_timer_and_a_return_resumes_it(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(23))
        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()
    assert loaded is not None

    restarted = after_restart(loaded, NOW + 430.0)
    returned = rejoin(restarted.state, "Ana", FIRST_TOKEN, NOW + 700.0)

    assert restarted.state.timer_resumed_at is None
    assert restarted.state.timer_elapsed_ms == 90000
    snapshot = snapshot_in(returned)
    assert snapshot.timer_elapsed_ms == 90000
    assert snapshot.timer_running is True
    assert returned.state.timer_resumed_at == NOW + 700.0
    assert timer_value_ms(returned.state, NOW + 710.0) == 100000


def test_ac7_the_other_player_resumes_the_timer_too_after_a_restart(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(23))
        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()
    assert loaded is not None
    restarted = after_restart(loaded, NOW + 430.0).state

    returned = rejoin(restarted, "Bob", SECOND_TOKEN, NOW + 700.0)

    assert snapshot_in(returned).timer_elapsed_ms == 90000
    assert snapshot_in(returned).timer_running is True


def test_ac7_a_stored_snapshot_keeps_the_timer_fields(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(23))
        store.save_snapshot(play.state_after_seq(23))
        store.append(ROOM_CODE, play.entries_up_to(25)[23:])

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.solved is True
    assert timer_fields(loaded) == timer_fields(play.final)


def test_ac7_a_snapshot_at_seq_23_loads_with_its_running_timer(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(23))
        store.save_snapshot(play.state_after_seq(23))

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert timer_fields(loaded) == (True, 60000, NOW + 400.0)


def test_ac7_the_whole_play_loads_as_a_solved_room_with_its_final_time(
    fx01_grid: Grid, play: Play
) -> None:
    store = RoomStore(":memory:")
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries_up_to(25))

        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    assert loaded is not None
    assert loaded.solved is True
    assert loaded.timer_elapsed_ms == 114000
    assert loaded.timer_resumed_at is None
    assert snapshot_for(loaded, "p1", NOW + 9999.0).timer_elapsed_ms == 114000
