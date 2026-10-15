"""Tests of spec 006, AC-5: the pages are responsive from 320 px to desktop.

The catalogue page and a room page on FX-02 are opened at the eight window sizes of
the spec. The shared setup is in `spec006_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.server import RoomRegistry
from spec006_harness import WINDOW_SIZES, box_of, grid_from_text, open_room


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


# ---- AC-5: responsive from 320 px to desktop ---------------------------------


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_catalogue_page_has_no_horizontal_scroll(
    page: Page, live_server: str, width: int, height: int
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-page")).to_be_visible()

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_has_no_horizontal_scroll(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx02_grid)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollWidth, window.innerWidth]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_has_a_usable_grid_viewport(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    viewport = open_room(page, live_server, room_registry, fx02_grid)

    window_width = page.evaluate("() => window.innerWidth")
    box = box_of(viewport)
    assert box["x"] >= -1
    assert box["x"] + box["width"] <= window_width + 1
    assert box["width"] >= 100
    assert box["height"] >= 100


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac5_room_page_shows_at_least_one_cell_inside_the_window(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx02_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx02_grid)

    cells_inside = page.evaluate("""() => {
          let inside = 0;
          for (const e of document.querySelectorAll('[data-testid="cell"]')) {
            const b = e.getBoundingClientRect();
            if (b.width > 0 && b.height > 0 && b.left >= 0 && b.top >= 0
                && b.right <= window.innerWidth && b.bottom <= window.innerHeight) {
              inside += 1;
            }
          }
          return inside;
        }""")

    assert cells_inside >= 1
