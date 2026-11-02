"""Tests of `admin/ops-page.md` AC-11 to AC-16: the operator page `/ops` ignores an
answer that a later request superseded, refuses a token of another shape in the page,
empties and focuses the token input whenever it locks, and shows a replay with a
malformed edit as an error (rules 3, 5, 6).

AC-11: on the dashboard `ready` on 7 days, the 1 day then the 30 days pressed, the
30-day answer coming first and the 1-day one after: the page shows the 30-day
figures with 30 pressed, and still does once the 1-day answer has come.

AC-12: the replay of `AAAAAA` asked, then that of a room whose answer comes first,
then `AAAAAA`'s 404: the card shows the room's replay, not « Salon introuvable. ».

AC-13: on the form, a token of 40 characters holding `é`, one holding a space, or one
of 31 allowed characters, submitted: no request is sent, `sessionStorage` holds no
token, and the form shows « Jeton refusé. » with the input empty and focused.
Rule 4 of `admin/operations.md` has its boundaries checked on the other side: a token
of 32 and one of 256 allowed characters are sent, as the `Authorization` header says.

AC-14: with `sessionStorage` holding a 40-character token with `é`, `/ops` sends no
request and opens `locked` with no error line, the token removed.

AC-15: `ready` with the token, a replay answered 401 brings the form back with
« Jeton refusé. », its input empty and focused. Rule 3 says every lock does it, so a
429 (with `ops.throttled`) and a refused period press are checked the same way.

AC-16: a replay answered 200 whose second edit has the time `hier`, or the `seq` 1.5,
puts the replay card in `error`: its one state line reads « Impossible de charger les
données. », with no edit list, grid or slider (`ops-replay-body`), and the page
stays `ready` with its six figures above.

Setup: the live ops server of spec 038's "Test harness" (`ops_live_server`, the
operator token `OPS_TOKEN`), a browser window of 1280 by 720. The dashboard and the
replay are answered by the test through `page.route`, so that the order of the
answers is the test's; the shared parts are in `operations_harness`.

Readings where the spec leaves room:

- "No request is sent" is: no request to `/api/ops/` from the page's load to 300 ms
  after the form shows its answer.
- "Still does once the 1-day answer has come": the test waits for the 1-day response
  to finish, then for two drawn frames, and reads the page.
- The replay of the second room is FX-01's `REPLAY` of spec 048's harness (7 edits).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from operations_harness import (
    HeldDashboard,
    HeldReplays,
    OpsRequests,
    expect_refused_form,
    json_answer,
    let_the_page_draw,
    seed_stored_token,
)
from spec038_harness import (
    DASHBOARD_PATH,
    DASHBOARD_ROUTE,
    NOT_AUTHORIZED,
    OPS_TOKEN_KEY,
    SEVEN_DAY_TEXTS,
    TOO_MANY_REQUESTS,
    DashboardRoute,
    OpsServer,
    dashboard_answer,
    expect_ops_state,
    give_token,
    load_fr,
    mocked_dashboard,
    open_dashboard,
    open_ops_page,
    ops_live_server,
    period_button,
    pressed_periods,
    seven_day_figures,
    texts_of,
)
from spec046_harness import OpenWindow, window_opener
from spec048_harness import NOT_FOUND
from spec048_ops_harness import (
    NOW,
    REPLAY_COUNT,
    REPLAY_ROUTE,
    expect_replay_state,
    open_ready_ops,
    replay,
    submit_replay,
)

SETTLE_MS = 300  # "no request": nothing within this pause
ONE_DAY_ROOMS = 2
THIRTY_DAY_ROOMS = 9
FIRST_CODE = "AAAAAA"
ROOM_CODE = "K7QM2X"
TOKEN_OF_40_WITH_E_ACUTE = "Ops-\N{LATIN SMALL LETTER E WITH ACUTE}" + "x" * 35
TOKEN_OF_40_WITH_SPACE = "Ops " + "x" * 36
TOKEN_OF_31 = "Ops-" + "x" * 27
ALLOWED_MIX = "Ab_-0"  # every kind of allowed character, repeated to length
TOKEN_OF_32 = (ALLOWED_MIX * 7)[:32]
TOKEN_OF_256 = (ALLOWED_MIX * 52)[:256]


# ---- Fixtures  -----------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def window(browser: Browser, browser_name: str) -> Iterator[OpenWindow]:
    yield from window_opener(browser, browser_name)


@pytest.fixture
def server(tmp_path: Path, catalogue: Catalogue) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue) as running:
        yield running


# ---- Helpers  ------------------------------------------------------------------------


def figures_of(days: int, rooms: int) -> tuple[int, str]:
    """A 200 dashboard answer for a period, whose first tile reads `rooms` rooms."""
    figures = seven_day_figures(NOW).model_copy(
        update={"days": days, "rooms_created": rooms}
    )
    return dashboard_answer(figures)


def expect_thirty_days_shown(page: Page) -> None:
    """The 30-day figures are on the page, with the period 30 pressed."""
    expect(page.get_by_test_id("ops-metric").first).to_have_text(
        f"Salons créés : {THIRTY_DAY_ROOMS}"
    )
    assert pressed_periods(page) == ["false", "false", "true"]


# ---- AC-11: a dashboard answer that a later request superseded  ----------------------


def test_ac11_the_1_day_answer_after_the_30_day_one_changes_nothing(
    window: OpenWindow, server: OpsServer
) -> None:
    page = window(1280, 720)
    dashboard = HeldDashboard(figures_of(7, 3))
    page.route(DASHBOARD_ROUTE, dashboard.handle)
    open_dashboard(page, server.base_url)
    assert texts_of(page.get_by_test_id("ops-metric")) == SEVEN_DAY_TEXTS
    period_button(page, "1").click()
    period_button(page, "30").click()
    dashboard.wait_for(page, [1, 30])

    dashboard.answer(30, figures_of(30, THIRTY_DAY_ROOMS))
    expect_thirty_days_shown(page)
    with page.expect_response(
        lambda response: DASHBOARD_PATH in response.url and "days=1" in response.url
    ) as late:
        dashboard.answer(1, figures_of(1, ONE_DAY_ROOMS))
    late.value.finished()
    let_the_page_draw(page)

    expect_ops_state(page, "ready")
    expect_thirty_days_shown(page)


# ---- AC-12: a replay answer that a later code superseded  ----------------------------


def test_ac12_the_404_of_the_first_code_after_the_second_replay_changes_nothing(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid
) -> None:
    page = window(1280, 720)
    replays = HeldReplays(
        (200, replay(fx01_grid).model_dump(mode="json")), held_codes=[FIRST_CODE]
    )
    page.route(REPLAY_ROUTE, replays.handle)
    open_ready_ops(page, server.base_url)
    submit_replay(page, FIRST_CODE)
    replays.wait_for(page, FIRST_CODE)
    submit_replay(page, ROOM_CODE)
    expect_replay_state(page, "ready")
    expect(page.get_by_test_id("ops-edit")).to_have_count(REPLAY_COUNT)

    with page.expect_response(lambda response: FIRST_CODE in response.url) as late:
        replays.release(FIRST_CODE, 404, NOT_FOUND)
    late.value.finished()
    let_the_page_draw(page)

    expect_replay_state(page, "ready")
    expect(page.get_by_test_id("ops-edit")).to_have_count(REPLAY_COUNT)
    expect(page.get_by_test_id("ops-replay")).not_to_contain_text(
        load_fr()["ops.replay_not_found"]
    )


# ---- AC-13: a token of another shape given on the form  ------------------------------


@pytest.mark.parametrize(
    "token",
    [
        pytest.param(TOKEN_OF_40_WITH_E_ACUTE, id="40-with-e-acute"),
        pytest.param(TOKEN_OF_40_WITH_SPACE, id="40-with-space"),
        pytest.param(TOKEN_OF_31, id="31-allowed"),
    ],
)
def test_ac13_a_token_of_another_shape_is_refused_with_no_request(
    window: OpenWindow, server: OpsServer, token: str
) -> None:
    page = window(1280, 720)
    sent = OpsRequests(page)
    open_ops_page(page, server.base_url)

    give_token(page, token)

    expect_refused_form(page)
    page.wait_for_timeout(SETTLE_MS)
    assert sent.urls() == []
    assert page.evaluate("key => sessionStorage.getItem(key)", OPS_TOKEN_KEY) is None


@pytest.mark.parametrize(
    "token",
    [pytest.param(TOKEN_OF_32, id="32"), pytest.param(TOKEN_OF_256, id="256")],
)
def test_ac13_a_token_of_the_shape_is_sent_in_the_header(
    window: OpenWindow, server: OpsServer, token: str
) -> None:
    page = window(1280, 720)
    sent = OpsRequests(page)
    open_ops_page(page, server.base_url)

    give_token(page, token)

    # The server refuses it (it is not the operator's), after the page sent it.
    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-error")).to_have_text(
        load_fr()["ops.token_refused"]
    )
    assert sent.authorizations() == [f"Bearer {token}"]


# ---- AC-14: a stored token of another shape  -----------------------------------------


def test_ac14_a_stored_token_of_another_shape_is_removed_and_nothing_is_sent(
    window: OpenWindow, server: OpsServer
) -> None:
    page = window(1280, 720)
    sent = OpsRequests(page)
    seed_stored_token(page, TOKEN_OF_40_WITH_E_ACUTE)

    open_ops_page(page, server.base_url)

    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-form")).to_be_visible()
    page.wait_for_timeout(SETTLE_MS)
    assert sent.urls() == []
    expect(page.get_by_test_id("ops-token-error")).to_have_count(0)
    assert page.evaluate("key => sessionStorage.getItem(key)", OPS_TOKEN_KEY) is None


# ---- AC-15: every lock empties and focuses the input  --------------------------------


@pytest.mark.parametrize(
    ("status", "body", "text_key"),
    [
        pytest.param(401, NOT_AUTHORIZED, "ops.token_refused", id="401"),
        pytest.param(429, TOO_MANY_REQUESTS, "ops.throttled", id="429"),
    ],
)
def test_ac15_a_refused_replay_brings_the_form_back_with_the_input_empty_and_focused(
    window: OpenWindow,
    server: OpsServer,
    status: int,
    body: dict[str, str],
    text_key: str,
) -> None:
    page = window(1280, 720)

    def refuse(route: Route) -> None:
        json_answer(route, status, body)

    page.route(REPLAY_ROUTE, refuse)
    open_dashboard(page, server.base_url)
    submit_replay(page, ROOM_CODE)

    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-error")).to_have_text(load_fr()[text_key])
    token_input = page.get_by_test_id("ops-token-input")
    expect(token_input).to_have_value("")
    expect(token_input).to_be_focused()


def test_ac15_a_refused_period_press_brings_the_form_back_with_the_input_empty(
    window: OpenWindow, server: OpsServer
) -> None:
    page = window(1280, 720)
    refused = (401, json.dumps(NOT_AUTHORIZED))
    route = DashboardRoute([figures_of(7, 3), refused])
    mocked_dashboard(page, server.base_url, route)

    period_button(page, "30").click()

    expect_refused_form(page)


# ---- AC-16: a replay whose edit is malformed is an error  ----------------------------


def replay_with_second_edit(grid: Grid, field: str, value: object) -> object:
    """FX-01's `REPLAY` as JSON, one field of its second edit replaced by `value`."""
    body = replay(grid).model_dump(mode="json")
    body["edits"][1][field] = value
    return body


@pytest.mark.parametrize(
    ("field", "value"),
    [
        pytest.param("at", "hier", id="time-hier"),
        pytest.param("seq", 1.5, id="seq-1.5"),
    ],
)
def test_ac16_a_replay_with_a_malformed_edit_shows_only_the_error_line(
    window: OpenWindow, server: OpsServer, fx01_grid: Grid, field: str, value: object
) -> None:
    page = window(1280, 720)
    answer = (200, replay_with_second_edit(fx01_grid, field, value))
    replays = HeldReplays(answer, held_codes=[])
    page.route(REPLAY_ROUTE, replays.handle)
    open_ready_ops(page, server.base_url)

    submit_replay(page, ROOM_CODE)

    expect_replay_state(page, "error")
    expect(page.get_by_test_id("ops-replay-state-line")).to_have_text(
        load_fr()["ops.error"]
    )
    expect(page.get_by_test_id("ops-replay-body")).to_have_count(0)
    expect(page.get_by_test_id("ops-edit")).to_have_count(0)
    expect_ops_state(page, "ready")
    expect(page.get_by_test_id("ops-metric")).to_have_count(6)
