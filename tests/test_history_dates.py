"""Tests of `gameplay/history.md` AC-5: « Grilles terminées » lists real ISO
date-times only (rules 2 and 4).

Ana's catalogue page on the live server, 1280 by 720, no summaries to ask. The
device's `nock.history` holds seven records, one per code, finished
`2026-10-14T08:30:00Z`, `2028-02-29T09:30:00.5+01:00`, `2026-10-14 08:30:00Z`,
`2026-02-30T08:30:00Z`, `2026-10-14T24:00:00Z`, `2026-10-14T08:30:60Z` and
`2026-10-14T08:30:00+24:00`: the section lists the first two only, newest first.
Signed in (the account routes mocked), an answer of two records, one finished
`2026-02-30T08:30:00Z`, adds neither, while the device's valid record stays.

The browser under test is Chromium, whose `Date.parse` takes `2026-02-30` for
1 March: the page has to check the calendar itself.
"""

from __future__ import annotations

from playwright.sync_api import Page

from spec029_harness import (
    HISTORY_KEY,
    SignedInRoutes,
    account_record,
    device_record,
    expect_history_count,
    history_codes,
    history_item,
    history_value,
    open_catalogue,
    seed,
    wait_quietly,
)
from spec042_harness import wait_until

ELAPSED_MS = 754_000
LEAP_DAY_FINISH = "2028-02-29T09:30:00.5+01:00"
REAL_FINISH = "2026-10-14T08:30:00Z"
ACCOUNT_REAL_CODE = "ACCT01"
ACCOUNT_IMPOSSIBLE_CODE = "ACCT02"
# (code, finished_at), the spec's seven in its order.
DEVICE_FINISHES = [
    ("DEV001", REAL_FINISH),
    ("DEV002", LEAP_DAY_FINISH),
    ("DEV003", "2026-10-14 08:30:00Z"),
    ("DEV004", "2026-02-30T08:30:00Z"),
    ("DEV005", "2026-10-14T24:00:00Z"),
    ("DEV006", "2026-10-14T08:30:60Z"),
    ("DEV007", "2026-10-14T08:30:00+24:00"),
]


def device_records() -> list[object]:
    """The seven device records of AC-5, each with its own code."""
    records: list[object] = []
    for code, finished_at in DEVICE_FINISHES:
        records.append(device_record(code, 1, finished_at, ELAPSED_MS, []))
    return records


def test_ac5_the_device_lists_only_real_iso_date_times(
    page: Page, live_server: str
) -> None:
    seed(page, {HISTORY_KEY: history_value(device_records())})

    open_catalogue(page, live_server, None)

    expect_history_count(page, 2)
    assert history_codes(page) == ["DEV002", "DEV001"]
    first = history_item(page, "DEV002")
    second = history_item(page, "DEV001")
    assert first.get_attribute("data-finished-at") == LEAP_DAY_FINISH
    assert second.get_attribute("data-finished-at") == REAL_FINISH


def test_ac5_an_account_answer_holding_an_impossible_date_adds_none(
    page: Page, live_server: str
) -> None:
    answer: list[object] = [
        account_record(ACCOUNT_REAL_CODE, 2, REAL_FINISH, ELAPSED_MS, ["Bob"]),
        account_record(
            ACCOUNT_IMPOSSIBLE_CODE, 3, "2026-02-30T08:30:00Z", ELAPSED_MS, ["Cy"]
        ),
    ]
    routes = SignedInRoutes(answer)
    routes.install(page)
    device = device_record("DEV001", 1, REAL_FINISH, ELAPSED_MS, [])
    seed(page, {HISTORY_KEY: history_value([device])})

    open_catalogue(page, live_server, None)

    wait_until(page, lambda: routes.history_requests >= 1, "the account history")
    wait_quietly(page)
    expect_history_count(page, 1)
    assert history_codes(page) == ["DEV001"]
