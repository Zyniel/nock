"""Tests of `content/library.md` AC-18: the grid page while its summary is on the way.

Browser with the live server serving `CAT`. `GET /api/grids/2` is held (the route
keeps the request and never answers): `/g/2` is in its `loading` state and shows
« Chargement… » (`catalogue.loading`) as the muted state line of the catalogue, and
no card. The 404 and 500 answers of the same criterion are proven by the tests of
004 AC-6 and 046 AC-14.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from spec004_harness import load_fr
from spec046_harness import POLL_MS, WAIT_TIMEOUT_MS, HeldRoute, muted_line_problems

GRID_2_ROUTE = "**/api/grids/2"


CATALOGUE_KIND = "reference"


def test_ac18_while_the_grid_has_not_answered_the_page_shows_a_muted_loading_line(
    page: Page, live_server: str
) -> None:
    held = HeldRoute(page, GRID_2_ROUTE)

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    status = grid_page.get_by_test_id("catalogue-status")
    expect(grid_page).to_have_attribute("data-state", "loading")
    expect(status).to_have_text(load_fr()["catalogue.loading"])
    assert muted_line_problems(status) == []
    expect(grid_page.get_by_test_id("catalogue-item")).to_have_count(0)
    waited_ms = 0
    while len(held.routes) < 1 and waited_ms < WAIT_TIMEOUT_MS:
        page.wait_for_timeout(POLL_MS)
        waited_ms += POLL_MS
    assert len(held.routes) == 1
