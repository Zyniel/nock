"""Tests of `client/shell.md` AC-30: every page has one banner, the top bar, followed
by one `main` holding the page's heading (rule 19).

AC-30: on `/`, `/g/1`, `/r/ABC123` showing the nickname form, `/xyz`, a shared recap,
`/account` and `/ops` locked, the page has one banner, the top bar, followed by one
`main` holding the page's heading, and no banner inside `main`.

Browser tests on the live server serving the reference catalogue, at 1280 by 720 and
360 by 740, with the pages opened as the other tests of the client open them
(`spec046_harness`, `spec048_harness`): `/` and `/g/1` from the server, the room's
nickname form on a mocked socket, `/nowhere` (for `/xyz`), `/ops` and `/account`
by answering their path with the built `index.html` (the live server has no page
route for `/nowhere`, no operator token and no accounts), and the shared recap on a
mocked route.

Readings where the spec leaves room:

- A banner is what Playwright's `get_by_role("banner")` finds: a `header` that is not
  inside a `main`, `section`, `article`, `aside` or `nav`, or an element with
  `role="banner"`. The `main` is `get_by_role("main")`. Exactly one of each.
- "The top bar" is the element with the test id `page-topbar`: the banner is that
  element, and it is not inside the `main`. Every page of the list takes the frame of
  `client/shell.md` rule 9, whose top bar is `page-topbar`.
- "Followed by": the `main` comes after the banner in the document.
- "Holding the page's heading": the `main` holds at least one heading (any level;
  the grid page's is the grid's card title), and no heading of the page lies outside
  it.
- "No banner inside `main`": the `main` holds no `header` and no `role="banner"`
  element.
- Rule 19's "everything under it is in the page's one `main`": no element that shows
  (a box larger than 1 px) and sits beside the banner, after it, lies outside the
  `main`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from shell_harness import open_locked_ops, route_client
from spec035_harness import build_fx01_grid, build_reference_catalogue
from spec046_harness import (
    SIZES,
    WAIT_TIMEOUT_MS,
    OpenWindow,
    open_catalogue,
    open_nickname_card,
    open_nowhere,
    size_ids,
    window_opener,
)
from spec048_harness import AccountMock, open_account, open_share

BANNER_TEST_ID = "page-topbar"

# What the page looks like around its landmarks: the test id of the banner, whether
# the banner is inside the main, whether the main follows it, how many headings the
# main holds and the page holds outside it, how many headers or banner roles the main
# holds, and the elements that show beside the banner after it, outside the main.
LANDMARKS_SCRIPT = r"""
([banner, main]) => {
  const headings = 'h1, h2, h3, h4, h5, h6, [role="heading"]';
  const shows = (element) => {
    const box = element.getBoundingClientRect();
    return box.width > 1 && box.height > 1;
  };
  const outside = [];
  let afterBanner = false;
  for (const sibling of banner.parentElement.children) {
    if (sibling === banner) {
      afterBanner = true;
    } else if (afterBanner && sibling !== main && shows(sibling)) {
      outside.push(sibling.tagName + ':' + (sibling.getAttribute('data-testid') || ''));
    }
  }
  const allHeadings = [...document.querySelectorAll(headings)];
  return {
    bannerTestId: banner.getAttribute('data-testid'),
    bannerInsideMain: main.contains(banner),
    mainFollowsBanner: Boolean(
      banner.compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING),
    headingsInMain: main.querySelectorAll(headings).length,
    headingsOutsideMain: allHeadings.filter((item) => !main.contains(item)).length,
    bannersInMain: main.querySelectorAll('header, [role="banner"]').length,
    shownOutsideMain: outside,
  };
}
"""

PAGES = [
    "catalogue",
    "grid",
    "nickname",
    "not_found",
    "recap",
    "account",
    "ops",
]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- Opening each page ---------------------------------------------------------------


def open_grid_1(page: Page, base_url: str) -> None:
    """Open `/g/1` and wait until the grid page is `ready`."""
    page.goto(f"{base_url}/g/1")
    expect(page.get_by_test_id("grid-page")).to_have_attribute(
        "data-state", "ready", timeout=WAIT_TIMEOUT_MS
    )
    wait_for_fonts(page)


def open_nickname(page: Page, base_url: str) -> None:
    """Open `/r/ABC123` on a mocked socket, on the nickname form."""
    open_nickname_card(page, base_url)


def open_signed_out_account(page: Page, base_url: str) -> None:
    """Open `/account` signed out: the path answered with the built client."""
    route_client(page, f"{base_url}/account")
    open_account(page, base_url, AccountMock(), "signed_out")


OPENERS: dict[str, Callable[[Page, str], None]] = {
    "catalogue": open_catalogue,
    "grid": open_grid_1,
    "nickname": open_nickname,
    "not_found": open_nowhere,
    "recap": open_share,
    "account": open_signed_out_account,
    "ops": open_locked_ops,
}


# ---- AC-30 -------------------------------------------------------------------------


@pytest.mark.parametrize("name", PAGES)
@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac30_the_page_has_one_banner_the_top_bar_then_one_main_with_its_heading(
    window: OpenWindow, live_server: str, name: str, width: int, height: int
) -> None:
    page = window(width, height)
    OPENERS[name](page, live_server)

    banners = page.get_by_role("banner")
    mains = page.get_by_role("main")

    expect(banners).to_have_count(1)
    expect(mains).to_have_count(1)
    found = page.evaluate(
        LANDMARKS_SCRIPT, [banners.element_handle(), mains.element_handle()]
    )

    assert isinstance(found, dict), found
    headings_in_main = found.pop("headingsInMain")
    assert found == {
        "bannerTestId": BANNER_TEST_ID,
        "bannerInsideMain": False,
        "mainFollowsBanner": True,
        "headingsOutsideMain": 0,
        "bannersInMain": 0,
        "shownOutsideMain": [],
    }
    assert headings_in_main >= 1
