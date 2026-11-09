"""Shared setup of the tests of the domain viewport (`specs/gameplay/viewport.md`).

Pytest does not collect this module (its name does not start with `test_`). It
holds:

- The readers of painted pixels that the hyphen edge tests (viewport AC-9 and
  AC-10) use: a screenshot clip decoded into its pixels, and the reading of one
  cell edge across its thickness and along its length, with the geometry of
  `specs/_design/cells.md` « Hyphen edges ».
- The windows, cell sizes and cells that the hyphen edge tests share
  (`test_viewport_hyphen_edges_*.py`), and the `hyphen_grid` fixture.
- "AC-11's start" (FX-02 on a touch phone held upright, zoomed to 2 by a pinch,
  the viewport at the grid's top-left corner) and its readers of the scroll and
  the selection, which the zoomed tests of AC-11 to AC-20 share.
- Taps and drags by a finger, a pen or a mouse. Each is a real pointer of that
  type: a finger goes through the Chrome DevTools Protocol's
  `Input.dispatchTouchEvent`, a pen and a mouse through its
  `Input.dispatchMouseEvent` with `pointerType` `pen` or `mouse` (Playwright has
  no pen). They work in Chromium only.

Pixels: the page is in a context with a device scale factor of 1, so one pixel
of a screenshot is one CSS pixel. A clip is taken at whole CSS pixels and decoded
here (8-bit RGB or RGBA PNG, no interlacing), with no image library.

An edge reading: for the right edge of a cell, the pixel columns around the grid
line (offset 0 is the line's pixel, negative offsets are in the cell, positive
ones in the next cell) and, along each of them, the pixels from the crossing
line above (index 0) to the crossing line below (index `length + 1`). A bottom
edge is read the same way, turned a quarter: offsets are rows, positive ones in
the cell below, and the crossing lines are the vertical lines left and right.
"""

from __future__ import annotations

import math
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

import pytest
from playwright.sync_api import CDPSession, Locator, Page, ViewportSize, expect
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from grids_harness import FX01_HYPHENS, grid_with_answers
from nock.grid import Grid
from nock.protocol import GridView, grid_view
from spec006_harness import pinch
from spec019_harness import OpenWindow
from spec042_harness import (
    CELL_SELECTOR,
    RULE,
    WAIT_TIMEOUT_MS,
    Box,
    Rgb,
    box_of,
    cell_at,
    me,
    open_room,
    seed_value,
)
from spec044_harness import KEYBOARD_HIDDEN_KEY, expect_no_keyboard

# `--nock-hyphen` (`specs/_design/foundation.md`, « Colour tokens »).
HYPHEN: Rgb = (0x5E, 0x65, 0x73)

# The thickness of the dashes by the least cell side that takes it, and the
# period p of the dashes for each thickness (« Hyphen edges »).
THICKNESS_FROM_SIDE: list[tuple[float, int]] = [(72.0, 3), (36.0, 2), (0.0, 1)]
PERIOD_BY_THICKNESS: dict[int, int] = {1: 5, 2: 8, 3: 11}
LEAST_DASHES = 3
DASH_START_SHARE = 0.2
DASH_END_SHARE = 0.8
# A dash end may sit one pixel from the formula's: the formula reads the cell
# side, which is fractional, while the pixels count whole lines.
DASH_END_TOLERANCE_PX = 1

# How far from the line's pixel an edge reading goes, on each side.
READ_OFFSETS = 5
# How far the crossing lines are looked for around the cell's box.
CROSSING_SEARCH_PX = 3
# Where the interior of a cell is read beside an edge, in pixels from the line.
INTERIOR_OFFSET = 4
# How far past the grid's box a picture of the grid goes.
PICTURE_MARGIN = READ_OFFSETS + CROSSING_SEARCH_PX + 1

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
# The channels per pixel of the PNG colour types a screenshot can have:
# 2 is RGB and 6 is RGBA.
PNG_CHANNELS = {2: 3, 6: 4}

Run = tuple[int, int]  # a dash: its first pixel and the pixel after its last


class Side(StrEnum):
    """The edge of a cell that a hyphen mark names."""

    RIGHT = "right"
    BOTTOM = "bottom"


# ---- Screenshots ------------------------------------------------------------------


@dataclass(frozen=True)
class Picture:
    """The pixels of a screenshot clip, read at page coordinates."""

    left: int
    top: int
    width: int
    height: int
    rows: list[list[Rgb]]

    def at(self, x: int, y: int) -> Rgb:
        """The colour of the pixel at (x, y), in CSS px of the page.

        Raises:
            IndexError: if the pixel is outside the clip.
        """
        column = x - self.left
        line = y - self.top
        if not (0 <= column < self.width and 0 <= line < self.height):
            raise IndexError(f"({x}, {y}) is outside the picture")
        return self.rows[line][column]


def _paeth(left: int, up: int, up_left: int) -> int:
    """The PNG Paeth predictor."""
    estimate = left + up - up_left
    to_left = abs(estimate - left)
    to_up = abs(estimate - up)
    to_up_left = abs(estimate - up_left)
    if to_left <= to_up and to_left <= to_up_left:
        return left
    if to_up <= to_up_left:
        return up
    return up_left


def _unfilter(line: bytearray, previous: bytearray, kind: int, step: int) -> None:
    """Undo the PNG filter of one line of bytes, in place."""
    for index in range(len(line)):
        left = line[index - step] if index >= step else 0
        up = previous[index]
        up_left = previous[index - step] if index >= step else 0
        if kind == 0:
            predicted = 0
        elif kind == 1:
            predicted = left
        elif kind == 2:
            predicted = up
        elif kind == 3:
            predicted = (left + up) // 2
        elif kind == 4:
            predicted = _paeth(left, up, up_left)
        else:
            raise ValueError(f"unknown PNG filter {kind}")
        line[index] = (line[index] + predicted) % 256


def decode_png(png: bytes) -> tuple[int, int, list[list[Rgb]]]:
    """Decode an 8-bit RGB or RGBA PNG without interlacing.

    Args:
        png: The bytes of the PNG file.

    Returns:
        Its width, its height and its rows of pixels, top first (alpha dropped).

    Raises:
        ValueError: if the file is not a PNG of that kind.
    """
    if not png.startswith(PNG_SIGNATURE):
        raise ValueError("not a PNG file")
    width = 0
    height = 0
    channels = 0
    data = b""
    position = len(PNG_SIGNATURE)
    while position < len(png):
        length = int.from_bytes(png[position : position + 4], "big")
        kind = png[position + 4 : position + 8]
        body = png[position + 8 : position + 8 + length]
        if kind == b"IHDR":
            width = int.from_bytes(body[0:4], "big")
            height = int.from_bytes(body[4:8], "big")
            if body[8] != 8 or body[9] not in PNG_CHANNELS or body[12] != 0:
                raise ValueError(f"unexpected PNG header {body.hex()}")
            channels = PNG_CHANNELS[body[9]]
        elif kind == b"IDAT":
            data += body
        position += 12 + length
    raw = zlib.decompress(data)
    stride = width * channels
    previous = bytearray(stride)
    rows: list[list[Rgb]] = []
    for line_index in range(height):
        start = line_index * (stride + 1)
        line = bytearray(raw[start + 1 : start + 1 + stride])
        _unfilter(line, previous, raw[start], channels)
        pixels: list[Rgb] = []
        for index in range(0, stride, channels):
            pixels.append((line[index], line[index + 1], line[index + 2]))
        rows.append(pixels)
        previous = line
    return width, height, rows


def take_picture(
    page: Page, left: float, top: float, right: float, bottom: float
) -> Picture:
    """Screenshot the whole pixels that hold a box of the page, and decode them."""
    clip_left = math.floor(left)
    clip_top = math.floor(top)
    clip_width = math.ceil(right) - clip_left
    clip_height = math.ceil(bottom) - clip_top
    png = page.screenshot(
        clip={"x": clip_left, "y": clip_top, "width": clip_width, "height": clip_height}
    )
    width, height, rows = decode_png(png)
    assert (width, height) == (clip_width, clip_height), (width, height)
    return Picture(clip_left, clip_top, width, height, rows)


# ---- The geometry of « Hyphen edges » ----------------------------------------------


def js_round(value: float) -> int:
    """Round halves up, as JavaScript's `Math.round` does."""
    return math.floor(value + 0.5)


def dash_thickness(side: float) -> int:
    """The thickness t of the dashes on cells of side `side`: 1, 2 or 3 px."""
    for least_side, thickness in THICKNESS_FROM_SIDE:
        if side >= least_side:
            return thickness
    raise ValueError(f"no thickness for a side of {side}")


def thickness_offsets(thickness: int) -> list[int]:
    """The offsets from the line's pixel that the dashes cover.

    t = 1 is the line's pixel; t = 2 adds the next pixel into the following cell;
    t = 3 is one pixel on each side of it.
    """
    if thickness == 1:
        return [0]
    if thickness == 2:
        return [0, 1]
    return [-1, 0, 1]


def dash_count(side: float) -> int:
    """n = max(3, round(L / p)), with L = s - 1."""
    length = side - 1
    period = PERIOD_BY_THICKNESS[dash_thickness(side)]
    return max(LEAST_DASHES, js_round(length / period))


def expected_runs(side: float) -> list[Run]:
    """The dashes of « Hyphen edges », in pixels from the edge's start.

    Dash i runs from round((i + 0.2) L / n) to round((i + 0.8) L / n).
    """
    length = side - 1
    count = dash_count(side)
    runs: list[Run] = []
    for index in range(count):
        start = js_round((index + DASH_START_SHARE) * length / count)
        end = js_round((index + DASH_END_SHARE) * length / count)
        runs.append((start, end))
    return runs


def runs_of(pixels: list[Rgb], colour: Rgb) -> list[Run]:
    """The runs of `colour` in a list of pixels, as (first, after last) indexes."""
    runs: list[Run] = []
    start: int | None = None
    for index, pixel in enumerate(pixels):
        if pixel == colour and start is None:
            start = index
        if pixel != colour and start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(pixels)))
    return runs


def run_problems(found: list[Run], expected: list[Run]) -> list[str]:
    """How painted dashes differ from the formula's, each end within 1 px."""
    if len(found) != len(expected):
        return [f"{len(found)} dashes {found}, expected {len(expected)} {expected}"]
    problems: list[str] = []
    for (start, end), (want_start, want_end) in zip(found, expected, strict=True):
        if abs(start - want_start) > DASH_END_TOLERANCE_PX:
            problems.append(f"dash {start}-{end} starts away from {want_start}")
        if abs(end - want_end) > DASH_END_TOLERANCE_PX:
            problems.append(f"dash {start}-{end} ends away from {want_end}")
    return problems


# ---- Reading an edge --------------------------------------------------------------


@dataclass(frozen=True)
class EdgeReading:
    """The painted pixels around one edge of a cell.

    Attributes:
        side: The cell's side that was read.
        cell_side: The cell's side s, in CSS px (fractional at zoom 1).
        length: The pixels between the two crossing lines.
        first_inner: The page coordinate along the edge (y for a right edge, x
            for a bottom edge) of the first pixel after the first crossing line.
        pixels: By offset from the line's pixel, the pixels along the edge, from
            the first crossing line (index 0) to the second (`length + 1`).
    """

    side: Side
    cell_side: float
    length: int
    first_inner: int
    pixels: dict[int, list[Rgb]]

    def inner(self, offset: int) -> list[Rgb]:
        """The pixels along the edge between the crossing lines, at an offset."""
        return self.pixels[offset][1 : self.length + 1]

    def crossings(self, offset: int) -> tuple[Rgb, Rgb]:
        """The two pixels of the crossing lines, at an offset."""
        line = self.pixels[offset]
        return (line[0], line[self.length + 1])


def _rule_positions(colours: list[Rgb], first: int) -> list[int]:
    """The positions holding the rule grey, `first` being the position of index 0."""
    positions: list[int] = []
    for index, colour in enumerate(colours):
        if colour == RULE:
            positions.append(first + index)
    return positions


def _one_rule_position(colours: list[Rgb], first: int, what: str) -> int:
    """The one position of a list of pixels that holds the rule grey."""
    positions = _rule_positions(colours, first)
    if len(positions) != 1:
        pytest.fail(f"{what}: rule grey at {positions}, expected one pixel")
    return positions[0]


def grid_picture(page: Page) -> Picture:
    """Screenshot the grid and what an edge reading needs around it, and decode it.

    The clip goes `PICTURE_MARGIN` px past the grid on each side, inside the
    window, so that the edges of the outer cells can be read too.
    """
    grid = box_of(page.get_by_test_id("grid"))
    window = page.viewport_size
    assert window is not None
    left = max(0.0, grid.left - PICTURE_MARGIN)
    top = max(0.0, grid.top - PICTURE_MARGIN)
    right = min(float(window["width"]), grid.right + PICTURE_MARGIN)
    bottom = min(float(window["height"]), grid.bottom + PICTURE_MARGIN)
    return take_picture(page, left, top, right, bottom)


def _line_across(picture: Picture, reference: Box, side: Side) -> int:
    """The pixel of the plain grid line at the reference cell's right or bottom.

    It is read half way along the reference cell's edge: the one pixel of rule
    grey within a few pixels of the edge.
    """
    colours: list[Rgb] = []
    if side == Side.RIGHT:
        y = math.floor(reference.centre_y)
        start = math.floor(reference.right) - READ_OFFSETS
        for x in range(start, start + 2 * READ_OFFSETS):
            colours.append(picture.at(x, y))
    else:
        x = math.floor(reference.centre_x)
        start = math.floor(reference.bottom) - READ_OFFSETS
        for y in range(start, start + 2 * READ_OFFSETS):
            colours.append(picture.at(x, y))
    return _one_rule_position(colours, start, "the reference line")


def _pixel_reader(picture: Picture, side: Side, line: int) -> Callable[[int, int], Rgb]:
    """Read a pixel by its offset from the line and its position along the edge."""

    def across_right(offset: int, along: int) -> Rgb:
        return picture.at(line + offset, along)

    def across_bottom(offset: int, along: int) -> Rgb:
        return picture.at(along, line + offset)

    if side == Side.RIGHT:
        return across_right
    return across_bottom


def _crossing_line(
    pixel: Callable[[int, int], Rgb], along_from: int, window: int, what: str
) -> int:
    """Where a crossing grid line meets the edge, along it.

    The line is looked for 4 px from the edge, in the cell first, then in the
    next cell: my selection border may cover the crossing line's pixel inside
    my selected cell.
    """
    for offset in (-INTERIOR_OFFSET, INTERIOR_OFFSET):
        colours: list[Rgb] = []
        for along in range(along_from, along_from + window):
            colours.append(pixel(offset, along))
        positions = _rule_positions(colours, along_from)
        if len(positions) == 1:
            return positions[0]
    pytest.fail(f"{what}: no single rule grey pixel near {along_from}")


def read_edge(
    page: Page,
    picture: Picture,
    cell: tuple[int, int],
    side: Side,
    reference: tuple[int, int],
) -> EdgeReading:
    """Read the painted pixels around the right or bottom edge of a cell.

    Args:
        page: The room page, to read the cells' boxes.
        picture: The grid's pixels (`grid_picture`), taken in the state to read.
        cell: The cell's (row, column).
        side: The edge to read.
        reference: A cell whose right (or bottom) line is the same grid line
            and is plain half way along it, to find the line's pixel.

    Returns:
        The pixels around the edge, from crossing line to crossing line.
    """
    box = box_of(cell_at(page, *cell))
    line = _line_across(picture, box_of(cell_at(page, *reference)), side)
    pixel = _pixel_reader(picture, side, line)
    if side == Side.RIGHT:
        along_start = math.floor(box.top) - CROSSING_SEARCH_PX
        along_end = math.ceil(box.bottom) + CROSSING_SEARCH_PX
    else:
        along_start = math.floor(box.left) - CROSSING_SEARCH_PX
        along_end = math.ceil(box.right) + CROSSING_SEARCH_PX

    window = 2 * CROSSING_SEARCH_PX + 1
    first = _crossing_line(pixel, along_start, window, "the first crossing line")
    last = _crossing_line(pixel, along_end - window, window, "the second crossing line")

    pixels: dict[int, list[Rgb]] = {}
    for offset in range(-READ_OFFSETS, READ_OFFSETS + 1):
        along_pixels: list[Rgb] = []
        for along in range(first, last + 1):
            along_pixels.append(pixel(offset, along))
        pixels[offset] = along_pixels
    return EdgeReading(
        side=side,
        cell_side=box.width,
        length=last - first - 1,
        first_inner=first + 1,
        pixels=pixels,
    )


def hyphen_positions(reading: EdgeReading) -> dict[int, list[int]]:
    """By offset, the indexes along the edge (from 0) painted `--nock-hyphen`."""
    found: dict[int, list[int]] = {}
    for offset in reading.pixels:
        indexes: list[int] = []
        for index, colour in enumerate(reading.inner(offset)):
            if colour == HYPHEN:
                indexes.append(index)
        found[offset] = indexes
    return found


def plain_edge_problems(reading: EdgeReading) -> list[str]:
    """How an edge differs from the plain line: rule grey all along its pixel."""
    problems: list[str] = []
    for index, colour in enumerate(reading.inner(0)):
        if colour != RULE:
            problems.append(f"pixel {index} along the line is {colour}")
    return problems


# ---- AC-11's start: FX-02 zoomed to 2 on a phone held upright ---------------------

PHONE_WIDTH = 360
PHONE_HEIGHT = 740
# Fingers from 100 to 200 px apart double the zoom (rule 3).
PINCH_TO_TWO = (100.0, 200.0)

# Two animation frames: a scroll made at once has happened, an animated one not.
TWO_FRAMES_SCRIPT = (
    "() => new Promise(resolve =>"
    " requestAnimationFrame(() => requestAnimationFrame(() => resolve(null))))"
)
SCROLL_SCRIPT = "element => [element.scrollLeft, element.scrollTop]"
SCROLL_TO_CORNER_SCRIPT = "element => element.scrollTo(0, 0)"


def viewport_of(page: Page) -> Locator:
    """The grid's viewport, the element that scrolls (`grid-viewport`)."""
    return page.get_by_test_id("grid-viewport")


def read_scroll(viewport: Locator) -> tuple[float, float]:
    """The viewport's scroll, as (left, top)."""
    values = viewport.evaluate(SCROLL_SCRIPT)
    assert isinstance(values, list), values
    return float(values[0]), float(values[1])


def wait_two_frames(page: Page) -> None:
    """Wait two animation frames: a scroll made at once is done by then."""
    page.evaluate(TWO_FRAMES_SCRIPT)


def expect_selected(page: Page, row: int, column: int, direction: str) -> None:
    """Wait until the grid's selection is (row, column) in `direction`.

    Args:
        page: The room page.
        row: The selected cell's row.
        column: The selected cell's column.
        direction: `"across"` or `"down"`.
    """
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)


def open_phone_room(
    window: OpenWindow, base_url: str, view: GridView, *, keyboard_hidden: bool
) -> Page:
    """Open spec 042's mocked room on a touch phone held upright, at zoom 1."""
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


def open_ac11_start(window: OpenWindow, base_url: str, grid: Grid) -> Page:
    """AC-11's start: FX-02 zoomed to 2, at the grid's top-left corner."""
    return open_zoomed(window, base_url, grid_view(grid), keyboard_hidden=False)


# ---- Taps and drags by a finger, a pen or a mouse (Chromium only) ------------------

Point = tuple[float, float]  # (x, y) in CSS px of the page

# A drag moves in this many equal steps, as a hand moves in several events.
DRAG_STEPS = 10


class Pointer(StrEnum):
    """The kind of pointer, as the page's `PointerEvent.pointerType` reads it."""

    TOUCH = "touch"
    PEN = "pen"
    MOUSE = "mouse"


def shown_centre(page: Page, target: Locator) -> Point:
    """The centre of the part of a cell or clue that the viewport shows.

    A locator's own tap first scrolls its element into view, which would scroll
    the viewport under test: the zoomed tests tap this point instead.
    """
    shown = box_of(target)
    view = box_of(viewport_of(page))
    left = max(shown.left, view.left)
    right = min(shown.right, view.right)
    top = max(shown.top, view.top)
    bottom = min(shown.bottom, view.bottom)
    assert left < right, f"{shown} is not in the viewport {view} across"
    assert top < bottom, f"{shown} is not in the viewport {view} down"
    return (left + right) / 2, (top + bottom) / 2


def tap_shown_part(page: Page, target: Locator) -> None:
    """Touch the centre of the part of a cell or clue that the viewport shows."""
    x, y = shown_centre(page, target)
    page.touchscreen.tap(x, y)


def _send_touch(session: CDPSession, kind: str, fingers: list[Point]) -> None:
    """One `Input.dispatchTouchEvent` with the fingers now on the screen.

    Finger `n` of the list has the touch id `n`. An id that is new in a `touchMove`
    presses a finger; a `touchEnd` with no finger lifts them all.
    """
    touch_points: list[dict[str, float]] = []
    for identifier, finger in enumerate(fingers):
        touch_points.append({"x": finger[0], "y": finger[1], "id": identifier})
    event = {"type": kind, "touchPoints": touch_points}
    session.send("Input.dispatchTouchEvent", event)


def _send_mouse(
    session: CDPSession, pointer: Pointer, kind: str, point: Point, pressed: bool
) -> None:
    """One `Input.dispatchMouseEvent` of a pen or a mouse, its tip down or not.

    A move with the tip up is a hover and names no button; a press, a release and
    a move with the tip down name the left one.
    """
    pressed_buttons = 1 if pressed else 0
    button = "left"
    if kind == "mouseMoved" and not pressed:
        button = "none"
    session.send(
        "Input.dispatchMouseEvent",
        {
            "type": kind,
            "x": point[0],
            "y": point[1],
            "button": button,
            "buttons": pressed_buttons,
            "clickCount": 1,
            "pointerType": pointer.value,
        },
    )


def _drag_path(start: Point, offset: Point) -> list[Point]:
    """The points a drag goes through after its start, its end last."""
    path: list[Point] = []
    for step in range(1, DRAG_STEPS + 1):
        share = step / DRAG_STEPS
        path.append((start[0] + offset[0] * share, start[1] + offset[1] * share))
    return path


def tap_with(page: Page, pointer: Pointer, point: Point) -> None:
    """Put a finger, a pen or a mouse down at a point and lift it there.

    A pen first hovers at the point, as a real pen comes down from above it.
    """
    session = page.context.new_cdp_session(page)
    try:
        if pointer == Pointer.TOUCH:
            _send_touch(session, "touchStart", [point])
            _send_touch(session, "touchEnd", [])
        else:
            _send_mouse(session, pointer, "mouseMoved", point, pressed=False)
            _send_mouse(session, pointer, "mousePressed", point, pressed=True)
            _send_mouse(session, pointer, "mouseReleased", point, pressed=False)
    finally:
        session.detach()


def drag_with(page: Page, pointer: Pointer, start: Point, offset: Point) -> None:
    """Drag a finger, a pen or a mouse from a point by an offset, then lift it.

    Args:
        page: The page to drag on.
        pointer: The kind of pointer.
        start: Where the pointer goes down, in CSS px of the page.
        offset: How far it moves before it lifts, as (x, y) in CSS px.
    """
    path = _drag_path(start, offset)
    session = page.context.new_cdp_session(page)
    try:
        if pointer == Pointer.TOUCH:
            _send_touch(session, "touchStart", [start])
            for point in path:
                _send_touch(session, "touchMove", [point])
            _send_touch(session, "touchEnd", [])
        else:
            _send_mouse(session, pointer, "mouseMoved", start, pressed=False)
            _send_mouse(session, pointer, "mousePressed", start, pressed=True)
            for point in path:
                _send_mouse(session, pointer, "mouseMoved", point, pressed=True)
            _send_mouse(session, pointer, "mouseReleased", path[-1], pressed=False)
    finally:
        session.detach()


def pinch_beside_a_pen(
    page: Page,
    held_finger: Point,
    pen: tuple[Point, Point],
    moving_finger: tuple[Point, Point],
) -> None:
    """Pinch with two fingers while a pen, dragged first, stays pressed beside them.

    A first finger goes down and stays still; the pen goes down and is dragged by
    its offset; a second finger goes down and is dragged by its offset; the
    fingers lift, then the pen.

    Args:
        page: The page to pinch on.
        held_finger: Where the first finger stays down.
        pen: Where the pen goes down, and how far it moves before it stays still.
        moving_finger: Where the second finger goes down, and how far it moves.
    """
    pen_start, pen_offset = pen
    pen_path = _drag_path(pen_start, pen_offset)
    finger_start, finger_offset = moving_finger
    finger_path = _drag_path(finger_start, finger_offset)
    session = page.context.new_cdp_session(page)
    try:
        _send_touch(session, "touchStart", [held_finger])
        _send_mouse(session, Pointer.PEN, "mouseMoved", pen_start, pressed=False)
        _send_mouse(session, Pointer.PEN, "mousePressed", pen_start, pressed=True)
        for point in pen_path:
            _send_mouse(session, Pointer.PEN, "mouseMoved", point, pressed=True)
        _send_touch(session, "touchMove", [held_finger, finger_start])
        for point in finger_path:
            _send_touch(session, "touchMove", [held_finger, point])
        _send_touch(session, "touchEnd", [])
        _send_mouse(session, Pointer.PEN, "mouseReleased", pen_path[-1], pressed=False)
    finally:
        session.detach()


# ---- The hyphen edge tests: windows, cell sizes and cells ---------------------------

MEDIUM_WINDOW = ViewportSize(width=700, height=400)  # FX-01 cells of about 57.4 px
SMALL_WINDOW = ViewportSize(width=568, height=320)  # FX-02 cells of about 12.1 px
LARGE_WINDOW = ViewportSize(width=1024, height=768)  # FX-01 cells of about 130.6 px

Cell = tuple[int, int]
SideRange = tuple[float, float]
MEDIUM_SIDES: SideRange = (50.0, 64.0)
SMALL_SIDES: SideRange = (10.0, 20.0)
LARGE_SIDES: SideRange = (72.0, 200.0)

VIDE_EDGE: Cell = (2, 2)  # its right edge
NAVAL_EDGE: Cell = (1, 1)  # its bottom edge
TAMIS_EDGE: Cell = (1, 1)  # its right edge
FX02_EDGE: Cell = (1, 4)  # its right edge


# True once the cell's side is fractional and in [low, high).
SIDE_SCRIPT = """
([selector, low, high]) => {
  const cell = document.querySelector(selector);
  if (cell === null) {
    return false;
  }
  const side = cell.getBoundingClientRect().width;
  return low <= side && side < high && side !== Math.trunc(side);
}
"""


def require_side(page: Page, cell: Cell, sides: SideRange) -> float:
    """The cell's side, once it is fractional and in `sides`.

    The grid fits its area after the snapshot shows, so the side is polled; the
    test fails, naming the side, when it is not such a side in time.
    """
    row, column = cell
    low, high = sides
    selector = CELL_SELECTOR.format(row=row, column=column)
    try:
        page.wait_for_function(
            SIDE_SCRIPT, arg=[selector, low, high], timeout=WAIT_TIMEOUT_MS
        )
    except PlaywrightTimeoutError:
        side = box_of(cell_at(page, *cell)).width
        pytest.fail(f"cells of {side} px, expected a fractional side in {sides}")
    return box_of(cell_at(page, *cell)).width


def open_fx01(page: Page, base_url: str, view: GridView, window: ViewportSize) -> None:
    """Open FX-01's room at `window`, `p1` alone, on a view."""
    page.set_viewport_size(window)
    open_room(page, base_url, view, [me()])


@pytest.fixture
def hyphen_grid(fx01_text: str) -> Grid:
    """FX-01 with `VI-DE` and `NA-VAL`."""
    return grid_with_answers(fx01_text, FX01_HYPHENS)
