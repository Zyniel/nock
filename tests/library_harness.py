"""Shared setup of the tests of content/library, AC-22 to AC-24: the account's
progress on the catalogue and the grid page.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_library_*.py`:

- `test_library_progress.py`: AC-22 to AC-24, browser with the live server serving
  `CAT`, the account routes answered by `page.route` and `nock.progress` seeded.

The device's progress is `DEVICE_PROGRESS` and the account's `ACCOUNT_PROGRESS`
(AC-22's storage and answer). Merged, grids 1, 2 and 3 read `finished`, `started`
and `finished`; from the device alone, `started`, none and `finished`.
"""

from __future__ import annotations

import json
from urllib.parse import urlsplit

from playwright.sync_api import Page, Request, Route, expect

from spec004_harness import item_by_number, load_fr
from spec032_harness import read_storage, seed_storage
from spec042_harness import wait_until
from spec046_harness import fulfil_json

PROGRESS_KEY = "nock.progress"
ACCOUNT_PROGRESS_PATH = "/api/account/progress"
ACCOUNT_PROGRESS_ROUTE = "**/api/account/progress"
STATUS_PATH = "/api/account"
QUIET_MS = 500  # "never asks": nothing within this pause

DEVICE_PROGRESS = {"1": "started", "3": "finished"}
ACCOUNT_PROGRESS = {"1": "finished", "2": "started", "3": "started"}
MERGED = {1: "finished", 2: "started", 3: "finished"}
DEVICE_ONLY = {1: "started", 2: "none", 3: "finished"}

# What AC-24's answers have in common with a failure: no progress from the account.
FAILING_ANSWERS = ["401", "404", "500", "array", "bad value", "request fails"]


class RequestLog:
    """The GET requests a page makes to the grid and account APIs, and the answers.

    `answered` counts the requests of the account's progress that ended, with an
    answer or by failing.
    """

    def __init__(self, page: Page) -> None:
        self.paths: list[str] = []
        self.answered = 0
        page.on("request", self._record)
        page.on("requestfinished", self._finished)
        page.on("requestfailed", self._finished)

    def _record(self, request: Request) -> None:
        path = urlsplit(request.url).path
        is_api = path.startswith("/api/grids") or path.startswith("/api/account")
        if request.method == "GET" and is_api:
            self.paths.append(path)

    def _finished(self, request: Request) -> None:
        if urlsplit(request.url).path == ACCOUNT_PROGRESS_PATH:
            self.answered += 1

    def count(self, path: str) -> int:
        """How many GET requests asked `path`."""
        return self.paths.count(path)


def seed_device_progress(page: Page) -> None:
    """Put AC-22's `nock.progress` in the page's storage before its scripts run."""
    seed_storage(page, {PROGRESS_KEY: json.dumps(DEVICE_PROGRESS)})


def stored_progress(page: Page) -> object:
    """`nock.progress` parsed, or None when it is absent."""
    raw = read_storage(page, PROGRESS_KEY)
    if raw is None:
        return None
    return json.loads(raw)


def answer_failing(page: Page, kind: str) -> None:
    """Answer the account's progress route as `kind` (one of `FAILING_ANSWERS`)."""

    def handle(route: Route) -> None:
        if kind == "request fails":
            route.abort()
        elif kind == "array":
            fulfil_json(route, 200, [1])
        elif kind == "bad value":
            fulfil_json(route, 200, {"1": "done", "3": "started"})
        else:
            fulfil_json(route, int(kind), {"detail": "no"})

    page.route(ACCOUNT_PROGRESS_ROUTE, handle)


def wait_for_progress_answers(page: Page, log: RequestLog, count: int) -> None:
    """Wait until `count` requests of the account's progress have ended."""
    wait_until(
        page,
        lambda: log.answered >= count,
        f"{count} answers of {ACCOUNT_PROGRESS_PATH}",
    )


def expect_progress(page: Page, number: int, progress: str) -> None:
    """Expect card `number` to show `progress` (`started`, `finished` or `none`)."""
    item = item_by_number(page, number)
    pill = item.get_by_test_id("catalogue-progress")
    expect(item).to_have_attribute("data-progress", progress)
    if progress == "none":
        expect(pill).to_have_count(0)
    else:
        expect(pill).to_have_text(load_fr()[f"catalogue.progress.{progress}"])


def expect_progresses(page: Page, progresses: dict[int, str]) -> None:
    """Expect each card of `progresses` to show its progress."""
    for number, progress in progresses.items():
        expect_progress(page, number, progress)
