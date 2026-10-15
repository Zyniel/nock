"""Spec 036 tests: the room page in a browser, and its mocked socket.

The phone profile of the spec (CPU throttling and the 4G network profile), the
in-page timing (the interactive mark, the keydown and cell-change probe), the page
actions that type letters, and the mocked room socket used by the edge cases of
AC-1 and of AC-5 and AC-6. Used by the tests of AC-1 to AC-6.

The shared setup of the other themes is in `spec036_harness`.
"""

from __future__ import annotations

import json
import re
import string
from collections.abc import Callable
from typing import NamedTuple

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    CDPSession,
    Locator,
    Page,
    WebSocketRoute,
    expect,
)
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from nock.grid import Grid
from nock.protocol import (
    HelpMode,
    Join,
    PlayerState,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
    parse_client_message,
)

# ---- Values of the spec --------------------------------------------------------------

INTERACTIVE_MARK = "nock:interactive"

CPU_THROTTLING_RATE = 4
FOUR_G_CONDITIONS: dict[str, bool | int] = {
    "offline": False,
    "latency": 170,
    "downloadThroughput": 1125000,
    "uploadThroughput": 187500,
}

FX02_CELL_COUNT = 221


# ---- Values of the test harness ------------------------------------------------------

MOCK_CODE = "ABC123"
MOCK_SOCKET_PATTERN = re.compile(r".*/api/rooms/ABC123/ws$")
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"

JOIN_TIMEOUT_MS = 20_000
ARRIVAL_TIMEOUT_MS = 5_000
PAGE_WAIT_MS = 5_000

Cell = tuple[int, int]


# ---- Keys the test presses -----------------------------------------------------------


class Keystroke(NamedTuple):
    """One key the test presses: the cell it fills and the letter shown there."""

    row: int
    column: int
    letter: str  # A to Z
    starts_word: bool  # the test taps this cell just before the key


# ---- The phone profile and the in-page timing ----------------------------------------


class PhonePage(NamedTuple):
    """A page of the spec's phone profile, in a browser context of its own."""

    context: BrowserContext
    page: Page
    session: CDPSession  # kept open: the throttling lasts as long as the session


def open_phone_page(browser: Browser, with_network: bool) -> PhonePage:
    """Open a page with spec 006's phone options, throttled before any goto.

    CPU throttling 4 always; the 4G network profile when `with_network`.
    """
    context = browser.new_context(
        viewport={"width": 360, "height": 740},
        has_touch=True,
        is_mobile=True,
        device_scale_factor=2,
    )
    try:
        page = context.new_page()
        session = context.new_cdp_session(page)
        session.send("Emulation.setCPUThrottlingRate", {"rate": CPU_THROTTLING_RATE})
        if with_network:
            session.send("Network.enable")
            session.send("Network.emulateNetworkConditions", FOUR_G_CONDITIONS)
    except BaseException:
        context.close()
        raise
    return PhonePage(context=context, page=page, session=session)


def auto_join_script(code: str, nickname: str) -> str:
    """The harness's init script: the page joins `code` as soon as its socket opens.

    It stores spec 010's room record and spec 012's nickname, unless the page
    already wrote them.
    """
    items = {
        f"nock.room.{code}": json.dumps({"grid": 1, "selection": None}),
        "nock.nickname": nickname,
    }
    return (
        "(() => {\n"
        f"  const items = {json.dumps(items)};\n"
        "  for (const [key, value] of Object.entries(items)) {\n"
        "    if (localStorage.getItem(key) === null) {\n"
        "      localStorage.setItem(key, value);\n"
        "    }\n"
        "  }\n"
        "})();\n"
    )


# Records the room page as it is when the page sets its interactive mark. The
# real mark is taken first, so the probe adds nothing to its startTime.
MARK_PROBE_SCRIPT = """
(() => {
  const states = [];
  window.__nockStatesAtMark = states;
  const originalMark = Performance.prototype.mark;
  Performance.prototype.mark = function (name, ...rest) {
    const entry = originalMark.call(this, name, ...rest);
    if (name === "nock:interactive") {
      const room = document.querySelector('[data-testid="room-page"]');
      states.push({
        status: room === null ? null : room.getAttribute("data-status"),
        grid: room === null ? null : room.getAttribute("data-grid"),
        cells: document.querySelectorAll('[data-testid="cell"]').length,
      });
    }
    return entry;
  };
})();
"""

HAS_MARK_SCRIPT = "() => performance.getEntriesByName('nock:interactive').length > 0"
MARK_TIMES_SCRIPT = (
    "() => performance.getEntriesByName('nock:interactive')"
    ".map((entry) => entry.startTime)"
)
STATES_AT_MARK_SCRIPT = "() => window.__nockStatesAtMark ?? null"

# The in-page timing of the harness: a capturing keydown listener on window, and
# a MutationObserver that records each change of a cell's data-letter (a cell
# element added to the page counts as a change too). Each observer call reads
# performance.now() once, before it looks at its records.
TYPING_PROBE_SCRIPT = """
(() => {
  const probe = { keydowns: [], changes: [] };
  window.__nockProbe = probe;
  window.addEventListener(
    "keydown",
    (event) => {
      probe.keydowns.push({ key: event.key, time: performance.now() });
    },
    { capture: true },
  );
  const isCell = (node) =>
    node.nodeType === Node.ELEMENT_NODE &&
    node.getAttribute("data-testid") === "cell";
  const keepCell = (element, time) => {
    probe.changes.push({
      row: element.getAttribute("data-row"),
      column: element.getAttribute("data-column"),
      letter: element.getAttribute("data-letter"),
      time,
    });
  };
  const observer = new MutationObserver((records) => {
    const time = performance.now();
    for (const record of records) {
      if (record.type === "attributes") {
        if (isCell(record.target)) {
          keepCell(record.target, time);
        }
        continue;
      }
      for (const node of record.addedNodes) {
        if (node.nodeType !== Node.ELEMENT_NODE) {
          continue;
        }
        if (isCell(node)) {
          keepCell(node, time);
        }
        for (const cell of node.querySelectorAll('[data-testid="cell"]')) {
          keepCell(cell, time);
        }
      }
    }
  });
  observer.observe(document, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["data-letter"],
  });
})();
"""

READ_PROBE_SCRIPT = """
() => {
  const probe = window.__nockProbe;
  if (probe === undefined) {
    return null;
  }
  return {
    timeOrigin: performance.timeOrigin,
    keydowns: probe.keydowns,
    changes: probe.changes,
  };
}
"""


class MarkState(NamedTuple):
    """The room page as it was when the page set its interactive mark."""

    status: str | None
    grid: str | None
    cells: int


FX02_AT_MARK = MarkState(status="joined", grid="13x17", cells=FX02_CELL_COUNT)


def states_at_mark(page: Page) -> list[MarkState]:
    """The room page at each interactive mark the page set."""
    raw = page.evaluate(STATES_AT_MARK_SCRIPT)
    assert raw is not None, "the mark probe did not run"
    states: list[MarkState] = []
    for item in raw:
        states.append(
            MarkState(
                status=item["status"], grid=item["grid"], cells=int(item["cells"])
            )
        )
    return states


def interactive_mark_times(page: Page) -> list[float]:
    """The startTime of every `nock:interactive` mark of the page, in ms."""
    raw = page.evaluate(MARK_TIMES_SCRIPT)
    times: list[float] = []
    for value in raw:
        times.append(float(value))
    return times


def wait_for_interactive_mark(page: Page, timeout_ms: int) -> None:
    """Wait until the page has set its interactive mark, else fail the test."""
    try:
        page.wait_for_function(HAS_MARK_SCRIPT, timeout=timeout_ms, polling=50)
    except PlaywrightTimeoutError:
        pytest.fail(f"the page set no {INTERACTIVE_MARK!r} mark within {timeout_ms} ms")


class KeyRecord(NamedTuple):
    """A keydown seen by the probe."""

    key: str
    time: float  # performance.now() in ms


class CellChange(NamedTuple):
    """A cell's data-letter seen changing by the probe."""

    row: int
    column: int
    letter: str  # "" for an empty cell
    time: float  # performance.now() in ms


class PageProbe(NamedTuple):
    """Everything the timing probe of one page recorded."""

    time_origin: float  # performance.timeOrigin, ms since the epoch
    keydowns: list[KeyRecord]
    changes: list[CellChange]


def read_probe(page: Page) -> PageProbe:
    """Read what the timing probe of `page` recorded so far."""
    raw = page.evaluate(READ_PROBE_SCRIPT)
    assert raw is not None, "the timing probe did not run"
    keydowns: list[KeyRecord] = []
    for item in raw["keydowns"]:
        keydowns.append(KeyRecord(key=str(item["key"]), time=float(item["time"])))
    changes: list[CellChange] = []
    for item in raw["changes"]:
        letter = item["letter"] if item["letter"] is not None else ""
        changes.append(
            CellChange(
                row=int(item["row"]),
                column=int(item["column"]),
                letter=str(letter),
                time=float(item["time"]),
            )
        )
    return PageProbe(
        time_origin=float(raw["timeOrigin"]), keydowns=keydowns, changes=changes
    )


def letter_keydowns(probe: PageProbe) -> list[KeyRecord]:
    """The keydowns of letter keys, in the order they happened."""
    found: list[KeyRecord] = []
    for record in probe.keydowns:
        if len(record.key) == 1 and record.key.upper() in string.ascii_uppercase:
            found.append(record)
    return found


def first_showing(
    changes: list[CellChange], keystroke: Keystroke, not_before: float
) -> float | None:
    """When the keystroke's cell first changed to its letter, from `not_before`."""
    for change in changes:
        if change.time < not_before:
            continue
        is_same_cell = (change.row, change.column) == (keystroke.row, keystroke.column)
        if is_same_cell and change.letter == keystroke.letter:
            return change.time
    return None


def matched_keydowns(probe: PageProbe, keystrokes: list[Keystroke]) -> list[KeyRecord]:
    """The keydown of each keystroke, checked against the keys the test pressed."""
    keydowns = letter_keydowns(probe)
    pressed = [keystroke.letter for keystroke in keystrokes]
    seen = [record.key.upper() for record in keydowns]
    assert seen == pressed, "the page did not see the keys the test pressed"
    return keydowns


def local_echo_times(
    probe: PageProbe, keystrokes: list[Keystroke]
) -> list[float | None]:
    """For each key: ms from its keydown to its cell first showing its letter.

    None when the cell never showed the letter after the keydown.
    """
    times: list[float | None] = []
    keydowns = matched_keydowns(probe, keystrokes)
    for keystroke, keydown in zip(keystrokes, keydowns, strict=True):
        shown_at = first_showing(probe.changes, keystroke, keydown.time)
        if shown_at is None:
            times.append(None)
        else:
            times.append(shown_at - keydown.time)
    return times


def propagation_times(
    ana: PageProbe, bob: PageProbe, keystrokes: list[Keystroke]
) -> list[float | None]:
    """For each of Ana's keys: ms from her keydown to Bob's cell showing the letter.

    The two pages are compared as `performance.timeOrigin + performance.now()`.
    None when Bob's cell never showed the letter after Ana's keydown.
    """
    offset = bob.time_origin - ana.time_origin
    bob_changes: list[CellChange] = []
    for change in bob.changes:
        bob_changes.append(
            CellChange(change.row, change.column, change.letter, change.time + offset)
        )
    times: list[float | None] = []
    keydowns = matched_keydowns(ana, keystrokes)
    for keystroke, keydown in zip(keystrokes, keydowns, strict=True):
        shown_at = first_showing(bob_changes, keystroke, keydown.time)
        if shown_at is None:
            times.append(None)
        else:
            times.append(shown_at - keydown.time)
    return times


def missing_keystrokes(
    keystrokes: list[Keystroke], times: list[float | None]
) -> list[Keystroke]:
    """The keystrokes whose letter was never seen."""
    missing: list[Keystroke] = []
    for keystroke, measured in zip(keystrokes, times, strict=True):
        if measured is None:
            missing.append(keystroke)
    return missing


def measured_times(times: list[float | None]) -> list[float]:
    """The times that were measured."""
    return [measured for measured in times if measured is not None]


# ---- Room page actions ---------------------------------------------------------------


def cell_at(page: Page, row: int, column: int) -> Locator:
    return page.locator(
        f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    )


def expect_fx02_room_shown(page: Page) -> None:
    """Wait until the page joined and shows FX-02's 221 cells."""
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined", timeout=JOIN_TIMEOUT_MS)
    expect(page.get_by_test_id("cell")).to_have_count(
        FX02_CELL_COUNT, timeout=JOIN_TIMEOUT_MS
    )


def tap_word_start(page: Page, row: int, column: int) -> None:
    """Tap the first cell of an across word and wait until it is selected, across."""
    cell_at(page, row, column).tap()
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", "across")


def type_keystrokes(page: Page, keystrokes: list[Keystroke], gap_ms: int) -> None:
    """Press each key `gap_ms` apart, tapping the first cell of each word first."""
    for keystroke in keystrokes:
        if keystroke.starts_word:
            tap_word_start(page, keystroke.row, keystroke.column)
        page.keyboard.press(keystroke.letter.lower())
        page.wait_for_timeout(gap_ms)


def expect_last_letters_shown(page: Page, keystrokes: list[Keystroke]) -> None:
    """Wait until each typed cell shows the last letter typed in it."""
    last_letters: dict[Cell, str] = {}
    for keystroke in keystrokes:
        last_letters[(keystroke.row, keystroke.column)] = keystroke.letter
    for (row, column), letter in last_letters.items():
        expect(cell_at(page, row, column)).to_have_attribute(
            "data-letter", letter, timeout=ARRIVAL_TIMEOUT_MS
        )


# ---- Mocked room socket (edge cases) -------------------------------------------------


class MockConnection:
    """One socket the page opened to /r/ABC123, served by the test."""

    def __init__(self, route: WebSocketRoute) -> None:
        self.route = route
        self.frames: list[str] = []
        route.on_message(self._on_message)

    def _on_message(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.frames.append(text)
        if json.loads(text) == {"type": "ping"}:
            self.route.send(Pong().model_dump_json())


class MockRoomServer:
    """The server side of /r/ABC123: every socket the page opens, in order."""

    def __init__(self) -> None:
        self.connections: list[MockConnection] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.connections.append(MockConnection(route))


def wait_until_page(page: Page, condition: Callable[[], bool], what: str) -> None:
    """Let Playwright run its callbacks until `condition` holds, else fail."""
    waited_ms = 0
    while not condition():
        if waited_ms >= PAGE_WAIT_MS:
            pytest.fail(f"timed out after {PAGE_WAIT_MS} ms waiting for {what}")
        page.wait_for_timeout(50)
        waited_ms += 50


def first_frame_of(page: Page, server: MockRoomServer, index: int) -> str:
    """Wait for socket number `index` (from 0) and return its first frame."""
    wait_until_page(page, lambda: len(server.connections) > index, "a new socket")
    connection = server.connections[index]
    wait_until_page(page, lambda: len(connection.frames) > 0, "a frame of the socket")
    return connection.frames[0]


def snapshot_frame(grid: Grid, seq: int) -> str:
    """A snapshot of `grid` for player p1, Ana, with the harness's token."""
    ana = PlayerView(
        player_id="p1",
        nickname="Ana",
        colour=0,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )
    budget = RevealBudget(letters=5, words=1)
    snapshot = Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_TOKEN,
        grid=grid_view(grid),
        players=(ana,),
        settings=RoomSettings(
            help_mode=HelpMode.FREE, reveal_budget=budget, locked=False
        ),
        reveal_budget=budget,
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_mock_room(page: Page, base_url: str, grid: Grid) -> MockRoomServer:
    """Open /r/ABC123 on a mocked socket; answer the automatic join at seq 5."""
    server = MockRoomServer()
    page.route_web_socket(MOCK_SOCKET_PATTERN, server.handle)
    page.add_init_script(auto_join_script(MOCK_CODE, "Ana"))
    page.goto(f"{base_url}/r/{MOCK_CODE}")
    join = parse_client_message(first_frame_of(page, server, 0))
    assert join == Join(nickname="Ana", resume_token=None)
    server.connections[0].route.send(snapshot_frame(grid, 5))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", "5")
    expect(room).to_have_attribute("data-status", "joined")
    return server


def expect_reconnection_after_close(
    page: Page, server: MockRoomServer, grid: Grid, close_code: int
) -> None:
    """Close the socket with `close_code`; the page must resume on a new socket."""
    server.connections[0].route.close(code=close_code)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "reconnecting")
    rejoin = parse_client_message(first_frame_of(page, server, 1))
    assert rejoin == Join(nickname="Ana", resume_token=SNAPSHOT_TOKEN)
    server.connections[1].route.send(snapshot_frame(grid, 7))
    expect(room).to_have_attribute("data-seq", "7")
    expect(room).to_have_attribute("data-status", "joined")
