"""Shared setup of the tests of spec 042: grid cells.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 042 uses: the values of the spec's
tables, the mocked room (opening, reloading, catching up), the readers of the
cells' boxes and marks, the hit test of "Test harness", the switches and the
geometry rules. The tests are in these files, one per group of criteria:

- `test_spec_042_ac01_ac03_lines_and_backgrounds.py`: AC-1 to AC-3.
- `test_spec_042_ac04_ac08_letters_and_marks.py`: AC-4 to AC-8.
- `test_spec_042_ac09_ac11_other_players.py`: AC-9 to AC-11.
- `test_spec_042_ac12_ac14_clue_cells.py`: AC-12 to AC-14.
- `test_spec_042_ac15_ac16_arrows.py`: AC-15 and AC-16.
- `test_spec_042_ac17_ac18_order_and_small_cells.py`: AC-17 and AC-18.
- `test_spec_042_ac19_ac20_switches_and_scans.py`: AC-19 and AC-20.

It reuses the harnesses of the specs it builds on: spec 019's mocked socket
(whose `send` uses the newest socket, so a reloaded page can be answered), its
windows and spec 013 AC-6's layout checks; spec 034's mocked catch-up route and
stored record; spec 041's colour readers and tokens; spec 035's frames, scans and
keyboard walker. Every helper that opens or reloads a page waits for the fonts
before it returns (spec 041's rule).

Readings: a reading is a JSON object read from the page with `page.evaluate`.
Its values are the page's (texts, numbers, lists, objects and nulls mixed), so a
reading is typed `dict[str, Any]` (`Reading`). A box read from the page is
`[left, top, right, bottom]`, turned into a `Box`.

The fixtures (`fx01_grid`, `catalogue`, ...) are defined in each test file as thin
wrappers: a fixture imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import json
import math
import re
import zlib
from collections.abc import Callable, Sequence
from datetime import date
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Arrow, ClueCell, Grid, LetterCell
from nock.protocol import (
    CheckResult,
    ClueRef,
    Direction,
    FlagView,
    GridTarget,
    GridView,
    HelpMode,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Selection,
    SelectionMoved,
    Snapshot,
    grid_view,
)
from room_panels import open_menu
from spec019_harness import MockRoomSocket, with_letter_cells
from spec034_harness import CATCH_UP_ROUTE, CatchUpRoute, seed_storage
from spec035_harness import COLOUR_CONTRAST_JS, credits, load_fr

# ---- Constants --------------------------------------------------------------

ROOM_CODE = "ABC123"
# The resume token of spec 034's stored identity, so that its catch-up request
# carries the token of the snapshot.
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
WAIT_TIMEOUT_MS = 5000
FOLLOW_MS = 300  # "within 300 ms"
QUIET_MS = 300  # "the page sent no frame within 300 ms"
FX01_CELL_COUNT = 25

POSITION_TOLERANCE_PX = 1.0
SIZE_TOLERANCE_PX = 0.5
FONT_TOLERANCE_PX = 0.1
MIX_TOLERANCE = 1.0
ALPHA_TOLERANCE = 0.01
MIN_MARK_CONTRAST = 3.0

TINT_STORAGE_KEY = "nock.others_tint"
ACCESS_STORAGE_KEY = "nock.accessibility"
TINT_SWITCH = "others-tint-switch"
ACCESS_SWITCH = "access-switch"

Rgb = tuple[int, int, int]
Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]
# A JSON object read from the page: its values are the page's (texts, numbers,
# lists, objects and nulls mixed), so their type is not known here.
Reading = dict[str, Any]

# The colours of the criteria (`_design.md` section 2, spec 041's tokens).
RULE: Rgb = (154, 163, 178)
WHITE: Rgb = (255, 255, 255)
SELECTED: Rgb = (207, 221, 243)
LOCKED: Rgb = (227, 231, 238)
WORD: Rgb = (230, 237, 249)
INK: Rgb = (20, 24, 31)
NAVY: Rgb = (27, 47, 85)
RED: Rgb = (180, 35, 24)
REVEAL: Rgb = (194, 65, 12)
CLUE_BG: Rgb = (238, 242, 248)
CLUE_INK: Rgb = (27, 34, 48)
# `--player-colour-0` to `--player-colour-7` (spec 041).
PLAYER_COLOURS: tuple[Rgb, ...] = (
    (0x60, 0x48, 0x00),
    (0x60, 0x88, 0x38),
    (0x00, 0x88, 0x78),
    (0x68, 0x38, 0xE0),
    (0xB8, 0x38, 0x50),
    (0xD0, 0x00, 0xA0),
    (0xB0, 0x60, 0x00),
    (0x78, 0x40, 0x30),
)
TINT_SHARE = 0.16
FLASH_OPACITY = 0.38

UI_FONT_STACK = ["Source Sans 3", "Segoe UI", "system-ui", "sans-serif"]
CLUE_FONT_STACK = [
    "IBM Plex Sans Condensed",
    "Arial Narrow",
    "Roboto Condensed",
    "sans-serif",
]

# The snapshot's players: `p1` is `you` and host, with colour 0.
NICKNAMES = {
    "p1": "ANA",
    "p2": "BOB",
    "p3": "CY",
    "p4": "DAN",
    "p5": "EVE",
    "p6": "FAY",
    "p7": "GUS",
    "p8": "HAL",
}
DISPLAY_NICKNAMES = ["Ana", "Bob", "Cy", "Dan", "Eve", "Fay", "Gus", "Hal"]
FX01_CLUE_TEXTS = [
    "Passoire fine",
    "De la marine",
    "Artiste muet",
    "Fatales à César",
    "Flaire",
    "Sans contenu",
    "Fin de prière",
    "Alourdit le ballon",
]

# The corners in their order of arrival ("Other players on a cell").
CORNERS = ["top-left", "top-right", "bottom-right", "bottom-left"]
# The triangle polygon's `points`, by corner.
TRIANGLE_POINTS = {
    "top-left": "0,0 10,0 0,10",
    "top-right": "0,0 10,0 10,10",
    "bottom-right": "10,0 10,10 0,10",
    "bottom-left": "0,0 10,10 0,10",
}
# The shapes of `PLAYER_ICONS[N]` (spec 041, `_design.md` section 6): per index,
# each shape's tag and the attributes the design gives it.
PLAYER_ICON_SHAPES: list[list[tuple[str, dict[str, str]]]] = [
    [("circle", {"cx": "5", "cy": "5", "r": "4.4"})],
    [("rect", {"x": "0.9", "y": "0.9", "width": "8.2", "height": "8.2"})],
    [("polygon", {"points": "5,0.4 9.7,9.3 0.3,9.3"})],
    [("polygon", {"points": "5,0.1 9.9,5 5,9.9 0.1,5"})],
    [
        (
            "polygon",
            {
                "points": (
                    "5,0.2 6.3,3.6 9.9,3.7 7.1,6 8.1,9.6 5,7.5 1.9,9.6 2.9,6"
                    " 0.1,3.7 3.7,3.6"
                )
            },
        )
    ],
    [
        (
            "polygon",
            {
                "points": (
                    "3.3,0.4 6.7,0.4 6.7,3.3 9.6,3.3 9.6,6.7 6.7,6.7 6.7,9.6"
                    " 3.3,9.6 3.3,6.7 0.4,6.7 0.4,3.3 3.3,3.3"
                )
            },
        )
    ],
    [("path", {"d": "M5 9.4L1.1 5.5A2.45 2.45 0 0 1 5 2.3A2.45 2.45 0 0 1 8.9 5.5Z"})],
    [("polygon", {"points": "0.6,0.6 9.4,0.6 5.6,5 9.4,9.4 0.6,9.4 4.4,5"})],
]
# The attributes compared as numbers (the others as written).
NUMBER_ATTRIBUTES = {"cx", "cy", "r", "x", "y", "width", "height"}

# The direction arrows' `path` `d` and `polygon` `points`, by `data-arrow`.
ARROW_SHAPES = {
    "right": ("M2 12H15", "14,7.5 22,12 14,16.5"),
    "down": ("M12 2V15", "7.5,14 12,22 16.5,14"),
    "down_then_right": ("M5 2V10Q5 15 10 15H15", "14,10.5 22,15 14,19.5"),
    "right_then_down": ("M2 5H10Q15 5 15 10V15", "10.5,14 15,22 19.5,14"),
}
# Spec 006's `data-side`, by `data-arrow`.
ARROW_SIDES = {
    "right": "right",
    "right_then_down": "right",
    "down": "bottom",
    "down_then_right": "bottom",
}
FLAG_PATHS = ["M6 21V4", "M6 4h12l-3 4.5 3 4.5H6z"]

IDES = ClueRef(row=0, column=3, clue_index=0)
NAVAL = ClueRef(row=0, column=0, clue_index=1)

# ---- Geometry ---------------------------------------------------------------


class Box(NamedTuple):
    """A bounding box (`getBoundingClientRect`), in CSS px."""

    left: float
    top: float
    right: float
    bottom: float

    @property
    def width(self) -> float:
        return self.right - self.left

    @property
    def height(self) -> float:
        return self.bottom - self.top

    @property
    def centre_x(self) -> float:
        return (self.left + self.right) / 2

    @property
    def centre_y(self) -> float:
        return (self.top + self.bottom) / 2


def to_box(raw: object) -> Box:
    """Turn a box read from the page, `[left, top, right, bottom]`, into a `Box`."""
    assert isinstance(raw, list), raw
    assert len(raw) == 4, raw
    edges: list[float] = []
    for value in raw:
        assert isinstance(value, (int, float)), raw
        edges.append(float(value))
    return Box(edges[0], edges[1], edges[2], edges[3])


def inner_box(cell: Box) -> Box:
    """The inner box of a cell: its box less its 1 px right and bottom lines."""
    return Box(cell.left, cell.top, cell.right - 1, cell.bottom - 1)


def triangle_side(side: float) -> float:
    """`t = max(6, round(0.3 s))`, rounding halves up as JavaScript does."""
    return float(max(6, math.floor(0.3 * side + 0.5)))


def icon_side(side: float) -> float:
    """The side of an Accessibilité icon's box, `max(6px, 0.24 s)`."""
    return max(6.0, 0.24 * side)


def icon_inset(side: float) -> float:
    """The inset of an icon from its corner, `max(1px, 0.04 s)`."""
    return max(1.0, 0.04 * side)


def notch_size(side: float) -> tuple[float, float]:
    """The revealed notch's width and height, `max(7, 0.22 s)` by `max(4, 0.11 s)`."""
    return (max(7.0, 0.22 * side), max(4.0, 0.11 * side))


def arrow_side(side: float) -> float:
    """The side of a direction arrow's box, `a = max(9px, 0.26 s)`."""
    return max(9.0, 0.26 * side)


def flag_side(side: float) -> float:
    """The side of a clue flag's square, `f = max(8px, 0.22 s)`."""
    return max(8.0, 0.22 * side)


def clue_font_size(side: float) -> float:
    """The clue text's font size, `max(6px, 0.145 s)`."""
    return max(6.0, 0.145 * side)


def close_to(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


def corner_point(inner: Box, corner: str) -> tuple[float, float]:
    """The point of the inner box at `corner`."""
    x = inner.left if corner.endswith("left") else inner.right
    y = inner.top if corner.startswith("top") else inner.bottom
    return (x, y)


def corner_distances(
    inner: Box, corner: str, x: float, y: float
) -> tuple[float, float]:
    """The distances of a point from the two edges of the inner box at `corner`."""
    dx = x - inner.left if corner.endswith("left") else inner.right - x
    dy = y - inner.top if corner.startswith("top") else inner.bottom - y
    return (dx, dy)


def inside_triangle(inner: Box, corner: str, t: float, x: float, y: float) -> bool:
    """ "Inside a triangle" of "Test harness": `dx + dy < t - 1.5`, both positive."""
    dx, dy = corner_distances(inner, corner, x, y)
    return dx >= 0 and dy >= 0 and dx + dy < t - 1.5


def point_inside(corner: str, inner: Box, inset: float) -> tuple[float, float]:
    """The point `inset` px inside both edges of the inner box at `corner`."""
    x = inner.left + inset if corner.endswith("left") else inner.right - inset
    y = inner.top + inset if corner.startswith("top") else inner.bottom - inset
    return (x, y)


def box_problems(
    name: str,
    box: Box,
    *,
    width: float | None = None,
    height: float | None = None,
    left: float | None = None,
    top: float | None = None,
    right: float | None = None,
    bottom: float | None = None,
    centre_x: float | None = None,
    centre_y: float | None = None,
) -> list[str]:
    """How a box differs from the sizes (0.5 px) and positions (1 px) given."""
    problems: list[str] = []
    sizes = {"width": (box.width, width), "height": (box.height, height)}
    for label, (actual, expected) in sizes.items():
        if expected is not None and not close_to(actual, expected, SIZE_TOLERANCE_PX):
            problems.append(f"{name}: {label} {actual:.2f}, expected {expected:.2f}")
    positions = {
        "left": (box.left, left),
        "top": (box.top, top),
        "right": (box.right, right),
        "bottom": (box.bottom, bottom),
        "centre x": (box.centre_x, centre_x),
        "centre y": (box.centre_y, centre_y),
    }
    for label, (actual, expected) in positions.items():
        if expected is None:
            continue
        if not close_to(actual, expected, POSITION_TOLERANCE_PX):
            problems.append(f"{name}: {label} {actual:.2f}, expected {expected:.2f}")
    return problems


def overlap_px(first: Box, second: Box) -> float:
    """By how much two boxes overlap: the smaller of their two axis overlaps."""
    across = min(first.right, second.right) - max(first.left, second.left)
    down = min(first.bottom, second.bottom) - max(first.top, second.top)
    return max(0.0, min(across, down))


# ---- Colours ----------------------------------------------------------------

Colour = tuple[float, float, float, float]


def to_colour(found: object) -> Colour:
    """Check and convert a parsed colour: what `parseColour` returned, or a tuple."""
    assert isinstance(found, (list, tuple)), found
    assert len(found) == 4, found
    channels: list[float] = []
    for value in found:
        assert isinstance(value, (int, float)), found
        channels.append(float(value))
    return (channels[0], channels[1], channels[2], channels[3])


def colour_problems(name: str, actual: object, expected: Rgb) -> list[str]:
    """Exact channels and opaque (a token, "Test harness")."""
    colour = to_colour(actual)
    channels = (round(colour[0]), round(colour[1]), round(colour[2]))
    exact = (colour[0], colour[1], colour[2]) == (
        float(expected[0]),
        float(expected[1]),
        float(expected[2]),
    )
    if not exact or abs(colour[3] - 1.0) > ALPHA_TOLERANCE:
        return [f"{name}: {channels} alpha {colour[3]}, expected {expected}"]
    return []


def mixed_colour_problems(name: str, actual: object, expected: Rgb) -> list[str]:
    """Channels within 1 and opaque (a `color-mix` or a composite)."""
    colour = to_colour(actual)
    for index in range(3):
        if abs(colour[index] - expected[index]) > MIX_TOLERANCE:
            return [f"{name}: {colour}, expected within 1 of {expected}"]
    if abs(colour[3] - 1.0) > ALPHA_TOLERANCE:
        return [f"{name}: {colour} is not opaque"]
    return []


def is_transparent(actual: object) -> bool:
    return abs(to_colour(actual)[3]) <= ALPHA_TOLERANCE


def mix_over_white(colour: Rgb, share: float) -> tuple[float, float, float]:
    """`colour` at `share` over white, per channel (`color-mix` in srgb)."""
    mixed: list[float] = []
    for channel in colour:
        mixed.append(channel * share + 255 * (1 - share))
    return (mixed[0], mixed[1], mixed[2])


def tint_of(colour_index: int) -> Rgb:
    """The word tint of a player colour, rounded to whole channels."""
    red, green, blue = mix_over_white(PLAYER_COLOURS[colour_index], TINT_SHARE)
    return (round(red), round(green), round(blue))


def flash_composite(colour_index: int) -> tuple[float, float, float]:
    """The flash of spec 041: the player colour at 38 % over white."""
    return mix_over_white(PLAYER_COLOURS[colour_index], FLASH_OPACITY)


def _channel(value: float) -> float:
    scaled = value / 255
    if scaled <= 0.03928:
        return scaled / 12.92
    return ((scaled + 0.055) / 1.055) ** 2.4


def _luminance(colour: Sequence[float]) -> float:
    return (
        0.2126 * _channel(colour[0])
        + 0.7152 * _channel(colour[1])
        + 0.0722 * _channel(colour[2])
    )


def contrast_ratio(first: Sequence[float], second: Sequence[float]) -> float:
    """The WCAG 2.x contrast of two opaque colours (spec 035's formula)."""
    lighter = max(_luminance(first), _luminance(second))
    darker = min(_luminance(first), _luminance(second))
    return (lighter + 0.05) / (darker + 0.05)


# ---- In-page readers ----------------------------------------------------------

# The colour helpers of tests/colour_contrast.js, then the readers of this spec.
READERS_JS = COLOUR_CONTRAST_JS + r"""
function boxOf(element) {
  const rect = element.getBoundingClientRect();
  return [rect.left, rect.top, rect.right, rect.bottom];
}
function colourOf(text) {
  if (text === null || text === undefined || text === '' || text === 'none') {
    return null;
  }
  return parseColour(text);
}
function attributesOf(element) {
  const found = {};
  for (const attribute of element.attributes) {
    found[attribute.name] = attribute.value;
  }
  return found;
}
function shapeOf(element) {
  const style = getComputedStyle(element);
  return {
    tag: element.tagName.toLowerCase(),
    attributes: attributesOf(element),
    fill: style.fill,
    fillColour: colourOf(style.fill),
    stroke: style.stroke,
    strokeColour: colourOf(style.stroke),
    strokeWidth: style.strokeWidth,
    linecap: style.strokeLinecap,
    linejoin: style.strokeLinejoin,
  };
}
function svgOf(svg) {
  const shapes = [];
  for (const child of svg.children) {
    shapes.push(shapeOf(child));
  }
  return {
    testId: svg.getAttribute('data-testid'),
    dataIcon: svg.getAttribute('data-icon'),
    viewBox: svg.getAttribute('viewBox'),
    aspect: svg.getAttribute('preserveAspectRatio'),
    ariaHidden: svg.getAttribute('aria-hidden'),
    box: boxOf(svg),
    shapes: shapes,
  };
}
function svgsIn(element) {
  const found = [];
  for (const svg of element.querySelectorAll('svg')) {
    found.push(svgOf(svg));
  }
  return found;
}
function markOf(element) {
  const style = getComputedStyle(element);
  return {
    testId: element.getAttribute('data-testid'),
    ariaHidden: element.getAttribute('aria-hidden'),
    text: element.textContent,
    position: style.position,
    zIndex: style.zIndex,
    pointerEvents: style.pointerEvents,
    visibility: style.visibility,
    box: boxOf(element),
  };
}
"""

CELL_SELECTOR = '[data-testid="cell"][data-row="{row}"][data-column="{column}"]'

# The other players' cursors of one cell: the cell's box, then for each
# `remote-selection` its attributes, its mark styles, its box and its `svg`s.
CURSORS_SCRIPT = "cell => {\n" + READERS_JS + r"""
const cursors = [];
for (const element of cell.querySelectorAll('[data-testid="remote-selection"]')) {
  const reading = markOf(element);
  reading.playerId = element.getAttribute('data-player-id');
  reading.colour = element.getAttribute('data-colour');
  reading.corner = element.getAttribute('data-corner');
  reading.shape = element.getAttribute('data-shape');
  reading.svgs = svgsIn(element);
  cursors.push(reading);
}
return {cell: boxOf(cell), cursors: cursors};
}"""

# Each roster item: its player, its `data-colour`, its swatch's parsed
# background and the `svg`s the swatch holds.
SWATCHES_SCRIPT = "() => {\n" + READERS_JS + r"""
const found = [];
for (const item of document.querySelectorAll('[data-testid="roster-player"]')) {
  const swatch = item.querySelector('[data-testid="roster-colour"]');
  found.push({
    playerId: item.getAttribute('data-player-id'),
    colour: item.getAttribute('data-colour'),
    background: swatch === null
      ? null : parseColour(getComputedStyle(swatch).backgroundColor),
    svgs: swatch === null ? [] : svgsIn(swatch),
  });
}
return found;
}"""

# A computed colour property of an element, parsed.
COLOUR_SCRIPT = (
    "([element, property]) => {\n"
    + READERS_JS
    + "\nreturn parseColour(getComputedStyle(element)[property]);\n}"
)

# Every `clue-arrow` of the page, with its cell and the shapes it holds.
ARROWS_SCRIPT = "() => {\n" + READERS_JS + r"""
const found = [];
for (const arrow of document.querySelectorAll('[data-testid="clue-arrow"]')) {
  const style = getComputedStyle(arrow);
  const cell = arrow.closest('[data-testid="cell"]');
  const reading = markOf(arrow);
  reading.tag = arrow.tagName.toLowerCase();
  reading.arrow = arrow.getAttribute('data-arrow');
  reading.side = arrow.getAttribute('data-side');
  reading.clueRow = arrow.getAttribute('data-clue-row');
  reading.clueColumn = arrow.getAttribute('data-clue-column');
  reading.clueIndex = arrow.getAttribute('data-clue-index');
  reading.viewBox = arrow.getAttribute('viewBox');
  reading.filter = style.filter;
  reading.cellRow = cell === null ? null : cell.getAttribute('data-row');
  reading.cellColumn = cell === null ? null : cell.getAttribute('data-column');
  reading.cellType = cell === null ? null : cell.getAttribute('data-type');
  reading.parentIsCell = cell !== null && arrow.parentElement === cell;
  reading.cell = cell === null ? null : boxOf(cell);
  const shapes = [];
  for (const child of arrow.children) {
    shapes.push(shapeOf(child));
  }
  reading.shapes = shapes;
  found.push(reading);
}
return found;
}"""

# The element at a point of the page and its ancestors' test ids, nearest first.
HIT_SCRIPT = r"""
([x, y]) => {
  const found = document.elementFromPoint(x, y);
  const chain = [];
  for (let node = found; node !== null; node = node.parentElement) {
    let name = node.getAttribute('data-testid');
    if (name === 'remote-selection') {
      name = `remote-selection:${node.getAttribute('data-player-id')}`;
    }
    chain.push({name: name, tag: node.tagName.toLowerCase()});
  }
  return chain;
}
"""

HIT_STYLE_ID = "spec042-hit-test"
# The test style of "Hit tests": `pointer-events: auto !important` on every
# descendant of every `cell`, after `scrollIntoView` of the cell. The
# `cell-selection` element keeps its own `pointer-events: none` unless the test
# asks for it (AC-17's "With pointer events on for the probe").
START_HIT_TEST_SCRIPT = """
([selector, styleId, withSelection]) => {
  document.querySelector(selector).scrollIntoView();
  const style = document.createElement('style');
  style.id = styleId;
  const skipped = withSelection ? '' : ':not([data-testid="cell-selection"])';
  style.textContent = '[data-testid="cell"] *' + skipped
    + ' { pointer-events: auto !important; }';
  document.head.appendChild(style);
}
"""
END_HIT_TEST_SCRIPT = "styleId => document.getElementById(styleId)?.remove()"


# ---- Snapshots and players ----------------------------------------------------


def player(
    player_id: str,
    colour: int,
    *,
    selection: Selection | None = None,
    state: PlayerState = PlayerState.ACTIVE,
) -> PlayerView:
    """A player of the snapshot: `p1` is host; nicknames from NICKNAMES."""
    return PlayerView(
        player_id=player_id,
        nickname=NICKNAMES[player_id],
        colour=colour,
        state=state,
        is_host=player_id == "p1",
        muted=False,
        selection=selection,
    )


def me() -> PlayerView:
    """`p1`: `you`, `ANA`, colour 0, host."""
    return player("p1", 0)


def selecting(row: int, column: int, direction: Direction) -> Selection:
    return Selection(row=row, column=column, direction=direction)


def fx01_view(grid: Grid, changes: ChangeList | None = None) -> GridView:
    """FX-01's view, with some letter cells changed with `model_copy`."""
    view = grid_view(grid)
    if changes is None:
        return view
    return with_letter_cells(view, changes)


def snapshot_frame(
    view: GridView,
    players: list[PlayerView],
    *,
    seq: int = 5,
    flags: Sequence[FlagView] = (),
    budget: RevealBudget | None = None,
) -> str:
    """A snapshot for `p1` (help mode `free`, 5 letters and 1 word by default)."""
    shown_budget = RevealBudget(letters=5, words=1) if budget is None else budget
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=view,
        players=tuple(players),
        settings=RoomSettings(
            help_mode=HelpMode.FREE, reveal_budget=shown_budget, locked=False
        ),
        reveal_budget=shown_budget,
        flags=tuple(flags),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def selection_frame(player_id: str, row: int, column: int, direction: Direction) -> str:
    """A `selection_moved` that puts `player_id` on (row, column)."""
    selection = Selection(row=row, column=column, direction=direction)
    return SelectionMoved(player_id=player_id, selection=selection).model_dump_json()


def make_catalogue(grid: Grid) -> Catalogue:
    """A catalogue holding `grid` as published entry 1 (for the live server's `/`)."""
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=1,
        published=True,
        **credits(),
        grid=grid,
    )
    return Catalogue(entries=(entry,))


# ---- Pages --------------------------------------------------------------------


def wait_until(page: Page, condition: Callable[[], bool], what: str) -> None:
    """Let Playwright run its callbacks until `condition` holds, else fail."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail(f"timed out waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50


def expect_seq(page: Page, seq: int) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def show_snapshot(
    page: Page, mock: MockRoomSocket, frame: str, seq: int, cell_count: int
) -> None:
    """Send a snapshot on the newest socket and wait until the page shows it."""
    mock.send(frame)
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(cell_count)
    wait_for_fonts(page)


def open_room(
    page: Page,
    base_url: str,
    view: GridView,
    players: list[PlayerView],
    *,
    seq: int = 5,
    flags: Sequence[FlagView] = (),
    budget: RevealBudget | None = None,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, join as Ana and show a snapshot.

    Args:
        page: A fresh page; its `localStorage` starts as the test seeded it.
        base_url: The live server, which serves the built client.
        view: The snapshot's grid.
        players: The roster, `p1` (`you`) first.
        seq: The snapshot's seq.
        flags: The snapshot's flags.
        budget: The reveal allowance and what is left (5 letters, 1 word).

    Returns:
        The mocked socket, once the page shows the snapshot and its fonts.
    """
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until(page, lambda: mock.has_join_after(0), "the join")
    frame = snapshot_frame(view, players, seq=seq, flags=flags, budget=budget)
    show_snapshot(page, mock, frame, seq, view.width * view.height)
    return mock


def reload_room(
    page: Page,
    mock: MockRoomSocket,
    view: GridView,
    players: list[PlayerView],
    *,
    seq: int = 5,
) -> None:
    """Reload the page and answer its new join with the same snapshot.

    The page joins again with the identity it stored (spec 012), so no nickname
    form shows.
    """
    frames_before = len(mock.received)
    page.reload()
    wait_until(page, lambda: mock.has_join_after(frames_before), "the second join")
    frame = snapshot_frame(view, players, seq=seq)
    show_snapshot(page, mock, frame, seq, view.width * view.height)


def open_caught_up_room(
    page: Page,
    base_url: str,
    view: GridView,
    players: list[PlayerView],
    route: CatchUpRoute,
    *,
    seen_seq: int,
    seq: int,
) -> MockRoomSocket:
    """Open the room as spec 034 does on a return, with `seen_seq` stored.

    Spec 034's identity of `p1` and its room record with `seen_seq` are stored
    before the page opens, so the page joins at once; the catch-up request goes to
    `route`. The function returns once the page shows the snapshot; the test then
    waits for `data-catch-up`.
    """
    mock = MockRoomSocket()
    page.route(CATCH_UP_ROUTE, route.handle)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    seed_storage(page, {"grid": None, "selection": None, "seen_seq": seen_seq})
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    wait_until(page, lambda: mock.has_join_after(0), "the join")
    frame = snapshot_frame(view, players, seq=seq)
    show_snapshot(page, mock, frame, seq, view.width * view.height)
    return mock


def expect_catch_up(page: Page, value: str) -> None:
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-catch-up", value, timeout=WAIT_TIMEOUT_MS
    )


def seed_value(page: Page, key: str, value: str) -> None:
    """Store `value` under `key` before the page's first load only.

    The init script runs again on a reload; a flag in `sessionStorage` makes it
    store the value once, so a reload reads what the page wrote meanwhile.
    """
    script = (
        f"if (sessionStorage.getItem('spec042-seeded-{key}') === null) {{"
        f" localStorage.setItem({json.dumps(key)}, {json.dumps(value)});"
        f" sessionStorage.setItem('spec042-seeded-{key}', '1'); }}"
    )
    page.context.add_init_script(script)


# A `localStorage` that throws on every use (private mode, "Edge cases").
THROWING_STORAGE_SCRIPT = r"""
(() => {
  const refuse = () => { throw new DOMException('refused', 'SecurityError'); };
  Storage.prototype.getItem = refuse;
  Storage.prototype.setItem = refuse;
  Storage.prototype.removeItem = refuse;
  Storage.prototype.key = refuse;
})();
"""


def make_storage_throw(page: Page) -> None:
    page.context.add_init_script(THROWING_STORAGE_SCRIPT)


def stored_value(page: Page, key: str) -> str | None:
    value = page.evaluate("key => localStorage.getItem(key)", key)
    assert value is None or isinstance(value, str)
    return value


def frames_sent_after(
    page: Page, mock: MockRoomSocket, action: Callable[[], object]
) -> list[str]:
    """Do `action`, wait QUIET_MS, and return the frames sent meanwhile (no pings)."""
    before = len(mock.frames_without_pings())
    action()
    page.wait_for_timeout(QUIET_MS)
    return mock.frames_without_pings()[before:]


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(CELL_SELECTOR.format(row=row, column=column))


def tap(page: Page, row: int, column: int) -> None:
    """Click a cell and wait until the grid selects it (spec 007)."""
    cell_at(page, row, column).click(timeout=WAIT_TIMEOUT_MS)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


def click_switch(page: Page, test_id: str, pressed: str) -> None:
    """Click a switch and wait until its `aria-pressed` is `pressed`.

    The switches are items of the room Menu (spec 043): the Menu is opened first
    with spec 043's `open_menu`, then closed again with a click on `menu-button`,
    so that it covers nothing the test reads next.
    """
    open_menu(page)
    switch = page.get_by_test_id(test_id)
    switch.click(timeout=WAIT_TIMEOUT_MS)
    expect(switch).to_have_attribute("aria-pressed", pressed)
    page.get_by_test_id("menu-button").click(timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("room-menu")).to_be_hidden()


# ---- Readings -------------------------------------------------------------------


def box_of(locator: Locator) -> Box:
    return to_box(
        locator.evaluate(
            "e => { const r = e.getBoundingClientRect();"
            " return [r.left, r.top, r.right, r.bottom]; }"
        )
    )


def style_of(locator: Locator, property_name: str) -> str:
    """The computed style property `property_name` (camelCase) of an element."""
    value = locator.evaluate(
        "(element, name) => getComputedStyle(element)[name]", property_name
    )
    assert isinstance(value, str), value
    return value


def px(value: str) -> float:
    """Read a computed length such as `15.2px` as a number of px."""
    if not value.endswith("px"):
        pytest.fail(f"{value!r} is not a length in px")
    return float(value.removesuffix("px"))


def line_height_px(value: str, font_size: float) -> float:
    """A computed `line-height` in px; a plain number is a factor of the size."""
    if value.endswith("px"):
        return float(value.removesuffix("px"))
    if value == "normal":
        pytest.fail("the computed line-height is 'normal'")
    return float(value) * font_size


def colour_of(locator: Locator, property_name: str) -> Colour:
    """A computed colour property (camelCase) of an element, parsed."""
    found = locator.evaluate(
        "(element, property) => {\n"
        + READERS_JS
        + "\nreturn parseColour(getComputedStyle(element)[property]);\n}",
        property_name,
    )
    return to_colour(found)


def font_families(value: str) -> list[str]:
    """A computed `font-family` as a list of names, quotes removed (spec 041 AC-4)."""
    families: list[str] = []
    for part in value.split(","):
        families.append(part.strip().strip('"').strip("'"))
    return families


def read_cursors(page: Page, row: int, column: int) -> tuple[Box, list[Reading]]:
    """The box of a cell and the readings of its `remote-selection` elements."""
    found = cell_at(page, row, column).evaluate(CURSORS_SCRIPT)
    assert isinstance(found, dict), found
    cursors = found["cursors"]
    assert isinstance(cursors, list), found
    return to_box(found["cell"]), cursors


def corners_on(page: Page, row: int, column: int) -> dict[str, str | None]:
    """The `data-corner` of each `remote-selection` of a cell, by player id."""
    _, cursors = read_cursors(page, row, column)
    corners: dict[str, str | None] = {}
    for cursor in cursors:
        corners[str(cursor["playerId"])] = cursor["corner"]
    return corners


def read_swatches(page: Page) -> list[Reading]:
    """Each roster item's player, colour index, swatch background and icons."""
    found = page.evaluate(SWATCHES_SCRIPT)
    assert isinstance(found, list), found
    return found


def read_arrows(page: Page) -> list[Reading]:
    """Every `clue-arrow` of the page, with its cell and shapes."""
    found = page.evaluate(ARROWS_SCRIPT)
    assert isinstance(found, list), found
    return found


def arrow_of(arrows: list[Reading], row: int, column: int, index: int) -> Reading:
    """The one arrow whose `data-clue-*` name the clue (row, column, index)."""
    matching: list[Reading] = []
    for arrow in arrows:
        names = (arrow["clueRow"], arrow["clueColumn"], arrow["clueIndex"])
        if names == (str(row), str(column), str(index)):
            matching.append(arrow)
    assert len(matching) == 1, f"{len(matching)} arrows for clue {row},{column},{index}"
    return matching[0]


def start_hit_test(
    page: Page, row: int, column: int, *, with_selection: bool = False
) -> None:
    """`scrollIntoView` of the cell, then the test style of "Hit tests".

    Args:
        page: The page of the room.
        row: The cell's row.
        column: The cell's column.
        with_selection: Also turn pointer events on for `cell-selection`; by
            default it keeps `pointer-events: none`.
    """
    selector = CELL_SELECTOR.format(row=row, column=column)
    page.evaluate(START_HIT_TEST_SCRIPT, [selector, HIT_STYLE_ID, with_selection])


def end_hit_test(page: Page) -> None:
    page.evaluate(END_HIT_TEST_SCRIPT, HIT_STYLE_ID)


def pixel_at(page: Page, x: float, y: float) -> Rgb:
    """The painted colour of the screen pixel that holds the point (x, y).

    The point is in CSS px of the viewport (the page is in a context with a
    device scale factor of 1). It reads a 1 by 1 screenshot clip, a PNG, whose
    one pixel is the pixel itself.
    """
    column = math.floor(x)
    line = math.floor(y)
    png = page.screenshot(clip={"x": column, "y": line, "width": 1, "height": 1})
    return png_single_pixel(png)


# The channels per pixel of the PNG colour types a screenshot can have:
# 2 is RGB and 6 is RGBA.
PNG_CHANNELS = {2: 3, 6: 4}


def png_single_pixel(png: bytes) -> Rgb:
    """The colour of the one pixel of an 8-bit RGB or RGBA PNG of 1 by 1."""
    data = b""
    channels = 0
    position = 8
    while position < len(png):
        length = int.from_bytes(png[position : position + 4], "big")
        kind = png[position + 4 : position + 8]
        body = png[position + 8 : position + 8 + length]
        if kind == b"IHDR":
            assert body[8] == 8, "not an 8-bit PNG"
            colour_type = body[9]
            assert colour_type in PNG_CHANNELS, f"PNG colour type {colour_type}"
            channels = PNG_CHANNELS[colour_type]
            assert int.from_bytes(body[0:4], "big") == 1, "not 1 px wide"
            assert int.from_bytes(body[4:8], "big") == 1, "not 1 px high"
        if kind == b"IDAT":
            data += body
        position += 12 + length
    raw = zlib.decompress(data)
    # One filter byte, then the pixel; a filter of a first pixel is the identity.
    assert len(raw) == 1 + channels, raw
    return (raw[1], raw[2], raw[3])


def hit_chain(page: Page, x: float, y: float) -> list[Reading]:
    """The element at (x, y) and its ancestors, nearest first.

    Each item has the element's `name`, its test id (`remote-selection:<id>` for a
    cursor, with its player id), or None when it has none, and its `tag`.
    """
    chain = page.evaluate(HIT_SCRIPT, [x, y])
    assert isinstance(chain, list), chain
    return chain


def hit_owner(chain: list[Reading]) -> str | None:
    """The name of the nearest element of the chain that has a test id.

    A hit on a shape of an `svg` mark returns the mark (the shapes have no test
    id); None when nothing with a test id was hit.
    """
    for node in chain:
        if node["name"] is not None:
            return str(node["name"])
    return None


# ---- Shapes ---------------------------------------------------------------------


def attribute_matches(name: str, actual: str | None, expected: str) -> bool:
    """A shape attribute: numbers compared as numbers, other values as written."""
    if actual is None:
        return False
    if name in NUMBER_ATTRIBUTES:
        try:
            return math.isclose(float(actual), float(expected), abs_tol=1e-9)
        except ValueError:
            return False
    return " ".join(actual.split()) == expected


def icon_shape_problems(svg: Reading, colour_index: int) -> list[str]:
    """How an `svg`'s shapes differ from `PLAYER_ICONS[colour_index]`."""
    expected = PLAYER_ICON_SHAPES[colour_index]
    shapes: list[Reading] = svg["shapes"]
    if len(shapes) != len(expected):
        return [f"{len(shapes)} shapes, expected {len(expected)}"]
    problems: list[str] = []
    for shape, (tag, attributes) in zip(shapes, expected, strict=True):
        if shape["tag"] != tag:
            problems.append(f"a {shape['tag']}, expected a {tag}")
            continue
        for name, value in attributes.items():
            actual = shape["attributes"].get(name)
            if not attribute_matches(name, actual, value):
                problems.append(f"{tag} {name}={actual!r}, expected {value!r}")
    return problems


def shape_colour_problems(name: str, shape: Reading, expected: Rgb) -> list[str]:
    """A shape filled with `expected`, with no stroke."""
    problems: list[str] = []
    if shape["fillColour"] is None:
        problems.append(f"{name}: fill {shape['fill']!r}")
    else:
        problems.extend(colour_problems(f"{name} fill", shape["fillColour"], expected))
    if shape["stroke"] != "none":
        problems.append(f"{name}: stroke {shape['stroke']!r}")
    return problems


# ---- FX-02 ----------------------------------------------------------------------


def letter_cells_of(grid: Grid) -> list[Cell]:
    """The letter cells of a grid, in row-major order."""
    cells: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            cells.append((cell.row, cell.column))
    return sorted(cells)


def first_clue_cell(grid: Grid) -> Cell:
    """The first clue cell of a grid in row-major order."""
    cells: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            cells.append((cell.row, cell.column))
    return min(cells)


def across_word_holds(grid: Grid, target: Cell) -> bool:
    """Tell whether an across word of the grid holds `target`.

    An across word starts right of a clue cell (`right`) or under it
    (`down_then_right`) and runs right over letter cells.
    """
    letters = set(letter_cells_of(grid))
    for cell in grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for clue in cell.clues:
            if clue.arrow == Arrow.RIGHT:
                start = (cell.row, cell.column + 1)
            elif clue.arrow == Arrow.DOWN_THEN_RIGHT:
                start = (cell.row + 1, cell.column)
            else:
                continue
            position = start
            while position in letters:
                if position == target:
                    return True
                position = (position[0], position[1] + 1)
    return False


# ---- The toolbar setup of spec 024 AC-8 -------------------------------------------

FEED_ITEMS = 100


def eight_players() -> list[PlayerView]:
    """`p1` (`you`, host, colour 0) and `p2` to `p8` with colours 1 to 7."""
    players = [me()]
    for number in range(2, 9):
        players.append(player(f"p{number}", number - 1))
    return players


def open_toolbar_setup_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Spec 024 AC-8's setup, without its tap: 8 players and 100 feed items.

    Spec 013 AC-6's FX-01 snapshot with `you` host among 8 players and help mode
    `free`, then 100 `check_result` lines of `p2` (seq 6 to 105).
    """
    mock = open_room(page, base_url, fx01_view(grid), eight_players())
    last_seq = 5 + FEED_ITEMS
    for seq in range(6, last_seq + 1):
        result = CheckResult(
            seq=seq, player_id="p2", target=GridTarget(), correct=(), wrong=()
        )
        mock.send(result.model_dump_json())
    expect_seq(page, last_seq)
    return mock


def fr_value(key: str) -> str:
    """The value of a key of `web/src/i18n/fr.json` (KeyError when it is missing)."""
    return load_fr()[key]
