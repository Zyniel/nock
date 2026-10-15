"""Tests of spec 024, AC-9: a revealed cell is marked by more than its colour, and
the reveal controls meet spec 035.

The page is driven with a mocked socket. The contrast scan, the language scan and
the keyboard walker (`tab_to`) are spec 035's. The mark's contrast is measured over
its colours, as "Client: revealed cells" says since the lead's refinement of
2026-10-15. The flash run (decision 14) reads the flash as spec 016 AC-2's tests
do: `data-flash` holds the colour index, and the cell's background is the colour
of the matching roster swatch. The edge case "Revealed while flashing" is tested by
the flash run. The shared setup is in `spec024_harness`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import CellTarget, LetterChanged, PlayerView, RevealBudget
from spec024_harness import (
    COLOUR_CONTRAST_JS,
    MARK_COLOURS_JS,
    SOLUTION,
    WAIT_TIMEOUT_MS,
    Cell,
    ChangeList,
    MockRoomSocket,
    cell_at,
    cell_locked_frame,
    cell_selector,
    contrast_problems,
    expect_selection,
    expect_seq,
    grid_from_text,
    language_data,
    language_problems,
    load_fr,
    make_catalogue,
    make_walker,
    mark_contrast,
    mark_problems,
    open_room,
    outline_problems,
    player_view,
    reveal_result_frame,
)

SCAN_SIZES = [(1280, 720), (360, 740)]
MIN_MARK_CONTRAST = 3.0
LETTER_CELLS = [(0, 1), *[(1, column) for column in range(5)]]
for _row in range(2, 5):
    for _column in range(1, 5):
        LETTER_CELLS.append((_row, _column))

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[Callable[[int, int], Page]]:
    """Return `new_page(width, height)`, a page in a fresh context of that size."""
    contexts: list[BrowserContext] = []

    def make(width: int, height: int) -> Page:
        context = browser.new_context(viewport={"width": width, "height": height})
        contexts.append(context)
        return context.new_page()

    yield make
    for context in contexts:
        context.close()


# ---- The state of AC-9 ----


def ac9_changes() -> ChangeList:
    """(1, 0) holds `T` revealed; (1, 1) holds `A` locked by a check of `p2`."""
    return [
        (1, 0, {"letter": "T", "locked": True, "revealed": True, "author": None}),
        (1, 1, {"letter": "A", "locked": True, "revealed": False, "author": "p2"}),
    ]


def open_ac9(page: Page, live_server: str, grid: Grid) -> MockRoomSocket:
    """The FX-01 snapshot of AC-9: seq 10, `you` `p1` (host), players `p1`, `p2`."""
    return open_room(page, live_server, grid, changes=ac9_changes(), seq=10)


# ---- AC-9 ----


def test_ac9_the_new_fr_json_key_of_a_revealed_cell() -> None:
    assert load_fr()["a11y.revealed"] == "lettre révélée"


def test_ac9_a_revealed_cell_holds_the_corner_mark_and_the_hidden_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-revealed", "true")
    expect(cell).to_have_attribute("data-letter", "T")
    expect(cell.get_by_test_id("reveal-mark")).to_have_count(1)
    label = cell.get_by_test_id("reveal-label")
    expect(label).to_have_count(1)
    expect(label).to_have_text(load_fr()["a11y.revealed"])
    expect(label).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))
    assert mark_problems(cell) == []


def test_ac9_a_cell_locked_by_a_check_holds_neither_mark_nor_label(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    cell = cell_at(page, 1, 1)
    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-revealed", "false")
    expect(cell.get_by_test_id("reveal-mark")).to_have_count(0)
    expect(cell.get_by_test_id("reveal-label")).to_have_count(0)


def test_ac9_every_other_letter_cell_is_not_revealed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)

    for row, column in LETTER_CELLS:
        if (row, column) == (1, 0):
            continue
        cell = cell_at(page, row, column)
        expect(cell).to_have_attribute("data-revealed", "false")
        expect(cell.get_by_test_id("reveal-mark")).to_have_count(0)
        expect(cell.get_by_test_id("reveal-label")).to_have_count(0)
    expect(page.get_by_test_id("reveal-mark")).to_have_count(1)


def test_ac9_the_mark_keeps_3_to_1_against_the_cell_selected_or_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac9(page, live_server, fx01_grid)
    cell = cell_at(page, 1, 0)
    expect(cell).to_have_attribute("data-revealed", "true")

    not_selected = mark_contrast(cell)
    cell.click()
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "1")
    expect(grid).to_have_attribute("data-selected-column", "0")
    selected = mark_contrast(cell)

    assert not_selected >= MIN_MARK_CONTRAST
    assert selected >= MIN_MARK_CONTRAST


def open_scanned_state(page: Page, live_server: str, grid: Grid) -> None:
    """AC-9's state with (2, 2) tapped and the reveal controls shown."""
    open_ac9(page, live_server, grid)
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("reveal-letter")).to_be_visible()
    expect(page.get_by_test_id("reveal-word")).to_be_visible()
    expect(cell_at(page, 1, 0)).to_have_attribute("data-revealed", "true")


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=["desktop", "phone"])
def test_ac9_the_contrast_scan_finds_no_offending_element(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_scanned_state(page, live_server, fx01_grid)

    assert contrast_problems(page) == []


@pytest.mark.parametrize(("width", "height"), SCAN_SIZES, ids=["desktop", "phone"])
def test_ac9_the_language_scan_finds_no_offending_element(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    width: int,
    height: int,
) -> None:
    page = new_page(width, height)
    open_scanned_state(page, live_server, fx01_grid)

    data = language_data(live_server, ["Ana", "Bob"])
    assert language_problems(page, data) == []


def test_ac9_the_keyboard_reaches_both_reveal_buttons_with_a_visible_focus(
    new_page: Callable[[int, int], Page], live_server: str, fx01_grid: Grid
) -> None:
    page = new_page(1280, 720)
    open_ac9(page, live_server, fx01_grid)
    walker = make_walker(page)

    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_selection(page, 1, 2, "across", "0,0,0")
    for test_id in ("reveal-letter", "reveal-word"):
        walker.tab_to(test_id)
        expect(page.get_by_test_id(test_id)).to_be_enabled()
        expect(page.get_by_test_id(test_id)).to_be_focused()

    reached = {step.test_id: step for step in walker.reached}
    for test_id in ("reveal-letter", "reveal-word"):
        step = reached[test_id]
        problems = outline_problems(
            step.outline_style, step.outline_width, step.outline_contrast
        )
        assert problems == [], step


# ---- AC-9, flash run: the mark keeps 3:1 on each flash colour (decision 14) ----

# The eight cells of the flash run; the cell at position c + 1 flashes in colour c.
FLASH_CELLS: list[Cell] = [
    (1, 0),
    (1, 1),
    (1, 2),
    (1, 3),
    (1, 4),
    (2, 1),
    (2, 2),
    (2, 3),
]
FLASH_NICKNAMES = ["Ana", "Bob", "Cleo", "Dan", "Eve", "Fay", "Gus", "Hal"]
FLASH_SNAPSHOT_SEQ = 10
FLASH_BUDGET = RevealBudget(letters=8, words=1)
ABSENT_PLAYER = "p9"  # not in the roster: spec 016 flashes it in colour 0

# Polled on each animation frame: false until the cell's `data-revealed` is
# `true`, then, read at once, the cell's `data-flash`, its computed background,
# the computed background of the roster swatch of the player whose colour
# flashes, the grid's selected cell, and the colours of the cell's corner mark.
FLASH_READING_SCRIPT = (
    "([selector, swatchPlayerId]) => {\n" + COLOUR_CONTRAST_JS + MARK_COLOURS_JS + r"""
  const cell = document.querySelector(selector);
  if (cell === null || cell.getAttribute('data-revealed') !== 'true') {
    return false;
  }
  const grid = document.querySelector('[data-testid="grid"]');
  const swatch = document.querySelector(
    `[data-testid="roster-player"][data-player-id="${swatchPlayerId}"] `
    + '[data-testid="roster-colour"]'
  );
  const marks = cell.querySelectorAll('[data-testid="reveal-mark"]');
  const colours = marks.length === 1 ? markColours(cell, marks[0]) : [];
  return {
    flash: cell.getAttribute('data-flash'),
    background: getComputedStyle(cell).backgroundColor,
    swatch: swatch === null ? null : getComputedStyle(swatch).backgroundColor,
    selected: [
      grid.getAttribute('data-selected-row'),
      grid.getAttribute('data-selected-column'),
    ],
    marks: marks.length,
    colours: colours,
    ratio: highestRatio(colours),
  };
}
"""
)


def flash_players() -> list[PlayerView]:
    """`p1` (you, host, colour 0), then `p2` to `p8` with the colours 1 to 7."""
    players = [player_view("p1", FLASH_NICKNAMES[0], 0, is_host=True)]
    for colour in range(1, 8):
        players.append(player_view(f"p{colour + 1}", FLASH_NICKNAMES[colour], colour))
    return players


def flash_changes() -> ChangeList:
    """The eight cells of the flash run hold `X` written by `p1`, unlocked."""
    changes: ChangeList = []
    for row, column in FLASH_CELLS:
        changes.append((row, column, {"letter": "X", "author": "p1"}))
    return changes


def replacer_of(colour: int) -> str:
    """The player whose letter makes a cell flash in `colour`."""
    if colour == 0:
        return ABSENT_PLAYER
    return f"p{colour + 1}"


def swatch_owner_of(colour: int) -> str:
    """The roster player whose swatch shows `colour` (`p1` for colour 0)."""
    return f"p{colour + 1}"


def letter_changed_frame(seq: int, row: int, column: int, player_id: str) -> str:
    """The JSON text of a `letter_changed` that writes `Y` for `player_id`."""
    event = LetterChanged(
        seq=seq, row=row, column=column, letter="Y", pencil=False, player_id=player_id
    )
    return event.model_dump_json()


def send_flash_then_reveal(mock: MockRoomSocket, colour: int) -> None:
    """Send back to back the three frames of the flash run for one colour.

    A `letter_changed` from the player whose colour is `colour`, a
    `reveal_result` for the cell (1 letter fewer than before), then its
    `cell_locked` with its solution letter, `revealed` true.

    Args:
        mock: The page's mocked socket.
        colour: The colour index c; the cell is the one at position c + 1.
    """
    row, column = FLASH_CELLS[colour]
    first_seq = FLASH_SNAPSHOT_SEQ + 1 + 3 * colour
    left = RevealBudget(letters=FLASH_BUDGET.letters - colour - 1, words=1)
    target = CellTarget(row=row, column=column)
    mock.send(letter_changed_frame(first_seq, row, column, replacer_of(colour)))
    mock.send(reveal_result_frame(first_seq + 1, target, left, player_id="p1"))
    solution = SOLUTION[(row, column)]
    mock.send(cell_locked_frame(first_seq + 2, row, column, solution, revealed=True))


def read_at_reveal(page: Page, colour: int) -> dict[str, Any]:
    """Wait for the cell of `colour` to be revealed, and read it at that moment."""
    row, column = FLASH_CELLS[colour]
    handle = page.wait_for_function(
        FLASH_READING_SCRIPT,
        arg=[cell_selector(row, column), swatch_owner_of(colour)],
        timeout=WAIT_TIMEOUT_MS,
    )
    reading = handle.json_value()
    assert isinstance(reading, dict), reading
    return reading


def flash_problems(
    reading: dict[str, Any], colour: int, selected: list[str] | None
) -> list[str]:
    """How one reading of the flash run breaks AC-9.

    Args:
        reading: What `read_at_reveal` read.
        colour: The colour index c the cell flashes in.
        selected: The row and column the grid must show as selected, as text, or
            None in the run without a tap.

    Returns:
        One line per broken rule; an empty list when the reading meets AC-9.
    """
    problems: list[str] = []
    if reading["flash"] != str(colour):
        problems.append(f"data-flash is {reading['flash']!r}, not {colour!r}")
    if reading["swatch"] is None:
        problems.append(f"no roster swatch for {swatch_owner_of(colour)}")
    elif reading["background"] != reading["swatch"]:
        problems.append(
            f"background {reading['background']} is not the swatch {reading['swatch']}"
        )
    if selected is not None and reading["selected"] != selected:
        problems.append(f"selected cell {reading['selected']}, expected {selected}")
    if reading["marks"] != 1:
        problems.append(f"{reading['marks']} reveal-mark elements in the cell")
    elif reading["ratio"] < MIN_MARK_CONTRAST:
        problems.append(f"mark contrast {reading['ratio']}: {reading['colours']}")
    return problems


@pytest.mark.parametrize("selected", [False, True], ids=["unselected", "selected"])
def test_ac9_the_mark_keeps_3_to_1_while_the_cell_flashes_in_each_colour(
    new_page: Callable[[int, int], Page],
    live_server: str,
    fx01_grid: Grid,
    selected: bool,
) -> None:
    page = new_page(1280, 720)
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        changes=flash_changes(),
        players=flash_players(),
        seq=FLASH_SNAPSHOT_SEQ,
        left=FLASH_BUDGET,
        allowance=FLASH_BUDGET,
    )
    problems: dict[int, list[str]] = {}
    readings: dict[int, dict[str, Any]] = {}

    for colour in range(8):
        row, column = FLASH_CELLS[colour]
        cell = cell_at(page, row, column)
        expect(cell).to_have_attribute("data-revealed", "false")
        expected_selection: list[str] | None = None
        if selected:
            cell.click(timeout=WAIT_TIMEOUT_MS)
            grid = page.get_by_test_id("grid")
            expect(grid).to_have_attribute("data-selected-row", str(row))
            expect(grid).to_have_attribute("data-selected-column", str(column))
            expected_selection = [str(row), str(column)]
        send_flash_then_reveal(mock, colour)
        reading = read_at_reveal(page, colour)
        readings[colour] = reading
        found = flash_problems(reading, colour, expected_selection)
        if found:
            problems[colour] = found

    expect_seq(page, FLASH_SNAPSHOT_SEQ + 3 * 8)
    assert problems == {}, readings
