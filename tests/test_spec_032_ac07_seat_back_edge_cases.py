"""Tests of spec 032, AC-7: the edge cases of a seat back, and the join's nickname.

The runs are those of `test_spec_032_ac07_seat_back.py`: a FX-01 room played with
the rules (`spec032_harness.Run`), with Ana timed out by the tick of t0 + 311
(`spec032_harness.ana_timed_out`). The edge cases: a past player can be neither
removed nor muted, a player seated back can be removed, a second join with the
same token is a resume, a second time-out leaves one past record, and a past
player dropped by the cap of 100 joins as a new player.

The join's nickname: a seat back ignores `message.nickname` and does not check
it, so spec 012's step 5 does not apply ("Seat back"). The joins below carry
nicknames that the protocol lets through and that spec 012's `normalize_nickname`
refuses. A nickname of one character, such as `x`, breaks the protocol's
`Nickname` (2 to 20 characters, spec 039): a `Join` cannot hold it, and over the
socket `parse_client_message` refuses it, so it never reaches the rules.
"""

from __future__ import annotations

import pytest

import nock.room
from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    HostChanged,
    LeaveReason,
    MutePlayer,
    PlayerJoined,
    PlayerLeft,
    RemovePlayer,
)
from spec032_harness import (
    ANA,
    BOB,
    CY,
    IN_THE_WINDOW_LIMIT,
    LEFT_AT,
    NEW_PLAYER_ID,
    SEAT_BACK_AT,
    T0,
    TA,
    ana_timed_out,
    ana_wrote_t,
    anas_past_record,
    error_code_of,
    events_of,
    grid_from_text,
    past,
    player_ids,
    player_of,
    refused_by_spec_012,
    seat_back,
    snapshot_of,
    view,
)

# One nickname made only of punctuation, one with a refused character (spec 012,
# "Allowed characters").
REFUSED_NICKNAMES = pytest.mark.parametrize(
    "nickname", ["--", "Ana!"], ids=["only_punctuation", "a_refused_character"]
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Edge cases ----------------------------------------------------------------


def test_ac7_a_past_player_can_be_neither_removed_nor_muted(fx01_grid: Grid) -> None:
    run = ana_timed_out(fx01_grid)

    removal = run.send(BOB, RemovePlayer(player_id=ANA), T0 + 320)
    mute = run.send(BOB, MutePlayer(player_id=ANA, muted=True), T0 + 321)

    assert error_code_of(removal.reply) is ErrorCode.INVALID_TARGET
    assert error_code_of(mute.reply) is ErrorCode.INVALID_TARGET
    assert run.state.past_players == (anas_past_record(),)


def test_ac7_a_player_seated_back_can_be_removed_and_is_then_refused(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    seat_back(run)

    removal = run.send(BOB, RemovePlayer(player_id=ANA), SEAT_BACK_AT + 1)
    again = seat_back(run, now=SEAT_BACK_AT + 2)

    assert events_of(removal) == [
        PlayerLeft(seq=9, player_id=ANA, reason=LeaveReason.REMOVED)
    ]
    assert error_code_of(again.reply) is ErrorCode.REMOVED
    assert again.state.past_players == ()


def test_ac7_a_second_join_with_the_same_token_resumes_the_player(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    seat_back(run)

    second_device = seat_back(run, now=SEAT_BACK_AT + 1)

    assert snapshot_of(second_device).you == ANA
    assert second_device.entries == ()
    assert player_ids(second_device.state) == [BOB, CY, ANA]


def test_ac7_a_player_who_times_out_again_has_one_past_record(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    seat_back(run)
    run.disconnect(ANA, SEAT_BACK_AT + 10)

    run.tick(SEAT_BACK_AT + 311)

    assert run.state.past_players == (anas_past_record(),)


def test_ac7_a_past_player_dropped_by_the_cap_joins_as_a_new_player(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    others: list[object] = []
    for number in range(nock.room.MAX_PAST_PLAYERS - 1):
        others.append(past(f"past{number}", f"token-of-past-{number:04d}", "OLD", 7))
    full = run.state.model_copy(update={"past_players": (anas_past_record(), *others)})
    run.state = full
    run.disconnect(BOB, T0 + 320)
    run.tick(T0 + 621)

    outcome = seat_back(run, now=T0 + 630)

    snapshot = snapshot_of(outcome)
    assert snapshot.you == NEW_PLAYER_ID
    assert player_of(outcome.state, NEW_PLAYER_ID).nickname == "AUTRE"


# ---- The join's nickname -------------------------------------------------------


@REFUSED_NICKNAMES
def test_ac7_a_seat_back_ignores_a_nickname_that_spec_012_refuses(
    fx01_grid: Grid, nickname: str
) -> None:
    assert refused_by_spec_012(nickname) is True
    run = ana_timed_out(fx01_grid)

    outcome = seat_back(run, nickname=nickname)

    assert events_of(outcome) == [
        PlayerJoined(seq=8, player=view(ANA, "ANA", 0, is_host=False))
    ]
    snapshot = snapshot_of(outcome)
    assert (snapshot.you, snapshot.resume_token) == (ANA, TA)
    assert outcome.close_sender is False


@REFUSED_NICKNAMES
def test_ac7_a_join_that_times_the_player_out_ignores_a_refused_nickname_too(
    fx01_grid: Grid, nickname: str
) -> None:
    assert refused_by_spec_012(nickname) is True
    run = ana_wrote_t(fx01_grid)
    run.disconnect(ANA, LEFT_AT)

    outcome = seat_back(run, now=IN_THE_WINDOW_LIMIT, nickname=nickname)

    assert events_of(outcome) == [
        PlayerLeft(seq=6, player_id=ANA, reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=7, player_id=BOB),
        PlayerJoined(seq=8, player=view(ANA, "ANA", 0, is_host=False)),
    ]
    assert snapshot_of(outcome).you == ANA
