"""Tests of `content/library.md` AC-25 and AC-26: a summary that is not a summary is
a failed answer (rule 2).

Browser with the live server serving `CAT`. The test lets the page's request reach
the server (`route.fetch`), puts `2026-02-30` (no such day) or `hier` in grid 2's
`published_on`, and gives the page that answer: `/` shows « Impossible de charger
les grilles. » in its `error` state, with no filter and no card; `/g/2`, given that
summary by `GET /api/grids/2`, shows the same line in its `error` state, no card.

AC-26: the page gets the server's list with one field of grid 2's item of the wrong
type (`number`, `force`, `width`, `height` or `word_count` as a string, `"2"` for
`number`; `published_on` as a number): `/` shows the same error, no filter, no card.

The same holds when grid 2's item lacks `word_count`, in the list for `/` and as
`GET /api/grids/2`'s answer for `/g/2` (`/g/2` does not ask the list), and when
`GET /api/grids/2` answers `[]` for `/g/2`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable

import pytest
from playwright.sync_api import Page, Route, expect

from spec004_harness import load_fr

LIST_ROUTE = re.compile(r".*/api/grids(\?.*)?$")
GRID_2_ROUTE = re.compile(r".*/api/grids/2$")
NOT_A_DATE = [
    pytest.param("2026-02-30", id="february-30"),
    pytest.param("hier", id="hier"),
]


CATALOGUE_KIND = "reference"


def with_grid_2_published_on(summary: dict[str, object], published_on: str) -> None:
    """Put `published_on` in a summary when it is grid 2's."""
    if summary["number"] == 2:
        summary["published_on"] = published_on


DELETE = object()  # marks a field to remove rather than set


def answer_list_changing(field: str, value: object) -> Callable[[Route], None]:
    """A route handler: the server's list, grid 2's `field` set to `value`.

    With `DELETE` as `value`, the field is removed from grid 2's item instead.
    """

    def answer(route: Route) -> None:
        summaries = route.fetch().json()
        assert isinstance(summaries, list), summaries
        changed = 0
        for summary in summaries:
            if summary["number"] == 2:
                if value is DELETE:
                    del summary[field]
                else:
                    summary[field] = value
                changed += 1
        assert changed == 1, summaries
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
    page.route(LIST_ROUTE, answer_list_changing("published_on", published_on))

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


def answer_grid_2_without_word_count(route: Route) -> None:
    """A route handler: the server's summary of grid 2, without `word_count`."""
    summary = route.fetch().json()
    assert isinstance(summary, dict), summary
    del summary["word_count"]
    route.fulfill(status=200, content_type="application/json", body=json.dumps(summary))


def test_ac25_a_list_with_an_item_without_word_count_is_an_error(
    page: Page, live_server: str
) -> None:
    page.route(LIST_ROUTE, answer_list_changing("word_count", DELETE))

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "error")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.error"])
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)
    expect(page.get_by_test_id("catalogue-item")).to_have_count(0)


def test_ac25_a_grid_page_given_a_summary_without_word_count_shows_the_error(
    page: Page, live_server: str
) -> None:
    page.route(GRID_2_ROUTE, answer_grid_2_without_word_count)

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "error")
    expect(grid_page).to_contain_text(load_fr()["catalogue.error"])
    expect(grid_page.get_by_test_id("catalogue-item")).to_have_count(0)


def test_ac25_a_grid_page_given_an_empty_list_shows_the_error(
    page: Page, live_server: str
) -> None:
    page.route(
        GRID_2_ROUTE,
        lambda route: route.fulfill(
            status=200, content_type="application/json", body="[]"
        ),
    )

    page.goto(f"{live_server}/g/2")

    grid_page = page.get_by_test_id("grid-page")
    expect(grid_page).to_have_attribute("data-state", "error")
    expect(grid_page).to_contain_text(load_fr()["catalogue.error"])
    expect(grid_page.get_by_test_id("catalogue-item")).to_have_count(0)


# AC-26: one field of grid 2's item of the wrong type, in turn.
WRONG_TYPE_FIELDS: list[tuple[str, object]] = [
    ("number", "2"),
    ("force", "2"),
    ("width", "5"),
    ("height", "5"),
    ("word_count", "8"),
    ("published_on", 20261001),
]


@pytest.mark.parametrize(
    ("field", "value"), WRONG_TYPE_FIELDS, ids=[name for name, _ in WRONG_TYPE_FIELDS]
)
def test_ac26_a_list_with_a_field_of_the_wrong_type_is_an_error(
    page: Page, live_server: str, field: str, value: object
) -> None:
    page.route(LIST_ROUTE, answer_list_changing(field, value))

    page.goto(f"{live_server}/")

    catalogue_page = page.get_by_test_id("catalogue-page")
    expect(catalogue_page).to_have_attribute("data-state", "error")
    expect(catalogue_page).to_contain_text(load_fr()["catalogue.error"])
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)
    expect(page.get_by_test_id("catalogue-item")).to_have_count(0)
