"""Tests of spec 046, AC-3: « Compte » in the catalogue's top bar opens the account
sheet, with the intro for a page outside a room.

Browser with mocked routes: the live server serves `CAT` and the client, and
`page.route` answers `GET /api/account` (200 signed out or signed in, 404, 500),
`POST /api/account/link` (202, the body of each request kept), and, while signed
in, `GET /api/account/history` and `GET /api/account/rooms` with an empty list.

Choices where the spec leaves room:

- "Centred" (the dialog on a wide window) is read on both axes: the dialog's
  centre within 1 px of the window's centre.
- The dialog's heading is the element that its `aria-labelledby` names; its intro
  is the element of the dialog whose text is `account.signed_out_intro`.
- "The dialog is a bottom sheet" is read on its box: the window's width (0.5 px),
  its bottom on the window's bottom (1 px), its top at least 56 px down.
- Edge cases "Wide or narrow" (an open dialog takes the other form's look within
  300 ms and keeps its content) and "Accounts that fail to answer show no
  « Compte »" (`GET /api/account` answering 500) are tested here.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import outline_problems
from spec035_harness import Walker, build_fx01_grid, build_reference_catalogue
from spec042_harness import box_of
from spec043_harness import MUTED, NAVY, WORD, fr_format, fr_value
from spec046_harness import (
    ACCOUNT_ROUTE,
    EMAIL,
    NARROW,
    SIGNED_IN,
    SIGNED_OUT,
    WIDE,
    OpenWindow,
    accounts_on,
    answer_json,
    colour_of,
    colour_problem,
    font_problems,
    is_clear,
    open_catalogue,
    padding_matches,
    page_topbar_problems,
    same_position,
    same_size,
    settled,
    style_of,
    window_opener,
)
from sure_click import click_until_pressed


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return build_reference_catalogue(fx01_grid)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_with_accounts(
    window: OpenWindow,
    base_url: str,
    size: tuple[int, int],
    status: dict[str, object],
) -> tuple[Page, list[object]]:
    """Open `/` with accounts on; return the page and its link request bodies."""
    page = window(*size)
    link_bodies = accounts_on(page, status)
    open_catalogue(page, base_url)
    expect(page.get_by_test_id("account-open")).to_be_visible()
    return page, link_bodies


def open_dialog(page: Page) -> Locator:
    page.get_by_test_id("account-open").click()
    dialog = page.get_by_test_id("account-dialog")
    expect(dialog).to_have_attribute("open", "")
    wait_for_fonts(page)
    return dialog


def heading_of(page: Page, dialog: Locator) -> Locator:
    heading_id = dialog.get_attribute("aria-labelledby")
    assert heading_id is not None, "account-dialog has no aria-labelledby"
    return page.locator(f'[id="{heading_id}"]')


# ---- The button ------------------------------------------------------------------


def test_ac3_account_open_is_a_button_in_the_top_bar_reading_compte(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    button = page.get_by_test_id("page-topbar").get_by_test_id("account-open")

    expect(button).to_have_count(1)
    assert button.evaluate("element => element.tagName") == "BUTTON"
    expect(button).to_have_attribute("type", "button")
    expect(button).to_have_text(fr_value("account.open"))
    expect(button).to_have_attribute("aria-haspopup", "dialog")
    expect(button.locator("svg")).to_have_count(0)


def test_ac3_account_open_is_38_px_high_16_px_from_the_right_navy_on_clear(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    button = page.get_by_test_id("account-open")

    box = box_of(button)

    assert same_size(box.height, 38.0), box
    assert same_position(1280.0 - box.right, 16.0), box
    assert font_problems(button, "account-open", 14.72, colour=NAVY) == []
    assert is_clear(colour_of(button, "backgroundColor"))
    expect(button).to_have_attribute("aria-expanded", "false")


def test_ac3_the_catalogue_has_no_account_link(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)

    expect(page.get_by_test_id("account-link")).to_have_count(0)


def test_ac3_with_accounts_on_the_bar_keeps_its_56_px_and_its_brand(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)

    assert page_topbar_problems(page, 56.0, 16.0) == []


# ---- The dialog on a wide window ----------------------------------------------


def test_ac3_a_click_opens_the_dialog_440_px_wide_centred_with_its_look(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)

    dialog = open_dialog(page)
    box = box_of(dialog)

    assert same_position(box.width, 440.0), box
    assert same_position(box.centre_x, 640.0), box
    assert same_position(box.centre_y, 360.0), box
    assert style_of(dialog, "borderTopLeftRadius") == "12px"
    assert padding_matches(dialog, "20px 22px")


def test_ac3_the_dialog_heading_is_navy_700_at_19_2_px(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    dialog = open_dialog(page)

    heading = heading_of(page, dialog)

    expect(heading).to_have_text(fr_value("account.dialog_heading"))
    assert font_problems(heading, "heading", 19.2, "700", NAVY) == []


def test_ac3_signed_out_the_intro_is_the_one_for_a_page_outside_a_room(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    dialog = open_dialog(page)

    intro = dialog.get_by_text(fr_value("account.signed_out_intro"), exact=True)

    expect(intro).to_have_count(1)
    expect(dialog).not_to_contain_text(fr_value("account.dialog_intro"))
    assert font_problems(intro, "intro", 14.4, colour=MUTED) == []


def test_ac3_while_its_dialog_is_open_account_open_is_expanded_on_word_blue(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    open_dialog(page)
    button = page.get_by_test_id("account-open")

    expect(button).to_have_attribute("aria-expanded", "true")
    assert colour_problem(button, "account-open", "backgroundColor", WORD) == []


def test_ac3_the_link_request_has_no_room_and_its_answer_shows_account_sent(
    window: OpenWindow, live_server: str
) -> None:
    page, link_bodies = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    open_dialog(page)

    email_input = page.get_by_test_id("account-email-input")
    email_input.fill(EMAIL)
    # Fix after #40's CI: the field holds the text before the submit (no race).
    expect(email_input).to_have_value(EMAIL)
    # 2026-10-23: Firefox under load lost the press; main's run after #43.
    click_until_pressed(page.get_by_test_id("account-email-submit"))

    expect(page.get_by_test_id("account-sent")).to_be_visible()
    page.wait_for_timeout(300)
    assert link_bodies == [{"email": EMAIL, "room": None}]


def test_ac3_escape_closes_the_dialog_and_gives_the_focus_back(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    dialog = open_dialog(page)

    page.keyboard.press("Escape")

    expect(dialog).not_to_have_attribute("open", "")
    button = page.get_by_test_id("account-open")
    expect(button).to_be_focused()
    expect(button).to_have_attribute("aria-expanded", "false")


def test_ac3_account_close_closes_the_dialog_and_gives_the_focus_back(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    dialog = open_dialog(page)

    page.get_by_test_id("account-close").click()

    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("account-open")).to_be_focused()


# ---- On a narrow window ----------------------------------------------------------


def test_ac3_on_a_phone_account_open_is_34_px_high(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, NARROW, SIGNED_OUT)

    box = box_of(page.get_by_test_id("account-open"))

    assert same_size(box.height, 34.0), box
    assert same_position(360.0 - box.right, 16.0), box


def test_ac3_on_a_phone_the_dialog_is_a_bottom_sheet(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, NARROW, SIGNED_OUT)

    dialog = open_dialog(page)
    box = box_of(dialog)

    assert same_size(box.width, 360.0), box
    assert same_position(box.bottom, 740.0), box
    assert box.top >= 56.0 - 1.0, box
    assert style_of(dialog, "borderTopLeftRadius") == "16px"
    assert padding_matches(dialog, "14px 18px 18px")


def test_ac3_on_a_phone_a_click_on_the_backdrop_closes_the_sheet(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, NARROW, SIGNED_OUT)
    dialog = open_dialog(page)

    page.mouse.click(180, 80)

    expect(dialog).not_to_have_attribute("open", "")


def test_ac3_an_open_dialog_takes_the_other_look_on_a_resize_and_keeps_its_text(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    dialog = open_dialog(page)

    page.set_viewport_size({"width": 360, "height": 740})
    width = settled(page, lambda: box_of(dialog).width, lambda w: same_size(w, 360))

    assert same_size(width, 360.0), width
    assert same_position(box_of(dialog).bottom, 740.0), box_of(dialog)
    expect(dialog).to_have_attribute("open", "")
    expect(dialog).to_contain_text(fr_value("account.signed_out_intro"))


# ---- Signed in, accounts off -----------------------------------------------------


def test_ac3_signed_in_the_dialog_shows_the_account_and_links_to_its_page(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_IN)

    dialog = open_dialog(page)

    expect(dialog).to_contain_text(fr_value("account.signed_in_heading"))
    expect(dialog).to_contain_text(fr_format("account.signed_in_as", email=EMAIL))
    expect(dialog.get_by_test_id("account-page-link")).to_have_attribute(
        "href", "/account"
    )


@pytest.mark.parametrize("status", [404, 500], ids=["accounts_off", "failed"])
def test_ac3_without_an_account_answer_there_is_no_account_open(
    window: OpenWindow, live_server: str, status: int
) -> None:
    page = window(*WIDE)
    answer_json(page, ACCOUNT_ROUTE, status, {"detail": "Not Found"})

    open_catalogue(page, live_server)
    page.wait_for_timeout(300)

    expect(page.get_by_test_id("account-open")).to_have_count(0)


# ---- Keyboard only ---------------------------------------------------------------


def test_ac3_tab_reaches_account_open_with_spec_035s_outline(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    walker = Walker(page)

    walker.tab_to("account-open")

    reached = walker.reached[0]
    problems = outline_problems(
        reached.outline_style, reached.outline_width, reached.outline_contrast
    )
    assert problems == []


def test_ac3_enter_opens_the_dialog_on_the_address_and_escape_comes_back(
    window: OpenWindow, live_server: str
) -> None:
    page, _ = open_with_accounts(window, live_server, WIDE, SIGNED_OUT)
    Walker(page).tab_to("account-open")

    page.keyboard.press("Enter")

    dialog = page.get_by_test_id("account-dialog")
    expect(dialog).to_have_attribute("open", "")
    expect(page.get_by_test_id("account-email-input")).to_be_focused()
    page.keyboard.press("Escape")
    expect(dialog).not_to_have_attribute("open", "")
    expect(page.get_by_test_id("account-open")).to_be_focused()
