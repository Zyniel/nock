"""Shared setup of the tests of spec 045: the Auteurs mode.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 045 uses: the values of the spec, the
`EIGHT` snapshot of its "Test harness", the helpers that open the room with the
mode on or off and flip it in the Menu, and the readers of a letter cell's inks
and of `authors-legend`. The tests are in these files, one per group of criteria:

- `test_spec_045_ac01_switch.py`: AC-1 (the switch, off by default, remembered).
- `test_spec_045_ac02_ac05_inks.py`: AC-2 to AC-5 (the letters in their inks).
- `test_spec_045_ac06_ac08_legend.py`: AC-6 to AC-8 (the legend and its room).
- `test_spec_045_ac09_ac11_clue_bar_room_scans.py`: AC-9 to AC-11 (the clue bar,
  the room page's guarantees, the scans and `fr.json`).

It reuses spec 043's harness ("Browser with mocked socket": the mocked room, its
FX-01 snapshots and players, the box and colour readers), spec 042's in-page
readers and pixel reader, and spec 019's desktop and touch windows. Every helper
that opens or reloads a page waits for the fonts before it returns (spec 041's
rule).

Choices where the spec leaves room:

- "Within 300 ms of each event the page applies" is measured from the moment
  `room-page` shows the event's `data-seq` (spec 040's attribute), as spec 019's
  tests measure it; a colour is read again every 50 ms until it matches, and the
  last reading is made when the 300 ms are over.
- "The mode on" by seeding is `localStorage["nock.authors"]` = `"true"` before the
  first load only (spec 043's `seed_value`), so a reload reads what the page wrote
  meanwhile. The page is ready once `authors-switch` has `aria-pressed="true"`.
- The legend's place is read once the layout has settled: the boxes of
  `grid-viewport`, the `grid` and the legend are read every 100 ms until two
  readings in a row are the same (the grid refits as on a resize, spec 006).
- Which of its two places the legend takes is not read from its top against
  `grid-viewport`'s bottom (AC-10's wording): in the sheet layout on a portrait
  window the grid is centred in a viewport taller than itself, and the legend,
  8 px under the grid (AC-7) in a viewport 38 px less high (AC-8), lies inside
  the viewport's box with the room given. A test that does not know the case
  accepts either place (`legend_room_problems`); one that knows it (the rule of
  "The grid's room" from the height with the mode off) checks that place.
- An element "shown" (`grid-status` when shown, `keyboard`, `salon` when open)
  has no `hidden` attribute, a client rect and `visibility: visible`.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence

from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import GridView, PlayerView
from room_panels import open_menu
from spec019_harness import OpenWindow, press
from spec042_harness import READERS_JS, Box, ChangeList, to_box, to_colour
from spec043_harness import (
    COMPUTER,
    POSITION_TOLERANCE_PX,
    Reading,
    Rgb,
    RoomMock,
    colour_matches,
    fx01_view,
    open_room,
    player,
    players_up_to,
    seed_value,
    snapshot_frame,
)

# ---- Values of the spec ------------------------------------------------------------

AUTHORS_KEY = "nock.authors"
ACCESS_KEY = "nock.accessibility"
FOLLOW_MS = 300  # "within 300 ms"
POLL_MS = 50
SETTLE_POLL_MS = 100
SETTLE_TIMEOUT_MS = 3000

# The inks of "Test harness": `--player-ink-0` to `--player-ink-7`.
INKS: tuple[Rgb, ...] = (
    (96, 72, 0),
    (75, 106, 44),
    (0, 109, 96),
    (104, 56, 224),
    (173, 53, 75),
    (179, 0, 138),
    (144, 79, 0),
    (120, 64, 48),
)
INK: Rgb = (20, 24, 31)
PENCIL: Rgb = (85, 91, 103)
RED: Rgb = (180, 35, 24)
LINE: Rgb = (221, 226, 234)
MUTED: Rgb = (94, 101, 115)
LEGEND_BG: Rgb = (255, 255, 255)
LEGEND_BG_ALPHA = 0.96

LEGEND_GAP_PX = 8.0  # its top 8 px below the grid's bottom
ONE_LINE_ROOM_PX = 38.0  # R = max(38, h + 8)

# `EIGHT`: (1, 0) to (1, 4), (2, 1), (2, 2) and (2, 3) hold T, A, M, I, S, V, I, D
# by `p1` to `p8` in that order (colours 0 to 7).
EIGHT_CELLS: list[tuple[int, int]] = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 1),
    (2, 2),
    (2, 3),
]
EIGHT_LETTERS = "TAMISVID"

# Eight nicknames of 20 characters (AC-8, AC-10), as the server stores them.
LONG_NICKNAMES = [
    "BARTHOLOMEW LEFEBVRE",
    "GENEVIEVE MONTAIGNES",
    "ALEXANDRINE DUVERNAY",
    "CHRISTOPHE BEAUCHAMP",
    "MARIE-CLAIRE FONTANE",
    "JEAN-BAPTISTE ROUSSY",
    "PHILIPPINE ROCHEFORT",
    "EMMANUELLE GRANDPRES",
]

# ---- Snapshots ---------------------------------------------------------------------


def eight_changes() -> ChangeList:
    """The letters of `EIGHT`: one per player, `p1` to `p8`, none locked or pencil."""
    changes: ChangeList = []
    for index, (row, column) in enumerate(EIGHT_CELLS):
        update: dict[str, object] = {
            "letter": EIGHT_LETTERS[index],
            "author": f"p{index + 1}",
        }
        changes.append((row, column, update))
    return changes


def eight_view(grid: Grid, replaced: ChangeList | None = None) -> GridView:
    """`EIGHT`'s grid; each cell of `replaced` takes that whole update instead."""
    changes = eight_changes()
    if replaced is not None:
        changes.extend(replaced)
    return fx01_view(grid, changes)


def eight_frame(
    grid: Grid,
    *,
    players: Sequence[PlayerView] | None = None,
    replaced: ChangeList | None = None,
) -> str:
    """`EIGHT`'s snapshot: `seq` 5, `you` `p1`, players `p1` to `p8` by default."""
    shown_players = players_up_to(8) if players is None else players
    return snapshot_frame(eight_view(grid, replaced), shown_players)


def long_name_players() -> list[PlayerView]:
    """`p1` (host) to `p8`, each with one of the 20-character `LONG_NICKNAMES`."""
    players: list[PlayerView] = []
    for number, nickname in enumerate(LONG_NICKNAMES, start=1):
        assert len(nickname) == 20, nickname
        players.append(player(f"p{number}", nickname=nickname, host=number == 1))
    return players


AC3_SEQ = 7


def ac3_frame(grid: Grid) -> str:
    """AC-3's snapshot: `p1` (colour 0), `p2` (colour 1), seq 7, row 1 filled.

    (1, 0) `T` by `p1`, (1, 1) `A` by `p2`, (1, 2) `M` by `p9` (not in the room)
    and (1, 4) `S` revealed (`locked`, `revealed`, no author).
    """
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p2"}),
        (1, 2, {"letter": "M", "author": "p9"}),
        (1, 4, {"letter": "S", "author": None, "locked": True, "revealed": True}),
    ]
    return snapshot_frame(fx01_view(grid, changes), players_up_to(2), seq=AC3_SEQ)


def finder_of_colour(colour_index: int) -> tuple[int, int]:
    """The cell of `EIGHT` written by the player of colour `colour_index`."""
    return EIGHT_CELLS[colour_index]


# ---- Opening the room and flipping the mode ---------------------------------------


def open_page(
    window: OpenWindow,
    base_url: str,
    frame: str,
    size: tuple[int, int] = COMPUTER,
    *,
    touch: bool = False,
    mode_on: bool = False,
    accessibility: bool = False,
) -> tuple[Page, RoomMock]:
    """Open the room on a snapshot, by default at 1280 by 720 in the desktop context.

    Args:
        window: The `window` fixture (spec 019's desktop and touch contexts).
        base_url: The live server.
        frame: The snapshot.
        size: The window, as (width, height).
        touch: Whether the context is the touch context.
        mode_on: Whether `nock.authors` is seeded `"true"` before the first load;
            the page is then waited for until `authors-switch` is pressed.
        accessibility: Whether `nock.accessibility` is seeded `"true"` too.

    Returns:
        The page, once it shows the snapshot and its fonts, and the mocked socket.
    """
    width, height = size
    page = window(width, height, touch)
    if mode_on:
        seed_value(page, AUTHORS_KEY, "true")
    if accessibility:
        seed_value(page, ACCESS_KEY, "true")
    mock = open_room(page, base_url, frame)
    if mode_on:
        expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    return page, mock


def authors_switch(page: Page) -> Locator:
    """The `authors-switch` of the room Menu (the Menu must be open to press it).

    Args:
        page: The room page.

    Returns:
        A locator on the switch.
    """
    return page.get_by_test_id("authors-switch")


def legend_of(page: Page) -> Locator:
    """The `authors-legend` of the room page.

    Args:
        page: The room page.

    Returns:
        A locator on the legend, which exists only with the mode on.
    """
    return page.get_by_test_id("authors-legend")


def set_mode(page: Page, on: bool, touch: bool = False) -> None:
    """Turn the mode on or off in the Menu, then close the Menu again.

    The Menu is opened with spec 043's `open_menu`, the switch is pressed when it
    is not in the wanted state, and a press on `menu-button` closes the Menu, so
    that it covers nothing the test reads next.
    """
    wanted = "true" if on else "false"
    open_menu(page)
    switch = authors_switch(page)
    if switch.get_attribute("aria-pressed") != wanted:
        press(switch, touch)
    expect(switch).to_have_attribute("aria-pressed", wanted)
    press(page.get_by_test_id("menu-button"), touch)
    expect(page.get_by_test_id("room-menu")).to_be_hidden()


# ---- Reading a letter cell ------------------------------------------------------

# One letter cell read at once: its `data-author-colour`, `data-flash`, its
# computed colour, background, font and strike, the colour of its `cell-letter`
# and the number of its `cell-flash` overlays.
CELL_INK_SCRIPT = "cell => {\n" + READERS_JS + r"""
const style = getComputedStyle(cell);
const letter = cell.querySelector('[data-testid="cell-letter"]');
return {
  authorColour: cell.getAttribute('data-author-colour'),
  flash: cell.getAttribute('data-flash'),
  letterText: letter === null ? null : letter.textContent,
  colour: parseColour(style.color),
  letterColour: letter === null ? null : parseColour(getComputedStyle(letter).color),
  background: parseColour(style.backgroundColor),
  fontStyle: style.fontStyle,
  fontWeight: style.fontWeight,
  fontSize: parseFloat(style.fontSize),
  decorationLine: style.textDecorationLine,
  decorationColour: parseColour(style.textDecorationColor),
  decorationStyle: style.textDecorationStyle,
  decorationThickness: style.textDecorationThickness,
  overlays: cell.querySelectorAll('[data-testid="cell-flash"]').length,
};
}"""

# The colour of a probe `span` whose style is `color: var(--player-ink-N)`,
# appended to `body`, read, then removed ("Test harness" of spec 019 and 045).
INK_PROBE_SCRIPT = "index => {\n" + READERS_JS + r"""
const probe = document.createElement('span');
probe.style.cssText = `color: var(--player-ink-${index})`;
probe.textContent = 'probe';
document.body.appendChild(probe);
const colour = parseColour(getComputedStyle(probe).color);
probe.remove();
return colour;
}"""


def cell_locator(page: Page, row: int, column: int) -> Locator:
    """The grid cell at a row and a column.

    Args:
        page: The room page.
        row: Row of the cell, from 0.
        column: Column of the cell, from 0.

    Returns:
        A locator on the `cell` with these `data-row` and `data-column`.
    """
    return page.locator(
        f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    )


def read_cell(page: Page, row: int, column: int) -> Reading:
    """A letter cell's inks, font, strike and flash, read in one go."""
    found = cell_locator(page, row, column).evaluate(CELL_INK_SCRIPT)
    assert isinstance(found, dict), found
    return found


def ink_probe(page: Page, colour_index: int) -> tuple[float, float, float, float]:
    """The colour of `var(--player-ink-N)`, read through a probe `span`."""
    return to_colour(page.evaluate(INK_PROBE_SCRIPT, colour_index))


def has_colour(reading: Reading, expected: Rgb) -> bool:
    """Whether a cell and its `cell-letter` (when it has one) are in `expected`."""
    if not colour_matches(reading["colour"], expected):
        return False
    letter_colour = reading["letterColour"]
    return letter_colour is None or colour_matches(letter_colour, expected)


def colour_problems(where: str, reading: Reading, expected: Rgb) -> list[str]:
    """How a cell's colour or its letter's colour differs from `expected`."""
    problems: list[str] = []
    if not colour_matches(reading["colour"], expected):
        problems.append(f"{where}: cell color {reading['colour']}, not {expected}")
    letter_colour = reading["letterColour"]
    if letter_colour is not None and not colour_matches(letter_colour, expected):
        problems.append(f"{where}: cell-letter color {letter_colour}, not {expected}")
    return problems


def finder_problems(
    where: str, reading: Reading, author_colour: str, expected: Rgb
) -> list[str]:
    """A cell's `data-author-colour` and colours against what it should show."""
    problems = colour_problems(where, reading, expected)
    if reading["authorColour"] != author_colour:
        problems.append(
            f"{where}: data-author-colour {reading['authorColour']!r},"
            f" not {author_colour!r}"
        )
    return problems


def read_until(
    page: Page,
    read: Callable[[], Reading],
    accept: Callable[[Reading], bool],
    timeout_ms: float = FOLLOW_MS,
) -> Reading:
    """Read until `accept` takes the reading, for `timeout_ms` at most.

    The caller asserts on the reading returned, so a page that has not changed in
    time fails there, with the last reading in the message.

    Returns:
        The first reading that `accept` takes, else the last reading.
    """
    deadline = time.monotonic() + timeout_ms / 1000
    reading = read()
    while not accept(reading):
        remaining_ms = (deadline - time.monotonic()) * 1000
        if remaining_ms <= 0:
            break
        page.wait_for_timeout(min(POLL_MS, remaining_ms))
        reading = read()
    return reading


def cell_shows_within(
    page: Page,
    row: int,
    column: int,
    author_colour: str,
    expected: Rgb,
    timeout_ms: float = FOLLOW_MS,
) -> Reading:
    """Read a cell until it shows `author_colour` and the colour `expected`."""

    def read() -> Reading:
        return read_cell(page, row, column)

    def accept(reading: Reading) -> bool:
        return reading["authorColour"] == author_colour and has_colour(
            reading, expected
        )

    return read_until(page, read, accept, timeout_ms)


# ---- Reading the legend --------------------------------------------------------

# The legend, read at once: where it sits in the document, its look, and each of
# its `authors-legend-label` and `authors-legend-name` in document order. Null
# when there is no `authors-legend`.
LEGEND_SCRIPT = "() => {\n" + READERS_JS + r"""
const legend = document.querySelector('[data-testid="authors-legend"]');
if (legend === null) {
  return null;
}
const style = getComputedStyle(legend);
const area = document.querySelector('[data-testid="grid-area"]');
const previous = legend.previousElementSibling;
const items = [];
const selector =
  '[data-testid="authors-legend-label"], [data-testid="authors-legend-name"]';
for (const item of legend.querySelectorAll(selector)) {
  const itemStyle = getComputedStyle(item);
  items.push({
    testId: item.getAttribute('data-testid'),
    text: item.textContent,
    playerId: item.getAttribute('data-player-id'),
    colourIndex: item.getAttribute('data-colour'),
    childElements: item.children.length,
    svgs: item.querySelectorAll('svg').length,
    colour: parseColour(itemStyle.color),
    fontSize: parseFloat(itemStyle.fontSize),
    fontWeight: itemStyle.fontWeight,
    lineHeight: itemStyle.lineHeight,
    fontFamily: itemStyle.fontFamily,
    box: boxOf(item),
  });
}
let areaContent = null;
if (area !== null) {
  const areaStyle = getComputedStyle(area);
  const areaBox = area.getBoundingClientRect();
  areaContent = [
    areaBox.left + parseFloat(areaStyle.borderLeftWidth)
      + parseFloat(areaStyle.paddingLeft),
    areaBox.top + parseFloat(areaStyle.borderTopWidth)
      + parseFloat(areaStyle.paddingTop),
    areaBox.right - parseFloat(areaStyle.borderRightWidth)
      - parseFloat(areaStyle.paddingRight),
    areaBox.bottom - parseFloat(areaStyle.borderBottomWidth)
      - parseFloat(areaStyle.paddingBottom),
  ];
}
return {
  inGridArea: area !== null && area.contains(legend),
  parentTestId: legend.parentElement === null
    ? null : legend.parentElement.getAttribute('data-testid'),
  previousTestId: previous === null ? null : previous.getAttribute('data-testid'),
  ariaHidden: legend.getAttribute('aria-hidden'),
  box: boxOf(legend),
  areaBox: area === null ? null : boxOf(area),
  areaContent: areaContent,
  background: parseColour(style.backgroundColor),
  display: style.display,
  columnGap: style.columnGap,
  zIndex: style.zIndex,
  pointerEvents: style.pointerEvents,
  items: items,
  playerIcons: legend.querySelectorAll('[data-testid="player-icon"]').length,
};
}"""


def read_legend(page: Page) -> Reading | None:
    """The legend and its items, or None when there is no `authors-legend`."""
    found = page.evaluate(LEGEND_SCRIPT)
    if found is None:
        return None
    assert isinstance(found, dict), found
    return found


def legend_reading(page: Page) -> Reading:
    """The legend, once it shows (fails when it does not)."""
    expect(legend_of(page)).to_be_visible()
    reading = read_legend(page)
    assert reading is not None, "no authors-legend"
    return reading


def legend_names(reading: Reading) -> list[Reading]:
    """The `authors-legend-name` items of a legend reading, in document order."""
    names: list[Reading] = []
    for item in reading["items"]:
        if item["testId"] == "authors-legend-name":
            names.append(item)
    return names


def name_texts(reading: Reading) -> list[str]:
    """The texts of the legend's names, in document order.

    Args:
        reading: A legend reading.

    Returns:
        The text of each `authors-legend-name`.
    """
    return [str(name["text"]) for name in legend_names(reading)]


def name_ids(reading: Reading) -> list[str]:
    """The player ids of the legend's names, in document order.

    Args:
        reading: A legend reading.

    Returns:
        The `data-player-id` of each `authors-legend-name`.
    """
    return [str(name["playerId"]) for name in legend_names(reading)]


def names_within(
    page: Page, accept: Callable[[Reading], bool], timeout_ms: float = FOLLOW_MS
) -> Reading:
    """Read the legend until `accept` takes it, for `timeout_ms` at most."""

    def read() -> Reading:
        reading = read_legend(page)
        if reading is None:
            return {"items": []}
        return reading

    return read_until(page, read, accept, timeout_ms)


# ---- Boxes and the settled layout ----------------------------------------------

BOXES_SCRIPT = r"""
testIds => {
  const found = {};
  for (const testId of testIds) {
    const element = document.querySelector(`[data-testid="${testId}"]`);
    if (element === null) {
      found[testId] = null;
    } else {
      const rect = element.getBoundingClientRect();
      found[testId] = [rect.left, rect.top, rect.right, rect.bottom];
    }
  }
  return found;
}
"""

SETTLE_IDS = ["grid-viewport", "grid", "authors-legend", "clue-bar"]


def boxes_of(page: Page, test_ids: Sequence[str]) -> dict[str, Box | None]:
    """The box of the first element of each test id, None when there is none."""
    found = page.evaluate(BOXES_SCRIPT, list(test_ids))
    assert isinstance(found, dict), found
    boxes: dict[str, Box | None] = {}
    for test_id in test_ids:
        raw = found[test_id]
        boxes[test_id] = None if raw is None else to_box(raw)
    return boxes


def settle_layout(page: Page) -> None:
    """Wait until the viewport, the grid, the legend and the clue bar stop moving."""
    waited_ms = 0
    before = boxes_of(page, SETTLE_IDS)
    while waited_ms < SETTLE_TIMEOUT_MS:
        page.wait_for_timeout(SETTLE_POLL_MS)
        waited_ms += SETTLE_POLL_MS
        now = boxes_of(page, SETTLE_IDS)
        if now == before:
            return
        before = now


def required_box(boxes: dict[str, Box | None], test_id: str) -> Box:
    """The box of an element that must be on the page.

    Args:
        boxes: Boxes by test id, as `boxes_of` reads them.
        test_id: The `data-testid` to take.

    Returns:
        Its box.

    Raises:
        AssertionError: The page has no such element.
    """
    box = boxes[test_id]
    assert box is not None, f"no {test_id} on the page"
    return box


def overlap_area(first: Box, second: Box) -> float:
    """The area two boxes share (0 when they do not overlap)."""
    across = min(first.right, second.right) - max(first.left, second.left)
    down = min(first.bottom, second.bottom) - max(first.top, second.top)
    if across <= 0 or down <= 0:
        return 0.0
    return across * down


def legend_place_problems(page: Page) -> list[str]:
    """How the legend's place breaks "Place" (empty: none).

    Horizontally centred on the `grid`'s box (1 px); its top 8 px below the bottom
    of the part of the grid's box that shows in `grid-viewport` (1 px).
    """
    boxes = boxes_of(page, ["grid-viewport", "grid", "authors-legend"])
    viewport = required_box(boxes, "grid-viewport")
    grid = required_box(boxes, "grid")
    legend = required_box(boxes, "authors-legend")
    problems: list[str] = []
    if abs(legend.centre_x - grid.centre_x) > POSITION_TOLERANCE_PX:
        problems.append(
            f"legend centre x {legend.centre_x}, grid centre x {grid.centre_x}"
        )
    shown_bottom = min(grid.bottom, viewport.bottom)
    gap = legend.top - shown_bottom
    if abs(gap - LEGEND_GAP_PX) > POSITION_TOLERANCE_PX:
        problems.append(f"legend top {legend.top} is {gap} px below the grid's bottom")
    return problems


# ---- Under the grid, or over its bottom ("The grid's room") ----------------------

# The box of the first element of each test id, or null when it is not shown: no
# such element, a `hidden` attribute, no client rect, or not `visibility: visible`.
SHOWN_BOXES_SCRIPT = r"""
testIds => {
  const found = {};
  for (const testId of testIds) {
    const element = document.querySelector(`[data-testid="${testId}"]`);
    const shown = element !== null
      && !element.hasAttribute('hidden')
      && element.getClientRects().length > 0
      && getComputedStyle(element).visibility === 'visible';
    if (shown) {
      const rect = element.getBoundingClientRect();
      found[testId] = [rect.left, rect.top, rect.right, rect.bottom];
    } else {
      found[testId] = null;
    }
  }
  return found;
}
"""

# What the legend may never cover ("The legend", second "Place"; AC-10).
UNCOVERED_IDS = ["room-topbar", "clue-bar", "grid-status", "keyboard", "salon"]

# What `document.elementFromPoint` finds at the centre of the legend's box: its
# test id (or tag name) and whether the `grid` holds it.
LEGEND_HIT_SCRIPT = r"""
() => {
  const legend = document.querySelector('[data-testid="authors-legend"]');
  const grid = document.querySelector('[data-testid="grid"]');
  const box = legend.getBoundingClientRect();
  const hit = document.elementFromPoint(
    box.left + box.width / 2, box.top + box.height / 2
  );
  return {
    inGrid: hit !== null && grid !== null && grid.contains(hit),
    hit: hit === null ? null : (hit.getAttribute('data-testid') || hit.tagName),
  };
}
"""


def shown_boxes(page: Page, test_ids: Sequence[str]) -> dict[str, Box | None]:
    """The box of each test id that shows, None for one that does not."""
    found = page.evaluate(SHOWN_BOXES_SCRIPT, list(test_ids))
    assert isinstance(found, dict), found
    boxes: dict[str, Box | None] = {}
    for test_id in test_ids:
        raw = found[test_id]
        boxes[test_id] = None if raw is None else to_box(raw)
    return boxes


def legend_cover_problems(page: Page) -> list[str]:
    """How the legend breaks "it covers nothing it may not" (empty: none).

    The legend lies inside the window, and its box overlaps none of `room-topbar`,
    `clue-bar`, `grid-status`, `keyboard` and `salon` that show.
    """
    legend = required_box(boxes_of(page, ["authors-legend"]), "authors-legend")
    size = page.evaluate("() => [innerWidth, innerHeight]")
    assert isinstance(size, list), size
    problems: list[str] = []
    if (
        legend.left < -POSITION_TOLERANCE_PX
        or legend.top < -POSITION_TOLERANCE_PX
        or legend.right > float(size[0]) + POSITION_TOLERANCE_PX
        or legend.bottom > float(size[1]) + POSITION_TOLERANCE_PX
    ):
        problems.append(f"legend {legend} is not inside the window {size}")
    others = shown_boxes(page, UNCOVERED_IDS)
    for test_id in UNCOVERED_IDS:
        other = others[test_id]
        if other is not None and overlap_area(legend, other) > 0:
            problems.append(f"legend {legend} overlaps {test_id} {other}")
    return problems


def legend_under_problems(page: Page) -> list[str]:
    """How the legend breaks its place when the grid gives it its room.

    Its top is 8 px below the bottom of the part of the `grid` that shows in
    `grid-viewport` (1 px), and its box does not overlap the `grid`'s.
    """
    boxes = boxes_of(page, ["grid-viewport", "grid", "authors-legend"])
    viewport = required_box(boxes, "grid-viewport")
    grid = required_box(boxes, "grid")
    legend = required_box(boxes, "authors-legend")
    problems: list[str] = []
    shown_bottom = min(grid.bottom, viewport.bottom)
    gap = legend.top - shown_bottom
    if abs(gap - LEGEND_GAP_PX) > POSITION_TOLERANCE_PX:
        problems.append(f"legend top {legend.top} is {gap} px below the grid's bottom")
    if overlap_area(legend, grid) > 0:
        problems.append(f"legend {legend} overlaps the grid {grid}")
    return problems


def legend_over_problems(page: Page) -> list[str]:
    """How the legend breaks its place when the grid gives it no room.

    Its bottom is 8 px above `grid-viewport`'s bottom (1 px) and its top is not
    above the viewport's top, so it covers only the viewport's bottom.
    """
    boxes = boxes_of(page, ["grid-viewport", "authors-legend"])
    viewport = required_box(boxes, "grid-viewport")
    legend = required_box(boxes, "authors-legend")
    problems: list[str] = []
    rise = viewport.bottom - legend.bottom
    if abs(rise - LEGEND_GAP_PX) > POSITION_TOLERANCE_PX:
        problems.append(
            f"legend's bottom {legend.bottom} is {rise} px above grid-viewport's"
            f" bottom {viewport.bottom}"
        )
    if legend.top < viewport.top - POSITION_TOLERANCE_PX:
        problems.append(
            f"legend's top {legend.top} is above grid-viewport's top {viewport.top}"
        )
    return problems


def legend_room_problems(page: Page) -> list[str]:
    """How the legend breaks both of its places (empty: it follows one of them).

    Either it sits under the grid (`legend_under_problems`) or it lies over the
    bottom of `grid-viewport` (`legend_over_problems`); this reads which from
    neither the mode off nor the window, so a test that knows the case checks
    the matching function instead.
    """
    under = legend_under_problems(page)
    if under == []:
        return []
    over = legend_over_problems(page)
    if over == []:
        return []
    return [f"not under the grid: {under}", f"not over its bottom: {over}"]


def legend_hit(page: Page) -> Reading:
    """What `elementFromPoint` finds at the legend's centre (`inGrid`, `hit`)."""
    found = page.evaluate(LEGEND_HIT_SCRIPT)
    assert isinstance(found, dict), found
    return found
