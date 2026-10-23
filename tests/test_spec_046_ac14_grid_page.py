"""Tests of spec 046, AC-14: the grid page shows its one card in the catalogue's
frame.

Browser with live server, serving `CAT`. On `/g/2` at 1280 by 720 and 360 by 740,
`grid-page` holds `page-topbar` (56 px, its brand, no `account-open`) and a
`catalogue-column` with no `h1` holding one `catalogue-list` with the card of
grid 2, which has its drawing on the wide window only. With `GET /api/grids/2`
answering 500, `catalogue-status` is the error line.

Choices where the spec leaves room:

- "No `account-open`" is checked with accounts on (`GET /api/account` answering
  200 signed out), so that its absence is the grid page's rule, not the live
  server's accounts being off.
- "The card look of AC-5": white, 1 px solid `--nock-line`, radius 8 px, padding
  12 px 14 px, `display: flex`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec043_harness import LINE, RED, WHITE, fr_value
from spec046_harness import (
    SIGNED_OUT,
    SIZES,
    WAIT_TIMEOUT_MS,
    WIDE_BAR_HEIGHT,
    WIDE_BAR_INSET,
    OpenWindow,
    accounts_on,
    answer_json,
    border_problems,
    child_ids,
    child_tags,
    colour_problem,
    is_wide,
    padding_matches,
    page_topbar_problems,
    size_ids,
    style_of,
    window_opener,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_grid_page(page: Page, base_url: str, state: str = "ready") -> None:
    page.goto(f"{base_url}/g/2")
    expect(page.get_by_test_id("grid-page")).to_have_attribute(
        "data-state", state, timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac14_the_grid_page_has_the_56_px_bar_without_account_open(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    accounts_on(page, SIGNED_OUT)
    open_grid_page(page, live_server)
    page.wait_for_timeout(300)

    assert page_topbar_problems(page, WIDE_BAR_HEIGHT, WIDE_BAR_INSET) == []
    expect(page.get_by_test_id("account-open")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac14_the_grid_page_holds_the_bar_then_a_column_with_no_heading(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_grid_page(page, live_server)
    column = page.get_by_test_id("grid-page").get_by_test_id("catalogue-column")

    page_ids = child_ids(page.get_by_test_id("grid-page"))

    assert page_ids == ["page-topbar", "catalogue-column"], page_ids
    assert child_ids(column) == ["catalogue-list"], child_ids(column)
    assert "H1" not in child_tags(column)
    expect(column.locator("h1")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac14_the_list_holds_the_one_card_of_grid_2_in_the_card_look(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_grid_page(page, live_server)
    cards = page.get_by_test_id("catalogue-list").get_by_test_id("catalogue-item")

    expect(cards).to_have_count(1)
    card = cards.first
    expect(card).to_have_attribute("data-number", "2")
    problems = colour_problem(card, "card", "backgroundColor", WHITE)
    problems.extend(border_problems(card, "card", LINE))

    assert problems == []
    assert style_of(card, "borderTopLeftRadius") == "8px"
    assert padding_matches(card, "12px 14px")
    assert style_of(card, "display") == "flex"


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac14_the_card_has_its_drawing_on_the_wide_window_only(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_grid_page(page, live_server)

    thumbs = page.get_by_test_id("catalogue-thumb")

    expect(thumbs).to_have_count(1 if is_wide(width, height) else 0)


def test_ac14_a_failed_request_shows_the_error_line(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    answer_json(page, "**/api/grids/2", 500, {"detail": "Internal Server Error"})
    open_grid_page(page, live_server, "error")

    status = page.get_by_test_id("catalogue-status")

    expect(status).to_have_text(fr_value("catalogue.error"))
    assert colour_problem(status, "status", "color", RED) == []
