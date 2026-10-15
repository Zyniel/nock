"""Tests of spec 020, AC-3 and AC-5: completion counts pencil letters, and pencil
letters survive an undo and a reload.

AC-3 checks this spec's side of spec 026's rule on `handle_message`: a pencil
letter fills its cell and is compared with the solution like any letter
(`_is_filled` is private, so it is observed through the completion entries). AC-5
checks undo (spec 018), `replay` and a `RoomStore` saved and loaded again. Rule
tests only, no browser. The shared setup is in `spec020_harness` and
`spec024_harness`.
"""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple

import pytest

from nock.grid import Grid
from nock.protocol import ErrorCode, GridFullWrong, GridSolved, LetterChanged, Undo
from nock.room import (
    LogEntry,
    Outcome,
    RoomState,
    UndoEntry,
    handle_message,
    new_room,
    replay,
)
from nock.store import RoomStore
from spec020_harness import (
    SOLVED_AT,
    accepted_confirm,
    accepted_pencil,
    cell_values,
    confirm,
    pencil,
)
from spec024_harness import (
    FIRST_17,
    NOW,
    ROOM_CODE,
    ROW_MAJOR,
    SOLUTION,
    events_of,
    full17,
    grid_from_text,
    joined_room,
    player_record,
    refusal_code,
    seen_at,
    two_player_room,
    write,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-3: completion evaluates pencil and normal letters the same way ----


def solved_by_a_pencil_letter(grid: Grid) -> RoomState:
    """The first run of AC-3: `p2`'s pencil `T` at (4, 4) solved `FULL17` (seq 21)."""
    state = accepted_pencil(full17(grid), "p2", 4, 4, "T", now=SOLVED_AT).state
    assert state.solved is True
    return state


def test_ac3_a_pencil_letter_that_completes_the_grid_gives_grid_solved(
    fx01_grid: Grid,
) -> None:
    outcome = pencil(full17(fx01_grid), "p2", 4, 4, "T", now=SOLVED_AT)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=20, row=4, column=4, letter="T", pencil=True, player_id="p2"),
        GridSolved(seq=21, elapsed_ms=754000),
    ]
    assert outcome.state.solved is True


def test_ac3_a_wrong_pencil_letter_that_fills_the_grid_gives_grid_full_wrong(
    fx01_grid: Grid,
) -> None:
    outcome = pencil(full17(fx01_grid), "p2", 4, 4, "X", now=SOLVED_AT)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=20, row=4, column=4, letter="X", pencil=True, player_id="p2"),
        GridFullWrong(seq=21),
    ]
    assert outcome.state.solved is False


def test_ac3_confirming_the_wrong_pencil_letter_gives_only_its_letter_changed(
    fx01_grid: Grid,
) -> None:
    full_wrong = accepted_pencil(
        full17(fx01_grid), "p2", 4, 4, "X", now=SOLVED_AT
    ).state

    outcome = confirm(full_wrong, "p2", 4, 4, now=SOLVED_AT + 1.0)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=22, row=4, column=4, letter="X", pencil=False, player_id="p2")
    ]
    assert outcome.state.solved is False


def test_ac3_eighteen_pencil_letters_give_one_grid_solved_after_the_last(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    events: list[object] = []
    for row, column in ROW_MAJOR:
        outcome = accepted_pencil(state, "p1", row, column, SOLUTION[(row, column)])
        events.extend(events_of(outcome))
        state = outcome.state

    solved_events = [event for event in events if isinstance(event, GridSolved)]
    full_wrong_events = [event for event in events if isinstance(event, GridFullWrong)]
    assert len(events) == 19
    assert solved_events == [GridSolved(seq=21, elapsed_ms=0)]
    assert full_wrong_events == []
    assert events[-2:] == [
        LetterChanged(seq=20, row=4, column=4, letter="T", pencil=True, player_id="p1"),
        GridSolved(seq=21, elapsed_ms=0),
    ]


def test_ac3_a_pencil_letter_elsewhere_counts_when_a_normal_letter_completes_the_grid(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for row, column in FIRST_17:
        letter = SOLUTION[(row, column)]
        if (row, column) == (1, 0):
            state = accepted_pencil(state, "p1", row, column, letter).state
        else:
            state = write(state, "p1", row, column, letter).state

    outcome = write(state, "p2", 4, 4, "T", SOLVED_AT)

    assert events_of(outcome) == [
        LetterChanged(
            seq=20, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=21, elapsed_ms=754000),
    ]


def test_ac3_on_the_solved_grid_a_pencil_edit_is_refused_grid_solved(
    fx01_grid: Grid,
) -> None:
    before = solved_by_a_pencil_letter(fx01_grid)
    later = SOLVED_AT + 1.0

    outcome = pencil(before, "p1", 4, 4, "X", now=later)

    assert refusal_code(outcome) == ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p1", later)


def test_ac3_on_the_solved_grid_a_confirmation_is_refused_grid_solved(
    fx01_grid: Grid,
) -> None:
    before = solved_by_a_pencil_letter(fx01_grid)
    later = SOLVED_AT + 1.0

    outcome = confirm(before, "p1", 4, 4, now=later)

    assert refusal_code(outcome) == ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p1", later)


# ---- AC-5: pencil letters survive an undo and a reload ----


class Ac5Play(NamedTuple):
    """The play of AC-5: the three undos, the live state and every entry logged."""

    undo_of_pencil: Outcome
    undo_of_pencil_over_normal: Outcome
    undo_of_confirmation: Outcome
    state: RoomState
    entries: list[LogEntry]


def accepted_undo(state: RoomState, player_id: str) -> Outcome:
    """Send `Undo()` from a player, after checking it was not refused."""
    outcome = handle_message(state, player_id, Undo(), NOW)
    assert outcome.reply == (), outcome.reply
    return outcome


def ac5_play(grid: Grid) -> Ac5Play:
    """Play AC-5 on a FX-01 room with `p1` and `p2`, keeping every logged entry."""
    state, entries = joined_room(grid)
    steps: list[Outcome] = []

    # p1's pencil T at (1, 0) (seq 3), then p1's undo (seq 4).
    steps.append(accepted_pencil(state, "p1", 1, 0, "T"))
    steps.append(accepted_undo(steps[-1].state, "p1"))
    undo_of_pencil = steps[-1]
    # p1's normal A at (1, 1) (seq 5), pencil B there (seq 6), undo (seq 7).
    steps.append(write(steps[-1].state, "p1", 1, 1, "A"))
    steps.append(accepted_pencil(steps[-1].state, "p1", 1, 1, "B"))
    steps.append(accepted_undo(steps[-1].state, "p1"))
    undo_of_pencil_over_normal = steps[-1]
    # p1's pencil T at (1, 0) again (seq 8), p2 confirms it (seq 9), p2's undo
    # (seq 10).
    steps.append(accepted_pencil(steps[-1].state, "p1", 1, 0, "T"))
    steps.append(accepted_confirm(steps[-1].state, "p2", 1, 0))
    steps.append(accepted_undo(steps[-1].state, "p2"))
    undo_of_confirmation = steps[-1]

    for step in steps:
        entries.extend(step.entries)
    return Ac5Play(
        undo_of_pencil=undo_of_pencil,
        undo_of_pencil_over_normal=undo_of_pencil_over_normal,
        undo_of_confirmation=undo_of_confirmation,
        state=steps[-1].state,
        entries=entries,
    )


def test_ac5_a_pencil_edit_records_the_cell_before_for_undo(fx01_grid: Grid) -> None:
    state = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T").state

    assert player_record(state, "p1").last_edit == UndoEntry(
        row=1, column=0, seq=3, letter=None, pencil=False, author=None
    )


def test_ac5_a_confirmation_records_the_pencil_letter_and_its_author_for_undo(
    fx01_grid: Grid,
) -> None:
    pencilled = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T").state

    state = accepted_confirm(pencilled, "p2", 1, 0).state

    assert player_record(state, "p2").last_edit == UndoEntry(
        row=1, column=0, seq=4, letter="T", pencil=True, author="p1"
    )


def test_ac5_undoing_a_pencil_edit_empties_the_cell(fx01_grid: Grid) -> None:
    undo = ac5_play(fx01_grid).undo_of_pencil

    assert events_of(undo) == [
        LetterChanged(seq=4, row=1, column=0, letter=None, pencil=False, player_id="p1")
    ]
    assert [entry.undo for entry in undo.entries] == [True]
    assert cell_values(undo.state)[(1, 0)] == (None, False, None)


def test_ac5_undoing_a_pencil_letter_over_a_normal_letter_gives_the_normal_one_back(
    fx01_grid: Grid,
) -> None:
    undo = ac5_play(fx01_grid).undo_of_pencil_over_normal

    assert events_of(undo) == [
        LetterChanged(seq=7, row=1, column=1, letter="A", pencil=False, player_id="p1")
    ]
    assert [entry.undo for entry in undo.entries] == [True]
    assert cell_values(undo.state)[(1, 1)] == ("A", False, "p1")


def test_ac5_undoing_a_confirmation_puts_the_pencil_letter_back_by_the_undoer(
    fx01_grid: Grid,
) -> None:
    undo = ac5_play(fx01_grid).undo_of_confirmation

    assert events_of(undo) == [
        LetterChanged(seq=10, row=1, column=0, letter="T", pencil=True, player_id="p2")
    ]
    assert [entry.undo for entry in undo.entries] == [True]
    assert cell_values(undo.state)[(1, 0)] == ("T", True, "p2")


def test_ac5_replaying_the_play_from_new_room_gives_the_live_cells(
    fx01_grid: Grid,
) -> None:
    play = ac5_play(fx01_grid)

    replayed = new_room(ROOM_CODE, fx01_grid, NOW)
    for entry in play.entries:
        replayed = replay(replayed, entry)

    assert replayed.seq == 10
    assert cell_values(replayed) == cell_values(play.state)
    assert cell_values(replayed)[(1, 0)] == ("T", True, "p2")
    assert cell_values(replayed)[(1, 1)] == ("A", False, "p1")


def test_ac5_the_room_saved_and_loaded_again_gives_the_live_cells(
    fx01_grid: Grid, tmp_path: Path
) -> None:
    play = ac5_play(fx01_grid)
    path = tmp_path / "rooms.sqlite3"
    store = RoomStore(path)
    try:
        store.create_room(new_room(ROOM_CODE, fx01_grid, NOW))
        store.append(ROOM_CODE, play.entries)
    finally:
        store.close()

    reopened = RoomStore(path)
    try:
        loaded = reopened.load_room(ROOM_CODE)
    finally:
        reopened.close()

    assert loaded is not None
    assert loaded.seq == 10
    assert cell_values(loaded) == cell_values(play.state)
