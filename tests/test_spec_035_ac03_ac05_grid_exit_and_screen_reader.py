"""Tests of spec 035: leaving the grid, announcements, roles (AC-3, AC-4, AC-5).

They use a mocked socket. The setup the test files of spec 035 share is in
`tests/spec035_harness.py`.

Refined by spec 043 (the design's room layout): the navy clue bar's buttons follow
the grid in document order, so `Escape` then `Tab` moves the focus to `clue-prev`
and `Escape` then `Shift+Tab` to `menu-button` (the last top-bar button). No
sentinel is needed and no engine is skipped; the run "with nothing after the grid"
became the run on the page as it is.

Not tested here, and why:

- The announcement of a word of one cell (`a11y.announcement_one`): FX-01 holds no
  such word and the spec gives no hand-built view for it.
"""

from __future__ import annotations

import json
import re
from typing import Any

import pytest
from playwright.sync_api import Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import Direction
from spec035_harness import (
    EPSILON,
    NEW_KEYS,
    SETTLE_MS,
    MockRoomSocket,
    Walker,
    build_fx01_grid,
    build_reference_catalogue,
    cell_at,
    computed,
    expect_focus_on_grid,
    expect_selected,
    expect_word,
    grid_of,
    letter_changed_frame,
    load_fr,
    open_room,
    selection_frame,
)

# ---- Fixtures: thin wrappers around spec035_harness -------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """The reference catalogue CAT of spec 004 (also served by live_server)."""
    return build_reference_catalogue(fx01_grid)


# The `Tab` listener of the spec's "Test harness": on `window`, bubble phase, it
# records `defaultPrevented` of each Tab keydown (with or without Shift), which tells
# whether the page cancelled it.
TAB_LISTENER_SCRIPT = r"""
() => {
  window.tabKeydowns = [];
  window.addEventListener('keydown', event => {
    if (event.key === 'Tab') {
      window.tabKeydowns.push({
        shift: event.shiftKey,
        defaultPrevented: event.defaultPrevented,
      });
    }
  });
}
"""

# Is the focus where a plain Tab (direction 1) or Shift+Tab (direction -1) from the
# grid leads: on the next (previous) focusable element in document order.
NEIGHBOUR_FOCUSED_SCRIPT = r"""
direction => {
  const grid = document.querySelector('[data-testid="grid"]');
  const focusable = [];
  const selector = 'a[href], button, input, select, textarea, [tabindex]';
  for (const element of document.querySelectorAll(selector)) {
    const tabindex = element.getAttribute('tabindex');
    if (element.disabled || (tabindex !== null && Number(tabindex) < 0)) {
      continue;
    }
    if (element.tagName === 'INPUT' && element.type === 'hidden') {
      continue;
    }
    const hidden = getComputedStyle(element).visibility === 'hidden';
    if (hidden || element.getClientRects().length === 0) {
      continue;
    }
    focusable.push(element);
  }
  const neighbour = focusable[focusable.indexOf(grid) + direction];
  return neighbour !== undefined && document.activeElement === neighbour;
}
"""

# Counts, in `window.announcementRewrites`, the mutations of a live region.
OBSERVE_REWRITES_SCRIPT = r"""
region => {
  window.announcementRewrites = 0;
  const observer = new MutationObserver(records => {
    window.announcementRewrites += records.length;
  });
  observer.observe(region, {
    childList: true,
    characterData: true,
    subtree: true,
    attributes: true,
  });
}
"""


def announcement_of(page: Page) -> Locator:
    return page.get_by_test_id("grid-announcement")


def watch_tab_keys(page: Page) -> None:
    """Record, from now on, whether the page cancelled each Tab keydown."""
    page.evaluate(TAB_LISTENER_SCRIPT)


def tab_keydowns(page: Page) -> list[dict[str, Any]]:
    """The Tab keydowns recorded since `watch_tab_keys`: `shift`, `defaultPrevented`."""
    recorded = page.evaluate("window.tabKeydowns")
    assert isinstance(recorded, list)
    return recorded


# ---- AC-3: a keyboard player can leave the grid ---------------------------------


def open_host_room(page: Page, live_server: str, fx01_grid: Grid) -> MockRoomSocket:
    """A FX-01 room where `you` (`p1`) is host."""
    return open_room(page, live_server, fx01_grid)


def focus_grid_with_first_word(page: Page, walker: Walker) -> None:
    """Tab to the grid, then Tab again: `0,0,0` is selected on (1, 0)."""
    walker.tab_to("grid")
    page.keyboard.press("Tab")
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)


def test_ac3_tab_stays_on_the_grid_then_escape_tab_leaves_forward(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect(page.get_by_test_id("clue-prev")).to_be_focused()
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, 1) is True
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)


def test_ac3_escape_then_shift_tab_leaves_backward(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")

    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("menu-button")).to_be_focused()
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, -1) is True
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)


def test_ac3_coming_back_to_the_grid_with_shift_tab_works_both_ways(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Escape")
    page.keyboard.press("Tab")
    expect(page.get_by_test_id("clue-prev")).to_be_focused()

    page.keyboard.press("Shift+Tab")
    expect_focus_on_grid(page)
    expect_word(page, "0,0,0")
    page.keyboard.press("Escape")
    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("menu-button")).to_be_focused()
    assert page.evaluate(NEIGHBOUR_FOCUSED_SCRIPT, -1) is True
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)


def test_ac3_on_the_page_as_it_is_escape_tab_reaches_the_clue_bar_in_every_engine(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect(page.get_by_test_id("clue-prev")).to_be_focused()
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 0)


@pytest.mark.parametrize("key", ["Tab", "Shift+Tab"], ids=["forward", "backward"])
def test_ac3_a_tab_pressed_right_after_escape_is_not_cancelled(
    page: Page, live_server: str, fx01_grid: Grid, key: str
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    watch_tab_keys(page)

    # Control: the Tab that selects the next word is cancelled (spec 009), so the
    # listener does tell a cancelled Tab from a released one.
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    page.keyboard.press("Escape")
    page.keyboard.press(key)

    assert tab_keydowns(page) == [
        {"shift": False, "defaultPrevented": True},
        {"shift": key == "Shift+Tab", "defaultPrevented": False},
    ]


def test_ac3_a_letter_after_escape_is_typed_and_the_release_ends(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("Tab")
    expect_word(page, "0,0,1")
    expect_selected(page, 0, 1)

    page.keyboard.press("Escape")
    page.keyboard.press("t")
    expect(cell_at(page, 0, 1)).to_have_attribute("data-letter", "T")
    page.keyboard.press("Tab")

    expect_word(page, "0,2,0")
    expect_selected(page, 1, 2)
    expect_focus_on_grid(page)
    assert "edit_letter" in mock.types()


def test_ac3_any_other_key_ends_the_release(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    page.keyboard.press("ArrowRight")
    expect_selected(page, 1, 1)
    page.keyboard.press("Tab")

    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)


def test_ac3_losing_then_regaining_the_focus_ends_the_release(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)

    page.keyboard.press("Escape")
    grid_of(page).evaluate("el => { el.blur(); el.focus(); }")
    expect_focus_on_grid(page)
    page.keyboard.press("Tab")

    expect_word(page, "0,0,1")
    expect_focus_on_grid(page)


def frames_without_pings(mock: MockRoomSocket) -> list[str]:
    """The frames the page sent, without its keep-alive `ping` frames.

    The page sends a `ping` on its own timer, so one can fall between two reads
    whatever the test does.
    """
    frames: list[str] = []
    for frame in mock.received:
        if json.loads(frame)["type"] != "ping":
            frames.append(frame)
    return frames


def test_ac3_escape_changes_nothing_else(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    focus_grid_with_first_word(page, walker)
    page.keyboard.press("t")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect_selected(page, 1, 1)
    page.wait_for_timeout(SETTLE_MS)
    sent_before = frames_without_pings(mock)

    page.keyboard.press("Escape")
    page.wait_for_timeout(SETTLE_MS)

    assert frames_without_pings(mock) == sent_before
    expect_word(page, "0,0,0")
    expect_selected(page, 1, 1)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "true")
    expect_focus_on_grid(page)


def test_ac3_escape_with_nothing_selected_lets_tab_leave(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)
    walker = Walker(page)
    walker.tab_to("grid")
    expect(grid_of(page)).to_have_attribute("data-word", "")

    page.keyboard.press("Escape")
    page.keyboard.press("Tab")

    expect(page.get_by_test_id("clue-prev")).to_be_focused()
    expect(grid_of(page)).to_have_attribute("data-word", "")
    expect(grid_of(page)).not_to_have_attribute(
        "aria-activedescendant", re.compile(r".")
    )


def test_ac3_the_grid_is_described_by_the_hint_with_the_exit_method(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_host_room(page, live_server, fx01_grid)

    expect(grid_of(page)).to_have_attribute("aria-describedby", "grid-hint")
    hint = page.get_by_test_id("grid-hint")
    expect(hint).to_have_attribute("id", "grid-hint")
    expect(hint).to_have_text(load_fr()["a11y.grid_hint"])
    expect(hint).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))


# ---- AC-4: the screen reader hears the clue, direction, length, position --------


def test_ac4_the_announcement_follows_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)

    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_word(page, "0,2,0")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 2")
    expect(announcement).to_have_attribute("role", "status")
    expect(announcement).to_have_attribute("aria-live", "polite")
    expect(announcement).to_have_attribute("aria-atomic", "true")
    expect(announcement).to_have_class(re.compile(r"(^|\s)visually-hidden(\s|$)"))

    page.keyboard.press("ArrowDown")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 3")
    page.keyboard.press("ArrowUp")
    expect(announcement).to_have_text("Artiste muet, vertical, 4 lettres, lettre 2")

    cell_at(page, 2, 2).click()
    expect_word(page, "2,0,0")
    expect(announcement).to_have_text("Sans contenu, horizontal, 4 lettres, lettre 2")

    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")


def test_ac4_choosing_the_same_selection_again_does_not_rewrite_the_region(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    expect_selected(page, 1, 0)
    word_before = grid_of(page).get_attribute("data-word")
    announcement.evaluate(OBSERVE_REWRITES_SCRIPT)

    # (1, 0) has only an across word, so tapping it again chooses the very same
    # selection. ArrowLeft cannot leave it (only clue cells lie to its left), and
    # Escape, remote events leave it alone too.
    cell_at(page, 1, 0).click()
    page.keyboard.press("ArrowLeft")
    page.keyboard.press("Escape")
    mock.send(selection_frame("p2", 3, 1, Direction.DOWN))
    mock.send(letter_changed_frame(6, 3, 1, "A", "p2"))
    expect(cell_at(page, 3, 1)).to_have_attribute("data-letter", "A")
    page.wait_for_timeout(SETTLE_MS)

    expect_selected(page, 1, 0)
    assert grid_of(page).get_attribute("data-word") == word_before
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    assert page.evaluate("window.announcementRewrites") == 0

    # Control: a real move does rewrite the region, so the observer works.
    page.keyboard.press("ArrowRight")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")
    assert page.evaluate("window.announcementRewrites") > 0


@pytest.mark.parametrize("first_step", ["cell", "clue"])
def test_ac4_tapping_the_clue_of_the_selected_word_does_not_rewrite_the_region(
    page: Page, live_server: str, fx01_grid: Grid, first_step: str
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    passoire_clue = page.get_by_test_id("clue").filter(has_text="Passoire fine")
    # Spec 007: a clue tap selects the word's first unfilled cell. The grid is
    # empty, so for "Passoire fine" that is (1, 0), across: the cell tap below
    # and the clue tap choose the very same selection.
    if first_step == "cell":
        cell_at(page, 1, 0).click()
    else:
        passoire_clue.click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    expect_selected(page, 1, 0)
    expect_word(page, "0,0,0")
    announcement.evaluate(OBSERVE_REWRITES_SCRIPT)

    passoire_clue.click()
    page.wait_for_timeout(SETTLE_MS)

    expect_selected(page, 1, 0)
    expect_word(page, "0,0,0")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")
    assert page.evaluate("window.announcementRewrites") == 0

    # Control: a real move does rewrite the region, so the observer works.
    page.keyboard.press("ArrowRight")
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")
    assert page.evaluate("window.announcementRewrites") > 0


def test_ac4_the_announcement_texts_come_from_fr_json() -> None:
    fr_json = load_fr()

    assert fr_json.get("a11y.direction.across") == "horizontal"
    assert fr_json.get("a11y.direction.down") == "vertical"
    assert fr_json.get("a11y.announcement") == NEW_KEYS["a11y.announcement"]


def test_ac4_the_region_exists_and_is_empty_with_nothing_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    announcement = announcement_of(page)
    expect(announcement).to_have_count(1)
    expect(announcement).to_have_text("")
    expect(announcement).to_have_attribute("role", "status")
    expect(announcement).to_have_attribute("aria-live", "polite")


def test_ac4_typing_a_letter_only_updates_the_position(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    announcement = announcement_of(page)
    cell_at(page, 1, 0).click()
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 1")

    page.keyboard.press("t")

    expect_selected(page, 1, 1)
    expect(announcement).to_have_text("Passoire fine, horizontal, 5 lettres, lettre 2")


def test_ac4_the_announcement_is_visually_hidden_but_not_removed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    announcement = announcement_of(page)
    expect(announcement).not_to_have_text("")

    assert computed(announcement, "position") == "absolute"
    assert computed(announcement, "overflow") == "hidden"
    assert computed(announcement, "whiteSpace") == "nowrap"
    assert computed(announcement, "width") == "1px"
    assert computed(announcement, "height") == "1px"
    assert computed(announcement, "display") != "none"
    assert computed(announcement, "visibility") == "visible"


# ---- AC-5: grid, row and gridcell roles -----------------------------------------


def test_ac5_the_grid_has_rows_and_gridcells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(page.get_by_role("grid")).to_have_count(1)
    expect(page.get_by_role("gridcell")).to_have_count(25)
    structure = grid_of(page).evaluate(
        """grid => Array.from(grid.children).map(row => ({
            testId: row.getAttribute('data-testid'),
            role: row.getAttribute('role'),
            dataRow: row.getAttribute('data-row'),
            cells: Array.from(row.children).map(cell => ({
                testId: cell.getAttribute('data-testid'),
                role: cell.getAttribute('role'),
                row: cell.getAttribute('data-row'),
                column: cell.getAttribute('data-column'),
            })),
        }))"""
    )
    assert len(structure) == 5
    for row_number, row in enumerate(structure):
        assert row["testId"] == "grid-row"
        assert row["role"] == "row"
        assert row["dataRow"] == str(row_number)
        assert len(row["cells"]) == 5
        for column_number, cell in enumerate(row["cells"]):
            assert cell["testId"] == "cell"
            assert cell["role"] == "gridcell"
            assert cell["row"] == str(row_number)
            assert cell["column"] == str(column_number)


def test_ac5_the_grid_keeps_its_label_and_focusability(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(grid_of(page)).to_have_attribute("role", "grid")
    expect(grid_of(page)).to_have_attribute("aria-label", load_fr()["grid.label"])
    expect(grid_of(page)).to_have_attribute("tabindex", "0")


def test_ac5_every_cell_has_a_role_and_an_id(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    for row in range(5):
        for column in range(5):
            cell = cell_at(page, row, column)
            expect(cell).to_have_attribute("role", "gridcell")
            expect(cell).to_have_attribute("id", f"cell-{row}-{column}")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-testid", "cell")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-row", "2")
    expect(page.locator("#cell-2-2")).to_have_attribute("data-column", "2")


def test_ac5_only_letter_cells_carry_aria_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(grid_of(page)).not_to_have_attribute(
        "aria-activedescendant", re.compile(r".")
    )
    letter_cells = page.locator('[data-testid="cell"][data-type="letter"]')
    expect(letter_cells).to_have_count(18)
    for index in range(18):
        expect(letter_cells.nth(index)).to_have_attribute("aria-selected", "false")
    other_cells = page.locator('[data-testid="cell"]:not([data-type="letter"])')
    expect(other_cells).to_have_count(7)
    for index in range(7):
        assert other_cells.nth(index).get_attribute("aria-selected") is None


def test_ac5_the_selection_is_exposed_by_activedescendant_and_aria_selected(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    cell_at(page, 2, 2).click()

    expect(grid_of(page)).to_have_attribute("aria-activedescendant", "cell-2-2")
    expect(cell_at(page, 2, 2)).to_have_attribute("aria-selected", "true")
    others = page.locator(
        '[data-testid="cell"][data-type="letter"][aria-selected="false"]'
    )
    expect(others).to_have_count(17)
    assert page.locator('[aria-selected="true"]').count() == 1

    cell_at(page, 1, 0).click()
    expect(grid_of(page)).to_have_attribute("aria-activedescendant", "cell-1-0")


def test_ac5_clue_arrows_stay_hidden_from_assistive_technology(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    arrows = page.get_by_test_id("clue-arrow")
    expect(arrows).to_have_count(8)
    for index in range(8):
        expect(arrows.nth(index)).to_have_attribute("aria-hidden", "true")


def test_ac5_the_rows_do_not_change_the_layout_of_the_cells(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    origin = cell_at(page, 0, 0).bounding_box()
    assert origin is not None
    width = origin["width"]
    height = origin["height"]
    assert abs(width - height) <= EPSILON
    for row in range(5):
        for column in range(5):
            box = cell_at(page, row, column).bounding_box()
            assert box is not None
            assert abs(box["width"] - width) <= EPSILON
            assert abs(box["height"] - height) <= EPSILON
            assert abs(box["x"] - (origin["x"] + column * width)) <= EPSILON
            assert abs(box["y"] - (origin["y"] + row * height)) <= EPSILON
