"""Tests of spec 036 (performance), AC-1 to AC-4: the time budgets.

AC-1, AC-2 and AC-4 measure the room page in Chromium under the spec's phone
profile (CPU throttling, plus the 4G network profile for AC-1 and AC-2, both sent
through CDP before the first `page.goto`), with the in-page timing of the test
harness. AC-3 measures the server's relay with eight simulated clients.

The shared setup is in `spec036_harness` and `spec036_browser_harness`. What
only this file uses is defined below the imports.

Notes:

- FX-02's across words hold at most 7 letters, so two of them hold 12 cells. In
  AC-4 Ana types her two words, then types them again with other letters (so
  every key changes its cell on Bob's page): 20 keys in all.
- Edge cases checked as well: no mark for a room that is not found, nor a second
  one after a reconnection.
"""

from __future__ import annotations

import contextlib
import random
import statistics
import string
import threading
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect
from starlette.testclient import WebSocketTestSession

from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorMessage,
    Join,
    LetterChanged,
    ServerMessage,
    Snapshot,
    parse_server_message,
)
from nock.room import RoomConfig
from nock.server import create_app
from spec036_browser_harness import (
    FX02_AT_MARK,
    LOCAL_ECHO_KEYS,
    MARK_PROBE_SCRIPT,
    PAGE_WAIT_MS,
    TYPING_PROBE_SCRIPT,
    Cell,
    Keystroke,
    Word,
    across_words,
    auto_join_script,
    cell_at,
    expect_fx02_room_shown,
    expect_last_letters_shown,
    expect_reconnection_after_close,
    interactive_mark_times,
    local_echo_keystrokes,
    local_echo_times,
    measured_times,
    missing_keystrokes,
    open_mock_room,
    open_phone_page,
    percentile_95,
    propagation_times,
    read_probe,
    states_at_mark,
    tap_word_start,
    type_keystrokes,
    wait_for_interactive_mark,
)
from spec036_harness import POLL_SECONDS, WAIT_SECONDS, triples

# The fixtures of the harness. pytest looks for a test's fixtures among the names of
# its module, so they are imported by name. `x as x` is the explicit re-export
# form: it keeps ruff from reporting the import as unused or as redefined.
from spec036_harness import fx01_grid as fx01_grid

# ---- Values of the spec --------------------------------------------------------------

INTERACTIVE_BUDGET_MS = 2500.0
LOCAL_ECHO_BUDGET_MS = 50.0
PROPAGATION_BUDGET_MS = 300.0
RELAY_BUDGET_SECONDS = 0.100

COLD_LOADS = 3
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


# ---- Values of the test harness ------------------------------------------------------

MARK_TIMEOUT_MS = 20_000
SETTLE_MS = 500
LOAD_WARM_UP_MS = 1_000
LOAD_PLAN_EDITS = 80  # more than AC-4 ever sends: its load stops after Ana's keys

SENDER_LEAD_SECONDS = 0.2
SENDER_LIMIT_SECONDS = 60.0


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return Grid.model_validate_json(fx02_text)


@pytest.fixture
def default_registry() -> Iterator[RoomRegistry]:
    """A registry with `RoomConfig()` defaults: spec 037's 20 edits a second apply."""
    registry = RoomRegistry(config=RoomConfig())
    yield registry
    registry.close()


# ---- Grids ---------------------------------------------------------------------------


def letter_cells(grid: Grid) -> list[Cell]:
    """The letter cells of `grid`, in row-major order."""
    positions: list[Cell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            positions.append((cell.row, cell.column))
    positions.sort()
    return positions


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


# ---- Simulated players (spec 015's Python clients) -----------------------------------


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


# ---- AC-1: FX-02 is interactive within 2.5 seconds --------------------------------


@pytest.mark.only_browser("chromium")
def test_ac1_three_cold_loads_of_fx02_are_interactive_within_2500_ms_at_the_median(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    url = f"{live_server}/r/{code}"
    tap_row, tap_column = across_words(fx02_grid)[0].cells[0]
    start_times: list[float] = []
    for load_number in range(1, COLD_LOADS + 1):
        phone = open_phone_page(browser, with_network=True)
        try:
            phone.page.add_init_script(auto_join_script(code, "Ana"))
            phone.page.add_init_script(MARK_PROBE_SCRIPT)
            phone.page.goto(url)
            wait_for_interactive_mark(phone.page, MARK_TIMEOUT_MS)
            phone.page.wait_for_timeout(SETTLE_MS)
            mark_times = interactive_mark_times(phone.page)
            assert len(mark_times) == 1, f"load {load_number} set {mark_times} marks"
            at_mark = states_at_mark(phone.page)
            assert at_mark == [FX02_AT_MARK], f"load {load_number}, at the mark"
            start_times.append(mark_times[0])
            if load_number == COLD_LOADS:
                tap_word_start(phone.page, tap_row, tap_column)
                phone.page.keyboard.press("A")
                expect(cell_at(phone.page, tap_row, tap_column)).to_have_attribute(
                    "data-letter", "A"
                )
        finally:
            phone.context.close()

    median_ms = statistics.median(start_times)
    assert median_ms <= INTERACTIVE_BUDGET_MS, (
        f"median of the three nock:interactive startTime values {median_ms:.0f} ms, "
        f"limit {INTERACTIVE_BUDGET_MS:.0f} ms (loads: {start_times})"
    )


def test_ac1_a_room_that_is_not_found_sets_no_mark(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/r/ZZZZZZ")
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "not_found"
    )
    page.wait_for_timeout(SETTLE_MS)

    assert interactive_mark_times(page) == []


def test_ac1_a_snapshot_after_a_reconnection_adds_no_mark(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    server = open_mock_room(page, live_server, fx01_grid)
    wait_for_interactive_mark(page, PAGE_WAIT_MS)

    expect_reconnection_after_close(page, server, fx01_grid, 1011)
    page.wait_for_timeout(SETTLE_MS)

    assert len(interactive_mark_times(page)) == 1


# ---- AC-2: a typed letter shows locally within 50 ms ------------------------------


@pytest.mark.only_browser("chromium")
def test_ac2_a_typed_letter_shows_locally_within_50_ms_at_the_p95(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    keystrokes = local_echo_keystrokes(fx02_grid)
    assert len(keystrokes) == LOCAL_ECHO_KEYS
    phone = open_phone_page(browser, with_network=True)
    try:
        phone.page.add_init_script(auto_join_script(code, "Ana"))
        phone.page.add_init_script(TYPING_PROBE_SCRIPT)
        phone.page.goto(f"{live_server}/r/{code}")
        expect_fx02_room_shown(phone.page)

        type_keystrokes(phone.page, keystrokes, LOCAL_ECHO_GAP_MS)
        expect_last_letters_shown(phone.page, keystrokes)
        probe = read_probe(phone.page)
    finally:
        phone.context.close()

    times = local_echo_times(probe, keystrokes)
    assert missing_keystrokes(keystrokes, times) == []
    p95_ms = percentile_95(measured_times(times))
    assert p95_ms <= LOCAL_ECHO_BUDGET_MS, (
        f"p95 (38th smallest of 40) from keydown to the cell's data-letter: "
        f"{p95_ms:.1f} ms, limit {LOCAL_ECHO_BUDGET_MS:.0f} ms "
        f"(max {max(measured_times(times)):.1f} ms)"
    )


# ---- AC-3: eight players typing two letters a second, server relay ----------------


def test_ac3_eight_players_typing_two_letters_a_second_are_relayed_within_100_ms(
    default_registry: RoomRegistry, fx02_grid: Grid, tmp_path: Path
) -> None:
    code = default_registry.register_room(fx02_grid)
    plans = random_edit_plans(
        random.Random(LOAD_SEED),
        letter_cells(fx02_grid),
        len(RELAY_CLIENT_NAMES),
        EDITS_PER_RELAY_CLIENT,
    )
    app = create_app(rooms=default_registry, dist_dir=tmp_path)
    with TestClient(app) as test_client, contextlib.ExitStack() as sockets:
        clients = join_simulated_clients(sockets, test_client, code, RELAY_CLIENT_NAMES)
        load = TypingLoad(clients, plans)
        load.start()
        assert load.wait_until_sent() == []
        wait_for(lambda: every_edit_answered(clients), "an answer to every edit")
        for client, plan in zip(clients, plans, strict=True):
            assert client.errors() == [], f"{client.name} got an error"
            assert triples(client.own_letter_changes()) == triples(plan)
        edit_seqs: set[int] = set()
        for client in clients:
            for answer in client.own_letter_changes():
                edit_seqs.add(answer.seq)
        assert len(edit_seqs) == RELAY_EDIT_COUNT
        wait_for(
            lambda: every_seq_received(clients, edit_seqs),
            "every letter_changed on every client",
        )
        for client in clients:
            seqs = [event.seq for event in client.letter_changes()]
            assert sorted(seqs) == sorted(edit_seqs), f"{client.name}'s events"
        times = relay_times(clients)

    assert len(times) == RELAY_TIME_COUNT
    p95 = percentile_95(times)
    assert p95 <= RELAY_BUDGET_SECONDS, (
        f"p95 (1064th smallest of 1120) of the relay times: {p95 * 1000:.1f} ms, "
        f"limit {RELAY_BUDGET_SECONDS * 1000:.0f} ms (max {max(times) * 1000:.1f} ms)"
    )


# ---- AC-4: under the same load, a letter reaches another page within 300 ms -------


@pytest.mark.only_browser("chromium")
def test_ac4_a_letter_typed_in_one_page_shows_in_another_within_300_ms_under_load(
    browser: Browser, live_server: str, room_registry: RoomRegistry, fx02_grid: Grid
) -> None:
    code = room_registry.register_room(fx02_grid)
    url = f"{live_server}/r/{code}"
    keystrokes = ana_keystrokes(ana_words(fx02_grid))
    assert len(keystrokes) == ANA_KEYS
    ana_cells = {(keystroke.row, keystroke.column) for keystroke in keystrokes}
    load_cells = [cell for cell in letter_cells(fx02_grid) if cell not in ana_cells]
    plans = random_edit_plans(
        random.Random(LOAD_SEED), load_cells, len(LOAD_CLIENT_NAMES), LOAD_PLAN_EDITS
    )
    with contextlib.ExitStack() as pages:
        ana = open_phone_page(browser, with_network=False)
        pages.callback(ana.context.close)
        bob = open_phone_page(browser, with_network=False)
        pages.callback(bob.context.close)
        for phone, nickname in ((ana, "Ana"), (bob, "Bob")):
            phone.page.add_init_script(auto_join_script(code, nickname))
            phone.page.add_init_script(TYPING_PROBE_SCRIPT)
            phone.page.goto(url)
            expect_fx02_room_shown(phone.page)

        simulated_app = create_app(rooms=room_registry)
        with (
            TestClient(simulated_app) as test_client,
            contextlib.ExitStack() as sockets,
        ):
            clients = join_simulated_clients(
                sockets, test_client, code, LOAD_CLIENT_NAMES
            )
            load = TypingLoad(clients, plans)
            load.start()
            try:
                ana.page.wait_for_timeout(LOAD_WARM_UP_MS)
                type_keystrokes(ana.page, keystrokes, ANA_GAP_MS)
                expect_last_letters_shown(bob.page, keystrokes)
            finally:
                load.stop()
            assert load.wait_until_sent() == []
            ana_probe = read_probe(ana.page)
            bob_probe = read_probe(bob.page)
            wait_for(lambda: every_edit_answered(clients), "answers to the load")
            for client in clients:
                assert client.errors() == [], f"{client.name} was refused an edit"

    times = propagation_times(ana_probe, bob_probe, keystrokes)
    assert missing_keystrokes(keystrokes, times) == []
    p95_ms = percentile_95(measured_times(times))
    assert p95_ms <= PROPAGATION_BUDGET_MS, (
        f"p95 (19th smallest of 20) from Ana's keydown to Bob's data-letter: "
        f"{p95_ms:.1f} ms, limit {PROPAGATION_BUDGET_MS:.0f} ms "
        f"(max {max(measured_times(times)):.1f} ms)"
    )
