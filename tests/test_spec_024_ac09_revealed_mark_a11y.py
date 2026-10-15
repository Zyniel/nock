"""Tests of spec 024, AC-9: a revealed cell is marked by more than its colour, and
the reveal controls meet spec 035.

The page is driven with a mocked socket. The contrast scan, the language scan and
the keyboard walker (`tab_to`) are spec 035's. The shared setup is in
`spec024_harness`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import (
    ChangeList,
    MockRoomSocket,
    cell_at,
    contrast_problems,
    expect_selection,
    grid_from_text,
    language_data,
    language_problems,
    load_fr,
    make_catalogue,
    make_walker,
    mark_contrast,
    mark_problems,
    open_room,
    outline_problems,
)

SCAN_SIZES = [(1280, 720), (360, 740)]
MIN_MARK_CONTRAST = 3.0
LETTER_CELLS = [(0, 1), *[(1, column) for column in range(5)]]
for _row in range(2, 5):
    for _column in range(1, 5):
        LETTER_CELLS.append((_row, _column))

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    contexts: list[BrowserContext] = []

    def make(width: int, height: int) -> Page:
        context = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


# ---- The state of AC-9 ----


def ac9_changes() -> ChangeList:
    """(1, 0) holds `T` revealed; (1, 1) holds `A` locked by a check of `p2`."""
    return [
        (1, 0, {"letter": "T", "locked": True, "revealed": True, "author": None}),
        (1, 1, {"letter": "A", "locked": True, "revealed": False, "author": "p2"}),
    ]


def open_ac9(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """The FX-01 snapshot of AC-9: seq 10, `you` `p1` (host), players `p1`, `p2`."""
    return open_room(page, live_server, grid, changes=ac9_changes(), seq=10)


# ---- AC-9 ----


def test_ac9_the_new_fr_json_key_of_a_revealed_cell() -> None:
    assert load_fr()["a11y.revealed"] == "lettre révélée"


def test_ac9_a_revealed_cell_holds_the_corner_mark_and_the_hidden_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-revealed", "true")
    expect(cell).to_have_attribute("data-letter", "T")
    expect(cell.get_by_test_id("reveal-mark")).to_have_count(1)
    label = cell.get_by_test_id("reveal-label")
    expect(label).to_have_count(1)
    expect(label).to_have_text(load_fr()["a11y.revealed"])
    expect(label).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))
    assert mark_problems(cell) == []


def test_ac9_a_cell_locked_by_a_check_holds_neither_mark_nor_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-revealed", "false")
    expect(cell.get_by_test_id("reveal-mark")).to_have_count(0)
    expect(cell.get_by_test_id("reveal-label")).to_have_count(0)


def test_ac9_every_other_letter_cell_is_not_revealed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    for row, column in LETTER_CELLS:
        if (row, column) == (1, 0):
            continue
        cell = cell_at(page, row, column)
        expect(cell).to_have_attribute("data-revealed", "false")
        expect(cell.get_by_test_id("reveal-mark")).to_have_count(0)
        expect(cell.get_by_test_id("reveal-label")).to_have_count(0)
    expect(page.get_by_test_id("reveal-mark")).to_have_count(1)


def test_ac9_the_mark_keeps_3_to_1_against_the_cell_selected_or_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-revealed", "true")

    not_selected = mark_contrast(cell)
    cell.click()
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "1")
    expect(grid).to_have_attribute("data-selected-column", "0")
    selected = mark_contrast(cell)

    assert not_selected >= MIN_MARK_CONTRAST
    assert selected >= MIN_MARK_CONTRAST


def open_scanned_state(page: Page, live_server: str, grid: Grid) -> None:
    """AC-9's state with (2, 2) tapped and the reveal controls shown."""
    open_ac9(page, live_server, grid)
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("reveal-letter")).to_be_visible()
    expect(page.get_by_test_id("reveal-word")).to_be_visible()
    expect(cell_at(page, 1, 0)).to_have_attribute("data-revealed", "true")


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=["desktop", "phone"])
def test_ac9_the_contrast_scan_finds_no_offending_element(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_scanned_state(page, live_server, fx01_grid)

    assert contrast_problems(page) == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=["desktop", "phone"])
def test_ac9_the_language_scan_finds_no_offending_element(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_scanned_state(page, live_server, fx01_grid)

    data = language_data(live_server, ["Ana", "Bob"])
    assert language_problems(page, data) == []


def test_ac9_the_keyboard_reaches_both_reveal_buttons_with_a_visible_focus(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    open_ac9(page, live_server, fx01_grid)
    walker = make_walker(page)

    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_selection(page, 1, 2, "across", "0,0,0")
    for test_id in ("reveal-letter", "reveal-word"):
        walker.tab_to(test_id)
        expect(page.get_by_test_id(test_id)).to_be_enabled()
        expect(page.get_by_test_id(test_id)).to_be_focused()

    reached = {step.test_id: step for step in walker.reached}
    for test_id in ("reveal-letter", "reveal-word"):
        step = reached[test_id]
        problems = outline_problems(
            step.outline_style, step.outline_width, step.outline_contrast
        )
        assert problems == [], step
