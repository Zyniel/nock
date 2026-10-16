"""Tests of spec 013, AC-6: the roster and the feed keep the grid's room.

The page is tested at several window sizes, with a mouse and with a touch screen:
with 100 feed items and a tapped cell, the grid keeps its room; and, without a
tap, the first three feed lines never move `grid-viewport`, and the feed list is
as tall with 3 items as with 100 ("Client: feed height"). The second check runs
all its item counts on one page per window size and context, to keep the run
short. The shared setup is in `spec013_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import GridTarget, PlayerView
from spec013_harness import (
    FEED_LIMIT,
    MockRoomSocket,
    cell_at,
    check_frame,
    feed_locator,
    grid_from_text,
    make_page,
    open_room,
    player_view,
    settle,
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
# The feed height check runs at 1280 by 720 and at spec 006 AC-5's eight sizes.
FEED_HEIGHT_SIZES = [(1280, 720), *WINDOW_SIZES]
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
SNAPSHOT_SEQ = 5
SHORT_FEED_LINES = 3
FEED_LIST_SELECTOR = '[data-testid="activity-feed"] ul'

# A bounding box as (x, y, width, height).
Box = tuple[float, float, float, float]


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


# ---- AC-6: feed height ("Client: feed height") ----


def line_frame(seq: int) -> str:
    """The line event of "Feed scroll states": Bob (`p2`) checks the grid."""
    return check_frame(seq, "p2", GridTarget())


def expect_room_seq(page: Page, seq: int) -> None:
    """Wait until `room-page` has `data-seq` `seq` (spec 040), else fail."""
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def viewport_box(page: Page) -> Box:
    """The bounding box of `grid-viewport`."""
    box = page.get_by_test_id("grid-viewport").bounding_box()
    assert box is not None
    return (box["x"], box["y"], box["width"], box["height"])


def feed_list_height(page: Page) -> float:
    """The height of the feed list's bounding box."""
    box = page.locator(FEED_LIST_SELECTOR).bounding_box()
    assert box is not None
    return box["height"]


def viewport_boxes_with_short_feeds(page: Page, mock: MockRoomSocket) -> list[Box]:
    """The `grid-viewport` box with 0, 1, 2 and 3 feed items.

    The mock sends the line events one at a time, each with the next seq, and the
    box is read once `room-page` has that seq and the feed holds that many items.

    Args:
        page: The room page, with no feed item yet.
        mock: Its mocked socket.

    Returns:
        The boxes, in the order of the item counts 0, 1, 2 and 3.
    """
    feed = feed_locator(page)
    expect(feed).to_have_count(0)
    boxes = [viewport_box(page)]
    for item_count in range(1, SHORT_FEED_LINES + 1):
        seq = SNAPSHOT_SEQ + item_count
        mock.send(line_frame(seq))
        expect_room_seq(page, seq)
        expect(feed).to_have_count(item_count)
        boxes.append(viewport_box(page))
    return boxes


def boxes_unlike_the_first(boxes: list[Box]) -> list[str]:
    """The boxes with a value more than EPSILON away from the first box's."""
    first = boxes[0]
    different: list[str] = []
    for item_count, box in enumerate(boxes):
        for index in range(len(first)):
            if abs(box[index] - first[index]) > EPSILON:
                different.append(f"{item_count} items: {box}, 0 items: {first}")
                break
    return different


@pytest.mark.parametrize("context_kind", ["desktop", "touch"])
@pytest.mark.parametrize(
    ("width", "height"),
    FEED_HEIGHT_SIZES,
    ids=[f"{w}x{h}" for w, h in FEED_HEIGHT_SIZES],
)
def test_ac6_browser_new_feed_lines_never_move_the_grid_viewport(
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
        mock = open_room(
            page, live_server, fx01_grid, eight_players(), seq=SNAPSHOT_SEQ
        )
        settle(page)
        boxes = viewport_boxes_with_short_feeds(page, mock)
        short_feed_height = feed_list_height(page)

        last_seq = SNAPSHOT_SEQ + FEED_LIMIT
        for seq in range(SNAPSHOT_SEQ + SHORT_FEED_LINES + 1, last_seq + 1):
            mock.send(line_frame(seq))
        expect_room_seq(page, last_seq)
        expect(feed_locator(page)).to_have_count(FEED_LIMIT)
        full_feed_height = feed_list_height(page)

        assert boxes_unlike_the_first(boxes) == []
        assert abs(full_feed_height - short_feed_height) <= EPSILON, (
            f"feed list {short_feed_height} px with 3 items, "
            f"{full_feed_height} px with {FEED_LIMIT}"
        )
    finally:
        close()
