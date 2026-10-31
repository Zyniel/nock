"""Tests of account/account, AC-28: the device of an erased player returns.

A browser, on the live server of spec 033's "Test harness" (accounts on, a recording
mailer, the real client). Zoé enters room R from her device and writes `T` at (1, 0);
she asks a link from the room's account dialog and opens it in a second page of the
same device, where she deletes her account. Her device still holds her identity in R
(`nock.identity.<code>` in its `localStorage`). Her room page then reloads: it enters
with no form, as the same player (same id, same colour, her `T` at (1, 0)), her own
roster row names her « Ancien joueur », a letter she types is applied, and
`GET /api/account` from that page reads signed out.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, Page, expect

from account_harness import ZOE_EMAIL, ZOE_NICKNAME
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec011_harness import EnterRoom
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_PLAYER_TEXT,
    SIGNED_OUT,
    WAIT_TIMEOUT_MS,
    AccountServer,
    Devices,
    account_live_server,
    ask_link_in_form,
    cell_at,
    expect_account_state,
    link_in,
    open_account_dialog,
    room_page,
    roster_item,
    sign_in_with_link,
    type_letter,
    wait_for_messages,
    you_of,
)


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


class Erased(NamedTuple):
    """Zoé's room page, after her deletion, and what it showed before."""

    page: Page
    base_url: str
    zoe_id: str
    colour: str


def zoe_deletes_her_account(
    server: AccountServer, devices: Devices, grid: Grid, enter_room: EnterRoom
) -> Erased:
    """Zoé enters R, writes `T`, signs in on a second page and deletes her account."""
    code = server.registry.register_room(grid, grid_number=1)
    context = devices.new()
    page = context.new_page()
    enter_room(page, f"{server.base_url}/r/{code}", ZOE_NICKNAME)
    zoe_id = you_of(page)
    colour = roster_item(page, zoe_id).get_attribute("data-colour")
    assert colour is not None
    type_letter(page, 1, 0, "t")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    open_account_dialog(page)
    ask_link_in_form(page, ZOE_EMAIL)
    wait_for_messages(server.mailer, 1)
    page.keyboard.press("Escape")
    account = context.new_page()
    sign_in_with_link(account, link_in(server.base_url, server.mailer.messages[0]))
    account.get_by_test_id("account-delete").click()
    account.get_by_test_id("account-delete-confirm").click()
    expect_account_state(account, "deleted")
    return Erased(page, server.base_url, zoe_id, colour)


def test_ac28_her_device_reloads_the_room_as_the_player_named_ancien_joueur(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    erased = zoe_deletes_her_account(account_server, devices, fx01_grid, enter_room)
    page = erased.page

    page.reload()

    expect(room_page(page)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )
    expect(page.get_by_test_id("nickname-input")).to_have_count(0)
    assert you_of(page) == erased.zoe_id
    row = roster_item(page, erased.zoe_id)
    expect(row.get_by_test_id("roster-nickname")).to_have_text(FORMER_PLAYER_TEXT)
    expect(row).to_have_attribute("data-colour", erased.colour)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")


def test_ac28_a_letter_she_types_is_applied_and_the_page_reads_signed_out(
    account_server: AccountServer,
    devices: Devices,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    erased = zoe_deletes_her_account(account_server, devices, fx01_grid, enter_room)
    page = erased.page
    page.reload()
    expect(room_page(page)).to_have_attribute(
        "data-status", "joined", timeout=WAIT_TIMEOUT_MS
    )

    type_letter(page, 1, 1, "a")

    expect(cell_at(page, 1, 1)).to_have_attribute(
        "data-letter", "A", timeout=WAIT_TIMEOUT_MS
    )
    status = page.request.get(f"{erased.base_url}{ACCOUNT_PATH}")
    assert status.json() == SIGNED_OUT
