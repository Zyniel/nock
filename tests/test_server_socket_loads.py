"""Tests of platform/server, AC-26: a socket's lookup loads its room once.

Over the room socket of an app on a store of `server_harness.CountingStore`, which
records each `load_room` read that found a room. Rooms are created over HTTP, so
they are in the store and not in memory until a socket comes.

Readings of the spec's wording:

- "One `load_room` read for that socket" is one recorded read of the room's code
  from the opening of the socket to its snapshot.
- "Loads nothing" is no recorded read: a read of an unknown code finds no room, so
  an implementation that asks the store about `ZZZZZZ` and gets nothing loads
  nothing either.
- "With its restart step" has no outside sign when the room has no connected
  player (rule 21: the restart step logs nothing then); the test checks that the
  room is live and serves the join.
"""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path

import pytest

from host_harness import SOCKET_CONFIG, open_member
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Join
from server_harness import CountingStore, serving
from spec014_harness import Peer, socket_url
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import DATABASE_FILE_NAME

GRID_NUMBER = 1  # the number of the grid of `spec024_harness.make_catalogue`
UNKNOWN_CODE = "ZZZZZZ"
ROOM_NOT_FOUND_CLOSE_CODE = 4404


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def test_ac26_a_socket_to_a_room_not_in_memory_loads_it_once_and_a_second_loads_nothing(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = CountingStore(tmp_path / DATABASE_FILE_NAME)
    try:
        with (
            serving(store, fake_clock, catalogue, SOCKET_CONFIG) as (client, registry),
            ExitStack() as stack,
        ):
            code = client.post("/api/rooms", json={"grid_number": GRID_NUMBER}).json()[
                "code"
            ]
            live_before = registry.live_codes()
            store.loaded.clear()

            open_member(stack, client, code, "Ana")
            loaded_by_the_first = list(store.loaded)
            live_with_the_first = registry.live_codes()

            open_member(stack, client, code, "Bob")
            loaded_after_the_second = list(store.loaded)
    finally:
        store.close()

    assert live_before == frozenset()
    assert loaded_by_the_first == [code]
    assert live_with_the_first == frozenset({code})
    assert loaded_after_the_second == [code]


def test_ac26_a_socket_to_an_unknown_room_loads_nothing_and_closes_with_4404(
    tmp_path: Path, fake_clock: FakeClock, catalogue: Catalogue
) -> None:
    store = CountingStore(tmp_path / DATABASE_FILE_NAME)
    try:
        with (
            serving(store, fake_clock, catalogue, SOCKET_CONFIG) as (client, registry),
            ExitStack() as stack,
        ):
            websocket = stack.enter_context(
                client.websocket_connect(socket_url(UNKNOWN_CODE))
            )
            peer = Peer(websocket)
            peer.send(Join(nickname="Ana", resume_token=None))
            peer.wait_until(lambda: peer.close_code is not None, "the close")
            close_code = peer.close_code
            messages = peer.messages()
            live = registry.live_codes()
    finally:
        store.close()

    assert close_code == ROOM_NOT_FOUND_CLOSE_CODE
    assert messages == []
    assert store.loaded == []
    assert live == frozenset()
