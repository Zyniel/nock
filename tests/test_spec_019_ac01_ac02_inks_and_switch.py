"""Tests of spec 019, AC-1 and AC-2: the authors switch and the letters' inks.

Refined by spec 045 (the design's Auteurs mode): the band `author-mark` is gone,
with its colour, its hatching, its box, drawing-order and contrast runs. While the
switch is on, each filled letter is drawn in its finder's ink: `data-author-colour`
is the finder's colour index and the cell's computed `color` (which its
`cell-letter` inherits) is `--player-ink-N`, compared with the inks of spec 045's
"Test harness" and with a probe `span` whose style is `color:
var(--player-ink-N)`; a letter with no finder (revealed, or by a player who is not
in the kept snapshot) is ink, rgb(20, 24, 31). AC-1 runs on a mocked socket and
on the live server. AC-2: with the switch off, no cell has a finder, there is no
`authors-legend`, and a letter's look does not depend on its author; a reload keeps
the switch as it was (`localStorage["nock.authors"]`). The shared setup is in
`spec019_harness`; the readers of the inks are spec 045's (`spec045_harness`).

Besides the criteria's own steps, the tests cover the edge cases the spec files
under AC-1 and AC-2: pending edits, a newcomer who takes a departed player's
colour index, the cell backgrounds the inks must not replace, the solved grid,
`data-author` with the switch on, and the switch's own rules (a `<button>` that
reads `Auteurs`, flips on each click and sends nothing).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Direction, Selection, SelectionMoved, grid_view
from room_panels import open_menu
from spec019_harness import (
    FOLLOW_MS,
    SETTLE_MS,
    ChangeList,
    EnterRoom,
    ac1_players,
    ac1_view,
    ana_types_t_and_bob_types_a,
    authors_switch,
    cell_at,
    cell_locked_frame,
    expect_seq,
    grid_from_text,
    letter_changed_frame,
    load_fr,
    open_ac1,
    open_room,
    player_joined_frame,
    player_left_frame,
    player_view,
    press_authors_switch,
    room_page,
    snapshot_frame,
    turn_switch_off,
    turn_switch_on,
    wait_until,
    with_letter_cells,
)
from spec045_harness import (
    AUTHORS_KEY,
    INK,
    INKS,
    cell_shows_within,
    colour_problems,
    finder_problems,
    ink_probe,
    read_cell,
)

FX01_SOLUTION = {
    (0, 1): "N",
    (1, 0): "T",
    (1, 1): "A",
    (1, 2): "M",
    (1, 3): "I",
    (1, 4): "S",
    (2, 1): "V",
    (2, 2): "I",
    (2, 3): "D",
    (2, 4): "E",
    (3, 1): "A",
    (3, 2): "M",
    (3, 3): "E",
    (3, 4): "N",
    (4, 1): "L",
    (4, 2): "E",
    (4, 3): "S",
    (4, 4): "T",
}

# What each of the 25 cells shows in `data-author-colour` once the switch is on,
# for the snapshot of AC-1: p1 has colour 0, p2 colour 3, p9 is not in the room.
AC1_AUTHOR_COLOURS = {(1, 0): "0", (1, 1): "3", (1, 3): "3"}

AUTHOR_COLOURS_SCRIPT = """
() => Array.from(document.querySelectorAll('[data-testid="cell"]')).map(cell => [
  Number(cell.dataset.row), Number(cell.dataset.column),
  cell.getAttribute('data-author-colour'),
])
"""

# The look of a letter cell: the computed colour, background colour, font style
# and font weight of the cell, and of each element whose own text is its letter.
LETTER_LOOK_SCRIPT = """
cell => {
  const pick = node => {
    const style = getComputedStyle(node);
    return [style.color, style.backgroundColor, style.fontStyle, style.fontWeight];
  };
  const letter = cell.getAttribute('data-letter');
  const holders = [];
  for (const node of [cell, ...cell.querySelectorAll('*')]) {
    for (const child of node.childNodes) {
      if (child.nodeType === Node.TEXT_NODE && child.textContent.trim() === letter) {
        holders.push(pick(node));
        break;
      }
    }
  }
  return {cell: pick(cell), letter: holders};
}
"""

LETTER_BACKGROUNDS_SCRIPT = """
() => Array.from(document.querySelectorAll(
  '[data-testid="cell"][data-type="letter"]'
)).map(cell => [
  Number(cell.dataset.row), Number(cell.dataset.column),
  getComputedStyle(cell).backgroundColor,
])
"""

AUTHOR_ATTRIBUTES_SCRIPT = """
() => Array.from(document.querySelectorAll(
  '[data-testid="cell"][data-type="letter"]'
)).map(cell => [
  Number(cell.dataset.row), Number(cell.dataset.column),
  cell.getAttribute('data-author'),
])
"""

ROSTER_COLOUR_SCRIPT = """
playerId => {
  const row = document.querySelector(
    `[data-testid="roster-player"][data-player-id="${playerId}"]`
  );
  return row === null ? null : row.getAttribute('data-colour');
}
"""


# ---- Fixtures ---------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- Helpers of these tests -------------------------------------------------


def author_colours(page: Page) -> dict[tuple[int, int], str | None]:
    """The `data-author-colour` of every cell (None: no attribute)."""
    found = page.evaluate(AUTHOR_COLOURS_SCRIPT)
    result: dict[tuple[int, int], str | None] = {}
    for row, column, value in found:
        result[(row, column)] = value
    return result


def expected_author_colours(
    coloured: dict[tuple[int, int], str],
) -> dict[tuple[int, int], str | None]:
    """Every FX-01 cell mapped to its `data-author-colour`: `""` unless listed."""
    result: dict[tuple[int, int], str | None] = {}
    for row in range(5):
        for column in range(5):
            result[(row, column)] = coloured.get((row, column), "")
    return result


def letter_look(page: Page, row: int, column: int) -> dict[str, list[object]]:
    look = cell_at(page, row, column).evaluate(LETTER_LOOK_SCRIPT)
    assert isinstance(look, dict)
    return look


def letter_backgrounds(page: Page) -> dict[tuple[int, int], str]:
    found = page.evaluate(LETTER_BACKGROUNDS_SCRIPT)
    result: dict[tuple[int, int], str] = {}
    for row, column, background in found:
        result[(row, column)] = background
    return result


def author_attributes(page: Page) -> dict[tuple[int, int], str | None]:
    found = page.evaluate(AUTHOR_ATTRIBUTES_SCRIPT)
    result: dict[tuple[int, int], str | None] = {}
    for row, column, author in found:
        result[(row, column)] = author
    return result


def expect_no_finder_anywhere(page: Page) -> None:
    """No cell has a finder, no `author-mark` and no `authors-legend` exist."""
    expect(page.get_by_test_id("author-mark")).to_have_count(0)
    expect(page.get_by_test_id("authors-legend")).to_have_count(0)
    assert author_colours(page) == expected_author_colours({})


def expect_same_look_for_three_authors(page: Page) -> None:
    """(1, 0) by p1, (1, 1) by p2 and (1, 2) by p9 look the same, in ink."""
    by_p1 = letter_look(page, 1, 0)
    by_p2 = letter_look(page, 1, 1)
    by_p9 = letter_look(page, 1, 2)
    assert by_p2 == by_p1
    assert by_p9 == by_p1
    for row, column in [(1, 0), (1, 1), (1, 2)]:
        reading = read_cell(page, row, column)
        assert colour_problems(f"({row}, {column})", reading, INK) == []


def ac1_ink_problems(page: Page) -> list[str]:
    """How the AC-1 snapshot's letters differ from their inks with the switch on."""
    problems = finder_problems("(1, 0)", read_cell(page, 1, 0), "0", INKS[0])
    problems.extend(finder_problems("(1, 1)", read_cell(page, 1, 1), "3", INKS[3]))
    problems.extend(finder_problems("(1, 3)", read_cell(page, 1, 3), "3", INKS[3]))
    problems.extend(finder_problems("(1, 2)", read_cell(page, 1, 2), "", INK))
    problems.extend(finder_problems("(1, 4)", read_cell(page, 1, 4), "", INK))
    return problems


# ---- AC-1: the switch on, mocked socket -------------------------------------


def test_ac1_the_switch_on_draws_each_letter_in_its_finders_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    press_authors_switch(page)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    assert ac1_ink_problems(page) == []


def test_ac1_each_ink_is_the_colour_of_a_probe_of_its_token(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    assert tuple(read_cell(page, 1, 0)["colour"]) == ink_probe(page, 0)
    assert tuple(read_cell(page, 1, 1)["colour"]) == ink_probe(page, 3)


def test_ac1_a_letter_locked_by_a_check_keeps_its_ink_and_its_weight(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(cell_at(page, 1, 3)).to_have_attribute("data-author-colour", "3")
    reading = read_cell(page, 1, 3)
    assert reading["fontWeight"] == "700"
    assert colour_problems("(1, 3)", reading, INKS[3]) == []


def test_ac1_each_cell_has_its_finders_colour_index_and_no_cell_holds_a_band(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    assert author_colours(page) == expected_author_colours(AC1_AUTHOR_COLOURS)
    expect(page.get_by_test_id("author-mark")).to_have_count(0)


def test_ac1_inks_follow_each_event_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    problems: list[str] = []

    mock.send(letter_changed_frame(6, 1, 0, "X", "p2"))
    expect_seq(page, 6)
    reading = cell_shows_within(page, 1, 0, "3", INKS[3], FOLLOW_MS)
    problems.extend(finder_problems("seq 6 (1, 0)", reading, "3", INKS[3]))

    mock.send(letter_changed_frame(7, 1, 1, None, "p2"))
    expect_seq(page, 7)
    reading = cell_shows_within(page, 1, 1, "", INK, FOLLOW_MS)
    if reading["authorColour"] != "":
        problems.append(f"seq 7 (1, 1): data-author-colour {reading['authorColour']}")

    mock.send(cell_locked_frame(8, 1, 0, "T", revealed=True))
    expect_seq(page, 8)
    reading = cell_shows_within(page, 1, 0, "", INK, FOLLOW_MS)
    problems.extend(finder_problems("seq 8 (1, 0)", reading, "", INK))

    mock.send(player_left_frame(9, "p2"))
    expect_seq(page, 9)
    reading = cell_shows_within(page, 1, 3, "", INK, FOLLOW_MS)
    problems.extend(finder_problems("seq 9 (1, 3)", reading, "", INK))
    assert problems == []


def test_ac1_a_newcomer_with_the_departed_players_colour_takes_no_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    mock.send(player_left_frame(6, "p2"))
    expect_seq(page, 6)
    expect(cell_at(page, 1, 3)).to_have_attribute("data-author-colour", "")

    mock.send(player_joined_frame(7, player_view("p3", "Cy", 3)))
    expect_seq(page, 7)
    page.wait_for_timeout(FOLLOW_MS)

    problems: list[str] = []
    for row, column in [(1, 1), (1, 3)]:
        reading = read_cell(page, row, column)
        problems.extend(finder_problems(f"({row}, {column})", reading, "", INK))
    problems.extend(finder_problems("(1, 0)", read_cell(page, 1, 0), "0", INKS[0]))
    problems.extend(finder_problems("(1, 2)", read_cell(page, 1, 2), "", INK))
    assert problems == []


def test_ac1_a_letter_i_type_takes_my_ink_once_the_server_confirms_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell = cell_at(page, 2, 1)
    cell.click()

    page.keyboard.press("v")

    expect(cell).to_have_attribute("data-letter", "V")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    page.wait_for_timeout(SETTLE_MS)
    assert finder_problems("(2, 1)", read_cell(page, 2, 1), "", INK) == []

    mock.send(letter_changed_frame(6, 2, 1, "V", "p1"))
    expect_seq(page, 6)
    reading = cell_shows_within(page, 2, 1, "0", INKS[0], FOLLOW_MS)
    assert finder_problems("(2, 1)", reading, "0", INKS[0]) == []
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def test_ac1_a_pending_letter_over_another_authors_letter_keeps_that_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    cell = cell_at(page, 1, 1)
    cell.click()

    page.keyboard.press("b")

    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    page.wait_for_timeout(SETTLE_MS)
    assert finder_problems("(1, 1)", read_cell(page, 1, 1), "3", INKS[3]) == []


def test_ac1_the_inks_replace_no_cell_background(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    selection = Selection(row=2, column=2, direction=Direction.DOWN)
    mock.send(SelectionMoved(player_id="p2", selection=selection).model_dump_json())
    expect(cell_at(page, 3, 2)).to_have_attribute("data-tinted-by", "p2")
    cell_at(page, 1, 1).click()
    expect(cell_at(page, 1, 1)).to_have_attribute("data-selected", "true")
    # The focus is on the switch for both measures, so that only the view differs.
    turn_switch_on(page)
    turn_switch_off(page)
    backgrounds_off = letter_backgrounds(page)

    turn_switch_on(page)

    expect(cell_at(page, 1, 1)).to_have_attribute("data-author-colour", "3")
    assert letter_backgrounds(page) == backgrounds_off


def test_ac1_data_author_keeps_its_meaning_with_the_switch_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    authors_off = author_attributes(page)

    turn_switch_on(page)

    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    authors_on = author_attributes(page)
    assert authors_on == authors_off
    assert authors_on[(1, 0)] == "p1"
    assert authors_on[(1, 1)] == "p2"
    assert authors_on[(1, 2)] == "p9"
    assert authors_on[(1, 3)] == "p2"
    assert authors_on[(1, 4)] == ""


def solved_changes() -> ChangeList:
    """Every FX-01 letter right: row 0 and row 1 by p1, the rest by p2."""
    changes: ChangeList = []
    for (row, column), letter in FX01_SOLUTION.items():
        author = "p1" if row <= 1 else "p2"
        changes.append((row, column, {"letter": letter, "author": author}))
    return changes


def test_ac1_the_switch_keeps_working_on_a_solved_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    view = with_letter_cells(grid_view(fx01_grid), solved_changes())
    open_room(page, live_server, view, ac1_players(), solved=True)
    expect(room_page(page)).to_have_attribute("data-solved", "true")
    open_menu(page)
    switch = authors_switch(page)
    expect(switch).to_be_enabled()

    press_authors_switch(page)

    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(cell_at(page, 4, 4)).to_have_attribute("data-author-colour", "3")
    problems = finder_problems("(1, 0)", read_cell(page, 1, 0), "0", INKS[0])
    problems.extend(finder_problems("(4, 4)", read_cell(page, 4, 4), "3", INKS[3]))
    assert problems == []


# ---- AC-1: the switch on, live server ---------------------------------------


def roster_colour_index(page: Page, player_id: str) -> int:
    """A player's colour index, read from their `roster-player`'s `data-colour`."""
    found = page.evaluate(ROSTER_COLOUR_SCRIPT, player_id)
    assert isinstance(found, str), f"no roster-player data-colour for {player_id}"
    return int(found)


def test_ac1_live_each_letter_has_the_ink_of_its_authors_colour_index(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        ana_id, bob_id = ana_types_t_and_bob_types_a(
            page, bob_page, f"{live_server}/r/{code}", enter_room
        )

        press_authors_switch(page)

        expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
        ana_colour = roster_colour_index(page, ana_id)
        bob_colour = roster_colour_index(page, bob_id)
        expect(cell_at(page, 1, 0)).to_have_attribute(
            "data-author-colour", str(ana_colour)
        )
        t_cell = read_cell(page, 1, 0)
        a_cell = read_cell(page, 1, 1)
        problems = colour_problems("(1, 0)", t_cell, INKS[ana_colour])
        problems.extend(colour_problems("(1, 1)", a_cell, INKS[bob_colour]))
        assert problems == []
    finally:
        bob_context.close()


# ---- AC-2: the switch off ---------------------------------------------------


def test_ac2_the_switch_is_a_button_reading_auteurs_that_starts_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    open_menu(page)  # spec 043: the switch is a Menu item, named once it shows
    switch = authors_switch(page)

    expect(switch).to_have_count(1)
    assert switch.evaluate("el => el.tagName") == "BUTTON"
    expect(switch).to_have_attribute("type", "button")
    assert load_fr()["authors.switch"] == "Auteurs"
    expect(switch).to_have_accessible_name("Auteurs")
    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(switch).to_be_enabled()


def test_ac2_with_the_switch_off_no_cell_has_a_finder_and_there_is_no_legend(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    expect_no_finder_anywhere(page)


def test_ac2_letters_by_different_authors_look_the_same(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    expect_same_look_for_three_authors(page)


def test_ac2_after_switching_on_then_off_letters_look_the_same_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author-colour", "0")

    turn_switch_off(page)

    expect_no_finder_anywhere(page)
    expect_same_look_for_three_authors(page)


def test_ac2_each_click_flips_the_switch(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    switch = authors_switch(page)

    for expected in ["true", "false", "true"]:
        press_authors_switch(page)
        expect(switch).to_have_attribute("aria-pressed", expected)


def test_ac2_clicking_the_switch_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    sent_before = len(mock.frames_without_pings())

    turn_switch_on(page)
    turn_switch_off(page)
    page.wait_for_timeout(SETTLE_MS)

    assert mock.frames_without_pings()[sent_before:] == []


def reload_ac1(page: Page, live_server: str, fx01_grid: Grid, turn_on: bool) -> None:
    """Open AC-1's page, set the switch, reload it and answer its join."""
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    if not turn_on:
        turn_switch_off(page)
    frames_before = len(mock.received)

    page.reload()

    wait_until(page, lambda: mock.has_join_after(frames_before))
    mock.send(snapshot_frame(ac1_view(fx01_grid), 5, ac1_players()))
    expect(room_page(page)).to_have_attribute("data-status", "joined")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")


def test_ac2_a_reload_after_turning_the_switch_off_keeps_it_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    reload_ac1(page, live_server, fx01_grid, turn_on=False)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    assert page.evaluate("key => localStorage.getItem(key)", AUTHORS_KEY) == "false"
    expect_no_finder_anywhere(page)


def test_ac2_a_reload_after_turning_the_switch_on_keeps_it_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    reload_ac1(page, live_server, fx01_grid, turn_on=True)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_test_id("authors-legend")).to_be_visible()
    assert ac1_ink_problems(page) == []
