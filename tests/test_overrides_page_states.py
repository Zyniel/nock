"""Tests of admin/overrides, AC-19: the card's states.

The in-memory line is read on the real app (`settings_server`), with a database
file or without. The card's waiting, failed and refused states need an answer the
real app does not give, so `GET /api/ops/settings` alone is answered by
`page.route("**/api/ops/settings", ...)`; the dashboard stays the real one.

Readings taken where the spec leaves room:

- "The card holds « Chargement… » only" is the heading and that one line; the
  line is announced politely (`role="status"`), as `_design/pages.md`, « States »
  says of a waiting line in a card. The failure line is an alert.
- The 401 and 429 of rule 11 lock the page as `admin/operations.md` rule 16 says:
  the token form comes back with « Jeton refusé. » or « Trop d'essais. Réessayez
  dans une minute. », and the tab's `sessionStorage` forgets the token.
- Rule 12's 401 or 429 on a save, which no criterion names, is checked here
  beside the card's own lock: the `PUT` alone is answered by `page.route`
  (`answer_saves`), on the interval's row, which sends the `PUT` at once.

The shared setup is in `overrides_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, expect

from nock.catalogue import Catalogue
from overrides_harness import (
    HEADING,
    IN_MEMORY,
    INTERVAL,
    LOAD_ERROR,
    LOADING,
    SETTING_NAMES,
    SETTINGS_ROUTE,
    THROTTLED,
    TOKEN_REFUSED,
    RequestLog,
    answer_saves,
    box_below,
    card_of,
    expect_node_text,
    input_box,
    open_card,
    settings_server,
    type_and_save,
)
from spec038_harness import OPS_TOKEN_KEY, session_value
from spec042_harness import box_of
from spec046_harness import HeldRoute, OpenWindow, answer_json, window_opener
from spec048_ops_harness import expect_ops_state, open_ops, seed_ops_token


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


# ---- AC-19: without a database file ----


def test_ac19_without_a_database_the_card_holds_the_in_memory_line_under_its_title(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue, database=False) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        line = card_of(page).get_by_text(IN_MEMORY, exact=True)
        expect(line).to_have_count(1)
        heading = box_of(page.get_by_role("heading", name=HEADING, exact=True))
        under_the_title = box_below(box_of(line), heading)
        above_the_rows = box_below(input_box(page, SETTING_NAMES[0]), box_of(line))

    assert under_the_title
    assert above_the_rows


def test_ac19_on_a_database_file_the_card_has_no_such_line(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)

        expect(page.get_by_text(IN_MEMORY)).to_have_count(0)


# ---- AC-19: waiting and failing ----


def test_ac19_while_the_settings_load_the_card_holds_only_the_waiting_line(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        HeldRoute(page, SETTINGS_ROUTE)
        seed_ops_token(page)
        open_ops(page, server.base_url)
        expect_ops_state(page, "ready")

        card = card_of(page)
        expect_node_text(card, f"{HEADING} {LOADING}")
        status = card.get_by_role("status")
        expect(status).to_have_count(1)
        expect(status).to_have_text(LOADING)


def test_ac19_a_500_gives_the_failure_line_as_an_alert(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        answer_json(page, SETTINGS_ROUTE, 500, {"detail": "Internal Server Error"})
        seed_ops_token(page)
        open_ops(page, server.base_url)
        expect_ops_state(page, "ready")

        card = card_of(page)
        alert = card.get_by_role("alert")
        expect(alert).to_have_count(1)
        expect(alert).to_have_text(LOAD_ERROR)
        expect_node_text(card, f"{HEADING} {LOAD_ERROR}")


@pytest.mark.parametrize(
    ("status", "shown"), [(401, TOKEN_REFUSED), (429, THROTTLED)], ids=["401", "429"]
)
def test_ac19_a_401_or_429_of_the_settings_locks_the_page(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    status: int,
    shown: str,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        answer_json(page, SETTINGS_ROUTE, status, {"detail": "refused"})
        seed_ops_token(page)
        open_ops(page, server.base_url)

        error = page.get_by_test_id("ops-token-error")
        expect(error).to_have_text(shown)
        expect_ops_state(page, "locked")
        kept = session_value(page, OPS_TOKEN_KEY)

    assert kept is None


@pytest.mark.parametrize(
    ("status", "shown"), [(401, TOKEN_REFUSED), (429, THROTTLED)], ids=["401", "429"]
)
def test_ac19_a_401_or_429_of_a_save_locks_the_page(
    window: OpenWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalogue: Catalogue,
    status: int,
    shown: str,
) -> None:
    with settings_server(monkeypatch, tmp_path, catalogue) as server:
        page = window(1280, 720)
        open_card(page, server.base_url)
        answer_saves(page, status, {"detail": "refused"})
        sent = RequestLog(page)

        type_and_save(page, INTERVAL, "30")

        error = page.get_by_test_id("ops-token-error")
        expect(error).to_have_text(shown)
        expect_ops_state(page, "locked")
        kept = session_value(page, OPS_TOKEN_KEY)

    assert kept is None
    assert sent.saves() == [{"name": INTERVAL, "value": 30}]
