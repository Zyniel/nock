"""Tests of spec 018, AC-1: `replay` and `after_restart`.

Each rule of the replay table of the spec, event by event, then the step that a
room loaded in a new process goes through. Both are functions of `nock.room`,
tested without a store. The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    Direction,
    EditLetter,
    GridFullWrong,
    HelpMode,
    HostChanged,
    Join,
    LeaveReason,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Selection,
    SettingsChanged,
)
from nock.room import (
    CellState,
    LogEntry,
    PlayerRecord,
    RoomState,
    UndoEntry,
    after_restart,
    handle_message,
    join_room,
    new_room,
    replay,
)
from spec018_harness import (
    FIRST_TOKEN,
    LATER,
    NOW,
    ROOM_CODE,
    SECOND_TOKEN,
    START_TIME,
    cell_state,
    grid_from_text,
    letter_changed,
    other_cells,
    player_record,
    resume_tokens,
    token_of,
    two_player_room,
    with_cell,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-1: replay ----


def test_ac1_replay_player_joined_appends_a_record_with_the_logged_token(
    fx01_grid: Grid,
) -> None:
    empty = new_room(ROOM_CODE, fx01_grid, START_TIME)
    view = PlayerView(
        player_id="p1",
        nickname="Ana",
        colour=3,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )
    entry = LogEntry(
        at=NOW, event=PlayerJoined(seq=1, player=view), resume_token=FIRST_TOKEN
    )

    replayed = replay(empty, entry)

    assert replayed.seq == 1
    assert replayed.players == (
        PlayerRecord(
            player_id="p1",
            resume_token=FIRST_TOKEN,
            nickname="Ana",
            colour=3,
            is_host=True,
            muted=False,
            state=PlayerState.ACTIVE,
            joined_seq=1,
            last_input_at=NOW,
            last_seen_at=NOW,
            disconnected_at=None,
            selection=None,
            recent_edits=(),
            last_edit=None,
        ),
    )


def test_ac1_replay_a_second_join_goes_after_the_first(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)
    view = PlayerView(
        player_id="p3",
        nickname="Cleo",
        colour=2,
        state=PlayerState.ACTIVE,
        is_host=False,
        muted=False,
        selection=None,
    )

    replayed = replay(
        base,
        LogEntry(
            at=LATER, event=PlayerJoined(seq=3, player=view), resume_token=token_of(3)
        ),
    )

    assert [player.player_id for player in replayed.players] == ["p1", "p2", "p3"]
    third = player_record(replayed, "p3")
    assert third.resume_token == token_of(3)
    assert third.joined_seq == 3
    assert third.last_input_at == LATER
    assert third.last_seen_at == LATER
    assert replayed.players[:2] == base.players


def test_ac1_replay_player_state_changed_sets_the_state_and_disconnected_at(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)
    gone = replay(
        base,
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=3, player_id="p2", state=PlayerState.DISCONNECTED
            ),
        ),
    )

    back = replay(
        gone,
        LogEntry(
            at=LATER + 5,
            event=PlayerStateChanged(seq=4, player_id="p2", state=PlayerState.ACTIVE),
        ),
    )

    assert gone.seq == 3
    assert player_record(gone, "p2").state is PlayerState.DISCONNECTED
    assert player_record(gone, "p2").disconnected_at == LATER
    assert player_record(gone, "p1") == player_record(base, "p1")
    assert back.seq == 4
    assert player_record(back, "p2").state is PlayerState.ACTIVE
    assert player_record(back, "p2").disconnected_at is None


def test_ac1_replay_player_left_removed_drops_the_player_and_bans_the_token(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)

    replayed = replay(
        base,
        LogEntry(
            at=LATER,
            event=PlayerLeft(seq=3, player_id="p2", reason=LeaveReason.REMOVED),
        ),
    )

    assert replayed.seq == 3
    assert [player.player_id for player in replayed.players] == ["p1"]
    assert replayed.removed_tokens == (SECOND_TOKEN,)


@pytest.mark.parametrize("reason", [LeaveReason.LEFT, LeaveReason.TIMED_OUT])
def test_ac1_replay_player_left_for_another_reason_does_not_ban_the_token(
    fx01_grid: Grid, reason: LeaveReason
) -> None:
    replayed = replay(
        two_player_room(fx01_grid),
        LogEntry(at=LATER, event=PlayerLeft(seq=3, player_id="p2", reason=reason)),
    )

    assert [player.player_id for player in replayed.players] == ["p1"]
    assert replayed.removed_tokens == ()


def test_ac1_replay_letter_changed_writes_the_cell_and_remembers_the_old_one(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=1,
            letter="B",
            pencil=True,
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    replayed = replay(
        seeded, LogEntry(at=NOW, event=letter_changed(3, 1, 1, "A", "p1"))
    )

    assert replayed.seq == 3
    assert cell_state(replayed, 1, 1) == CellState(
        row=1, column=1, letter="A", author="p1", changed_seq=3, changed_by="p1"
    )
    assert player_record(replayed, "p1").last_edit == UndoEntry(
        row=1, column=1, seq=3, letter="B", pencil=True, author="p2"
    )
    assert player_record(replayed, "p2").last_edit is None
    assert other_cells(replayed, 1, 1) == other_cells(seeded, 1, 1)


def test_ac1_replay_an_erase_clears_the_author_and_remembers_the_letter(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=0, letter="T", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    replayed = replay(
        seeded, LogEntry(at=NOW, event=letter_changed(3, 1, 0, None, "p1"))
    )

    assert cell_state(replayed, 1, 0) == CellState(
        row=1, column=0, changed_seq=3, changed_by="p1"
    )
    assert player_record(replayed, "p1").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter="T", pencil=False, author="p2"
    )


def test_ac1_replay_an_undo_entry_clears_last_edit(fx01_grid: Grid) -> None:
    typed = replay(
        two_player_room(fx01_grid),
        LogEntry(at=NOW, event=letter_changed(3, 1, 0, "T", "p1")),
    )
    assert player_record(typed, "p1").last_edit is not None

    undone = replay(
        typed,
        LogEntry(at=NOW, event=letter_changed(4, 1, 0, None, "p1"), undo=True),
    )

    assert undone.seq == 4
    assert player_record(undone, "p1").last_edit is None
    assert cell_state(undone, 1, 0) == CellState(
        row=1, column=0, changed_seq=4, changed_by="p1"
    )


def test_ac1_replay_cell_locked_by_a_check_keeps_the_letter_and_locks_it(
    fx01_grid: Grid,
) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1,
            column=2,
            letter="X",
            author="p2",
            wrong=True,
            changed_seq=2,
            changed_by="p2",
        ),
    )

    replayed = replay(
        seeded,
        LogEntry(
            at=NOW, event=CellLocked(seq=3, row=1, column=2, letter="M", revealed=False)
        ),
    )

    cell = cell_state(replayed, 1, 2)
    assert replayed.seq == 3
    assert (cell.letter, cell.locked, cell.revealed) == ("M", True, False)
    assert (cell.changed_seq, cell.changed_by) == (3, None)


def test_ac1_replay_cell_locked_by_a_reveal_has_no_author(fx01_grid: Grid) -> None:
    seeded = with_cell(
        two_player_room(fx01_grid),
        CellState(
            row=1, column=2, letter="X", author="p2", changed_seq=2, changed_by="p2"
        ),
    )

    replayed = replay(
        seeded,
        LogEntry(
            at=NOW, event=CellLocked(seq=3, row=1, column=2, letter="M", revealed=True)
        ),
    )

    assert cell_state(replayed, 1, 2) == CellState(
        row=1,
        column=2,
        letter="M",
        pencil=False,
        author=None,
        locked=True,
        revealed=True,
        wrong=False,
        changed_seq=3,
        changed_by=None,
    )


def test_ac1_replay_settings_changed_sets_the_settings_and_the_budget(
    fx01_grid: Grid,
) -> None:
    settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=9, words=3),
        locked=True,
    )
    left = RevealBudget(letters=4, words=2)

    replayed = replay(
        two_player_room(fx01_grid),
        LogEntry(
            at=NOW,
            event=SettingsChanged(
                seq=3, player_id="p1", settings=settings, reveal_budget=left
            ),
        ),
    )

    assert replayed.seq == 3
    assert replayed.settings == settings
    assert replayed.reveal_budget == left


def test_ac1_replay_host_changed_moves_the_host_role(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)
    assert player_record(base, "p1").is_host is True

    replayed = replay(base, LogEntry(at=NOW, event=HostChanged(seq=3, player_id="p2")))

    assert replayed.seq == 3
    assert player_record(replayed, "p1").is_host is False
    assert player_record(replayed, "p2").is_host is True


def test_ac1_replay_player_muted_sets_and_clears_the_flag(fx01_grid: Grid) -> None:
    base = two_player_room(fx01_grid)

    muted = replay(
        base,
        LogEntry(at=NOW, event=PlayerMuted(seq=3, player_id="p2", muted=True)),
    )
    unmuted = replay(
        muted,
        LogEntry(at=NOW, event=PlayerMuted(seq=4, player_id="p2", muted=False)),
    )

    assert player_record(muted, "p2").muted is True
    assert player_record(muted, "p1").muted is False
    assert player_record(unmuted, "p2").muted is False
    assert unmuted.seq == 4


def test_ac1_replay_an_event_of_a_later_spec_only_moves_the_seq(
    fx01_grid: Grid,
) -> None:
    base = two_player_room(fx01_grid)

    replayed = replay(base, LogEntry(at=NOW, event=GridFullWrong(seq=3)))

    assert replayed == base.model_copy(update={"seq": 3})


# ---- AC-1: after_restart ----


def three_player_room_with_live_data(grid: Grid) -> RoomState:
    """p1 active with edits, p2 already disconnected, p3 idle with a selection."""
    state = two_player_room(grid)
    third = join_room(
        state, Join(nickname="Cleo", resume_token=None), NOW, "p3", token_of(3)
    )
    state = third.state
    edited = handle_message(state, "p1", EditLetter(row=1, column=0, letter="T"), NOW)
    state = edited.state
    selection = Selection(row=1, column=1, direction=Direction.ACROSS)
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == "p1":
            players.append(player.model_copy(update={"selection": selection}))
        elif player.player_id == "p2":
            players.append(
                player.model_copy(
                    update={"state": PlayerState.DISCONNECTED, "disconnected_at": 500.0}
                )
            )
        else:
            players.append(
                player.model_copy(
                    update={"state": PlayerState.IDLE, "selection": selection}
                )
            )
    return state.model_copy(update={"players": tuple(players)})


def test_ac1_after_restart_disconnects_every_player_who_was_not(
    fx01_grid: Grid,
) -> None:
    before = three_player_room_with_live_data(fx01_grid)
    assert before.seq == 4
    assert len(player_record(before, "p1").recent_edits) == 1

    outcome = after_restart(before, LATER)

    first = player_record(outcome.state, "p1")
    third = player_record(outcome.state, "p3")
    assert first.state is PlayerState.DISCONNECTED
    assert third.state is PlayerState.DISCONNECTED
    for restarted in (first, third):
        assert restarted.disconnected_at == LATER
        assert restarted.selection is None
        assert restarted.recent_edits == ()
    second = player_record(outcome.state, "p2")
    assert second == player_record(before, "p2")
    assert second.disconnected_at == 500.0


def test_ac1_after_restart_logs_one_state_change_per_player_in_players_order(
    fx01_grid: Grid,
) -> None:
    before = three_player_room_with_live_data(fx01_grid)

    outcome = after_restart(before, LATER)

    assert outcome.entries == (
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=5, player_id="p1", state=PlayerState.DISCONNECTED
            ),
        ),
        LogEntry(
            at=LATER,
            event=PlayerStateChanged(
                seq=6, player_id="p3", state=PlayerState.DISCONNECTED
            ),
        ),
    )
    assert outcome.state.seq == 6
    assert outcome.reply == ()
    assert outcome.to_others == ()
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac1_after_restart_keeps_the_grid_and_the_tokens(fx01_grid: Grid) -> None:
    before = three_player_room_with_live_data(fx01_grid)

    after = after_restart(before, LATER).state

    assert [player.state for player in after.players] == [PlayerState.DISCONNECTED] * 3
    assert after.cells == before.cells
    assert resume_tokens(after) == resume_tokens(before)
    assert [player.nickname for player in after.players] == ["Ana", "Bob", "Cleo"]
    assert player_record(after, "p1").last_edit == player_record(before, "p1").last_edit


def test_ac1_after_restart_of_a_room_with_nobody_to_disconnect_changes_nothing(
    fx01_grid: Grid,
) -> None:
    empty = new_room(ROOM_CODE, fx01_grid, START_TIME)
    gone = after_restart(three_player_room_with_live_data(fx01_grid), LATER).state
    assert [player.state for player in gone.players] == [PlayerState.DISCONNECTED] * 3

    for state in (empty, gone):
        outcome = after_restart(state, LATER + 10)
        assert outcome.entries == ()
        assert outcome.state == state
