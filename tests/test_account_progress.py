"""Tests of account/account, AC-19 to AC-21: `GET /api/account/progress`.

Over HTTP, on the app of spec 033's "Test harness" with a fake clock (accounts on,
both stores on one file); `account_harness` builds Ana's rooms. The route answers
the account's progress: grid numbers in decimal to `finished` (each history
record, each solved room of an identity) or `started` (each unsolved one, each
creator room that still exists), `finished` winning; derived at each request.

Choices where the spec leaves room:

- "An account with no room" is an account signed in from no room, so with no
  identity.
- "A room with no grid number gives nothing" is tried with a solved room, an
  unsolved room and the record of a swept solved room, each beside an open room of
  grid 5 so that the answer is not empty by accident.
- "Once S expires" is tried swept (`expire_rooms`), unswept (the request finds it
  expired) and swept with a new room of S's code (grid 2, Bob and Cy) registered.
- "`finished` wins" between rooms is tried with no record saved (the stored history
  is checked empty first): a solved creator room Ana joined, and a solved and an
  unsolved room of one grid, in both orders.
- "Saves no record" is read on `AccountStore.history`, which saves nothing, before
  `GET /api/account/history` is asked.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from account_harness import (
    ANA_PROGRESS,
    BOB_PLAYER,
    CONTROL_GRID,
    CY_PLAYER,
    NO_STORE,
    PROGRESS_PATH,
    Q_CODE,
    R_CODE,
    S_CODE,
    U_CODE,
    X_CODE,
    add_and_link,
    add_control_room,
    ana_play,
    ask_progress,
    build_ana_progress_rooms,
    creator_room,
    progress_body,
    sign_in_ana_from,
    sign_in_ana_without_room,
)
from host_harness import host_app
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import history_body, link_room, play_fx01
from spec032_harness import LIFE, T0, TA, grid_from_text
from spec033_harness import (
    NOT_AUTHORIZED,
    NOT_FOUND,
    SESSION_LIFE,
    account_app,
    with_session,
)

CONTROL_ONLY = {str(CONTROL_GRID): "started"}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-19: what the route answers ------------------------------------------------


def test_ac19_the_progress_marks_each_grid_finished_or_started(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = build_ana_progress_rooms(app, fx01_grid)

        response = ask_progress(app.client, ana.session)

    assert response.status_code == 200
    assert response.json() == ANA_PROGRESS
    assert response.headers.get("cache-control") == NO_STORE


def test_ac19_the_progress_saves_no_record_and_the_history_lists_the_finished_grids(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = build_ana_progress_rooms(app, fx01_grid)

        progress_body(app.client, ana.session)
        saved = app.accounts.history(ana.account_id)
        listed = history_body(app.client, ana.session)

    # Only the swept Q has a record: the progress saved R's no more than a history
    # not asked yet would have.
    assert [record.code for record in saved] == [Q_CODE]
    grid_numbers = [record["grid_number"] for record in listed]
    assert grid_numbers == [1, 3]


def test_ac19_an_account_with_no_room_gets_an_empty_object(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_without_room(app)

        body = progress_body(app.client, ana.session)

    assert body == {}


def test_ac19_a_solved_creator_room_the_account_never_joined_is_started(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_without_room(app)
        creator_room(app, ana, fx01_grid, U_CODE, 4, solved=True)

        body = progress_body(app.client, ana.session)

    assert body == {"4": "started"}


@pytest.mark.parametrize(
    "case", ["joined creator room", "solved then unsolved", "unsolved then solved"]
)
def test_ac19_finished_wins_over_started_with_no_record_saved_yet(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid, case: str
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_without_room(app)
        if case == "joined creator room":
            creator_room(app, ana, fx01_grid, U_CODE, 4, solved=True, joined=True)
            link_room(app.client, ana.session, U_CODE, TA)
        else:
            solved_room = ana_play(fx01_grid, R_CODE, 4, solved=True, start=app.clock())
            unsolved_room = ana_play(
                fx01_grid, S_CODE, 4, solved=False, start=app.clock()
            )
            rooms = [solved_room, unsolved_room]
            if case == "unsolved then solved":
                rooms.reverse()
            for room in rooms:
                add_and_link(app, ana, room)
        # No history was asked and no room swept: a record cannot give "finished".
        assert app.accounts.history(ana.account_id) == []

        body = progress_body(app.client, ana.session)

    assert body == {"4": "finished"}


# ---- AC-20: rooms that are gone, rooms with no grid number ----------------------


@pytest.mark.parametrize("how", ["swept", "unswept", "code reused"])
def test_ac20_an_expired_room_leaves_the_progress(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid, how: str
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_from(
            app, ana_play(fx01_grid, S_CODE, 2, solved=False, start=T0)
        )
        fake_clock.advance(LIFE / 2)
        add_control_room(app, ana, fx01_grid)
        before = progress_body(app.client, ana.session)
        fake_clock.advance(LIFE / 2 + 1)
        if how != "unswept":
            assert app.registry.expire_rooms() == [S_CODE]
        if how == "code reused":
            reused = play_fx01(
                fx01_grid,
                S_CODE,
                [BOB_PLAYER, CY_PLAYER],
                start=fake_clock.now,
                solved_after=None,
                grid_number=2,
            )
            app.registry.add_room(reused.state)

        after = progress_body(app.client, ana.session)

    assert before == {"2": "started", "5": "started"}
    assert after == CONTROL_ONLY


@pytest.mark.parametrize("kind", ["solved", "unsolved", "swept record"])
def test_ac20_a_room_with_no_grid_number_gives_nothing(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid, kind: str
) -> None:
    solved = kind != "unsolved"
    with account_app(tmp_path, fake_clock) as app:
        room = ana_play(fx01_grid, X_CODE, None, solved=solved, start=T0)
        ana = sign_in_ana_from(app, room)
        if kind == "swept record":
            fake_clock.advance(LIFE + 1)
            assert app.registry.expire_rooms() == [X_CODE]
            saved = app.accounts.history(ana.account_id)
            assert [record.grid_number for record in saved] == [None]
        add_control_room(app, ana, fx01_grid)

        body = progress_body(app.client, ana.session)

    assert body == CONTROL_ONLY


def test_ac20_a_solved_room_expired_and_unswept_is_still_finished(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_from(
            app, ana_play(fx01_grid, R_CODE, 1, solved=True, start=T0)
        )
        fake_clock.advance(LIFE + 1)

        body = progress_body(app.client, ana.session)

    assert body == {"1": "finished"}


# ---- AC-21: signed out, accounts off ---------------------------------------------


@pytest.mark.parametrize("cookie", ["none", "unknown", "expired"])
def test_ac21_without_a_valid_session_the_progress_answers_401(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid, cookie: str
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        ana = sign_in_ana_from(
            app, ana_play(fx01_grid, R_CODE, 1, solved=True, start=T0)
        )
        headers: dict[str, str] = {}
        if cookie == "unknown":
            headers = with_session("u" * len(ana.session))
        if cookie == "expired":
            fake_clock.advance(SESSION_LIFE + 1)
            headers = with_session(ana.session)
        app.client.cookies.clear()

        response = app.client.get(PROGRESS_PATH, headers=headers)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac21_with_accounts_off_the_progress_answers_404(
    tmp_path: Path, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    with host_app(
        tmp_path, fake_clock, Catalogue(), monkeypatch, accounts_on=False
    ) as app:
        app.client.cookies.clear()

        response = app.client.get(PROGRESS_PATH)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
