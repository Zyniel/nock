"""Tests of spec 010: instant solo start (catalogue play button, room record)."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from playwright.sync_api import (
    Browser,
    Locator,
    Page,
    Request,
    Route,
    WebSocket,
    WebSocketRoute,
    expect,
)

import nock.room
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    ErrorMessage,
    GridSolved,
    Join,
    PlayerState,
    PlayerView,
    RevealBudget,
    SelectCell,
    Snapshot,
    grid_view,
    parse_client_message,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 500
URL_TIMEOUT_MS = 10_000
MOCK_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
MOCK_CODE = "ABC123"
PROGRESS_KEY = "nock.progress"
NICKNAME_KEY = "nock.nickname"
ROOM_URL_PATTERN = re.compile(r"/r/[A-Z0-9]{6}$")
ROOM_RECORD_KEY = f"nock.room.{MOCK_CODE}"
IDENTITY_KEY = f"nock.identity.{MOCK_CODE}"
CATALOGUE_RECORD = json.dumps({"grid": 1, "selection": None})
STARTED_PROGRESS = json.dumps({"1": "started"})
STORED_IDENTITY = json.dumps(
    {"player_id": "p7", "resume_token": MOCK_TOKEN, "nickname": "Ana 2"}
)
BREAK_STORAGE_SCRIPT = (
    "Storage.prototype.setItem = function () {"
    " throw new DOMException('quota', 'QuotaExceededError'); };"
)


# ---- Fixtures and helpers ---------------------------------------------------


def credits() -> dict[str, str]:
    """Return the credit fields of a catalogue entry (tests/fixtures/credits.json)."""
    credits_path = Path(__file__).parent / "fixtures" / "credits.json"
    return json.loads(credits_path.read_text(encoding="utf-8"))


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1, force 2."""
    entry = CatalogueEntry(
        number=1,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        **credits(),
        grid=fx01_grid,
    )
    return Catalogue(entries=(entry,))


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def cell_at(page: Page, row: int, column: int) -> Locator:
    selector = f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
    return page.locator(selector)


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click()


def wait_until(page: Page, condition: Callable[[], bool]) -> None:
    """Let Playwright run its callbacks until `condition` holds."""
    waited_ms = 0
    while not condition():
        if waited_ms >= WAIT_TIMEOUT_MS:
            pytest.fail("timed out waiting for the page")
        page.wait_for_timeout(50)
        waited_ms += 50


def settle(page: Page) -> None:
    """Give the page time to do things that must not happen."""
    page.wait_for_timeout(SETTLE_MS)


def read_storage(page: Page, key: str) -> str | None:
    raw = page.evaluate("key => localStorage.getItem(key)", key)
    if raw is None:
        return None
    assert isinstance(raw, str)
    return raw


def wait_for_storage(page: Page, key: str) -> str:
    """Return the value of `key` once the page has written it."""
    waited_ms = 0
    while waited_ms < WAIT_TIMEOUT_MS:
        value = read_storage(page, key)
        if value is not None:
            return value
        page.wait_for_timeout(50)
        waited_ms += 50
    pytest.fail(f"the page never wrote localStorage[{key!r}]")


def read_json_object(page: Page, key: str) -> dict[str, object]:
    """Return `localStorage[key]` parsed as a JSON object."""
    raw = read_storage(page, key)
    assert raw is not None, f"localStorage[{key!r}] is absent"
    parsed = json.loads(raw)
    assert isinstance(parsed, dict), raw
    return parsed


def wait_for_progress(page: Page, expected: dict[str, str]) -> None:
    """Wait until `nock.progress` parses to exactly `expected`."""

    def has_expected() -> bool:
        raw = read_storage(page, PROGRESS_KEY)
        if raw is None:
            return False
        return json.loads(raw) == expected

    wait_until(page, has_expected)


def seed_local_storage(page: Page, items: dict[str, str]) -> None:
    """Fill absent `localStorage` keys before the page's own scripts run.

    The script runs again on every navigation, so it must not overwrite
    values the client wrote since.
    """
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " if (localStorage.getItem(key) === null) {"
        " localStorage.setItem(key, value); } }"
    )
    page.context.add_init_script(script)


def item_play_button(page: Page, number: int = 1) -> Locator:
    selector = f'[data-testid="catalogue-item"][data-number="{number}"]'
    return page.locator(selector).get_by_test_id("catalogue-play")


def code_from_url(url: str) -> str:
    match = re.search(r"/r/([A-Z0-9]{6})$", url)
    assert match is not None, url
    return match.group(1)


def start_from_catalogue(page: Page, base_url: str) -> str:
    """Click play on item 1 of `/` and return the code of the room it loads."""
    page.goto(f"{base_url}/")
    item_play_button(page).click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    return code_from_url(page.url)


def expect_joined(page: Page) -> Locator:
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined", timeout=URL_TIMEOUT_MS)
    return room


def is_firefox(page: Page) -> bool:
    browser = page.context.browser
    return browser is not None and browser.browser_type.name == "firefox"


def fix_firefox_text(payload: str) -> str:
    """Undo Playwright's Firefox delivering UTF-8 text frames as latin-1."""
    try:
        return payload.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return payload


class FrameRecorder:
    """The frames a page sends on its room sockets, in order."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.frames: list[str] = []
        self.is_firefox = is_firefox(page)
        page.on("websocket", self._on_socket)

    def _on_socket(self, websocket: WebSocket) -> None:
        if websocket.url.endswith("/ws"):
            websocket.on("framesent", self._on_frame)

    def _on_frame(self, payload: str | bytes) -> None:
        if isinstance(payload, str):
            text = fix_firefox_text(payload) if self.is_firefox else payload
        else:
            text = payload.decode("utf-8")
        self.frames.append(text)

    def wait_for_frames(self, count: int) -> None:
        wait_until(self.page, lambda: len(self.frames) >= count)

    def first_join(self) -> Join:
        self.wait_for_frames(1)
        message = parse_client_message(self.frames[0])
        assert isinstance(message, Join), self.frames[0]
        return message


class RequestCounter:
    """Counts the room creation requests a page sends."""

    def __init__(self, page: Page) -> None:
        self.count = 0
        page.on("request", self._on_request)

    def _on_request(self, request: Request) -> None:
        if request.method == "POST" and request.url.endswith("/api/rooms"):
            self.count += 1


def fail_creation_with_500(route: Route) -> None:
    route.fulfill(status=500, content_type="application/json", body="{}")


def fail_creation_with_500_and_code(route: Route) -> None:
    route.fulfill(
        status=500, content_type="application/json", body='{"code": "ABC123"}'
    )


def fail_creation_with_409_and_code(route: Route) -> None:
    route.fulfill(
        status=409, content_type="application/json", body='{"code": "ABC123"}'
    )


def fail_creation_by_abort(route: Route) -> None:
    route.abort()


def letters_on_server(
    registry: RoomRegistry, code: str, positions: list[tuple[int, int]]
) -> list[str | None]:
    state = registry.room_state(code)
    assert state is not None
    letters: list[str | None] = []
    for row, column in positions:
        for cell in state.cells:
            if (cell.row, cell.column) == (row, column):
                letters.append(cell.letter)
    return letters


def expect_selection(page: Page, row: int, column: int, direction: str) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))
    expect(grid).to_have_attribute("data-direction", direction)


def expect_nothing_selected(page: Page) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", "")
    expect(grid).to_have_attribute("data-selected-column", "")


# ---- Mocked socket ----------------------------------------------------------


class MockRoomSocket:
    """The server side of the room socket of /r/ABC123, driven by the test."""

    def __init__(self, page: Page) -> None:
        self.page = page
        self.received: list[str] = []
        self.routes: list[WebSocketRoute] = []

    def handle(self, route: WebSocketRoute) -> None:
        self.routes.append(route)
        route.on_message(self._record)

    def _record(self, message: str | bytes) -> None:
        text = message if isinstance(message, str) else message.decode("utf-8")
        self.received.append(text)

    def send(self, frame: str) -> None:
        self.routes[0].send(frame)

    def close(self, code: int) -> None:
        self.routes[0].close(code=code)

    def wait_for_frames(self, count: int) -> None:
        wait_until(self.page, lambda: len(self.received) >= count)

    def first_join(self) -> Join:
        self.wait_for_frames(1)
        message = parse_client_message(self.received[0])
        assert isinstance(message, Join), self.received[0]
        return message


def open_mock_room(
    page: Page, base_url: str, items: dict[str, str] | None = None
) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and `localStorage` seeded with `items`."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    if items:
        seed_local_storage(page, items)
    page.goto(f"{base_url}/r/{MOCK_CODE}")
    return mock


def submit_form(page: Page, nickname: str) -> None:
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)


def snapshot_of(grid: Grid, solved: bool = False, seq: int = 0) -> Snapshot:
    you = PlayerView(
        player_id="p1",
        nickname="Ana",
        colour=0,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )
    return Snapshot(
        seq=seq,
        you="p1",
        resume_token=MOCK_TOKEN,
        grid=grid_view(grid),
        players=(you,),
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=solved,
    )


def send_snapshot(mock: MockRoomSocket, grid: Grid, solved: bool = False) -> None:
    mock.send(snapshot_of(grid, solved).model_dump_json())
    expect(mock.page.get_by_test_id("cell")).to_have_count(25)


def send_solved_event(mock: MockRoomSocket) -> None:
    event = GridSolved(seq=1, elapsed_ms=1000)
    mock.send(event.model_dump_json())


def selection_record(row: int, column: int, direction: str) -> str:
    selection = {"row": row, "column": column, "direction": direction}
    return json.dumps({"grid": 1, "selection": selection})


def sent_selects(mock: MockRoomSocket) -> list[SelectCell]:
    selects: list[SelectCell] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, SelectCell):
            selects.append(message)
    return selects


# ---- AC-1: one tap starts a joined room --------------------------------------


def test_ac1_play_button_is_on_the_catalogue_item_with_its_label(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")

    button = item_play_button(page)
    expect(button).to_have_count(1)
    expect(button).to_have_text(load_fr()["catalogue.play"])
    expect(button).to_be_enabled()


def test_ac1_play_button_is_on_the_grid_page_too(page: Page, live_server: str) -> None:
    page.goto(f"{live_server}/g/1")

    button = page.get_by_test_id("catalogue-item").get_by_test_id("catalogue-play")
    expect(button).to_have_count(1)
    expect(button).to_have_text(load_fr()["catalogue.play"])


def test_ac1_one_click_leads_to_a_joined_room_with_the_grid(
    page: Page, live_server: str
) -> None:
    start_from_catalogue(page, live_server)

    room = expect_joined(page)
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("cell")).to_have_count(25)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("nickname-input")).to_have_count(0)


def test_ac1_one_click_on_the_grid_page_leads_to_a_joined_room(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/g/1")
    page.get_by_test_id("catalogue-play").click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)

    room = expect_joined(page)
    expect(room).to_have_attribute("data-grid", "5x5")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("nickname-input")).to_have_count(0)


def test_ac1_the_new_room_exists_on_the_server(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    code = start_from_catalogue(page, live_server)

    expect_joined(page)
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1


def test_ac1_typing_in_the_new_room_shows_the_letter(
    page: Page, live_server: str
) -> None:
    start_from_catalogue(page, live_server)
    expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)

    tap(page, 1, 0)
    page.keyboard.press("t")

    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")


@pytest.mark.parametrize(
    "handler",
    [
        fail_creation_with_500,
        fail_creation_with_500_and_code,
        fail_creation_with_409_and_code,
        fail_creation_by_abort,
    ],
    ids=["500", "500-with-code", "409-with-code", "abort"],
)
def test_ac1_creation_failure_stays_on_the_page_and_shows_the_error(
    page: Page, live_server: str, handler: Callable[[Route], None]
) -> None:
    page.route("**/api/rooms", handler)
    page.goto(f"{live_server}/")
    button = item_play_button(page)

    button.click()

    error = page.get_by_test_id("catalogue-error")
    expect(error).to_have_text(load_fr()["catalogue.play_failed"])
    expect(button).to_be_enabled()
    settle(page)
    assert page.url == f"{live_server}/"
    progress = read_json_object(page, PROGRESS_KEY)
    assert progress == {"1": "started"}


def test_ac1_after_a_failure_the_next_tap_works(page: Page, live_server: str) -> None:
    page.route("**/api/rooms", fail_creation_with_500)
    page.goto(f"{live_server}/")
    item_play_button(page).click()
    expect(page.get_by_test_id("catalogue-error")).to_have_text(
        load_fr()["catalogue.play_failed"]
    )

    page.unroute("**/api/rooms")
    item_play_button(page).click()

    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    expect_joined(page)


def test_ac1_a_double_tap_sends_one_creation_request(
    page: Page, live_server: str
) -> None:
    counter = RequestCounter(page)
    page.goto(f"{live_server}/")

    item_play_button(page).dblclick()

    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    expect_joined(page)
    assert counter.count == 1


def test_ac1_replaying_a_grid_creates_a_new_room_each_time(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    first_code = start_from_catalogue(page, live_server)
    expect_joined(page)

    second_code = start_from_catalogue(page, live_server)

    expect_joined(page)
    assert second_code != first_code
    assert room_registry.room_state(first_code) is not None
    assert room_registry.room_state(second_code) is not None


def test_ac1_storage_that_refuses_writes_still_creates_and_loads_the_room(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    page.context.add_init_script(BREAK_STORAGE_SCRIPT)

    code = start_from_catalogue(page, live_server)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname", timeout=URL_TIMEOUT_MS)
    assert room_registry.room_state(code) is not None
    assert read_storage(page, PROGRESS_KEY) is None


# ---- AC-2: a solo room becomes shared, letters kept --------------------------


def test_ac2_a_second_player_joins_the_solo_room_and_sees_the_letters(
    page: Page,
    browser: Browser,
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    code = start_from_catalogue(page, live_server)
    room = expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    tap(page, 1, 0)
    page.keyboard.press("t")
    page.keyboard.press("a")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    page.evaluate("window.soloMarker = 'still here'")
    friend_context = browser.new_context()
    try:
        friend_page = friend_context.new_page()

        enter_room(friend_page, page.url, nickname="Bob")

        friend_room = friend_page.get_by_test_id("room-page")
        expect(friend_room).to_have_attribute("data-status", "joined")
        expect(cell_at(friend_page, 1, 0)).to_have_attribute("data-letter", "T")
        expect(cell_at(friend_page, 1, 1)).to_have_attribute("data-letter", "A")
        expect(page.get_by_test_id("roster-player")).to_have_count(2)
        expect(room).to_have_attribute("data-room-code", code)
        expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
        expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
        assert page.evaluate("window.soloMarker") == "still here"
        assert page.url.endswith(f"/r/{code}")
    finally:
        friend_context.close()


# ---- AC-3: reload restores letters and selection -----------------------------


def test_ac3_reload_resumes_the_same_player_with_letters_and_selection(
    page: Page, live_server: str, room_registry: RoomRegistry
) -> None:
    recorder = FrameRecorder(page)
    code = start_from_catalogue(page, live_server)
    room = expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    tap(page, 1, 0)
    page.keyboard.press("t")
    page.keyboard.press("a")
    tap(page, 2, 2)
    tap(page, 2, 2)
    expect_selection(page, 2, 2, "down")
    wait_until(
        page,
        lambda: letters_on_server(room_registry, code, [(1, 0), (1, 1)]) == ["T", "A"],
    )
    expected_selection = {"row": 2, "column": 2, "direction": "down"}
    wait_until(
        page,
        lambda: read_json_object(page, f"nock.room.{code}").get("selection")
        == expected_selection,
    )
    you = room.get_attribute("data-you")
    assert you
    identity = read_json_object(page, f"nock.identity.{code}")
    token = identity["resume_token"]
    assert isinstance(token, str)
    recorder.frames.clear()

    page.reload()

    room = expect_joined(page)
    expect(room).to_have_attribute("data-room-code", code)
    expect(room).to_have_attribute("data-you", you)
    assert recorder.first_join().resume_token == token
    expect(page.get_by_test_id("roster").get_by_test_id("roster-player")).to_have_count(
        1
    )
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-letter", "A")
    expect_selection(page, 2, 2, "down")


def test_ac3_the_selection_is_written_to_the_room_record(
    page: Page, live_server: str
) -> None:
    code = start_from_catalogue(page, live_server)
    expect_joined(page)
    expect(page.get_by_test_id("cell")).to_have_count(25)

    tap(page, 3, 1)
    tap(page, 3, 1)

    expected = {"row": 3, "column": 1, "direction": "down"}
    wait_until(
        page,
        lambda: read_json_object(page, f"nock.room.{code}").get("selection")
        == expected,
    )
    record = read_json_object(page, f"nock.room.{code}")
    assert record["grid"] == 1


def test_ac3_a_valid_saved_selection_is_restored_and_sent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(
        page, live_server, {ROOM_RECORD_KEY: selection_record(2, 2, "down")}
    )
    mock.first_join()

    send_snapshot(mock, fx01_grid)

    expect_selection(page, 2, 2, "down")
    wait_until(page, lambda: len(sent_selects(mock)) >= 1)
    assert sent_selects(mock) == [SelectCell(row=2, column=2, direction="down")]


@pytest.mark.parametrize(
    ("row", "column", "direction"),
    [
        (0, 0, "across"),
        (0, 3, "down"),
        (9, 9, "across"),
        (1, 0, "down"),
        (2, 2, "diagonal"),
    ],
    ids=[
        "clue-cell",
        "clue-cell-2",
        "outside",
        "no-word-in-direction",
        "bad-direction",
    ],
)
def test_ac3_an_invalid_saved_selection_is_ignored_and_nothing_is_sent(
    page: Page, live_server: str, fx01_grid: Grid, row: int, column: int, direction: str
) -> None:
    record = selection_record(row, column, direction)
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: record})
    mock.first_join()

    send_snapshot(mock, fx01_grid)

    settle(page)
    expect_nothing_selected(page)
    assert sent_selects(mock) == []
    assert len(mock.received) == 1


def test_ac3_a_null_saved_selection_selects_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: CATALOGUE_RECORD})
    mock.first_join()

    send_snapshot(mock, fx01_grid)

    settle(page)
    expect_nothing_selected(page)
    assert len(mock.received) == 1


def test_ac3_unknown_fields_of_the_room_record_are_kept(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    record = json.dumps({"grid": 1, "selection": None, "colour": "teal"})
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: record})
    mock.first_join()
    send_snapshot(mock, fx01_grid)

    tap(page, 1, 1)

    expected = {"row": 1, "column": 1, "direction": "across"}
    wait_until(
        page,
        lambda: read_json_object(page, ROOM_RECORD_KEY).get("selection") == expected,
    )
    stored = read_json_object(page, ROOM_RECORD_KEY)
    assert stored["colour"] == "teal"
    assert stored["grid"] == 1


@pytest.mark.parametrize("raw_record", ["not json", "[]"])
def test_ac3_a_corrupt_room_record_is_read_as_no_record(
    page: Page, live_server: str, raw_record: str
) -> None:
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: raw_record})

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.received == []


def test_ac3_a_corrupt_room_record_is_replaced_when_the_selection_changes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: "not json"})
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    send_snapshot(mock, fx01_grid)

    tap(page, 1, 1)

    expected = {"row": 1, "column": 1, "direction": "across"}
    wait_until(
        page,
        lambda: read_json_object(page, ROOM_RECORD_KEY).get("selection") == expected,
    )
    assert read_json_object(page, ROOM_RECORD_KEY)["grid"] is None


def test_ac3_a_room_that_is_gone_shows_not_found_and_keeps_the_record(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(
        page, live_server, {ROOM_RECORD_KEY: selection_record(2, 2, "down")}
    )
    mock.first_join()

    mock.close(4404)

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.not_found"]
    )
    assert read_json_object(page, ROOM_RECORD_KEY) == {
        "grid": 1,
        "selection": {"row": 2, "column": 2, "direction": "down"},
    }


def test_ac3_a_room_joined_by_link_records_a_null_grid_and_the_selection(
    page: Page,
    browser: Browser,
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    start_from_catalogue(page, live_server)
    expect_joined(page)
    friend_context = browser.new_context()
    try:
        friend_page = friend_context.new_page()
        enter_room(friend_page, page.url, nickname="Bob")
        expect(friend_page.get_by_test_id("cell")).to_have_count(25)
        code = code_from_url(friend_page.url)

        tap(friend_page, 1, 1)

        expected = {"row": 1, "column": 1, "direction": "across"}
        wait_until(
            friend_page,
            lambda: read_json_object(friend_page, f"nock.room.{code}").get("selection")
            == expected,
        )
        record = read_json_object(friend_page, f"nock.room.{code}")
        assert record["grid"] is None
        assert read_storage(friend_page, PROGRESS_KEY) is None
    finally:
        friend_context.close()


# ---- AC-4: starting marks the grid started ------------------------------------


def test_ac4_starting_marks_the_grid_started_and_records_the_room(
    page: Page, live_server: str
) -> None:
    code = start_from_catalogue(page, live_server)

    progress = read_json_object(page, PROGRESS_KEY)
    assert progress == {"1": "started"}
    record = read_json_object(page, f"nock.room.{code}")
    assert record["grid"] == 1


def test_ac4_the_catalogue_shows_the_grid_as_started_afterwards(
    page: Page, live_server: str
) -> None:
    start_from_catalogue(page, live_server)
    expect_joined(page)

    page.goto(f"{live_server}/")

    item = page.locator('[data-testid="catalogue-item"][data-number="1"]')
    expect(item).to_have_attribute("data-progress", "started")


def test_ac4_the_room_record_is_written_before_the_page_loads(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/")
    item_play_button(page).click()
    page.wait_for_url(ROOM_URL_PATTERN, timeout=URL_TIMEOUT_MS)
    code = code_from_url(page.url)

    record = json.loads(wait_for_storage(page, f"nock.room.{code}"))

    assert record["grid"] == 1
    assert "selection" in record


def test_ac4_a_finished_grid_stays_finished_when_replayed(
    page: Page, live_server: str
) -> None:
    seed_local_storage(page, {PROGRESS_KEY: json.dumps({"1": "finished"})})

    code = start_from_catalogue(page, live_server)

    assert read_json_object(page, PROGRESS_KEY) == {"1": "finished"}
    assert read_json_object(page, f"nock.room.{code}")["grid"] == 1


def test_ac4_other_grids_progress_is_kept(page: Page, live_server: str) -> None:
    seed_local_storage(page, {PROGRESS_KEY: json.dumps({"2": "finished"})})

    start_from_catalogue(page, live_server)

    assert read_json_object(page, PROGRESS_KEY) == {"1": "started", "2": "finished"}


# ---- AC-5: solving marks the grid finished -------------------------------------


def test_ac5_grid_solved_event_marks_the_grid_finished(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    items = {ROOM_RECORD_KEY: CATALOGUE_RECORD, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    mock.first_join()
    send_snapshot(mock, fx01_grid)
    assert read_json_object(page, PROGRESS_KEY) == {"1": "started"}

    send_solved_event(mock)

    wait_for_progress(page, {"1": "finished"})


def test_ac5_a_solved_snapshot_marks_the_grid_finished(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    items = {ROOM_RECORD_KEY: CATALOGUE_RECORD, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    mock.first_join()

    send_snapshot(mock, fx01_grid, solved=True)

    wait_for_progress(page, {"1": "finished"})


def test_ac5_an_unsolved_snapshot_alone_marks_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    items = {ROOM_RECORD_KEY: CATALOGUE_RECORD, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    mock.first_join()

    send_snapshot(mock, fx01_grid)

    settle(page)
    assert read_json_object(page, PROGRESS_KEY) == {"1": "started"}


def test_ac5_solving_a_room_without_catalogue_grid_changes_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    record = json.dumps({"grid": None, "selection": None})
    items = {ROOM_RECORD_KEY: record, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    send_snapshot(mock, fx01_grid)

    send_solved_event(mock)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "1")
    settle(page)
    assert read_json_object(page, PROGRESS_KEY) == {"1": "started"}


def test_ac5_a_solved_snapshot_in_a_room_without_catalogue_grid_changes_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    record = json.dumps({"grid": None, "selection": None})
    items = {ROOM_RECORD_KEY: record, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)

    send_snapshot(mock, fx01_grid, solved=True)

    settle(page)
    assert read_json_object(page, PROGRESS_KEY) == {"1": "started"}


@pytest.mark.parametrize("raw_record", ["not json", "[]"])
def test_ac5_a_corrupt_room_record_marks_nothing(
    page: Page, live_server: str, fx01_grid: Grid, raw_record: str
) -> None:
    items = {ROOM_RECORD_KEY: raw_record, PROGRESS_KEY: STARTED_PROGRESS}
    mock = open_mock_room(page, live_server, items)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    send_snapshot(mock, fx01_grid)

    send_solved_event(mock)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "1")
    settle(page)
    assert read_json_object(page, PROGRESS_KEY) == {"1": "started"}


# ---- AC-6: the creator joins at once -------------------------------------------


def test_ac6_the_creator_joins_with_the_saved_nickname(
    page: Page, live_server: str
) -> None:
    seed_local_storage(page, {NICKNAME_KEY: "Zoé"})
    recorder = FrameRecorder(page)

    code = start_from_catalogue(page, live_server)

    assert recorder.first_join() == Join(nickname="Zoé", resume_token=None)
    room = expect_joined(page)
    roster = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(roster).to_have_count(1)
    expect(roster).to_have_attribute("data-you", "true")
    expect(roster.get_by_test_id("roster-nickname")).to_have_text("Zoé")
    you = room.get_attribute("data-you")
    assert you
    wait_for_storage(page, f"nock.identity.{code}")
    identity = read_json_object(page, f"nock.identity.{code}")
    assert identity["player_id"] == you
    assert identity["nickname"] == "Zoé"


def test_ac6_without_a_saved_nickname_the_creator_is_the_default_guest(
    page: Page, live_server: str
) -> None:
    default_nickname = load_fr()["room.default_nickname"]
    recorder = FrameRecorder(page)

    code = start_from_catalogue(page, live_server)

    assert recorder.first_join() == Join(nickname=default_nickname, resume_token=None)
    room = expect_joined(page)
    roster = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(roster).to_have_count(1)
    expect(roster).to_have_attribute("data-you", "true")
    expect(roster.get_by_test_id("roster-nickname")).to_have_text(default_nickname)
    wait_for_storage(page, f"nock.identity.{code}")
    identity = read_json_object(page, f"nock.identity.{code}")
    assert identity["player_id"] == room.get_attribute("data-you")
    assert identity["nickname"] == default_nickname
    assert read_storage(page, NICKNAME_KEY) is None


@pytest.mark.parametrize("saved", ["A", "<b>"])
def test_ac6_an_invalid_saved_nickname_is_not_used(
    page: Page, live_server: str, saved: str
) -> None:
    seed_local_storage(page, {NICKNAME_KEY: saved})
    recorder = FrameRecorder(page)

    start_from_catalogue(page, live_server)

    expected = Join(nickname=load_fr()["room.default_nickname"], resume_token=None)
    assert recorder.first_join() == expected
    expect_joined(page)


def test_ac6_the_creator_reload_sends_the_stored_token_and_nickname(
    page: Page, live_server: str
) -> None:
    seed_local_storage(page, {NICKNAME_KEY: "Zoé"})
    recorder = FrameRecorder(page)
    code = start_from_catalogue(page, live_server)
    expect_joined(page)
    token = read_json_object(page, f"nock.identity.{code}")["resume_token"]
    assert isinstance(token, str)
    recorder.frames.clear()

    page.reload()

    expect_joined(page)
    assert recorder.first_join() == Join(nickname="Zoé", resume_token=token)


def test_ac6_a_stored_identity_wins_over_the_room_record_and_the_nickname(
    page: Page, live_server: str
) -> None:
    items = {
        IDENTITY_KEY: STORED_IDENTITY,
        ROOM_RECORD_KEY: CATALOGUE_RECORD,
        NICKNAME_KEY: "Zoé",
    }
    mock = open_mock_room(page, live_server, items)

    assert mock.first_join() == Join(nickname="Ana 2", resume_token=MOCK_TOKEN)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_stored_identity_wins_without_a_room_record(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {IDENTITY_KEY: STORED_IDENTITY})

    assert mock.first_join() == Join(nickname="Ana 2", resume_token=MOCK_TOKEN)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_room_record_with_a_grid_joins_at_once_without_a_form(
    page: Page, live_server: str
) -> None:
    items = {ROOM_RECORD_KEY: CATALOGUE_RECORD, NICKNAME_KEY: "Zoé"}
    mock = open_mock_room(page, live_server, items)

    assert mock.first_join() == Join(nickname="Zoé", resume_token=None)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_corrupt_identity_with_a_room_record_joins_as_a_new_player(
    page: Page, live_server: str
) -> None:
    items = {IDENTITY_KEY: "not json", ROOM_RECORD_KEY: CATALOGUE_RECORD}
    mock = open_mock_room(page, live_server, items)

    expected = Join(nickname=load_fr()["room.default_nickname"], resume_token=None)
    assert mock.first_join() == expected
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_corrupt_identity_without_a_room_record_shows_the_form(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {IDENTITY_KEY: "not json"})

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.received == []


def test_ac6_a_record_without_a_grid_shows_the_form(
    page: Page, live_server: str
) -> None:
    record = json.dumps({"grid": None, "selection": None})
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: record})

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.received == []


def test_ac6_a_refused_creator_falls_back_to_the_nickname_form(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: CATALOGUE_RECORD})
    mock.first_join()

    refusal = ErrorMessage(code=ErrorCode.INVALID_NICKNAME, message="refused")
    mock.send(refusal.model_dump_json())

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()


def test_ac1_fr_json_has_the_play_texts() -> None:
    fr = load_fr()

    assert fr["catalogue.play"] == "Jouer"
    assert fr["catalogue.play_failed"] == "Impossible de lancer la partie. Réessayez."
    assert fr["room.default_nickname"] == "Invité"
