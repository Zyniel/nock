"""Tests of spec 029, AC-3 over HTTP: with an account, my history follows me.

With the app of spec 033's "Test harness" on a fake clock (accounts on, both
stores on one file, the recording mailer). Each room is a FX-01 room played with
the rules and registered with `add_room`, so that its date and its time taken are
known: Ana (and the others) join at `t0`, the first player writes 17 letters at
`t0`, the last writes `T` at (4, 4) at `t0 + 754`.

Ana signs in from room R (spec 033), and R is solved with `Bob`:
`GET /api/account/history` answers one record, R's, with R's date in UTC, its
time taken and `["BOB"]`, Bob's nickname as the server stores it (spec 012
decision 12). A linked room that is not solved gives no record; without a session
the route answers 401, and with accounts off 404.

Code reused: Ana's account holds an identity in room C, which is not solved, and
has not asked its history; C expires and the sweep deletes it (spec 032); a solved
FX-01 room with the same code, whose members are Bob and Cy only, is registered
with `add_room`; the history answers `[]`, and `save_history` of that state saves
no record.

Edge cases checked as well: every identity of the account in a room counts, not
only the latest one; a record is saved once; the records are newest first, then
by code; the answer is not cached (spec 033).
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec029_harness import (
    HISTORY_PATH,
    SOLVE_MS,
    Player,
    account_id_of,
    ask_history,
    elapsed_ms_of,
    history_body,
    link_room,
    play_fx01,
    sign_in_from,
    solved_at_of,
)
from spec032_harness import (
    ANA,
    BOB,
    CY,
    LIFE,
    T0,
    TA,
    TB,
    TC,
    grid_from_text,
    make_dist_dir,
    utc,
)
from spec033_harness import ANA_EMAIL, NOT_AUTHORIZED, NOT_FOUND, account_app

R_CODE = "RRRRRR"
S_CODE = "SSSSSS"
C_CODE = "CCCCCC"
ANA_PLAYER = Player("Ana", ANA, TA)
BOB_PLAYER = Player("Bob", BOB, TB)
CY_PLAYER = Player("Cy", CY, TC)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def expected_record(
    code: str, finished_at: float, elapsed_ms: int, teammates: list[str]
) -> dict[str, object]:
    """A record of the history answer, `finished_at` as a datetime (FX-01, grid 1)."""
    return {
        "code": code,
        "grid_number": 1,
        "width": 5,
        "height": 5,
        "finished_at": utc(finished_at),
        "elapsed_ms": elapsed_ms,
        "teammates": teammates,
    }


@contextlib.contextmanager
def accounts_off_client(
    tmp_path: Path, clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> Iterator[TestClient]:
    """The app of spec 033's "Accounts off", with a built client."""
    monkeypatch.delenv("NOCK_PUBLIC_URL", raising=False)
    monkeypatch.delenv("NOCK_SMTP_HOST", raising=False)
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=clock, store=store)
    try:
        app = create_app(rooms=registry, dist_dir=make_dist_dir(tmp_path))
        with TestClient(app) as client:
            yield client
    finally:
        registry.close()
        store.close()


# ---- Ana signs in from R, solved with Bob -----------------------------------------


def test_ac3_the_history_answers_the_record_of_the_room_ana_signed_in_from(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)

        records = history_body(app.client, session)

    expected = expected_record(R_CODE, solved_at_of(room), elapsed_ms_of(room), ["BOB"])
    assert records == [expected]
    assert elapsed_ms_of(room) == SOLVE_MS


def test_ac3_a_linked_room_that_is_not_solved_gives_no_record(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    unsolved = play_fx01(
        fx01_grid, S_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0, solved_after=None
    )
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(solved.state)
        app.registry.add_room(unsolved.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        link_room(app.client, session, S_CODE, TA)

        records = history_body(app.client, session)

    codes = [record["code"] for record in records]
    assert codes == [R_CODE]


def test_ac3_without_a_session_the_history_answers_401(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        app.client.cookies.clear()

        response = app.client.get(HISTORY_PATH)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac3_with_accounts_off_the_history_answers_404(
    tmp_path: Path, fake_clock: FakeClock, monkeypatch: pytest.MonkeyPatch
) -> None:
    with accounts_off_client(tmp_path, fake_clock, monkeypatch) as client:
        response = client.get(HISTORY_PATH)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND


def test_ac3_the_history_answer_is_not_cached(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)

        response = ask_history(app.client, session)

    assert response.status_code == 200
    assert response.headers.get("cache-control") == "no-store"


# ---- Edge cases of the records ----------------------------------------------------


def test_ac3_every_identity_of_the_account_in_the_room_is_left_out_of_the_teammates(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    # Ana joined R twice (spec 012 names the second seat `ANA 2`) and linked both
    # seats; the latest identity alone would leave `ANA` among the team-mates.
    second_seat = Player("Ana", CY, TC)
    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER, second_seat], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        fake_clock.advance(1)
        link_room(app.client, session, R_CODE, TC)

        records = history_body(app.client, session)

    assert len(records) == 1
    assert records[0]["teammates"] == ["BOB"]


def test_ac3_the_records_are_newest_first_then_by_code(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    players = [ANA_PLAYER, BOB_PLAYER]
    early_a = play_fx01(fx01_grid, "AAAAAA", players, start=T0)
    late_b = play_fx01(fx01_grid, "BBBBBB", players, start=T0, solved_after=900.0)
    early_c = play_fx01(fx01_grid, "CCCCCC", players, start=T0)
    with account_app(tmp_path, fake_clock) as app:
        for play in (early_c, late_b, early_a):
            app.registry.add_room(play.state)
        session = sign_in_from(app, ANA_EMAIL, "CCCCCC", TA)
        link_room(app.client, session, "AAAAAA", TA)
        link_room(app.client, session, "BBBBBB", TA)

        records = history_body(app.client, session)

    codes = [record["code"] for record in records]
    assert codes == ["BBBBBB", "AAAAAA", "CCCCCC"]


# ---- save_history and history ----------------------------------------------------


def test_ac3_save_history_saves_the_record_of_a_solved_room(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    from nock.accounts import HistoryRecord

    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        account_id = account_id_of(app, session)

        app.accounts.save_history(account_id, room.state)
        records = app.accounts.history(account_id)

    expected = HistoryRecord(
        code=R_CODE,
        grid_number=1,
        width=5,
        height=5,
        finished_at=utc(solved_at_of(room)),
        elapsed_ms=elapsed_ms_of(room),
        teammates=("BOB",),
    )
    assert records == [expected]


def test_ac3_save_history_keeps_a_record_already_saved(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        account_id = account_id_of(app, session)
        app.accounts.save_history(account_id, room.state)
        first = app.accounts.history(account_id)
        changed = room.state.model_copy(update={"grid_number": 9})

        app.accounts.save_history(account_id, changed)
        records = app.accounts.history(account_id)

    assert len(records) == 1
    assert records == first
    assert records[0].grid_number == 1


def test_ac3_save_history_does_nothing_for_an_unsolved_room(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room = play_fx01(
        fx01_grid, S_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0, solved_after=None
    )
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room.state)
        session = sign_in_from(app, ANA_EMAIL, S_CODE, TA)
        account_id = account_id_of(app, session)

        app.accounts.save_history(account_id, room.state)
        records = app.accounts.history(account_id)

    assert records == []


# ---- Code reused ------------------------------------------------------------------


def test_ac3_a_reused_code_gives_no_record_through_the_history_route(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    old_room = play_fx01(fx01_grid, C_CODE, [ANA_PLAYER], start=T0, solved_after=None)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(old_room.state)
        session = sign_in_from(app, ANA_EMAIL, C_CODE, TA)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [C_CODE]
        new_room = play_fx01(
            fx01_grid, C_CODE, [BOB_PLAYER, CY_PLAYER], start=fake_clock.now
        )
        app.registry.add_room(new_room.state)

        response = ask_history(app.client, session)

    assert response.status_code == 200
    assert response.json() == []


def test_ac3_save_history_of_a_new_room_with_a_reused_code_saves_no_record(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    old_room = play_fx01(fx01_grid, C_CODE, [ANA_PLAYER], start=T0, solved_after=None)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(old_room.state)
        session = sign_in_from(app, ANA_EMAIL, C_CODE, TA)
        account_id = account_id_of(app, session)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [C_CODE]
        new_room = play_fx01(
            fx01_grid, C_CODE, [BOB_PLAYER, CY_PLAYER], start=fake_clock.now
        )
        app.registry.add_room(new_room.state)

        app.accounts.save_history(account_id, new_room.state)
        records = app.accounts.history(account_id)

    assert records == []
