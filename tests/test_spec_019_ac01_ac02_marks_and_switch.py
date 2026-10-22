"""Tests of spec 019, AC-1 and AC-2: the authors switch and the marks.

AC-1: with the switch on, each letter cell with an author holds one `author-mark`
in that author's colour, and a departed author's band is hatched in ink and
white (spec 041: the hatch has no grey) while no player's band has a pattern
(mocked socket and live server). AC-2: with the switch off, no mark exists and
a letter's look does not depend on its author (mocked socket). The shared setup
is in `spec019_harness`. AC-1's contrast run and box run have files of their own.

Besides the criteria's own steps, the tests cover the edge cases the spec files
under AC-1 and AC-2: pending edits, a newcomer who takes a departed player's
colour index, the cell backgrounds the band must not replace, the solved grid,
`data-author` with the switch on, and the switch's own rules (a `<button>` that
reads `Auteurs`, flips on each click, sends nothing and starts off after a
reload).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import Direction, Selection, SelectionMoved, grid_view
from spec019_harness import (
    FOLLOW_MS,
    SETTLE_MS,
    ChangeList,
    EnterRoom,
    ac1_players,
    ac1_view,
    ana_types_t_and_bob_types_a,
    authors_switch,
    band_readings,
    box_of,
    cell_at,
    cell_locked_frame,
    expect_seq,
    grid_from_text,
    hatched_problems,
    letter_changed_frame,
    load_fr,
    mark_box_problems,
    marks_in,
    marks_of,
    only_mark_of,
    open_ac1,
    open_room,
    pattern_problems,
    player_joined_frame,
    player_left_frame,
    player_view,
    press_authors_switch,
    room_page,
    snapshot_frame,
    swatch_colour,
    turn_switch_off,
    turn_switch_on,
    wait_until,
    with_letter_cells,
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
AC1_AUTHOR_COLOURS = {(1, 0): "0", (1, 1): "3", (1, 2): "", (1, 3): "3"}

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


def expect_no_mark_anywhere(page: Page) -> None:
    expect(page.get_by_test_id("author-mark")).to_have_count(0)
    assert author_colours(page) == expected_author_colours({})


def expect_same_look_for_three_authors(page: Page) -> None:
    """(1, 0) by p1, (1, 1) by p2 and (1, 2) by p9 look the same."""
    by_p1 = letter_look(page, 1, 0)
    by_p2 = letter_look(page, 1, 1)
    by_p9 = letter_look(page, 1, 2)
    assert by_p2 == by_p1
    assert by_p9 == by_p1


# ---- AC-1: the switch on, mocked socket -------------------------------------


def test_ac1_the_switch_on_marks_each_letter_in_its_authors_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    press_authors_switch(page)

    expect(authors_switch(page)).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_test_id("author-mark")).to_have_count(4)
    by_p1 = only_mark_of(page, 1, 0)
    assert by_p1.colour == "0"
    assert by_p1.background == swatch_colour(page, "p1")
    for row, column in [(1, 1), (1, 3)]:
        by_p2 = only_mark_of(page, row, column)
        assert by_p2.colour == "3"
        assert by_p2.background == swatch_colour(page, "p2")


def test_ac1_only_the_band_of_an_author_not_in_the_room_is_hatched_ink_and_white(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(page.get_by_test_id("author-mark")).to_have_count(4)
    assert only_mark_of(page, 1, 2).colour == ""
    cells = [(1, 0), (1, 1), (1, 2), (1, 3)]
    readings = band_readings(page, cells)
    problems: dict[tuple[int, int], list[str]] = {}
    for cell, reading in zip(cells, readings, strict=True):
        if cell == (1, 2):
            found = hatched_problems(reading)
        else:
            found = pattern_problems(reading)
        if found:
            problems[cell] = found
    assert problems == {}


def test_ac1_revealed_empty_and_clue_cells_hold_no_mark(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(marks_in(page, 1, 0)).to_have_count(1)
    marked = {(1, 0), (1, 1), (1, 2), (1, 3)}
    for row in range(5):
        for column in range(5):
            if (row, column) not in marked:
                assert marks_of(page, row, column) == [], f"({row}, {column})"


def test_ac1_each_cell_has_its_authors_colour_index(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(marks_in(page, 1, 0)).to_have_count(1)
    assert author_colours(page) == expected_author_colours(AC1_AUTHOR_COLOURS)


def test_ac1_each_mark_is_a_visible_hidden_band_along_the_bottom_of_its_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)

    turn_switch_on(page)

    expect(page.get_by_test_id("author-mark")).to_have_count(4)
    for row, column in [(1, 0), (1, 1), (1, 2), (1, 3)]:
        mark = only_mark_of(page, row, column)
        assert mark.aria_hidden == "true", f"({row}, {column})"
        assert mark.text.strip() == "", f"({row}, {column})"
        assert mark.visibility == "visible", f"({row}, {column})"
        cell_box = box_of(cell_at(page, row, column))
        assert mark_box_problems(cell_box, mark.box) == [], f"({row}, {column})"


def test_ac1_marks_follow_each_event_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    expect(marks_in(page, 1, 0)).to_have_count(1)

    mock.send(letter_changed_frame(6, 1, 0, "X", "p2"))
    expect_seq(page, 6)
    expect(marks_in(page, 1, 0)).to_have_attribute(
        "data-colour", "3", timeout=FOLLOW_MS
    )

    mock.send(letter_changed_frame(7, 1, 1, None, "p2"))
    expect_seq(page, 7)
    expect(marks_in(page, 1, 1)).to_have_count(0, timeout=FOLLOW_MS)

    mock.send(cell_locked_frame(8, 1, 0, "T", revealed=True))
    expect_seq(page, 8)
    expect(marks_in(page, 1, 0)).to_have_count(0, timeout=FOLLOW_MS)

    mock.send(player_left_frame(9, "p2"))
    expect_seq(page, 9)
    expect(marks_in(page, 1, 3)).to_have_attribute("data-colour", "", timeout=FOLLOW_MS)
    assert hatched_problems(band_readings(page, [(1, 3)])[0]) == []


def test_ac1_a_newcomer_with_the_departed_players_colour_changes_no_mark(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    mock.send(player_left_frame(6, "p2"))
    expect_seq(page, 6)
    expect(marks_in(page, 1, 3)).to_have_attribute("data-colour", "")

    mock.send(player_joined_frame(7, player_view("p3", "Cy", 3)))
    expect_seq(page, 7)
    page.wait_for_timeout(FOLLOW_MS)

    for row, column in [(1, 1), (1, 3)]:
        mark = only_mark_of(page, row, column)
        assert mark.colour == "", f"({row}, {column})"
        assert mark.background != swatch_colour(page, "p3"), f"({row}, {column})"
    assert only_mark_of(page, 1, 0).colour == "0"
    assert only_mark_of(page, 1, 2).colour == ""


def test_ac1_a_letter_i_type_gets_its_mark_once_the_server_confirms_it(
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
    assert marks_of(page, 2, 1) == []
    assert cell.get_attribute("data-author-colour") == ""

    mock.send(letter_changed_frame(6, 2, 1, "V", "p1"))
    expect_seq(page, 6)
    expect(marks_in(page, 2, 1)).to_have_attribute(
        "data-colour", "0", timeout=FOLLOW_MS
    )
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def test_ac1_a_pending_letter_over_another_authors_letter_keeps_that_mark(
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
    mark = only_mark_of(page, 1, 1)
    assert mark.colour == "3"
    assert mark.background == swatch_colour(page, "p2")
    assert cell.get_attribute("data-author-colour") == "3"


def test_ac1_the_band_replaces_no_cell_background(
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

    expect(marks_in(page, 1, 1)).to_have_count(1)
    assert letter_backgrounds(page) == backgrounds_off


def test_ac1_data_author_keeps_its_meaning_with_the_switch_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    authors_off = author_attributes(page)

    turn_switch_on(page)

    expect(marks_in(page, 1, 0)).to_have_count(1)
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
    switch = authors_switch(page)
    expect(switch).to_be_enabled()

    press_authors_switch(page)

    expect(switch).to_have_attribute("aria-pressed", "true")
    expect(page.get_by_test_id("author-mark")).to_have_count(18)
    assert only_mark_of(page, 1, 0).colour == "0"
    assert only_mark_of(page, 4, 4).colour == "3"


# ---- AC-1: the switch on, live server ---------------------------------------


def test_ac1_live_each_mark_has_the_colour_of_its_authors_swatch(
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
        expect(marks_in(page, 1, 0)).to_have_count(1)
        assert only_mark_of(page, 1, 0).background == swatch_colour(page, ana_id)
        assert only_mark_of(page, 1, 1).background == swatch_colour(page, bob_id)
    finally:
        bob_context.close()


# ---- AC-2: the switch off ---------------------------------------------------


def test_ac2_the_switch_is_a_button_reading_auteurs_that_starts_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    switch = authors_switch(page)

    expect(switch).to_have_count(1)
    assert switch.evaluate("el => el.tagName") == "BUTTON"
    expect(switch).to_have_attribute("type", "button")
    assert load_fr()["authors.switch"] == "Auteurs"
    expect(switch).to_have_accessible_name("Auteurs")
    expect(switch).to_have_attribute("aria-pressed", "false")
    expect(switch).to_be_enabled()


def test_ac2_with_the_switch_off_no_mark_exists_and_no_cell_has_a_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_ac1(page, live_server, fx01_grid)
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")

    expect_no_mark_anywhere(page)


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
    expect(marks_in(page, 1, 0)).to_have_count(1)

    turn_switch_off(page)

    expect_no_mark_anywhere(page)
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


def test_ac2_a_reload_turns_the_switch_off(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_ac1(page, live_server, fx01_grid)
    turn_switch_on(page)
    expect(marks_in(page, 1, 0)).to_have_count(1)
    frames_before = len(mock.received)

    page.reload()

    wait_until(page, lambda: mock.has_join_after(frames_before))
    mock.send(snapshot_frame(ac1_view(fx01_grid), 5, ac1_players()))
    expect(room_page(page)).to_have_attribute("data-status", "joined")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(authors_switch(page)).to_have_attribute("aria-pressed", "false")
    expect_no_mark_anywhere(page)
