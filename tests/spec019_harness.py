"""Shared setup of the tests of spec 019: the authorship view.

This module is not a test file: pytest does not collect it. The tests of spec 019
are in `tests/test_spec_019_*.py`, one file per criterion group:

- `test_spec_019_ac01_ac02_marks_and_switch.py`: AC-1 and AC-2 (the marks with the
  switch on, the departed author's hatched band, the neutral look with the switch
  off);
- `test_spec_019_ac01_band_contrast.py`: AC-1's contrast run (3:1 in every state
  of the cell, the flash included);
- `test_spec_019_ac01_box_and_drawing_order.py`: AC-1's box run (box rules, the
  letter's baseline and the drawing order at three window sizes);
- `test_spec_019_ac03_authorship_kept.py`: AC-3 (rules, WebSocket, live browser);
- `test_spec_019_ac04_author_in_words.py`: AC-4 (`clue-bar-author`);
- `test_spec_019_ac05_switch_in_toolbar.py`: AC-5 (the switch in `room-toolbar`,
  keyboard, contrast and language).

The spec adds no Python name and no server change, so the browser tests drive the
room page through a mocked socket (spec 023's "browser with mocked socket") or the
live server, and AC-3 pins the server's existing behaviour with `nock.room`,
`nock.store` and the real WebSocket.

This module holds what more than one of those files uses: the mocked room, the
snapshot builders, the AC-1 snapshot, spec 026's FX-02 snapshot with eight
players, the reading of the marks, of their colours and of the roster swatches,
the desktop and touch windows and spec 013 AC-6's layout checks. What only one
file uses stays in that file. Fixtures are thin wrappers defined in each file
(`fx01_grid`, `window`): a fixture imported from here would be an unused import
for ruff.

Choices where the spec leaves room:

- A mark's box is compared with the cell's box with `SUBPIXEL_PX` (0.05 px) of
  allowance, for the sub-pixel rounding of layout units; the spec's 3 px, 6 px,
  half side and tenth of a side are used as written.
- "Within 300 ms of each event the page applies" (AC-1) is measured from the moment
  `room-page` shows the event's `data-seq` (spec 040's attribute).
- The band's colours (AC-1, "Contrast") are read with spec 035's colour helpers,
  shared through spec 024's `COLOUR_CONTRAST_JS`. Spec 024's `MARK_COLOURS_JS`
  measures a corner mark with other size limits and no gradient, so the band has
  its own reader, `BAND_COLOURS_JS`: the computed `background-color` and the
  colour stops of the computed `background-image` of `author-mark` and of each
  layer at least half the cell side wide and 1 px high. Like spec 024's, it
  composites each colour over the cell's computed background (itself over white)
  and keeps the highest ratio. "The cell side" is the cell's width.
- The colours of the "layers" whose `background-image` must be `none` (players'
  bands) are those of the same reader, so the same size limits apply.
"""

from __future__ import annotations

import json
import math
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, NamedTuple, Protocol

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    WebSocketRoute,
    expect,
)

from nock.grid import Grid, LetterCell
from nock.protocol import (
    CellLocked,
    CellView,
    GridView,
    HelpMode,
    LeaveReason,
    LetterCellView,
    LetterChanged,
    Ping,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    Selection,
    Snapshot,
    grid_view,
    parse_client_message,
)
from spec024_harness import COLOUR_CONTRAST_JS

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
ROOM_CODE = "ABC123"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_TIMEOUT_MS = 5000
ROOM_TIMEOUT_MS = 10_000
FOLLOW_MS = 300  # "within 300 ms of each event the page applies"
SETTLE_MS = 300
TAP_TIMEOUT_MS = 3000

FX01_CELL_COUNT = 25
SUBPIXEL_PX = 0.05

# The eight window sizes of spec 006 AC-5.
WINDOW_SIZES = [
    (320, 568),
    (568, 320),
    (360, 740),
    (740, 360),
    (768, 1024),
    (1024, 768),
    (1280, 800),
    (1920, 1080),
]
WINDOW_IDS = [f"{width}x{height}" for width, height in WINDOW_SIZES]
CONTEXT_KINDS = ["desktop", "touch"]

# Spec 013 AC-6 and spec 006 AC-5: the grid's room.
MIN_GRID_VIEWPORT_PX = 100.0
LAYOUT_EPSILON_PX = 1.0

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]

DEFAULT_SETTINGS = RoomSettings(
    help_mode=HelpMode.FREE,
    reveal_budget=RevealBudget(letters=5, words=1),
    locked=False,
)

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged
# (the script of spec 009, for the touch contexts of Firefox and WebKit).
COARSE_POINTER_SCRIPT = r"""
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""


# ---- Small helpers ----------------------------------------------------------


def load_fr() -> dict[str, str]:
    """Return the French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def grid_from_text(text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixtures)."""
    return Grid.model_validate_json(text)


def cell_selector(row: int, column: int) -> str:
    return f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(cell_selector(row, column))


def room_page(page: Page) -> Locator:
    return page.get_by_test_id("room-page")


def authors_switch(page: Page) -> Locator:
    return page.get_by_test_id("authors-switch")


def marks_in(page: Page, row: int, column: int) -> Locator:
    """The `author-mark` elements inside one cell."""
    return cell_at(page, row, column).get_by_test_id("author-mark")


def press(locator: Locator, touch: bool) -> None:
    """Tap the element in a touch context, click it otherwise."""
    if touch:
        locator.tap(timeout=TAP_TIMEOUT_MS)
    else:
        locator.click(timeout=TAP_TIMEOUT_MS)


def turn_switch_on(page: Page, touch: bool = False) -> None:
    """Press `authors-switch` once and wait until it reads `aria-pressed="true"`."""
    switch = authors_switch(page)
    press(switch, touch)
    expect(switch).to_have_attribute("aria-pressed", "true")


def turn_switch_off(page: Page) -> None:
    """Click `authors-switch` once and wait until it reads `aria-pressed="false"`."""
    switch = authors_switch(page)
    switch.click(timeout=TAP_TIMEOUT_MS)
    expect(switch).to_have_attribute("aria-pressed", "false")


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def expect_seq(page: Page, seq: int) -> None:
    """Wait until the page has applied the event numbered `seq`."""
    expect(room_page(page)).to_have_attribute("data-seq", str(seq))


# ---- Mocked room ------------------------------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the route
    that sent it: without the answer, the page takes 4 s without a frame from the
    server for a lost connection (spec 017, AC-4), so a step that takes longer on a
    slow engine would find the page `reconnecting`. `send` always uses the newest
    socket, so a test can answer the join of a reloaded page.
    """

    def __init__(self) -> None:
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)

        def on_message(message: str | bytes) -> None:
            self._record_and_answer(route, message)

        route.on_message(on_message)

    def _record_and_answer(self, route: WebSocketRoute, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)
        if parse_client_message(text) == Ping():
            route.send(Pong().model_dump_json())

    def send(self, frame: str) -> None:
        self.routes[-1].send(frame)

    def frames_without_pings(self) -> list[str]:
        """The frames the page sent, without its keep-alive `ping` frames.

        The page sends a `ping` every 2 s once the socket is open (spec 017), so
        one can fall between two reads whatever the test does.
        """
        frames: list[str] = []
        for frame in self.received:
            if json.loads(frame)["type"] != "ping":
                frames.append(frame)
        return frames

    def has_join_after(self, frame_count: int) -> bool:
        """Tell whether a `join` frame came after the first `frame_count` frames."""
        for frame in self.received[frame_count:]:
            if json.loads(frame)["type"] == "join":
                return True
        return False


def player_view(
    player_id: str,
    nickname: str,
    colour: int,
    *,
    is_host: bool = False,
    state: PlayerState = PlayerState.ACTIVE,
    selection: Selection | None = None,
) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=state,
        is_host=is_host,
        muted=False,
        selection=selection,
    )


def snapshot_frame(
    view: GridView,
    seq: int,
    players: list[PlayerView],
    *,
    solved: bool = False,
) -> str:
    """A snapshot for `p1`, with the default settings (help mode `free`)."""
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=tuple(players),
        settings=DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )
    return snapshot.model_dump_json()


def with_letter_cells(view: GridView, changes: ChangeList) -> GridView:
    """The view with some letter cells replaced with `model_copy`."""
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def open_room(
    page: Page,
    base_url: str,
    view: GridView,
    players: list[PlayerView],
    *,
    seq: int = 5,
    solved: bool = False,
    cell_count: int = FX01_CELL_COUNT,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, join as `Ana` and show a snapshot."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until(page, lambda: len(mock.received) > 0)
    mock.send(snapshot_frame(view, seq, players, solved=solved))
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(cell_count)
    return mock


# ---- The snapshot of AC-1 ---------------------------------------------------


def ac1_players() -> list[PlayerView]:
    """`p1` (`you`, `Ana`, colour 0, host) and `p2` (`Bob`, colour 3)."""
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)]


def ac1_changes() -> ChangeList:
    """Row 1 of AC-1: T by p1, A by p2, M by p9, I locked by a check, S revealed."""
    return [
        (1, 0, {"letter": "T", "author": "p1"}),
        (1, 1, {"letter": "A", "author": "p2"}),
        (1, 2, {"letter": "M", "author": "p9"}),
        (1, 3, {"letter": "I", "author": "p2", "locked": True}),
        (1, 4, {"letter": "S", "author": None, "locked": True, "revealed": True}),
    ]


def ac1_view(grid: Grid) -> GridView:
    return with_letter_cells(grid_view(grid), ac1_changes())


def open_ac1(
    page: Page, base_url: str, grid: Grid, players: list[PlayerView] | None = None
) -> MockRoomSocket:
    """The page joined with the snapshot of AC-1 (FX-01, `seq` 5)."""
    shown_players = ac1_players() if players is None else players
    return open_room(page, base_url, ac1_view(grid), shown_players, seq=5)


# ---- Events sent by the mock ------------------------------------------------


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return event.model_dump_json()


def cell_locked_frame(
    seq: int, row: int, column: int, letter: str, revealed: bool
) -> str:
    event = CellLocked(
        seq=seq, row=row, column=column, letter=letter, revealed=revealed
    )
    return event.model_dump_json()


def player_left_frame(seq: int, player_id: str) -> str:
    event = PlayerLeft(seq=seq, player_id=player_id, reason=LeaveReason.LEFT)
    return event.model_dump_json()


def player_joined_frame(seq: int, player: PlayerView) -> str:
    return PlayerJoined(seq=seq, player=player).model_dump_json()


# ---- Marks and swatches -----------------------------------------------------


class Box(NamedTuple):
    """A bounding box in CSS px."""

    left: float
    top: float
    right: float
    bottom: float


class Mark(NamedTuple):
    """One `author-mark` element as the page draws it."""

    colour: str | None
    aria_hidden: str | None
    text: str
    background: str
    visibility: str
    box: Box


MARKS_SCRIPT = """
cell => {
  const found = [];
  for (const mark of cell.querySelectorAll('[data-testid="author-mark"]')) {
    const style = getComputedStyle(mark);
    const box = mark.getBoundingClientRect();
    found.push({
      colour: mark.getAttribute('data-colour'),
      ariaHidden: mark.getAttribute('aria-hidden'),
      text: mark.textContent,
      background: style.backgroundColor,
      visibility: style.visibility,
      left: box.left, top: box.top, right: box.right, bottom: box.bottom,
    });
  }
  return found;
}
"""


def marks_of(page: Page, row: int, column: int) -> list[Mark]:
    """Every `author-mark` inside the cell, in document order."""
    raw_marks = cell_at(page, row, column).evaluate(MARKS_SCRIPT)
    marks: list[Mark] = []
    for raw in raw_marks:
        box = Box(raw["left"], raw["top"], raw["right"], raw["bottom"])
        marks.append(
            Mark(
                colour=raw["colour"],
                aria_hidden=raw["ariaHidden"],
                text=raw["text"],
                background=raw["background"],
                visibility=raw["visibility"],
                box=box,
            )
        )
    return marks


def only_mark_of(page: Page, row: int, column: int) -> Mark:
    """The one `author-mark` of a cell; fails unless there is exactly one."""
    marks = marks_of(page, row, column)
    assert len(marks) == 1, f"({row}, {column}) holds {len(marks)} author marks"
    return marks[0]


def box_of(locator: Locator) -> Box:
    found = locator.bounding_box()
    assert found is not None
    return Box(
        found["x"],
        found["y"],
        found["x"] + found["width"],
        found["y"] + found["height"],
    )


MIN_SIDE_FOR_BOX_RULES_PX = 20.0
MARK_INSET_PX = 3.0
MARK_BOTTOM_GAP_MIN_PX = 3.0
MARK_BOTTOM_GAP_MAX_PX = 6.0
MARK_MIN_HEIGHT_PX = 3.0


def mark_box_problems(cell: Box, mark: Box) -> list[str]:
    """How a mark breaks the box rules of "The view, switch on" (empty: none).

    On a cell whose side (its width) is 20 px or more: inside the cell's box
    shrunk by 3 px on every side; bottom edge 3 to 6 px above the cell's bottom
    edge; at least half the side wide; at least 3 px and a tenth of the side high.
    On a smaller cell: inside the cell's box only.
    """
    side = cell.right - cell.left
    problems: list[str] = []
    inset = MARK_INSET_PX if side >= MIN_SIDE_FOR_BOX_RULES_PX else 0.0
    if mark.left < cell.left + inset - SUBPIXEL_PX:
        problems.append(f"left edge {mark.left} is left of {cell.left + inset}")
    if mark.top < cell.top + inset - SUBPIXEL_PX:
        problems.append(f"top edge {mark.top} is above {cell.top + inset}")
    if mark.right > cell.right - inset + SUBPIXEL_PX:
        problems.append(f"right edge {mark.right} is right of {cell.right - inset}")
    if mark.bottom > cell.bottom - inset + SUBPIXEL_PX:
        problems.append(f"bottom edge {mark.bottom} is below {cell.bottom - inset}")
    if side < MIN_SIDE_FOR_BOX_RULES_PX:
        return problems
    gap = cell.bottom - mark.bottom
    if gap < MARK_BOTTOM_GAP_MIN_PX - SUBPIXEL_PX:
        problems.append(f"bottom edge only {gap} px above the cell's")
    if gap > MARK_BOTTOM_GAP_MAX_PX + SUBPIXEL_PX:
        problems.append(f"bottom edge {gap} px above the cell's")
    width = mark.right - mark.left
    if width < side / 2 - SUBPIXEL_PX:
        problems.append(f"{width} px wide on a {side} px cell")
    height = mark.bottom - mark.top
    min_height = max(MARK_MIN_HEIGHT_PX, side / 10)
    if height < min_height - SUBPIXEL_PX:
        problems.append(f"{height} px high on a {side} px cell")
    return problems


def background_of(locator: Locator) -> str:
    background = locator.evaluate("el => getComputedStyle(el).backgroundColor")
    assert isinstance(background, str)
    return background


def swatch_colour(page: Page, player_id: str) -> str:
    """The computed background colour of the `roster-colour` of a player."""
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    swatch = page.locator(selector).get_by_test_id("roster-colour")
    return background_of(swatch)


# ---- The band's colours (AC-1, "Contrast" and the departed band) ------------

MIN_BAND_CONTRAST = 3.0
GREY_CHANNEL_SPREAD = 8.0  # "its red, green and blue channels are within 8"
ANGLE_TOLERANCE_DEGREES = 0.001

# Declares `readBand(cell)`, after spec 035's colour helpers (`parseColour`,
# `over`, `contrast`, `WHITE`). It returns the cell's computed background and,
# for its one `author-mark`, the mark's computed background colour and image, the
# images of its layers, the colour stops of the mark's own image and every colour
# of the band with its ratio against the cell. A layer is an element inside the
# mark, or the mark's `::before` or `::after` whose computed `content` is not
# `none`, at least half the cell side wide and 1 px high.
BAND_COLOURS_JS = COLOUR_CONTRAST_JS + r"""
const BAND_COLOUR_PATTERN = new RegExp(
  '(?:rgba?|hsla?|hwb|oklab|oklch|lab|lch|color)\\([^()]*\\)'
  + '|\\btransparent\\b|\\bcurrentcolor\\b',
  'gi'
);
function imageColours(image, style) {
  if (image === 'none') {
    return [];
  }
  const found = [];
  for (const text of image.match(BAND_COLOUR_PATTERN) || []) {
    found.push(text.toLowerCase() === 'currentcolor' ? style.color : text);
  }
  return found;
}
function bandLayers(cell, mark) {
  const side = cell.getBoundingClientRect().width;
  const layers = [{source: 'author-mark', style: getComputedStyle(mark)}];
  for (const element of mark.querySelectorAll('*')) {
    const box = element.getBoundingClientRect();
    if (box.width >= side / 2 && box.height >= 1) {
      layers.push({source: element.tagName.toLowerCase(),
                   style: getComputedStyle(element)});
    }
  }
  for (const pseudo of ['::before', '::after']) {
    const style = getComputedStyle(mark, pseudo);
    if (style.content === 'none') {
      continue;
    }
    if (parseFloat(style.width) >= side / 2 && parseFloat(style.height) >= 1) {
      layers.push({source: pseudo, style: style});
    }
  }
  return layers;
}
function readBand(cell) {
  const marks = cell.querySelectorAll('[data-testid="author-mark"]');
  const backgroundText = getComputedStyle(cell).backgroundColor;
  const reading = {
    marks: marks.length, background: backgroundText, markBackground: '',
    markImage: '', layerImages: [], markStops: [], colours: [],
  };
  if (marks.length !== 1) {
    return reading;
  }
  const cellBackground = over(parseColour(backgroundText), WHITE);
  const addColour = (source, text) => {
    const rgba = parseColour(text);
    const ratio = contrast(over(rgba, cellBackground), cellBackground);
    reading.colours.push({source: source, text: text, rgba: rgba, ratio: ratio});
  };
  for (const layer of bandLayers(cell, marks[0])) {
    const image = layer.style.backgroundImage;
    const stops = imageColours(image, layer.style);
    if (layer.source === 'author-mark') {
      reading.markBackground = layer.style.backgroundColor;
      reading.markImage = image;
      for (const text of stops) {
        reading.markStops.push(parseColour(text));
      }
    } else {
      reading.layerImages.push([layer.source, image]);
    }
    addColour(layer.source + ' background-color', layer.style.backgroundColor);
    for (const text of stops) {
      addColour(layer.source + ' background-image', text);
    }
  }
  return reading;
}
"""

BANDS_SCRIPT = "cells => {\n" + BAND_COLOURS_JS + r"""
  const found = [];
  for (const [row, column] of cells) {
    const cell = document.querySelector(
      `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`
    );
    found.push(readBand(cell));
  }
  return found;
}
"""

Rgba = tuple[float, float, float, float]


class BandColour(NamedTuple):
    """One colour of a band: where it comes from, its text, value and ratio."""

    source: str
    text: str
    rgba: Rgba
    ratio: float


class BandReading(NamedTuple):
    """A cell's computed background and the colours of its `author-mark`."""

    marks: int
    background: str
    mark_background: str
    mark_image: str
    layer_images: list[tuple[str, str]]
    mark_stops: list[Rgba]
    colours: list[BandColour]


def rgba_from(raw: list[float]) -> Rgba:
    """The (red, green, blue, alpha) tuple of a colour read in the page."""
    return (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3]))


# Any: a JSON object returned by `readBand` in the page.
def band_reading_from(raw: dict[str, Any]) -> BandReading:
    """Turn what `readBand` returned into a `BandReading`."""
    colours: list[BandColour] = []
    for colour in raw["colours"]:
        colours.append(
            BandColour(
                source=colour["source"],
                text=colour["text"],
                rgba=rgba_from(colour["rgba"]),
                ratio=float(colour["ratio"]),
            )
        )
    layer_images: list[tuple[str, str]] = []
    for source, image in raw["layerImages"]:
        layer_images.append((source, image))
    mark_stops: list[Rgba] = []
    for stop in raw["markStops"]:
        mark_stops.append(rgba_from(stop))
    return BandReading(
        marks=int(raw["marks"]),
        background=raw["background"],
        mark_background=raw["markBackground"],
        mark_image=raw["markImage"],
        layer_images=layer_images,
        mark_stops=mark_stops,
        colours=colours,
    )


def band_readings(page: Page, cells: list[Cell]) -> list[BandReading]:
    """Read the bands of several cells in one `page.evaluate`, in that order."""
    raw_readings = page.evaluate(BANDS_SCRIPT, [list(cell) for cell in cells])
    readings: list[BandReading] = []
    for raw in raw_readings:
        readings.append(band_reading_from(raw))
    return readings


def counted_colours(reading: BandReading) -> list[BandColour]:
    """The colours of a band that count: every one whose alpha is not 0."""
    counted: list[BandColour] = []
    for colour in reading.colours:
        if colour.rgba[3] > 0:
            counted.append(colour)
    return counted


def band_contrast(reading: BandReading) -> float:
    """The band's contrast: the highest ratio of its colours against the cell."""
    highest = 0.0
    for colour in counted_colours(reading):
        highest = max(highest, colour.ratio)
    return highest


def describe_colours(reading: BandReading) -> str:
    """The band's colours and ratios, for a failure message."""
    parts: list[str] = []
    for colour in reading.colours:
        parts.append(f"{colour.source} {colour.text} ({colour.ratio:.2f}:1)")
    return "; ".join(parts)


def band_contrast_problems(reading: BandReading, swatch: str | None) -> list[str]:
    """How a band breaks "Contrast" and its first item (empty: none).

    Args:
        reading: The band of one cell, in the state to check.
        swatch: The computed background colour of the author's `roster-colour`,
            which the mark's own background colour must equal; None for a
            departed author, who has no swatch.

    Returns:
        One line per broken rule: a colour that counts but is not opaque, a
        contrast under 3:1, a main colour that is not the author's swatch.
    """
    if reading.marks != 1:
        return [f"{reading.marks} author-mark elements in the cell"]
    problems: list[str] = []
    for colour in counted_colours(reading):
        if colour.rgba[3] < 1.0:
            problems.append(f"{colour.source} {colour.text} is not opaque")
    contrast = band_contrast(reading)
    if contrast < MIN_BAND_CONTRAST:
        problems.append(
            f"contrast {contrast:.2f}:1 on {reading.background}: "
            f"{describe_colours(reading)}"
        )
    if swatch is not None and reading.mark_background != swatch:
        problems.append(
            f"background-color {reading.mark_background}, not the swatch {swatch}"
        )
    return problems


def first_gradient_argument(image: str) -> str:
    """The text before the first top-level comma inside a gradient's brackets."""
    inside = image[image.index("(") + 1 :]
    depth = 0
    for index, character in enumerate(inside):
        if character == "(":
            depth += 1
        elif character == ")" and depth > 0:
            depth -= 1
        elif character in ",)" and depth == 0:
            return inside[:index].strip()
    return inside.strip()


ANGLE_PATTERN = re.compile(
    r"^(-?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)(deg|grad|rad|turn)$"
)
DEGREES_PER_UNIT = {"deg": 1.0, "grad": 0.9, "rad": 180.0 / math.pi, "turn": 360.0}
VERTICAL_SIDES = {"top", "bottom"}
HORIZONTAL_SIDES = {"left", "right"}


def is_diagonal(direction: str) -> bool:
    """Tell whether a gradient's first argument draws a diagonal line.

    An angle that is not a whole multiple of 90 degrees, or a corner keyword such
    as `to top right`, is diagonal. A side keyword, a multiple of 90 degrees or a
    missing direction (the first argument is then a colour stop) is not.
    """
    match = ANGLE_PATTERN.match(direction)
    if match is not None:
        degrees = float(match.group(1)) * DEGREES_PER_UNIT[match.group(2)]
        nearest_right_angle = 90.0 * round(degrees / 90.0)
        return abs(degrees - nearest_right_angle) > ANGLE_TOLERANCE_DEGREES
    words = direction.split()
    if len(words) != 3 or words[0] != "to":
        return False
    sides = {words[1], words[2]}
    return len(sides & VERTICAL_SIDES) == 1 and len(sides & HORIZONTAL_SIDES) == 1


def is_grey(rgba: Rgba) -> bool:
    """Tell whether a colour's red, green and blue channels are within 8."""
    red, green, blue, _alpha = rgba
    return max(red, green, blue) - min(red, green, blue) <= GREY_CHANNEL_SPREAD


def hatched_problems(reading: BandReading) -> list[str]:
    """How a departed author's band fails to be hatched in greys (empty: none).

    Its computed `background-image` is a `repeating-linear-gradient` whose line
    is diagonal and whose colour stops hold at least two different colours, and
    each colour of the band that counts is a grey.
    """
    if reading.marks != 1:
        return [f"{reading.marks} author-mark elements in the cell"]
    problems: list[str] = []
    image = reading.mark_image
    if not image.startswith("repeating-linear-gradient("):
        problems.append(f"background-image {image!r} is no repeating-linear-gradient")
    else:
        direction = first_gradient_argument(image)
        if not is_diagonal(direction):
            problems.append(f"the gradient's line {direction!r} is not diagonal")
    different_stops = set(reading.mark_stops)
    if len(different_stops) < 2:
        problems.append(f"the colour stops of {image!r} hold under two colours")
    for colour in counted_colours(reading):
        if not is_grey(colour.rgba):
            problems.append(f"{colour.source} {colour.text} is not a grey")
    return problems


def pattern_problems(reading: BandReading) -> list[str]:
    """How a player's band has a pattern (empty: none).

    The computed `background-image` of `author-mark` and of each of its layers is
    `none`.
    """
    if reading.marks != 1:
        return [f"{reading.marks} author-mark elements in the cell"]
    problems: list[str] = []
    if reading.mark_image != "none":
        problems.append(f"author-mark has the background-image {reading.mark_image}")
    for source, image in reading.layer_images:
        if image != "none":
            problems.append(f"its layer {source} has the background-image {image}")
    return problems


# ---- FX-02 with eight players (spec 026's `FX02_FULL_WRONG`) ----------------

FX02_CELL_COUNT = 13 * 17
# Spec 013 AC-6's players, as spec 026's status snapshots give them: `p1` (`Ana`,
# host, colour 0) and `p2` to `p8`, with colours 1 to 7.
EIGHT_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]


def letter_positions_of(grid: Grid) -> list[Cell]:
    """The (row, column) of every letter cell of a grid, in grid order."""
    positions: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    return positions


def fx02_full_wrong_view(grid: Grid) -> GridView:
    """`FX02_FULL_WRONG` of spec 026: every letter cell holds `E` by `p2`."""
    changes: ChangeList = []
    for row, column in letter_positions_of(grid):
        changes.append((row, column, {"letter": "E", "author": "p2"}))
    return with_letter_cells(grid_view(grid), changes)


def eight_players(second_nickname: str = "Bob") -> list[PlayerView]:
    """`p1` (`Ana`, host, colour 0) and `p2` to `p8` (colours 1 to 7).

    Args:
        second_nickname: The nickname of `p2`.

    Returns:
        The eight players, `p1` first.
    """
    players = [player_view("p1", EIGHT_NICKNAMES[0], 0, is_host=True)]
    for number in range(2, 9):
        nickname = EIGHT_NICKNAMES[number - 1]
        if number == 2:
            nickname = second_nickname
        players.append(player_view(f"p{number}", nickname, number - 1))
    return players


def with_selection(
    players: list[PlayerView], player_ids: list[str], selection: Selection
) -> list[PlayerView]:
    """The players, those of `player_ids` selecting `selection` (spec 013)."""
    result: list[PlayerView] = []
    for player in players:
        if player.player_id in player_ids:
            result.append(player.model_copy(update={"selection": selection}))
        else:
            result.append(player)
    return result


# ---- Two pages on the live server (AC-1 and AC-3) ---------------------------


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


def expect_confirmed(page: Page, row: int, column: int, author: str) -> None:
    """Wait until the cell's confirmed author is `author` and nothing is pending."""
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-author", author)
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def ana_types_t_and_bob_types_a(
    page: Page, bob_page: Page, url: str, enter_room: EnterRoom
) -> tuple[str, str]:
    """Ana and Bob join; Ana types T at (1, 0), Bob A at (1, 1); return their ids.

    Returns once Ana's page shows both letters confirmed with their authors.
    """
    enter_room(page, url, "Ana")
    enter_room(bob_page, url, "Bob")
    ana_id = room_page(page).get_attribute("data-you")
    bob_id = room_page(bob_page).get_attribute("data-you")
    assert ana_id
    assert bob_id
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    expect_confirmed(page, 1, 0, ana_id)
    cell_at(bob_page, 1, 1).click()
    bob_page.keyboard.press("a")
    expect_confirmed(bob_page, 1, 1, bob_id)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect_confirmed(page, 1, 1, bob_id)
    return ana_id, bob_id


# ---- Desktop and touch windows ----------------------------------------------


class OpenWindow(Protocol):
    """The `window` fixtures: open a page of a size, desktop or touch."""

    def __call__(self, width: int, height: int, touch: bool) -> Page: ...


def new_context(
    browser: Browser, browser_name: str, width: int, height: int, touch: bool
) -> BrowserContext:
    """A desktop or touch context (spec 024's "Test harness", from spec 014's)."""
    viewport = {"width": width, "height": height}
    if not touch:
        return browser.new_context(viewport=viewport)
    if browser_name == "firefox":
        context = browser.new_context(
            viewport=viewport, has_touch=True, device_scale_factor=2
        )
    else:
        context = browser.new_context(
            viewport=viewport,
            has_touch=True,
            is_mobile=True,
            device_scale_factor=2,
        )
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    return context


def window_opener(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Yield `open_window(width, height, touch)`; close its contexts afterwards."""
    contexts: list[BrowserContext] = []

    def open_window(width: int, height: int, touch: bool) -> Page:
        context = new_context(browser, browser_name, width, height, touch)
        contexts.append(context)
        return context.new_page()

    yield open_window
    for context in contexts:
        context.close()


# ---- Spec 013 AC-6's layout checks ------------------------------------------


PAGE_SIZES_SCRIPT = (
    "() => [document.documentElement.scrollWidth, window.innerWidth,"
    " document.documentElement.scrollHeight, window.innerHeight]"
)


def layout_problems(page: Page, touch: bool) -> list[str]:
    """How the page breaks spec 013 AC-6's guarantees (empty: none).

    `grid-viewport` at least 100 px high, no horizontal or vertical page scroll,
    the grid inside the viewport at zoom 1, and `clue-bar` inside the window,
    above the in-app keyboard in a touch context.
    """
    problems: list[str] = []
    viewport = page.get_by_test_id("grid-viewport")
    viewport_box = box_of(viewport)
    grid_box = box_of(page.get_by_test_id("grid"))
    bar_box = box_of(page.get_by_test_id("clue-bar"))
    scroll_width, window_width, scroll_height, window_height = page.evaluate(
        PAGE_SIZES_SCRIPT
    )
    viewport_height = viewport_box.bottom - viewport_box.top
    if viewport_height < MIN_GRID_VIEWPORT_PX:
        problems.append(f"grid-viewport is {viewport_height} px high")
    if scroll_width > window_width:
        problems.append(f"page scrolls sideways: {scroll_width} > {window_width}")
    if scroll_height > window_height:
        problems.append(f"page scrolls down: {scroll_height} > {window_height}")
    zoom = viewport.get_attribute("data-zoom")
    if zoom != "1":
        problems.append(f"data-zoom is {zoom}")
    if not box_inside(grid_box, viewport_box):
        problems.append(f"grid {grid_box} is not inside the viewport {viewport_box}")
    window_box = Box(0.0, 0.0, float(window_width), float(window_height))
    if not box_inside(bar_box, window_box):
        problems.append(f"clue-bar {bar_box} is not inside the window")
    if touch:
        keyboard_box = box_of(page.get_by_test_id("keyboard"))
        if bar_box.bottom > keyboard_box.top + LAYOUT_EPSILON_PX:
            problems.append(f"clue-bar {bar_box} goes below the top of the keyboard")
        if keyboard_box.bottom > window_height + LAYOUT_EPSILON_PX:
            problems.append(f"keyboard {keyboard_box} goes below the window")
    return problems


def box_inside(inner: Box, outer: Box) -> bool:
    """Tell whether `inner` lies inside `outer`, with 1 px of tolerance."""
    return (
        inner.left >= outer.left - LAYOUT_EPSILON_PX
        and inner.top >= outer.top - LAYOUT_EPSILON_PX
        and inner.right <= outer.right + LAYOUT_EPSILON_PX
        and inner.bottom <= outer.bottom + LAYOUT_EPSILON_PX
    )
