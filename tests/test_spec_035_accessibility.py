"""Tests of spec 035: accessibility.

Every test runs in a browser, except the static ones of AC-9 (the language
checker on its samples and the new `fr.json` keys). The keyboard walk (AC-1, AC-2)
uses the live server and the real WebSocket; AC-3 to AC-7 use a mocked socket;
AC-8 and AC-9 scan the rendered pages of the states K1 to K7 of the spec.

Not tested here, and why:

- State K7 `/g/99`: the live server answers `GET /g/99` with the 404 JSON body of
  spec 004 AC-4 and never serves the app there, so no page with `<html lang="fr">`
  exists to scan (see the report). `/r/ZZZZZZ` is scanned.
- The announcement of a word of one cell (`a11y.announcement_one`): FX-01 holds no
  such word and the spec gives no hand-built view for it.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    FloatRect,
    Locator,
    Page,
    WebSocket,
    WebSocketRoute,
    expect,
)

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.protocol import (
    CellView,
    CheckResult,
    Direction,
    ErrorCode,
    ErrorMessage,
    GridView,
    HelpMode,
    LetterCellView,
    LetterChanged,
    PlayerJoined,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Selection,
    SelectionMoved,
    SettingsChanged,
    Snapshot,
    WordTarget,
    grid_view,
)

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
ROOM_CODE = "ABC123"
UNKNOWN_CODE = "ZZZZZZ"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_TIMEOUT_MS = 5000
ROOM_TIMEOUT_MS = 10_000
SETTLE_MS = 300
MAX_TABS = 60
EPSILON = 1.0

MIN_OUTLINE_PX = 2.0
MIN_FOCUS_CONTRAST = 3.0
MIN_TEXT_CONTRAST = 4.5
BOLD_WEIGHT = 700

WINDOW_SIZES = [(1280, 720), (360, 740)]

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]

# The solution of FX-01 (specs/_reference.md), in row-major order.
SOLUTION: dict[Cell, str] = {(0, 1): "N"}
for _column, _letter in enumerate("TAMIS"):
    SOLUTION[(1, _column)] = _letter
for _row, _word in ((2, "VIDE"), (3, "AMEN"), (4, "LEST")):
    for _offset, _letter in enumerate(_word):
        SOLUTION[(_row, _offset + 1)] = _letter
LAST_CELL: Cell = (4, 4)

FX01_CLUES = [
    "Passoire fine",
    "De la marine",
    "Artiste muet",
    "Fatales à César",
    "Flaire",
    "Sans contenu",
    "Fin de prière",
    "Alourdit le ballon",
]

NEW_KEYS = {
    "a11y.announcement": "{clue}, {direction}, {length} lettres, lettre {position}",
    "a11y.announcement_one": "{clue}, {direction}, 1 lettre",
    "a11y.direction.across": "horizontal",
    "a11y.direction.down": "vertical",
    "a11y.grid_hint": (
        "Flèches pour se déplacer, Tab pour le mot suivant. "
        "Échap puis Tab pour quitter la grille."
    ),
    "grid.remote_overflow": "+{count}",
    "a11y.remote_overflow": "{count} autres joueurs",
}

# ---- In-page scripts ----------------------------------------------------------

# Colour helpers shared by the scripts: `parseColour` gives [r, g, b, alpha] from a
# computed colour (rgb() fast path, a canvas for any other CSS colour syntax),
# `over` composites a colour on an opaque one, `contrast` is the WCAG 2.x ratio.
COLOUR_HELPERS = r"""
const canvas = document.createElement('canvas');
canvas.width = 1;
canvas.height = 1;
const drawing = canvas.getContext('2d', { willReadFrequently: true });
function parseColour(text) {
  const match = text.match(/^rgba?\(([^)]*)\)$/);
  if (match) {
    const parts = match[1].split(/[\s,\/]+/).filter(part => part !== '');
    let alpha = 1;
    if (parts.length > 3) {
      alpha = parts[3].endsWith('%') ? parseFloat(parts[3]) / 100 : Number(parts[3]);
    }
    return [Number(parts[0]), Number(parts[1]), Number(parts[2]), alpha];
  }
  drawing.clearRect(0, 0, 1, 1);
  drawing.fillStyle = '#000000';
  drawing.fillStyle = text;
  drawing.fillRect(0, 0, 1, 1);
  const data = drawing.getImageData(0, 0, 1, 1).data;
  return [data[0], data[1], data[2], data[3] / 255];
}
function over(top, bottom) {
  const alpha = top[3];
  return [
    top[0] * alpha + bottom[0] * (1 - alpha),
    top[1] * alpha + bottom[1] * (1 - alpha),
    top[2] * alpha + bottom[2] * (1 - alpha),
    1,
  ];
}
function channel(value) {
  const scaled = value / 255;
  if (scaled <= 0.03928) {
    return scaled / 12.92;
  }
  return Math.pow((scaled + 0.055) / 1.055, 2.4);
}
function luminance(colour) {
  return 0.2126 * channel(colour[0]) + 0.7152 * channel(colour[1])
    + 0.0722 * channel(colour[2]);
}
function contrast(first, second) {
  const lighter = Math.max(luminance(first), luminance(second));
  const darker = Math.min(luminance(first), luminance(second));
  return (lighter + 0.05) / (darker + 0.05);
}
const WHITE = [255, 255, 255, 1];
"""

CONTRAST_SCAN_SCRIPT = "() => {" + COLOUR_HELPERS + r"""
  const skippedTags = new Set(
    ['SCRIPT', 'STYLE', 'NOSCRIPT', 'OPTION', 'TITLE', 'HEAD']
  );
  const measurements = [];
  for (const element of document.body.querySelectorAll('*')) {
    if (skippedTags.has(element.tagName)) {
      continue;
    }
    let ownText = '';
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        ownText += node.textContent;
      }
    }
    ownText = ownText.trim();
    if (ownText === '') {
      continue;
    }
    const style = getComputedStyle(element);
    const box = element.getBoundingClientRect();
    if (box.width === 0 || box.height === 0 || style.visibility !== 'visible') {
      continue;
    }
    if (element.closest('.visually-hidden') || element.closest(':disabled')) {
      continue;
    }
    let opacity = 1;
    let background = null;
    for (let node = element; node; node = node.parentElement) {
      const nodeStyle = getComputedStyle(node);
      opacity *= parseFloat(nodeStyle.opacity);
      if (background === null) {
        const candidate = parseColour(nodeStyle.backgroundColor);
        if (candidate[3] > 0) {
          background = candidate;
        }
      }
    }
    const opaqueBackground = background === null ? WHITE : over(background, WHITE);
    const text = parseColour(style.color);
    text[3] = text[3] * opacity;
    const shown = over(text, opaqueBackground);
    const ratio = contrast(shown, opaqueBackground);
    const row = element.closest('[data-testid="roster-player"]');
    measurements.push({
      tag: element.tagName,
      testid: element.getAttribute('data-testid'),
      rowState: row === null ? null : row.getAttribute('data-state'),
      text: ownText,
      opacity: opacity,
      ratio: ratio,
    });
  }
  return measurements;
}"""

LANGUAGE_SCAN_SCRIPT = r"""
() => {
  const skippedTags = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TITLE', 'HEAD']);
  const attributes = ['aria-label', 'title', 'placeholder', 'alt'];
  const found = [];
  for (const element of document.body.querySelectorAll('*')) {
    if (skippedTags.has(element.tagName)) {
      continue;
    }
    let rendered = element.getClientRects().length > 0;
    if (element.tagName === 'OPTION') {
      const select = element.closest('select');
      rendered = select !== null && select.getClientRects().length > 0;
    }
    if (!rendered || getComputedStyle(element).visibility !== 'visible') {
      continue;
    }
    for (const node of element.childNodes) {
      if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== '') {
        found.push(node.textContent.trim());
      }
    }
    for (const name of attributes) {
      const value = element.getAttribute(name);
      if (value !== null && value.trim() !== '') {
        found.push(value.trim());
      }
    }
  }
  return found;
}
"""

FOCUS_OUTLINE_SCRIPT = "() => {" + COLOUR_HELPERS + r"""
  const element = document.activeElement;
  const style = getComputedStyle(element);
  const colour = over(parseColour(style.outlineColor), WHITE);
  return {
    style: style.outlineStyle,
    width: parseFloat(style.outlineWidth),
    ratio: contrast(colour, WHITE),
  };
}"""

ACTIVE_ELEMENT_SCRIPT = r"""
() => {
  const element = document.activeElement;
  if (element === null) {
    return null;
  }
  return {testId: element.getAttribute('data-testid')};
}
"""

# What `Walker.tab_to` needs to know before each press: how many elements are the
# target (they have the test id and, when a selector is given, match it) and, when
# there is exactly one, whether it has the focus, whether the grid has the focus,
# and whether the target comes before the focused element in document order. With
# the focus on `body`, the target never comes before it.
TAB_TARGET_SCRIPT = r"""
([testId, selector]) => {
  const targets = [];
  for (const element of document.querySelectorAll(`[data-testid="${testId}"]`)) {
    if (selector === '' || element.matches(selector)) {
      targets.push(element);
    }
  }
  const grid = document.querySelector('[data-testid="grid"]');
  const focused = document.activeElement;
  const state = {
    matches: targets.length,
    onTarget: false,
    onGrid: focused !== null && focused === grid,
    targetIsBefore: false,
  };
  if (targets.length === 1 && focused !== null) {
    state.onTarget = focused === targets[0];
    const position = focused.compareDocumentPosition(targets[0]);
    state.targetIsBefore = (position & Node.DOCUMENT_POSITION_PRECEDING) !== 0;
  }
  return state;
}
"""

SENTINEL_TEST_ID = "tab-sentinel"

# The sentinel of the spec's "Test harness": a button appended as the last child of
# `body`, fixed in a corner so that the layout does not change. The room page has
# nothing focusable after the grid, so the sentinel becomes the first focusable
# element after it, and `Escape` then `Tab` moves the focus there in every engine.
ADD_SENTINEL_SCRIPT = r"""
() => {
  const sentinel = document.createElement('button');
  sentinel.type = 'button';
  sentinel.setAttribute('data-testid', 'tab-sentinel');
  sentinel.textContent = 'Sentinel';
  sentinel.style.position = 'fixed';
  sentinel.style.left = '0';
  sentinel.style.bottom = '0';
  document.body.appendChild(sentinel);
}
"""

# The `Tab` listener of the spec's "Test harness": on `window`, bubble phase, it
# records `defaultPrevented` of each Tab keydown (with or without Shift), which tells
# whether the page cancelled it.
TAB_LISTENER_SCRIPT = r"""
() => {
  window.tabKeydowns = [];
  window.addEventListener('keydown', event => {
    if (event.key === 'Tab') {
      window.tabKeydowns.push({
        shift: event.shiftKey,
        defaultPrevented: event.defaultPrevented,
      });
    }
  });
}
"""

# After the released Tab, with nothing focusable after the grid: the focus left the
# page content wherever the browser could move it.
FOCUS_LEFT_THE_PAGE_CONTENT_SCRIPT = r"""
() => {
  const grid = document.querySelector('[data-testid="grid"]');
  return document.activeElement !== grid || !document.hasFocus();
}
"""

# Is the focus where a plain Tab (direction 1) or Shift+Tab (direction -1) from the
# grid leads: on the next (previous) focusable element in document order.
NEIGHBOUR_FOCUSED_SCRIPT = r"""
direction => {
  const grid = document.querySelector('[data-testid="grid"]');
  const focusable = [];
  const selector = 'a[href], button, input, select, textarea, [tabindex]';
  for (const element of document.querySelectorAll(selector)) {
    const tabindex = element.getAttribute('tabindex');
    if (element.disabled || (tabindex !== null && Number(tabindex) < 0)) {
      continue;
    }
    if (element.tagName === 'INPUT' && element.type === 'hidden') {
      continue;
    }
    const hidden = getComputedStyle(element).visibility === 'hidden';
    if (hidden || element.getClientRects().length === 0) {
      continue;
    }
    focusable.push(element);
  }
  const neighbour = focusable[focusable.indexOf(grid) + direction];
  return neighbour !== undefined && document.activeElement === neighbour;
}
"""

LETTER_OUTLINES_SCRIPT = r"""
() => {
  const result = [];
  const cells = document.querySelectorAll(
    '[data-testid="cell"][data-type="letter"]'
  );
  for (const cell of cells) {
    const style = getComputedStyle(cell);
    result.push({
      row: Number(cell.getAttribute('data-row')),
      column: Number(cell.getAttribute('data-column')),
      selected: cell.getAttribute('data-selected') === 'true',
      style: style.outlineStyle,
      width: parseFloat(style.outlineWidth),
    });
  }
  return result;
}
"""

# Counts, in `window.announcementRewrites`, the mutations of a live region.
OBSERVE_REWRITES_SCRIPT = r"""
region => {
  window.announcementRewrites = 0;
  const observer = new MutationObserver(records => {
    window.announcementRewrites += records.length;
  });
  observer.observe(region, {
    childList: true,
    characterData: true,
    subtree: true,
    attributes: true,
  });
}
"""

# ---- Fixtures and small helpers -------------------------------------------------


def load_fr() -> dict[str, str]:
    """Return the French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def make_entry(
    grid: Grid, number: int, published_on: date, force: int, published: bool
) -> CatalogueEntry:
    return CatalogueEntry(
        number=number,
        published_on=published_on,
        force=force,
        published=published,
        **credits(),
        grid=grid,
    )


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    entries = (
        make_entry(fx01_grid, 1, date(2026, 9, 1), 1, True),
        make_entry(fx01_grid, 2, date(2026, 10, 1), 2, True),
        make_entry(fx01_grid, 3, date(2026, 10, 1), 1, True),
        make_entry(fx01_grid, 4, date(2026, 10, 5), 3, False),
    )
    return Catalogue(entries=entries)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    contexts: list[BrowserContext] = []

    def make_page(width: int, height: int) -> Page:
        context = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(context)
        return context.new_page()

    yield make_page
    for context in contexts:
        context.close()


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def grid_of(page: Page) -> Locator:
    return page.get_by_test_id("grid")


def announcement_of(page: Page) -> Locator:
    return page.get_by_test_id("grid-announcement")


def expect_word(page: Page, word: str) -> None:
    expect(grid_of(page)).to_have_attribute("data-word", word)


def expect_selected(page: Page, row: int, column: int) -> None:
    expect(grid_of(page)).to_have_attribute("data-selected-row", str(row))
    expect(grid_of(page)).to_have_attribute("data-selected-column", str(column))


def expect_focus_on_grid(page: Page) -> None:
    expect(grid_of(page)).to_be_focused()


def computed(locator: Locator, property_name: str) -> str:
    """The computed style property `property_name` (camelCase) of an element."""
    value = locator.evaluate(f"el => getComputedStyle(el).{property_name}")
    assert isinstance(value, str)
    return value


# ---- Mocked room ----------------------------------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self) -> None:
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def types(self) -> list[str]:
        """The `type` of every frame the page sent, in order."""
        return [json.loads(frame)["type"] for frame in self.received]


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


def default_players() -> list[PlayerView]:
    """`p1` (`you`, host) and `p2`."""
    return [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)]


def room_settings(locked: bool = False) -> RoomSettings:
    return RoomSettings(
        help_mode=HelpMode.FREE,
        reveal_budget=RevealBudget(letters=5, words=1),
        locked=locked,
    )


def snapshot_frame(
    view: GridView, seq: int, players: list[PlayerView], solved: bool = False
) -> str:
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=tuple(players),
        settings=room_settings(),
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
    new_cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, update in changes:
                if cell.row == row and cell.column == column:
                    new_cell = cell.model_copy(update=update)
        new_cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(new_cells)})


def open_nickname_form(page: Page, base_url: str) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and wait for the nickname form."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    expect(page.get_by_test_id("nickname-input")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    return mock


def open_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    changes: ChangeList | None = None,
    players: list[PlayerView] | None = None,
    seq: int = 5,
    solved: bool = False,
    cell_count: int = 25,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket and show a grid (FX-01) as `p1` at `seq`."""
    mock = open_nickname_form(page, base_url)
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until(page, lambda: len(mock.received) > 0)
    view = grid_view(grid)
    if changes is not None:
        view = with_letter_cells(view, changes)
    shown_players = default_players() if players is None else players
    mock.send(snapshot_frame(view, seq, shown_players, solved))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))
    expect(page.get_by_test_id("cell")).to_have_count(cell_count)
    return mock


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


def selection_frame(player_id: str, row: int, column: int, direction: Direction) -> str:
    selection = Selection(row=row, column=column, direction=direction)
    return SelectionMoved(player_id=player_id, selection=selection).model_dump_json()


# ---- Keyboard walker ------------------------------------------------------------


class Reached(NamedTuple):
    """An element a `tab_to` reached, with its focus outline."""

    test_id: str
    outline_style: str
    outline_width: float
    outline_contrast: float


class TabState(NamedTuple):
    """Where the focus is, compared with the target of a `tab_to`."""

    match_count: int
    on_target: bool
    on_grid: bool
    target_is_before: bool


def read_tab_state(page: Page, test_id: str, selector: str) -> TabState:
    """Count the elements that are the target and say where the focus is."""
    found = page.evaluate(TAB_TARGET_SCRIPT, [test_id, selector])
    return TabState(
        match_count=found["matches"],
        on_target=found["onTarget"],
        on_grid=found["onGrid"],
        target_is_before=found["targetIsBefore"],
    )


class Walker:
    """Keyboard-only navigation of one page (spec 035, "Test harness")."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.reached: list[Reached] = []
        self.outlines: list[list[dict[str, Any]]] = []

    def tab_to(self, test_id: str, selector: str = "") -> None:
        """Move the focus to the one element with `test_id` that matches `selector`.

        Before each press, it stops when the target has the focus. When the grid
        has the focus, it first presses `Escape`, which releases the grid's next
        Tab or Shift+Tab (spec 035, "Leaving the grid"). Then it presses Shift+Tab
        when the target comes before the focused element in document order, and
        Tab otherwise. It fails after 60 presses of Tab or Shift+Tab (the Escape
        presses do not count), so it never relies on Tab wrapping past the end of
        the document.
        """
        # The target may appear a moment after the page asks for it (a roster row).
        wait_until(
            self.page,
            lambda: read_tab_state(self.page, test_id, selector).match_count > 0,
        )
        state = read_tab_state(self.page, test_id, selector)
        if state.match_count != 1:
            pytest.fail(f"{state.match_count} elements match {test_id} {selector}")
        presses = 0
        while not state.on_target:
            if presses == MAX_TABS:
                pytest.fail(f"{test_id} {selector} not reached in {MAX_TABS} presses")
            if state.on_grid:
                self.page.keyboard.press("Escape")
            key = "Shift+Tab" if state.target_is_before else "Tab"
            self.page.keyboard.press(key)
            presses += 1
            state = read_tab_state(self.page, test_id, selector)
        self.record(test_id)

    def record(self, test_id: str) -> None:
        outline = self.page.evaluate(FOCUS_OUTLINE_SCRIPT)
        self.reached.append(
            Reached(
                test_id=test_id,
                outline_style=outline["style"],
                outline_width=outline["width"],
                outline_contrast=outline["ratio"],
            )
        )


def add_sentinel(page: Page) -> None:
    """Append the test-only button that follows the grid in the Tab order.

    Args:
        page: A page that shows the grid. No contrast or language scan may run
            while the sentinel is on the page.
    """
    page.evaluate(ADD_SENTINEL_SCRIPT)


def expect_focus_on_sentinel(page: Page) -> None:
    expect(page.get_by_test_id(SENTINEL_TEST_ID)).to_be_focused()


def watch_tab_keys(page: Page) -> None:
    """Record, from now on, whether the page cancelled each Tab keydown."""
    page.evaluate(TAB_LISTENER_SCRIPT)


def tab_keydowns(page: Page) -> list[dict[str, Any]]:
    """The Tab keydowns recorded since `watch_tab_keys`: `shift`, `defaultPrevented`."""
    recorded = page.evaluate("window.tabKeydowns")
    assert isinstance(recorded, list)
    return recorded


def letter_outlines(page: Page) -> list[dict[str, Any]]:
    outlines = page.evaluate(LETTER_OUTLINES_SCRIPT)
    assert isinstance(outlines, list)
    return outlines


def assert_only_selected_cell_is_outlined(outlines: list[dict[str, Any]]) -> None:
    """The selected cell is `solid` and at least 2 px; the others have no outline."""
    selected = [outline for outline in outlines if outline["selected"]]
    assert len(selected) == 1, outlines
    assert selected[0]["style"] == "solid", selected
    assert selected[0]["width"] >= MIN_OUTLINE_PX, selected
    for outline in outlines:
        if not outline["selected"]:
            assert outline["style"] == "none", outline


# ---- The walk of AC-1 and AC-2 ----------------------------------------------------


class FrameRecorder:
    """The frames a page sends on its room sockets, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[dict[str, Any]] = []
        page.on("websocket", self._on_socket)

    def _on_socket(self, websocket: WebSocket) -> None:
        if websocket.url.endswith("/ws"):
            websocket.on("framesent", self._on_frame)

    def _on_frame(self, payload: str | bytes) -> None:
        text = payload if isinstance(payload, str) else payload.decode("utf-8")
        self.frames.append(json.loads(text))

    def of_type(self, type_name: str) -> list[dict[str, Any]]:
        found: list[dict[str, Any]] = []
        for frame in self.frames:
            if frame["type"] == type_name:
                found.append(frame)
        return found

    def wait_for(self, type_name: str, count: int) -> list[dict[str, Any]]:
        """Wait until `count` frames of that type were sent; return them all."""
        wait_until(self.page, lambda: len(self.of_type(type_name)) >= count)
        return self.of_type(type_name)


class WalkResult(NamedTuple):
    """What the walk of AC-1 left behind."""

    ana: Walker
    recorder: FrameRecorder
    bob_walker: Walker


def press_and_expect_sent(
    walker: Walker, recorder: FrameRecorder, type_name: str, count: int
) -> dict[str, Any]:
    """Press Enter on the focused control; return the new frame of that type."""
    walker.page.keyboard.press("Enter")
    frames = recorder.wait_for(type_name, count)
    return frames[count - 1]


def walk_the_catalogue(walker: Walker, live_server: str) -> None:
    """On `/`: filter by force 1 and start item 1, keyboard only."""
    page = walker.page
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-item").first).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )
    walker.tab_to("force-filter", selector='[data-force="1"]')
    page.keyboard.press("Enter")
    expect(
        page.locator('[data-testid="force-filter"][data-force="1"]')
    ).to_have_attribute("aria-pressed", "true")
    item_one_play = (
        '[data-testid="catalogue-item"][data-number="1"] [data-testid="catalogue-play"]'
    )
    walker.tab_to("catalogue-play", selector=item_one_play)
    page.keyboard.press("Enter")
    page.wait_for_url(re.compile(r"/r/[A-Z0-9]{6}$"), timeout=ROOM_TIMEOUT_MS)
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "joined", timeout=ROOM_TIMEOUT_MS
    )


def walk_the_grid(walker: Walker, recorder: FrameRecorder) -> None:
    """In the room: select, type, move, erase, undo and leave the grid.

    The room is `joined`, so the sentinel is added first: leaving the grid moves
    the focus to it.
    """
    page = walker.page
    add_sentinel(page)
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)
    walker.outlines.append(letter_outlines(page))

    page.keyboard.press("t")
    page.keyboard.press("a")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect_selected(page, 1, 2)

    page.keyboard.press("ArrowDown")
    expect_selected(page, 2, 2)
    page.keyboard.press("ArrowLeft")
    expect_selected(page, 2, 1)
    page.keyboard.press("ArrowUp")
    expect_selected(page, 1, 1)

    page.keyboard.press("Backspace")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "")
    erased = recorder.wait_for("erase", 1)
    assert (erased[0]["row"], erased[0]["column"]) == (1, 1)

    page.keyboard.press("Control+z")
    recorder.wait_for("undo", 1)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    expect_focus_on_sentinel(page)
    walker.outlines.append(letter_outlines(page))


def walk_the_controls(walker: Walker, recorder: FrameRecorder) -> None:
    """Checks, undo, share links, lock and settings, keyboard only."""
    page = walker.page
    expected_scopes = [
        ("check-word", "word"),
        ("check-letter", "letter"),
        ("check-grid", "grid"),
    ]
    for count, (test_id, scope) in enumerate(expected_scopes, start=1):
        walker.tab_to(test_id)
        frame = press_and_expect_sent(walker, recorder, "check", count)
        assert frame["target"]["scope"] == scope

    walker.tab_to("undo-button")
    press_and_expect_sent(walker, recorder, "undo", 2)

    walker.tab_to("copy-link")
    walker.tab_to("share-link")

    lock_room = page.get_by_test_id("lock-room")
    walker.tab_to("lock-room")
    page.keyboard.press("Enter")
    expect(lock_room).to_have_attribute("aria-pressed", "true")
    page.keyboard.press("Enter")
    expect(lock_room).to_have_attribute("aria-pressed", "false")
    locks = recorder.wait_for("lock_room", 2)
    assert [frame["locked"] for frame in locks] == [True, False]

    walker.tab_to("help-mode-select")
    page.keyboard.press("ArrowDown")
    walker.tab_to("settings-save")
    saved = press_and_expect_sent(walker, recorder, "change_settings", 1)
    assert saved["help_mode"] == "vote"


def walk_the_removal(
    walker: Walker, recorder: FrameRecorder, browser: Browser
) -> Walker:
    """Bob joins from the keyboard, then Ana removes him; return Bob's walker."""
    page = walker.page
    bob_context = browser.new_context()
    bob_page = bob_context.new_page()
    bob_walker = Walker(bob_page)
    try:
        bob_page.goto(page.url)
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "nickname", timeout=ROOM_TIMEOUT_MS
        )
        bob_walker.tab_to("nickname-input")
        bob_page.keyboard.type("Bob")
        bob_page.keyboard.press("Enter")
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "joined", timeout=ROOM_TIMEOUT_MS
        )

        label = load_fr()["host.remove_label"].replace("{name}", "Bob")
        walker.tab_to("remove-player", selector=f'[aria-label="{label}"]')
        page.keyboard.press("Enter")
        recorder.wait_for("remove_player", 1)
        expect(bob_page.get_by_test_id("room-page")).to_have_attribute(
            "data-status", "removed", timeout=ROOM_TIMEOUT_MS
        )
    finally:
        bob_context.close()
    return bob_walker


def run_keyboard_walk(page: Page, browser: Browser, live_server: str) -> WalkResult:
    """The whole walk of AC-1; every step uses the keyboard only."""
    recorder = FrameRecorder(page)
    walker = Walker(page)
    walk_the_catalogue(walker, live_server)
    walk_the_grid(walker, recorder)
    walk_the_controls(walker, recorder)
    bob_walker = walk_the_removal(walker, recorder, browser)
    return WalkResult(ana=walker, recorder=recorder, bob_walker=bob_walker)


# ---- AC-1: every action is reachable from the keyboard -------------------------


def test_ac1_every_action_is_reachable_from_the_keyboard(
    page: Page, browser: Browser, live_server: str
) -> None:
    result = run_keyboard_walk(page, browser, live_server)

    reached = [step.test_id for step in result.ana.reached]
    expected_in_order = [
        "force-filter",
        "catalogue-play",
        "grid",
        "check-word",
        "check-letter",
        "check-grid",
        "undo-button",
        "copy-link",
        "share-link",
        "lock-room",
        "help-mode-select",
        "settings-save",
        "remove-player",
    ]
    assert reached == expected_in_order
    assert [step.test_id for step in result.bob_walker.reached] == ["nickname-input"]
    letters = result.recorder.of_type("edit_letter")
    typed = [(frame["row"], frame["column"], frame["letter"]) for frame in letters]
    assert typed[:2] == [(1, 0, "T"), (1, 1, "A")]


# ---- AC-2: the focus is always visible -----------------------------------------


def test_ac2_every_element_reached_by_the_walk_shows_a_visible_focus(
    page: Page, browser: Browser, live_server: str
) -> None:
    result = run_keyboard_walk(page, browser, live_server)

    assert len(result.ana.outlines) == 2
    for outlines in result.ana.outlines:
        assert_only_selected_cell_is_outlined(outlines)
    steps = result.ana.reached + result.bob_walker.reached
    assert len(steps) == 14
    assert "grid" in [step.test_id for step in steps]
    for step in steps:
        assert step.outline_style not in ("none", "auto"), step
        assert step.outline_width >= MIN_OUTLINE_PX, step
        assert step.outline_contrast >= MIN_FOCUS_CONTRAST, step


def test_ac2_the_selected_cell_keeps_its_outline_without_the_focus(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    add_sentinel(page)
    walker = Walker(page)
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_selected(page, 1, 0)
    assert_only_selected_cell_is_outlined(letter_outlines(page))

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect_focus_on_sentinel(page)
    expect_selected(page, 1, 0)
    assert_only_selected_cell_is_outlined(letter_outlines(page))


def test_ac2_no_cell_is_outlined_before_a_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    for outline in letter_outlines(page):
        assert outline["style"] == "none", outline


# Pointer focus must not disturb the host panel's fade (spec 014 AC-7); a keyboard
# focus on a panel control hides it. The probes run in K2 on a 320x568 phone.
# On a pointer focus the page's own code never scrolls the panel, but the browser may
# (WebKit scrolls a partly visible select into view), so the test spies on the
# page's scroll calls instead of comparing the panel's `scrollLeft`.

PHONE_SIZE = {"width": 320, "height": 568}
PANEL_CONTROLS = [
    "lock-room",
    "help-mode-select",
    "reveal-letters-input",
    "reveal-words-input",
]

HOST_PANEL_STATE_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const fade = document.querySelector('[data-testid="host-panel-more"]');
  const fadeStyle = fade === null ? null : getComputedStyle(fade);
  return {
    fade: fadeStyle === null ? null : fadeStyle.visibility,
    fadeDisplay: fadeStyle === null ? null : fadeStyle.display,
    moreToTheRight: panel.scrollLeft + panel.clientWidth < panel.scrollWidth - 1,
  };
}
"""

# Records in `window.panelScrollCalls` each scroll call that the page makes on the
# host panel or on an element inside it: the scroll methods of `Element.prototype`
# (`scrollIntoViewIfNeeded` where the engine has it) and the `scrollLeft` setter. A
# scroll that the browser makes by itself does not go through them.
SCROLL_SPY_SCRIPT = r"""
() => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  window.panelScrollCalls = [];
  const record = (name, element) => {
    if (element === panel || panel.contains(element)) {
      window.panelScrollCalls.push(name);
    }
  };
  const methods = [
    'scrollIntoView', 'scrollIntoViewIfNeeded', 'scroll', 'scrollTo', 'scrollBy',
  ];
  for (const name of methods) {
    const originalMethod = Element.prototype[name];
    if (typeof originalMethod !== 'function') {
      continue;
    }
    Element.prototype[name] = function (...args) {
      record(name, this);
      return originalMethod.apply(this, args);
    };
  }
  const scrollLeft = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollLeft');
  Object.defineProperty(Element.prototype, 'scrollLeft', {
    configurable: true,
    enumerable: scrollLeft.enumerable,
    get: scrollLeft.get,
    set(value) {
      record('scrollLeft', this);
      scrollLeft.set.call(this, value);
    },
  });
}
"""

# Put the control in the panel so that it is fully shown ("full") or cut by the
# right edge of the panel ("partial"), without any focus change.
SCROLL_CONTROL_SCRIPT = r"""
([testId, mode]) => {
  const panel = document.querySelector('[data-testid="host-panel"]');
  const control = document.querySelector(`[data-testid="${testId}"]`);
  const panelBox = panel.getBoundingClientRect();
  const box = control.getBoundingClientRect();
  const left = box.left - panelBox.left + panel.scrollLeft;
  panel.scrollLeft = mode === 'full'
    ? left - 10
    : left + box.width * 0.6 - panel.clientWidth;
}
"""

# The outline band of the focused element: how much an ancestor scroll container
# cuts of its outer edge, and which other elements cover the band (sampled along
# the four sides and at the four corners with `elementFromPoint`).
FOCUS_BAND_SCRIPT = r"""
() => {
  const element = document.activeElement;
  const style = getComputedStyle(element);
  const width = parseFloat(style.outlineWidth);
  const offset = parseFloat(style.outlineOffset);
  const box = element.getBoundingClientRect();
  const grow = offset + width;
  const outer = {
    left: box.left - grow, top: box.top - grow,
    right: box.right + grow, bottom: box.bottom + grow,
  };
  const clip = {left: 0, top: 0, right: innerWidth, bottom: innerHeight};
  for (let node = element.parentElement; node; node = node.parentElement) {
    const nodeStyle = getComputedStyle(node);
    if (nodeStyle.overflowX === 'visible' && nodeStyle.overflowY === 'visible') {
      continue;
    }
    const rect = node.getBoundingClientRect();
    clip.left = Math.max(clip.left, rect.left + node.clientLeft);
    clip.top = Math.max(clip.top, rect.top + node.clientTop);
    clip.right = Math.min(clip.right, rect.left + node.clientLeft + node.clientWidth);
    clip.bottom = Math.min(clip.bottom, rect.top + node.clientTop + node.clientHeight);
  }
  const cut = {
    top: Math.max(clip.top - outer.top, 0),
    right: Math.max(outer.right - clip.right, 0),
    bottom: Math.max(outer.bottom - clip.bottom, 0),
    left: Math.max(clip.left - outer.left, 0),
  };
  const half = width / 2;
  const left = outer.left + half;
  const right = outer.right - half;
  const top = outer.top + half;
  const bottom = outer.bottom - half;
  const points = [];
  for (let x = left; x <= right; x += 2) {
    points.push([x, top]);
    points.push([x, bottom]);
  }
  for (let y = top; y <= bottom; y += 2) {
    points.push([left, y]);
    points.push([right, y]);
  }
  points.push([left, top], [right, top], [left, bottom], [right, bottom]);
  // An outline paints above the in-flow, non-positioned content around it, so
  // only a positioned element, a stacking context or a scroll container that
  // comes later in the document (browsers paint it as its own layer) on the way
  // up from `hit`, below the nearest ancestor shared with `element`, covers it.
  // Limits: the rule relies on `elementFromPoint`, so it cannot see a cover with
  // `pointer-events: none` (like the host-panel fade). It only counts later
  // positioned, stacking-context or scroll-container elements, which is sound
  // because the focused list is its own layer. It is not meant for reuse on
  // other targets as is.
  const isPaintedAbove = (hit, element) => {
    for (let node = hit; node && !node.contains(element); node = node.parentElement) {
      const nodeStyle = getComputedStyle(node);
      const positioned = nodeStyle.position !== 'static';
      const stacking = nodeStyle.zIndex !== 'auto' || nodeStyle.transform !== 'none'
        || Number(nodeStyle.opacity) < 1 || nodeStyle.isolation === 'isolate';
      const scroller = nodeStyle.overflowX !== 'visible'
        || nodeStyle.overflowY !== 'visible';
      const follows = Boolean(
        element.compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING
      );
      if (positioned || stacking || (scroller && follows)) {
        return true;
      }
    }
    return false;
  };
  const coveredBy = {};
  let covered = 0;
  for (const [x, y] of points) {
    const hit = document.elementFromPoint(x, y);
    const paintsOver = hit !== null && hit !== element
      && !element.contains(hit) && !hit.contains(element)
      && isPaintedAbove(hit, element);
    if (paintsOver) {
      covered += 1;
      const name = hit.getAttribute('data-testid') || hit.tagName;
      coveredBy[name] = (coveredBy[name] || 0) + 1;
    }
  }
  return {
    style: style.outlineStyle, width, cut, covered, coveredBy,
    sampled: points.length,
  };
}
"""

FEED_LIST_SELECTOR = '[data-testid="activity-feed"] ul'
FEED_LIST_TEST_ID = "feed list"
FEED_SIZES = [(360, 740), (568, 320), (1280, 720)]
FIRST_EXTRA_FEED_SEQ = 14
EXTRA_FEED_EVENTS = 40
FEED_OVERFLOWS_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  return list.scrollHeight > list.clientHeight;
}
"""


def fill_feed_until_it_scrolls(page: Page, mock: MockRoomSocket) -> None:
    """Send extra check results until the feed list overflows and scrolls.

    Args:
        page: The room page, already in state K2 (last event `seq` 13).
        mock: The mocked room socket that sends the extra feed events.
    """
    last_seq = FIRST_EXTRA_FEED_SEQ + EXTRA_FEED_EVENTS - 1
    for seq in range(FIRST_EXTRA_FEED_SEQ, last_seq + 1):
        result = CheckResult(
            seq=seq,
            player_id="p2",
            target=WordTarget(row=0, column=2, clue_index=0),
            correct=(),
            wrong=(),
        )
        mock.send(result.model_dump_json())
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-seq", str(last_seq)
    )
    overflows = page.evaluate(FEED_OVERFLOWS_SCRIPT, FEED_LIST_SELECTOR)
    assert overflows is True, "the feed list does not scroll after extra events"


def mobile_context(browser: Browser, touch: bool) -> BrowserContext:
    """A 320x568 context; `touch` adds a touch screen like a phone has."""
    is_mobile = touch and browser.browser_type.name != "firefox"
    return browser.new_context(
        viewport=PHONE_SIZE, has_touch=touch, is_mobile=is_mobile
    )


def visible_centre(page: Page, test_id: str) -> tuple[float, float] | None:
    """The centre of the part of a host-panel control that the panel shows."""
    box = page.get_by_test_id(test_id).bounding_box()
    panel = page.get_by_test_id("host-panel").bounding_box()
    assert box is not None
    assert panel is not None
    left = max(box["x"], panel["x"]) + 2
    right = min(box["x"] + box["width"], panel["x"] + panel["width"]) - 2
    if right <= left:
        return None
    return (left + right) / 2, box["y"] + box["height"] / 2


def focused_test_id(page: Page) -> str | None:
    """The `data-testid` of the focused element.

    Args:
        page: The page to inspect.

    Returns:
        The test id of the focused element, or None when nothing is focused or
        the focused element has no test id.
    """
    found = page.evaluate(ACTIVE_ELEMENT_SCRIPT)
    if found is None:
        return None
    return found["testId"]


@pytest.mark.parametrize("scroll_mode", ["partial", "full"])
@pytest.mark.parametrize("target", PANEL_CONTROLS)
@pytest.mark.parametrize("touch", [False, True], ids=["mouse", "touch"])
def test_ac2_a_pointer_focus_keeps_the_host_panel_fade_and_makes_no_scroll_call(
    browser: Browser,
    live_server: str,
    fx01_grid: Grid,
    touch: bool,
    target: str,
    scroll_mode: str,
) -> None:
    context = mobile_context(browser, touch)
    page = context.new_page()
    open_k2(page, live_server, fx01_grid)
    page.evaluate(SCROLL_CONTROL_SCRIPT, [target, scroll_mode])
    page.wait_for_timeout(SETTLE_MS)
    centre = visible_centre(page, target)
    if centre is None:
        context.close()
        pytest.skip(f"{target} has no visible part in mode {scroll_mode}")

    # The spy goes in after the set-up scroll above, which it must not record.
    page.evaluate(SCROLL_SPY_SCRIPT)
    # Raw coordinates: `.click()` scrolls the element into view and hides the bug.
    x, y = centre
    if touch:
        page.touchscreen.tap(x, y)
    else:
        page.mouse.click(x, y)
    page.wait_for_timeout(SETTLE_MS)
    scroll_calls = page.evaluate("window.panelScrollCalls")
    state = page.evaluate(HOST_PANEL_STATE_SCRIPT)
    context.close()

    assert scroll_calls == [], state
    if state["moreToTheRight"]:
        assert state["fade"] == "visible", state
        assert state["fadeDisplay"] != "none", state


@pytest.mark.parametrize("target", PANEL_CONTROLS)
def test_ac2_a_keyboard_focus_in_the_host_panel_hides_the_fade(
    browser: Browser, live_server: str, fx01_grid: Grid, target: str
) -> None:
    context = mobile_context(browser, touch=False)
    page = context.new_page()
    open_k2(page, live_server, fx01_grid)
    page.evaluate("document.activeElement.blur()")
    walker = Walker(page)
    walker.tab_to(target)
    page.wait_for_timeout(SETTLE_MS)
    state = page.evaluate(HOST_PANEL_STATE_SCRIPT)
    context.close()

    assert state["fade"] == "hidden", state


@pytest.mark.parametrize(("width", "height"), FEED_SIZES)
def test_ac2_the_activity_feed_focus_outline_is_fully_visible(
    browser: Browser,
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    context = browser.new_context(viewport={"width": width, "height": height})
    page = context.new_page()
    mock = open_k2(page, live_server, fx01_grid)
    fill_feed_until_it_scrolls(page, mock)
    page.evaluate("document.activeElement.blur()")
    reached = False
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        if focused_test_id(page) == "grid":
            page.keyboard.press("Escape")
        is_feed = page.evaluate(
            "selector => document.activeElement.matches(selector)",
            FEED_LIST_SELECTOR,
        )
        if is_feed:
            reached = True
            break
    if not reached and browser.browser_type.name != "chromium":
        # Engine guard: not every browser makes a scroll container focusable.
        context.close()
        pytest.skip(f"this browser does not make the {FEED_LIST_TEST_ID} a Tab stop")
    assert reached, f"Tab never reached the {FEED_LIST_TEST_ID} at {width}x{height}"
    page.wait_for_timeout(SETTLE_MS)
    band = page.evaluate(FOCUS_BAND_SCRIPT)
    context.close()

    assert band["style"] not in ("none", "auto"), band
    assert band["width"] >= MIN_OUTLINE_PX, band
    no_cut = {"top": 0, "right": 0, "bottom": 0, "left": 0}
    assert {side: round(px) for side, px in band["cut"].items()} == no_cut, band
    assert band["coveredBy"] == {}, band


# ---- AC-3: a keyboard player can leave the grid ---------------------------------


def open_host_room(page: Page, live_server: str, fx01_grid: Grid) -> MockRoomSocket:
    """A FX-01 room where `you` (`p1`) is host, so the host panel shows."""
    return open_room(page, live_server, fx01_grid)


def focus_grid_with_first_word(page: Page, walker: Walker) -> None:
    """Tab to the grid, then Tab again: `0,0,0` is selected on (1, 0)."""
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)


def test_ac3_tab_stays_on_the_grid_then_escape_tab_leaves_forward(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    expect(page.get_by_test_id("host-panel")).to_be_visible()
    add_sentinel(page)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect_focus_on_sentinel(page)
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, 1) is True
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)


def test_ac3_escape_then_shift_tab_leaves_backward(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")

    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    expect(grid_of(page)).not_to_be_focused()
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, -1) is True
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)


def test_ac3_coming_back_to_the_grid_with_shift_tab_works_both_ways(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    add_sentinel(page)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    expect_focus_on_sentinel(page)

    page.keyboard.press("Shift+Tab")
    expect_focus_on_grid(page)
    expect_word(page, "0,0,0")
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    expect(grid_of(page)).not_to_be_focused()
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, -1) is True
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)


def test_ac3_escape_tab_with_nothing_after_the_grid_leaves_the_page_content(
    page: Page, live_server: str, fx01_grid: Grid, browser_name: str
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)
    if browser_name == "firefox":
        # Firefox under automation has no toolbar to move the focus to, so it leaves
        # the focus on the grid. That the page released the Tab is checked in every
        # engine by test_ac3_a_tab_pressed_right_after_escape_is_not_cancelled.
        pytest.skip("Firefox under automation keeps the focus on the grid")
    wait_until(page, lambda: page.evaluate(FOCUS_LEFT_THE_PAGE_CONTENT_SCRIPT) is True)


@pytest.mark.parametrize(
    ("with_sentinel", "key"),
    [(True, "Tab"), (False, "Shift+Tab"), (False, "Tab")],
    ids=["forward_with_sentinel", "backward", "forward_without_sentinel"],
)
def test_ac3_a_tab_pressed_right_after_escape_is_not_cancelled(
    page: Page, live_server: str, fx01_grid: Grid, with_sentinel: bool, key: str
) -> None:
    open_host_room(page, live_server, fx01_grid)
    if with_sentinel:
        add_sentinel(page)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    watch_tab_keys(page)

    # Control: the Tab that selects the next word is cancelled (spec 009), so the
    # listener does tell a cancelled Tab from a released one.
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    page.keyboard.press("Escape")
    page.keyboard.press(key)

    assert tab_keydowns(page) == [
        {"shift": False, "defaultPrevented": True},
        {"shift": key == "Shift+Tab", "defaultPrevented": False},
    ]


def test_ac3_a_letter_after_escape_is_typed_and_the_release_ends(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)

    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(cell_at(page, 0, 1)).to_have_attribute("data-letter", "T")
    page.keyboard.press("Tab")

    expect_word(page, "0,2,0")
    expect_selected(page, 1, 2)
    expect_focus_on_grid(page)
    assert "edit_letter" in mock.types()


def test_ac3_any_other_key_ends_the_release(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    page.keyboard.press("ArrowRight")
    expect_selected(page, 1, 1)
    page.keyboard.press("Tab")

    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)


def test_ac3_losing_then_regaining_the_focus_ends_the_release(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    grid_of(page).evaluate("el => { el.blur(); el.focus(); }")
    expect_focus_on_grid(page)
    page.keyboard.press("Tab")

    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)


def test_ac3_escape_changes_nothing_else(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("t")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect_selected(page, 1, 1)
    page.wait_for_timeout(SETTLE_MS)
    sent_before = len(mock.received)

    page.keyboard.press("Escape")
    page.wait_for_timeout(SETTLE_MS)

    assert len(mock.received) == sent_before
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 1)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "true")
    expect_focus_on_grid(page)


def test_ac3_escape_with_nothing_selected_lets_tab_leave(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    add_sentinel(page)
    walker = Walker(page)
    walker.tab_to("grid")
    expect(grid_of(page)).to_have_attribute("data-word", "")

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect_focus_on_sentinel(page)
    expect(grid_of(page)).to_have_attribute("data-word", "")
    expect(grid_of(page)).not_to_have_attribute(
        "aria-activedescendant", re.compile(r".")
    )


def test_ac3_the_grid_is_described_by_the_hint_with_the_exit_method(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)

    expect(grid_of(page)).to_have_attribute("aria-describedby", "grid-hint")
    hint = page.get_by_test_id("grid-hint")
    expect(hint).to_have_attribute("id", "grid-hint")
    expect(hint).to_have_text(load_fr()["a11y.grid_hint"])
    expect(hint).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))


# ---- AC-4: the screen reader hears the clue, direction, length, position --------


def test_ac4_the_announcement_follows_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)

    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_word(page, "0,2,0")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 2")
    expect(announcement).to_have_attribute("role", "status")
    expect(announcement).to_have_attribute("aria-live", "polite")
    expect(announcement).to_have_attribute("aria-atomic", "true")
    expect(announcement).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))

    page.keyboard.press("ArrowDown")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 3")
    page.keyboard.press("ArrowUp")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 2")

    cell_at(page, 2, 2).click()
    expect_word(page, "2,0,0")
    expect(announcement).to_have_text("Sans contenu, horizontal, 4 lettres, lettre 2")

    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")


def test_ac4_choosing_the_same_selection_again_does_not_rewrite_the_region(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    expect_selected(page, 1, 0)
    word_before = grid_of(page).get_attribute("data-word")
    announcement.evaluate(OBSERVE_REWRITES_SCRIPT)

    # (1, 0) has only an across word, so tapping it again chooses the very same
    # selection. ArrowLeft cannot leave it (only clue cells lie to its left), and
    # Escape, remote events leave it alone too.
    cell_at(page, 1, 0).click()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Escape")
    mock.send(selection_frame("p2", 3, 1, Direction.DOWN))
    mock.send(letter_changed_frame(6, 3, 1, "A", "p2"))
    expect(cell_at(page, 3, 1)).to_have_attribute("data-letter", "A")
    page.wait_for_timeout(SETTLE_MS)

    expect_selected(page, 1, 0)
    assert grid_of(page).get_attribute("data-word") == word_before
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    assert page.evaluate("window.announcementRewrites") == 0

    # Control: a real move does rewrite the region, so the observer works.
    page.keyboard.press("ArrowRight")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")
    assert page.evaluate("window.announcementRewrites") > 0


@pytest.mark.parametrize("first_step", ["cell", "clue"])
def test_ac4_tapping_the_clue_of_the_selected_word_does_not_rewrite_the_region(
    page: Page, live_server: str, fx01_grid: Grid, first_step: str
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    passoire_clue = page.get_by_test_id("clue").filter(has_text="Passoire fine")
    # Spec 007: a clue tap selects the word's first unfilled cell. The grid is
    # empty, so for "Passoire fine" that is (1, 0), across: the cell tap below
    # and the clue tap choose the very same selection.
    if first_step == "cell":
        cell_at(page, 1, 0).click()
    else:
        passoire_clue.click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    expect_selected(page, 1, 0)
    expect_word(page, "0,0,0")
    announcement.evaluate(OBSERVE_REWRITES_SCRIPT)

    passoire_clue.click()
    page.wait_for_timeout(SETTLE_MS)

    expect_selected(page, 1, 0)
    expect_word(page, "0,0,0")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    assert page.evaluate("window.announcementRewrites") == 0

    # Control: a real move does rewrite the region, so the observer works.
    page.keyboard.press("ArrowRight")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")
    assert page.evaluate("window.announcementRewrites") > 0


def test_ac4_the_announcement_texts_come_from_fr_json() -> None:
    fr_json = load_fr()

    assert fr_json.get("a11y.direction.across") == "horizontal"
    assert fr_json.get("a11y.direction.down") == "vertical"
    assert fr_json.get("a11y.announcement") == NEW_KEYS["a11y.announcement"]


def test_ac4_the_region_exists_and_is_empty_with_nothing_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    announcement = announcement_of(page)
    expect(announcement).to_have_count(1)
    expect(announcement).to_have_text("")
    expect(announcement).to_have_attribute("role", "status")
    expect(announcement).to_have_attribute("aria-live", "polite")


def test_ac4_typing_a_letter_only_updates_the_position(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")

    page.keyboard.press("t")

    expect_selected(page, 1, 1)
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")


def test_ac4_the_announcement_is_visually_hidden_but_not_removed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    announcement = announcement_of(page)
    expect(announcement).not_to_have_text("")

    assert computed(announcement, "position") == "absolute"
    assert computed(announcement, "overflow") == "hidden"
    assert computed(announcement, "whiteSpace") == "nowrap"
    assert computed(announcement, "width") == "1px"
    assert computed(announcement, "height") == "1px"
    assert computed(announcement, "display") != "none"
    assert computed(announcement, "visibility") == "visible"


# ---- AC-5: grid, row and gridcell roles -----------------------------------------


def test_ac5_the_grid_has_rows_and_gridcells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(page.get_by_role("grid")).to_have_count(1)
    expect(page.get_by_role("gridcell")).to_have_count(25)
    structure = grid_of(page).evaluate(
        """grid => Array.from(grid.children).map(row => ({
            testId: row.getAttribute('data-testid'),
            role: row.getAttribute('role'),
            dataRow: row.getAttribute('data-row'),
            cells: Array.from(row.children).map(cell => ({
                testId: cell.getAttribute('data-testid'),
                role: cell.getAttribute('role'),
                row: cell.getAttribute('data-row'),
                column: cell.getAttribute('data-column'),
            })),
        }))"""
    )
    assert len(structure) == 5
    for row_number, row in enumerate(structure):
        assert row["testId"] == "grid-row"
        assert row["role"] == "row"
        assert row["dataRow"] == str(row_number)
        assert len(row["cells"]) == 5
        for column_number, cell in enumerate(row["cells"]):
            assert cell["testId"] == "cell"
            assert cell["role"] == "gridcell"
            assert cell["row"] == str(row_number)
            assert cell["column"] == str(column_number)


def test_ac5_the_grid_keeps_its_label_and_focusability(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(grid_of(page)).to_have_attribute("role", "grid")
    expect(grid_of(page)).to_have_attribute("aria-label", load_fr()["grid.label"])
    expect(grid_of(page)).to_have_attribute("tabindex", "0")


def test_ac5_every_cell_has_a_role_and_an_id(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    for row in range(5):
        for column in range(5):
            cell = cell_at(page, row, column)
            expect(cell).to_have_attribute("role", "gridcell")
            expect(cell).to_have_attribute("id", f"cell-{row}-{column}")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-testid", "cell")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-row", "2")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-column", "2")


def test_ac5_only_letter_cells_carry_aria_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(grid_of(page)).not_to_have_attribute(
        "aria-activedescendant", re.compile(r".")
    )
    letter_cells = page.locator('[data-testid="cell"][data-type="letter"]')
    expect(letter_cells).to_have_count(18)
    for index in range(18):
        expect(letter_cells.nth(index)).to_have_attribute("aria-selected", "false")
    other_cells = page.locator('[data-testid="cell"]:not([data-type="letter"])')
    expect(other_cells).to_have_count(7)
    for index in range(7):
        assert other_cells.nth(index).get_attribute("aria-selected") is None


def test_ac5_the_selection_is_exposed_by_activedescendant_and_aria_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    cell_at(page, 2, 2).click()

    expect(grid_of(page)).to_have_attribute("aria-activedescendant", "cell-2-2")
    expect(cell_at(page, 2, 2)).to_have_attribute("aria-selected", "true")
    others = page.locator(
        '[data-testid="cell"][data-type="letter"][aria-selected="false"]'
    )
    expect(others).to_have_count(17)
    assert page.locator('[aria-selected="true"]').count() == 1

    cell_at(page, 1, 0).click()
    expect(grid_of(page)).to_have_attribute("aria-activedescendant", "cell-1-0")


def test_ac5_clue_arrows_stay_hidden_from_assistive_technology(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    arrows = page.get_by_test_id("clue-arrow")
    expect(arrows).to_have_count(8)
    for index in range(8):
        expect(arrows.nth(index)).to_have_attribute("aria-hidden", "true")


def test_ac5_the_rows_do_not_change_the_layout_of_the_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    origin = cell_at(page, 0, 0).bounding_box()
    assert origin is not None
    width = origin["width"]
    height = origin["height"]
    assert abs(width - height) <= EPSILON
    for row in range(5):
        for column in range(5):
            box = cell_at(page, row, column).bounding_box()
            assert box is not None
            assert abs(box["width"] - width) <= EPSILON
            assert abs(box["height"] - height) <= EPSILON
            assert abs(box["x"] - (origin["x"] + column * width)) <= EPSILON
            assert abs(box["y"] - (origin["y"] + row * height)) <= EPSILON


# ---- AC-6: colour is not the only signal of a cursor ----------------------------


def initials_players() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Jean-Luc",
            1,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
        player_view(
            "p3",
            "Ana",
            2,
            selection=Selection(row=2, column=2, direction=Direction.ACROSS),
        ),
        player_view(
            "p4",
            "zoé",
            3,
            selection=Selection(row=1, column=0, direction=Direction.ACROSS),
        ),
    ]


def remote_initials(page: Page, row: int, column: int) -> Locator:
    selector = '[data-testid="remote-selection"] [data-testid="remote-initials"]'
    return cell_at(page, row, column).locator(selector)


def assert_initials_inside_the_cell(page: Page, row: int, column: int) -> None:
    cell_box = cell_at(page, row, column).bounding_box()
    assert cell_box is not None
    initials = remote_initials(page, row, column)
    for index in range(initials.count()):
        box = initials.nth(index).bounding_box()
        assert box is not None
        assert box["x"] >= cell_box["x"] - EPSILON
        assert box["y"] >= cell_box["y"] - EPSILON
        assert box["x"] + box["width"] <= cell_box["x"] + cell_box["width"] + EPSILON
        assert box["y"] + box["height"] <= cell_box["y"] + cell_box["height"] + EPSILON
        assert computed(initials.nth(index), "visibility") == "visible"


def corners_of(page: Page, row: int, column: int) -> list[str | None]:
    """The `data-corner` of each `remote-initials` of a cell, in document order."""
    corners: list[str | None] = []
    initials = remote_initials(page, row, column)
    for index in range(initials.count()):
        corners.append(initials.nth(index).get_attribute("data-corner"))
    return corners


def test_ac6_each_remote_cursor_carries_the_initials_of_its_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    shared = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(shared).to_have_count(2)
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])
    expect(cell_at(page, 1, 0).get_by_test_id("remote-selection")).to_have_count(1)
    expect(remote_initials(page, 1, 0)).to_have_text(["ZO"])
    assert_initials_inside_the_cell(page, 2, 2)
    assert_initials_inside_the_cell(page, 1, 0)


def test_ac6_data_corner_holds_the_name_of_the_corner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])
    assert corners_of(page, 2, 2) == ["top-left", "bottom-right"]
    assert corners_of(page, 1, 0) == ["top-left"]


def test_ac6_each_labelled_cursor_holds_exactly_one_initials_element(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, players=initials_players())

    cursors = page.get_by_test_id("remote-selection")
    expect(cursors).to_have_count(3)
    for index in range(3):
        initials = cursors.nth(index).get_by_test_id("remote-initials")
        expect(initials).to_have_count(1)


def test_ac6_the_initials_follow_a_moved_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, players=initials_players())
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN"])

    mock.send(selection_frame("p2", 3, 1, Direction.DOWN))

    expect(remote_initials(page, 3, 1)).to_have_text(["JL"])
    expect(remote_initials(page, 2, 2)).to_have_text(["AN"])
    assert_initials_inside_the_cell(page, 3, 1)
    assert corners_of(page, 3, 1) == ["top-left"]
    assert corners_of(page, 2, 2) == ["top-left"]


def test_ac6_two_players_with_the_same_initials_are_both_shown(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Anne",
            1,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
        player_view(
            "p3",
            "Anouk",
            2,
            selection=Selection(row=2, column=2, direction=Direction.ACROSS),
        ),
    ]

    open_room(page, live_server, fx01_grid, players=players)

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(2)
    expect(remote_initials(page, 2, 2)).to_have_text(["AN", "AN"])
    assert_initials_inside_the_cell(page, 2, 2)


def test_ac6_a_disconnected_player_has_no_cursor_and_no_initials(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view(
            "p2",
            "Bob",
            1,
            state=PlayerState.DISCONNECTED,
            selection=Selection(row=2, column=2, direction=Direction.DOWN),
        ),
    ]

    open_room(page, live_server, fx01_grid, players=players)

    expect(page.get_by_test_id("remote-initials")).to_have_count(0)


INITIALS_EXAMPLES = [
    ("Ana", "AN"),
    ("Jean-Luc", "JL"),
    ("marie ève", "MÈ"),
    ("R2", "R2"),
    ("Zoé", "ZO"),
    ("_Max_", "MA"),
    ("O" + chr(0x2019) + "Neil", "ON"),
]
MORE_INITIALS_EXAMPLES = [
    ("O'Neil", "ON"),
    ("Anne Marie", "AM"),
    ("a-b-c", "AB"),
    ("Élodie", "ÉL"),
    ("Jean Luc Paul", "JL"),
    ("\U0001d49cbc", "\U0001d49cB"),
]
INITIALS_CELLS: list[Cell] = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (0, 1),
    (2, 1),
]


def players_with_nicknames(nicknames: list[str]) -> list[PlayerView]:
    players = [player_view("p1", "Host", 0, is_host=True)]
    for index, nickname in enumerate(nicknames):
        row, column = INITIALS_CELLS[index]
        selection = Selection(row=row, column=column, direction=Direction.ACROSS)
        players.append(
            player_view(f"p{index + 2}", nickname, index % 8, selection=selection)
        )
    return players


@pytest.mark.parametrize(
    "examples",
    [INITIALS_EXAMPLES, MORE_INITIALS_EXAMPLES],
    ids=["spec_examples", "more_examples"],
)
def test_ac6_initials_follow_the_rule_of_initials_of(
    page: Page, live_server: str, fx01_grid: Grid, examples: list[tuple[str, str]]
) -> None:
    nicknames = [nickname for nickname, _ in examples]
    open_room(page, live_server, fx01_grid, players=players_with_nicknames(nicknames))

    for index, (nickname, initials) in enumerate(examples):
        row, column = INITIALS_CELLS[index]
        shown = remote_initials(page, row, column)
        expect(shown, f"initials of {nickname}").to_have_text([initials])


# ---- AC-7: locked letters differ by more than colour -----------------------------

K2_PLAYERS_SELECTION = Selection(row=2, column=2, direction=Direction.DOWN)


def k2_players() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1, selection=K2_PLAYERS_SELECTION),
        player_view("p3", "Cleo", 2, state=PlayerState.IDLE),
        player_view("p4", "Dan", 3, state=PlayerState.DISCONNECTED),
    ]


def k2_changes() -> ChangeList:
    return [
        (1, 0, {"letter": "T", "author": "p1", "locked": True}),
        (1, 1, {"letter": "X", "author": "p1", "wrong": True}),
        (1, 2, {"letter": "M", "author": "p2"}),
        (1, 3, {"letter": "I", "author": "p1"}),
    ]


def open_k2(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """State K2 of the spec: the room page with its feed, undo message and lock."""
    mock = open_room(
        page,
        live_server,
        grid,
        changes=k2_changes(),
        players=k2_players(),
        seq=10,
    )
    cell_at(page, 1, 3).click()
    joined = PlayerJoined(seq=11, player=player_view("p5", "Eve", 4))
    mock.send(joined.model_dump_json())
    result = CheckResult(
        seq=12,
        player_id="p2",
        target=WordTarget(row=0, column=2, clue_index=0),
        correct=(),
        wrong=(),
    )
    mock.send(result.model_dump_json())
    locked = SettingsChanged(
        seq=13,
        player_id="p1",
        settings=room_settings(locked=True),
        reveal_budget=RevealBudget(letters=5, words=1),
    )
    mock.send(locked.model_dump_json())
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "13")
    expect(page.get_by_test_id("feed-item")).to_have_count(3)
    nothing_to_undo = ErrorMessage(code=ErrorCode.NOTHING_TO_UNDO, message="nothing")
    mock.send(nothing_to_undo.model_dump_json())
    expect(page.get_by_test_id("undo-message")).to_be_visible()
    return mock


def test_ac7_a_locked_letter_is_bold_and_an_unlocked_one_is_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    locked = cell_at(page, 1, 0)
    expect(locked).to_have_attribute("data-locked", "true")
    assert int(computed(locked, "fontWeight")) >= BOLD_WEIGHT
    unlocked = cell_at(page, 1, 2)
    expect(unlocked).to_have_attribute("data-locked", "false")
    assert int(computed(unlocked, "fontWeight")) < BOLD_WEIGHT


def test_ac7_other_unlocked_letters_are_not_bold(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    for row, column in [(1, 1), (1, 3), (1, 4), (2, 2)]:
        weight = int(computed(cell_at(page, row, column), "fontWeight"))
        assert weight < BOLD_WEIGHT, (row, column)


ROSTER_ROWS = [
    ("p2", "actif", "normal", False),
    ("p3", "inactif", "italic", False),
    ("p4", "déconnecté", "italic", True),
]

NON_OPAQUE_SCRIPT = """
row => {
  const found = [];
  const nodes = [row, ...row.querySelectorAll('*')];
  for (let node = row.parentElement; node; node = node.parentElement) {
    nodes.push(node);
  }
  for (const node of nodes) {
    const opacity = getComputedStyle(node).opacity;
    if (opacity !== '1') {
      found.push([node.getAttribute('data-testid') || node.tagName, opacity]);
    }
  }
  return found;
}
"""


def roster_row(page: Page, player_id: str) -> Locator:
    selector = f'[data-testid="roster-player"][data-player-id="{player_id}"]'
    return page.locator(selector)


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
@pytest.mark.parametrize(("player_id", "state_text", "style", "struck"), ROSTER_ROWS)
def test_ac7_roster_rows_use_no_opacity(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    player_id: str,
    state_text: str,
    style: str,
    struck: bool,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)

    row = roster_row(page, player_id)
    expect(row).to_have_count(1)
    assert row.evaluate(NON_OPAQUE_SCRIPT) == []


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
@pytest.mark.parametrize(("player_id", "state_text", "style", "struck"), ROSTER_ROWS)
def test_ac7_roster_state_is_shown_by_font_style_and_line_through(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
    player_id: str,
    state_text: str,
    style: str,
    struck: bool,
) -> None:
    page = new_page(width, height)
    open_k2(page, live_server, fx01_grid)

    nickname = roster_row(page, player_id).get_by_test_id("roster-nickname")
    assert computed(nickname, "fontStyle") == style
    line = computed(nickname, "textDecorationLine")
    assert ("line-through" in line) is struck, line


@pytest.mark.parametrize("player_id", ["p2", "p3", "p4"])
def test_ac7_roster_state_is_written_in_the_row(
    page: Page, live_server: str, fx01_grid: Grid, player_id: str
) -> None:
    open_k2(page, live_server, fx01_grid)

    expected = {"p2": "actif", "p3": "inactif", "p4": "déconnecté"}[player_id]
    state = roster_row(page, player_id).get_by_test_id("roster-state")
    expect(state).to_have_text(expected)


# ---- States K1 to K7 for AC-8 and AC-9 -------------------------------------------


def all_right_changes() -> ChangeList:
    changes: ChangeList = []
    for position, letter in SOLUTION.items():
        update: dict[str, object] = {"letter": letter, "author": "p2"}
        changes.append((position[0], position[1], update))
    return changes


def open_k1(page: Page, live_server: str, grid: Grid) -> None:
    progress = json.dumps({"1": "started", "2": "finished"})
    script = f"localStorage.setItem('nock.progress', {json.dumps(progress)})"
    page.context.add_init_script(script)
    page.goto(f"{live_server}/")
    expect(page.get_by_test_id("catalogue-item").first).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )
    expect(page.get_by_test_id("catalogue-progress").first).to_be_visible()


def open_k3(page: Page, live_server: str, grid: Grid) -> None:
    mock = open_k2(page, live_server, grid)
    mock.send(letter_changed_frame(14, 1, 3, "O", "p2"))
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", "1")


def open_k4(page: Page, live_server: str, grid: Grid) -> None:
    mock = open_k2(page, live_server, grid)
    mock.routes[0].close(code=1011)
    expect(page.get_by_test_id("connection-banner")).to_be_visible(
        timeout=ROOM_TIMEOUT_MS
    )


def open_k5(page: Page, live_server: str, grid: Grid) -> None:
    open_nickname_form(page, live_server)
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana!")
    nickname_input.press("Enter")
    expect(page.get_by_test_id("nickname-error")).to_have_text(
        load_fr()["join.error.characters"]
    )


def open_k6_solved(page: Page, live_server: str, grid: Grid) -> None:
    open_room(page, live_server, grid, changes=all_right_changes(), solved=True)
    expect(page.get_by_test_id("grid-status")).to_have_attribute("data-state", "solved")


def open_k6_full_wrong(page: Page, live_server: str, grid: Grid) -> None:
    changes = all_right_changes()
    changes.append((4, 4, {"letter": "X", "author": "p2"}))
    open_room(page, live_server, grid, changes=changes)
    expect(page.get_by_test_id("grid-status")).to_have_attribute(
        "data-state", "full_wrong"
    )


def open_k7(page: Page, live_server: str, grid: Grid) -> None:
    page.goto(f"{live_server}/r/{UNKNOWN_CODE}")
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "not_found", timeout=ROOM_TIMEOUT_MS
    )


def open_k2_state(page: Page, live_server: str, grid: Grid) -> None:
    open_k2(page, live_server, grid)


STATE_OPENERS: dict[str, Callable[[Page, str, Grid], None]] = {
    "k1_catalogue": open_k1,
    "k2_room": open_k2_state,
    "k3_flash": open_k3,
    "k4_connection_banner": open_k4,
    "k5_nickname_error": open_k5,
    "k6_solved": open_k6_solved,
    "k6_full_wrong": open_k6_full_wrong,
    "k7_room_not_found": open_k7,
}
STATE_NAMES = list(STATE_OPENERS)


# ---- AC-8: text contrast ------------------------------------------------------------


def contrast_measurements(page: Page) -> list[dict[str, Any]]:
    """Return what the contrast scan measured for every text element it reaches."""
    measurements = page.evaluate(CONTRAST_SCAN_SCRIPT)
    assert isinstance(measurements, list)
    return measurements


def contrast_offenders(page: Page) -> list[dict[str, Any]]:
    """Return the scanned elements whose text contrast is under 4.5:1."""
    offenders: list[dict[str, Any]] = []
    for measurement in contrast_measurements(page):
        if measurement["ratio"] < 4.5:
            offenders.append(measurement)
    return offenders


@pytest.mark.parametrize("state", STATE_NAMES)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac8_text_contrast_is_at_least_4_5_to_1(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    STATE_OPENERS[state](page, live_server, fx01_grid)

    offenders = contrast_offenders(page)

    assert offenders == [], f"{state} at {width}x{height}: {offenders}"
    if state == "k3_flash":
        # The flash must not have ended during the scan.
        expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", "1")


# Who replaces my letter to make a cell flash in each colour 0 to 7: colour 0 is the
# flash of a player not in the roster, the others are the roster's colours.
FLASH_PLAYERS = {
    0: "p9",
    1: "p2",
    2: "p3",
    3: "p4",
    4: "p5",
    5: "p6",
    6: "p7",
    7: "p8",
}
FLASH_COLOURS = list(FLASH_PLAYERS)


@pytest.mark.parametrize("colour", FLASH_COLOURS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac8_text_contrast_holds_on_a_cell_flashing_in_every_colour(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    colour: int,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    mock = open_k2(page, live_server, fx01_grid)
    seq = 14
    for index, joining in enumerate(["p6", "p7", "p8"]):
        joined = PlayerJoined(
            seq=seq, player=player_view(joining, f"Joueur{index}", 5 + index)
        )
        mock.send(joined.model_dump_json())
        seq += 1
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq - 1))

    # Make (1, 3) mine again, then let the player of this colour replace it.
    mock.send(letter_changed_frame(seq, 1, 3, "I", "p1"))
    mock.send(letter_changed_frame(seq + 1, 1, 3, "O", FLASH_PLAYERS[colour]))
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", str(colour))

    offenders = contrast_offenders(page)

    assert offenders == [], f"flash colour {colour} at {width}x{height}: {offenders}"
    # The flash must not have ended during the scan.
    expect(cell_at(page, 1, 3)).to_have_attribute("data-flash", str(colour))


def test_ac8_the_dimmed_roster_rows_are_scanned_with_their_opacity(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    measurements = contrast_measurements(page)

    dimmed_rows = {"idle": "Cleo", "disconnected": "Dan"}
    for state, nickname in dimmed_rows.items():
        found: list[dict[str, Any]] = []
        for measurement in measurements:
            is_nickname = measurement["testid"] == "roster-nickname"
            if is_nickname and measurement["rowState"] == state:
                found.append(measurement)
        # The scan reached the nickname exactly once.
        assert [item["text"] for item in found] == [nickname], (state, found)
        assert found[0]["ratio"] >= 4.5, (state, found[0])


INJECT_PROBE_SCRIPT = """
opacity => {
  let probe = document.querySelector('[data-testid="opacity-probe"]');
  if (probe === null) {
    probe = document.createElement('p');
    probe.setAttribute('data-testid', 'opacity-probe');
    probe.textContent = 'Sonde opacité';
    document.body.appendChild(probe);
  }
  probe.style.color = '#5b6070';
  probe.style.backgroundColor = '#ffffff';
  probe.style.opacity = String(opacity);
}
"""


def probe_measurement(page: Page, opacity: float) -> dict[str, Any]:
    """Inject the probe text at an opacity and return what the scan measured."""
    page.evaluate(INJECT_PROBE_SCRIPT, opacity)
    found: list[dict[str, Any]] = []
    for measurement in contrast_measurements(page):
        if measurement["testid"] == "opacity-probe":
            found.append(measurement)
    assert len(found) == 1, found
    return found[0]


def test_ac8_the_contrast_scan_folds_in_opacity(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_k2(page, live_server, fx01_grid)

    # The same colours pass at full opacity and fail once the element is faded.
    opaque = probe_measurement(page, 1)
    opaque_flagged = opaque in contrast_offenders(page)
    faded = probe_measurement(page, 0.45)
    faded_flagged = faded in contrast_offenders(page)

    assert opaque["ratio"] >= 4.5, opaque
    assert not opaque_flagged
    assert faded["ratio"] < 4.5, faded
    assert faded["ratio"] < opaque["ratio"]
    assert faded_flagged


# ---- AC-9: the interface is in French, every string from fr.json -----------------


def template_pattern(template: str) -> re.Pattern[str]:
    """A `fr.json` value as a pattern: each `{name}` matches one or more characters."""
    literal_parts = re.split(r"\{[A-Za-z_]+\}", template)
    escaped_parts = [re.escape(part) for part in literal_parts]
    return re.compile(".+".join(escaped_parts), re.DOTALL)


def normalised(text: str) -> str:
    return " ".join(text.split())


def unknown_texts(texts: list[str], data: set[str]) -> list[str]:
    """The texts that are neither a `fr.json` value, nor test data, nor trivial."""
    patterns = [template_pattern(normalised(value)) for value in load_fr().values()]
    normalised_data = {normalised(item) for item in data}
    unknown: list[str] = []
    for text in texts:
        shown = normalised(text)
        if shown in normalised_data:
            continue
        if re.fullmatch(r"[0-9]+", shown) or re.fullmatch(r"[A-Z]", shown):
            continue
        if any(pattern.fullmatch(shown) for pattern in patterns):
            continue
        unknown.append(text)
    return unknown


def test_ac9_the_checker_flags_english_and_a_bare_salon() -> None:
    samples = ["Loading…", "Salon", "Check word"]

    assert unknown_texts(samples, set()) == samples


def test_ac9_the_checker_accepts_templates_filled_in() -> None:
    samples = ["Salon ABC123", "Grille n° 2", "Ana a rejoint le salon"]

    assert unknown_texts(samples, set()) == []


def test_ac9_the_checker_accepts_the_data_of_the_test() -> None:
    samples = ["Bob", "BO", "Artiste muet", "Z", "42", "ABC123"]
    data = {"Bob", "BO", "Artiste muet", "ABC123"}

    assert unknown_texts(samples, data) == []
    assert unknown_texts(["Bobby"], data) == ["Bobby"]


def test_ac9_the_new_keys_exist_with_their_values() -> None:
    fr_json = load_fr()

    for key, value in NEW_KEYS.items():
        assert fr_json.get(key) == value, key


NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve"]
INITIALS = ["AN", "BO", "CL", "DA", "EV"]


@pytest.mark.parametrize("state", STATE_NAMES)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=["desktop", "phone"])
def test_ac9_the_page_is_in_french_with_every_string_from_fr_json(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    state: str,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    STATE_OPENERS[state](page, live_server, fx01_grid)

    assert page.evaluate("document.documentElement.lang") == "fr"
    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    assert len(texts) > 0, "the language scan found no text at all"
    data = {
        *NICKNAMES,
        *INITIALS,
        *FX01_CLUES,
        ROOM_CODE,
        UNKNOWN_CODE,
        f"{live_server}/r/{ROOM_CODE}",
    }
    unknown = unknown_texts(texts, data)
    assert unknown == [], f"{state} at {width}x{height}: {unknown}"


# ---- AC-10: the in-app keyboard keys stay out of the Tab order --------------------

COARSE_POINTER_SCRIPT = """
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\\s/g, '') !== '(pointer:coarse)') {
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

KEY_MARKUP_SCRIPT = """
() => {
  const keys = [...document.querySelectorAll('[data-testid="key"]')];
  const reports = keys.map(key => ({
    name: key.getAttribute('data-key'),
    tag: key.tagName,
    type: key.getAttribute('type'),
    tabindex: key.getAttribute('tabindex'),
    tabIndex: key.tabIndex,
  }));
  const del = document.querySelector('[data-testid="key-delete"]');
  reports.push({
    name: 'delete',
    tag: del.tagName,
    type: del.getAttribute('type'),
    tabindex: del.getAttribute('tabindex'),
    tabIndex: del.tabIndex,
  });
  return reports;
}
"""

KEY_HIDING_SCRIPT = """
() => {
  const targets = [
    ...document.querySelectorAll('[data-testid="key"]'),
    document.querySelector('[data-testid="key-delete"]'),
  ];
  const offenders = [];
  for (const key of targets) {
    for (let node = key; node; node = node.parentElement) {
      const role = node.getAttribute('role');
      const hides = node.getAttribute('aria-hidden') === 'true'
        || node.hasAttribute('inert')
        || role === 'presentation' || role === 'none';
      if (hides) {
        offenders.push([key.getAttribute('data-key'), node.tagName]);
      }
    }
  }
  return offenders;
}
"""

FOCUSED_KIND_SCRIPT = """
() => {
  const element = document.activeElement;
  if (element === null) {
    return null;
  }
  return {
    testId: element.getAttribute('data-testid'),
    isBody: element === document.body,
  };
}
"""

LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page, as in spec 009's harness."""
    viewport = {"width": 360, "height": 740}
    if browser_name == "firefox":
        context = browser.new_context(viewport=viewport, has_touch=True)
    else:
        context = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    yield context.new_page()
    context.close()


def key_of(page: Page, letter: str) -> Locator:
    return page.locator(f'[data-testid="key"][data-key="{letter}"]')


def test_ac10_every_key_is_a_button_with_tabindex_minus_one(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    expect(touch_page.get_by_test_id("key")).to_have_count(26)

    reports = touch_page.evaluate(KEY_MARKUP_SCRIPT)

    assert sorted(report["name"] for report in reports) == sorted([*LETTERS, "delete"])
    for report in reports:
        assert report["tag"] == "BUTTON", report
        assert report["type"] == "button", report
        assert report["tabindex"] == "-1", report
        assert report["tabIndex"] == -1, report


def test_ac10_every_letter_key_has_the_letter_as_accessible_name(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    keyboard = touch_page.get_by_test_id("keyboard")

    for letter in LETTERS:
        by_name = keyboard.get_by_role("button", name=letter, exact=True)
        expect(by_name, letter).to_have_count(1)
        expect(by_name, letter).to_have_attribute("data-key", letter)
        expect(by_name, letter).to_have_attribute("data-testid", "key")


def test_ac10_the_delete_key_is_named_effacer(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    name = load_fr()["keyboard.delete"]
    assert name == "Effacer"
    by_name = touch_page.get_by_role("button", name=name, exact=True)
    expect(by_name).to_have_count(1)
    expect(by_name).to_have_attribute("data-testid", "key-delete")


def test_ac10_no_key_and_no_ancestor_hides_the_keys_from_assistive_technology(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    assert touch_page.evaluate(KEY_HIDING_SCRIPT) == []


def test_ac10_a_tap_on_a_key_keeps_the_focus_on_the_grid(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)

    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    key_of(touch_page, "T").tap()
    expect(cell_at(touch_page, 1, 0)).to_contain_text("T")
    expect_focus_on_grid(touch_page)
    touch_page.get_by_test_id("key-delete").tap()
    expect_focus_on_grid(touch_page)


@pytest.mark.parametrize("shift", [False, True], ids=["tab", "shift_tab"])
def test_ac10_tab_never_lands_on_a_key(
    touch_page: Page, live_server: str, fx01_grid: Grid, shift: bool
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    key = "Shift+Tab" if shift else "Tab"

    touch_page.keyboard.press("Escape")
    for _ in range(MAX_TABS + 1):
        touch_page.keyboard.press(key)
        focused = touch_page.evaluate(FOCUSED_KIND_SCRIPT)
        assert focused is not None
        assert focused["testId"] not in ("key", "key-delete"), focused
        if focused["testId"] == "grid" or focused["isBody"]:
            break


def test_ac10_a_key_focused_with_focus_shows_the_visible_focus(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(touch_page, live_server, fx01_grid)
    cell_at(touch_page, 1, 0).tap()
    expect_focus_on_grid(touch_page)
    touch_page.keyboard.press("ArrowRight")

    key_of(touch_page, "A").evaluate("element => element.focus()")

    outline = touch_page.evaluate(FOCUS_OUTLINE_SCRIPT)
    assert outline["style"] not in ("none", "auto"), outline
    assert outline["width"] >= MIN_OUTLINE_PX, outline
    assert outline["ratio"] >= MIN_FOCUS_CONTRAST, outline


# ---- AC-11: the "+N" rule for crowded cells -----------------------------------------

FX02_PATH = Path(__file__).parent / "fixtures" / "fx02.json"
CORNER_ORDER = ["top-left", "bottom-right", "top-right", "bottom-left"]
MIN_LABEL_FONT_PX = 7.0
CORNER_TOLERANCE_PX = 3.0
CURSOR_NICKNAMES = [
    "Jean-Luc",
    "Ana",
    "zoé",
    "Wanda Moreau",
    "Max",
    "Lou Ann",
    "Ned Orr",
]
CURSOR_INITIALS = ["JL", "AN", "ZO", "WM", "MA", "LA", "NO"]

LABELS_SCRIPT = """
cell => {
  const found = [];
  const selector = '[data-testid="remote-initials"], [data-testid="remote-overflow"]';
  for (const label of cell.querySelectorAll(selector)) {
    const box = label.getBoundingClientRect();
    const style = getComputedStyle(label);
    found.push({
      kind: label.getAttribute('data-testid'),
      text: label.textContent.trim(),
      corner: label.getAttribute('data-corner'),
      count: label.getAttribute('data-count'),
      ariaHidden: label.getAttribute('aria-hidden'),
      insideSelection: label.closest('[data-testid="remote-selection"]') !== null,
      fontSize: parseFloat(style.fontSize),
      visibility: style.visibility,
      left: box.left, top: box.top, right: box.right, bottom: box.bottom,
    });
  }
  return found;
}
"""


class Label(NamedTuple):
    """A `remote-initials` or `remote-overflow` element as the page draws it."""

    kind: str
    text: str
    corner: str | None
    count: str | None
    aria_hidden: str | None
    inside_selection: bool
    font_size: float
    visibility: str
    left: float
    top: float
    right: float
    bottom: float


def fx02_letter_cells() -> list[Cell]:
    """The letter cells of FX-02 in row-major order, read from the fixture."""
    grid = json.loads(FX02_PATH.read_text(encoding="utf-8"))
    cells = [cell for cell in grid["cells"] if cell["type"] == "letter"]
    cells.sort(key=lambda cell: (cell["row"], cell["column"]))
    return [(cell["row"], cell["column"]) for cell in cells]


def labels_of(page: Page, row: int, column: int) -> list[Label]:
    raw_labels = cell_at(page, row, column).evaluate(LABELS_SCRIPT)
    labels: list[Label] = []
    for raw in raw_labels:
        labels.append(
            Label(
                kind=raw["kind"],
                text=raw["text"],
                corner=raw["corner"],
                count=raw["count"],
                aria_hidden=raw["ariaHidden"],
                inside_selection=raw["insideSelection"],
                font_size=raw["fontSize"],
                visibility=raw["visibility"],
                left=raw["left"],
                top=raw["top"],
                right=raw["right"],
                bottom=raw["bottom"],
            )
        )
    return labels


def cell_side(page: Page, row: int, column: int) -> float:
    box = cell_at(page, row, column).bounding_box()
    assert box is not None
    return box["width"]


def assert_cell_tier(
    page: Page, row: int, column: int, at_least: float, below: float | None
) -> None:
    """Fail with the measured side when the cell is not in the expected tier."""
    side = cell_side(page, row, column)
    in_tier = side >= at_least and (below is None or side < below)
    assert in_tier, (
        f"cell ({row}, {column}) side is {side}px, expected at least {at_least}px"
        f" and below {below}px: the layout changed, revisit this example"
    )


def overlap(first: Label, second: Label) -> tuple[float, float]:
    width = min(first.right, second.right) - max(first.left, second.left)
    height = min(first.bottom, second.bottom) - max(first.top, second.top)
    return width, height


def corner_gap(label: Label, cell: FloatRect) -> tuple[float, float]:
    """Distance on both axes between the label's corner and the cell's corner."""
    corner = label.corner
    assert corner is not None
    if corner.endswith("left"):
        gap_x = label.left - cell["x"]
    else:
        gap_x = (cell["x"] + cell["width"]) - label.right
    if corner.startswith("top"):
        gap_y = label.top - cell["y"]
    else:
        gap_y = (cell["y"] + cell["height"]) - label.bottom
    return gap_x, gap_y


def assert_label_layout(page: Page, row: int, column: int) -> None:
    """Check the layout rules of "Initials on a crowded cell" for one cell."""
    cell_box = cell_at(page, row, column).bounding_box()
    assert cell_box is not None
    labels = labels_of(page, row, column)
    for label in labels:
        assert label.left >= cell_box["x"] - EPSILON, label
        assert label.top >= cell_box["y"] - EPSILON, label
        assert label.right <= cell_box["x"] + cell_box["width"] + EPSILON, label
        assert label.bottom <= cell_box["y"] + cell_box["height"] + EPSILON, label
        gap_x, gap_y = corner_gap(label, cell_box)
        assert abs(gap_x) <= CORNER_TOLERANCE_PX, (label, gap_x)
        assert abs(gap_y) <= CORNER_TOLERANCE_PX, (label, gap_y)
        assert label.font_size >= MIN_LABEL_FONT_PX, label
        assert label.visibility == "visible", label
    for first_index, first in enumerate(labels):
        for second in labels[first_index + 1 :]:
            width, height = overlap(first, second)
            assert width <= EPSILON or height <= EPSILON, (first, second)


def assert_slots(
    page: Page,
    row: int,
    column: int,
    initials: dict[str, str],
    overflow: tuple[str, int] | None,
) -> None:
    """Check the labels of a cell: initials by corner and the overflow label.

    Args:
        page: The room page.
        row: Row of the cell.
        column: Column of the cell.
        initials: Expected text of each `remote-initials`, by corner name.
        overflow: Expected corner and count `k` of the overflow label, or None
            when the cell holds no overflow label at all.
    """
    labels = labels_of(page, row, column)
    shown_initials: dict[str, str] = {}
    overflows: list[Label] = []
    for label in labels:
        if label.kind == "remote-initials":
            assert label.corner is not None, label
            shown_initials[label.corner] = label.text
        else:
            overflows.append(label)
    initials_count = len([label for label in labels if label.kind == "remote-initials"])
    assert initials_count == len(initials), labels
    assert shown_initials == initials, labels

    hidden_label = cell_at(page, row, column).get_by_test_id("remote-overflow-label")
    if overflow is None:
        assert overflows == [], labels
        expect(hidden_label).to_have_count(0)
        return
    corner, count = overflow
    assert len(overflows) == 1, labels
    only = overflows[0]
    assert only.corner == corner, only
    assert only.count == str(count), only
    assert only.text == f"+{count}", only
    assert only.aria_hidden == "true", only
    assert not only.inside_selection, only
    expect(hidden_label).to_have_count(1)
    expect(hidden_label).to_have_text(f"{count} autres joueurs")
    expect(hidden_label).to_have_class(re.compile(r"\bvisually-hidden\b"))


def cursors_on(cell: Cell, count: int, first_id: int = 2) -> list[PlayerView]:
    """The `p1` (`you`) player followed by `count` cursors all on `cell`."""
    players = [player_view("p1", "Ana", 0, is_host=True)]
    for index in range(count):
        selection = Selection(row=cell[0], column=cell[1], direction=Direction.ACROSS)
        players.append(
            player_view(
                f"p{first_id + index}",
                CURSOR_NICKNAMES[index],
                (index + 1) % 8,
                selection=selection,
            )
        )
    return players


def initials_by_corner(texts: list[str], corners: list[str]) -> dict[str, str]:
    return dict(zip(corners, texts, strict=True))


FX01_CROWDED: Cell = (2, 2)
# (cursors, initials shown, overflow count) on a cell of 44 px or more: 4 slots.
LARGE_CELL_CASES = [
    (1, 1, 0),
    (2, 2, 0),
    (3, 3, 0),
    (4, 4, 0),
    (5, 3, 2),
    (6, 3, 3),
    (7, 3, 4),
]
# On a cell from 20 px to 44 px: 2 slots.
SMALL_CELL_CASES = [(1, 1, 0), (2, 2, 0), (3, 1, 2), (4, 1, 3), (7, 1, 6)]


def expected_slots(
    initials_shown: int, overflow_count: int, slots: list[str], offset: int = 0
) -> tuple[dict[str, str], tuple[str, int] | None]:
    """Expected initials by corner and overflow for a case of the spec's tables."""
    texts = CURSOR_INITIALS[offset : offset + initials_shown]
    corners = slots[:initials_shown]
    overflow = None
    if overflow_count > 0:
        overflow = (slots[-1], overflow_count)
    return initials_by_corner(texts, corners), overflow


@pytest.mark.parametrize(("cursors", "shown", "hidden"), LARGE_CELL_CASES)
def test_ac11_a_large_cell_has_four_slots(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    cursors: int,
    shown: int,
    hidden: int,
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, cursors)
    open_room(page, live_server, fx01_grid, players=players)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(
        cursors
    )
    assert_cell_tier(page, 2, 2, 44, None)

    initials, overflow = expected_slots(shown, hidden, CORNER_ORDER)
    assert_slots(page, 2, 2, initials, overflow)
    assert_label_layout(page, 2, 2)


def test_ac11_the_players_without_a_label_hold_no_initials(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)

    selections = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(selections).to_have_count(5)
    with_initials = 0
    without_initials = 0
    for index in range(5):
        found = selections.nth(index).get_by_test_id("remote-initials").count()
        assert found in (0, 1), index
        if found == 1:
            with_initials += 1
        else:
            without_initials += 1
    assert (with_initials, without_initials) == (3, 2)
    expect(remote_initials(page, 2, 2)).to_have_text(["JL", "AN", "ZO"])


def test_ac11_a_cursor_leaving_a_crowded_cell_frees_a_slot_for_the_next(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    mock = open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-overflow")).to_have_count(1)

    mock.send(selection_frame("p6", 3, 1, Direction.ACROSS))

    expect(remote_initials(page, 2, 2)).to_have_count(4)
    initials = {
        "top-left": "JL",
        "bottom-right": "AN",
        "top-right": "ZO",
        "bottom-left": "WM",
    }
    assert_slots(page, 2, 2, initials, None)
    assert_label_layout(page, 2, 2)
    assert_slots(page, 3, 1, {"top-left": "MA"}, None)
    assert_label_layout(page, 3, 1)


def test_ac11_a_disconnected_player_is_not_counted(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    players[5] = players[5].model_copy(update={"state": PlayerState.DISCONNECTED})
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(4)
    initials = {
        "top-left": "JL",
        "bottom-right": "AN",
        "top-right": "ZO",
        "bottom-left": "WM",
    }
    assert_slots(page, 2, 2, initials, None)


@pytest.mark.parametrize(("cursors", "shown", "hidden"), SMALL_CELL_CASES)
def test_ac11_a_small_cell_has_two_slots(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx02_text: str,
    cursors: int,
    shown: int,
    hidden: int,
) -> None:
    page = new_page(360, 740)
    first_cell = fx02_letter_cells()[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    players = cursors_on(first_cell, cursors)
    open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 20, 44)

    initials, overflow = expected_slots(shown, hidden, CORNER_ORDER[:2])
    assert_slots(page, row, column, initials, overflow)
    assert_label_layout(page, row, column)


def test_ac11_a_small_cell_shows_two_initials_when_the_third_cursor_leaves(
    new_page: Callable[[int, int], Page], live_server: str, fx02_text: str
) -> None:
    page = new_page(360, 740)
    cells = fx02_letter_cells()
    first_cell = cells[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    # Jean-Luc, Ana and Wanda Moreau join in that order and all select the cell.
    players = cursors_on(first_cell, 3)
    players[3] = players[3].model_copy(update={"nickname": "Wanda Moreau"})
    mock = open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 20, 44)
    assert_slots(page, row, column, {"top-left": "JL"}, ("bottom-right", 2))
    assert_label_layout(page, row, column)

    other = cells[1]
    mock.send(selection_frame("p2", other[0], other[1], Direction.ACROSS))

    expect(remote_initials(page, row, column)).to_have_text(["AN", "WM"])
    assert_slots(page, row, column, {"top-left": "AN", "bottom-right": "WM"}, None)
    assert_label_layout(page, row, column)


@pytest.mark.parametrize("cursors", [1, 2, 3, 7])
def test_ac11_a_tiny_cell_has_one_slot(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx02_text: str,
    cursors: int,
) -> None:
    page = new_page(568, 320)
    first_cell = fx02_letter_cells()[0]
    fx02_grid = Grid.model_validate_json(fx02_text)
    players = cursors_on(first_cell, cursors)
    open_room(
        page,
        live_server,
        fx02_grid,
        players=players,
        cell_count=fx02_grid.width * fx02_grid.height,
    )
    row, column = first_cell
    assert_cell_tier(page, row, column, 0, 20)

    if cursors == 1:
        assert_slots(page, row, column, {"top-left": "JL"}, None)
    else:
        assert_slots(page, row, column, {}, ("top-left", cursors))


def test_ac11_the_overflow_label_passes_the_language_and_contrast_scans(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    players = cursors_on(FX01_CROWDED, 5)
    open_room(page, live_server, fx01_grid, players=players)
    assert_cell_tier(page, 2, 2, 44, None)
    expect(cell_at(page, 2, 2).get_by_test_id("remote-overflow")).to_have_count(1)

    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)
    assert isinstance(texts, list)
    assert "+2" in texts
    assert "2 autres joueurs" in texts
    data = {
        "Ana",
        *CURSOR_NICKNAMES,
        *CURSOR_INITIALS,
        *FX01_CLUES,
        ROOM_CODE,
        f"{live_server}/r/{ROOM_CODE}",
    }
    assert unknown_texts(texts, data) == []
    assert contrast_offenders(page) == []
