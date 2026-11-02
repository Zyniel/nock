"""Shared setup of the tests of admin/operations, AC-22 to AC-30: the WAL checkpoint
and the operator page.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_operations_*.py`:

- `test_operations_checkpoint.py`: AC-22, AC-23 and AC-25's busy timeout, with no
  timing: `checkpoint_wal` on a connection that fakes its answers, and the five
  deletions and erasures that call it.
- `test_operations_checkpoint_busy.py`: AC-24 and AC-25, a second connection that
  holds a read open, and the time bounds. It measures durations (a busy timeout
  of 5 s against a bound of 1 s), so it runs in the serial pass
  (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

- `test_operations_page.py`: AC-26 to AC-30, the operator page: an answer that a
  later request superseded, a token of another shape, a lock that empties and
  focuses the input. A browser on the live ops server, with the dashboard and the
  replay answered by the test.

The same helpers serve `tests/test_account_erasure_busy.py` (account/account
AC-22). This module holds the two ways to look at a busy database: a second
connection that holds a read open, which makes a `TRUNCATE` checkpoint report
busy, and the size of the WAL file; and, for the page, the held dashboard and
replay routes, the log of the page's ops requests and the checks of the locked
form.
"""

from __future__ import annotations

import contextlib
import json
import logging
import re
import sqlite3
from collections.abc import Iterator, Sequence
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import Page, Request, Route, expect

from nock.store import RoomStore
from spec032_harness import Run
from spec038_harness import (
    HELD_POLL_MS,
    OPS_TIMEOUT_MS,
    OPS_TOKEN_KEY,
    expect_ops_state,
    load_fr,
)

LOGGER_PREFIX = "nock"


@contextlib.contextmanager
def holding_a_read(database_path: Path) -> Iterator[None]:
    """Hold a read transaction open on the database file, on a connection of its own.

    A `TRUNCATE` checkpoint cannot empty the WAL while a reader uses it, so every
    checkpoint of the other connections to the file is busy until the block ends.
    """
    reader = sqlite3.connect(database_path, isolation_level=None)
    try:
        reader.execute("BEGIN")
        reader.execute("SELECT COUNT(*) FROM rooms").fetchall()
        yield
    finally:
        reader.close()


def wal_size(database_path: Path) -> int:
    """The size in bytes of the WAL file, 0 for a WAL that was emptied or is absent."""
    wal_path = database_path.with_name(database_path.name + "-wal")
    if not wal_path.exists():
        return 0
    return wal_path.stat().st_size


def write_room(store: RoomStore, room: Run) -> None:
    """Write a played room to the store: first state, log, then its last state."""
    store.create_room(room.initial)
    store.append(room.initial.code, room.log)
    store.save_snapshot(room.state)


def warnings_logged(caplog: pytest.LogCaptureFixture) -> list[logging.LogRecord]:
    """The records captured at WARNING or above, whatever logger wrote them."""
    records: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.levelno >= logging.WARNING:
            records.append(record)
    return records


# ---- The operator page (AC-26 to AC-30) --------------------------------------------

FRAMES_TO_WAIT = 2
EDITS_CODE = re.compile(r"/api/ops/rooms/([^/]+)/edits")
LATE_ANSWER_TIMEOUT_MS = 5_000

# Resolves after the page has drawn `frames` frames.
FRAMES_SCRIPT = """
(frames) => new Promise((resolve) => {
  const next = (left) => {
    if (left === 0) {
      resolve(null);
    } else {
      requestAnimationFrame(() => next(left - 1));
    }
  };
  next(frames);
})
"""


def let_the_page_draw(page: Page) -> None:
    """Wait until the page has drawn two frames, so a late answer has been applied."""
    page.evaluate(FRAMES_SCRIPT, FRAMES_TO_WAIT)


def json_answer(route: Route, status: int, body: object) -> None:
    """Fulfil a held or mocked request with a JSON body."""
    route.fulfill(status=status, content_type="application/json", body=json.dumps(body))


class OpsRequests:
    """The requests a page makes to `/api/ops/`, recorded from now on."""

    def __init__(self, page: Page) -> None:
        self.requests: list[Request] = []
        page.on("request", self._keep)

    def _keep(self, request: Request) -> None:
        if "/api/ops/" in request.url:
            self.requests.append(request)

    def urls(self) -> list[str]:
        """The URL of each request."""
        found: list[str] = []
        for request in self.requests:
            found.append(request.url)
        return found

    def authorizations(self) -> list[str | None]:
        """The `Authorization` header of each request."""
        found: list[str | None] = []
        for request in self.requests:
            found.append(request.header_value("authorization"))
        return found


class HeldDashboard:
    """Answers the page's first dashboard request, holds the later ones by period.

    A held request is answered by the test with `answer`, in the order it wants.
    """

    def __init__(self, first: tuple[int, str]) -> None:
        self.first = first
        self.first_seen = False
        self.held: dict[int, Route] = {}

    def handle(self, route: Route) -> None:
        """Answer the first request; hold the others under their `days`."""
        if not self.first_seen:
            self.first_seen = True
            status, body = self.first
            route.fulfill(status=status, content_type="application/json", body=body)
            return
        query = parse_qs(urlparse(route.request.url).query)
        self.held[int(query["days"][0])] = route

    def wait_for(self, page: Page, periods: Sequence[int]) -> None:
        """Wait until a request for each of the `periods` is held."""
        waited_ms = 0
        while not all(days in self.held for days in periods):
            assert (
                waited_ms < OPS_TIMEOUT_MS
            ), f"held {sorted(self.held)}, not {periods}"
            page.wait_for_timeout(HELD_POLL_MS)
            waited_ms += HELD_POLL_MS

    def answer(self, days: int, answer: tuple[int, str]) -> None:
        """Answer the held request of one period."""
        status, body = answer
        self.held[days].fulfill(
            status=status, content_type="application/json", body=body
        )


class HeldReplays:
    """Answers the replay requests of the page; those of `held_codes` wait.

    `answer` is the status and body given to every code that is not held.
    """

    def __init__(self, answer: tuple[int, object], held_codes: Sequence[str]) -> None:
        self.answer = answer
        self.held_codes = list(held_codes)
        self.held: dict[str, Route] = {}

    def handle(self, route: Route) -> None:
        """Hold the request of a held code; answer any other."""
        found = EDITS_CODE.search(route.request.url)
        assert found is not None, route.request.url
        code = found.group(1)
        if code in self.held_codes:
            self.held[code] = route
            return
        status, body = self.answer
        json_answer(route, status, body)

    def wait_for(self, page: Page, code: str) -> None:
        """Wait until the request for `code` is held."""
        waited_ms = 0
        while code not in self.held:
            assert waited_ms < OPS_TIMEOUT_MS, f"no held request for {code}"
            page.wait_for_timeout(HELD_POLL_MS)
            waited_ms += HELD_POLL_MS

    def release(self, code: str, status: int, body: object) -> None:
        """Answer the held request of `code`."""
        json_answer(self.held[code], status, body)


def seed_stored_token(page: Page, token: str) -> None:
    """Put `token` in the tab's `sessionStorage` before the page loads."""
    script = f"sessionStorage.setItem({json.dumps(OPS_TOKEN_KEY)}, {json.dumps(token)})"
    page.context.add_init_script(script)


def expect_refused_form(page: Page) -> None:
    """The page is `locked` on the form with « Jeton refusé. », the input empty and
    focused."""
    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-error")).to_have_text(
        load_fr()["ops.token_refused"]
    )
    token_input = page.get_by_test_id("ops-token-input")
    expect(token_input).to_have_value("")
    expect(token_input).to_be_focused()
