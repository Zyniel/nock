"""Tests of spec 013, AC-6: the roster and the feed keep the grid's room.

The page is tested at several window sizes, with a mouse and with a touch screen.
The shared setup is in `spec013_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from nock.protocol import GridTarget, PlayerView
from spec013_harness import (
    FEED_LIMIT,
    cell_at,
    check_frame,
    grid_from_text,
    make_page,
    open_room,
    player_view,
)

TAP_TIMEOUT_MS = 3000
MIN_GRID_VIEWPORT_PX = 100.0
EPSILON = 1.0
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-6: the roster and the feed keep the grid's room ----


def eight_players() -> list[PlayerView]:
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for number in range(2, 9):
        players.append(
            player_view(f"p{number}", EIGHT_NICKNAMES[number - 1], number - 1)
        )
    return players


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac6_browser_the_roster_and_the_feed_keep_the_grids_room(
    browser: Browser,
    browser_name: str,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page, close = make_page(browser, browser_name, width, height, touch)
    try:
        last_seq = 5 + FEED_LIMIT
        mock = open_room(page, live_server, fx01_grid, eight_players(), seq=5)
        for seq in range(6, last_seq + 1):
            mock.send(check_frame(seq, "p2", GridTarget()))
        expect(page.get_by_test_id("room-page")).to_have_attribute(
            "data-seq", str(last_seq)
        )

        cell = cell_at(page, 3, 1)
        if touch:
            cell.tap(timeout=TAP_TIMEOUT_MS)
        else:
            cell.click(timeout=TAP_TIMEOUT_MS)

        bar = page.get_by_test_id("clue-bar")
        expect(bar).to_have_attribute("data-word", "3,0,0")
        viewport = page.get_by_test_id("grid-viewport")
        viewport_box = viewport.bounding_box()
        bar_box = bar.bounding_box()
        assert viewport_box is not None
        assert bar_box is not None
        sizes = page.evaluate(
            "() => [document.documentElement.scrollWidth, window.innerWidth,"
            " document.documentElement.scrollHeight, window.innerHeight]"
        )
        scroll_width, window_width, scroll_height, window_height = sizes

        assert viewport_box["height"] >= MIN_GRID_VIEWPORT_PX
        assert scroll_width <= window_width
        assert scroll_height <= window_height
        expect(viewport).to_have_attribute("data-zoom", "1")
        grid_box = page.get_by_test_id("grid").bounding_box()
        assert grid_box is not None
        assert grid_box["x"] >= viewport_box["x"] - EPSILON
        assert grid_box["y"] >= viewport_box["y"] - EPSILON
        grid_right = grid_box["x"] + grid_box["width"]
        grid_bottom = grid_box["y"] + grid_box["height"]
        assert grid_right <= viewport_box["x"] + viewport_box["width"] + EPSILON
        assert grid_bottom <= viewport_box["y"] + viewport_box["height"] + EPSILON
        assert bar_box["x"] >= -EPSILON
        assert bar_box["x"] + bar_box["width"] <= window_width + EPSILON
        assert bar_box["y"] >= -EPSILON
        bar_bottom = bar_box["y"] + bar_box["height"]
        assert bar_bottom <= window_height + EPSILON
        if touch:
            keyboard_box = page.get_by_test_id("keyboard").bounding_box()
            assert keyboard_box is not None
            assert bar_bottom <= keyboard_box["y"] + EPSILON
            keyboard_bottom = keyboard_box["y"] + keyboard_box["height"]
            assert keyboard_bottom <= window_height + EPSILON
    finally:
        close()
