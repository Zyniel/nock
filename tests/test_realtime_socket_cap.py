"""Tests of platform/realtime, AC-22: at most 50 open sockets per address.

The app of the tests serves a registry the test gives it (the cap is the default
one, the variable being cleared), over the real WebSocket and the real clock.
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
    TOO_MANY_SOCKETS_CLOSE_CODE,
    WRONG_CODE_LIMIT,
    OpenSocket,
    client_from_another_address,
    fill_address,
    is_served,
    try_socket,
    try_socket_until_free,
)
from spec011_harness import make_dist_dir
from spec014_harness import Peer
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text

TYPED_ROW = 1
TYPED_COLUMN = 0
TYPED_LETTER = "T"
QUIET_JOINS = RoomConfig(
    tick_seconds=0.05, silence_timeout_seconds=1e9, join_timeout_seconds=600.0
)


class FullAddress(NamedTuple):
    """An app whose address holds 50 open sockets to one room."""

    client: TestClient
    code: str
    ana: Peer
    fillers: list[OpenSocket]
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
