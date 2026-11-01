"""Tests of shell AC-26 and AC-27: the pace of remote updates on the reference phone.

`client/shell.md` rule 18: on the reference phone (`product.md` rule 21) and FX-02,
a frame that changes no cell costs at most 2 ms of main-thread time on average
over a burst, and with the 7 other players typing at `product.md` rule 24's pace
the local echo of rule 23 holds. The mutation counts of rule 18 are in
`test_shell_remote_updates.py`.

These tests measure a time and a pace, so this file runs alone, after the
parallel pass (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

Setup, Chromium only: Ana's page is spec 036's phone profile with the 4G network
profile (`open_phone_page`, CPU throttling 4 and the network conditions sent
through CDP before the first `goto`, in a fresh context, so a cold cache), joined
to a FX-02 room of the live server by spec 036's automatic join. The 7 other
players are spec 024's simulated clients (`Peer`), on a second app that serves
the same registry, as spec 036's AC-4 does it.

Choices where the spec leaves room:

- The other players' words: the 7 longest across words of FX-02 that hold none
  of the cells Ana types (the first in row-major order among words of one
  length). Each player's cursor starts on the first cell of their word.
- "Each typing 2 letters a second in their own words, their cursors following":
  every 500 ms, on an absolute schedule, each player sends an `edit_letter` for
  the next cell of their word, then a `select_cell` (across) on the cell after it,
  back to the first after the last. Their first sends are 62.5 ms apart, as in
  spec 036's AC-4. A word's first pass types its answer, each later pass the
  letter after the one before (Z gives A), so every edit changes its cell.
- AC-26's 40 letters: spec 036 AC-2's keys (`local_echo_keystrokes`, the answers
  of FX-02's across words from the first, a tap on each word's first cell),
  typed 250 ms apart once the other players have typed for 1 s; the local echo is
  timed from each keydown to its cell's `data-letter` by spec 036's probe, and
  the p95 is the 38th smallest of the 40.
- AC-27, "main-thread time": the renderer main thread's time in tasks, the
  `TaskDuration` of CDP `Performance.getMetrics` (under the CPU throttling),
  read once before Bob's first `select_cell` and once after the page has received
  the 100 `selection_moved`. The page's cost per `selection_moved` is the
  difference divided by 100.
- AC-27, "100 `select_cell` in a row": `product.md` rule 25 lets a connection have
  at most 100 inputs posted and not yet applied, so Bob sends them in 10 batches
  of 10, each followed by a ping whose pong he waits for.
- AC-27, the test's own work in the measure: between the two reads the test runs
  nothing in the page but the reads of a counter (a property read, once the
  burst has been relayed) and the counter itself, an init script's `message`
  listener on each socket that counts the frames holding `selection_moved` (a
  substring test). Both are counted as the page's: they make the measure
  stricter by microseconds. The page's own pings and their pongs during the
  burst are frames that change no cell, so they count too.
- The simulated players send no keep-alive ping, so this module's registry
  lifts the silence timeout of `platform/realtime.md` (6 s): a player quiet
  during the setup would otherwise be disconnected and lose their cursor. Every
  other value of the room is the default.
"""

from __future__ import annotations

import contextlib
import string
import threading
import time
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, CDPSession, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Direction, EditLetter, SelectCell
from nock.room import RoomConfig
from nock.server import create_app
from spec024_harness import Peer, join_one, ping_and_wait
from spec036_browser_harness import (
    LOCAL_ECHO_KEYS,
    TYPING_PROBE_SCRIPT,
    Cell,
    Keystroke,
    Word,
    across_words,
    auto_join_script,
    expect_fx02_room_shown,
    expect_last_letters_shown,
    local_echo_keystrokes,
    local_echo_times,
    measured_times,
    missing_keystrokes,
    open_phone_page,
    percentile_95,
    read_probe,
    type_keystrokes,
)

# ---- Values of the criteria ---------------------------------------------------

LOCAL_ECHO_BUDGET_MS = 50.0  # `product.md` rule 23, at the p95
KEY_GAP_MS = 250
OTHER_PLAYER_NAMES = ("Bob", "Cy", "Dan", "Eve", "Fay", "Gus", "Hal")
LETTERS_PER_SECOND = 2  # `product.md` rule 24
SELECTION_BURST = 100
MAIN_THREAD_BUDGET_MS = 2.0  # per `selection_moved`, on average

# ---- Values of the test harness -----------------------------------------------

TYPING_INTERVAL_SECONDS = 1 / LETTERS_PER_SECOND
START_OFFSET_SECONDS = 0.0625
SENDER_LEAD_SECONDS = 0.2
SENDER_LIMIT_SECONDS = 30.0
LOAD_WARM_UP_MS = 1_000
SETTLE_MS = 1_000
BATCH_SIZE = 10
RELAY_WAIT_MS = 300
COUNTER_WAIT_MS = 10_000
CURSOR_TIMEOUT_MS = 10_000
QUIET_PLAYERS_SILENCE_SECONDS = 600.0

# Counts, on every socket the page opens, the frames that hold a `selection_moved`.
SELECTION_COUNTER_SCRIPT = r"""
(() => {
  const counter = { selectionMoved: 0 };
  window.__shellSelectionCounter = counter;
  const NativeWebSocket = window.WebSocket;
  window.WebSocket = class extends NativeWebSocket {
    constructor(...args) {
      super(...args);
      this.addEventListener('message', (event) => {
        if (typeof event.data === 'string' && event.data.includes('selection_moved')) {
          counter.selectionMoved += 1;
        }
      });
    }
  };
})();
"""
READ_SELECTION_COUNTER_SCRIPT = "() => window.__shellSelectionCounter.selectionMoved"


# ---- Fixtures -----------------------------------------------------------------


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def room_registry() -> Iterator[RoomRegistry]:
    """The live server's registry, the silence timeout lifted (see the docstring)."""
    config = RoomConfig(silence_timeout_seconds=QUIET_PLAYERS_SILENCE_SECONDS)
    registry = RoomRegistry(config=config)
    yield registry
    registry.close()


# ---- The other players --------------------------------------------------------


def cells_of(keystrokes: list[Keystroke]) -> set[Cell]:
    return {(keystroke.row, keystroke.column) for keystroke in keystrokes}


def other_players_words(grid: Grid, ana_cells: set[Cell]) -> list[Word]:
    """The 7 longest across words holding none of Ana's cells, in row-major order."""
    free_words: list[Word] = []
    for word in across_words(grid):
        if ana_cells.isdisjoint(word.cells):
            free_words.append(word)
    longest_first = sorted(free_words, key=lambda word: len(word.cells), reverse=True)
    chosen = longest_first[: len(OTHER_PLAYER_NAMES)]
    chosen.sort(key=lambda word: word.cells[0])
    assert len(chosen) == len(OTHER_PLAYER_NAMES), "FX-02 has too few free words"
    return chosen


def letter_of_pass(answer_letter: str, pass_number: int) -> str:
    """The letter typed in a cell on a pass: the answer, then the next letters."""
    index = string.ascii_uppercase.index(answer_letter)
    return string.ascii_uppercase[(index + pass_number) % len(string.ascii_uppercase)]


def select_across(peer: Peer, cell: Cell) -> None:
    peer.send(SelectCell(row=cell[0], column=cell[1], direction=Direction.ACROSS))


def join_other_players(
    stack: contextlib.ExitStack, client: TestClient, code: str, words: list[Word]
) -> list[Peer]:
    """Join the 7 other players, each with a cursor on their word's first cell."""
    peers: list[Peer] = []
    for name, word in zip(OTHER_PLAYER_NAMES, words, strict=True):
        peer = join_one(stack, client, code, name)
        select_across(peer, word.cells[0])
        peers.append(peer)
    return peers


class TypingPlayers:
    """The other players typing 2 letters a second in their words, cursors following.

    Each player sends from a thread of their own, on an absolute schedule, until
    the load is stopped.
    """

    def __init__(self, peers: list[Peer], words: list[Word]) -> None:
        self._peers = peers
        self._words = words
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._typed: list[Keystroke] = []
        self._edit_counts: list[int] = [0] * len(peers)
        self._problems: list[str] = []
        self._threads: list[threading.Thread] = []

    def start(self) -> None:
        start_at = time.monotonic() + SENDER_LEAD_SECONDS
        for index in range(len(self._peers)):
            first_send_at = start_at + index * START_OFFSET_SECONDS
            thread = threading.Thread(
                target=self._type, args=(index, first_send_at), daemon=True
            )
            self._threads.append(thread)
            thread.start()

    def _type(self, index: int, first_send_at: float) -> None:
        peer = self._peers[index]
        word = self._words[index]
        step = 0
        try:
            while not self._stop.is_set():
                delay = (
                    first_send_at + step * TYPING_INTERVAL_SECONDS - time.monotonic()
                )
                if delay > 0 and self._stop.wait(delay):
                    return
                self._type_one_letter(index, peer, word, step)
                step += 1
        except Exception as error:  # reported by the test thread
            with self._lock:
                self._problems.append(f"{OTHER_PLAYER_NAMES[index]}: {error!r}")

    def _type_one_letter(self, index: int, peer: Peer, word: Word, step: int) -> None:
        position = step % len(word.cells)
        pass_number = step // len(word.cells)
        row, column = word.cells[position]
        letter = letter_of_pass(word.answer[position], pass_number)
        peer.send(EditLetter(row=row, column=column, letter=letter))
        select_across(peer, word.cells[(position + 1) % len(word.cells)])
        with self._lock:
            self._typed.append(Keystroke(row, column, letter, False))
            self._edit_counts[index] += 1

    def stop(self) -> list[str]:
        """Stop every player, wait for their threads; return the problems met."""
        self._stop.set()
        for thread in self._threads:
            thread.join(timeout=SENDER_LIMIT_SECONDS)
            assert not thread.is_alive(), "a typing thread did not end"
        with self._lock:
            return list(self._problems)

    def typed(self) -> list[Keystroke]:
        """Every letter the players sent, in the order sent."""
        with self._lock:
            return list(self._typed)

    def edit_counts(self) -> list[int]:
        """How many letters each player sent."""
        with self._lock:
            return list(self._edit_counts)


def expect_cursors_shown(page: Page, count: int) -> None:
    expect(page.get_by_test_id("remote-selection")).to_have_count(
        count, timeout=CURSOR_TIMEOUT_MS
    )


# ---- Main-thread time ---------------------------------------------------------


def main_thread_ms(session: CDPSession) -> float:
    """The page's main-thread time in tasks so far (CDP `TaskDuration`), in ms."""
    result = session.send("Performance.getMetrics")
    for metric in result["metrics"]:
        if metric["name"] == "TaskDuration":
            return float(metric["value"]) * 1000
    pytest.fail("CDP Performance.getMetrics gave no TaskDuration")


def selection_frames_received(page: Page) -> int:
    count = page.evaluate(READ_SELECTION_COUNTER_SCRIPT)
    assert isinstance(count, int), count
    return count


def wait_for_selection_frames(page: Page, count: int) -> None:
    """Wait until the page has received `count` `selection_moved`, else fail."""
    waited_ms = 0
    while selection_frames_received(page) < count:
        if waited_ms >= COUNTER_WAIT_MS:
            received = selection_frames_received(page)
            pytest.fail(f"the page received {received} selection_moved, not {count}")
        page.wait_for_timeout(RELAY_WAIT_MS)
        waited_ms += RELAY_WAIT_MS


def send_selection_burst(bob: Peer, cell: Cell) -> None:
    """Bob's 100 `select_cell` for the cell he holds, across, in batches of 10."""
    for _ in range(SELECTION_BURST // BATCH_SIZE):
        for _ in range(BATCH_SIZE):
            select_across(bob, cell)
        ping_and_wait(bob)


# ---- AC-26: the local echo holds while the 7 others type ----------------------


@pytest.mark.only_browser("chromium")
def test_ac26_the_local_echo_holds_while_seven_other_players_type(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    keystrokes = local_echo_keystrokes(fx02_grid)
    assert len(keystrokes) == LOCAL_ECHO_KEYS
    words = other_players_words(fx02_grid, cells_of(keystrokes))
    with contextlib.ExitStack() as stack:
        phone = open_phone_page(browser, with_network=True)
        stack.callback(phone.context.close)
        phone.page.add_init_script(auto_join_script(code, "Ana"))
        phone.page.add_init_script(TYPING_PROBE_SCRIPT)
        phone.page.goto(f"{live_server}/r/{code}")
        expect_fx02_room_shown(phone.page)

        client = stack.enter_context(TestClient(create_app(rooms=room_registry)))
        peers = join_other_players(stack, client, code, words)
        expect_cursors_shown(phone.page, len(peers))
        players = TypingPlayers(peers, words)
        players.start()
        try:
            phone.page.wait_for_timeout(LOAD_WARM_UP_MS)
            type_keystrokes(phone.page, keystrokes, KEY_GAP_MS)
            expect_last_letters_shown(phone.page, keystrokes)
        finally:
            problems = players.stop()
        probe = read_probe(phone.page)
        expect_last_letters_shown(phone.page, players.typed())
        for peer in peers:
            assert peer.errors() == [], f"{peer.name} was refused"

    assert problems == []
    least_letters = int(LOCAL_ECHO_KEYS * KEY_GAP_MS / 1000 * LETTERS_PER_SECOND)
    for name, count in zip(OTHER_PLAYER_NAMES, players.edit_counts(), strict=True):
        assert count >= least_letters, f"{name} typed {count} letters"
    times = local_echo_times(probe, keystrokes)
    assert missing_keystrokes(keystrokes, times) == []
    p95_ms = percentile_95(measured_times(times))
    assert p95_ms <= LOCAL_ECHO_BUDGET_MS, (
        f"p95 (38th smallest of 40) from keydown to the cell's data-letter with 7 "
        f"players typing: {p95_ms:.1f} ms, limit {LOCAL_ECHO_BUDGET_MS:.0f} ms "
        f"(max {max(measured_times(times)):.1f} ms)"
    )


# ---- AC-27: a selection that changes nothing costs at most 2 ms ---------------


@pytest.mark.only_browser("chromium")
def test_ac27_a_selection_bob_already_holds_costs_at_most_2_ms_of_main_thread(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    keystrokes = local_echo_keystrokes(fx02_grid)
    words = other_players_words(fx02_grid, cells_of(keystrokes))
    with contextlib.ExitStack() as stack:
        phone = open_phone_page(browser, with_network=True)
        stack.callback(phone.context.close)
        phone.page.add_init_script(auto_join_script(code, "Ana"))
        phone.page.add_init_script(SELECTION_COUNTER_SCRIPT)
        phone.page.goto(f"{live_server}/r/{code}")
        expect_fx02_room_shown(phone.page)

        client = stack.enter_context(TestClient(create_app(rooms=room_registry)))
        peers = join_other_players(stack, client, code, words)
        expect_cursors_shown(phone.page, len(peers))
        bob = peers[0]
        bobs_cell = words[0].cells[0]
        phone.session.send("Performance.enable")
        phone.page.wait_for_timeout(SETTLE_MS)
        frames_before = selection_frames_received(phone.page)

        before_ms = main_thread_ms(phone.session)
        send_selection_burst(bob, bobs_cell)
        phone.page.wait_for_timeout(RELAY_WAIT_MS)
        wait_for_selection_frames(phone.page, frames_before + SELECTION_BURST)
        after_ms = main_thread_ms(phone.session)

        assert selection_frames_received(phone.page) == frames_before + SELECTION_BURST
        assert bob.errors() == []
        expect_cursors_shown(phone.page, len(peers))

    per_selection_ms = (after_ms - before_ms) / SELECTION_BURST
    assert per_selection_ms <= MAIN_THREAD_BUDGET_MS, (
        f"main-thread time per selection_moved that changes no cell: "
        f"{per_selection_ms:.2f} ms on average over {SELECTION_BURST}, limit "
        f"{MAIN_THREAD_BUDGET_MS:.0f} ms ({after_ms - before_ms:.0f} ms in all)"
    )
