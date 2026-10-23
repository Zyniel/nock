"""Tests of spec 047, AC-6: the end band keeps « Voir le bilan » whole on its right
and lets its text wrap.

On `SOLVED` (spec 044's), in the desktop context: at 1280 by 720 the band holds
`grid-status-text` (the ✓ pictogram and spec 026's text) then `recap-open`, on one
line; at 320 by 568 `recap-open` keeps its whole text on one line on the band's
right, and the text may take two lines. On `FULL_WRONG` (spec 044's) at 320 by 568
the band holds the whole text and no `recap-open`.

Readings where the spec leaves room:

- "Its ✓ pictogram before it": an element of `grid-status-text` (itself or inside
  it) draws `"✓"` in a `::before` or `::after` placed before the first text node
  (spec 043 AC-27's test reads the band's pictogram the same way).
- "The band's content right edge": `grid-status`'s box less its right border and
  padding.
- "One `getClientRects()` line box for its text": the rectangles of a range over
  the text nodes of `grid-status-text` (outside `svg` and `aria-hidden`) share one
  top (spec 043's `label_of`).
- "Keeps its whole text": its text content, white space collapsed, is the
  `fr.json` value, and its `scrollWidth` is at most its `clientWidth` plus 1, so
  nothing is clipped.
- "At least as wide as at 1280 by 720" compares two pages of the same snapshot.
- Spec 013 AC-6's checks are spec 019's `layout_problems` in the desktop context,
  after a click on (1, 0) (the desktop context's tap).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from spec019_harness import OpenWindow, layout_problems, window_opener
from spec042_harness import box_of
from spec043_harness import (
    box_inside,
    fr_value,
    label_of,
    open_room,
    press_cell,
    same_position,
    style_of,
    window_box,
)
from spec044_harness import full_wrong_frame, solved_frame
from spec046_harness import child_ids, content_box
from spec047_harness import COMPUTER, NARROW

CHECK_MARK = "\N{CHECK MARK}"
WIDTH_TOLERANCE_PX = 0.5

# Where `glyph` is drawn against the text of an element: for each element (the
# root and its descendants) whose `::before` or `::after` draws it, whether that
# pictogram comes before the first text node.
PICTOGRAM_PLACE_SCRIPT = r"""
(root, glyph) => {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  let first = null;
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    if (node.textContent.trim() !== '') {
      first = node;
      break;
    }
  }
  if (first === null) {
    return [];
  }
  const drawn = `"${glyph}"`;
  const precedes = element => (element.compareDocumentPosition(first)
    & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  const places = [];
  for (const element of [root, ...root.querySelectorAll('*')]) {
    const holds = element.contains(first);
    if (getComputedStyle(element, '::before').content === drawn) {
      places.push(holds || precedes(element) ? 'before' : 'after');
    }
    if (getComputedStyle(element, '::after').content === drawn) {
      places.push(!holds && precedes(element) ? 'before' : 'after');
    }
  }
  return places;
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_band(
    window: OpenWindow, base_url: str, frame: str, size: tuple[int, int], state: str
) -> Page:
    """Open a snapshot in the desktop context; wait for the band's state."""
    page = window(size[0], size[1], False)
    open_room(page, base_url, frame)
    expect(page.get_by_test_id("grid-status")).to_have_attribute("data-state", state)
    return page


def open_solved_band(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int]
) -> Page:
    return open_band(window, base_url, solved_frame(grid), size, "solved")


def band_text(page: Page) -> Locator:
    return page.get_by_test_id("grid-status").get_by_test_id("grid-status-text")


def collapsed_text(locator: Locator) -> str:
    return " ".join(str(locator.text_content()).split())


def pictogram_places(locator: Locator, glyph: str) -> list[str]:
    found = locator.evaluate(PICTOGRAM_PLACE_SCRIPT, glyph)
    assert isinstance(found, list), found
    return [str(place) for place in found]


def text_line_count(locator: Locator) -> int:
    label = label_of(locator)
    assert label is not None, "grid-status-text holds no text"
    return int(label["lines"])


def clipped(locator: Locator) -> bool:
    """Whether an element's content is wider than its box (1 px)."""
    found = locator.evaluate("e => e.scrollWidth > e.clientWidth + 1")
    assert isinstance(found, bool), found
    return found


# ---- At 1280 by 720 ----------------------------------------------------------------


def test_ac6_the_band_holds_its_text_then_voir_le_bilan(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, COMPUTER)
    status = page.get_by_test_id("grid-status")

    assert child_ids(status) == ["grid-status-text", "recap-open"]
    assert collapsed_text(band_text(page)) == fr_value("completion.solved")
    assert pictogram_places(band_text(page), CHECK_MARK) == ["before"]


def test_ac6_voir_le_bilan_sits_on_the_bands_right_10_px_or_more_from_the_text(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, COMPUTER)
    status = page.get_by_test_id("grid-status")

    text_box = box_of(band_text(page))
    button_box = box_of(status.get_by_test_id("recap-open"))
    band_right = content_box(status).right

    assert button_box.left - text_box.right >= 10.0 - 1.0, (text_box, button_box)
    assert same_position(button_box.right, band_right), (button_box, band_right)
    assert abs(button_box.centre_y - text_box.centre_y) <= 1.0, (text_box, button_box)


def test_ac6_the_band_is_one_line_of_text_high(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, COMPUTER)

    expect(band_text(page)).to_have_count(1)
    assert text_line_count(band_text(page)) == 1


# ---- At 320 by 568 -----------------------------------------------------------------


def test_ac6_at_320_voir_le_bilan_keeps_its_whole_text_on_one_line(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, NARROW)
    button = page.get_by_test_id("grid-status").get_by_test_id("recap-open")

    assert style_of(button, "whiteSpace") == "nowrap"
    assert clipped(button) is False
    expect(button).to_have_text(fr_value("recap.open"))


def test_ac6_at_320_voir_le_bilan_lies_on_the_bands_right_inside_the_window(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, NARROW)
    status = page.get_by_test_id("grid-status")
    button = status.get_by_test_id("recap-open")

    button_box = box_of(button)

    assert box_inside(button_box, box_of(status)), (button_box, box_of(status))
    assert box_inside(button_box, window_box(page)), button_box
    assert same_position(button_box.right, content_box(status).right), button_box


def test_ac6_at_320_voir_le_bilan_is_at_least_as_wide_as_at_1280(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    wide = open_solved_band(window, live_server, fx01_grid, COMPUTER)
    wide_width = box_of(wide.get_by_test_id("recap-open")).width
    narrow = open_solved_band(window, live_server, fx01_grid, NARROW)

    narrow_width = box_of(narrow.get_by_test_id("recap-open")).width

    assert narrow_width >= wide_width - WIDTH_TOLERANCE_PX, (narrow_width, wide_width)


def test_ac6_at_320_the_text_lies_left_of_the_button_and_keeps_its_whole_text(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, NARROW)
    text = band_text(page)

    expect(text).to_have_count(1)
    text_box = box_of(text)
    button_box = box_of(page.get_by_test_id("recap-open"))

    assert text_box.right <= button_box.left + 1.0, (text_box, button_box)
    assert collapsed_text(text) == fr_value("completion.solved")
    assert clipped(text) is False
    assert text_line_count(text) <= 2


def test_ac6_at_320_spec_013_ac6_checks_hold_after_a_tap(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_solved_band(window, live_server, fx01_grid, NARROW)

    press_cell(page, 1, 0)

    assert layout_problems(page, touch=False) == []


def test_ac6_full_and_wrong_at_320_shows_its_whole_text_and_no_voir_le_bilan(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    frame = full_wrong_frame(fx01_grid)
    page = open_band(window, live_server, frame, NARROW, "full_wrong")
    status = page.get_by_test_id("grid-status")
    text = band_text(page)

    expect(text).to_have_count(1)
    assert collapsed_text(text) == fr_value("completion.full_wrong")
    assert clipped(text) is False
    expect(status.get_by_test_id("recap-open")).to_have_count(0)
    assert box_inside(box_of(status), window_box(page)), box_of(status)
