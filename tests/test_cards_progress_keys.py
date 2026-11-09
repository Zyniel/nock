"""Tests of content/cards, AC-10: the pills read both keys of the device.

Browser with the live server serving `CAT` (accounts off). Signed out
(`GET /api/account` answers `signed_out`), the device holds `nock.progress`
`{"1": "started"}` and `nock.account_progress` `{"1": "finished", "2": "started",
"3": "done"}`.

Choices where the spec leaves room:

- « as `/g/1` and `/g/2` do »: `/g/1` shows card 1 « Terminée » and `/g/2` card 2
  « Commencée » (a grid page shows one card).
- The `not json` case runs on the same page as the first one: the key is
  overwritten once and the page reloaded, so that a page that fails the first
  case cannot pass this one by accident.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page

from cards_harness import (
    ACCOUNT_PROGRESS_KEY,
    PROGRESS_KEY,
    expect_progress,
    expect_progresses,
    open_grid,
)
from spec032_harness import seed_storage
from spec046_harness import SIGNED_OUT, accounts_on, open_catalogue

CATALOGUE_KIND = "reference"

DEVICE_PROGRESS = {"1": "started"}
ACCOUNT_MARKS = {"1": "finished", "2": "started", "3": "done"}


def seed_both_keys(page: Page) -> None:
    """Put AC-10's two keys in the page's storage before its scripts run."""
    seed_storage(
        page,
        {
            PROGRESS_KEY: json.dumps(DEVICE_PROGRESS),
            ACCOUNT_PROGRESS_KEY: json.dumps(ACCOUNT_MARKS),
        },
    )


def test_ac10_signed_out_the_catalogue_reads_both_keys_and_ignores_a_bad_value(
    page: Page, live_server: str
) -> None:
    seed_both_keys(page)
    accounts_on(page, SIGNED_OUT)

    open_catalogue(page, live_server)

    expect_progresses(page, {1: "finished", 2: "started", 3: "none"})


def test_ac10_signed_out_a_key_that_is_not_json_gives_no_progress(
    page: Page, live_server: str
) -> None:
    seed_both_keys(page)
    accounts_on(page, SIGNED_OUT)
    open_catalogue(page, live_server)
    expect_progresses(page, {1: "finished", 2: "started", 3: "none"})

    page.evaluate("key => localStorage.setItem(key, 'not json')", ACCOUNT_PROGRESS_KEY)
    open_catalogue(page, live_server)

    expect_progresses(page, {1: "started", 2: "none"})


@pytest.mark.parametrize(("number", "progress"), [(1, "finished"), (2, "started")])
def test_ac10_the_grid_page_reads_both_keys(
    page: Page, live_server: str, number: int, progress: str
) -> None:
    seed_both_keys(page)
    accounts_on(page, SIGNED_OUT)

    open_grid(page, live_server, number)

    expect_progress(page, number, progress)
