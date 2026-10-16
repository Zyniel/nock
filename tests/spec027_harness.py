"""Shared setup of the tests of spec 027: the shared timer.

This module is not a test file: pytest does not collect it. The tests of spec 027
are in `tests/test_spec_027_*.py`, one file per criterion group:

- `test_spec_027_ac01_ac03_rules_and_websocket.py`: AC-1 and AC-3 (rule, WebSocket
  with a fake clock);
- `test_spec_027_ac02_ac03_live_pages.py`: AC-2 and AC-3 (browsers on the live
  server, real time: the file is timing-sensitive);
- `test_spec_027_ac04_hide.py`: AC-4 (page with a mocked socket);
- `test_spec_027_ac05_display.py`: AC-5 (page with a mocked socket and Playwright's
  page clock);
- `test_spec_027_ac06_ac07_solve_and_restart.py`: AC-6 and AC-7 (rule, `replay`,
  `RoomStore`);
- `test_spec_027_ac08_a11y_and_french.py`: AC-8, the semantics, the keyboard, the
  scans and `fr.json`;
- `test_spec_027_ac08_layout.py`: AC-8, the layout at every window size.

The page's clock. Where a test needs an exact reading of a running timer (AC-5),
the page is opened with Playwright's page clock: `page.clock.install` before the
page loads, then `page.clock.pause_at` once the snapshot is shown (a page whose
clock is paused before its snapshot never leaves `connecting`), so that
`performance.now()` stops a few ms after the page anchored the timer.
`advance_clock` then moves it by hand, in small steps with a real pause between
them, so that the pong the mocked socket sends back to each of the page's
`ping` frames (spec 017) reaches the page before its next 4 s check. Nothing in
those tests depends on how fast the machine is.

The fixtures (`fx01_grid`, `dist_dir`, `registry`...) are defined in each test file
that needs them, as thin wrappers: a fixture imported from here would be an unused
import for ruff.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from typing import Any, NamedTuple

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    HelpMode,
    Join,
    LetterChanged,
    PlayerState,
    PlayerView,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
)
from nock.room import (
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
)
from spec017_harness import Peer
from spec024_harness import (
    FIRST_TOKEN,
    NOW,
    ROOM_CODE,
    SECOND_TOKEN,
    SNAPSHOT_RESUME_TOKEN,
    default_players,
    expect_seq,
)
from spec025_harness import MockRoomSocket

THIRD_TOKEN = "third-token-number-0003"
PAGE_TIMEOUT_MS = 10_000
QUIET_MS = 300
CLOCK_STEP_MS = 100
CLOCK_PAUSE_JUMP_MS = 50
POLL_MS = 25
DEFAULT_BUDGET = RevealBudget(letters=5, words=1)

# The WebSocket tests' room (spec 027, "Test harness"): the clock only moves when the
# test moves it, and no player is timed out for silence while it does.
TIMER_CONFIG = RoomConfig(
    tick_seconds=0.05, silence_timeout_seconds=3600, max_edits_per_second=1000
)

TIME_PATTERN = re.compile(r"^(?:(\d+):)?(\d+):(\d\d)$")


# ---- Rules ----


def join_new(
    state: RoomState,
    nickname: str,
    player_id: str,
    token: str,
    now: float,
) -> Outcome:
    """Join a new player with `join_room`.

    Args:
        state: The room.
        nickname: The new player's nickname.
        player_id: The id the new player gets.
        token: The resume token the new player gets.
        now: The clock time of the step.

    Returns:
        The outcome, whose reply is the new player's snapshot.
    """
    join = Join(nickname=nickname, resume_token=None)
    return join_room(state, join, now, player_id, token)


def rejoin(state: RoomState, nickname: str, token: str, now: float) -> Outcome:
    """Join again with a resume token.

    Args:
        state: The room.
        nickname: The nickname sent with the join.
        token: The player's resume token.
        now: The clock time of the step.

    Returns:
        The outcome, whose reply is the player's snapshot.
    """
    join = Join(nickname=nickname, resume_token=token)
    return join_room(state, join, now, "unused-new-id", "unused-new-token")


def room_with_players(grid: Grid, count: int) -> RoomState:
    """A FX-01 room created at NOW where `p1` (Ana) and, if asked, `p2` (Bob) joined.

    Args:
        grid: FX-01.
        count: 1 or 2 players, who all join at NOW.

    Returns:
        The room, at seq `count`.
    """
    state = new_room(ROOM_CODE, grid, NOW)
    state = join_new(state, "Ana", "p1", FIRST_TOKEN, NOW).state
    if count == 2:
        state = join_new(state, "Bob", "p2", SECOND_TOKEN, NOW).state
    assert state.seq == count
    return state


def type_letter(
    state: RoomState, player_id: str, row: int, column: int, letter: str, now: float
) -> Outcome:
    """Write a letter with `handle_message`, after checking it was accepted."""
    edit = EditLetter(row=row, column=column, letter=letter)
    outcome = handle_message(state, player_id, edit, now)
    assert outcome.reply == (), outcome.reply
    return outcome


def snapshot_in(outcome: Outcome) -> Snapshot:
    """The one snapshot a join answered with."""
    assert len(outcome.reply) == 1, outcome.reply
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot), snapshot
    return snapshot


def timer_fields(state: RoomState) -> tuple[bool, int, float | None]:
    """The three timer fields of a room: started, elapsed, resumed at."""
    return state.timer_started, state.timer_elapsed_ms, state.timer_resumed_at


# ---- The play of AC-6 and AC-7 ----


class PlayStep(NamedTuple):
    """One step of the play: the room after it and the entries it logged."""

    state: RoomState
    entries: tuple[LogEntry, ...]


class Play(NamedTuple):
    """The play of AC-6: every step, in order."""

    steps: list[PlayStep]

    @property
    def final(self) -> RoomState:
        """The room after the last step."""
        return self.steps[-1].state

    def state_after_seq(self, seq: int) -> RoomState:
        """The room after the step whose last entry has `seq`."""
        for step in self.steps:
            if step.state.seq == seq:
                return step.state
        pytest.fail(f"no step of the play ends at seq {seq}")

    def entries_up_to(self, seq: int) -> list[LogEntry]:
        """Every entry with a seq of at most `seq`, in order."""
        found: list[LogEntry] = []
        for step in self.steps:
            for entry in step.entries:
                if entry.event.seq <= seq:
                    found.append(entry)
        return found


FIRST_17 = [
    (1, 0, "T"),
    (1, 1, "A"),
    (1, 2, "M"),
    (1, 3, "I"),
    (1, 4, "S"),
    (0, 1, "N"),
    (2, 1, "V"),
    (3, 1, "A"),
    (4, 1, "L"),
    (2, 2, "I"),
    (3, 2, "M"),
    (4, 2, "E"),
    (2, 3, "D"),
    (3, 3, "E"),
    (4, 3, "S"),
    (2, 4, "E"),
    (3, 4, "N"),
]


def play_of_ac6(grid: Grid) -> Play:
    """The play of AC-6.

    Joins of `p1` and `p2` at NOW (seq 1 and 2); `p1` writes the 17 letters other
    than (4, 4) at NOW + 100.0 (seq 3 to 19); both disconnect at NOW + 160.0 (seq 20
    and 21); both join again with their tokens at NOW + 400.0 (seq 22 and 23); `p2`
    writes `T` at (4, 4) at NOW + 454.0 (seq 24 and 25).
    """
    steps: list[PlayStep] = []
    state = new_room(ROOM_CODE, grid, NOW)

    def keep(outcome: Outcome) -> RoomState:
        steps.append(PlayStep(outcome.state, outcome.entries))
        return outcome.state

    state = keep(join_new(state, "Ana", "p1", FIRST_TOKEN, NOW))
    state = keep(join_new(state, "Bob", "p2", SECOND_TOKEN, NOW))
    for row, column, letter in FIRST_17:
        state = keep(type_letter(state, "p1", row, column, letter, NOW + 100.0))
    state = keep(disconnect_player(state, "p1", NOW + 160.0))
    state = keep(disconnect_player(state, "p2", NOW + 160.0))
    state = keep(rejoin(state, "Ana", FIRST_TOKEN, NOW + 400.0))
    state = keep(rejoin(state, "Bob", SECOND_TOKEN, NOW + 400.0))
    assert state.seq == 23
    state = keep(type_letter(state, "p2", 4, 4, "T", NOW + 454.0))
    assert state.seq == 25
    return Play(steps)


def events_of(outcome: Outcome) -> list[object]:
    """The event of each log entry of a step, in order."""
    events: list[object] = []
    for entry in outcome.entries:
        events.append(entry.event)
    return events


# ---- WebSocket ----


def has_letter(peer: Peer, row: int, column: int) -> bool:
    """Whether a client received a `letter_changed` for a cell after its snapshot."""
    for event in peer.events():
        if not isinstance(event, LetterChanged):
            continue
        if (event.row, event.column) == (row, column):
            return True
    return False


def wait_until_disconnected(
    registry: RoomRegistry, code: str, player_id: str, timeout_seconds: float = 5.0
) -> None:
    """Wait until the registry's room holds `player_id` as disconnected, else fail."""
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        state = registry.room_state(code)
        assert state is not None
        for player in state.players:
            if (
                player.player_id == player_id
                and player.state == PlayerState.DISCONNECTED
            ):
                return
        time.sleep(0.02)
    pytest.fail(f"{player_id} was not seen disconnected in {timeout_seconds}s")


# ---- Reading the timer on a page ----


def clock_seconds(text: str) -> int:
    """The whole seconds a timer text shows: `1:05` is 65, `1:02:05` is 3725."""
    found = TIME_PATTERN.match(text.strip())
    assert found is not None, f"not a timer text: {text!r}"
    hours = int(found.group(1)) if found.group(1) is not None else 0
    return hours * 3600 + int(found.group(2)) * 60 + int(found.group(3))


def timer_of(page: Page) -> Locator:
    """The page's `timer` element."""
    return page.get_by_test_id("timer")


def elapsed_ms_of(page: Page) -> int:
    """The `data-elapsed-ms` of the page's timer, as a number."""
    value = timer_of(page).get_attribute("data-elapsed-ms")
    assert value is not None, "the timer has no data-elapsed-ms"
    assert re.fullmatch(r"\d+", value), f"data-elapsed-ms is {value!r}"
    return int(value)


def text_of(page: Page) -> str:
    """The text of the page's timer, without surrounding spaces."""
    return timer_of(page).inner_text().strip()


def local_storage_value(page: Page, key: str) -> str | None:
    """The value of a `localStorage` key of the page, None when absent."""
    value = page.evaluate("key => window.localStorage.getItem(key)", key)
    assert value is None or isinstance(value, str)
    return value


# ---- The page with a mocked socket ----


def timer_snapshot(
    grid: Grid,
    *,
    elapsed_ms: int,
    running: bool,
    solved: bool = False,
    seq: int = 5,
    players: list[PlayerView] | None = None,
) -> Snapshot:
    """A FX-01 snapshot for `p1` (host) with a chosen timer.

    Args:
        grid: FX-01.
        elapsed_ms: The snapshot's `timer_elapsed_ms`.
        running: The snapshot's `timer_running`.
        solved: The snapshot's `solved`.
        seq: The snapshot's seq.
        players: The roster (default: `p1` host and `p2`).

    Returns:
        The snapshot, help mode `free`, the default budget, no flag, chat or vote.
    """
    shown_players = default_players() if players is None else players
    return Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=grid_view(grid),
        players=tuple(shown_players),
        settings=RoomSettings(
            help_mode=HelpMode.FREE, reveal_budget=DEFAULT_BUDGET, locked=False
        ),
        reveal_budget=DEFAULT_BUDGET,
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=elapsed_ms,
        timer_running=running,
        solved=solved,
    )


def open_timer_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    elapsed_ms: int,
    running: bool,
    solved: bool = False,
    seq: int = 5,
    players: list[PlayerView] | None = None,
    frozen: bool = False,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, join as Ana and show a timer snapshot.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        grid: FX-01.
        elapsed_ms: The snapshot's `timer_elapsed_ms`.
        running: The snapshot's `timer_running`.
        solved: The snapshot's `solved`.
        seq: The snapshot's seq.
        players: The roster.
        frozen: Whether the page's clock is frozen when the snapshot arrives (see
            the module docstring); `advance_clock` then moves it.

    Returns:
        Spec 025's mocked socket: it answers each ping with a pong.
    """
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    if frozen:
        page.clock.install(time=0)
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana")
    nickname_input.press("Enter")
    mock.wait_for_join_on_socket(0)
    snapshot = timer_snapshot(
        grid,
        elapsed_ms=elapsed_ms,
        running=running,
        solved=solved,
        seq=seq,
        players=players,
    )
    mock.send(snapshot.model_dump_json())
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    if frozen:
        now_ms = page.evaluate("() => Date.now()")
        page.clock.pause_at(now_ms + CLOCK_PAUSE_JUMP_MS)
    return mock


def send_reconnect_snapshot(
    mock: MockRoomSocket, grid: Grid, socket_index: int, *, elapsed_ms: int
) -> None:
    """Wait for the join on a new socket of the page and answer it with a snapshot."""
    mock.wait_for_join_on_socket(socket_index)
    snapshot = timer_snapshot(grid, elapsed_ms=elapsed_ms, running=True)
    mock.send(snapshot.model_dump_json())


def advance_clock(page: Page, milliseconds: int) -> None:
    """Move a frozen page clock forward by hand, in steps of `CLOCK_STEP_MS`.

    Between two steps the test waits a real 10 ms, so that the mocked socket's
    pongs reach the page.
    """
    remaining = milliseconds
    while remaining > 0:
        step = min(CLOCK_STEP_MS, remaining)
        page.clock.run_for(step)
        page.wait_for_timeout(10)
        remaining -= step


def advance_until_text(page: Page, expected: str, limit_ms: int) -> int:
    """Advance a frozen clock until the timer reads `expected`.

    Args:
        page: The page, with a frozen clock.
        expected: The text the timer must read.
        limit_ms: The most the clock may move.

    Returns:
        How far the clock moved, in milliseconds. The test fails when the text is
        not there after `limit_ms`.
    """
    moved = 0
    while text_of(page) != expected:
        if moved >= limit_ms:
            pytest.fail(
                f"the timer reads {text_of(page)!r}, not {expected!r}, "
                f"after {moved} ms of the page's clock"
            )
        advance_clock(page, CLOCK_STEP_MS)
        moved += CLOCK_STEP_MS
    return moved


def new_context_page(browser: Browser) -> tuple[Page, Callable[[], None]]:
    """A 1280 by 720 page in a context of its own, and the function that closes it."""
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    page = context.new_page()
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    return page, context.close


def sent_frames(mock: MockRoomSocket) -> list[dict[str, Any]]:
    """Every frame the page sent, `ping` frames left out, as JSON objects."""
    found: list[dict[str, Any]] = []
    for frame in mock.frames_without_pings():
        parsed = json.loads(frame)
        assert isinstance(parsed, dict), frame
        found.append(parsed)
    return found
