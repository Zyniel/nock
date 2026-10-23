"""Tests of spec 046, AC-7 and AC-8: the force line's Nock marks and the generic
drawing of a grid's proportions.

Browser with mocked routes: `GET /api/grids` answers `BIG` (grid 12, 13 by 17,
force 3, 54 words; grid 2, 5 by 5, force 2, 8 words); the live server serves the
client. AC-7: four 8 by 11 px Nock marks, navy up to the force and `--nock-thumb`
after, then « Force F · W by H · N mots ». AC-8: the drawing, an `svg` whose cells,
clue cells and inner lines follow the grid's width and height, only while two
cards fit per row.

Choices where the spec leaves room:

- "Followed by the texts ..., with one `meta-sep` between each two" is read on
  the force line (the parent of `catalogue-force-marks`): what it holds in order,
  an element without a test id being read through, must be the marks, `Force 3`,
  a separator, the size, `54 mots`.
- A `thumb-line` is checked on its `x1`, `y1`, `x2` and `y2` attributes: a vertical
  line at each inner column edge from the top to the bottom, a horizontal one at
  each inner row edge from the left to the right, in viewBox units.
- "The drawings are gone within 300 ms": no `catalogue-thumb` within 300 ms of
  the resize, and back within 300 ms of the resize back.
"""

from __future__ import annotations

from collections.abc import Iterator
from itertools import pairwise

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from fonts_ready import wait_for_fonts
from spec042_harness import box_of, to_box
from spec043_harness import LINE, MUTED, NAVY, WHITE, Reading, colour_matches, px
from spec046_harness import (
    FOLLOW_MS,
    NOCK_MARK_POINTS,
    SEP,
    THUMB,
    WIDE,
    OpenWindow,
    answer_big,
    border_problems,
    content_box,
    font_problems,
    item_of,
    near,
    same_position,
    same_size,
    separator_problems,
    sequence_of,
    size_ids,
    svg_of,
    window_opener,
)

TIMES = "\N{MULTIPLICATION SIGN}"
SMALL_WINDOWS = [(360, 740), (768, 1024)]


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_big(window: OpenWindow, base_url: str, size: tuple[int, int]) -> Page:
    """Open `/` with `GET /api/grids` answering `BIG`; wait for its two cards."""
    page = window(*size)
    answer_big(page)
    page.goto(f"{base_url}/")
    expect(page.get_by_test_id("catalogue-item")).to_have_count(2)
    wait_for_fonts(page)
    return page


def marks_of(card: Locator) -> list[Reading]:
    marks = card.get_by_test_id("catalogue-force-marks").locator("svg")
    readings: list[Reading] = []
    for index in range(marks.count()):
        readings.append(svg_of(marks.nth(index)))
    return readings


def force_line_of(card: Locator) -> Locator:
    return card.get_by_test_id("catalogue-force-marks").locator("xpath=..")


def thumb_of(card: Locator) -> Locator:
    return card.get_by_test_id("catalogue-thumb")


def number_of(value: object) -> float:
    return float(str(value))


def shapes_with(thumb: Reading, test_id: str) -> list[Reading]:
    found: list[Reading] = []
    for shape in thumb["shapes"]:
        if shape["attributes"].get("data-testid") == test_id:
            found.append(shape)
    return found


def clue_positions(width: int, height: int) -> set[tuple[float, float]]:
    """Where the drawing's clue cells are, in viewBox units."""
    positions: set[tuple[float, float]] = set()
    for column in range(0, width, 2):
        positions.add((10.0 * column, 0.0))
    for row in range(2, height, 2):
        positions.add((0.0, 10.0 * row))
    return positions


def line_problems(thumb: Reading, width: int, height: int) -> list[str]:
    """How the `thumb-line` elements differ from the inner lines of the drawing."""
    lines = shapes_with(thumb, "thumb-line")
    vertical: list[float] = []
    horizontal: list[float] = []
    problems: list[str] = []
    for line in lines:
        attributes = line["attributes"]
        if line["tag"] != "line":
            problems.append(f"a thumb-line is a {line['tag']}")
            continue
        x1 = number_of(attributes.get("x1"))
        y1 = number_of(attributes.get("y1"))
        x2 = number_of(attributes.get("x2"))
        y2 = number_of(attributes.get("y2"))
        if x1 == x2 and {y1, y2} == {0.0, 10.0 * height}:
            vertical.append(x1)
        elif y1 == y2 and {x1, x2} == {0.0, 10.0 * width}:
            horizontal.append(y1)
        else:
            problems.append(f"a thumb-line from ({x1}, {y1}) to ({x2}, {y2})")
        if line["strokeColour"] is None or not colour_matches(
            line["strokeColour"], LINE
        ):
            problems.append(f"a thumb-line stroke {line['stroke']}")
        if not near(px(str(line["strokeWidth"])), 1.0, 0.0):
            problems.append(f"a thumb-line stroke-width {line['strokeWidth']}")
    expected_vertical = [10.0 * column for column in range(1, width)]
    expected_horizontal = [10.0 * row for row in range(1, height)]
    if sorted(vertical) != expected_vertical:
        problems.append(f"vertical lines at {sorted(vertical)}")
    if sorted(horizontal) != expected_horizontal:
        problems.append(f"horizontal lines at {sorted(horizontal)}")
    return problems


def clue_problems(thumb: Reading, width: int, height: int) -> list[str]:
    """How the `thumb-clue` elements differ from the drawing's clue cells."""
    clues = shapes_with(thumb, "thumb-clue")
    positions: set[tuple[float, float]] = set()
    problems: list[str] = []
    for clue in clues:
        attributes = clue["attributes"]
        if clue["tag"] != "rect":
            problems.append(f"a thumb-clue is a {clue['tag']}")
            continue
        positions.add((number_of(attributes.get("x")), number_of(attributes.get("y"))))
        size = (number_of(attributes.get("width")), number_of(attributes.get("height")))
        if size != (10.0, 10.0):
            problems.append(f"a thumb-clue of {size}")
        if clue["fillColour"] is None or not colour_matches(clue["fillColour"], THUMB):
            problems.append(f"a thumb-clue fill {clue['fill']}")
    if len(clues) != len(clue_positions(width, height)):
        problems.append(f"{len(clues)} thumb-clue elements")
    if positions != clue_positions(width, height):
        problems.append(f"thumb-clue at {sorted(positions)}")
    return problems


# ---- AC-7: the force line --------------------------------------------------------


def test_ac7_the_marks_are_four_8_by_11_nock_marks_2_px_apart(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)
    card = item_of(page, 12)

    expect(card.get_by_test_id("catalogue-force-marks")).to_have_attribute(
        "aria-hidden", "true"
    )
    marks = marks_of(card)
    boxes = [to_box(mark["box"]) for mark in marks]

    assert len(marks) == 4, marks
    for mark, box in zip(marks, boxes, strict=True):
        assert mark["viewBox"] == "0 0 10 14", mark
        assert same_size(box.width, 8.0), box
        assert same_size(box.height, 11.0), box
        assert len(mark["shapes"]) == 1, mark
        polygon = mark["shapes"][0]
        assert polygon["tag"] == "polygon", polygon
        points = " ".join(str(polygon["attributes"].get("points")).split())
        assert points == NOCK_MARK_POINTS, polygon
    for before, after in pairwise(boxes):
        assert same_position(after.left - before.right, 2.0), (before, after)


@pytest.mark.parametrize(("number", "force"), [(12, 3), (2, 2)], ids=["12", "2"])
def test_ac7_the_marks_are_navy_up_to_the_force_and_thumb_grey_after(
    window: OpenWindow, live_server: str, number: int, force: int
) -> None:
    page = open_big(window, live_server, WIDE)

    marks = marks_of(item_of(page, number))

    assert len(marks) == 4, marks
    for index, mark in enumerate(marks):
        fill = mark["shapes"][0]["fillColour"]
        expected = NAVY if index < force else THUMB
        assert fill is not None, mark
        assert colour_matches(fill, expected), (index, fill)


def test_ac7_the_force_line_writes_force_size_and_words_between_separators(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)
    line = force_line_of(item_of(page, 12))

    found = sequence_of(line)

    assert found == [
        "#catalogue-force-marks",
        "Force 3",
        SEP,
        f"13 {TIMES} 17",
        SEP,
        "54 mots",
    ], found
    assert separator_problems(line) == []


def test_ac7_the_force_line_is_muted_at_13_6_px(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)

    line = force_line_of(item_of(page, 12))

    assert font_problems(line, "force line", 13.6, colour=MUTED) == []


# ---- AC-8: the drawing -----------------------------------------------------------


@pytest.mark.parametrize("number", [12, 2])
def test_ac8_each_card_starts_with_its_hidden_drawing(
    window: OpenWindow, live_server: str, number: int
) -> None:
    page = open_big(window, live_server, WIDE)
    card = item_of(page, number)

    first_test_id = card.evaluate(
        "card => card.firstElementChild?.getAttribute('data-testid') ?? null"
    )
    thumb = thumb_of(card)

    assert first_test_id == "catalogue-thumb"
    assert thumb.evaluate("element => element.tagName.toLowerCase()") == "svg"
    expect(thumb).to_have_attribute("aria-hidden", "true")


@pytest.mark.parametrize(
    ("number", "width", "height", "drawn_width"),
    [(12, 13, 17, "39"), (2, 5, 5, "51")],
    ids=["13x17", "5x5"],
)
def test_ac8_the_drawing_has_the_grids_proportions_51_px_high(
    window: OpenWindow,
    live_server: str,
    number: int,
    width: int,
    height: int,
    drawn_width: str,
) -> None:
    page = open_big(window, live_server, WIDE)
    thumb = thumb_of(item_of(page, number))

    box = content_box(thumb)

    expect(thumb).to_have_attribute("width", drawn_width)
    expect(thumb).to_have_attribute("height", "51")
    expect(thumb).to_have_attribute("viewBox", f"0 0 {10 * width} {10 * height}")
    assert same_size(box.width, float(drawn_width)), box
    assert same_size(box.height, 51.0), box
    assert border_problems(thumb, "catalogue-thumb", (154, 163, 178)) == []


def test_ac8_the_first_shape_is_a_white_rect_over_the_whole_drawing(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)

    thumb = svg_of(thumb_of(item_of(page, 12)))

    background = thumb["shapes"][0]
    assert background["tag"] == "rect", background
    assert number_of(background["attributes"].get("width")) == 130.0, background
    assert number_of(background["attributes"].get("height")) == 170.0, background
    assert background["fillColour"] is not None, background
    assert colour_matches(background["fillColour"], WHITE), background


@pytest.mark.parametrize(
    ("number", "width", "height"), [(12, 13, 17), (2, 5, 5)], ids=["13x17", "5x5"]
)
def test_ac8_the_clue_cells_are_in_row_0_and_column_0_at_even_places(
    window: OpenWindow,
    live_server: str,
    number: int,
    width: int,
    height: int,
) -> None:
    page = open_big(window, live_server, WIDE)

    thumb = svg_of(thumb_of(item_of(page, number)))

    assert clue_problems(thumb, width, height) == []


@pytest.mark.parametrize(
    ("number", "width", "height", "count"),
    [(12, 13, 17, 28), (2, 5, 5, 8)],
    ids=["13x17", "5x5"],
)
def test_ac8_the_inner_lines_cross_the_drawing_in_line_grey(
    window: OpenWindow,
    live_server: str,
    number: int,
    width: int,
    height: int,
    count: int,
) -> None:
    page = open_big(window, live_server, WIDE)

    thumb = svg_of(thumb_of(item_of(page, number)))

    assert len(shapes_with(thumb, "thumb-line")) == count
    assert line_problems(thumb, width, height) == []


def test_ac8_the_drawing_holds_the_background_then_the_clue_cells_then_the_lines(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)

    thumb = svg_of(thumb_of(item_of(page, 12)))

    kinds: list[str] = []
    for shape in thumb["shapes"]:
        kinds.append(str(shape["attributes"].get("data-testid", "")))
    first_line = kinds.index("thumb-line")
    assert kinds[0] == "", kinds
    assert kinds[1:first_line] == ["thumb-clue"] * 15, kinds
    assert kinds[first_line:] == ["thumb-line"] * 28, kinds


@pytest.mark.parametrize(
    ("width", "height"), SMALL_WINDOWS, ids=size_ids(SMALL_WINDOWS)
)
def test_ac8_with_one_card_per_row_no_card_has_a_drawing(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_big(window, live_server, (width, height))

    expect(page.get_by_test_id("catalogue-thumb")).to_have_count(0)


def test_ac8_the_drawings_go_and_come_back_within_300_ms_of_a_resize(
    window: OpenWindow, live_server: str
) -> None:
    page = open_big(window, live_server, WIDE)
    thumbs = page.get_by_test_id("catalogue-thumb")
    expect(thumbs).to_have_count(2)

    page.set_viewport_size({"width": 360, "height": 740})
    expect(thumbs).to_have_count(0, timeout=FOLLOW_MS)
    page.set_viewport_size({"width": 1280, "height": 720})
    expect(thumbs).to_have_count(2, timeout=FOLLOW_MS)

    assert box_of(thumbs.first).height > 0
