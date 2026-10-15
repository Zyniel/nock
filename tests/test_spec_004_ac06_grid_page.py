"""Tests of spec 004, AC-6: the grid page of a direct URL (`/g/<number>`).

The shared setup is in `spec004_harness`.
"""

from __future__ import annotations

import json
import re

import pytest
from playwright.sync_api import Page, Request, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec004_harness import (
    NOT_FOUND_BODY,
    expect_entry_2_attributes,
    expect_entry_2_texts,
    grid_from_text,
    load_fr,
    make_reference_catalogue,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


# ---- AC-6: grid page ---------------------------------------------------------


def test_ac6_browser_grid_page_shows_one_grid(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "ready")
    item = grid_page.get_by_test_id("catalogue-item")
    expect(item).to_have_count(1)
    expect_entry_2_attributes(item)
    expect_entry_2_texts(item)
    expect(page.get_by_test_id("catalogue-page")).to_have_count(0)
    expect(page.get_by_test_id("room-page")).to_have_count(0)


def test_ac6_browser_grid_page_shows_the_grid_asked_for(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/g/3")

    item = page.get_by_test_id("grid-page").get_by_test_id("catalogue-item")
    expect(item).to_have_count(1)
    expect(item).to_have_attribute("data-number", "3")
    expect(item).to_have_attribute("data-force", "1")
    expect(item).to_have_attribute("data-published-on", "2026-10-01")


def test_ac6_browser_grid_page_asks_the_api_for_that_grid(
    page: Page, live_server: str
) -> None:
    requested_paths: list[str] = []

    def record_request(request: Request) -> None:
        url = request.url
        requested_paths.append(url)

    page.on("request", record_request)

    page.goto(f"{live_server}/g/2")

    expect(page.get_by_test_id("grid-page")).to_have_attribute("data-state", "ready")
    api_requests = [url for url in requested_paths if "/api/grids" in url]
    assert api_requests
    assert api_requests[0].endswith("/api/grids/2")


def test_ac6_browser_grid_page_shows_not_found_on_a_404_answer(
    page: Page, live_server: str
) -> None:
    def answer_404(route: Route) -> None:
        route.fulfill(
            status=404,
            content_type="application/json",
            body=json.dumps(NOT_FOUND_BODY),
        )

    page.route(re.compile(r".*/api/grids/2$"), answer_404)

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "not_found")
    expect(grid_page).to_contain_text(load_fr()["not_found.heading"])
    expect(grid_page.get_by_test_id("catalogue-item")).to_have_count(0)


def test_ac6_browser_grid_page_shows_the_error_state_on_a_500_answer(
    page: Page, live_server: str
) -> None:
    def fail_with_500(route: Route) -> None:
        route.fulfill(status=500, body="boom")

    page.route(re.compile(r".*/api/grids/2$"), fail_with_500)

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "error")
    expect(grid_page).to_contain_text(load_fr()["catalogue.error"])
