"""Tests of `content/library.md`, AC-19 and AC-20: the brand of the catalogue.

Browser with live server, serving `CAT`. AC-19: on `/`, at 1280 by 720 and 360 by
740, `page-topbar`'s `topbar-brand` is the link « Accueil » to `/` of
`client/shell.md` rule 17 with `aria-current="page"`; a click on it loads the
page `/` again, which asks `GET /api/grids` a second time and shows the
catalogue `ready`. AC-20: at 1280 by 720, the hovered brand has the word-blue
background of « Brand link » (`_design/foundation.md`, « Components ») in its
6 px rounded, 8 px by 10 px padded box, with no underline, and its Nock mark and
« Nock » keep the boxes they had at rest.

Choices where the spec leaves room:

- "The link « Accueil » to `/`": spec 043's `expect_brand_link`, an `A` with
  `href="/"`, role link, name `topbar.home`, one Nock mark hidden from assistive
  technology and the text `app.title`.
- "Loads the catalogue again": after the click the page made a navigation request
  for `/` (shell rule 17: "loads the page `/`, as any link does"), two
  `GET /api/grids` in all, and `catalogue-page` is `ready` again.
- "At rest" is read with the pointer at (1, 700), on the page under the bar.
  "Where they are at rest": the Nock mark's box and the box of the text « Nock »
  (spec 043's `label_of`) within 1 px of each edge.
- The hovered background is read until it is word blue, up to 300 ms, so a short
  transition of the colour does not fail the check.
"""

from __future__ import annotations

from collections.abc import Iterator
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Browser, Locator, Page, Request, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec042_harness import Box, box_of, colour_of, to_box, wait_until
from spec043_harness import (
    WORD,
    colour_matches,
    expect_brand_link,
    is_clear,
    label_of,
    padding_matches,
    padding_of,
    same_box,
    style_of,
)
from spec046_harness import (
    SIZES,
    WAIT_TIMEOUT_MS,
    WIDE,
    OpenWindow,
    open_catalogue,
    settled,
    size_ids,
    window_opener,
)

REST_POINT = (1.0, 700.0)  # on the page, under the bar


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


def catalogue_brand(page: Page) -> Locator:
    return page.get_by_test_id("page-topbar").get_by_test_id("topbar-brand")


class PageRequests:
    """The `GET /api/grids` requests and the navigation requests of a page."""

    def __init__(self, page: Page) -> None:
        self.grid_lists = 0
        self.navigations: list[str] = []
        page.on("request", self.record)

    def record(self, request: Request) -> None:
        path = urlsplit(request.url).path
        if request.method == "GET" and path == "/api/grids":
            self.grid_lists += 1
        if request.is_navigation_request():
            self.navigations.append(path)


def content_boxes(brand: Locator) -> tuple[Box, Box]:
    """The boxes of the brand's Nock mark and of its text « Nock »."""
    mark_box = box_of(brand.locator("svg"))
    label = label_of(brand)
    assert label is not None, "topbar-brand has no text"
    return mark_box, to_box(label["box"])


# ---- AC-19: the link to `/`, current on `/` ----------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_on_home_the_brand_is_the_link_accueil_with_aria_current_page(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)

    expect_brand_link(catalogue_brand(page), current=True)


def test_ac19_following_the_brand_loads_the_catalogue_again(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    requests = PageRequests(page)
    open_catalogue(page, live_server)
    assert requests.grid_lists == 1
    first_navigations = len(requests.navigations)

    catalogue_brand(page).click()

    wait_until(page, lambda: requests.grid_lists >= 2, "a second GET /api/grids")
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    assert requests.grid_lists == 2
    assert requests.navigations[first_navigations:] == ["/"]
    assert page.url == f"{live_server}/"


# ---- AC-20: the hovered brand ------------------------------------------------------


def test_ac20_the_hovered_brand_takes_the_brand_link_hover_look_in_place(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    brand = catalogue_brand(page)
    page.mouse.move(*REST_POINT)
    rest_background = colour_of(brand, "backgroundColor")
    rest_mark, rest_text = content_boxes(brand)

    brand.hover()
    background = settled(
        page,
        lambda: colour_of(brand, "backgroundColor"),
        lambda colour: colour_matches(colour, WORD),
    )
    hover_mark, hover_text = content_boxes(brand)

    assert is_clear(rest_background), rest_background
    assert colour_matches(background, WORD), background
    assert style_of(brand, "borderTopLeftRadius") == "6px"
    assert padding_matches(brand, "8px 10px"), padding_of(brand)
    assert style_of(brand, "textDecorationLine") == "none"
    assert same_box(hover_mark, rest_mark), (hover_mark, rest_mark)
    assert same_box(hover_text, rest_text), (hover_text, rest_text)
