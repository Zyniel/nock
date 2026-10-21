"""Tests of spec 029, AC-4: replaying a finished grid opens a new room, empty.

Live server with FX-01 as published entry 1 (spec 010's harness). The device holds
`nock.progress` = `{"1": "finished"}` and one history record, of room `QQQQQQ` on
grid 1. A click on its `history-replay` runs spec 010's play steps: it sends
`POST /api/rooms` with `{"grid_number": 1}` and loads `/r/<code>` with a code other
than the record's; the room page reaches `data-status="joined"` without
`nickname-form` (spec 017's watcher), `data-solved="false"`, 18 letter cells with
`data-letter=""`; `nock.room.<code>` holds `"grid": 1`, and `nock.progress["1"]` is
still `"finished"`.

When `POST /api/rooms` answers 500, or 404 as for a withdrawn grid (spec 005), the
page stays on `/`, the item shows `history-error` with
`fr.json["catalogue.play_failed"]`, and the button is enabled again. The button is
disabled while the request runs.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, Request, Route, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec010_harness import (
    ROOM_URL_PATTERN,
    catalogue_from_grid,
    code_from_url,
    expect_joined,
    read_json_object,
    seed_local_storage,
)
from spec029_harness import (
    HISTORY_KEY,
    OLD_FINISHED_AT,
    WAIT_TIMEOUT_MS,
    device_record,
    expect_history_count,
    history_item,
    history_value,
    open_catalogue,
    wait_quietly,
)
from spec032_harness import FORM_WATCHER, grid_from_text, load_fr

RECORD_CODE = "QQQQQQ"
PROGRESS_KEY = "nock.progress"
FINISHED_PROGRESS = json.dumps({"1": "finished"})
CREATE_ROUTE = "**/api/rooms"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (spec 010's harness), served by `live_server`."""
    return catalogue_from_grid(fx01_grid)


def grid_1_record() -> dict[str, object]:
    """A history record of a room on grid 1, with Bob."""
    return device_record(RECORD_CODE, 1, OLD_FINISHED_AT, 600_000, ["Bob"])


def open_history(page: Page, live_server: str) -> None:
    """Open `/` with the finished progress and the record of grid 1."""
    seed_local_storage(
        page,
        {
            PROGRESS_KEY: FINISHED_PROGRESS,
            HISTORY_KEY: history_value([grid_1_record()]),
        },
    )
    page.add_init_script(FORM_WATCHER)
    open_catalogue(page, live_server, None)
    expect_history_count(page, 1)


def click_replay(page: Page, live_server: str) -> str:
    """Click the record's replay button; return the code of the room it loads."""
    open_history(page, live_server)
    history_item(page, RECORD_CODE).get_by_test_id("history-replay").click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=WAIT_TIMEOUT_MS)
    return code_from_url(page.url)


# ---- A replay that succeeds ---------------------------------------------------------


def test_ac4_replay_sends_the_creation_request_with_the_grid_number(
    page: Page, live_server: str
) -> None:
    created: list[object] = []

    def keep_creation(request: Request) -> None:
        if request.method == "POST" and request.url.endswith("/api/rooms"):
            created.append(request.post_data_json)

    page.on("request", keep_creation)

    click_replay(page, live_server)

    assert created == [{"grid_number": 1}]


def test_ac4_replay_loads_a_new_room_with_another_code(
    page: Page, live_server: str
) -> None:
    code = click_replay(page, live_server)

    assert code != RECORD_CODE


def test_ac4_the_new_room_is_joined_without_the_nickname_form(
    page: Page, live_server: str
) -> None:
    click_replay(page, live_server)

    expect_joined(page)
    assert page.evaluate("() => window.__formSeen") is False


def test_ac4_the_new_room_is_unsolved_with_18_empty_letter_cells(
    page: Page, live_server: str
) -> None:
    click_replay(page, live_server)

    room = expect_joined(page)
    expect(room).to_have_attribute("data-solved", "false")
    letter_cells = page.locator('[data-testid="cell"][data-type="letter"]')
    expect(letter_cells).to_have_count(18)
    empty_cells = page.locator('[data-testid="cell"][data-letter=""]')
    expect(empty_cells).to_have_count(18)


def test_ac4_the_room_record_of_the_new_room_holds_the_grid_number(
    page: Page, live_server: str
) -> None:
    code = click_replay(page, live_server)
    expect_joined(page)

    record = read_json_object(page, f"nock.room.{code}")

    assert record["grid"] == 1


def test_ac4_the_progress_of_the_grid_stays_finished(
    page: Page, live_server: str
) -> None:
    click_replay(page, live_server)
    expect_joined(page)

    progress = read_json_object(page, PROGRESS_KEY)

    assert progress["1"] == "finished"


# ---- A replay that fails ------------------------------------------------------------


def fail_replay(page: Page, live_server: str, status: int) -> None:
    """Open the history with the creation route answering `status`, click replay."""

    def handle(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        route.fulfill(
            status=status,
            content_type="application/json",
            body=json.dumps({"detail": "refused by the test"}),
        )

    page.route(CREATE_ROUTE, handle)
    open_history(page, live_server)
    history_item(page, RECORD_CODE).get_by_test_id("history-replay").click()


@pytest.mark.parametrize("status", [500, 404])
def test_ac4_a_failed_replay_stays_on_the_catalogue_page(
    page: Page, live_server: str, status: int
) -> None:
    fail_replay(page, live_server, status)

    error = history_item(page, RECORD_CODE).get_by_test_id("history-error")
    expect(error).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    wait_quietly(page)
    assert page.url == f"{live_server}/"


@pytest.mark.parametrize("status", [500, 404])
def test_ac4_a_failed_replay_shows_the_error_in_its_item(
    page: Page, live_server: str, status: int
) -> None:
    fail_replay(page, live_server, status)

    error = history_item(page, RECORD_CODE).get_by_test_id("history-error")
    expect(error).to_have_text(
        load_fr()["catalogue.play_failed"], timeout=WAIT_TIMEOUT_MS
    )
    expect(error).to_have_attribute("role", "alert")


@pytest.mark.parametrize("status", [500, 404])
def test_ac4_after_a_failed_replay_the_button_is_enabled_again(
    page: Page, live_server: str, status: int
) -> None:
    fail_replay(page, live_server, status)

    item = history_item(page, RECORD_CODE)
    expect(item.get_by_test_id("history-error")).to_be_visible(timeout=WAIT_TIMEOUT_MS)
    expect(item.get_by_test_id("history-replay")).to_be_enabled()


def test_ac4_the_button_is_disabled_while_the_request_runs(
    page: Page, live_server: str
) -> None:
    held: list[Route] = []

    def hold(route: Route) -> None:
        if route.request.method != "POST":
            route.continue_()
            return
        held.append(route)

    page.route(CREATE_ROUTE, hold)
    open_history(page, live_server)
    replay = history_item(page, RECORD_CODE).get_by_test_id("history-replay")
    replay.click()
    waited_ms = 0
    while len(held) == 0:
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("the page sent no POST /api/rooms")
        page.wait_for_timeout(50)
        waited_ms += 50

    expect(replay).to_be_disabled()
    held[0].fulfill(status=500, content_type="application/json", body="{}")
    expect(replay).to_be_enabled(timeout=WAIT_TIMEOUT_MS)
