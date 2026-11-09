"""Tests of account/my-account, AC-9: a sign-out forgets the account's marks.

A browser, on the live server of spec 033's "Test harness" (accounts on, a
recording mailer, the real client) serving `CAT`. Ana signs in from `/account`
with a real link. The device holds `nock.progress` `{"1": "finished"}` and
`nock.account_progress` `{"1": "started", "2": "finished"}`; `GET
/api/account/progress` is answered `{}` by `page.route`, so the pills of `/` come
from the two device keys alone.

- « Se déconnecter » or « Supprimer définitivement », answered 204 by the server,
  shows `signed_out` or `deleted`; the device then holds no `nock.account_progress`,
  `nock.progress` as it was, and `/` shows card 1 « Terminée » and card 2 no pill.
- The same two actions answered 500 show `error` and leave both keys as they were.

Choices where the spec leaves room:

- "`nock.progress` is unchanged": its stored text is the seeded one.
- The keys are written once, after the sign-in (not by an init script, which would
  write them again on the next navigation).
- The deletion's confirmation is the `account-delete-confirm` button of spec 033.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Route

from cards_harness import (
    ACCOUNT_PROGRESS_KEY,
    ACCOUNT_PROGRESS_ROUTE,
    PROGRESS_KEY,
    expect_progresses,
)
from catalogue_builders import reference_catalogue
from nock.grid import Grid
from spec033_harness import (
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    AccountServer,
    Devices,
    account_live_server,
    ask_link_in_form,
    expect_account_state,
    fulfill_json,
    link_in,
    sign_in_with_link,
    wait_for_messages,
)
from spec046_harness import open_catalogue

DEVICE_TEXT = json.dumps({"1": "finished"})
ACCOUNT_TEXT = json.dumps({"1": "started", "2": "finished"})
SIGN_OUT_ROUTE = "**/api/account/sign-out"
ACCOUNT_ROUTE = "**/api/account"
BOTH_FINISHED = {1: "finished", 2: "finished"}
CARD_1_ONLY = {1: "finished", 2: "none"}


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    with account_live_server(tmp_path, reference_catalogue(fx01_grid)) as server:
        yield server


@pytest.fixture
def devices(browser: Browser) -> Iterator[Devices]:
    opened = Devices(browser)
    yield opened
    opened.close()


def signed_in_ana(server: AccountServer, devices: Devices) -> Page:
    """Ana's device, signed in, holding the two progress keys of AC-9."""
    page = devices.new().new_page()
    page.goto(f"{server.base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_out")
    ask_link_in_form(page, ANA_EMAIL)
    wait_for_messages(server.mailer, 1)
    sign_in_with_link(page, link_in(server.base_url, server.mailer.messages[-1]))
    page.route(ACCOUNT_PROGRESS_ROUTE, answer_empty_progress)
    page.evaluate(
        "items => { for (const [key, value] of Object.entries(items))"
        " { localStorage.setItem(key, value); } }",
        {PROGRESS_KEY: DEVICE_TEXT, ACCOUNT_PROGRESS_KEY: ACCOUNT_TEXT},
    )
    open_catalogue(page, server.base_url)
    expect_progresses(page, BOTH_FINISHED)
    return page


def answer_empty_progress(route: Route) -> None:
    """Answer `GET /api/account/progress` with `{}`."""
    fulfill_json(route, 200, {})


def read_text(page: Page, key: str) -> str | None:
    """The text of the `localStorage` item `key`, None when it is absent."""
    value = page.evaluate("key => localStorage.getItem(key)", key)
    if value is None:
        return None
    assert isinstance(value, str), value
    return value


def leave_the_account(page: Page, base_url: str, action: str) -> None:
    """Press « Se déconnecter » (`sign-out`) or delete the account (`deletion`)."""
    page.goto(f"{base_url}{ACCOUNT_PAGE_PATH}")
    expect_account_state(page, "signed_in")
    if action == "sign-out":
        page.get_by_test_id("account-sign-out").click()
    else:
        page.get_by_test_id("account-delete").click()
        page.get_by_test_id("account-delete-confirm").click()


def fail_with_500(route: Route) -> None:
    """Answer a sign-out, or a `DELETE /api/account`, with a 500."""
    if route.request.method in ("POST", "DELETE"):
        fulfill_json(route, 500, {"detail": "Internal Error"})
    else:
        route.fallback()


@pytest.mark.parametrize(
    ("action", "state"), [("sign-out", "signed_out"), ("deletion", "deleted")]
)
def test_ac9_a_sign_out_or_deletion_removes_the_account_key_and_keeps_the_device_key(
    account_server: AccountServer, devices: Devices, action: str, state: str
) -> None:
    page = signed_in_ana(account_server, devices)

    leave_the_account(page, account_server.base_url, action)

    expect_account_state(page, state)
    assert read_text(page, ACCOUNT_PROGRESS_KEY) is None
    assert read_text(page, PROGRESS_KEY) == DEVICE_TEXT
    open_catalogue(page, account_server.base_url)
    expect_progresses(page, CARD_1_ONLY)


@pytest.mark.parametrize("action", ["sign-out", "deletion"])
def test_ac9_a_failed_sign_out_or_deletion_keeps_both_keys(
    account_server: AccountServer, devices: Devices, action: str
) -> None:
    page = signed_in_ana(account_server, devices)
    route = SIGN_OUT_ROUTE if action == "sign-out" else ACCOUNT_ROUTE
    page.route(route, fail_with_500)

    leave_the_account(page, account_server.base_url, action)

    expect_account_state(page, "error")
    assert read_text(page, ACCOUNT_PROGRESS_KEY) == ACCOUNT_TEXT
    assert read_text(page, PROGRESS_KEY) == DEVICE_TEXT
