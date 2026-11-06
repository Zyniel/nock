"""Tests of `platform/reconnection.md` AC-9: a hidden page whose own timers stop.

Rule 3. Ana's page joins a room of the live server, is hidden (`VISIBILITY_SCRIPT`,
`set_page_hidden`), then its own timers stop: Playwright's page clock, installed
before the page loads, is paused (spec 027's `freeze_clock`) and stays paused for
the 10 seconds. That clock does not reach a dedicated worker, whose timer keeps
real time.

What is observed, over 10 seconds of real time from the pause:

- The page's pings: every frame the page sends on its room socket, seen by
  Playwright (`framesent`) and timed by the test as it arrives. "Every 2 seconds"
  is read as: the first ping comes at most 2 seconds after the pause, each later
  one 2 seconds after the one before, and the last one at most 2 seconds before
  the end, each within `PACE_TOLERANCE_SECONDS`.
- "The server never closes it with 4408" (`platform/realtime.md` rule 16): the
  page's room socket is never closed, the page opens no other one, and the server
  never reads Ana as disconnected (`RoomRegistry.peek_room`, read after every
  step of `STEP_MS`).

The test measures a pace in real time, so this file runs on its own
(`SERIAL_TEST_FILES` in `scripts/gate_browsers.py`).
"""

from __future__ import annotations

import itertools
import time
from typing import NamedTuple

from playwright.sync_api import Page, WebSocket

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Ping, PlayerState, parse_client_message
from reconnection_harness import VISIBILITY_SCRIPT, set_page_hidden
from spec024_harness import EnterRoom
from spec027_harness import freeze_clock

OBSERVED_SECONDS = 10.0  # how long the page's own timers stay stopped
PING_INTERVAL_SECONDS = 2.0
PACE_TOLERANCE_SECONDS = 0.5
STEP_MS = 100  # the real pause between two readings of the server's state


class RoomSockets:
    """The room sockets a page opens: how many, the pings it sends, the closes.

    Attributes:
        opened: How many room sockets the page opened.
        ping_times: The `time.monotonic()` at which each `ping` the page sent on a
            room socket reached the test, in order.
        closes: How many of the page's room sockets were closed.
    """

    def __init__(self, page: Page) -> None:
        self.opened = 0
        self.ping_times: list[float] = []
        self.closes = 0
        page.on("websocket", self._on_socket)

    def _on_socket(self, websocket: WebSocket) -> None:
        if not websocket.url.endswith("/ws"):
            return
        self.opened += 1
        websocket.on("framesent", self._on_frame)
        websocket.on("close", self._on_close)

    def _on_frame(self, payload: str | bytes) -> None:
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if parse_client_message(payload) == Ping():
            self.ping_times.append(time.monotonic())

    def _on_close(self, _websocket: WebSocket) -> None:
        self.closes += 1


class Watch(NamedTuple):
    """What the test saw while the page's own timers were stopped.

    Attributes:
        started_at: The `time.monotonic()` at which the 10 seconds began.
        ended_at: The `time.monotonic()` at which they ended.
        disconnected_readings: How many readings of the server's state found
            Ana disconnected.
    """

    started_at: float
    ended_at: float
    disconnected_readings: int


def is_disconnected(registry: RoomRegistry, code: str, player_id: str) -> bool:
    """Whether the server reads the player as disconnected now."""
    state = registry.peek_room(code)
    assert state is not None, f"room {code} is gone"
    for player in state.players:
        if player.player_id == player_id:
            return player.state == PlayerState.DISCONNECTED
    raise AssertionError(f"no player {player_id} in room {code}")


def watch_for(
    page: Page, registry: RoomRegistry, code: str, player_id: str, seconds: float
) -> Watch:
    """Let `seconds` of real time pass, reading the player's state at each step.

    Args:
        page: The page, whose events Playwright delivers while the test waits.
        registry: The live server's rooms.
        code: The room's code.
        player_id: The player whose state is read.
        seconds: How long to watch.

    Returns:
        When the watch began and ended, and how often the player was disconnected.
    """
    started_at = time.monotonic()
    ends_at = started_at + seconds
    disconnected_readings = 0
    while time.monotonic() < ends_at:
        page.wait_for_timeout(STEP_MS)
        if is_disconnected(registry, code, player_id):
            disconnected_readings += 1
    return Watch(started_at, time.monotonic(), disconnected_readings)


def pace_problems(
    ping_times: list[float], started_at: float, ended_at: float
) -> list[str]:
    """How the pings sent between `started_at` and `ended_at` miss a 2-second pace.

    Returns:
        One line per gap out of bounds: from the start to the first ping and from
        the last ping to the end at most 2 seconds, between two pings 2 seconds,
        each within `PACE_TOLERANCE_SECONDS`. Empty when the pace holds.
    """
    longest = PING_INTERVAL_SECONDS + PACE_TOLERANCE_SECONDS
    shortest = PING_INTERVAL_SECONDS - PACE_TOLERANCE_SECONDS
    pings: list[float] = []
    for sent_at in ping_times:
        if started_at <= sent_at <= ended_at:
            pings.append(sent_at - started_at)
    problems: list[str] = []
    if not pings:
        return [f"no ping in the {ended_at - started_at:.1f} s"]
    if pings[0] > longest:
        problems.append(f"the first ping came {pings[0]:.2f} s after the pause")
    for earlier, later in itertools.pairwise(pings):
        gap = later - earlier
        if not shortest <= gap <= longest:
            problems.append(f"a ping at {later:.2f} s came {gap:.2f} s after the last")
    last_gap = (ended_at - started_at) - pings[-1]
    if last_gap > longest:
        problems.append(f"no ping in the last {last_gap:.2f} s")
    return problems


def test_ac9_a_hidden_page_whose_own_timers_stop_pings_every_2_s_and_stays_open(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    page.add_init_script(VISIBILITY_SCRIPT)
    sockets = RoomSockets(page)
    page.clock.install()
    enter_room(page, f"{live_server}/r/{code}", "Ana")
    ana_id = page.get_by_test_id("room-page").get_attribute("data-you")
    assert ana_id, "the joined page names no player of its own"

    set_page_hidden(page, True)
    freeze_clock(page)
    watch = watch_for(page, room_registry, code, ana_id, OBSERVED_SECONDS)

    assert pace_problems(sockets.ping_times, watch.started_at, watch.ended_at) == []
    assert sockets.closes == 0
    assert sockets.opened == 1
    assert watch.disconnected_readings == 0
