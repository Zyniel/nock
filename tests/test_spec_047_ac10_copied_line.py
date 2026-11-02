"""Tests of spec 047, AC-10's clipboard check (Chromium only): a copy shows
« Lien copié » under the share row, while « Copier le lien » keeps its text.

On `SOLVED` (spec 044's) with the recap route answering `RECAP`, at 1280 by 720 in
a context with spec 011's clipboard permissions (`clipboard-read`,
`clipboard-write`), after `recap-open`: a click on `recap-copy` puts the share
link in the clipboard; `recap-copied` then shows under `recap-share-row` with
no live role, `fr.json["room.share.copied"]` and the confirmation line's look, and
is gone 2,500 ms after the click. The recap's own status region
(`sheet-status-region` inside `recap`, `client/hud.md` rule 18) reads
`fr.json["room.share.copied"]` (B-046, `gameplay/results.md` AC-13).

This file times a window (the 2-second line), so it belongs with the
timing-sensitive files that run serially (`SERIAL_TEST_FILES`).

Readings where the spec leaves room:

- "Under `recap-share-row`": its top at or below the row's bottom (1 px).
- "Gone 2,500 ms later": no `recap-copied` on the page, or none that shows, at
  most 2,500 ms after the click.
"""

from __future__ import annotations

import time
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from hud_harness import live_role_problems, region_problems, sheet_region
from nock.grid import Grid
from spec042_harness import box_of
from spec043_harness import fr_value, set_timeouts
from spec044_harness import solved_frame
from spec047_harness import (
    COMPUTER,
    GREEN,
    SHARE_PATH,
    open_loaded_recap,
    open_solved,
    type_problems,
)

GONE_AFTER_MS = 2500  # "gone 2,500 ms later"

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def clipboard_page(browser: Browser) -> Iterator[Page]:
    """A 1280 by 720 page whose context may read and write the clipboard."""
    viewport = {"width": COMPUTER[0], "height": COMPUTER[1]}
    context = browser.new_context(
        viewport=viewport, permissions=["clipboard-read", "clipboard-write"]
    )
    try:
        page = context.new_page()
        set_timeouts(page)
        yield page
    finally:
        context.close()


# ---- Setup -------------------------------------------------------------------------


def copy_the_link(page: Page, base_url: str, grid: Grid) -> float:
    """Open the recap, click `recap-copy`; return the click's `time.monotonic`."""
    open_solved(page, base_url, solved_frame(grid))
    open_loaded_recap(page)
    clicked = time.monotonic()
    page.get_by_test_id("recap-copy").click()
    return clicked


# ---- The copy ----------------------------------------------------------------------


@pytest.mark.only_browser("chromium")
def test_ac10_a_copy_puts_the_link_in_the_clipboard(
    clipboard_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    copy_the_link(clipboard_page, live_server, fx01_grid)

    expect(clipboard_page.get_by_test_id("recap-copied")).to_be_visible()
    copied = clipboard_page.evaluate("navigator.clipboard.readText()")
    assert copied == f"{live_server}{SHARE_PATH}"


@pytest.mark.only_browser("chromium")
def test_ac10_lien_copie_shows_under_the_row_while_the_button_keeps_its_text(
    clipboard_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    copy_the_link(clipboard_page, live_server, fx01_grid)
    copied = clipboard_page.get_by_test_id("recap-copied")

    expect(copied).to_be_visible()
    assert live_role_problems(copied) == []
    expect(copied).to_have_text(fr_value("room.share.copied"))
    region = sheet_region(clipboard_page, "recap")
    expect(region).to_have_text(fr_value("room.share.copied"))
    assert region_problems(region) == []
    expect(clipboard_page.get_by_test_id("recap-copy")).to_have_text(
        fr_value("room.share.copy")
    )
    row_box = box_of(clipboard_page.get_by_test_id("recap-share-row"))
    assert box_of(copied).top >= row_box.bottom - 1.0, (box_of(copied), row_box)
    problems = type_problems(
        copied, "recap-copied", size=13.6, weight="500", colour=GREEN
    )
    assert problems == []


@pytest.mark.only_browser("chromium")
def test_ac10_lien_copie_is_gone_2500_ms_after_the_click(
    clipboard_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    clicked = copy_the_link(clipboard_page, live_server, fx01_grid)
    copied = clipboard_page.get_by_test_id("recap-copied")
    expect(copied).to_be_visible()

    left_ms = max(1.0, GONE_AFTER_MS - (time.monotonic() - clicked) * 1000)

    expect(copied).to_be_hidden(timeout=left_ms)
