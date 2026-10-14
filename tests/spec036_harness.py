"""Shared setup of the spec 036 tests: values, helpers, scripts and fixtures.

The `tests/test_spec_036_*.py` files share everything defined here. The name of
this module matches none of pytest's `python_files` patterns, so pytest does not
collect it; each test file imports the names it uses. A fixture defined here is
imported by name in every test file that uses it, because pytest looks for the
fixtures of a test among the names of the test module.

"The harness" in the comments of these files is the "Test harness" section of
the spec; this module is its Python code, with the helpers of the tests.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import random
import re
import socket
import string
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Coroutine, Generator, Iterator, Sequence
from pathlib import Path
from typing import NamedTuple

import pytest
import uvicorn
from fastapi.testclient import TestClient
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
from pydantic import ValidationError
from starlette.testclient import WebSocketTestSession

import nock.server
from nock.catalogue import Catalogue
from nock.grid import Arrow, ClueCell, Grid, LetterCell
from nock.hub import RoomConnection, RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorMessage,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    Ping,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RevealBudget,
    RoomSettings,
    ServerMessage,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import LogEntry, RoomConfig, RoomState
from nock.server import WEB_DIST_DIR, create_app
from nock.store import RoomStore

# ---- Values of the spec ---------------------------------------------------------

INTERACTIVE_MARK = "nock:interactive"
INTERACTIVE_BUDGET_MS = 2500.0
LOCAL_ECHO_BUDGET_MS = 50.0
PROPAGATION_BUDGET_MS = 300.0
RELAY_BUDGET_SECONDS = 0.100
STALL_BUDGET_SECONDS = 1.0

CPU_THROTTLING_RATE = 4
FOUR_G_CONDITIONS: dict[str, bool | int] = {
    "offline": False,
    "latency": 170,
    "downloadThroughput": 1125000,
    "uploadThroughput": 187500,
}

COLD_LOADS = 3
FX02_CELL_COUNT = 221
LOCAL_ECHO_KEYS = 40
LOCAL_ECHO_GAP_MS = 250
ANA_KEYS = 20
ANA_GAP_MS = 500

RELAY_CLIENT_NAMES = ("Ana", "Bob", "Cleo", "Dan", "Eve", "Finn", "Gus", "Hugo")
LOAD_CLIENT_NAMES = ("Cleo", "Dan", "Eve", "Finn", "Gus", "Hugo")
LOAD_SEED = 36
EDIT_INTERVAL_SECONDS = 0.5
START_OFFSET_SECONDS = 0.0625
EDITS_PER_RELAY_CLIENT = 20  # one every 500 ms for 10 seconds
RELAY_EDIT_COUNT = 160
RELAY_TIME_COUNT = 1120  # 160 edits times 7 other clients

STALLED_CODE = 4507
FLOOD_CODE = 1008
TOO_BIG_CODE = 1009
MAX_WS_FRAME_BYTES = 8192
OUTBOUND_LIMIT = 20  # AC-5's max_outbound_messages
INBOUND_LIMIT = 5  # AC-6's max_inbound_pending
DEFAULT_OUTBOUND_LIMIT = 1000
DEFAULT_INBOUND_LIMIT = 100
OVERSIZED_FRAME_BYTES = 9000  # AC-9's frame

HOST_VARIABLE = "NOCK_HOST"
PORT_VARIABLE = "NOCK_PORT"
DATABASE_VARIABLE = "NOCK_DATABASE"  # spec 018
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
SERVER_LOG_LEVEL = "info"  # server_config's default, which main() keeps

# Digits outside ASCII, which NOCK_PORT refuses (int() reads the first two as 8000;
# str.isdigit() takes all three).
FULLWIDTH_8000 = "\N{FULLWIDTH DIGIT EIGHT}" + "\N{FULLWIDTH DIGIT ZERO}" * 3
ARABIC_INDIC_8000 = "\N{ARABIC-INDIC DIGIT EIGHT}" + "\N{ARABIC-INDIC DIGIT ZERO}" * 3
SUPERSCRIPT_TWO = "\N{SUPERSCRIPT TWO}"

# ---- Values of the test harness ---------------------------------------------------

MOCK_CODE = "ABC123"
MOCK_SOCKET_PATTERN = re.compile(r".*/api/rooms/ABC123/ws$")
SNAPSHOT_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
MISSING_BUILD_MESSAGE = "web/dist is missing: run npm --prefix web run build"

JOIN_TIMEOUT_MS = 20_000
MARK_TIMEOUT_MS = 20_000
ARRIVAL_TIMEOUT_MS = 5_000
PAGE_WAIT_MS = 5_000
SETTLE_MS = 500
LOAD_WARM_UP_MS = 1_000
LOAD_PLAN_EDITS = 80  # more than AC-4 ever sends: its load stops after Ana's keys

WAIT_SECONDS = 10.0
SETTLE_SECONDS = 0.3
POLL_SECONDS = 0.01
SENDER_LEAD_SECONDS = 0.2
SENDER_LIMIT_SECONDS = 60.0
SCENARIO_LIMIT_SECONDS = 60.0
BLOCK_LIMIT_SECONDS = 10.0
SERVER_START_SECONDS = 10.0  # also how long AC-8 and AC-9 poll GET /

DATABASE_FILE_NAME = "nock.sqlite3"
LOG_FILE_NAME = "python-m-nock.log"
REQUEST_TIMEOUT_SECONDS = 2.0
START_POLL_SECONDS = 0.05
PROCESS_STOP_SECONDS = 10.0
PROCESS_EXIT_LIMIT_SECONDS = 30.0

Cell = tuple[int, int]

# ---- Fixtures -------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def default_registry() -> Iterator[RoomRegistry]:
    """A registry with `RoomConfig()` defaults: spec 037's 20 edits a second apply."""
    registry = RoomRegistry(config=RoomConfig())
    yield registry
    registry.close()


# ---- Measurements -----------------------------------------------------------------


def percentile_95(samples: Sequence[float]) -> float:
    """The p95 of the spec: the ceil(0.95 * n)-th smallest of n samples."""
    ordered = sorted(samples)
    rank = (95 * len(ordered) + 99) // 100  # ceil(0.95 * n), in whole numbers
    return ordered[rank - 1]


# ---- Grids ------------------------------------------------------------------------


def letter_cells(grid: Grid) -> list[Cell]:
    """The letter cells of `grid`, in row-major order."""
    positions: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


class Word(NamedTuple):
    """An across word: its cells in reading order and its answer."""

    cells: list[Cell]
    answer: str


def across_words(grid: Grid) -> list[Word]:
    """The across words of `grid`, ordered by their first cell (row-major)."""
    words: list[Word] = []
    for cell in grid.cells:
        if not isinstance(cell, ClueCell):
            continue
        for index, clue in enumerate(cell.clues):
            if clue.arrow in (Arrow.RIGHT, Arrow.DOWN_THEN_RIGHT):
                cells = grid.word_cells(cell.row, cell.column, index)
                words.append(Word(cells=cells, answer=clue.answer))
    words.sort(key=lambda word: word.cells[0])
    return words


class Keystroke(NamedTuple):
    """One key the test presses: the cell it fills and the letter shown there."""

    row: int
    column: int
    letter: str  # A to Z
    starts_word: bool  # the test taps this cell just before the key


def local_echo_keystrokes(grid: Grid) -> list[Keystroke]:
    """AC-2's 40 keys: the answers of the across words, word after word."""
    keystrokes: list[Keystroke] = []
    for word in across_words(grid):
        for index, (row, column) in enumerate(word.cells):
            if len(keystrokes) == LOCAL_ECHO_KEYS:
                return keystrokes
            keystrokes.append(Keystroke(row, column, word.answer[index], index == 0))
    return keystrokes


def ana_words(grid: Grid) -> list[Word]:
    """Ana's two across words in AC-4: the two longest, in row-major order.

    Among words of the same length, the first in row-major order is taken.
    """
    longest_first = sorted(
        across_words(grid), key=lambda word: len(word.cells), reverse=True
    )
    chosen = longest_first[:2]
    chosen.sort(key=lambda word: word.cells[0])
    return chosen


def next_letter(letter: str) -> str:
    """The letter after `letter` in the alphabet, Z giving A."""
    index = string.ascii_uppercase.index(letter)
    return string.ascii_uppercase[(index + 1) % len(string.ascii_uppercase)]


def ana_keystrokes(words: list[Word]) -> list[Keystroke]:
    """AC-4's 20 keys on Ana's words: their answers, then other letters.

    The second pass types the same cells again with the next letter of the
    alphabet, so every key changes its cell.
    """
    keystrokes: list[Keystroke] = []
    for pass_number in range(2):
        for word in words:
            for index, (row, column) in enumerate(word.cells):
                if len(keystrokes) == ANA_KEYS:
                    return keystrokes
                letter = word.answer[index]
                if pass_number == 1:
                    letter = next_letter(letter)
                keystrokes.append(Keystroke(row, column, letter, index == 0))
    return keystrokes


# ---- The phone profile and the in-page timing -------------------------------------


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


# ---- Room page actions ------------------------------------------------------------


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


# ---- Simulated players (spec 015's Python clients) --------------------------------


class SimulatedClient:
    """A simulated player: one TestClient socket and a reader thread.

    The reader keeps each message with the `time.monotonic()` taken as soon as
    `receive_text` returned, before parsing. Each edit is kept with the
    `time.monotonic()` taken just before its `send_text`.
    """

    def __init__(self, websocket: WebSocketTestSession, name: str) -> None:
        self.name = name
        self._websocket = websocket
        self._arrived = threading.Condition()
        self._received: list[tuple[float, ServerMessage]] = []
        self._sent: list[tuple[float, EditLetter]] = []
        self._failures: list[str] = []
        reader = threading.Thread(target=self._read, daemon=True)
        reader.start()

    def _read(self) -> None:
        while True:
            try:
                text = self._websocket.receive_text()
            except BaseException:  # the socket closed at the end of the test
                return
            received_at = time.monotonic()
            try:
                message = parse_server_message(text)
            except ValueError as error:
                with self._arrived:
                    self._failures.append(f"{self.name} got {text!r}: {error}")
                    self._arrived.notify_all()
                continue
            with self._arrived:
                self._received.append((received_at, message))
                self._arrived.notify_all()

    def join(self) -> None:
        """Join with this client's name and wait for the snapshot."""
        join = Join(nickname=self.name, resume_token=None)
        self._websocket.send_text(join.model_dump_json())
        with self._arrived:
            has_snapshot = self._arrived.wait_for(
                lambda: len(self._received) > 0 or len(self._failures) > 0,
                WAIT_SECONDS,
            )
        self.check_failures()
        assert has_snapshot, f"{self.name} got no snapshot"
        assert isinstance(self.messages()[0], Snapshot), self.messages()[0]

    def send_edit(self, edit: EditLetter) -> None:
        """Send one edit, keeping the time taken just before it left."""
        frame = edit.model_dump_json()
        sent_at = time.monotonic()
        self._websocket.send_text(frame)
        with self._arrived:
            self._sent.append((sent_at, edit))

    def check_failures(self) -> None:
        """Fail the test when the reader got a message it could not parse."""
        with self._arrived:
            failures = list(self._failures)
        if failures:
            pytest.fail(failures[0])

    def timed_messages(self) -> list[tuple[float, ServerMessage]]:
        with self._arrived:
            return list(self._received)

    def messages(self) -> list[ServerMessage]:
        return [message for _, message in self.timed_messages()]

    def sent(self) -> list[tuple[float, EditLetter]]:
        with self._arrived:
            return list(self._sent)

    def you(self) -> str:
        first = self.messages()[0]
        assert isinstance(first, Snapshot), first
        return first.you

    def errors(self) -> list[ErrorMessage]:
        found: list[ErrorMessage] = []
        for message in self.messages():
            if isinstance(message, ErrorMessage):
                found.append(message)
        return found

    def letter_changes(self) -> list[LetterChanged]:
        found: list[LetterChanged] = []
        for message in self.messages():
            if isinstance(message, LetterChanged):
                found.append(message)
        return found

    def own_letter_changes(self) -> list[LetterChanged]:
        """The letter_changed events of this client's own edits: its answers."""
        you = self.you()
        found: list[LetterChanged] = []
        for event in self.letter_changes():
            if event.player_id == you:
                found.append(event)
        return found

    def answer_count(self) -> int:
        """How many of this client's edits got an answer, accepted or refused."""
        return len(self.own_letter_changes()) + len(self.errors())

    def letter_change_times(self) -> dict[int, float]:
        """When each letter_changed arrived, by seq."""
        times: dict[int, float] = {}
        for received_at, message in self.timed_messages():
            if isinstance(message, LetterChanged):
                times[message.seq] = received_at
        return times


def join_simulated_clients(
    stack: contextlib.ExitStack,
    test_client: TestClient,
    code: str,
    names: Sequence[str],
) -> list[SimulatedClient]:
    """Open one socket per name in `stack` and join with each, one after the other."""
    clients: list[SimulatedClient] = []
    for name in names:
        websocket = stack.enter_context(
            test_client.websocket_connect(f"/api/rooms/{code}/ws")
        )
        simulated = SimulatedClient(websocket, name)
        simulated.join()
        clients.append(simulated)
    return clients


def random_edit_plans(
    rng: random.Random, cells: list[Cell], client_count: int, edit_count: int
) -> list[list[EditLetter]]:
    """One plan per client: `edit_count` random letters on random cells of `cells`."""
    plans: list[list[EditLetter]] = []
    for _ in range(client_count):
        plan: list[EditLetter] = []
        for _ in range(edit_count):
            row, column = rng.choice(cells)
            letter = rng.choice(string.ascii_uppercase)
            plan.append(EditLetter(row=row, column=column, letter=letter))
        plans.append(plan)
    return plans


class TypingLoad:
    """Simulated players typing one edit every 500 ms, starting 62.5 ms apart.

    Each client sends from a thread of its own, on an absolute schedule, until
    its plan ends or the load is stopped.
    """

    def __init__(
        self, clients: list[SimulatedClient], plans: list[list[EditLetter]]
    ) -> None:
        self._clients = clients
        self._plans = plans
        self._stop = threading.Event()
        self._problems: list[str] = []
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        start_at = time.monotonic() + SENDER_LEAD_SECONDS
        pairs = zip(self._clients, self._plans, strict=True)
        for index, (client, plan) in enumerate(pairs):
            first_send_at = start_at + index * START_OFFSET_SECONDS
            thread = threading.Thread(
                target=self._send_plan, args=(client, plan, first_send_at), daemon=True
            )
            self._threads.append(thread)
            thread.start()

    def _send_plan(
        self, client: SimulatedClient, plan: list[EditLetter], first_send_at: float
    ) -> None:
        try:
            for index, edit in enumerate(plan):
                delay = first_send_at + index * EDIT_INTERVAL_SECONDS - time.monotonic()
                if delay > 0 and self._stop.wait(delay):
                    return
                if self._stop.is_set():
                    return
                client.send_edit(edit)
        except Exception as error:  # reported by the test thread
            self._problems.append(f"{client.name}: {error!r}")

    def stop(self) -> None:
        self._stop.set()

    def wait_until_sent(self) -> list[str]:
        """Wait for every sender to end; return the problems they met."""
        for thread in self._threads:
            thread.join(timeout=SENDER_LIMIT_SECONDS)
            assert not thread.is_alive(), "a sender thread did not end"
        return list(self._problems)


def wait_for(
    condition: Callable[[], bool], what: str, timeout: float = WAIT_SECONDS
) -> None:
    """Poll `condition` from the test thread until it holds, else fail the test."""
    deadline = time.monotonic() + timeout
    while not condition():
        if time.monotonic() >= deadline:
            pytest.fail(f"timed out after {timeout}s waiting for {what}")
        time.sleep(POLL_SECONDS)


def every_edit_answered(clients: list[SimulatedClient]) -> bool:
    """Whether every edit sent so far got its answer."""
    for client in clients:
        client.check_failures()
        if client.answer_count() < len(client.sent()):
            return False
    return True


def every_seq_received(clients: list[SimulatedClient], seqs: set[int]) -> bool:
    """Whether every client received a letter_changed for each of `seqs`."""
    for client in clients:
        client.check_failures()
        if not seqs <= set(client.letter_change_times()):
            return False
    return True


def relay_times(clients: list[SimulatedClient]) -> list[float]:
    """For each edit and each other client: its letter_changed's receipt minus its send.

    The seq of an edit is the one of its sender's own answer.
    """
    receipts: dict[str, dict[int, float]] = {}
    for client in clients:
        receipts[client.name] = client.letter_change_times()
    times: list[float] = []
    for sender in clients:
        answers = sender.own_letter_changes()
        for (sent_at, _edit), answer in zip(sender.sent(), answers, strict=True):
            for receiver in clients:
                if receiver is sender:
                    continue
                times.append(receipts[receiver.name][answer.seq] - sent_at)
    return times


# ---- Hub scenarios (AC-5, AC-6) ---------------------------------------------------


class FakeSocket:
    """The socket of a hub connection, as its writer sees it: keeps what it gets."""

    def __init__(self) -> None:
        self.texts: list[str] = []
        self.close_codes: list[int] = []

    async def send_text(self, text: str) -> None:
        self.texts.append(text)

    async def close(self, code: int) -> None:
        self.close_codes.append(code)

    def messages(self) -> list[ServerMessage]:
        """Every text received so far, parsed."""
        parsed: list[ServerMessage] = []
        for text in self.texts:
            parsed.append(parse_server_message(text))
        return parsed


class StuckSocket(FakeSocket):
    """The socket of a client that never reads: `send_text` never completes."""

    def __init__(self) -> None:
        super().__init__()
        self._never_set = asyncio.Event()

    async def send_text(self, text: str) -> None:
        self.texts.append(text)
        await self._never_set.wait()


class HubClient(NamedTuple):
    """A connection of a hub test, its socket and the task of its writer."""

    connection: RoomConnection
    socket: FakeSocket
    writer: asyncio.Task[None]


def open_hub_client(
    registry: RoomRegistry, code: str, fake_socket: FakeSocket
) -> HubClient:
    """Connect to room `code` and start the connection's writer on `fake_socket`.

    Called from the scenario's event loop, which then owns the connection.
    """
    connection = registry.connect(code)
    assert connection is not None, f"room {code} is unknown"
    writer = asyncio.create_task(
        connection.run_writer(fake_socket.send_text, fake_socket.close)
    )
    return HubClient(connection=connection, socket=fake_socket, writer=writer)


async def wait_until_async(
    condition: Callable[[], bool], what: str, timeout: float = WAIT_SECONDS
) -> None:
    """Poll `condition` on the running loop until it holds, else fail the test."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while not condition():
        if loop.time() >= deadline:
            pytest.fail(f"timed out after {timeout}s waiting for {what}")
        await asyncio.sleep(POLL_SECONDS)


async def join_hub_client(client: HubClient, nickname: str) -> Snapshot:
    """Send a join and wait for the snapshot that answers it."""
    client.connection.submit(Join(nickname=nickname, resume_token=None))
    await wait_until_async(
        lambda: len(client.socket.texts) > 0, f"the snapshot of {nickname}"
    )
    first = parse_server_message(client.socket.texts[0])
    assert isinstance(first, Snapshot), first
    return first


def run_hub_scenario[ResultT](scenario: Coroutine[object, object, ResultT]) -> ResultT:
    """Run `scenario` with asyncio.run in a thread of its own; return its result.

    A failure inside the scenario fails the test.
    """
    results: list[ResultT] = []
    errors: list[BaseException] = []

    def run() -> None:
        try:
            results.append(asyncio.run(scenario))
        except BaseException as error:  # handed over to the test thread
            errors.append(error)

    thread = threading.Thread(target=run, name="hub-scenario", daemon=True)
    thread.start()
    thread.join(timeout=SCENARIO_LIMIT_SECONDS)
    if thread.is_alive():
        pytest.fail(f"the hub scenario did not end within {SCENARIO_LIMIT_SECONDS}s")
    if errors:
        raise errors[0]
    return results[0]


class BlockingStore(RoomStore):
    """The spec's blocking store: `append` waits on an event while a flag is set."""

    def __init__(self) -> None:
        super().__init__(":memory:")
        self.is_blocking = False
        self.released = threading.Event()
        self.append_waiting = threading.Event()

    def append(self, code: str, entries: Sequence[LogEntry]) -> None:
        if self.is_blocking:
            self.append_waiting.set()
            # Bounded, so that a failing test never hangs the engine thread.
            self.released.wait(BLOCK_LIMIT_SECONDS)
        super().append(code, entries)

    def block(self) -> None:
        """Make the next appends wait until `release`."""
        self.released.clear()
        self.append_waiting.clear()
        self.is_blocking = True

    def release(self) -> None:
        """Let the waiting append, and every later one, go through."""
        self.is_blocking = False
        self.released.set()


@pytest.fixture
def blocking_store() -> Iterator[BlockingStore]:
    store = BlockingStore()
    yield store
    store.release()
    store.close()


@contextlib.contextmanager
def open_registry(
    config: RoomConfig, store: BlockingStore | None = None
) -> Generator[RoomRegistry]:
    """A registry for one hub test, closed at the end (its store released first)."""
    registry = RoomRegistry(config=config, store=store)
    try:
        yield registry
    finally:
        if store is not None:
            store.release()
        registry.close()


def letter_in_state(state: RoomState | None, row: int, column: int) -> str | None:
    """The letter the room holds at (row, column)."""
    assert state is not None, "the room is unknown"
    for cell in state.cells:
        if (cell.row, cell.column) == (row, column):
            return cell.letter
    pytest.fail(f"no letter cell at ({row}, {column})")


def letter_in_snapshot(snapshot: Snapshot, row: int, column: int) -> str | None:
    """The letter a snapshot shows at (row, column)."""
    for cell in snapshot.grid.cells:
        if isinstance(cell, LetterCellView) and (cell.row, cell.column) == (
            row,
            column,
        ):
            return cell.letter
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


def own_letter_changes(
    messages: list[ServerMessage], player_id: str
) -> list[LetterChanged]:
    """The letter_changed events of `player_id` among `messages`."""
    found: list[LetterChanged] = []
    for message in messages:
        if isinstance(message, LetterChanged) and message.player_id == player_id:
            found.append(message)
    return found


def state_changes_of(
    messages: list[ServerMessage], player_id: str
) -> list[PlayerStateChanged]:
    """The player_state_changed events about `player_id` among `messages`."""
    found: list[PlayerStateChanged] = []
    for message in messages:
        if isinstance(message, PlayerStateChanged) and message.player_id == player_id:
            found.append(message)
    return found


def b_edit(index: int) -> EditLetter:
    """B's edit number `index`, on row 1 of FX-01: the grid is never filled."""
    letter = string.ascii_uppercase[index % len(string.ascii_uppercase)]
    return EditLetter(row=1, column=index % 5, letter=letter)


def triples(edits: Sequence[EditLetter | LetterChanged]) -> list[tuple[int, int, str]]:
    """The (row, column, letter) of each edit or letter_changed."""
    found: list[tuple[int, int, str]] = []
    for edit in edits:
        assert edit.letter is not None, edit
        found.append((edit.row, edit.column, edit.letter))
    return found


class StallRun(NamedTuple):
    """What the stalled-client scenario of AC-5 saw."""

    a_id: str
    b_id: str
    close_codes_within_budget: list[int]
    writer_returned: bool
    b_messages_after_30: list[ServerMessage]
    a_texts: list[str]
    final_close_codes: list[int]
    b_messages_after_40: list[ServerMessage]


async def stalled_client_scenario(registry: RoomRegistry, code: str) -> StallRun:
    """A never reads; B sends 30 edits, then 10 more (AC-5)."""
    a = open_hub_client(registry, code, StuckSocket())
    a_id = (await join_hub_client(a, "Ana")).you
    b = open_hub_client(registry, code, FakeSocket())
    b_id = (await join_hub_client(b, "Bob")).you

    for index in range(30):
        b.connection.submit(b_edit(index))
    await wait_until_async(
        lambda: len(a.socket.close_codes) > 0 and a.writer.done(),
        "A's close and the end of A's writer",
        timeout=STALL_BUDGET_SECONDS,
    )
    close_codes_within_budget = list(a.socket.close_codes)
    writer_returned = not a.writer.cancelled() and a.writer.exception() is None

    def b_saw_the_stall() -> bool:
        messages = b.socket.messages()
        if len(own_letter_changes(messages, b_id)) < 30:
            return False
        return len(state_changes_of(messages, a_id)) > 0

    await wait_until_async(b_saw_the_stall, "B's 30 letter_changed and A's new state")
    b_messages_after_30 = b.socket.messages()

    for index in range(30, 40):
        b.connection.submit(b_edit(index))
    await wait_until_async(
        lambda: len(own_letter_changes(b.socket.messages(), b_id)) >= 40,
        "B's 10 more letter_changed",
    )
    await asyncio.sleep(SETTLE_SECONDS)
    return StallRun(
        a_id=a_id,
        b_id=b_id,
        close_codes_within_budget=close_codes_within_budget,
        writer_returned=writer_returned,
        b_messages_after_30=b_messages_after_30,
        a_texts=list(a.socket.texts),
        final_close_codes=list(a.socket.close_codes),
        b_messages_after_40=b.socket.messages(),
    )


class BoundRun(NamedTuple):
    """What a scenario saw at the bound, then one input or message over it."""

    close_codes_at_bound: list[int]
    writer_done_at_bound: bool
    close_codes_over_bound: list[int]


async def outbound_bound_scenario(registry: RoomRegistry, code: str) -> BoundRun:
    """A never reads; its queue gets exactly 20 messages, then one more (AC-5).

    A's snapshot is in the stuck `send_text`, so it is no longer queued. A's
    queue then gets B's player_joined and one letter_changed per edit of B:
    after 19 edits it holds 20 messages.
    """
    a = open_hub_client(registry, code, StuckSocket())
    await join_hub_client(a, "Ana")
    b = open_hub_client(registry, code, FakeSocket())
    b_id = (await join_hub_client(b, "Bob")).you

    for index in range(OUTBOUND_LIMIT - 1):
        b.connection.submit(b_edit(index))
    await wait_until_async(
        lambda: len(own_letter_changes(b.socket.messages(), b_id))
        >= OUTBOUND_LIMIT - 1,
        "B's 19 letter_changed",
    )
    await asyncio.sleep(SETTLE_SECONDS)
    close_codes_at_bound = list(a.socket.close_codes)
    writer_done_at_bound = a.writer.done()

    b.connection.submit(b_edit(OUTBOUND_LIMIT - 1))
    await wait_until_async(
        lambda: len(a.socket.close_codes) > 0,
        "A's close after one more message",
        timeout=STALL_BUDGET_SECONDS,
    )
    return BoundRun(
        close_codes_at_bound=close_codes_at_bound,
        writer_done_at_bound=writer_done_at_bound,
        close_codes_over_bound=list(a.socket.close_codes),
    )


async def ana_edit_waiting_in_append(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> HubClient:
    """Ana joins; then the store blocks and her edit T at (1, 0) waits in append."""
    ana = open_hub_client(registry, code, FakeSocket())
    await join_hub_client(ana, "Ana")
    await asyncio.sleep(SETTLE_SECONDS)  # the step of the join is over
    store.block()
    ana.connection.submit(EditLetter(row=1, column=0, letter="T"))
    await wait_until_async(store.append_waiting.is_set, "the edit's step in append")
    return ana


async def send_pings_until_closed(client: HubClient, count: int) -> None:
    """Submit `count` pings, then wait for the connection's close."""
    for _ in range(count):
        client.connection.submit(Ping())
    await wait_until_async(
        lambda: len(client.socket.close_codes) > 0,
        "the close of the flooding connection",
    )


async def release_and_wait_for_t(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> None:
    """Release the store and wait until the room holds T at (1, 0)."""
    store.release()
    await wait_until_async(
        lambda: letter_in_state(registry.room_state(code), 1, 0) == "T",
        "T at (1, 0) once the store is released",
    )


async def join_cleo(registry: RoomRegistry, code: str) -> Snapshot:
    """A new connection C joins as Cleo; return its snapshot."""
    cleo = open_hub_client(registry, code, FakeSocket())
    return await join_hub_client(cleo, "Cleo")


class FloodRun(NamedTuple):
    """What the flooding-client scenario of AC-6 saw."""

    close_codes_while_blocked: list[int]
    store_still_blocked: bool
    letter_in_room: str | None
    c_snapshot: Snapshot
    final_close_codes: list[int]


async def flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> FloodRun:
    """A's edit waits in append, then A sends 7 pings (AC-6)."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    await send_pings_until_closed(ana, 7)
    close_codes_while_blocked = list(ana.socket.close_codes)
    store_still_blocked = store.is_blocking and not store.released.is_set()

    await release_and_wait_for_t(registry, store, code)
    letter_in_room = letter_in_state(registry.room_state(code), 1, 0)
    c_snapshot = await join_cleo(registry, code)
    await asyncio.sleep(SETTLE_SECONDS)
    return FloodRun(
        close_codes_while_blocked=close_codes_while_blocked,
        store_still_blocked=store_still_blocked,
        letter_in_room=letter_in_room,
        c_snapshot=c_snapshot,
        final_close_codes=list(ana.socket.close_codes),
    )


async def inbound_bound_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> BoundRun:
    """A's edit and 4 pings are unapplied (5 in all), then one more ping (AC-6)."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    for _ in range(INBOUND_LIMIT - 1):
        ana.connection.submit(Ping())
    await asyncio.sleep(SETTLE_SECONDS)
    close_codes_at_bound = list(ana.socket.close_codes)
    writer_done_at_bound = ana.writer.done()

    await send_pings_until_closed(ana, 1)
    close_codes_over_bound = list(ana.socket.close_codes)
    await release_and_wait_for_t(registry, store, code)
    return BoundRun(
        close_codes_at_bound=close_codes_at_bound,
        writer_done_at_bound=writer_done_at_bound,
        close_codes_over_bound=close_codes_over_bound,
    )


async def stranger_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str, frame: str
) -> list[int]:
    """While A's edit waits in append, a socket that never joined sends 6 frames."""
    await ana_edit_waiting_in_append(registry, store, code)
    stranger = open_hub_client(registry, code, FakeSocket())
    for _ in range(INBOUND_LIMIT + 1):
        if frame == "ping":
            stranger.connection.submit(Ping())
        else:
            stranger.connection.submit_invalid()
    await wait_until_async(
        lambda: len(stranger.socket.close_codes) > 0,
        "the close of the stranger while the store is blocked",
    )
    close_codes = list(stranger.socket.close_codes)
    await release_and_wait_for_t(registry, store, code)
    return close_codes


async def frame_after_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> Snapshot:
    """A floods; once the room caught up, A sends an edit of (1, 1); C joins."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    await send_pings_until_closed(ana, 7)
    await release_and_wait_for_t(registry, store, code)
    ana.connection.submit(EditLetter(row=1, column=1, letter="X"))
    return await join_cleo(registry, code)


async def close_after_flood_scenario(
    registry: RoomRegistry, store: BlockingStore, code: str
) -> tuple[str, Snapshot]:
    """A floods, then A's socket closes (`leave`); C joins once the room caught up."""
    ana = await ana_edit_waiting_in_append(registry, store, code)
    ana_snapshot = parse_server_message(ana.socket.texts[0])
    assert isinstance(ana_snapshot, Snapshot), ana_snapshot
    await send_pings_until_closed(ana, 7)
    ana.connection.leave()  # what the server's socket handler does once closed
    await release_and_wait_for_t(registry, store, code)
    return ana_snapshot.you, await join_cleo(registry, code)


def error_types(error: ValidationError) -> list[str]:
    """The pydantic error type of each problem of `error`."""
    return [problem["type"] for problem in error.errors()]


# ---- Mocked room socket (edge cases) ----------------------------------------------


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


# ---- Live server with the production limits (AC-7) --------------------------------


@contextlib.contextmanager
def production_live_server(
    registry: RoomRegistry, catalogue: Catalogue
) -> Generator[str]:
    """Run the app like conftest's `live_server`, but built with `server_config`.

    Yields the base URL. Fails (not skips) when the client is not built.
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    app = create_app(rooms=registry, dist_dir=WEB_DIST_DIR, catalogue=catalogue)
    server = uvicorn.Server(nock.server.server_config(app, log_level="warning"))
    listening_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listening_socket.bind(("127.0.0.1", 0))
    port = listening_socket.getsockname()[1]
    thread = threading.Thread(
        target=server.run, kwargs={"sockets": [listening_socket]}, daemon=True
    )
    thread.start()
    try:
        deadline = time.monotonic() + SERVER_START_SECONDS
        while not server.started and time.monotonic() < deadline:
            time.sleep(POLL_SECONDS)
        if not server.started:
            pytest.fail("the live server built with server_config did not start")
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=SERVER_START_SECONDS)
        listening_socket.close()


def socket_url(base_url: str, code: str) -> str:
    return base_url.replace("http://", "ws://", 1) + f"/api/rooms/{code}/ws"


def padded_frame(size: int) -> str:
    """A valid edit_letter followed by spaces, `size` bytes long in UTF-8."""
    text = EditLetter(row=1, column=0, letter="T").model_dump_json()
    return text + " " * (size - len(text.encode("utf-8")))


# Opens a socket, sends one frame and reports how the socket was closed, and
# everything it received. Gives up after 5 seconds without a close.
OVERSIZED_FRAME_SCRIPT = """
async ({ url, frame, binary }) => {
  const socket = new WebSocket(url);
  const received = [];
  socket.addEventListener("message", (event) => {
    received.push(typeof event.data === "string" ? event.data : "(binary)");
  });
  const closed = new Promise((resolve) => {
    socket.addEventListener("close", (event) => resolve(event.code));
  });
  const opened = await Promise.race([
    new Promise((resolve) => socket.addEventListener("open", () => resolve(true))),
    closed.then(() => false),
  ]);
  if (!opened) {
    return { opened: false, closeCode: await closed, received };
  }
  socket.send(binary ? new TextEncoder().encode(frame) : frame);
  const giveUp = new Promise((resolve) => setTimeout(() => resolve(null), 5000));
  const closeCode = await Promise.race([closed, giveUp]);
  socket.close();
  return { opened: true, closeCode, received };
}
"""

# Opens a socket, joins, sends one big frame, then a ping, waiting up to 5
# seconds for an answer to each; reports what arrived and the socket's state.
ANSWERED_FRAME_SCRIPT = """
async ({ url, join, frame, binary }) => {
  const socket = new WebSocket(url);
  const received = [];
  let closeCode = null;
  socket.addEventListener("message", (event) => received.push(event.data));
  socket.addEventListener("close", (event) => {
    closeCode = event.code;
  });
  const waitFor = async (condition) => {
    const deadline = performance.now() + 5000;
    while (!condition() && closeCode === null && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };
  await waitFor(() => socket.readyState === WebSocket.OPEN);
  socket.send(join);
  await waitFor(() => received.length >= 1);
  const afterJoin = received.length;
  socket.send(binary ? new TextEncoder().encode(frame) : frame);
  await waitFor(() => received.length > afterJoin);
  const afterFrame = received.length;
  socket.send(JSON.stringify({ type: "ping" }));
  await waitFor(() => received.length > afterFrame);
  const readyState = socket.readyState;
  const closeCodeBefore = closeCode;
  socket.close();
  return { received, readyState, closeCode: closeCodeBefore };
}
"""

# uvicorn options that `server_config` leaves at uvicorn's default.
UVICORN_DEFAULT_OPTIONS = (
    "ws",
    "ws_max_queue",
    "ws_ping_interval",
    "ws_ping_timeout",
    "ws_per_message_deflate",
    "http",
    "lifespan",
    "interface",
    "proxy_headers",
    "timeout_keep_alive",
    "limit_concurrency",
    "backlog",
    "root_path",
)


# ---- The production entry point in a subprocess (AC-8, AC-9) ----------------------


def database_with_room(path: Path, grid: Grid) -> str:
    """Write a SQLite file at `path` holding one room on `grid`; return its code.

    The room is registered by `RoomRegistry(store=RoomStore(path))`; then the
    registry, then the store, are closed.
    """
    store = RoomStore(path)
    registry = RoomRegistry(store=store)
    code = registry.register_room(grid)
    registry.close()
    store.close()
    return code


def free_local_port() -> int:
    """A free port of 127.0.0.1: bound with port 0, then released."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind(("127.0.0.1", 0))
        port: int = probe.getsockname()[1]
    return port


def nock_environment(database: Path, port: int) -> dict[str, str]:
    """The test's own environment plus NOCK_DATABASE and NOCK_PORT, no NOCK_HOST."""
    environment = dict(os.environ)
    environment.pop(HOST_VARIABLE, None)
    environment[DATABASE_VARIABLE] = str(database)
    environment[PORT_VARIABLE] = str(port)
    return environment


class HttpAnswer(NamedTuple):
    """The status and the body of an HTTP answer."""

    status: int
    body: bytes


def get_directly(url: str) -> HttpAnswer:
    """GET `url` without the proxies of the environment; return the answer.

    Raises:
        OSError: nothing answered (connection refused or reset, timeout).
    """
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return HttpAnswer(status=response.status, body=response.read())
    except urllib.error.HTTPError as error:
        return HttpAnswer(status=error.code, body=error.read())


def process_output(log_path: Path) -> str:
    """What the process wrote on stdout and stderr so far."""
    return log_path.read_text(encoding="utf-8", errors="replace")


def wait_for_first_answer(
    process: subprocess.Popen[bytes], url: str, log_path: Path
) -> HttpAnswer:
    """Poll GET `url` until the server answers, for up to 10 seconds.

    Fails the test when the process ends first, or when nothing answers in time.
    """
    deadline = time.monotonic() + SERVER_START_SECONDS
    while True:
        exit_status = process.poll()
        if exit_status is not None:
            pytest.fail(
                f"python -m nock ended with status {exit_status} before answering "
                f"GET {url}:\n{process_output(log_path)}"
            )
        try:
            return get_directly(url)
        except OSError as error:
            if time.monotonic() >= deadline:
                pytest.fail(
                    f"python -m nock did not answer GET {url} within "
                    f"{SERVER_START_SECONDS:.0f} s ({error}):\n"
                    f"{process_output(log_path)}"
                )
        time.sleep(START_POLL_SECONDS)


def stop_process(process: subprocess.Popen[bytes]) -> None:
    """Terminate the process, then kill it when it has not ended in 10 seconds."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=PROCESS_STOP_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=PROCESS_STOP_SECONDS)


class NockServer(NamedTuple):
    """A running `python -m nock`: its base URL and its first answer to GET /."""

    base_url: str
    first_answer: HttpAnswer


@contextlib.contextmanager
def nock_process(database: Path, log_path: Path) -> Generator[NockServer]:
    """Run `python -m nock` on the SQLite file `database`, on a free port.

    Runs `[sys.executable, "-m", "nock"]` with the environment of
    `nock_environment`, its output going to `log_path`, and yields once GET /
    got an answer. Fails (not skips) when the client is not built. The process
    is terminated at the end, then killed if it does not stop.
    """
    if not (WEB_DIST_DIR / "index.html").is_file():
        pytest.fail(MISSING_BUILD_MESSAGE)
    port = free_local_port()
    base_url = f"http://127.0.0.1:{port}"
    with log_path.open("wb") as log_file:
        process = subprocess.Popen(
            [sys.executable, "-m", "nock"],
            env=nock_environment(database, port),
            stdin=subprocess.DEVNULL,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
        try:
            first_answer = wait_for_first_answer(process, f"{base_url}/", log_path)
            yield NockServer(base_url=base_url, first_answer=first_answer)
        finally:
            stop_process(process)


# Opens a socket and sends a join as soon as it is open; reports the first
# message it received, or the close that came instead. Gives up after 5 seconds.
FIRST_MESSAGE_SCRIPT = """
async ({ url, join }) => {
  const socket = new WebSocket(url);
  let firstMessage = null;
  let closeCode = null;
  socket.addEventListener("message", (event) => {
    if (firstMessage === null) {
      firstMessage = typeof event.data === "string" ? event.data : "(binary)";
    }
  });
  socket.addEventListener("close", (event) => {
    closeCode = event.code;
  });
  const deadline = performance.now() + 5000;
  const waitFor = async (condition) => {
    while (!condition() && closeCode === null && performance.now() < deadline) {
      await new Promise((resolve) => setTimeout(resolve, 20));
    }
  };
  await waitFor(() => socket.readyState === WebSocket.OPEN);
  const opened = socket.readyState === WebSocket.OPEN;
  if (opened) {
    socket.send(join);
    await waitFor(() => firstMessage !== null);
  }
  const closeCodeBefore = closeCode;
  socket.close();
  return { opened, firstMessage, closeCode: closeCodeBefore };
}
"""


# ---- The production entry point in the test process (AC-10, AC-11) ----------------


@pytest.fixture
def server_runs(monkeypatch: pytest.MonkeyPatch) -> list[uvicorn.Config]:
    """Replace `uvicorn.Server.run` by the harness's recorder; return what it keeps.

    The recorder keeps the `config` of each server whose `run` is called and
    returns None. `uvicorn.Server.serve` is replaced too, so that a server
    started without `run` fails the test instead of serving in it.
    """
    configs: list[uvicorn.Config] = []

    def record_run(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        configs.append(server.config)

    async def refuse_serve(
        server: uvicorn.Server, sockets: list[socket.socket] | None = None
    ) -> None:
        raise AssertionError("main() must start its server with uvicorn.Server.run")

    monkeypatch.setattr(uvicorn.Server, "run", record_run)
    monkeypatch.setattr(uvicorn.Server, "serve", refuse_serve)
    return configs


def entry_point() -> Callable[[], None]:
    """Import `nock.__main__` and return its `main`.

    Called by each test of AC-10 and AC-11 once the recorder is in place, so that
    a missing module fails those tests, not the collection of this file.
    """
    from nock.__main__ import main

    return main


def set_variable(monkeypatch: pytest.MonkeyPatch, name: str, value: str | None) -> None:
    """Set the environment variable `name` to `value`; None deletes it."""
    if value is None:
        monkeypatch.delenv(name, raising=False)
    else:
        monkeypatch.setenv(name, value)


def refusal_message(main: Callable[[], None]) -> str:
    """Call `main`, which must raise SystemExit naming NOCK_PORT; return its code.

    Fails the test when the code of the SystemExit is not a `str`.
    """
    with pytest.raises(SystemExit, match=PORT_VARIABLE) as caught:
        main()
    message = caught.value.code
    assert isinstance(message, str), f"the SystemExit code {message!r} is no message"
    return message
