"""Tests of spec 041, AC-21: form controls take the page font, not the OS control
font.

On `/` once `catalogue-page` shows (live server), and on the room page once the
`grid` of a FX-01 snapshot shows (mocked room of spec 035's harness), the test
appends the probe of the criterion to `body` and reads the computed font of each
control; then it reads a real control of the page. The tests only read computed
styles, so they need no wait for the fonts. The shared setup is in
`tests/spec041_harness.py`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import build_fx01_grid, build_reference_catalogue, open_room
from spec041_harness import (
    UI_FONT_STACK,
    add_probe,
    font_families,
    open_catalogue,
    px,
    style_of,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- The pages and the probe ------------------------------------------------------

CONTROLS_PROBE = (
    '<div style="font-size: 20px">'
    '<button type="button">Bouton</button>'
    '<input type="text" value="Texte">'
    "<select><option>Choix</option></select>"
    "<textarea>Zone</textarea>"
    "</div>"
)
CONTROL_TAGS = ("button", "input", "select", "textarea")
PAGES = ("catalogue", "room")

PageOpener = Callable[[Page, str, Grid], None]


def open_catalogue_page(page: Page, base_url: str, grid: Grid) -> None:
    del grid  # `/` serves the reference catalogue, which holds FX-01.
    open_catalogue(page, base_url)


def open_room_page(page: Page, base_url: str, grid: Grid) -> None:
    open_room(page, base_url, grid)
    expect(page.get_by_test_id("grid")).to_be_visible()


OPENERS: dict[str, PageOpener] = {
    "catalogue": open_catalogue_page,
    "room": open_room_page,
}


def add_controls(page: Page, base_url: str, grid: Grid, page_name: str) -> Locator:
    OPENERS[page_name](page, base_url, grid)
    return add_probe(page, "controls", CONTROLS_PROBE)


def real_control(page: Page, page_name: str) -> Locator:
    """The control of the page that the criterion reads."""
    if page_name == "catalogue":
        return page.locator('[data-testid="force-filter"][data-force="1"]')
    return page.get_by_test_id("timer-toggle")


# ---- AC-21: form controls take the page font --------------------------------------


@pytest.mark.parametrize("tag", CONTROL_TAGS)
@pytest.mark.parametrize("page_name", PAGES)
def test_ac21_a_probe_control_has_the_ui_font_family(
    page: Page, live_server: str, fx01_grid: Grid, page_name: str, tag: str
) -> None:
    probe = add_controls(page, live_server, fx01_grid, page_name)

    family = style_of(probe.locator(tag), "fontFamily")

    assert font_families(family) == UI_FONT_STACK


@pytest.mark.parametrize("tag", CONTROL_TAGS)
@pytest.mark.parametrize("page_name", PAGES)
def test_ac21_a_probe_control_has_the_size_of_its_parent(
    page: Page, live_server: str, fx01_grid: Grid, page_name: str, tag: str
) -> None:
    probe = add_controls(page, live_server, fx01_grid, page_name)

    size = px(style_of(probe.locator(tag), "fontSize"))

    assert size == px(style_of(probe, "fontSize"))
    assert size == 20.0


@pytest.mark.parametrize("page_name", PAGES)
def test_ac21_a_real_control_of_the_page_has_the_ui_font_family(
    page: Page, live_server: str, fx01_grid: Grid, page_name: str
) -> None:
    OPENERS[page_name](page, live_server, fx01_grid)
    control = real_control(page, page_name)
    expect(control).to_have_count(1)

    family = style_of(control, "fontFamily")

    assert font_families(family) == UI_FONT_STACK
