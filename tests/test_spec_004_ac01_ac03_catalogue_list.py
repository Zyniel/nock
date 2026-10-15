"""Tests of spec 004, AC-1 to AC-3: the catalogue list.

AC-1 is the data of each listed grid, AC-2 the filter by force and the order
(newest first), AC-3 the progress kept on this device. The shared setup is in
`spec004_harness`.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, Route, expect

from nock.catalogue import Catalogue, GridSummary, summarize
from nock.grid import Grid
from nock.server import GRID_NUMBER_PATTERN, create_app
from spec004_harness import (
    ENTRY_2_JSON,
    expect_entry_2_attributes,
    expect_entry_2_texts,
    expect_item_numbers,
    fr_text,
    grid_from_text,
    item_by_number,
    json_numbers,
    load_fr,
    make_client,
    make_dist_dir,
    make_entry,
    make_reference_catalogue,
    summary_numbers,
)

FORBIDDEN_IN_BODIES = [
    '"answer"',
    '"cells"',
    '"clues"',
    "TAMIS",
    "NAVAL",
    "MIME",
    "IDES",
    "SENT",
    "VIDE",
    "AMEN",
    "LEST",
]
PROGRESS_KEY = "nock.progress"


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


def filter_button(page: Page, force: str) -> Locator:
    return page.locator(f'[data-testid="force-filter"][data-force="{force}"]')


def seed_progress(page: Page, raw_value: str) -> None:
    script = f"localStorage.setItem({PROGRESS_KEY!r}, {raw_value!r})"
    page.context.add_init_script(script)


# ---- AC-1: listing data -----------------------------------------------------


def test_ac1_summarize_gives_number_date_force_size_and_word_count(
    catalogue: Catalogue,
) -> None:
    entry_2 = catalogue.entries[1]

    summary = summarize(entry_2)

    assert summary == GridSummary(
        number=2,
        published_on=date(2026, 10, 1),
        force=2,
        width=5,
        height=5,
        word_count=8,
    )


def test_ac1_summarize_takes_force_and_number_from_the_entry(
    fx01_grid: Grid,
) -> None:
    entry = make_entry(fx01_grid, 777, date(2027, 1, 31), 4, True)

    summary = summarize(entry)

    assert summary.number == 777
    assert summary.published_on == date(2027, 1, 31)
    assert summary.force == 4
    assert summary.word_count == 8


def test_ac1_http_grid_summary_is_exact(client: TestClient) -> None:
    response = client.get("/api/grids/2")

    assert response.status_code == 200
    assert response.json() == ENTRY_2_JSON


def test_ac1_http_list_items_are_summaries(client: TestClient) -> None:
    response = client.get("/api/grids")

    assert response.status_code == 200
    assert ENTRY_2_JSON in response.json()
    for item in response.json():
        assert set(item) == set(ENTRY_2_JSON)


def test_ac1_http_empty_catalogue_lists_nothing(dist_dir: Path) -> None:
    empty_client = TestClient(create_app(dist_dir=dist_dir))

    response = empty_client.get("/api/grids")

    assert response.status_code == 200
    assert response.json() == []


def test_ac1_http_default_catalogue_is_empty_for_a_single_grid(
    dist_dir: Path,
) -> None:
    empty_client = TestClient(create_app(dist_dir=dist_dir))

    assert empty_client.get("/api/grids/1").status_code == 404


@pytest.mark.parametrize("path", ["/api/grids", "/api/grids/2"])
def test_ac1_http_bodies_hold_no_answer(client: TestClient, path: str) -> None:
    body = client.get(path).text

    for forbidden in FORBIDDEN_IN_BODIES:
        assert forbidden not in body


def test_ac1_grid_number_pattern_is_the_declared_one() -> None:
    assert GRID_NUMBER_PATTERN == r"^[1-9][0-9]{0,8}$"


def test_ac1_browser_item_shows_listing_data(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/")

    item = item_by_number(page, 2)
    expect(item).to_have_count(1)
    expect_entry_2_attributes(item)
    expect(item).to_contain_text("Grille n° 2")
    expect(item).to_contain_text("1 octobre 2026")
    expect(item).to_contain_text("Force 2")
    expect(item).to_contain_text("5 \N{MULTIPLICATION SIGN} 5")
    expect(item).to_contain_text("8 mots")
    expect_entry_2_texts(item)


def test_ac1_browser_other_items_carry_their_own_data(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    item_1 = item_by_number(page, 1)
    expect(item_1).to_have_attribute("data-published-on", "2026-09-01")
    expect(item_1).to_have_attribute("data-force", "1")
    expect(item_1).to_contain_text("1 septembre 2026")


@pytest.mark.parametrize("timezone_id", ["Pacific/Kiritimati", "Pacific/Pago_Pago"])
def test_ac1_browser_date_is_shown_in_utc(
    browser: Browser, live_server: str, timezone_id: str
) -> None:
    context = browser.new_context(timezone_id=timezone_id)
    try:
        page = context.new_page()
        page.goto(f"{live_server}/")

        expect(item_by_number(page, 2)).to_contain_text("1 octobre 2026")
    finally:
        context.close()


def test_ac1_browser_catalogue_request_failure_shows_the_error(
    page: Page, live_server: str
) -> None:
    def fail_with_500(route: Route) -> None:
        route.fulfill(status=500, body="boom")

    page.route(re.compile(r".*/api/grids(\?.*)?$"), fail_with_500)

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "error")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.error"])
    expect(page.get_by_test_id("catalogue-item")).to_have_count(0)


def test_ac1_browser_answer_that_is_not_an_array_is_an_error(
    page: Page, live_server: str
) -> None:
    def answer_with_object(route: Route) -> None:
        route.fulfill(status=200, content_type="application/json", body="{}")

    page.route(re.compile(r".*/api/grids(\?.*)?$"), answer_with_object)

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "error")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.error"])


def test_ac1_browser_loading_state_is_shown_until_the_answer(
    page: Page, live_server: str
) -> None:
    held_routes: list[Route] = []

    def hold(route: Route) -> None:
        held_routes.append(route)

    page.route(re.compile(r".*/api/grids(\?.*)?$"), hold)

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "loading")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.loading"])
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.heading"])


def test_ac1_browser_catalogue_page_is_ready_with_a_heading(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "ready")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.heading"])
    expect(catalogue_page).not_to_contain_text(load_fr()["catalogue.loading"])


class TestEmptyCatalogue:
    """The live server of the default (empty) catalogue."""

    @pytest.fixture
    def catalogue(self) -> Catalogue:
        return Catalogue()

    def test_ac1_browser_empty_catalogue_shows_the_empty_text(
        self, page: Page, live_server: str
    ) -> None:
        page.goto(f"{live_server}/")

        catalogue_page = page.get_by_test_id("catalogue-page")
        expect(catalogue_page).to_have_attribute("data-state", "ready")
        expect(catalogue_page).to_contain_text(load_fr()["catalogue.empty"])
        expect(page.get_by_test_id("catalogue-item")).to_have_count(0)
        expect(page.get_by_test_id("force-filter")).to_have_count(5)


# ---- AC-2: filter by force, newest first -------------------------------------


def test_ac2_published_summaries_are_newest_first_then_highest_number(
    catalogue: Catalogue,
) -> None:
    summaries = catalogue.published_summaries()

    assert summary_numbers(summaries) == [3, 2, 1]


def test_ac2_published_summaries_filter_on_force(catalogue: Catalogue) -> None:
    summaries = catalogue.published_summaries(force=1)

    assert summary_numbers(summaries) == [3, 1]


@pytest.mark.parametrize("force", [4, 5])
def test_ac2_published_summaries_of_a_force_without_entry_is_empty(
    catalogue: Catalogue, force: int
) -> None:
    assert catalogue.published_summaries(force=force) == []


def test_ac2_force_of_an_unpublished_entry_gives_nothing(
    catalogue: Catalogue,
) -> None:
    assert catalogue.published_summaries(force=3) == []


def test_ac2_dates_are_compared_as_dates_not_as_numbers(fx01_grid: Grid) -> None:
    older = make_entry(fx01_grid, 9, date(2026, 9, 30), 1, True)
    newer = make_entry(fx01_grid, 1, date(2026, 10, 1), 1, True)
    year_earlier = make_entry(fx01_grid, 8, date(2025, 12, 31), 1, True)
    catalogue = Catalogue(entries=(older, year_earlier, newer))

    assert summary_numbers(catalogue.published_summaries()) == [1, 9, 8]


def test_ac2_order_does_not_depend_on_the_order_of_entries(
    fx01_grid: Grid,
) -> None:
    entries = (
        make_entry(fx01_grid, 5, date(2026, 10, 1), 1, True),
        make_entry(fx01_grid, 6, date(2026, 10, 1), 1, True),
        make_entry(fx01_grid, 7, date(2026, 10, 1), 1, True),
    )

    forward = Catalogue(entries=entries)
    backward = Catalogue(entries=tuple(reversed(entries)))

    assert summary_numbers(forward.published_summaries()) == [7, 6, 5]
    assert summary_numbers(backward.published_summaries()) == [7, 6, 5]


def test_ac2_empty_catalogue_has_no_summary() -> None:
    assert Catalogue().published_summaries() == []


def test_ac2_http_list_is_newest_first(client: TestClient) -> None:
    body = client.get("/api/grids").json()

    assert json_numbers(body) == [3, 2, 1]


def test_ac2_http_list_filters_on_force(client: TestClient) -> None:
    response = client.get("/api/grids?force=1")

    assert response.status_code == 200
    assert json_numbers(response.json()) == [3, 1]


def test_ac2_http_force_without_grid_gives_an_empty_array(
    client: TestClient,
) -> None:
    response = client.get("/api/grids?force=4")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("force", ["0", "5", "x", ""])
def test_ac2_http_invalid_force_is_a_422(client: TestClient, force: str) -> None:
    response = client.get(f"/api/grids?force={force}")

    assert response.status_code == 422
    assert "detail" in response.json()


def test_ac2_http_unknown_query_parameter_is_ignored(client: TestClient) -> None:
    response = client.get("/api/grids?colour=red")

    assert response.status_code == 200
    assert json_numbers(response.json()) == [3, 2, 1]


def test_ac2_browser_list_is_newest_first_with_all_pressed(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    expect_item_numbers(page, [3, 2, 1])
    expect(page.get_by_test_id("catalogue-list")).to_be_visible()
    expect(filter_button(page, "all")).to_have_attribute("aria-pressed", "true")
    for force in ["1", "2", "3", "4"]:
        expect(filter_button(page, force)).to_have_attribute("aria-pressed", "false")


def test_ac2_browser_filter_buttons_are_five_in_order_and_labelled(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    buttons = page.get_by_test_id("force-filter")
    expect(buttons).to_have_count(5)
    expected_forces = ["all", "1", "2", "3", "4"]
    for index, force in enumerate(expected_forces):
        expect(buttons.nth(index)).to_have_attribute("data-force", force)
    expect(buttons.nth(0)).to_have_text(load_fr()["catalogue.filter.all"])
    for index in range(1, 5):
        expected_label = fr_text("catalogue.filter.force", force=index)
        expect(buttons.nth(index)).to_have_text(expected_label)


def test_ac2_browser_filter_group_is_labelled(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/")

    group = page.get_by_label(load_fr()["catalogue.filter.label"], exact=True)
    expect(group).to_be_visible()
    expect(group.get_by_test_id("force-filter")).to_have_count(5)


def test_ac2_browser_selecting_force_1_shows_its_grids(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")
    expect_item_numbers(page, [3, 2, 1])

    filter_button(page, "1").click()

    expect_item_numbers(page, [3, 1])
    expect(filter_button(page, "1")).to_have_attribute("aria-pressed", "true")
    expect(filter_button(page, "all")).to_have_attribute("aria-pressed", "false")


def test_ac2_browser_force_without_grid_shows_the_filtered_empty_text(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")
    expect_item_numbers(page, [3, 2, 1])

    filter_button(page, "4").click()

    expect_item_numbers(page, [])
    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.empty_filtered"])
    expect(catalogue_page).not_to_contain_text(load_fr()["catalogue.empty"])
    expect(filter_button(page, "4")).to_have_attribute("aria-pressed", "true")


def test_ac2_browser_selecting_all_again_restores_the_list(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")
    filter_button(page, "4").click()
    expect_item_numbers(page, [])

    filter_button(page, "all").click()

    expect_item_numbers(page, [3, 2, 1])
    expect(page.get_by_test_id("catalogue-page")).not_to_contain_text(
        load_fr()["catalogue.empty_filtered"]
    )


# ---- AC-3: progress on this device -------------------------------------------


def test_ac3_browser_progress_is_read_from_local_storage(
    page: Page, live_server: str
) -> None:
    seed_progress(page, '{"1": "started", "2": "finished", "99": "started"}')

    page.goto(f"{live_server}/")

    expect_item_numbers(page, [3, 2, 1])
    item_1 = item_by_number(page, 1)
    item_2 = item_by_number(page, 2)
    item_3 = item_by_number(page, 3)
    expect(item_1).to_have_attribute("data-progress", "started")
    expect(item_1.get_by_test_id("catalogue-progress")).to_have_text(
        load_fr()["catalogue.progress.started"]
    )
    expect(item_2).to_have_attribute("data-progress", "finished")
    expect(item_2.get_by_test_id("catalogue-progress")).to_have_text(
        load_fr()["catalogue.progress.finished"]
    )
    expect(item_3).to_have_attribute("data-progress", "none")
    expect(item_3.get_by_test_id("catalogue-progress")).to_have_count(0)


def test_ac3_browser_without_progress_every_item_is_none(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    expect_item_numbers(page, [3, 2, 1])
    for number in [1, 2, 3]:
        item = item_by_number(page, number)
        expect(item).to_have_attribute("data-progress", "none")
        expect(item.get_by_test_id("catalogue-progress")).to_have_count(0)


@pytest.mark.parametrize("raw_value", ["not json", "[1]", '{"1": "done"}'])
def test_ac3_browser_corrupt_progress_reads_as_none(
    page: Page, live_server: str, raw_value: str
) -> None:
    seed_progress(page, raw_value)

    page.goto(f"{live_server}/")

    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )
    expect_item_numbers(page, [3, 2, 1])
    for number in [1, 2, 3]:
        item = item_by_number(page, number)
        expect(item).to_have_attribute("data-progress", "none")
        expect(item.get_by_test_id("catalogue-progress")).to_have_count(0)


def test_ac3_browser_one_bad_value_does_not_hide_the_good_ones(
    page: Page, live_server: str
) -> None:
    seed_progress(page, '{"1": "started", "2": "done", "3": 1}')

    page.goto(f"{live_server}/")

    expect_item_numbers(page, [3, 2, 1])
    expect(item_by_number(page, 1)).to_have_attribute("data-progress", "started")
    expect(item_by_number(page, 2)).to_have_attribute("data-progress", "none")
    expect(item_by_number(page, 3)).to_have_attribute("data-progress", "none")


def test_ac3_browser_grid_page_shows_the_progress(page: Page, live_server: str) -> None:
    seed_progress(page, '{"1": "started", "2": "finished", "99": "started"}')

    page.goto(f"{live_server}/g/1")

    item = page.get_by_test_id("catalogue-item")
    expect(item).to_have_count(1)
    expect(item).to_have_attribute("data-progress", "started")
    expect(item.get_by_test_id("catalogue-progress")).to_have_text(
        load_fr()["catalogue.progress.started"]
    )


def test_ac3_browser_grid_page_without_progress_shows_none(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/g/1")

    item = page.get_by_test_id("catalogue-item")
    expect(item).to_have_attribute("data-progress", "none")
    expect(item.get_by_test_id("catalogue-progress")).to_have_count(0)
