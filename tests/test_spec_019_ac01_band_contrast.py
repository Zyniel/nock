"""Tests of spec 019, AC-1's contrast run: the band keeps 3:1 against its cell.

At 1280 by 720 in the desktop context, with the switch on, on FX-01 snapshots
(`seq` 10) where `you` is `p1` (colour 0) and `p2` to `p8` have colours 1 to 7.
There are nine bands: colours 0 to 7, by `p1` to `p8`, and the departed band, by
`p9`, who is not in the room. Each test opens one page and checks every state the
spec lists for it, reading each state in one `page.evaluate`:

- static states, one page per band: (0, 1) not selected, (4, 4) locked by a check
  and (3, 3) struck through; after a tap on (1, 0), (1, 0) selected and (1, 1) in
  my word; then (2, 2) tinted by each player with colour 1 to 7 in turn;
- flash states, one page per flash colour: nine cells flashing in that colour, one
  per band, as the spec builds them with `letter_changed` events from `seq` 11.

In every state the band's contrast, measured over its colours (`BAND_COLOURS_JS`
of `spec019_harness`), is at least 3:1, each colour that counts is opaque, and
the mark's own background colour is still its author's swatch colour (the first
item of "The view, switch on": "in every state of the cell"). A failing test
lists every state its page misses.

Choices where the spec leaves room:

- The static pages fill every letter cell with `X`, so the grid is full and wrong
  (spec 026 shows its status under the clue bar at this size).
- The tint of (2, 2) is waited for with spec 013's `data-tinted-by`, the cleared
  tint likewise; the selection and word with spec 007's `data-selected` and
  `data-in-word`; the lock and strike with `data-locked` and `data-wrong`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, GridView, grid_view
from spec013_harness import clear_frame, selection_frame
from spec019_harness import (
    BAND_COLOURS_JS,
    WAIT_TIMEOUT_MS,
    Cell,
    ChangeList,
    OpenWindow,
    band_contrast_problems,
    band_reading_from,
    band_readings,
    cell_at,
    eight_players,
    grid_from_text,
    letter_changed_frame,
    letter_positions_of,
    open_room,
    swatch_colour,
    turn_switch_on,
    window_opener,
    with_letter_cells,
)

CONTRAST_WIDTH = 1280
CONTRAST_HEIGHT = 720
SNAPSHOT_SEQ = 10
FIRST_EVENT_SEQ = 11
DEPARTED = "p9"

# The authors of the nine bands: colours 0 to 7 (p1 to p8), then the departed one.
BAND_AUTHORS = ["p1", "p2", "p3", "p4", "p5", "p6", "p7", "p8", DEPARTED]
BAND_IDS = [f"colour-{index}" for index in range(8)] + ["departed"]
FX01_LETTER_CELL_COUNT = 18

PLAIN_CELL: Cell = (0, 1)
LOCKED_CELL: Cell = (4, 4)
STRUCK_CELL: Cell = (3, 3)
TAPPED_CELL: Cell = (1, 0)
WORD_CELL: Cell = (1, 1)
TINTED_CELL: Cell = (2, 2)

# One cell per band on the flash pages, in the order of BAND_AUTHORS.
FLASH_CELLS: list[Cell] = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 1),
    (2, 2),
    (2, 3),
    (2, 4),
]

ALL_AUTHORS_SCRIPT = """
expected => expected.every(([row, column, author]) => {
  const cell = document.querySelector(
    `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`
  );
  return cell !== null && cell.getAttribute('data-author') === author;
})
"""

# One reading of a flash page: for each cell its `data-flash` and band, and the
# computed background colour of the swatch of the player whose colour flashes.
FLASH_SCRIPT = "args => {\n" + BAND_COLOURS_JS + r"""
  const swatch = document.querySelector(
    `[data-testid="roster-player"][data-player-id="${args.flashPlayer}"]`
    + ' [data-testid="roster-colour"]'
  );
  const cells = [];
  for (const [row, column] of args.cells) {
    const cell = document.querySelector(
      `[data-testid="cell"][data-row="${row}"][data-column="${column}"]`
    );
    cells.push({flash: cell.getAttribute('data-flash'), band: readBand(cell)});
  }
  return {swatch: getComputedStyle(swatch).backgroundColor, cells: cells};
}
"""


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- Helpers of these tests -------------------------------------------------


def static_view(grid: Grid, author: str) -> GridView:
    """Every letter cell holds `X` by `author`; (4, 4) locked, (3, 3) wrong."""
    changes: ChangeList = []
    for row, column in letter_positions_of(grid):
        update: dict[str, object] = {"letter": "X", "author": author}
        if (row, column) == LOCKED_CELL:
            update["locked"] = True
        if (row, column) == STRUCK_CELL:
            update["wrong"] = True
        changes.append((row, column, update))
    return with_letter_cells(grid_view(grid), changes)


def flash_view(grid: Grid) -> GridView:
    """The nine cells of FLASH_CELLS hold `X` by `p1`; the others are empty."""
    changes: ChangeList = []
    for row, column in FLASH_CELLS:
        changes.append((row, column, {"letter": "X", "author": "p1"}))
    return with_letter_cells(grid_view(grid), changes)


def author_swatches(page: Page) -> dict[str, str | None]:
    """Each band author's swatch colour; None for the departed author."""
    swatches: dict[str, str | None] = {DEPARTED: None}
    for author in BAND_AUTHORS:
        if author != DEPARTED:
            swatches[author] = swatch_colour(page, author)
    return swatches


def state_problems(
    page: Page, states: list[tuple[str, Cell]], swatch: str | None
) -> list[str]:
    """Read the bands of some states in one `page.evaluate` and check them."""
    cells = [cell for _, cell in states]
    readings = band_readings(page, cells)
    problems: list[str] = []
    for (state, cell), reading in zip(states, readings, strict=True):
        for problem in band_contrast_problems(reading, swatch):
            problems.append(f"{state} {cell}: {problem}")
    return problems


def player_with_colour(colour: int) -> str:
    """The id of the player with a colour index: `p1` to `p8` for 0 to 7."""
    return f"p{colour + 1}"


def flasher_of(flash_colour: int) -> str:
    """The player other than `p1` whose letters flash in `flash_colour`.

    For colour 0 it is `p9`, who is not in the room: spec 016 flashes a player it
    does not know in colour 0.
    """
    if flash_colour == 0:
        return DEPARTED
    return player_with_colour(flash_colour)


def flash_frames(flasher: str) -> list[str]:
    """The events of a flash page, back to back with consecutive seqs from 11.

    On each cell: `Y` from the flasher, which starts the flash, then, unless the
    flasher is the band's author, `Z` from the band's author, which keeps it.
    """
    frames: list[str] = []
    seq = FIRST_EVENT_SEQ
    for (row, column), author in zip(FLASH_CELLS, BAND_AUTHORS, strict=True):
        frames.append(letter_changed_frame(seq, row, column, "Y", flasher))
        seq += 1
        if author != flasher:
            frames.append(letter_changed_frame(seq, row, column, "Z", author))
            seq += 1
    return frames


# ---- AC-1: the contrast run, static states ----------------------------------


@pytest.mark.parametrize("author", BAND_AUTHORS, ids=BAND_IDS)
def test_ac1_the_band_keeps_3_to_1_in_every_static_state_of_its_cell(
    window: OpenWindow, live_server: str, fx01_grid: Grid, author: str
) -> None:
    page = window(CONTRAST_WIDTH, CONTRAST_HEIGHT, False)
    mock = open_room(
        page,
        live_server,
        static_view(fx01_grid, author),
        eight_players(),
        seq=SNAPSHOT_SEQ,
    )
    turn_switch_on(page)
    expect(page.get_by_test_id("author-mark")).to_have_count(FX01_LETTER_CELL_COUNT)
    expect(cell_at(page, *LOCKED_CELL)).to_have_attribute("data-locked", "true")
    expect(cell_at(page, *STRUCK_CELL)).to_have_attribute("data-wrong", "true")
    expect(cell_at(page, *PLAIN_CELL)).to_have_attribute("data-selected", "false")
    expect(cell_at(page, *PLAIN_CELL)).to_have_attribute("data-in-word", "false")
    swatch = author_swatches(page)[author]
    problems = state_problems(
        page,
        [
            ("not selected", PLAIN_CELL),
            ("locked", LOCKED_CELL),
            ("struck through", STRUCK_CELL),
        ],
        swatch,
    )

    cell_at(page, *TAPPED_CELL).click()
    expect(cell_at(page, *TAPPED_CELL)).to_have_attribute("data-selected", "true")
    expect(cell_at(page, *WORD_CELL)).to_have_attribute("data-in-word", "true")
    problems.extend(
        state_problems(
            page, [("selected", TAPPED_CELL), ("in my word", WORD_CELL)], swatch
        )
    )

    tinted_cell = cell_at(page, *TINTED_CELL)
    for colour in range(1, 8):
        player = player_with_colour(colour)
        mock.send(selection_frame(player, *TINTED_CELL, Direction.ACROSS))
        expect(tinted_cell).to_have_attribute("data-tinted-by", player)
        problems.extend(
            state_problems(page, [(f"tinted in colour {colour}", TINTED_CELL)], swatch)
        )
        mock.send(clear_frame(player))
        expect(tinted_cell).to_have_attribute("data-tinted-by", "")

    assert problems == [], f"band of {author}: {problems}"


# ---- AC-1: the contrast run, flash states -----------------------------------


@pytest.mark.parametrize("flash_colour", range(8), ids=lambda colour: f"f{colour}")
def test_ac1_every_band_keeps_3_to_1_on_a_cell_flashing_in_each_colour(
    window: OpenWindow, live_server: str, fx01_grid: Grid, flash_colour: int
) -> None:
    page = window(CONTRAST_WIDTH, CONTRAST_HEIGHT, False)
    mock = open_room(
        page, live_server, flash_view(fx01_grid), eight_players(), seq=SNAPSHOT_SEQ
    )
    turn_switch_on(page)
    expect(page.get_by_test_id("author-mark")).to_have_count(len(FLASH_CELLS))
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "")
    swatches = author_swatches(page)
    expected_authors: list[list[object]] = []
    for (row, column), author in zip(FLASH_CELLS, BAND_AUTHORS, strict=True):
        expected_authors.append([row, column, author])

    for frame in flash_frames(flasher_of(flash_colour)):
        mock.send(frame)
    page.wait_for_function(
        ALL_AUTHORS_SCRIPT, arg=expected_authors, timeout=WAIT_TIMEOUT_MS
    )
    reading = page.evaluate(
        FLASH_SCRIPT,
        {
            "cells": [list(cell) for cell in FLASH_CELLS],
            "flashPlayer": player_with_colour(flash_colour),
        },
    )

    problems: list[str] = []
    flash_swatch = reading["swatch"]
    for cell, author, found in zip(
        FLASH_CELLS, BAND_AUTHORS, reading["cells"], strict=True
    ):
        band = band_reading_from(found["band"])
        if found["flash"] != str(flash_colour):
            problems.append(f"{cell}: data-flash is {found['flash']!r}")
        if band.background != flash_swatch:
            problems.append(
                f"{cell}: background {band.background}, not the flash {flash_swatch}"
            )
        for problem in band_contrast_problems(band, swatches[author]):
            problems.append(f"{cell} band of {author}: {problem}")
    assert problems == [], f"flash in colour {flash_colour}: {problems}"
