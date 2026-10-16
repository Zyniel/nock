"""Tests of spec 032 in browsers on the live server: AC-3 and AC-5.

AC-3: Ana's page (context 1) types `T` then `A` from (1, 0) across and is closed;
a page in context 2, with empty storage, opens the room's link, enters as Bob and
shows both letters. AC-5: Ana starts FX-01 from the catalogue (spec 010), with
`Ana` as the nickname her browser remembers (spec 012's case b), and types `T` at
(1, 0); Bob joins her room from his own context; Ana's context then opens `/`:
"My rooms" lists her room, with grid 1 and both nicknames, and its link brings her
back into the room as the same player, without the nickname form.

The live server serves spec 010's catalogue, FX-01 as published entry 1. The
shared setup is in `spec032_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from spec010_harness import (
    EnterRoom,
    catalogue_from_grid,
    cell_at,
    expect_joined,
    start_from_catalogue,
)
from spec017_harness import expect_cell
from spec032_harness import (
    FORM_WATCHER,
    PARIS,
    WAIT_TIMEOUT_MS,
    expect_my_rooms_ready,
    grid_from_text,
    my_room_items,
    seed_storage,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The catalogue the live server serves: FX-01 as published entry 1."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def two_contexts(browser: Browser) -> Iterator[tuple[BrowserContext, BrowserContext]]:
    """Two browser contexts, each with its own storage, in Paris time."""
    first = browser.new_context(timezone_id=PARIS)
    second = browser.new_context(timezone_id=PARIS)
    yield first, second
    second.close()
    first.close()


# ---- AC-3: another device sees the letters of a closed page --------------------


def test_ac3_browser_another_context_shows_the_letters_of_a_closed_page(
    two_contexts: tuple[BrowserContext, BrowserContext],
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    first_context, second_context = two_contexts
    code = room_registry.register_room(fx01_grid)
    link = f"{live_server}/r/{code}"
    first = first_context.new_page()
    enter_room(first, link, "Ana")
    cell_at(first, 1, 0).click()
    first.keyboard.press("t")
    first.keyboard.press("a")
    expect_cell(first, 1, 0, "T", unconfirmed=False)
    expect_cell(first, 1, 1, "A", unconfirmed=False)
    first.close()

    second = second_context.new_page()
    enter_room(second, link, "Bob")

    expect(cell_at(second, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(second, 1, 1)).to_have_attribute("data-letter", "A")


# ---- AC-5: "My rooms" of a room started from the catalogue ---------------------


def start_and_share(
    ana_page: Page, bob_page: Page, live_server: str, enter_room: EnterRoom
) -> tuple[str, str]:
    """Ana starts FX-01 and types `T`; Bob joins. Return the code and Ana's id."""
    seed_storage(ana_page, {"nock.nickname": "Ana"})
    code = start_from_catalogue(ana_page, live_server)
    ana_room = expect_joined(ana_page)
    ana_id = ana_room.get_attribute("data-you")
    assert ana_id
    cell_at(ana_page, 1, 0).click()
    ana_page.keyboard.press("t")
    expect_cell(ana_page, 1, 0, "T", unconfirmed=False)
    enter_room(bob_page, f"{live_server}/r/{code}", "Bob")
    expect(ana_page.get_by_test_id("roster-player")).to_have_count(2)
    return code, ana_id


def test_ac5_live_my_rooms_lists_the_room_with_its_grid_and_players(
    two_contexts: tuple[BrowserContext, BrowserContext],
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    ana_context, bob_context = two_contexts
    ana_page = ana_context.new_page()
    bob_page = bob_context.new_page()
    code, _ = start_and_share(ana_page, bob_page, live_server, enter_room)

    ana_page.goto(f"{live_server}/")

    expect_my_rooms_ready(ana_page, 1)
    item = my_room_items(ana_page)
    expect(item).to_have_attribute("data-code", code)
    expect(item).to_have_attribute("data-grid", "1")
    expect(item.get_by_test_id("my-room-players")).to_have_text("Joueurs : Ana, Bob")


def test_ac5_live_the_link_of_my_rooms_brings_the_player_back_without_the_form(
    two_contexts: tuple[BrowserContext, BrowserContext],
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    ana_context, bob_context = two_contexts
    ana_page = ana_context.new_page()
    bob_page = bob_context.new_page()
    code, ana_id = start_and_share(ana_page, bob_page, live_server, enter_room)
    ana_page.goto(f"{live_server}/")
    expect_my_rooms_ready(ana_page, 1)
    ana_page.add_init_script(FORM_WATCHER)

    my_room_items(ana_page).get_by_test_id("my-room-link").click()

    ana_page.wait_for_url(f"{live_server}/r/{code}", timeout=WAIT_TIMEOUT_MS)
    room = ana_page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined", timeout=WAIT_TIMEOUT_MS)
    expect(room).to_have_attribute("data-you", ana_id)
    assert ana_page.evaluate("window.__formSeen") is False
    expect(ana_page.get_by_test_id("nickname-form")).to_have_count(0)
