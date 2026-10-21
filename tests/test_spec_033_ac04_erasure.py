"""Tests of spec 033, AC-4: deleting my account removes my personal data at once.

HTTP, with the app of the "Test harness" on a fake clock and both stores on one
file. `Bob` then `Zélie-Probe` join room R, so Bob is host; Zélie writes `T` at
(1, 0), asks a link from R and signs in. She also joins room S, links it with
`PUT /api/account/rooms` and times out there, so she is a past player of S (spec
032); then she asks one more link and leaves it unused. `DELETE /api/account`
erases her: the account routes no longer know her, her nickname is `--` in R's
state, log and new snapshots and in S's past players, and the database files hold
neither her address nor her nickname as stored (`ZÉLIE-PROBE`), while they still
hold `BOB`.

Python, for "Seat back of a former player": a past player named `--` who comes
back with their token is seated back as `--`, without spec 012's suffix, even
when a player of `players` is `--` too.

The rooms tick every 0.05 s with spec 017's resume window of 300 s
(`SEAT_BACK_SOCKET_CONFIG` of spec 032), so that Zélie times out in S once the
fake clock moved past it; no other rule changes anything on a tick. The shared
setup is in `spec033_harness`, `spec032_harness` and `spec017_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
from httpx2 import Response

import nock.room
from nock.grid import Grid
from nock.protocol import EditLetter, LetterChanged, PlayerJoined
from nock.room import PastPlayer, RoomState
from spec017_harness import FakeClock, open_peer
from spec032_harness import (
    BOB,
    CY,
    DAN,
    LEFT_AT,
    SEAT_BACK_AT,
    SEAT_BACK_SOCKET_CONFIG,
    T0,
    TB,
    TC,
    TD,
    TIMED_OUT_AT,
    Run,
    events_of,
    grid_from_text,
)
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    NOT_AUTHORIZED,
    NOT_FOUND,
    ROOMS_PATH,
    SESSION_COOKIE,
    SIGNED_OUT,
    ZELIE_EMAIL,
    AccountApp,
    account_app,
    ask_link,
    cell_state,
    database_bytes,
    last_token,
    link_and_sign_in,
    room_key,
    set_cookie_of,
    sign_in,
    state_of,
    strings_in,
    wait_for,
    with_session,
)

ZELIE_NICKNAME = "Zélie-Probe"
ZELIE_STORED = "ZÉLIE-PROBE"  # as the server stores it (spec 012 decision 12)
RESUME_WINDOW = 300.0  # spec 017's resume window, RoomConfig's default


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class Erased(NamedTuple):
    """What AC-4's play left once `DELETE /api/account` was answered."""

    app: AccountApp
    deletion: Response
    old_session: str
    unused_token: str
    r_code: str
    s_code: str
    zelie_id: str
    zelie_in_s: str
    joined_seq_in_r: int
    colour_in_r: int


def has_letter_changed(peer_messages: Sequence[object]) -> bool:
    return any(isinstance(message, LetterChanged) for message in peer_messages)


def is_past_player_of(registry_state: RoomState, player_id: str) -> bool:
    for past_player in registry_state.past_players:
        if past_player.player_id == player_id:
            return True
    return False


def colour_of(state: RoomState, player_id: str) -> int:
    for player in state.players:
        if player.player_id == player_id:
            return player.colour
    pytest.fail(f"no player {player_id} in the room")


def player_joined_entries(app: AccountApp, code: str, player_id: str) -> list[int]:
    """The seq of each logged `player_joined` of a player in a room."""
    seqs: list[int] = []
    for entry in app.store.read_log(code):
        event = entry.event
        if isinstance(event, PlayerJoined) and event.player.player_id == player_id:
            seqs.append(event.seq)
    return seqs


def nicknames_joined(app: AccountApp, code: str, player_id: str) -> list[str]:
    """The nickname of each logged `player_joined` of a player in a room."""
    found: list[str] = []
    for entry in app.store.read_log(code):
        event = entry.event
        if isinstance(event, PlayerJoined) and event.player.player_id == player_id:
            found.append(event.player.nickname)
    return found


@contextlib.contextmanager
def zelie_deleted(tmp_path: Path, clock: FakeClock, grid: Grid) -> Iterator[Erased]:
    """AC-4's play, up to the answer of `DELETE /api/account`."""
    with (
        account_app(tmp_path, clock, config=SEAT_BACK_SOCKET_CONFIG) as app,
        contextlib.ExitStack() as stack,
    ):
        r_code = app.registry.register_room(grid, grid_number=1)
        s_code = app.registry.register_room(grid, grid_number=1)
        open_peer(stack, app.client, r_code, "Bob")
        zelie = open_peer(stack, app.client, r_code, ZELIE_NICKNAME)
        zelie_id = zelie.snapshot().you
        zelie_token = zelie.snapshot().resume_token
        colour_in_r = colour_of(state_of(app.registry, r_code), zelie_id)
        zelie.send(EditLetter(row=1, column=0, letter="T"))
        zelie.wait_until(lambda: has_letter_changed(zelie.events()), "Zélie's T")
        signed_in = link_and_sign_in(app, ZELIE_EMAIL, room_key(r_code, zelie_token))
        old_session = set_cookie_of(signed_in).value
        joined_seq_in_r = player_joined_entries(app, r_code, zelie_id)[0]

        with contextlib.ExitStack() as s_stack:
            zelie_s = open_peer(s_stack, app.client, s_code, ZELIE_NICKNAME)
            zelie_in_s = zelie_s.snapshot().you
            s_key = room_key(s_code, zelie_s.snapshot().resume_token)
            linked = app.client.put(ROOMS_PATH, json=s_key)
            assert linked.status_code == 204, linked.text
        clock.advance(RESUME_WINDOW + 1)
        wait_for(
            lambda: is_past_player_of(state_of(app.registry, s_code), zelie_in_s),
            "Zélie's time-out in S",
        )

        asked = ask_link(app.client, ZELIE_EMAIL)
        assert asked.status_code == 202, asked.text
        unused_token = last_token(app.mailer)

        deletion = app.client.delete(ACCOUNT_PATH)
        yield Erased(
            app=app,
            deletion=deletion,
            old_session=old_session,
            unused_token=unused_token,
            r_code=r_code,
            s_code=s_code,
            zelie_id=zelie_id,
            zelie_in_s=zelie_in_s,
            joined_seq_in_r=joined_seq_in_r,
            colour_in_r=colour_in_r,
        )


# ---- The answer and the account routes ------------------------------------------


def test_ac4_delete_answers_204_and_clears_the_session_cookie(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        deletion = erased.deletion

    assert deletion.status_code == 204
    cookie = set_cookie_of(deletion)
    assert cookie.value == ""
    assert cookie.attributes.get("max-age") == "0", cookie
    assert cookie.attributes.get("path") == "/", cookie


def test_ac4_the_old_cookie_then_says_signed_out(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        erased.app.client.cookies.clear()

        response = erased.app.client.get(
            ACCOUNT_PATH, headers=with_session(erased.old_session)
        )

    assert response.status_code == 200
    assert response.json() == SIGNED_OUT


def test_ac4_the_old_cookie_gets_401_from_the_rooms_route(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        erased.app.client.cookies.clear()

        response = erased.app.client.get(
            ROOMS_PATH, headers=with_session(erased.old_session)
        )

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac4_the_unused_link_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        erased.app.client.cookies.clear()

        response = sign_in(erased.app.client, erased.unused_token)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac4_delete_without_a_session_answers_401(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        response = app.client.delete(ACCOUNT_PATH)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED
    assert SESSION_COOKIE not in response.headers.get("set-cookie", "")


# ---- Room R: the state, the letter, the log, a new snapshot ---------------------


def test_ac4_in_r_her_record_keeps_its_id_and_colour_with_the_nickname_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        state = state_of(erased.app.registry, erased.r_code)

    records = [p for p in state.players if p.player_id == erased.zelie_id]
    assert len(records) == 1
    assert records[0].nickname == FORMER_NICKNAME
    assert records[0].colour == erased.colour_in_r
    bobs = [p for p in state.players if p.player_id != erased.zelie_id]
    assert [p.nickname for p in bobs] == ["BOB"]


def test_ac4_in_r_the_letter_keeps_its_author(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        state = state_of(erased.app.registry, erased.r_code)

    cell = cell_state(state, 1, 0)
    assert (cell.letter, cell.author) == ("T", erased.zelie_id)


def test_ac4_in_r_the_log_holds_her_join_with_the_nickname_dashes_at_its_seq(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        seqs = player_joined_entries(erased.app, erased.r_code, erased.zelie_id)
        nicknames = nicknames_joined(erased.app, erased.r_code, erased.zelie_id)

    assert seqs == [erased.joined_seq_in_r]
    assert nicknames == [FORMER_NICKNAME]


def test_ac4_a_new_client_of_r_sees_her_as_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with (
        zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased,
        contextlib.ExitStack() as stack,
    ):
        newcomer = open_peer(stack, erased.app.client, erased.r_code, "Cy")
        snapshot = newcomer.snapshot()

    views = [view for view in snapshot.players if view.player_id == erased.zelie_id]
    assert len(views) == 1
    assert views[0].nickname == FORMER_NICKNAME


# ---- Room S: her past record ----------------------------------------------------


def test_ac4_in_s_her_past_record_has_the_nickname_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        state = state_of(erased.app.registry, erased.s_code)

    records = [p for p in state.past_players if p.player_id == erased.zelie_in_s]
    assert len(records) == 1
    assert records[0].nickname == FORMER_NICKNAME


def test_ac4_in_s_the_log_holds_her_join_with_the_nickname_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        nicknames = nicknames_joined(erased.app, erased.s_code, erased.zelie_in_s)

    assert nicknames == [FORMER_NICKNAME]


# ---- The database files ---------------------------------------------------------


def test_ac4_the_database_files_hold_neither_her_address_nor_her_nickname(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion.status_code == 204
        data = database_bytes(erased.app.database_path)

    assert strings_in(data, [ZELIE_EMAIL, ZELIE_STORED]) == []


def test_ac4_the_database_files_still_hold_bob(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion.status_code == 204
        data = database_bytes(erased.app.database_path)

    assert strings_in(data, ["BOB"]) == ["BOB"]


def test_ac4_before_the_deletion_the_files_held_her_address_and_nickname(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app, contextlib.ExitStack() as stack:
        code = app.registry.register_room(fx01_grid, grid_number=1)
        zelie = open_peer(stack, app.client, code, ZELIE_NICKNAME)
        key = room_key(code, zelie.snapshot().resume_token)
        link_and_sign_in(app, ZELIE_EMAIL, key)
        data = database_bytes(app.database_path)

    assert strings_in(data, [ZELIE_EMAIL, ZELIE_STORED]) == [ZELIE_EMAIL, ZELIE_STORED]


# ---- Python: a former player seated back ----------------------------------------


def former_players_room(grid: Grid) -> Run:
    """A FX-01 room: `BOB` and a player `--` in `players`, a past player `--`.

    Bob, Cy and Dan join at t0; Dan leaves and times out, so he is a past player
    whose token is `TD` (the `TP` of the criterion). Then Cy's record and Dan's
    past record get the nickname `--`, as an erasure gives them.
    """
    run = Run(grid)
    run.join_new("Bob", BOB, TB, T0)
    run.join_new("Cy", CY, TC, T0)
    run.join_new("Dan", DAN, TD, T0)
    run.disconnect(DAN, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    players: list[nock.room.PlayerRecord] = []
    for player in run.state.players:
        if player.player_id == CY:
            players.append(player.model_copy(update={"nickname": FORMER_NICKNAME}))
        else:
            players.append(player)
    past_players: list[PastPlayer] = []
    for past_player in run.state.past_players:
        if past_player.player_id == DAN:
            erased = past_player.model_copy(update={"nickname": FORMER_NICKNAME})
            past_players.append(erased)
        else:
            past_players.append(past_player)
    run.state = run.state.model_copy(
        update={"players": tuple(players), "past_players": tuple(past_players)}
    )
    assert [p.nickname for p in run.state.players] == ["BOB", FORMER_NICKNAME]
    assert [p.player_id for p in run.state.past_players] == [DAN]
    return run


def test_ac4_python_the_former_player_nickname_is_two_hyphens() -> None:
    assert nock.room.FORMER_PLAYER_NICKNAME == "--"


def test_ac4_python_a_former_player_seated_back_joins_as_dashes_without_suffix(
    fx01_grid: Grid,
) -> None:
    run = former_players_room(fx01_grid)

    outcome = run.join("Autre", TD, SEAT_BACK_AT)

    events = events_of(outcome)
    assert len(events) == 1
    event = events[0]
    assert isinstance(event, PlayerJoined)
    assert event.player.player_id == DAN
    assert event.player.nickname == FORMER_NICKNAME


def test_ac4_python_then_two_players_of_the_room_are_named_dashes(
    fx01_grid: Grid,
) -> None:
    run = former_players_room(fx01_grid)

    outcome = run.join("Autre", TD, SEAT_BACK_AT)

    nicknames = [p.nickname for p in outcome.state.players]
    assert sorted(nicknames) == sorted(["BOB", FORMER_NICKNAME, FORMER_NICKNAME])
    dans = [p for p in outcome.state.players if p.player_id == DAN]
    assert [p.nickname for p in dans] == [FORMER_NICKNAME]


def test_ac4_python_another_nickname_still_gets_spec_012_s_suffix(
    fx01_grid: Grid,
) -> None:
    run = Run(fx01_grid)
    run.join_new("Bob", BOB, TB, T0)
    run.join_new("Dan", DAN, TD, T0)
    run.disconnect(DAN, LEFT_AT)
    run.tick(TIMED_OUT_AT)
    run.join_new("Dan", CY, TC, T0 + 320)

    outcome = run.join("Autre", TD, SEAT_BACK_AT)

    event = events_of(outcome)[-1]
    assert isinstance(event, PlayerJoined)
    assert event.player.player_id == DAN
    assert event.player.nickname == "DAN 2"
