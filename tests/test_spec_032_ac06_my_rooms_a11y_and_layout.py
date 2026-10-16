"""Tests of spec 032, AC-6: "My rooms" meets spec 035 and the window sizes of spec
006 AC-5.

With AC-5's two summaries (the summaries route mocked, the live server's empty
catalogue, Paris time), at 1280 by 720 and at 360 by 740: spec 035's contrast scan
and language scan find no offending element on `/`; keyboard only, spec 035's
`Walker.tab_to` reaches each `my-room-link`, which then shows spec 035 AC-2's
outline, and `Enter` on the first loads `/r/XYZ789`. At each window size of spec
006 AC-5 the page has no horizontal scroll, also when the first summary lists 8
players whose nicknames have 20 characters each.

The language scan's data is only what the spec names as data: the room codes and
the nicknames of the summaries. Every other text must match a `fr.json` value read
as a pattern.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from spec006_harness import WINDOW_SIZES
from spec024_harness import outline_problems
from spec032_harness import (
    ABC,
    WAIT_TIMEOUT_MS,
    XYZ,
    NewPage,
    SummariesRoute,
    abc_summary,
    expect_my_rooms_ready,
    open_catalogue,
    open_two_summaries,
    paris_page_factory,
    seed_storage,
    two_identities,
    xyz_summary,
)
from spec035_harness import (
    LANGUAGE_SCAN_SCRIPT,
    Walker,
    contrast_offenders,
    unknown_texts,
)

SCAN_SIZES = [(1280, 720), (360, 740)]
SCAN_DATA = {XYZ, ABC, "Ana", "Bob"}
# Spec 035 AC-9's samples: the checker flags the first ones and accepts the others.
FLAGGED_SAMPLES = [
    "Loading\N{HORIZONTAL ELLIPSIS}",
    "Salon",
    "Check word",
    "Error: connection lost",
    "Score: 3",
    "Grille n\N{DEGREE SIGN} deux",
]
ACCEPTED_SAMPLES = [
    "Salon ABC123",
    "Grille n\N{DEGREE SIGN} 2",
    "Ana a rejoint le salon",
    "0:00",
    "1:02:05",
]


def size_ids(sizes: list[tuple[int, int]]) -> list[str]:
    return [f"{width}x{height}" for width, height in sizes]


def eight_long_names() -> list[str]:
    """Eight different nicknames of 20 characters each."""
    names: list[str] = []
    for number in range(1, 9):
        prefix = f"Joueur{number}"
        names.append(prefix + "x" * (20 - len(prefix)))
    return names


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_page_factory(browser)


# ---- Scans ---------------------------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac6_my_rooms_has_no_contrast_offender(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_summaries(page, live_server)

    assert contrast_offenders(page) == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac6_my_rooms_has_no_text_outside_fr_json_and_the_data(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_summaries(page, live_server)

    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)

    assert isinstance(texts, list)
    assert len(texts) > 0
    assert unknown_texts(texts, SCAN_DATA) == []


def test_ac6_the_language_checker_still_flags_spec_035s_samples() -> None:
    assert unknown_texts(FLAGGED_SAMPLES, set()) == FLAGGED_SAMPLES
    assert unknown_texts(ACCEPTED_SAMPLES, set()) == []


# ---- Keyboard ------------------------------------------------------------------


def link_selector(code: str) -> str:
    return f'[href="/r/{code}"]'


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac6_tab_reaches_each_link_and_shows_spec_035s_outline(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_summaries(page, live_server)
    walker = Walker(page)

    walker.tab_to("my-room-link", link_selector(XYZ))
    walker.tab_to("my-room-link", link_selector(ABC))

    assert [reached.test_id for reached in walker.reached] == ["my-room-link"] * 2
    for reached in walker.reached:
        problems = outline_problems(
            reached.outline_style, reached.outline_width, reached.outline_contrast
        )
        assert problems == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac6_enter_on_the_first_link_loads_its_room(
    new_page: NewPage, live_server: str, width: int, height: int
) -> None:
    page = new_page(width, height)
    open_two_summaries(page, live_server)
    walker = Walker(page)
    walker.tab_to("my-room-link", link_selector(XYZ))

    page.keyboard.press("Enter")

    page.wait_for_url(f"{live_server}/r/{XYZ}", timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("room-page")).to_be_attached()


# ---- Window sizes --------------------------------------------------------------


def open_with_long_names(page: Page, live_server: str) -> None:
    """Open `/` where the first summary lists eight 20-character nicknames."""
    route = SummariesRoute(
        body=[xyz_summary(players=eight_long_names()), abc_summary()]
    )
    seed_storage(page, two_identities())
    open_catalogue(page, live_server, route)
    expect_my_rooms_ready(page, 2)


@pytest.mark.parametrize("long_names", [False, True], ids=["two_names", "eight_long"])
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac6_the_catalogue_with_my_rooms_has_no_horizontal_scroll(
    new_page: NewPage, live_server: str, width: int, height: int, long_names: bool
) -> None:
    page = new_page(width, height)
    if long_names:
        open_with_long_names(page, live_server)
    else:
        open_two_summaries(page, live_server)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1], sizes
