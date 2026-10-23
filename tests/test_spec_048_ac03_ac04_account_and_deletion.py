"""Tests of spec 048, AC-3 and AC-4: the account page signed in, one card in the
entry-page frame, and the deletion asked once more in the same card.

The server is spec 033's live server with accounts on (`account_live_server`),
which serves `/account`; every account route is answered by `page.route`
(`AccountMock` of `spec048_harness`). The page signs in through
`/account#<43 characters>`, answered with a `SignInResult` for
`ana.probe@example.org` whose `room_code` is `K7QM2X`. Windows: desktop contexts
at 360 by 740 and 1280 by 720, and 320 by 568 where AC-3 says so.

Readings of the spec's wording:

- "Holds in order ... each the next one's top 12 px or more above": each part
  lies inside the card and the gap from its bottom to the next part's top is at
  least 12 px (1 px).
- "On one line ... 8 px apart": the vertical centres within 1 px, and the gap
  from the first button's right edge to the second's left edge 8 px (1 px).
- "One button per line" (at 360 by 740 and 320 by 568, refined by the lead on
  2026-10-23 after the code, as the screens sheet draws it): the second button's
  top 8 px under the first one's bottom (1 px; for AC-4, cancel 8 px under
  confirm and confirm 12 px under the warning), each inside the card's content
  box (1 px). At 320 by 568, "the row wraps the same way" is read with the same
  8 px gap.
- "Below `account-actions`": the panel's top is not above the row's bottom
  (1 px); "as wide as the card's content": the card's width less its borders and
  paddings (1 px).
- The panel "hides": `account-delete-panel` is hidden or gone.
- "No element inside `account-page` is red" is read with the panel shown, the
  state where a destructive button could be red.
- The edge cases of AC-3 and AC-4 are checked as well: a long address wraps in
  the card; signing out while the question shows gives `signed_out` without the
  panel; toggling the panel sends no `DELETE`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from spec033_harness import ANA_EMAIL, AccountServer, account_live_server
from spec042_harness import box_of
from spec043_harness import INK, LINE, NAVY, RED, fr_format, fr_value, style_of
from spec046_harness import (
    OpenWindow,
    button_colour_problems,
    colour_problem,
    content_box,
    font_problems,
    same_position,
    window_opener,
)
from spec048_harness import (
    CARD_PART_GAP,
    ROOM_CODE,
    SIZE_IDS,
    SIZES,
    SMALL,
    AccountMock,
    account_card,
    ask_deletion,
    box_inside,
    card_title_problems,
    coloured_in,
    done_line_problems,
    entry_frame_problems,
    expect_account_state,
    gap_at_least,
    no_horizontal_scroll,
    open_account,
    open_signed_in,
    others_in,
    primary_link_problems,
    quiet_button_problems,
    role_problems,
    secondary_button_problems,
    text_problems,
)

LONG_EMAIL = "ana." + "tres-longue-adresse" * 4 + "@example.org"


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def account_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[AccountServer]:
    with account_live_server(tmp_path, catalogue) as server:
        yield server


def signed_in_page(
    window: OpenWindow, server: AccountServer, size: tuple[int, int]
) -> tuple[Page, AccountMock]:
    page = window(*size)
    mock = open_signed_in(page, server.base_url)
    return page, mock


def side_by_side_problems(first_id: str, second_id: str, page: Page) -> list[str]:
    """Two buttons on one line (centres within 1 px), 8 px apart (1 px)."""
    first = box_of(page.get_by_test_id(first_id))
    second = box_of(page.get_by_test_id(second_id))
    problems: list[str] = []
    if not same_position(first.centre_y, second.centre_y):
        problems.append(f"{first_id} and {second_id} are not on one line")
    if not same_position(second.left - first.right, 8.0):
        problems.append(f"{second.left - first.right} px from {first_id}")
    return problems


def stacked_problems(
    first_id: str, second_id: str, page: Page, card: Locator
) -> list[str]:
    """One button per line: the second 8 px under the first (1 px), each inside
    the card's content box (1 px)."""
    first = box_of(page.get_by_test_id(first_id))
    second = box_of(page.get_by_test_id(second_id))
    inner = content_box(card)
    problems: list[str] = []
    if not same_position(second.top - first.bottom, 8.0):
        problems.append(
            f"{second_id} is {second.top - first.bottom} px under {first_id}"
        )
    for test_id, box in ((first_id, first), (second_id, second)):
        if not box_inside(box, inner):
            problems.append(f"{test_id} {box} is not inside the card's content {inner}")
    return problems


# ---- AC-3: the signed-in card -------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_signed_in_the_card_sits_in_the_entry_page_frame(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)

    problems = entry_frame_problems(page, account_card(page))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_card_holds_its_title_address_room_link_and_actions_in_order(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    card = account_card(page)
    heading = card.locator("h1")
    expect(heading).to_have_count(1)
    test_ids = ["account-email", "account-room-link", "account-actions"]
    parts = [heading]
    for test_id in test_ids:
        part = card.get_by_test_id(test_id)
        expect(part).to_have_count(1)
        parts.append(part)

    problems: list[str] = []
    for index in range(len(parts) - 1):
        first = box_of(parts[index])
        second = box_of(parts[index + 1])
        if not gap_at_least(first, second, CARD_PART_GAP):
            problems.append(f"part {index + 1}: {second.top - first.bottom} px apart")
    selectors = ["h1", *[f'[data-testid="{test_id}"]' for test_id in test_ids]]
    problems.extend(others_in(card, selectors))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_title_address_and_room_link_have_their_texts_and_looks(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    heading = account_card(page).locator("h1")
    email = page.get_by_test_id("account-email")
    link = page.get_by_test_id("account-room-link")

    problems = text_problems(heading, "h1", fr_value("account.page_heading"))
    problems.extend(card_title_problems(heading, "h1"))
    signed_in_as = fr_format("account.signed_in_as", email=ANA_EMAIL)
    problems.extend(text_problems(email, "account-email", signed_in_as))
    problems.extend(font_problems(email, "account-email", 15.2, colour=INK))
    back = fr_format("account.back_to_room", code=ROOM_CODE)
    problems.extend(text_problems(link, "account-room-link", back))
    problems.extend(colour_problem(link, "account-room-link", "color", NAVY))
    if style_of(link, "fontWeight") != "600":
        problems.append(f"account-room-link: weight {style_of(link, 'fontWeight')}")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_the_two_actions_are_secondary_buttons_side_by_side_or_stacked(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    actions = page.get_by_test_id("account-actions")
    sign_out = actions.get_by_test_id("account-sign-out")
    delete = actions.get_by_test_id("account-delete")
    expect(sign_out).to_have_count(1)
    expect(delete).to_have_count(1)

    if size == (1280, 720):
        problems = side_by_side_problems("account-sign-out", "account-delete", page)
        if box_of(sign_out).left > box_of(delete).left:
            problems.append("account-delete comes before account-sign-out")
    else:
        card = account_card(page)
        problems = stacked_problems("account-sign-out", "account-delete", page, card)
    problems.extend(secondary_button_problems(sign_out, "account-sign-out"))
    problems.extend(secondary_button_problems(delete, "account-delete"))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac3_account_delete_is_a_closed_disclosure_naming_the_panel(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    delete = page.get_by_test_id("account-delete")
    expanded = delete.get_attribute("aria-expanded")
    controls = delete.get_attribute("aria-controls")

    ask_deletion(page)
    panel_id = page.get_by_test_id("account-delete-panel").get_attribute("id")

    assert expanded == "false"
    assert panel_id is not None
    assert panel_id != ""
    assert controls == panel_id


def test_ac3_at_320_by_568_the_buttons_stack_inside_the_card_and_nothing_scrolls(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page, _ = signed_in_page(window, account_server, SMALL)
    card = account_card(page)

    problems = stacked_problems("account-sign-out", "account-delete", page, card)

    assert problems == []
    assert no_horizontal_scroll(page)


def test_ac3_a_long_address_wraps_inside_the_card(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page = window(360, 740)
    mock = AccountMock(status=(200, {"signed_in": True, "email": LONG_EMAIL}))
    open_account(page, account_server.base_url, mock, "signed_in")

    email = box_of(page.get_by_test_id("account-email"))

    assert box_inside(email, content_box(account_card(page)))
    assert no_horizontal_scroll(page)


# ---- AC-4: the deletion, asked in the same card -------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac4_a_click_on_delete_presses_it_quietly_and_shows_the_panel(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    delete = page.get_by_test_id("account-delete")

    ask_deletion(page)

    expect(delete).to_have_attribute("aria-expanded", "true")
    panel = page.get_by_test_id("account-delete-panel")
    card = account_card(page)
    panel_box = box_of(panel)
    actions_box = box_of(page.get_by_test_id("account-actions"))
    problems = quiet_button_problems(delete, "account-delete")
    if panel_box.top < actions_box.bottom - 1.0:
        problems.append(f"the panel's top {panel_box.top} is above the actions")
    if not box_inside(panel_box, box_of(card)):
        problems.append("the panel is not inside the card")
    if not same_position(panel_box.width, content_box(card).width):
        problems.append(f"the panel is {panel_box.width} px wide")
    if style_of(panel, "borderTopWidth") != "1px":
        problems.append(f"panel border-top {style_of(panel, 'borderTopWidth')}")
    if style_of(panel, "borderTopStyle") != "solid":
        problems.append(f"panel border-top {style_of(panel, 'borderTopStyle')}")
    problems.extend(colour_problem(panel, "panel", "borderTopColor", LINE))
    if style_of(panel, "paddingTop") != "12px":
        problems.append(f"panel padding-top {style_of(panel, 'paddingTop')}")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac4_the_panel_holds_the_warning_then_confirm_and_cancel(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    ask_deletion(page)
    panel = page.get_by_test_id("account-delete-panel")
    warning = panel.get_by_test_id("account-delete-warning")
    confirm = panel.get_by_test_id("account-delete-confirm")
    cancel = panel.get_by_test_id("account-delete-cancel")
    expect(warning).to_have_count(1)
    expect(confirm).to_have_count(1)
    expect(cancel).to_have_count(1)

    warning_text = fr_value("account.delete_warning")
    problems = text_problems(warning, "account-delete-warning", warning_text)
    problems.extend(font_problems(warning, "warning", 15.2, colour=INK))
    problems.extend(button_colour_problems(confirm, "primary"))
    problems.extend(button_colour_problems(cancel, "secondary"))
    pair = ("account-delete-confirm", "account-delete-cancel")
    warning_bottom = box_of(warning).bottom
    if size == (1280, 720):
        problems.extend(side_by_side_problems(*pair, page))
        lined_up = [("confirm", confirm), ("cancel", cancel)]
    else:
        problems.extend(stacked_problems(*pair, page, account_card(page)))
        lined_up = [("confirm", confirm)]
    for name, button in lined_up:
        gap = box_of(button).top - warning_bottom
        if not same_position(gap, 12.0):
            problems.append(f"{name}'s top {gap} px under the warning")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac4_no_element_of_the_page_is_red_while_deletion_is_asked(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    ask_deletion(page)

    red = coloured_in(page.get_by_test_id("account-page"), RED)

    assert red == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac4_cancel_hides_the_panel_and_delete_is_secondary_again(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_in_page(window, account_server, size)
    ask_deletion(page)
    delete = page.get_by_test_id("account-delete")

    page.get_by_test_id("account-delete-cancel").click()

    expect(page.get_by_test_id("account-delete-panel")).to_be_hidden()
    expect(delete).to_have_attribute("aria-expanded", "false")
    assert button_colour_problems(delete, "secondary") == []


def test_ac4_account_delete_shows_then_hides_the_panel_and_sends_nothing(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page, mock = signed_in_page(window, account_server, (1280, 720))
    delete = page.get_by_test_id("account-delete")
    panel = page.get_by_test_id("account-delete-panel")
    ask_deletion(page)
    page.get_by_test_id("account-delete-cancel").click()
    expect(panel).to_be_hidden()

    delete.click()
    expect(panel).to_be_visible()
    expect(delete).to_have_attribute("aria-expanded", "true")
    delete.click()

    expect(panel).to_be_hidden()
    expect(delete).to_have_attribute("aria-expanded", "false")
    page.wait_for_timeout(300)
    assert mock.deletions() == 0
    expect_account_state(page, "signed_in")


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac4_confirm_sends_one_delete_then_the_card_says_so_with_a_way_home(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, mock = signed_in_page(window, account_server, size)
    ask_deletion(page)

    page.get_by_test_id("account-delete-confirm").click()

    expect_account_state(page, "deleted")
    card = account_card(page)
    line = card.get_by_test_id("account-state-line")
    home = card.get_by_test_id("account-home")
    expect(line).to_have_count(1)
    expect(home).to_have_count(1)
    problems = text_problems(line, "account-state-line", fr_value("account.deleted"))
    problems.extend(role_problems(line, "account-state-line", "status"))
    problems.extend(done_line_problems(line, "account-state-line"))
    problems.extend(text_problems(home, "account-home", fr_value("share.home")))
    problems.extend(primary_link_problems(home, "account-home"))
    heading_box = box_of(card.locator("h1"))
    if box_of(line).top < heading_box.bottom - 1.0:
        problems.append("account-state-line is not under the h1")
    if box_of(home).top < box_of(line).bottom - 1.0:
        problems.append("account-home is not under account-state-line")
    selectors = ["h1", '[data-testid="account-state-line"]']
    selectors.append('[data-testid="account-home"]')
    problems.extend(others_in(card, selectors))

    assert problems == []
    assert mock.deletions() == 1


def test_ac4_signing_out_while_deletion_is_asked_leaves_no_panel(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page, mock = signed_in_page(window, account_server, (360, 740))
    ask_deletion(page)
    sign_out = page.get_by_test_id("account-sign-out")
    expect(sign_out).to_be_enabled()

    sign_out.click()

    expect_account_state(page, "signed_out")
    expect(page.get_by_test_id("account-delete-panel")).to_have_count(0)
    assert mock.deletions() == 0
