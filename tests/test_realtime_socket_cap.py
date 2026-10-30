"""Tests of platform/realtime, AC-22: at most 50 open sockets per address.

The app of the tests serves a registry the test gives it (the cap is the default
one, the variable being cleared), over the real WebSocket and the real clock; the
tests of the edge case below change the cap and the clock.
Ana's socket is joined; the 49 others only ping (`realtime_harness`), which is
how a test tells a socket that is served from one that is closed. The registry's
rooms are given a join deadline of 600 s so that the sockets that never join
outlast the test (`RoomConfig.join_timeout_seconds`, AC-21).

Readings of the spec's wording:

- "The 51st closes with 4503 before any message": it has the close code and
  received no message at all (it sent a ping, which the refused socket does not
  answer).
- "Ana's play goes on": Ana types a letter after the refusal and receives her
  `letter_changed`.
- "The next socket of the address is served" after one of the 50 closed: the
  server learns of a close a little later, so the tries go on for 5 s; any close
  other than 4503 in between fails the test.
- "After ten 4503s": ten refused sockets in a row, then one of the 50 closes and
  the next socket is served, whereas ten refusals recorded as wrong codes would
  have the address closed with 4429.
- The edge case "a socket closed with 4429 or 4404 counted while it was open, like
  any other": its tests take a cap of 2 (`NOCK_SOCKETS_PER_ADDRESS`, AC-23) so
  that a few closed sockets would fill the cap if they kept their count, and give
  the registry the fake clock, on which the wrong-code throttle counts its
  minute. After the closes, two sockets of the address to a real room are served
  and a third is closed with 4503, which shows that the cap was 2 and that the
  closed sockets hold none of it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

from host_harness import open_member, wait_for_message
from lifetime_harness import variables_of
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, LetterChanged
from nock.room import RoomConfig
from nock.server import create_app
from realtime_harness import (
    DEFAULT_SOCKET_CAP,
    ROOM_NOT_FOUND_CLOSE_CODE,
    SOCKETS_VARIABLE,
    THROTTLED_CLOSE_CODE,
    TOO_MANY_SOCKETS_CLOSE_CODE,
    UNKNOWN_CODE,
    WRONG_CODE_LIMIT,
    WRONG_CODE_WINDOW_SECONDS,
    OpenSocket,
    client_from_another_address,
    fill_address,
    is_served,
    try_socket,
    try_socket_until_counted,
    try_socket_until_free,
)
from spec011_harness import make_dist_dir
from spec014_harness import Peer
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

TYPED_ROW = 1
TYPED_COLUMN = 0
TYPED_LETTER = "T"
QUIET_JOINS = RoomConfig(
    tick_seconds=0.05, silence_timeout_seconds=1e9, join_timeout_seconds=600.0
)
SMALL_CAP_VALUE = "2"
SMALL_CAP = 2


class FullAddress(NamedTuple):
    """An app whose address holds 50 open sockets to one room."""

    client: TestClient
    code: str
    ana: Peer
    fillers: list[OpenSocket]
    stack: ExitStack


class SmallCapAddress(NamedTuple):
    """An app with a cap of 2 sockets per address, on the fake clock, and a room."""

    client: TestClient
    code: str
    clock: FakeClock
    stack: ExitStack


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


@pytest.fixture
def full_address(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    catalogue: Catalogue,
) -> Iterator[FullAddress]:
    variables_of(monkeypatch, {})
    registry = RoomRegistry(config=QUIET_JOINS)
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(
            rooms=registry, dist_dir=make_dist_dir(tmp_path), catalogue=catalogue
        )
        with TestClient(app) as client, ExitStack() as stack:
            ana = open_member(stack, client, code, "Ana")
            others = fill_address(client, code, stack, DEFAULT_SOCKET_CAP - 1)
            yield FullAddress(client, code, ana, others, stack)
    finally:
        registry.close()


@pytest.fixture
def small_cap_address(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    catalogue: Catalogue,
) -> Iterator[SmallCapAddress]:
    variables_of(monkeypatch, {SOCKETS_VARIABLE: SMALL_CAP_VALUE})
    registry = RoomRegistry(config=QUIET_JOINS, clock=fake_clock)
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(
            rooms=registry, dist_dir=make_dist_dir(tmp_path), catalogue=catalogue
        )
        with TestClient(app) as client, ExitStack() as stack:
            yield SmallCapAddress(client, code, fake_clock, stack)
    finally:
        registry.close()


def close_codes_of_sockets_to(
    address: SmallCapAddress, code: str, count: int
) -> list[int | None]:
    """Open `count` sockets to room `code` one after the other; their close codes.

    A socket closed with 4503 is tried again (`try_socket_until_counted`), so each
    close code is the one the cap let the socket reach.
    """
    close_codes: list[int | None] = []
    for _ in range(count):
        socket = try_socket_until_counted(address.client, code, address.stack)
        close_codes.append(socket.peer.close_code)
    return close_codes


def sockets_of_the_room_past_the_cap(
    address: SmallCapAddress,
) -> tuple[list[OpenSocket], OpenSocket]:
    """Fill the cap with sockets to the room, then try one more.

    Returns:
        The sockets that were served, which fail the test unless the cap's places
        come free, and the socket tried after them.
    """
    served: list[OpenSocket] = []
    for _ in range(SMALL_CAP):
        served.append(
            try_socket_until_free(address.client, address.code, address.stack)
        )
    one_more = try_socket(address.client, address.code, address.stack)
    return served, one_more


def test_ac22_the_51st_socket_is_closed_with_4503_while_the_rest_goes_on(
    full_address: FullAddress,
) -> None:
    client, code, ana, fillers, stack = full_address

    refused = try_socket(client, code, stack)
    ana.send(EditLetter(row=TYPED_ROW, column=TYPED_COLUMN, letter=TYPED_LETTER))
    wait_for_message(ana, LetterChanged)
    another_address = client_from_another_address(client)
    bob = open_member(stack, another_address, code, "Bob")  # waits for his snapshot
    fillers[0].close()
    freed = try_socket_until_free(client, code, stack)

    assert refused.peer.close_code == TOO_MANY_SOCKETS_CLOSE_CODE
    assert refused.peer.messages() == []
    assert ana.close_code is None
    assert bob.close_code is None
    assert [is_served(socket) for socket in fillers[1:]] == [True] * (
        DEFAULT_SOCKET_CAP - 2
    )
    assert is_served(freed)


def test_ac22_ten_refusals_do_not_count_as_wrong_codes(
    full_address: FullAddress,
) -> None:
    client, code, _ana, fillers, stack = full_address

    refusals: list[int | None] = []
    for _ in range(WRONG_CODE_LIMIT):
        refused = try_socket(client, code, stack)
        refusals.append(refused.peer.close_code)
    fillers[0].close()
    freed = try_socket_until_free(client, code, stack)

    assert refusals == [TOO_MANY_SOCKETS_CLOSE_CODE] * WRONG_CODE_LIMIT
    assert is_served(freed)


def test_ac22_a_socket_closed_with_4404_releases_its_count(
    small_cap_address: SmallCapAddress,
) -> None:
    wrong_code_closes = close_codes_of_sockets_to(
        small_cap_address, UNKNOWN_CODE, SMALL_CAP
    )
    served, one_more = sockets_of_the_room_past_the_cap(small_cap_address)

    assert wrong_code_closes == [ROOM_NOT_FOUND_CLOSE_CODE] * SMALL_CAP
    assert [is_served(socket) for socket in served] == [True] * SMALL_CAP
    assert one_more.peer.close_code == TOO_MANY_SOCKETS_CLOSE_CODE


def test_ac22_a_socket_closed_with_4429_releases_its_count(
    small_cap_address: SmallCapAddress,
) -> None:
    code = small_cap_address.code
    wrong_code_closes = close_codes_of_sockets_to(
        small_cap_address, UNKNOWN_CODE, WRONG_CODE_LIMIT
    )
    throttled_closes = close_codes_of_sockets_to(
        small_cap_address, UNKNOWN_CODE, SMALL_CAP
    )
    throttled_closes += close_codes_of_sockets_to(small_cap_address, code, SMALL_CAP)
    small_cap_address.clock.advance(WRONG_CODE_WINDOW_SECONDS)
    served, one_more = sockets_of_the_room_past_the_cap(small_cap_address)

    assert wrong_code_closes == [ROOM_NOT_FOUND_CLOSE_CODE] * WRONG_CODE_LIMIT
    assert throttled_closes == [THROTTLED_CLOSE_CODE] * (2 * SMALL_CAP)
    assert [is_served(socket) for socket in served] == [True] * SMALL_CAP
    assert one_more.peer.close_code == TOO_MANY_SOCKETS_CLOSE_CODE
