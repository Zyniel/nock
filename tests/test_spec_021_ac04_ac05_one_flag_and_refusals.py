"""Tests of spec 021, AC-4 and AC-5: one flag per player, refusals and no-ops.

AC-4 on `handle_message` (a new flag replaces the previous one, the snapshot's
`flags` in `players` order) and on the page with a mocked socket (the marker moves;
several flaggers in roster order, joiners appended; an unknown player id; snapshot
entries that are not well formed). AC-5 on `handle_message`: the five cases of
"Server rule: `Flag`" that write nothing or refuse, on an empty room, `FULL17`, the
solved state of spec 026 AC-1 and a full but wrong grid. The shared setup is in
`spec021_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    ClueRef,
    ErrorCode,
    FlagChanged,
    FlagView,
    PlayerJoined,
    grid_view,
)
from nock.room import PlayerRecord, RoomState
from spec021_harness import (
    EIGHT_WORDS,
    IDES,
    MIME,
    MIME_CELLS,
    SENT,
    TAMIS,
    accepted_flag,
    expect_marker,
    expect_unflagged,
    expected_flagged_map,
    flag_changed_frame,
    flag_of,
    flagged_map,
    flags_by_player,
    open_flag_room,
    open_with_snapshot,
    send_flag,
    snapshot_flags,
    snapshot_with_flags,
    three_players,
)
from spec024_harness import (
    NOW,
    events_of,
    expect_seq,
    full17,
    grid_from_text,
    load_fr,
    make_catalogue,
    player_view,
    refusal_code,
    seen_at,
    two_player_room,
    write,
)

LATER = NOW + 5.0
SOLVED_AT = NOW + 754.0
AFTER_SOLVED = NOW + 760.0
NO_WORD_CLUES = [
    ClueRef(row=1, column=0, clue_index=0),  # a letter cell
    ClueRef(row=0, column=2, clue_index=1),  # that clue cell has one clue
    ClueRef(row=9, column=9, clue_index=0),  # outside the grid
]

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Rooms ----


def ides_flagged_by_p2(grid: Grid) -> RoomState:
    """The two-player room where `p2` flagged IDES (seq 3)."""
    state = accepted_flag(two_player_room(grid), "p2", IDES).state
    assert state.seq == 3
    return state


def mime_written_by_p1(grid: Grid) -> RoomState:
    """The two-player room where `p1` wrote the four letters of MIME (seq 6)."""
    state = two_player_room(grid)
    for index, letter in enumerate("MIME"):
        row, column = MIME_CELLS[index]
        state = write(state, "p1", row, column, letter).state
    assert state.seq == 6
    return state


def solved_state(grid: Grid) -> RoomState:
    """The solved state of spec 026 AC-1: `p2` wrote `T` at (4, 4) (seq 21)."""
    state = write(full17(grid), "p2", 4, 4, "T", SOLVED_AT).state
    assert state.solved is True
    assert state.seq == 21
    return state


def assert_refused_without_change(
    state: RoomState, player_id: str, clue: ClueRef, now: float
) -> None:
    """A `Flag(clue)` is refused with `invalid_target` and changes nothing else.

    Args:
        state: The room the flag is sent to.
        player_id: The sender.
        clue: The refused clue.
        now: The clock time of the step.
    """
    outcome = send_flag(state, player_id, clue, now)

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.state.seq == state.seq
    assert outcome.state == seen_at(state, player_id, now)


# ---- AC-4, rule ----


def test_ac4_a_new_flag_replaces_the_previous_one_with_one_entry(
    fx01_grid: Grid,
) -> None:
    outcome = send_flag(ides_flagged_by_p2(fx01_grid), "p2", MIME)

    assert events_of(outcome) == [FlagChanged(seq=4, player_id="p2", clue=MIME)]
    assert outcome.reply == ()
    assert flag_of(outcome.state, "p2") == MIME
    assert snapshot_flags(outcome.state) == (FlagView(player_id="p2", clue=MIME),)


def test_ac4_two_players_on_one_clue_are_listed_in_players_order(
    fx01_grid: Grid,
) -> None:
    moved = accepted_flag(ides_flagged_by_p2(fx01_grid), "p2", MIME).state

    after = accepted_flag(moved, "p1", MIME).state

    assert snapshot_flags(after) == (
        FlagView(player_id="p1", clue=MIME),
        FlagView(player_id="p2", clue=MIME),
    )


def test_ac4_the_flag_is_one_field_of_the_player_record_none_by_default(
    fx01_grid: Grid,
) -> None:
    assert PlayerRecord.model_fields["flag"].default is None
    assert flags_by_player(two_player_room(fx01_grid)) == {"p1": None, "p2": None}


# ---- AC-4, page with a mocked socket ----


def test_ac4_browser_a_new_flag_moves_the_marker_and_flaggers_share_one_marker(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    ides_flag = FlagView(player_id="p2", clue=IDES)
    mock = open_flag_room(page, live_server, grid_view(fx01_grid), flags=[ides_flag])
    expect_marker(page, IDES, "p2", ["Bob"])

    mock.send(flag_changed_frame(6, "p2", MIME))

    expect_seq(page, 6)
    expect_unflagged(page, IDES)
    expect_marker(page, MIME, "p2", ["Bob"])
    assert flagged_map(page) == expected_flagged_map([MIME])

    mock.send(flag_changed_frame(7, "p3", MIME))

    expect_seq(page, 7)
    expect_marker(page, MIME, "p2 p3", ["Bob", "Cy"])
    assert flagged_map(page) == expected_flagged_map([MIME])


def test_ac4_browser_flaggers_follow_roster_order_and_an_unknown_id_is_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_flag_room(page, live_server, grid_view(fx01_grid))
    assert flagged_map(page) == expected_flagged_map([])
    joined = PlayerJoined(seq=6, player=player_view("p4", "Dee", 3))
    mock.send(joined.model_dump_json())

    mock.send(flag_changed_frame(7, "p4", SENT))
    expect_seq(page, 7)
    expect_marker(page, SENT, "p4", ["Dee"])
    mock.send(flag_changed_frame(8, "p3", SENT))
    expect_seq(page, 8)
    expect_marker(page, SENT, "p3 p4", ["Cy", "Dee"])
    mock.send(flag_changed_frame(9, "p2", SENT))
    expect_seq(page, 9)
    expect_marker(page, SENT, "p2 p3 p4", ["Bob", "Cy", "Dee"])
    mock.send(flag_changed_frame(10, "p9", IDES))
    expect_seq(page, 10)
    expect_marker(page, IDES, "p9", [load_fr()["feed.someone"]])

    assert flagged_map(page) == expected_flagged_map([IDES, SENT])


def test_ac4_browser_snapshot_flag_entries_that_are_not_well_formed_are_skipped(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = grid_view(fx01_grid)
    value = snapshot_with_flags(view, 5, three_players(), []).model_dump(mode="json")
    value["flags"] = [
        {"player_id": "p2", "clue": {"row": 0, "column": 3, "clue_index": 0}},
        {"player_id": 7, "clue": {"row": 0, "column": 2, "clue_index": 0}},
        {"player_id": "p3", "clue": {"row": 0, "column": 4}},
        {"player_id": "p3", "clue": {"row": 0, "column": 4, "clue_index": "0"}},
        {"player_id": "p3", "clue": {"row": "2", "column": 0, "clue_index": 0}},
        {"player_id": "p3", "clue": {"row": 3, "column": 0, "clue_index": 0.5}},
        {"clue": {"row": 4, "column": 0, "clue_index": 0}},
        {"player_id": "p3", "clue": None},
        "p3",
        None,
    ]

    open_with_snapshot(page, live_server, json.dumps(value), 5, len(view.cells))

    expect_marker(page, IDES, "p2", ["Bob"])
    assert flagged_map(page) == expected_flagged_map([IDES])


# ---- AC-5, rule: flags that change nothing ----


def test_ac5_removing_a_flag_one_does_not_hold_writes_nothing(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    outcome = send_flag(state, "p1", None, LATER)

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state == seen_at(state, "p1", LATER)


def test_ac5_flagging_the_clue_one_already_flagged_writes_nothing(
    fx01_grid: Grid,
) -> None:
    state = ides_flagged_by_p2(fx01_grid)

    outcome = send_flag(state, "p2", IDES, LATER)

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state == seen_at(state, "p2", LATER)


# ---- AC-5, rule: refusals ----


@pytest.mark.parametrize(
    "clue", NO_WORD_CLUES, ids=["letter-cell", "missing-index", "outside"]
)
def test_ac5_a_clue_that_names_no_word_is_refused(
    fx01_grid: Grid, clue: ClueRef
) -> None:
    assert_refused_without_change(ides_flagged_by_p2(fx01_grid), "p2", clue, LATER)


def test_ac5_a_full_word_is_refused(fx01_grid: Grid) -> None:
    assert_refused_without_change(mime_written_by_p1(fx01_grid), "p2", MIME, LATER)


def test_ac5_in_full17_a_full_word_is_refused_and_an_unfinished_one_accepted(
    fx01_grid: Grid,
) -> None:
    state = full17(fx01_grid)

    assert_refused_without_change(state, "p2", TAMIS, LATER)
    accepted = send_flag(state, "p2", SENT, LATER)
    assert accepted.reply == ()
    assert events_of(accepted) == [FlagChanged(seq=20, player_id="p2", clue=SENT)]


@pytest.mark.parametrize("word", list(EIGHT_WORDS))
def test_ac5_on_the_solved_grid_every_word_is_refused_as_full(
    fx01_grid: Grid, word: str
) -> None:
    state = solved_state(fx01_grid)

    assert_refused_without_change(state, "p1", EIGHT_WORDS[word], AFTER_SOLVED)


def test_ac5_on_the_solved_grid_removing_no_flag_still_writes_nothing(
    fx01_grid: Grid,
) -> None:
    state = solved_state(fx01_grid)

    outcome = send_flag(state, "p1", None, AFTER_SOLVED)

    assert outcome.entries == ()
    assert outcome.reply == ()


def test_ac5_on_a_full_but_wrong_grid_a_flag_is_refused(fx01_grid: Grid) -> None:
    full = write(full17(fx01_grid, wrong_at=(1, 1)), "p2", 4, 4, "T", SOLVED_AT)
    assert full.state.solved is False

    assert_refused_without_change(full.state, "p2", TAMIS, AFTER_SOLVED)
