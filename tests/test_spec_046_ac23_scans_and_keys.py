"""Tests of spec 046, AC-23: the pages of this spec pass spec 035's scans, and
`fr.json` holds this spec's keys.

At 1280 by 720 and at 360 by 740, in each state of the criterion, spec 035's
contrast scan (its AC-8) and language scan (its AC-9) find no offending element:
`/` with `CAT`, `nock.progress` `{"1": "started", "2": "finished"}`, `ROOMS2` and
`HIST2`; `/` loading, in error, empty, and with no grid of the selected force;
`/` after a failed « Jouer »; `/` with `account-dialog` open signed out (after
`account-error` for `ana@`) and signed in; `/g/2`; the nickname card with
`nickname-error`; each of the five status cards of AC-17; the `not_found` card;
the page not found; and the opening of AC-20. Static: the values of `share.home`
and `room.status.not_found_detail`, the two keys removed, and no `account-link`
left under `web/src`.

Choices where the spec leaves room:

- The language scan's data: the nicknames as the pages show them (`Ana`, `Bob`,
  `Cy`), the room codes, the e-mail address and `ana@`, and the dates the pages
  write (spec 024's `language_data` gives the room codes and the nicknames).
- Each state is scanned once for both scans, in one test.
- `account-error` for `ana@`: the test types `ana@` in `account-email-input` and
  submits with `account-email-submit`, the route answering 422 (as spec 048
  AC-5 does on the account page).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import contrast_problems, language_problems
from spec032_harness import ABC, XYZ
from spec035_harness import (
    build_fx01_grid,
    build_reference_catalogue,
    load_fr,
    unknown_texts,
)
from spec041_harness import WEB_SRC_DIR
from spec046_harness import (
    EMAIL,
    GRIDS_ROUTE,
    REFUSALS,
    ROOM_CODE,
    SIGNED_IN,
    SIGNED_OUT,
    SIZES,
    UNKNOWN_CODE,
    WAIT_TIMEOUT_MS,
    HeldRoute,
    OpenWindow,
    accounts_on,
    answer_json,
    expect_history_count,
    expect_my_rooms_ready,
    fail_play,
    item_of,
    open_catalogue,
    open_catalogue_loading,
    open_nickname_card,
    open_nowhere,
    open_opening,
    open_status_card,
    open_unknown_room,
    seed_hist2,
    seed_progress,
    seed_rooms2,
    show_nickname_error,
    window_opener,
)
from sure_click import click_until_pressed

STATES = [
    "catalogue",
    "loading",
    "error",
    "empty",
    "filtered",
    "play-failed",
    "dialog-signed-out",
    "dialog-signed-in",
    "grid-page",
    "nickname-error",
    *[f"card-{refusal}" for refusal in REFUSALS],
    "not-found-card",
    "page-not-found",
    "opening",
]
CASES = [(size, state) for size in SIZES for state in STATES]
CASE_IDS = [f"{w}x{h}-{state}" for (w, h), state in CASES]

SCAN_DATA = {
    ROOM_CODE,
    UNKNOWN_CODE,
    XYZ,
    ABC,
    "QQQQQQ",
    "Ana",
    "Bob",
    "Cy",
    "ANA",
    EMAIL,
    "ana@",
    "1 septembre 2026",
    "1 octobre 2026",
    "14 octobre 2026",
}
NEW_KEYS = {
    "share.home": "Voir les grilles",
    "room.status.not_found_detail": "Un salon est "
    "effac\N{LATIN SMALL LETTER E WITH ACUTE}"
    " apr\N{LATIN SMALL LETTER E WITH GRAVE}s un certain temps sans modification.",
}
REMOVED_KEYS = ("my_rooms.loading", "my_rooms.empty")
# Spec 035 AC-9's samples (as spec 032 AC-6's test lists them): the checker flags
# the first ones and accepts the others, also with this spec's new key.
FLAGGED_SAMPLES = [
    "Loading\N{HORIZONTAL ELLIPSIS}",
    "Salle",
    "Check word",
    "Error: connection lost",
    "Score: 3",
    "Grille n\N{DEGREE SIGN} deux",
]
ACCEPTED_SAMPLES = [
    "Salon",
    "Salon ABC123",
    "Grille n\N{DEGREE SIGN} 2",
    "Ana a rejoint le salon",
    "0:00",
    "1:02:05",
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_dialog(page: Page, base_url: str, status: dict[str, object]) -> None:
    """Open `/` with accounts on, then the account dialog from « Compte »."""
    signed_in = status["signed_in"] is True
    accounts_on(page, status, link_status=422)
    open_catalogue(page, base_url)
    page.get_by_test_id("account-open").click()
    expect(page.get_by_test_id("account-dialog")).to_have_attribute("open", "")
    if not signed_in:
        email_input = page.get_by_test_id("account-email-input")
        email_input.fill("ana@")
        # Fix after #40's CI: the field holds the text before the submit (no race).
        expect(email_input).to_have_value("ana@")
        # 2026-10-23: Firefox under load lost the press; main's run after #43.
        click_until_pressed(page.get_by_test_id("account-email-submit"))
        expect(page.get_by_test_id("account-error")).to_be_visible()


def open_catalogue_state(page: Page, base_url: str, state: str) -> None:
    """Open one of the catalogue's states of AC-23."""
    catalogue_page = page.get_by_test_id("catalogue-page")
    if state == "catalogue":
        seed_progress(page)
        seed_rooms2(page)
        seed_hist2(page)
        open_catalogue(page, base_url)
        expect_my_rooms_ready(page, 2)
        expect_history_count(page, 2)
        expect(page.get_by_test_id("catalogue-progress")).to_have_count(2)
    elif state == "loading":
        HeldRoute(page, GRIDS_ROUTE)
        open_catalogue_loading(page, base_url)
        expect(catalogue_page).to_have_attribute("data-state", "loading")
    elif state == "error":
        answer_json(page, GRIDS_ROUTE, 500, {"detail": "Internal Server Error"})
        open_catalogue_loading(page, base_url)
        expect(catalogue_page).to_have_attribute("data-state", "error")
    elif state == "empty":
        answer_json(page, GRIDS_ROUTE, 200, [])
        open_catalogue(page, base_url)
    elif state == "filtered":
        open_catalogue(page, base_url)
        page.locator('[data-testid="force-filter"][data-force="4"]').click()
        expect(page.get_by_test_id("catalogue-status")).to_be_visible()
    else:
        fail_play(page)
        open_catalogue(page, base_url)
        item_of(page, 2).get_by_test_id("catalogue-play").click()
        expect(page.get_by_test_id("catalogue-error")).to_be_visible()


def open_scan_state(page: Page, base_url: str, state: str) -> None:
    """Open one of AC-23's states and wait until it shows with its fonts."""
    if state in ("catalogue", "loading", "error", "empty", "filtered", "play-failed"):
        open_catalogue_state(page, base_url, state)
    elif state == "dialog-signed-out":
        open_dialog(page, base_url, SIGNED_OUT)
    elif state == "dialog-signed-in":
        open_dialog(page, base_url, SIGNED_IN)
    elif state == "grid-page":
        page.goto(f"{base_url}/g/2")
        expect(page.get_by_test_id("grid-page")).to_have_attribute(
            "data-state", "ready", timeout=WAIT_TIMEOUT_MS
        )
    elif state == "nickname-error":
        open_nickname_card(page, base_url)
        show_nickname_error(page)
    elif state.startswith("card-"):
        open_status_card(page, base_url, state.removeprefix("card-"))
    elif state == "not-found-card":
        open_unknown_room(page, base_url)
    elif state == "page-not-found":
        open_nowhere(page, base_url)
    else:
        open_opening(page, base_url)
    wait_for_fonts(page)


# ---- The scans -----------------------------------------------------------------


@pytest.mark.parametrize(("size", "state"), CASES, ids=CASE_IDS)
def test_ac23_the_contrast_and_language_scans_find_no_offender(
    window: OpenWindow, live_server: str, size: tuple[int, int], state: str
) -> None:
    page = window(*size)
    open_scan_state(page, live_server, state)
    expect(page.locator("html")).to_have_attribute("lang", "fr")

    contrast = contrast_problems(page)
    language = language_problems(page, SCAN_DATA)

    assert contrast == []
    assert language == []


# ---- Static checks -----------------------------------------------------------


@pytest.mark.parametrize(("key", "value"), list(NEW_KEYS.items()))
def test_ac23_fr_json_holds_each_key_of_this_spec(key: str, value: str) -> None:
    assert load_fr().get(key) == value


def test_ac23_fr_json_holds_none_of_the_removed_keys() -> None:
    fr = load_fr()

    present = [key for key in REMOVED_KEYS if key in fr]

    assert present == []


def test_ac23_no_file_under_web_src_holds_account_link() -> None:
    holders: list[str] = []
    for path in sorted(WEB_SRC_DIR.rglob("*")):
        if path.is_file() and b"account-link" in path.read_bytes():
            holders.append(str(path))

    assert holders == []


def test_ac23_the_language_checker_still_flags_spec_035s_samples() -> None:
    assert unknown_texts(FLAGGED_SAMPLES, set()) == FLAGGED_SAMPLES
    assert unknown_texts(ACCEPTED_SAMPLES, set()) == []
