"""Shared setup of the tests of gameplay/results about reading and keeping the recap
(AC-21 to AC-23).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_results_*.py`:

- `test_results_recap_kept.py`: AC-21 and AC-22, a solved FX-01 room that is only
  in the store (spec 028's `PLAY_R`: Ana and Bob joined and solved it, both still
  connected), read through the recap routes of an app on a registry over that store.
- `test_results_recap_after_changes.py`: AC-23, a room played over sockets with the
  app of `host_harness`, an account erased and a room deleted.

The room of `stored_solved_app` is room `ABC123` with the share token
`SHARE_TOKEN` (`spec028_harness`). Its snapshot at seq 34 is saved with both
players still connected, as a server stopped with their sockets open leaves it. The
registry reads `after_play_r` as its clock, so the room has not expired.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

from fastapi.testclient import TestClient

from host_harness import SOCKET_CONFIG
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter
from nock.server import create_app
from nock.store import RoomStore
from spec011_harness import make_dist_dir
from spec014_harness import Peer, ping_and_wait
from spec028_harness import ROW_MAJOR, SOLUTION, Game, after_play_r, stored_play_r

RECAP_LOG_LENGTH = 34  # the entries of `PLAY_R`
DATABASE_NAME = "rooms.db"


class StoredRoomApp(NamedTuple):
    """The app over a stored solved room, its registry and store, and the play."""

    client: TestClient
    registry: RoomRegistry
    store: RoomStore
    game: Game


@contextlib.contextmanager
def stored_solved_app(directory: Path, grid: Grid) -> Iterator[StoredRoomApp]:
    """Store `PLAY_R`'s room, then run an app on a new registry over its file.

    The registry and the store are closed when the block ends.
    """
    path = directory / DATABASE_NAME
    game = stored_play_r(path, grid)
    store = RoomStore(path)
    registry = RoomRegistry(clock=after_play_r, store=store, config=SOCKET_CONFIG)
    try:
        store.save_snapshot(game.state)
        app = create_app(rooms=registry, dist_dir=make_dist_dir(directory))
        with TestClient(app) as client:
            yield StoredRoomApp(client, registry, store, game)
    finally:
        registry.close()
        store.close()


def recap_route(code: str) -> str:
    """The path of a room's recap."""
    return f"/api/rooms/{code}/recap"


def shared_api_route(token: str) -> str:
    """The path of a share token's public recap."""
    return f"/api/recaps/{token}"


def shared_page_route(token: str) -> str:
    """The path of a share token's page."""
    return f"/recap/{token}"


def type_the_solution(peer: Peer) -> None:
    """Type the right letter of every cell from a peer, then wait for the room."""
    for row, column in ROW_MAJOR:
        letter = SOLUTION[(row, column)]
        peer.send(EditLetter(row=row, column=column, letter=letter))
    ping_and_wait(peer)
