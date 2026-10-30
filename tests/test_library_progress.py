"""Tests of content/library, AC-22 to AC-24: the account's progress on `/` and
`/g/<n>`, merged with the device's.

Browser with the live server serving `CAT` (accounts off, so the account routes
are answered by `page.route`): `GET /api/account` answers signed in or signed out,
`GET /api/account/progress` the case under test, and `nock.progress` is seeded
before the page's scripts run.

Choices where the spec leaves room:

- "While the answer is pending": the progress route holds its request, the test
  waits for the request to be held, and the page is `ready` with the device's
  pills; releasing the answer then gives the merged ones.
- "`nock.progress` is unchanged": its parsed value is the seeded one, after the
  merged pills show.
- "Ready" on `/g/<n>` is the `data-state` `ready` of `grid-page`.
- AC-24 reads « `/g/1` show « Commencée » on card 1, « Terminée » on card 3 »: a
  grid page shows one card, so `/g/1` shows card 1 « Commencée » and `/g/3` card 3
  « Terminée ».
- A failed answer is waited for (the request ended) and the page given a pause
  before the pills are read, so that a page that wipes the device's progress on a
  failure is caught.
- "Signed out, `/` never asks the route": `GET /api/account` answers signed out,
  the « Compte » button shows (the status is handled), and the route is not asked
  within a pause. The route would answer AC-22's progress if it were.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from library_harness import (
    ACCOUNT_PROGRESS,
    ACCOUNT_PROGRESS_PATH,
    ACCOUNT_PROGRESS_ROUTE,
    DEVICE_ONLY,
    DEVICE_PROGRESS,
    FAILING_ANSWERS,
    MERGED,
    QUIET_MS,
    STATUS_PATH,
    RequestLog,
    answer_failing,
    expect_progress,
    expect_progresses,
    seed_device_progress,
    stored_progress,
    wait_for_progress_answers,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec004_harness import grid_from_text, make_reference_catalogue
from spec042_harness import wait_until
from spec046_harness import (
    SIGNED_IN,
    SIGNED_OUT,
    HeldRoute,
    accounts_on,
    answer_json,
    open_catalogue,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


def open_grid(page: Page, base_url: str, number: int) -> None:
    """Open `/g/<number>` and wait until `grid-page` is `ready`."""
    page.goto(f"{base_url}/g/{number}")
    expect(page.get_by_test_id("grid-page")).to_have_attribute("data-state", "ready")


# ---- AC-22: the catalogue merges the two sources ---------------------------------


def test_ac22_the_catalogue_shows_the_merged_progress_and_keeps_the_device_storage(
    page: Page, live_server: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_IN)
    answer_json(page, ACCOUNT_PROGRESS_ROUTE, 200, ACCOUNT_PROGRESS)
    log = RequestLog(page)

    open_catalogue(page, live_server)

    expect_progresses(page, MERGED)
    wait_for_progress_answers(page, log, 1)
    page.wait_for_timeout(QUIET_MS)
    assert stored_progress(page) == DEVICE_PROGRESS
    assert log.count(ACCOUNT_PROGRESS_PATH) == 1
    assert log.count(STATUS_PATH) == 1


def test_ac22_while_the_answer_is_pending_the_page_is_ready_with_the_devices_pills(
    page: Page, live_server: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_IN)
    held = HeldRoute(page, ACCOUNT_PROGRESS_ROUTE)

    open_catalogue(page, live_server)
    wait_until(page, lambda: len(held.routes) == 1, "the held progress request")

    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )
    expect_progresses(page, DEVICE_ONLY)
    held.release(200, ACCOUNT_PROGRESS)
    expect_progresses(page, MERGED)
    assert stored_progress(page) == DEVICE_PROGRESS


# ---- AC-23: the grid page --------------------------------------------------------


@pytest.mark.parametrize(
    ("number", "progress"), [(1, "finished"), (2, "started"), (3, "finished")]
)
def test_ac23_the_grid_page_asks_the_progress_and_not_the_status(
    page: Page, live_server: str, number: int, progress: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_IN)
    answer_json(page, ACCOUNT_PROGRESS_ROUTE, 200, ACCOUNT_PROGRESS)
    log = RequestLog(page)

    open_grid(page, live_server, number)

    expect_progress(page, number, progress)
    wait_for_progress_answers(page, log, 1)
    page.wait_for_timeout(QUIET_MS)
    assert sorted(log.paths) == sorted([f"/api/grids/{number}", ACCOUNT_PROGRESS_PATH])
    expect(page.get_by_test_id("account-open")).to_have_count(0)


# ---- AC-24: no progress from the account -----------------------------------------


@pytest.mark.parametrize("answer", FAILING_ANSWERS)
def test_ac24_the_catalogue_keeps_the_devices_progress_when_the_account_gives_none(
    page: Page, live_server: str, answer: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_IN)
    answer_failing(page, answer)
    log = RequestLog(page)

    open_catalogue(page, live_server)
    wait_for_progress_answers(page, log, 1)
    page.wait_for_timeout(QUIET_MS)

    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )
    expect_progresses(page, DEVICE_ONLY)


@pytest.mark.parametrize("answer", FAILING_ANSWERS)
def test_ac24_the_grid_pages_keep_the_devices_progress_when_the_account_gives_none(
    page: Page, live_server: str, answer: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_IN)
    answer_failing(page, answer)
    log = RequestLog(page)

    for answers, number in enumerate([1, 3], start=1):
        open_grid(page, live_server, number)
        wait_for_progress_answers(page, log, answers)
        page.wait_for_timeout(QUIET_MS)

        expect(page.get_by_test_id("grid-page")).to_have_attribute(
            "data-state", "ready"
        )
        expect_progress(page, number, DEVICE_ONLY[number])


def test_ac24_signed_out_the_catalogue_never_asks_the_progress(
    page: Page, live_server: str
) -> None:
    seed_device_progress(page)
    accounts_on(page, SIGNED_OUT)
    answer_json(page, ACCOUNT_PROGRESS_ROUTE, 200, ACCOUNT_PROGRESS)
    log = RequestLog(page)

    open_catalogue(page, live_server)
    expect(page.get_by_test_id("account-open")).to_be_visible()
    page.wait_for_timeout(QUIET_MS)

    assert log.count(STATUS_PATH) == 1
    assert log.count(ACCOUNT_PROGRESS_PATH) == 0
    expect_progresses(page, DEVICE_ONLY)
