"""Tests of lobby/lifetime, AC-14 and AC-15: the expiry read again under the lock.

A room is read as expired, then an edit is committed, then the registry takes its
lock to delete it: the deletion has to read the times again and keep the room.
The shared setup is in `lifetime_harness`: a store (`EditingStore`) that runs an
action right after the first read of the times, so that Ana's letter, typed over
her open socket, is committed exactly between that read and the lock.

- AC-14: the lookup is a socket of Bob's to the room (`RoomRegistry.connect`).
- AC-15: the lookup is the sweep, `RoomRegistry.expire_rooms()`.

Readings of the spec's wording:

- "Live" is a room with a joined player's socket open; the clock moves past the
  room's life while the sockets stay open (quiet rules, so that only the clock's
  move expires the room).
- "Serves A with her letter": Bob's join gets a snapshot that shows Ana's letter.
- Each criterion has a second test without Ana's letter, as the spec's second
  half says: the lookup, or the sweep, then deletes the room and closes its
  sockets with 4404. It already holds today and guards the rule's other side.
- The hook runs in the thread that reads the times (a worker thread for a
  socket's lookup, the test's thread for the sweep).
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from host_harness import open_member, wait_for_message
from lifetime_harness import (
    HOUR,
    EditingStore,
    config_with_lives,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import EditLetter, Join, LetterCellView, LetterChanged, Snapshot
from rooms_harness import create_room_code
from server_harness import serving
from spec014_harness import Peer, socket_url
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import DATABASE_FILE_NAME

ROOM_NOT_FOUND_CLOSE_CODE = 4404
LIFE_HOURS = 24
PAST_THE_LIFE_SECONDS = LIFE_HOURS * HOUR + 1
LETTER_ROW = 1
LETTER_COLUMN = 0
LETTER = "T"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def type_the_letter(player: Peer) -> None:
    """Ana types her letter and waits until the room announced it.

    The room commits an edit to the store before it announces it, so the letter
    is stored once this returns.
    """
    player.send(EditLetter(row=LETTER_ROW, column=LETTER_COLUMN, letter=LETTER))
    wait_for_message(player, LetterChanged)


def letter_in(snapshot: Snapshot) -> str | None:
    """The letter that a snapshot shows at the cell of Ana's letter."""
    for cell in snapshot.grid.cells:
        if not isinstance(cell, LetterCellView):
            continue
        if (cell.row, cell.column) == (LETTER_ROW, LETTER_COLUMN):
            return cell.letter
    pytest.fail("no letter cell at the position of Ana's letter in the snapshot")


def join_or_be_closed(stack: ExitStack, client: TestClient, code: str) -> Peer:
    """Open a socket, join as Bob, and return once a snapshot or a close came."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    bob = Peer(websocket)
    bob.send(Join(nickname="Bob", resume_token=None))
    bob.wait_until(
        lambda: bob.close_code is not None
        or any(isinstance(m, Snapshot) for m in bob.messages()),
        "Bob's snapshot or his close",
    )
    return bob


# ---- AC-14: a lookup ---------------------------------------------------------------


def test_ac14_a_lookup_keeps_the_room_when_a_letter_lands_before_its_lock(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = EditingStore(tmp_path / DATABASE_FILE_NAME)
    config = config_with_lives(anonymous=LIFE_HOURS)
    try:
        with (
            serving(store, fake_clock, catalogue, config) as (client, registry),
            ExitStack() as stack,
        ):
            code = create_room_code(client)
            ana = open_member(stack, client, code, "Ana")
            fake_clock.advance(PAST_THE_LIFE_SECONDS)
            store.after_next_read = lambda: type_the_letter(ana)

            bob = join_or_be_closed(stack, client, code)

            bob_snapshot = bob.snapshot()
            bob_close_code = bob.close_code
            ana_close_code = ana.close_code
            stored = store.has_room(code)
            live = registry.live_codes()
    finally:
        store.close()

    assert letter_in(bob_snapshot) == LETTER
    assert bob_close_code is None
    assert ana_close_code is None
    assert stored is True
    assert live == frozenset({code})


def test_ac14_a_lookup_deletes_the_expired_room_when_no_letter_lands(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = EditingStore(tmp_path / DATABASE_FILE_NAME)
    config = config_with_lives(anonymous=LIFE_HOURS)
    try:
        with (
            serving(store, fake_clock, catalogue, config) as (client, registry),
            ExitStack() as stack,
        ):
            code = create_room_code(client)
            ana = open_member(stack, client, code, "Ana")
            fake_clock.advance(PAST_THE_LIFE_SECONDS)

            bob = join_or_be_closed(stack, client, code)

            ana.wait_until(lambda: ana.close_code is not None, "Ana's close")
            bob_close_code = bob.close_code
            ana_close_code = ana.close_code
            stored = store.has_room(code)
            live = registry.live_codes()
    finally:
        store.close()

    assert bob_close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert ana_close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert stored is False
    assert live == frozenset()


# ---- AC-15: the sweep --------------------------------------------------------------


def test_ac15_the_sweep_keeps_the_room_where_a_letter_landed_after_its_read(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = EditingStore(tmp_path / DATABASE_FILE_NAME)
    config = config_with_lives(anonymous=LIFE_HOURS)
    try:
        with (
            serving(store, fake_clock, catalogue, config) as (client, registry),
            ExitStack() as stack,
        ):
            code_a = create_room_code(client)
            code_b = create_room_code(client)
            bob = open_member(stack, client, code_a, "Bob")
            ana = open_member(stack, client, code_b, "Ana")
            fake_clock.advance(PAST_THE_LIFE_SECONDS)
            store.after_next_read = lambda: type_the_letter(ana)

            deleted = registry.expire_rooms()

            bob.wait_until(lambda: bob.close_code is not None, "Bob's close")
            bob_close_code = bob.close_code
            ana_close_code = ana.close_code
            a_stored = store.has_room(code_a)
            b_stored = store.has_room(code_b)
            b_state = registry.peek_room(code_b)
    finally:
        store.close()

    assert deleted == [code_a]
    assert bob_close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert ana_close_code is None
    assert a_stored is False
    assert b_stored is True
    assert b_state is not None
    letters = []
    for cell in b_state.cells:
        if (cell.row, cell.column) == (LETTER_ROW, LETTER_COLUMN):
            letters.append(cell.letter)
    assert letters == [LETTER]


def test_ac15_the_sweep_deletes_both_rooms_when_no_letter_lands(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = EditingStore(tmp_path / DATABASE_FILE_NAME)
    config = config_with_lives(anonymous=LIFE_HOURS)
    try:
        with (
            serving(store, fake_clock, catalogue, config) as (client, registry),
            ExitStack() as stack,
        ):
            code_a = create_room_code(client)
            code_b = create_room_code(client)
            bob = open_member(stack, client, code_a, "Bob")
            ana = open_member(stack, client, code_b, "Ana")
            fake_clock.advance(PAST_THE_LIFE_SECONDS)

            deleted = registry.expire_rooms()

            bob.wait_until(lambda: bob.close_code is not None, "Bob's close")
            ana.wait_until(lambda: ana.close_code is not None, "Ana's close")
            bob_close_code = bob.close_code
            ana_close_code = ana.close_code
            stored = [store.has_room(code_a), store.has_room(code_b)]
    finally:
        store.close()

    assert deleted == sorted([code_a, code_b])
    assert bob_close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert ana_close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert stored == [False, False]
