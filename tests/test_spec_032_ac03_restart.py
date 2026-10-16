"""Tests of spec 032, AC-3 over the room socket: the room the next day, on another
device, after a restart.

Process one (a store file, conftest's fake clock, a registry and an app): a FX-01
room is registered at t0; Ana joins at t0, writes `T` at (1, 0) at t0 + 10 and `A`
at (1, 1) at t0 + 20, reveals the letter (4, 4) at t0 + 30 (spec 024), and her
socket closes at t0 + 100; process one stops. Process two starts on the same file
with the same clock object, moved to t0 + 100 + DAY. A client with no token
(another device) joins as Bob; then a client with Ana's token (her device) joins:
she timed out (at the first tick of the room's new task, or in her join), so she
is seated back (AC-7). The timer ran from the first letter, at t0 + 10, until
nobody was connected, at t0 + 100: 90 seconds (spec 027).

The browser part of AC-3 is in `test_spec_032_ac03_ac05_live_pages.py`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellTarget,
    EditLetter,
    LetterChanged,
    PlayerState,
    Reveal,
    RevealBudget,
    Snapshot,
)
from nock.room import RoomState, grid_state
from spec017_harness import FakeClock, Peer, open_peer
from spec018_harness import Process, wait_for
from spec032_harness import (
    DAY,
    SEAT_BACK_CONFIG,
    T0,
    grid_from_text,
    make_dist_dir,
    snapshot_cell,
)

TIMER_MS = 90_000  # from the first letter (t0 + 10) to the last leave (t0 + 100)
TIMER_TOLERANCE_MS = 1_000


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


class NextDay(NamedTuple):
    """What the test knows of the room after the restart."""

    left_by_process_one: RoomState  # the room's state when process one stopped
    ana_id: str
    bob: Snapshot  # the snapshot of the other device
    ana: Snapshot  # the snapshot of Ana's device, with her token


def has_seq(peer: Peer, seq: int) -> bool:
    for message in peer.events():
        if isinstance(message, LetterChanged | CellLocked) and message.seq >= seq:
            return True
    return False


def ana_is_disconnected(process: Process, code: str) -> bool:
    state = process.registry.room_state(code)
    if state is None:
        return False
    return state.players[0].state is PlayerState.DISCONNECTED


def play_day_one(
    process: Process, clock: FakeClock, grid: Grid
) -> tuple[str, str, str, RoomState]:
    """Process one's day: return the code, Ana's id and token, the last state."""
    clock.now = T0
    code = process.registry.register_room(grid)
    with TestClient(process.app) as client, contextlib.ExitStack() as stack:
        ana = open_peer(stack, client, code, "Ana")
        ana_id = ana.snapshot().you
        ana_token = ana.snapshot().resume_token
        clock.now = T0 + 10
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.wait_until(lambda: has_seq(ana, 2), "Ana's T")
        clock.now = T0 + 20
        ana.send(EditLetter(row=1, column=1, letter="A"))
        ana.wait_until(lambda: has_seq(ana, 3), "Ana's A")
        clock.now = T0 + 30
        ana.send_raw(Reveal(target=CellTarget(row=4, column=4)).model_dump_json())
        ana.wait_until(lambda: has_seq(ana, 5), "the reveal of (4, 4)")
        clock.now = T0 + 100
        stack.close()
        wait_for(lambda: ana_is_disconnected(process, code), "Ana's leave")
        last_state = process.registry.room_state(code)
    assert last_state is not None
    return code, ana_id, ana_token, last_state


@pytest.fixture
def next_day(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> NextDay:
    path = tmp_path / "nock.sqlite3"
    one = Process(path, dist_dir, SEAT_BACK_CONFIG, clock=fake_clock)
    try:
        code, ana_id, ana_token, left = play_day_one(one, fake_clock, fx01_grid)
    finally:
        one.shutdown()

    fake_clock.now = T0 + 100 + DAY
    two = Process(path, dist_dir, SEAT_BACK_CONFIG, clock=fake_clock)
    try:
        with TestClient(two.app) as client, contextlib.ExitStack() as stack:
            bob = open_peer(stack, client, code, "Bob")
            ana = open_peer(stack, client, code, "Ana", ana_token)
            bob_snapshot = bob.snapshot()
            ana_snapshot = ana.snapshot()
    finally:
        two.shutdown()
    return NextDay(left, ana_id, bob_snapshot, ana_snapshot)


def test_ac3_websocket_another_device_gets_the_grid_the_room_kept(
    next_day: NextDay,
) -> None:
    assert next_day.bob.grid == grid_state(next_day.left_by_process_one)


def test_ac3_websocket_the_letters_keep_their_author_and_the_reveal_its_lock(
    next_day: NextDay,
) -> None:
    first = snapshot_cell(next_day.bob, 1, 0)
    second = snapshot_cell(next_day.bob, 1, 1)
    revealed = snapshot_cell(next_day.bob, 4, 4)

    assert (first.letter, first.author) == ("T", next_day.ana_id)
    assert (second.letter, second.author) == ("A", next_day.ana_id)
    assert (revealed.letter, revealed.locked, revealed.revealed) == ("T", True, True)


def test_ac3_websocket_another_device_gets_the_hint_budget_left(
    next_day: NextDay,
) -> None:
    assert next_day.bob.reveal_budget == RevealBudget(letters=4, words=1)


def test_ac3_websocket_another_device_gets_the_time_counted_while_someone_was_there(
    next_day: NextDay,
) -> None:
    assert abs(next_day.bob.timer_elapsed_ms - TIMER_MS) <= TIMER_TOLERANCE_MS


def test_ac3_websocket_the_first_device_gets_its_player_back_the_next_day(
    next_day: NextDay,
) -> None:
    assert next_day.ana.you == next_day.ana_id


def test_ac3_websocket_the_first_device_gets_the_same_grid_budget_and_timer(
    next_day: NextDay,
) -> None:
    assert next_day.ana.grid == next_day.bob.grid
    assert next_day.ana.reveal_budget == next_day.bob.reveal_budget
    timer_gap = abs(next_day.ana.timer_elapsed_ms - next_day.bob.timer_elapsed_ms)
    assert timer_gap <= TIMER_TOLERANCE_MS
