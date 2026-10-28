"""Tests of lobby/host, AC-10 and AC-11 in the browser: what the pages show.

On the live server of spec 033's harness (accounts on, the recording mailer, the
built client). Each device is a browser context with its own cookies and storage.

AC-11: Lea creates a room signed in, Bob enters first and holds the host controls
(« Réglages de l'hôte » in the Menu); once Lea enters, Bob's Menu has lost the
entry and hers has it.

AC-10: a device signed in as Lea, with no identity stored for a room where her
member is not linked to her account (her `PUT /api/account/rooms` links none), shows
the nickname form.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from host_harness import GRID_NUMBER, LEA_EMAIL
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Join
from nock.room import join_room, new_room
from room_panels import open_menu
from spec011_harness import EnterRoom
from spec014_harness import load_fr, token_of
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ROOMS_PATH,
    WAIT_TIMEOUT_MS,
    AccountServer,
    Devices,
    account_live_server,
    ask_link_in_form,
    expect_account_state,
    link_in,
    room_page,
    sign_in_with_link,
    wait_for_messages,
)

ROOMS_URL = "/api/rooms"


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


def signed_in_page(server: AccountServer, devices: Devices) -> Page:
    """A new device signs in as Lea from `/account`; return its page."""
    page = devices.new().new_page()
    page.goto(f"{server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    sent_before = len(server.mailer.messages)
    ask_link_in_form(page, LEA_EMAIL)
    wait_for_messages(server.mailer, sent_before + 1)
    sign_in_with_link(page, link_in(server.base_url, server.mailer.messages[-1]))
    return page


def test_ac11_the_creators_arrival_moves_the_host_controls_to_her_menu(
    account_server: AccountServer, devices: Devices, enter_room: EnterRoom
) -> None:
    lea_page = signed_in_page(account_server, devices)
    created = lea_page.context.request.post(
        f"{account_server.base_url}{ROOMS_URL}", data={"grid_number": GRID_NUMBER}
    )
    assert created.status == 201
    url = f"{account_server.base_url}/r/{created.json()['code']}"
    bob_page = devices.new().new_page()
    host_entry = "host-settings-open"

    enter_room(bob_page, url, "Bob")
    expect(bob_page.get_by_test_id(host_entry)).to_have_count(1)
    enter_room(lea_page, url, "Lea")

    expect(bob_page.get_by_test_id(host_entry)).to_have_count(0)
    expect(lea_page.get_by_test_id(host_entry)).to_have_count(1)
    open_menu(lea_page)
    expect(lea_page.get_by_test_id(host_entry)).to_contain_text(
        load_fr()["settings.heading"]
    )
    open_menu(bob_page)
    expect(bob_page.get_by_text(load_fr()["settings.heading"])).to_have_count(0)


def test_ac10_a_signed_in_device_without_an_identity_shows_the_nickname_form(
    account_server: AccountServer, devices: Devices, fx01_grid: Grid
) -> None:
    code = "ABCDEF"
    token = token_of(1)
    joined = join_room(
        new_room(code, fx01_grid, time.time(), GRID_NUMBER),
        Join(nickname="Lea", resume_token=None),
        time.time(),
        "p1",
        token,
    )
    account_server.registry.add_room(joined.state)
    lea_page = signed_in_page(account_server, devices)

    put = lea_page.context.request.put(
        f"{account_server.base_url}{ROOMS_PATH}",
        data={"code": code, "resume_token": token},
    )
    lea_page.goto(f"{account_server.base_url}/r/{code}")

    assert put.status == 204
    expect(room_page(lea_page)).to_have_attribute(
        "data-status", "nickname", timeout=WAIT_TIMEOUT_MS
    )
    expect(lea_page.get_by_test_id("nickname-input")).to_be_visible()
