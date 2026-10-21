"""Tests of spec 034, AC-2 and AC-4, with two browsers on the live server.

Ana and Bob join a FX-01 room registered on the live server. Ana types `T` at
(1, 0); once her page shows it confirmed (so her stored `seen_seq` holds its
seq), her page is closed; her context, and so its storage, stays. Bob types
`VIDE` from (2, 1) across (and, for AC-4, checks the word). Ana then opens the
room again in a new page of her context. The shared setup is in
`spec034_harness`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Protocol

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from spec034_harness import (
    catch_up_marks,
    cell_at,
    feed_item_locator,
    feed_items,
    grid_from_text,
    room_page,
)

FEED_LIST_SELECTOR = '[data-testid="activity-feed"] ul'
ITEMS_IN_VIEW_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  const listBox = list.getBoundingClientRect();
  const found = [];
  for (const item of list.querySelectorAll('[data-testid="feed-item"]')) {
    const box = item.getBoundingClientRect();
    const overlap = Math.min(box.bottom, listBox.bottom)
      - Math.max(box.top, listBox.top);
    found.push(overlap > 1);
  }
  return found;
}
"""
VIDE_CELLS = [(2, 1), (2, 2), (2, 3), (2, 4)]


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def new_context(browser: Browser) -> Iterator[Callable[[], BrowserContext]]:
    """Open browser contexts on demand (1280 by 720); close them all afterwards."""
    contexts: list[BrowserContext] = []

    def open_context() -> BrowserContext:
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        contexts.append(context)
        return context

    yield open_context
    for context in contexts:
        context.close()


def expect_confirmed_letter(page: Page, row: int, column: int, letter: str) -> None:
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def play_while_ana_is_away(
    new_context: Callable[[], BrowserContext],
    url: str,
    enter_room: EnterRoom,
    bob_checks: bool,
) -> Page:
    """Run the play of AC-2 (and AC-4 with `bob_checks`); return Ana's new page."""
    ana_context = new_context()
    bob_context = new_context()
    ana_page = ana_context.new_page()
    bob_page = bob_context.new_page()
    enter_room(ana_page, url, "Ana")
    enter_room(bob_page, url, "Bob")

    cell_at(ana_page, 1, 0).click()
    ana_page.keyboard.press("t")
    expect_confirmed_letter(ana_page, 1, 0, "T")
    ana_page.close()

    cell_at(bob_page, 2, 1).click()
    for letter in "vide":
        bob_page.keyboard.press(letter)
    expect_confirmed_letter(bob_page, 2, 4, "E")
    if bob_checks:
        bob_page.get_by_test_id("check-word").click()
        expect(feed_item_locator(bob_page).last).to_have_text("Bob a vérifié un mot")

    back_page = ana_context.new_page()
    back_page.goto(url)
    expect(room_page(back_page)).to_have_attribute("data-status", "joined")
    return back_page


def test_ac2_live_ana_comes_back_to_the_cells_bob_changed(
    new_context: Callable[[], BrowserContext],
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"

    page = play_while_ana_is_away(new_context, url, enter_room, bob_checks=False)

    for row, column in VIDE_CELLS:
        cell = cell_at(page, row, column)
        expect(cell).to_have_attribute("data-caught-up", "true")
        expect(cell.get_by_test_id("catch-up-mark")).to_have_count(1)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-caught-up", "false")
    expect(catch_up_marks(page)).to_have_count(4)


def test_ac4_live_anas_feed_ends_with_bobs_word_then_his_check_in_view(
    new_context: Callable[[], BrowserContext],
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"

    page = play_while_ana_is_away(new_context, url, enter_room, bob_checks=True)

    expect(feed_item_locator(page).last).to_have_text("Bob a vérifié un mot")
    texts = [text for _, _, text in feed_items(page)]
    assert texts[-2:] == ["Bob a complété « Sans contenu »", "Bob a vérifié un mot"]
    in_view = page.evaluate(ITEMS_IN_VIEW_SCRIPT, FEED_LIST_SELECTOR)
    assert in_view[-1] is True, "the newest feed item is not in view"
