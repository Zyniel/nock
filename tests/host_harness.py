"""Shared setup of the tests of lobby/host about members and the creator (AC-9 to
AC-16), and of the account seat of lobby/joining (AC-21).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_host_*.py` and `tests/test_joining_account_seat.py`:

- `test_host_creator_rooms.py`: AC-9, the creator of a room and its stored row.
- `test_host_members.py`: AC-10, the account of a member.
- `test_host_creator_role.py`: AC-11 (over the sockets), AC-12, AC-13 and AC-14 (the
  rules).
- `test_host_creator_erasure.py`: AC-15 and AC-16, over the sockets, with the
  deletion of an account and with accounts switched off.
- `test_host_creator_pages.py`: what the pages of AC-10 and AC-11 show.
- `test_joining_account_seat.py`: AC-21.

Two kinds of tests:

- The rules (`join_room`, `tick`, `handle_message`) run with exact clock values on
  a room built by `room_with_creator`. A signed-in join is a `join_room` with
  `account_id`.
- The sockets run on `host_app`: the real app with a fake clock, a catalogue, the
  rooms' store and, when accounts are on, the accounts' store and a recording
  mailer, both on one database file. A device is a socket opened with the session
  cookie of an account (`open_member`), or with none. `sign_in_as` returns the
  session and leaves the test client without a cookie, so that only the sockets
  and requests that are given a session are signed in.

Nicknames are stored in capitals (`lobby/joining.md` rule 1), so `Lea` is `LEA` in
the room.
"""

from __future__ import annotations

import contextlib
import sqlite3
from collections.abc import Generator, Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from nock.accounts import AccountStore
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    HostChanged,
    Join,
    PlayerJoined,
    PlayerState,
    PlayerView,
    Pong,
    ServerMessage,
    Snapshot,
)
from nock.room import (
    RoomConfig,
    RoomState,
    disconnect_player,
    join_room,
    new_room,
    tick,
)
from nock.server import create_app
from nock.store import RoomStore
from spec014_harness import (
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    QUIET_RULES,
    Peer,
    keep_seen,
    socket_url,
    token_of,
)
from spec017_harness import FakeClock
from spec033_harness import (
    DATABASE_FILE_NAME,
    RecordingMailer,
    account_settings,
    ask_link,
    last_token,
    set_cookie_of,
    sign_in,
    state_of,
    wait_for,
    with_session,
)

LEA_EMAIL = "lea.probe@example.org"
ZOE_EMAIL = "zoe.probe@example.org"
BOB_EMAIL = "bob.probe@example.org"
LEA_ACCOUNT = "account-of-lea-0001"  # the account id of a rules-level creator
GRID_NUMBER = 1  # the number of the grid of `make_catalogue`
NAMES = ["Lea", "Bob", "Cy", "Di", "Ed", "Flo", "Gus", "Hal", "Ivy"]
REPLACED_CLOSE_CODE = 4001  # `lobby/joining.md` rule 6
HAND_OVER_SECONDS = 60.0  # `host_handover_seconds`
RESUME_WINDOW_SECONDS = 300.0

# The sockets' rooms: a tick every 50 ms of real time, and nobody timed out by
# silence or idleness, so that only the fake clock's moves change a room.
SOCKET_CONFIG = RoomConfig(
    tick_seconds=0.05, idle_after_seconds=1e9, silence_timeout_seconds=1e9
)

# The rules' times: the host is away from AWAY_AT, and a tick just after the
# hand-over delay gives the role away.
AWAY_AT = NOW + 10
HAND_OVER_AT = AWAY_AT + HAND_OVER_SECONDS + 0.5
TIMED_OUT_AT = AWAY_AT + RESUME_WINDOW_SECONDS + 1


# ---- Helpers for the rules ---------------------------------------------------------


def room_with_creator(grid: Grid, count: int = 3) -> RoomState:
    """Return a creator room where `p1` to `p<count>` joined at NOW.

    `p1` is Lea, the creator's player (signed in as `LEA_ACCOUNT`), joined first and
    so host. The others are anonymous: Bob (`p2`), Cy (`p3`)... Their tokens are
    `token_of(n)`.
    """
    state = new_room("ABCDEF", grid, NOW, creator_account_id=LEA_ACCOUNT)
    for number in range(1, count + 1):
        join = Join(nickname=NAMES[number - 1], resume_token=None)
        account = LEA_ACCOUNT if number == 1 else None
        outcome = join_room(
            state, join, NOW, f"p{number}", token_of(number), account_id=account
        )
        state = outcome.state
    assert state.seq == count
    return state


def room_without_lea(grid: Grid, count: int) -> RoomState:
    """Return a creator room where `p2` to `p<count + 1>` joined at NOW; Lea did not.

    `p2` is Bob, the host. Nobody is signed in. At most 8 players.
    """
    state = new_room("ABCDEF", grid, NOW, creator_account_id=LEA_ACCOUNT)
    for number in range(2, count + 2):
        join = Join(nickname=NAMES[number - 1], resume_token=None)
        outcome = join_room(state, join, NOW, f"p{number}", token_of(number))
        state = outcome.state
    assert len(state.players) == count
    return state


def lea_joins(
    state: RoomState, now: float, resume_token: str | None = None
) -> tuple[RoomState, list[object], Snapshot]:
    """Lea's signed-in join of the room (a new player, a resume or a seat back).

    Returns:
        The room after the join, the events it logged in order, and Lea's snapshot.
    """
    join = Join(nickname="Lea", resume_token=resume_token)
    outcome = join_room(
        state, join, now, NEW_PLAYER_ID, NEW_TOKEN, account_id=LEA_ACCOUNT
    )
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    return outcome.state, events, snapshot


def away(state: RoomState, player_id: str, at: float) -> RoomState:
    """Return the room after the player's connection closed at `at`."""
    return disconnect_player(state, player_id, at).state


def ticked(state: RoomState, now: float) -> tuple[RoomState, list[object]]:
    """Run a tick at `now` on a room whose connected players were all just seen.

    Returns:
        The room after the tick and the events it logged, in order.
    """
    outcome = tick(keep_seen(state, now), now, QUIET_RULES)
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    return outcome.state, events


def stand_in_room(grid: Grid) -> RoomState:
    """Lea is away and Bob (`p2`), a stand-in host, holds the role after a tick."""
    state = away(room_with_creator(grid), "p1", AWAY_AT)
    state, events = ticked(state, HAND_OVER_AT)
    assert host_changes(events) == ["p2"]
    return state


def host_flags(players: Sequence[PlayerView]) -> dict[str, bool]:
    """Whether each player of a snapshot is host, by player id."""
    flags: dict[str, bool] = {}
    for player in players:
        flags[player.player_id] = player.is_host
    return flags


def view_in(players: Sequence[PlayerView], player_id: str) -> PlayerView:
    """The view of one player in a snapshot's roster; fails when there is none."""
    for player in players:
        if player.player_id == player_id:
            return player
    pytest.fail(f"no player {player_id} in the roster")


def host_ids(state: RoomState) -> list[str]:
    """The ids of the players who are host: none or one."""
    ids: list[str] = []
    for player in state.players:
        if player.is_host:
            ids.append(player.player_id)
    return ids


def event_types(events: Sequence[object]) -> list[str]:
    """The `type` of each event, in order."""
    types: list[str] = []
    for event in events:
        type_name = getattr(event, "type", None)
        assert isinstance(type_name, str), event
        types.append(type_name)
    return types


def host_changes(events: Sequence[object]) -> list[str]:
    """The new host of each `host_changed` among the events, in order."""
    new_hosts: list[str] = []
    for event in events:
        if isinstance(event, HostChanged):
            new_hosts.append(event.player_id)
    return new_hosts


# ---- The app over the sockets ------------------------------------------------------


class HostApp(NamedTuple):
    """The app of the socket tests, its stores, its mailer and its fake clock.

    `accounts` and `mailer` are None while accounts are off.
    """

    client: TestClient
    registry: RoomRegistry
    store: RoomStore
    accounts: AccountStore | None
    mailer: RecordingMailer
    clock: FakeClock
    database_path: Path


@contextlib.contextmanager
def host_app(
    directory: Path,
    clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
    *,
    accounts_on: bool = True,
    config: RoomConfig = SOCKET_CONFIG,
) -> Generator[HostApp]:
    """Run the app on `directory`'s database file in a `TestClient` and yield it.

    Opened again on the same directory, it is the same server after a restart, with
    accounts on or off. Accounts off: the account variables of the environment are
    removed first, so that the app starts without them.

    Args:
        directory: The test's directory; the database file is `nock.sqlite3` in it.
        clock: The fake clock of the rooms, and so of the account routes.
        catalogue: The catalogue `POST /api/rooms` reads.
        monkeypatch: To unset the account variables when accounts are off.
        accounts_on: Whether the app has account settings and an account store.
        config: The thresholds of the rooms.
    """
    database_path = directory / DATABASE_FILE_NAME
    mailer = RecordingMailer()
    store = RoomStore(database_path)
    registry = RoomRegistry(clock=clock, store=store, config=config)
    account_store = AccountStore(database_path) if accounts_on else None
    try:
        if account_store is None:
            monkeypatch.delenv("NOCK_PUBLIC_URL", raising=False)
            monkeypatch.delenv("NOCK_SMTP_HOST", raising=False)
            app = create_app(rooms=registry, dist_dir=directory, catalogue=catalogue)
        else:
            app = create_app(
                rooms=registry,
                dist_dir=directory,
                catalogue=catalogue,
                accounts=account_settings(),
                account_store=account_store,
                mailer=mailer,
            )
        with TestClient(app) as client:
            yield HostApp(
                client, registry, store, account_store, mailer, clock, database_path
            )
    finally:
        if account_store is not None:
            account_store.close()
        registry.close()
        store.close()


def sign_in_as(app: HostApp, email: str) -> str:
    """Sign `email` in over HTTP and return the session; the client keeps no cookie."""
    asked = ask_link(app.client, email)
    assert asked.status_code == 202, asked.text
    signed_in = sign_in(app.client, last_token(app.mailer))
    assert signed_in.status_code == 200, signed_in.text
    session = set_cookie_of(signed_in).value
    app.client.cookies.clear()
    return session


def account_id_of(app: HostApp, session: str) -> str:
    """The id of the account that a session belongs to."""
    assert app.accounts is not None
    account = app.accounts.account_of_session(session, app.clock())
    assert account is not None, "the session belongs to no account"
    return account.account_id


def create_room_as(app: HostApp, session: str | None) -> str:
    """`POST /api/rooms` for the catalogue's grid, with the session if any; the code."""
    headers = {} if session is None else with_session(session)
    response = app.client.post(
        "/api/rooms", json={"grid_number": GRID_NUMBER}, headers=headers
    )
    assert response.status_code == 201, response.text
    code = response.json()["code"]
    assert isinstance(code, str)
    return code


class CreatorRoom(NamedTuple):
    """A room that Lea created while signed in."""

    session: str
    account_id: str
    code: str


def lea_creates_a_room(app: HostApp) -> CreatorRoom:
    """Lea signs in and creates a room: her session, her account and the code."""
    session = sign_in_as(app, LEA_EMAIL)
    account_id = account_id_of(app, session)
    code = create_room_as(app, session)
    return CreatorRoom(session, account_id, code)


def open_member(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
    session: str | None = None,
) -> Peer:
    """Open a socket carrying `session`, join, and return once the snapshot came."""
    headers = {} if session is None else with_session(session)
    websocket = stack.enter_context(
        client.websocket_connect(socket_url(code), headers=headers)
    )
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_until(
        lambda: any(isinstance(m, Snapshot) for m in peer.messages()),
        f"the snapshot of {nickname}",
    )
    return peer


def open_refused_member(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
    session: str | None = None,
) -> Peer:
    """Open a socket carrying `session`, join, and return once the server closed it."""
    headers = {} if session is None else with_session(session)
    websocket = stack.enter_context(
        client.websocket_connect(socket_url(code), headers=headers)
    )
    peer = Peer(websocket)
    peer.send(Join(nickname=nickname, resume_token=resume_token))
    peer.wait_until(lambda: peer.close_code is not None, f"the close of {nickname}")
    return peer


def wait_for_state(
    registry: RoomRegistry, code: str, player_id: str, wanted: PlayerState
) -> None:
    """Wait until the room shows the player in the state `wanted`."""

    def reached() -> bool:
        for player in state_of(registry, code).players:
            if player.player_id == player_id:
                return player.state == wanted
        return False

    wait_for(reached, f"{player_id} to be {wanted}")


def wait_for_host(registry: RoomRegistry, code: str, player_id: str) -> None:
    """Wait until the room's one host is `player_id`."""
    wait_for(
        lambda: host_ids(state_of(registry, code)) == [player_id],
        f"{player_id} to be the host",
    )


def wait_for_departure(registry: RoomRegistry, code: str, player_id: str) -> None:
    """Wait until the player is no player of the room (timed out)."""

    def gone() -> bool:
        for player in state_of(registry, code).players:
            if player.player_id == player_id:
                return False
        return True

    wait_for(gone, f"{player_id} to leave the room")


def wait_for_message(peer: Peer, kind: type) -> None:
    """Wait until the peer received a message of this class after its snapshot."""
    peer.wait_until(
        lambda: any(isinstance(m, kind) for m in peer.events()),
        f"a {kind.__name__}",
    )


def events_without_pongs(peer: Peer) -> list[ServerMessage]:
    """What the peer received after its snapshot, leaving the pongs out."""
    kept: list[ServerMessage] = []
    for message in peer.events():
        if not isinstance(message, Pong):
            kept.append(message)
    return kept


def received_text(peer: Peer) -> str:
    """Everything the peer received, as the JSON texts joined in one string."""
    texts: list[str] = []
    for message in peer.messages():
        texts.append(message.model_dump_json())
    return "\n".join(texts)


def error_codes_of(peer: Peer) -> list[ErrorCode]:
    """The code of each error the peer received, in order."""
    codes: list[ErrorCode] = []
    for message in peer.messages():
        code = getattr(message, "code", None)
        if isinstance(code, ErrorCode):
            codes.append(code)
    return codes


def joined_ids(peer: Peer) -> list[str]:
    """The id of each player the `player_joined` events of the peer announced."""
    ids: list[str] = []
    for message in peer.events():
        if isinstance(message, PlayerJoined):
            ids.append(message.player.player_id)
    return ids


# ---- The database file -------------------------------------------------------------


def stored_creator(database_path: Path, code: str) -> str | None:
    """The `creator_account_id` that `room_times` holds for the room."""
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            "SELECT creator_account_id FROM room_times WHERE code = ?", (code,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, f"no room_times row for {code}"
    return row[0]


def schema_version(database_path: Path) -> int:
    """`PRAGMA user_version` of the database file."""
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute("PRAGMA user_version").fetchone()
    finally:
        connection.close()
    return int(row[0])
