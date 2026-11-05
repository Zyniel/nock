"""Tests of lobby/rooms, AC-18: the « Jouer » buttons are told apart.

On the catalogue page and on a grid page, each card's button is named « Jouer » and
described by its card's title (`catalogue.item.number`), so a screen reader that lists
the buttons can tell them apart. The shared setup is in `spec004_harness`: the
reference catalogue CAT serves the published grids 1, 2 and 3.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

PLAY_NAME = "Jouer"  # `catalogue.play`


CATALOGUE_KIND = "reference"


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
