"""Tests of spec 021, AC-3: the flag clears when every cell of its word is filled.

The rule on `handle_message` ("Server rule: a flag clears when its word is full":
an edit, the `FULL17` example, a letter or word reveal, several flaggers in
`players` order, the completion entry last), the real WebSocket, and the page with
a mocked socket. The edge cases of AC-3 are here too: a check never clears a flag
by itself, an undo that fills the word's last empty cell clears its flag (the rule
names undo among its triggers), an undo or an erase does not bring a cleared flag
back, and a pencil
letter (spec 020) that fills the last empty cell clears the flag like a normal
one. Two tests named `test_ac5_...` are here as well, because they are about the
same fact: a pencil letter fills its cell, so a word full of them is full and a
`Flag` on it is refused (case 4 of "Server rule: `Flag`"). The shared setup is in
`spec021_harness`, `spec020_harness` and `spec024_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellTarget,
    Check,
    EditLetter,
    Erase,
    ErrorCode,
    Flag,
    FlagChanged,
    FlagView,
    GridFullWrong,
    GridSolved,
    LetterChanged,
    RevealBudget,
    RevealResult,
    Undo,
    WordTarget,
    grid_view,
)
from nock.room import RoomState, handle_message
from nock.server import create_app
from spec020_harness import accepted_pencil
from spec021_harness import (
    IDES,
    LEST,
    MIME,
    MIME_CELLS,
    SENT,
    Cell,
    accepted_flag,
    expect_marker,
    expect_unflagged,
    expected_flagged_map,
    flag_changed_frame,
    flag_of,
    flagged_map,
    flags_by_player,
    open_flag_room,
    send_flag,
    snapshot_flags,
)
from spec024_harness import (
    NOW,
    SETTLE_MS,
    accepted_reveal,
    cell_state,
    events_of,
    expect_seq,
    full17,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    refusal_code,
    seen_at,
    two_player_room,
    write,
)

LATER = NOW + 5.0
FIRST_THREE_OF_IDES = [(1, 3, "I"), (2, 3, "D"), (3, 3, "E")]
# `p2` writes the last letter of `FULL17` at (4, 4): its entry, seq 22.
T_AT_4_4 = LetterChanged(
    seq=22, row=4, column=4, letter="T", pencil=False, player_id="p2"
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- Rooms ----


def ides_flagged_by_p2(grid: Grid) -> RoomState:
    """The two-player room where `p2` flagged IDES (seq 3)."""
    state = accepted_flag(two_player_room(grid), "p2", IDES).state
    assert state.seq == 3
    return state


def ides_but_its_last_letter(state: RoomState) -> RoomState:
    """`p1` writes `I`, `D` and `E` in IDES: only (4, 3) stays empty."""
    for row, column, letter in FIRST_THREE_OF_IDES:
        state = write(state, "p1", row, column, letter).state
    return state


def written_in_pencil(
    state: RoomState, player_id: str, cells: list[Cell], letters: str
) -> RoomState:
    """A player writes `letters` in `cells` in pencil, one `PencilEdit` per cell."""
    for index, (row, column) in enumerate(cells):
        letter = letters[index]
        state = accepted_pencil(state, player_id, row, column, letter).state
    return state


def flag_changes_of(events: list[object]) -> list[object]:
    """The `flag_changed` events among a step's events."""
    found: list[object] = []
    for event in events:
        if isinstance(event, FlagChanged):
            found.append(event)
    return found


# ---- AC-3, rule: an edit fills the word ----


def test_ac3_each_of_the_first_three_letters_logs_only_its_letter_changed(
    fx01_grid: Grid,
) -> None:
    state = ides_flagged_by_p2(fx01_grid)

    for number, (row, column, letter) in enumerate(FIRST_THREE_OF_IDES):
        outcome = write(state, "p1", row, column, letter)
        assert events_of(outcome) == [
            LetterChanged(
                seq=4 + number,
                row=row,
                column=column,
                letter=letter,
                pencil=False,
                player_id="p1",
            )
        ]
        state = outcome.state

    assert flag_of(state, "p2") == IDES


def test_ac3_the_last_letter_of_the_word_clears_the_flag_right_after_it(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    assert state.seq == 6

    outcome = write(state, "p1", 4, 3, "S")

    assert events_of(outcome) == [
        LetterChanged(seq=7, row=4, column=3, letter="S", pencil=False, player_id="p1"),
        FlagChanged(seq=8, player_id="p2", clue=None),
    ]
    assert outcome.state.seq == 8
    assert flag_of(outcome.state, "p2") is None
    assert snapshot_flags(outcome.state) == ()


def test_ac3_the_full17_example_clears_both_flags_before_grid_solved(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(full17(fx01_grid), "p1", LEST).state
    state = accepted_flag(state, "p2", SENT).state
    assert state.seq == 21

    outcome = write(state, "p2", 4, 4, "T", NOW + 754.0)

    assert events_of(outcome) == [
        T_AT_4_4,
        FlagChanged(seq=23, player_id="p1", clue=None),
        FlagChanged(seq=24, player_id="p2", clue=None),
        GridSolved(seq=25, elapsed_ms=754000),
    ]
    assert flags_by_player(outcome.state) == {"p1": None, "p2": None}


def test_ac3_the_clearing_entries_follow_players_order_not_flag_order(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(full17(fx01_grid), "p2", SENT).state
    state = accepted_flag(state, "p1", LEST).state

    outcome = write(state, "p2", 4, 4, "T", NOW + 754.0)

    assert events_of(outcome) == [
        T_AT_4_4,
        FlagChanged(seq=23, player_id="p1", clue=None),
        FlagChanged(seq=24, player_id="p2", clue=None),
        GridSolved(seq=25, elapsed_ms=754000),
    ]


def test_ac3_on_a_full_but_wrong_grid_grid_full_wrong_comes_after_the_clearing(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(full17(fx01_grid, wrong_at=(1, 1)), "p1", LEST).state
    state = accepted_flag(state, "p2", SENT).state

    outcome = write(state, "p2", 4, 4, "T", NOW + 754.0)

    assert events_of(outcome) == [
        T_AT_4_4,
        FlagChanged(seq=23, player_id="p1", clue=None),
        FlagChanged(seq=24, player_id="p2", clue=None),
        GridFullWrong(seq=25),
    ]


def test_ac3_two_players_on_the_same_word_are_both_cleared_in_players_order(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(ides_flagged_by_p2(fx01_grid), "p1", IDES).state
    state = ides_but_its_last_letter(state)
    assert state.seq == 7

    outcome = write(state, "p2", 4, 3, "S")

    assert events_of(outcome) == [
        LetterChanged(seq=8, row=4, column=3, letter="S", pencil=False, player_id="p2"),
        FlagChanged(seq=9, player_id="p1", clue=None),
        FlagChanged(seq=10, player_id="p2", clue=None),
    ]
    assert snapshot_flags(outcome.state) == ()


# ---- AC-3, rule: reveals, checks, undo and erase (edge cases) ----


def test_ac3_a_letter_reveal_that_fills_the_word_clears_its_flag(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    target = CellTarget(row=4, column=3)

    outcome = accepted_reveal(state, target, "p1")

    assert events_of(outcome) == [
        RevealResult(
            seq=7,
            player_id="p1",
            target=target,
            reveal_budget=RevealBudget(letters=4, words=1),
        ),
        CellLocked(seq=8, row=4, column=3, letter="S", revealed=True),
        FlagChanged(seq=9, player_id="p2", clue=None),
    ]
    assert flag_of(outcome.state, "p2") is None


def test_ac3_a_word_reveal_clears_the_flag_after_all_its_locks(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(two_player_room(fx01_grid), "p2", MIME).state
    target = WordTarget(row=0, column=2, clue_index=0)

    outcome = accepted_reveal(state, target, "p1")

    assert events_of(outcome) == [
        RevealResult(
            seq=4,
            player_id="p1",
            target=target,
            reveal_budget=RevealBudget(letters=5, words=0),
        ),
        CellLocked(seq=5, row=1, column=2, letter="M", revealed=True),
        CellLocked(seq=6, row=2, column=2, letter="I", revealed=True),
        CellLocked(seq=7, row=3, column=2, letter="M", revealed=True),
        CellLocked(seq=8, row=4, column=2, letter="E", revealed=True),
        FlagChanged(seq=9, player_id="p2", clue=None),
    ]


def test_ac3_a_check_that_locks_cells_never_clears_a_flag_by_itself(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    check = Check(target=WordTarget(row=0, column=3, clue_index=0))

    outcome = handle_message(state, "p1", check, NOW)

    assert outcome.reply == ()
    assert len(events_of(outcome)) > 1
    assert flag_changes_of(events_of(outcome)) == []
    assert flag_of(outcome.state, "p2") == IDES


def test_ac3_an_undo_that_fills_the_last_empty_cell_clears_the_flag(
    fx01_grid: Grid,
) -> None:
    written = ides_but_its_last_letter(two_player_room(fx01_grid))
    written = write(written, "p1", 4, 3, "S").state
    erased = handle_message(written, "p1", Erase(row=4, column=3), NOW)
    assert erased.reply == ()
    flagged = accepted_flag(erased.state, "p2", IDES).state
    assert flagged.seq == 8

    outcome = handle_message(flagged, "p1", Undo(), NOW)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=9, row=4, column=3, letter="S", pencil=False, player_id="p1"),
        FlagChanged(seq=10, player_id="p2", clue=None),
    ]
    assert outcome.state.seq == 10
    assert flag_of(outcome.state, "p2") is None
    assert snapshot_flags(outcome.state) == ()


def test_ac3_an_undo_that_empties_the_word_does_not_bring_the_flag_back(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    cleared = write(state, "p1", 4, 3, "S").state
    assert flag_of(cleared, "p2") is None

    outcome = handle_message(cleared, "p1", Undo(), NOW)

    assert outcome.reply == ()
    assert cell_state(outcome.state, 4, 3).letter is None
    assert flag_changes_of(events_of(outcome)) == []
    assert flag_of(outcome.state, "p2") is None
    assert snapshot_flags(outcome.state) == ()


def test_ac3_an_erase_that_empties_the_word_does_not_bring_the_flag_back(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    cleared = write(state, "p1", 4, 3, "S").state

    outcome = handle_message(cleared, "p2", Erase(row=4, column=3), NOW)

    assert outcome.reply == ()
    assert cell_state(outcome.state, 4, 3).letter is None
    assert flag_changes_of(events_of(outcome)) == []
    assert flag_of(outcome.state, "p2") is None


# ---- AC-3, rule: pencil letters of spec 020 (edge case) ----


def test_ac3_a_pencil_letter_in_the_last_empty_cell_clears_the_flag(
    fx01_grid: Grid,
) -> None:
    state = ides_but_its_last_letter(ides_flagged_by_p2(fx01_grid))
    assert state.seq == 6

    outcome = accepted_pencil(state, "p1", 4, 3, "S")

    assert events_of(outcome) == [
        LetterChanged(seq=7, row=4, column=3, letter="S", pencil=True, player_id="p1"),
        FlagChanged(seq=8, player_id="p2", clue=None),
    ]
    assert outcome.state.seq == 8
    assert flag_of(outcome.state, "p2") is None
    assert snapshot_flags(outcome.state) == ()


def test_ac3_a_word_written_only_in_pencil_clears_the_flag_on_its_last_letter(
    fx01_grid: Grid,
) -> None:
    state = ides_flagged_by_p2(fx01_grid)

    for number, (row, column, letter) in enumerate(FIRST_THREE_OF_IDES):
        outcome = accepted_pencil(state, "p1", row, column, letter)
        assert events_of(outcome) == [
            LetterChanged(
                seq=4 + number,
                row=row,
                column=column,
                letter=letter,
                pencil=True,
                player_id="p1",
            )
        ]
        assert flag_of(outcome.state, "p2") == IDES
        state = outcome.state

    last = accepted_pencil(state, "p1", 4, 3, "X")

    assert events_of(last) == [
        LetterChanged(seq=7, row=4, column=3, letter="X", pencil=True, player_id="p1"),
        FlagChanged(seq=8, player_id="p2", clue=None),
    ]
    assert flag_of(last.state, "p2") is None


def test_ac3_a_pencil_letter_that_solves_the_grid_clears_the_flags_before_it(
    fx01_grid: Grid,
) -> None:
    state = accepted_flag(full17(fx01_grid), "p1", LEST).state
    state = accepted_flag(state, "p2", SENT).state
    assert state.seq == 21

    outcome = accepted_pencil(state, "p2", 4, 4, "T", now=NOW + 754.0)

    assert events_of(outcome) == [
        LetterChanged(seq=22, row=4, column=4, letter="T", pencil=True, player_id="p2"),
        FlagChanged(seq=23, player_id="p1", clue=None),
        FlagChanged(seq=24, player_id="p2", clue=None),
        GridSolved(seq=25, elapsed_ms=754000),
    ]
    assert flags_by_player(outcome.state) == {"p1": None, "p2": None}


def test_ac5_a_word_full_of_pencil_letters_is_refused_as_full(
    fx01_grid: Grid,
) -> None:
    state = written_in_pencil(two_player_room(fx01_grid), "p1", MIME_CELLS, "MIME")
    assert state.seq == 6

    outcome = send_flag(state, "p2", MIME, LATER)

    assert refusal_code(outcome) is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.state == seen_at(state, "p2", LATER)
    assert flag_of(outcome.state, "p2") is None


def test_ac5_a_word_with_one_empty_cell_among_pencil_letters_can_be_flagged(
    fx01_grid: Grid,
) -> None:
    state = written_in_pencil(two_player_room(fx01_grid), "p1", MIME_CELLS[:3], "MIM")
    assert state.seq == 5

    outcome = send_flag(state, "p2", MIME)

    assert outcome.reply == ()
    assert events_of(outcome) == [FlagChanged(seq=6, player_id="p2", clue=MIME)]
    assert flag_of(outcome.state, "p2") == MIME


# ---- AC-3, WebSocket ----


def test_ac3_websocket_both_players_get_the_clearing_right_after_the_last_letter(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send(Flag(clue=MIME))
        ana.wait_for_seq(3, "Bob's flag on Ana")

        for index, letter in enumerate("MIME"):
            row, column = MIME_CELLS[index]
            ana.send(EditLetter(row=row, column=column, letter=letter))

        last_letter = LetterChanged(
            seq=7, row=4, column=2, letter="E", pencil=False, player_id=ana.you()
        )
        clearing = FlagChanged(seq=8, player_id=bob.you(), clue=None)
        for peer in (ana, bob):
            peer.wait_for_seq(8, f"the clearing on {peer.name}")
            messages = peer.messages()
            assert last_letter in messages
            after_last_letter = messages[messages.index(last_letter) + 1]
            assert after_last_letter == clearing


# ---- AC-3, page with a mocked socket ----


def test_ac3_browser_a_cleared_flag_removes_the_marker_and_adds_no_feed_item(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    ides_flag = FlagView(player_id="p2", clue=IDES)
    mock = open_flag_room(page, live_server, grid_view(fx01_grid), flags=[ides_flag])
    expect_marker(page, IDES, "p2", ["Bob"])
    feed_items = page.get_by_test_id("activity-feed").get_by_test_id("feed-item")
    items_before = feed_items.count()

    mock.send(flag_changed_frame(6, "p2", None))

    expect_seq(page, 6)
    expect_unflagged(page, IDES)
    page.wait_for_timeout(SETTLE_MS)
    assert feed_items.count() == items_before
    assert flagged_map(page) == expected_flagged_map([])
