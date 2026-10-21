"""Tests of spec 029, AC-2 on the room page and with live players.

Room page, on spec 026's mocked socket of `/r/ABC123` (the page enters as `Ana`,
the snapshot's resume token is `SNAPSHOT_RESUME_TOKEN`) and a mocked summaries
route that answers the solved summary of ABC123 (players `Ana` and `Bob`): given a
first snapshot with `solved: true`, or a `grid_solved` event after an unsolved
snapshot, the page sends `POST /api/rooms/summaries` with its code and token, and
`nock.history` gets the room's record, team-mate `Bob`.

Live server, with FX-01 as published entry 1: `Ana` (context 1, Paris time, her
saved nickname `Ana`) starts FX-01 from the catalogue and `Bob` (context 2) joins
the room; Ana types the 17 letters other than (4, 4), Bob types `T` there (spec
026 AC-3). Context 1 then opens `/`: `history` lists one item with
`data-grid="1"`, `Avec Bob`, a `data-elapsed-ms` equal to the room's
`solved_elapsed_ms` and the date text of its `solved_at` (spec 032's `date`, read
with `Intl.DateTimeFormat` in Paris time).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import GridSolved, LetterChanged
from spec010_harness import (
    catalogue_from_grid,
    expect_joined,
    seed_local_storage,
    start_from_catalogue,
)
from spec026_harness import (
    BROWSER_FIRST_17,
    KEY_PAUSE_MS,
    LAST_CELL,
    ROOM_CODE,
    SNAPSHOT_RESUME_TOKEN,
    EnterRoom,
    MockRoomSocket,
    cell_at,
    letters_except,
    open_fx01,
)
from spec029_harness import (
    WAIT_TIMEOUT_MS,
    XYZ_FINISHED_AT,
    NewPage,
    device_record,
    expect_history_count,
    history_items,
    open_catalogue,
    paris_pages,
    solved_summary,
    wait_for_stored_history,
)
from spec032_harness import PARIS, SummariesRoute, grid_from_text, sent_keys

PARIS_DATE_SCRIPT = (
    "milliseconds => new Intl.DateTimeFormat('fr-FR', {day: 'numeric',"
    " month: 'long', year: 'numeric', timeZone: 'Europe/Paris'})"
    ".format(new Date(milliseconds))"
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """FX-01 as published entry 1 (spec 010's harness), served by `live_server`."""
    return catalogue_from_grid(fx01_grid)


@pytest.fixture
def new_page(browser: Browser) -> Iterator[NewPage]:
    yield from paris_pages(browser)


# ---- Room page, mocked socket -------------------------------------------------------


def abc_solved_summary() -> dict[str, object]:
    """The answer for the room page's own room: ABC123, grid 1, Ana and Bob."""
    return solved_summary(ROOM_CODE, 1, ["Ana", "Bob"], XYZ_FINISHED_AT, 754_000)


def abc_record() -> dict[str, object]:
    """The record the room page writes from that answer."""
    return device_record(ROOM_CODE, 1, XYZ_FINISHED_AT, 754_000, ["Bob"])


def wait_for_summaries_request(page: Page, route: SummariesRoute) -> None:
    """Wait until the page has sent one summaries request."""
    waited_ms = 0
    while len(route.bodies) == 0:
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("the room page sent no POST /api/rooms/summaries")
        page.wait_for_timeout(50)
        waited_ms += 50


def open_solved_snapshot(
    page: Page, live_server: str, grid: Grid
) -> tuple[SummariesRoute, MockRoomSocket]:
    """Open /r/ABC123, whose first snapshot has `solved: true`."""
    route = SummariesRoute(body=[abc_solved_summary()])
    page.route("**/api/rooms/summaries", route.handle)
    mock = open_fx01(page, live_server, grid, letters_except([]), solved=True)
    return route, mock


def solve_after_the_snapshot(
    page: Page, live_server: str, grid: Grid
) -> tuple[SummariesRoute, MockRoomSocket]:
    """Open /r/ABC123 with (4, 4) empty, then send its letter and `grid_solved`."""
    route = SummariesRoute(body=[abc_solved_summary()])
    page.route("**/api/rooms/summaries", route.handle)
    mock = open_fx01(page, live_server, grid, letters_except([LAST_CELL]), seq=5)
    row, column = LAST_CELL
    last_letter = LetterChanged(
        seq=6, row=row, column=column, letter="T", pencil=False, player_id="p2"
    )
    mock.send(last_letter.model_dump_json())
    mock.send(GridSolved(seq=7, elapsed_ms=754_000).model_dump_json())
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-solved", "true", timeout=WAIT_TIMEOUT_MS
    )
    return route, mock


def test_ac2_a_solved_first_snapshot_makes_the_page_ask_its_summary(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route, _ = open_solved_snapshot(page, live_server, fx01_grid)

    wait_for_summaries_request(page, route)

    assert route.methods[0] == "POST"
    assert sent_keys(route.bodies[0]) == [(ROOM_CODE, SNAPSHOT_RESUME_TOKEN)]


def test_ac2_a_solved_first_snapshot_writes_the_rooms_record(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_solved_snapshot(page, live_server, fx01_grid)

    wait_for_stored_history(page, [abc_record()])


def test_ac2_a_grid_solved_event_makes_the_page_ask_its_summary(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    route, _ = solve_after_the_snapshot(page, live_server, fx01_grid)

    wait_for_summaries_request(page, route)

    assert route.methods[0] == "POST"
    assert sent_keys(route.bodies[0]) == [(ROOM_CODE, SNAPSHOT_RESUME_TOKEN)]


def test_ac2_a_grid_solved_event_writes_the_rooms_record(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    solve_after_the_snapshot(page, live_server, fx01_grid)

    wait_for_stored_history(page, [abc_record()])


# ---- Live: Ana and Bob solve FX-01 --------------------------------------------------


def ana_and_bob_solve(
    browser: Browser, live_server: str, enter_room: EnterRoom
) -> tuple[Page, str]:
    """AC-2's live play; return Ana's page, back on `/`, and the room's code."""
    ana_context = browser.new_context(timezone_id=PARIS)
    ana_page = ana_context.new_page()
    seed_local_storage(ana_page, {"nock.nickname": "Ana"})
    code = start_from_catalogue(ana_page, live_server)
    expect_joined(ana_page)
    bob_context = browser.new_context()
    bob_page = bob_context.new_page()
    enter_room(bob_page, f"{live_server}/r/{code}", "Bob")
    for row, column, key in BROWSER_FIRST_17:
        cell_at(ana_page, row, column).click()
        ana_page.keyboard.press(key)
        ana_page.wait_for_timeout(KEY_PAUSE_MS)
    expect(cell_at(bob_page, 3, 4)).to_have_attribute(
        "data-letter", "N", timeout=WAIT_TIMEOUT_MS
    )
    cell_at(bob_page, 4, 4).click()
    bob_page.keyboard.press("t")
    for room_page in (ana_page, bob_page):
        expect(room_page.get_by_test_id("room-page")).to_have_attribute(
            "data-solved", "true", timeout=WAIT_TIMEOUT_MS
        )
    open_catalogue(ana_page, live_server, None)
    return ana_page, code


@pytest.fixture
def solved_live(
    browser: Browser, live_server: str, enter_room: EnterRoom
) -> Iterator[tuple[Page, str]]:
    """Ana's page on `/` once Ana and Bob solved FX-01; its contexts closed after."""
    contexts_before = list(browser.contexts)
    try:
        yield ana_and_bob_solve(browser, live_server, enter_room)
    finally:
        for context in browser.contexts:
            if context not in contexts_before:
                context.close()


def test_ac2_live_the_history_lists_the_room_with_its_grid_and_time(
    solved_live: tuple[Page, str], room_registry: RoomRegistry
) -> None:
    page, code = solved_live
    expect_history_count(page, 1)
    state = room_registry.room_state(code)
    assert state is not None

    item = history_items(page)

    expect(item).to_have_attribute("data-code", code)
    expect(item).to_have_attribute("data-grid", "1")
    expect(item).to_have_attribute("data-elapsed-ms", str(state.solved_elapsed_ms))


def test_ac2_live_the_history_names_bob_and_the_date_it_was_solved(
    solved_live: tuple[Page, str], room_registry: RoomRegistry
) -> None:
    page, code = solved_live
    expect_history_count(page, 1)
    state = room_registry.room_state(code)
    assert state is not None
    assert state.solved_at is not None
    date = page.evaluate(PARIS_DATE_SCRIPT, state.solved_at * 1000)

    item = history_items(page)

    expect(item.get_by_test_id("history-teammates")).to_have_text("Avec Bob")
    expect(item.get_by_test_id("history-date")).to_have_text(f"Terminée le {date}")
