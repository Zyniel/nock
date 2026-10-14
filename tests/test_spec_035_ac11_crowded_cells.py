"""Tests of spec 035: the "+N" rule for crowded cells (AC-11).

The setup the test files of spec 035 share is in `tests/spec035_harness.py`.

Choices where the spec leaves room:

- AC-11, a cell just above 20 px: the layout rules hold for every cell of 20 px or
  more. Besides the spec's examples, one test runs them on the first letter cell
  of FX-02 at 320 px wide and the lowest window height that makes its side more
  than 20 px (it must stay below 20.6 px), where the two diagonal labels have the
  least room.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, FloatRect, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction, PlayerState, PlayerView, Selection
from spec035_harness import (
    EPSILON,
    FX01_CLUES,
    LANGUAGE_SCAN_SCRIPT,
    ROOM_CODE,
    Cell,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    contrast_offenders,
    open_room,
    page_factory,
    player_view,
    remote_initials,
    selection_frame,
    unknown_texts,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    yield from page_factory(browser)


# ---- AC-11: the "+N" rule for crowded cells -----------------------------------------

FX02_PATH = Path(__file__).parent / "fixtures" / "fx02.json"
CORNER_ORDER = ["top-left", "bottom-right", "top-right", "bottom-left"]
MIN_LABEL_FONT_PX = 7.0
CORNER_TOLERANCE_PX = 3.0
CURSOR_NICKNAMES = [
    "Jean-Luc",
    "Ana",
    "zoé",
    "Wanda Moreau",
    "Max",
    "Lou Ann",
    "Ned Orr",
]
CURSOR_INITIALS = ["JL", "AN", "ZO", "WM", "MA", "LA", "NO"]

LABELS_SCRIPT = """
cell => {
  const found = [];
  const selector = '[data-testid="remote-initials"], [data-testid="remote-overflow"]';
  for (const label of cell.querySelectorAll(selector)) {
    const box = label.getBoundingClientRect();
    const style = getComputedStyle(label);
    found.push({
      kind: label.getAttribute('data-testid'),
      text: label.textContent.trim(),
      corner: label.getAttribute('data-corner'),
      count: label.getAttribute('data-count'),
      ariaHidden: label.getAttribute('aria-hidden'),
      insideSelection: label.closest('[data-testid="remote-selection"]') !== null,
      fontSize: parseFloat(style.fontSize),
      visibility: style.visibility,
      left: box.left, top: box.top, right: box.right, bottom: box.bottom,
    });
  }
  return found;
}
"""


class Label(NamedTuple):
    """A `remote-initials` or `remote-overflow` element as the page draws it."""

    kind: str
    text: str
    corner: str | None
    count: str | None
    aria_hidden: str | None
    inside_selection: bool
    font_size: float
    visibility: str
    left: float
    top: float
    right: float
    bottom: float


def fx02_letter_cells() -> list[Cell]:
    """The letter cells of FX-02 in row-major order, read from the fixture."""
    grid = json.loads(FX02_PATH.read_text(encoding="utf-8"))
    cells = [cell for cell in grid["cells"] if cell["type"] == "letter"]
    cells.sort(key=lambda cell: (cell["row"], cell["column"]))
    return [(cell["row"], cell["column"]) for cell in cells]


def labels_of(page: Page, row: int, column: int) -> list[Label]:
    raw_labels = cell_at(page, row, column).evaluate(LABELS_SCRIPT)
    labels: list[Label] = []
    for raw in raw_labels:
        labels.append(
            Label(
                kind=raw["kind"],
                text=raw["text"],
                corner=raw["corner"],
                count=raw["count"],
                aria_hidden=raw["ariaHidden"],
                inside_selection=raw["insideSelection"],
                font_size=raw["fontSize"],
                visibility=raw["visibility"],
                left=raw["left"],
                top=raw["top"],
                right=raw["right"],
                bottom=raw["bottom"],
            )
        )
    return labels


def cell_side(page: Page, row: int, column: int) -> float:
    box = cell_at(page, row, column).bounding_box()
    assert box is not None
    return box["width"]


def assert_cell_tier(
    page: Page, row: int, column: int, at_least: float, below: float | None
) -> None:
    """Fail with the measured side when the cell is not in the expected tier."""
    side = cell_side(page, row, column)
    in_tier = side >= at_least and (below is None or side < below)
    assert in_tier, (
        f"cell ({row}, {column}) side is {side}px, expected at least {at_least}px"
        f" and below {below}px: the layout changed, revisit this example"
    )


def overlap(first: Label, second: Label) -> tuple[float, float]:
    width = min(first.right, second.right) - max(first.left, second.left)
    height = min(first.bottom, second.bottom) - max(first.top, second.top)
    return width, height


def corner_gap(label: Label, cell: FloatRect) -> tuple[float, float]:
    """Distance on both axes between the label's corner and the cell's corner."""
    corner = label.corner
    assert corner is not None
    if corner.endswith("left"):
        gap_x = label.left - cell["x"]
    else:
        gap_x = (cell["x"] + cell["width"]) - label.right
    if corner.startswith("top"):
        gap_y = label.top - cell["y"]
    else:
        gap_y = (cell["y"] + cell["height"]) - label.bottom
    return gap_x, gap_y


def assert_label_layout(page: Page, row: int, column: int) -> None:
    """Check the layout rules of "Initials on a crowded cell" for one cell."""
    cell_box = cell_at(page, row, column).bounding_box()
    assert cell_box is not None
    labels = labels_of(page, row, column)
    for label in labels:
        assert label.left >= cell_box["x"] - EPSILON, label
        assert label.top >= cell_box["y"] - EPSILON, label
        assert label.right <= cell_box["x"] + cell_box["width"] + EPSILON, label
        assert label.bottom <= cell_box["y"] + cell_box["height"] + EPSILON, label
        gap_x, gap_y = corner_gap(label, cell_box)
        assert abs(gap_x) <= CORNER_TOLERANCE_PX, (label, gap_x)
        assert abs(gap_y) <= CORNER_TOLERANCE_PX, (label, gap_y)
        assert label.font_size >= MIN_LABEL_FONT_PX, label
        assert label.visibility == "visible", label
    for first_index, first in enumerate(labels):
        for second in labels[first_index + 1 :]:
            width, height = overlap(first, second)
            assert width <= EPSILON or height <= EPSILON, (first, second)


def assert_slots(
    page: Page,
    row: int,
    column: int,
    initials: dict[str, str],
    overflow: tuple[str, int] | None,
) -> None:
    """Check the labels of a cell: initials by corner and the overflow label.

    Args:
        page: The room page.
        row: Row of the cell.
        column: Column of the cell.
        initials: Expected text of each `remote-initials`, by corner name.
        overflow: Expected corner and count `k` of the overflow label, or None
            when the cell holds no overflow label at all.
    """
    labels = labels_of(page, row, column)
    shown_initials: dict[str, str] = {}
    overflows: list[Label] = []
    for label in labels:
        if label.kind == "remote-initials":
            assert label.corner is not None, label
            shown_initials[label.corner] = label.text
        else:
            overflows.append(label)
    initials_count = len([label for label in labels if label.kind == "remote-initials"])
    assert initials_count == len(initials), labels
    assert shown_initials == initials, labels

    hidden_label = cell_at(page, row, column).get_by_test_id("remote-overflow-label")
    if overflow is None:
        assert overflows == [], labels
        expect(hidden_label).to_have_count(0)
        return
    corner, count = overflow
    assert len(overflows) == 1, labels
    only = overflows[0]
    assert only.corner == corner, only
    assert only.count == str(count), only
    assert only.text == f"+{count}", only
    assert only.aria_hidden == "true", only
    assert not only.inside_selection, only
    expect(hidden_label).to_have_count(1)
    expect(hidden_label).to_have_text(f"{count} autres joueurs")
    expect(hidden_label).to_have_class(re.compile(r"\bvisually-hidden\b"))


def cursors_on(cell: Cell, count: int, first_id: int = 2) -> list[PlayerView]:
    """The `p1` (`you`) player followed by `count` cursors all on `cell`."""
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for index in range(count):
        selection = Selection(row=cell[0], column=cell[1], direction=Direction.ACROSS)
        players.append(
            player_view(
                f"p{first_id + index}",
                CURSOR_NICKNAMES[index],
                (index + 1) % 8,
                selection=selection,
            )
        )
    return players


def initials_by_corner(texts: list[str], corners: list[str]) -> dict[str, str]:
    return dict(zip(corners, texts, strict=True))


FX01_CROWDED: Cell = (2, 2)
# (cursors, initials shown, overflow count) on a cell of 44 px or more: 4 slots.
LARGE_CELL_CASES = [
    (1, 1, 0),
    (2, 2, 0),
    (3, 3, 0),
    (4, 4, 0),
    (5, 3, 2),
    (6, 3, 3),
    (7, 3, 4),
]
# On a cell from 20 px to 44 px: 2 slots.
SMALL_CELL_CASES = [(1, 1, 0), (2, 2, 0), (3, 1, 2), (4, 1, 3), (7, 1, 6)]


def expected_slots(
    initials_shown: int, overflow_count: int, slots: list[str], offset: int = 0
) -> tuple[dict[str, str], tuple[str, int] | None]:
    """Expected initials by corner and overflow for a case of the spec's tables."""
    texts = CURSOR_INITIALS[offset : offset + initials_shown]
    corners = slots[:initials_shown]
    overflow = None
    if overflow_count > 0:
        overflow = (slots[-1], overflow_count)
    return initials_by_corner(texts, corners), overflow


@pytest.mark.parametrize(("cursors", "shown", "hidden"), LARGE_CELL_CASES)
def test_ac11_a_large_cell_has_four_slots(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    cursors: int,
    shown: int,
    hidden: int,
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, cursors)
    open_room(page, live_server, fx01_grid, players=players)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(
        cursors
    )
    assert_cell_tier(page, 2, 2, 44, None)

    initials, overflow = expected_slots(shown, hidden, CORNER_ORDER)
    assert_slots(page, 2, 2, initials, overflow)
    assert_label_layout(page, 2, 2)


def test_ac11_the_players_without_a_label_hold_no_initials(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)

    selections = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(selections).to_have_count(5)
    with_initials = 0
    without_initials = 0
    for index in range(5):
        found = selections.nth(index).get_by_test_id("remote-initials").count()
        assert found in (0, 1), index
        if found == 1:
            with_initials += 1
        else:
            without_initials += 1
    assert (with_initials, without_initials) == (3, 2)
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN", "ZO"])


def test_ac11_a_cursor_leaving_a_crowded_cell_frees_a_slot_for_the_next(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    mock = open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-overflow")).to_have_count(1)

    mock.send(selection_frame("p6", 3, 1, Direction.ACROSS))

    expect(remote_initials(page, 2, 2)).to_have_count(4)
    initials = {
        "top-left": "JL",
        "bottom-right": "AN",
        "top-right": "ZO",
        "bottom-left": "WM",
    }
    assert_slots(page, 2, 2, initials, None)
    assert_label_layout(page, 2, 2)
    assert_slots(page, 3, 1, {"top-left": "MA"}, None)
    assert_label_layout(page, 3, 1)


def test_ac11_a_disconnected_player_is_not_counted(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    players[5] = players[5].model_copy(update={"state": PlayerState.DISCONNECTED})
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(4)
    initials = {
        "top-left": "JL",
        "bottom-right": "AN",
        "top-right": "ZO",
        "bottom-left": "WM",
    }
    assert_slots(page, 2, 2, initials, None)


@pytest.mark.parametrize(("cursors", "shown", "hidden"), SMALL_CELL_CASES)
def test_ac11_a_small_cell_has_two_slots(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx02_text: str,
    cursors: int,
    shown: int,
    hidden: int,
) -> None:
    page = new_page(360, 740)
    first_cell = fx02_letter_cells()[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    players = cursors_on(first_cell, cursors)
    open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 20, 44)

    initials, overflow = expected_slots(shown, hidden, CORNER_ORDER[:2])
    assert_slots(page, row, column, initials, overflow)
    assert_label_layout(page, row, column)


def test_ac11_a_small_cell_shows_two_initials_when_the_third_cursor_leaves(
    new_page: Callable[[int, int], Page], live_server: str, fx02_text: str
) -> None:
    page = new_page(360, 740)
    cells = fx02_letter_cells()
    first_cell = cells[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    # Jean-Luc, Ana and Wanda Moreau join in that order and all select the cell.
    players = cursors_on(first_cell, 3)
    players[3] = players[3].model_copy(update={"nickname": "Wanda Moreau"})
    mock = open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 20, 44)
    assert_slots(page, row, column, {"top-left": "JL"}, ("bottom-right", 2))
    assert_label_layout(page, row, column)

    other = cells[1]
    mock.send(selection_frame("p2", other[0], other[1], Direction.ACROSS))

    expect(remote_initials(page, row, column)).to_have_text(["AN", "WM"])
    assert_slots(page, row, column, {"top-left": "AN", "bottom-right": "WM"}, None)
    assert_label_layout(page, row, column)


# A cell just above 20 px: the smallest cells of the two-slot tier, where the two
# labels in diagonal corners, one above the other, have the least room. At 320 px
# wide the FX-02 grid fits the window's height there, but each engine needs its own
# height (today about 565 px in Chromium and 588 px in WebKit). So the test looks
# for the lowest window height that makes the cell side more than 20 px.
TWO_SLOT_TIER_PX = 20.0
JUST_ABOVE_TIER_PX = 20.6
SEARCH_WIDTH = 320
LOWEST_SEARCH_HEIGHT = 520  # taller than the low layout of 500 px
HIGHEST_SEARCH_HEIGHT = 900
JUST_ABOVE_CASES = [(2, 2, 0), (3, 1, 2)]  # (cursors, initials shown, overflow k)
# Resolves with the cell side once it has stood still for three animation frames:
# after a resize, the page measures its viewport again and redraws the grid.
SETTLED_SIDE_SCRIPT = """
cell => new Promise(resolve => {
  let previous = -1;
  let stillFrames = 0;
  let frames = 0;
  const look = () => {
    const side = cell.getBoundingClientRect().width;
    stillFrames = side === previous ? stillFrames + 1 : 0;
    previous = side;
    frames += 1;
    if (stillFrames >= 3 || frames >= 120) {
      resolve(side);
    } else {
      requestAnimationFrame(look);
    }
  };
  requestAnimationFrame(look);
})
"""


def side_at_height(page: Page, cell: Cell, height: int) -> float:
    """Resize the window to `height` and return the cell side once it settled.

    Args:
        page: The room page. Its window keeps the search width.
        cell: Row and column of the cell to measure.
        height: The new window height in CSS px.

    Returns:
        The width of the cell's bounding box.
    """
    page.set_viewport_size({"width": SEARCH_WIDTH, "height": height})
    cell_at(page, cell[0], cell[1]).evaluate(SETTLED_SIDE_SCRIPT)
    return cell_side(page, cell[0], cell[1])


def lowest_height_above_the_tier(page: Page, cell: Cell) -> int:
    """Return the lowest window height that makes the cell side more than 20 px.

    A taller window never gives a smaller cell, so the search halves the range
    between a height whose cell is 20 px or less and one whose cell is larger.

    Args:
        page: The room page.
        cell: Row and column of the cell to measure.

    Returns:
        The window height in CSS px, at the search width.
    """
    low = LOWEST_SEARCH_HEIGHT
    high = HIGHEST_SEARCH_HEIGHT
    low_side = side_at_height(page, cell, low)
    high_side = side_at_height(page, cell, high)
    assert low_side <= TWO_SLOT_TIER_PX < high_side, (
        f"the cell side is {low_side}px at {SEARCH_WIDTH}x{low} and {high_side}px"
        f" at {SEARCH_WIDTH}x{high}: the layout changed, revisit this example"
    )
    while high - low > 1:
        middle = (low + high) // 2
        if side_at_height(page, cell, middle) > TWO_SLOT_TIER_PX:
            high = middle
        else:
            low = middle
    return high


@pytest.mark.parametrize(
    ("cursors", "shown", "hidden"),
    JUST_ABOVE_CASES,
    ids=["two_initials", "initials_and_overflow"],
)
def test_ac11_the_labels_do_not_overlap_on_a_cell_just_above_20_px(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx02_text: str,
    cursors: int,
    shown: int,
    hidden: int,
) -> None:
    page = new_page(SEARCH_WIDTH, LOWEST_SEARCH_HEIGHT)
    first_cell = fx02_letter_cells()[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    open_room(
        page,
        live_server,
        fx02_grid,
        players=cursors_on(first_cell, cursors),
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    height = lowest_height_above_the_tier(page, first_cell)
    side = side_at_height(page, first_cell, height)
    row, column = first_cell
    assert TWO_SLOT_TIER_PX < side < JUST_ABOVE_TIER_PX, (
        f"cell ({row}, {column}) side is {side}px at {SEARCH_WIDTH}x{height},"
        f" expected above {TWO_SLOT_TIER_PX}px and below {JUST_ABOVE_TIER_PX}px:"
        " the layout changed, revisit this example"
    )

    initials, overflow = expected_slots(shown, hidden, CORNER_ORDER[:2])
    assert_slots(page, row, column, initials, overflow)
    assert_label_layout(page, row, column)


@pytest.mark.parametrize("cursors", [1, 2, 3, 7])
def test_ac11_a_tiny_cell_has_one_slot(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx02_text: str,
    cursors: int,
) -> None:
    page = new_page(568, 320)
    first_cell = fx02_letter_cells()[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    players = cursors_on(first_cell, cursors)
    open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 0, 20)

    if cursors == 1:
        assert_slots(page, row, column, {"top-left": "JL"}, None)
    else:
        assert_slots(page, row, column, {}, ("top-left", cursors))


def test_ac11_the_overflow_label_passes_the_language_and_contrast_scans(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-overflow")).to_have_count(1)

    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    assert "+2" in texts
    assert "2 autres joueurs" in texts
    data = {
        "Ana",
        *CURSOR_NICKNAMES,
        *CURSOR_INITIALS,
        *FX01_CLUES,
        ROOM_CODE,
        f"{live_server}/r/{ROOM_CODE}",
    }
    assert unknown_texts(texts, data) == []
    assert contrast_offenders(page) == []
