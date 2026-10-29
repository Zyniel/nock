"""Tests of lobby/joining, AC-21: an account has one seat in a room.

Over the room socket, with the app of `host_harness`. In room R, Lea (signed in,
token T, host, `T` at (1, 0)) and Bob (token U) are players. A device signed in as
Lea reaches Lea's seat whatever token it carries; signed out, a token reaches
its own member.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import (
    LEA_EMAIL,
    REPLACED_CLOSE_CODE,
    RESUME_WINDOW_SECONDS,
    HostApp,
    events_without_pongs,
    host_app,
    host_ids,
    open_member,
    sign_in_as,
    view_in,
    wait_for_departure,
    wait_for_state,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import EditLetter, PlayerState
from spec014_harness import Peer, ping_and_wait
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text, snapshot_cell
from spec033_harness import NOBODYS_TOKEN, state_of


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


class Room(NamedTuple):
    """Room R: Lea signed in and host, Bob signed out, both connected."""

    code: str
    session: str
    lea: Peer
    lea_id: str
    lea_token: str
    bob: Peer
    bob_id: str
    bob_token: str


def lea_and_bob(
    app: HostApp,
    grid: Grid,
    lea_stack: contextlib.ExitStack,
    bob_stack: contextlib.ExitStack,
) -> Room:
    """Lea (signed in) writes `T` at (1, 0); Bob joins with no account."""
    code = app.registry.register_room(grid, grid_number=1)
    session = sign_in_as(app, LEA_EMAIL)
    lea = open_member(lea_stack, app.client, code, "Lea", None, session)
    lea.send(EditLetter(row=1, column=0, letter="T"))
    ping_and_wait(lea)
    bob = open_member(bob_stack, app.client, code, "Bob")
    return Room(
        code=code,
        session=session,
        lea=lea,
        lea_id=lea.snapshot().you,
        lea_token=lea.snapshot().resume_token,
        bob=bob,
        bob_id=bob.snapshot().you,
        bob_token=bob.snapshot().resume_token,
    )


@pytest.mark.parametrize("token_of_the_device", ["none", "bobs", "unknown"])
def test_ac21_a_signed_in_device_resumes_leas_seat_whatever_token_it_carries(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
    token_of_the_device: str,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as lea_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        room = lea_and_bob(app, fx01_grid, lea_stack, bob_stack)
        carried = {
            "none": None,
            "bobs": room.bob_token,
            "unknown": NOBODYS_TOKEN,
        }[token_of_the_device]
        ping_and_wait(room.bob)
        bob_heard_before = events_without_pongs(room.bob)

        with contextlib.ExitStack() as device_stack:
            device = open_member(
                device_stack, app.client, room.code, "Autre", carried, room.session
            )
            room.lea.wait_until(
                lambda: room.lea.close_code == REPLACED_CLOSE_CODE,
                "the 4001 close of Lea's older connection",
            )
            ping_and_wait(room.bob)
            bob_heard_after = events_without_pongs(room.bob)
            players = state_of(app.registry, room.code).players

    snapshot = device.snapshot()
    before = view_in(room.lea.snapshot().players, room.lea_id)
    after = view_in(snapshot.players, room.lea_id)
    cell = snapshot_cell(snapshot, 1, 0)
    assert snapshot.you == room.lea_id
    assert (after.colour, after.is_host) == (before.colour, True)
    assert (cell.letter, cell.author) == ("T", room.lea_id)
    assert room.bob.close_code is None
    assert bob_heard_after == bob_heard_before
    assert len(players) == 2
    assert view_in(snapshot.players, room.bob_id).state == PlayerState.ACTIVE


def test_ac21_signed_out_bobs_token_still_resumes_bob(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as lea_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        room = lea_and_bob(app, fx01_grid, lea_stack, bob_stack)

        with contextlib.ExitStack() as device_stack:
            device = open_member(
                device_stack, app.client, room.code, "Autre", room.bob_token
            )
            room.bob.wait_until(
                lambda: room.bob.close_code == REPLACED_CLOSE_CODE,
                "the 4001 close of Bob's older connection",
            )
            ping_and_wait(room.lea)

    assert device.snapshot().you == room.bob_id
    assert room.lea.close_code is None


def test_ac21_the_signed_in_join_seats_a_timed_out_lea_back_with_her_id(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as lea_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        room = lea_and_bob(app, fx01_grid, lea_stack, bob_stack)
        lea_stack.close()
        wait_for_state(app.registry, room.code, room.lea_id, PlayerState.DISCONNECTED)
        fake_clock.advance(RESUME_WINDOW_SECONDS + 1)
        wait_for_departure(app.registry, room.code, room.lea_id)

        with contextlib.ExitStack() as device_stack:
            device = open_member(
                device_stack, app.client, room.code, "Autre", None, room.session
            )
            hosts = host_ids(state_of(app.registry, room.code))

    assert device.snapshot().you == room.lea_id
    assert hosts == [room.bob_id]
    assert view_in(device.snapshot().players, room.lea_id).nickname == "LEA"
