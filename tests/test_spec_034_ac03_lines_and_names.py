"""Tests of spec 034, AC-3: the words completed, checks and reveals of an absence.

Python: `RoomRegistry.catch_up` on the reference absence ABSENCE, and
`build_catch_up` on hand-made plays of the rules (one letter that completes two
words, the letters that complete nothing, the line limit, the names). HTTP: the
200 answer of AC-1. The shared setup is in `spec034_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Check,
    CheckResult,
    ConfirmPencil,
    Erase,
    GridTarget,
    PencilEdit,
    RemovePlayer,
    Reveal,
    WordTarget,
)
from nock.room import LogEntry
from spec034_harness import (
    ANA,
    BOB,
    NAVAL,
    SENT,
    TA,
    TB,
    VIDE,
    AbsenceRooms,
    Play,
    absence_rooms,
    catch_up_path,
    grid_from_text,
    known_catch_up,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def rooms(tmp_path: Path, fx01_grid: Grid) -> Iterator[AbsenceRooms]:
    with absence_rooms(tmp_path, fx01_grid) as found:
        yield found


def two_players(grid: Grid) -> Play:
    """A play where Ana (`p1`, host) and Bob (`p2`) joined (seq 2)."""
    play = Play(grid)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    return play


class Clock:
    """Times one second apart, so that no step meets spec 037's edit rate."""

    def __init__(self) -> None:
        self.now = 1_000_000.0

    def next(self) -> float:
        self.now += 1.0
        return self.now


def write_letters(
    play: Play, clock: Clock, player_id: str, letters: list[tuple[int, int, str]]
) -> None:
    for row, column, letter in letters:
        play.write(player_id, row, column, letter, now=clock.next())


VID = [(2, 1, "V"), (2, 2, "I"), (2, 3, "D")]


# ---- ABSENCE ----------------------------------------------------------------------


def test_ac3_catch_up_lists_the_words_checks_and_reveals_in_seq_order(
    rooms: AbsenceRooms,
) -> None:
    from nock.catch_up import WordCompleted

    answer = known_catch_up(rooms.registry, 3, 22)

    assert answer.lines == (
        WordCompleted(seq=8, player_id=BOB, clue=VIDE),
        rooms.play.entry_of(9).event,
        rooms.play.entry_of(14).event,
        WordCompleted(seq=18, player_id=BOB, clue=NAVAL),
    )


def test_ac3_catch_up_names_a_player_who_has_left(rooms: AbsenceRooms) -> None:
    from nock.catch_up import PlayerName

    answer = known_catch_up(rooms.registry, 3, 22)

    assert answer.names == (PlayerName(player_id=BOB, nickname="BOB"),)


def test_ac3_a_word_completed_before_the_absence_gives_no_line(
    rooms: AbsenceRooms,
) -> None:
    # Edge case "Words in the absence": VIDE's last letter is seq 8; the check
    # locks it during the absence (seq 9 to 13).
    from nock.catch_up import WordCompleted

    answer = known_catch_up(rooms.registry, 8, 22)

    assert answer.lines == (
        rooms.play.entry_of(9).event,
        rooms.play.entry_of(14).event,
        WordCompleted(seq=18, player_id=BOB, clue=NAVAL),
    )


def test_ac3_the_line_limit_is_100() -> None:
    from nock.catch_up import CATCH_UP_LINE_LIMIT

    assert CATCH_UP_LINE_LIMIT == 100


# ---- build_catch_up on hand-made plays --------------------------------------------


def test_ac3_one_letter_that_completes_two_words_gives_two_lines_in_clue_order(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import WordCompleted, build_catch_up

    play = two_players(fx01_grid)
    clock = Clock()
    write_letters(play, clock, BOB, [*VID, (1, 4, "S"), (3, 4, "N"), (4, 4, "T")])
    before = play.state
    play.write(BOB, 2, 4, "E", now=clock.next())
    seq = play.state.seq

    answer = build_catch_up(before.seq, seq, before, play.entries_after(before.seq))

    assert answer.lines == (
        WordCompleted(seq=seq, player_id=BOB, clue=SENT),
        WordCompleted(seq=seq, player_id=BOB, clue=VIDE),
    )
    assert len(answer.cells) == 1


def full_vide(grid: Grid, clock: Clock) -> Play:
    play = two_players(grid)
    write_letters(play, clock, BOB, [*VID, (2, 4, "E")])
    return play


def test_ac3_a_letter_written_over_another_completes_no_word(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import build_catch_up

    clock = Clock()
    play = full_vide(fx01_grid, clock)
    before = play.state
    play.write(BOB, 2, 4, "X", now=clock.next())

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert answer.lines == ()
    assert answer.names == ()


def test_ac3_a_pencil_letter_confirmed_completes_no_word(fx01_grid: Grid) -> None:
    from nock.catch_up import build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    write_letters(play, clock, BOB, VID)
    play.send(BOB, PencilEdit(row=2, column=4, letter="E"), now=clock.next())
    before = play.state
    play.send(BOB, ConfirmPencil(row=2, column=4), now=clock.next())

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert answer.lines == ()


def test_ac3_an_erase_completes_no_word(fx01_grid: Grid) -> None:
    from nock.catch_up import build_catch_up

    clock = Clock()
    play = full_vide(fx01_grid, clock)
    before = play.state
    play.send(BOB, Erase(row=2, column=4), now=clock.next())

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert answer.lines == ()


def test_ac3_a_reveal_that_fills_a_words_last_cell_gives_only_its_reveal_line(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    write_letters(play, clock, BOB, VID)
    before = play.state
    play.send(BOB, Reveal(target=CellTarget(row=2, column=4)), now=clock.next())
    reveal = play.entry_of(before.seq + 1).event

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert reveal.type == "reveal_result"
    assert answer.lines == (reveal,)


def test_ac3_a_pencil_letter_that_fills_a_words_last_cell_completes_it(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import WordCompleted, build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    write_letters(play, clock, BOB, VID)
    before = play.state
    play.send(BOB, PencilEdit(row=2, column=4, letter="E"), now=clock.next())

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert answer.lines == (
        WordCompleted(seq=play.state.seq, player_id=BOB, clue=VIDE),
    )


def test_ac3_a_word_completed_emptied_and_completed_again_gives_two_lines(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import WordCompleted, build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    write_letters(play, clock, BOB, VID)
    before = play.state
    play.write(BOB, 2, 4, "E", now=clock.next())
    first = play.state.seq
    play.send(BOB, Erase(row=2, column=4), now=clock.next())
    play.write(ANA, 2, 4, "E", now=clock.next())
    second = play.state.seq

    answer = build_catch_up(before.seq, second, before, play.entries_after(before.seq))

    assert answer.lines == (
        WordCompleted(seq=first, player_id=BOB, clue=VIDE),
        WordCompleted(seq=second, player_id=ANA, clue=VIDE),
    )


def test_ac3_with_150_checks_the_lines_are_the_last_100(fx01_grid: Grid) -> None:
    from nock.catch_up import PlayerName, build_catch_up

    before = two_players(fx01_grid).state
    entries: list[LogEntry] = []
    for seq in range(3, 153):
        event = CheckResult(
            seq=seq, player_id=BOB, target=GridTarget(), correct=(), wrong=()
        )
        entries.append(LogEntry(at=1_000_000.0, event=event))

    answer = build_catch_up(2, 152, before, entries)

    expected: list[object] = []
    for entry in entries[50:]:
        expected.append(entry.event)
    assert list(answer.lines) == expected
    assert answer.names == (PlayerName(player_id=BOB, nickname="BOB"),)


def test_ac3_names_come_in_order_of_first_appearance(fx01_grid: Grid) -> None:
    from nock.catch_up import PlayerName, WordCompleted, build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    write_letters(play, clock, ANA, VID)
    before = play.state
    play.send(BOB, Check(target=CellTarget(row=2, column=1)), now=clock.next())
    check = play.entry_of(before.seq + 1).event
    play.write(ANA, 2, 4, "E", now=clock.next())
    completed = play.state.seq

    answer = build_catch_up(
        before.seq, completed, before, play.entries_after(before.seq)
    )

    assert answer.lines == (
        check,
        WordCompleted(seq=completed, player_id=ANA, clue=VIDE),
    )
    assert answer.names == (
        PlayerName(player_id=BOB, nickname="BOB"),
        PlayerName(player_id=ANA, nickname="ANA"),
    )


def test_ac3_names_a_player_removed_after_their_line(fx01_grid: Grid) -> None:
    # Edge case "Removed players": the replay gives the name they had then.
    from nock.catch_up import PlayerName, build_catch_up

    clock = Clock()
    play = two_players(fx01_grid)
    before = play.state
    play.send(
        BOB, Check(target=WordTarget(row=2, column=0, clue_index=0)), clock.next()
    )
    play.send(ANA, RemovePlayer(player_id=BOB), now=clock.next())

    answer = build_catch_up(
        before.seq, play.state.seq, before, play.entries_after(before.seq)
    )

    assert answer.names == (PlayerName(player_id=BOB, nickname="BOB"),)


def test_ac3_a_line_whose_player_is_not_in_the_room_gets_no_name(
    fx01_grid: Grid,
) -> None:
    # Edge case "Removed players": a vote that passes after its requester left.
    from nock.catch_up import build_catch_up

    before = two_players(fx01_grid).state
    event = CheckResult(
        seq=3, player_id="p9", target=GridTarget(), correct=(), wrong=()
    )

    answer = build_catch_up(2, 3, before, [LogEntry(at=1_000_000.0, event=event)])

    assert answer.lines == (event,)
    assert answer.names == ()


# ---- HTTP -----------------------------------------------------------------------


def test_ac3_http_answer_holds_the_lines_and_names(rooms: AbsenceRooms) -> None:
    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TA, "after_seq": 3, "until_seq": 22}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["lines"] == [
        {
            "type": "word_completed",
            "seq": 8,
            "player_id": BOB,
            "clue": {"row": 2, "column": 0, "clue_index": 0},
        },
        rooms.play.entry_of(9).event.model_dump(mode="json"),
        rooms.play.entry_of(14).event.model_dump(mode="json"),
        {
            "type": "word_completed",
            "seq": 18,
            "player_id": BOB,
            "clue": {"row": 0, "column": 0, "clue_index": 1},
        },
    ]
    assert body["names"] == [{"player_id": BOB, "nickname": "BOB"}]
