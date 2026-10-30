"""Tests of platform/server, AC-25: a slow socket lookup delays no other request.

The registry of `server_harness.SlowConnectRegistry` takes a second to run
`connect` for one room, the lookup of a socket (rule 22). While that lookup waits,
`GET /api/grids` and a socket to another room, sent meanwhile, are answered within
200 ms; the first socket's join then gets its snapshot.

This file measures durations, so it runs on its own (`SERIAL_TEST_FILES`).

Readings of the spec's wording:

- "Meanwhile" is after the slow lookup began (`connect_started`) and before it
  ended: the first socket has no snapshot yet when the other two are answered.
- "Answered" for the second socket is its snapshot, from the opening of the socket
  to the snapshot of its join.
- Both requests are timed after a warm-up of the same requests, so that the
  first-use costs of the app (and of the engine thread) are not counted.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from host_harness import open_member
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Join, Snapshot
from nock.server import create_app
from server_harness import CONNECT_DELAY_SECONDS, SlowConnectRegistry
from spec011_harness import make_dist_dir
from spec014_harness import Peer, socket_url
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

ANSWER_LIMIT_SECONDS = 0.2
SLOW_START_LIMIT_SECONDS = 5.0
SNAPSHOT_LIMIT_SECONDS = CONNECT_DELAY_SECONDS + 5.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def has_snapshot(peer: Peer) -> bool:
    """Whether the peer received a snapshot."""
    return any(isinstance(message, Snapshot) for message in peer.messages())


def test_ac25_a_socket_whose_lookup_takes_a_second_delays_no_other_request(
    tmp_path: Path, fx01_grid: Grid, catalogue: Catalogue
) -> None:
    registry = SlowConnectRegistry()
    try:
        slow_code = registry.register_room(fx01_grid)
        other_code = registry.register_room(fx01_grid)
        registry.slow_codes.add(slow_code)
        app = create_app(
            rooms=registry, dist_dir=make_dist_dir(tmp_path), catalogue=catalogue
        )
        with TestClient(app) as client, ExitStack() as stack:
            client.get("/api/grids")
            with ExitStack() as warm_up_stack:
                open_member(warm_up_stack, client, other_code, "Zoe")

            websocket = stack.enter_context(
                client.websocket_connect(socket_url(slow_code))
            )
            slow = Peer(websocket)
            slow.send(Join(nickname="Ana", resume_token=None))
            assert registry.connect_started.wait(SLOW_START_LIMIT_SECONDS)

            started = time.perf_counter()
            grids = client.get("/api/grids")
            grids_seconds = time.perf_counter() - started

            started = time.perf_counter()
            open_member(stack, client, other_code, "Bob")
            other_socket_seconds = time.perf_counter() - started

            answered_meanwhile = has_snapshot(slow)
            slow.wait_until(
                lambda: has_snapshot(slow),
                "the snapshot of the first socket",
                timeout=SNAPSHOT_LIMIT_SECONDS,
            )
    finally:
        registry.close()

    assert grids.status_code == 200
    assert grids_seconds < ANSWER_LIMIT_SECONDS
    assert other_socket_seconds < ANSWER_LIMIT_SECONDS
    assert answered_meanwhile is False
