"""Shared setup of the tests of spec 004: the grid catalogue.

This module is not a test file: pytest does not collect it. The tests of spec 004
are in `tests/test_spec_004_*.py`, one file per criterion group.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `catalogue`,
`dist_dir` and `client` are defined in each file that needs them, as thin wrappers
around `grid_from_text`, `make_reference_catalogue`, `make_dist_dir` and
`make_client`: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue, CatalogueEntry, GridSummary
from nock.grid import Grid
from nock.server import create_app

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


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def make_entry(
    grid: Grid, number: int, published_on: date, force: int, published: bool
) -> CatalogueEntry:
    return CatalogueEntry(
        number=number,
        published_on=published_on,
        force=force,
        published=published,
        **credits(),
        grid=grid,
    )


def grid_from_text(text: str) -> Grid:
    """Return the grid that the JSON `text` holds (the body of `fx01_grid`)."""
    return Grid.model_validate_json(text)


def make_reference_catalogue(grid: Grid) -> Catalogue:
    """Return the reference catalogue CAT of the spec, built on `grid`."""
    entries = (
        make_entry(grid, 1, date(2026, 9, 1), 1, True),
        make_entry(grid, 2, date(2026, 10, 1), 2, True),
        make_entry(grid, 3, date(2026, 10, 1), 1, True),
        make_entry(grid, 4, date(2026, 10, 5), 3, False),
    )
    return Catalogue(entries=entries)


def make_dist_dir(tmp_path: Path) -> Path:
    """Create a `dist` directory with a minimal `index.html` and return it."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def make_client(catalogue: Catalogue, dist_dir: Path) -> TestClient:
    """Return a test client of the app serving `catalogue` and `dist_dir`."""
    return TestClient(create_app(catalogue=catalogue, dist_dir=dist_dir))


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
        **credits(),
        "grid": json.loads(grid_text),
    }
    for key, value in overrides.items():
        payload[key] = value
    path = directory / name
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def item_by_number(page: Page, number: int) -> Locator:
    return page.locator(f'[data-testid="catalogue-item"][data-number="{number}"]')


def expect_item_numbers(page: Page, numbers: list[int]) -> None:
    """Expect the shown catalogue items to be exactly `numbers`, in order."""
    items = page.get_by_test_id("catalogue-item")
    expect(items).to_have_count(len(numbers))
    for index, number in enumerate(numbers):
        expect(items.nth(index)).to_have_attribute("data-number", str(number))


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
