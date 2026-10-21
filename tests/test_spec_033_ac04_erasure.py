"""Tests of spec 033, AC-4: deleting my account removes my personal data at once.

HTTP, with the app of the "Test harness" on a fake clock and both stores on one
file. `Bob` then `Zélie-Probe` join room R, so Bob is host; Zélie writes `T` at
(1, 0), asks a link from R and signs in. She also joins room S, links it with
`PUT /api/account/rooms` and times out there, so she is a past player of S (spec
032): `Dan` stays in S until her time-out, so that S ticks, then leaves it, and
the setup waits until S's stored snapshot holds her (play (a) of the criterion);
then she asks one more link and leaves it unused. `DELETE /api/account` erases
her: the account routes no longer know her, her nickname is `--` in R's state, log
and new snapshots and in S's past players, and the database files hold neither her
address nor her nickname as stored (`ZÉLIE-PROBE`), while they still hold `BOB`.

The three plays of the criterion that run the other paths of the erasure:

- (a) the rewrite of a stored snapshot: after the deletion, and again after a
  restart (a second app on the same file), the files hold neither her address nor
  `ZÉLIE-PROBE`, and R and S load with her records named `--`;
- (b) a room only in the store: the play runs up to the deletion in a first app,
  which stops; the deletion goes to a second app, with the old session in a
  `Cookie` header;
- (c) the checkpoint of `delete_account` on its own: an account with no room.

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
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
from httpx2 import Response

import nock.room
from nock.grid import Grid
from nock.protocol import EditLetter, LetterChanged, PlayerJoined, PlayerState
from nock.room import PastPlayer, RoomState
from nock.store import RoomStore
from spec017_harness import FakeClock, has_state_change, open_peer
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
    ANA_EMAIL,
    DATABASE_FILE_NAME,
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


class SnapshotRecorder(RoomStore):
    """A `RoomStore` that keeps each state it is given to save as a snapshot.

    The room tasks save from the engine's thread; the test reads from its own.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._saved_lock = threading.Lock()
        self._saved: list[RoomState] = []

    def save_snapshot(self, state: RoomState) -> None:
        """Save the snapshot, then keep the state."""
        super().save_snapshot(state)
        with self._saved_lock:
            self._saved.append(state)

    def saved_states(self) -> list[RoomState]:
        """The states saved so far, in the order they were saved."""
        with self._saved_lock:
            return list(self._saved)


class Played(NamedTuple):
    """What AC-4's play left just before `DELETE /api/account` was sent."""

    old_session: str
    unused_token: str
    r_code: str
    s_code: str
    zelie_id: str
    zelie_in_s: str
    joined_seq_in_r: int
    colour_in_r: int


class Erased(NamedTuple):
    """The app that answered `DELETE /api/account`, its answer, and the play."""

    app: AccountApp
    deletion: Response
    play: Played


def has_letter_changed(peer_messages: Sequence[object]) -> bool:
    return any(isinstance(message, LetterChanged) for message in peer_messages)


def is_past_player_of(registry_state: RoomState, player_id: str) -> bool:
    for past_player in registry_state.past_players:
        if past_player.player_id == player_id:
            return True
    return False


def holds_past_player(state: RoomState, player_id: str, nickname: str) -> bool:
    """Whether `state.past_players` holds that player with that nickname."""
    for past_player in state.past_players:
        if past_player.player_id == player_id and past_player.nickname == nickname:
            return True
    return False


def snapshot_of_s_holds_zelie(store: SnapshotRecorder, code: str, zelie: str) -> bool:
    """Whether a snapshot saved of room S holds Zélie as `ZÉLIE-PROBE`."""
    for state in store.saved_states():
        if state.code == code and holds_past_player(state, zelie, ZELIE_STORED):
            return True
    return False


def colour_of(state: RoomState, player_id: str) -> int:
    for player in state.players:
        if player.player_id == player_id:
            return player.colour
    pytest.fail(f"no player {player_id} in the room")


def player_joined_entries(store: RoomStore, code: str, player_id: str) -> list[int]:
    """The seq of each logged `player_joined` of a player in a room."""
    seqs: list[int] = []
    for entry in store.read_log(code):
        event = entry.event
        if isinstance(event, PlayerJoined) and event.player.player_id == player_id:
            seqs.append(event.seq)
    return seqs


def nicknames_joined(store: RoomStore, code: str, player_id: str) -> list[str]:
    """The nickname of each logged `player_joined` of a player in a room."""
    found: list[str] = []
    for entry in store.read_log(code):
        event = entry.event
        if isinstance(event, PlayerJoined) and event.player.player_id == player_id:
            found.append(event.player.nickname)
    return found


def nicknames_in_players(state: RoomState, player_id: str) -> list[str]:
    """The nickname of each record of a player in `state.players`."""
    return [p.nickname for p in state.players if p.player_id == player_id]


def nicknames_in_past_players(state: RoomState, player_id: str) -> list[str]:
    """The nickname of each record of a player in `state.past_players`."""
    return [p.nickname for p in state.past_players if p.player_id == player_id]


def loaded(store: RoomStore, code: str) -> RoomState:
    """The room as the store loads it; fails when the room is unknown."""
    state = store.load_room(code)
    assert state is not None, f"the store has no room {code}"
    return state


def play_up_to_the_deletion(
    app: AccountApp,
    store: SnapshotRecorder,
    stack: contextlib.ExitStack,
    clock: FakeClock,
    grid: Grid,
) -> Played:
    """AC-4's play, up to the moment `DELETE /api/account` is sent.

    Bob and Zélie stay connected to R in `stack`; nobody is left in S.
    """
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
    joined_seq_in_r = player_joined_entries(app.store, r_code, zelie_id)[0]

    # A room ticks only while someone is connected to it (specs 017 and 032):
    # Dan stays in S until Zélie's time-out, and sees her leave.
    with contextlib.ExitStack() as dan_stack:
        dan_in_s = open_peer(dan_stack, app.client, s_code, "Dan")
        with contextlib.ExitStack() as s_stack:
            zelie_s = open_peer(s_stack, app.client, s_code, ZELIE_NICKNAME)
            zelie_in_s = zelie_s.snapshot().you
            s_key = room_key(s_code, zelie_s.snapshot().resume_token)
            linked = app.client.put(ROOMS_PATH, json=s_key)
            assert linked.status_code == 204, linked.text
        dan_in_s.wait_until(
            lambda: has_state_change(dan_in_s, zelie_in_s, PlayerState.DISCONNECTED),
            "Zélie's disconnection from S",
        )
        clock.advance(RESUME_WINDOW + 1)
        wait_for(
            lambda: is_past_player_of(state_of(app.registry, s_code), zelie_in_s),
            "Zélie's time-out in S",
        )
    # Dan left S: its task stops and saves a snapshot (spec 018), which holds her.
    wait_for(
        lambda: snapshot_of_s_holds_zelie(store, s_code, zelie_in_s),
        "a stored snapshot of S that holds Zélie",
    )

    asked = ask_link(app.client, ZELIE_EMAIL)
    assert asked.status_code == 202, asked.text
    unused_token = last_token(app.mailer)
    return Played(
        old_session=old_session,
        unused_token=unused_token,
        r_code=r_code,
        s_code=s_code,
        zelie_id=zelie_id,
        zelie_in_s=zelie_in_s,
        joined_seq_in_r=joined_seq_in_r,
        colour_in_r=colour_in_r,
    )


@contextlib.contextmanager
def zelie_deleted(tmp_path: Path, clock: FakeClock, grid: Grid) -> Iterator[Erased]:
    """AC-4's play, up to the answer of `DELETE /api/account`."""
    store = SnapshotRecorder(tmp_path / DATABASE_FILE_NAME)
    with (
        account_app(
            tmp_path, clock, config=SEAT_BACK_SOCKET_CONFIG, store=store
        ) as app,
        contextlib.ExitStack() as stack,
    ):
        play = play_up_to_the_deletion(app, store, stack, clock, grid)
        deletion = app.client.delete(ACCOUNT_PATH)
        yield Erased(app=app, deletion=deletion, play=play)


@contextlib.contextmanager
def restarted_after_the_deletion(
    tmp_path: Path, clock: FakeClock, grid: Grid
) -> Iterator[Erased]:
    """Play (a): AC-4's play and deletion, then a second app on the same file.

    The first app stops, which saves a snapshot of each live room (spec 018);
    the second has its own registry and stores. Yields the second app, with the
    first app's deletion.
    """
    with zelie_deleted(tmp_path, clock, grid) as erased:
        assert erased.deletion.status_code == 204, erased.deletion.text
    with account_app(tmp_path, clock) as second:
        yield Erased(app=second, deletion=erased.deletion, play=erased.play)


@contextlib.contextmanager
def deleted_in_a_second_app(
    tmp_path: Path, clock: FakeClock, grid: Grid
) -> Iterator[Erased]:
    """Play (b): AC-4's play in a first app, which stops; the deletion in a second.

    The second app has its own registry, `RoomStore` and `AccountStore` on the
    same file, and a client with no cookie: the deletion carries the old session
    in a `Cookie` header. Nothing opens a room of that app before it.
    """
    store = SnapshotRecorder(tmp_path / DATABASE_FILE_NAME)
    with (
        account_app(
            tmp_path, clock, config=SEAT_BACK_SOCKET_CONFIG, store=store
        ) as first,
        contextlib.ExitStack() as stack,
    ):
        play = play_up_to_the_deletion(first, store, stack, clock, grid)
    with account_app(tmp_path, clock) as second:
        assert len(second.client.cookies) == 0
        deletion = second.client.delete(
            ACCOUNT_PATH, headers=with_session(play.old_session)
        )
        yield Erased(app=second, deletion=deletion, play=play)


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
            ACCOUNT_PATH, headers=with_session(erased.play.old_session)
        )

    assert response.status_code == 200
    assert response.json() == SIGNED_OUT


def test_ac4_the_old_cookie_gets_401_from_the_rooms_route(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        erased.app.client.cookies.clear()

        response = erased.app.client.get(
            ROOMS_PATH, headers=with_session(erased.play.old_session)
        )

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac4_the_unused_link_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        erased.app.client.cookies.clear()

        response = sign_in(erased.app.client, erased.play.unused_token)

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
        state = state_of(erased.app.registry, erased.play.r_code)

    zelie_id = erased.play.zelie_id
    records = [p for p in state.players if p.player_id == zelie_id]
    assert len(records) == 1
    assert records[0].nickname == FORMER_NICKNAME
    assert records[0].colour == erased.play.colour_in_r
    bobs = [p for p in state.players if p.player_id != zelie_id]
    assert [p.nickname for p in bobs] == ["BOB"]


def test_ac4_in_r_the_letter_keeps_its_author(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        state = state_of(erased.app.registry, erased.play.r_code)

    cell = cell_state(state, 1, 0)
    assert (cell.letter, cell.author) == ("T", erased.play.zelie_id)


def test_ac4_in_r_the_log_holds_her_join_with_the_nickname_dashes_at_its_seq(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        play = erased.play
        seqs = player_joined_entries(erased.app.store, play.r_code, play.zelie_id)
        nicknames = nicknames_joined(erased.app.store, play.r_code, play.zelie_id)

    assert seqs == [erased.play.joined_seq_in_r]
    assert nicknames == [FORMER_NICKNAME]


def test_ac4_a_new_client_of_r_sees_her_as_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with (
        zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased,
        contextlib.ExitStack() as stack,
    ):
        newcomer = open_peer(stack, erased.app.client, erased.play.r_code, "Cy")
        snapshot = newcomer.snapshot()

    zelie_id = erased.play.zelie_id
    views = [view for view in snapshot.players if view.player_id == zelie_id]
    assert len(views) == 1
    assert views[0].nickname == FORMER_NICKNAME


# ---- Room S: her past record ----------------------------------------------------


def test_ac4_in_s_her_past_record_has_the_nickname_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        state = state_of(erased.app.registry, erased.play.s_code)

    nicknames = nicknames_in_past_players(state, erased.play.zelie_in_s)
    assert nicknames == [FORMER_NICKNAME]


def test_ac4_in_s_the_log_holds_her_join_with_the_nickname_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deleted(tmp_path, fake_clock, fx01_grid) as erased:
        play = erased.play
        nicknames = nicknames_joined(erased.app.store, play.s_code, play.zelie_in_s)

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


# ---- (a) A stored snapshot that held her, then a restart ------------------------


def test_ac4_after_a_restart_the_files_hold_neither_her_address_nor_her_nickname(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with restarted_after_the_deletion(tmp_path, fake_clock, fx01_grid) as second:
        data = database_bytes(second.app.database_path)

    assert strings_in(data, [ZELIE_EMAIL, ZELIE_STORED]) == []


def test_ac4_after_a_restart_r_loads_with_her_record_named_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with restarted_after_the_deletion(tmp_path, fake_clock, fx01_grid) as second:
        state = state_of(second.app.registry, second.play.r_code)

    assert nicknames_in_players(state, second.play.zelie_id) == [FORMER_NICKNAME]


def test_ac4_after_a_restart_s_loads_with_her_past_record_named_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with restarted_after_the_deletion(tmp_path, fake_clock, fx01_grid) as second:
        state = state_of(second.app.registry, second.play.s_code)

    nicknames = nicknames_in_past_players(state, second.play.zelie_in_s)
    assert nicknames == [FORMER_NICKNAME]


# ---- (b) The deletion sent to a second app --------------------------------------


def test_ac4_a_deletion_in_a_second_app_answers_204_and_clears_the_cookie(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with deleted_in_a_second_app(tmp_path, fake_clock, fx01_grid) as erased:
        deletion = erased.deletion

    assert deletion.status_code == 204
    cookie = set_cookie_of(deletion)
    assert cookie.value == ""
    assert cookie.attributes.get("max-age") == "0", cookie


def test_ac4_after_a_deletion_in_a_second_app_r_loads_with_her_named_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with deleted_in_a_second_app(tmp_path, fake_clock, fx01_grid) as erased:
        state = loaded(erased.app.store, erased.play.r_code)

    assert nicknames_in_players(state, erased.play.zelie_id) == [FORMER_NICKNAME]


def test_ac4_after_a_deletion_in_a_second_app_s_loads_with_her_named_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with deleted_in_a_second_app(tmp_path, fake_clock, fx01_grid) as erased:
        state = loaded(erased.app.store, erased.play.s_code)

    nicknames = nicknames_in_past_players(state, erased.play.zelie_in_s)
    assert nicknames == [FORMER_NICKNAME]


def test_ac4_after_a_deletion_in_a_second_app_the_log_of_r_holds_her_join_as_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with deleted_in_a_second_app(tmp_path, fake_clock, fx01_grid) as erased:
        play = erased.play
        seqs = player_joined_entries(erased.app.store, play.r_code, play.zelie_id)
        nicknames = nicknames_joined(erased.app.store, play.r_code, play.zelie_id)

    assert seqs == [play.joined_seq_in_r]
    assert nicknames == [FORMER_NICKNAME]


def test_ac4_after_a_deletion_in_a_second_app_the_files_hold_neither_of_her_names(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with deleted_in_a_second_app(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion.status_code == 204
        data = database_bytes(erased.app.database_path)

    assert strings_in(data, [ZELIE_EMAIL, ZELIE_STORED]) == []


# ---- (c) An account with no room ------------------------------------------------


def test_ac4_an_account_with_no_room_is_in_the_files_before_its_deletion(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        link_and_sign_in(app, ANA_EMAIL, None)
        data = database_bytes(app.database_path)

    assert strings_in(data, [ANA_EMAIL]) == [ANA_EMAIL]


def test_ac4_after_the_deletion_of_an_account_with_no_room_no_file_holds_it(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        link_and_sign_in(app, ANA_EMAIL, None)
        deletion = app.client.delete(ACCOUNT_PATH)
        data = database_bytes(app.database_path)

    assert deletion.status_code == 204
    assert strings_in(data, [ANA_EMAIL]) == []


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
