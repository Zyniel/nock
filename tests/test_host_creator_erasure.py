"""Tests of lobby/host, AC-16: a creator room loaded while accounts are off.

Over the room socket, with the app of `host_harness`: Lea creates a room signed in,
Bob joins, Lea goes away and Bob becomes the stand-in host. AC-16 opens the same
database file in an app with accounts off, then on again. The erasure of the
creator account (AC-15) is in `test_host_creator_deletion.py`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import (
    HAND_OVER_SECONDS,
    CreatorRoom,
    HostApp,
    error_codes_of,
    events_without_pongs,
    host_app,
    host_changes,
    host_flags,
    host_ids,
    lea_creates_a_room,
    open_member,
    stored_creator,
    wait_for_host,
    wait_for_state,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import ErrorCode, PlayerState, RemovePlayer
from spec014_harness import Peer, ping_and_wait
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import ROOMS_PATH, room_key, state_of, with_session

TICKS_PAUSE_SECONDS = 0.4  # several ticks of 50 ms


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


class Scene(NamedTuple):
    """Lea's creator room, with Lea and Bob in it."""

    room: CreatorRoom
    lea_id: str
    lea_token: str
    bob_id: str
    bob_token: str
    bob: Peer


def lea_and_bob_join(
    app: HostApp, lea_stack: contextlib.ExitStack, bob_stack: contextlib.ExitStack
) -> Scene:
    """Lea creates a room and joins it signed in; Bob joins; Lea's room is put."""
    room = lea_creates_a_room(app)
    lea = open_member(lea_stack, app.client, room.code, "Lea", None, room.session)
    bob = open_member(bob_stack, app.client, room.code, "Bob")
    lea_token = lea.snapshot().resume_token
    key = room_key(room.code, lea_token)
    put = app.client.put(ROOMS_PATH, json=key, headers=with_session(room.session))
    assert put.status_code == 204
    return Scene(
        room=room,
        lea_id=lea.snapshot().you,
        lea_token=lea_token,
        bob_id=bob.snapshot().you,
        bob_token=bob.snapshot().resume_token,
        bob=bob,
    )


def lea_goes_away(app: HostApp, scene: Scene, lea_stack: contextlib.ExitStack) -> None:
    """Close Lea's socket, once the room saw her go."""
    lea_stack.close()
    wait_for_state(
        app.registry, scene.room.code, scene.lea_id, PlayerState.DISCONNECTED
    )


def hand_over_to_bob(app: HostApp, scene: Scene) -> None:
    """Move the fake clock past the hand-over delay; wait until Bob is host."""
    app.clock.advance(HAND_OVER_SECONDS + 1)
    wait_for_host(app.registry, scene.room.code, scene.bob_id)


# ---- AC-16: accounts off, then on again --------------------------------------------


def test_ac16_a_room_loaded_with_accounts_off_plays_as_an_anonymous_room(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as accounts_on,
        contextlib.ExitStack() as lea_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        scene = lea_and_bob_join(accounts_on, lea_stack, bob_stack)
        lea_goes_away(accounts_on, scene, lea_stack)
        hand_over_to_bob(accounts_on, scene)
    code = scene.room.code

    with (
        host_app(
            tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False
        ) as accounts_off,
        contextlib.ExitStack() as bob_stack,
        contextlib.ExitStack() as lea_stack,
    ):
        bob = open_member(bob_stack, accounts_off.client, code, "Bob", scene.bob_token)
        lea = open_member(
            lea_stack,
            accounts_off.client,
            code,
            "Lea",
            scene.lea_token,
            scene.room.session,
        )
        lea.send(RemovePlayer(player_id=scene.bob_id))
        lea.wait_until(lambda: error_codes_of(lea) != [], "an error")
        ping_and_wait(bob)
        bob_events = events_without_pongs(bob)
        roster_while_off = host_flags(lea.snapshot().players)
        hosts_while_off = host_ids(state_of(accounts_off.registry, code))
    creator_while_off = stored_creator(accounts_off.database_path, code)

    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as accounts_on_again,
        contextlib.ExitStack() as stack,
    ):
        back = open_member(
            stack,
            accounts_on_again.client,
            code,
            "Lea",
            scene.lea_token,
            scene.room.session,
        )
        roster_again = host_flags(back.snapshot().players)

    assert host_changes(bob_events) == []
    assert roster_while_off == {scene.lea_id: False, scene.bob_id: True}
    assert error_codes_of(lea) == [ErrorCode.NOT_HOST]
    assert hosts_while_off == [scene.bob_id]
    assert creator_while_off == scene.room.account_id
    assert roster_again == {scene.lea_id: True, scene.bob_id: False}
