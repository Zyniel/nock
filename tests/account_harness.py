"""Shared setup of the tests of account/account, AC-19 to AC-21: the grid progress.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_account_*.py`:

- `test_account_progress.py`: AC-19 to AC-21, `GET /api/account/progress` over
  HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one
  file, a fake clock).

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

from typing import NamedTuple

from fastapi.testclient import TestClient
from httpx2 import Response

from nock.grid import Grid
from nock.room import RoomState
from spec029_harness import (
    SOLVE_SECONDS,
    Play,
    Player,
    account_id_of,
    link_room,
    play_fx01,
    sign_in_from,
)
from spec032_harness import ANA, BOB, CY, LIFE, T0, TA, TB, TC
from spec033_harness import (
    ANA_EMAIL,
    AccountApp,
    link_and_sign_in,
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
