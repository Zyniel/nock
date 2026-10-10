"""Tests of spec 004: the grid catalogue (model, HTTP routes and Svelte pages)."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, Route, expect
from pydantic import ValidationError

from nock.catalogue import (
    GRIDS_DIR,
    Catalogue,
    CatalogueEntry,
    CatalogueError,
    GridSummary,
    load_catalogue,
    summarize,
)
from nock.grid import Grid
from nock.grid_import import GridImportError
from nock.server import GRID_NUMBER_PATTERN, create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"
INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
NOT_FOUND_BODY = {"detail": "Not Found"}
ENTRY_2_JSON = {
    "number": 2,
    "published_on": "2026-10-01",
    "force": 2,
    "width": 5,
    "height": 5,
    "word_count": 8,
}
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
    return Grid.model_validate_json(fx01_text)


def make_entry(
    grid: Grid, number: int, published_on: date, force: int, published: bool
) -> CatalogueEntry:
    return CatalogueEntry(
        number=number,
        published_on=published_on,
        force=force,
        published=published,
        grid=grid,
    )


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of the spec (also served by live_server)."""
    entries = (
        make_entry(fx01_grid, 1, date(2026, 9, 1), 1, True),
        make_entry(fx01_grid, 2, date(2026, 10, 1), 2, True),
        make_entry(fx01_grid, 3, date(2026, 10, 1), 1, True),
        make_entry(fx01_grid, 4, date(2026, 10, 5), 3, False),
    )
    return Catalogue(entries=entries)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


@pytest.fixture
def client(catalogue: Catalogue, dist_dir: Path) -> TestClient:
    return TestClient(create_app(catalogue=catalogue, dist_dir=dist_dir))


@pytest.fixture
def unbuilt_client(catalogue: Catalogue, tmp_path: Path) -> TestClient:
    return TestClient(create_app(catalogue=catalogue, dist_dir=tmp_path / "nodist"))


def summary_numbers(summaries: list[GridSummary]) -> list[int]:
    numbers: list[int] = []
    for summary in summaries:
        numbers.append(summary.number)
    return numbers


def json_numbers(body: list[dict[str, object]]) -> list[object]:
    numbers: list[object] = []
    for item in body:
        numbers.append(item["number"])
    return numbers


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fr_text(key: str, **values: object) -> str:
    """Return the fr.json text of `key` with its {placeholders} filled."""
    text = load_fr()[key]
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def write_catalogue_file(
    directory: Path, name: str, grid_text: str, **overrides: object
) -> Path:
    """Write a valid catalogue file (number 1) and apply `overrides` to its keys."""
    payload: dict[str, object] = {
        "number": 1,
        "published_on": "2026-10-01",
        "force": 2,
        "published": True,
        "grid": json.loads(grid_text),
    }
    for key, value in overrides.items():
        payload[key] = value
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def item_by_number(page: Page, number: int) -> Locator:
    return page.locator(f'[data-testid="catalogue-item"][data-number="{number}"]')


def filter_button(page: Page, force: str) -> Locator:
    return page.locator(f'[data-testid="force-filter"][data-force="{force}"]')


def expect_item_numbers(page: Page, numbers: list[int]) -> None:
    """Expect the shown catalogue items to be exactly `numbers`, in order."""
    items = page.get_by_test_id("catalogue-item")
    expect(items).to_have_count(len(numbers))
    for index, number in enumerate(numbers):
        expect(items.nth(index)).to_have_attribute("data-number", str(number))


def seed_progress(page: Page, raw_value: str) -> None:
    script = f"localStorage.setItem({PROGRESS_KEY!r}, {raw_value!r})"
    page.context.add_init_script(script)


def expect_entry_2_attributes(item: Locator) -> None:
    expect(item).to_have_attribute("data-number", "2")
    expect(item).to_have_attribute("data-published-on", "2026-10-01")
    expect(item).to_have_attribute("data-force", "2")
    expect(item).to_have_attribute("data-width", "5")
    expect(item).to_have_attribute("data-height", "5")
    expect(item).to_have_attribute("data-word-count", "8")


def expect_entry_2_texts(item: Locator) -> None:
    expect(item).to_contain_text(fr_text("catalogue.item.number", number=2))
    expect(item).to_contain_text(
        fr_text("catalogue.item.published", date="1 octobre 2026")
    )
    expect(item).to_contain_text(fr_text("catalogue.item.force", force=2))
    expect(item).to_contain_text(fr_text("catalogue.item.size", width=5, height=5))
    expect(item).to_contain_text(fr_text("catalogue.item.words", count=8))


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

    assert summary_numbers(summaries) == [2, 3, 1]


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

    assert json_numbers(body) == [2, 3, 1]


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
    assert json_numbers(response.json()) == [2, 3, 1]


def test_ac2_browser_list_is_newest_first_with_all_pressed(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    expect_item_numbers(page, [2, 3, 1])
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
    expect_item_numbers(page, [2, 3, 1])

    filter_button(page, "1").click()

    expect_item_numbers(page, [3, 1])
    expect(filter_button(page, "1")).to_have_attribute("aria-pressed", "true")
    expect(filter_button(page, "all")).to_have_attribute("aria-pressed", "false")


def test_ac2_browser_force_without_grid_shows_the_filtered_empty_text(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")
    expect_item_numbers(page, [2, 3, 1])

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

    expect_item_numbers(page, [2, 3, 1])
    expect(page.get_by_test_id("catalogue-page")).not_to_contain_text(
        load_fr()["catalogue.empty_filtered"]
    )


# ---- AC-3: progress on this device -------------------------------------------


def test_ac3_browser_progress_is_read_from_local_storage(
    page: Page, live_server: str
) -> None:
    seed_progress(page, '{"1": "started", "2": "finished", "99": "started"}')

    page.goto(f"{live_server}/")

    expect_item_numbers(page, [2, 3, 1])
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

    expect_item_numbers(page, [2, 3, 1])
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
    expect_item_numbers(page, [2, 3, 1])
    for number in [1, 2, 3]:
        item = item_by_number(page, number)
        expect(item).to_have_attribute("data-progress", "none")
        expect(item.get_by_test_id("catalogue-progress")).to_have_count(0)


def test_ac3_browser_one_bad_value_does_not_hide_the_good_ones(
    page: Page, live_server: str
) -> None:
    seed_progress(page, '{"1": "started", "2": "done", "3": 1}')

    page.goto(f"{live_server}/")

    expect_item_numbers(page, [2, 3, 1])
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

    expect_item_numbers(page, [2, 3, 1])
    expect(item_by_number(page, 4)).to_have_count(0)


# ---- AC-5: catalogue files ---------------------------------------------------


def test_ac5_grids_dir_is_the_grids_directory_of_the_repository() -> None:
    assert GRIDS_DIR == PROJECT_ROOT / "grids"


def test_ac5_files_load_in_file_name_order(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=2)
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=1)

    loaded = load_catalogue(tmp_path)

    numbers = []
    for entry in loaded.entries:
        numbers.append(entry.number)
    assert numbers == [1, 2]
    expected_grid = Grid.model_validate_json(fx01_text)
    for entry in loaded.entries:
        assert entry.grid == expected_grid


def test_ac5_file_fields_are_read(tmp_path: Path, fx01_text: str) -> None:
    write_catalogue_file(
        tmp_path,
        "g.json",
        fx01_text,
        number=42,
        published_on="2026-02-03",
        force=4,
        published=False,
    )

    loaded = load_catalogue(tmp_path)

    assert len(loaded.entries) == 1
    entry = loaded.entries[0]
    assert entry.number == 42
    assert entry.published_on == date(2026, 2, 3)
    assert entry.force == 4
    assert entry.published is False


def test_ac5_missing_directory_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path / "absent") == Catalogue()


def test_ac5_empty_directory_is_an_empty_catalogue(tmp_path: Path) -> None:
    assert load_catalogue(tmp_path) == Catalogue()


def test_ac5_other_extensions_and_sub_directories_are_ignored(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=1)
    (tmp_path / "notes.txt").write_text("not a catalogue file", encoding="utf-8")
    old_directory = tmp_path / "old"
    old_directory.mkdir()
    write_catalogue_file(old_directory, "z.json", fx01_text, number=9)

    loaded = load_catalogue(tmp_path)

    numbers = []
    for entry in loaded.entries:
        numbers.append(entry.number)
    assert numbers == [1]


def test_ac5_a_rejected_grid_raises_a_catalogue_error_from_the_import_error(
    tmp_path: Path, fx01_text: str
) -> None:
    broken_text = fx01_text.replace('"MIME"', '"MIMA"')
    assert broken_text != fx01_text
    write_catalogue_file(tmp_path, "good.json", fx01_text, number=1)
    write_catalogue_file(tmp_path, "bad.json", broken_text, number=2)

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert isinstance(error_info.value.__cause__, GridImportError)


def test_ac5_catalogue_error_is_a_value_error() -> None:
    assert issubclass(CatalogueError, ValueError)


INVALID_OVERRIDES = [
    pytest.param({"force": 5}, id="force-5"),
    pytest.param({"force": 0}, id="force-0"),
    pytest.param({"force": "2"}, id="force-string"),
    pytest.param({"number": 0}, id="number-0"),
    pytest.param({"number": 1_000_000_000}, id="number-too-big"),
    pytest.param({"number": "1"}, id="number-string"),
    pytest.param({"published": "yes"}, id="published-string"),
    pytest.param({"published": 1}, id="published-int"),
    pytest.param({"published_on": "01/10/2026"}, id="date-format"),
    pytest.param({"colour": "red"}, id="extra-key"),
]


@pytest.mark.parametrize("overrides", INVALID_OVERRIDES)
def test_ac5_an_invalid_value_or_key_names_the_file(
    tmp_path: Path, fx01_text: str, overrides: dict[str, object]
) -> None:
    write_catalogue_file(tmp_path, "bad.json", fx01_text, **overrides)

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert error_info.value.__cause__ is not None


@pytest.mark.parametrize(
    "missing_key", ["number", "published_on", "force", "published"]
)
def test_ac5_a_missing_key_names_the_file(
    tmp_path: Path, fx01_text: str, missing_key: str
) -> None:
    path = write_catalogue_file(tmp_path, "bad.json", fx01_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload[missing_key]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json"):
        load_catalogue(tmp_path)


def test_ac5_a_missing_grid_key_names_the_file(tmp_path: Path, fx01_text: str) -> None:
    path = write_catalogue_file(tmp_path, "bad.json", fx01_text)
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["grid"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json"):
        load_catalogue(tmp_path)


def test_ac5_text_that_is_not_json_names_the_file(tmp_path: Path) -> None:
    (tmp_path / "bad.json").write_text("this is not json", encoding="utf-8")

    with pytest.raises(CatalogueError, match=r"bad\.json") as error_info:
        load_catalogue(tmp_path)

    assert error_info.value.__cause__ is not None


def test_ac5_two_files_with_the_same_number_name_the_second_file(
    tmp_path: Path, fx01_text: str
) -> None:
    write_catalogue_file(tmp_path, "a.json", fx01_text, number=3)
    write_catalogue_file(tmp_path, "b.json", fx01_text, number=3)

    with pytest.raises(CatalogueError, match=r"b\.json"):
        load_catalogue(tmp_path)


def test_ac5_duplicate_numbers_are_rejected_by_the_model(
    catalogue: Catalogue,
) -> None:
    first = catalogue.entries[0]
    copy = first.model_copy()

    with pytest.raises(ValidationError, match="duplicate") as error_info:
        Catalogue(entries=(first, copy))

    assert "1" in str(error_info.value)


def test_ac5_duplicate_number_message_holds_the_number(fx01_grid: Grid) -> None:
    first = make_entry(fx01_grid, 424242, date(2026, 10, 1), 1, True)
    second = make_entry(fx01_grid, 424242, date(2026, 10, 2), 2, False)

    with pytest.raises(ValidationError, match=r"duplicate.*424242|424242.*duplicate"):
        Catalogue(entries=(first, second))


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

    def record_request(request: object) -> None:
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
