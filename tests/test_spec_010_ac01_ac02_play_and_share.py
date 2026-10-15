"""Tests of spec 010, AC-1 and AC-2: the play button and the shared room.

AC-1: one tap on the catalogue starts a joined solo room, and the ways it can
fail. AC-2: a second player joins that room and sees the letters. The shared
setup is in `spec010_harness`.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from playwright.sync_api import Browser, Page, Request, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from spec010_harness import (
    PROGRESS_KEY,
    ROOM_URL_PATTERN,
    URL_TIMEOUT_MS,
    EnterRoom,
    catalogue_from_grid,
    cell_at,
    expect_joined,
    grid_from_text,
    item_play_button,
    load_fr,
    read_json_object,
    read_storage,
    settle,
    start_from_catalogue,
    tap,
)

BREAK_STORAGE_SCRIPT = (
    "Storage.prototype.setItem = function () {"
    " throw new DOMException('quota', 'QuotaExceededError'); };"
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1, force 2."""
    return catalogue_from_grid(fx01_grid)


class RequestCounter:
    """Counts the room creation requests a page sends."""

    def __init__(self, page: Page) -> None:
        self.count = 0
        page.on("request", self._on_request)

    def _on_request(self, request: Request) -> None:
        if request.method == "POST" and request.url.endswith("/api/rooms"):
            self.count += 1


def fail_creation_with_500(route: Route) -> None:
    route.fulfill(status=500, content_type="application/json", body="{}")


def fail_creation_with_500_and_code(route: Route) -> None:
    route.fulfill(
        status=500, content_type="application/json", body='{"code": "ABC123"}'
    )


def fail_creation_with_409_and_code(route: Route) -> None:
    route.fulfill(
        status=409, content_type="application/json", body='{"code": "ABC123"}'
    )


def fail_creation_by_abort(route: Route) -> None:
    route.abort()


# ---- AC-1: one tap starts a joined room --------------------------------------


def test_ac1_play_button_is_on_the_catalogue_item_with_its_label(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    button = item_play_button(page)
    expect(button).to_have_count(1)
    expect(button).to_have_text(load_fr()["catalogue.play"])
    expect(button).to_be_enabled()


def test_ac1_play_button_is_on_the_grid_page_too(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/g/1")

    button = page.get_by_test_id("catalogue-item").get_by_test_id("catalogue-play")
    expect(button).to_have_count(1)
    expect(button).to_have_text(load_fr()["catalogue.play"])


def test_ac1_one_click_leads_to_a_joined_room_with_the_grid(
    page: Page, live_server: str
) -> None:
    start_from_catalogue(page, live_server)

    room = expect_joined(page)
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("nickname-input")).to_have_count(0)


def test_ac1_one_click_on_the_grid_page_leads_to_a_joined_room(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/g/1")
    page.get_by_test_id("catalogue-play").click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)

    room = expect_joined(page)
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("nickname-input")).to_have_count(0)


def test_ac1_the_new_room_exists_on_the_server(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    code = start_from_catalogue(page, live_server)

    expect_joined(page)
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1


def test_ac1_typing_in_the_new_room_shows_the_letter(
    page: Page, live_server: str
) -> None:
    start_from_catalogue(page, live_server)
    expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)

    tap(page, 1, 0)
    page.keyboard.press("t")

    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")


@pytest.mark.parametrize(
    "handler",
    [
        fail_creation_with_500,
        fail_creation_with_500_and_code,
        fail_creation_with_409_and_code,
        fail_creation_by_abort,
    ],
    ids=["500", "500-with-code", "409-with-code", "abort"],
)
def test_ac1_creation_failure_stays_on_the_page_and_shows_the_error(
    page: Page, live_server: str, handler: Callable[[Route], None]
) -> None:
    page.route("**/api/rooms", handler)
    page.goto(f"{live_server}/")
    button = item_play_button(page)

    button.click()

    error = page.get_by_test_id("catalogue-error")
    expect(error).to_have_text(load_fr()["catalogue.play_failed"])
    expect(button).to_be_enabled()
    settle(page)
    assert page.url == f"{live_server}/"
    progress = read_json_object(page, PROGRESS_KEY)
    assert progress == {"1": "started"}


def test_ac1_after_a_failure_the_next_tap_works(page: Page, live_server: str) -> None:
    page.route("**/api/rooms", fail_creation_with_500)
    page.goto(f"{live_server}/")
    item_play_button(page).click()
    expect(page.get_by_test_id("catalogue-error")).to_have_text(
        load_fr()["catalogue.play_failed"]
    )

    page.unroute("**/api/rooms")
    item_play_button(page).click()

    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    expect_joined(page)


def test_ac1_a_double_tap_sends_one_creation_request(
    page: Page, live_server: str
) -> None:
    counter = RequestCounter(page)
    page.goto(f"{live_server}/")

    item_play_button(page).dblclick()

    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    expect_joined(page)
    assert counter.count == 1


def test_ac1_replaying_a_grid_creates_a_new_room_each_time(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    first_code = start_from_catalogue(page, live_server)
    expect_joined(page)

    second_code = start_from_catalogue(page, live_server)

    expect_joined(page)
    assert second_code != first_code
    assert room_registry.room_state(first_code) is not None
    assert room_registry.room_state(second_code) is not None


def test_ac1_storage_that_refuses_writes_still_creates_and_loads_the_room(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    page.context.add_init_script(BREAK_STORAGE_SCRIPT)

    code = start_from_catalogue(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname", timeout=URL_TIMEOUT_MS)
    assert room_registry.room_state(code) is not None
    assert read_storage(page, PROGRESS_KEY) is None


def test_ac1_fr_json_has_the_play_texts() -> None:
    fr = load_fr()

    assert fr["catalogue.play"] == "Jouer"
    assert fr["catalogue.play_failed"] == "Impossible de lancer la partie. Réessayez."
    assert fr["room.default_nickname"] == "Invité"


# ---- AC-2: a solo room becomes shared, letters kept --------------------------


def test_ac2_a_second_player_joins_the_solo_room_and_sees_the_letters(
    page: Page,
    browser: Browser,
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    code = start_from_catalogue(page, live_server)
    room = expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    tap(page, 1, 0)
    page.keyboard.press("t")
    page.keyboard.press("a")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    page.evaluate("window.soloMarker = 'still here'")
    friend_context = browser.new_context()
    try:
        friend_page = friend_context.new_page()

        enter_room(friend_page, page.url, nickname="Bob")

        friend_room = friend_page.get_by_test_id("room-page")
        expect(friend_room).to_have_attribute("data-status", "joined")
        expect(cell_at(friend_page, 1, 0)).to_have_attribute("data-letter", "T")
        expect(cell_at(friend_page, 1, 1)).to_have_attribute("data-letter", "A")
        expect(page.get_by_test_id("roster-player")).to_have_count(2)
        expect(room).to_have_attribute("data-room-code", code)
        expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
        expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
        assert page.evaluate("window.soloMarker") == "still here"
        assert page.url.endswith(f"/r/{code}")
    finally:
        friend_context.close()
