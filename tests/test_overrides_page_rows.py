"""Tests of admin/overrides, AC-15, AC-16 and AC-18: the card's rows on `/ops`.

The page runs on the real app (`settings_server`): no mocked API, so the values
come from the server's variables, `PUT` and dashboard. The token is kept in the
tab's `sessionStorage` (`open_card`). The card has no test id in the spec; the
rows are found as `overrides_harness` says: by the number input named with the
row's name, and the row's text reads the name, the effective value, the source and
the two buttons.

Readings taken where the spec leaves room:

- AC-16's second half types 100 in a life whose effective value is 720. Rule 12
  says that a life below the row's effective value sends the dry run first and
  asks, so the test confirms the question (0 rooms, « Cela effacera 0 salon
  maintenant. ») before it reads the chips. The first half (96 over a variable of
  48) is not below, so it asks nothing.
- AC-16's first and second halves run on two servers: with `NOCK_CREATOR_ROOM_HOURS`
  at 48 the shortest life is 48 hours, so the 7-day chip could not come back.
- « Rétablir » sends `PUT` with `value` null (rule 4's reset); a reset to a longer
  life asks nothing.
- AC-18's "not a whole number" and "empty" cases of rule 12 are checked with 24.5
  and an empty input.
- The card sits between `ops-dashboard` and `ops-replay` (rule 11): its box starts
  under the dashboard's and ends above the replay's.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from lifetime_harness import ANONYMOUS, ANONYMOUS_SOLVED, CREATOR
from nock.catalogue import Catalogue
from overrides_harness import (
    CONFIRM,
    INTERVAL,
    ONE_DAY,
    RESET,
    SAVE,
    SETTING_BY_NAME,
    SETTING_NAMES,
    THREE_PERIODS,
    RequestLog,
    bounds_text,
    box_below,
    button_in,
    card_of,
    expect_row,
    input_box,
    input_of,
    open_card,
    period_texts,
    question_of,
    row_line,
    row_of,
    row_summary,
    row_text,
    settings_server,
    type_and_save,
)
from spec033_harness import wait_for
from spec042_harness import box_of
from spec046_harness import OpenWindow, window_opener


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- AC-15: the card and its five rows ----


def test_ac15_the_card_lists_the_five_settings_at_their_defaults(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        texts = [row_text(page, name) for name in SETTING_NAMES]
        tops = [input_box(page, name).top for name in SETTING_NAMES]

        for name in SETTING_NAMES:
            expect(input_of(page, name)).to_have_value("")
            expect(button_in(row_of(page, name), RESET)).to_be_disabled()
            expect(button_in(row_of(page, name), SAVE)).to_be_enabled()

    expected = []
    for name in SETTING_NAMES:
        expected.append(row_line(name, SETTING_BY_NAME[name].default, "default"))
    assert texts == expected
    assert tops == sorted(tops)
    assert len(set(tops)) == len(SETTING_NAMES)


def test_ac15_the_card_stands_between_the_dashboard_and_the_replay(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        dashboard = box_of(page.get_by_test_id("ops-dashboard"))
        card = box_of(card_of(page))
        replay = box_of(page.get_by_test_id("ops-replay"))

    assert box_below(card, dashboard)
    assert box_below(replay, card)


def test_ac15_a_variable_shows_its_value_and_the_variable_source(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    variables = {CREATOR.variable: "48"}
    with settings_server(monkeypatch, tmp_path, catalogue, variables) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        text = row_text(page, CREATOR.field)
        other = row_text(page, ANONYMOUS.field)
        reset = button_in(row_of(page, CREATOR.field), RESET)

        expect(reset).to_be_disabled()

    assert text == row_line(CREATOR.field, 48, "environment")
    assert other == row_line(ANONYMOUS.field, 720, "default")


# ---- AC-16: a save with no question ----


def test_ac16_a_save_not_below_the_effective_value_sends_the_put_with_no_question(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    variables = {CREATOR.variable: "48"}
    with settings_server(monkeypatch, tmp_path, catalogue, variables) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)
        sent = RequestLog(page)

        type_and_save(page, CREATOR.field, "96")

        expect_row(page, CREATOR.field, 96, "override")
        expect(input_of(page, CREATOR.field)).to_have_value("")
        expect(button_in(row_of(page, CREATOR.field), RESET)).to_be_enabled()
        expect(page.get_by_text("Cela effacera")).to_have_count(0)
        # The dashboard is asked again, with no period.
        wait_for(lambda: len(sent.dashboards()) == 1, "the dashboard asked again")

    assert sent.saves() == [{"name": CREATOR.field, "value": 96}]
    assert sent.dry_runs() == []
    assert sent.dashboards() == [""]


def test_ac16_a_shorter_life_shrinks_the_periods_and_its_reset_brings_them_back(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    name = ANONYMOUS_SOLVED.field
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)
        sent = RequestLog(page)
        assert period_texts(page) == THREE_PERIODS

        type_and_save(page, name, "100")
        expect(question_of(page, 0)).to_be_visible()
        card_of(page).get_by_role("button", name=CONFIRM, exact=True).click()

        expect_row(page, name, 100, "override")
        expect(page.get_by_test_id("ops-period")).to_have_count(1)
        shortened = period_texts(page)
        pressed = page.get_by_test_id("ops-period").get_attribute("aria-pressed")

        button_in(row_of(page, name), RESET).click()

        expect_row(page, name, 720, "default")
        expect(page.get_by_test_id("ops-period")).to_have_count(3)
        restored = period_texts(page)
        restored_pressed = page.locator(
            '[data-testid="ops-period"][aria-pressed="true"]'
        ).all_inner_texts()
        wait_for(lambda: len(sent.dashboards()) == 2, "the dashboard asked twice")

    assert shortened == [ONE_DAY]
    assert pressed == "true"
    assert restored == THREE_PERIODS
    assert restored_pressed == ["7 derniers jours"]
    assert sent.dry_runs() == [{"name": name, "value": 100}]
    assert sent.saves() == [{"name": name, "value": 100}, {"name": name, "value": None}]
    assert sent.dashboards() == ["", ""]


# ---- AC-18: bounds ----


@pytest.mark.parametrize(
    ("name", "text"),
    [
        pytest.param(CREATOR.field, "23", id="life-23"),
        pytest.param(CREATOR.field, "8761", id="life-8761"),
        pytest.param(CREATOR.field, "24.5", id="life-not-whole"),
        pytest.param(CREATOR.field, "", id="life-empty"),
        pytest.param(INTERVAL, "0", id="interval-0"),
        pytest.param(INTERVAL, "1441", id="interval-1441"),
    ],
)
def test_ac18_a_value_out_of_bounds_shows_the_error_line_and_sends_nothing(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    name: str,
    text: str,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)
        sent = RequestLog(page)

        type_and_save(page, name, text)

        alert = row_of(page, name).get_by_role("alert")
        expect(alert).to_have_text(bounds_text(name))
        expect(alert).to_have_count(1)
        under_the_input = box_below(box_of(alert), input_box(page, name))
        row_after = row_text(page, name)

    default = SETTING_BY_NAME[name].default
    assert under_the_input
    assert row_after.startswith(row_summary(name, default, "default"))
    assert sent.saves() == []
    assert sent.dry_runs() == []


def test_ac18_the_interval_saves_at_once_with_no_question(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)
        sent = RequestLog(page)

        type_and_save(page, INTERVAL, "30")

        expect_row(page, INTERVAL, 30, "override")
        expect(page.get_by_text("Cela effacera")).to_have_count(0)

    assert sent.saves() == [{"name": INTERVAL, "value": 30}]
    assert sent.dry_runs() == []
