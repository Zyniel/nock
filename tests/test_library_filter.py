"""Tests of `content/library.md` AC-6: which filter chip is pressed, and the
requests the filter makes.

Browser with the live server serving `CAT`. The pointer tests (004 AC-2, 046 AC-4)
prove the chips, the cards each press shows and the look; these add what the widened
criterion says:

- After each press, in any order, the chip just pressed is the only one with
  `aria-pressed="true"`. The sequence goes « Force 1 », « Force 4 », « Force 2 »,
  « Toutes », « Force 3 », « Force 3 » again (a press on the pressed chip keeps it
  alone pressed) and « Force 1 ».
- From the load through all the presses, the page made exactly one request whose
  path is `/api/grids`, with no query (so no `?force=`), and none other to it.
  "Made" is read after a pause with no new request.
"""

from __future__ import annotations

from urllib.parse import urlsplit

from playwright.sync_api import Page, expect

from library_harness import QUIET_MS
from spec004_harness import fr_text, load_fr

GRIDS_PATH = "/api/grids"
CHIPS = ["all", "1", "2", "3", "4"]
PRESSES = ["1", "4", "2", "all", "3", "3", "1"]


CATALOGUE_KIND = "reference"


def chip_label(chip: str) -> str:
    """The visible text of a chip: `all` or a force from 1 to 4."""
    if chip == "all":
        return load_fr()["catalogue.filter.all"]
    return fr_text("catalogue.filter.force", force=int(chip))


def record_grid_requests(page: Page) -> list[str]:
    """Collect the URL of each request to the path `/api/grids`, query or not."""
    urls: list[str] = []

    def record(url: str) -> None:
        if urlsplit(url).path == GRIDS_PATH:
            urls.append(url)

    page.on("request", lambda request: record(request.url))
    return urls


def expect_only_pressed(page: Page, pressed: str) -> None:
    """Expect `pressed` to be the one chip with `aria-pressed="true"`."""
    for chip in CHIPS:
        button = page.get_by_role("button", name=chip_label(chip), exact=True)
        expected = "true" if chip == pressed else "false"
        expect(button).to_have_attribute("aria-pressed", expected)


def test_ac6_only_the_chip_just_pressed_is_pressed_and_the_list_is_asked_once(
    page: Page, live_server: str
) -> None:
    urls = record_grid_requests(page)

    page.goto(f"{live_server}/")

    expect(page.get_by_test_id("catalogue-page")).to_have_attribute(
        "data-state", "ready"
    )
    expect_only_pressed(page, "all")
    for chip in PRESSES:
        page.get_by_role("button", name=chip_label(chip), exact=True).click()
        expect_only_pressed(page, chip)

    page.wait_for_timeout(QUIET_MS)
    assert urls == [f"{live_server}{GRIDS_PATH}"]
