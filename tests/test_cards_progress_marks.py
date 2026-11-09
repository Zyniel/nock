"""Tests of content/cards, AC-11 and AC-13: « Jouer » and « Rejouer » write one key.

Browser with the live server serving `CAT` (accounts off, so the account routes are
answered by `page.route`); the tap creates a real room.

Choices where the spec leaves room:

- "Signed in on `/`": `GET /api/account` answers `signed_in` and the test waits for
  the « Compte » button (the status is handled) before the tap.
- "Not answered yet when the tap comes": the status request is held and never
  answered; the test waits for the request to be held and for the catalogue to be
  `ready` before the tap.
- "Answered `{}`" on `/g/2`: the test waits for the progress request to end before
  the tap, since a tap before that answer counts as signed out.
- AC-13's « Rejouer »: the device holds one `nock.history` record of grid 2, and
  the account's history is empty.
- Every storage seed is `seed_storage`'s: it only fills absent keys, so it never
  overwrites a key the client wrote since.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect

from cards_harness import (
    ACCOUNT_PROGRESS_KEY,
    ACCOUNT_PROGRESS_PATH,
    ACCOUNT_PROGRESS_ROUTE,
    PROGRESS_KEY,
    RequestLog,
    device_keys,
    open_grid,
    stored_object,
    tap_play,
    tap_replay,
    wait_for_progress_answers,
    wait_for_stored,
)
from spec029_harness import HISTORY_KEY, device_record, history_value
from spec032_harness import seed_storage
from spec042_harness import wait_until
from spec046_harness import (
    ACCOUNT_ROUTE,
    SIGNED_IN,
    SIGNED_OUT,
    HeldRoute,
    accounts_on,
    answer_json,
    open_catalogue,
)

CATALOGUE_KIND = "reference"

FINISHED_ONE = {"1": "finished"}
REPLAYED_ROOM = "QQQQQQ"
REPLAYED_AT = "2026-10-14T08:30:00Z"


def seed_finished_one(page: Page) -> None:
    """The device holds `nock.progress` `{"1": "finished"}` and no other key."""
    seed_storage(page, {PROGRESS_KEY: json.dumps(FINISHED_ONE)})


def open_signed_in_catalogue(page: Page, base_url: str) -> None:
    """Open `/` with the account signed in, once its status is handled."""
    open_catalogue(page, base_url)
    expect(page.get_by_test_id("account-open")).to_be_visible()


# ---- AC-11: « Jouer » on the catalogue -------------------------------------------


def test_ac11_signed_in_the_tap_writes_the_account_key_and_leaves_the_device_key(
    page: Page, live_server: str
) -> None:
    seed_finished_one(page)
    accounts_on(page, SIGNED_IN)
    open_signed_in_catalogue(page, live_server)

    tap_play(page, 2)

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, {"2": "started"})
    assert stored_object(page, PROGRESS_KEY) == FINISHED_ONE


def test_ac11_signed_out_the_tap_writes_the_device_key_alone(
    page: Page, live_server: str
) -> None:
    seed_finished_one(page)
    accounts_on(page, SIGNED_OUT)
    open_catalogue(page, live_server)
    expect(page.get_by_test_id("account-open")).to_be_visible()

    tap_play(page, 2)

    wait_for_stored(page, PROGRESS_KEY, {"1": "finished", "2": "started"})
    assert stored_object(page, ACCOUNT_PROGRESS_KEY) is None


def test_ac11_a_tap_before_the_status_answers_counts_as_signed_out(
    page: Page, live_server: str
) -> None:
    seed_finished_one(page)
    accounts_on(page, SIGNED_IN)
    held = HeldRoute(page, ACCOUNT_ROUTE)
    open_catalogue(page, live_server)
    wait_until(page, lambda: len(held.routes) == 1, "the held status request")

    tap_play(page, 2)

    wait_for_stored(page, PROGRESS_KEY, {"1": "finished", "2": "started"})
    assert stored_object(page, ACCOUNT_PROGRESS_KEY) is None


# ---- AC-13: « Jouer » on /g/<n> and « Rejouer » ----------------------------------


def test_ac13_the_grid_page_signed_in_writes_the_account_key(
    page: Page, live_server: str
) -> None:
    answer_json(page, ACCOUNT_PROGRESS_ROUTE, 200, {})
    log = RequestLog(page)
    open_grid(page, live_server, 2)
    wait_for_progress_answers(page, log, 1)

    tap_play(page, 2)

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, {"2": "started"})
    assert stored_object(page, PROGRESS_KEY) is None
    assert log.count(ACCOUNT_PROGRESS_PATH) == 1


def test_ac13_the_grid_page_signed_out_writes_the_device_key(
    page: Page, live_server: str
) -> None:
    answer_json(page, ACCOUNT_PROGRESS_ROUTE, 401, {"detail": "Not authorized"})
    log = RequestLog(page)
    open_grid(page, live_server, 2)
    wait_for_progress_answers(page, log, 1)

    tap_play(page, 2)

    wait_for_stored(page, PROGRESS_KEY, {"2": "started"})
    assert stored_object(page, ACCOUNT_PROGRESS_KEY) is None


def test_ac13_signed_in_the_replay_of_a_grid_writes_the_account_key(
    page: Page, live_server: str
) -> None:
    record = device_record(REPLAYED_ROOM, 2, REPLAYED_AT, 600_000, ["Bob"])
    seed_storage(page, {HISTORY_KEY: history_value([record])})
    accounts_on(page, SIGNED_IN)
    open_signed_in_catalogue(page, live_server)

    tap_replay(page, REPLAYED_ROOM)

    wait_for_stored(page, ACCOUNT_PROGRESS_KEY, {"2": "started"})
    assert device_keys(page) == (None, {"2": "started"})
