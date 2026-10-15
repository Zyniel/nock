"""Tests of spec 019, AC-4: the author of the selected letter, in words.

While the switch is on, `clue-bar` names the author of the selected cell's
confirmed letter in `clue-bar-author`, after `clue-bar-text`. The first tests use
the snapshot of AC-1 at the default window; the last two use a FX-02 snapshot at
the window sizes of spec 006 AC-5, in desktop and touch contexts. The shared setup
is in `spec019_harness`.

Choices where the spec leaves room:

- "FX-02's longest clue" is the clue with the most characters in its text, read
  from `tests/fixtures/fx02.json`; the test checks that only one clue has that
  length. Its word's first cell is selected by tapping the clue (spec 007: with
  every cell filled, a tapped clue selects its word's first cell).
- FX-02's letter cells are all filled with `E` by `p2`, with `solved` false, so the
  page shows spec 026's `full_wrong` status line, as any full grid would.
- Spec 009 AC-4's font-size check of `clue-bar-text` (14 px or more) is run in the
  touch contexts it names (360 by 740 and 740 by 360), since the spec says spec
  009 AC-4 keeps holding.
- "It sits on the line of the clue text when there is room" is not tested: the
  spec does not say when there is room. The height rule at 568 by 320 and 740 by
  360 is tested.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.grid import ClueCell, Grid, LetterCell
from nock.protocol import GridView, grid_view
from spec019_harness import (
    CONTEXT_KINDS,
    LAYOUT_EPSILON_PX,
    SETTLE_MS,
    WINDOW_IDS,
    WINDOW_SIZES,
    ChangeList,
    OpenWindow,
    authors_switch,
    box_of,
    cell_at,
    expect_seq,
    grid_from_text,
    layout_problems,
    load_fr,
    open_ac1,
    open_room,
    player_left_frame,
    player_view,
    press,
    turn_switch_off,
    turn_switch_on,
    window_opener,
    with_letter_cells,
)

LONG_NICKNAME = "Bartholomew Lefebvre"
FX02_CELL_COUNT = 13 * 17
TIGHT_WINDOWS = [(568, 320), (740, 360)]
KEYBOARD_WINDOWS = [(360, 740), (740, 360)]  # spec 009 AC-4's touch contexts
MIN_CLUE_FONT_PX = 14.0

AUTHOR_PLACE_SCRIPT = """
() => {
  const bar = document.querySelector('[data-testid="clue-bar"]');
  const text = document.querySelector('[data-testid="clue-bar-text"]');
  const author = document.querySelector('[data-testid="clue-bar-author"]');
  const position = text.compareDocumentPosition(author);
  return {
    inBar: bar.contains(author),
    afterText: (position & Node.DOCUMENT_POSITION_FOLLOWING) !== 0,
    insideText: text.contains(author),
  };
}
"""


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


# ---- Helpers of these tests -------------------------------------------------


def author_line(page: Page) -> Locator:
    return page.get_by_test_id("clue-bar-author")


def selected_text(name: str) -> str:
    """`t("authors.selected", { name })`, built from `fr.json`."""
    return load_fr()["authors.selected"].replace("{name}", name)


# ---- AC-4: the snapshot of AC-1 ---------------------------------------------


def test_ac4_fr_json_has_the_selected_author_text() -> None:
    assert load_fr()["authors.selected"] == "Lettre de {name}"


def test_ac4_tapping_a_letter_names_its_author_after_the_clue_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)

    cell_at(page, 1, 1).click()

    expect(author_line(page)).to_have_text(selected_text("Bob"))
    expect(author_line(page)).to_have_text("Lettre de Bob")
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Passoire fine")
    place = page.evaluate(AUTHOR_PLACE_SCRIPT)
    assert place == {"inBar": True, "afterText": True, "insideText": False}


def test_ac4_a_player_who_left_is_still_named(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    mock.send(player_left_frame(6, "p2"))
    expect_seq(page, 6)

    cell_at(page, 1, 3).click()

    expect(author_line(page)).to_have_text("Lettre de Bob")


def test_ac4_an_author_the_page_never_knew_is_named_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)

    cell_at(page, 1, 2).click()

    someone = load_fr()["feed.someone"]
    expect(author_line(page)).to_have_text(selected_text(someone))


def test_ac4_a_revealed_or_empty_cell_shows_no_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell_at(page, 1, 1).click()
    expect(author_line(page)).to_have_count(1)

    cell_at(page, 1, 4).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-column", "4")
    expect(author_line(page)).to_have_count(0)

    cell_at(page, 2, 1).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "2")
    expect(author_line(page)).to_have_count(0)


def test_ac4_switching_the_view_off_removes_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell_at(page, 1, 1).click()
    expect(author_line(page)).to_have_count(1)

    turn_switch_off(page)

    expect(author_line(page)).to_have_count(0)
    expect(page.get_by_test_id("clue-bar-text")).to_have_text("Passoire fine")


def test_ac4_no_author_while_the_switch_is_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    cell_at(page, 1, 1).click()

    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "0,0,0")
    page.wait_for_timeout(SETTLE_MS)
    expect(author_line(page)).to_have_count(0)


def test_ac4_no_author_while_nothing_is_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(page.get_by_test_id("clue-bar")).to_have_attribute("data-word", "")
    page.wait_for_timeout(SETTLE_MS)
    expect(author_line(page)).to_have_count(0)


def test_ac4_the_name_is_inserted_as_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "<b>Bo</b>", 3),
    ]
    open_ac1(page, live_server, fx01_grid, players)
    turn_switch_on(page)

    cell_at(page, 1, 1).click()

    expect(author_line(page)).to_have_text("Lettre de <b>Bo</b>")
    expect(author_line(page).locator("b")).to_have_count(0)


# ---- AC-4: FX-02 at every window size ---------------------------------------


def longest_clue(grid: Grid) -> tuple[int, int, int]:
    """The clue cell and index of the clue with the longest text (only one)."""
    found: list[tuple[int, tuple[int, int, int]]] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            for index, clue in enumerate(cell.clues):
                found.append((len(clue.text), (cell.row, cell.column, index)))
    longest = max(length for length, _ in found)
    winners = [where for length, where in found if length == longest]
    assert len(winners) == 1, f"several clues of {longest} characters: {winners}"
    return winners[0]


def fx02_all_by_p2(grid: Grid) -> GridView:
    """FX-02 with every letter cell holding `E`, written by `p2`."""
    changes: ChangeList = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            changes.append((cell.row, cell.column, {"letter": "E", "author": "p2"}))
    return with_letter_cells(grid_view(grid), changes)


def open_fx02_with_the_longest_clue_selected(
    page: Page, base_url: str, grid: Grid, touch: bool
) -> None:
    """The FX-02 snapshot, then a tap on its longest clue (the switch still off)."""
    assert len(LONG_NICKNAME) == 20
    players = [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", LONG_NICKNAME, 3),
    ]
    open_room(
        page,
        base_url,
        fx02_all_by_p2(grid),
        players,
        cell_count=FX02_CELL_COUNT,
    )
    row, column, index = longest_clue(grid)
    first_row, first_column = grid.word_cells(row, column, index)[0]
    clue = cell_at(page, row, column).get_by_test_id("clue").nth(index)
    press(clue, touch)
    grid_element = page.get_by_test_id("grid")
    expect(grid_element).to_have_attribute("data-word", f"{row},{column},{index}")
    expect(grid_element).to_have_attribute("data-selected-row", str(first_row))
    expect(grid_element).to_have_attribute("data-selected-column", str(first_column))


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES, ids=WINDOW_IDS)
def test_ac4_fx02_the_grid_keeps_its_room_with_the_author_shown(
    window: OpenWindow,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_fx02_with_the_longest_clue_selected(page, live_server, fx02_grid, touch)

    turn_switch_on(page, touch)

    expect(author_line(page)).to_have_text(selected_text(LONG_NICKNAME))
    assert layout_problems(page, touch) == []
    if touch and (width, height) in KEYBOARD_WINDOWS:
        font_size = page.get_by_test_id("clue-bar-text").evaluate(
            "el => parseFloat(getComputedStyle(el).fontSize)"
        )
        assert font_size >= MIN_CLUE_FONT_PX


@pytest.mark.parametrize("context_kind", CONTEXT_KINDS)
@pytest.mark.parametrize(
    ("width", "height"), TIGHT_WINDOWS, ids=[f"{w}x{h}" for w, h in TIGHT_WINDOWS]
)
def test_ac4_fx02_the_clue_bar_is_no_taller_with_the_author_shown(
    window: OpenWindow,
    live_server: str,
    fx02_grid: Grid,
    width: int,
    height: int,
    context_kind: str,
) -> None:
    touch = context_kind == "touch"
    page = window(width, height, touch)
    open_fx02_with_the_longest_clue_selected(page, live_server, fx02_grid, touch)
    bar = page.get_by_test_id("clue-bar")
    off_box = box_of(bar)

    turn_switch_on(page, touch)

    expect(author_line(page)).to_have_text(selected_text(LONG_NICKNAME))
    on_box = box_of(bar)
    off_height = off_box.bottom - off_box.top
    on_height = on_box.bottom - on_box.top
    assert abs(on_height - off_height) <= LAYOUT_EPSILON_PX
