"""Tests of spec 046, AC-15 to AC-17: the nickname card, its error, and the status
cards of a room that refuses entry.

Browser with mocked socket on `/r/ABC123` (spec 043's `RoomMock`, which answers
each `ping`), at 1280 by 720 and 360 by 740. AC-15 and AC-16: nothing seeded
(spec 012's case c), so the page shows the nickname card under the room code
line. AC-17: `nock.identity.ABC123` seeded (case a), and the mock refuses the
join in five runs (`room_full`, `room_locked`, `removed`, a close with 4429, a
close with 4001 before any snapshot).

Choices where the spec leaves room:

- The field's label is the `label` element of `nickname-form`.
- "As wide as the card's content box": the card's box less its border and its
  padding; "its left on the card's content left" likewise.
- "No frame was sent" leaves spec 017's pings aside and waits 300 ms.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from spec035_harness import build_fx01_grid
from spec042_harness import box_of
from spec043_harness import INK, NAVY, RED, RULE, WHITE, fr_value, px
from spec046_harness import (
    REFUSALS,
    SIZES,
    STATUS_OF_REFUSAL,
    OpenWindow,
    border_problems,
    border_side_problems,
    button_colour_problems,
    card_problems,
    child_ids,
    code_line_problems,
    colour_problem,
    content_box,
    entry_frame_problems,
    entry_home_problems,
    error_line_problems,
    expect_status,
    font_problems,
    frames_after,
    fx01_snapshot,
    is_visually_hidden,
    open_nickname_card,
    open_status_card,
    padding_matches,
    same_font,
    same_position,
    show_nickname_error,
    size_ids,
    status_card_problems,
    style_of,
    wait_for_join,
    window_opener,
)
from sure_click import click_until_pressed

REFUSAL_CASES = [(size, refusal) for size in SIZES for refusal in REFUSALS]
REFUSAL_IDS = [f"{w}x{h}-{refusal}" for (w, h), refusal in REFUSAL_CASES]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return build_fx01_grid(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


def open_card(window: OpenWindow, base_url: str, size: tuple[int, int]) -> Page:
    page = window(*size)
    open_nickname_card(page, base_url)
    return page


# ---- AC-15: the nickname card ----------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_nickname_card_has_the_entry_frame_and_no_room_top_bar(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))

    assert entry_frame_problems(page) == []
    expect(page.get_by_test_id("room-topbar")).to_have_count(0)
    assert page.get_by_test_id("room-page").get_attribute("data-layout") is None


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_form_is_the_card_under_the_room_code_line(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    form = page.get_by_test_id("nickname-form")

    ids = child_ids(page.get_by_test_id("page-column"))

    assert ids[1:] == ["nickname-form"], ids
    assert code_line_problems(page, "ABC123") == []
    assert card_problems(form) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_cards_title_is_its_navy_700_heading(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    form = page.get_by_test_id("nickname-form")
    heading = form.locator(":scope > h2")

    first_tag = form.evaluate("form => form.firstElementChild?.tagName ?? null")
    line_height = style_of(heading, "lineHeight")

    assert first_tag == "H2"
    expect(heading).to_have_text(fr_value("join.heading"))
    assert font_problems(heading, "h2", 20.0, "700", NAVY) == []
    assert line_height.endswith("px"), line_height
    assert same_font(px(line_height), 24.0), line_height


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_label_is_above_the_input_6_px_apart(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    form = page.get_by_test_id("nickname-form")
    label = form.locator("label")

    expect(label).to_have_count(1)
    expect(label).to_have_text(fr_value("join.nickname_label"))
    gap = box_of(page.get_by_test_id("nickname-input")).top - box_of(label).bottom

    assert font_problems(label, "label", 13.6, "600", INK) == []
    assert same_position(gap, 6.0), gap


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_input_is_as_wide_as_the_cards_content_with_its_look(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    field = page.get_by_test_id("nickname-input")

    content = content_box(page.get_by_test_id("nickname-form"))
    box = box_of(field)

    assert same_position(box.left, content.left), (box, content)
    assert same_position(box.right, content.right), (box, content)
    assert border_problems(field, "nickname-input", RULE) == []
    assert style_of(field, "borderTopLeftRadius") == "6px"
    assert padding_matches(field, "10px 12px")
    assert font_problems(field, "nickname-input", 16.0) == []
    assert style_of(field, "textTransform") == "uppercase"
    assert colour_problem(field, "input", "backgroundColor", WHITE) == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_the_submit_is_a_primary_button_at_the_contents_left(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    submit = page.get_by_test_id("nickname-submit")

    content = content_box(page.get_by_test_id("nickname-form"))
    box = box_of(submit)

    expect(submit).to_have_text(fr_value("join.submit"))
    assert button_colour_problems(submit, "primary") == []
    assert same_position(box.left, content.left), (box, content)
    assert box.width < content.width, (box, content)


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac15_room_status_says_nickname_and_is_visually_hidden(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))
    room_status = page.get_by_test_id("room-status")

    expect(room_status).to_have_text(fr_value("room.status.nickname"))
    assert is_visually_hidden(room_status)


# ---- AC-16: the nickname error -------------------------------------------------


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac16_a_refused_nickname_turns_the_input_border_red_on_each_side(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))

    show_nickname_error(page)

    field = page.get_by_test_id("nickname-input")
    problems: list[str] = []
    for side in ("Top", "Right", "Bottom", "Left"):
        problems.extend(border_side_problems(field, "nickname-input", side, RED))
    assert problems == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac16_the_reason_is_an_error_line_between_the_input_and_the_button(
    window: OpenWindow, live_server: str, width: int, height: int
) -> None:
    page = open_card(window, live_server, (width, height))

    show_nickname_error(page)

    error = page.get_by_test_id("nickname-error")
    expect(error).to_have_text(fr_value("join.error.length"))
    expect(error).to_have_attribute("role", "alert")
    error_box = box_of(error)
    input_box = box_of(page.get_by_test_id("nickname-input"))
    submit_box = box_of(page.get_by_test_id("nickname-submit"))
    assert error_line_problems(error) == []
    assert error_box.top >= input_box.bottom - 1.0, (error_box, input_box)
    assert error_box.bottom <= submit_box.top + 1.0, (error_box, submit_box)


def test_ac16_a_refused_nickname_sends_no_frame(
    window: OpenWindow, live_server: str
) -> None:
    page = window(1280, 720)
    mock = open_nickname_card(page, live_server)

    sent = frames_after(page, mock, lambda: show_nickname_error(page))

    assert sent == []


@pytest.mark.parametrize(("width", "height"), SIZES, ids=size_ids(SIZES))
def test_ac16_while_joining_the_card_stays_with_a_disabled_button_until_the_room(
    window: OpenWindow, live_server: str, fx01_grid: Grid, width: int, height: int
) -> None:
    page = window(width, height)
    mock = open_nickname_card(page, live_server)
    show_nickname_error(page)
    field = page.get_by_test_id("nickname-input")
    field.fill("Ana")
    # Fix after #40's CI: the field holds the text before the submit (no race).
    expect(field).to_have_value("Ana")

    # 2026-10-23: Firefox under load lost the press; main's run after #40
    # failed here (no error, nothing happened), most likely the same lost press.
    click_until_pressed(page.get_by_test_id("nickname-submit"))

    expect_status(page, "joining")
    wait_for_join(page, mock)
    submit = page.get_by_test_id("nickname-submit")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(submit).to_be_disabled()
    assert button_colour_problems(submit, "disabled") == []
    mock.send(fx01_snapshot(fx01_grid))
    expect(page.get_by_test_id("room-topbar")).to_be_visible()
    expect(page.get_by_test_id("page-body")).to_have_count(0)
    expect(page.get_by_test_id("page-topbar")).to_have_count(0)


# ---- AC-17: the status cards -----------------------------------------------------


@pytest.mark.parametrize(("size", "refusal"), REFUSAL_CASES, ids=REFUSAL_IDS)
def test_ac17_a_refused_entry_shows_the_entry_frame_under_the_room_code(
    window: OpenWindow, live_server: str, size: tuple[int, int], refusal: str
) -> None:
    page = window(*size)
    open_status_card(page, live_server, refusal)

    ids = child_ids(page.get_by_test_id("page-column"))

    assert entry_frame_problems(page) == []
    assert code_line_problems(page, "ABC123") == []
    assert ids[1:] == ["entry-card"], ids
    expect(page.get_by_test_id("room-topbar")).to_have_count(0)


@pytest.mark.parametrize(("size", "refusal"), REFUSAL_CASES, ids=REFUSAL_IDS)
def test_ac17_the_status_is_the_cards_title_and_voir_les_grilles_its_way_back(
    window: OpenWindow, live_server: str, size: tuple[int, int], refusal: str
) -> None:
    page = window(*size)
    open_status_card(page, live_server, refusal)
    wait_for_fonts(page)
    home = page.get_by_test_id("entry-home")

    assert status_card_problems(page, STATUS_OF_REFUSAL[refusal]) == []
    expect(page.get_by_test_id("entry-detail")).to_have_count(0)
    assert entry_home_problems(page, "secondary") == []
    assert style_of(home, "borderTopLeftRadius") == "6px"
    assert padding_matches(home, "10px 16px")
