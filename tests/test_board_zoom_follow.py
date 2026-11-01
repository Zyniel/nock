"""Tests of board AC-23 to AC-29: a zoomed grid follows the selection (rule 3).

The room is spec 042's mocked room (`tests/spec042_harness.py`) on the live
server's client, in spec 019's touch context at 360 by 740 (a phone held
upright, the in-app keyboard showing unless the test hides it). "AC-23's start"
is FX-02 zoomed to 2 by a pinch from 100 to 200 px apart (`spec006_harness`'s
`pinch`, AC-2's), then the viewport scrolled back to the grid's top-left corner,
with nothing selected. At that zoom a FX-02 cell is about 52.75 px and the
viewport about 344 by 478 px.

Choices where the spec leaves room:

- A pinch goes through the Chrome DevTools Protocol, as AC-2's do, and there is
  no other zoom control: every zoomed test runs in Chromium only. AC-26, at zoom
  1, runs in the three engines.
- The viewport is put back at the grid's top-left corner by setting its scroll
  from the test. The rule reads no scroll: a pan and a scroll set by script are
  the same for it.
- Taps on a zoomed grid are touches at the centre of the part of the cell or
  clue that the viewport shows. A locator's own tap first scrolls its element
  into view, which would scroll the viewport under test.
- The least scroll is computed from the boxes before the step: when the margin
  cell (the cell after the selected one, across or down) is not whole in view,
  the scroll moves by what it lacks, so that the viewport's edge ends at the
  margin cell's edge; else it does not move. A scroll position is checked to
  within 1 px: cell edges are fractional while the scroll offset is snapped to
  device pixels. A centring scroll is many pixels away.
- "At once": the scroll is read two animation frames after the step, so an
  animated scroll is caught mid-way.
- "The page unscrolled": the window and every ancestor of the viewport keep a
  scroll of 0 (an element's `scrollIntoView` also scrolls hidden overflows).
- AC-25's cut cell: at 360 px and zoom 2, the viewport's right edge falls
  inside (1, 6), a letter cell of OREILLE; the test finds it from the boxes.
- AC-29's start: OREIL is in the snapshot, (1, 2) to (1, 6), so the page opens
  with nothing selected and the clue tap changes the selected cell.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridView, grid_view
from spec006_harness import pan, pinch
from spec019_harness import OpenWindow, window_opener, with_letter_cells
from spec042_harness import (
    Box,
    box_of,
    cell_at,
    me,
    open_room,
    seed_value,
)
from spec044_harness import KEYBOARD_HIDDEN_KEY, expect_no_keyboard, key_of

PHONE_WIDTH = 360
PHONE_HEIGHT = 740
# Fingers from 100 to 200 px apart double the zoom (rule 3), 100 to 150 px
# multiply it by 1.5.
PINCH_TO_TWO = (100.0, 200.0)
PINCH_TWO_TO_THREE = (100.0, 150.0)
SCROLL_TOLERANCE_PX = 1.0
MAX_PANS = 6

IN_APP_KEYS = "in-app keys"
PHYSICAL_KEYBOARD = "physical keyboard"

# FX-02's OREILLE, « Elle entend les sons » in (1, 1): (1, 2) to (1, 8).
OREILLE = "OREILLE"
OREILLE_ROW = 1
OREILLE_FIRST_COLUMN = 2
OREILLE_LAST_COLUMN = 8
EARS_CLUE = (1, 1, 0)
# « Elle va du genou au pied » (JAMBE, (2, 0) to (6, 0)), clue 1 of (1, 0).
LEG_CLUE = (1, 0, 1)
# ArrowDown from (2, 0): JAMBE's cells, then past the empty (7, 0) and the clue
# cell (8, 0), MONT's (9, 0) to (12, 0).
COLUMN_ZERO_STEPS = [3, 4, 5, 6, 9, 10, 11, 12]
# ECHEC, « Contraire d'une réussite » in (16, 5): (16, 6) to (16, 10).
ECHEC_FIRST = (16, 6)

# Two animation frames: a scroll made at once has happened, an animated one not.
TWO_FRAMES_SCRIPT = (
    "() => new Promise(resolve =>"
    " requestAnimationFrame(() => requestAnimationFrame(() => resolve(null))))"
)
SCROLL_SCRIPT = "element => [element.scrollLeft, element.scrollTop]"
SCROLL_TO_CORNER_SCRIPT = "element => element.scrollTo(0, 0)"
AT_BOTTOM_RIGHT_SCRIPT = (
    "element => element.scrollLeft >= element.scrollWidth - element.clientWidth - 1"
    " && element.scrollTop >= element.scrollHeight - element.clientHeight - 1"
)
# The window and every ancestor of the viewport that is scrolled.
SCROLLED_ANCESTORS_SCRIPT = """
viewport => {
  const scrolled = [];
  if (window.scrollX !== 0 || window.scrollY !== 0) {
    scrolled.push('window ' + window.scrollX + ',' + window.scrollY);
  }
  for (let element = viewport.parentElement; element !== null;
       element = element.parentElement) {
    if (element.scrollLeft !== 0 || element.scrollTop !== 0) {
      const name = element.tagName + '.' + element.className;
      scrolled.push(name + ' ' + element.scrollLeft + ',' + element.scrollTop);
    }
  }
  return scrolled;
}
"""

# ---- Fixtures ---------------------------------------------------------------------


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


# ---- Reading the viewport ---------------------------------------------------------


def viewport_of(page: Page) -> Locator:
    return page.get_by_test_id("grid-viewport")


def read_scroll(viewport: Locator) -> tuple[float, float]:
    """The viewport's scroll, as (left, top)."""
    values = viewport.evaluate(SCROLL_SCRIPT)
    assert isinstance(values, list), values
    return float(values[0]), float(values[1])


def scrolled_ancestors(viewport: Locator) -> list[str]:
    """The window and the viewport's ancestors that are scrolled (empty: none)."""
    scrolled = viewport.evaluate(SCROLLED_ANCESTORS_SCRIPT)
    assert isinstance(scrolled, list), scrolled
    return [str(item) for item in scrolled]


def wait_two_frames(page: Page) -> None:
    page.evaluate(TWO_FRAMES_SCRIPT)


def overlap(first_low: float, first_high: float, low: float, high: float) -> float:
    """The length two intervals share (0 when they are apart)."""
    return max(0.0, min(first_high, high) - max(first_low, low))


def is_out_of_view(cell: Box, view: Box) -> bool:
    """Whether no part of a cell's box is inside the viewport's."""
    across = overlap(cell.left, cell.right, view.left, view.right)
    down = overlap(cell.top, cell.bottom, view.top, view.bottom)
    return across == 0 or down == 0


def is_whole_in_view(cell: Box, view: Box) -> bool:
    return (
        cell.left >= view.left
        and cell.right <= view.right
        and cell.top >= view.top
        and cell.bottom <= view.bottom
    )


def least_scroll(scroll_before: float, margin_edge: float, view_edge: float) -> float:
    """The scroll that brings a margin cell's far edge to the viewport's edge.

    Args:
        scroll_before: The scroll on that axis before the step.
        margin_edge: Where the margin cell's right (or bottom) edge was then.
        view_edge: The viewport's right (or bottom) edge.

    Returns:
        The scroll before when the edge was in view, else that scroll moved by
        what the margin cell lacked.
    """
    shortfall = margin_edge - view_edge
    if shortfall <= 0:
        return scroll_before
    return scroll_before + shortfall


# ---- Selecting and typing ---------------------------------------------------------


def clue_at(page: Page, row: int, column: int, clue_index: int) -> Locator:
    selector = f'[data-testid="clue"][data-clue-index="{clue_index}"]'
    return cell_at(page, row, column).locator(selector)


def tap_shown_part(page: Page, target: Locator) -> None:
    """Touch the centre of the part of a cell or clue that the viewport shows."""
    shown = box_of(target)
    view = box_of(viewport_of(page))
    left = max(shown.left, view.left)
    right = min(shown.right, view.right)
    top = max(shown.top, view.top)
    bottom = min(shown.bottom, view.bottom)
    assert left < right, f"{shown} is not in the viewport {view} across"
    assert top < bottom, f"{shown} is not in the viewport {view} down"
    page.touchscreen.tap((left + right) / 2, (top + bottom) / 2)


def expect_selected(page: Page, row: int, column: int, direction: str) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)


def type_letter(page: Page, letter: str, typing: str) -> None:
    """Type a capital letter with the in-app key or on the focused grid."""
    if typing == IN_APP_KEYS:
        key_of(page, letter).tap()
    else:
        page.keyboard.press(letter.lower())


# ---- Opening the room -------------------------------------------------------------


def open_phone_room(
    window: OpenWindow, base_url: str, view: GridView, *, keyboard_hidden: bool
) -> Page:
    """Open the mocked room on a touch phone held upright, at zoom 1."""
    page = window(PHONE_WIDTH, PHONE_HEIGHT, True)
    if keyboard_hidden:
        seed_value(page, KEYBOARD_HIDDEN_KEY, "true")
    open_room(page, base_url, view, [me()])
    if keyboard_hidden:
        expect_no_keyboard(page)
    expect(viewport_of(page)).to_have_attribute("data-zoom", "1")
    return page


def open_zoomed(
    window: OpenWindow, base_url: str, view: GridView, *, keyboard_hidden: bool
) -> Page:
    """Open the room on a phone, zoom to 2 and scroll back to the top-left corner.

    Returns:
        The page, nothing selected, the viewport's scroll at (0, 0).
    """
    page = open_phone_room(window, base_url, view, keyboard_hidden=keyboard_hidden)
    viewport = viewport_of(page)
    start, end = PINCH_TO_TWO
    pinch(page, viewport, start, end)
    expect(viewport).to_have_attribute("data-zoom", "2")
    viewport.evaluate(SCROLL_TO_CORNER_SCRIPT)
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "")
    return page


def open_ac23_start(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    """AC-23's start: FX-02 zoomed to 2, at the grid's top-left corner."""
    return open_zoomed(window, base_url, grid_view(grid), keyboard_hidden=False)


def pan_to_bottom_right(page: Page, viewport: Locator) -> None:
    """Pan with one finger until the viewport is at the grid's bottom-right corner."""
    for _ in range(MAX_PANS):
        if viewport.evaluate(AT_BOTTOM_RIGHT_SCRIPT):
            return
        pan(page, viewport)
        wait_two_frames(page)
    assert viewport.evaluate(
        AT_BOTTOM_RIGHT_SCRIPT
    ), "the pans did not reach the corner"


# ---- AC-23: typing along an across word scrolls across only -----------------------


@pytest.mark.only_browser("chromium")
@pytest.mark.parametrize("typing", [IN_APP_KEYS, PHYSICAL_KEYBOARD])
def test_ac23_typing_oreille_scrolls_across_only_to_the_cell_after_the_selected_one(
    window: OpenWindow, live_server: str, fx02_grid: Grid, typing: str
) -> None:
    page = open_ac23_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    tap_shown_part(page, clue_at(page, *EARS_CLUE))
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "across")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)

    view = box_of(viewport)
    scrolled_letters: list[str] = []
    for index, letter in enumerate(OREILLE):
        selected_column = min(OREILLE_FIRST_COLUMN + index + 1, OREILLE_LAST_COLUMN)
        margin_cell = cell_at(page, OREILLE_ROW, selected_column + 1)
        left_before, _ = read_scroll(viewport)
        margin_right = box_of(margin_cell).right
        expected_left = least_scroll(left_before, margin_right, view.right)
        if expected_left != left_before:
            scrolled_letters.append(letter)

        type_letter(page, letter, typing)

        expect_selected(page, OREILLE_ROW, selected_column, "across")
        wait_two_frames(page)
        left_after, top_after = read_scroll(viewport)
        assert left_after == pytest.approx(expected_left, abs=SCROLL_TOLERANCE_PX), (
            f"after {letter} at column {selected_column}: scroll {left_after},"
            f" expected {expected_left}"
        )
        assert top_after == 0.0, f"after {letter}: scrolled down to {top_after}"
        assert scrolled_ancestors(viewport) == []

    assert scrolled_letters != [], "no letter needed a scroll: the start changed"
    for index, letter in enumerate(OREILLE):
        cell = cell_at(page, OREILLE_ROW, OREILLE_FIRST_COLUMN + index)
        expect(cell).to_have_attribute("data-letter", letter)


# ---- AC-24: ArrowDown and Shift+Tab scroll the least ------------------------------


@pytest.mark.only_browser("chromium")
def test_ac24_arrow_down_column_zero_scrolls_down_only_one_cell_below_the_selected(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_ac23_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    tap_shown_part(page, clue_at(page, *LEG_CLUE))
    expect_selected(page, 2, 0, "down")

    view = box_of(viewport)
    scrolled_rows: list[int] = []
    for row in COLUMN_ZERO_STEPS:
        _, top_before = read_scroll(viewport)
        margin_bottom = box_of(cell_at(page, row + 1, 0)).bottom
        expected_top = least_scroll(top_before, margin_bottom, view.bottom)
        if expected_top != top_before:
            scrolled_rows.append(row)

        page.keyboard.press("ArrowDown")

        expect_selected(page, row, 0, "down")
        wait_two_frames(page)
        left_after, top_after = read_scroll(viewport)
        assert top_after == pytest.approx(
            expected_top, abs=SCROLL_TOLERANCE_PX
        ), f"on ({row}, 0): scroll down {top_after}, expected {expected_top}"
        assert left_after == 0.0, f"on ({row}, 0): scrolled across to {left_after}"
        assert scrolled_ancestors(viewport) == []

    assert scrolled_rows != [], "no step needed a scroll: the start changed"


@pytest.mark.only_browser("chromium")
def test_ac24_shift_tab_selects_echec_and_scrolls_to_the_grid_bottom_and_shows_16_7(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_ac23_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    grid = page.get_by_test_id("grid")
    view = box_of(viewport)
    grid_bottom_before = box_of(grid).bottom
    margin_right_before = box_of(cell_at(page, 16, 7)).right
    grid.focus()

    page.keyboard.press("Shift+Tab")

    expect_selected(page, *ECHEC_FIRST, "across")
    wait_two_frames(page)
    left_after, top_after = read_scroll(viewport)
    assert top_after == pytest.approx(
        grid_bottom_before - view.bottom, abs=SCROLL_TOLERANCE_PX
    )
    assert box_of(grid).bottom == pytest.approx(view.bottom, abs=SCROLL_TOLERANCE_PX)
    assert left_after == pytest.approx(
        least_scroll(0.0, margin_right_before, view.right), abs=SCROLL_TOLERANCE_PX
    )
    assert left_after > 0.0, "(16, 7) was already whole in view: the start changed"
    assert box_of(cell_at(page, 16, 7)).right == pytest.approx(
        view.right, abs=SCROLL_TOLERANCE_PX
    )
    assert scrolled_ancestors(viewport) == []


# ---- AC-25: a cell already in view, or a tap on a cut cell, scrolls nothing -------


@pytest.mark.only_browser("chromium")
def test_ac25_a_cell_in_view_with_its_margin_and_a_tap_on_a_cut_cell_scroll_nothing(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_ac23_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    view = box_of(viewport)
    tap_shown_part(page, cell_at(page, OREILLE_ROW, OREILLE_FIRST_COLUMN))
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "across")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)
    for row in range(0, 3):
        for column in range(2, 5):
            margin_box = box_of(cell_at(page, row, column))
            assert is_whole_in_view(margin_box, view), f"({row}, {column}) is cut"

    type_letter(page, "O", IN_APP_KEYS)

    expect_selected(page, OREILLE_ROW, 3, "across")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)

    cut_column: int | None = None
    for column in range(fx02_grid.width):
        cell_box = box_of(cell_at(page, OREILLE_ROW, column))
        if cell_box.left < view.right < cell_box.right:
            cut_column = column
    assert cut_column is not None, "the viewport's right edge cuts no cell of row 1"
    cut_cell = cell_at(page, OREILLE_ROW, cut_column)
    expect(cut_cell).to_have_attribute("data-type", "letter")

    tap_shown_part(page, cut_cell)

    expect_selected(page, OREILLE_ROW, cut_column, "across")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)
    assert scrolled_ancestors(viewport) == []


# ---- AC-26: at zoom 1 nothing scrolls ---------------------------------------------


def test_ac26_at_zoom_1_typing_shift_tab_and_arrows_leave_everything_unscrolled(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_phone_room(
        window, live_server, grid_view(fx02_grid), keyboard_hidden=False
    )
    viewport = viewport_of(page)
    clue_at(page, *EARS_CLUE).tap()
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "across")

    for letter in OREILLE:
        type_letter(page, letter, IN_APP_KEYS)
        wait_two_frames(page)
        assert read_scroll(viewport) == (0.0, 0.0), f"after {letter}"
        assert scrolled_ancestors(viewport) == [], f"after {letter}"
    expect_selected(page, OREILLE_ROW, OREILLE_LAST_COLUMN, "across")

    page.keyboard.press("Shift+Tab")
    expect_selected(page, 2, 0, "down")
    wait_two_frames(page)
    assert read_scroll(viewport) == (0.0, 0.0)
    assert scrolled_ancestors(viewport) == []

    for row in COLUMN_ZERO_STEPS:
        page.keyboard.press("ArrowDown")
        expect_selected(page, row, 0, "down")
        wait_two_frames(page)
        assert read_scroll(viewport) == (0.0, 0.0), f"on ({row}, 0)"
        assert scrolled_ancestors(viewport) == [], f"on ({row}, 0)"
    expect(viewport).to_have_attribute("data-zoom", "1")


# ---- AC-27: a viewport under three cells across centres the cell ------------------


@pytest.mark.only_browser("chromium")
def test_ac27_a_viewport_of_two_and_a_half_cells_centres_the_cell_left_to_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_zoomed(window, live_server, grid_view(fx01_grid), keyboard_hidden=True)
    viewport = viewport_of(page)
    view = box_of(viewport)
    cells_across = view.width / box_of(cell_at(page, 2, 2)).width
    assert cells_across == pytest.approx(2.5, abs=0.1), cells_across
    tap_shown_part(page, cell_at(page, 2, 1))
    expect_selected(page, 2, 1, "across")

    page.keyboard.press("ArrowRight")

    expect_selected(page, 2, 2, "across")
    wait_two_frames(page)
    selected_box = box_of(cell_at(page, 2, 2))
    assert selected_box.centre_x == pytest.approx(
        view.centre_x, abs=SCROLL_TOLERANCE_PX
    )
    assert scrolled_ancestors(viewport) == []


# ---- AC-28: ⇄, a pinch and the keyboard hidden do not bring the cell back ---------


@pytest.mark.only_browser("chromium")
def test_ac28_after_a_pan_swap_pinch_and_hidden_keyboard_never_scroll_to_the_cell(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    page = open_ac23_start(window, live_server, fx02_grid)
    viewport = viewport_of(page)
    selected = cell_at(page, OREILLE_ROW, OREILLE_FIRST_COLUMN)
    tap_shown_part(page, selected)
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "across")
    pan_to_bottom_right(page, viewport)
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "across")
    assert is_out_of_view(box_of(selected), box_of(viewport))
    scroll_after_pan = read_scroll(viewport)

    page.get_by_test_id("key-swap").tap()

    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "down")
    wait_two_frames(page)
    assert read_scroll(viewport) == scroll_after_pan
    assert is_out_of_view(box_of(selected), box_of(viewport))

    start, end = PINCH_TWO_TO_THREE
    pinch(page, viewport, start, end)

    expect(viewport).to_have_attribute("data-zoom", "3")
    wait_two_frames(page)
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "down")
    assert is_out_of_view(box_of(selected), box_of(viewport))

    page.get_by_test_id("keyboard-toggle").tap()

    expect_no_keyboard(page)
    wait_two_frames(page)
    wait_two_frames(page)
    expect_selected(page, OREILLE_ROW, OREILLE_FIRST_COLUMN, "down")
    assert is_out_of_view(box_of(selected), box_of(viewport))
    assert scrolled_ancestors(viewport) == []


# ---- AC-29: a tap on a clue scrolls like a key ------------------------------------


@pytest.mark.only_browser("chromium")
def test_ac29_a_tap_on_the_clue_selects_1_7_and_scrolls_across_to_1_8(
    window: OpenWindow, live_server: str, fx02_grid: Grid
) -> None:
    changes: list[tuple[int, int, dict[str, object]]] = []
    for index, letter in enumerate("OREIL"):
        column = OREILLE_FIRST_COLUMN + index
        changes.append((OREILLE_ROW, column, {"letter": letter, "author": "p1"}))
    view_with_oreil = with_letter_cells(grid_view(fx02_grid), changes)
    page = open_zoomed(window, live_server, view_with_oreil, keyboard_hidden=False)
    viewport = viewport_of(page)
    view = box_of(viewport)
    margin_right_before = box_of(cell_at(page, OREILLE_ROW, 8)).right
    assert margin_right_before > view.right, "(1, 8) was already whole in view"

    tap_shown_part(page, clue_at(page, *EARS_CLUE))

    expect_selected(page, OREILLE_ROW, 7, "across")
    wait_two_frames(page)
    left_after, top_after = read_scroll(viewport)
    assert left_after == pytest.approx(
        margin_right_before - view.right, abs=SCROLL_TOLERANCE_PX
    )
    assert box_of(cell_at(page, OREILLE_ROW, 8)).right == pytest.approx(
        view.right, abs=SCROLL_TOLERANCE_PX
    )
    assert top_after == 0.0
    assert scrolled_ancestors(viewport) == []
