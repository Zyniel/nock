"""Tests of spec 028, AC-1 to AC-4, AC-7 and AC-8 (Python part): `build_recap` and
`public_recap` on plays of the rules.

The plays are the spec's `PLAY_R` (checks and reveals) and `PLAY_W` (word
completions), played with `handle_message` (see `spec028_harness`). Every expected
number is the spec's, or follows from the spec's rules for the small plays added
here for the edge cases (erase, undo, pencil, wrong letters, departed, rejoined
and late players, a second `grid_solved`).

Reading of "Players" for a hand-built log: an author with no `player_joined` has a
`None` nickname and is left out of the team (a `PublicRecap` team holds only
nicknames).

A player seated back with the same id (spec 032 AC-7) is a hand-built log here, as
`join_room` does not seat a player back yet. A player who comes back without their
token is played with the rules: a time-out (`disconnect_player`, then `tick` past the
resume window), then a join under a new id.
"""

from __future__ import annotations

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Check,
    ConfirmPencil,
    GridSolved,
    GridTarget,
    LeaveReason,
    PlayerJoined,
    PlayerLeft,
    Reveal,
    Vote,
)
from nock.recap import PublicRecap, Recap, RecapPlayer, build_recap, public_recap
from nock.room import LogEntry, RoomConfig, disconnect_player, tick
from spec028_harness import (
    NOW,
    SHARE_TOKEN,
    TAMIS,
    THIRD_TOKEN,
    Game,
    pencil_message,
    play_r,
    play_w,
    remove_message,
    renumbered,
    undo_message,
    vote_mode_message,
)

# A player disconnected at NOW times out at the first tick past the resume window
# (spec 017); the other delays are long, so that this tick does nothing else.
RESUME_WINDOW_SECONDS = 300.0
TIME_OUT_ONLY_CONFIG = RoomConfig(
    resume_window_seconds=RESUME_WINDOW_SECONDS,
    silence_timeout_seconds=600.0,
    idle_after_seconds=600.0,
)
BACK_AT = NOW + RESUME_WINDOW_SECONDS + 1.0
AFTER_THE_SOLVE = NOW + 800.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def recap_of(game: Game) -> Recap:
    return build_recap(game.state, game.log)


def counts(recap: Recap) -> dict[str, tuple[int, int]]:
    """The letters and words of each player, by player id."""
    found: dict[str, tuple[int, int]] = {}
    for player in recap.players:
        found[player.player_id] = (player.letters, player.words)
    return found


# ---- AC-1: time, checks, reveals ----


def test_ac1_time_checks_and_reveals_after_play_r(fx01_grid: Grid) -> None:
    recap = recap_of(play_r(fx01_grid))

    assert recap.elapsed_ms == 754000
    assert recap.checks == 2
    assert recap.letter_reveals == 1
    assert recap.word_reveals == 1


def test_ac1_grid_number_and_grid_sizes_after_play_r(fx01_grid: Grid) -> None:
    recap = recap_of(play_r(fx01_grid))

    assert recap.grid_number == 1
    assert recap.letter_cells == 18
    assert recap.word_count == 8


def test_ac1_the_whole_recap_of_play_r(fx01_grid: Grid) -> None:
    recap = recap_of(play_r(fx01_grid))

    assert recap == Recap(
        grid_number=1,
        elapsed_ms=754000,
        checks=2,
        letter_reveals=1,
        word_reveals=1,
        revealed_letters=5,
        letter_cells=18,
        word_count=8,
        players=(
            RecapPlayer(
                player_id="p1", nickname="Ana", letters=8, words=4, removed=False
            ),
            RecapPlayer(
                player_id="p2", nickname="Bob", letters=5, words=3, removed=False
            ),
        ),
        share_path="/recap/" + SHARE_TOKEN,
    )


def test_ac1_a_game_without_check_or_reveal_counts_zero(fx01_grid: Grid) -> None:
    game = play_w(fx01_grid)

    recap = recap_of(game)

    assert (recap.checks, recap.letter_reveals, recap.word_reveals) == (0, 0, 0)


def test_ac1_checks_of_every_scope_count(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.write("p1", (1, 0), "T")
    game.send("p1", Check(target=CellTarget(row=1, column=0)))
    game.send("p1", Check(target=TAMIS))
    game.send("p2", Check(target=GridTarget()))
    game.finish("p1")

    assert recap_of(game).checks == 3


def test_ac1_a_check_approved_by_a_vote_counts_once(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.send("p1", vote_mode_message())
    game.write("p1", (1, 0), "T")
    game.send("p2", Check(target=GridTarget()))
    game.send("p1", Vote(vote_id=1, yes=True))
    game.finish("p1")

    assert recap_of(game).checks == 1


def test_ac1_a_vote_that_only_opened_counts_nothing(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.send("p1", vote_mode_message())
    game.send("p2", Check(target=GridTarget()))
    game.finish("p1")

    assert recap_of(game).checks == 0


# ---- AC-2: letters of each player ----


def test_ac2_players_and_letters_after_play_r(fx01_grid: Grid) -> None:
    recap = recap_of(play_r(fx01_grid))

    assert recap.players == (
        RecapPlayer(player_id="p1", nickname="Ana", letters=8, words=4, removed=False),
        RecapPlayer(player_id="p2", nickname="Bob", letters=5, words=3, removed=False),
    )


def test_ac2_players_and_letters_after_play_w(fx01_grid: Grid) -> None:
    recap = recap_of(play_w(fx01_grid))

    assert recap.players == (
        RecapPlayer(player_id="p1", nickname="Ana", letters=10, words=3, removed=False),
        RecapPlayer(player_id="p2", nickname="Bob", letters=8, words=5, removed=False),
    )


def test_ac2_an_undo_credits_the_undoer(fx01_grid: Grid) -> None:
    recap = recap_of(play_w(fx01_grid, undo_variant=True))

    assert counts(recap)["p1"][0] == 9
    assert counts(recap)["p2"][0] == 9


def test_ac2_a_pencil_confirmation_credits_the_confirmer(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.send("p1", pencil_message((1, 0), "T"))
    game.send("p2", ConfirmPencil(row=1, column=0))
    game.finish("p1")

    assert counts(recap_of(game)) == {"p1": (17, 8), "p2": (1, 0)}


def test_ac2_a_check_lock_keeps_the_author(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.write("p2", (1, 0), "T")
    game.send("p1", Check(target=GridTarget()))
    game.finish("p1")

    assert counts(recap_of(game))["p2"][0] == 1


def test_ac2_a_departed_player_keeps_a_row_and_the_removed_flag(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.join("Cy", "p3", THIRD_TOKEN)
    game.write("p3", (1, 0), "T")
    game.send("p1", remove_message("p3"))
    game.finish("p1")

    recap = recap_of(game)

    assert recap.players == (
        RecapPlayer(player_id="p1", nickname="Ana", letters=17, words=8, removed=False),
        RecapPlayer(player_id="p2", nickname="Bob", letters=0, words=0, removed=False),
        RecapPlayer(player_id="p3", nickname="Cy", letters=1, words=0, removed=True),
    )


def test_ac2_a_player_joined_twice_keeps_the_first_join_place_and_the_last_nickname(
    fx01_grid: Grid,
) -> None:
    game = play_w(fx01_grid)
    first_join = game.log[0]
    assert isinstance(first_join.event, PlayerJoined)
    assert first_join.event.player.player_id == "p1"
    # Spec 032's seat back is built by hand: p1 (Ana), who joined before p2, times
    # out after seq 9 and joins again with the same id as Anna, then writes on.
    renamed = first_join.event.player.model_copy(update={"nickname": "Anna"})
    second_join_event = PlayerJoined(seq=1, player=renamed)
    left = LogEntry(
        at=NOW,
        event=PlayerLeft(seq=1, player_id="p1", reason=LeaveReason.TIMED_OUT),
    )
    second_join = first_join.model_copy(update={"event": second_join_event})
    log = renumbered([*game.log[:9], left, second_join, *game.log[9:]])
    state = game.state.model_copy(update={"seq": len(log)})

    recap = build_recap(state, log)

    assert recap.players == (
        RecapPlayer(
            player_id="p1", nickname="Anna", letters=10, words=3, removed=False
        ),
        RecapPlayer(player_id="p2", nickname="Bob", letters=8, words=5, removed=False),
    )
    assert public_recap(recap).team == ("Anna", "Bob")


def test_ac2_a_player_back_under_a_new_id_has_a_row_but_one_name_in_the_team(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.write("p2", (1, 0), "T")
    game.keep(disconnect_player(game.state, "p2", NOW))
    game.keep(tick(game.state, BACK_AT, TIME_OUT_ONLY_CONFIG))
    assert [player.player_id for player in game.state.players] == ["p1"]
    # Bob comes back without his token (another device): a new id, the same name.
    game.join("Bob", "p3", THIRD_TOKEN, BACK_AT)
    game.write("p3", (1, 1), "A", BACK_AT)
    game.finish("p1")

    recap = recap_of(game)

    assert recap.players == (
        RecapPlayer(player_id="p1", nickname="Ana", letters=16, words=8, removed=False),
        RecapPlayer(player_id="p2", nickname="Bob", letters=1, words=0, removed=False),
        RecapPlayer(player_id="p3", nickname="Bob", letters=1, words=0, removed=False),
    )
    assert public_recap(recap).team == ("Ana", "Bob")


def test_ac2_an_author_with_no_player_joined_is_listed_last_with_no_nickname(
    fx01_grid: Grid,
) -> None:
    game = play_w(fx01_grid)
    log = renumbered(game.log[:1] + game.log[2:])
    state = game.state.model_copy(update={"seq": len(log)})

    recap = build_recap(state, log)

    assert recap.players == (
        RecapPlayer(player_id="p1", nickname="Ana", letters=10, words=3, removed=False),
        RecapPlayer(player_id="p2", nickname=None, letters=8, words=5, removed=False),
    )
    assert public_recap(recap).team == ("Ana",)


# ---- AC-3: words completed by each player ----


def test_ac3_words_after_play_w(fx01_grid: Grid) -> None:
    recap = recap_of(play_w(fx01_grid))

    assert counts(recap) == {"p1": (10, 3), "p2": (8, 5)}


def test_ac3_words_after_play_r_and_a_revealed_word_counts_for_nobody(
    fx01_grid: Grid,
) -> None:
    recap = recap_of(play_r(fx01_grid))

    assert counts(recap) == {"p1": (8, 4), "p2": (5, 3)}
    assert sum(player.words for player in recap.players) == 7
    assert recap.word_count == 8


def test_ac3_a_word_completed_with_a_wrong_letter_counts_for_its_writer(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3)])
    game.write("p2", (1, 4), "X")
    game.finish("p1")

    assert counts(recap_of(game)) == {"p1": (18, 7), "p2": (0, 1)}


def test_ac3_an_undo_that_empties_a_full_word_takes_the_completer_away(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3)])
    game.write("p2", (1, 4), "S")
    game.send("p2", undo_message())
    game.write("p1", (1, 4), "S")
    game.finish("p1")

    assert counts(recap_of(game)) == {"p1": (18, 8), "p2": (0, 0)}


def test_ac3_a_pencil_letter_fills_a_word_and_its_confirmation_changes_nothing(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3)])
    game.send("p2", pencil_message((1, 4), "S"))
    game.send("p1", ConfirmPencil(row=1, column=4))
    game.finish("p1")

    assert counts(recap_of(game)) == {"p1": (18, 7), "p2": (0, 1)}


def test_ac3_an_edit_at_a_crossing_completes_both_words(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.write_all("p1", [(1, 0), (1, 1), (1, 2), (1, 3)])
    game.write_all("p1", [(2, 4), (3, 4), (4, 4)])
    game.write("p2", (1, 4), "S")
    game.finish("p1")

    # TAMIS and SENT both went to p2 with the one letter at (1, 4).
    assert counts(recap_of(game)) == {"p1": (17, 6), "p2": (1, 2)}


# ---- AC-4: revealed letters belong to nobody ----


def test_ac4_revealed_letters_and_the_sum_after_play_r(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)
    recap = recap_of(game)

    assert recap.revealed_letters == 5
    assert counts(recap) == {"p1": (8, 4), "p2": (5, 3)}
    sum_of_letters = sum(player.letters for player in recap.players)
    assert sum_of_letters + recap.revealed_letters == recap.letter_cells == 18
    for cell in game.state.cells:
        if (cell.row, cell.column) in [(0, 1), (4, 1), (4, 2), (4, 3), (4, 4)]:
            assert cell.revealed is True
            assert cell.author is None


def test_ac4_no_revealed_letter_after_play_w(fx01_grid: Grid) -> None:
    recap = recap_of(play_w(fx01_grid))

    assert recap.revealed_letters == 0
    assert sum(player.letters for player in recap.players) == 18 == recap.letter_cells


def test_ac4_a_reveal_over_a_typed_letter_is_credited_to_nobody(
    fx01_grid: Grid,
) -> None:
    game = Game(fx01_grid)
    game.write("p1", (1, 0), "T")
    game.send("p2", Reveal(target=CellTarget(row=1, column=0)))
    game.finish("p1")

    recap = recap_of(game)

    assert recap.revealed_letters == 1
    assert counts(recap)["p1"][0] == 17
    total = sum(player.letters for player in recap.players) + recap.revealed_letters
    assert total == recap.letter_cells


# ---- AC-7: a player who joins a solved room ----


def test_ac7_a_late_joiner_gets_the_same_recap_and_a_row_with_nothing(
    fx01_grid: Grid,
) -> None:
    game = play_r(fx01_grid)
    before = recap_of(game)

    game.join("Cy", "p3", THIRD_TOKEN, AFTER_THE_SOLVE)

    late_joiner = RecapPlayer(
        player_id="p3", nickname="Cy", letters=0, words=0, removed=False
    )
    expected = before.model_copy(update={"players": (*before.players, late_joiner)})
    assert recap_of(game) == expected


def test_ac7_a_late_joiner_is_in_the_team(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)

    game.join("Cy", "p3", THIRD_TOKEN, AFTER_THE_SOLVE)

    assert public_recap(recap_of(game)).team == ("Ana", "Bob", "Cy")


# ---- AC-8: only a solved room, public recap ----


def test_ac8_build_recap_refuses_the_room_one_step_before_the_solve(
    fx01_grid: Grid,
) -> None:
    game = play_r(fx01_grid)
    state = game.states_by_seq[32]
    assert state.solved is False

    with pytest.raises(ValueError, match=r".+"):
        build_recap(state, game.log[:32])


def test_ac8_build_recap_refuses_a_log_with_an_entry_left_out(
    fx01_grid: Grid,
) -> None:
    game = play_r(fx01_grid)
    log: list[LogEntry] = []
    for entry in game.log:
        if entry.event.seq != 12:
            log.append(entry)

    with pytest.raises(ValueError, match=r".+"):
        build_recap(game.state, log)


def test_ac8_build_recap_refuses_a_log_that_is_out_of_order(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)
    log = list(game.log)
    log[4], log[5] = log[5], log[4]

    with pytest.raises(ValueError, match=r".+"):
        build_recap(game.state, log)


def test_ac8_build_recap_refuses_a_log_without_grid_solved(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)
    state = game.state.model_copy(update={"seq": 33})

    with pytest.raises(ValueError, match=r".+"):
        build_recap(state, game.log[:33])


def test_ac8_build_recap_refuses_a_log_with_two_grid_solved(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)
    second_solve = LogEntry(
        at=AFTER_THE_SOLVE, event=GridSolved(seq=35, elapsed_ms=800_000)
    )
    state = game.state.model_copy(update={"seq": 35})

    with pytest.raises(ValueError, match=r".+"):
        build_recap(state, [*game.log, second_solve])


def test_ac8_build_recap_ignores_the_entries_after_the_state(fx01_grid: Grid) -> None:
    game = play_r(fx01_grid)
    extra_event = PlayerLeft(seq=35, player_id="p2", reason=LeaveReason.REMOVED)
    extra = LogEntry(at=NOW + 800.0, event=extra_event)

    recap = build_recap(game.state, [*game.log, extra])

    assert recap == build_recap(game.state, game.log)
    assert recap.players[1].removed is False


def test_ac8_public_recap_holds_the_grid_number_the_time_and_the_team(
    fx01_grid: Grid,
) -> None:
    public = public_recap(recap_of(play_r(fx01_grid)))

    assert public == PublicRecap(grid_number=1, elapsed_ms=754000, team=("Ana", "Bob"))


def test_ac8_the_team_leaves_out_a_removed_player(fx01_grid: Grid) -> None:
    game = Game(fx01_grid)
    game.join("Cy", "p3", THIRD_TOKEN)
    game.send("p1", remove_message("p3"))
    game.finish("p1")

    assert public_recap(recap_of(game)).team == ("Ana", "Bob")
