"""Tests of spec 004, AC-4: an unpublished grid is hidden.

The grid is absent from the list and its direct URLs answer "not found"; the
routes also reject numbers outside the declared pattern. The shared setup is in
`spec004_harness`.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.server import create_app
from spec004_harness import (
    ENTRY_2_JSON,
    INDEX_HTML,
    NOT_FOUND_BODY,
    expect_item_numbers,
    grid_from_text,
    item_by_number,
    json_numbers,
    make_client,
    make_dist_dir,
    make_entry,
    make_reference_catalogue,
    summary_numbers,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    return make_reference_catalogue(fx01_grid)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def client(catalogue: Catalogue, dist_dir: Path) -> TestClient:
    return make_client(catalogue, dist_dir)


@pytest.fixture
def unbuilt_client(catalogue: Catalogue, tmp_path: Path) -> TestClient:
    return TestClient(create_app(catalogue=catalogue, dist_dir=tmp_path / "nodist"))


# ---- AC-4: unpublished grids -------------------------------------------------


def test_ac4_unpublished_entry_is_not_in_the_summaries(
    catalogue: Catalogue,
) -> None:
    assert 4 not in summary_numbers(catalogue.published_summaries())
    assert 4 not in summary_numbers(catalogue.published_summaries(force=3))


def test_ac4_find_published_returns_the_entry_or_none(catalogue: Catalogue) -> None:
    found = catalogue.find_published(2)

    assert found == catalogue.entries[1]
    assert catalogue.find_published(4) is None
    assert catalogue.find_published(99) is None


def test_ac4_a_published_grid_with_a_future_date_is_listed(
    fx01_grid: Grid,
) -> None:
    future = make_entry(fx01_grid, 5, date(2999, 1, 1), 2, True)
    past = make_entry(fx01_grid, 6, date(2020, 1, 1), 2, False)
    catalogue = Catalogue(entries=(future, past))

    assert summary_numbers(catalogue.published_summaries()) == [5]
    assert catalogue.find_published(5) == future
    assert catalogue.find_published(6) is None


def test_ac4_http_list_does_not_show_the_unpublished_grid(
    client: TestClient,
) -> None:
    assert 4 not in json_numbers(client.get("/api/grids").json())
    assert client.get("/api/grids?force=3").json() == []


@pytest.mark.parametrize("path", ["/api/grids/4", "/g/4", "/g/99"])
def test_ac4_http_unpublished_or_unknown_grid_is_a_json_404(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac4_http_published_grid_page_serves_index_html(client: TestClient) -> None:
    response = client.get("/g/2")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert response.text == INDEX_HTML


@pytest.mark.parametrize(
    "path",
    [
        "/api/grids/0",
        "/api/grids/01",
        "/api/grids/abc",
        "/api/grids/-1",
        "/g/0",
        "/g/01",
        "/g/abc",
        "/g/-1",
        "/g/1234567890",
    ],
)
def test_ac4_http_numbers_outside_the_pattern_are_a_json_404(
    client: TestClient, path: str
) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize("path", ["/api/grids/", "/g/2/", "/g/"])
def test_ac4_http_trailing_slash_is_a_404_without_redirect(
    client: TestClient, path: str
) -> None:
    response = client.get(path, follow_redirects=False)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac4_http_nine_digit_number_matches_the_pattern(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    entry = make_entry(fx01_grid, 999_999_999, date(2026, 10, 1), 1, True)
    big_client = TestClient(
        create_app(catalogue=Catalogue(entries=(entry,)), dist_dir=dist_dir)
    )

    api_response = big_client.get("/api/grids/999999999")
    page_response = big_client.get("/g/999999999")

    assert api_response.status_code == 200
    assert api_response.json()["number"] == 999_999_999
    assert page_response.status_code == 200
    assert page_response.text == INDEX_HTML


def test_ac4_http_unbuilt_client_answers_503_for_a_published_grid(
    unbuilt_client: TestClient,
) -> None:
    assert unbuilt_client.get("/g/2").status_code == 503


@pytest.mark.parametrize("path", ["/g/4", "/g/99", "/g/0"])
def test_ac4_http_unbuilt_client_still_answers_404_for_hidden_grids(
    unbuilt_client: TestClient, path: str
) -> None:
    response = unbuilt_client.get(path)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


def test_ac4_http_api_still_works_when_the_client_is_not_built(
    unbuilt_client: TestClient,
) -> None:
    assert unbuilt_client.get("/api/grids/2").json() == ENTRY_2_JSON


def test_ac4_browser_unpublished_grid_is_not_listed(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    expect_item_numbers(page, [3, 2, 1])
    expect(item_by_number(page, 4)).to_have_count(0)
