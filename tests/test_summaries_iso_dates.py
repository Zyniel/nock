"""Tests of lobby/summaries, AC-4: « Mes salons » reads ISO dates only.

Browser with the summaries route mocked: the live server serves the client in
Paris time, `page.route` answers `POST /api/rooms/summaries` with one summary
whose date is the string under test, and the identities of the answer's room are
seeded. A date the rule refuses makes the answer no list of summaries: the section
shows `my_rooms.error` and no row. The "every engine" part of the rule is covered
by the gate running these tests in each browser engine.

The shared setup is in `tests/spec032_harness.py`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from spec032_harness import (
    XYZ,
    XYZ_TOKEN,
    NewPage,
    SummariesRoute,
    expect_my_rooms_ready,
    identity_value,
    my_room_items,
    my_rooms,
    open_catalogue,
    paris_page_factory,
    seed_storage,
    summary_json,
)

ERROR_TEXT = "Impossible de charger vos salons."
SOLVED_AT = "2026-10-14T09:00:00Z"
REFUSED_DATES = [
    "2026-10-14 08:30:00Z",
    "2026-10-14T08:30:00",
    "2026-02-30T08:30:00Z",
]
ACCEPTED_DATES = [
    "2026-10-14T08:30:00.5Z",
    "2026-10-14T08:30:00.123456+00:00",
]


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_page_factory(browser)


def solved_summary(last_activity_at: str, finished_at: str) -> dict[str, object]:
    """XYZ789, solved, with the given dates (the result fields of a solved room)."""
    summary = summary_json(XYZ, 2, (5, 5), ["Ana"], last_activity_at, True)
    summary["finished_at"] = finished_at
    summary["elapsed_ms"] = 60_000
    return summary


def open_with_summary(
    page: Page, base_url: str, summary: dict[str, object]
) -> SummariesRoute:
    """Open the catalogue with an identity for XYZ789 and `summary` as the answer."""
    route = SummariesRoute(body=[summary])
    seed_storage(page, {f"nock.identity.{XYZ}": identity_value(XYZ_TOKEN)})
    open_catalogue(page, base_url, route)
    return route


@pytest.mark.parametrize("date", REFUSED_DATES)
def test_ac4_a_last_activity_that_is_no_iso_date_time_shows_the_error_and_no_row(
    new_page: NewPage, live_server: str, date: str
) -> None:
    page = new_page(1280, 720)
    summary = summary_json(XYZ, 2, (5, 5), ["Ana"], date, False)

    route = open_with_summary(page, live_server, summary)

    section = my_rooms(page)
    expect(section).to_have_attribute("data-state", "error")
    expect(section.get_by_test_id("my-rooms-error")).to_have_text(ERROR_TEXT)
    expect(my_room_items(page)).to_have_count(0)
    assert route.methods == ["POST"]


@pytest.mark.parametrize("date", REFUSED_DATES)
def test_ac4_a_finished_at_that_is_no_iso_date_time_shows_the_error_and_no_row(
    new_page: NewPage, live_server: str, date: str
) -> None:
    page = new_page(1280, 720)
    summary = solved_summary("2026-10-14T08:30:00Z", date)

    open_with_summary(page, live_server, summary)

    section = my_rooms(page)
    expect(section).to_have_attribute("data-state", "error")
    expect(section.get_by_test_id("my-rooms-error")).to_have_text(ERROR_TEXT)
    expect(my_room_items(page)).to_have_count(0)


@pytest.mark.parametrize("date", ACCEPTED_DATES)
def test_ac4_a_last_activity_with_a_fraction_and_a_zone_lists_the_row(
    new_page: NewPage, live_server: str, date: str
) -> None:
    page = new_page(1280, 720)
    summary = summary_json(XYZ, 2, (5, 5), ["Ana"], date, False)

    open_with_summary(page, live_server, summary)

    expect_my_rooms_ready(page, 1)
    expect(my_room_items(page)).to_have_attribute("data-code", XYZ)
    expect(my_rooms(page).get_by_test_id("my-rooms-error")).to_have_count(0)
    expect(my_room_items(page)).to_contain_text("14 octobre 2026 à 10:30")


@pytest.mark.parametrize("date", ACCEPTED_DATES)
def test_ac4_a_finished_at_with_a_fraction_and_a_zone_lists_the_row(
    new_page: NewPage, live_server: str, date: str
) -> None:
    page = new_page(1280, 720)
    summary = solved_summary(SOLVED_AT, date)

    open_with_summary(page, live_server, summary)

    expect_my_rooms_ready(page, 1)
    expect(my_room_items(page)).to_have_attribute("data-code", XYZ)
