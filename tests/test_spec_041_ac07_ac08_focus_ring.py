"""Tests of spec 041, AC-7 and AC-8: the 2 px navy focus ring, and the white ring
on a navy surface.

Keyboard focus as spec 035: its `Walker.tab_to`, or a key press followed by
`focus()` from `page.evaluate` (spec 035 AC-10's "Focus forced onto a key"). The
shared setup is in `tests/spec041_harness.py`.

Choices where the spec leaves room:

- AC-8, "a key press": the test presses Tab, which puts the page in keyboard
  modality in every engine, then calls `focus()` on the probe button. It checks
  that the button then matches `:focus-visible` before it reads the outline, so a
  ring that is not drawn fails as such.
- AC-7, touch context: as spec 035 AC-10's test, a tap on (1, 0), then
  ArrowRight (the key press), then `focus()` on the key `A`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import (
    Walker,
    build_fx01_grid,
    build_reference_catalogue,
    open_room,
)
from spec041_harness import (
    NAVY,
    WHITE,
    add_probe,
    assert_colour,
    cell_at,
    colour_of,
    open_catalogue,
    px,
    style_of,
    touch_context,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """The 360 by 740 touch page of spec 035 AC-10."""
    context = touch_context(browser, browser_name)
    yield context.new_page()
    context.close()


# ---- Helpers ------------------------------------------------------------------


def force_one_filter(page: Page) -> Locator:
    """Return a locator for the catalogue's force 1 filter button."""
    return page.locator('[data-testid="force-filter"][data-force="1"]')


def tab_to_force_one(page: Page, base_url: str) -> Locator:
    """On `/`, move the keyboard focus to the force 1 filter button."""
    open_catalogue(page, base_url)
    Walker(page).tab_to("force-filter", '[data-force="1"]')
    button = force_one_filter(page)
    expect(button).to_be_focused()
    return button


def tab_to_grid(page: Page, base_url: str, grid: Grid) -> Locator:
    """On the room page with a FX-01 snapshot, move the keyboard focus to the grid."""
    open_room(page, base_url, grid)
    Walker(page).tab_to("grid")
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_be_focused()
    return grid_element


def focus_key_a(page: Page, base_url: str, grid: Grid) -> Locator:
    """In the touch context, a key press then `focus()` on the key `A`."""
    open_room(page, base_url, grid)
    cell_at(page, 1, 0).tap()
    expect(page.get_by_test_id("grid")).to_be_focused()
    page.keyboard.press("ArrowRight")
    key = page.locator('[data-testid="key"][data-key="A"]')
    key.evaluate("element => element.focus()")
    expect(key).to_be_focused()
    return key


def assert_two_px_solid(element: Locator) -> None:
    assert style_of(element, "outlineStyle") == "solid"
    assert px(style_of(element, "outlineWidth")) == 2.0


# ---- AC-7: the focus ring is 2 px navy --------------------------------------------


def test_ac7_force_filter_ring_is_2px_solid(page: Page, live_server: str) -> None:
    button = tab_to_force_one(page, live_server)

    assert_two_px_solid(button)


def test_ac7_force_filter_ring_is_navy(page: Page, live_server: str) -> None:
    button = tab_to_force_one(page, live_server)

    assert_colour(colour_of(button, "outlineColor"), NAVY)


def test_ac7_force_filter_ring_has_offset_2px(page: Page, live_server: str) -> None:
    button = tab_to_force_one(page, live_server)

    assert px(style_of(button, "outlineOffset")) == 2.0


def test_ac7_grid_ring_is_2px_solid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    grid_element = tab_to_grid(page, live_server, fx01_grid)

    assert_two_px_solid(grid_element)


def test_ac7_grid_ring_is_navy(page: Page, live_server: str, fx01_grid: Grid) -> None:
    grid_element = tab_to_grid(page, live_server, fx01_grid)

    assert_colour(colour_of(grid_element, "outlineColor"), NAVY)


def test_ac7_key_ring_is_2px_solid(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    key = focus_key_a(touch_page, live_server, fx01_grid)

    assert_two_px_solid(key)


def test_ac7_key_ring_is_navy(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    key = focus_key_a(touch_page, live_server, fx01_grid)

    assert_colour(colour_of(key, "outlineColor"), NAVY)


# ---- AC-8: a navy surface has a white focus ring ----------------------------------

NAVY_SURFACE_PROBE = (
    '<div class="nock-on-navy">'
    '<button type="button" class="nock-button">Test</button>'
    "</div>"
)


def add_navy_surface(page: Page, base_url: str) -> Locator:
    """Open the catalogue, add a navy surface probe and return its locator."""
    open_catalogue(page, base_url)
    return add_probe(page, "navy-surface", NAVY_SURFACE_PROBE)


def focus_navy_button(page: Page, base_url: str) -> Locator:
    """A key press, then `focus()` on the probe's button."""
    surface = add_navy_surface(page, base_url)
    button = surface.locator("button")
    page.keyboard.press("Tab")
    button.evaluate("element => element.focus()")
    expect(button).to_be_focused()
    assert button.evaluate("element => element.matches(':focus-visible')") is True
    return button


def test_ac8_navy_surface_has_the_navy_background(page: Page, live_server: str) -> None:
    surface = add_navy_surface(page, live_server)

    assert_colour(colour_of(surface, "backgroundColor"), NAVY)


def test_ac8_navy_surface_has_white_text(page: Page, live_server: str) -> None:
    surface = add_navy_surface(page, live_server)

    assert_colour(colour_of(surface, "color"), WHITE)


def test_ac8_ring_on_navy_is_2px_solid(page: Page, live_server: str) -> None:
    button = focus_navy_button(page, live_server)

    assert_two_px_solid(button)


def test_ac8_ring_on_navy_is_white(page: Page, live_server: str) -> None:
    button = focus_navy_button(page, live_server)

    assert_colour(colour_of(button, "outlineColor"), WHITE)


def test_ac8_ring_on_navy_has_offset_minus_4px(page: Page, live_server: str) -> None:
    button = focus_navy_button(page, live_server)

    assert px(style_of(button, "outlineOffset")) == -4.0
