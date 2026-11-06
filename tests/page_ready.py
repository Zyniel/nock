"""Wait until a room page's code has loaded after its `goto` (DRAFT-053, B-100).

The room page's code loads as its own chunk, one round trip after the entry
script. Under heavy parallel load, the harness waits of 5 s for the room page's
first state (its nickname form, or its first socket) ran out before the chunk had
run, while each test passed alone. A harness opener therefore first waits for the
room page itself with `PAGE_READY_TIMEOUT_MS`, as conftest's `enter_room` and spec
043's `open_room` already do. This bounds how long a test waits for a page to
load, on a machine shared with other browser runs: it is no budget of the product
(the room route's load time is spec 036's AC-1, measured on its own).

Pytest does not collect this module (its name does not start with `test_`).
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

PAGE_READY_TIMEOUT_MS = 10_000


def wait_for_room_page(page: Page) -> None:
    """Wait until `page`, sent to a room's address, shows its room page.

    Args:
        page: A page whose `goto` to `/r/<code>` has returned.
    """
    expect(page.get_by_test_id("room-page")).to_be_attached(
        timeout=PAGE_READY_TIMEOUT_MS
    )
