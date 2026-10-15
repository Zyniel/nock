"""Shared setup of the tests of spec 035: accessibility.

Pytest does not collect this module (its name does not start with `test_`). It
holds what more than one test file of spec 035 uses: the constants, the in-page
scripts, the helpers, the mocked room, the keyboard `Walker`, the scans. What only
one group of criteria uses stays in the test file of that group. The tests are in
these files, one per group of criteria, in the order of the criteria:

- `test_spec_035_ac01_ac02_keyboard_and_focus.py`: AC-1, AC-2.
- `test_spec_035_ac03_ac05_grid_exit_and_screen_reader.py`: AC-3, AC-4, AC-5.
- `test_spec_035_ac06_ac07_not_colour_alone.py`: AC-6, AC-7.
- `test_spec_035_ac08_ac09_contrast_and_french.py`: AC-8, AC-9.
- `test_spec_035_ac10_in_app_keys.py`: AC-10.
- `test_spec_035_ac11_crowded_cells.py`: AC-11.
- `test_spec_035_ac12_scrolling_lists.py`: AC-12.

Every test runs in a browser, except the static ones of AC-9 (the language
checker on its samples and the new `fr.json` keys). The keyboard walk (AC-1, AC-2)
uses the live server and the real WebSocket; AC-3 to AC-7 use a mocked socket;
AC-8 and AC-9 scan the rendered pages of the states K1 to K7 of the spec.

Fixtures: a fixture imported from here would make ruff report the import as unused
(F401) and the test parameter of the same name as a redefinition (F811). So each
test file defines the fixtures it needs (`fx01_grid`, `catalogue`, `new_page`) as
thin wrappers around `build_fx01_grid`, `build_reference_catalogue` and
`page_factory`, which are defined here. A file that has a test using `live_server`
needs the `catalogue` wrapper: it makes the live server serve the reference
catalogue CAT of spec 004.
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
    Locator,
    Page,
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
    Ping,
    PlayerJoined,
    PlayerState,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    Selection,
    SelectionMoved,
    SettingsChanged,
    Snapshot,
    WordTarget,
    grid_view,
    parse_client_message,
)

FR_JSON_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "i18n" / "fr.json"
ROOM_CODE = "ABC123"
SNAPSHOT_RESUME_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

WAIT_TIMEOUT_MS = 5000
ROOM_TIMEOUT_MS = 10_000
SETTLE_MS = 300
MAX_TABS = 60
EPSILON = 1.0

MIN_OUTLINE_PX = 2.0
MIN_FOCUS_CONTRAST = 3.0
MIN_TEXT_CONTRAST = 4.5

WINDOW_SIZES = [(1280, 720), (360, 740)]

Cell = tuple[int, int]
ChangeList = list[tuple[int, int, dict[str, object]]]
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

# The colour helpers, the contrast scan and the focus outline reader of the spec's
# "Test harness" are in tests/colour_contrast.js, which the spec 014 tests read
# too, so that both files always measure the same way. That file only declares
# them; each script below wraps it in a function for `page.evaluate` that returns
# one measurement.
COLOUR_CONTRAST_JS = (Path(__file__).parent / "colour_contrast.js").read_text(
    encoding="utf-8"
)
# Each measurement: tag, testid, rowState (the `data-state` of the roster row that
# holds the element, or None), removeFor, text, opacity and ratio.
CONTRAST_SCAN_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn scanTextContrast();\n}"
)
# The outline of the focused element: style, width (px) and ratio (against white).
FOCUS_OUTLINE_SCRIPT = (
    "() => {\n" + COLOUR_CONTRAST_JS + "\nreturn readFocusOutline();\n}"
)

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

# ---- Fixtures and small helpers -------------------------------------------------


def load_fr() -> dict[str, str]:
    """Return the French messages of the web client."""
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


def build_fx01_grid(fx01_text: str) -> Grid:
    """Parse the JSON text of FX-01 (the body of the `fx01_grid` fixtures)."""
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


def build_reference_catalogue(fx01_grid: Grid) -> Catalogue:
    """Return the reference catalogue CAT of spec 004."""
    entries = (
        make_entry(fx01_grid, 1, date(2026, 9, 1), 1, True),
        make_entry(fx01_grid, 2, date(2026, 10, 1), 2, True),
        make_entry(fx01_grid, 3, date(2026, 10, 1), 1, True),
        make_entry(fx01_grid, 4, date(2026, 10, 5), 3, False),
    )
    return Catalogue(entries=entries)


def page_factory(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Yield `new_page(width, height)`; close its contexts afterwards."""
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
    """The server side of the room socket of /r/ABC123, driven by the test.

    It records every frame the page sends, `ping` frames included. Like the real
    server (specs 017 and 039), it answers each `ping` with one `pong` on the
    route that sent it. Without the answer, the page takes 4 s without a frame
    from the server for a lost connection (spec 017, AC-4) and goes to
    `reconnecting`, so a step that takes longer than that on a slow engine would
    send the next frames to a dead socket.
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
  // that content never covers it. On the way up from `hit`, below the nearest
  // ancestor shared with `element`, the cover is any of these: a positioned
  // element or a stacking context, wherever it is in the document; or a scroll
  // container that comes after `element` in document order. Only a later scroll
  // container counts because the focused list is a scroll container too, and
  // browsers paint each one as its own layer, in document order.
  // Limits: the rule relies on `elementFromPoint`, so it cannot see a cover with
  // `pointer-events: none` (like the host-panel fade). A point outside the window
  // finds no element; `cut` covers that case. It is written for the scrolling
  // lists of AC-2 and AC-12, which are scroll containers, and is not meant for
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
FEED_SIZES = [(360, 740), (568, 320), (1280, 720)]
FIRST_EXTRA_FEED_SEQ = 14
EXTRA_FEED_EVENTS = 40
FEED_OVERFLOWS_SCRIPT = """
selector => {
  const list = document.querySelector(selector);
  return list.scrollHeight > list.clientHeight;
}
"""


def fill_feed_and_check_it_scrolls(page: Page, mock: MockRoomSocket) -> None:
    """Send 40 more check results, then fail unless the feed list scrolls.

    The count is fixed: the events have `seq` 14 to 53, so the feed holds 43
    items. Once the page shows `seq` 53, the list must be taller inside than its
    box (`scrollHeight` greater than `clientHeight`).

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


def remote_initials(page: Page, row: int, column: int) -> Locator:
    selector = '[data-testid="remote-selection"] [data-testid="remote-initials"]'
    return cell_at(page, row, column).locator(selector)


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
