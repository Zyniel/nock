"""Tests of spec 046, AC-9 and AC-10: the catalogue's states, and a failed
« Jouer ».

AC-9 (browser with mocked routes): with `GET /api/grids` delayed, answered 500 or
answered `[]`, `catalogue-status` is one line where the cards will be, muted while
waiting or empty and the error line when the request failed, with no filter row;
with `CAT` (live) and the force 4 chip pressed, the filter row stays and the line
reads `catalogue.empty_filtered`. No state has a `role="progressbar"` element or
an animation. AC-10 (browser with live server): with `POST /api/rooms` answering
500, a click on the « Jouer » of grid 2 puts the error line inside its card,
under its force line.

Choices where the spec leaves room:

- "Muted" is the state line of "States": 400 1rem/1.5 (16 px, a 24 px line
  height), `--nock-muted`.
- "Followed by `catalogue-status`": the element child of `catalogue-column` right
  after `catalogue-filters` is `catalogue-status`.
- The card's force line is the parent of its `catalogue-force-marks`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec042_harness import box_of
from spec043_harness import fr_value
from spec046_harness import (
    GRIDS_ROUTE,
    SIZES,
    HeldRoute,
    OpenWindow,
    answer_json,
    child_ids,
    error_line_problems,
    fail_play,
    inside,
    item_of,
    muted_line_problems,
    no_progress_or_animation,
    open_catalogue,
    open_catalogue_loading,
    same_position,
    size_ids,
    window_opener,
)

STATES = ["loading", "error", "empty", "filtered"]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_in_state(page: Page, base_url: str, state: str) -> None:
    """Open `/` in one of AC-9's states and wait until the page shows it."""
    catalogue_page = page.get_by_test_id("catalogue-page")
    if state == "loading":
        HeldRoute(page, GRIDS_ROUTE)
        open_catalogue_loading(page, base_url)
        expect(catalogue_page).to_have_attribute("data-state", "loading")
    elif state == "error":
        answer_json(page, GRIDS_ROUTE, 500, {"detail": "Internal Server Error"})
        open_catalogue_loading(page, base_url)
        expect(catalogue_page).to_have_attribute("data-state", "error")
    elif state == "empty":
        answer_json(page, GRIDS_ROUTE, 200, [])
        open_catalogue(page, base_url)
    else:
        open_catalogue(page, base_url)
        filters = page.get_by_test_id("catalogue-filters")
        filters.locator('[data-force="4"]').click()
        expect(page.get_by_test_id("catalogue-status")).to_be_visible()
    wait_for_fonts(page)


# ---- AC-9: the states ------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac9_while_the_grids_load_one_muted_line_is_under_the_heading(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_in_state(page, live_server, "loading")
    status = page.get_by_test_id("catalogue-status")
    heading = page.get_by_test_id("catalogue-column").locator(":scope > h1")

    expect(status).to_have_text(fr_value("catalogue.loading"))
    gap = box_of(status).top - box_of(heading).bottom

    assert muted_line_problems(status) == []
    assert same_position(gap, 16.0), gap
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)
    expect(page.get_by_test_id("catalogue-list")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac9_a_failed_request_shows_the_error_line_and_no_filter_row(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_in_state(page, live_server, "error")
    status = page.get_by_test_id("catalogue-status")

    expect(status).to_have_text(fr_value("catalogue.error"))

    assert error_line_problems(status) == []
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac9_an_empty_catalogue_shows_its_muted_line_and_no_chip(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_in_state(page, live_server, "empty")
    status = page.get_by_test_id("catalogue-status")

    expect(status).to_have_text(fr_value("catalogue.empty"))

    assert muted_line_problems(status) == []
    expect(page.get_by_test_id("force-filter")).to_have_count(0)
    expect(page.get_by_test_id("catalogue-filters")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac9_no_grid_of_the_chosen_force_keeps_the_chips_and_shows_a_muted_line(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_in_state(page, live_server, "filtered")
    status = page.get_by_test_id("catalogue-status")

    expect(status).to_have_text(fr_value("catalogue.empty_filtered"))
    ids = child_ids(page.get_by_test_id("catalogue-column"))

    assert "catalogue-filters" in ids, ids
    assert ids[ids.index("catalogue-filters") + 1] == "catalogue-status", ids
    assert muted_line_problems(status) == []
    expect(page.get_by_test_id("catalogue-list")).to_have_count(0)


def test_ac9_with_grids_shown_there_is_no_status_line(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    open_catalogue(page, live_server)

    expect(page.get_by_test_id("catalogue-list")).to_be_visible()
    expect(page.get_by_test_id("catalogue-status")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
@pytest.mark.parametrize("state", STATES)
def test_ac9_no_state_has_a_progress_bar_or_an_animation(
    window: OpenWindow, live_server: str, width: int, height: int, state: str
) -> None:
    page = window(width, height)
    open_in_state(page, live_server, state)

    assert no_progress_or_animation(page) == []


# ---- AC-10: a failed « Jouer » ---------------------------------------------------


def fail_the_play_of_grid_2(page: Page, base_url: str) -> None:
    fail_play(page)
    open_catalogue(page, base_url)
    item_of(page, 2).get_by_test_id("catalogue-play").click()
    expect(item_of(page, 2).get_by_test_id("catalogue-error")).to_be_visible()
    wait_for_fonts(page)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac10_the_error_line_is_inside_the_card_and_is_an_alert(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    fail_the_play_of_grid_2(page, live_server)
    error = item_of(page, 2).get_by_test_id("catalogue-error")

    expect(error).to_have_text(fr_value("catalogue.play_failed"))
    expect(error).to_have_attribute("role", "alert")
    assert error_line_problems(error) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac10_the_error_line_is_under_the_force_line_on_the_left_of_the_number(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    fail_the_play_of_grid_2(page, live_server)
    card = item_of(page, 2)
    force_line = card.get_by_test_id("catalogue-force-marks").locator("xpath=..")

    error_box = box_of(card.get_by_test_id("catalogue-error"))
    line_box = box_of(force_line)
    heading_box = box_of(card.locator("h2"))

    assert error_box.top >= line_box.bottom - 1.0, (error_box, line_box)
    assert same_position(error_box.left, heading_box.left), (error_box, heading_box)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac10_the_card_stays_in_the_list_and_jouer_is_enabled_again(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    fail_the_play_of_grid_2(page, live_server)
    card = item_of(page, 2)

    assert inside(box_of(card), box_of(page.get_by_test_id("catalogue-list")))
    expect(card.get_by_test_id("catalogue-play")).to_be_enabled()
    expect(page.get_by_test_id("catalogue-error")).to_have_count(1)
    expect(item_of(page, 1).get_by_test_id("catalogue-error")).to_have_count(0)
    expect(item_of(page, 3).get_by_test_id("catalogue-error")).to_have_count(0)
