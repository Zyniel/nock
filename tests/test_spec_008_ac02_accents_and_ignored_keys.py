"""Tests of spec 008, AC-2: accents fold and the other keys are ignored.

Accented letters enter the letter without accent; digits, space, punctuation,
ligatures, named keys and modifier combinations enter nothing. The shared setup is
in `spec008_harness`.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import EditLetter, Erase
from spec008_harness import (
    ACROSS_W1,
    across,
    dispatch_key,
    expect_edits,
    expect_letter,
    expect_letters,
    expect_selection,
    grid_from_text,
    open_fx01,
    press_all,
    put,
    sent_edits,
    sent_selections,
    settle,
    tap,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


# ---- AC-2: accents fold, other keys are ignored ------------------------------


def test_ac2_accented_letters_enter_the_letter_without_accent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    press_all(page, ["é", "à", "ç"])

    expect_letters(page, {(1, 0): "E", (1, 1): "A", (1, 2): "C"})
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "E"), put(1, 1, "A"), put(1, 2, "C")])


def test_ac2_other_french_accents_and_capitals_fold_to_one_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    # e grave, e circumflex, e diaeresis, E acute, i circumflex
    press_all(page, ["è", "ê", "ë", "É", "î"])

    expect_letters(
        page, {(1, 0): "E", (1, 1): "E", (1, 2): "E", (1, 3): "E", (1, 4): "I"}
    )
    tap(page, 3, 1)
    # a circumflex, i diaeresis, o circumflex, u grave
    press_all(page, ["â", "ï", "ô", "ù"])
    expect_letters(page, {(3, 1): "A", (3, 2): "I", (3, 3): "O", (3, 4): "U"})
    tap(page, 4, 1)
    # u circumflex, u diaeresis, C cedilla, A grave
    press_all(page, ["û", "ü", "Ç", "À"])
    expect_letters(page, {(4, 1): "U", (4, 2): "U", (4, 3): "C", (4, 4): "A"})
    expected: list[EditLetter | Erase] = [
        put(1, 0, "E"),
        put(1, 1, "E"),
        put(1, 2, "E"),
        put(1, 3, "E"),
        put(1, 4, "I"),
        put(3, 1, "A"),
        put(3, 2, "I"),
        put(3, 3, "O"),
        put(3, 4, "U"),
        put(4, 1, "U"),
        put(4, 2, "U"),
        put(4, 3, "C"),
        put(4, 4, "A"),
    ]
    expect_edits(page, mock, expected)


def test_ac2_digits_space_and_punctuation_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    press_all(page, ["é", "à", "ç"])
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "E"), put(1, 1, "A"), put(1, 2, "C")])
    frames_before = len(mock.frames_without_pings())

    press_all(page, ["1", "Space", ".", "-", "'", "?"])

    settle(page)
    expect_selection(page, 1, 3, "across", ACROSS_W1)
    expect_letters(
        page, {(1, 0): "E", (1, 1): "A", (1, 2): "C", (1, 3): "", (1, 4): ""}
    )
    assert len(mock.frames_without_pings()) == frames_before


def test_ac2_ligatures_and_other_letters_that_do_not_fold_are_ignored(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    frames_before = len(mock.frames_without_pings())

    # oe ligature, ae ligature, sharp s, o with stroke, then named keys
    press_all(page, ["œ", "æ", "ß", "ø"])
    dispatch_key(page, "Dead")
    dispatch_key(page, "F2")
    dispatch_key(page, "Enter")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert len(mock.frames_without_pings()) == frames_before


def test_ac2_shift_a_gives_a_capital_a(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    page.keyboard.press("Shift+A")

    expect_letter(page, 1, 0, "A")
    expect_selection(page, 1, 1, "across", ACROSS_W1)
    expect_edits(page, mock, [put(1, 0, "A")])


def test_ac2_modifier_combinations_are_left_to_the_browser(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)
    expect_selection(page, 1, 0, "across", ACROSS_W1)

    page.keyboard.press("Control+a")
    page.keyboard.press("Meta+r")
    page.keyboard.press("Alt+e")

    settle(page)
    expect_selection(page, 1, 0, "across", ACROSS_W1)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert dispatch_key(page, "a", ctrl=True) is True
    assert dispatch_key(page, "r", meta=True) is True
    assert dispatch_key(page, "e", alt=True) is True
    assert dispatch_key(page, "a", composing=True) is True
    settle(page)
    expect(page.locator('[data-testid="cell"][data-letter=""]')).to_have_count(18)
    assert sent_edits(mock) == []
    assert sent_selections(mock) == [across(1, 0)]


def test_ac2_handled_keys_are_prevented_and_ignored_keys_are_not(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid)
    tap(page, 1, 0)

    assert dispatch_key(page, "q") is False
    assert dispatch_key(page, "é") is False
    assert dispatch_key(page, "Backspace") is False
    assert dispatch_key(page, "1") is True
    assert dispatch_key(page, "œ") is True
