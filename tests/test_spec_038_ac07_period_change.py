"""Tests of spec 038 (privacy and operations), AC-7: a period change keeps the page.

"Period change" of "Client: the ops page `/ops`": a press of an `ops-period`
button keeps `data-state="ready"`; the dashboard and the replay stay on screen,
the focus stays on the pressed button, and the six metrics change when the answer
arrives. A 401 or a 429 to that request still locks the page; any other answer,
or a network failure, sends it to `error`.

Live, as "Replay before a period change" of the spec's "Test harness" says: the
server of the "Test harness" (`ops_live_server` of `spec038_harness`), and a room
with edits that the test seeds in its store as AC-6 seeds its rooms (`new_room`,
`add_room`, then `store.append`), whose code the page submits in
`ops-replay-code`. The period is pressed from the keyboard, spec 035's `tab_to`
and then `Enter`, since WebKit on Windows and macOS does not focus a clicked
button (spec 014). Mocked: `page.route("**/api/ops/dashboard*", handler)`
answers the dashboard's requests with JSON built from `DashboardFigures`, and
holds the request of the period change while the test looks at the page.

Edge cases checked as well, from "Edge cases and errors": `data-state` stays
`ready` while the request of a period change is pending (a script records every
state the page takes), and `loading` never shows for it.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, BrowserContext, Page, Route, expect

from nock.grid import Grid
from nock.room import new_room
from spec010_harness import catalogue_from_grid
from spec035_harness import Walker
from spec038_harness import (
    DASHBOARD_PATH,
    DASHBOARD_ROUTE,
    NO_ROOM_TEXTS,
    OPS_TIMEOUT_MS,
    OPS_TOKEN,
    OPS_TOKEN_KEY,
    PARIS,
    SEVEN_DAY_TEXTS,
    TOO_MANY_REQUESTS,
    DashboardRoute,
    Log,
    OpsServer,
    answer_held_routes,
    attributes_of,
    dashboard_answer,
    expect_ops_state,
    load_fr,
    mocked_dashboard,
    no_room_figures,
    open_dashboard,
    ops_live_server,
    ops_page,
    period_button,
    pressed_periods,
    seed_room,
    session_value,
    seven_day_figures,
    texts_of,
    wait_for_held_route,
)

# ---- Values of the test harness ------------------------------------------------------

NOW = 1_800_000_000.0
REPLAY_ROOM = "PERIOD"
REPLAY_LETTERS = "TAM"  # typed by ANA from (1, 0) across: three edits

# Records each `data-state` the ops page takes from now on, starting with the
# current one, in `window.__opsStates`; a state is written again only once it
# changed.
STATE_WATCHER_SCRIPT = """
() => {
  const states = [];
  const record = () => {
    const root = document.querySelector('[data-testid="ops-page"]');
    const state = root === null ? null : root.getAttribute("data-state");
    if (states.length === 0 || states[states.length - 1] !== state) {
      states.push(state);
    }
  };
  record();
  new MutationObserver(record).observe(document.documentElement, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["data-state"],
  });
  window.__opsStates = states;
}
"""
STATES_SEEN_SCRIPT = "() => window.__opsStates"

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


def seed_replay_room(server: OpsServer, grid: Grid) -> None:
    """Write REPLAY_ROOM to the live server's store: ANA joined and typed TAM."""
    now = time.time()
    log = Log(now)
    log.join("p1", "ANA", 0, "token-of-ana-0001")
    for column, letter in enumerate(REPLAY_LETTERS):
        log.letter("p1", 1, column, letter)
    seed_room(server.registry, new_room(REPLAY_ROOM, grid, now), log.entries)


def show_replay(page: Page, code: str) -> None:
    """Submit `code` in `ops-replay-code` with `Enter`; wait until its edits show.

    From the keyboard, like the press of the period: in WebKit, `Shift+Tab` does
    not move the focus away from a button focused by a click, so `tab_to` could
    not go back from the submit button to the period buttons.
    """
    code_input = page.get_by_test_id("ops-replay-code")
    code_input.fill(code)
    code_input.press("Enter")
    expect(page.get_by_test_id("ops-replay")).to_have_attribute(
        "data-state", "ready", timeout=OPS_TIMEOUT_MS
    )
    expect(page.get_by_test_id("ops-edit")).to_have_count(len(REPLAY_LETTERS))


def dashboard_with_a_replay(page: Page, server: OpsServer, grid: Grid) -> None:
    """Open the live dashboard (period 7) and show the replay of REPLAY_ROOM."""
    seed_replay_room(server, grid)
    open_dashboard(page, server.base_url)
    show_replay(page, REPLAY_ROOM)
    assert pressed_periods(page) == ["false", "true", "false"]


def press_the_period_30_from_the_keyboard(page: Page) -> None:
    """`tab_to` the period 30, press `Enter`, and wait until it is pressed.

    Waits for the answer to its `days=30` request, then for its
    `aria-pressed="true"`.
    """
    walker = Walker(page)
    walker.tab_to("ops-period", '[data-days="30"]')
    with page.expect_response(
        lambda response: DASHBOARD_PATH in response.url and "days=30" in response.url,
        timeout=OPS_TIMEOUT_MS,
    ):
        page.keyboard.press("Enter")
    expect(period_button(page, "30")).to_have_attribute(
        "aria-pressed", "true", timeout=OPS_TIMEOUT_MS
    )


def hold_after_the_first_answer(page: Page, first: tuple[int, str]) -> list[Route]:
    """Answer the page's first dashboard request with `first`; hold the later ones.

    Returns the held requests, which the test answers when it is ready.
    """
    held: list[Route] = []
    answered: list[str] = []

    def handle(route: Route) -> None:
        if len(answered) > 0:
            held.append(route)
            return
        answered.append(route.request.url)
        status, body = first
        route.fulfill(status=status, content_type="application/json", body=body)

    page.route(DASHBOARD_ROUTE, handle)
    return held


def states_seen(page: Page) -> list[str | None]:
    """The states that STATE_WATCHER_SCRIPT recorded, in their order."""
    states = page.evaluate(STATES_SEEN_SCRIPT)
    assert isinstance(states, list), states
    seen: list[str | None] = []
    for state in states:
        seen.append(None if state is None else str(state))
    return seen


# ---- AC-7: a press of the period 30, with a replay shown (live) ---------------------


def test_ac7_live_a_keyboard_press_of_the_period_30_leaves_the_focus_on_it(
    page: Page, server: OpsServer, fx01_grid: Grid
) -> None:
    dashboard_with_a_replay(page, server, fx01_grid)

    press_the_period_30_from_the_keyboard(page)

    expect(period_button(page, "30")).to_be_focused()
    assert pressed_periods(page) == ["false", "false", "true"]
    expect_ops_state(page, "ready")


def test_ac7_live_a_press_of_the_period_30_keeps_the_replay_and_its_edits(
    page: Page, server: OpsServer, fx01_grid: Grid
) -> None:
    dashboard_with_a_replay(page, server, fx01_grid)
    edits = page.get_by_test_id("ops-edit")
    texts_before = texts_of(edits)
    seqs_before = attributes_of(edits, "data-seq")

    press_the_period_30_from_the_keyboard(page)

    expect(page.get_by_test_id("ops-replay")).to_have_attribute("data-state", "ready")
    expect(edits).to_have_count(len(REPLAY_LETTERS))
    assert texts_of(edits) == texts_before
    assert attributes_of(edits, "data-seq") == seqs_before


# ---- AC-7: a period change with a mocked ops API -------------------------------------


def test_ac7_mocked_the_page_stays_ready_while_a_period_change_is_pending(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    held = hold_after_the_first_answer(page, dashboard_answer(seven_day_figures(NOW)))
    open_dashboard(page, server.base_url)
    page.evaluate(STATE_WATCHER_SCRIPT)
    metrics = page.get_by_test_id("ops-metric")

    period_button(page, "30").click()
    wait_for_held_route(page, held)

    # Pending: the dashboard and the replay stay on screen, with the 7-day figures.
    expect(page.get_by_test_id("ops-dashboard")).to_be_visible()
    expect(page.get_by_test_id("ops-replay")).to_be_visible()
    assert texts_of(metrics) == SEVEN_DAY_TEXTS
    answer_held_routes(held, dashboard_answer(no_room_figures(NOW, 30)))
    # The answer changes the six metrics (0 rooms instead of 3).
    expect(metrics.first).to_have_attribute("data-value", "0", timeout=OPS_TIMEOUT_MS)
    assert texts_of(metrics) == NO_ROOM_TEXTS
    assert states_seen(page) == ["ready"]


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param((500, json.dumps({"detail": "x"})), id="500"),
        pytest.param(None, id="network-failure"),
    ],
)
def test_ac7_mocked_another_answer_to_a_period_change_shows_the_error_state(
    new_page: NewPage, server: OpsServer, answer: tuple[int, str] | None
) -> None:
    page = new_page(1280, 720)
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW)), answer])
    mocked_dashboard(page, server.base_url, route)

    period_button(page, "30").click()

    expect_ops_state(page, "error")
    expect(ops_page(page)).to_contain_text(load_fr()["ops.error"])


def test_ac7_mocked_a_429_to_a_period_change_locks_the_page(
    new_page: NewPage, server: OpsServer
) -> None:
    page = new_page(1280, 720)
    throttled = (429, json.dumps(TOO_MANY_REQUESTS))
    route = DashboardRoute([dashboard_answer(seven_day_figures(NOW)), throttled])
    mocked_dashboard(page, server.base_url, route)
    assert session_value(page, OPS_TOKEN_KEY) == OPS_TOKEN

    period_button(page, "30").click()

    expect_ops_state(page, "locked")
    error = page.get_by_test_id("ops-token-error")
    expect(error).to_have_text(load_fr()["ops.throttled"])
    expect(error).to_have_attribute("role", "alert")
    assert session_value(page, OPS_TOKEN_KEY) is None
