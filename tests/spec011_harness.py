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

import asyncio
import json
import queue
import re
import threading
import time
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from playwright.sync_api import Page
from starlette.testclient import WebSocketTestSession

from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomConnection, RoomRegistry
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


# ---- Bursts of wrong codes (AC-3; spec 028 AC-8 uses them too) ---------------

BURST_SIZE = 40  # sent at once from one address
LOOKUP_DELAY_SECONDS = 0.02
BURST_TIMEOUT_SECONDS = 10.0


class SlowLookupRegistry(RoomRegistry):
    """A registry whose room lookups answer `LOOKUP_DELAY_SECONDS` later.

    The room socket looks its room up with `connect` (`platform/server.md`
    rule 22) and the recap route with `peek_room`; `room_state` is slowed too. A
    lookup that loads a room from the disk can take that long. In a burst the
    delay keeps the requests in flight at the same time, whatever the order in
    which their threads run, so a burst that is not counted one request after
    another shows on every run. The throttle's rule holds whatever a lookup costs.
    """

    def room_state(self, code: str) -> RoomState | None:
        """Wait `LOOKUP_DELAY_SECONDS`, then look the room up as usual."""
        time.sleep(LOOKUP_DELAY_SECONDS)
        return super().room_state(code)

    def peek_room(self, code: str) -> RoomState | None:
        """Wait `LOOKUP_DELAY_SECONDS`, then peek at the room as usual."""
        time.sleep(LOOKUP_DELAY_SECONDS)
        return super().peek_room(code)

    def connect(
        self,
        code: str,
        account_id: str | None = None,
        *,
        owner_loop: asyncio.AbstractEventLoop | None = None,
    ) -> RoomConnection | None:
        """Wait `LOOKUP_DELAY_SECONDS`, then open the connection as usual.

        `owner_loop` is handed on only when the caller gave one, so that the
        wait is the same for a caller that does not know the keyword.
        """
        time.sleep(LOOKUP_DELAY_SECONDS)
        if owner_loop is None:
            return super().connect(code, account_id)
        return super().connect(code, account_id, owner_loop=owner_loop)


def at_once(count: int, action: Callable[[], object]) -> list[object]:
    """Run `action` in `count` threads that start together; what each returned.

    The threads wait on one barrier, then each runs `action` once. An exception
    that an action raises is its thread's result. A thread still running after
    `BURST_TIMEOUT_SECONDS` gives no result, so the list is then shorter.

    Returns:
        The results, in the order in which the threads finished.
    """
    barrier = threading.Barrier(count)
    results: list[object] = []
    lock = threading.Lock()

    def run_once() -> None:
        try:
            barrier.wait(BURST_TIMEOUT_SECONDS)
            result = action()
        except Exception as error:  # the test reports it as this thread's result
            result = error
        with lock:
            results.append(result)

    threads: list[threading.Thread] = []
    for _ in range(count):
        thread = threading.Thread(target=run_once, daemon=True)
        thread.start()
        threads.append(thread)
    deadline = time.monotonic() + BURST_TIMEOUT_SECONDS
    for thread in threads:
        thread.join(max(deadline - time.monotonic(), 0.0))
    with lock:
        return list(results)
