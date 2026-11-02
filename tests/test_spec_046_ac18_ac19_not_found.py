"""Tests of spec 046, AC-18 and AC-19: a room that does not exist or has expired,
and the page not found.

AC-18 (browser with live server): on `/r/ZZZZZZ` with an empty registry, the
status card says the room does not exist, why a room may be gone, and leads to
the grids with a primary « Voir les grilles ». AC-19 (browser with live server,
routed path): `GET /nowhere` is answered with `web/dist/index.html` through
`page.route` (the server never serves the app on an unknown path, spec 040), and
the page not found is the entry frame with one card and the same way back, also
with the keyboard only.

Choices where the spec leaves room:

- "`entry-card` holds in order": its element children that show are
  `room-status`, `entry-detail`, `entry-home`, in that order.
- The page not found's card is `page-column`'s only element child; its children
  are the `h1`, then `entry-home`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from spec024_harness import outline_problems
from spec035_harness import Walker
from spec043_harness import MUTED, fr_value
from spec046_harness import (
    SIZES,
    WAIT_TIMEOUT_MS,
    OpenWindow,
    card_problems,
    card_title_problems,
    child_ids,
    child_tags,
    entry_frame_problems,
    entry_home_problems,
    font_problems,
    open_nowhere,
    open_unknown_room,
    size_ids,
    window_opener,
)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def expect_catalogue_at_root(page: Page, base_url: str) -> None:
    page.wait_for_url(f"{base_url}/", timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("catalogue-page")).to_be_visible(timeout=WAIT_TIMEOUT_MS)


# ---- AC-18: a room that does not exist or has expired ----------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac18_the_card_holds_the_status_the_reason_and_the_way_back_in_order(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    ids = child_ids(page.get_by_test_id("entry-card"))

    assert ids == ["room-status", "entry-detail", "entry-home"], ids


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac18_the_status_is_the_cards_title(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)
    room_status = page.get_by_test_id("entry-card").get_by_test_id("room-status")

    expect(room_status).to_have_text(fr_value("room.status.not_found"))
    assert card_title_problems(room_status) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac18_the_detail_says_why_a_room_may_be_gone_in_muted_13_6_px(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)
    detail = page.get_by_test_id("entry-detail")

    expect(detail).to_have_text(fr_value("room.status.not_found_detail"))
    assert font_problems(detail, "entry-detail", 13.6, colour=MUTED) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac18_voir_les_grilles_is_primary_the_only_way_on(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    assert entry_home_problems(page, "primary") == []


def test_ac18_a_click_on_voir_les_grilles_loads_the_catalogue(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    open_unknown_room(page, live_server)

    page.get_by_test_id("entry-home").click()

    expect_catalogue_at_root(page, live_server)


# ---- AC-19: the page not found ----------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_the_page_not_found_has_the_entry_frame(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_nowhere(page, live_server)

    ids = child_ids(page.get_by_test_id("not-found-page"))

    assert ids == ["page-topbar", "page-body"], ids
    assert entry_frame_problems(page) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_the_column_holds_only_the_card_with_no_room_code_line(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_nowhere(page, live_server)
    column = page.get_by_test_id("page-column")
    card = column.locator(":scope > *").first

    tags = child_tags(column)

    assert len(tags) == 1, tags
    assert tags != ["H1"], tags
    assert card_problems(card) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_the_card_holds_the_heading_then_voir_les_grilles_primary(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_nowhere(page, live_server)
    card = page.get_by_test_id("page-column").locator(":scope > *").first
    heading = card.locator(":scope > h1")

    tags = child_tags(card)
    ids = child_ids(card)

    assert tags[0] == "H1", tags
    assert ids[1:] == ["entry-home"], ids
    expect(heading).to_have_text(fr_value("not_found.heading"))
    assert card_title_problems(heading) == []
    assert entry_home_problems(page, "primary") == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_keyboard_only_tab_reaches_voir_les_grilles_and_enter_loads_the_grids(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_nowhere(page, live_server)
    walker = Walker(page)

    walker.tab_to("entry-home")
    reached = walker.reached[0]
    problems = outline_problems(
        reached.outline_style, reached.outline_width, reached.outline_contrast
    )
    page.keyboard.press("Enter")

    assert problems == []
    expect_catalogue_at_root(page, live_server)
