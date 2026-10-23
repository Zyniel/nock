"""Tests of spec 045, AC-1: « Auteurs » is off by default, and the browser
remembers it.

On a FX-01 snapshot at 360 by 740 (desktop context), `authors-switch` starts from
`localStorage["nock.authors"]`: `"true"` turns the mode on, any other value or
none leaves it off. Each activation flips it, writes `"true"` or `"false"`, keeps
`room-menu` open and sends no frame. The shared setup is in `spec045_harness`.

Also tested, from "Edge cases and errors": a `localStorage` that throws (the mode
starts off and flips for the page's life), and a solved grid (the switch keeps
working).

Choices where the spec leaves room:

- The switch's detail is the Menu item's `.nock-menu-detail` (spec 043's tests
  read it the same way).
- "After a reload with the same mock": the page reloads and the mock answers its
  new join with the same snapshot (spec 043's `reload_room`).
- "Flips for the page's life" with a throwing `localStorage`: after a click the
  switch reads `aria-pressed="true"` and `authors-legend` shows; a second click
  turns both back.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from room_panels import open_menu
from spec019_harness import OpenWindow, window_opener
from spec042_harness import make_storage_throw
from spec043_harness import (
    FX01_SOLUTION,
    PHONE,
    fr_value,
    frames_sent_after,
    fx01_view,
    letters_of,
    open_room,
    players_up_to,
    reload_room,
    seed_value,
    snapshot_frame,
    stored_value,
)
from spec045_harness import (
    AUTHORS_KEY,
    INKS,
    authors_switch,
    finder_problems,
    legend_of,
    open_page,
    read_cell,
)

DETAIL_SCRIPT = r"""
item => {
  const found = [];
  for (const detail of item.querySelectorAll('.nock-menu-detail')) {
    found.push(detail.textContent.trim());
  }
  return found;
}
"""

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Helpers of these tests ----


def fx01_frame(grid: Grid) -> str:
    """A FX-01 snapshot, `seq` 5, `you` `p1` among `p1` to `p3`, (1, 0) `T` by p1."""
    view = fx01_view(grid, letters_of([(1, 0)]))
    return snapshot_frame(view, players_up_to(3))


def detail_of(page: Page) -> list[str]:
    found = authors_switch(page).evaluate(DETAIL_SCRIPT)
    assert isinstance(found, list), found
    return [str(text) for text in found]


def open_phone(
    window: OpenWindow, base_url: str, grid: Grid, *, stored: str | None = None
) -> Page:
    """The FX-01 page at 360 by 740, `nock.authors` seeded with `stored` if given."""
    width, height = PHONE
    page = window(width, height, False)
    if stored is not None:
        seed_value(page, AUTHORS_KEY, stored)
    open_room(page, base_url, fx01_frame(grid))
    return page


# ---- AC-1: off by default ----


def test_ac1_with_an_empty_storage_the_switch_starts_off_and_reads_desactive(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)

    open_menu(page)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    assert detail_of(page) == [fr_value("authors.off")]
    expect(legend_of(page)).to_have_count(0)


def test_ac1_a_click_turns_it_on_reads_active_and_stores_true(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid)
    open_menu(page)

    authors_switch(page).click()

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    assert detail_of(page) == [fr_value("authors.on")]
    assert stored_value(page, AUTHORS_KEY) == "true"


def test_ac1_a_click_leaves_the_menu_open_and_sends_no_frame(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = PHONE
    page = window(width, height, False)
    mock = open_room(page, live_server, fx01_frame(fx01_grid))
    open_menu(page)

    sent = frames_sent_after(page, mock, lambda: authors_switch(page).click())

    assert sent == []
    expect(page.get_by_test_id("room-menu")).to_be_visible()
    expect(page.get_by_test_id("room-menu")).not_to_have_attribute("hidden", "")


def test_ac1_after_a_reload_the_switch_is_still_on_and_the_legend_shows(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = PHONE
    page = window(width, height, False)
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    open_menu(page)
    authors_switch(page).click()
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")

    reload_room(page, mock, frame)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    expect(legend_of(page)).to_be_visible()


def test_ac1_a_second_click_turns_it_off_stores_false_and_removes_the_legend(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = PHONE
    page = window(width, height, False)
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    open_menu(page)
    authors_switch(page).click()
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    reload_room(page, mock, frame)
    expect(legend_of(page)).to_be_visible()
    open_menu(page)

    sent = frames_sent_after(page, mock, lambda: authors_switch(page).click())

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    assert detail_of(page) == [fr_value("authors.off")]
    assert stored_value(page, AUTHORS_KEY) == "false"
    expect(legend_of(page)).to_have_count(0)
    assert sent == []


def test_ac1_after_turning_it_off_a_reload_keeps_it_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = PHONE
    page = window(width, height, False)
    seed_value(page, AUTHORS_KEY, "true")
    frame = fx01_frame(fx01_grid)
    mock = open_room(page, live_server, frame)
    open_menu(page)
    authors_switch(page).click()
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    reload_room(page, mock, frame)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    expect(legend_of(page)).to_have_count(0)


def test_ac1_a_stored_true_starts_the_page_with_the_mode_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_phone(window, live_server, fx01_grid, stored="true")

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    expect(legend_of(page)).to_be_visible()
    assert finder_problems("(1, 0)", read_cell(page, 1, 0), "0", INKS[0]) == []


@pytest.mark.parametrize("stored", ["yes", "True", "1", ""])
def test_ac1_any_other_stored_value_starts_the_page_with_the_mode_off(
    window: OpenWindow, live_server: str, fx01_grid: Grid, stored: str
) -> None:
    page = open_phone(window, live_server, fx01_grid, stored=stored)
    open_menu(page)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    assert detail_of(page) == [fr_value("authors.off")]
    expect(legend_of(page)).to_have_count(0)


# ---- AC-1: edge cases ----


def test_ac1_with_a_storage_that_throws_it_starts_off_and_flips_for_the_page(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    width, height = PHONE
    page = window(width, height, False)
    make_storage_throw(page)
    open_room(page, live_server, fx01_frame(fx01_grid))
    open_menu(page)
    switch = authors_switch(page)
    expect(switch).to_have_attribute("aria-pressed", "false")

    switch.click()

    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(legend_of(page)).to_be_visible()
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(legend_of(page)).to_have_count(0)


def test_ac1_on_a_solved_grid_the_switch_is_enabled_and_turns_the_mode_on(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    view = fx01_view(fx01_grid, letters_of(list(FX01_SOLUTION), author="p2"))
    frame = snapshot_frame(view, players_up_to(3), solved=True)
    page, _ = open_page(window, live_server, frame, PHONE)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    open_menu(page)
    switch = authors_switch(page)
    expect(switch).to_be_enabled()

    switch.click()

    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(legend_of(page)).to_be_visible()
    assert finder_problems("(4, 4)", read_cell(page, 4, 4), "1", INKS[1]) == []
