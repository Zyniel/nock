"""Tests of spec 048, AC-14: the three pages pass spec 035's scans, fit every
window and keep the keyboard.

Scans: spec 035's contrast scan (its AC-8) and language scan (its AC-9) at 1280
by 720 and 360 by 740 in each state the criterion lists, one test per page and
state that runs both scans. The language scan's test data are the nicknames
(`ANA`, `BOB`, shown `Ana`, `Bob`), `ana.probe@example.org`, `ana@`, the room
code `K7QM2X` and the share URL. Fit: at the eight window sizes of spec 006
AC-5, `document.documentElement.scrollWidth <= window.innerWidth`. Keyboard: spec
035's `Walker` (`tab_to`), each control reached with the focus ring (`2px`
`solid` navy, offset `2px`).

The pages are opened as in the other files of spec 048: the shared recap on the
live server with its routes answered by `page.route`, the account page on spec
033's account server with `AccountMock`, the ops page on spec 038's ops server
with the token seeded and the mocked ops API.

Readings of the spec's wording:

- "`Enter` on `account-delete` shows the panel and `Tab` then reaches
  `account-delete-confirm` and `account-delete-cancel`": after `Enter`, the
  walker moves the focus to each of the two buttons in turn.
- The ops page `ready` of the keyboard part is the dashboard with the replay
  `idle`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import contrast_problems, language_problems
from spec033_harness import (
    ANA_EMAIL,
    WINDOW_SIZES,
    AccountServer,
    account_live_server,
)
from spec035_harness import Walker
from spec038_harness import DASHBOARD_ROUTE, OpsServer, ops_live_server
from spec046_harness import HeldRoute, OpenWindow, fulfil_json, window_opener
from spec048_harness import (
    NOT_FOUND,
    ROOM_CODE,
    SHARE_PATH,
    SIGNED_OUT,
    SIZE_IDS,
    SIZES,
    AccountMock,
    ask_deletion,
    expect_account_state,
    no_horizontal_scroll,
    open_account,
    open_share,
    open_share_loading,
    open_share_unavailable,
    open_signed_in,
    ring_problems,
    submit_address,
)
from spec048_ops_harness import (
    ReplayRoute,
    expect_ops_state,
    open_ops,
    open_ready_ops,
    open_replay,
    replay,
    replay_answer,
    replay_empty,
    replay_fx02,
    seed_ops_token,
    set_position,
)
from sure_click import click_until_pressed

SHARE_STATES = ["loading", "loaded", "unavailable"]
ACCOUNT_STATES = [
    "loading",
    "signing_in",
    "signed_in",
    "deletion_asked",
    "link_invalid",
    "signed_out_error",
    "signed_out_sent",
    "deleted",
    "error",
]
OPS_STATES = [
    "locked_refused",
    "loading",
    "error",
    "ready_position_4",
    "ready_empty",
    "replay_not_found",
]
SIZE_LIST = list(WINDOW_SIZES)
SIZE_LIST_IDS = [f"{width}x{height}" for width, height in WINDOW_SIZES]
FIT_PAGES = ["share", "account", "ops_replay", "ops_replay_fx02"]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def account_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[AccountServer]:
    with account_live_server(tmp_path, catalogue) as server:
        yield server


@pytest.fixture
def ops_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


def scan_data(base_url: str) -> set[str]:
    """The test data the language scan accepts (see the module's docstring)."""
    return {"ANA", "BOB", ANA_EMAIL, "ana@", ROOM_CODE, f"{base_url}{SHARE_PATH}"}


def scan_problems(page: Page, base_url: str) -> list[str]:
    """Both scans of spec 035 on the page as it shows."""
    problems: list[str] = []
    for offender in contrast_problems(page):
        problems.append(f"contrast: {offender}")
    for text in language_problems(page, scan_data(base_url)):
        problems.append(f"language: {text!r}")
    return problems


# ---- Opening each state ------------------------------------------------------------


def open_share_state(page: Page, base_url: str, state: str) -> None:
    if state == "loading":
        open_share_loading(page, base_url)
    elif state == "loaded":
        open_share(page, base_url)
    else:
        open_share_unavailable(page, base_url)


def open_account_state(page: Page, base_url: str, state: str) -> None:
    """Open the account page in one of `ACCOUNT_STATES`."""
    if state in ("signed_in", "deletion_asked", "deleted"):
        open_signed_in(page, base_url)
        if state == "deletion_asked":
            ask_deletion(page)
        elif state == "deleted":
            ask_deletion(page)
            page.get_by_test_id("account-delete-confirm").click()
            expect_account_state(page, "deleted")
        return
    if state == "loading":
        open_account(page, base_url, AccountMock(status=None), "loading")
    elif state == "signing_in":
        mock = AccountMock(sign_in=None)
        open_account(page, base_url, mock, "signing_in", link=True)
    elif state == "link_invalid":
        mock = AccountMock(sign_in=404)
        open_account(page, base_url, mock, "link_invalid", link=True)
    elif state == "error":
        mock = AccountMock(status=(500, {"detail": "Internal Server Error"}))
        open_account(page, base_url, mock, "error")
    else:
        link_status = 422 if state == "signed_out_error" else 202
        mock = AccountMock(status=(200, SIGNED_OUT), link_statuses=(link_status,))
        open_account(page, base_url, mock, "signed_out")
        submit_address(page, "ana@")
        shown = "account-error" if state == "signed_out_error" else "account-sent"
        expect(page.get_by_test_id(shown)).to_be_visible()


def open_ops_state(page: Page, base_url: str, state: str, grid: Grid) -> None:
    """Open the ops page in one of `OPS_STATES`."""
    if state == "locked_refused":

        def refuse(route: Route) -> None:
            fulfil_json(route, 401, {"detail": "Not authorized"})

        page.route(DASHBOARD_ROUTE, refuse)
        open_ops(page, base_url)
        field = page.get_by_test_id("ops-token-input")
        field.fill("wrong")
        expect(field).to_have_value("wrong")
        # 2026-10-23: Firefox under load lost the press; main's run after #43.
        click_until_pressed(page.get_by_test_id("ops-token-submit"))
        expect(page.get_by_test_id("ops-token-error")).to_be_visible()
    elif state in ("loading", "error"):

        def fail(route: Route) -> None:
            fulfil_json(route, 500, {"detail": "Internal Server Error"})

        if state == "loading":
            HeldRoute(page, DASHBOARD_ROUTE)
        else:
            page.route(DASHBOARD_ROUTE, fail)
        seed_ops_token(page)
        open_ops(page, base_url)
        expect_ops_state(page, state)
    elif state == "ready_position_4":
        open_replay(page, base_url, replay_answer(replay(grid)), "ready")
        set_position(page, 4)
    elif state == "ready_empty":
        open_replay(page, base_url, replay_answer(replay_empty(grid)), "ready")
    else:
        open_replay(page, base_url, ReplayRoute(404, NOT_FOUND), "not_found")


# ---- Scans -------------------------------------------------------------------------


@pytest.mark.parametrize("state", SHARE_STATES)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac14_the_shared_recap_page_passes_both_scans(
    window: OpenWindow, live_server: str, size: tuple[int, int], state: str
) -> None:
    page = window(*size)
    open_share_state(page, live_server, state)

    assert scan_problems(page, live_server) == []


@pytest.mark.parametrize("state", ACCOUNT_STATES)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac14_the_account_page_passes_both_scans(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int], state: str
) -> None:
    page = window(*size)
    open_account_state(page, account_server.base_url, state)

    assert scan_problems(page, account_server.base_url) == []


@pytest.mark.parametrize("state", OPS_STATES)
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac14_the_ops_page_passes_both_scans(
    window: OpenWindow,
    ops_server: OpsServer,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    page = window(*size)
    open_ops_state(page, ops_server.base_url, state, fx01_grid)

    assert scan_problems(page, ops_server.base_url) == []


# ---- Every window ------------------------------------------------------------------


@pytest.mark.parametrize("size", SIZE_LIST, ids=SIZE_LIST_IDS)
def test_ac14_the_shared_recap_page_fits_every_window(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_share(page, live_server)

    assert no_horizontal_scroll(page)


@pytest.mark.parametrize("size", SIZE_LIST, ids=SIZE_LIST_IDS)
def test_ac14_the_account_page_with_the_deletion_asked_fits_every_window(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_signed_in(page, account_server.base_url)
    ask_deletion(page)

    assert no_horizontal_scroll(page)


@pytest.mark.parametrize("size", SIZE_LIST, ids=SIZE_LIST_IDS)
def test_ac14_the_ops_page_with_the_replay_fits_every_window(
    window: OpenWindow, ops_server: OpsServer, fx01_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_replay(page, ops_server.base_url, replay_answer(replay(fx01_grid)), "ready")
    expect(page.get_by_test_id("ops-replay-cell").first).to_be_visible()

    assert no_horizontal_scroll(page)


@pytest.mark.parametrize("size", SIZE_LIST, ids=SIZE_LIST_IDS)
def test_ac14_the_ops_page_with_the_fx02_replay_fits_every_window(
    window: OpenWindow, ops_server: OpsServer, fx02_grid: Grid, size: tuple[int, int]
) -> None:
    page = window(*size)
    answer = replay_answer(replay_fx02(fx02_grid))
    open_replay(page, ops_server.base_url, answer, "ready")
    expect(page.get_by_test_id("ops-replay-cell").first).to_be_visible()

    assert no_horizontal_scroll(page)


# ---- Keyboard only -----------------------------------------------------------------


def reach_with_ring(
    page: Page, walker: Walker, test_id: str, selector: str = ""
) -> list[str]:
    """`tab_to` the element, then read the focus ring of the element focused."""
    walker.tab_to(test_id, selector)
    focused = page.locator(f'[data-testid="{test_id}"]{selector}')
    return ring_problems(focused, f"{test_id}{selector}")


def test_ac14_keyboard_reaches_the_account_controls_with_the_ring(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page = window(1280, 720)
    open_signed_in(page, account_server.base_url)
    walker = Walker(page)

    problems: list[str] = []
    for test_id in ("account-room-link", "account-sign-out", "account-delete"):
        problems.extend(reach_with_ring(page, walker, test_id))
    page.keyboard.press("Enter")
    expect(page.get_by_test_id("account-delete-panel")).to_be_visible()
    for test_id in ("account-delete-confirm", "account-delete-cancel"):
        problems.extend(reach_with_ring(page, walker, test_id))

    assert problems == []


def test_ac14_keyboard_reaches_share_home_with_the_ring(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    open_share(page, live_server)

    problems = reach_with_ring(page, Walker(page), "share-home")

    assert problems == []


def test_ac14_keyboard_reaches_the_ops_controls_with_the_ring(
    window: OpenWindow, ops_server: OpsServer
) -> None:
    page = window(1280, 720)
    open_ready_ops(page, ops_server.base_url)
    walker = Walker(page)

    problems: list[str] = []
    for days in ("1", "7", "30"):
        problems.extend(
            reach_with_ring(page, walker, "ops-period", f'[data-days="{days}"]')
        )
    problems.extend(reach_with_ring(page, walker, "ops-replay-code"))
    problems.extend(reach_with_ring(page, walker, "ops-replay-submit"))

    assert problems == []
