"""Tests of spec 034, AC-2: on a return, the changed cells are highlighted.

Browser with the mocked socket and the mocked catch-up: the cells' attribute,
the ring's look ("Applying a catch-up" step 2), the marks drawn over it and the
cell still taking clicks and letters. The timing of the highlight (still on at
4.5 s, gone at 6 s) is in `test_spec_034_ac02_highlight_timing.py`, which runs in
the serial pass. The shared setup is in `spec034_harness`.

Spec 042 (the design's grid cells) refines AC-2: the other players' cursors are
corner triangles with no initials, so the hit test is on `p2`'s triangle, at the
point 1.5 px inside both edges of the inner box's corner that holds it (inside the
ring's band and the triangle), in place of the centre of its initials.
"""

from __future__ import annotations

from typing import Any

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, Selection
from spec034_harness import (
    BOB,
    COLOUR_CONTRAST_JS,
    CatchUpRoute,
    catch_up_json,
    caught_up_values,
    cell_at,
    expect_catch_up_applied,
    expected_caught_up,
    grid_from_text,
    marks_by_cell,
    open_mocked_room,
    record_with,
    snapshot_players,
)

HIGHLIGHTED = [(1, 0), (2, 2)]
BOB_ON_2_2 = Selection(row=2, column=2, direction=Direction.ACROSS)
BOX_TOLERANCE_PX = 1.0
MIN_RING_PX = 3.0
MIN_RING_CONTRAST = 3.0

# The ring of a cell, as step 2 of "Applying a catch-up" measures it: the
# `catch-up-mark` elements of the cell and, for the first one, its box and the
# cell's, its `aria-hidden` and computed `pointer-events`, and per side its
# computed border style, width and colour, with the contrast of that colour
# against the cell's computed background (that background first composited over
# white, the border colour, when it has alpha, then composited over that
# background: the note of 2026-10-21 on step 2).
RING_SCRIPT = "cell => {\n" + COLOUR_CONTRAST_JS + r"""
  const marks = cell.querySelectorAll('[data-testid="catch-up-mark"]');
  const result = {marks: marks.length};
  if (marks.length === 0) {
    return result;
  }
  const mark = marks[0];
  const style = getComputedStyle(mark);
  const cellBox = cell.getBoundingClientRect();
  const markBox = mark.getBoundingClientRect();
  const background = over(
    parseColour(getComputedStyle(cell).backgroundColor), WHITE
  );
  result.cell = [cellBox.left, cellBox.top, cellBox.right, cellBox.bottom];
  result.mark = [markBox.left, markBox.top, markBox.right, markBox.bottom];
  result.ariaHidden = mark.getAttribute('aria-hidden');
  result.pointerEvents = style.pointerEvents;
  result.sides = [];
  for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
    const colour = style['border' + side + 'Color'];
    result.sides.push({
      side: side,
      style: style['border' + side + 'Style'],
      width: parseFloat(style['border' + side + 'Width']),
      colour: colour,
      ratio: contrast(over(parseColour(colour), background), background),
    });
  }
  return result;
}
"""

# The drawing order on the cell, as spec 019 AC-1's tests read it: after
# `scrollIntoView`, a test style sets `pointer-events: auto !important` on every
# descendant of every cell (hit testing follows the drawing order but skips an
# element with `pointer-events: none`, such as the ring), then
# `document.elementFromPoint` at the point 1.5 px inside both edges of the inner
# box's corner (the cell's box less its 1 px right and bottom grid lines) that
# holds `p2`'s triangle (spec 042) must give that `remote-selection` or an element
# inside it, never the `catch-up-mark`. The point is checked to lie inside the
# ring's band (3 px) and inside the triangle (`dx + dy < t - 1.5`, `t` the
# triangle's side, spec 042's "Test harness") before the hit. The style is
# removed afterwards.
# `cell-selection` (my selection border, spec 042 AC-17) keeps its own
# `pointer-events: none`: it is drawn over the triangles by design, so a probe in
# its 2 px band would return it.
TRIANGLE_HIT_SCRIPT = r"""
cell => {
  const triangle = cell.querySelector(
    '[data-testid="remote-selection"][data-player-id="p2"]'
  );
  if (triangle === null) {
    return {found: false};
  }
  cell.scrollIntoView();
  // A constructed stylesheet: the page's Content-Security-Policy blocks an
  // inline `<style>` element, not the CSSOM.
  const sheet = new CSSStyleSheet();
  sheet.replaceSync('[data-testid="cell"] *:not([data-testid="cell-selection"])'
    + ' { pointer-events: auto !important; }');
  document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet];
  try {
    const corner = triangle.getAttribute('data-corner') || '';
    const cellBox = cell.getBoundingClientRect();
    const left = cellBox.left;
    const top = cellBox.top;
    const right = cellBox.right - 1;
    const bottom = cellBox.bottom - 1;
    const x = corner.endsWith('left') ? left + 1.5 : right - 1.5;
    const y = corner.startsWith('top') ? top + 1.5 : bottom - 1.5;
    const side = triangle.getBoundingClientRect().width;
    const hit = document.elementFromPoint(x, y);
    return {
      found: true,
      corner: corner,
      insideTriangle: 1.5 + 1.5 < side - 1.5,
      hits: hit !== null && triangle.contains(hit),
      hitsMark: hit !== null && hit.closest('[data-testid="catch-up-mark"]') !== null,
      hit: hit === null ? null : hit.outerHTML.slice(0, 200),
    };
  } finally {
    document.adoptedStyleSheets = document.adoptedStyleSheets.filter(
      adopted => adopted !== sheet
    );
  }
}
"""


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def return_page(page: Page, live_server: str, fx01_grid: Grid) -> Page:
    """AC-2's return: `seen_seq` 5, a snapshot at 9, cells (1, 0) and (2, 2).

    `p2` selects (2, 2) across in the snapshot. Each test first waits for
    `data-catch-up="5-9"` (`wait_for_the_highlight`), so that a page that never
    applies the catch-up fails the test, not its setup.
    """
    route = CatchUpRoute(answer=catch_up_json(5, 9, cells=HIGHLIGHTED))
    open_mocked_room(
        page,
        live_server,
        fx01_grid,
        route,
        record=record_with(5),
        seq=9,
        players=snapshot_players(bob_selection=BOB_ON_2_2),
    )
    return page


def wait_for_the_highlight(page: Page) -> None:
    expect_catch_up_applied(page, "5-9")


def read_ring(cell: Locator) -> dict[str, Any]:
    """Measure the `catch-up-mark` of a cell (a JSON object from the page)."""
    reading = cell.evaluate(RING_SCRIPT)
    assert isinstance(reading, dict)
    return reading


def ring_problems(cell: Locator) -> list[str]:
    """How the cell's `catch-up-mark` breaks step 2 of "Applying a catch-up"."""
    reading = read_ring(cell)
    if reading["marks"] != 1:
        return [f"{reading['marks']} catch-up-mark elements in the cell"]
    problems: list[str] = []
    if reading["ariaHidden"] != "true":
        problems.append(f"aria-hidden is {reading['ariaHidden']!r}")
    if reading["pointerEvents"] != "none":
        problems.append(f"pointer-events is {reading['pointerEvents']!r}")
    for cell_edge, mark_edge in zip(reading["cell"], reading["mark"], strict=True):
        if abs(cell_edge - mark_edge) > BOX_TOLERANCE_PX:
            problems.append(f"mark box {reading['mark']} is not the cell's box")
            break
    for side in reading["sides"]:
        if side["style"] != "solid":
            problems.append(f"{side['side']} border style is {side['style']!r}")
        if side["width"] < MIN_RING_PX:
            problems.append(f"{side['side']} border width is {side['width']} px")
        if side["ratio"] < MIN_RING_CONTRAST:
            problems.append(
                f"{side['side']} border colour {side['colour']} has a contrast"
                f" of {side['ratio']:.2f} with the cell's background"
            )
    return problems


def test_ac2_letter_cells_are_not_caught_up_from_their_first_render(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route = CatchUpRoute()
    open_mocked_room(page, live_server, fx01_grid, route, record=record_with(5), seq=5)

    assert caught_up_values(page) == expected_caught_up([])
    assert marks_by_cell(page) == {}


def test_ac2_a_return_highlights_exactly_the_changed_cells(
    return_page: Page,
) -> None:
    wait_for_the_highlight(return_page)
    page = return_page

    assert caught_up_values(page) == expected_caught_up(HIGHLIGHTED)
    assert marks_by_cell(page) == {(1, 0): 1, (2, 2): 1}


@pytest.mark.parametrize("cell", HIGHLIGHTED, ids=["1-0", "2-2"])
def test_ac2_the_mark_is_a_solid_ring_on_the_cells_edge(
    return_page: Page, cell: tuple[int, int]
) -> None:
    wait_for_the_highlight(return_page)
    row, column = cell

    assert ring_problems(cell_at(return_page, row, column)) == []


def test_ac2_the_other_players_triangle_stays_visible_over_the_ring(
    return_page: Page,
) -> None:
    wait_for_the_highlight(return_page)
    cell = cell_at(return_page, 2, 2)
    outline = cell.locator(f'[data-testid="remote-selection"][data-player-id="{BOB}"]')

    # Spec 042: the cursor is a corner triangle; its initials are gone.
    expect(outline).to_be_visible()
    expect(outline).to_have_attribute("data-shape", "triangle")


def test_ac2_a_click_on_a_highlighted_cell_selects_it(
    return_page: Page,
) -> None:
    wait_for_the_highlight(return_page)
    cell = cell_at(return_page, 2, 2)

    cell.click()

    expect(cell).to_have_attribute("data-selected", "true")


def test_ac2_the_triangle_is_drawn_over_the_ring(return_page: Page) -> None:
    wait_for_the_highlight(return_page)
    cell = cell_at(return_page, 2, 2)
    # The spec's order: the click and the step 2 checks first, since the test
    # style of the hit test changes the computed `pointer-events` they read.
    cell.click()
    expect(cell).to_have_attribute("data-selected", "true")
    assert ring_problems(cell) == []

    hit = cell.evaluate(TRIANGLE_HIT_SCRIPT)

    assert hit["found"] is True, "no remote-selection of p2 on (2, 2)"
    assert hit["corner"] in ("top-left", "top-right", "bottom-right", "bottom-left")
    if not hit["insideTriangle"]:
        pytest.fail(f"the point is not inside p2's triangle: {hit}")
    assert hit["hitsMark"] is False, f"elementFromPoint found the ring: {hit['hit']}"
    assert hit["hits"] is True, f"elementFromPoint found {hit['hit']}"


def test_ac2_typing_in_a_highlighted_cell_keeps_its_highlight(
    return_page: Page,
) -> None:
    wait_for_the_highlight(return_page)
    # Edge case "Highlight while the player types": the 5,000 ms run on.
    cell = cell_at(return_page, 1, 0)

    cell.click()
    return_page.keyboard.press("t")

    expect(cell).to_have_attribute("data-letter", "T")
    expect(cell).to_have_attribute("data-caught-up", "true")
    assert marks_by_cell(return_page)[(1, 0)] == 1
