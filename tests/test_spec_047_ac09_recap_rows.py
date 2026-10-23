"""Tests of spec 047, AC-9: each recap row reads dot, name, « (vous) » and the
counts, and a player who left has no dot.

On `SOLVED` (spec 044's) with the recap route answering `RECAP` (`p1` Ana 8 letters
4 words, `p2` Bob 5 letters 3 words), after `recap-open`, in the desktop context.

Readings where the spec leaves room:

- "`recap-values`, whose text content is `8 lettres · 4 mots complétés`": the
  spec also says `recap-sep` holds no text node and draws « · » as a pictogram, so
  the DOM text content cannot hold the « · ». The test reads the row as it is
  drawn: the texts of `recap-values`' children in order, `recap-sep` standing for
  its pictogram « · », joined with single spaces, and requires that reading to be
  `8 lettres · 4 mots complétés`, with nothing else in `recap-values`.
- "Left to right": the parts of the row that show, in document order, have
  increasing left edges.
- "The list's right edge": the right edge of `recap-players`' box.
- "Its left edge 18 px right of the row's left edge" at 360 by 740 is measured on
  the row's box (the row has no padding of its own).
- "A `box-shadow` of spread 1 px and colour ink at 0.55": the one shadow
  `0 0 0 1px` in that colour (the design's ring).
- The accessibility switch is turned on in the Menu (spec 043's `open_menu`), the
  Menu then closed with `Escape`, before `recap-open` is clicked.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.protocol import LeaveReason
from room_panels import open_menu
from spec019_harness import OpenWindow, window_opener
from spec041_harness import shadow_of
from spec042_harness import READERS_JS, box_of, colour_of, expect_seq, to_box
from spec043_harness import (
    INK,
    Reading,
    colour_matches,
    expect_closed,
    fr_value,
    is_clear,
    left_frame,
    pictogram_of,
    same_position,
    same_size,
    shows_pictogram,
    style_of,
)
from spec044_harness import solved_frame
from spec047_harness import (
    COMPUTER,
    DOT_RING_ALPHA,
    MUTED,
    PHONE,
    open_loaded_recap,
    open_solved,
    parts_of,
    row_of,
    tabular_problems,
    type_problems,
)

MIDDLE_DOT = "\N{MIDDLE DOT}"
ROW_PARTS = ["recap-colour", "recap-name", "recap-you", "recap-values"]
VALUE_PARTS = ["recap-letters", "recap-sep", "recap-words"]

# What `recap-values` holds, in order: each text node (trimmed) as `text`, and each
# element child as its test id and its text.
VALUES_SCRIPT = r"""
values => {
  const found = [];
  for (const node of values.childNodes) {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent.replace(/\s+/g, ' ').trim();
      if (text !== '') {
        found.push({testId: null, text: text});
      }
    } else if (node.nodeType === Node.ELEMENT_NODE) {
      found.push({testId: node.getAttribute('data-testid'),
        text: node.textContent.replace(/\s+/g, ' ').trim()});
    }
  }
  return found;
}
"""

# A `recap-colour`'s look: background, image, shadow, box and its `player-icon`s.
DOT_SCRIPT = "dot => {\n" + READERS_JS + r"""
const style = getComputedStyle(dot);
const icons = [];
for (const svg of dot.querySelectorAll('[data-testid="player-icon"]')) {
  icons.push(svgOf(svg));
}
return {
  background: parseColour(style.backgroundColor),
  image: style.backgroundImage,
  shadow: style.boxShadow,
  box: boxOf(dot),
  icons: icons,
};
}"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Setup -------------------------------------------------------------------------


def open_rows(
    window: OpenWindow,
    base_url: str,
    grid: Grid,
    size: tuple[int, int] = COMPUTER,
    *,
    bob_left: bool = False,
    access_on: bool = False,
) -> Page:
    """`SOLVED` with `RECAP`; the recap open and loaded.

    Args:
        window: The `window` fixture.
        base_url: The live server.
        grid: FX-01.
        size: The window (desktop context).
        bob_left: Whether `p2` leaves (`timed_out`, seq 6) before the opening.
        access_on: Whether `access-switch` is turned on before the opening.

    Returns:
        The page, with the recap's rows shown.
    """
    page = window(size[0], size[1], False)
    mock, _ = open_solved(page, base_url, solved_frame(grid))
    if bob_left:
        mock.send(left_frame(6, "p2", LeaveReason.TIMED_OUT))
        expect_seq(page, 6)
    if access_on:
        open_menu(page)
        switch = page.get_by_test_id("access-switch")
        switch.click()
        expect(switch).to_have_attribute("aria-pressed", "true")
        page.keyboard.press("Escape")
        expect_closed(page.get_by_test_id("room-menu"))
    open_loaded_recap(page)
    expect(page.get_by_test_id("recap-player")).to_have_count(2)
    return page


def part_of_row(page: Page, player_id: str, test_id: str) -> Locator:
    return row_of(page, player_id).get_by_test_id(test_id)


def dot_reading(page: Page, player_id: str) -> Reading:
    dot = part_of_row(page, player_id, "recap-colour")
    expect(dot).to_have_count(1)
    found = dot.evaluate(DOT_SCRIPT)
    assert isinstance(found, dict), found
    return found


def values_reading(page: Page, player_id: str) -> list[Reading]:
    values = part_of_row(page, player_id, "recap-values")
    expect(values).to_have_count(1)
    found = values.evaluate(VALUES_SCRIPT)
    assert isinstance(found, list), found
    return found


def drawn_values_text(reading: list[Reading]) -> str:
    """The values as drawn: each child's text, `recap-sep` as its « · »."""
    words: list[str] = []
    for item in reading:
        if item["testId"] == "recap-sep":
            words.append(MIDDLE_DOT)
        else:
            words.append(str(item["text"]))
    return " ".join(words)


# ---- My row ------------------------------------------------------------------------


def test_ac9_my_row_reads_dot_name_you_and_values_left_to_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)

    parts = parts_of(row_of(page, "p1"))

    assert [part.name for part in parts] == ROW_PARTS
    lefts = [part.box.left for part in parts]
    assert all(left < right for left, right in pairwise(lefts)), parts
    expect(part_of_row(page, "p1", "recap-name")).to_have_text("Ana")
    expect(part_of_row(page, "p1", "recap-you")).to_have_text(fr_value("roster.you"))


def test_ac9_the_values_read_letters_a_dot_then_words(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)

    reading = values_reading(page, "p1")

    assert [item["testId"] for item in reading] == VALUE_PARTS
    assert drawn_values_text(reading) == f"8 lettres {MIDDLE_DOT} 4 mots complétés"
    expect(part_of_row(page, "p1", "recap-letters")).to_have_text("8 lettres")
    expect(part_of_row(page, "p1", "recap-words")).to_have_text("4 mots complétés")


def test_ac9_the_separator_is_an_aria_hidden_pictogram(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)
    separator = part_of_row(page, "p1", "recap-sep")

    expect(separator).to_have_count(1)
    reading = pictogram_of(separator)

    assert reading["ariaHidden"] == "true"
    assert reading["textNodes"] == 0
    assert shows_pictogram(reading, MIDDLE_DOT), reading


def test_ac9_my_dot_is_a_10_px_player_dot_with_its_ring(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)
    dot = part_of_row(page, "p1", "recap-colour")
    roster = page.locator(
        '[data-testid="roster-player"][data-player-id="p1"] '
        '[data-testid="roster-colour"]'
    )

    box = box_of(dot)
    assert same_size(box.width, 10.0), box
    assert same_size(box.height, 10.0), box
    assert style_of(dot, "borderTopLeftRadius") == "50%"
    assert colour_of(dot, "backgroundColor") == colour_of(roster, "backgroundColor")
    shadow = shadow_of(dot)
    assert (shadow.x, shadow.y, shadow.blur, shadow.spread) == (0, 0, 0, 1), shadow
    assert shadow.colour is not None, shadow
    assert colour_matches(shadow.colour, INK, DOT_RING_ALPHA), shadow


def test_ac9_the_name_sits_8_px_right_of_the_dot_in_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)
    name = part_of_row(page, "p1", "recap-name")
    dot = part_of_row(page, "p1", "recap-colour")

    gap = box_of(name).left - box_of(dot).right

    assert same_position(gap, 8.0), gap
    assert type_problems(name, "recap-name", size=15.2, weight="600", colour=INK) == []


def test_ac9_you_is_muted(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)
    you = part_of_row(page, "p1", "recap-you")

    expect(you).to_have_count(1)
    assert type_problems(you, "recap-you", size=15.2, weight="400", colour=MUTED) == []


def test_ac9_the_values_are_muted_tabular_on_the_lists_right(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)
    values = part_of_row(page, "p1", "recap-values")
    name = part_of_row(page, "p1", "recap-name")

    problems = type_problems(values, "recap-values", size=13.6, colour=MUTED)
    problems += tabular_problems(values, "recap-values")
    values_box = box_of(values)
    list_box = box_of(page.get_by_test_id("recap-players"))

    assert problems == []
    assert same_position(values_box.right, list_box.right), (values_box, list_box)
    assert abs(values_box.centre_y - box_of(name).centre_y) <= 1.0, values_box


def test_ac9_the_two_rows_are_8_px_apart(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid)

    first = box_of(row_of(page, "p1"))
    second = box_of(row_of(page, "p2"))

    assert same_position(second.top - first.bottom, 8.0), (first, second)


# ---- At 360 by 740 ---------------------------------------------------------------


def test_ac9_at_360_the_values_go_under_the_name_18_px_in(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid, PHONE)

    problems: list[str] = []
    for player_id in ("p1", "p2"):
        row_box = box_of(row_of(page, player_id))
        name_box = box_of(part_of_row(page, player_id, "recap-name"))
        values_box = box_of(part_of_row(page, player_id, "recap-values"))
        if values_box.top < name_box.bottom - 1.0:
            problems.append(f"{player_id}: values top {values_box.top}, {name_box}")
        if not same_position(values_box.left - row_box.left, 18.0):
            problems.append(f"{player_id}: values {values_box.left - row_box.left} in")

    assert problems == []


# ---- A player who left -------------------------------------------------------------


def test_ac9_a_player_who_left_has_an_empty_10_px_slot(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid, bob_left=True)
    dot = part_of_row(page, "p2", "recap-colour")

    expect(dot).to_have_attribute("data-colour", "")
    reading = dot_reading(page, "p2")

    assert same_size(to_box(reading["box"]).width, 10.0), reading
    assert is_clear(reading["background"]), reading
    assert reading["image"] == "none", reading
    assert reading["shadow"] == "none", reading


def test_ac9_the_names_stay_aligned_after_a_player_left(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid, bob_left=True)

    mine = box_of(part_of_row(page, "p1", "recap-name"))
    bobs = box_of(part_of_row(page, "p2", "recap-name"))

    assert same_position(bobs.left, mine.left), (mine, bobs)


# ---- With the accessibility switch on -----------------------------------------------


def test_ac9_with_access_on_my_dot_holds_my_12_px_icon(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = open_rows(window, live_server, fx01_grid, access_on=True)

    reading = dot_reading(page, "p1")

    assert is_clear(reading["background"]), reading
    icons = reading["icons"]
    assert isinstance(icons, list), reading
    assert len(icons) == 1, icons
    icon_box = to_box(icons[0]["box"])
    assert same_size(icon_box.width, 12.0), icon_box
    assert same_size(icon_box.height, 12.0), icon_box
    assert icons[0]["dataIcon"] == "0", icons[0]
