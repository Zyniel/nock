"""Tests of spec 038 (privacy and operations), AC-7: the ops page and its dashboard.

Live: the server of the spec's "Test harness" (a file database and
`operator_token=OPS_TOKEN`, `ops_live_server` of `spec038_harness`), so the page
talks to the real ops API. Mocked: the same server serves `/ops`, and
`page.route("**/api/ops/dashboard*", handler)` answers JSON built from
`DashboardFigures` (`DashboardRoute`), in a context with
`timezone_id="Europe/Paris"`. Keyboard: spec 035's `Walker` (`tab_to`) and its
outline rule (spec 035 AC-2). Scans: spec 035's contrast and language scans, and
spec 006 AC-5's window sizes.

The six texts of the criterion are written as it writes them; every other French
text comes from `fr.json`.

Edge cases checked as well, from "Client: the ops page" and "Edge cases and
errors": the labels and the password input with `autocomplete="off"`, a new tab
that asks for the token again, a 401 while the dashboard is shown, a 429, an
answer other than 200, 401 or 429 and a network failure (`error`), the `loading`
state, the `data-value` of each figure as received, and the rounding rules of the
duration, the percentage and the latency.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
from playwright.sync_api import (
    Browser,
    BrowserContext,
    Locator,
    Page,
    Request,
    Route,
    expect,
)

from nock.grid import Grid
from spec006_harness import WINDOW_SIZES as RESPONSIVE_WINDOW_SIZES
from spec010_harness import catalogue_from_grid
from spec035_harness import (
    LANGUAGE_SCAN_SCRIPT,
    MIN_FOCUS_CONTRAST,
    MIN_OUTLINE_PX,
    WINDOW_SIZES,
    Reached,
    Walker,
    contrast_offenders,
    unknown_texts,
)
from spec038_harness import (
    DASHBOARD_PATH,
    NOT_AUTHORIZED,
    OPS_PAGE_PATH,
    OPS_TOKEN,
    OPS_TOKEN_KEY,
    PARIS,
    TOO_MANY_REQUESTS,
    DashboardRoute,
    OpsServer,
    attributes_of,
    dashboard_answer,
    expect_ops_state,
    fill,
    give_token,
    load_fr,
    no_room_figures,
    open_dashboard,
    open_ops_page,
    ops_live_server,
    ops_page,
    seven_day_figures,
    texts_of,
    utc,
)

# ---- Values of the spec --------------------------------------------------------------

METRICS = [
    "rooms_created",
    "players_per_room",
    "completion_rate",
    "median_solving_time",
    "latency",
    "disconnection_rate",
]
PERIOD_DAYS = ["1", "7", "30"]

# The six texts of AC-5's 7-day result, and of the result with no room.
SEVEN_DAY_TEXTS = [
    "Salons créés : 3",
    "Joueurs par salon : 2,0",
    "Grilles terminées : 67 %",
    "Temps médian de résolution : 12 min 30 s",
    "Latence du serveur : 30 ms (médiane), 50 ms (95e centile)",
    "Coupures par joueur : 0,50",
]
NO_ROOM_TEXTS = [
    "Salons créés : 0",
    "Joueurs par salon : aucune donnée",
    "Grilles terminées : aucune donnée",
    "Temps médian de résolution : aucune donnée",
    "Latence du serveur : aucune donnée",
    "Coupures par joueur : aucune donnée",
]

# ---- Values of the test harness ------------------------------------------------------

NOW = 1_800_000_000.0
DASHBOARD_ROUTE = "**/api/ops/dashboard*"
WRONG_TOKEN = "wrong"
FORM_WATCHER = (
    "window.__opsFormSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"ops-token-form\"]')) {"
    " window.__opsFormSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)
LOCAL_VALUES_SCRIPT = """
() => {
  const values = [];
  for (let index = 0; index < localStorage.length; index += 1) {
    values.push(localStorage.getItem(localStorage.key(index)));
  }
  return values;
}
"""
NO_HORIZONTAL_SCROLL_SCRIPT = (
    "() => document.documentElement.scrollWidth <= window.innerWidth"
)

NewPage = Callable[[int, int], Page]


# ---- Fixtures ------------------------------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def server(tmp_path: Path, fx01_grid: Grid) -> Iterator[OpsServer]:
    with ops_live_server(tmp_path, catalogue_from_grid(fx01_grid)) as running:
        yield running


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    """Yield `new_page(width, height)`: a page in its own context, in Paris time."""
    contexts: list[BrowserContext] = []

    def make_page(width: int, height: int) -> Page:
        context = browser.new_context(
            viewport={"width": width, "height": height}, timezone_id=PARIS
        )
        contexts.append(context)
        return context.new_page()

    yield make_page
    for context in contexts:
        context.close()


# ---- Helpers -------------------------------------------------------------------------


def session_value(page: Page, key: str) -> str | None:
    value = page.evaluate("key => sessionStorage.getItem(key)", key)
    if value is None:
        return None
    assert isinstance(value, str), value
    return value


def pressed_periods(page: Page) -> list[str | None]:
    """The `aria-pressed` of the period buttons, in their order."""
    return attributes_of(page.get_by_test_id("ops-period"), "aria-pressed")


def period_button(page: Page, days: str) -> Locator:
    """The period button of `days` days."""
    return page.locator(f'[data-testid="ops-period"][data-days="{days}"]')


def mocked_dashboard(page: Page, base_url: str, route: DashboardRoute) -> None:
    """Answer the page's dashboard requests with `route`, then open the dashboard."""
    page.route(DASHBOARD_ROUTE, route.handle)
    open_dashboard(page, base_url)


def metric_values(page: Page, attribute: str) -> list[str | None]:
    return attributes_of(page.get_by_test_id("ops-metric"), attribute)


def outline_problems(reached: list[Reached]) -> list[str]:
    """The elements reached by `tab_to` whose outline breaks spec 035 AC-2."""
    problems: list[str] = []
    for element in reached:
        if element.outline_style in ("none", "auto"):
            problems.append(f"{element.test_id}: outline style {element.outline_style}")
        if element.outline_width < MIN_OUTLINE_PX:
            problems.append(f"{element.test_id}: outline {element.outline_width} px")
        if element.outline_contrast < MIN_FOCUS_CONTRAST:
            problems.append(f"{element.test_id}: contrast {element.outline_contrast}")
    return problems


# ---- AC-7: the live page -------------------------------------------------------------


def test_ac7_live_ops_shows_the_locked_page_with_the_token_form(
    page: Page, server: OpsServer
) -> None:
    open_ops_page(page, server.base_url)

    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-form")).to_be_visible()
    expect(page.get_by_test_id("ops-token-input")).to_be_visible()
    expect(page.get_by_role("heading", name=load_fr()["ops.heading"])).to_be_visible()


def test_ac7_live_the_token_input_is_a_password_input_labelled_from_fr_json(
    page: Page, server: OpsServer
) -> None:
    fr = load_fr()
    open_ops_page(page, server.base_url)
    token_input = page.get_by_test_id("ops-token-input")

    expect(token_input).to_have_attribute("type", "password")
    expect(token_input).to_have_attribute("autocomplete", "off")
    expect(page.get_by_label(fr["ops.token_label"], exact=True)).to_have_attribute(
        "data-testid", "ops-token-input"
    )
    expect(page.get_by_test_id("ops-token-submit")).to_have_text(fr["ops.token_submit"])


def test_ac7_live_a_wrong_token_shows_the_refusal(
    page: Page, server: OpsServer
) -> None:
    open_ops_page(page, server.base_url)

    give_token(page, WRONG_TOKEN)

    error = page.get_by_test_id("ops-token-error")
    expect(error).to_have_text(load_fr()["ops.token_refused"])
    expect(error).to_have_attribute("role", "alert")
    expect_ops_state(page, "locked")
    assert session_value(page, OPS_TOKEN_KEY) is None


def test_ac7_live_the_operator_token_loads_the_dashboard_with_its_six_figures(
    page: Page, server: OpsServer
) -> None:
    open_ops_page(page, server.base_url)
    give_token(page, WRONG_TOKEN)
    expect(page.get_by_test_id("ops-token-error")).to_be_visible()

    give_token(page, OPS_TOKEN)

    expect_ops_state(page, "ready")
    expect(page.get_by_test_id("ops-dashboard")).to_be_visible()
    expect(page.get_by_test_id("ops-metric")).to_have_count(len(METRICS))
    assert metric_values(page, "data-metric") == METRICS
    assert attributes_of(page.get_by_test_id("ops-period"), "data-days") == PERIOD_DAYS
    assert pressed_periods(page) == ["false", "true", "false"]


def test_ac7_live_every_ops_request_carries_the_bearer_token(
    page: Page, server: OpsServer
) -> None:
    ops_requests: list[Request] = []

    def keep(request: Request) -> None:
        if "/api/ops/" in request.url:
            ops_requests.append(request)

    page.on("request", keep)
    open_ops_page(page, server.base_url)
    give_token(page, WRONG_TOKEN)
    expect(page.get_by_test_id("ops-token-error")).to_be_visible()
    wrong_count = len(ops_requests)
    give_token(page, OPS_TOKEN)
    expect_ops_state(page, "ready")
    period_button(page, "30").click()
    expect(period_button(page, "30")).to_have_attribute("aria-pressed", "true")
    expect_ops_state(page, "ready")

    authorizations: list[str | None] = []
    for request in ops_requests:
        authorizations.append(request.header_value("authorization"))
    right_count = len(ops_requests) - wrong_count
    assert wrong_count >= 1
    assert right_count >= 2
    assert authorizations[:wrong_count] == [f"Bearer {WRONG_TOKEN}"] * wrong_count
    assert authorizations[wrong_count:] == [f"Bearer {OPS_TOKEN}"] * right_count


def test_ac7_live_the_token_is_kept_in_session_storage_only(
    page: Page, server: OpsServer
) -> None:
    open_dashboard(page, server.base_url)

    local_values = page.evaluate(LOCAL_VALUES_SCRIPT)
    cookie_values = [cookie.get("value", "") for cookie in page.context.cookies()]
    document_cookie = page.evaluate("() => document.cookie")

    assert session_value(page, OPS_TOKEN_KEY) == OPS_TOKEN
    assert [value for value in local_values if OPS_TOKEN in str(value)] == []
    assert [value for value in cookie_values if OPS_TOKEN in value] == []
    assert OPS_TOKEN not in document_cookie
    assert page.url == f"{server.base_url}{OPS_PAGE_PATH}"


def test_ac7_live_the_period_30_sends_days_30_and_is_pressed(
    page: Page, server: OpsServer
) -> None:
    open_dashboard(page, server.base_url)

    with page.expect_request(
        lambda request: DASHBOARD_PATH in request.url and "days=30" in request.url
    ) as caught:
        period_button(page, "30").click()

    query = parse_qs(urlparse(caught.value.url).query)
    assert query.get("days") == ["30"]
    expect(period_button(page, "30")).to_have_attribute("aria-pressed", "true")
    expect_ops_state(page, "ready")
    assert pressed_periods(page) == ["false", "false", "true"]


def test_ac7_live_a_reload_shows_the_dashboard_without_the_form(
    page: Page, server: OpsServer
) -> None:
    open_dashboard(page, server.base_url)
    page.add_init_script(FORM_WATCHER)

    page.reload()

    expect_ops_state(page, "ready")
    expect(page.get_by_test_id("ops-dashboard")).to_be_visible()
    assert page.evaluate("() => window.__opsFormSeen") is False


def test_ac7_live_a_new_tab_asks_for_the_token_again(
    page: Page, server: OpsServer
) -> None:
    open_dashboard(page, server.base_url)
    other_tab = page.context.new_page()

    open_ops_page(other_tab, server.base_url)

    expect_ops_state(other_tab, "locked")
    expect(other_tab.get_by_test_id("ops-token-form")).to_be_visible()
    assert session_value(other_tab, OPS_TOKEN_KEY) is None


# ---- AC-7: the dashboard with a mocked ops API ---------------------------------------


def test_ac7_mocked_the_six_texts_of_the_7_day_figures(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])

    mocked_dashboard(page, server.base_url, route)

    assert texts_of(page.get_by_test_id("ops-metric")) == SEVEN_DAY_TEXTS


def test_ac7_mocked_the_data_values_are_the_figures_as_received(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])

    mocked_dashboard(page, server.base_url, route)

    # The figures whose JSON text and JavaScript value read the same.
    values = metric_values(page, "data-value")
    assert values[0] == "3"
    assert values[2] == str(2 / 3)  # 0.6666666666666666, in JSON as in JavaScript
    assert values[5] == "0.5"
    assert metric_values(page, "data-p95")[4] == "50"


def test_ac7_mocked_the_six_texts_with_no_room(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(no_room_figures(NOW))])

    mocked_dashboard(page, server.base_url, route)

    assert texts_of(page.get_by_test_id("ops-metric")) == NO_ROOM_TEXTS


def test_ac7_mocked_with_no_room_every_data_value_but_rooms_created_is_empty(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(no_room_figures(NOW))])

    mocked_dashboard(page, server.base_url, route)

    assert metric_values(page, "data-value") == ["0", "", "", "", "", ""]
    assert metric_values(page, "data-p95")[4] == ""


def test_ac7_mocked_the_figures_follow_the_formats_of_the_client(
    new_page: NewPage, server: OpsServer
) -> None:
    from nock.operations import DashboardFigures

    figures = DashboardFigures(
        days=7,
        since=utc(NOW - 7 * 86_400),
        rooms_created=12,
        players_per_room=3.4,
        completion_rate=0.126,  # Math.round(12.6) is 13
        median_solving_ms=3_725_999.0,  # 3,725 whole seconds: 1 h 02 min 05 s
        latency_median_ms=30.6,  # rounded to 31
        latency_p95_ms=41,
        disconnection_rate=1 / 3,
    )
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(figures)])

    mocked_dashboard(page, server.base_url, route)

    fr = load_fr()
    duration = fill(
        fr["duration.hours"], {"hours": "1", "minutes": "02", "seconds": "05"}
    )
    latency = fill(fr["ops.latency_value"], {"median": "31", "p95": "41"})
    percent = fill(fr["ops.percent"], {"value": "13"})
    values = ["12", "3,4", percent, duration, latency, "0,33"]
    expected: list[str] = []
    for metric, value in zip(METRICS, values, strict=True):
        expected.append(fill(fr[f"ops.metric.{metric}"], {"value": value}))
    assert texts_of(page.get_by_test_id("ops-metric")) == expected


def test_ac7_mocked_a_duration_under_an_hour_has_seconds_on_two_digits(
    new_page: NewPage, server: OpsServer
) -> None:
    figures = seven_day_figures(NOW).model_copy(update={"median_solving_ms": 5_999.0})
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(figures)])

    mocked_dashboard(page, server.base_url, route)

    fr = load_fr()
    duration = fill(fr["duration.minutes"], {"minutes": "0", "seconds": "05"})
    expected = fill(fr["ops.metric.median_solving_time"], {"value": duration})
    assert texts_of(page.get_by_test_id("ops-metric"))[3] == expected


def test_ac7_mocked_the_dashboard_heading_and_period_buttons_come_from_fr_json(
    new_page: NewPage, server: OpsServer
) -> None:
    fr = load_fr()
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])

    mocked_dashboard(page, server.base_url, route)

    expect(
        page.get_by_role("heading", name=fr["ops.dashboard_heading"])
    ).to_be_visible()
    group = page.get_by_role("group", name=fr["ops.period_label"])
    expect(group.get_by_test_id("ops-period")).to_have_count(3)
    expected_texts = [
        fr["ops.period.one_day"],
        fr["ops.period.seven_days"],
        fr["ops.period.thirty_days"],
    ]
    assert texts_of(page.get_by_test_id("ops-period")) == expected_texts


def test_ac7_mocked_a_401_while_the_dashboard_is_shown_locks_the_page_again(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    refused = (401, json.dumps(NOT_AUTHORIZED))
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW)), refused])
    mocked_dashboard(page, server.base_url, route)

    period_button(page, "30").click()

    expect_ops_state(page, "locked")
    expect(page.get_by_test_id("ops-token-error")).to_have_text(
        load_fr()["ops.token_refused"]
    )
    assert session_value(page, OPS_TOKEN_KEY) is None


def test_ac7_mocked_a_429_shows_the_throttle_text(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([(429, json.dumps(TOO_MANY_REQUESTS))])
    page.route(DASHBOARD_ROUTE, route.handle)
    open_ops_page(page, server.base_url)

    give_token(page, OPS_TOKEN)

    error = page.get_by_test_id("ops-token-error")
    expect(error).to_have_text(load_fr()["ops.throttled"])
    expect(error).to_have_attribute("role", "alert")


@pytest.mark.parametrize("status", [500, 404, 403])
def test_ac7_mocked_another_answer_shows_the_error_state(
    new_page: NewPage, server: OpsServer, status: int
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([(status, json.dumps({"detail": "x"}))])
    page.route(DASHBOARD_ROUTE, route.handle)
    open_ops_page(page, server.base_url)

    give_token(page, OPS_TOKEN)

    expect_ops_state(page, "error")
    expect(ops_page(page)).to_contain_text(load_fr()["ops.error"])


def test_ac7_mocked_a_network_failure_shows_the_error_state(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([None])
    page.route(DASHBOARD_ROUTE, route.handle)
    open_ops_page(page, server.base_url)

    give_token(page, OPS_TOKEN)

    expect_ops_state(page, "error")
    expect(ops_page(page)).to_contain_text(load_fr()["ops.error"])


def test_ac7_mocked_the_page_is_loading_until_the_answer_comes(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    held: list[Route] = []
    page.route(DASHBOARD_ROUTE, held.append)
    open_ops_page(page, server.base_url)

    give_token(page, OPS_TOKEN)
    expect_ops_state(page, "loading")
    status, body = dashboard_answer(seven_day_figures(NOW))
    for route in held:
        route.fulfill(status=status, content_type="application/json", body=body)

    expect_ops_state(page, "ready")


# ---- AC-7: keyboard only -------------------------------------------------------------


def test_ac7_keyboard_tab_to_the_token_input_then_enter_loads_the_dashboard(
    page: Page, server: OpsServer
) -> None:
    open_ops_page(page, server.base_url)
    walker = Walker(page)

    walker.tab_to("ops-token-input")
    page.keyboard.type(OPS_TOKEN)
    page.keyboard.press("Enter")

    expect_ops_state(page, "ready")


def test_ac7_keyboard_each_period_button_shows_the_focus_outline(
    page: Page, server: OpsServer
) -> None:
    open_ops_page(page, server.base_url)
    walker = Walker(page)
    walker.tab_to("ops-token-input")
    page.keyboard.type(OPS_TOKEN)
    page.keyboard.press("Enter")
    expect_ops_state(page, "ready")

    for days in PERIOD_DAYS:
        walker.tab_to("ops-period", f'[data-days="{days}"]')

    assert [element.test_id for element in walker.reached[1:]] == ["ops-period"] * 3
    assert outline_problems(walker.reached[1:]) == []


def test_ac7_keyboard_the_token_input_shows_the_focus_outline(
    page: Page, server: OpsServer
) -> None:
    # "Accessibility (spec 035)": every control shows AC-2's visible focus.
    open_ops_page(page, server.base_url)
    walker = Walker(page)

    walker.tab_to("ops-token-input")

    assert outline_problems(walker.reached) == []


# ---- AC-7: contrast, language and window sizes ---------------------------------------


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES)
def test_ac7_the_contrast_scan_finds_no_offending_element_on_the_ready_page(
    new_page: NewPage, server: OpsServer, width: int, height: int
) -> None:
    page = new_page(width, height)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])
    mocked_dashboard(page, server.base_url, route)

    assert contrast_offenders(page) == []


@pytest.mark.parametrize(("width", "height"), WINDOW_SIZES)
def test_ac7_the_language_scan_finds_no_text_outside_fr_json_on_the_ready_page(
    new_page: NewPage, server: OpsServer, width: int, height: int
) -> None:
    page = new_page(width, height)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])
    mocked_dashboard(page, server.base_url, route)

    texts = page.evaluate(LANGUAGE_SCAN_SCRIPT)

    assert len(texts) > 0
    assert unknown_texts(texts, set()) == []


@pytest.mark.parametrize(("width", "height"), RESPONSIVE_WINDOW_SIZES)
def test_ac7_the_ready_page_has_no_horizontal_scroll(
    new_page: NewPage, server: OpsServer, width: int, height: int
) -> None:
    page = new_page(width, height)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW))])
    mocked_dashboard(page, server.base_url, route)

    assert page.evaluate(NO_HORIZONTAL_SCROLL_SCRIPT) is True
