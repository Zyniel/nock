"""Tests of spec 029, AC-3 in browsers: the account's history on the catalogue page.

Live server with accounts on (spec 033's "Test harness": the recording mailer, both
stores on one file, the built client, FX-01 as published entry 1): room R is a
FX-01 room solved by Ana and Bob, played with the rules and registered with
`add_room`, and Ana's account holds her identity of R (`AccountStore.sign_in` and
`link_identity` of spec 033, as her first device's sign-in from R leaves it). Her
second device, a new context with empty storage, signs in with her address from
`/account` (spec 033 AC-2) and opens `/`: `history` lists R with `Avec Bob`,
although that device never opened R.

Mocked routes, signed in (`GET /api/account` says so, `GET /api/account/rooms`
answers `[]`): the page asks `GET /api/account/history` and lists its records with
the device's, one item per room code, the account's record replacing the device's
of the same code, `finished_at` newest first, then code; the account's records are
not written to the device; and the section shows from the account's records alone.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from nock.accounts import RoomIdentity
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec010_harness import catalogue_from_grid
from spec029_harness import (
    HISTORY_KEY,
    OLD_CODE,
    OLD_FINISHED_AT,
    XYZ,
    XYZ_FINISHED_AT,
    NewPage,
    Player,
    SignedInRoutes,
    account_record,
    device_record,
    expect_history_count,
    history_codes,
    history_item,
    history_value,
    old_record,
    open_catalogue,
    paris_pages,
    play_fx01,
    seed,
    stored_history,
    wait_quietly,
)
from spec032_harness import ANA, BOB, TA, TB, grid_from_text
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    AccountServer,
    Devices,
    account_live_server,
    ask_link_in_form,
    expect_account_state,
    link_in,
    sign_in_with_link,
    wait_for_messages,
)

R_CODE = "RRRRRR"
ACCOUNT_ONLY_CODE = "AAA111"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = catalogue_from_grid(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.fixture
def devices(browser: Browser) -> Iterator[Devices]:
    opened = Devices(browser)
    yield opened
    opened.close()


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_pages(browser)


# ---- Live: a second device ----------------------------------------------------


def ana_holds_solved_r(server: AccountServer, grid: Grid) -> None:
    """R solved by Ana and Bob, and Ana's account holding her identity of R."""
    start = time.time() - 1_000.0
    players = [Player("Ana", ANA, TA), Player("Bob", BOB, TB)]
    room = play_fx01(grid, R_CODE, players, start=start)
    server.registry.add_room(room.state)
    now = time.time()
    account = server.accounts.sign_in(ANA_EMAIL, now)
    identity = RoomIdentity(code=R_CODE, player_id=ANA, resume_token=TA, nickname="ANA")
    assert server.accounts.link_identity(account.account_id, identity, now) is True


def test_ac3_a_second_device_lists_the_room_after_signing_in(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid
) -> None:
    ana_holds_solved_r(account_server, fx01_grid)
    page = devices.new().new_page()
    page.goto(f"{account_server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    ask_link_in_form(page, ANA_EMAIL)
    wait_for_messages(account_server.mailer, 1)
    sign_in_with_link(
        page, link_in(account_server.base_url, account_server.mailer.messages[-1])
    )

    open_catalogue(page, account_server.base_url, None)

    expect_history_count(page, 1)
    item = history_item(page, R_CODE)
    expect(item).to_have_attribute("data-grid", "1")
    expect(item.get_by_test_id("history-teammates")).to_have_text("Avec Bob")


# ---- Mocked: the account's records with the device's -------------------------


def account_records() -> list[object]:
    """The account's records: XYZ789 with Bob only, and AAA111 of 1 October."""
    return [
        account_record(XYZ, 2, XYZ_FINISHED_AT, 754_000, ["BOB"]),
        account_record(ACCOUNT_ONLY_CODE, 1, OLD_FINISHED_AT, 500_000, ["CY"]),
    ]


def device_records() -> list[object]:
    """The device's records: XYZ789 with Bob and Cy, and the older QQQQQQ."""
    xyz = device_record(XYZ, 2, XYZ_FINISHED_AT, 754_000, ["Bob", "Cy"])
    return [xyz, old_record()]


def test_ac3_signed_in_the_page_asks_the_accounts_history(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    routes = SignedInRoutes(account_records())
    routes.install(page)
    seed(page, {HISTORY_KEY: history_value(device_records())})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 3)
    assert routes.history_requests >= 1


def test_ac3_one_item_per_code_newest_first_then_by_code(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    SignedInRoutes(account_records()).install(page)
    seed(page, {HISTORY_KEY: history_value(device_records())})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 3)
    assert history_codes(page) == [XYZ, ACCOUNT_ONLY_CODE, OLD_CODE]


def test_ac3_the_accounts_record_replaces_the_devices_of_the_same_code(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    SignedInRoutes(account_records()).install(page)
    seed(page, {HISTORY_KEY: history_value(device_records())})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 3)
    teammates = history_item(page, XYZ).get_by_test_id("history-teammates")
    expect(teammates).to_have_text("Avec Bob")


def test_ac3_the_accounts_records_are_not_written_to_the_device(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    SignedInRoutes(account_records()).install(page)
    seeded = history_value(device_records())
    seed(page, {HISTORY_KEY: seeded})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 3)
    wait_quietly(page)
    assert stored_history(page) == device_records()


def test_ac3_the_accounts_records_alone_make_the_section(
    new_page: NewPage, live_server: str
) -> None:
    page = new_page(1280, 720)
    SignedInRoutes(account_records()).install(page)

    open_catalogue(page, live_server, None)

    expect_history_count(page, 2)
    assert history_codes(page) == [XYZ, ACCOUNT_ONLY_CODE]
