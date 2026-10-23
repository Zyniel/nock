"""Tests of spec 048, AC-1 and AC-2: the shared recap page, one card in the
entry-page frame, and its loading and unavailable states.

The page is opened on `/recap/tok_ABCDEFGHIJKLMNOP` of the live server (an
empty registry), the page itself and its API route answered by `page.route`
(see `spec048_harness`), with `PUBLIC` unless a test says otherwise, in desktop
contexts at 360 by 740 and 1280 by 720.

Readings of the spec's wording:

- "`share-card` holds in order" the five parts: each lies inside the card and
  the gap from one part's bottom to the next one's top is at least 12 px (1 px);
  the card shows nothing else (wrappers aside).
- `share-home` "as wide as its text plus its padding": its box is the width of
  its text plus its left and right padding and borders (1 px).
- A waiting line is 400 15.2 px muted ("State lines"), so `recap-loading`'s
  weight is read too.
- The unavailable recap answers 404, as an expired link does (spec 028); its
  card shows nothing but `share-error` and `share-home`.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from spec042_harness import box_of
from spec043_harness import INK, MUTED, NAVY, fr_value, style_of
from spec046_harness import OpenWindow, font_problems, window_opener
from spec048_harness import (
    CARD_PART_GAP,
    PUBLIC_NO_NUMBER,
    SIZE_IDS,
    SIZES,
    card_title_problems,
    entry_frame_problems,
    gap_at_least,
    open_share,
    open_share_loading,
    open_share_unavailable,
    others_in,
    primary_link_problems,
    role_problems,
    text_problems,
    waiting_line_problems,
)

SHARE_PARTS = ["share-grid", "share-time", "share-team", "share-home"]
TIME_TEXT = "Temps : 12:34"
TEAM_TEXT = "\N{LATIN CAPITAL LETTER E WITH ACUTE}quipe : Ana, Bob"
GRID_TEXT = "Grille n\N{DEGREE SIGN} 12"


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def loaded_share(window: OpenWindow, live_server: str, size: tuple[int, int]) -> Page:
    page = window(*size)
    open_share(page, live_server)
    return page


# ---- AC-1: one card on the page grey -----------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_share_card_sits_in_the_entry_page_frame(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = loaded_share(window, live_server, size)

    problems = entry_frame_problems(page, page.get_by_test_id("share-card"))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_card_holds_its_five_parts_in_order_12_px_apart(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = loaded_share(window, live_server, size)
    card = page.get_by_test_id("share-card")
    heading = card.locator("h1")
    expect(heading).to_have_count(1)
    parts = [heading]
    for test_id in SHARE_PARTS:
        part = card.get_by_test_id(test_id)
        expect(part).to_have_count(1)
        parts.append(part)

    gaps: list[str] = []
    for index in range(len(parts) - 1):
        first = box_of(parts[index])
        second = box_of(parts[index + 1])
        if not gap_at_least(first, second, CARD_PART_GAP):
            gaps.append(f"part {index + 1}: {second.top - first.bottom} px to the next")
    selectors = ["h1", *[f'[data-testid="{test_id}"]' for test_id in SHARE_PARTS]]

    assert gaps == []
    assert others_in(card, selectors) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_the_title_grid_time_and_team_have_their_texts_and_looks(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = loaded_share(window, live_server, size)
    card = page.get_by_test_id("share-card")
    heading = card.locator("h1")
    grid = page.get_by_test_id("share-grid")
    time = page.get_by_test_id("share-time")
    team = page.get_by_test_id("share-team")

    problems = text_problems(heading, "h1", fr_value("share.heading"))
    problems.extend(card_title_problems(heading, "h1"))
    problems.extend(text_problems(grid, "share-grid", GRID_TEXT))
    problems.extend(font_problems(grid, "share-grid", 13.6, colour=MUTED))
    problems.extend(text_problems(time, "share-time", TIME_TEXT))
    problems.extend(font_problems(time, "share-time", 33.6, "700", NAVY))
    if style_of(time, "fontVariantNumeric") != "tabular-nums":
        problems.append(f"share-time: {style_of(time, 'fontVariantNumeric')}")
    problems.extend(text_problems(team, "share-team", TEAM_TEXT))
    problems.extend(font_problems(team, "share-team", 15.2, colour=INK))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac1_share_home_is_a_link_drawn_as_a_primary_button(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = loaded_share(window, live_server, size)
    home = page.get_by_test_id("share-home")

    problems = text_problems(home, "share-home", fr_value("share.home"))
    problems.extend(primary_link_problems(home, "share-home"))

    assert problems == []


def test_ac1_a_recap_without_a_grid_number_shows_no_share_grid(
    window: OpenWindow, live_server: str
) -> None:
    page = window(360, 740)
    open_share(page, live_server, PUBLIC_NO_NUMBER)

    expect(page.get_by_test_id("share-time")).to_have_text(TIME_TEXT)
    expect(page.get_by_test_id("share-grid")).to_have_count(0)
    card = page.get_by_test_id("share-card")
    selectors = ["h1", '[data-testid="share-time"]', '[data-testid="share-team"]']
    selectors.append('[data-testid="share-home"]')
    assert others_in(card, selectors) == []


# ---- AC-2: loading and unavailable ---------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac2_while_loading_the_card_holds_only_one_muted_status_line(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_share_loading(page, live_server)
    expect(page.get_by_test_id("recap-page")).to_have_attribute("data-state", "loading")
    card = page.get_by_test_id("share-card")
    line = card.get_by_test_id("recap-loading")
    expect(line).to_have_count(1)

    problems = text_problems(line, "recap-loading", fr_value("recap.loading"))
    problems.extend(role_problems(line, "recap-loading", "status"))
    problems.extend(waiting_line_problems(line, "recap-loading"))
    problems.extend(others_in(card, ['[data-testid="recap-loading"]']))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac2_while_loading_the_card_is_in_the_entry_page_frame(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_share_loading(page, live_server)

    problems = entry_frame_problems(page, page.get_by_test_id("share-card"))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac2_an_unavailable_recap_keeps_the_card_with_its_title_and_way_on(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_share_unavailable(page, live_server)
    card = page.get_by_test_id("share-card")
    error = card.get_by_test_id("share-error")
    home = card.get_by_test_id("share-home")
    expect(error).to_have_count(1)
    expect(home).to_have_count(1)

    problems: list[str] = []
    tag = error.evaluate("element => element.tagName")
    if tag != "H1":
        problems.append(f"share-error is a {tag}")
    problems.extend(text_problems(error, "share-error", fr_value("share.error")))
    problems.extend(card_title_problems(error, "share-error"))
    problems.extend(primary_link_problems(home, "share-home"))
    if box_of(home).top < box_of(error).bottom:
        problems.append("share-home is not under share-error")
    selectors = ['[data-testid="share-error"]', '[data-testid="share-home"]']
    problems.extend(others_in(card, selectors))

    assert problems == []
    expect(page.locator("h1")).to_have_count(1)


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac2_the_unavailable_card_is_in_the_entry_page_frame(
    window: OpenWindow, live_server: str, size: tuple[int, int]
) -> None:
    page = window(*size)
    open_share_unavailable(page, live_server)

    problems = entry_frame_problems(page, page.get_by_test_id("share-card"))

    assert problems == []
