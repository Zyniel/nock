"""Tests of spec 006, AC-7: the room page fits the window.

A fresh FX-01 room is opened at the eight window sizes of AC-5: the viewport, the
page and every cell must lie inside the window. The shared setup is in
`spec006_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.server import RoomRegistry
from spec006_harness import WINDOW_SIZES, box_of, grid_from_text, open_room


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-7: the room page fits the window -------------------------------------

CELLS_OUTSIDE_SCRIPT = """() => {
  const outside = [];
  for (const e of document.querySelectorAll('[data-testid="cell"]')) {
    const b = e.getBoundingClientRect();
    const inside = b.left >= -1 && b.top >= -1
      && b.right <= window.innerWidth + 1 && b.bottom <= window.innerHeight + 1;
    if (!inside) outside.push(e.dataset.row + ',' + e.dataset.column);
  }
  return outside;
}"""


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_viewport_is_inside_the_window_vertically(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    viewport = open_room(page, live_server, room_registry, fx01_grid)

    expect(viewport).to_have_attribute("data-zoom", "1")
    window_height = page.evaluate("() => window.innerHeight")
    box = box_of(viewport)
    assert box["y"] >= -1
    assert box["y"] + box["height"] <= window_height + 1


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_room_page_has_no_vertical_scroll(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx01_grid)

    sizes = page.evaluate(
        "() => [document.documentElement.scrollHeight, window.innerHeight]"
    )

    assert sizes[0] <= sizes[1]


@pytest.mark.parametrize(
    ("width", "height"), WINDOW_SIZES, ids=[f"{w}x{h}" for w, h in WINDOW_SIZES]
)
def test_ac7_every_cell_is_inside_the_window(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page.set_viewport_size({"width": width, "height": height})
    open_room(page, live_server, room_registry, fx01_grid)

    expect(page.get_by_test_id("cell")).to_have_count(25)
    assert page.evaluate(CELLS_OUTSIDE_SCRIPT) == []
