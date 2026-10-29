"""Tests of admin/overrides, AC-20: the keyboard, the scans and the phone.

The server (`server`) is the real app on a database file that holds one override
before it starts: `creator_room_hours` 96, so that its « Rétablir » is enabled and
the Tab order of a row with three controls is read. The question is opened on
`anonymous_room_hours` (720 hours, a value of 24 is shorter), which asks with 0
rooms.

- Keys: the focus is put on the first input, then Tab is pressed once per control
  and the next control must have the focus, with spec 048's focus ring (a 2 px solid
  navy outline at offset 2 px, `ring_problems`). A disabled button is not a stop.
- Scans: spec 035's contrast and language scans (`spec024_harness`), with the
  question open, at 1280 by 720 and 360 by 740. The language scan accepts no test
  data: the card holds French text and numbers only.
- Phone: at 360 px wide each row stacks (the input and the buttons start under the
  name's text) and no window scrolls sideways, at both sizes.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from lifetime_harness import ANONYMOUS, CREATOR
from nock.catalogue import Catalogue
from overrides_harness import (
    CANCEL,
    CONFIRM,
    INTERVAL,
    RESET,
    SAVE,
    SETTING_NAMES,
    TITLES,
    RequestLog,
    SettingsServer,
    box_below,
    button_in,
    card_of,
    expect_row,
    input_box,
    input_of,
    insert_override_rows,
    open_card,
    question_of,
    row_of,
    settings_server,
    type_and_save,
)
from spec024_harness import contrast_problems, language_problems
from spec033_harness import DATABASE_FILE_NAME
from spec042_harness import box_of
from spec046_harness import OpenWindow, window_opener
from spec048_harness import SIZE_IDS, SIZES, no_horizontal_scroll, ring_problems

ANONYMOUS_NAME = ANONYMOUS.field
CREATOR_NAME = CREATOR.field
MAX_TABS = 6
STACKED_WIDTH = 360


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalogue: Catalogue
) -> Iterator[SettingsServer]:
    """The real app on a file with an override of `creator_room_hours`."""
    insert_override_rows(tmp_path / DATABASE_FILE_NAME, [(CREATOR_NAME, 96)])
    with settings_server(monkeypatch, tmp_path, catalogue) as running:
        yield running


def open_question(page: Page) -> None:
    """Ask the question of a shorter `anonymous_room_hours` and wait for it."""
    type_and_save(page, ANONYMOUS_NAME, "24")
    expect(question_of(page, 0)).to_be_visible()


def press_tab_and_expect(page: Page, control: Locator, name: str) -> list[str]:
    """Press Tab, expect the focus on `control`, and read its focus ring."""
    page.keyboard.press("Tab")
    expect(control).to_be_focused()
    return ring_problems(control, name)


def tab_until_focused(page: Page, control: Locator, name: str) -> list[str]:
    """Press Tab, at most `MAX_TABS` times, until `control` has the focus."""
    for _ in range(MAX_TABS):
        page.keyboard.press("Tab")
        if control.evaluate("element => element === document.activeElement") is True:
            return ring_problems(control, name)
    pytest.fail(f"Tab did not reach {name} in {MAX_TABS} presses")


# ---- AC-20: keys ----


def test_ac20_tab_reaches_each_input_and_enabled_button_with_the_focus_ring(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    expected: list[tuple[Locator, str]] = []
    for name in SETTING_NAMES:
        row = row_of(page, name)
        expected.append((input_of(page, name), f"{name} input"))
        expected.append((button_in(row, SAVE), f"{name} save"))
        if name == CREATOR_NAME:
            expected.append((button_in(row, RESET), f"{name} reset"))
    expect(button_in(row_of(page, ANONYMOUS_NAME), RESET)).to_be_disabled()

    first_control, first_name = expected[0]
    first_control.focus()
    expect(first_control).to_be_focused()
    problems = ring_problems(first_control, first_name)
    for control, control_name in expected[1:]:
        problems.extend(press_tab_and_expect(page, control, control_name))

    assert problems == []


def test_ac20_enter_in_an_input_saves(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    sent = RequestLog(page)

    field = input_of(page, INTERVAL)
    field.fill("30")
    field.press("Enter")

    expect_row(page, INTERVAL, 30, "override")
    assert sent.saves() == [{"name": INTERVAL, "value": 30}]


def test_ac20_with_the_question_open_tab_reaches_confirm_then_cancel_with_the_ring(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(1280, 720)
    open_card(page, server.base_url)
    open_question(page)
    card = card_of(page)
    button_in(row_of(page, ANONYMOUS_NAME), SAVE).focus()

    problems = tab_until_focused(
        page, card.get_by_role("button", name=CONFIRM, exact=True), "confirm"
    )
    problems.extend(
        press_tab_and_expect(
            page, card.get_by_role("button", name=CANCEL, exact=True), "cancel"
        )
    )

    assert problems == []


# ---- AC-20: the scans, the phone ----


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_with_the_question_open_the_contrast_and_language_scans_find_nothing(
    window: OpenWindow, server: SettingsServer, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_card(page, server.base_url)
    open_question(page)

    contrast = contrast_problems(page)
    language = language_problems(page, set())

    assert contrast == []
    assert language == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac20_with_the_question_open_no_window_scrolls_sideways(
    window: OpenWindow, server: SettingsServer, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_card(page, server.base_url)
    open_question(page)

    assert no_horizontal_scroll(page)


def test_ac20_on_a_phone_each_row_stacks(
    window: OpenWindow, server: SettingsServer
) -> None:
    page = window(STACKED_WIDTH, 740)
    open_card(page, server.base_url)

    problems: list[str] = []
    for name in SETTING_NAMES:
        row = row_of(page, name)
        title = box_of(row.get_by_text(TITLES[name], exact=True))
        field = input_box(page, name)
        save = box_of(button_in(row, SAVE))
        if not box_below(field, title):
            problems.append(f"{name}: the input does not start under the name")
        if not box_below(save, title):
            problems.append(f"{name}: the save button does not start under the name")

    assert problems == []
