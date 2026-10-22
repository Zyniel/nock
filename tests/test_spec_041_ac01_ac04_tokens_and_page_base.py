"""Tests of spec 041, AC-1 to AC-4: the colour tokens, the player colours and the
page base.

Each token is read through a probe `div` with `color: var(<token>)` on `/` once
`catalogue-page` shows (spec 041, "Test harness"), never from the custom
property's text. The room page is the mocked room of spec 035's harness with a
FX-01 snapshot. The shared setup is in `tests/spec041_harness.py`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec035_harness import (
    build_fx01_grid,
    build_reference_catalogue,
    open_room,
    player_view,
)
from spec041_harness import (
    CLUE_FONT_STACK,
    COLOUR_TOKENS,
    INK,
    PLAYER_COLOURS,
    PLAYER_INKS,
    TRANSLUCENT_TOKENS,
    UI_FONT_STACK,
    WHITE,
    add_probe,
    assert_colour,
    colour_of,
    font_families,
    hex_to_rgb,
    open_catalogue,
    player_colour_token,
    player_ink_token,
    style_of,
    token_colour,
)

# ---- Fixtures: thin wrappers around the harnesses ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (served by live_server for `/`)."""
    return build_reference_catalogue(fx01_grid)


# ---- AC-1: each colour token resolves to its value --------------------------------


@pytest.mark.parametrize("token", list(COLOUR_TOKENS))
def test_ac1_a_probe_with_the_token_has_the_colour_of_the_table(
    page: Page, live_server: str, token: str
) -> None:
    open_catalogue(page, live_server)

    colour = token_colour(page, token)

    assert_colour(colour, hex_to_rgb(COLOUR_TOKENS[token]))


# ---- AC-2: each translucent token resolves to its value ---------------------------


@pytest.mark.parametrize("token", list(TRANSLUCENT_TOKENS))
def test_ac2_a_probe_with_the_translucent_token_has_its_channels_and_alpha(
    page: Page, live_server: str, token: str
) -> None:
    open_catalogue(page, live_server)
    channels, alpha = TRANSLUCENT_TOKENS[token]

    colour = token_colour(page, token)

    assert_colour(colour, channels, alpha)


# ---- AC-3: the eight imposed player colours and their inks ------------------------


@pytest.mark.parametrize("index", range(8))
def test_ac3_a_probe_with_the_player_colour_has_the_colour_of_the_table(
    page: Page, live_server: str, index: int
) -> None:
    open_catalogue(page, live_server)

    colour = token_colour(page, player_colour_token(index))

    assert_colour(colour, hex_to_rgb(PLAYER_COLOURS[index]))


@pytest.mark.parametrize("index", range(8))
def test_ac3_a_probe_with_the_player_ink_has_the_colour_of_the_table(
    page: Page, live_server: str, index: int
) -> None:
    open_catalogue(page, live_server)

    colour = token_colour(page, player_ink_token(index))

    assert_colour(colour, hex_to_rgb(PLAYER_INKS[index]))


EIGHT_NICKNAMES = ("Ana", "Bob", "Cleo", "Dan", "Eve", "Fred", "Gus", "Hugo")


@pytest.mark.parametrize("index", range(8))
def test_ac3_the_roster_swatch_of_colour_n_has_the_background_of_player_colour_n(
    page: Page, live_server: str, fx01_grid: Grid, index: int
) -> None:
    players = []
    for colour in range(8):
        player_id = f"p{colour + 1}"
        players.append(
            player_view(player_id, EIGHT_NICKNAMES[colour], colour, is_host=colour == 0)
        )
    open_room(page, live_server, fx01_grid, players=players)
    swatch = page.locator(f'[data-testid="roster-colour"][data-colour="{index}"]')

    background = colour_of(swatch, "backgroundColor")

    assert_colour(background, hex_to_rgb(PLAYER_COLOURS[index]))


# ---- AC-4: the page base uses the tokens ------------------------------------------


def test_ac4_catalogue_body_background_is_white(page: Page, live_server: str) -> None:
    open_catalogue(page, live_server)

    assert_colour(colour_of(page.locator("body"), "backgroundColor"), WHITE)


def test_ac4_catalogue_body_text_is_ink(page: Page, live_server: str) -> None:
    open_catalogue(page, live_server)

    assert_colour(colour_of(page.locator("body"), "color"), INK)


def test_ac4_catalogue_body_font_family_is_the_ui_stack(
    page: Page, live_server: str
) -> None:
    open_catalogue(page, live_server)

    family = style_of(page.locator("body"), "fontFamily")

    assert font_families(family) == UI_FONT_STACK


def test_ac4_room_body_background_is_white(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    assert_colour(colour_of(page.locator("body"), "backgroundColor"), WHITE)


def test_ac4_room_body_text_is_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    assert_colour(colour_of(page.locator("body"), "color"), INK)


def test_ac4_room_body_font_family_is_the_ui_stack(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    family = style_of(page.locator("body"), "fontFamily")

    assert font_families(family) == UI_FONT_STACK


def test_ac4_a_probe_with_the_clue_font_token_reads_the_clue_stack(
    page: Page, live_server: str
) -> None:
    open_catalogue(page, live_server)
    probe = add_probe(
        page,
        "clue-font",
        '<div style="font-family: var(--nock-font-clue)">Passoire fine</div>',
    )

    family = style_of(probe, "fontFamily")

    assert font_families(family) == CLUE_FONT_STACK
