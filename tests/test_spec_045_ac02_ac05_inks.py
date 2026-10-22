"""Tests of spec 045, AC-2 to AC-5: while the mode is on, each letter is drawn in
its finder's ink.

AC-2: on `EIGHT`, each letter cell has its finder's colour index in
`data-author-colour`, and it and its `cell-letter` have the computed `color` of
`--player-ink-N`; with the mode off, no cell has a finder and every letter is ink.
AC-3: a letter with no finder (revealed, or by a player who is not in the kept
snapshot) is ink, and the inks follow `letter_changed`, `cell_locked`,
`player_left` and `player_joined` within 300 ms. AC-4: a pencil letter keeps its
italics, a locked letter its weight, and the strike of a wrong letter turns ink.
AC-5: the mode changes the letters only, and a flash keeps the inks. The shared
setup is in `spec045_harness`.

Also tested, from "Edge cases and errors": a pending letter (shown in the ink of
the cell's confirmed author, or ink on an empty cell, until the server confirms
it), a newcomer who takes the colour index of a player who left, a removed player,
and a revealed letter (ink, bold, with its notch).

Choices where the spec leaves room:

- AC-3's events are sent in the spec's order, each test sending the ones before
  its own (their seqs follow each other). After `cell_locked` (seq 10) no letter
  by `p2` is left in that run, so `player_left` (seq 11) is checked there on
  every cell whose `data-author` is `p2`, and a separate run sends `player_left`
  of `p2` right after the snapshot, where (1, 1) holds `p2`'s `A`.
- AC-4's strike is read on the `cell`, where spec 042's tests read it.
- AC-5's comparison: the mode is turned on and off once in the Menu before the
  first reading, so that both readings follow the same Menu clicks (the focus is
  then the same) and only the mode differs. The marks are counted among the
  cell's descendants.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.protocol import Direction, LeaveReason
from spec019_harness import (
    OpenWindow,
    cell_locked_frame,
    letter_changed_frame,
    window_opener,
)
from spec042_harness import ChangeList
from spec043_harness import (
    FX01_SOLUTION,
    WHITE,
    Reading,
    RoomMock,
    colour_matches,
    expect_seq,
    fx01_view,
    joined_frame,
    left_frame,
    letter_frame,
    player,
    players_up_to,
    press_cell,
    selecting,
    send_and_wait,
    snapshot_frame,
)
from spec045_harness import (
    AC3_SEQ,
    EIGHT_CELLS,
    INK,
    INKS,
    PENCIL,
    RED,
    ac3_frame,
    cell_locator,
    cell_shows_within,
    colour_problems,
    eight_frame,
    finder_of_colour,
    finder_problems,
    ink_probe,
    open_page,
    read_cell,
    read_until,
    set_mode,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


# ---- AC-2: each letter in its finder's ink ----


def empty_letter_cells() -> list[tuple[int, int]]:
    """FX-01's letter cells that `EIGHT` leaves empty."""
    empty: list[tuple[int, int]] = []
    for cell in FX01_SOLUTION:
        if cell not in EIGHT_CELLS:
            empty.append(cell)
    return empty


def test_ac2_each_letter_cell_has_its_finders_colour_index(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid), mode_on=True)

    found: dict[tuple[int, int], str] = {}
    expected: dict[tuple[int, int], str] = {}
    for colour_index in range(8):
        row, column = finder_of_colour(colour_index)
        found[(row, column)] = read_cell(page, row, column)["authorColour"]
        expected[(row, column)] = str(colour_index)
    for row, column in empty_letter_cells():
        found[(row, column)] = read_cell(page, row, column)["authorColour"]
        expected[(row, column)] = ""
    assert found == expected


def test_ac2_each_letter_and_its_cell_are_in_the_finders_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid), mode_on=True)

    problems: list[str] = []
    for colour_index in range(8):
        row, column = finder_of_colour(colour_index)
        reading = read_cell(page, row, column)
        if reading["letterColour"] is None:
            problems.append(f"({row}, {column}) has no cell-letter")
        problems.extend(
            colour_problems(f"({row}, {column})", reading, INKS[colour_index])
        )
    assert problems == []


def test_ac2_each_ink_is_the_colour_of_its_token(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid), mode_on=True)

    problems: list[str] = []
    for colour_index in range(8):
        row, column = finder_of_colour(colour_index)
        reading = read_cell(page, row, column)
        probe = ink_probe(page, colour_index)
        if not colour_matches(probe, INKS[colour_index]):
            problems.append(f"--player-ink-{colour_index} is {probe}")
        if tuple(reading["colour"]) != probe:
            problems.append(f"({row}, {column}) {reading['colour']}, probe {probe}")
        if reading["letterColour"] is None or tuple(reading["letterColour"]) != probe:
            problems.append(f"({row}, {column}) letter {reading['letterColour']}")
    assert problems == []


def test_ac2_with_the_mode_off_no_cell_has_a_finder_and_every_letter_is_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, eight_frame(fx01_grid))

    problems: list[str] = []
    for row, column in EIGHT_CELLS:
        reading = read_cell(page, row, column)
        problems.extend(finder_problems(f"({row}, {column})", reading, "", INK))
    assert problems == []


# ---- AC-3: no finder, ink; the inks follow the grid ----


def open_ac3(window: OpenWindow, base_url: str, grid: Grid) -> tuple[Page, RoomMock]:
    return open_page(window, base_url, ac3_frame(grid), mode_on=True)


# AC-3's events, in the spec's order: (seq, frame).
def ac3_events() -> list[tuple[int, str]]:
    return [
        (8, letter_changed_frame(8, 1, 0, "X", "p2")),
        (9, letter_changed_frame(9, 1, 1, None, "p2")),
        (10, cell_locked_frame(10, 1, 0, "T", revealed=True)),
        (11, left_frame(11, "p2", LeaveReason.LEFT)),
    ]


def send_events_before(page: Page, mock: RoomMock, seq: int) -> None:
    """Send AC-3's events whose seq is below `seq` and wait until each applies."""
    for event_seq, frame in ac3_events():
        if event_seq < seq:
            send_and_wait(page, mock, frame)


def send_event(page: Page, mock: RoomMock, seq: int) -> None:
    """Send AC-3's event numbered `seq`; return once `room-page` shows its seq."""
    for event_seq, frame in ac3_events():
        if event_seq == seq:
            mock.send(frame)
            expect_seq(page, seq)
            return
    pytest.fail(f"no event with seq {seq}")


def test_ac3_letters_by_players_of_the_room_have_their_inks(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac3(window, live_server, fx01_grid)

    problems = finder_problems("(1, 0)", read_cell(page, 1, 0), "0", INKS[0])
    problems.extend(finder_problems("(1, 1)", read_cell(page, 1, 1), "1", INKS[1]))
    assert problems == []


def test_ac3_a_letter_by_a_player_not_in_the_room_and_a_revealed_letter_are_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_ac3(window, live_server, fx01_grid)

    problems = finder_problems("(1, 2)", read_cell(page, 1, 2), "", INK)
    problems.extend(finder_problems("(1, 4)", read_cell(page, 1, 4), "", INK))
    assert problems == []


def test_ac3_a_letter_written_by_another_player_takes_their_ink_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)

    send_event(page, mock, 8)

    reading = cell_shows_within(page, 1, 0, "1", INKS[1])
    assert finder_problems("(1, 0)", reading, "1", INKS[1]) == []
    assert reading["letterText"] == "X"


def test_ac3_an_erase_leaves_the_cell_with_no_letter_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    send_events_before(page, mock, 9)

    send_event(page, mock, 9)

    letter = cell_locator(page, 1, 1).get_by_test_id("cell-letter")
    expect(letter).to_have_count(0, timeout=300)
    assert read_cell(page, 1, 1)["authorColour"] == ""


def test_ac3_a_reveal_leaves_the_cell_with_no_finder_and_in_ink_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    send_events_before(page, mock, 10)

    send_event(page, mock, 10)

    reading = cell_shows_within(page, 1, 0, "", INK)
    assert finder_problems("(1, 0)", reading, "", INK) == []


def test_ac3_in_the_spec_run_a_player_left_leaves_no_letter_in_their_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    send_events_before(page, mock, 11)

    send_event(page, mock, 11)
    page.wait_for_timeout(300)

    problems: list[str] = []
    for row, column in FX01_SOLUTION:
        cell = cell_locator(page, row, column)
        if cell.get_attribute("data-author") == "p2":
            reading = read_cell(page, row, column)
            problems.extend(finder_problems(f"({row}, {column})", reading, "", INK))
    assert problems == []


def test_ac3_a_player_who_leaves_turns_their_letters_to_ink_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)

    mock.send(left_frame(8, "p2", LeaveReason.LEFT))
    expect_seq(page, 8)

    reading = cell_shows_within(page, 1, 1, "", INK)
    assert finder_problems("(1, 1)", reading, "", INK) == []


def test_ac3_a_removed_player_is_as_a_player_who_left(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)

    mock.send(left_frame(8, "p2", LeaveReason.REMOVED))
    expect_seq(page, 8)

    reading = cell_shows_within(page, 1, 1, "", INK)
    assert finder_problems("(1, 1)", reading, "", INK) == []


def test_ac3_a_newcomer_with_the_colour_of_a_player_who_left_takes_no_letter(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    send_and_wait(page, mock, left_frame(8, "p2", LeaveReason.LEFT))

    send_and_wait(page, mock, joined_frame(9, player("p3", colour=1)))
    page.wait_for_timeout(300)

    assert finder_problems("(1, 1)", read_cell(page, 1, 1), "", INK) == []


def seat_back_frame(grid: Grid) -> str:
    """AC-3's second run: (1, 0) holds `T` by `p9`, a past player of the room."""
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p9"})]
    return snapshot_frame(fx01_view(grid, changes), players_up_to(2), seq=AC3_SEQ)


def test_ac3_a_player_seated_back_finds_their_letters_again_within_300_ms(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_page(
        window, live_server, seat_back_frame(fx01_grid), mode_on=True
    )
    assert finder_problems("(1, 0)", read_cell(page, 1, 0), "", INK) == []

    mock.send(joined_frame(8, player("p9", colour=2, nickname="ZOÉ")))
    expect_seq(page, 8)

    reading = cell_shows_within(page, 1, 0, "2", INKS[2])
    assert finder_problems("(1, 0)", reading, "2", INKS[2]) == []


# ---- AC-3: pending letters ----


def test_ac3_a_pending_letter_keeps_the_ink_of_the_cells_confirmed_author(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    press_cell(page, 1, 1)

    page.keyboard.press("b")

    cell = cell_locator(page, 1, 1)
    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    page.wait_for_timeout(300)
    assert finder_problems("(1, 1)", read_cell(page, 1, 1), "1", INKS[1]) == []
    mock.send(letter_frame(8, 1, 1, "B", "p1"))
    expect_seq(page, 8)
    reading = cell_shows_within(page, 1, 1, "0", INKS[0])
    assert finder_problems("(1, 1)", reading, "0", INKS[0]) == []


def test_ac3_a_pending_letter_on_an_empty_cell_is_ink_until_confirmed(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_ac3(window, live_server, fx01_grid)
    press_cell(page, 2, 1)

    page.keyboard.press("v")

    cell = cell_locator(page, 2, 1)
    expect(cell).to_have_attribute("data-letter", "V")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    page.wait_for_timeout(300)
    assert finder_problems("(2, 1)", read_cell(page, 2, 1), "", INK) == []
    mock.send(letter_frame(8, 2, 1, "V", "p1"))
    expect_seq(page, 8)
    reading = cell_shows_within(page, 2, 1, "0", INKS[0])
    assert finder_problems("(2, 1)", reading, "0", INKS[0]) == []


# ---- AC-4: pencil, locked and wrong letters ----


def ac4_frame(grid: Grid, replaced: ChangeList | None = None) -> str:
    """AC-4's snapshot: `p1` (colour 0), `p2` (colour 3); a lock, a pencil, a wrong."""
    changes: ChangeList = [
        (1, 0, {"letter": "T", "author": "p2", "locked": True}),
        (2, 3, {"letter": "D", "author": "p2", "pencil": True}),
        (1, 1, {"letter": "X", "author": "p1", "wrong": True}),
    ]
    if replaced is not None:
        changes.extend(replaced)
    players = [player("p1", host=True), player("p2", colour=3)]
    return snapshot_frame(fx01_view(grid, changes), players)


def test_ac4_a_letter_locked_by_a_check_keeps_weight_700_in_its_finders_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac4_frame(fx01_grid), mode_on=True)

    reading = read_cell(page, 1, 0)

    assert reading["fontWeight"] == "700"
    assert finder_problems("(1, 0)", reading, "3", INKS[3]) == []


def test_ac4_a_pencil_letter_keeps_its_italics_in_its_finders_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac4_frame(fx01_grid), mode_on=True)

    reading = read_cell(page, 2, 3)

    assert reading["fontStyle"] == "italic"
    assert finder_problems("(2, 3)", reading, "3", INKS[3]) == []
    assert not colour_matches(reading["colour"], PENCIL)


def test_ac4_a_wrong_letter_is_struck_through_in_ink_and_drawn_in_its_finders_ink(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac4_frame(fx01_grid), mode_on=True)

    reading = read_cell(page, 1, 1)

    assert "line-through" in reading["decorationLine"]
    assert colour_matches(reading["decorationColour"], INK), reading
    assert finder_problems("(1, 1)", reading, "0", INKS[0]) == []


def test_ac4_with_the_mode_off_the_pencil_is_grey_and_the_strike_red(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac4_frame(fx01_grid))

    pencil = read_cell(page, 2, 3)
    wrong = read_cell(page, 1, 1)

    assert colour_matches(pencil["colour"], PENCIL), pencil
    assert "line-through" in wrong["decorationLine"]
    assert colour_matches(wrong["decorationColour"], RED), wrong


def test_ac4_the_strikes_line_and_thickness_do_not_change_with_the_mode(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac4_frame(fx01_grid))
    off = read_cell(page, 1, 1)

    set_mode(page, True)

    on = read_cell(page, 1, 1)
    assert colour_matches(on["decorationColour"], INK), on
    assert on["decorationLine"] == off["decorationLine"]
    assert on["decorationStyle"] == off["decorationStyle"]
    assert on["decorationThickness"] == off["decorationThickness"]


def test_ac4_a_revealed_letter_stays_ink_and_bold_with_its_notch(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    revealed: ChangeList = [
        (1, 4, {"letter": "S", "author": None, "locked": True, "revealed": True})
    ]
    frame = ac4_frame(fx01_grid, revealed)
    page, _ = open_page(window, live_server, frame, mode_on=True)

    reading = read_cell(page, 1, 4)

    assert reading["fontWeight"] == "700"
    assert finder_problems("(1, 4)", reading, "", INK) == []
    expect(cell_locator(page, 1, 4).get_by_test_id("reveal-mark")).to_have_count(1)


# ---- AC-5: the mode changes the letters only; a flash keeps the inks ----

CELL_LOOK_SCRIPT = r"""
() => {
  const marks = ['remote-selection', 'reveal-mark', 'catch-up-mark', 'clue-arrow'];
  const found = [];
  for (const cell of document.querySelectorAll('[data-testid="cell"]')) {
    const style = getComputedStyle(cell);
    const counts = {};
    for (const mark of marks) {
      counts[mark] = cell.querySelectorAll(`[data-testid="${mark}"]`).length;
    }
    found.push({
      cell: `${cell.dataset.row},${cell.dataset.column}`,
      background: style.backgroundColor,
      outlineStyle: style.outlineStyle,
      counts: counts,
    });
  }
  return found;
}
"""


def ac5_frame(grid: Grid) -> str:
    """`EIGHT` with `p2` selecting (3, 2) `down`."""
    players = players_up_to(8)
    players[1] = player("p2", selection=selecting(3, 2, Direction.DOWN))
    return eight_frame(grid, players=players)


def cell_looks(page: Page) -> list[Reading]:
    found = page.evaluate(CELL_LOOK_SCRIPT)
    assert isinstance(found, list), found
    return found


def test_ac5_the_mode_changes_no_background_outline_or_mark_of_any_cell(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, _ = open_page(window, live_server, ac5_frame(fx01_grid))
    press_cell(page, 1, 0)
    set_mode(page, True)
    set_mode(page, False)
    looks_off = cell_looks(page)

    set_mode(page, True)

    expect(cell_locator(page, 1, 0)).to_have_attribute("data-author-colour", "0")
    looks_on = cell_looks(page)
    assert len(looks_on) == 25
    assert looks_on == looks_off


def test_ac5_a_flash_keeps_the_replacers_ink_over_the_white_cell(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page, mock = open_page(window, live_server, ac5_frame(fx01_grid), mode_on=True)
    press_cell(page, 1, 0)

    mock.send(letter_frame(6, 1, 0, "Y", "p4"))
    expect_seq(page, 6)

    def read() -> Reading:
        return read_cell(page, 1, 0)

    def accept(reading: Reading) -> bool:
        flashing = reading["flash"] == "3" and reading["overlays"] == 1
        return flashing and colour_problems("(1, 0)", reading, INKS[3]) == []

    reading = read_until(page, read, accept)
    problems: list[str] = []
    if reading["flash"] != "3":
        problems.append(f"data-flash {reading['flash']!r}")
    if reading["overlays"] != 1:
        problems.append(f"{reading['overlays']} cell-flash overlays")
    if not colour_matches(reading["background"], WHITE):
        problems.append(f"background {reading['background']}")
    problems.extend(colour_problems("(1, 0)", reading, INKS[3]))
    assert problems == [], reading
