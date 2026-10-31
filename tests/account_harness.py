"""Shared setup of the tests of account/account, AC-19 to AC-21 and AC-24 to AC-30.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_account_*.py`:

- `test_account_progress.py`: AC-19 to AC-21, `GET /api/account/progress` over
  HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one
  file, a fake clock).
- `test_account_erasure.py`, `test_account_erasure_history.py`,
  `test_account_erasure_record.py`, `test_account_erasure_retry.py` and
  `test_account_erasure_overlap.py`: AC-24 to AC-27, AC-29 and AC-30, the erasure
  that always finishes, on the same app. Zoé's play (`zoe_in_rooms`,
  `zoe_in_new_live_room`), the room store that holds a room's engine
  (`HoldingStore`) and the reading of the erasure's two tables are here.
- `test_account_returning_device.py`: AC-28, a browser.

Ana's rooms are FX-01 rooms played with the rules (spec 029's `play_fx01`) and
registered with `add_room`, so that the grid number of each one is chosen. A room
registered at the clock's time starts its life then (`lobby/lifetime.md`): a
solved room, as an unsolved one, expires once the clock is more than `LIFE` past
it. A creator room is a room whose `creator_account_id` is Ana's account, which
Ana never joined: its only player is Bob.

Nicknames are stored in capitals (`lobby/joining.md` rule 1), which no test here
reads.
"""

from __future__ import annotations

import contextlib
import sqlite3
import threading
import time
from pathlib import Path
from typing import NamedTuple

from fastapi.testclient import TestClient
from httpx2 import Response

from nock.grid import Grid
from nock.room import RoomState
from nock.store import RoomStore
from spec017_harness import open_peer
from spec029_harness import (
    SOLVE_SECONDS,
    Play,
    Player,
    account_id_of,
    link_room,
    play_fx01,
    sign_in_from,
)
from spec032_harness import ANA, BOB, CY, LIFE, NO_TICK_CONFIG, T0, TA, TB, TC
from spec033_harness import (
    ANA_EMAIL,
    AccountApp,
    link_and_sign_in,
    room_key,
    set_cookie_of,
    with_session,
)

PROGRESS_PATH = "/api/account/progress"
NO_STORE = "no-store"

ANA_PLAYER = Player("Ana", ANA, TA)
BOB_PLAYER = Player("Bob", BOB, TB)
CY_PLAYER = Player("Cy", CY, TC)

R_CODE = "RRRRRR"  # AC-19: grid 1, solved
S_CODE = "SSSSSS"  # grid 2, not solved
S2_CODE = "TTTTTT"  # grid 3, not solved
Q_CODE = "QQQQQQ"  # grid 3, solved, then swept: Ana keeps its record
U_CODE = "UUUUUU"  # grid 4, created by Ana, never joined
K_CODE = "KKKKKK"  # a control room of grid 5, not solved, that stays open
X_CODE = "XXXXXX"  # a room with no grid number
CONTROL_GRID = 5

# AC-19's answer.
ANA_PROGRESS = {"1": "finished", "2": "started", "3": "finished", "4": "started"}


class Ana(NamedTuple):
    """Ana, signed in: her session and her account id."""

    session: str
    account_id: str


def ana_play(
    grid: Grid,
    code: str,
    grid_number: int | None,
    *,
    solved: bool,
    start: float,
    others: list[Player] | None = None,
) -> Play:
    """A FX-01 room that Ana and Bob play, solved or not, on `grid_number`."""
    players = [ANA_PLAYER, BOB_PLAYER] if others is None else others
    solved_after = SOLVE_SECONDS if solved else None
    return play_fx01(
        grid,
        code,
        players,
        start=start,
        solved_after=solved_after,
        grid_number=grid_number,
    )


def sign_in_ana_from(app: AccountApp, play: Play) -> Ana:
    """Register the room, sign Ana in from it (her first identity) and return her."""
    app.registry.add_room(play.state)
    session = sign_in_from(app, ANA_EMAIL, play.state.code, TA)
    return Ana(session, account_id_of(app, session))


def sign_in_ana_without_room(app: AccountApp) -> Ana:
    """Sign Ana in from no room: an account with no identity."""
    signed_in = link_and_sign_in(app, ANA_EMAIL, None)
    session = set_cookie_of(signed_in).value
    app.client.cookies.clear()
    return Ana(session, account_id_of(app, session))


def add_and_link(app: AccountApp, ana: Ana, play: Play) -> None:
    """Register the room and link Ana's member of it to her account."""
    app.registry.add_room(play.state)
    link_room(app.client, ana.session, play.state.code, TA)


def add_control_room(app: AccountApp, ana: Ana, grid: Grid) -> None:
    """Add the open room K (grid 5, not solved) at the clock's time and link Ana."""
    play = ana_play(grid, K_CODE, CONTROL_GRID, solved=False, start=app.clock())
    add_and_link(app, ana, play)


def creator_room(
    app: AccountApp,
    ana: Ana,
    grid: Grid,
    code: str,
    grid_number: int,
    *,
    solved: bool,
    joined: bool = False,
) -> RoomState:
    """Register a room that Ana created: only Bob plays in it, unless `joined`.

    With `joined`, Ana is a member too, but her account is not linked to her member
    yet: the caller links it (`link_room`) when the test needs it.
    """
    players = [ANA_PLAYER, BOB_PLAYER] if joined else [BOB_PLAYER]
    play = ana_play(
        grid,
        code,
        grid_number,
        solved=solved,
        start=app.clock(),
        others=players,
    )
    state = play.state.model_copy(update={"creator_account_id": ana.account_id})
    app.registry.add_room(state)
    return state


def build_ana_progress_rooms(app: AccountApp, grid: Grid) -> Ana:
    """AC-19's accounts and rooms: Ana, member of R, S and S2 and creator of U.

    Ana signs in from Q (grid 3, solved), which expires and is swept before she
    asks anything: her record of Q stays. Then R (grid 1, solved), S (grid 2) and
    S2 (grid 3) are registered and linked, and U (grid 4) is created for her.
    """
    swept = ana_play(grid, Q_CODE, 3, solved=True, start=T0)
    ana = sign_in_ana_from(app, swept)
    app.clock.advance(LIFE + 1)
    assert app.registry.expire_rooms() == [Q_CODE]
    now = app.clock()
    add_and_link(app, ana, ana_play(grid, R_CODE, 1, solved=True, start=now))
    add_and_link(app, ana, ana_play(grid, S_CODE, 2, solved=False, start=now))
    add_and_link(app, ana, ana_play(grid, S2_CODE, 3, solved=False, start=now))
    creator_room(app, ana, grid, U_CODE, 4, solved=False)
    return ana


def ask_progress(client: TestClient, session: str) -> Response:
    """`GET /api/account/progress` with the session `session` and no other cookie."""
    client.cookies.clear()
    return client.get(PROGRESS_PATH, headers=with_session(session))


def progress_body(client: TestClient, session: str) -> object:
    """The JSON body that `GET /api/account/progress` answers with a 200."""
    response = ask_progress(client, session)
    assert response.status_code == 200, response.text
    return response.json()


# ---- AC-24 to AC-29: Zoé deletes her account -------------------------------------

ZOE_EMAIL = "zoe.probe@example.org"
BOB_EMAIL = "bob.probe@example.org"
ZOE_NICKNAME = "Zoé"
ZOE_STORED = "ZOÉ"  # as the server stores her nickname (spec 012 decision 12)
ZOE = "p-zoe"
TZ = "token-of-zoe-0001"
# A sweep every 0.1 s of real time, on which no tick changes anything.
FAST_SWEEP_CONFIG = NO_TICK_CONFIG.model_copy(update={"expiry_sweep_seconds": 0.1})

DELETED_SUBJECT = "Votre compte Nock a été supprimé"
# Rule 27's text, as `email.deleted.body` holds it.
DELETED_BODY = (
    "Bonjour,\n\nVotre compte Nock et les données qui lui étaient liées ont été"
    " supprimés. Les salons que vous aviez créés sont fermés ; dans les autres,"
    " vous apparaissez comme « Ancien joueur ».\n\nSi vous n'aviez rien demandé,"
    " une personne connectée à ce compte l'a supprimé."
)


class ZoeRooms(NamedTuple):
    """Zoé, signed in, and her three rooms: R and S as a player, U as the creator."""

    session: str
    account_id: str
    r_code: str
    s_code: str
    zoe_in_r: str
    zoe_in_s: str


def zoe_in_rooms(
    app: AccountApp, stack: contextlib.ExitStack, grid: Grid, *, s_live: bool
) -> ZoeRooms:
    """Zoé plays R and S, signs in and creates U; no request carries her cookie.

    R is live: she enters it by a socket kept open in `stack`, writes nothing, then
    asks a link from it and signs in. S is another room of hers, linked to her
    account with `PUT /api/account/rooms`: live by a second socket in `stack` when
    `s_live`, else a room only in the store, with Bob. U is a room she created, only
    in the store, where Bob plays (`creator_room`). The session is returned apart,
    and the client's cookies are cleared: the tests name it with `with_session`.
    """
    zoe_in_r = zoe_in_new_live_room(app, stack, grid)
    signed_in = link_and_sign_in(
        app, ZOE_EMAIL, room_key(zoe_in_r.code, zoe_in_r.resume_token)
    )
    session = set_cookie_of(signed_in).value
    account_id = account_id_of(app, session)
    if s_live:
        zoe_in_s = zoe_in_new_live_room(app, stack, grid)
        s_code = zoe_in_s.code
        s_player = zoe_in_s.player_id
        s_token = zoe_in_s.resume_token
    else:
        s_code = "SSSSSS"
        stored = play_fx01(
            grid,
            s_code,
            [Player(ZOE_NICKNAME, ZOE, TZ), BOB_PLAYER],
            start=app.clock(),
            solved_after=None,
        )
        app.registry.add_room(stored.state)
        s_player = ZOE
        s_token = TZ
    link_room(app.client, session, s_code, s_token)
    creator_room(app, Ana(session, account_id), grid, U_CODE, 4, solved=False)
    app.client.cookies.clear()
    return ZoeRooms(
        session, account_id, zoe_in_r.code, s_code, zoe_in_r.player_id, s_player
    )


class LiveMember(NamedTuple):
    """Zoé's member of a live room: the room's code, her player id and her token."""

    code: str
    player_id: str
    resume_token: str


def zoe_in_new_live_room(
    app: AccountApp, stack: contextlib.ExitStack, grid: Grid
) -> LiveMember:
    """Register a room on `grid` (grid 1) and make it live with Zoé in it.

    She enters it by a socket kept open in `stack` and writes nothing. Her account,
    if any, is not linked to the member: the caller signs in from the room
    (`sign_in_from`) or links it (`link_room`).
    """
    code = app.registry.register_room(grid, grid_number=1)
    zoe = open_peer(stack, app.client, code, ZOE_NICKNAME)
    snapshot = zoe.snapshot()
    return LiveMember(code, snapshot.you, snapshot.resume_token)


class HoldingStore(RoomStore):
    """A `RoomStore` whose `erase_player` of one room holds the room's engine.

    `hold` arms it for one room code. While it is armed, each call of
    `erase_player` for that code sleeps for the hold's seconds, then sets
    `hold_over` and either raises `RuntimeError` (`fail`) or erases the player as
    the store does. For a live room the call runs in the step of the room's task,
    so the engine's loop is blocked for as long. With `once`, the first such call
    disarms it; `release` disarms it at any time, a hold under way ending as
    planned. Every other call is the store's own.
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.hold_over = threading.Event()
        self._held_code = ""
        self._hold_seconds = 0.0
        self._is_failing = False
        self._is_once = False

    def hold(self, code: str, seconds: float, *, fail: bool, once: bool) -> None:
        """Arm the hold for room `code`; `hold_over` is cleared."""
        self.hold_over.clear()
        self._hold_seconds = seconds
        self._is_failing = fail
        self._is_once = once
        self._held_code = code

    def release(self) -> None:
        """Disarm the hold: later calls are the store's own."""
        self._held_code = ""

    def erase_player(self, code: str, player_id: str) -> bool:
        """Hold (then fail, with `fail`) for the held room; else erase the player."""
        if self._held_code == "" or code != self._held_code:
            return super().erase_player(code, player_id)
        seconds = self._hold_seconds
        is_failing = self._is_failing
        if self._is_once:
            self.release()
        time.sleep(seconds)
        self.hold_over.set()
        if is_failing:
            raise RuntimeError("the engine was held in this step")
        return super().erase_player(code, player_id)


def nicknames_of(state: RoomState, player_id: str) -> list[str]:
    """The nickname of each record of the player in `players` and `past_players`."""
    found = [p.nickname for p in state.players if p.player_id == player_id]
    found += [p.nickname for p in state.past_players if p.player_id == player_id]
    return found


class ErasureRow(NamedTuple):
    """One row of `account_erasures`, as the file holds it."""

    account_id: str | None
    email: str | None
    requested_at: float
    done_at: float | None
    notified_at: float | None
    attempts: int
    players: int
    rooms_deleted: int


def erasure_rows(database_path: Path) -> list[ErasureRow]:
    """The rows of `account_erasures`, oldest request first, read on a connection."""
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT account_id, email, requested_at, done_at, notified_at, attempts,"
            " players, rooms_deleted FROM account_erasures ORDER BY erasure_id"
        ).fetchall()
    found: list[ErasureRow] = []
    for row in rows:
        found.append(ErasureRow(*row))
    return found


def listed_players(database_path: Path) -> list[tuple[str, str]]:
    """The (code, player id) of each row of `account_erasure_players`, in order."""
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT code, player_id FROM account_erasure_players"
            " ORDER BY code, player_id"
        ).fetchall()
    found: list[tuple[str, str]] = []
    for code, player_id in rows:
        found.append((code, player_id))
    return found
