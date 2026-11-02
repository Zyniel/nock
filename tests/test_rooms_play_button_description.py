"""Tests of lobby/rooms, AC-18: the « Jouer » buttons are told apart.

On the catalogue page and on a grid page, each card's button is named « Jouer » and
described by its card's title (`catalogue.item.number`), so a screen reader that lists
the buttons can tell them apart. The shared setup is in `spec004_harness`: the
reference catalogue CAT serves the published grids 1, 2 and 3.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec004_harness import grid_from_text, make_reference_catalogue

PLAY_NAME = "Jouer"  # `catalogue.play`


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT (also served by `live_server`)."""
    return make_reference_catalogue(fx01_grid)


@pytest.mark.parametrize(
    ("path", "number", "description"),
    [
        pytest.param("/", 2, "Grille n° 2", id="catalogue-card-2"),
        pytest.param("/", 3, "Grille n° 3", id="catalogue-card-3"),
        pytest.param("/g/1", 1, "Grille n° 1", id="grid-page"),
    ],
)
def test_ac18_play_button_is_described_by_its_cards_title(
    page: Page, live_server: str, path: str, number: int, description: str
) -> None:
    page.goto(f"{live_server}{path}")

    card = page.locator(f'[data-testid="catalogue-item"][data-number="{number}"]')
    expect(card).to_have_count(1)
    button = card.get_by_role("button")
    expect(button).to_have_count(1)
    expect(button).to_have_accessible_name(PLAY_NAME)
    expect(button).to_have_accessible_description(description)
