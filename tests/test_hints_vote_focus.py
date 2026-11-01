"""Tests of `gameplay/hints.md` AC-25: the vote's buttons give the focus to the grid
before they are disabled (rule 19).

AC-25: on Bob's vote, Ana's unvoted page has « Oui » focused and (1, 0) selected;
her socket closes: once « Oui » and « Non » are disabled the focus is on the grid,
(1, 0) still selected, and no ballot was sent. « Non » focused does the same.

Readings where the spec leaves room:

- The socket closes with 1011, as a lost connection does; the page then waits to
  join again and the mock answers its new join with nothing, so the page stays not
  joined (`hud_harness.LOST_CLOSE_CODE`).
- "Once disabled" is the buttons' `disabled` attribute; "the focus is on the grid"
  is read from then on, as Playwright retries it for 5 s.
- "No ballot was sent" is no `vote` frame among the frames the page sent, from the
  focus on the button to 300 ms after the buttons are disabled.
- The room is in help mode `vote` with 3 players and Ana the host; Bob's vote is
  spec 043's `vote_opened_frame` (vote 1, a grid check, 3 voters).
"""

from __future__ import annotations

import json
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, expect

from hud_harness import LOST_CLOSE_CODE
from nock.grid import Grid
from nock.protocol import HelpMode
from spec019_harness import OpenWindow, window_opener
from spec043_harness import (
    COMPUTER,
    QUIET_MS,
    expect_selected,
    fx01_view,
    open_room,
    players_up_to,
    press_cell,
    send_and_wait,
    snapshot_frame,
    vote_opened_frame,
)

DISABLED_TIMEOUT_MS = 10_000
VOTE_SEQ = 6


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


@pytest.mark.parametrize("button", ["vote-yes", "vote-no"])
def test_ac25_a_lost_connection_gives_the_focus_to_the_grid_and_sends_no_ballot(
    window: OpenWindow, live_server: str, fx01_grid: Grid, button: str
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    frame = snapshot_frame(
        fx01_view(fx01_grid), players_up_to(3), help_mode=HelpMode.VOTE
    )
    mock = open_room(page, live_server, frame)
    press_cell(page, 1, 0)
    send_and_wait(page, mock, vote_opened_frame(VOTE_SEQ, "p2"))
    focused_button = page.get_by_test_id(button)
    expect(focused_button).to_be_enabled()
    focused_button.focus()
    expect(focused_button).to_be_focused()
    expect_selected(page, 1, 0)

    mock.close(LOST_CLOSE_CODE)

    expect(page.get_by_test_id("vote-yes")).to_be_disabled(timeout=DISABLED_TIMEOUT_MS)
    expect(page.get_by_test_id("vote-no")).to_be_disabled()
    expect(page.get_by_test_id("grid")).to_be_focused()
    expect_selected(page, 1, 0)
    page.wait_for_timeout(QUIET_MS)
    sent_types = [json.loads(sent)["type"] for sent in mock.frames_without_pings()]
    assert "vote" not in sent_types, sent_types
