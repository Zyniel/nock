"""Tests of platform/realtime, AC-21: the deadline of a socket that does not join.

A registry on the real clock with `join_timeout_seconds` 0.5, served by the app
over the real WebSocket. The deadline is counted by the socket's own connection,
on real time, so the tests wait in real time with bounds.

This file measures time windows (a socket that is silent for 0.5 s, one that is
spoken to every 0.3 s for 2 s), so it runs on its own (`SERIAL_TEST_FILES`).

Readings of the spec's wording:

- "Within 1.5 seconds": from the opening of the socket to its close, the close
  code is 4408 and nothing was received.
- "A `ping`, an invalid frame or a join as `A`": one frame every 0.3 s, the first
  at once, for 2 seconds. The invalid frame is the text `not json`; the join as
  `A` is a join whose nickname is too short, so the room never accepts it. The
  server answers each frame; the answers are not looked at.
- "Its join as `Ana` then gets a snapshot": sent right after the 2 seconds.
- "Once joined, Ana's silence is the 6 seconds of AC-15": the rule's value is
  `silence_timeout_seconds`, given 2 s here to keep the test short. Ana joins and
  says nothing: she is still open 1.2 s later, well past the join deadline, and
  closed with 4408 when her silence reaches 2 s.
"""

from __future__ import annotations

import time
from contextlib import ExitStack
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lifetime_harness import variables_of
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Ping, Snapshot
from nock.room import RoomConfig
from nock.server import create_app
from realtime_harness import SILENT_CLOSE_CODE, open_socket
from spec011_harness import make_dist_dir
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

JOIN_TIMEOUT_SECONDS = 0.5
CLOSE_LIMIT_SECONDS = 1.5
FRAME_INTERVAL_SECONDS = 0.3
FRAME_COUNT = 7  # one at once, then every 0.3 s: the last one 1.8 s after the first
SILENCE_TIMEOUT_SECONDS = 2.0
STILL_OPEN_AFTER_SECONDS = 1.2
SILENCE_CLOSE_LIMIT_SECONDS = 4.0
JOIN_AS_ANA = '{"type": "join", "nickname": "Ana", "resume_token": null}'
FRAMES = {
    "ping": Ping().model_dump_json(),
    "invalid-frame": "not json",
    "refused-join": '{"type": "join", "nickname": "A", "resume_token": null}',
}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def serve_room(
    registry: RoomRegistry,
    fx01_grid: Grid,
    catalogue: Catalogue,
    directory: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[TestClient, str]:
    """An app on `registry` (not entered yet) and the code of a room of FX-01."""
    variables_of(monkeypatch, {})
    code = registry.register_room(fx01_grid)
    app = create_app(
        rooms=registry, dist_dir=make_dist_dir(directory), catalogue=catalogue
    )
    return TestClient(app), code


def test_ac21_a_socket_that_sends_nothing_is_closed_with_4408_within_1_5_seconds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    catalogue: Catalogue,
) -> None:
    registry = RoomRegistry(
        config=RoomConfig(join_timeout_seconds=JOIN_TIMEOUT_SECONDS)
    )
    try:
        test_client, code = serve_room(
            registry, fx01_grid, catalogue, tmp_path, monkeypatch
        )
        with test_client as client, ExitStack() as stack:
            silent = open_socket(client, code, stack)
            silent.peer.wait_until(
                lambda: silent.peer.close_code is not None,
                "the close of the silent socket",
                timeout=CLOSE_LIMIT_SECONDS,
            )
            close_code = silent.peer.close_code
            messages = silent.peer.messages()
    finally:
        registry.close()

    assert close_code == SILENT_CLOSE_CODE
    assert messages == []


@pytest.mark.parametrize("frame", FRAMES.values(), ids=FRAMES.keys())
def test_ac21_a_socket_that_keeps_sending_frames_stays_open_and_can_join(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    catalogue: Catalogue,
    frame: str,
) -> None:
    registry = RoomRegistry(
        config=RoomConfig(join_timeout_seconds=JOIN_TIMEOUT_SECONDS)
    )
    try:
        test_client, code = serve_room(
            registry, fx01_grid, catalogue, tmp_path, monkeypatch
        )
        with test_client as client, ExitStack() as stack:
            talking = open_socket(client, code, stack)
            for _ in range(FRAME_COUNT):
                talking.websocket.send_text(frame)
                time.sleep(FRAME_INTERVAL_SECONDS)
            close_code_before_joining = talking.peer.close_code
            talking.websocket.send_text(JOIN_AS_ANA)
            talking.peer.wait_until(
                lambda: any(isinstance(m, Snapshot) for m in talking.peer.messages()),
                "the snapshot of Ana",
            )
            close_code_after_joining = talking.peer.close_code
    finally:
        registry.close()

    assert close_code_before_joining is None
    assert close_code_after_joining is None


def test_ac21_once_joined_the_silence_of_the_player_is_the_one_of_the_room(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    catalogue: Catalogue,
) -> None:
    config = RoomConfig(
        tick_seconds=0.05,
        join_timeout_seconds=JOIN_TIMEOUT_SECONDS,
        silence_timeout_seconds=SILENCE_TIMEOUT_SECONDS,
    )
    registry = RoomRegistry(config=config)
    try:
        test_client, code = serve_room(
            registry, fx01_grid, catalogue, tmp_path, monkeypatch
        )
        with test_client as client, ExitStack() as stack:
            ana = open_socket(client, code, stack)
            ana.websocket.send_text(JOIN_AS_ANA)
            ana.peer.wait_until(
                lambda: any(isinstance(m, Snapshot) for m in ana.peer.messages()),
                "the snapshot of Ana",
            )
            time.sleep(STILL_OPEN_AFTER_SECONDS)
            close_code_while_silent = ana.peer.close_code
            ana.peer.wait_until(
                lambda: ana.peer.close_code is not None,
                "the close of the silent player",
                timeout=SILENCE_CLOSE_LIMIT_SECONDS,
            )
            close_code = ana.peer.close_code
    finally:
        registry.close()

    assert close_code_while_silent is None
    assert close_code == SILENT_CLOSE_CODE
