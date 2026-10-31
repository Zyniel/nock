"""Tests of platform/serving, AC-7 to AC-9: the body limit of the HTTP edge.

AC-7: `POST /api/rooms` with a `Content-Length` of 65,537 gets 413 and creates no
room, and one of exactly 65,536 bytes is not refused. AC-8: the same with a
chunked body and no `Content-Length`. AC-9: the `Caddyfile` sets the same limit.

The body of every request is the valid `{"grid_number": 1}` padded with spaces
to the size wanted, so that a request nothing refuses creates a room (201): a
refusal for the size shows as a 413 and no room, and a missing limit as a room.
A test client sends AC-7's bodies. The requests that no test client makes (a
declared length with no body, a chunked body with no `Content-Length`) go over a
socket to the live server (`serving` of `spec038_harness`): `raw_exchange` of
`serving_harness`.

Choices where the spec leaves room:

- "The answer it gets without the limit" for 65,536 bytes: 201 and a room, the
  answer of the padded valid body.
- "With its body unread": a request that declares 65,537 bytes and sends none
  gets its 413 all the same, and no room.
- "Nothing is counted by a throttle": 31 refused requests (one more than the
  default of 30 rooms an hour for an address) do not stop a valid one.
- The `Caddyfile`'s "site block" is the block of its one site address; its
  comment lines are left out.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.settings import DEFAULT_ROOMS_PER_ADDRESS_PER_HOUR
from serving_harness import (
    BODY_LIMIT,
    CONTENT_TOO_LARGE,
    ROOM_REQUEST_HEADERS,
    RecordingRegistry,
    chunked,
    edge_app,
    padded_room_request,
    raw_exchange,
)
from spec010_harness import catalogue_from_grid
from spec038_harness import serving

CADDYFILE_PATH = Path(__file__).resolve().parents[1] / "Caddyfile"
ROOMS_PATH = "/api/rooms"
CREATED = 201


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RecordingRegistry]:
    room_registry = RecordingRegistry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RecordingRegistry, catalogue: Catalogue, tmp_path: Path
) -> Iterator[TestClient]:
    app = edge_app(registry, tmp_path / "no-build", catalogue)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def base_url(
    registry: RecordingRegistry, catalogue: Catalogue, tmp_path: Path
) -> Iterator[str]:
    """The URL of the live server of the same app."""
    app = edge_app(registry, tmp_path / "no-build", catalogue)
    with serving(app) as url:
        yield url


# ---- AC-7: a declared length ---------------------------------------------------------


def test_ac7_a_declared_length_above_the_limit_is_413_and_creates_no_room(
    client: TestClient, registry: RecordingRegistry
) -> None:
    response = client.post(
        ROOMS_PATH,
        content=padded_room_request(BODY_LIMIT + 1),
        headers=ROOM_REQUEST_HEADERS,
    )

    assert response.status_code == 413
    assert response.json() == CONTENT_TOO_LARGE
    assert registry.created_codes == []


def test_ac7_a_body_of_exactly_the_limit_is_not_refused(
    client: TestClient, registry: RecordingRegistry
) -> None:
    response = client.post(
        ROOMS_PATH,
        content=padded_room_request(BODY_LIMIT),
        headers=ROOM_REQUEST_HEADERS,
    )

    assert response.status_code == CREATED
    assert registry.created_codes == [response.json()["code"]]


def test_ac7_a_refusal_is_not_counted_by_the_creation_throttle(
    client: TestClient, registry: RecordingRegistry
) -> None:
    oversize = padded_room_request(BODY_LIMIT + 1)
    refused: list[int] = []
    for _ in range(DEFAULT_ROOMS_PER_ADDRESS_PER_HOUR + 1):
        response = client.post(
            ROOMS_PATH, content=oversize, headers=ROOM_REQUEST_HEADERS
        )
        refused.append(response.status_code)

    valid = client.post(
        ROOMS_PATH, content=padded_room_request(0), headers=ROOM_REQUEST_HEADERS
    )

    assert refused == [413] * (DEFAULT_ROOMS_PER_ADDRESS_PER_HOUR + 1)
    assert valid.status_code == CREATED
    assert registry.created_codes == [valid.json()["code"]]


def test_ac7_a_declared_length_above_the_limit_is_refused_before_the_body(
    base_url: str, registry: RecordingRegistry
) -> None:
    head = (
        f"POST {ROOMS_PATH} HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {BODY_LIMIT + 1}\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")

    answer = raw_exchange(base_url, head, [])

    assert answer.status == 413
    assert json.loads(answer.body) == CONTENT_TOO_LARGE
    assert registry.created_codes == []


# ---- AC-8: a chunked body ------------------------------------------------------------


def test_ac8_a_chunked_body_above_the_limit_is_413_and_creates_no_room(
    base_url: str, registry: RecordingRegistry
) -> None:
    head = (
        f"POST {ROOMS_PATH} HTTP/1.1\r\n"
        "Host: 127.0.0.1\r\n"
        "Content-Type: application/json\r\n"
        "Transfer-Encoding: chunked\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii")
    assert b"content-length" not in head.lower()
    pieces = chunked(padded_room_request(BODY_LIMIT + 1))

    answer = raw_exchange(base_url, head, pieces)

    assert answer.status == 413
    assert json.loads(answer.body) == CONTENT_TOO_LARGE
    assert registry.created_codes == []


# ---- AC-9: the Caddyfile -------------------------------------------------------------


def site_block_of(caddyfile: str) -> str:
    """The text between the braces of the Caddyfile's first block, comments out."""
    lines: list[str] = []
    for line in caddyfile.splitlines():
        if not line.lstrip().startswith("#"):
            lines.append(line)
    text = "\n".join(lines).replace("{$NOCK_DOMAIN}", "SITE")
    start = text.index("{")
    depth = 0
    for position in range(start, len(text)):
        if text[position] == "{":
            depth += 1
        elif text[position] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : position]
    raise AssertionError("the Caddyfile's site block is never closed")


def test_ac9_the_caddyfile_site_block_limits_the_request_body_to_64_kib() -> None:
    block = site_block_of(CADDYFILE_PATH.read_text(encoding="utf-8"))

    pattern = r"request_body\s*\{\s*max_size\s+64KiB\s*\}"
    assert re.search(pattern, block) is not None, block
