"""Tests of spec 019, AC-4: the players named in words, each in their ink, and a
clue bar that keeps only the clue.

Refined by spec 045 (the design's Auteurs mode): the clue bar's line
`clue-bar-author` (« Lettre de … ») is gone, with its rules of following the
selected cell (decision 12) and of shrinking first on a low window (decision 11).
While the switch is on, `authors-legend` under the grid names every player of the
kept snapshot in their ink: on the snapshot of AC-1, its `authors-legend-label`
reads `fr.json["authors.legend"]`, then `Ana` and `Bob` in their inks
(`--player-ink-0`, `--player-ink-3`); after `player_left` (seq 6) of `p2` it reads
`Ana` only; switching the view off removes it. A tap on (1, 1) shows no
`clue-bar-author` and `clue-bar-text` reads `Passoire fine`. The last test uses
spec 026's `FX02_FULL_WRONG` page with `p2`'s nickname 20 characters long, at the
window sizes of spec 006 AC-5, in desktop and touch contexts: spec 013 AC-6's
checks pass with the switch on, and at 568 by 320 and 740 by 360 `clue-bar` is as
high with the switch on as with it off (1 px). The shared setup is in
`spec019_harness`; the legend's readers are spec 045's (`spec045_harness`).

Choices where the spec leaves room:

- Spec 026's page is built as its AC-10 tests build it: the eight players of
  spec 013 AC-6 (`p2` renamed), 100 feed lines (`check_result` events of `p2` on
  the grid, `seq` 6 to 105), then a tap on the clue `On la glisse dans une
  enveloppe` at (0, 6), which selects (1, 6), with the switch still off.
- Spec 009 AC-4's font-size check of `clue-bar-text` (14 px or more) is run in the
  touch contexts it names (360 by 740 and 740 by 360), since the spec says spec
  009 AC-4 keeps holding.
- "After `player_left`" is read within 300 ms of the moment `room-page` shows its
  seq, as spec 045 measures the legend's names.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import GridTarget
from spec013_harness import check_frame
from spec019_harness import (
    CONTEXT_KINDS,
    FX02_CELL_COUNT,
    LAYOUT_EPSILON_PX,
    WINDOW_IDS,
    WINDOW_SIZES,
    OpenWindow,
    box_of,
    cell_at,
    eight_players,
    expect_seq,
    fx02_full_wrong_view,
    grid_from_text,
    layout_problems,
    load_fr,
    open_ac1,
    open_room,
    player_left_frame,
    press,
    turn_switch_off,
    turn_switch_on,
    window_opener,
)
from spec043_harness import colour_matches
from spec045_harness import (
    INKS,
    legend_names,
    legend_of,
    legend_reading,
    name_texts,
    names_within,
    settle_layout,
)

LONG_NICKNAME = "Bartholomew Lefebvre"
TIGHT_WINDOWS = [(568, 320), (740, 360)]
KEYBOARD_WINDOWS = [(360, 740), (740, 360)]  # spec 009 AC-4's touch contexts
MIN_CLUE_FONT_PX = 14.0

# Spec 026's status page.
SNAPSHOT_SEQ = 5
LAST_FEED_SEQ = 105
LONGEST_CLUE = "On la glisse dans une enveloppe"
LONGEST_CLUE_CELL = (0, 6)
LONGEST_WORD = "0,6,0"
# Spec 043's 3-second note for `p2`'s last check covers the top row while it
# shows (a tap on it opens the Salon); it leaves the page 3,350 ms after it showed.
NOTE_GONE_TIMEOUT_MS = 5000
SELECTED_CELL = (1, 6)

SETTLE_LAYOUT_SCRIPT = (
    "() => new Promise(resolve =>"
    " requestAnimationFrame(() => requestAnimationFrame(resolve)))"
)


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def fx02_grid(fx02_text: str) -> Grid:
    return grid_from_text(fx02_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- AC-4: the snapshot of AC-1 ---------------------------------------------


def test_ac4_fr_json_has_the_legend_text_and_no_selected_author_text() -> None:
    messages = load_fr()

    assert messages.get("authors.legend") == "Auteurs :"
    assert "authors.selected" not in messages


def test_ac4_the_legend_names_ana_then_bob_in_their_inks(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    reading = legend_reading(page)
    label = reading["items"][0]
    assert label["testId"] == "authors-legend-label"
    assert label["text"].strip() == load_fr()["authors.legend"]
    names = legend_names(reading)
    assert [text.strip() for text in name_texts(reading)] == ["Ana", "Bob"]
    assert colour_matches(names[0]["colour"], INKS[0]), names[0]
    assert colour_matches(names[1]["colour"], INKS[3]), names[1]


def test_ac4_the_legend_is_under_the_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    legend = box_of(legend_of(page))
    grid = box_of(page.get_by_test_id("grid"))
    assert legend.top >= grid.bottom - LAYOUT_EPSILON_PX, (legend, grid)


def test_ac4_a_tap_on_a_letter_shows_no_author_line_and_the_whole_clue(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)

    cell_at(page, 1, 1).click()

    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Passoire fine")
    expect(page.get_by_test_id("clue-bar-author")).to_have_count(0)


def test_ac4_after_bob_leaves_the_legend_names_ana_only(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    legend_reading(page)

    mock.send(player_left_frame(6, "p2"))
    expect_seq(page, 6)

    reading = names_within(page, lambda found: name_texts(found) == ["Ana"])
    assert [text.strip() for text in name_texts(reading)] == ["Ana"]


def test_ac4_switching_the_view_off_removes_the_legend(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    expect(legend_of(page)).to_be_visible()

    turn_switch_off(page)

    expect(legend_of(page)).to_have_count(0)


# ---- AC-4: spec 026's FX-02 page at every window size -----------------------


def open_fx02_status_page(page: Page, base_url: str, grid: Grid, touch: bool) -> None:
    """Spec 026's `FX02_FULL_WRONG` page, `p2` with a 20-character nickname.

    The snapshot (`seq` 5), 100 feed lines (`seq` 6 to 105), then a tap on the
    clue `On la glisse dans une enveloppe`, which selects (1, 6). The switch is
    still off.
    """
    assert len(LONG_NICKNAME) == 20
    mock = open_room(
        page,
        base_url,
        fx02_full_wrong_view(grid),
        eight_players(LONG_NICKNAME),
        seq=SNAPSHOT_SEQ,
        cell_count=FX02_CELL_COUNT,
    )
    for seq in range(SNAPSHOT_SEQ + 1, LAST_FEED_SEQ + 1):
        mock.send(check_frame(seq, "p2", GridTarget()))
    expect_seq(page, LAST_FEED_SEQ)
    expect(page.get_by_test_id("room-note")).to_have_count(
        0, timeout=NOTE_GONE_TIMEOUT_MS
    )
    clue = cell_at(page, *LONGEST_CLUE_CELL).get_by_test_id("clue")
    press(clue.filter(has_text=LONGEST_CLUE), touch)
    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", LONGEST_WORD)
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-selected-row", str(SELECTED_CELL[0]))
    expect(grid_element).to_have_attribute(
        "data-selected-column", str(SELECTED_CELL[1])
    )
    expect(page.get_by_test_id("clue-bar-text")).to_have_text(LONGEST_CLUE)
    expect(page.get_by_test_id("grid-status")).to_have_attribute(
        "data-state", "full_wrong"
    )
    if touch:
        expect(page.get_by_test_id("keyboard")).to_be_visible()
    page.evaluate(SETTLE_LAYOUT_SCRIPT)


def bar_height(page: Page) -> float:
    bar = box_of(page.get_by_test_id("clue-bar"))
    return bar.bottom - bar.top


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac4_fx02_the_grid_keeps_its_room_and_the_clue_bar_its_height(
    window: OpenWindow,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    tight = (width, height) in TIGHT_WINDOWS
    page = window(width, height, touch)
    open_fx02_status_page(page, live_server, fx02_grid, touch)
    height_off = bar_height(page)

    turn_switch_on(page, touch)

    expect(legend_of(page)).to_be_visible()
    settle_layout(page)
    problems = layout_problems(page, touch)
    expect(page.get_by_test_id("clue-bar-author")).to_have_count(0)
    if touch and (width, height) in KEYBOARD_WINDOWS:
        font_size = page.get_by_test_id("clue-bar-text").evaluate(
            "el => parseFloat(getComputedStyle(el).fontSize)"
        )
        if font_size < MIN_CLUE_FONT_PX:
            problems.append(f"clue-bar-text has a font-size of {font_size} px")
    if tight:
        height_on = bar_height(page)
        if abs(height_on - height_off) > LAYOUT_EPSILON_PX:
            problems.append(
                f"clue-bar is {height_on:.1f} px high with the switch on and "
                f"{height_off:.1f} px with it off"
            )
    assert problems == [], f"{width}x{height} {context_kind}: {problems}"
