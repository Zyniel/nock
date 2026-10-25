"""Tests of spec 046, AC-1 and AC-2: the frames of the entry pages and of the
catalogue.

AC-1: on `/r/ZZZZZZ` (an empty registry, so `not_found`), the entry frame: a white
brand bar across the top (56 px on a wide window, 54 px on a narrow one), the page
grey under it down to the window's bottom, and one centred column, 420 px wide at
most, 48 px or 20 px under the bar, whose first child is the room code line and
whose second child is the card. AC-2: on `/` with `CAT`, the catalogue's 56 px bar
and its 920 px column on white, with the heading, the filter row and the list
16 px apart.

Choices where the spec leaves room:

- "The brand 16 px from its left edge" is read on the boxes: the left of
  `topbar-brand`'s Nock mark less `page-topbar`'s left (the brand link's box is
  larger than its content, `foundation.md`, « Brand link »).
- The brand is the link « Accueil » to `/` (B-010, `client/shell.md` AC-10): an
  `A` with `href="/"`, role link and name `topbar.home`, its Nock mark hidden from
  assistive technology; on the entry page it has no `aria-current`.
- "The brand alone in it while accounts are off" (AC-2): the live server has
  accounts off (`GET /api/account` answers 404), `page-topbar` holds one
  `topbar-brand`, the plain text « Nock » of `client/shell.md` rule 17 (B-011),
  and no `button`, `a`, `input`, `select` or `textarea` at all.
- "`catalogue-page` holds `page-topbar` then `catalogue-column`" and "its children
  are, in order" read the element children that show (a box).
- Edge case "Wide or narrow": a resize from 1280 by 720 to 360 by 740 gives the
  entry page the narrow bar within 300 ms, and the way back the wide one.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec042_harness import box_of
from spec043_harness import NAVY, WHITE, expect_brand_link, fr_value, label_of, px
from spec046_harness import (
    NARROW_BAR_HEIGHT,
    NARROW_SIZES,
    NOCK_MARK_POINTS,
    SIZES,
    WIDE,
    WIDE_BAR_HEIGHT,
    WIDE_BAR_INSET,
    WIDE_SIZES,
    OpenWindow,
    card_problems,
    child_ids,
    child_tags,
    children_of,
    code_line_problems,
    colour_matches,
    colour_problem,
    entry_frame_problems,
    font_problems,
    open_catalogue,
    open_unknown_room,
    padding_matches,
    page_topbar_problems,
    same_font,
    same_position,
    same_size,
    settled,
    size_ids,
    svg_of,
    to_box,
    window_opener,
)

ENTRY_SIZES = [*WIDE_SIZES, *NARROW_SIZES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004, served by the live server."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- AC-1: the entry frame -------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), ENTRY_SIZES, ids=size_ids(ENTRY_SIZES))
def test_ac1_the_entry_page_has_the_bar_the_grey_body_and_the_centred_column(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    assert entry_frame_problems(page) == []


@pytest.mark.parametrize(("width", "height"), NARROW_SIZES, ids=size_ids(NARROW_SIZES))
def test_ac1_a_narrow_window_has_the_54_px_bar_and_a_column_of_width_less_32(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    bar = box_of(page.get_by_test_id("page-topbar"))
    column = box_of(page.get_by_test_id("page-column"))

    assert same_size(bar.height, NARROW_BAR_HEIGHT), bar
    assert same_size(column.width, min(420.0, width - 32.0)), column


def test_ac1_the_column_is_328_px_wide_at_360(
    window: OpenWindow, live_server: str
) -> None:
    page = window(360, 740)
    open_unknown_room(page, live_server)

    column = box_of(page.get_by_test_id("page-column"))

    assert same_size(column.width, 328.0), column


@pytest.mark.parametrize(("width", "height"), ENTRY_SIZES, ids=size_ids(ENTRY_SIZES))
def test_ac1_the_brand_holds_the_navy_nock_mark_and_the_app_title(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)
    brand = page.get_by_test_id("page-topbar").get_by_test_id("topbar-brand")
    expect(brand.locator("svg")).to_have_count(1)

    mark = svg_of(brand.locator("svg"))
    mark_box = to_box(mark["box"])
    label = label_of(brand)

    assert same_size(mark_box.width, 12.0), mark_box
    assert same_size(mark_box.height, 18.0), mark_box
    assert len(mark["shapes"]) == 1, mark
    polygon = mark["shapes"][0]
    assert polygon["tag"] == "polygon", polygon
    assert " ".join(str(polygon["attributes"].get("points")).split()) == (
        NOCK_MARK_POINTS
    )
    assert polygon["fillColour"] is not None, polygon
    assert colour_matches(polygon["fillColour"], NAVY), polygon
    assert label is not None
    assert label["text"] == fr_value("app.title")
    assert label["fontWeight"] == "700"
    assert same_font(px(str(label["fontSize"])), 20.8), label


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac1_the_brand_is_the_link_accueil_to_home_with_no_aria_current(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    brand = page.get_by_test_id("page-topbar").get_by_test_id("topbar-brand")

    expect_brand_link(brand)


@pytest.mark.parametrize(("width", "height"), ENTRY_SIZES, ids=size_ids(ENTRY_SIZES))
def test_ac1_the_column_holds_the_room_code_line_then_the_card(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    assert code_line_problems(page, "ZZZZZZ") == []


@pytest.mark.parametrize(("width", "height"), ENTRY_SIZES, ids=size_ids(ENTRY_SIZES))
def test_ac1_the_second_child_of_the_column_is_the_card(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)
    column = page.get_by_test_id("page-column")

    children = children_of(column)
    card = column.locator(":scope > *").nth(1)

    assert len(children) >= 2, children
    assert card_problems(card) == []


@pytest.mark.parametrize(("width", "height"), ENTRY_SIZES, ids=size_ids(ENTRY_SIZES))
def test_ac1_the_entry_page_has_no_room_topbar(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_unknown_room(page, live_server)

    expect(page.get_by_test_id("room-topbar")).to_have_count(0)


def test_ac1_a_resize_gives_the_entry_page_the_other_bar_within_300_ms(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_unknown_room(page, live_server)
    bar = page.get_by_test_id("page-topbar")

    def bar_height() -> float:
        return box_of(bar).height

    page.set_viewport_size({"width": 360, "height": 740})
    narrow = settled(page, bar_height, lambda h: same_size(h, NARROW_BAR_HEIGHT))
    page.set_viewport_size({"width": 1280, "height": 720})
    wide = settled(page, bar_height, lambda h: same_size(h, WIDE_BAR_HEIGHT))

    assert same_size(narrow, NARROW_BAR_HEIGHT), narrow
    assert same_size(wide, WIDE_BAR_HEIGHT), wide


# ---- AC-2: the catalogue frame ---------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac2_the_catalogue_has_the_56_px_bar_on_every_window(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)

    assert page_topbar_problems(page, WIDE_BAR_HEIGHT, WIDE_BAR_INSET) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac2_with_accounts_off_the_bar_holds_no_other_control(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    bar = page.get_by_test_id("page-topbar")
    brand = bar.get_by_test_id("topbar-brand")
    expect(brand).to_have_count(1)

    controls = bar.locator("button, a, input, select, textarea")

    expect(controls).to_have_count(0)
    expect(brand).to_have_text(fr_value("app.title"))
    expect(page.get_by_test_id("account-open")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac2_the_catalogue_page_is_white_and_holds_the_bar_then_the_column(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    catalogue_page = page.get_by_test_id("catalogue-page")

    ids = child_ids(catalogue_page)

    assert ids == ["page-topbar", "catalogue-column"], ids
    assert colour_problem(catalogue_page, "page", "backgroundColor", WHITE) == []


def test_ac2_on_a_computer_the_column_is_920_px_wide_centred_with_24_px_padding(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    column = page.get_by_test_id("catalogue-column")

    box = box_of(column)

    assert same_size(box.width, 920.0), box
    assert same_position(box.left, 180.0), box
    assert padding_matches(column, "24px")


def test_ac2_on_a_phone_the_column_is_the_window_wide_with_16_px_padding(
    window: OpenWindow, live_server: str
) -> None:
    page = window(360, 740)
    open_catalogue(page, live_server)
    column = page.get_by_test_id("catalogue-column")

    box = box_of(column)

    assert same_size(box.width, 360.0), box
    assert padding_matches(column, "16px")


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac2_the_column_holds_the_heading_the_filters_and_the_list_16_px_apart(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    column = page.get_by_test_id("catalogue-column")

    children = children_of(column)
    tags = child_tags(column)
    ids = child_ids(column)

    assert tags[0] == "H1", tags
    assert ids[1:] == ["catalogue-filters", "catalogue-list"], ids
    for before, after in pairwise(children):
        gap = to_box(after["box"]).top - to_box(before["box"]).bottom
        assert same_position(gap, 16.0), (before, after)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac2_the_heading_reads_grilles_in_navy_700_at_27_2_px(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    heading = page.get_by_test_id("catalogue-column").locator(":scope > h1")

    expect(heading).to_have_text(fr_value("catalogue.heading"))
    assert font_problems(heading, "h1", 27.2, "700", NAVY) == []
