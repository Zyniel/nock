"""Shared setup of the tests of content/cards, AC-10 to AC-13: which key the
device's progress is read from and written to.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in:

- `test_cards_progress_keys.py`: AC-10, the pills read both device keys.
- `test_cards_progress_marks.py`: AC-11 and AC-13, « Jouer » and « Rejouer »
  write one key.
- `test_cards_progress_solve.py`: AC-12, a solve writes one key.

All run on the live server serving `CAT` (accounts off), with the account routes
answered by `page.route`. The setup of AC-7 to AC-9 (`RequestLog`, the pills
readers, `nock.progress`) is in `library_harness.py`.
"""

from __future__ import annotations

import json
import re

from playwright.sync_api import Page, expect

from library_harness import PROGRESS_KEY
from spec010_harness import ROOM_URL_PATTERN, item_play_button, read_storage
from spec029_harness import history_item
from spec042_harness import wait_until
from spec046_harness import WAIT_TIMEOUT_MS

ACCOUNT_PROGRESS_KEY = "nock.account_progress"
ROOM_SOCKET_PATTERN = re.compile(r".*/api/rooms/[A-Z0-9]{6}/ws$")


def stored_object(page: Page, key: str) -> object:
    """The `localStorage` item `key` parsed as JSON, or None when it is absent."""
    raw = read_storage(page, key)
    if raw is None:
        return None
    return json.loads(raw)


def wait_for_stored(page: Page, key: str, expected: object) -> None:
    """Wait until the item `key` parses to `expected` (None: absent), else fail."""
    wait_until(
        page,
        lambda: stored_object(page, key) == expected,
        f"{key} to hold {expected!r}",
    )


def open_grid(page: Page, base_url: str, number: int) -> None:
    """Open `/g/<number>` and wait until `grid-page` is `ready`."""
    page.goto(f"{base_url}/g/{number}")
    expect(page.get_by_test_id("grid-page")).to_have_attribute("data-state", "ready")


def tap_play(page: Page, number: int) -> None:
    """Tap « Jouer » on card `number` and wait until a room page loads."""
    item_play_button(page, number).click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=WAIT_TIMEOUT_MS)


def tap_replay(page: Page, code: str) -> None:
    """Tap « Rejouer » on the history row of room `code` and wait for the room."""
    row = history_item(page, code)
    expect(row).to_be_visible()
    row.get_by_test_id("history-replay").click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=WAIT_TIMEOUT_MS)


def device_keys(page: Page) -> tuple[object, object]:
    """`nock.progress` and `nock.account_progress`, parsed (None when absent)."""
    return stored_object(page, PROGRESS_KEY), stored_object(page, ACCOUNT_PROGRESS_KEY)
