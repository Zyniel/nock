"""Tests of spec 038 (privacy and operations), AC-4: room data is gone at expiry.

The test reads `nock.sqlite3` and, when it exists, `nock.sqlite3-wal` from
`tmp_path` as bytes and searches them for UTF-8 strings, as the spec's "Test
harness" says (`database_bytes` and `strings_in` of `spec038_harness`).

Python: rooms A and B are played with the rules (spec 032's `Run`) and written to a
store file: their first state, their log and a snapshot of their last state. A's
code, `QJ7WXK`, occurs nowhere else in the file. A registry on conftest's fake
clock then expires A with `expire_rooms()`. WebSocket: spec 032 AC-2's setup (a
store file, `expiry_sweep_seconds=0.05`, Ana and Bob joined, Ana's `T`), plus a
chat; after `advance(LIFE + 1)` the app's sweep alone deletes the room.

Each test first checks that the strings it then expects gone are in the files,
so that it can only pass once they were written and then removed.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Generator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import CellTarget, Chat, ChatMessage, Check, EditLetter
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock, Peer, join_two
from spec032_harness import NO_TICK_CONFIG, T0, Run, make_dist_dir, sweeping_config
from spec038_harness import (
    DATABASE_FILE_NAME,
    DAY,
    LIFE,
    database_bytes,
    strings_in,
)

# ---- Values of the spec --------------------------------------------------------------

CODE_A = "QJ7WXK"  # occurs nowhere else in the file (see "Edge cases")
CODE_B = "HN4PRT"
SECRET_CHAT = "chat-secret-4711"  # Zélie's chat message in room A
KEPT_CHAT = "chat-kept-8203"  # room B's chat message
ZELIE = "Z\N{LATIN SMALL LETTER E WITH ACUTE}lie"  # her nickname as she types it
ZELIE_STORED = "Z\N{LATIN CAPITAL LETTER E WITH ACUTE}LIE"  # as the server stores it
ANA_STORED = "ANA"
BOB_STORED = "BOB"
YANN_STORED = "YANN"
ZELIE_TOKEN = "zelie-resume-token-0001"
BOB_TOKEN = "bob-resume-token-000002"
YANN_TOKEN = "yann-resume-token-00003"

# ---- Values of the test harness ------------------------------------------------------

SWEPT_CHAT = "chat-swept-6390"  # the chat of the WebSocket part
SWEEP_DEADLINE_SECONDS = 2.0  # "within 2 seconds of real time"
POLL_SECONDS = 0.05


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


# ---- Python: rooms A and B on a store file -------------------------------------------


def play_room_a(grid: Grid) -> Run:
    """Room A at t0: Zélie and Bob join, Zélie chats, two letters and a check.

    Its last edit is the check's lock, at t0 + 4.
    """
    room = Run(grid, code=CODE_A, grid_number=None, config=NO_TICK_CONFIG)
    room.join_new(ZELIE, "pZ", ZELIE_TOKEN, T0)
    room.join_new("Bob", "pB", BOB_TOKEN, T0)
    room.send("pZ", Chat(text=SECRET_CHAT), T0 + 1)
    room.send("pZ", EditLetter(row=1, column=0, letter="T"), T0 + 2)
    room.send("pB", EditLetter(row=1, column=1, letter="X"), T0 + 3)
    room.send("pB", Check(target=CellTarget(row=1, column=0)), T0 + 4)
    return room


def play_room_b(grid: Grid) -> Run:
    """Room B: Yann joins and chats at t0, and writes a letter two days later."""
    room = Run(grid, code=CODE_B, grid_number=None, config=NO_TICK_CONFIG)
    room.join_new("Yann", "pY", YANN_TOKEN, T0)
    room.send("pY", Chat(text=KEPT_CHAT), T0 + 1)
    room.send("pY", EditLetter(row=1, column=0, letter="T"), T0 + 2 * DAY)
    return room


def write_room(store: RoomStore, room: Run) -> None:
    """Write a played room to the store: first state, log, then its last state."""
    store.create_room(room.initial)
    store.append(room.initial.code, room.log)
    store.save_snapshot(room.state)


def room_a_strings() -> list[str]:
    """What must leave the files with room A."""
    return [SECRET_CHAT, ZELIE_STORED, BOB_STORED, CODE_A, ZELIE_TOKEN, BOB_TOKEN]


def room_b_strings() -> list[str]:
    """What must stay in the files with room B."""
    return [KEPT_CHAT, YANN_STORED]


class ExpiredFile(NamedTuple):
    """What the Python part saw: the files before, then after A's expiry."""

    before: bytes
    expired: list[str]
    after: bytes


@contextlib.contextmanager
def room_a_expired(
    path: Path, grid: Grid, clock: FakeClock
) -> Generator[tuple[ExpiredFile, RoomStore, RoomRegistry]]:
    """Write rooms A and B to `path`, then expire A, the store still open.

    Yields what the files held before and after the expiry, the store and the
    registry; both are closed at the end.
    """
    room_a = play_room_a(grid)
    room_b = play_room_b(grid)
    assert room_a.state.players[0].nickname == ZELIE_STORED
    assert room_b.state.players[0].nickname == YANN_STORED
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store, config=NO_TICK_CONFIG)
    try:
        write_room(store, room_a)
        write_room(store, room_b)
        before = database_bytes(path)
        last_edit_at = store.last_edit_at(CODE_A)
        assert last_edit_at is not None
        clock.now = last_edit_at + LIFE + 1  # A expires; B, edited later, does not
        expired = registry.expire_rooms()
        after = database_bytes(path)
        yield ExpiredFile(before=before, expired=expired, after=after), store, registry
    finally:
        registry.close()
        store.close()


def test_ac4_python_expire_rooms_returns_room_a_only(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / DATABASE_FILE_NAME

    with room_a_expired(path, fx01_grid, fake_clock) as (seen, store, _):
        assert seen.expired == [CODE_A]
        assert store.has_room(CODE_B)


def test_ac4_python_with_the_store_open_no_byte_of_room_a_remains(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / DATABASE_FILE_NAME

    with room_a_expired(path, fx01_grid, fake_clock) as (seen, _, _):
        assert strings_in(seen.before, room_a_strings()) == room_a_strings()
        assert seen.expired == [CODE_A]
        assert strings_in(seen.after, room_a_strings()) == []


def test_ac4_python_with_the_store_open_room_b_stays(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / DATABASE_FILE_NAME

    with room_a_expired(path, fx01_grid, fake_clock) as (seen, _, _):
        assert strings_in(seen.after, room_b_strings()) == room_b_strings()


def test_ac4_python_once_the_store_is_closed_no_byte_of_room_a_remains(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / DATABASE_FILE_NAME

    with room_a_expired(path, fx01_grid, fake_clock) as (seen, _, _):
        assert seen.expired == [CODE_A]
    closed = database_bytes(path)

    assert strings_in(closed, room_a_strings()) == []
    assert strings_in(closed, room_b_strings()) == room_b_strings()


def test_ac4_python_room_a_stays_deleted_in_a_new_store_on_the_file(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    # Edge case "Restart after a crash": the deletion is committed.
    path = tmp_path / DATABASE_FILE_NAME
    with room_a_expired(path, fx01_grid, fake_clock):
        pass

    store = RoomStore(path)
    try:
        has_a = store.has_room(CODE_A)
        log_of_a = store.read_log(CODE_A)
        has_b = store.has_room(CODE_B)
    finally:
        store.close()

    assert (has_a, log_of_a, has_b) == (False, [], True)


# ---- WebSocket: the sweep alone deletes the room -------------------------------------


class SweptRoom(NamedTuple):
    """The strings of the swept room, and what the files held before and after."""

    strings: list[str]
    before: bytes
    after: bytes


def has_chat(peer: Peer, text: str) -> bool:
    for message in peer.events():
        if isinstance(message, ChatMessage) and message.text == text:
            return True
    return False


def has_letter(peer: Peer) -> bool:
    return any(message.type == "letter_changed" for message in peer.events())


def bytes_once_gone(path: Path, strings: list[str]) -> bytes:
    """The files' bytes once they hold none of `strings`, or at the 2 s deadline."""
    deadline = time.monotonic() + SWEEP_DEADLINE_SECONDS
    data = database_bytes(path)
    while strings_in(data, strings) != [] and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        data = database_bytes(path)
    return data


def sweep_a_room_with_a_chat(
    path: Path, grid: Grid, clock: FakeClock, dist_dir: Path
) -> SweptRoom:
    """Spec 032 AC-2's run with a chat, up to 2 s after `advance(LIFE + 1)`."""
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store, config=sweeping_config())
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client, contextlib.ExitStack() as stack:
            ana, bob = join_two(stack, stack, client, code)
            ana.send(EditLetter(row=1, column=0, letter="T"))
            bob.wait_until(lambda: has_letter(bob), "Ana's T on Bob")
            ana.send_raw(Chat(text=SWEPT_CHAT).model_dump_json())
            bob.wait_until(lambda: has_chat(bob, SWEPT_CHAT), "Ana's chat on Bob")
            ana.wait_until(lambda: has_chat(ana, SWEPT_CHAT), "Ana's chat on Ana")
            tokens = [ana.snapshot().resume_token, bob.snapshot().resume_token]
            strings = [SWEPT_CHAT, ANA_STORED, BOB_STORED, code, *tokens]
            before = database_bytes(path)

            clock.advance(LIFE + 1)
            after = bytes_once_gone(path, strings)
    finally:
        registry.close()
        store.close()
    return SweptRoom(strings=strings, before=before, after=after)


def test_ac4_websocket_the_sweep_leaves_no_byte_of_the_room_within_2_seconds(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    path = tmp_path / DATABASE_FILE_NAME
    dist_dir = make_dist_dir(tmp_path)

    swept = sweep_a_room_with_a_chat(path, fx01_grid, fake_clock, dist_dir)

    assert strings_in(swept.before, swept.strings) == swept.strings
    assert strings_in(swept.after, swept.strings) == []
