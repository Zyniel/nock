"""Tests of `client/room.md` AC-8: « Rien à annuler. » is announced by the status
region, not by the note.

At 1280 by 720, joined as Ana on FX-01 with a mocked socket, Ana presses « Annuler »
twice, 1 s apart, and the server answers `nothing_to_undo` each time. The note
`undo-message` shows « Rien à annuler. » with no live role (`client/hud.md` rule
17), and after each press the page's status region reads it, having been empty in
between: the same message twice is announced twice.

Readings where the spec leaves room:

- "Having been empty in between" is read from a `MutationObserver` on the region
  (`hud_harness.record_region_texts`): once the empty states before the first
  message and after the last one are left out, the region went from the message to
  empty and back to the message.
- The look and the place of the note are tested by spec 043 AC-26
  (`test_spec_043_ac26_notes.py`).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, expect

from hud_harness import (
    UNDO_NOTHING_TEXT,
    announcements_of,
    expect_page_region_reads,
    live_role_problems,
    open_fx01_room,
    press_undo_answered_nothing,
    record_region_texts,
    recorded_region_texts,
)
from nock.grid import Grid
from spec019_harness import OpenWindow, window_opener
from spec043_harness import COMPUTER

PRESS_GAP_MS = 1000  # "1 s apart"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def test_ac8_the_note_has_no_live_role_and_the_region_announces_each_press(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    mock = open_fx01_room(page, live_server, fx01_grid)
    record_region_texts(page)
    note = page.get_by_test_id("undo-message")

    press_undo_answered_nothing(page, mock)

    expect(note).to_have_text(UNDO_NOTHING_TEXT)
    assert live_role_problems(note) == []
    expect_page_region_reads(page, UNDO_NOTHING_TEXT)

    page.wait_for_timeout(PRESS_GAP_MS)
    press_undo_answered_nothing(page, mock)

    expect(note).to_have_text(UNDO_NOTHING_TEXT)
    assert live_role_problems(note) == []
    expect_page_region_reads(page, UNDO_NOTHING_TEXT)
    states = announcements_of(recorded_region_texts(page))
    assert states == [UNDO_NOTHING_TEXT, "", UNDO_NOTHING_TEXT]
