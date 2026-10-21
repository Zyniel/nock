"""Tests of spec 029, AC-6: deleting an account removes its history and makes its
player a former player in the others' history.

HTTP, on the app of spec 033's "Test harness" with a fake clock: room R is a FX-01
room played with the rules, solved with Ana, Zélie (`Zélie-Probe`, stored as
`ZÉLIE-PROBE`, spec 012) and Bob, who joined in that order. Ana and Zélie sign in
from R (spec 033), so both accounts hold R, and both ask their history once. When
Zélie deletes her account, Ana's `GET /api/account/history` lists R with
`"teammates": ["--", "BOB"]` in R's `team_nicknames` order, Zélie's records are
gone, and the database files no longer hold `ZÉLIE-PROBE`.

Expired room: the same R and accounts, but R has expired (the fake clock moved past
spec 032's life) and has not been swept, and Ana has not asked her history; after
Zélie's deletion Ana's history lists R with `["--", "BOB"]` and the files do not
hold `ZÉLIE-PROBE` (they held it before). `AccountStore.erase_players_from_history`
is also checked on its own: the records of another account whose team-mate matches
an identity (room code and player id) read `--`, a team-mate with another player id
or another code is kept, and the files no longer hold the nickname.

Browser with mocked routes: on Ana's catalogue page, signed in, the account's
record with `["--", "BOB"]` reads `Avec Ancien joueur, Bob`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, expect

from nock.accounts import AccountStore, RoomIdentity
from nock.grid import Grid
from nock.room import RoomState
from spec017_harness import FakeClock
from spec029_harness import (
    XYZ,
    XYZ_FINISHED_AT,
    NewPage,
    Play,
    Player,
    SignedInRoutes,
    account_id_of,
    account_record,
    ask_history,
    elapsed_ms_of,
    expect_history_count,
    history_body,
    history_item,
    open_catalogue,
    paris_pages,
    play_fx01,
    sign_in_from,
    solved_at_of,
)
from spec032_harness import ANA, BOB, CY, LIFE, T0, TA, TB, TC, grid_from_text, utc
from spec033_harness import (
    ACCOUNT_PATH,
    ANA_EMAIL,
    ZELIE_EMAIL,
    AccountApp,
    account_app,
    database_bytes,
    strings_in,
    with_session,
)

R_CODE = "RRRRRR"
ZELIE_STORED = "ZÉLIE-PROBE"  # as the server stores `Zélie-Probe` (spec 012)
PLAYERS = [
    Player("Ana", ANA, TA),
    Player("Zélie-Probe", BOB, TB),
    Player("Bob", CY, TC),
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_pages(browser)


class Erased(NamedTuple):
    """The app once Zélie deleted her account, and what the play left."""

    app: AccountApp
    room: Play
    ana_session: str
    zelie_session: str
    zelie_id: str
    ana_before: list[dict[str, object]]
    bytes_before: list[str]
    deletion_status: int


@contextlib.contextmanager
def zelie_deletes_her_account(
    tmp_path: Path, clock: FakeClock, grid: Grid, *, expired: bool = False
) -> Iterator[Erased]:
    """AC-6's play, up to Zélie's `DELETE /api/account`.

    With `expired`, nobody asks a history, and the clock moves past a room's life
    just before the deletion, so that R has expired and no sweep has run.
    """
    room = play_fx01(grid, R_CODE, PLAYERS, start=T0)
    with account_app(tmp_path, clock) as app:
        app.registry.add_room(room.state)
        ana_session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        zelie_session = sign_in_from(app, ZELIE_EMAIL, R_CODE, TB)
        zelie_id = account_id_of(app, zelie_session)
        ana_before: list[dict[str, object]] = []
        if not expired:
            ana_before = history_body(app.client, ana_session)
            history_body(app.client, zelie_session)
        bytes_before = strings_in(database_bytes(app.database_path), [ZELIE_STORED])
        if expired:
            clock.advance(LIFE + 1)
        app.client.cookies.clear()
        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(zelie_session))
        app.client.cookies.clear()
        yield Erased(
            app,
            room,
            ana_session,
            zelie_session,
            zelie_id,
            ana_before,
            bytes_before,
            deletion.status_code,
        )


def anas_record(room: Play, teammates: list[str]) -> dict[str, object]:
    return {
        "code": R_CODE,
        "grid_number": 1,
        "width": 5,
        "height": 5,
        "finished_at": utc(solved_at_of(room)),
        "elapsed_ms": elapsed_ms_of(room),
        "teammates": teammates,
    }


def test_ac6_before_the_deletion_anas_record_names_zelie(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(tmp_path, fake_clock, fx01_grid) as erased:
        before = erased.ana_before

    assert before == [anas_record(erased.room, [ZELIE_STORED, "BOB"])]


def test_ac6_anas_history_names_zelie_a_former_player_in_team_order(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion_status == 204

        records = history_body(erased.app.client, erased.ana_session)

    assert records == [anas_record(erased.room, ["--", "BOB"])]


def test_ac6_zelies_records_are_gone(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion_status == 204

        records = erased.app.accounts.history(erased.zelie_id)
        response = ask_history(erased.app.client, erased.zelie_session)

    assert records == []
    assert response.status_code == 401


def test_ac6_the_database_files_no_longer_hold_zelies_stored_nickname(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(tmp_path, fake_clock, fx01_grid) as erased:
        assert erased.deletion_status == 204

        found = strings_in(database_bytes(erased.app.database_path), [ZELIE_STORED])

    assert erased.bytes_before == [ZELIE_STORED]
    assert found == []


# ---- R expired and not swept, nobody asked a history -------------------------------


def test_ac6_an_expired_room_still_gives_anas_history_zelie_as_a_former_player(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(
        tmp_path, fake_clock, fx01_grid, expired=True
    ) as erased:
        assert erased.deletion_status == 204

        records = history_body(erased.app.client, erased.ana_session)

    assert records == [anas_record(erased.room, ["--", "BOB"])]


def test_ac6_an_expired_room_leaves_no_trace_of_zelies_nickname_in_the_files(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with zelie_deletes_her_account(
        tmp_path, fake_clock, fx01_grid, expired=True
    ) as erased:
        assert erased.deletion_status == 204

        found = strings_in(database_bytes(erased.app.database_path), [ZELIE_STORED])

    assert erased.bytes_before == [ZELIE_STORED]
    assert found == []


# ---- AccountStore.erase_players_from_history --------------------------------------

OTHER_CODE = "SSSSSS"
UNKNOWN_PLAYER_ID = "p9"
BOTH_ROOMS_BEFORE = {
    R_CODE: [ZELIE_STORED, "BOB"],
    OTHER_CODE: [ZELIE_STORED, "BOB"],
}


class TwoRecords(NamedTuple):
    """An account store whose one account holds the records of two rooms."""

    accounts: AccountStore
    path: Path
    account_id: str


def identity_of(code: str, player_id: str, token: str, nickname: str) -> RoomIdentity:
    return RoomIdentity(
        code=code, player_id=player_id, resume_token=token, nickname=nickname
    )


def solved_state(grid: Grid, code: str) -> RoomState:
    """A solved FX-01 room: Ana, Zélie (`Zélie-Probe`) and Bob."""
    return play_fx01(grid, code, PLAYERS, start=T0).state


@contextlib.contextmanager
def account_with_two_records(tmp_path: Path, grid: Grid) -> Iterator[TwoRecords]:
    """Ana's account on its own store file, with the records of R and S.

    Ana is `ANA` in both rooms; Zélie (`BOB`'s player id) and Bob are her
    team-mates. No room store holds the nickname: only the records do.
    """
    path = tmp_path / "accounts.sqlite3"
    accounts = AccountStore(path)
    try:
        started = accounts.sign_in(ANA_EMAIL, T0)
        for code in (R_CODE, OTHER_CODE):
            ana = identity_of(code, ANA, TA, "ANA")
            assert accounts.link_identity(started.account_id, ana, T0)
            accounts.save_history(started.account_id, solved_state(grid, code))
        yield TwoRecords(accounts, path, started.account_id)
    finally:
        accounts.close()


def teammates_by_code(accounts: AccountStore, account_id: str) -> dict[str, list[str]]:
    """The team-mates of each record of the account, by room code."""
    found: dict[str, list[str]] = {}
    for record in accounts.history(account_id):
        found[record.code] = list(record.teammates)
    return found


def test_ac6_erase_players_from_history_makes_the_matching_teammate_a_former_player(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with account_with_two_records(tmp_path, fx01_grid) as held:
        zelie = identity_of(R_CODE, BOB, TB, ZELIE_STORED)
        before = teammates_by_code(held.accounts, held.account_id)

        held.accounts.erase_players_from_history([zelie])
        after = teammates_by_code(held.accounts, held.account_id)

    assert before == BOTH_ROOMS_BEFORE
    assert after[R_CODE] == ["--", "BOB"]


def test_ac6_erase_players_from_history_keeps_a_teammate_of_another_room_code(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with account_with_two_records(tmp_path, fx01_grid) as held:
        zelie = identity_of(R_CODE, BOB, TB, ZELIE_STORED)

        held.accounts.erase_players_from_history([zelie])
        after = teammates_by_code(held.accounts, held.account_id)

    assert after[OTHER_CODE] == [ZELIE_STORED, "BOB"]


def test_ac6_erase_players_from_history_keeps_a_teammate_with_another_player_id(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with account_with_two_records(tmp_path, fx01_grid) as held:
        stranger = identity_of(R_CODE, UNKNOWN_PLAYER_ID, TB, ZELIE_STORED)

        held.accounts.erase_players_from_history([stranger])
        after = teammates_by_code(held.accounts, held.account_id)

    assert after == BOTH_ROOMS_BEFORE


def test_ac6_erase_players_from_history_erases_every_identity_given(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with account_with_two_records(tmp_path, fx01_grid) as held:
        zelie_in_r = identity_of(R_CODE, BOB, TB, ZELIE_STORED)
        zelie_in_s = identity_of(OTHER_CODE, BOB, TB, ZELIE_STORED)

        held.accounts.erase_players_from_history([zelie_in_r, zelie_in_s])
        after = teammates_by_code(held.accounts, held.account_id)

    assert after == {R_CODE: ["--", "BOB"], OTHER_CODE: ["--", "BOB"]}


def test_ac6_erase_players_from_history_leaves_the_files_without_the_nickname(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with account_with_two_records(tmp_path, fx01_grid) as held:
        zelie_in_r = identity_of(R_CODE, BOB, TB, ZELIE_STORED)
        zelie_in_s = identity_of(OTHER_CODE, BOB, TB, ZELIE_STORED)
        before = strings_in(database_bytes(held.path), [ZELIE_STORED])

        held.accounts.erase_players_from_history([zelie_in_r, zelie_in_s])
        after = strings_in(database_bytes(held.path), [ZELIE_STORED])

    assert before == [ZELIE_STORED]
    assert after == []


# ---- Ana's page -------------------------------------------------------------------


def test_ac6_anas_page_shows_the_former_player_as_ancien_joueur(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    record = account_record(XYZ, 2, XYZ_FINISHED_AT, 754_000, ["--", "BOB"])
    SignedInRoutes([record]).install(page)

    open_catalogue(page, live_server, None)

    expect_history_count(page, 1)
    teammates = history_item(page, XYZ).get_by_test_id("history-teammates")
    expect(teammates).to_have_text("Avec Ancien joueur, Bob")
