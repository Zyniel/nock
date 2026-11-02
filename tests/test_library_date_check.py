"""Tests of `content/library.md` AC-25: a summary whose `published_on` is not a
calendar date is a failed answer (rule 2).

Browser with the live server serving `CAT`. The test lets the page's request reach
the server (`route.fetch`), puts `2026-02-30` (no such day) or `hier` in grid 2's
`published_on`, and gives the page that answer: `/` shows « Impossible de charger
les grilles. » in its `error` state, with no filter and no card; `/g/2`, given that
summary by `GET /api/grids/2`, shows the same line in its `error` state, no card.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec004_harness import grid_from_text, load_fr, make_reference_catalogue

LIST_ROUTE = re.compile(r".*/api/grids(\?.*)?$")
GRID_2_ROUTE = re.compile(r".*/api/grids/2$")
NOT_A_DATE = [
    pytest.param("2026-02-30", id="february-30"),
    pytest.param("hier", id="hier"),
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


def with_grid_2_published_on(summary: dict[str, object], published_on: str) -> None:
    """Put `published_on` in a summary when it is grid 2's."""
    if summary["number"] == 2:
        summary["published_on"] = published_on


def answer_list_with(published_on: str) -> Callable[[Route], None]:
    """A route handler: the server's list, grid 2 published on `published_on`."""

    def answer(route: Route) -> None:
        summaries = route.fetch().json()
        assert isinstance(summaries, list), summaries
        for summary in summaries:
            with_grid_2_published_on(summary, published_on)
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps(summaries)
        )

    return answer


def answer_grid_2_with(published_on: str) -> Callable[[Route], None]:
    """A route handler: the server's summary of grid 2, published on `published_on`."""

    def answer(route: Route) -> None:
        summary = route.fetch().json()
        assert isinstance(summary, dict), summary
        with_grid_2_published_on(summary, published_on)
        route.fulfill(
            status=200, content_type="application/json", body=json.dumps(summary)
        )

    return answer


@pytest.mark.parametrize("published_on", NOT_A_DATE)
def test_ac25_a_list_with_a_date_that_is_not_a_calendar_date_is_an_error(
    page: Page, live_server: str, published_on: str
) -> None:
    page.route(LIST_ROUTE, answer_list_with(published_on))

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "error")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.error"])
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)
    expect(page.get_by_test_id("catalogue-item")).to_have_count(0)


@pytest.mark.parametrize("published_on", NOT_A_DATE)
def test_ac25_a_grid_page_given_that_summary_shows_the_error(
    page: Page, live_server: str, published_on: str
) -> None:
    page.route(GRID_2_ROUTE, answer_grid_2_with(published_on))

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "error")
    expect(grid_page).to_contain_text(load_fr()["catalogue.error"])
    expect(grid_page.get_by_test_id("catalogue-item")).to_have_count(0)
