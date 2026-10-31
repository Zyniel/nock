"""Shared setup of the tests of platform/serving about the HTTP edge (AC-7 to AC-14).

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_serving_*.py`:

- `test_serving_body_limit.py`: AC-7 to AC-9 and AC-14, the body limit of rule 11
  and the `Caddyfile`'s.
- `test_serving_security_headers.py`: AC-10, the three headers of rule 12 on
  every kind of answer.
- `test_serving_cache_control.py`: AC-12 and AC-13, the `Cache-Control` of rule 13.
- `test_serving_csp_browser.py`: AC-11, the pages under rule 12's policy in a
  browser.

This module holds what more than one of those files uses: the values of the
spec, the fixtures `fx01_grid`, `catalogue` (FX-01 as entry 1) and `registry`
(a `RecordingRegistry`), the app of the HTTP edge tests (a built client, the
operator pages on, a catalogue holding FX-01) and a bare HTTP exchange over a
socket, for the requests that no test client can make (a chunked body with no
`Content-Length`, a declared length with no body).

Pytest finds a fixture by name in the module of the test, so each test file that
asks for one imports it under the same name (`from serving_harness import
catalogue as catalogue`, the form that tells ruff the import is meant to stay).

The app is `create_app(rooms=registry, dist_dir=..., catalogue=...,
operator_token=OPS_TOKEN)`, the way spec 038's tests build it, with the accounts
on when an account store is given.
"""

from __future__ import annotations

import socket
import threading
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlsplit

import pytest
from fastapi import FastAPI

from nock.accounts import AccountStore
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.server import create_app
from spec010_harness import catalogue_from_grid
from spec033_harness import account_settings
from spec038_harness import OPS_TOKEN

# ---- Values of the spec --------------------------------------------------------------

BODY_LIMIT = 65_536
CONTENT_TOO_LARGE = {"detail": "Content Too Large"}
CONTENT_SECURITY_POLICY = "default-src 'self'; frame-ancestors 'none'"
EDGE_HEADERS = {
    "content-security-policy": CONTENT_SECURITY_POLICY,
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
NO_CACHE = "no-cache"
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"

# ---- Values of the test harness ------------------------------------------------------

# The body of a valid `POST /api/rooms` for the catalogue's entry 1. JSON allows
# white space after the value, so the request can be padded to any size and still
# create a room when nothing refuses it.
ROOM_REQUEST = '{"grid_number": 1}'
ROOM_REQUEST_HEADERS = {"content-type": "application/json"}
RAW_TIMEOUT_SECONDS = 10.0
CHUNK_SIZE = 8192
RECEIVE_SIZE = 65_536


class RecordingRegistry(RoomRegistry):
    """A real registry that keeps the code of each room it registered.

    `created_codes` is the proof that a request created a room, or none: a room
    that nobody asked for is not necessarily live in memory.
    """

    def __init__(self) -> None:
        super().__init__()
        self.created_codes: list[str] = []

    def register_room(
        self,
        grid: Grid,
        grid_number: int | None = None,
        creator_account_id: str | None = None,
    ) -> str:
        """Register the room as usual and keep its code."""
        code = super().register_room(
            grid, grid_number=grid_number, creator_account_id=creator_account_id
        )
        self.created_codes.append(code)
        return code


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RecordingRegistry]:
    """A registry that keeps the codes of the rooms it registered; closed after."""
    room_registry = RecordingRegistry()
    yield room_registry
    room_registry.close()


def padded_room_request(size: int) -> bytes:
    """A valid body of `POST /api/rooms`, padded with spaces to `size` bytes."""
    return ROOM_REQUEST.ljust(size).encode("ascii")


def edge_app(
    registry: RoomRegistry,
    dist_dir: Path,
    catalogue: Catalogue | None = None,
    account_store: AccountStore | None = None,
    operator_pages: bool = True,
) -> FastAPI:
    """The app of the HTTP edge tests.

    Args:
        registry: The rooms.
        dist_dir: The built client (a folder that may hold no build).
        catalogue: The grids served; None: an empty catalogue.
        account_store: Turns the accounts on, with this store; None: accounts off.
        operator_pages: True: the operator pages are on (`OPS_TOKEN`); False: off.

    Returns:
        The app.
    """
    operator_token = OPS_TOKEN if operator_pages else ""
    if account_store is None:
        return create_app(
            rooms=registry,
            dist_dir=dist_dir,
            catalogue=catalogue,
            operator_token=operator_token,
        )
    return create_app(
        rooms=registry,
        dist_dir=dist_dir,
        catalogue=catalogue,
        operator_token=operator_token,
        accounts=account_settings(),
        account_store=account_store,
    )


# ---- A bare HTTP exchange ------------------------------------------------------------


class RawAnswer(NamedTuple):
    """What the server sent back on a socket: status, lowercase headers, body."""

    status: int
    headers: dict[str, str]
    body: bytes


def chunked(body: bytes) -> list[bytes]:
    """The body as HTTP/1.1 chunks of `CHUNK_SIZE` bytes, then the last chunk."""
    pieces: list[bytes] = []
    for start in range(0, len(body), CHUNK_SIZE):
        piece = body[start : start + CHUNK_SIZE]
        pieces.append(f"{len(piece):x}\r\n".encode("ascii") + piece + b"\r\n")
    pieces.append(b"0\r\n\r\n")
    return pieces


def raw_exchange(base_url: str, head: bytes, parts: Sequence[bytes]) -> RawAnswer:
    """Send `head`, then each of `parts`, to the server at `base_url`; read the answer.

    The answer is read by a thread while the request is sent, so that an answer
    sent before the end of the request is kept whatever the server does with
    the rest of it (a reset of the connection loses nothing already received).
    The server is asked to close the connection after its answer. A refusal of
    the request's end (`OSError` on sending) is expected when the server answers
    early.

    Args:
        base_url: `http://host:port`.
        head: The request line, the headers and the empty line, ending with
            `\\r\\n\\r\\n`.
        parts: What follows the head, sent one after the other.

    Returns:
        The status, the headers and the body of the answer.

    Raises:
        AssertionError: The server sent no answer within the time allowed.
    """
    address = urlsplit(base_url)
    assert address.hostname is not None, base_url
    received = bytearray()
    with socket.create_connection(
        (address.hostname, address.port), timeout=RAW_TIMEOUT_SECONDS
    ) as connection:

        def read_answer() -> None:
            try:
                while True:
                    data = connection.recv(RECEIVE_SIZE)
                    if not data:
                        return
                    received.extend(data)
            except OSError:
                return

        reader = threading.Thread(target=read_answer, daemon=True)
        reader.start()
        try:
            connection.sendall(head)
            for part in parts:
                connection.sendall(part)
        except OSError:
            pass  # the server answered before the end of the request
        reader.join(RAW_TIMEOUT_SECONDS)
    return parse_answer(bytes(received))


def parse_answer(data: bytes) -> RawAnswer:
    """Split the bytes of an HTTP/1.1 answer into status, headers and body."""
    separator = data.find(b"\r\n\r\n")
    assert separator != -1, f"no complete answer: {data!r}"
    head_lines = data[:separator].decode("latin-1").split("\r\n")
    status = int(head_lines[0].split(" ")[1])
    headers: dict[str, str] = {}
    for line in head_lines[1:]:
        name, _, value = line.partition(":")
        headers[name.strip().lower()] = value.strip()
    return RawAnswer(status=status, headers=headers, body=data[separator + 4 :])
