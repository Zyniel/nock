"""Tests of spec 034, AC-1: the server names the cells that changed in an absence.

Python: `RoomStore.load_room_at`, `RoomRegistry.catch_up` on the reference
absence ABSENCE (seq 1 to 22) of the spec's harness, and `build_catch_up` for the
edge cases on hand-made plays. HTTP: `POST /api/rooms/{code}/catch-up` on the
same registry. The shared setup is in `spec034_harness`.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import CellRef, Check, Erase, WordTarget
from nock.room import PlayerRecord
from nock.store import RoomStore
from spec034_harness import (
    ANA,
    ANSWERS,
    BOB,
    CODE,
    NOBODYS_TOKEN,
    TA,
    TB,
    TICK_AT,
    UNKNOWN_CODE,
    AbsenceRooms,
    Play,
    absence_rooms,
    catch_up_path,
    cell_refs,
    grid_from_text,
    known_catch_up,
    registry_catch_up,
)

ABSENCE_CELLS = [(0, 1), (1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (3, 1), (4, 1)]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def rooms(tmp_path: Path, fx01_grid: Grid) -> Iterator[AbsenceRooms]:
    with absence_rooms(tmp_path, fx01_grid) as found:
        yield found


def nicknames_by_id(players: tuple[PlayerRecord, ...]) -> list[tuple[str, str]]:
    """The (player id, nickname) of each player record, in order."""
    pairs: list[tuple[str, str]] = []
    for player in players:
        pairs.append((player.player_id, player.nickname))
    return pairs


# ---- RoomStore.load_room_at ------------------------------------------------------


def test_ac1_load_room_at_gives_the_room_just_after_the_seen_seq(
    rooms: AbsenceRooms,
) -> None:
    state = rooms.store.load_room_at(CODE, 3)

    live = rooms.play.states[3]
    assert state is not None
    assert state.seq == 3
    assert state.cells == live.cells
    assert nicknames_by_id(state.players) == [(ANA, "ANA"), (BOB, "BOB")]


def test_ac1_load_room_at_beyond_the_log_gives_the_latest_stored_state(
    rooms: AbsenceRooms,
) -> None:
    latest = rooms.store.load_room(CODE)

    assert latest is not None
    assert latest.seq == 22
    assert rooms.store.load_room_at(CODE, 99) == latest


def test_ac1_load_room_at_an_unknown_room_is_none(rooms: AbsenceRooms) -> None:
    assert rooms.store.load_room_at(UNKNOWN_CODE, 3) is None


def test_ac1_load_room_at_before_the_first_snapshot_is_none(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    # Edge case "Range limits": a room added in a later state, as `add_room` allows.
    play = Play(fx01_grid)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    play.write(ANA, 1, 0, "T")
    store = RoomStore(tmp_path / "later.sqlite3")
    try:
        store.create_room(play.state)
        assert store.load_room_at(CODE, 2) is None
        assert store.load_room_at(CODE, 3) == play.state
    finally:
        store.close()


# ---- RoomRegistry.catch_up --------------------------------------------------------


def test_ac1_catch_up_names_the_changed_cells_in_row_major_order(
    rooms: AbsenceRooms,
) -> None:
    answer = known_catch_up(rooms.registry, 3, 22)

    assert answer.cells == cell_refs(ABSENCE_CELLS)
    assert CellRef(row=1, column=0) not in answer.cells
    assert answer.after_seq == 3
    assert answer.until_seq == 22


def test_ac1_catch_up_after_seq_15_names_the_later_cells_only(
    rooms: AbsenceRooms,
) -> None:
    answer = known_catch_up(rooms.registry, 15, 22)

    assert answer.cells == cell_refs([(0, 1), (3, 1), (4, 1)])


@pytest.mark.parametrize("after_seq", [22, 25])
def test_ac1_catch_up_from_the_room_seq_or_beyond_is_empty(
    rooms: AbsenceRooms, after_seq: int
) -> None:
    answer = known_catch_up(rooms.registry, after_seq, 22)

    assert answer.after_seq == after_seq
    assert answer.until_seq == 22
    assert answer.cells == ()
    assert answer.lines == ()
    assert answer.names == ()


def test_ac1_catch_up_after_seq_at_or_above_until_seq_is_empty(
    rooms: AbsenceRooms,
) -> None:
    # Edge case "Range limits": `after_seq` at or above `until_seq`.
    answer = known_catch_up(rooms.registry, 10, 9)

    assert (answer.after_seq, answer.until_seq) == (10, 9)
    assert answer.cells == ()
    assert answer.lines == ()
    assert answer.names == ()


def test_ac1_catch_up_until_seq_beyond_the_room_reads_to_its_last_event(
    rooms: AbsenceRooms,
) -> None:
    up_to_22 = known_catch_up(rooms.registry, 3, 22)
    up_to_99 = known_catch_up(rooms.registry, 3, 99)

    assert up_to_99.until_seq == 99
    assert up_to_99.after_seq == 3
    assert up_to_99.cells == up_to_22.cells
    assert up_to_99.lines == up_to_22.lines
    assert up_to_99.names == up_to_22.names


def test_ac1_catch_up_until_seq_stops_the_absence(rooms: AbsenceRooms) -> None:
    # The absence is `after_seq < seq <= until_seq`: seq 5 to 8 only here.
    answer = known_catch_up(rooms.registry, 4, 8)

    assert answer.cells == cell_refs([(2, 1), (2, 2), (2, 3), (2, 4)])


def test_ac1_catch_up_counts_my_own_changes_this_device_did_not_see(
    rooms: AbsenceRooms,
) -> None:
    # Edge case "My own changes": Ana's own letter at seq 3, asked with her token.
    answer = known_catch_up(rooms.registry, 2, 22, token=TA)

    assert answer.cells == cell_refs(
        [(0, 1), (1, 0), (1, 1), (2, 1), (2, 2), (2, 3), (2, 4), (3, 1), (4, 1)]
    )


def test_ac1_catch_up_counts_cells_locked_with_their_letter_unchanged(
    rooms: AbsenceRooms,
) -> None:
    # Edge case "Locked by a check": VIDE was written up to seq 8, locked 10 to 13.
    answer = known_catch_up(rooms.registry, 8, 13)

    assert answer.cells == cell_refs([(2, 1), (2, 2), (2, 3), (2, 4)])


def test_ac1_catch_up_with_a_past_players_token(rooms: AbsenceRooms) -> None:
    answer = known_catch_up(rooms.registry, 3, 22, token=TB)

    assert answer.cells == cell_refs(ABSENCE_CELLS)


def test_ac1_catch_up_with_a_token_no_player_had_is_none(
    rooms: AbsenceRooms,
) -> None:
    assert registry_catch_up(rooms.registry, 3, 22, token=NOBODYS_TOKEN) is None


def test_ac1_catch_up_of_an_unknown_room_is_none(rooms: AbsenceRooms) -> None:
    assert registry_catch_up(rooms.registry, 3, 22, code=UNKNOWN_CODE) is None


def test_ac1_catch_up_of_a_room_with_no_snapshot_at_the_seen_seq_is_none(
    fx01_grid: Grid,
) -> None:
    # Edge case "Range limits": a room added in a later state gets None.
    from nock.hub import RoomRegistry

    play = Play(fx01_grid)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    play.write(ANA, 1, 0, "T")
    registry = RoomRegistry(clock=lambda: TICK_AT)
    try:
        registry.add_room(play.state)
        assert registry_catch_up(registry, 1, 3) is None
        known = known_catch_up(registry, 3, 3)
        assert known.cells == ()
    finally:
        registry.close()


def test_ac1_catch_up_only_reads(rooms: AbsenceRooms) -> None:
    log_before = rooms.store.read_log(CODE)

    known_catch_up(rooms.registry, 3, 22)

    assert rooms.store.read_log(CODE) == log_before
    assert rooms.store.load_room(CODE) == rooms.play.state


# ---- build_catch_up: the cells of hand-made plays ---------------------------------


def test_ac1_build_catch_up_lists_a_cell_changed_many_times_once(
    fx01_grid: Grid,
) -> None:
    from nock.catch_up import build_catch_up

    play = Play(fx01_grid)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    before = play.state
    play.write(BOB, 3, 3, "X", now=1_000_001.0)
    play.send(BOB, Erase(row=3, column=3), now=1_000_002.0)
    play.write(BOB, 3, 3, "E", now=1_000_003.0)
    play.write(BOB, 1, 2, "M", now=1_000_004.0)

    answer = build_catch_up(2, 6, before, play.entries_after(2))

    assert answer.cells == cell_refs([(1, 2), (3, 3)])
    assert (answer.after_seq, answer.until_seq) == (2, 6)


def test_ac1_build_catch_up_leaves_out_cells_only_struck_through(
    fx01_grid: Grid,
) -> None:
    # Edge case "Wrong marks": a wrong letter checked is struck through, not locked.
    from nock.catch_up import build_catch_up

    play = Play(fx01_grid)
    play.join("Ana", ANA, TA)
    play.join("Bob", BOB, TB)
    play.write(BOB, 2, 1, "X")
    play.write(BOB, 2, 2, "I", now=1_000_001.0)
    before = play.state
    play.send(BOB, Check(target=WordTarget(row=2, column=0, clue_index=0)), 1_000_002.0)
    entries = play.entries_after(before.seq)

    answer = build_catch_up(before.seq, play.state.seq, before, entries)

    assert answer.cells == cell_refs([(2, 2)])


# ---- HTTP -----------------------------------------------------------------------


def assert_the_route_answers_a_member(rooms: AbsenceRooms) -> None:
    """The route answers 200 to a member, so that a 404 below is the route's own."""
    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TA, "after_seq": 3, "until_seq": 22}
    )
    assert response.status_code == 200


def test_ac1_http_answers_the_catch_up_as_json(rooms: AbsenceRooms) -> None:
    expected = known_catch_up(rooms.registry, 3, 22)

    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TA, "after_seq": 3, "until_seq": 22}
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")
    assert response.json()["after_seq"] == 3
    assert response.json()["until_seq"] == 22
    assert response.json()["cells"] == [
        {"row": 0, "column": 1},
        {"row": 1, "column": 1},
        {"row": 2, "column": 1},
        {"row": 2, "column": 2},
        {"row": 2, "column": 3},
        {"row": 2, "column": 4},
        {"row": 3, "column": 1},
        {"row": 4, "column": 1},
    ]


def test_ac1_http_answers_a_past_player_too(rooms: AbsenceRooms) -> None:
    expected = known_catch_up(rooms.registry, 3, 22, token=TB)

    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TB, "after_seq": 3, "until_seq": 22}
    )

    assert response.status_code == 200
    assert response.json() == expected.model_dump(mode="json")


@pytest.mark.parametrize(
    ("code", "token"),
    [(CODE, NOBODYS_TOKEN), (UNKNOWN_CODE, TA), ("abc123", TA), ("ABC12", TA)],
    ids=["token-nobody-had", "unknown-room", "small-letters", "five-characters"],
)
def test_ac1_http_answers_404_without_saying_why(
    rooms: AbsenceRooms, code: str, token: str
) -> None:
    assert_the_route_answers_a_member(rooms)

    response = rooms.client.post(
        catch_up_path(code),
        json={"resume_token": token, "after_seq": 3, "until_seq": 22},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_ac1_http_404_answers_do_not_count_against_the_wrong_code_throttle(
    rooms: AbsenceRooms,
) -> None:
    # "nock.server": spec 011's throttle does not count the catch-up's 404.
    assert_the_route_answers_a_member(rooms)
    for _ in range(12):
        response = rooms.client.post(
            catch_up_path(UNKNOWN_CODE),
            json={"resume_token": TA, "after_seq": 3, "until_seq": 22},
        )
        assert response.status_code == 404

    recap = rooms.client.get("/api/rooms/YYYYYY/recap")

    assert recap.status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"resume_token": TA, "after_seq": -1, "until_seq": 22},
        {"resume_token": TA, "after_seq": 3},
        {"resume_token": TA, "after_seq": 3, "until_seq": 22, "extra": 1},
    ],
    ids=["after-seq-minus-1", "no-until-seq", "extra-key"],
)
def test_ac1_http_refuses_an_invalid_request_with_422(
    rooms: AbsenceRooms, body: dict[str, object]
) -> None:
    response = rooms.client.post(catch_up_path(), json=body)

    assert response.status_code == 422


def test_ac1_http_request_leaves_the_log_unchanged(rooms: AbsenceRooms) -> None:
    log_before = rooms.store.read_log(CODE)

    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TA, "after_seq": 3, "until_seq": 22}
    )

    assert response.status_code == 200
    assert rooms.store.read_log(CODE) == log_before


def test_ac1_http_body_holds_no_answer(rooms: AbsenceRooms) -> None:
    response = rooms.client.post(
        catch_up_path(), json={"resume_token": TA, "after_seq": 3, "until_seq": 22}
    )

    assert response.status_code == 200
    text = json.dumps(response.json())
    for answer in ANSWERS:
        assert answer not in text
    assert '"answer"' not in text
