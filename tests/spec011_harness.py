"""Shared setup of the tests of spec 011: room creation, engine and throttle.

This module is not a test file: pytest does not collect it. The tests of spec 011
are in `tests/test_spec_011_*.py`, one file per criterion.

This module holds what more than one of those files uses. What only one file uses
stays in that file, next to its tests. The fixtures `fx01_grid`, `dist_dir` and
`catalogue` are defined in each file that needs them as thin wrappers around
`grid_from_text`, `make_dist_dir` and `build_catalogue`: a fixture imported from
here would be an unused import for ruff.
"""

from __future__ import annotations

import json
import queue
import re
import threading
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from playwright.sync_api import Page
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.room import RoomState, new_room

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
JOIN_TEXT = '{"type": "join", "nickname": "Ana", "resume_token": null}'
CODE_PATTERN = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$")
START_TIME = 1_000_000.0
RECEIVE_TIMEOUT_SECONDS = 5.0
PUBLISHED_NUMBER = 2
UNPUBLISHED_NUMBER = 4
UNKNOWN_CODE = "ZZZZZZ"
EXPECTED_FR_VALUES = {
    "room.share.label": "Lien d'invitation",
    "room.share.copy": "Copier le lien",
    "room.share.copied": "Lien copié",
    "room.status.throttled": "Trop de codes erronés. Réessayez dans une minute.",
}


# ---- Fixture bodies and helpers used by several files ------------------------


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


def grid_from_text(fx01_text: str) -> Grid:
    """The grid of a JSON text (the body of the `fx01_grid` fixture)."""
    return Grid.model_validate_json(fx01_text)


def make_dist_dir(tmp_path: Path) -> Path:
    """A `dist` directory with a minimal `index.html` (the `dist_dir` fixture)."""
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


def build_catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue with FX-01 as published entry 2 and as unpublished entry 4.

    This is the body of the `catalogue` fixture. The conftest `live_server`
    serves the catalogue of the test module, so each file that starts a live
    server or an HTTP client defines the fixture as a wrapper around it.
    """
    published = CatalogueEntry(
        number=PUBLISHED_NUMBER,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=fx01_grid,
    )
    unpublished = CatalogueEntry(
        number=UNPUBLISHED_NUMBER,
        published_on=date(2026, 10, 2),
        force=2,
        published=False,
        **credits(),
        grid=fx01_grid,
    )
    return Catalogue(entries=(published, unpublished))


def receive_text_or_fail(websocket: WebSocketTestSession) -> str:
    """Return the next text of the socket, failing instead of waiting forever."""
    received: queue.Queue[str | BaseException] = queue.Queue()

    def read() -> None:
        try:
            received.put(websocket.receive_text())
        except BaseException as error:  # handed to the test thread, re-raised there
            received.put(error)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        outcome = received.get(timeout=RECEIVE_TIMEOUT_SECONDS)
    except queue.Empty:
        pytest.fail(f"nothing received from the socket in {RECEIVE_TIMEOUT_SECONDS}s")
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def fresh_state(grid: Grid, code: str = "ABCDEF") -> RoomState:
    return new_room(code, grid, START_TIME)


def open_fx01_room(
    enter_room: EnterRoom,
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
) -> str:
    """Register FX-01, enter the room and return the room's expected link."""
    code = room_registry.register_room(fx01_grid)
    link = f"{live_server}/r/{code}"
    enter_room(page, link)
    return link
