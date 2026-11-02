"""Tests of `lobby/host.md` AC-18, AC-19 and AC-20: the host's settings sheet
(rule 8) keeps the focus inside, refuses a bad count in French, and goes with the
host role.

AC-18: at 1280 by 720, the sheet opened by keyboard: Tab on « Enregistrer » focuses
the switch « Verrouiller le salon », Shift+Tab on the switch focuses
« Enregistrer », and no run of Tabs leaves the sheet.

AC-19: `100` in « Lettres à révéler » and a press on « Enregistrer » send nothing;
the sheet stays open, the field is focused, marked invalid and described by
« Entrez un nombre entier de 0 à 99. », « Mots à révéler » unmarked; `-1`, `2.5` and
an empty field do the same. Set to `3`, the next « Enregistrer » sends 3 and closes
the sheet, and reopened it shows no error line. Rule 8 adds: each refused count is
marked, the focus goes to the first, each « Enregistrer » sets the marks anew and a
close clears them.

AC-20: Ana's host sheet open at 360 by 740, a `host_changed` to Bob closes it and
focuses « Menu », whose items no longer hold « Réglages de l'hôte ».

Readings where the spec leaves room:

- "Marked invalid" is `aria-invalid` `true`; "unmarked" is `aria-invalid` absent
  or `false`. "Described by" is the field's accessible description, which is the
  text of the element its `aria-describedby` names.
- The error line is the one element of the sheet whose text is the French line;
  it is one line for both fields, so it shows once when both are refused.
- "Sends nothing" is read 300 ms after the press: no frame but keep-alive pings.
- A walk of 12 Tabs then 12 Shift+Tabs has no element outside the sheet, `body`
  included, and meets the switch, a help-mode choice, both counts and
  « Enregistrer ».
- "Opened by keyboard" is spec 043's `open_host_settings_with_keyboard`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import host_changed_frame, open_host_sheet
from nock.grid import Grid
from nock.protocol import ChangeSettings, HelpMode, RevealBudget, parse_client_message
from room_panels import open_host_settings
from spec019_harness import OpenWindow, window_opener
from spec035_harness import Walker
from spec043_harness import (
    COMPUTER,
    PHONE,
    fr_value,
    frames_sent_after,
    send_and_wait,
)

COUNT_ERROR = "Entrez un nombre entier de 0 à 99."  # `settings.error.count`
WALK_PRESSES = 12
SHEET_CONTROLS = [
    "lock-room",
    "help-mode-option",
    "reveal-letters-input",
    "reveal-words-input",
    "settings-save",
]

# The `data-testid` of the focused element when it is inside the sheet, else `outside`.
FOCUS_IN_SHEET_SCRIPT = r"""
() => {
  const sheet = document.querySelector('[data-testid="host-settings"]');
  const active = document.activeElement;
  if (active === null || !sheet.contains(active)) {
    return 'outside';
  }
  return active.getAttribute('data-testid') || active.tagName;
}
"""

# ---- Fixtures --------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    """Return the fixture grid FX-01, parsed."""
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    """Return `window(width, height, touch)`: a page in a context of that size."""
    yield from window_opener(browser, browser_name)


def count_inputs(page: Page) -> dict[str, Locator]:
    """The two count fields of the open sheet, by name."""
    return {
        "letters": page.get_by_test_id("reveal-letters-input"),
        "words": page.get_by_test_id("reveal-words-input"),
    }


def marked_invalid(field: Locator) -> bool:
    """Whether a field has `aria-invalid` `true`."""
    return field.get_attribute("aria-invalid") == "true"


def focus_place(page: Page) -> str:
    """The test id of the focused element, or `outside` when it is not in the sheet."""
    found = page.evaluate(FOCUS_IN_SHEET_SCRIPT)
    assert isinstance(found, str), found
    return found


def fill_counts_and_save(page: Page, letters: str, words: str) -> None:
    """Fill both counts and press « Enregistrer »."""
    fields = count_inputs(page)
    fields["letters"].fill(letters)
    fields["words"].fill(words)
    page.get_by_test_id("settings-save").click()


def expect_no_marks(page: Page) -> None:
    """Neither count is marked invalid and the sheet shows no error line."""
    dialog = page.get_by_test_id("host-settings")
    for name, field in count_inputs(page).items():
        assert not marked_invalid(field), name
        expect(field).not_to_have_accessible_description(COUNT_ERROR)
    expect(dialog.get_by_text(COUNT_ERROR, exact=True)).to_have_count(0)


# ---- AC-18: the Tab trap -----------------------------------------------------------


def test_ac18_tab_wraps_from_enregistrer_to_the_switch_and_back(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid, keyboard=True)
    Walker(page).tab_to("settings-save")
    expect(page.get_by_test_id("settings-save")).to_be_focused()

    page.keyboard.press("Tab")
    expect(page.get_by_test_id("lock-room")).to_be_focused()
    page.keyboard.press("Shift+Tab")

    expect(page.get_by_test_id("settings-save")).to_be_focused()


def test_ac18_no_run_of_tabs_leaves_the_sheet(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid, keyboard=True)

    places: list[str] = []
    for key in ["Tab"] * WALK_PRESSES + ["Shift+Tab"] * WALK_PRESSES:
        page.keyboard.press(key)
        places.append(focus_place(page))

    assert "outside" not in places, places
    for control in SHEET_CONTROLS:
        assert control in places, (control, places)
    expect(page.get_by_test_id("host-settings")).to_have_attribute("open", "")


# ---- AC-19: a count that is not whole, 0 to 99 -----------------------------------


def test_ac19_fr_json_holds_the_count_error() -> None:
    assert fr_value("settings.error.count") == COUNT_ERROR


@pytest.mark.parametrize(
    ("letters", "words", "refused"),
    [
        ("100", "1", ["letters"]),
        ("-1", "1", ["letters"]),
        ("2.5", "1", ["letters"]),
        ("", "1", ["letters"]),
        ("5", "100", ["words"]),
        ("5", "2.5", ["words"]),
        ("100", "", ["letters", "words"]),
    ],
    ids=["100", "-1", "2.5", "empty", "words-100", "words-2.5", "both"],
)
def test_ac19_a_refused_count_sends_nothing_and_is_marked_with_the_error(
    window: OpenWindow,
    live_server: str,
    fx01_grid: Grid,
    letters: str,
    words: str,
    refused: list[str],
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    mock = open_host_sheet(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")
    fields = count_inputs(page)

    frames = frames_sent_after(
        page, mock, lambda: fill_counts_and_save(page, letters, words)
    )

    assert frames == []
    expect(dialog).to_have_attribute("open", "")
    expect(fields[refused[0]]).to_be_focused()
    for name, field in fields.items():
        if name in refused:
            expect(field).to_have_attribute("aria-invalid", "true")
            expect(field).to_have_accessible_description(COUNT_ERROR)
        else:
            assert not marked_invalid(field), name
            expect(field).not_to_have_accessible_description(COUNT_ERROR)
    line = dialog.get_by_text(COUNT_ERROR, exact=True)
    expect(line).to_have_count(1)
    expect(line).to_be_visible()


def test_ac19_set_to_3_the_next_save_sends_3_and_closes_and_reopened_is_clear(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    mock = open_host_sheet(page, live_server, fx01_grid)
    dialog = page.get_by_test_id("host-settings")
    letters = count_inputs(page)["letters"]
    letters.fill("100")
    page.get_by_test_id("settings-save").click()
    expect(letters).to_have_attribute("aria-invalid", "true")
    letters.fill("3")

    frames = frames_sent_after(
        page, mock, lambda: page.get_by_test_id("settings-save").click()
    )

    sent = [parse_client_message(frame) for frame in frames]
    assert sent == [
        ChangeSettings(
            help_mode=HelpMode.FREE, reveal_budget=RevealBudget(letters=3, words=1)
        )
    ]
    expect(dialog).not_to_have_attribute("open", "")
    open_host_settings(page)
    expect_no_marks(page)


def test_ac19_each_save_sets_the_marks_anew(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid)
    fields = count_inputs(page)
    fill_counts_and_save(page, "100", "1")
    expect(fields["letters"]).to_have_attribute("aria-invalid", "true")

    fill_counts_and_save(page, "3", "100")

    expect(fields["words"]).to_have_attribute("aria-invalid", "true")
    expect(fields["words"]).to_be_focused()
    assert not marked_invalid(fields["letters"])
    expect(fields["letters"]).not_to_have_accessible_description(COUNT_ERROR)
    expect(
        page.get_by_test_id("host-settings").get_by_text(COUNT_ERROR, exact=True)
    ).to_have_count(1)


def test_ac19_a_close_without_saving_clears_the_marks(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(COMPUTER[0], COMPUTER[1], False)
    open_host_sheet(page, live_server, fx01_grid)
    fill_counts_and_save(page, "100", "100")
    expect(count_inputs(page)["letters"]).to_have_attribute("aria-invalid", "true")

    page.keyboard.press("Escape")
    expect(page.get_by_test_id("host-settings")).not_to_have_attribute("open", "")
    open_host_settings(page)

    expect_no_marks(page)


# ---- AC-20: the host role goes while the sheet is open ---------------------------


def test_ac20_a_host_change_closes_the_sheet_and_focuses_menu(
    window: OpenWindow, live_server: str, fx01_grid: Grid
) -> None:
    page = window(PHONE[0], PHONE[1], False)
    mock = open_host_sheet(page, live_server, fx01_grid)
    expect(page.get_by_test_id("host-settings")).to_have_attribute("open", "")

    send_and_wait(page, mock, host_changed_frame(6, "p2"))

    expect(page.locator('[data-testid="host-settings"][open]')).to_have_count(0)
    expect(page.get_by_test_id("menu-button")).to_be_focused()
    room_menu = page.get_by_test_id("room-menu")
    expect(room_menu.get_by_test_id("host-settings-open")).to_have_count(0)
