"""Tests of account/my-account, AC-1: a link opened on an `/account` already shown.

A browser, on the live server of spec 033's "Test harness" (accounts on, a
recording mailer, the real client). A link is asked over HTTP from a device with no
room, so that nothing but the token is needed. Another browser device opens
`/account`, which shows signed out, and sets the link's token as the fragment of
its URL, with no reload (the page stays the same document). The page then signs in
and the URL loses the fragment.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import make_catalogue
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    LINK_PATH,
    AccountServer,
    Devices,
    account_live_server,
    expect_account_state,
    token_of,
    wait_for_messages,
)

STATUS_PATH = "/api/account"
FRAGMENT_TOKEN_SCRIPT = "token => { location.hash = token; }"
LOAD_MARK_SCRIPT = "() => { window.__loadMark = 'same document'; }"
READ_MARK_SCRIPT = "() => window.__loadMark"


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


def asked_token(server: AccountServer, devices: Devices) -> str:
    """Ask a sign-in link for Ana with no room, and return its token."""
    asking = devices.new().request.post(
        f"{server.base_url}{LINK_PATH}", data={"email": ANA_EMAIL, "room": None}
    )
    assert asking.status == 202
    wait_for_messages(server.mailer, 1)
    return token_of(server.mailer.messages[0])


def test_ac1_a_token_set_as_the_fragment_of_a_signed_out_page_signs_in(
    account_server: AccountServer, devices: Devices
) -> None:
    token = asked_token(account_server, devices)
    page: Page = devices.new().new_page()
    page.goto(f"{account_server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    page.evaluate(LOAD_MARK_SCRIPT)

    page.evaluate(FRAGMENT_TOKEN_SCRIPT, token)
    expect_account_state(page, "signed_in")

    assert page.url == f"{account_server.base_url}{ACCOUNT_PAGE_PATH}"
    assert page.evaluate(READ_MARK_SCRIPT) == "same document"
    status = page.context.request.get(f"{account_server.base_url}{STATUS_PATH}")
    assert status.json() == {"signed_in": True, "email": ANA_EMAIL}
