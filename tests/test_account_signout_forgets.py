"""Tests of account/account, AC-31 to AC-33: a sign-out forgets the account's seats.

A browser, on the live server of spec 033's "Test harness" (accounts on, a
recording mailer, the real client). Ana's account lists the rooms R and T; her
device holds its own seat in T, `nock.room.R` and history records of R and T. She
signs in from `/account` (which stores R), her account links S from another device
and `/` loads (which stores S): the device holds the identities of R and S, T's
unchanged, and `nock.account_rooms` names R and S.

- AC-31: « Se déconnecter », answered 204 by the server, shows `signed_out`; the
  device then holds no identity, room record or history record of R or S and no
  `nock.account_rooms`; T's identity, room record and history record stay, and
  « Mes salons » on `/` lists T alone.
- AC-32: « Supprimer définitivement », answered 204, shows `deleted` and leaves the
  device the same way.
- AC-33: a sign-out answered 500 or a deletion answered 500 shows
  `account.error.generic` and every `localStorage` item stays as it was.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Join
from nock.room import join_room, new_room
from spec024_harness import make_catalogue
from spec029_harness import device_record, history_value, read_key, stored_history
from spec032_harness import expect_my_rooms_ready, grid_from_text, my_room_items
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    LINK_PATH,
    ROOMS_PATH,
    SIGN_IN_PATH,
    WAIT_TIMEOUT_MS,
    AccountServer,
    Devices,
    account_live_server,
    account_page,
    ask_link_in_form,
    expect_account_state,
    fulfill_json,
    link_in,
    load_fr,
    room_key,
    sign_in_with_link,
    wait_for_messages,
)
from spec033_harness import token_of as link_token_of

R_CODE = "RRRRRR"  # the account brings it, at the sign-in
S_CODE = "SSSSSS"  # the account brings it, at the catalogue load
T_CODE = "TTTTTT"  # the device's own seat, which the account lists as well
ACCOUNT_ROOMS_KEY = "nock.account_rooms"
HISTORY_KEY = "nock.history"
FINISHED_AT = "2026-10-14T08:30:00Z"
ELAPSED_MS = 754_000
SIGN_OUT_ROUTE = "**/api/account/sign-out"
ACCOUNT_ROUTE = "**/api/account"

Identity = dict[str, str]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = make_catalogue(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.fixture
def devices(browser: Browser) -> Iterator[Devices]:
    opened = Devices(browser)
    yield opened
    opened.close()


class Seats(NamedTuple):
    """Ana's device, signed in, with the seats of R, S and T on it."""

    page: Page
    base_url: str
    identities: dict[str, Identity]  # by room code, as the server holds them
    t_identity_text: str  # `nock.identity.<T>` as seeded
    t_room_text: str  # `nock.room.<T>` as seeded
    t_history: dict[str, object]  # T's record of `nock.history` as seeded


# ---- The server: three rooms of Ana ----------------------------------------------


def add_room_with_ana(server: AccountServer, grid: Grid, code: str) -> Identity:
    """Register room `code` where Ana is the only player; return her identity."""
    letter = code[0].lower()
    player_id = f"p-ana-{letter}"
    token = f"token-of-ana-in-{letter}-01"
    now = time.time()
    joined = join_room(
        new_room(code, grid, now, 1),
        Join(nickname="Ana", resume_token=None),
        now,
        player_id,
        token,
    )
    server.registry.add_room(joined.state)
    return {"player_id": player_id, "resume_token": token, "nickname": "ANA"}


def link_to_account(
    context: BrowserContext, server: AccountServer, code: str, identity: Identity
) -> None:
    """`PUT /api/account/rooms` from a device that is signed in."""
    key = room_key(code, identity["resume_token"])
    response = context.request.put(f"{server.base_url}{ROOMS_PATH}", data=key)
    assert response.status == 204


def sign_in_by_http(
    context: BrowserContext, server: AccountServer, identity_of_r: Identity
) -> None:
    """Another device signs in as Ana from R's key, with requests only."""
    key = room_key(R_CODE, identity_of_r["resume_token"])
    link = context.request.post(
        f"{server.base_url}{LINK_PATH}", data={"email": ANA_EMAIL, "room": key}
    )
    assert link.status == 202
    wait_for_messages(server.mailer, 1)
    token = link_token_of(server.mailer.messages[0])
    signed_in = context.request.post(
        f"{server.base_url}{SIGN_IN_PATH}", data={"token": token}
    )
    assert signed_in.status == 200


# ---- The device's storage ---------------------------------------------------------


def store_items(page: Page, items: dict[str, str]) -> None:
    """Write `items` in the page's `localStorage`, once (no init script)."""
    page.evaluate(
        "items => { for (const [key, value] of Object.entries(items))"
        " { localStorage.setItem(key, value); } }",
        items,
    )


def local_storage_of(page: Page) -> dict[str, str]:
    """Every item of the page's `localStorage`."""
    stored = page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")
    assert isinstance(stored, dict), stored
    items: dict[str, str] = {}
    for key, value in stored.items():
        assert isinstance(key, str), key
        assert isinstance(value, str), value
        items[key] = value
    return items


def stored_json(page: Page, key: str) -> object:
    """The item `key` parsed, or None when it is absent."""
    raw = read_key(page, key)
    if raw is None:
        return None
    return json.loads(raw)


def history_by_code(page: Page) -> dict[str, object]:
    """The records of `nock.history`, by room code; empty when it is absent."""
    stored = stored_history(page)
    if stored is None:
        return {}
    assert isinstance(stored, list), stored
    records: dict[str, object] = {}
    for record in stored:
        assert isinstance(record, dict), record
        code = record["code"]
        assert isinstance(code, str), record
        records[code] = record
    return records


def account_rooms_of(page: Page) -> list[str]:
    """The codes of `nock.account_rooms`, sorted; empty when it is absent."""
    stored = stored_json(page, ACCOUNT_ROOMS_KEY)
    if stored is None:
        return []
    assert isinstance(stored, list), stored
    codes: list[str] = []
    for code in stored:
        assert isinstance(code, str), stored
        codes.append(code)
    return sorted(codes)


# ---- Ana's device before the sign-out ---------------------------------------------


def device_with_seats(server: AccountServer, devices: Devices, grid: Grid) -> Seats:
    """AC-31's device, signed in, holding the seats of R and S and its own of T.

    Another device signs in from R and links T; this device holds its own seat in
    T, `nock.room.R`, `nock.room.T` and history records of R and T, signs in from
    `/account`, then `/` loads after the other device linked S.
    """
    identities = {
        code: add_room_with_ana(server, grid, code) for code in (R_CODE, S_CODE, T_CODE)
    }
    other = devices.new()
    sign_in_by_http(other, server, identities[R_CODE])
    link_to_account(other, server, T_CODE, identities[T_CODE])

    page = devices.new().new_page()
    page.goto(f"{server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    t_identity_text = json.dumps(identities[T_CODE])
    t_room_text = json.dumps({"grid": 1, "selection": None})
    t_history = device_record(T_CODE, 1, FINISHED_AT, ELAPSED_MS, ["Bob"])
    r_history = device_record(R_CODE, 1, FINISHED_AT, ELAPSED_MS, [])
    store_items(
        page,
        {
            f"nock.identity.{T_CODE}": t_identity_text,
            f"nock.room.{R_CODE}": t_room_text,
            f"nock.room.{T_CODE}": t_room_text,
            HISTORY_KEY: history_value([r_history, t_history]),
        },
    )
    ask_link_in_form(page, ANA_EMAIL)
    wait_for_messages(server.mailer, 2)
    sign_in_with_link(page, link_in(server.base_url, server.mailer.messages[-1]))
    assert_seat_stored(page, R_CODE, identities[R_CODE])
    assert account_rooms_of(page) == [R_CODE]

    link_to_account(other, server, S_CODE, identities[S_CODE])
    page.goto(f"{server.base_url}/")
    expect_my_rooms_ready(page, 3)
    seats = Seats(
        page, server.base_url, identities, t_identity_text, t_room_text, t_history
    )
    assert_device_holds_all(seats)
    return seats


def assert_seat_stored(page: Page, code: str, identity: Identity) -> None:
    """The device holds `identity` under `nock.identity.<code>`."""
    assert stored_json(page, f"nock.identity.{code}") == identity


def assert_device_holds_all(seats: Seats) -> None:
    """The premise of the three criteria: R, S and T are all on the device."""
    page = seats.page
    for code in (R_CODE, S_CODE):
        assert_seat_stored(page, code, seats.identities[code])
    assert read_key(page, f"nock.identity.{T_CODE}") == seats.t_identity_text
    assert account_rooms_of(page) == [R_CODE, S_CODE]
    assert sorted(history_by_code(page)) == [R_CODE, T_CODE]
    assert read_key(page, f"nock.room.{R_CODE}") is not None


def open_account_page(seats: Seats) -> None:
    """Open `/account` on the signed-in device and wait for `signed_in`."""
    seats.page.goto(f"{seats.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(seats.page, "signed_in")


# ---- What the device holds afterwards ---------------------------------------------


def assert_device_forgot_the_account_seats(seats: Seats) -> None:
    """R and S are gone from the device; T's identity, record and history stay."""
    page = seats.page
    items = local_storage_of(page)
    for code in (R_CODE, S_CODE):
        assert f"nock.identity.{code}" not in items
        assert f"nock.room.{code}" not in items
    assert ACCOUNT_ROOMS_KEY not in items
    assert items[f"nock.identity.{T_CODE}"] == seats.t_identity_text
    assert items[f"nock.room.{T_CODE}"] == seats.t_room_text
    assert history_by_code(page) == {T_CODE: seats.t_history}


# ---- AC-31 to AC-33 ---------------------------------------------------------------


def test_ac31_a_sign_out_forgets_r_and_s_and_keeps_t(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid
) -> None:
    seats = device_with_seats(account_server, devices, fx01_grid)
    open_account_page(seats)

    seats.page.get_by_test_id("account-sign-out").click()

    expect_account_state(seats.page, "signed_out")
    assert_device_forgot_the_account_seats(seats)


def test_ac31_mes_salons_lists_t_alone_after_the_sign_out(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid
) -> None:
    seats = device_with_seats(account_server, devices, fx01_grid)
    open_account_page(seats)
    seats.page.get_by_test_id("account-sign-out").click()
    expect_account_state(seats.page, "signed_out")

    seats.page.goto(f"{seats.base_url}/")

    expect_my_rooms_ready(seats.page, 1)
    expect(my_room_items(seats.page).first).to_have_attribute("data-code", T_CODE)


def test_ac32_a_deletion_leaves_the_device_as_a_sign_out_does(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid
) -> None:
    seats = device_with_seats(account_server, devices, fx01_grid)
    open_account_page(seats)

    seats.page.get_by_test_id("account-delete").click()
    seats.page.get_by_test_id("account-delete-confirm").click()

    expect_account_state(seats.page, "deleted")
    assert_device_forgot_the_account_seats(seats)


def fail_with_500(route: Route) -> None:
    """Answer a sign-out, or a `DELETE /api/account`, with a 500."""
    if route.request.method in ("POST", "DELETE"):
        fulfill_json(route, 500, {"detail": "Internal Error"})
    else:
        route.fallback()


@pytest.mark.parametrize("action", ["sign-out", "deletion"])
def test_ac33_a_failed_sign_out_or_deletion_removes_nothing(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid, action: str
) -> None:
    seats = device_with_seats(account_server, devices, fx01_grid)
    open_account_page(seats)
    page = seats.page
    before = local_storage_of(page)
    if action == "sign-out":
        page.route(SIGN_OUT_ROUTE, fail_with_500)
    else:
        page.route(ACCOUNT_ROUTE, fail_with_500)

    if action == "sign-out":
        page.get_by_test_id("account-sign-out").click()
    else:
        page.get_by_test_id("account-delete").click()
        page.get_by_test_id("account-delete-confirm").click()

    expect_account_state(page, "error")
    expect(account_page(page).get_by_test_id("account-state-line")).to_have_text(
        load_fr()["account.error.generic"], timeout=WAIT_TIMEOUT_MS
    )
    assert local_storage_of(page) == before
