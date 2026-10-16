"""Tests of spec 038 (privacy and operations), AC-5: the dashboard's figures.

`dashboard_figures` reads hand-made `RoomLog` values, as the spec's "Test harness"
says: R1 to R4 of the criterion, at `now = T`. The shared setup is in
`spec038_harness`.

Edge cases checked as well, from "Edge cases and errors" and "Dashboard figures":
a period with rooms but no relay time, a room created exactly at the start of the
period, the median of an even count, the p95 rank `ceil(0.95 * n)`, relay times
of entries other than `letter_changed`, a drop that ends at the player's
`player_left` (a player timed out, then seated back with the same id), a drop
that is another player's, the 30-day period, and the values of `days` other
than 1, 7 and 30.

`nock.operations` is imported inside the helpers, so that each test fails on it
until it exists (see `spec038_harness`).
"""

from __future__ import annotations

import math
from datetime import timedelta
from typing import TYPE_CHECKING

import pytest

from nock.protocol import LeaveReason, PlayerState
from spec038_harness import DAY, Log, no_room_figures, seven_day_figures, utc

if TYPE_CHECKING:
    from nock.operations import DashboardFigures, RoomLog

# ---- Values of the spec --------------------------------------------------------------

T = 1_800_000_000.0  # `now` of the criterion

R1, R2, R3, R4 = "ROOM01", "ROOM02", "ROOM03", "ROOM04"


# ---- The rooms of the criterion ------------------------------------------------------


def room_log(code: str, created_at: float, log: Log) -> RoomLog:
    """The `RoomLog` of a hand-made log."""
    from nock.operations import RoomLog

    return RoomLog(code=code, created_at=created_at, entries=tuple(log.entries))


def r1() -> RoomLog:
    """R1, created at T - 2 DAY: 3 joins, five letters, one drop of p2, p3 gone."""
    created_at = T - 2 * DAY
    log = Log(created_at + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.join("p2", "BOB", 1, "token-of-bob-0002")
    log.join("p3", "CY", 2, "token-of-cy-00003")
    log.letter("p1", 1, 0, "T", relay_ms=10)
    log.letter("p2", 1, 1, "A", relay_ms=20)
    log.presence("p2", PlayerState.DISCONNECTED)
    log.presence("p2", PlayerState.ACTIVE)  # the drop of p2
    log.letter("p1", 1, 2, "M", relay_ms=30)
    log.letter("p1", 1, 3, "I", relay_ms=40)
    log.presence("p3", PlayerState.DISCONNECTED)  # never back: no drop
    log.letter("p1", 1, 4, "S")  # no relay_ms: logged before this spec
    log.solved(600_000)
    return room_log(R1, created_at, log)


def r2() -> RoomLog:
    """R2, created at T - 1 DAY: one join, one letter (relay 50), solved."""
    created_at = T - 1 * DAY
    log = Log(created_at + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.letter("p1", 1, 0, "T", relay_ms=50)
    log.solved(900_000)
    return room_log(R2, created_at, log)


def r3() -> RoomLog:
    """R3, created at T - 3 DAY: two joins, no edit, two drops of p1."""
    created_at = T - 3 * DAY
    log = Log(created_at + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.join("p2", "BOB", 1, "token-of-bob-0002")
    log.presence("p1", PlayerState.DISCONNECTED)
    log.presence("p1", PlayerState.ACTIVE)
    log.presence("p1", PlayerState.DISCONNECTED)
    log.presence("p1", PlayerState.ACTIVE)
    return room_log(R3, created_at, log)


def r4() -> RoomLog:
    """R4, created at T - 8 DAY: five joins and a `grid_solved` (100,000 ms)."""
    created_at = T - 8 * DAY
    log = Log(created_at + 10)
    for number in range(1, 6):
        log.join(f"p{number}", f"P{number}A", number - 1, f"token-of-p{number}-00000")
    log.solved(100_000)
    return room_log(R4, created_at, log)


def the_four_rooms() -> list[RoomLog]:
    return [r1(), r2(), r3(), r4()]


def figures(rooms: list[RoomLog], days: int, now: float = T) -> DashboardFigures:
    """`dashboard_figures(rooms, days, now)`."""
    from nock.operations import dashboard_figures

    return dashboard_figures(rooms, days, now)


def one_room(log: Log, created_at: float = T - DAY) -> list[RoomLog]:
    """A period of one room, with the given log."""
    return [room_log(R1, created_at, log)]


# ---- AC-5: the figures come from the room logs -------------------------------------


def test_ac5_day_seconds_is_86400() -> None:
    import nock.operations

    assert nock.operations.DAY_SECONDS == 86_400.0


def test_ac5_seven_days_give_the_figures_of_r1_r2_and_r3() -> None:
    result = figures(the_four_rooms(), 7)

    assert result == seven_day_figures(T)


def test_ac5_seven_days_figures_one_by_one() -> None:
    result = figures(the_four_rooms(), 7)

    assert result.days == 7
    assert result.rooms_created == 3
    assert result.players_per_room == 2.0
    assert result.completion_rate == 2 / 3
    assert result.median_solving_ms == 750_000.0
    assert result.latency_median_ms == 30.0
    assert result.latency_p95_ms == 50
    assert result.disconnection_rate == 0.5


def test_ac5_since_is_now_minus_the_period_in_utc() -> None:
    result = figures(the_four_rooms(), 7)

    assert result.since == utc(T - 7 * DAY)
    assert result.since.utcoffset() == timedelta(0)


def test_ac5_one_day_gives_r2_created_exactly_at_the_start_of_the_period() -> None:
    result = figures(the_four_rooms(), 1)

    assert result.days == 1
    assert result.since == utc(T - DAY)
    assert result.rooms_created == 1
    assert result.players_per_room == 1.0
    assert result.completion_rate == 1.0
    assert result.median_solving_ms == 900_000.0
    assert result.latency_median_ms == 50.0
    assert result.latency_p95_ms == 50
    assert result.disconnection_rate == 0.0


def test_ac5_no_room_gives_zero_rooms_and_none_elsewhere() -> None:
    result = figures([], 7)

    assert result == no_room_figures(T)


def test_ac5_only_rooms_created_before_the_period_give_no_room() -> None:
    result = figures([r4()], 7)

    assert result == no_room_figures(T)


@pytest.mark.parametrize("days", [2, 0, -7, 8, 31, 365])
def test_ac5_a_period_other_than_1_7_or_30_days_raises_value_error(days: int) -> None:
    # Built before the call: only `dashboard_figures` may raise here.
    rooms = the_four_rooms()

    with pytest.raises(ValueError, match=r".+"):
        figures(rooms, days)


@pytest.mark.parametrize("days", [2, 0, 31])
def test_ac5_a_period_other_than_1_7_or_30_days_raises_even_with_no_room(
    days: int,
) -> None:
    from nock.operations import dashboard_figures

    with pytest.raises(ValueError, match=r".+"):
        dashboard_figures([], days, T)


# ---- AC-5: edge cases ----------------------------------------------------------------


def test_ac5_thirty_days_take_r4_too() -> None:
    result = figures(the_four_rooms(), 30)

    assert result.days == 30
    assert result.since == utc(T - 30 * DAY)
    assert result.rooms_created == 4
    assert result.players_per_room == 11 / 4
    assert result.completion_rate == 3 / 4
    assert result.median_solving_ms == 600_000.0
    assert result.latency_median_ms == 30.0
    assert result.latency_p95_ms == 50
    assert result.disconnection_rate == 3 / 11


def test_ac5_rooms_with_no_relay_time_give_no_latency() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.letter("p1", 1, 0, "T")
    log.letter("p1", 1, 1, "A")

    result = figures(one_room(log), 7)

    assert result.rooms_created == 1
    assert result.latency_median_ms is None
    assert result.latency_p95_ms is None


def test_ac5_a_room_that_is_not_solved_gives_no_solving_time() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.letter("p1", 1, 0, "T", relay_ms=7)

    result = figures(one_room(log), 7)

    assert result.completion_rate == 0.0
    assert result.median_solving_ms is None


def test_ac5_a_room_with_no_join_gives_no_disconnection_rate() -> None:
    log = Log(T - DAY + 10)

    result = figures(one_room(log), 7)

    assert result.rooms_created == 1
    assert result.players_per_room == 0.0
    assert result.disconnection_rate is None


def test_ac5_only_the_relay_times_of_letter_changed_entries_count() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001", relay_ms=900)
    log.chat("p1", "bonjour", relay_ms=800)
    log.letter("p1", 1, 0, "T", relay_ms=5)

    result = figures(one_room(log), 7)

    assert result.latency_median_ms == 5.0
    assert result.latency_p95_ms == 5


def test_ac5_the_p95_is_the_ceil_of_0_95_n_th_smallest_relay_time() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    relay_times = list(range(1, 21))  # 1 to 20 ms: the 19th smallest is 19
    for relay_ms in reversed(relay_times):
        log.letter("p1", 1, 0, "T", relay_ms=relay_ms)

    result = figures(one_room(log), 7)

    rank = math.ceil(0.95 * len(relay_times))
    assert rank == 19
    assert result.latency_p95_ms == sorted(relay_times)[rank - 1]
    assert result.latency_median_ms == 10.5  # mean of the 10th and 11th values


def test_ac5_a_disconnection_ended_by_player_left_is_no_drop() -> None:
    # The player times out (spec 017), then is seated back with the same id (spec
    # 032): their `active` after the seat back ends no drop.
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.presence("p1", PlayerState.DISCONNECTED)
    log.leave("p1", LeaveReason.TIMED_OUT)
    log.join("p1", "ANA", 0, "token-of-ana-0001")  # seated back, the same id
    log.presence("p1", PlayerState.IDLE)
    log.presence("p1", PlayerState.ACTIVE)

    result = figures(one_room(log), 7)

    # Two player_joined entries and no drop.
    assert result.players_per_room == 2.0
    assert result.disconnection_rate == 0.0


def test_ac5_a_player_who_closes_the_tab_for_good_is_no_drop() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.join("p2", "BOB", 1, "token-of-bob-0002")
    log.presence("p1", PlayerState.DISCONNECTED)
    # Another player's comings and goings do not bring p1 back.
    log.presence("p2", PlayerState.IDLE)
    log.presence("p2", PlayerState.ACTIVE)

    result = figures(one_room(log), 7)

    assert result.disconnection_rate == 0.0


def test_ac5_a_drop_counts_once_until_the_next_disconnection() -> None:
    log = Log(T - DAY + 10)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    log.join("p2", "BOB", 1, "token-of-bob-0002")
    log.presence("p1", PlayerState.DISCONNECTED)
    log.presence("p1", PlayerState.ACTIVE)  # one drop
    log.presence("p1", PlayerState.IDLE)
    log.presence("p1", PlayerState.ACTIVE)  # the same player again: no new drop

    result = figures(one_room(log), 7)

    assert result.disconnection_rate == 0.5


def test_ac5_the_order_of_the_rooms_does_not_change_the_figures() -> None:
    rooms = the_four_rooms()
    rooms.reverse()

    result = figures(rooms, 7)

    assert result == seven_day_figures(T)
