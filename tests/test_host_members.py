"""Tests of lobby/host, AC-10: the account of a member.

Over the room socket, with the app of `host_harness`: a signed-in join links the
member it makes, resumes or seats back only when that member has none; a member's
account never changes otherwise; `PUT /api/account/rooms` links no member. The
member's account is read from the live room (`PlayerRecord.account_id`); the page
that follows (the nickname form of a signed-in device) is in
`test_host_creator_pages.py`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from host_harness import (
    BOB_EMAIL,
    LEA_EMAIL,
    ZOE_EMAIL,
    HostApp,
    account_id_of,
    host_app,
    open_member,
    received_text,
    sign_in_as,
    wait_for_state,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import PlayerState, RemovePlayer
from spec014_harness import ping_and_wait, player_of
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import ROOMS_PATH, room_key, state_of, with_session


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


def room_of(app: HostApp, grid: Grid) -> str:
    """A room with no creator."""
    return app.registry.register_room(grid, grid_number=1)


def test_ac10_a_signed_in_resume_links_the_member_it_resumes(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as first_device,
    ):
        code = room_of(app, fx01_grid)
        session = sign_in_as(app, LEA_EMAIL)
        lea_account = account_id_of(app, session)
        signed_out = open_member(first_device, app.client, code, "Lea")
        lea_id = signed_out.snapshot().you
        token = signed_out.snapshot().resume_token
        unlinked = player_of(state_of(app.registry, code), lea_id).account_id
        first_device.close()
        wait_for_state(app.registry, code, lea_id, PlayerState.DISCONNECTED)

        with contextlib.ExitStack() as stack:
            resumed = open_member(stack, app.client, code, "Lea", token, session)
            linked = player_of(state_of(app.registry, code), lea_id).account_id
            heard = received_text(resumed)

    assert unlinked is None
    assert resumed.snapshot().you == lea_id
    assert linked == lea_account
    assert lea_account not in heard


def test_ac10_the_linked_member_is_reached_by_the_account_without_a_token(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as first_device,
    ):
        code = room_of(app, fx01_grid)
        session = sign_in_as(app, LEA_EMAIL)
        signed_out = open_member(first_device, app.client, code, "Lea")
        lea_id = signed_out.snapshot().you
        token = signed_out.snapshot().resume_token
        first_device.close()
        wait_for_state(app.registry, code, lea_id, PlayerState.DISCONNECTED)
        with contextlib.ExitStack() as linking:
            open_member(linking, app.client, code, "Lea", token, session)

        with contextlib.ExitStack() as stack:
            other_device = open_member(stack, app.client, code, "Autre", None, session)
            players = state_of(app.registry, code).players

    assert other_device.snapshot().you == lea_id
    assert len(players) == 1


def test_ac10_a_members_account_does_not_change_when_another_account_resumes_it(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as bob_device,
    ):
        code = room_of(app, fx01_grid)
        bob_session = sign_in_as(app, BOB_EMAIL)
        bob_account = account_id_of(app, bob_session)
        zoe_session = sign_in_as(app, ZOE_EMAIL)
        bob = open_member(bob_device, app.client, code, "Bob", None, bob_session)
        bob_id = bob.snapshot().you
        token = bob.snapshot().resume_token
        bob_linked = player_of(state_of(app.registry, code), bob_id).account_id
        bob_device.close()
        wait_for_state(app.registry, code, bob_id, PlayerState.DISCONNECTED)

        with contextlib.ExitStack() as stack:
            resumed = open_member(stack, app.client, code, "Zoe", token, zoe_session)
            account_after = player_of(state_of(app.registry, code), bob_id).account_id
        with contextlib.ExitStack() as zoe_stack:
            zoe = open_member(zoe_stack, app.client, code, "Zoe", None, zoe_session)
            players = state_of(app.registry, code).players

    assert bob_linked == bob_account
    assert resumed.snapshot().you == bob_id
    assert account_after == bob_account
    assert zoe.snapshot().you != bob_id
    assert len(players) == 2


def test_ac10_putting_a_room_links_no_member(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as first_device,
    ):
        code = room_of(app, fx01_grid)
        session = sign_in_as(app, LEA_EMAIL)
        signed_out = open_member(first_device, app.client, code, "Lea")
        lea_id = signed_out.snapshot().you
        key = room_key(code, signed_out.snapshot().resume_token)
        first_device.close()
        wait_for_state(app.registry, code, lea_id, PlayerState.DISCONNECTED)

        put = app.client.put(ROOMS_PATH, json=key, headers=with_session(session))
        with contextlib.ExitStack() as stack:
            new_device = open_member(stack, app.client, code, "Lea", None, session)
            room_state = state_of(app.registry, code)

    assert put.status_code == 204
    assert new_device.snapshot().you != lea_id
    assert len(room_state.players) == 2
    assert player_of(room_state, lea_id).account_id is None


def test_ac10_a_removed_account_player_returns_from_another_device_as_a_new_player(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    fx01_grid: Grid,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        code = room_of(app, fx01_grid)
        bob_session = sign_in_as(app, BOB_EMAIL)
        with contextlib.ExitStack() as ana_stack, contextlib.ExitStack() as bob_stack:
            ana = open_member(ana_stack, app.client, code, "Ana")
            bob = open_member(bob_stack, app.client, code, "Bob", None, bob_session)
            bob_id = bob.snapshot().you
            ana.send(RemovePlayer(player_id=bob_id))
            bob.wait_until(lambda: bob.close_code is not None, "Bob's removal")
            ping_and_wait(ana)

            with contextlib.ExitStack() as device_stack:
                again = open_member(
                    device_stack, app.client, code, "Bob", None, bob_session
                )

    assert again.snapshot().you != bob_id
