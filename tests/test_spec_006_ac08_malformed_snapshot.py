"""Tests of spec 006, AC-8: a malformed grid in a snapshot is ignored.

The page is tested with spec 040's mocked socket and snapshot frames broken one rule
at a time. The shared setup is in `spec006_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import GridView, grid_view
from spec006_harness import (
    SETTLE_MS,
    cell_at,
    grid_from_text,
    open_mock_room,
    show_snapshot,
    snapshot_frame,
    with_letter_cells,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-8: a malformed grid in a snapshot is ignored --------------------------

MALFORMED_KINDS = ["duplicate_position", "out_of_range_row", "out_of_range_column"]
MALFORMED_KINDS += ["missing_cell", "extra_cell"]


def malformed_frame(view: GridView, seq: int, kind: str) -> str:
    """A snapshot frame whose grid breaks one rule; it also changes cell (1, 1)."""
    changed = with_letter_cells(view, [(1, 1, {"letter": "Q"})])
    data = json.loads(snapshot_frame(changed, seq))
    cells = data["grid"]["cells"]
    if kind == "duplicate_position":
        cells[1] = dict(cells[0])
    elif kind == "out_of_range_row":
        cells[-1]["row"] = 5
    elif kind == "out_of_range_column":
        cells[-1]["column"] = 5
    elif kind == "missing_cell":
        cells.pop()
    elif kind == "extra_cell":
        cells.append(dict(cells[-1]))
    else:
        pytest.fail(f"unknown kind {kind}")
    return json.dumps(data)


@pytest.mark.parametrize("kind", MALFORMED_KINDS)
def test_ac8_a_malformed_grid_is_ignored_and_the_previous_grid_is_kept(
    page: Page, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    errors: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    mock = open_mock_room(page, live_server)
    first_view = with_letter_cells(grid_view(fx01_grid), [(1, 0, {"letter": "T"})])
    show_snapshot(page, mock, first_view, 0)

    mock.send(malformed_frame(grid_view(fx01_grid), 1, kind))
    page.wait_for_timeout(SETTLE_MS)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "0")
    expect(room).to_have_attribute("data-status", "joined")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    expect(page.locator('[data-testid="cell"][data-type="clue"]')).to_have_count(7)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-width", "5")
    assert errors == []


@pytest.mark.parametrize("kind", MALFORMED_KINDS)
def test_ac8_a_valid_snapshot_sent_after_a_malformed_one_is_shown(
    page: Page, live_server: str, fx01_grid: Grid, kind: str
) -> None:
    mock = open_mock_room(page, live_server)
    show_snapshot(page, mock, grid_view(fx01_grid), 0)
    mock.send(malformed_frame(grid_view(fx01_grid), 1, kind))
    page.wait_for_timeout(SETTLE_MS)
    next_view = with_letter_cells(grid_view(fx01_grid), [(1, 2, {"letter": "M"})])

    show_snapshot(page, mock, next_view, 2)

    expect(cell_at(page, 1, 2)).to_have_attribute("data-letter", "M")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    expect(page.get_by_test_id("cell")).to_have_count(25)
