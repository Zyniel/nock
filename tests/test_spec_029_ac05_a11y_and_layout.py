"""Tests of spec 029, AC-5: the history list meets spec 035 and spec 006 AC-5.

Browser with mocked routes, on the live server with an empty catalogue and accounts
off, in Paris time. The device holds the two records of AC-2 (XYZ789 on grid 2 with
Bob and Cy; the older QQQQQQ, a bare grid played alone). At 1280 by 720 and at 360
by 740: spec 035's contrast scan and language scan find no offending element on `/`;
keyboard only, spec 035's `Walker.tab_to` reaches the `history-replay` (only XYZ789
has one), which shows spec 035 AC-2's outline, and `Enter` on it sends
`POST /api/rooms` with `{"grid_number": 2}` (answered 500 by the test, so the page
stays). At each window size of spec 006 AC-5 the page has no horizontal scroll,
also with a record that lists 7 team-mates of 20 characters each.

The language scan's data is only what the spec names as data: the room codes and
the team-mates' nicknames of the records.
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, Route

from spec006_harness import WINDOW_SIZES
from spec024_harness import outline_problems
from spec029_harness import (
    HISTORY_KEY,
    OLD_CODE,
    WAIT_TIMEOUT_MS,
    XYZ,
    XYZ_FINISHED_AT,
    NewPage,
    device_record,
    expect_history_count,
    history_value,
    old_record,
    open_catalogue,
    paris_pages,
    seed,
    xyz_record,
)
from spec035_harness import (
    LANGUAGE_SCAN_SCRIPT,
    Walker,
    contrast_offenders,
    unknown_texts,
)

SCAN_SIZES = [(1280, 720), (360, 740)]
SCAN_DATA = {XYZ, OLD_CODE, "Bob", "Cy"}


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


def seven_long_names() -> list[str]:
    """Seven different nicknames of 20 characters each."""
    names: list[str] = []
    for number in range(1, 8):
        prefix = f"Coequipier{number}"
        names.append(prefix + "x" * (20 - len(prefix)))
    return names


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_pages(browser)


def open_two_records(page: Page, live_server: str) -> None:
    """Open `/` with the two records of AC-2."""
    seed(page, {HISTORY_KEY: history_value([xyz_record(), old_record()])})
    open_catalogue(page, live_server, None)
    expect_history_count(page, 2)


def open_long_names(page: Page, live_server: str) -> None:
    """Open `/` where the first record lists seven 20-character team-mates."""
    crowded = device_record(XYZ, 2, XYZ_FINISHED_AT, 754_000, seven_long_names())
    seed(page, {HISTORY_KEY: history_value([crowded, old_record()])})
    open_catalogue(page, live_server, None)
    expect_history_count(page, 2)


class CreationRoute:
    """`POST /api/rooms` answered 500, with the body of each request kept."""

    def __init__(self) -> None:
        self.bodies: list[object] = []

    def handle(self, route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        post_data = route.request.post_data
        self.bodies.append(None if post_data is None else json.loads(post_data))
        route.fulfill(status=500, content_type="application/json", body="{}")


# ---- Scans ------------------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac5_the_history_has_no_contrast_offender(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_records(page, live_server)

    assert contrast_offenders(page) == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac5_the_history_has_no_text_outside_fr_json_and_the_data(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_records(page, live_server)

    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)

    assert isinstance(texts, list)
    assert len(texts) > 0
    assert unknown_texts(texts, SCAN_DATA) == []


# ---- Keyboard ---------------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac5_tab_reaches_the_replay_button_and_shows_spec_035s_outline(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_records(page, live_server)
    walker = Walker(page)

    walker.tab_to("history-replay")

    assert [reached.test_id for reached in walker.reached] == ["history-replay"]
    reached = walker.reached[0]
    problems = outline_problems(
        reached.outline_style, reached.outline_width, reached.outline_contrast
    )
    assert problems == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac5_enter_on_the_replay_button_sends_the_creation_request(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    creation = CreationRoute()
    page.route("**/api/rooms", creation.handle)
    open_two_records(page, live_server)
    walker = Walker(page)
    walker.tab_to("history-replay")

    page.keyboard.press("Enter")

    waited_ms = 0
    while len(creation.bodies) == 0:
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("Enter sent no POST /api/rooms")
        page.wait_for_timeout(50)
        waited_ms += 50
    assert creation.bodies == [{"grid_number": 2}]


# ---- Window sizes -----------------------------------------------------------------


@pytest.mark.parametrize("long_names", [False, True], ids=["two_records", "seven_long"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac5_the_catalogue_with_the_history_has_no_horizontal_scroll(
    new_page: NewPage, live_server: str, width: int, height: int, long_names: bool
) -> None:
    page = new_page(width, height)
    if long_names:
        open_long_names(page, live_server)
    else:
        open_two_records(page, live_server)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1], sizes
