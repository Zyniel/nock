"""Tests of spec 019, AC-1's box run: box rules, letter and drawing order.

In the desktop context, with the switch on, on four mocked pages: FX-01 at 1280 by
720 (the snapshot of AC-1 with `p3` to `p6` added, colours 1, 2, 4 and 5, and `p2`
to `p6` selecting (1, 0) `across`), and FX-02 at 320 by 568, at 568 by 320 and at
296 by 640 (spec 026's `FX02_FULL_WRONG` snapshot without its feed items or tap,
its row 1 letters by `p9` instead of `p2`, and `p2` to `p6` selecting (1, 6)
`down`). Each test opens one page and checks, together:

- every `author-mark` against the box rules of "The view, switch on", held to the
  rule of its own cell's measured side (20 px or more, or smaller);
- every band's top at or below its letter's baseline (1 px tolerance), measured
  with the probe the spec describes, which must move the letter's `Range` box by
  at most 0.5 px;
- at 568 by 320, that FX-02's cells are under 20 px, so the small-cell rule is the
  one tested there (the spec says so, after spec 035 AC-11);
- at 296 by 640, that FX-02's cells measure 20 to 21 px (the width of their
  bounding box), asserted before the box rules and the drawing order, so that the
  page keeps testing the cells closest to the letter rule's limit; the bands are
  then held to the full rules of a cell of 20 px or more;
- the drawing order on the cell with the five outlines: `elementFromPoint` along
  the band's middle line finds the corner labels inside their boxes and the band
  everywhere else, never a `remote-selection`.

Choices where the spec leaves room:

- "The measured side of a letter cell" is read on every cell that holds a band
  (on that page, every letter cell); the smallest and the largest side must both
  lie in [20, 21] px, with no tolerance, as the spec writes the interval.

- The letter's text node is the first text node of the cell whose trimmed text is
  the cell's `data-letter`, outside the mark, the outlines and their labels.
- "Every 2 px from 1 px inside its left end to 1 px inside its right end" includes
  the last point, 1 px inside the right end.
- The probe is given `margin`, `padding` and `border` 0 as well, so that it stays
  the zero-size box the spec describes whatever the page's styles for `span`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, GridView, Selection
from spec019_harness import (
    FX02_CELL_COUNT,
    MIN_SIDE_FOR_BOX_RULES_PX,
    Box,
    Cell,
    ChangeList,
    OpenWindow,
    ac1_players,
    ac1_view,
    cell_at,
    eight_players,
    fx02_full_wrong_view,
    grid_from_text,
    letter_positions_of,
    mark_box_problems,
    open_room,
    player_view,
    turn_switch_on,
    window_opener,
    with_letter_cells,
    with_selection,
)

BASELINE_TOLERANCE_PX = 1.0
PROBE_SHIFT_MAX_PX = 0.5
SMALL_CELL_WINDOW = (568, 320)
# The window where FX-02's cells measure 20 to 21 px, and the range their side
# must lie in.
CLOSE_TO_LIMIT_WINDOW = (296, 640)
CLOSE_TO_LIMIT_SIDE_MIN_PX = 20.0
CLOSE_TO_LIMIT_SIDE_MAX_PX = 21.0

SELECTORS = ["p2", "p3", "p4", "p5", "p6"]
FX01_CROWDED: Cell = (1, 0)
FX02_CROWDED: Cell = (1, 6)
FX01_MARKED_CELLS = 4  # (1, 0) to (1, 3) in the snapshot of AC-1

BOX_PAGES = [
    ("fx01", 1280, 720),
    ("fx02", 320, 568),
    ("fx02", 568, 320),
    ("fx02", 296, 640),
]
BOX_PAGE_IDS = [f"{name}-{width}x{height}" for name, width, height in BOX_PAGES]

# For every cell holding an `author-mark`: its box, its marks' count and first
# box, and its letter's baseline, read with the probe of "The view, switch on".
BOX_RUN_SCRIPT = r"""
() => {
  const SKIPPED_TEST_IDS = [
    'author-mark', 'remote-selection', 'remote-initials', 'remote-overflow',
    'remote-overflow-label', 'reveal-mark', 'reveal-label',
  ];
  const edges = box => [box.left, box.top, box.right, box.bottom];
  const letterTextNode = cell => {
    const letter = cell.getAttribute('data-letter');
    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
      if (node.textContent.trim() !== letter) {
        continue;
      }
      let skipped = false;
      for (let element = node.parentElement; element !== null && element !== cell;
           element = element.parentElement) {
        if (SKIPPED_TEST_IDS.includes(element.getAttribute('data-testid'))) {
          skipped = true;
        }
      }
      if (!skipped) {
        return node;
      }
    }
    return null;
  };
  const rangeBox = node => {
    const range = document.createRange();
    range.selectNodeContents(node);
    return edges(range.getBoundingClientRect());
  };
  const letterBaseline = cell => {
    const textNode = letterTextNode(cell);
    if (textNode === null) {
      return {baseline: null, shift: null};
    }
    const before = rangeBox(textNode);
    const parent = textNode.parentNode;
    const display = getComputedStyle(parent).display;
    const probe = document.createElement('span');
    probe.style.display = 'inline-block';
    probe.style.width = '0';
    probe.style.height = '0';
    probe.style.verticalAlign = 'baseline';
    probe.style.margin = '0';
    probe.style.padding = '0';
    probe.style.border = '0';
    let wrapper = null;
    if (display.includes('flex') || display.includes('grid')) {
      wrapper = document.createElement('span');
      parent.insertBefore(wrapper, textNode);
      wrapper.appendChild(textNode);
      wrapper.appendChild(probe);
    } else {
      parent.insertBefore(probe, textNode.nextSibling);
    }
    const after = rangeBox(textNode);
    const baseline = probe.getBoundingClientRect().top;
    probe.remove();
    if (wrapper !== null) {
      parent.insertBefore(textNode, wrapper);
      wrapper.remove();
    }
    let shift = 0;
    for (let index = 0; index < 4; index += 1) {
      shift = Math.max(shift, Math.abs(after[index] - before[index]));
    }
    return {baseline: baseline, shift: shift};
  };
  const found = [];
  for (const cell of document.querySelectorAll('[data-testid="cell"]')) {
    const marks = cell.querySelectorAll('[data-testid="author-mark"]');
    if (marks.length === 0) {
      continue;
    }
    const letter = letterBaseline(cell);
    found.push({
      row: Number(cell.dataset.row), column: Number(cell.dataset.column),
      marks: marks.length,
      cell: edges(cell.getBoundingClientRect()),
      mark: edges(marks[0].getBoundingClientRect()),
      baseline: letter.baseline, shift: letter.shift,
    });
  }
  return found;
}
"""

# The measured side (the width of the bounding box) of every cell holding an
# `author-mark`, for the page that must keep cells of 20 to 21 px.
CELL_SIDES_SCRIPT = r"""
() => {
  const sides = [];
  for (const cell of document.querySelectorAll('[data-testid="cell"]')) {
    if (cell.querySelector('[data-testid="author-mark"]') !== null) {
      sides.push(cell.getBoundingClientRect().width);
    }
  }
  return sides;
}
"""

# The drawing order on one cell, after `scrollIntoView`:`elementFromPoint` along
# the band's middle line, with `pointer-events: auto !important` on every
# descendant of every cell. Points within 1 px of a label's box are not judged, as
# the spec says; on a small cell that can be every point (at 568 by 320 today the
# band's middle line runs within 1 px of the bottom edge of the cell's label).
DRAWING_ORDER_SCRIPT = r"""
([row, column]) => {
  const cell = document.querySelector(
    `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`
  );
  cell.scrollIntoView();
  const style = document.createElement('style');
  style.textContent = '[data-testid="cell"] * { pointer-events: auto !important; }';
  document.head.appendChild(style);
  const describe = element => {
    if (element === null) {
      return 'nothing';
    }
    const testId = element.getAttribute('data-testid');
    return testId === null ? `${element.tagName} ${element.className}` : testId;
  };
  try {
    const mark = cell.querySelector('[data-testid="author-mark"]');
    if (mark === null) {
      return {points: 0, judged: 0, wrong: ['the cell holds no author-mark']};
    }
    const labels = Array.from(cell.querySelectorAll(
      '[data-testid="remote-initials"], [data-testid="remote-overflow"]'
    ));
    const labelBoxes = labels.map(label => label.getBoundingClientRect());
    const box = mark.getBoundingClientRect();
    const y = box.top + box.height / 2;
    const xs = [];
    for (let x = box.left + 1; x <= box.right - 1; x += 2) {
      xs.push(x);
    }
    if (xs.length === 0 || xs[xs.length - 1] < box.right - 1) {
      xs.push(box.right - 1);
    }
    const wrong = [];
    let judged = 0;
    for (const x of xs) {
      const found = document.elementFromPoint(x, y);
      const insideLabels = [];
      let outsideAll = true;
      labels.forEach((label, index) => {
        const labelBox = labelBoxes[index];
        if (x > labelBox.left + 1 && x < labelBox.right - 1
            && y > labelBox.top + 1 && y < labelBox.bottom - 1) {
          insideLabels.push(label);
        }
        if (!(x < labelBox.left - 1 || x > labelBox.right + 1
              || y < labelBox.top - 1 || y > labelBox.bottom + 1)) {
          outsideAll = false;
        }
      });
      let right = true;
      if (insideLabels.length > 0) {
        right = found !== null && insideLabels.some(label => label.contains(found));
      } else if (outsideAll) {
        right = found !== null && mark.contains(found);
      } else {
        continue;
      }
      judged += 1;
      if (!right) {
        wrong.push(`(${x.toFixed(1)}, ${y.toFixed(1)}) finds ${describe(found)}`);
      }
    }
    return {points: xs.length, judged: judged, wrong: wrong};
  } finally {
    style.remove();
  }
}
"""


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Helpers of these tests -------------------------------------------------


def open_fx01_box_page(page: Page, base_url: str, grid: Grid) -> None:
    """The snapshot of AC-1 with `p3` to `p6`, and `p2` to `p6` on (1, 0)."""
    players = ac1_players()
    players.append(player_view("p3", "Cleo", 1))
    players.append(player_view("p4", "Dan", 2))
    players.append(player_view("p5", "Eve", 4))
    players.append(player_view("p6", "Fay", 5))
    selection = Selection(row=1, column=0, direction=Direction.ACROSS)
    open_room(
        page, base_url, ac1_view(grid), with_selection(players, SELECTORS, selection)
    )


def fx02_box_view(grid: Grid) -> GridView:
    """`FX02_FULL_WRONG` whose letter cells of row 1 are by `p9` instead."""
    changes: ChangeList = []
    for row, column in letter_positions_of(grid):
        if row == 1:
            changes.append((row, column, {"author": "p9"}))
    return with_letter_cells(fx02_full_wrong_view(grid), changes)


def open_fx02_box_page(page: Page, base_url: str, grid: Grid) -> None:
    """The FX-02 page of the box run, with `p2` to `p6` on (1, 6) `down`."""
    selection = Selection(row=1, column=6, direction=Direction.DOWN)
    players = with_selection(eight_players(), SELECTORS, selection)
    open_room(page, base_url, fx02_box_view(grid), players, cell_count=FX02_CELL_COUNT)


def box_run_problems(
    page: Page, expected_cells: int, small_cells_expected: bool
) -> list[str]:
    """The box rules and the letter rule on every band of the page."""
    found = page.evaluate(BOX_RUN_SCRIPT)
    problems: list[str] = []
    if len(found) != expected_cells:
        problems.append(f"{len(found)} cells hold a band, not {expected_cells}")
    for item in found:
        where = f"({item['row']}, {item['column']})"
        cell_box = Box(*item["cell"])
        mark_box = Box(*item["mark"])
        side = cell_box.right - cell_box.left
        if item["marks"] != 1:
            problems.append(f"{where}: {item['marks']} author-mark elements")
        for problem in mark_box_problems(cell_box, mark_box):
            problems.append(f"{where} ({side:.1f} px): {problem}")
        if small_cells_expected and side >= MIN_SIDE_FOR_BOX_RULES_PX:
            problems.append(f"{where}: the cell is {side:.1f} px, not under 20 px")
        problems.extend(baseline_problems(f"{where} ({side:.2f} px)", mark_box, item))
    return problems


def cell_side_problems(page: Page) -> list[str]:
    """How the cells' measured side is outside 20 to 21 px (empty: none)."""
    sides: list[float] = page.evaluate(CELL_SIDES_SCRIPT)
    if not sides:
        return ["no cell holds a band, so no cell side was measured"]
    smallest = min(sides)
    largest = max(sides)
    if smallest < CLOSE_TO_LIMIT_SIDE_MIN_PX or largest > CLOSE_TO_LIMIT_SIDE_MAX_PX:
        return [
            f"the cells measure {smallest:.2f} to {largest:.2f} px, not "
            f"{CLOSE_TO_LIMIT_SIDE_MIN_PX:.0f} to {CLOSE_TO_LIMIT_SIDE_MAX_PX:.0f} px"
        ]
    return []


def baseline_problems(where: str, mark_box: Box, item: dict[str, object]) -> list[str]:
    """The letter rule: the band's top at or below the letter's baseline.

    Args:
        where: The cell, for the messages.
        mark_box: The band's box.
        item: The cell's reading from BOX_RUN_SCRIPT, with `baseline` (the probe's
            top, or None when no text node holds the letter) and `shift` (how far
            the probe moved the letter's `Range` box).

    Returns:
        One line per broken rule.
    """
    baseline = item["baseline"]
    shift = item["shift"]
    if not isinstance(baseline, float | int) or not isinstance(shift, float | int):
        return [f"{where}: no text node holds the letter"]
    problems: list[str] = []
    if shift > PROBE_SHIFT_MAX_PX:
        problems.append(f"{where}: the probe moved the letter by {shift:.2f} px")
    if mark_box.top < baseline - BASELINE_TOLERANCE_PX:
        problems.append(
            f"{where}: the band's top {mark_box.top:.2f} is above the letter's "
            f"baseline {baseline:.2f}"
        )
    return problems


def drawing_order_problems(page: Page, cell: Cell) -> list[str]:
    """The drawing order on the cell with the five outlines."""
    found = page.evaluate(DRAWING_ORDER_SCRIPT, list(cell))
    problems: list[str] = []
    for wrong in found["wrong"]:
        problems.append(f"drawing order on {cell}: {wrong}")
    return problems


# ---- AC-1: the box run ------------------------------------------------------


@pytest.mark.parametrize(("grid_name", "width", "height"), BOX_PAGES, ids=BOX_PAGE_IDS)
def test_ac1_every_band_meets_the_box_rules_and_the_drawing_order(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    fx02_grid: Grid,
    grid_name: str,
    width: int,
    height: int,
) -> None:
    page = window(width, height, False)
    if grid_name == "fx01":
        open_fx01_box_page(page, live_server, fx01_grid)
        crowded = FX01_CROWDED
        expected_cells = FX01_MARKED_CELLS
    else:
        open_fx02_box_page(page, live_server, fx02_grid)
        crowded = FX02_CROWDED
        expected_cells = len(letter_positions_of(fx02_grid))
    crowded_cell = cell_at(page, *crowded)
    expect(crowded_cell.get_by_test_id("remote-selection")).to_have_count(5)

    turn_switch_on(page)

    expect(page.get_by_test_id("author-mark")).to_have_count(expected_cells)
    if (width, height) == CLOSE_TO_LIMIT_WINDOW:
        side_problems = cell_side_problems(page)
        assert side_problems == [], f"{grid_name} at {width}x{height}: {side_problems}"
    small_cells_expected = (width, height) == SMALL_CELL_WINDOW
    problems = box_run_problems(page, expected_cells, small_cells_expected)
    problems.extend(drawing_order_problems(page, crowded))
    assert problems == [], f"{grid_name} at {width}x{height}: {problems}"
