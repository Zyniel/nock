"""Tests of `content/library.md`, AC-19 to AC-21: the brand of both pages.

Browser with live server, serving `CAT`. AC-19: on `/`, at 1280 by 720 and 360 by
740, `page-topbar`'s `topbar-brand` is the plain text « Nock » of
`client/shell.md` rule 17: the bar holds no link, the page no `aria-current`;
Tab, from the top of the page, first stops on « Toutes » and never on the brand
up to the last « Jouer »; and at 1280 by 720 the hovered brand keeps the look it
has at rest. AC-20: on `/g/2` at 1280 by 720, the hovered brand has the word-blue
background of « Brand link » (`_design/foundation.md`, « Components ») in its
6 px rounded, 8 px by 10 px padded box, with no underline, and its Nock mark and
« Nock » keep the boxes they had at rest. AC-21: on `/g/2`, at both sizes, the
brand is the link « Accueil » to `/` with no `aria-current`; a click on it loads
the page `/`, which asks `GET /api/grids` and shows the catalogue `ready`.

Choices where the spec leaves room:

- "Plain text read « Nock »": spec 043's `expect_plain_brand`: `topbar-brand` is
  no `A` with an `href`, is inside none and holds none, has no role link, no
  `aria-current` and no `aria-label`; it holds one Nock mark hidden from
  assistive technology, and its text, and the part of it not hidden from
  assistive technology, is `app.title`.
- "The top bar holds no link": `page-topbar` holds no element of role link.
- "Tab never stops on the brand": Tab is pressed from the freshly loaded page
  until the focus reaches card 1's « Jouer », the last control of `/` with CAT
  and accounts off (20 presses at most); no focused element is or is inside
  `topbar-brand`, and the first is a `force-filter`, so the walk began before
  the bar.
- "Keeps its look at rest": the brand's computed background, text colour, text
  decoration, shadow and cursor, its Nock mark's fill, and the boxes of its mark
  and of the text « Nock » (spec 043's `label_of`, within 1 px of each edge),
  read while hovered until they differ from rest, up to 300 ms, so a transition
  of the hover look fails the check too.
- "The link « Accueil » to `/`": spec 043's `expect_brand_link`, an `A` with
  `href="/"` and no `aria-current`, role link, name `topbar.home`, one Nock mark
  hidden from assistive technology and the text `app.title`.
- "Loads the catalogue": after the click the page made one navigation request,
  for `/` (shell rule 17: "loads the page `/`, as any link does"), one
  `GET /api/grids` in all (`/g/2` asks none, rule 16), and `catalogue-page` is
  `ready`.
- "At rest" is read with the pointer at (1, 700), on the page under the bar.
- The hovered background of AC-20 is read until it is word blue, up to 300 ms,
  so a short transition of the colour does not fail the check.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import NamedTuple
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
    expect_plain_brand,
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
    open_grid_page,
    settled,
    size_ids,
    window_opener,
)

REST_POINT = (1.0, 700.0)  # on the page, under the bar
MAX_TABS = 20  # CAT with accounts off has 8 Tab stops: 5 chips, 3 « Jouer »

# Card 1 comes last in CAT's order (3, 2, 1), so its « Jouer » is the last stop.
LAST_PLAY = (
    '[data-testid="catalogue-item"][data-number="1"] [data-testid="catalogue-play"]'
)

# The brand's computed styles that make its look, besides its boxes.
LOOK_PROPERTIES = (
    "backgroundColor",
    "color",
    "textDecorationLine",
    "boxShadow",
    "cursor",
)

# The focused element: its test id, whether it is or is inside `topbar-brand`,
# and whether it is card 1's « Jouer ».
FOCUS_SCRIPT = r"""
lastPlay => {
  const element = document.activeElement;
  if (element === null || element === document.body) {
    return {testId: null, inBrand: false, isLast: false};
  }
  return {
    testId: element.getAttribute('data-testid'),
    inBrand: element.closest('[data-testid="topbar-brand"]') !== null,
    isLast: element.matches(lastPlay),
  };
}
"""


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


def bar_brand(page: Page) -> Locator:
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


class FocusStop(NamedTuple):
    """One element the focus reached with Tab."""

    test_id: str | None
    in_brand: bool
    is_last: bool


def tab_stops_to_the_last_play(page: Page) -> list[FocusStop]:
    """Press Tab until card 1's « Jouer » has the focus; return every stop."""
    stops: list[FocusStop] = []
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        found = page.evaluate(FOCUS_SCRIPT, LAST_PLAY)
        assert isinstance(found, dict), found
        stop = FocusStop(
            test_id=found["testId"],
            in_brand=found["inBrand"],
            is_last=found["isLast"],
        )
        stops.append(stop)
        if stop.is_last:
            return stops
    pytest.fail(f"card 1's catalogue-play not reached in {MAX_TABS} presses: {stops}")


def content_boxes(brand: Locator) -> tuple[Box, Box]:
    """The boxes of the brand's Nock mark and of its text « Nock »."""
    mark_box = box_of(brand.locator("svg"))
    label = label_of(brand)
    assert label is not None, "topbar-brand has no text"
    return mark_box, to_box(label["box"])


class BrandLook(NamedTuple):
    """What the brand looks like: its styles, its mark's fill and its boxes."""

    styles: tuple[str, ...]
    mark_fill: str
    mark_box: Box
    text_box: Box


def brand_look(brand: Locator) -> BrandLook:
    styles: list[str] = []
    for property_name in LOOK_PROPERTIES:
        styles.append(style_of(brand, property_name))
    mark_box, text_box = content_boxes(brand)
    mark_fill = style_of(brand.locator("svg polygon"), "fill")
    return BrandLook(tuple(styles), mark_fill, mark_box, text_box)


def same_look(first: BrandLook, second: BrandLook) -> bool:
    """The same styles and fill, and boxes within 1 px on each edge."""
    return (
        first.styles == second.styles
        and first.mark_fill == second.mark_fill
        and same_box(first.mark_box, second.mark_box)
        and same_box(first.text_box, second.text_box)
    )


# ---- AC-19: on `/` the brand is plain text ------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_on_home_the_brand_is_plain_text_read_nock_with_no_link_or_current(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)
    bar = page.get_by_test_id("page-topbar")

    expect(bar.get_by_role("link")).to_have_count(0)
    expect_plain_brand(bar_brand(page))
    expect(page.locator("[aria-current]")).to_have_count(0)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac19_tab_never_stops_on_the_brand_of_home(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_catalogue(page, live_server)

    stops = tab_stops_to_the_last_play(page)

    in_brand = [stop for stop in stops if stop.in_brand]
    assert in_brand == [], stops
    assert stops[0].test_id == "force-filter", stops


def test_ac19_the_hovered_brand_of_home_keeps_its_look_at_rest(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_catalogue(page, live_server)
    brand = bar_brand(page)
    page.mouse.move(*REST_POINT)
    rest_look = brand_look(brand)

    brand.hover()
    hover_look = settled(
        page,
        lambda: brand_look(brand),
        lambda look: not same_look(look, rest_look),
    )

    assert same_look(hover_look, rest_look), (hover_look, rest_look)


# ---- AC-20: the hovered brand of the grid page ------------------------------------


def test_ac20_the_hovered_brand_takes_the_brand_link_hover_look_in_place(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    open_grid_page(page, live_server)
    brand = bar_brand(page)
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


# ---- AC-21: the grid page's brand links home --------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac21_on_the_grid_page_the_brand_is_the_link_accueil_with_no_aria_current(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = window(width, height)
    open_grid_page(page, live_server)

    expect_brand_link(bar_brand(page))


def test_ac21_following_the_grid_pages_brand_loads_the_catalogue(
    window: OpenWindow, live_server: str
) -> None:
    page = window(*WIDE)
    requests = PageRequests(page)
    open_grid_page(page, live_server)
    assert requests.grid_lists == 0
    first_navigations = len(requests.navigations)

    bar_brand(page).click()

    wait_until(page, lambda: requests.grid_lists >= 1, "a GET /api/grids")
    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    assert requests.grid_lists == 1
    assert requests.navigations[first_navigations:] == ["/"]
    assert page.url == f"{live_server}/"
