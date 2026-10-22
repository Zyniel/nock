"""Tests of spec 024, AC-7: the reveal controls send the right message and are
disabled when they cannot apply.

The page is driven with a mocked socket. "An error answering a reveal changes
nothing on the page" (Client: reveal controls) is tested here too. The shared
setup is in `spec024_harness`.

Refined by spec 043 (the design's room layout): `reveal-panel` is inside
`aide-menu`, after `check-panel` and a `nock-menu-separator`, a group labelled by
`reveal-heading` (`fr.json["reveal.label"]`); the clicks are made with the Aide
menu open (spec 043's `open_aide`), each closing it. It read "inside `room-toolbar`
right after `check-panel`, ... and the `aria-label` `fr.json["reveal.label"]`".
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ErrorCode,
    ErrorMessage,
    GridSolved,
    HelpMode,
    Reveal,
    WordTarget,
)
from room_panels import open_aide
from spec024_harness import (
    DEFAULT_BUDGET,
    MIME_CELLS,
    SETTLE_MS,
    ChangeList,
    cell_at,
    expect_selection,
    expect_seq,
    grid_from_text,
    load_fr,
    make_catalogue,
    open_room,
    settings_changed_frame,
    wait_until_page,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


# ---- Helpers ----

PANEL_SCRIPT = """
() => {
  const menu = document.querySelector('[data-testid="aide-menu"]');
  const checks = document.querySelector('[data-testid="check-panel"]');
  const panel = document.querySelector('[data-testid="reveal-panel"]');
  const buttons = [];
  for (const button of panel.querySelectorAll('button')) {
    buttons.push(button.getAttribute('data-testid'));
  }
  let separator = false;
  if (checks !== null) {
    for (let node = checks.nextElementSibling; node !== null && node !== panel;
         node = node.nextElementSibling) {
      if (node.classList.contains('nock-menu-separator')) {
        separator = true;
      }
    }
  }
  return {
    inAideMenu: menu !== null && menu.contains(panel),
    afterChecks: checks !== null && Boolean(
      checks.compareDocumentPosition(panel) & Node.DOCUMENT_POSITION_FOLLOWING
    ),
    separatorBetween: separator,
    buttons: buttons,
  };
}
"""
CELL_STATES_SCRIPT = """
() => Array.from(document.querySelectorAll('[data-testid="cell"]')).map(cell => [
  cell.getAttribute('data-row'), cell.getAttribute('data-column'),
  cell.getAttribute('data-letter'), cell.getAttribute('data-locked'),
  cell.getAttribute('data-revealed'), cell.getAttribute('data-author'),
  cell.getAttribute('data-unconfirmed'),
])
"""


def tap_mime(page: Page) -> None:
    """Tap (2, 2) twice: the selection is (2, 2) `down`, word MIME."""
    cell_at(page, 2, 2).click()
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2, "down", "0,2,0")


def locked_changes(cells: list[tuple[int, int]]) -> ChangeList:
    """The cells hold their MIME letter, locked by a check of `p2`."""
    letters = {(1, 2): "M", (2, 2): "I", (3, 2): "M", (4, 2): "E"}
    changes: ChangeList = []
    for row, column in cells:
        update: dict[str, object] = {
            "letter": letters[(row, column)],
            "author": "p2",
            "locked": True,
        }
        changes.append((row, column, update))
    return changes


# ---- AC-7 ----


def test_ac7_the_new_fr_json_key_of_the_panel() -> None:
    assert load_fr()["reveal.label"] == "Révéler"


def test_ac7_the_panel_is_a_labelled_group_in_the_aide_menu_after_the_checks(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    open_aide(page)

    panel = page.get_by_test_id("reveal-panel")
    heading = page.get_by_test_id("reveal-heading")
    expect(panel).to_be_visible()
    expect(panel).to_have_attribute("role", "group")
    heading_id = heading.get_attribute("id")
    assert heading_id
    expect(panel).to_have_attribute("aria-labelledby", heading_id)
    expect(heading).to_have_text(load_fr()["reveal.label"])
    layout = page.evaluate(PANEL_SCRIPT)
    assert layout["inAideMenu"] is True, layout
    assert layout["afterChecks"] is True, layout
    assert layout["separatorBetween"] is True, layout
    assert layout["buttons"] == ["reveal-letter", "reveal-word"], layout


def test_ac7_with_nothing_selected_both_buttons_are_disabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)

    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()
    expect(page.get_by_test_id("reveal-word")).to_be_disabled()


def test_ac7_the_buttons_send_the_selected_cell_and_word_once_each(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    tap_mime(page)
    expect(page.get_by_test_id("reveal-letter")).to_be_enabled()
    expect(page.get_by_test_id("reveal-word")).to_be_enabled()

    open_aide(page)
    page.get_by_test_id("reveal-letter").click()
    wait_until_page(page, lambda: len(mock.reveals()) >= 1, "the letter reveal")
    open_aide(page)
    page.get_by_test_id("reveal-word").click()
    wait_until_page(page, lambda: len(mock.reveals()) >= 2, "the word reveal")
    page.wait_for_timeout(SETTLE_MS)

    assert mock.reveals() == [
        Reveal(target=CellTarget(row=2, column=2)),
        Reveal(target=WordTarget(row=0, column=2, clue_index=0)),
    ]
    assert mock.raw_reveals() == [
        {"type": "reveal", "target": {"scope": "letter", "row": 2, "column": 2}},
        {
            "type": "reveal",
            "target": {"scope": "word", "row": 0, "column": 2, "clue_index": 0},
        },
    ]
    expect_selection(page, 2, 2, "down", "0,2,0")


def test_ac7_no_cell_changes_until_the_server_answers(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    tap_mime(page)
    before = page.evaluate(CELL_STATES_SCRIPT)

    open_aide(page)
    page.get_by_test_id("reveal-letter").click()
    open_aide(page)
    page.get_by_test_id("reveal-word").click()
    wait_until_page(page, lambda: len(mock.reveals()) >= 2, "the two reveals")
    page.wait_for_timeout(SETTLE_MS)

    assert page.evaluate(CELL_STATES_SCRIPT) == before
    expect_seq(page, 5)


def test_ac7_a_locked_selected_cell_disables_only_the_letter_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, changes=locked_changes([(2, 2)]))
    cell_at(page, 2, 2).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-selected-row", "2")

    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()
    expect(page.get_by_test_id("reveal-word")).to_be_enabled()


def test_ac7_a_word_whose_cells_are_all_locked_disables_the_word_button(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, changes=locked_changes(MIME_CELLS))
    tap_mime(page)

    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()
    expect(page.get_by_test_id("reveal-word")).to_be_disabled()


def test_ac7_grid_solved_disables_both_buttons(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    tap_mime(page)
    expect(page.get_by_test_id("reveal-letter")).to_be_enabled()
    expect(page.get_by_test_id("reveal-word")).to_be_enabled()

    mock.send(GridSolved(seq=6, elapsed_ms=1000).model_dump_json())

    expect_seq(page, 6)
    expect(page.get_by_test_id("reveal-letter")).to_be_disabled()
    expect(page.get_by_test_id("reveal-word")).to_be_disabled()


def test_ac7_help_mode_none_hides_the_panel_and_settings_changed_toggles_it(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, help_mode=HelpMode.NONE)
    panel = page.get_by_test_id("reveal-panel")
    expect(panel).to_have_count(0)

    mock.send(settings_changed_frame(6, HelpMode.FREE, DEFAULT_BUDGET, DEFAULT_BUDGET))
    expect_seq(page, 6)
    expect(panel).to_have_count(1)
    open_aide(page)
    expect(panel).to_be_visible()

    mock.send(settings_changed_frame(7, HelpMode.NONE, DEFAULT_BUDGET, DEFAULT_BUDGET))
    expect_seq(page, 7)
    expect(panel).to_have_count(0)


@pytest.mark.parametrize(
    "code",
    [ErrorCode.BUDGET_EXHAUSTED, ErrorCode.INVALID_TARGET, ErrorCode.HELP_DISABLED],
    ids=["budget-exhausted", "invalid-target", "help-disabled"],
)
def test_ac7_an_error_answering_a_reveal_leaves_the_pending_edit_alone(
    page: Page, live_server: str, fx01_grid: Grid, code: ErrorCode
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    expect(page.get_by_test_id("reveal-panel")).to_have_count(1)
    cell = cell_at(page, 1, 1)
    cell.click()
    page.keyboard.press("b")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: mock.edit_count() == 1, "the pending edit")

    mock.send(ErrorMessage(code=code, message="refused").model_dump_json())
    page.wait_for_timeout(SETTLE_MS)

    expect(cell).to_have_attribute("data-letter", "B")
    expect(cell).to_have_attribute("data-unconfirmed", "true")
    expect_seq(page, 5)
    # Control: an edit answer still drops the pending edit, so it was there.
    locked = ErrorMessage(code=ErrorCode.CELL_LOCKED, message="locked")
    mock.send(locked.model_dump_json())
    expect(cell).to_have_attribute("data-letter", "")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
