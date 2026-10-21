"""Tests of spec 032, AC-4: the server gives a room's summary only to a member.

Python: `replay` of a `player_left` makes a past player of a player who timed out
or left, never of a removed one, and keeps at most `MAX_PAST_PLAYERS` of them,
dropping the oldest; `member_id` finds the member who holds a token; and
`team_nicknames` names each member once. `room_summary` and its JSON form, which
the browser tests of AC-5 answer with, are checked against the spec's example.

HTTP: room A (FX-01, grid number 1), written to a store file with its log, so that
only the store holds it, where Ana (TA), Bob (TB) and Cy (TC) joined at t0, Ana
wrote `T` at (1, 0) at t0 + 10, Ana removed Cy and Bob timed out; room B (FX-01
with no grid number), added with `add_room` while the clock reads t0, in which Dan
then joins over the room socket and writes a letter at t0 + 50, so that B's last
activity is Dan's edit in B's log, not B's creation. Dan's token, `TD` in the
criterion, is the one his join got; his socket stays open, so that he stays a
player of B. The registry's fake clock then reads t0 + 400.
`POST /api/rooms/summaries` answers with the summaries of the rooms that a key's
token is a member of. The shared setup is in `spec032_harness`.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    LeaveReason,
    LetterChanged,
    PlayerLeft,
    RemovePlayer,
)
from nock.room import LogEntry, RoomState, new_room, replay
from nock.server import create_app
from nock.store import RoomStore
from spec012_harness import join_as
from spec017_harness import FakeClock, Peer, open_peer
from spec032_harness import (
    ANA,
    BOB,
    CODE_A,
    CODE_B,
    CY,
    DAN,
    LIFE,
    NOBODYS_TOKEN,
    SEAT_BACK_CONFIG,
    SUMMARIES_PATH,
    T0,
    TA,
    TB,
    TC,
    TD,
    UNKNOWN_CODE,
    Run,
    abc_summary,
    grid_from_text,
    make_dist_dir,
    player_ids,
    post_summaries,
    summaries_request,
    summary_codes,
    utc,
    xyz_summary,
)

ANSWERS = ("TAMIS", "NAVAL", "MIME", "IDES", "SENT", "VIDE", "AMEN", "LEST")
WRONG_CODE_LIMIT = 10  # spec 011 AC-3


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def ana_and_bob(grid: Grid) -> Run:
    """Ana (TA, colour 0, host) and Bob (TB, colour 1) join at t0: seq 2."""
    run = Run(grid)
    run.join_new("Ana", ANA, TA, T0)
    run.join_new("Bob", BOB, TB, T0)
    return run


def bobs_past_record() -> object:
    return nock.room.PastPlayer(
        player_id=BOB, resume_token=TB, nickname="BOB", colour=1
    )


def bob_leaves(state: RoomState, reason: LeaveReason) -> RoomState:
    """`replay` of a `player_left` of Bob, seq 3."""
    left = PlayerLeft(seq=3, player_id=BOB, reason=reason)
    return replay(state, LogEntry(at=T0 + 400, event=left))


# ---- Python: past players ------------------------------------------------------


@pytest.mark.parametrize("reason", [LeaveReason.TIMED_OUT, LeaveReason.LEFT])
def test_ac4_a_player_who_times_out_or_leaves_becomes_a_past_player(
    fx01_grid: Grid, reason: LeaveReason
) -> None:
    run = ana_and_bob(fx01_grid)

    left = bob_leaves(run.state, reason)

    assert player_ids(left) == [ANA]
    assert left.past_players == (bobs_past_record(),)
    assert left.removed_tokens == ()


def test_ac4_a_removed_player_is_no_past_player_and_their_token_is_banned(
    fx01_grid: Grid,
) -> None:
    run = ana_and_bob(fx01_grid)

    removed = bob_leaves(run.state, LeaveReason.REMOVED)

    assert player_ids(removed) == [ANA]
    assert removed.past_players == ()
    assert removed.removed_tokens == (TB,)


def past_records(count: int) -> list[object]:
    """`count` past players, oldest first, with ids `past0`, `past1`..."""
    records: list[object] = []
    for number in range(count):
        record = nock.room.PastPlayer(
            player_id=f"past{number}",
            resume_token=f"token-of-past-{number:04d}",
            nickname=f"PAST {number}",
            colour=number % 8,
        )
        records.append(record)
    return records


def test_ac4_the_room_keeps_at_most_100_past_players(fx01_grid: Grid) -> None:
    assert nock.room.MAX_PAST_PLAYERS == 100
    earlier = past_records(nock.room.MAX_PAST_PLAYERS)
    run = ana_and_bob(fx01_grid)
    full = run.state.model_copy(update={"past_players": tuple(earlier)})

    left = bob_leaves(full, LeaveReason.TIMED_OUT)

    assert len(left.past_players) == 100
    assert left.past_players == (*earlier[1:], bobs_past_record())


def test_ac4_a_room_state_with_101_past_players_is_refused(fx01_grid: Grid) -> None:
    data = ana_and_bob(fx01_grid).state.model_dump(mode="json")
    records: list[dict[str, object]] = []
    for number in range(101):
        records.append(
            {
                "player_id": f"past{number}",
                "resume_token": f"token-of-past-{number:04d}",
                "nickname": f"PAST {number}",
                "colour": number % 8,
                "muted": False,
            }
        )
    data["past_players"] = records

    # The message names the field and its bound, not an unknown field.
    with pytest.raises(ValidationError, match=r"past_players\s+.*at most 100"):
        RoomState.model_validate(data)


# ---- Python: members -----------------------------------------------------------


def bob_timed_out(grid: Grid) -> RoomState:
    """Bob disconnects at t0 + 10 and times out at the tick of t0 + 311."""
    run = ana_and_bob(grid)
    run.disconnect(BOB, T0 + 10)
    run.tick(T0 + 311)
    assert player_ids(run.state) == [ANA]
    return run.state


def test_ac4_member_id_finds_a_player_who_timed_out(fx01_grid: Grid) -> None:
    assert nock.room.member_id(bob_timed_out(fx01_grid), TB) == BOB


def test_ac4_member_id_finds_a_player_of_the_room(fx01_grid: Grid) -> None:
    assert nock.room.member_id(bob_timed_out(fx01_grid), TA) == ANA


def test_ac4_member_id_is_none_for_a_removed_player(fx01_grid: Grid) -> None:
    run = ana_and_bob(fx01_grid)
    run.send(ANA, RemovePlayer(player_id=BOB), T0 + 5)

    assert nock.room.member_id(run.state, TB) is None


def test_ac4_member_id_is_none_for_a_token_no_player_had(fx01_grid: Grid) -> None:
    assert nock.room.member_id(bob_timed_out(fx01_grid), NOBODYS_TOKEN) is None


def test_ac4_team_nicknames_names_past_then_present_members_once(
    fx01_grid: Grid,
) -> None:
    run = Run(fx01_grid)
    run.join_new("Ana", ANA, TA, T0)
    run.join_new("Cy", CY, TC, T0)
    past = (
        bobs_past_record(),
        nock.room.PastPlayer(player_id=DAN, resume_token=TD, nickname="ANA", colour=3),
    )
    state = run.state.model_copy(update={"past_players": past})

    assert nock.room.team_nicknames(state) == ("BOB", "ANA", "CY")


# U+1E9E, the capital sharp s: compared exactly, it differs from SS.
STRASSE_WITH_CAPITAL_SHARP_S = "STRA\N{LATIN CAPITAL LETTER SHARP S}E"


def test_ac4_team_nicknames_keeps_a_capital_sharp_s_and_ss_as_two_names(
    fx01_grid: Grid,
) -> None:
    run = Run(fx01_grid)
    run.join_new("STRASSE", CY, TC, T0)
    past = (
        nock.room.PastPlayer(
            player_id=BOB,
            resume_token=TB,
            nickname=STRASSE_WITH_CAPITAL_SHARP_S,
            colour=1,
        ),
    )
    state = run.state.model_copy(update={"past_players": past})

    names = nock.room.team_nicknames(state)

    assert names == (STRASSE_WITH_CAPITAL_SHARP_S, "STRASSE")


# ---- Python: summaries ---------------------------------------------------------


def test_ac4_room_summary_holds_the_grid_the_members_and_the_last_edit_time(
    fx01_grid: Grid,
) -> None:
    run = ana_and_bob(fx01_grid)
    run.send(ANA, EditLetter(row=1, column=0, letter="T"), T0 + 10)

    summary = nock.room.room_summary(run.state, T0 + 10)

    assert summary == nock.room.RoomSummary(
        code=CODE_A,
        grid_number=1,
        width=5,
        height=5,
        players=("ANA", "BOB"),
        last_activity_at=utc(T0 + 10),
        solved=False,
    )


def test_ac4_a_summary_in_json_reads_as_the_example_of_the_spec() -> None:
    summary = nock.room.RoomSummary(
        code="XYZ789",
        grid_number=2,
        width=5,
        height=5,
        players=("Ana", "Bob"),
        last_activity_at=datetime(2026, 10, 14, 8, 30, tzinfo=UTC),
        solved=False,
    )

    assert summary.model_dump(mode="json") == {
        "code": "XYZ789",
        "grid_number": 2,
        "width": 5,
        "height": 5,
        "players": ["Ana", "Bob"],
        "last_activity_at": "2026-10-14T08:30:00Z",
        "solved": False,
    }


def test_ac4_the_summaries_the_page_tests_answer_with_are_dumped_summaries() -> None:
    first = nock.room.RoomSummary.model_validate(xyz_summary())
    second = nock.room.RoomSummary.model_validate(abc_summary())

    assert first.model_dump(mode="json") == xyz_summary()
    assert second.model_dump(mode="json") == abc_summary()
    assert second.grid_number is None
    assert second.last_activity_at == datetime(2026, 10, 13, 20, 5, tzinfo=UTC)


def test_ac4_a_summary_holds_no_letter_clue_or_answer(fx01_grid: Grid) -> None:
    run = ana_and_bob(fx01_grid)
    for column, letter in enumerate("TAMIS"):
        run.send(ANA, EditLetter(row=1, column=column, letter=letter), T0 + 10)

    text = nock.room.room_summary(run.state, T0 + 10).model_dump_json()

    for answer in ANSWERS:
        assert answer not in text
    for key in ('"cells"', '"clues"', '"letter"', '"answer"', '"grid"'):
        assert key not in text


# ---- HTTP ----------------------------------------------------------------------


class Rooms(NamedTuple):
    """The app of the HTTP part, its registry, its store, its clock, and Dan."""

    client: TestClient
    registry: RoomRegistry
    store: RoomStore
    clock: FakeClock
    dan_id: str
    dan_token: str  # the criterion's TD: the token Dan's join got


def room_a_play(grid: Grid) -> Run:
    """Room A: Ana writes `T`, removes Cy; Bob leaves and times out."""
    run = Run(grid, code=CODE_A, grid_number=1)
    run.join_new("Ana", ANA, TA, T0)
    run.join_new("Bob", BOB, TB, T0)
    run.join_new("Cy", CY, TC, T0)
    run.send(ANA, EditLetter(row=1, column=0, letter="T"), T0 + 10)
    run.send(ANA, RemovePlayer(player_id=CY), T0 + 15)
    run.disconnect(BOB, T0 + 20)
    run.tick(T0 + 321)
    assert player_ids(run.state) == [ANA]
    return run


def has_letter_changed(peer: Peer) -> bool:
    return any(isinstance(message, LetterChanged) for message in peer.events())


def dan_writes_in_room_b(
    stack: contextlib.ExitStack, client: TestClient, clock: FakeClock
) -> Peer:
    """At t0 + 50, Dan joins room B and writes `A` at (1, 1), over the socket."""
    clock.now = T0 + 50
    dan = open_peer(stack, client, CODE_B, "Dan")
    dan.send(EditLetter(row=1, column=1, letter="A"))
    dan.wait_until(lambda: has_letter_changed(dan), "Dan's letter")
    return dan


@pytest.fixture
def rooms(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> Iterator[Rooms]:
    play_a = room_a_play(fx01_grid)
    store = RoomStore(tmp_path / "nock.sqlite3")
    store.create_room(play_a.initial)
    store.append(CODE_A, play_a.log)
    registry = RoomRegistry(clock=fake_clock, store=store, config=SEAT_BACK_CONFIG)
    try:
        fake_clock.now = T0
        registry.add_room(new_room(CODE_B, fx01_grid, T0))
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client, contextlib.ExitStack() as dan_stack:
            dan = dan_writes_in_room_b(dan_stack, client, fake_clock)
            fake_clock.now = T0 + 400
            snapshot = dan.snapshot()
            yield Rooms(
                client,
                registry,
                store,
                fake_clock,
                snapshot.you,
                snapshot.resume_token,
            )
    finally:
        registry.close()
        store.close()


def summary_of_a() -> object:
    return nock.room.RoomSummary(
        code=CODE_A,
        grid_number=1,
        width=5,
        height=5,
        players=("BOB", "ANA"),
        last_activity_at=utc(T0 + 10),
        solved=False,
    )


def summary_of_b() -> object:
    return nock.room.RoomSummary(
        code=CODE_B,
        grid_number=None,
        width=5,
        height=5,
        players=("DAN",),
        last_activity_at=utc(T0 + 50),
        solved=False,
    )


def summaries_of(body: object) -> list[object]:
    """The summaries of an answer, read with `RoomSummary.model_validate`."""
    assert isinstance(body, list), body
    summaries: list[object] = []
    for item in body:
        summaries.append(nock.room.RoomSummary.model_validate(item))
    return summaries


def test_ac4_http_a_player_of_the_room_gets_its_summary(rooms: Rooms) -> None:
    response = post_summaries(rooms.client, [(CODE_A, TA)])

    assert response.status_code == 200
    assert summaries_of(response.json()) == [summary_of_a()]


def test_ac4_http_a_player_who_timed_out_gets_the_same_summary(rooms: Rooms) -> None:
    response = post_summaries(rooms.client, [(CODE_A, TB)])

    assert response.status_code == 200
    assert summaries_of(response.json()) == [summary_of_a()]


@pytest.mark.parametrize(
    ("code", "token"),
    [(CODE_A, TC), (CODE_A, NOBODYS_TOKEN), (UNKNOWN_CODE, TA)],
    ids=["removed_player", "token_no_player_had", "unknown_code"],
)
def test_ac4_http_a_key_with_no_members_token_gets_no_summary(
    rooms: Rooms, code: str, token: str
) -> None:
    response = post_summaries(rooms.client, [(code, token)])

    assert response.status_code == 200
    assert response.json() == []


def test_ac4_http_the_summary_of_b_takes_its_last_activity_from_dans_edit(
    rooms: Rooms,
) -> None:
    response = post_summaries(rooms.client, [(CODE_B, rooms.dan_token)])

    assert response.status_code == 200
    assert summaries_of(response.json()) == [summary_of_b()]


def test_ac4_http_several_rooms_come_newest_first_and_each_once(rooms: Rooms) -> None:
    keys = [(CODE_A, TA), (CODE_B, rooms.dan_token), (CODE_A, TB)]

    response = post_summaries(rooms.client, keys)

    assert response.status_code == 200
    assert summaries_of(response.json()) == [summary_of_b(), summary_of_a()]


def test_ac4_http_one_members_key_among_the_keys_of_a_room_is_enough(
    rooms: Rooms,
) -> None:
    response = post_summaries(rooms.client, [(CODE_A, NOBODYS_TOKEN), (CODE_A, TB)])

    assert response.status_code == 200
    assert summaries_of(response.json()) == [summary_of_a()]


def test_ac4_http_a_body_of_100_keys_is_accepted(rooms: Rooms) -> None:
    response = post_summaries(rooms.client, [(CODE_A, TA)] * 100)

    assert response.status_code == 200
    assert summary_codes(response.json()) == [CODE_A]


def extra_key_at_the_top() -> dict[str, object]:
    body = summaries_request([(CODE_A, TA)])
    body["extra"] = 1
    return body


def extra_key_in_a_key() -> dict[str, object]:
    return {"rooms": [{"code": CODE_A, "resume_token": TA, "extra": 1}]}


@pytest.mark.parametrize(
    "body",
    [
        summaries_request([(CODE_A, TA)] * 101),
        summaries_request([("abc", TA)]),
        summaries_request([(CODE_A, "x" * 15)]),
        extra_key_at_the_top(),
        extra_key_in_a_key(),
    ],
    ids=["101_keys", "code_abc", "token_of_15", "extra_key", "extra_key_in_a_key"],
)
def test_ac4_http_a_body_that_is_not_valid_answers_422(
    rooms: Rooms, body: dict[str, object]
) -> None:
    response = rooms.client.post(SUMMARIES_PATH, json=body)

    assert response.status_code == 422


def test_ac4_http_a_body_that_is_not_json_answers_422(rooms: Rooms) -> None:
    response = rooms.client.post(
        SUMMARIES_PATH,
        content="not json",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422


def test_ac4_http_a_room_only_the_store_holds_keeps_the_same_log(
    rooms: Rooms,
) -> None:
    before = rooms.store.read_log(CODE_A)

    response = post_summaries(rooms.client, [(CODE_A, TA)])

    assert response.status_code == 200
    assert rooms.store.read_log(CODE_A) == before


def test_ac4_http_an_expired_room_is_left_out_and_deleted(rooms: Rooms) -> None:
    rooms.clock.now = T0 + 11 + LIFE

    response = post_summaries(rooms.client, [(CODE_A, TA), (CODE_B, rooms.dan_token)])

    assert response.status_code == 200
    assert summary_codes(response.json()) == [CODE_B]
    assert rooms.store.has_room(CODE_A) is False


def test_ac4_http_the_route_is_not_counted_by_the_wrong_code_throttle(
    rooms: Rooms,
) -> None:
    for _ in range(WRONG_CODE_LIMIT + 2):
        refused = post_summaries(rooms.client, [(UNKNOWN_CODE, TA)])
        assert refused.json() == []

    with contextlib.ExitStack() as stack:
        _, snapshot = join_as(stack, rooms.client, CODE_B, "Eve")

    assert [view.nickname for view in snapshot.players] == ["DAN", "EVE"]


def test_ac4_http_a_summary_holds_no_answer(rooms: Rooms) -> None:
    response = post_summaries(rooms.client, [(CODE_A, TA), (CODE_B, rooms.dan_token)])

    assert response.status_code == 200
    assert summary_codes(response.json()) == [CODE_B, CODE_A]
    text = json.dumps(response.json())
    for answer in ANSWERS:
        assert answer not in text


# ---- The registry --------------------------------------------------------------


def test_ac4_the_registry_gives_its_store(rooms: Rooms) -> None:
    assert rooms.registry.store is rooms.store


def test_ac4_peek_room_reads_a_stored_room_without_making_it_live(
    rooms: Rooms,
) -> None:
    before = rooms.store.read_log(CODE_A)

    peeked = rooms.registry.peek_room(CODE_A)

    assert peeked == rooms.store.load_room(CODE_A)
    assert rooms.store.read_log(CODE_A) == before


def test_ac4_the_registrys_member_id_reads_the_rooms_latest_state(
    rooms: Rooms,
) -> None:
    registry = rooms.registry

    assert registry.member_id(CODE_A, TB) == BOB
    assert registry.member_id(CODE_A, TA) == ANA
    assert registry.member_id(CODE_A, TC) is None
    assert registry.member_id(CODE_B, rooms.dan_token) == rooms.dan_id
    assert registry.member_id(UNKNOWN_CODE, TA) is None


def test_ac4_summaries_with_the_same_last_activity_follow_the_code_order(
    fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    registry = RoomRegistry(clock=fake_clock, config=SEAT_BACK_CONFIG)
    try:
        for code in [CODE_B, CODE_A]:
            run = Run(fx01_grid, code=code)
            run.join_new("Ana", ANA, TA, T0)
            registry.add_room(run.state)
        keys = [
            nock.room.RoomKey(code=CODE_B, resume_token=TA),
            nock.room.RoomKey(code=CODE_A, resume_token=TA),
        ]
        summaries = registry.room_summaries(keys)
    finally:
        registry.close()

    codes = [summary.code for summary in summaries]
    assert codes == [CODE_A, CODE_B]
