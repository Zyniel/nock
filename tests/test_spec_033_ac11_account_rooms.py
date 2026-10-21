"""Tests of spec 033, AC-11 over HTTP: a signed-in device gets the rooms of the
account.

With the app of the "Test harness" on a fake clock: after Ana's sign-in from room
R (AC-1), `GET /api/account/rooms` lists her identity of R. Once she joins room S
as a new player and links it with `PUT /api/account/rooms`, the list holds S then
R, newest link first. A `PUT` with a token that is no member's of S answers 404,
one without the cookie 401; once R expires (spec 032), the list holds S only.

S is created half a room life after R, so that moving the fake clock past R's life
leaves S alive. The rooms' config changes nothing on a tick.

Edge cases checked as well: an identity whose room was deleted is not served once
a new room has its code ("Room code reused"); linking a room again makes it the
newest; the 401 comes before any check of the body; `GET /api/account/rooms`
without a session answers 401.

The browser part of AC-11 is in `test_spec_033_ac02_ac11_devices.py`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest

from nock.grid import Grid
from nock.room import new_room
from spec017_harness import FakeClock, open_peer
from spec032_harness import LIFE, grid_from_text
from spec033_harness import (
    ANA_EMAIL,
    NOBODYS_TOKEN,
    NOT_AUTHORIZED,
    NOT_FOUND,
    ROOMS_PATH,
    AccountApp,
    account_app,
    link_and_sign_in,
    room_key,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class TwoRooms(NamedTuple):
    """Ana signed in from R, then a new player of S, linked with a PUT."""

    app: AccountApp
    r_code: str
    s_code: str
    r_identity: dict[str, str]
    s_identity: dict[str, str]
    put_status: int


@contextlib.contextmanager
def ana_signed_in_from_r(
    tmp_path: Path, clock: FakeClock, grid: Grid
) -> Iterator[tuple[AccountApp, str, dict[str, str], contextlib.ExitStack]]:
    """AC-1's sign-in: Ana joined R and signed in from it."""
    with account_app(tmp_path, clock) as app, contextlib.ExitStack() as stack:
        r_code = app.registry.register_room(grid, grid_number=1)
        ana = open_peer(stack, app.client, r_code, "Ana")
        identity = {
            "code": r_code,
            "player_id": ana.snapshot().you,
            "resume_token": ana.snapshot().resume_token,
            "nickname": "ANA",
        }
        link_and_sign_in(app, ANA_EMAIL, room_key(r_code, identity["resume_token"]))
        yield app, r_code, identity, stack


@contextlib.contextmanager
def two_rooms(tmp_path: Path, clock: FakeClock, grid: Grid) -> Iterator[TwoRooms]:
    with ana_signed_in_from_r(tmp_path, clock, grid) as (app, r_code, r_id, stack):
        clock.advance(LIFE / 2)
        s_code = app.registry.register_room(grid, grid_number=1)
        ana_in_s = open_peer(stack, app.client, s_code, "Ana")
        s_identity = {
            "code": s_code,
            "player_id": ana_in_s.snapshot().you,
            "resume_token": ana_in_s.snapshot().resume_token,
            "nickname": "ANA",
        }
        key = room_key(s_code, s_identity["resume_token"])
        put = app.client.put(ROOMS_PATH, json=key)
        yield TwoRooms(app, r_code, s_code, r_id, s_identity, put.status_code)


def test_ac11_after_the_sign_in_the_rooms_route_lists_r(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with ana_signed_in_from_r(tmp_path, fake_clock, fx01_grid) as signed_in:
        app, _, identity, _ = signed_in

        response = app.client.get(ROOMS_PATH)

    assert response.status_code == 200
    assert response.json() == [identity]


def test_ac11_linking_s_answers_204(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        status = rooms.put_status

    assert status == 204


def test_ac11_the_list_then_holds_s_then_r(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        response = rooms.app.client.get(ROOMS_PATH)

    assert response.status_code == 200
    assert response.json() == [rooms.s_identity, rooms.r_identity]


def test_ac11_a_put_with_a_token_that_is_no_members_answers_404(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        response = rooms.app.client.put(
            ROOMS_PATH, json=room_key(rooms.s_code, NOBODYS_TOKEN)
        )
        listed = rooms.app.client.get(ROOMS_PATH)

    assert response.status_code == 404
    assert response.json() == NOT_FOUND
    assert listed.json() == [rooms.s_identity, rooms.r_identity]


def test_ac11_a_put_without_the_cookie_answers_401(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        rooms.app.client.cookies.clear()
        key = room_key(rooms.s_code, rooms.s_identity["resume_token"])

        response = rooms.app.client.put(ROOMS_PATH, json=key)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac11_without_the_cookie_the_401_comes_before_the_body_check(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        rooms.app.client.cookies.clear()

        response = rooms.app.client.put(ROOMS_PATH, json={"code": "not a code"})

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac11_the_rooms_route_without_the_cookie_answers_401(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        rooms.app.client.cookies.clear()

        response = rooms.app.client.get(ROOMS_PATH)

    assert response.status_code == 401
    assert response.json() == NOT_AUTHORIZED


def test_ac11_once_r_expires_the_list_holds_s_only(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        fake_clock.advance(LIFE / 2 + 1)

        response = rooms.app.client.get(ROOMS_PATH)

    assert response.status_code == 200
    assert response.json() == [rooms.s_identity]


def test_ac11_a_room_linked_again_becomes_the_newest(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        fake_clock.advance(1)
        key = room_key(rooms.r_code, rooms.r_identity["resume_token"])
        again = rooms.app.client.put(ROOMS_PATH, json=key)

        response = rooms.app.client.get(ROOMS_PATH)

    assert again.status_code == 204
    assert response.json() == [rooms.r_identity, rooms.s_identity]


def test_ac11_an_identity_of_a_deleted_room_is_not_served_when_its_code_is_reused(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with two_rooms(tmp_path, fake_clock, fx01_grid) as rooms:
        fake_clock.advance(LIFE / 2 + 1)
        rooms.app.registry.expire_rooms()
        assert rooms.app.registry.peek_room(rooms.r_code) is None
        reused = new_room(rooms.r_code, fx01_grid, fake_clock.now, grid_number=1)
        rooms.app.registry.add_room(reused)

        response = rooms.app.client.get(ROOMS_PATH)

    assert response.json() == [rooms.s_identity]
