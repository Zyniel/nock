"""Tests of spec 011, AC-2: the share link opens the room on phone and desktop.

Browser tests with a live server, in a phone context and in a desktop context.
The shared setup is in `spec011_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from spec011_harness import (
    EnterRoom,
    build_catalogue,
    grid_from_text,
    open_fx01_room,
)

PHONE_VIEWPORT = {"width": 360, "height": 740}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue with FX-01 as published entry 2 and as unpublished entry 4.

    The conftest `live_server` serves this catalogue, so keep the fixture even in
    a file whose tests never name it.
    """
    return build_catalogue(fx01_grid)


# ---- AC-2: browser, phone and desktop ---------------------------------------


@pytest.fixture(params=["phone", "desktop"])
def device_page(
    request: pytest.FixtureRequest, browser: Browser, browser_name: str
) -> Iterator[Page]:
    """A page in the phone context, then in the desktop context."""
    if request.param == "desktop":
        context = browser.new_context(viewport=DESKTOP_VIEWPORT)
    elif browser_name == "firefox":
        context = browser.new_context(viewport=PHONE_VIEWPORT, has_touch=True)
    else:
        context = browser.new_context(
            viewport=PHONE_VIEWPORT, has_touch=True, is_mobile=True
        )
    try:
        yield context.new_page()
    finally:
        context.close()


def test_ac2_browser_link_opens_the_room_on_the_grid(
    device_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)

    enter_room(device_page, f"{live_server}/r/{code}")

    room = device_page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-grid", "5x5")
    grid = device_page.get_by_test_id("grid")
    expect(grid).to_be_visible()
    expect(grid.get_by_test_id("cell")).to_have_count(25)


def test_ac2_browser_share_link_opens_in_a_second_context(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
    link = page.get_by_test_id("share-link").get_attribute("href")
    assert link is not None
    friend_context = browser.new_context(viewport=PHONE_VIEWPORT)
    try:
        friend_page = friend_context.new_page()

        enter_room(friend_page, link, nickname="Bob")

        friend_room = friend_page.get_by_test_id("room-page")
        expect(friend_room).to_have_attribute("data-status", "joined")
        expect(friend_room).to_have_attribute("data-grid", "5x5")
    finally:
        friend_context.close()
