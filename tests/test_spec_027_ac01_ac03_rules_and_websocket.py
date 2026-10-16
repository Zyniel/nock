"""Tests of spec 027, AC-1 and AC-3: the timer starts at the first letter and pauses
while nobody is connected.

The rules are tested on `handle_message`, `join_room`, `disconnect_player`, `tick`
and `after_restart`, and the room on the real WebSocket with a fake clock (spec
011's `TestClient`, a `FakeClock` and `RoomConfig(tick_seconds=0.05,
silence_timeout_seconds=3600, max_edits_per_second=1000)`). The browser parts of
AC-2 and AC-3 are in `test_spec_027_ac02_ac03_live_pages.py`. The shared setup is
in `spec027_harness`.
"""

from __future__ import annotations

import contextlib
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ChangeSettings,
    Chat,
    Direction,
    EditLetter,
    Erase,
    HelpMode,
    LetterChanged,
    PencilEdit,
    PlayerState,
    Reveal,
    RevealBudget,
    SelectCell,
)
from nock.room import (
    RoomConfig,
    RoomState,
    after_restart,
    disconnect_player,
    handle_message,
    snapshot_for,
    tick,
    timer_value_ms,
)
from spec017_harness import FakeClock, make_dist_dir, open_peer, running_room
from spec024_harness import FIRST_TOKEN, NOW, SECOND_TOKEN, grid_from_text
from spec027_harness import (
    THIRD_TOKEN,
    TIMER_CONFIG,
    events_of,
    has_letter,
    join_new,
    rejoin,
    room_with_players,
    snapshot_in,
    timer_fields,
    type_letter,
    wait_until_disconnected,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def room_running_since_10(grid: Grid) -> RoomState:
    """AC-1's room: `p1` and `p2` joined at NOW, `p1` typed `T` at NOW + 10.0."""
    state = room_with_players(grid, 2)
    return type_letter(state, "p1", 1, 0, "T", NOW + 10.0).state


def room_with_p1_typing_alone(grid: Grid) -> RoomState:
    """AC-3's room: `p1` alone joined at NOW and typed `T` at (1, 0) at NOW."""
    state = room_with_players(grid, 1)
    return type_letter(state, "p1", 1, 0, "T", NOW).state


def room_where_p1_left_and_p2_stayed(grid: Grid) -> RoomState:
    """AC-3's running room after `p1` left.

    `p1` and `p2` joined at NOW, `p1` typed `T` at (1, 0) at NOW and left at
    NOW + 30.0, while `p2` stayed connected.
    """
    state = type_letter(room_with_players(grid, 2), "p1", 1, 0, "T", NOW).state
    return disconnect_player(state, "p1", NOW + 30.0).state


# ---- AC-1: the first letter starts the timer (rule) ----


def test_ac1_a_new_room_has_no_timer_fields_set(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)

    assert timer_fields(state) == (False, 0, None)


def test_ac1_before_a_letter_the_snapshot_says_zero_and_not_running(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 2)

    snapshot = snapshot_for(state, "p2", NOW + 9.0)

    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac1_an_erase_does_not_start_the_timer(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)

    outcome = handle_message(state, "p1", Erase(row=1, column=0), NOW + 5.0)

    events = events_of(outcome)
    assert len(events) == 1
    assert isinstance(events[0], LetterChanged)
    assert events[0].letter is None
    assert timer_fields(outcome.state) == (False, 0, None)


def test_ac1_a_reveal_does_not_start_the_timer(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)

    outcome = handle_message(
        state, "p1", Reveal(target=CellTarget(row=1, column=0)), NOW + 5.0
    )

    assert outcome.reply == ()
    assert len(outcome.entries) >= 1
    assert timer_fields(outcome.state) == (False, 0, None)


def test_ac1_selecting_chatting_and_changing_settings_do_not_start_the_timer(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 2)

    selected = handle_message(
        state, "p1", SelectCell(row=1, column=0, direction=Direction.ACROSS), NOW + 1
    )
    chatted = handle_message(selected.state, "p2", Chat(text="Salut"), NOW + 2.0)
    settings = ChangeSettings(
        help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=4, words=1)
    )
    changed = handle_message(chatted.state, "p1", settings, NOW + 3.0)

    assert len(chatted.entries) == 1
    assert len(changed.entries) == 1
    assert timer_fields(changed.state) == (False, 0, None)
    assert snapshot_for(changed.state, "p1", NOW + 4.0).timer_running is False


def test_ac1_a_pencil_letter_starts_the_timer(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)

    outcome = handle_message(
        state, "p1", PencilEdit(row=1, column=0, letter="T"), NOW + 10.0
    )

    assert outcome.reply == ()
    assert timer_fields(outcome.state) == (True, 0, NOW + 10.0)


def test_ac1_the_first_letter_starts_the_timer_at_its_step(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)
    erased = handle_message(state, "p1", Erase(row=1, column=0), NOW + 5.0).state
    assert erased.timer_started is False

    started = type_letter(erased, "p1", 1, 0, "T", NOW + 10.0).state

    assert started.timer_started is True
    assert started.timer_resumed_at == NOW + 10.0
    assert started.timer_elapsed_ms == 0


def test_ac1_after_the_start_the_timer_counts_from_the_first_letter(
    fx01_grid: Grid,
) -> None:
    state = room_running_since_10(fx01_grid)

    assert timer_value_ms(state, NOW + 40.0) == 30000
    snapshot = snapshot_for(state, "p2", NOW + 40.0)
    assert snapshot.timer_elapsed_ms == 30000
    assert snapshot.timer_running is True


def test_ac1_a_player_joining_later_receives_the_running_timer(
    fx01_grid: Grid,
) -> None:
    state = room_running_since_10(fx01_grid)

    outcome = join_new(state, "Cy", "p3", THIRD_TOKEN, NOW + 40.0)

    snapshot = snapshot_in(outcome)
    assert snapshot.timer_elapsed_ms == 30000
    assert snapshot.timer_running is True


def test_ac1_a_later_letter_does_not_restart_the_timer(fx01_grid: Grid) -> None:
    state = room_running_since_10(fx01_grid)

    later = type_letter(state, "p2", 1, 1, "A", NOW + 25.0).state

    assert timer_fields(later) == (True, 0, NOW + 10.0)


def test_ac1_erasing_every_letter_does_not_stop_or_reset_the_timer(
    fx01_grid: Grid,
) -> None:
    state = room_running_since_10(fx01_grid)

    erased = handle_message(state, "p1", Erase(row=1, column=0), NOW + 20.0).state

    assert timer_fields(erased) == (True, 0, NOW + 10.0)


def test_ac1_a_refused_step_changes_no_timer_field(fx01_grid: Grid) -> None:
    state = room_running_since_10(fx01_grid)

    refused = handle_message(
        state, "p1", EditLetter(row=0, column=0, letter="T"), NOW + 20.0
    )

    assert refused.entries == ()
    assert len(refused.reply) == 1
    assert timer_fields(refused.state) == timer_fields(state)


def test_ac1_a_refused_first_letter_does_not_start_the_timer(fx01_grid: Grid) -> None:
    state = room_with_players(fx01_grid, 2)

    refused = handle_message(
        state, "p1", EditLetter(row=0, column=0, letter="T"), NOW + 20.0
    )

    assert refused.entries == ()
    assert timer_fields(refused.state) == (False, 0, None)


# ---- AC-1: the value and the snapshot (rule) ----


@pytest.mark.parametrize(
    ("seconds_after_start", "expected_ms"),
    [
        (0.0, 0),
        (0.0004, 0),
        (0.0006, 1),
        (1.2346, 1235),
        (1.2344, 1234),
        (30.0, 30000),
        (3600.0, 3_600_000),
    ],
)
def test_ac1_timer_value_rounds_to_whole_milliseconds(
    fx01_grid: Grid, seconds_after_start: float, expected_ms: int
) -> None:
    state = room_running_since_10(fx01_grid)

    value = timer_value_ms(state, NOW + 10.0 + seconds_after_start)

    assert value == expected_ms


def test_ac1_timer_value_never_goes_below_what_was_counted(fx01_grid: Grid) -> None:
    state = room_running_since_10(fx01_grid)
    counted = state.model_copy(update={"timer_elapsed_ms": 7000})

    assert timer_value_ms(counted, NOW + 5.0) == 7000
    assert timer_value_ms(state, NOW) == 0


def test_ac1_timer_value_of_a_timer_that_is_not_running_ignores_the_time(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 2)
    paused = state.model_copy(update={"timer_started": True, "timer_elapsed_ms": 4321})

    assert timer_value_ms(state, NOW + 1000.0) == 0
    assert timer_value_ms(paused, NOW + 1000.0) == 4321


def test_ac1_timer_value_adds_the_current_run_to_the_time_counted_before(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 2)
    running = state.model_copy(
        update={
            "timer_started": True,
            "timer_elapsed_ms": 4000,
            "timer_resumed_at": NOW + 100.0,
        }
    )

    assert timer_value_ms(running, NOW + 102.5) == 6500


def test_ac1_a_snapshot_without_now_gives_the_time_counted_before_the_run(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 2)
    running = state.model_copy(
        update={
            "timer_started": True,
            "timer_elapsed_ms": 4000,
            "timer_resumed_at": NOW + 100.0,
        }
    )

    snapshot = snapshot_for(running, "p1")

    assert snapshot.timer_elapsed_ms == 4000
    assert snapshot.timer_running is True


def test_ac1_a_snapshot_without_now_of_a_new_room_is_zero_and_not_running(
    fx01_grid: Grid,
) -> None:
    snapshot = snapshot_for(room_with_players(fx01_grid, 2), "p1")

    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac1_the_timer_fields_are_validated_when_a_room_is_loaded(
    fx01_grid: Grid,
) -> None:
    state = room_running_since_10(fx01_grid)
    stored = json.loads(state.model_dump_json())
    assert RoomState.model_validate_json(json.dumps(stored)) == state

    for field, bad_value in [
        ("timer_elapsed_ms", -1),
        ("timer_elapsed_ms", 1.5),
        ("timer_started", 1),
    ]:
        damaged = {**stored, field: bad_value}
        with pytest.raises(ValidationError):
            RoomState.model_validate_json(json.dumps(damaged))


# ---- AC-1: the WebSocket ----


def test_ac1_websocket_the_timer_starts_at_the_first_letter(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, TIMER_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        peer_a = open_peer(stack, client, code, "Ana")
        peer_b = open_peer(stack, client, code, "Bob")
        peer_d = open_peer(stack, client, code, "Dan")
        first_snapshot = peer_d.snapshot()
        assert first_snapshot.timer_elapsed_ms == 0
        assert first_snapshot.timer_running is False

        fake_clock.advance(20)
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        peer_b.wait_until(lambda: has_letter(peer_b, 1, 0), "A's letter on B")
        fake_clock.advance(30)
        peer_c = open_peer(stack, client, code, "Cy")

        late_snapshot = peer_c.snapshot()
        assert late_snapshot.timer_elapsed_ms == 30000
        assert late_snapshot.timer_running is True


def test_ac1_websocket_an_erase_alone_leaves_the_timer_at_zero(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, TIMER_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        peer_a = open_peer(stack, client, code, "Ana")
        peer_b = open_peer(stack, client, code, "Bob")

        fake_clock.advance(20)
        peer_a.send(Erase(row=1, column=0))
        peer_b.wait_until(lambda: has_letter(peer_b, 1, 0), "A's erase on B")
        fake_clock.advance(30)
        peer_c = open_peer(stack, client, code, "Cy")

        snapshot = peer_c.snapshot()
        assert snapshot.timer_elapsed_ms == 0
        assert snapshot.timer_running is False


# ---- AC-3: the timer pauses while no player is connected (rule) ----


def test_ac3_the_last_player_leaving_pauses_the_timer(fx01_grid: Grid) -> None:
    state = room_with_p1_typing_alone(fx01_grid)

    outcome = disconnect_player(state, "p1", NOW + 30.0)

    assert outcome.state.timer_resumed_at is None
    assert outcome.state.timer_elapsed_ms == 30000
    assert outcome.state.timer_started is True
    assert timer_value_ms(outcome.state, NOW + 200.0) == 30000
    snapshot = snapshot_for(outcome.state, "p1", NOW + 200.0)
    assert snapshot.timer_elapsed_ms == 30000
    assert snapshot.timer_running is False


def test_ac3_the_next_connection_resumes_the_timer(fx01_grid: Grid) -> None:
    paused = disconnect_player(
        room_with_p1_typing_alone(fx01_grid), "p1", NOW + 30.0
    ).state

    outcome = rejoin(paused, "Ana", FIRST_TOKEN, NOW + 200.0)

    assert outcome.state.timer_resumed_at == NOW + 200.0
    assert outcome.state.timer_elapsed_ms == 30000
    snapshot = snapshot_in(outcome)
    assert snapshot.timer_elapsed_ms == 30000
    assert snapshot.timer_running is True
    assert timer_value_ms(outcome.state, NOW + 210.0) == 40000


def test_ac3_a_new_player_joining_a_paused_room_resumes_the_timer(
    fx01_grid: Grid,
) -> None:
    paused = disconnect_player(
        room_with_p1_typing_alone(fx01_grid), "p1", NOW + 30.0
    ).state

    outcome = join_new(paused, "Bob", "p2", SECOND_TOKEN, NOW + 100.0)

    assert outcome.state.timer_resumed_at == NOW + 100.0
    assert outcome.state.timer_elapsed_ms == 30000
    snapshot = snapshot_in(outcome)
    assert snapshot.timer_elapsed_ms == 30000
    assert snapshot.timer_running is True


def test_ac3_a_player_leaving_while_another_is_connected_keeps_the_timer_running(
    fx01_grid: Grid,
) -> None:
    state = type_letter(room_with_players(fx01_grid, 2), "p1", 1, 0, "T", NOW).state

    outcome = disconnect_player(state, "p1", NOW + 30.0)

    assert timer_fields(outcome.state) == (True, 0, NOW)
    assert snapshot_for(outcome.state, "p2", NOW + 45.0).timer_elapsed_ms == 45000


def test_ac3_a_player_coming_back_to_a_running_room_gets_the_running_time(
    fx01_grid: Grid,
) -> None:
    left = room_where_p1_left_and_p2_stayed(fx01_grid)

    outcome = rejoin(left, "Ana", FIRST_TOKEN, NOW + 45.0)

    snapshot = snapshot_in(outcome)
    assert snapshot.you == "p1"
    assert snapshot.timer_elapsed_ms == 45000
    assert snapshot.timer_running is True


def test_ac3_a_player_coming_back_to_a_running_room_changes_no_timer_field(
    fx01_grid: Grid,
) -> None:
    left = room_where_p1_left_and_p2_stayed(fx01_grid)
    assert left.timer_resumed_at == NOW
    assert left.timer_elapsed_ms == 0

    outcome = rejoin(left, "Ana", FIRST_TOKEN, NOW + 45.0)

    assert snapshot_in(outcome).you == "p1"
    assert outcome.state.players[0].state == PlayerState.ACTIVE
    assert outcome.state.timer_resumed_at == NOW
    assert outcome.state.timer_elapsed_ms == 0
    assert timer_fields(outcome.state) == (True, 0, NOW)


def test_ac3_the_second_player_leaving_pauses_the_timer(fx01_grid: Grid) -> None:
    state = type_letter(room_with_players(fx01_grid, 2), "p1", 1, 0, "T", NOW).state
    state = disconnect_player(state, "p1", NOW + 30.0).state

    outcome = disconnect_player(state, "p2", NOW + 50.0)

    assert outcome.state.timer_resumed_at is None
    assert outcome.state.timer_elapsed_ms == 50000


def test_ac3_an_idle_player_is_connected_so_the_timer_runs(fx01_grid: Grid) -> None:
    state = room_with_p1_typing_alone(fx01_grid)
    config = RoomConfig(silence_timeout_seconds=3600)

    outcome = tick(state, NOW + 150.0, config)

    assert outcome.state.players[0].state == PlayerState.IDLE
    assert timer_fields(outcome.state) == (True, 0, NOW)
    assert snapshot_for(outcome.state, "p1", NOW + 160.0).timer_running is True


def test_ac3_silence_pauses_the_timer_when_tick_disconnects_the_last_player(
    fx01_grid: Grid,
) -> None:
    state = room_with_p1_typing_alone(fx01_grid)

    outcome = tick(state, NOW + 6.0)

    assert outcome.state.players[0].state == PlayerState.DISCONNECTED
    assert outcome.state.timer_resumed_at is None
    assert outcome.state.timer_elapsed_ms == 6000


def test_ac3_a_restart_pauses_the_timer_of_a_running_room(fx01_grid: Grid) -> None:
    state = room_with_p1_typing_alone(fx01_grid)

    outcome = after_restart(state, NOW + 50.0)

    assert outcome.state.timer_resumed_at is None
    assert outcome.state.timer_elapsed_ms == 50000


def test_ac3_a_restart_leaves_the_timer_of_a_room_never_started_alone(
    fx01_grid: Grid,
) -> None:
    outcome = after_restart(room_with_players(fx01_grid, 2), NOW + 50.0)

    assert timer_fields(outcome.state) == (False, 0, None)


def test_ac3_a_player_who_times_out_of_a_paused_room_changes_no_timer_field(
    fx01_grid: Grid,
) -> None:
    paused = disconnect_player(
        room_with_p1_typing_alone(fx01_grid), "p1", NOW + 30.0
    ).state

    outcome = tick(paused, NOW + 400.0)

    assert len(outcome.entries) >= 1
    assert timer_fields(outcome.state) == (True, 30000, None)


def test_ac3_a_room_where_no_letter_was_typed_stays_at_zero_through_a_leave_and_return(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 1)
    left = disconnect_player(state, "p1", NOW + 30.0).state
    back = rejoin(left, "Ana", FIRST_TOKEN, NOW + 100.0)

    assert timer_fields(left) == (False, 0, None)
    assert timer_fields(back.state) == (False, 0, None)
    snapshot = snapshot_in(back)
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac3_a_letter_typed_after_a_return_starts_the_timer_then(
    fx01_grid: Grid,
) -> None:
    state = room_with_players(fx01_grid, 1)
    left = disconnect_player(state, "p1", NOW + 30.0).state
    back = rejoin(left, "Ana", FIRST_TOKEN, NOW + 100.0).state

    started = type_letter(back, "p1", 1, 0, "T", NOW + 120.0).state

    assert timer_fields(started) == (True, 0, NOW + 120.0)


# ---- AC-3: the WebSocket ----


def test_ac3_websocket_the_timer_pauses_while_the_player_is_away(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, TIMER_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as first_socket,
    ):
        peer_a = open_peer(first_socket, client, code, "Ana")
        token = peer_a.snapshot().resume_token
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        peer_a.wait_until(lambda: has_letter(peer_a, 1, 0), "A's letter")
        fake_clock.advance(30)
        first_socket.close()
        wait_until_disconnected(registry, code, peer_a.snapshot().you)

        fake_clock.advance(200)
        again = open_peer(stack, client, code, "Ana", token)
        returned = again.snapshot()
        fake_clock.advance(10)
        peer_b = open_peer(stack, client, code, "Bob")
        late = peer_b.snapshot()

        assert returned.timer_elapsed_ms == 30000
        assert returned.timer_running is True
        assert late.timer_elapsed_ms == 40000
        assert late.timer_running is True


def test_ac3_websocket_a_room_with_a_second_player_keeps_counting(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, TIMER_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as first_socket,
    ):
        peer_a = open_peer(first_socket, client, code, "Ana")
        peer_b = open_peer(stack, client, code, "Bob")
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        peer_b.wait_until(lambda: has_letter(peer_b, 1, 0), "A's letter on B")
        fake_clock.advance(30)
        first_socket.close()
        wait_until_disconnected(registry, code, peer_a.snapshot().you)
        fake_clock.advance(20)
        peer_c = open_peer(stack, client, code, "Cy")

        snapshot = peer_c.snapshot()
        assert snapshot.timer_elapsed_ms == 50000
        assert snapshot.timer_running is True
