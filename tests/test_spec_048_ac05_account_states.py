"""Tests of spec 048, AC-5: each other state of the account page is one line in
its card, and the e-mail form shows its answers in place.

The server is spec 033's live server with accounts on (`account_live_server`);
every account route is answered by `page.route` (`AccountMock` of
`spec048_harness`), or held unanswered where the criterion says so. Windows:
desktop contexts at 360 by 740 and 1280 by 720.

Readings of the spec's wording:

- "The card holds its `h1` and nothing else" (or "after its `h1`, only X"):
  everything the card shows is the `h1`, X, inside them, or a wrapper of them.
- "Lies above `account-email-form`": the line's bottom is not under the form's
  top (1 px). "Between the input and `account-email-submit`": the error line's
  top is not above the input's bottom and its bottom not under the button's top
  (1 px). "Under `account-email-submit`": `account-sent`'s top is not above the
  button's bottom (1 px).
- "The label lies 6 px above the input": from the label's bottom to the input's
  top, 6 px (1 px). The label is the element of the card that reads
  `fr.json["account.email_label"]`.
- "A border colour rgb(180, 35, 24)": the four sides have that colour.
- "A new submit clears both": after the new answer, `account-error` is gone, the
  border is `--nock-rule` again and `aria-invalid` is no longer `"true"`.
- A 429 leaves the address unblamed: the border stays `--nock-rule` and
  `aria-invalid` is not `"true"`.
- `aria-describedby` (added by the lead after review round 1): after a 422 and
  after a 429, `account-error`'s `id` is one of the input's whitespace-separated
  ids; after the 202 that follows a 422, every id there names an element of the
  page and none is the `id` `account-error` had.
- Each field is filled, then its value is checked, then the form is submitted
  with `account-email-submit`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from spec033_harness import AccountServer, account_live_server
from spec042_harness import box_of
from spec043_harness import INK, RED, RULE, fr_format, fr_value
from spec046_harness import (
    OpenWindow,
    button_colour_problems,
    font_problems,
    same_position,
    window_opener,
)
from spec048_harness import (
    SIGNED_OUT,
    SIZE_IDS,
    SIZES,
    AccountMock,
    account_card,
    border_colour_problems,
    described_by,
    described_by_problems,
    done_line_problems,
    error_line_problems,
    expect_account_state,
    field_label_problems,
    open_account,
    others_in,
    role_problems,
    submit_address,
    text_input_problems,
    text_problems,
    waiting_line_problems,
)

SHORT_ADDRESS = "ana@"
SENT_TEXT = "Lien envoyé à ana@. Il est valable 30 minutes."
SERVER_ERROR = {"detail": "Internal Server Error"}
STATE_LINE = '[data-testid="account-state-line"]'


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def account_server(tmp_path: Path, catalogue: Catalogue) -> Iterator[AccountServer]:
    with account_live_server(tmp_path, catalogue) as server:
        yield server


def open_in_state(
    window: OpenWindow,
    server: AccountServer,
    size: tuple[int, int],
    mock: AccountMock,
    state: str,
    link: bool = False,
) -> Page:
    page = window(*size)
    open_account(page, server.base_url, mock, state, link=link)
    return page


def state_line(page: Page) -> Locator:
    line = account_card(page).get_by_test_id("account-state-line")
    expect(line).to_have_count(1)
    return line


def email_label(page: Page) -> Locator:
    label = account_card(page).get_by_text(fr_value("account.email_label"), exact=True)
    expect(label).to_have_count(1)
    return label


def signed_out_page(
    window: OpenWindow,
    server: AccountServer,
    size: tuple[int, int],
    link_statuses: tuple[int, ...] = (202,),
) -> tuple[Page, AccountMock]:
    mock = AccountMock(status=(200, SIGNED_OUT), link_statuses=link_statuses)
    page = open_in_state(window, server, size, mock, "signed_out")
    return page, mock


def between_problems(page: Page, test_id: str) -> list[str]:
    """`test_id` lies between `account-email-input` and `account-email-submit`."""
    line = box_of(page.get_by_test_id(test_id))
    field = box_of(page.get_by_test_id("account-email-input"))
    submit = box_of(page.get_by_test_id("account-email-submit"))
    problems: list[str] = []
    if line.top < field.bottom - 1.0:
        problems.append(f"{test_id} starts above the input's bottom")
    if line.bottom > submit.top + 1.0:
        problems.append(f"{test_id} ends under the submit button's top")
    return problems


# ---- loading and signing in ---------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_while_the_first_request_runs_the_card_holds_its_title_only(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    mock = AccountMock(status=None)
    page = open_in_state(window, account_server, size, mock, "loading")
    card = account_card(page)
    expect(card.locator("h1")).to_have_text(fr_value("account.page_heading"))

    assert others_in(card, ["h1"]) == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_while_signing_in_the_card_holds_one_muted_status_line(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    mock = AccountMock(sign_in=None)
    page = open_in_state(window, account_server, size, mock, "signing_in", link=True)
    line = state_line(page)

    problems = text_problems(line, "state line", fr_value("account.signing_in"))
    problems.extend(role_problems(line, "state line", "status"))
    problems.extend(waiting_line_problems(line, "state line"))
    problems.extend(others_in(account_card(page), ["h1", STATE_LINE]))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_an_invalid_link_is_an_error_line_above_the_form(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    mock = AccountMock(sign_in=404)
    page = open_in_state(window, account_server, size, mock, "link_invalid", link=True)
    line = state_line(page)
    form = account_card(page).get_by_test_id("account-email-form")
    expect(form).to_be_visible()

    problems = text_problems(line, "state line", fr_value("account.link_invalid"))
    problems.extend(role_problems(line, "state line", "alert"))
    problems.extend(error_line_problems(line, "state line"))
    if box_of(line).bottom > box_of(form).top + 1.0:
        problems.append("the line is not above account-email-form")

    assert problems == []


# ---- signed out: the intro and the e-mail form --------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_signed_out_the_card_holds_the_intro_then_the_form(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size)
    card = account_card(page)
    intro = card.get_by_text(fr_value("account.signed_out_intro"), exact=True)
    expect(intro).to_have_count(1)
    form = card.get_by_test_id("account-email-form")
    expect(form).to_have_count(1)

    problems = font_problems(intro, "intro", 15.2, colour=INK)
    if box_of(intro).bottom > box_of(form).top + 1.0:
        problems.append("the intro is not above the form")
    if box_of(intro).top < box_of(card.locator("h1")).bottom - 1.0:
        problems.append("the intro is not under the h1")

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_the_field_has_its_label_6_px_above_a_full_width_input(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size)
    label = email_label(page)
    field = page.get_by_test_id("account-email-input")

    problems = field_label_problems(label, "label")
    gap = box_of(field).top - box_of(label).bottom
    if not same_position(gap, 6.0):
        problems.append(f"the label is {gap} px above the input")
    problems.extend(text_input_problems(field, account_card(page), "input"))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_the_submit_button_is_primary_12_px_under_the_input(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size)
    field = box_of(page.get_by_test_id("account-email-input"))
    submit = page.get_by_test_id("account-email-submit")

    problems = button_colour_problems(submit, "primary")
    gap = box_of(submit).top - field.bottom
    if not same_position(gap, 12.0):
        problems.append(f"account-email-submit is {gap} px under the input")

    assert problems == []


# ---- the answers to a link request ---------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_a_refused_address_turns_the_input_red_with_an_error_line_under_it(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size, (422,))
    field = page.get_by_test_id("account-email-input")

    submit_address(page, SHORT_ADDRESS)

    error = page.get_by_test_id("account-error")
    expect(error).to_have_text(fr_value("account.error.email"))
    expect(field).to_have_attribute("aria-invalid", "true")
    problems = border_colour_problems(field, "input", RED)
    problems.extend(role_problems(error, "account-error", "alert"))
    problems.extend(error_line_problems(error, "account-error"))
    problems.extend(between_problems(page, "account-error"))

    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_a_new_submit_answered_202_clears_the_error_and_confirms_under_the_button(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size, (422, 202))
    field = page.get_by_test_id("account-email-input")
    submit_address(page, SHORT_ADDRESS)
    expect(page.get_by_test_id("account-error")).to_be_visible()

    submit_address(page, SHORT_ADDRESS)

    sent = page.get_by_test_id("account-sent")
    expected = fr_format("account.sent", email=SHORT_ADDRESS)
    expect(sent).to_have_text(expected)
    expect(page.get_by_test_id("account-error")).to_have_count(0)
    expect(field).not_to_have_attribute("aria-invalid", "true")
    problems = border_colour_problems(field, "input", RULE)
    problems.extend(done_line_problems(sent, "account-sent"))
    submit = box_of(page.get_by_test_id("account-email-submit"))
    if box_of(sent).top < submit.bottom - 1.0:
        problems.append("account-sent is not under account-email-submit")

    assert expected == SENT_TEXT
    assert problems == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_too_many_requests_shows_its_line_and_keeps_the_normal_border(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size, (429,))
    field = page.get_by_test_id("account-email-input")

    submit_address(page, SHORT_ADDRESS)

    error = page.get_by_test_id("account-error")
    expect(error).to_have_text(fr_value("account.error.too_many"))
    problems = border_colour_problems(field, "input", RULE)
    if field.get_attribute("aria-invalid") == "true":
        problems.append("the input is aria-invalid after a 429")
    problems.extend(error_line_problems(error, "account-error"))
    problems.extend(between_problems(page, "account-error"))

    assert problems == []


@pytest.mark.parametrize("status", [422, 429], ids=["422", "429"])
@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_the_error_line_describes_the_input(
    window: OpenWindow,
    account_server: AccountServer,
    size: tuple[int, int],
    status: int,
) -> None:
    page, _ = signed_out_page(window, account_server, size, (status,))
    field = page.get_by_test_id("account-email-input")

    submit_address(page, SHORT_ADDRESS)

    error = page.get_by_test_id("account-error")
    expect(error).to_be_visible()
    assert described_by_problems(field, error, "account-error") == []


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_after_the_202_the_input_is_described_by_no_gone_line(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    page, _ = signed_out_page(window, account_server, size, (422, 202))
    field = page.get_by_test_id("account-email-input")
    submit_address(page, SHORT_ADDRESS)
    error = page.get_by_test_id("account-error")
    expect(error).to_be_visible()
    error_id = error.get_attribute("id")

    submit_address(page, SHORT_ADDRESS)

    expect(page.get_by_test_id("account-sent")).to_be_visible()
    expect(error).to_have_count(0)
    problems: list[str] = []
    for found_id, exists in described_by(field):
        if not exists:
            problems.append(f"aria-describedby names {found_id!r}, which is absent")
        if error_id is not None and found_id == error_id:
            problems.append(f"aria-describedby still names account-error {found_id!r}")
    assert problems == []


def test_ac5_a_failed_send_shows_its_line_and_keeps_the_normal_border(
    window: OpenWindow, account_server: AccountServer
) -> None:
    page, _ = signed_out_page(window, account_server, (360, 740), (503,))
    field = page.get_by_test_id("account-email-input")

    submit_address(page, "ana.probe@example.org")

    expect(page.get_by_test_id("account-error")).to_have_text(
        fr_value("account.error.send")
    )
    assert border_colour_problems(field, "input", RULE) == []


# ---- a failed status request ---------------------------------------------------------


@pytest.mark.parametrize("size", SIZES, ids=SIZE_IDS)
def test_ac5_a_failed_status_request_is_one_error_line(
    window: OpenWindow, account_server: AccountServer, size: tuple[int, int]
) -> None:
    mock = AccountMock(status=(500, SERVER_ERROR))
    page = open_in_state(window, account_server, size, mock, "error")
    line = state_line(page)

    problems = text_problems(line, "state line", fr_value("account.error.generic"))
    problems.extend(role_problems(line, "state line", "alert"))
    problems.extend(error_line_problems(line, "state line"))
    problems.extend(others_in(account_card(page), ["h1", STATE_LINE]))

    assert problems == []
    expect_account_state(page, "error")
