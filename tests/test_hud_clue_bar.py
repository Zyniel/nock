"""Tests of `client/hud.md` AC-16: what a tap on a reaction pill does.

AC-16 keeps the numbered tests of spec 043 AC-23 to AC-25 for the clue bar, the
picker and the pill's look. This file holds what the criterion adds: Bob's reaction
is a pill drawn on top of IDES's clue, and a tap on the pill selects IDES.

Readings where the spec leaves room:

- Bob is `p2` (nickname BOB in the snapshot); his reaction is a `clap` on IDES, the
  clue at (0, 3), index 0, shown by a `reaction` frame.
- "Selects IDES" is the selection spec 007 gives a tap on a clue: the grid's
  selected word is `0,3,0` and its selected cell is (1, 3). Nothing is selected
  before the tap.
- The tap is a tap in a touch window of 360 by 740, a click in a window of 1280 by
  720. It lands on the pill's own box: Playwright refuses an action whose target is
  hidden by another element, so the pill has to take the press.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Reaction
from spec019_harness import OpenWindow, window_opener
from spec043_harness import (
    COMPUTER,
    IDES,
    PHONE,
    expect_selected,
    expect_word,
    fx01_view,
    open_room,
    players_up_to,
    reaction_frame,
    snapshot_frame,
)

IDES_WORD = "0,3,0"
IDES_SELECTED_CELL = (1, 3)

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def open_with_bobs_reaction(
    window: OpenWindow, base_url: str, grid: Grid, size: tuple[int, int], touch: bool
) -> Page:
    """FX-01 with nothing selected, once Bob's `clap` on IDES shows as a pill."""
    page = window(size[0], size[1], touch)
    frame = snapshot_frame(fx01_view(grid), players_up_to(3))
    mock = open_room(page, base_url, frame)
    mock.send(reaction_frame("p2", IDES, Reaction.CLAP))
    expect(page.get_by_test_id("clue-reaction")).to_have_count(1)
    return page


# ---- AC-16: a tap on the pill ------------------------------------------------------


@pytest.mark.parametrize(
    ("size", "touch"), [(PHONE, True), (COMPUTER, False)], ids=["360x740", "1280x720"]
)
def test_ac16_a_tap_on_bobs_pill_selects_ides(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    size: tuple[int, int],
    touch: bool,
) -> None:
    page = open_with_bobs_reaction(window, live_server, fx01_grid, size, touch)
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-word", "")
    pill = page.get_by_test_id("clue-reaction")
    expect(pill).to_have_attribute("data-player-id", "p2")

    if touch:
        pill.tap()
    else:
        pill.click()

    expect_word(page, IDES_WORD)
    expect(grid).to_have_attribute("data-word", IDES_WORD)
    expect_selected(page, IDES_SELECTED_CELL[0], IDES_SELECTED_CELL[1])
