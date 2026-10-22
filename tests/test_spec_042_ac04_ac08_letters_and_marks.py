"""Tests of spec 042, AC-4 to AC-8: letters, the strike, the notch and the ring.

On the mocked room of `tests/spec042_harness.py`, 1280 by 720, desktop context.
AC-8 uses spec 034's mocked catch-up route, with `seen_seq` 5 stored. Sizes and
positions are read after `document.fonts.ready` (the harness waits for it).

Choices where the spec leaves room:

- AC-4, "the cell's text still holds the letter": the cell's trimmed
  `textContent` is its letter on a cell that is not revealed (a revealed cell
  also holds spec 024's hidden label).
- AC-4, the `text-box` check runs only where `CSS.supports("text-box",
  "trim-both cap alphabetic")` is true; elsewhere that test is skipped, as
  "Test harness" says.
- AC-6, the notch's contrast is measured against the cell's computed
  `background-color`, both opaque.
- AC-7, the flash colour of each step is that of the player of colour c, and the
  composite is `--player-colour-c` (spec 041's value) at 38 % over white; each
  reading is one `page.evaluate` made as soon as `data-revealed` is `true`.
- AC-8, "its box is the cell's inner box": left and top within 1 px of the
  cell's, width and height within 0.5 px of `s - 1`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CellTarget, LetterChanged, PlayerView, RevealBudget
from spec019_harness import MockRoomSocket
from spec024_harness import cell_locked_frame, reveal_result_frame
from spec034_harness import CatchUpRoute, catch_up_json
from spec042_harness import (
    CELL_SELECTOR,
    INK,
    MIN_MARK_CONTRAST,
    READERS_JS,
    RED,
    REVEAL,
    UI_FONT_STACK,
    WAIT_TIMEOUT_MS,
    ChangeList,
    Reading,
    box_of,
    box_problems,
    cell_at,
    colour_of,
    colour_problems,
    contrast_ratio,
    expect_catch_up,
    flash_composite,
    font_families,
    fx01_view,
    inner_box,
    line_height_px,
    make_catalogue,
    me,
    notch_size,
    open_caught_up_room,
    open_room,
    player,
    px,
    style_of,
    tap,
    to_box,
    to_colour,
)

# ---- Fixtures: thin wrappers around the harness ---------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- AC-4: grid letters ----------------------------------------------------------


def open_ac4(page: Page, base_url: str, grid: Grid) -> None:
    """(1, 0) holds `T` locked, (1, 1) holds `A`."""
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": "p1", "locked": True}),
        (1, 1, {"letter": "A", "author": "p1"}),
    ]
    open_room(page, base_url, fx01_view(grid, changes), [me()])


@pytest.mark.parametrize(
    ("column", "letter"), [(0, "T"), (1, "A")], ids=["locked-T", "plain-A"]
)
def test_ac4_a_letter_cell_holds_one_cell_letter_with_its_letter(
    page: Page, live_server: str, fx01_grid: Grid, column: int, letter: str
) -> None:
    open_ac4(page, live_server, fx01_grid)
    cell = cell_at(page, 1, column)
    expect(cell).to_have_attribute("data-letter", letter)

    letters = cell.get_by_test_id("cell-letter")

    expect(letters).to_have_count(1)
    expect(letters).to_have_text(letter)
    assert cell.evaluate("cell => cell.textContent.trim()") == letter


def test_ac4_an_empty_letter_cell_holds_no_cell_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac4(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 2)
    expect(cell).to_have_attribute("data-letter", "")

    expect(cell.get_by_test_id("cell-letter")).to_have_count(0)


@pytest.mark.parametrize(
    ("column", "weight"), [(0, 700), (1, 500)], ids=["locked-T", "plain-A"]
)
def test_ac4_the_letter_is_source_sans_3_at_056_of_the_cell_in_ink(
    page: Page, live_server: str, fx01_grid: Grid, column: int, weight: int
) -> None:
    open_ac4(page, live_server, fx01_grid)
    cell = cell_at(page, 1, column)
    letter = cell.get_by_test_id("cell-letter")
    expect(letter).to_have_count(1)
    side = box_of(cell).width

    size = px(style_of(letter, "fontSize"))
    line_height = line_height_px(style_of(letter, "lineHeight"), size)

    assert font_families(style_of(letter, "fontFamily")) == UI_FONT_STACK
    assert abs(size - 0.56 * side) <= 0.1, (size, side)
    assert abs(line_height - size) <= 0.1, (line_height, size)
    assert colour_problems("letter", colour_of(letter, "color"), INK) == []
    assert int(float(style_of(letter, "fontWeight"))) == weight


SUPPORTS_TEXT_BOX_SCRIPT = "() => CSS.supports('text-box', 'trim-both cap alphabetic')"


def test_ac4_the_capital_is_trimmed_to_its_cap_height_and_baseline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac4(page, live_server, fx01_grid)
    if not page.evaluate(SUPPORTS_TEXT_BOX_SCRIPT):
        pytest.skip("this engine has no text-box (spec 042, Test harness)")
    letter = cell_at(page, 1, 1).get_by_test_id("cell-letter")
    expect(letter).to_have_count(1)

    assert style_of(letter, "textBoxTrim") == "trim-both"
    assert style_of(letter, "textBoxEdge") == "cap alphabetic"


@pytest.mark.parametrize("column", [0, 1], ids=["locked-T", "plain-A"])
def test_ac4_the_letter_is_centred_horizontally_on_the_inner_box(
    page: Page, live_server: str, fx01_grid: Grid, column: int
) -> None:
    open_ac4(page, live_server, fx01_grid)
    cell = cell_at(page, 1, column)
    inner = inner_box(box_of(cell))
    letter = cell.get_by_test_id("cell-letter")
    expect(letter).to_have_count(1)

    letter_box = box_of(letter)

    assert abs(letter_box.centre_x - inner.centre_x) <= 1.0, (letter_box, inner)


# ---- AC-5: the strike of a wrong letter -------------------------------------------


def test_ac5_a_wrong_letter_is_struck_in_red_with_a_line_of_at_least_2_px(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 1, {"letter": "X", "author": "p1", "wrong": True})]
    open_room(page, live_server, fx01_view(fx01_grid, changes), [me()])
    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-wrong", "true")

    size = px(style_of(cell, "fontSize"))
    thickness = px(style_of(cell, "textDecorationThickness"))

    assert "line-through" in style_of(cell, "textDecorationLine")
    assert colour_problems("strike", colour_of(cell, "textDecorationColor"), RED) == []
    assert abs(thickness - max(2.0, 0.07 * size)) <= 0.1, (thickness, size)


# ---- AC-6: the revealed notch ----------------------------------------------------

# The notch of a cell: its marks' count, then its styles, its box, its colour and
# the cell's box and background.
NOTCH_SCRIPT = "cell => {\n" + READERS_JS + r"""
const marks = cell.querySelectorAll('[data-testid="reveal-mark"]');
const reading = {marks: marks.length, cell: boxOf(cell),
  cellBackground: parseColour(getComputedStyle(cell).backgroundColor),
  flash: cell.getAttribute('data-flash')};
if (marks.length === 1) {
  const style = getComputedStyle(marks[0]);
  Object.assign(reading, markOf(marks[0]));
  reading.clipPath = style.clipPath;
  reading.background = parseColour(style.backgroundColor);
}
return reading;
}"""


def read_notch(page: Page, row: int, column: int) -> Reading:
    found = cell_at(page, row, column).evaluate(NOTCH_SCRIPT)
    assert isinstance(found, dict)
    return found


def notch_box_problems(reading: Reading) -> list[str]:
    """The notch's box: its size, centred on the inner box, its bottom on it."""
    inner = inner_box(to_box(reading["cell"]))
    width, height = notch_size(to_box(reading["cell"]).width)
    return box_problems(
        "reveal-mark",
        to_box(reading["box"]),
        width=width,
        height=height,
        centre_x=inner.centre_x,
        bottom=inner.bottom,
    )


def open_ac6(page: Page, base_url: str, grid: Grid) -> None:
    """(1, 0) holds `T` revealed: locked, revealed, no author."""
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": None, "locked": True, "revealed": True})
    ]
    open_room(page, base_url, fx01_view(grid, changes), [me()])


def test_ac6_the_notch_is_an_orange_red_triangle_drawn_over_the_marks_below_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac6(page, live_server, fx01_grid)

    reading = read_notch(page, 1, 0)

    assert reading["marks"] == 1
    assert reading["ariaHidden"] == "true"
    assert reading["text"] == ""
    assert reading["position"] == "absolute"
    assert reading["zIndex"] == "3"
    assert reading["pointerEvents"] == "none"
    assert " ".join(reading["clipPath"].split()) == (
        "polygon(50% 0%, 100% 100%, 0% 100%)"
    )
    assert colour_problems("notch", reading["background"], REVEAL) == []


def test_ac6_the_notch_sits_at_the_middle_of_the_bottom_edge(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac6(page, live_server, fx01_grid)

    reading = read_notch(page, 1, 0)

    assert reading["marks"] == 1
    assert notch_box_problems(reading) == []


def test_ac6_the_notch_keeps_3_to_1_on_locked_grey_and_on_my_selected_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac6(page, live_server, fx01_grid)
    on_locked = read_notch(page, 1, 0)

    tap(page, 1, 0)
    on_selected = read_notch(page, 1, 0)

    for reading in (on_locked, on_selected):
        ratio = contrast_ratio(
            to_colour(reading["background"]), to_colour(reading["cellBackground"])
        )
        assert ratio >= MIN_MARK_CONTRAST, reading


def test_ac6_a_cell_that_is_not_revealed_holds_no_notch(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac6(page, live_server, fx01_grid)

    expect(cell_at(page, 1, 1).get_by_test_id("reveal-mark")).to_have_count(0)
    expect(page.get_by_test_id("reveal-mark")).to_have_count(1)


# ---- AC-7: the notch during a flash -----------------------------------------------

AC7_SEQ = 10
AC7_CELLS = [(1, 0, "T"), (1, 1, "A"), (1, 2, "M")]
AC7_COLOURS = [4, 5, 6]
FLASH_END_TIMEOUT_MS = 2000

# Polled until the cell's `data-revealed` is `true`, then read at once: its
# `data-flash` and the notch's computed background.
REVEALED_READING_SCRIPT = "selector => {\n" + READERS_JS + r"""
const cell = document.querySelector(selector);
if (cell === null || cell.getAttribute('data-revealed') !== 'true') {
  return false;
}
const marks = cell.querySelectorAll('[data-testid="reveal-mark"]');
return {
  flash: cell.getAttribute('data-flash'),
  marks: marks.length,
  background: marks.length === 1
    ? parseColour(getComputedStyle(marks[0]).backgroundColor) : null,
};
}"""


def ac7_players() -> list[PlayerView]:
    """`p1` (colour 0), `p5`, `p6` and `p7` of colours 4, 5 and 6."""
    return [me(), player("p5", 4), player("p6", 5), player("p7", 6)]


def open_ac7(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """The snapshot of AC-7: seq 10, (1, 0), (1, 1) and (1, 2) hold `X` by `p1`."""
    changes: ChangeList = []
    for row, column, _ in AC7_CELLS:
        changes.append((row, column, {"letter": "X", "author": "p1"}))
    view = fx01_view(grid, changes)
    return open_room(page, base_url, view, ac7_players(), seq=AC7_SEQ)


def run_ac7_step(page: Page, mock: MockRoomSocket, step: int) -> Reading:
    """Send a step's three frames back to back; read the cell once it is revealed.

    Args:
        page: The room of AC-7.
        mock: Its mocked socket.
        step: 0, 1 or 2: the cell at that position of AC7_CELLS, flashed by the
            player of colour AC7_COLOURS[step].

    Returns:
        The cell's `data-flash` and its notch's colour, read at once.
    """
    row, column, solution = AC7_CELLS[step]
    colour = AC7_COLOURS[step]
    replacer = f"p{colour + 1}"
    first_seq = AC7_SEQ + 1 + 3 * step
    changed = LetterChanged(
        seq=first_seq,
        row=row,
        column=column,
        letter="Y",
        pencil=False,
        player_id=replacer,
    )
    left = RevealBudget(letters=4 - step, words=1)
    target = CellTarget(row=row, column=column)
    mock.send(changed.model_dump_json())
    mock.send(reveal_result_frame(first_seq + 1, target, left, player_id="p1"))
    mock.send(cell_locked_frame(first_seq + 2, row, column, solution, revealed=True))
    selector = CELL_SELECTOR.format(row=row, column=column)
    handle = page.wait_for_function(
        REVEALED_READING_SCRIPT, arg=selector, timeout=WAIT_TIMEOUT_MS
    )
    reading = handle.json_value()
    assert isinstance(reading, dict), reading
    return reading


@pytest.mark.parametrize("step", [0, 1, 2], ids=["colour-4", "colour-5", "colour-6"])
def test_ac7_during_a_flash_the_notch_is_ink_and_keeps_3_to_1(
    page: Page, live_server: str, fx01_grid: Grid, step: int
) -> None:
    mock = open_ac7(page, live_server, fx01_grid)
    for earlier in range(step):
        run_ac7_step(page, mock, earlier)
    colour = AC7_COLOURS[step]

    reading = run_ac7_step(page, mock, step)

    assert reading["flash"] == str(colour), f"read after the flash: {reading}"
    assert reading["marks"] == 1
    assert colour_problems("notch", reading["background"], INK) == []
    notch = to_colour(reading["background"])
    assert contrast_ratio(notch, flash_composite(colour)) >= MIN_MARK_CONTRAST


def test_ac7_once_the_flash_ends_the_notch_is_orange_red_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac7(page, live_server, fx01_grid)
    run_ac7_step(page, mock, 0)
    cell = cell_at(page, 1, 0)

    expect(cell).to_have_attribute("data-flash", "", timeout=FLASH_END_TIMEOUT_MS)

    notch = cell.get_by_test_id("reveal-mark")
    assert colour_problems("notch", colour_of(notch, "backgroundColor"), REVEAL) == []


# ---- AC-8: the catch-up ring ---------------------------------------------------------

CAUGHT_UP = [(1, 0), (2, 2)]

RING_SCRIPT = "cell => {\n" + READERS_JS + r"""
const marks = cell.querySelectorAll('[data-testid="catch-up-mark"]');
const reading = {marks: marks.length, cell: boxOf(cell),
  cellBackground: parseColour(getComputedStyle(cell).backgroundColor)};
if (marks.length === 1) {
  const style = getComputedStyle(marks[0]);
  Object.assign(reading, markOf(marks[0]));
  reading.insets = [style.top, style.right, style.bottom, style.left];
  reading.boxSizing = style.boxSizing;
  reading.sides = [];
  for (const side of ['Top', 'Right', 'Bottom', 'Left']) {
    reading.sides.push({
      side: side,
      style: style['border' + side + 'Style'],
      width: style['border' + side + 'Width'],
      colour: parseColour(style['border' + side + 'Color']),
    });
  }
}
return reading;
}"""


def read_ring(page: Page, row: int, column: int) -> Reading:
    found = cell_at(page, row, column).evaluate(RING_SCRIPT)
    assert isinstance(found, dict)
    return found


def open_ac8(page: Page, base_url: str, grid: Grid) -> None:
    """`seen_seq` 5, a snapshot at 9, the catch-up of (1, 0) and (2, 2); tap (2, 2)."""
    route = CatchUpRoute(answer=catch_up_json(5, 9, cells=CAUGHT_UP))
    open_caught_up_room(
        page, base_url, fx01_view(grid), [me()], route, seen_seq=5, seq=9
    )
    expect_catch_up(page, "5-9")
    tap(page, 2, 2)


@pytest.mark.parametrize(("row", "column"), CAUGHT_UP, ids=["1-0", "2-2"])
def test_ac8_the_ring_is_a_3_px_ink_border_under_the_other_marks(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int
) -> None:
    open_ac8(page, live_server, fx01_grid)

    reading = read_ring(page, row, column)

    assert reading["marks"] == 1
    assert reading["position"] == "absolute"
    assert reading["insets"] == ["0px", "0px", "0px", "0px"]
    assert reading["boxSizing"] == "border-box"
    assert reading["zIndex"] == "1"
    assert reading["pointerEvents"] == "none"
    problems: list[str] = []
    for side in reading["sides"]:
        if side["style"] != "solid" or side["width"] != "3px":
            problems.append(f"{side['side']}: {side['style']} {side['width']}")
        problems.extend(colour_problems(side["side"], side["colour"], INK))
    assert problems == []


@pytest.mark.parametrize(("row", "column"), CAUGHT_UP, ids=["1-0", "2-2"])
def test_ac8_the_ring_covers_the_cells_inner_box(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int
) -> None:
    open_ac8(page, live_server, fx01_grid)

    reading = read_ring(page, row, column)

    assert reading["marks"] == 1
    cell = to_box(reading["cell"])
    problems = box_problems(
        "catch-up-mark",
        to_box(reading["box"]),
        left=cell.left,
        top=cell.top,
        width=cell.width - 1,
        height=cell.height - 1,
    )
    assert problems == []


@pytest.mark.parametrize(
    ("row", "column"), CAUGHT_UP, ids=["1-0-white", "2-2-selected"]
)
def test_ac8_the_ring_keeps_3_to_1_on_white_and_on_my_selected_cell(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int
) -> None:
    open_ac8(page, live_server, fx01_grid)

    reading = read_ring(page, row, column)

    assert reading["marks"] == 1
    ring = to_colour(reading["sides"][0]["colour"])
    ratio = contrast_ratio(ring, to_colour(reading["cellBackground"]))
    assert ratio >= MIN_MARK_CONTRAST, reading
