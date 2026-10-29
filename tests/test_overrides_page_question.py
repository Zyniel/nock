"""Tests of admin/overrides, AC-17: the question before a shorter life.

The server holds three rooms in its database file when it starts, written as the
real clock sees them: two unsolved anonymous rooms last edited 30 and 40 hours ago,
and one solved 30 hours ago, under `NOCK_ANONYMOUS_ROOM_HOURS` 48. None is due
under 48 hours, so the app's first sweep keeps them. A life of 24 hours then
would delete the two unsolved ones, a life of 36 hours the older one. (The criterion
reads "AC-6's rooms": its room A, expired by the current value and held open by a
socket, would be deleted by the first sweep of a file read at the start, so the
page test uses rooms that are all still open.)

The question is found in the card by its text; its buttons by their names. Rule 13's
other clauses are checked beside the criterion: a second press of the button that
asked closes the question with nothing sent, and at most one question is open.
Rule 12's reset to a shorter life, which no criterion names, is checked here too:
« Rétablir » on an override of 96 over the variable's 48 sends the dry run of null
and asks first.

Readings taken where the spec leaves room:

- "Under a divider" is read as a top border of the question's own block, or an
  `hr` or `role="separator"` right before it (`has_divider` of
  `overrides_harness`), and the question stands under the rows.
- "The account page's disclosure" (rule 13) is read as that page marks it
  (`account/account.md` rule 17, `AccountPage.svelte`): the button that asked
  has `aria-expanded` "true" while the question is open, "false" otherwise, and
  `aria-controls` naming the question's block (`expect_asking`). "The button
  pressed" is also checked as the account page's own tests check it: the quiet
  look (`quiet_button_problems` of `spec048_harness`) on « Enregistrer » while
  asked, the primary look once closed. « Rétablir » is quiet in both states, so
  only its `aria-expanded` is read.
- The focus after the question closes (the lead's reading after review round 1,
  as the account page's cancel focuses its disclosure): after « Annuler », or
  after « Confirmer » on a save, the button that asked has the focus; after
  « Confirmer » on a reset, « Rétablir » is disabled, and the row's input has it.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from lifetime_harness import ANONYMOUS, CREATOR, HOUR, stored_room
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.store import RoomStore
from overrides_harness import (
    CANCEL,
    CONFIRM,
    RESET,
    SAVE,
    RequestLog,
    SettingsServer,
    box_below,
    button_in,
    card_of,
    expect_asking,
    expect_not_asking,
    expect_row,
    has_divider,
    input_box,
    input_of,
    open_card,
    question_of,
    row_line,
    row_of,
    row_text,
    settings_server,
    solved_stored_room,
    type_and_save,
)
from spec032_harness import grid_from_text
from spec033_harness import DATABASE_FILE_NAME
from spec042_harness import box_of
from spec046_harness import OpenWindow, button_colour_problems, window_opener
from spec048_harness import quiet_button_problems

ANONYMOUS_NAME = ANONYMOUS.field
CURRENT_HOURS = 48
OVERRIDE_HOURS = 96


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def server(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    fx01_grid: Grid,
) -> Iterator[SettingsServer]:
    """The server of the module's docstring, with its three rooms."""
    now = time.time()
    store = RoomStore(tmp_path / DATABASE_FILE_NAME)
    stored_room(store, fx01_grid, "BBBBBB", now - 30 * HOUR)
    stored_room(store, fx01_grid, "DDDDDD", now - 40 * HOUR)
    solved_stored_room(store, fx01_grid, "CCCCCC", now - 30 * HOUR)
    store.close()
    variables = {ANONYMOUS.variable: str(CURRENT_HOURS)}
    with settings_server(monkeypatch, tmp_path, catalogue, variables) as running:
        yield running


def ask(page: Page, text: str) -> None:
    """Type `text` in the anonymous unsolved life and press its save button."""
    type_and_save(page, ANONYMOUS_NAME, text)


# ---- AC-17: the question ----


def test_ac17_a_shorter_life_asks_with_the_count_and_saves_nothing(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    sent = RequestLog(page)

    ask(page, "24")

    question = question_of(page, 2)
    expect(question).to_be_visible()
    card = card_of(page)
    expect(card.get_by_role("button", name=CONFIRM, exact=True)).to_be_visible()
    expect(card.get_by_role("button", name=CANCEL, exact=True)).to_be_visible()
    save = button_in(row_of(page, ANONYMOUS_NAME), SAVE)
    expect_asking(page, save, 2)
    pressed_look = quiet_button_problems(save, SAVE)
    under_the_rows = box_below(box_of(question), input_box(page, ANONYMOUS_NAME))
    divided = has_divider(question)
    unchanged = row_text(page, ANONYMOUS_NAME)

    assert pressed_look == []
    assert under_the_rows
    assert divided
    assert unchanged == row_line(ANONYMOUS_NAME, CURRENT_HOURS, "environment")
    assert sent.saves() == []
    assert sent.dry_runs() == [{"name": ANONYMOUS_NAME, "value": 24}]


@pytest.mark.parametrize("closer", ["cancel", "second-press"])
def test_ac17_closing_the_question_sends_nothing_and_leaves_the_row(
    window: OpenWindow, server: SettingsServer, closer: str
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    sent = RequestLog(page)
    ask(page, "24")
    expect(question_of(page, 2)).to_be_visible()

    if closer == "cancel":
        card_of(page).get_by_role("button", name=CANCEL, exact=True).click()
    else:
        button_in(row_of(page, ANONYMOUS_NAME), SAVE).click()

    expect(question_of(page, 2)).to_have_count(0)
    expect(card_of(page).get_by_role("button", name=CONFIRM, exact=True)).to_have_count(
        0
    )
    save = button_in(row_of(page, ANONYMOUS_NAME), SAVE)
    expect_not_asking(save)
    expect_row(page, ANONYMOUS_NAME, CURRENT_HOURS, "environment")
    unpressed_look = button_colour_problems(save, "primary")

    assert unpressed_look == []
    assert sent.saves() == []


def test_ac17_confirm_saves_the_life(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    sent = RequestLog(page)
    ask(page, "24")
    expect(question_of(page, 2)).to_be_visible()

    card_of(page).get_by_role("button", name=CONFIRM, exact=True).click()

    expect_row(page, ANONYMOUS_NAME, 24, "override")
    expect(question_of(page, 2)).to_have_count(0)
    assert sent.saves() == [{"name": ANONYMOUS_NAME, "value": 24}]


def test_ac17_one_room_reads_the_singular(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)

    ask(page, "36")

    expect(question_of(page, 1)).to_be_visible()


def test_ac17_at_most_one_question_is_open(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    ask(page, "24")
    expect(question_of(page, 2)).to_be_visible()

    type_and_save(page, CREATOR.field, "24")

    expect(question_of(page, 0)).to_be_visible()
    expect(question_of(page, 2)).to_have_count(0)
    expect(card_of(page).get_by_role("button", name=CONFIRM, exact=True)).to_have_count(
        1
    )
    expect_asking(page, button_in(row_of(page, CREATOR.field), SAVE), 0)
    expect_not_asking(button_in(row_of(page, ANONYMOUS_NAME), SAVE))


@pytest.mark.parametrize("closer", ["cancel", "confirm"])
def test_ac17_the_focus_goes_back_to_the_save_button_that_asked(
    window: OpenWindow, server: SettingsServer, closer: str
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    ask(page, "24")
    expect(question_of(page, 2)).to_be_visible()
    label = CANCEL if closer == "cancel" else CONFIRM

    card_of(page).get_by_role("button", name=label, exact=True).click()

    expect(question_of(page, 2)).to_have_count(0)
    if closer == "confirm":
        expect_row(page, ANONYMOUS_NAME, 24, "override")
    expect(button_in(row_of(page, ANONYMOUS_NAME), SAVE)).to_be_focused()


def override_the_life(page: Page) -> None:
    """Save the override of 96 over the variable's 48 (longer: no question)."""
    type_and_save(page, ANONYMOUS_NAME, str(OVERRIDE_HOURS))
    expect_row(page, ANONYMOUS_NAME, OVERRIDE_HOURS, "override")


def test_ac17_a_reset_to_a_shorter_life_asks_first_with_a_dry_run_of_null(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    override_the_life(page)
    sent = RequestLog(page)
    reset = button_in(row_of(page, ANONYMOUS_NAME), RESET)

    reset.click()

    expect(question_of(page, 0)).to_be_visible()
    expect_asking(page, reset, 0)
    expect_not_asking(button_in(row_of(page, ANONYMOUS_NAME), SAVE))
    unchanged = row_text(page, ANONYMOUS_NAME)

    assert unchanged == row_line(ANONYMOUS_NAME, OVERRIDE_HOURS, "override")
    assert sent.dry_runs() == [{"name": ANONYMOUS_NAME, "value": None}]
    assert sent.saves() == []


def test_ac17_confirming_a_reset_moves_the_focus_to_the_rows_input(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    override_the_life(page)
    sent = RequestLog(page)
    button_in(row_of(page, ANONYMOUS_NAME), RESET).click()
    expect(question_of(page, 0)).to_be_visible()

    card_of(page).get_by_role("button", name=CONFIRM, exact=True).click()

    expect_row(page, ANONYMOUS_NAME, CURRENT_HOURS, "environment")
    expect(button_in(row_of(page, ANONYMOUS_NAME), RESET)).to_be_disabled()
    expect(input_of(page, ANONYMOUS_NAME)).to_be_focused()
    assert sent.saves() == [{"name": ANONYMOUS_NAME, "value": None}]
