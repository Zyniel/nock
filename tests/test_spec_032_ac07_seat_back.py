"""Tests of spec 032, AC-7: a player who comes back after spec 017's time-out with
their stored token gets their seat back.

The runs play a FX-01 room with the rules (`spec032_harness.Run`) and the
`RoomConfig` of "no tick changes anything" except `resume_window_seconds`, left at
300: Ana (TA), Bob (TB) and Cy (TC) join at t0 (seq 1 to 3, colours 0 to 2, Ana
host); Ana writes `T` at (1, 0) (seq 4); her connection closes at t0 + 10 (seq 5);
the tick of t0 + 311 times her out (seq 6) and hands the host role to Bob (seq 7).
This base run is `spec032_harness.ana_timed_out`. Each run then does what the
criterion names: a seat back at t0 + 400 with the nickname `Autre`, a fresh record,
a mute, a colour or a nickname taken meanwhile, a full or a locked room, a time-out
in the join itself, a removed player, a vote opened while Ana is away. The rules of
"What a seat back keeps, and what starts afresh" are checked on the same runs.

The edge cases on seat backs are in `test_spec_032_ac07_seat_back_edge_cases.py`,
the WebSocket and HTTP part of AC-7 in `test_spec_032_ac02_ac07_sockets.py`, and
its page run in `test_spec_032_ac07_page_after_the_seat_back.py`.
"""

from __future__ import annotations

import pytest

import nock.room
from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellTarget,
    ChangeSettings,
    Chat,
    ChatMessage,
    ClueRef,
    EditLetter,
    ErrorCode,
    Flag,
    FlagChanged,
    HelpMode,
    HostChanged,
    LeaveReason,
    LetterChanged,
    LockRoom,
    MutePlayer,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    RemovePlayer,
    Reveal,
    RevealBudget,
    RevealResult,
    Undo,
    Vote,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
)
from nock.room import Outcome, PlayerRecord, RoomState
from spec032_harness import (
    ANA,
    BOB,
    CY,
    DAN,
    IN_THE_WINDOW_LIMIT,
    LEFT_AT,
    NEW_PLAYER_ID,
    NEW_TOKEN,
    SEAT_BACK_AT,
    T0,
    TA,
    TB,
    TC,
    TD,
    TIMED_OUT_AT,
    Run,
    ana_timed_out,
    ana_wrote_t,
    anas_past_record,
    cell_of,
    error_code_of,
    events_of,
    grid_from_text,
    past,
    player_ids,
    player_of,
    seat_back,
    snapshot_of,
    view,
)

IDES = ClueRef(row=0, column=3, clue_index=0)
MORE_PLAYERS = ["Dan", "Eve", "Fay", "Gus", "Hal", "Ivy"]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def players_summary(state: RoomState) -> list[tuple[str, str, int, bool]]:
    """The id, nickname, colour and host flag of each player, in order."""
    summary: list[tuple[str, str, int, bool]] = []
    for player in state.players:
        summary.append(
            (player.player_id, player.nickname, player.colour, player.is_host)
        )
    return summary


# ---- The time-out --------------------------------------------------------------


def test_ac7_the_tick_times_ana_out_and_hands_the_host_role_to_bob(
    fx01_grid: Grid,
) -> None:
    run = ana_wrote_t(fx01_grid)
    run.disconnect(ANA, LEFT_AT)

    ticked = run.tick(TIMED_OUT_AT)

    assert events_of(ticked) == [
        PlayerLeft(seq=6, player_id=ANA, reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=7, player_id=BOB),
    ]
    assert ticked.state.past_players == (anas_past_record(),)


# ---- Seat back -----------------------------------------------------------------


def test_ac7_a_seat_back_gives_one_player_joined_of_the_past_players_id(
    fx01_grid: Grid,
) -> None:
    outcome = seat_back(ana_timed_out(fx01_grid))

    assert events_of(outcome) == [
        PlayerJoined(seq=8, player=view(ANA, "ANA", 0, is_host=False))
    ]


def test_ac7_the_seat_back_is_logged_with_the_past_players_token(
    fx01_grid: Grid,
) -> None:
    outcome = seat_back(ana_timed_out(fx01_grid))

    assert len(outcome.entries) == 1
    assert outcome.entries[0].resume_token == TA


def test_ac7_the_seat_back_replies_with_the_snapshot_of_the_player(
    fx01_grid: Grid,
) -> None:
    outcome = seat_back(ana_timed_out(fx01_grid))

    snapshot = snapshot_of(outcome)
    assert (snapshot.you, snapshot.resume_token) == (ANA, TA)
    assert outcome.close_sender is False


def test_ac7_after_the_seat_back_the_player_is_last_and_no_longer_past(
    fx01_grid: Grid,
) -> None:
    state = seat_back(ana_timed_out(fx01_grid)).state

    assert player_ids(state) == [BOB, CY, ANA]
    assert player_of(state, ANA).joined_seq == 8
    assert state.past_players == ()


def test_ac7_the_seat_back_keeps_the_players_letters(fx01_grid: Grid) -> None:
    state = seat_back(ana_timed_out(fx01_grid)).state

    seated_back = player_of(state, ANA)
    cell = cell_of(state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_by) == (
        "T",
        seated_back.player_id,
        seated_back.player_id,
    )


def test_ac7_the_seat_back_uses_neither_the_new_id_nor_the_new_token(
    fx01_grid: Grid,
) -> None:
    state = seat_back(ana_timed_out(fx01_grid)).state

    assert NEW_PLAYER_ID not in player_ids(state)
    for player in state.players:
        assert player.resume_token != NEW_TOKEN


def test_ac7_the_token_of_a_player_seated_back_is_a_members_token(
    fx01_grid: Grid,
) -> None:
    state = seat_back(ana_timed_out(fx01_grid)).state

    assert nock.room.member_id(state, TA) == ANA


def test_ac7_replaying_the_whole_log_gives_the_same_players_and_past_players(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    seat_back(run)

    replayed = run.replayed()

    assert replayed.past_players == run.state.past_players
    assert players_summary(replayed) == players_summary(run.state)


def test_ac7_the_record_of_a_player_seated_back_is_a_new_one_with_their_id(
    fx01_grid: Grid,
) -> None:
    state = seat_back(ana_timed_out(fx01_grid)).state

    assert player_of(state, ANA) == PlayerRecord(
        player_id=ANA,
        resume_token=TA,
        nickname="ANA",
        colour=0,
        is_host=False,
        joined_seq=8,
        last_input_at=SEAT_BACK_AT,
        last_seen_at=SEAT_BACK_AT,
    )


def test_ac7_a_seat_back_changes_nothing_else_in_the_room(fx01_grid: Grid) -> None:
    run = ana_timed_out(fx01_grid)
    before = run.state

    outcome = seat_back(run)

    assert snapshot_of(outcome).you == ANA
    after = outcome.state
    assert after.cells == before.cells
    assert after.settings == before.settings
    assert after.reveal_budget == before.reveal_budget
    assert after.reveals_used == before.reveals_used
    assert after.removed_tokens == before.removed_tokens
    assert after.players[:2] == before.players


def test_ac7_the_snapshot_of_a_seat_back_holds_the_players_chat_lines(
    fx01_grid: Grid,
) -> None:
    run = ana_wrote_t(fx01_grid)
    run.send(ANA, Chat(text="salut"), T0 + 5)
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)

    snapshot = snapshot_of(seat_back(run))

    assert snapshot.you == ANA
    assert snapshot.chat == (ChatMessage(seq=5, player_id=ANA, text="salut"),)


def test_ac7_an_offline_edit_on_the_players_own_cell_is_not_stale_after_it(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    seat_back(run)

    resent = run.send(
        ANA, EditLetter(row=1, column=0, letter="X", base_seq=3), SEAT_BACK_AT + 1
    )

    assert resent.reply == ()
    assert events_of(resent) == [
        LetterChanged(seq=9, row=1, column=0, letter="X", pencil=False, player_id=ANA)
    ]


def ana_alone_timed_out(grid: Grid) -> Run:
    """Ana alone writes `T` at t0 (the timer starts), leaves at t0 + 10, times out."""
    run = Run(grid)
    run.join_new("Ana", ANA, TA, T0)
    run.send(ANA, EditLetter(row=1, column=0, letter="T"), T0)
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    assert run.state.players == ()
    return run


def test_ac7_a_seat_back_resumes_a_paused_timer_as_any_join(fx01_grid: Grid) -> None:
    outcome = seat_back(ana_alone_timed_out(fx01_grid))

    snapshot = snapshot_of(outcome)
    assert snapshot.you == ANA
    assert (snapshot.timer_running, snapshot.timer_elapsed_ms) == (True, 10_000)
    assert outcome.state.timer_resumed_at == SEAT_BACK_AT


def test_ac7_a_player_seated_back_in_a_room_nobody_else_is_in_is_host(
    fx01_grid: Grid,
) -> None:
    outcome = seat_back(ana_alone_timed_out(fx01_grid))

    # seq 1 to 4: Ana's join, her `T`, her leave and her time-out.
    assert events_of(outcome) == [
        PlayerJoined(seq=5, player=view(ANA, "ANA", 0, is_host=True))
    ]


# ---- Fresh record --------------------------------------------------------------


def ana_flagged_and_timed_out(grid: Grid) -> Run:
    """Ana flags IDES (seq 5) before she leaves (seq 6); the tick: seq 7 and 8."""
    run = ana_wrote_t(grid)
    flagged = run.send(ANA, Flag(clue=IDES), T0 + 5)
    assert events_of(flagged) == [FlagChanged(seq=5, player_id=ANA, clue=IDES)]
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    return run


def test_ac7_the_flag_of_a_player_does_not_come_back_with_the_seat(
    fx01_grid: Grid,
) -> None:
    outcome = seat_back(ana_flagged_and_timed_out(fx01_grid))

    assert events_of(outcome) == [
        PlayerJoined(seq=9, player=view(ANA, "ANA", 0, is_host=False))
    ]
    assert player_of(outcome.state, ANA).flag is None
    assert snapshot_of(outcome).flags == ()


def test_ac7_an_undo_right_after_a_seat_back_has_nothing_to_undo(
    fx01_grid: Grid,
) -> None:
    run = ana_flagged_and_timed_out(fx01_grid)
    assert snapshot_of(seat_back(run)).you == ANA

    undo = run.send(ANA, Undo(), SEAT_BACK_AT)

    assert error_code_of(undo.reply) is ErrorCode.NOTHING_TO_UNDO
    assert undo.entries == ()
    cell = cell_of(undo.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("T", ANA, 4)


# ---- Muted ---------------------------------------------------------------------


def cy_muted_and_gone(grid: Grid) -> Run:
    """Ana, host, mutes Cy at t0 + 5 (seq 5); Cy's connection closes (seq 6)."""
    run = ana_wrote_t(grid)
    muted = run.send(ANA, MutePlayer(player_id=CY, muted=True), T0 + 5)
    assert events_of(muted) == [PlayerMuted(seq=5, player_id=CY, muted=True)]
    run.disconnect(CY, LEFT_AT)
    assert run.state.seq == 6
    return run


def test_ac7_a_muted_player_who_times_out_keeps_the_mute_in_the_past_record(
    fx01_grid: Grid,
) -> None:
    run = cy_muted_and_gone(fx01_grid)

    ticked = run.tick(TIMED_OUT_AT)

    assert events_of(ticked) == [
        PlayerLeft(seq=7, player_id=CY, reason=LeaveReason.TIMED_OUT)
    ]
    assert ticked.state.past_players == (past(CY, TC, "CY", 2, muted=True),)


def test_ac7_a_muted_player_comes_back_muted(fx01_grid: Grid) -> None:
    run = cy_muted_and_gone(fx01_grid)
    run.tick(TIMED_OUT_AT)

    outcome = seat_back(run, TC)

    assert events_of(outcome) == [
        PlayerJoined(seq=8, player=view(CY, "CY", 2, is_host=False, muted=True))
    ]
    snapshot = snapshot_of(outcome)
    assert snapshot.you == CY
    own_views = [player for player in snapshot.players if player.player_id == CY]
    assert [player.muted for player in own_views] == [True]


def test_ac7_the_chat_of_a_player_who_comes_back_muted_is_refused(
    fx01_grid: Grid,
) -> None:
    run = cy_muted_and_gone(fx01_grid)
    run.tick(TIMED_OUT_AT)
    assert snapshot_of(seat_back(run, TC)).you == CY

    chat = run.send(CY, Chat(text="salut"), SEAT_BACK_AT)

    assert error_code_of(chat.reply) is ErrorCode.MUTED
    assert chat.entries == ()


def test_ac7_a_host_unmutes_the_player_once_seated_back(fx01_grid: Grid) -> None:
    run = cy_muted_and_gone(fx01_grid)
    run.tick(TIMED_OUT_AT)
    assert snapshot_of(seat_back(run, TC)).you == CY
    run.send(CY, Chat(text="salut"), SEAT_BACK_AT)

    unmuted = run.send(ANA, MutePlayer(player_id=CY, muted=False), SEAT_BACK_AT + 1)
    chat = run.send(CY, Chat(text="salut"), SEAT_BACK_AT + 2)

    assert events_of(unmuted) == [PlayerMuted(seq=9, player_id=CY, muted=False)]
    assert events_of(chat) == [ChatMessage(seq=10, player_id=CY, text="salut")]


def test_ac7_replaying_the_muted_run_gives_the_same_past_players_and_mute(
    fx01_grid: Grid,
) -> None:
    run = cy_muted_and_gone(fx01_grid)
    run.tick(TIMED_OUT_AT)
    after_the_time_out = run.replayed()
    expected_past_players = run.state.past_players

    seat_back(run, TC)
    after_the_seat_back = run.replayed()

    assert after_the_time_out.past_players == expected_past_players
    assert player_of(after_the_seat_back, CY).muted is True
    assert after_the_seat_back.past_players == ()


def test_ac7_a_muted_player_seated_back_in_an_empty_room_is_host_and_stays_muted(
    fx01_grid: Grid,
) -> None:
    run = Run(fx01_grid)
    run.join_new("Ana", ANA, TA, T0)
    run.join_new("Bob", BOB, TB, T0)
    run.send(ANA, MutePlayer(player_id=BOB, muted=True), T0 + 5)
    run.disconnect(BOB, LEFT_AT)
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    assert run.state.players == ()

    outcome = seat_back(run, TB)

    joined = events_of(outcome)
    assert len(joined) == 1
    assert isinstance(joined[0], PlayerJoined)
    assert (joined[0].player.player_id, joined[0].player.is_host) == (BOB, True)
    assert joined[0].player.muted is True


# ---- Colour taken, nickname taken ----------------------------------------------


def test_ac7_a_colour_taken_meanwhile_gives_the_lowest_free_one(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    run.join_new("Dan", DAN, TD, T0 + 320)
    assert player_of(run.state, DAN).colour == 0

    outcome = seat_back(run)

    assert events_of(outcome) == [
        PlayerJoined(seq=9, player=view(ANA, "ANA", 3, is_host=False))
    ]


def test_ac7_a_nickname_taken_meanwhile_gets_spec_012s_suffix(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out(fx01_grid)
    run.join_new("ana", "p5", "token-of-lower-ana-5", T0 + 320)
    newcomer = player_of(run.state, "p5")
    assert (newcomer.nickname, newcomer.colour) == ("ANA", 0)

    outcome = seat_back(run)

    assert events_of(outcome) == [
        PlayerJoined(seq=9, player=view(ANA, "ANA 2", 3, is_host=False))
    ]


# ---- Full, locked, removed -----------------------------------------------------


def ana_timed_out_in_a_full_room(grid: Grid) -> Run:
    """After the time-out six more players join: `players` holds 8."""
    run = ana_timed_out(grid)
    for number, nickname in enumerate(MORE_PLAYERS, start=4):
        run.join_new(nickname, f"p{number}", f"token-of-player-{number:04d}", T0 + 320)
    assert len(run.state.players) == 8
    return run


def test_ac7_a_full_room_refuses_the_seat_back(fx01_grid: Grid) -> None:
    run = ana_timed_out_in_a_full_room(fx01_grid)
    before = run.state

    outcome = seat_back(run)

    assert error_code_of(outcome.reply) is ErrorCode.ROOM_FULL
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert outcome.state == before


def test_ac7_after_a_refusal_in_a_full_room_the_player_is_still_a_member(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out_in_a_full_room(fx01_grid)

    state = seat_back(run).state

    assert state.past_players == (anas_past_record(),)
    assert nock.room.member_id(state, TA) == ANA


def ana_timed_out_in_a_locked_room(grid: Grid) -> Run:
    """After the time-out Bob, host since then, locks the room."""
    run = ana_timed_out(grid)
    locked = run.send(BOB, LockRoom(locked=True), T0 + 320)
    assert locked.reply == ()
    assert run.state.settings.locked is True
    return run


def test_ac7_a_locked_room_refuses_the_seat_back(fx01_grid: Grid) -> None:
    run = ana_timed_out_in_a_locked_room(fx01_grid)
    before = run.state

    outcome = seat_back(run)

    assert error_code_of(outcome.reply) is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert outcome.state == before
    assert outcome.state.past_players == (anas_past_record(),)
    assert nock.room.member_id(outcome.state, TA) == ANA


def test_ac7_once_the_room_is_unlocked_the_same_join_seats_the_player_back(
    fx01_grid: Grid,
) -> None:
    run = ana_timed_out_in_a_locked_room(fx01_grid)
    seat_back(run)
    run.send(BOB, LockRoom(locked=False), T0 + 410)

    outcome = seat_back(run, now=T0 + 420)

    assert snapshot_of(outcome).you == ANA
    assert player_of(outcome.state, ANA).nickname == "ANA"


def test_ac7_a_time_out_in_the_join_itself_still_seats_the_player_back(
    fx01_grid: Grid,
) -> None:
    run = ana_wrote_t(fx01_grid)
    run.disconnect(ANA, LEFT_AT)

    outcome = seat_back(run, now=IN_THE_WINDOW_LIMIT)

    assert events_of(outcome) == [
        PlayerLeft(seq=6, player_id=ANA, reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=7, player_id=BOB),
        PlayerJoined(seq=8, player=view(ANA, "ANA", 0, is_host=False)),
    ]
    assert snapshot_of(outcome).you == ANA


def ana_locked_then_gone(grid: Grid) -> Run:
    """Ana, still host, locks the room (seq 5), then leaves (seq 6); no tick."""
    run = ana_wrote_t(grid)
    run.send(ANA, LockRoom(locked=True), T0 + 5)
    run.disconnect(ANA, LEFT_AT)
    assert run.state.seq == 6
    return run


def test_ac7_a_locked_room_refuses_the_join_that_times_the_player_out(
    fx01_grid: Grid,
) -> None:
    run = ana_locked_then_gone(fx01_grid)

    outcome = seat_back(run, now=IN_THE_WINDOW_LIMIT)

    assert events_of(outcome) == [
        PlayerLeft(seq=7, player_id=ANA, reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=8, player_id=BOB),
    ]
    assert error_code_of(outcome.reply) is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True


def test_ac7_the_time_out_of_a_refused_join_is_kept_in_the_state(
    fx01_grid: Grid,
) -> None:
    run = ana_locked_then_gone(fx01_grid)

    state = seat_back(run, now=IN_THE_WINDOW_LIMIT).state

    assert state.past_players == (anas_past_record(),)
    assert player_of(state, BOB).is_host is True
    assert nock.room.member_id(state, TA) == ANA


def test_ac7_after_the_refused_join_and_an_unlock_the_join_seats_the_player_back(
    fx01_grid: Grid,
) -> None:
    run = ana_locked_then_gone(fx01_grid)
    seat_back(run, now=IN_THE_WINDOW_LIMIT)
    run.send(BOB, LockRoom(locked=False), T0 + 320)

    outcome = seat_back(run, now=T0 + 330)

    assert snapshot_of(outcome).you == ANA
    assert player_of(outcome.state, ANA).colour == 0


def test_ac7_a_removed_player_is_never_seated_back(fx01_grid: Grid) -> None:
    run = ana_wrote_t(fx01_grid)
    run.send(ANA, RemovePlayer(player_id=CY), T0 + 5)
    run.disconnect(ANA, LEFT_AT)
    run.tick(TIMED_OUT_AT)

    outcome = seat_back(run, TC)

    assert error_code_of(outcome.reply) is ErrorCode.REMOVED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert outcome.state.past_players == (anas_past_record(),)


# ---- Vote during the seat back -------------------------------------------------

LETTER_1_1 = CellTarget(row=1, column=1)
VOTE_MODE = ChangeSettings(
    help_mode=HelpMode.VOTE, reveal_budget=RevealBudget(letters=5, words=1)
)


def vote_opened_while_ana_is_away(grid: Grid) -> tuple[Run, Outcome]:
    """Bob, host since the time-out, sets the help mode `vote` at t0 + 380 (seq 8),
    then asks for the reveal of (1, 1) at t0 + 390, which opens vote 1 (seq 9).

    Returns:
        The run and the step of the reveal request.
    """
    run = ana_timed_out(grid)
    changed = run.send(BOB, VOTE_MODE, T0 + 380)
    assert changed.reply == ()
    assert run.state.seq == 8
    requested = run.send(BOB, Reveal(target=LETTER_1_1), T0 + 390)
    return run, requested


def vote_one() -> VoteOpened:
    return VoteOpened(
        seq=9,
        vote_id=1,
        player_id=BOB,
        request=Reveal(target=LETTER_1_1),
        timeout_seconds=20,
        eligible_voters=2,
    )


def ana_seated_back_during_the_vote(grid: Grid) -> Run:
    """The vote run until Ana's seat back at t0 + 395, which must succeed."""
    run, _ = vote_opened_while_ana_is_away(grid)
    assert snapshot_of(seat_back(run, now=T0 + 395)).you == ANA
    return run


def test_ac7_a_vote_opened_while_the_player_is_away_counts_only_the_players(
    fx01_grid: Grid,
) -> None:
    run, requested = vote_opened_while_ana_is_away(fx01_grid)

    assert events_of(requested) == [vote_one()]
    vote = run.state.open_vote
    assert vote is not None
    assert vote.eligible == (BOB, CY)


def test_ac7_a_player_seated_back_during_a_vote_gets_it_in_the_snapshot(
    fx01_grid: Grid,
) -> None:
    run, _ = vote_opened_while_ana_is_away(fx01_grid)

    outcome = seat_back(run, now=T0 + 395)

    assert events_of(outcome) == [
        PlayerJoined(seq=10, player=view(ANA, "ANA", 0, is_host=False))
    ]
    assert snapshot_of(outcome).open_vote == vote_one()


def test_ac7_the_ballot_of_a_player_seated_back_during_a_vote_changes_nothing(
    fx01_grid: Grid,
) -> None:
    run = ana_seated_back_during_the_vote(fx01_grid)

    ballot = run.send(ANA, Vote(vote_id=1, yes=True), T0 + 396)

    assert (ballot.entries, ballot.reply) == ((), ())
    vote = run.state.open_vote
    assert vote is not None
    assert (vote.eligible, vote.yes, vote.no) == ((BOB, CY), (BOB,), ())


def test_ac7_the_vote_passes_on_its_two_eligible_voters(fx01_grid: Grid) -> None:
    run = ana_seated_back_during_the_vote(fx01_grid)
    run.send(ANA, Vote(vote_id=1, yes=True), T0 + 396)

    passed = run.send(CY, Vote(vote_id=1, yes=True), T0 + 397)

    assert events_of(passed) == [
        VoteClosed(
            seq=11,
            vote_id=1,
            outcome=VoteOutcome.PASSED,
            yes_votes=2,
            eligible_voters=2,
        ),
        RevealResult(
            seq=12,
            player_id=BOB,
            target=LETTER_1_1,
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=13, row=1, column=1, letter="A", revealed=True),
    ]
