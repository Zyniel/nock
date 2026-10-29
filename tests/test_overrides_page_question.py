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

Reading taken where the spec leaves room: "under a divider" is read as a line or a
rule above the question's block (`has_divider` of `overrides_harness`), and the
question stands under the rows.

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
    SAVE,
    RequestLog,
    SettingsServer,
    box_below,
    button_in,
    card_of,
    expect_row,
    has_divider,
    input_box,
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
from spec046_harness import OpenWindow, window_opener

ANONYMOUS_NAME = ANONYMOUS.field
CURRENT_HOURS = 48


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
    expect(button_in(row_of(page, ANONYMOUS_NAME), SAVE)).to_have_attribute(
        "aria-pressed", "true"
    )
    under_the_rows = box_below(box_of(question), input_box(page, ANONYMOUS_NAME))
    divided = has_divider(question)
    unchanged = row_text(page, ANONYMOUS_NAME)

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
    expect(button_in(row_of(page, ANONYMOUS_NAME), SAVE)).not_to_have_attribute(
        "aria-pressed", "true"
    )
    expect_row(page, ANONYMOUS_NAME, CURRENT_HOURS, "environment")
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
    expect(button_in(row_of(page, CREATOR.field), SAVE)).to_have_attribute(
        "aria-pressed", "true"
    )
    expect(button_in(row_of(page, ANONYMOUS_NAME), SAVE)).not_to_have_attribute(
        "aria-pressed", "true"
    )
