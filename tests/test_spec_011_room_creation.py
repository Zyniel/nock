"""Tests of spec 011: room creation, the rooms engine and the wrong-code throttle."""

from __future__ import annotations

import contextlib
import itertools
import json
import logging
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, BrowserContext, Page, WebSocketRoute, expect
from pydantic import ValidationError
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

import nock.hub
import nock.room
import nock.server
from nock.catalogue import Catalogue, CatalogueEntry
from nock.grid import Grid, LetterCell
from nock.hub import ROOM_CODE_ALPHABET, ROOM_CODE_LENGTH, RoomRegistry
from nock.protocol import (
    CellView,
    ClientMessage,
    GridView,
    HelpMode,
    Join,
    LetterCellView,
    LetterChanged,
    PlayerJoined,
    Pong,
    RevealBudget,
    RoomSettings,
    SelectionMoved,
    Snapshot,
    grid_view,
    parse_server_message,
)
from nock.room import (
    DEFAULT_REVEAL_BUDGET,
    DEFAULT_SETTINGS,
    MAX_PLAYERS,
    CellState,
    LogEntry,
    Outcome,
    RoomConfig,
    RoomState,
    grid_state,
    new_room,
)
from nock.server import (
    THROTTLED_CLOSE_CODE,
    WRONG_CODE_LIMIT,
    WRONG_CODE_WINDOW_SECONDS,
    CreateRoomRequest,
    CreateRoomResponse,
    create_app,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
JOIN_TEXT = '{"type": "join", "nickname": "Ana", "resume_token": null}'
NOT_FOUND_BODY = {"detail": "Not Found"}
CODE_PATTERN = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$")
START_TIME = 1_000_000.0
WAIT_TIMEOUT_MS = 5000
RECEIVE_TIMEOUT_SECONDS = 5.0
SETTLE_MS = 500
PUBLISHED_NUMBER = 2
UNPUBLISHED_NUMBER = 4
UNKNOWN_NUMBER = 99
UNKNOWN_CODE = "ZZZZZZ"
PHONE_VIEWPORT = {"width": 360, "height": 740}
DESKTOP_VIEWPORT = {"width": 1280, "height": 800}
STORED_IDENTITY_SCRIPT = (
    "localStorage.setItem('nock.identity.ABC123', JSON.stringify("
    "{player_id: 'p1', resume_token: 'r7Kq2mXo9vB4tY1zW8nP', nickname: 'Ana'}));"
)
EXPECTED_FR_VALUES = {
    "room.share.label": "Lien d'invitation",
    "room.share.copy": "Copier le lien",
    "room.share.copied": "Lien copié",
    "room.status.throttled": "Trop de codes erronés. Réessayez dans une minute.",
}


# ---- Fixtures and helpers ---------------------------------------------------


class FakeClock(Protocol):
    """The `fake_clock` fixture of conftest: a clock moved by hand."""

    now: float

    def __call__(self) -> float: ...

    def advance(self, seconds: float) -> None: ...


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return dist


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue with FX-01 as published entry 2 and as unpublished entry 4."""
    published = CatalogueEntry(
        number=PUBLISHED_NUMBER,
        published_on=date(2026, 10, 1),
        force=2,
        published=True,
        grid=fx01_grid,
    )
    unpublished = CatalogueEntry(
        number=UNPUBLISHED_NUMBER,
        published_on=date(2026, 10, 2),
        force=2,
        published=False,
        grid=fx01_grid,
    )
    return Catalogue(entries=(published, unpublished))


class RecordingRegistry(RoomRegistry):
    """A real registry that remembers each room creation it was asked for."""

    def __init__(self, *, clock: FakeClock | None = None) -> None:
        super().__init__(clock=clock)
        self.created: list[tuple[Grid, int | None]] = []

    def register_room(self, grid: Grid, grid_number: int | None = None) -> str:
        self.created.append((grid, grid_number))
        return super().register_room(grid, grid_number=grid_number)


@pytest.fixture
def recording_registry() -> Iterator[RecordingRegistry]:
    registry = RecordingRegistry()
    yield registry
    registry.close()


@pytest.fixture
def http_client(
    recording_registry: RecordingRegistry, catalogue: Catalogue, dist_dir: Path
) -> TestClient:
    app = create_app(rooms=recording_registry, dist_dir=dist_dir, catalogue=catalogue)
    return TestClient(app)


@pytest.fixture
def clock_registry(fake_clock: FakeClock) -> Iterator[RoomRegistry]:
    """A registry on the fake clock, ticking fast, with no silence time-out."""
    config = RoomConfig(tick_seconds=0.05, silence_timeout_seconds=600)
    registry = RoomRegistry(clock=fake_clock, config=config)
    yield registry
    registry.close()


@pytest.fixture
def room_code(clock_registry: RoomRegistry, fx01_grid: Grid) -> str:
    return clock_registry.register_room(fx01_grid)


@pytest.fixture
def ws_client(
    clock_registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One client, one event loop, on an app serving the room `room_code`."""
    app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with TestClient(app) as client:
        yield client


def receive_text_or_fail(websocket: WebSocketTestSession) -> str:
    """Return the next text of the socket, failing instead of waiting forever."""
    received: queue.Queue[str | BaseException] = queue.Queue()

    def read() -> None:
        try:
            received.put(websocket.receive_text())
        except BaseException as error:  # handed to the test thread, re-raised there
            received.put(error)

    reader = threading.Thread(target=read, daemon=True)
    reader.start()
    try:
        outcome = received.get(timeout=RECEIVE_TIMEOUT_SECONDS)
    except queue.Empty:
        pytest.fail(f"nothing received from the socket in {RECEIVE_TIMEOUT_SECONDS}s")
    if isinstance(outcome, BaseException):
        raise outcome
    return outcome


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def close_code_on_first_read(client: TestClient, code: str) -> int:
    """Connect, send a join and return the close code received.

    The join makes the helper end on its own: a server that wrongly accepts
    the socket answers with a snapshot and the test fails instead of hanging.
    """
    try:
        with client.websocket_connect(socket_url(code)) as websocket:
            websocket.send_text(JOIN_TEXT)
            receive_text_or_fail(websocket)
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail("the server sent a message instead of closing the socket")


def join_and_get_snapshot(
    client: TestClient, code: str, resume_token: str | None = None
) -> Snapshot:
    join_text = Join(nickname="Ana", resume_token=resume_token).model_dump_json()
    with client.websocket_connect(socket_url(code)) as websocket:
        websocket.send_text(join_text)
        message = parse_server_message(receive_text_or_fail(websocket))
    assert isinstance(message, Snapshot)
    return message


def fail_with_wrong_codes(client: TestClient, wrong_codes: list[str]) -> None:
    """Connect once to each code, which must not exist, and expect 4404."""
    for wrong_code in wrong_codes:
        assert close_code_on_first_read(client, wrong_code) == 4404


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


def code_as_number(code: str) -> int:
    """Read a room code as a base-32 number over ROOM_CODE_ALPHABET."""
    value = 0
    for character in code:
        value = value * 32 + ROOM_CODE_ALPHABET.index(character)
    return value


def letter_cells_of(grid: Grid) -> list[LetterCell]:
    letter_cells: list[LetterCell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            letter_cells.append(cell)
    return letter_cells


def fresh_state(grid: Grid, code: str = "ABCDEF") -> RoomState:
    return new_room(code, grid, START_TIME)


# ---- AC-1: HTTP, room creation ----------------------------------------------


def test_ac1_post_creates_a_room_and_answers_201(
    http_client: TestClient, recording_registry: RecordingRegistry, fx01_grid: Grid
) -> None:
    response = http_client.post("/api/rooms", json={"grid_number": PUBLISHED_NUMBER})

    assert response.status_code == 201
    created = CreateRoomResponse.model_validate(response.json())
    assert CODE_PATTERN.match(created.code)
    assert created.share_url == f"http://testserver/r/{created.code}"
    assert recording_registry.find_room(created.code) == fx01_grid


def test_ac1_post_records_the_catalogue_number_in_the_room(
    http_client: TestClient, recording_registry: RecordingRegistry, fx01_grid: Grid
) -> None:
    response = http_client.post("/api/rooms", json={"grid_number": PUBLISHED_NUMBER})

    code = response.json()["code"]
    state = recording_registry.room_state(code)
    assert state is not None
    assert state.grid_number == PUBLISHED_NUMBER
    assert state.code == code
    assert recording_registry.created == [(fx01_grid, PUBLISHED_NUMBER)]


def test_ac1_post_body_holds_only_code_and_share_url(
    http_client: TestClient,
) -> None:
    response = http_client.post("/api/rooms", json={"grid_number": PUBLISHED_NUMBER})

    assert set(response.json()) == {"code", "share_url"}
    assert "TAMIS" not in response.text
    assert "cells" not in response.text


def test_ac1_two_posts_create_two_rooms(
    http_client: TestClient, recording_registry: RecordingRegistry
) -> None:
    first = http_client.post("/api/rooms", json={"grid_number": PUBLISHED_NUMBER})
    second = http_client.post("/api/rooms", json={"grid_number": PUBLISHED_NUMBER})

    assert first.json()["code"] != second.json()["code"]
    assert len(recording_registry.created) == 2


@pytest.mark.parametrize(
    "number", [UNPUBLISHED_NUMBER, UNKNOWN_NUMBER], ids=["unpublished", "unknown"]
)
def test_ac1_post_for_a_grid_not_published_is_404(
    http_client: TestClient, recording_registry: RecordingRegistry, number: int
) -> None:
    response = http_client.post("/api/rooms", json={"grid_number": number})

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert recording_registry.created == []


@pytest.mark.parametrize(
    "raw_body",
    [
        '{"grid_number": "2"}',
        '{"grid_number": 0}',
        '{"grid_number": -1}',
        "{}",
        '{"grid_number": 2, "x": 1}',
        "not json",
    ],
    ids=["string", "zero", "negative", "missing", "extra-key", "not-json"],
)
def test_ac1_post_with_an_invalid_body_is_422_and_creates_nothing(
    http_client: TestClient, recording_registry: RecordingRegistry, raw_body: str
) -> None:
    response = http_client.post(
        "/api/rooms",
        content=raw_body,
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert isinstance(detail, list)
    assert len(detail) >= 1
    assert recording_registry.created == []


def test_ac1_get_on_api_rooms_is_still_404_json(http_client: TestClient) -> None:
    response = http_client.get("/api/rooms")

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_ac1_other_methods_on_api_rooms_are_405(
    http_client: TestClient, method: str
) -> None:
    response = http_client.request(method, "/api/rooms")

    assert response.status_code == 405


def test_ac1_post_with_a_trailing_slash_is_404_without_redirect(
    http_client: TestClient, recording_registry: RecordingRegistry
) -> None:
    response = http_client.post(
        "/api/rooms/", json={"grid_number": PUBLISHED_NUMBER}, follow_redirects=False
    )

    assert response.status_code == 404
    assert response.json() == NOT_FOUND_BODY
    assert recording_registry.created == []


def test_ac1_create_room_request_model_is_strict() -> None:
    assert CreateRoomRequest(grid_number=2).grid_number == 2
    with pytest.raises(ValidationError):
        CreateRoomRequest.model_validate({"grid_number": "2"})
    with pytest.raises(ValidationError):
        CreateRoomRequest.model_validate({"grid_number": 0})
    with pytest.raises(ValidationError):
        CreateRoomRequest.model_validate({"grid_number": 2, "x": 1})


def test_ac1_server_reexports_the_hub_registry() -> None:
    assert nock.server.RoomRegistry is nock.hub.RoomRegistry


def test_ac1_registry_defaults_and_injection(fake_clock: FakeClock) -> None:
    default_registry = RoomRegistry()
    injected_config = RoomConfig(tick_seconds=0.05)
    injected_registry = RoomRegistry(clock=fake_clock, config=injected_config)
    try:
        assert default_registry.config == RoomConfig()
        assert default_registry.clock is time.time
        assert injected_registry.config == injected_config
        assert injected_registry.clock is fake_clock
    finally:
        default_registry.close()
        injected_registry.close()


def test_ac1_room_config_defaults_are_the_backlog_values() -> None:
    config = RoomConfig()

    assert config.idle_after_seconds == 120.0
    assert config.host_handover_seconds == 60.0
    assert config.silence_timeout_seconds == 6.0
    assert config.resume_window_seconds == 300.0
    assert config.max_edits_per_second == 20
    assert config.snapshot_every == 100
    assert config.tick_seconds == 1.0


def test_ac1_room_config_rejects_out_of_range_values() -> None:
    with pytest.raises(ValidationError):
        RoomConfig.model_validate({"tick_seconds": 0})
    with pytest.raises(ValidationError):
        RoomConfig.model_validate({"max_edits_per_second": 0})
    with pytest.raises(ValidationError):
        RoomConfig.model_validate({"snapshot_every": 0})
    with pytest.raises(ValidationError):
        RoomConfig.model_validate({"unknown_field": 1})


def test_ac1_defaults_of_the_room_module() -> None:
    assert MAX_PLAYERS == 8
    assert RevealBudget(letters=5, words=1) == DEFAULT_REVEAL_BUDGET
    assert (
        RoomSettings(
            help_mode=HelpMode.FREE,
            reveal_budget=RevealBudget(letters=5, words=1),
            locked=False,
        )
        == DEFAULT_SETTINGS
    )


def test_ac1_new_room_is_fresh(fx01_grid: Grid) -> None:
    state = new_room("ABCDEF", fx01_grid, START_TIME, grid_number=2)

    assert state.code == "ABCDEF"
    assert state.grid == fx01_grid
    assert state.grid_number == 2
    assert state.created_at == START_TIME
    assert state.seq == 0
    assert state.players == ()
    assert state.settings == DEFAULT_SETTINGS
    assert state.reveal_budget == DEFAULT_REVEAL_BUDGET
    assert state.removed_tokens == ()
    assert state.solved is False


def test_ac1_new_room_grid_number_defaults_to_none(fx01_grid: Grid) -> None:
    assert fresh_state(fx01_grid).grid_number is None


def test_ac1_new_room_has_one_empty_cell_per_letter_cell(fx01_grid: Grid) -> None:
    state = fresh_state(fx01_grid)

    expected_positions = [
        (cell.row, cell.column) for cell in letter_cells_of(fx01_grid)
    ]
    assert len(expected_positions) > 0
    assert [(cell.row, cell.column) for cell in state.cells] == expected_positions
    for cell in state.cells:
        assert cell == CellState(row=cell.row, column=cell.column)


@pytest.mark.parametrize("bad_code", ["ABCDE", "ABCDEFG", "abcdef", "ABC-EF", ""])
def test_ac1_new_room_rejects_a_code_that_breaks_the_pattern(
    fx01_grid: Grid, bad_code: str
) -> None:
    with pytest.raises(ValidationError):
        new_room(bad_code, fx01_grid, START_TIME)


def test_ac1_grid_state_of_a_fresh_room_is_the_fresh_grid_view(
    fx01_grid: Grid,
) -> None:
    assert grid_state(fresh_state(fx01_grid)) == grid_view(fx01_grid)


def test_ac1_grid_state_carries_the_letters_of_the_cells(fx01_grid: Grid) -> None:
    state = fresh_state(fx01_grid)
    first = state.cells[0]
    filled = first.model_copy(
        update={
            "letter": "T",
            "pencil": True,
            "author": "p1",
            "locked": True,
            "revealed": True,
            "wrong": True,
        }
    )
    state = state.model_copy(update={"cells": (filled, *state.cells[1:])})

    view = grid_state(state)

    fresh_view = grid_view(fx01_grid)
    expected_cells: list[CellView] = []
    for cell_view in fresh_view.cells:
        if cell_view.row == first.row and cell_view.column == first.column:
            expected_cells.append(
                LetterCellView(
                    row=first.row,
                    column=first.column,
                    letter="T",
                    pencil=True,
                    author="p1",
                    locked=True,
                    revealed=True,
                    wrong=True,
                )
            )
        else:
            expected_cells.append(cell_view)
    assert view == GridView(
        width=fresh_view.width, height=fresh_view.height, cells=tuple(expected_cells)
    )


def test_ac1_grid_state_never_holds_an_answer(fx01_grid: Grid) -> None:
    text = grid_state(fresh_state(fx01_grid)).model_dump_json()

    assert "answer" not in text
    assert "TAMIS" not in text


def test_ac1_registry_registers_a_room_state_on_the_clock(
    fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    registry = RoomRegistry(clock=fake_clock)
    try:
        code = registry.register_room(fx01_grid, grid_number=7)

        state = registry.room_state(code)
        assert state is not None
        assert state.created_at == START_TIME
        assert state.grid_number == 7
        assert state.seq == 0
        assert registry.find_room(code) == fx01_grid
    finally:
        registry.close()


def test_ac1_unknown_room_has_no_grid_and_no_state() -> None:
    registry = RoomRegistry()
    try:
        assert registry.find_room(UNKNOWN_CODE) is None
        assert registry.room_state(UNKNOWN_CODE) is None
    finally:
        registry.close()


def test_ac1_room_state_returns_the_same_object_between_steps(
    fx01_grid: Grid,
) -> None:
    registry = RoomRegistry()
    try:
        code = registry.register_room(fx01_grid)
        first = registry.room_state(code)
        second = registry.room_state(code)
        assert first is not None
        assert first is second
    finally:
        registry.close()


def test_ac1_add_room_returns_the_state_given(fx01_grid: Grid) -> None:
    registry = RoomRegistry()
    try:
        state = fresh_state(fx01_grid, "ABCDEF")
        registry.add_room(state)

        assert registry.room_state("ABCDEF") is state
        assert registry.find_room("ABCDEF") == fx01_grid
    finally:
        registry.close()


def test_ac1_close_is_idempotent_and_stops_register_room(fx01_grid: Grid) -> None:
    registry = RoomRegistry()
    registry.register_room(fx01_grid)

    registry.close()
    registry.close()

    with pytest.raises(RuntimeError):
        registry.register_room(fx01_grid)


def test_ac1_fr_json_has_the_share_keys() -> None:
    fr = load_fr()

    assert fr["room.share.label"] == EXPECTED_FR_VALUES["room.share.label"]
    assert fr["room.share.copy"] == EXPECTED_FR_VALUES["room.share.copy"]
    assert fr["room.share.copied"] == EXPECTED_FR_VALUES["room.share.copied"]


# ---- AC-1: browser ----------------------------------------------------------


def open_fx01_room(
    enter_room: EnterRoom,
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
) -> str:
    """Register FX-01, enter the room and return the room's expected link."""
    code = room_registry.register_room(fx01_grid)
    link = f"{live_server}/r/{code}"
    enter_room(page, link)
    return link


def test_ac1_browser_share_link_points_at_the_room(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    link = open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
    fr = load_fr()

    expect(page.get_by_test_id("share-panel")).to_be_visible()
    share_link = page.get_by_test_id("share-link")
    expect(share_link).to_have_attribute("href", link)
    expect(share_link).to_have_text(link)
    expect(page.get_by_test_id("copy-link")).to_have_text(fr["room.share.copy"])
    assert share_link.evaluate("element => element.tagName") == "A"


def test_ac1_browser_share_panel_is_absent_on_an_unknown_room(
    page: Page, live_server: str
) -> None:
    page.goto(f"{live_server}/r/{UNKNOWN_CODE}")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "not_found")
    expect(page.get_by_test_id("share-panel")).to_have_count(0)
    expect(page.get_by_test_id("share-link")).to_have_count(0)
    expect(page.get_by_test_id("copy-link")).to_have_count(0)


@pytest.fixture
def clipboard_page(browser: Browser) -> Iterator[Page]:
    context = browser.new_context(permissions=["clipboard-read", "clipboard-write"])
    try:
        yield context.new_page()
    finally:
        context.close()


@pytest.mark.only_browser("chromium")
def test_ac1_browser_copy_link_puts_the_link_in_the_clipboard(
    clipboard_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    link = open_fx01_room(
        enter_room, clipboard_page, live_server, room_registry, fx01_grid
    )
    fr = load_fr()
    copy_button = clipboard_page.get_by_test_id("copy-link")

    copy_button.click()

    expect(copy_button).to_have_text(fr["room.share.copied"])
    assert clipboard_page.evaluate("navigator.clipboard.readText()") == link
    expect(copy_button).to_have_text(fr["room.share.copy"], timeout=4000)


def clipboard_page_with(browser: Browser, init_script: str) -> BrowserContext:
    context = browser.new_context()
    context.add_init_script(init_script)
    return context


@pytest.mark.parametrize(
    "init_script",
    [
        "Object.defineProperty(navigator, 'clipboard', {value: undefined});",
        "Object.defineProperty(navigator, 'clipboard', {value: "
        "{writeText: () => Promise.reject(new Error('refused'))}});",
    ],
    ids=["missing", "refusing"],
)
def test_ac1_browser_copy_does_nothing_without_a_usable_clipboard(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    init_script: str,
    enter_room: EnterRoom,
) -> None:
    context = clipboard_page_with(browser, init_script)
    try:
        page = context.new_page()
        link = open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
        fr = load_fr()
        copy_button = page.get_by_test_id("copy-link")

        copy_button.click()
        page.wait_for_timeout(SETTLE_MS)

        expect(copy_button).to_have_text(fr["room.share.copy"])
        expect(page.get_by_test_id("share-link")).to_have_text(link)
    finally:
        context.close()


# ---- AC-2: browser, phone and desktop ---------------------------------------


@pytest.fixture(params=["phone", "desktop"])
def device_page(
    request: pytest.FixtureRequest, browser: Browser, browser_name: str
) -> Iterator[Page]:
    """A page in the phone context, then in the desktop context."""
    if request.param == "desktop":
        context = browser.new_context(viewport=DESKTOP_VIEWPORT)
    elif browser_name == "firefox":
        context = browser.new_context(viewport=PHONE_VIEWPORT, has_touch=True)
    else:
        context = browser.new_context(
            viewport=PHONE_VIEWPORT, has_touch=True, is_mobile=True
        )
    try:
        yield context.new_page()
    finally:
        context.close()


def test_ac2_browser_link_opens_the_room_on_the_grid(
    device_page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)

    enter_room(device_page, f"{live_server}/r/{code}")

    room = device_page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-grid", "5x5")
    grid = device_page.get_by_test_id("grid")
    expect(grid).to_be_visible()
    expect(grid.get_by_test_id("cell")).to_have_count(25)


def test_ac2_browser_share_link_opens_in_a_second_context(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
    link = page.get_by_test_id("share-link").get_attribute("href")
    assert link is not None
    friend_context = browser.new_context(viewport=PHONE_VIEWPORT)
    try:
        friend_page = friend_context.new_page()

        enter_room(friend_page, link, nickname="Bob")

        friend_room = friend_page.get_by_test_id("room-page")
        expect(friend_room).to_have_attribute("data-status", "joined")
        expect(friend_room).to_have_attribute("data-grid", "5x5")
    finally:
        friend_context.close()


# ---- AC-3: room codes -------------------------------------------------------


def test_ac3_code_alphabet_has_32_characters_without_look_alikes() -> None:
    assert ROOM_CODE_ALPHABET == "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    assert ROOM_CODE_LENGTH == 6
    assert len(set(ROOM_CODE_ALPHABET)) == 32
    for forbidden in "0O1I":
        assert forbidden not in ROOM_CODE_ALPHABET


@pytest.fixture
def thousand_codes(fx01_grid: Grid) -> Iterator[list[str]]:
    registry = RoomRegistry()
    try:
        codes = [registry.register_room(fx01_grid) for _ in range(1000)]
        yield codes
    finally:
        registry.close()


def test_ac3_a_thousand_codes_are_distinct_and_in_the_alphabet(
    thousand_codes: list[str],
) -> None:
    assert len(thousand_codes) == 1000
    assert len(set(thousand_codes)) == 1000
    for code in thousand_codes:
        assert CODE_PATTERN.match(code), code


def test_ac3_every_position_of_the_code_varies(thousand_codes: list[str]) -> None:
    for position in range(6):
        characters = {code[position] for code in thousand_codes}
        assert len(characters) >= 20, f"position {position}: {sorted(characters)}"


def test_ac3_codes_are_not_sequential(thousand_codes: list[str]) -> None:
    for previous, current in itertools.pairwise(thousand_codes):
        assert code_as_number(current) != code_as_number(previous) + 1


def test_ac3_add_room_with_a_taken_code_raises_and_keeps_the_room(
    fx01_grid: Grid, fx02_text: str
) -> None:
    registry = RoomRegistry()
    try:
        original = fresh_state(fx01_grid, "ABCDEF")
        registry.add_room(original)
        other_grid = Grid.model_validate_json(fx02_text)

        with pytest.raises(ValueError, match="ABCDEF"):
            registry.add_room(fresh_state(other_grid, "ABCDEF"))

        assert registry.room_state("ABCDEF") is original
        assert registry.find_room("ABCDEF") == fx01_grid
    finally:
        registry.close()


def test_ac3_register_room_never_returns_the_code_of_an_added_room(
    fx01_grid: Grid, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The first draw is the code of an existing room: it must be redrawn."""
    drawn_characters = iter("ABCDEF" + "GHJKLM")

    def scripted_choice(_alphabet: str) -> str:
        return next(drawn_characters)

    monkeypatch.setattr(nock.hub.secrets, "choice", scripted_choice)
    registry = RoomRegistry()
    try:
        original = fresh_state(fx01_grid, "ABCDEF")
        registry.add_room(original)

        code = registry.register_room(fx01_grid)

        assert code == "GHJKLM"
        assert registry.room_state("ABCDEF") is original
    finally:
        registry.close()


# ---- AC-3: throttle on the room socket --------------------------------------


def test_ac3_throttle_constants() -> None:
    assert THROTTLED_CLOSE_CODE == 4429
    assert WRONG_CODE_LIMIT == 10
    assert WRONG_CODE_WINDOW_SECONDS == 60.0


def test_ac3_the_eleventh_connection_is_refused_with_4429(
    ws_client: TestClient, room_code: str
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 10)

    assert close_code_on_first_read(ws_client, room_code) == 4429


def test_ac3_nine_wrong_codes_do_not_throttle(
    ws_client: TestClient, room_code: str
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 9)

    snapshot = join_and_get_snapshot(ws_client, room_code)
    assert snapshot.seq == 1


def test_ac3_after_a_minute_the_connection_is_accepted(
    ws_client: TestClient, room_code: str, fake_clock: FakeClock
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 10)
    assert close_code_on_first_read(ws_client, room_code) == 4429

    fake_clock.advance(60)

    snapshot = join_and_get_snapshot(ws_client, room_code)
    assert snapshot.seq == 1
    assert len(snapshot.players) == 1


def test_ac3_window_edge_59_9_refused_and_60_accepted(
    ws_client: TestClient, room_code: str, fake_clock: FakeClock
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 10)

    fake_clock.now = START_TIME + 59.9
    assert close_code_on_first_read(ws_client, room_code) == 4429

    fake_clock.now = START_TIME + 60.0
    snapshot = join_and_get_snapshot(ws_client, room_code)
    assert snapshot.seq == 1


def test_ac3_throttle_applies_to_a_code_that_does_not_exist(
    ws_client: TestClient,
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 10)

    assert close_code_on_first_read(ws_client, "YYYYYY") == 4429
    assert close_code_on_first_read(ws_client, UNKNOWN_CODE) == 4429


def test_ac3_refused_connections_do_not_extend_the_window(
    ws_client: TestClient, room_code: str, fake_clock: FakeClock
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 10)
    fake_clock.now = START_TIME + 50.0
    for _ in range(10):
        assert close_code_on_first_read(ws_client, room_code) == 4429

    fake_clock.now = START_TIME + 60.0

    assert join_and_get_snapshot(ws_client, room_code).seq == 1


def test_ac3_the_window_slides(
    ws_client: TestClient, room_code: str, fake_clock: FakeClock
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 5)
    fake_clock.now = START_TIME + 30.0
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 5)
    assert close_code_on_first_read(ws_client, room_code) == 4429

    fake_clock.now = START_TIME + 60.0

    assert join_and_get_snapshot(ws_client, room_code).seq == 1


@pytest.mark.parametrize(
    ("first_batch_at", "second_batch_at"),
    [(50.0, 70.0), (10.0, 30.0)],
    ids=["across-60s-from-start", "across-an-aligned-minute"],
)
def test_ac3_failures_in_a_sliding_window_add_up_across_fixed_windows(
    ws_client: TestClient,
    room_code: str,
    fake_clock: FakeClock,
    first_batch_at: float,
    second_batch_at: float,
) -> None:
    """5 and 5 failures within 60 s block, wherever fixed windows would cut."""
    fake_clock.now = START_TIME + first_batch_at
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 5)
    fake_clock.now = START_TIME + second_batch_at
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 5)

    fake_clock.now = START_TIME + second_batch_at + 5.0

    assert close_code_on_first_read(ws_client, room_code) == 4429


def test_ac3_failures_older_than_the_window_do_not_add_up(
    ws_client: TestClient, room_code: str, fake_clock: FakeClock
) -> None:
    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 9)
    fake_clock.now = START_TIME + 61.0

    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE])

    assert join_and_get_snapshot(ws_client, room_code).seq == 1


def test_ac3_valid_codes_never_add_a_failure(
    ws_client: TestClient, room_code: str
) -> None:
    first = join_and_get_snapshot(ws_client, room_code)
    for _ in range(14):
        # Resume the same player: a ninth new player would find the room full.
        resumed = join_and_get_snapshot(ws_client, room_code, first.resume_token)
        assert resumed.you == first.you

    fail_with_wrong_codes(ws_client, [UNKNOWN_CODE] * 9)

    last = join_and_get_snapshot(ws_client, room_code, first.resume_token)
    assert last.you == first.you


def test_ac3_mistyped_and_malformed_codes_count_as_wrong_codes(
    ws_client: TestClient, room_code: str
) -> None:
    wrong_codes = ["AB0O1I", "ABCDE0", "IIIIII", "OOOOOO", "111111"]
    wrong_codes += ["abc", "abc", "abc", "toolongcode", "x"]
    fail_with_wrong_codes(ws_client, wrong_codes)

    assert close_code_on_first_read(ws_client, room_code) == 4429


def test_ac3_http_page_requests_are_never_counted(
    ws_client: TestClient, room_code: str
) -> None:
    for _ in range(15):
        response = ws_client.get(f"/r/{UNKNOWN_CODE}")
        assert response.status_code == 200

    assert join_and_get_snapshot(ws_client, room_code).seq == 1


def test_ac3_the_throttle_is_per_address(
    clock_registry: RoomRegistry, room_code: str, dist_dir: Path
) -> None:
    app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with (
        TestClient(app, client=("10.0.0.1", 50000)) as noisy_client,
        TestClient(app, client=("10.0.0.2", 50000)) as quiet_client,
    ):
        fail_with_wrong_codes(noisy_client, [UNKNOWN_CODE] * 10)

        assert close_code_on_first_read(noisy_client, room_code) == 4429
        assert join_and_get_snapshot(quiet_client, room_code).seq == 1


def test_ac3_each_app_has_its_own_failures(
    clock_registry: RoomRegistry, room_code: str, dist_dir: Path
) -> None:
    first_app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    second_app = create_app(rooms=clock_registry, dist_dir=dist_dir)
    with TestClient(first_app) as first_client, TestClient(second_app) as second_client:
        fail_with_wrong_codes(first_client, [UNKNOWN_CODE] * 10)

        assert close_code_on_first_read(first_client, room_code) == 4429
        assert join_and_get_snapshot(second_client, room_code).seq == 1


# ---- AC-3: browser, throttled ----------------------------------------------


def test_ac3_browser_4429_makes_the_room_throttled(
    page: Page, live_server: str
) -> None:
    routes: list[WebSocketRoute] = []

    def refuse(route: WebSocketRoute) -> None:
        routes.append(route)
        route.on_message(lambda _message: route.close(code=4429))

    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), refuse)
    # A stored identity (spec 012) makes the page send its join at once.
    page.context.add_init_script(STORED_IDENTITY_SCRIPT)
    page.goto(f"{live_server}/r/ABC123")

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "throttled", timeout=WAIT_TIMEOUT_MS)
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.throttled"]
    )
    expect(page.get_by_test_id("share-panel")).to_have_count(0)
    page.wait_for_timeout(1500)
    assert len(routes) == 1
    expect(room).to_have_attribute("data-status", "throttled")


def test_ac3_fr_json_has_the_throttled_text() -> None:
    fr = load_fr()

    assert fr["room.status.throttled"] == EXPECTED_FR_VALUES["room.status.throttled"]


# ---- AC-4: the runtime guarantees of the room engine ------------------------

TICK_SECONDS = 0.05
ENGINE_WAIT_SECONDS = 5.0
POLL_SECONDS = 0.01
SETTLE_SECONDS = 0.4
LONG_TICK_SECONDS = 30.0
ENGINE_THREAD_PREFIX = "nock-rooms"
SELECT_TEXT = '{"type": "select_cell", "row": 0, "column": 0, "direction": "across"}'
UNDO_TEXT = '{"type": "undo"}'
PING_TEXT = '{"type": "ping"}'
SHARED_TOKEN = "Z" * 32
RULE_ERROR_TEXT = "rule exploded"


def wait_until(condition: Callable[[], bool], what: str) -> None:
    """Poll `condition` for a few seconds and fail with `what` when it stays false."""
    deadline = time.monotonic() + ENGINE_WAIT_SECONDS
    while time.monotonic() < deadline:
        if condition():
            return
        time.sleep(POLL_SECONDS)
    pytest.fail(f"timed out after {ENGINE_WAIT_SECONDS}s waiting for: {what}")


def last_seq_of(registry: RoomRegistry, code: str) -> int:
    """Return the seq of the last event of room `code`."""
    state = registry.room_state(code)
    assert state is not None
    return state.seq


def letter_changed(seq: int, player_id: str) -> LetterChanged:
    return LetterChanged(
        seq=seq, row=0, column=0, letter="T", pencil=False, player_id=player_id
    )


def log_entry(seq: int, player_id: str) -> LogEntry:
    return LogEntry(at=START_TIME, event=letter_changed(seq, player_id))


class RuleRecorder:
    """Fakes of the three rule functions, which record each call in order.

    `events` holds "tick", "message:<player>" and "disconnect:<player>", and
    "raised:<rule>" when a fake raised on purpose.
    """

    def __init__(self) -> None:
        self.events: list[str] = []
        self.rule_to_break: str | None = None

    def count(self, prefix: str) -> int:
        matching = [event for event in self.events if event.startswith(prefix)]
        return len(matching)

    def break_first_call_of(self, rule: str) -> None:
        self.rule_to_break = rule

    def _record(self, rule: str, event: str) -> None:
        if self.rule_to_break == rule:
            self.rule_to_break = None
            self.events.append(f"raised:{rule}")
            raise RuntimeError(RULE_ERROR_TEXT)
        self.events.append(event)

    def tick(
        self, state: RoomState, now: float, config: RoomConfig | None = None
    ) -> Outcome:
        self._record("tick", "tick")
        return Outcome(state=state)

    def disconnect_player(
        self, state: RoomState, player_id: str, now: float
    ) -> Outcome:
        self._record("disconnect_player", f"disconnect:{player_id}")
        return Outcome(state=state)

    def handle_message(
        self,
        state: RoomState,
        player_id: str,
        message: ClientMessage,
        now: float,
        config: RoomConfig | None = None,
    ) -> Outcome:
        """Select: two events, a reply and a selection. Undo: one event.

        Entries follow the room's last seq, as the real rules number them.
        """
        self._record("handle_message", f"message:{player_id}")
        if message.type == "select_cell":
            first = state.seq + 1
            return Outcome(
                state=state.model_copy(update={"seq": first + 1}),
                entries=(log_entry(first, player_id), log_entry(first + 1, player_id)),
                reply=(Pong(),),
                to_others=(SelectionMoved(player_id=player_id, selection=None),),
            )
        if message.type == "undo":
            seq = state.seq + 1
            return Outcome(
                state=state.model_copy(update={"seq": seq}),
                entries=(log_entry(seq, player_id),),
            )
        return Outcome(state=state)


@pytest.fixture
def recorder(monkeypatch: pytest.MonkeyPatch) -> RuleRecorder:
    """Replace the rule functions by recording fakes.

    `nock.hub` imports the rules by name (`from nock.room import tick, ...`), so
    the names to patch are the ones in `nock.hub`. The `nock.room` names are
    patched too, in case the hub ever calls the rules through the module.
    """
    fakes = RuleRecorder()
    monkeypatch.setattr(nock.room, "tick", fakes.tick)
    monkeypatch.setattr(nock.room, "handle_message", fakes.handle_message)
    monkeypatch.setattr(nock.room, "disconnect_player", fakes.disconnect_player)
    monkeypatch.setattr(nock.hub, "tick", fakes.tick, raising=False)
    monkeypatch.setattr(nock.hub, "handle_message", fakes.handle_message, raising=False)
    monkeypatch.setattr(
        nock.hub, "disconnect_player", fakes.disconnect_player, raising=False
    )
    return fakes


@contextlib.contextmanager
def running_room(
    grid: Grid, dist_dir: Path, tick_seconds: float = TICK_SECONDS
) -> Iterator[tuple[TestClient, RoomRegistry, str]]:
    """Yield a client, its registry and the code of one room; close it all."""
    registry = RoomRegistry(config=RoomConfig(tick_seconds=tick_seconds))
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            yield client, registry, code
    finally:
        registry.close()


def open_and_join(
    stack: contextlib.ExitStack, client: TestClient, code: str
) -> tuple[WebSocketTestSession, str]:
    """Open a socket in `stack`, join, and return it with its player id."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    websocket.send_text(JOIN_TEXT)
    snapshot = parse_server_message(receive_text_or_fail(websocket))
    assert isinstance(snapshot, Snapshot)
    return websocket, snapshot.you


def join_and_sync(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    recorder: RuleRecorder,
) -> tuple[WebSocketTestSession, str]:
    """Like `open_and_join`, then wait until the room has attached the socket.

    A ping is the barrier: the room applies inputs in order, so once the rules
    saw the ping, the attach that came before it was applied too.
    """
    websocket, player_id = open_and_join(stack, client, code)
    seen_before = recorder.count("message:")
    websocket.send_text(PING_TEXT)
    wait_until(
        lambda: recorder.count("message:") > seen_before,
        "the room to apply the ping of a new connection",
    )
    return websocket, player_id


def receive_message(websocket: WebSocketTestSession) -> object:
    return parse_server_message(receive_text_or_fail(websocket))


def skip_player_joined(websocket: WebSocketTestSession, count: int) -> None:
    """Read the `player_joined` events that later joins sent to this socket."""
    for _ in range(count):
        assert isinstance(receive_message(websocket), PlayerJoined)


def engine_threads() -> list[threading.Thread]:
    """The live threads named like the engine's."""
    threads: list[threading.Thread] = []
    for thread in threading.enumerate():
        if thread.name.startswith(ENGINE_THREAD_PREFIX):
            threads.append(thread)
    return threads


def test_ac4_tick_runs_repeatedly_while_a_connection_is_attached(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, _registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)

        wait_until(lambda: recorder.count("tick") >= 5, "5 ticks while attached")


def test_ac4_tick_stops_once_every_connection_has_left(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, _registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)
        wait_until(lambda: recorder.count("tick") >= 2, "ticks while attached")
        stack.close()
        wait_until(
            lambda: recorder.count("disconnect:") == 1,
            "the room to apply the departure",
        )
        time.sleep(TICK_SECONDS * 2)
        ticks_after_leaving = recorder.count("tick")

        time.sleep(SETTLE_SECONDS)

        assert recorder.count("tick") == ticks_after_leaving


def test_ac4_events_reach_everyone_then_the_reply_then_to_others(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        sender, sender_id = join_and_sync(stack, client, code, recorder)
        first_other, _ = join_and_sync(stack, client, code, recorder)
        second_other, _ = join_and_sync(stack, client, code, recorder)
        skip_player_joined(sender, 2)
        skip_player_joined(first_other, 1)
        last_seq = last_seq_of(registry, code)

        sender.send_text(SELECT_TEXT)

        assert receive_message(sender) == letter_changed(last_seq + 1, sender_id)
        assert receive_message(sender) == letter_changed(last_seq + 2, sender_id)
        assert receive_message(sender) == Pong()
        moved = SelectionMoved(player_id=sender_id, selection=None)
        for other in [first_other, second_other]:
            assert receive_message(other) == letter_changed(last_seq + 1, sender_id)
            assert receive_message(other) == letter_changed(last_seq + 2, sender_id)
            assert receive_message(other) == moved


def test_ac4_the_sender_does_not_receive_to_others_nor_the_others_a_reply(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    """After a select, the next thing every socket gets is the next event."""
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        sender, sender_id = join_and_sync(stack, client, code, recorder)
        other, _ = join_and_sync(stack, client, code, recorder)
        skip_player_joined(sender, 1)
        last_seq = last_seq_of(registry, code)
        sender.send_text(SELECT_TEXT)
        for _ in range(3):
            receive_message(sender)
            receive_message(other)

        sender.send_text(UNDO_TEXT)

        assert receive_message(sender) == letter_changed(last_seq + 3, sender_id)
        assert receive_message(other) == letter_changed(last_seq + 3, sender_id)


def test_ac4_the_task_stops_and_a_new_one_ticks_before_any_input(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    """A tick every 30 s never fires here: only the start of a task ticks."""
    with running_room(fx01_grid, dist_dir, LONG_TICK_SECONDS) as (
        client,
        _registry,
        code,
    ):
        with contextlib.ExitStack() as first_stack:
            join_and_sync(first_stack, client, code, recorder)
        wait_until(
            lambda: recorder.count("disconnect:") == 1,
            "the room to apply the departure",
        )
        time.sleep(SETTLE_SECONDS)
        events_before = list(recorder.events)
        assert events_before.count("tick") == 1

        with contextlib.ExitStack() as second_stack:
            join_and_sync(second_stack, client, code, recorder)

        new_events = recorder.events[len(events_before) :]
        assert new_events[0] == "tick"
        assert new_events[1].startswith("message:")
        assert new_events.count("tick") == 1


@pytest.mark.parametrize("broken_rule", ["handle_message", "tick", "disconnect_player"])
def test_ac4_a_raising_rule_is_logged_and_the_room_goes_on(
    recorder: RuleRecorder,
    fx01_grid: Grid,
    dist_dir: Path,
    caplog: pytest.LogCaptureFixture,
    broken_rule: str,
) -> None:
    recorder.break_first_call_of(broken_rule)
    caplog.set_level(logging.ERROR)
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        stay, stay_id = open_and_join(stack, client, code)
        state_before = registry.room_state(code)
        if broken_rule == "handle_message":
            stay.send_text(UNDO_TEXT)
        if broken_rule == "disconnect_player":
            with contextlib.ExitStack() as leaving:
                open_and_join(leaving, client, code)
                state_before = registry.room_state(code)
            skip_player_joined(stay, 1)
        wait_until(
            lambda: f"raised:{broken_rule}" in recorder.events,
            f"{broken_rule} to be called and to raise",
        )
        assert registry.room_state(code) is state_before
        ticks_at_error = recorder.count("tick")
        wait_until(
            lambda: recorder.count("tick") >= ticks_at_error + 3,
            "the room to keep ticking after the error",
        )

        last_seq = last_seq_of(registry, code)
        stay.send_text(SELECT_TEXT)

        assert receive_message(stay) == letter_changed(last_seq + 1, stay_id)
        assert receive_message(stay) == letter_changed(last_seq + 2, stay_id)
        assert receive_message(stay) == Pong()

    assert RULE_ERROR_TEXT in caplog.text
    error_loggers = [
        record.name for record in caplog.records if record.levelno >= logging.ERROR
    ]
    # asyncio logs a task that died with an error; the engine must log it itself.
    engine_loggers = [name for name in error_loggers if name != "asyncio"]
    assert engine_loggers != []


@pytest.fixture
def one_player_id(monkeypatch: pytest.MonkeyPatch) -> str:
    """Make the server give every connection the same player id.

    The hub draws the ids of a snapshot with `secrets.token_urlsafe`;
    a constant that fits both the player id and the resume token patterns makes
    two sockets attach under one player id.
    """

    def constant_token(_nbytes: int | None = None) -> str:
        return SHARED_TOKEN

    monkeypatch.setattr(nock.hub.secrets, "token_urlsafe", constant_token)
    return SHARED_TOKEN


def test_ac4_two_connections_of_one_player_both_receive(
    recorder: RuleRecorder, one_player_id: str, fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        first, first_id = join_and_sync(stack, client, code, recorder)
        second, second_id = join_and_sync(stack, client, code, recorder)
        assert first_id == second_id == one_player_id
        skip_player_joined(first, 1)

        last_seq = last_seq_of(registry, code)
        first.send_text(UNDO_TEXT)

        undone = letter_changed(last_seq + 1, one_player_id)
        assert receive_message(first) == undone
        assert receive_message(second) == undone


@pytest.mark.parametrize("leaver", ["first", "second"])
def test_ac4_detaching_one_connection_keeps_the_other_one(
    recorder: RuleRecorder,
    one_player_id: str,
    fx01_grid: Grid,
    dist_dir: Path,
    leaver: str,
) -> None:
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stay_stack,
    ):
        with contextlib.ExitStack() as leave_stack:
            if leaver == "first":
                join_and_sync(leave_stack, client, code, recorder)
                stay, _ = join_and_sync(stay_stack, client, code, recorder)
            else:
                stay, _ = join_and_sync(stay_stack, client, code, recorder)
                join_and_sync(leave_stack, client, code, recorder)
                skip_player_joined(stay, 1)
        # Leaving the inner stack closed a socket, and its departure was
        # posted before this ping, which the room applies in order.
        seen_before = recorder.count("message:")
        stay.send_text(PING_TEXT)
        wait_until(
            lambda: recorder.count("message:") > seen_before,
            "the room to apply the ping after the departure",
        )

        last_seq = last_seq_of(registry, code)
        stay.send_text(UNDO_TEXT)

        assert receive_message(stay) == letter_changed(last_seq + 1, one_player_id)


def test_ac4_close_stops_the_engine_thread_and_is_idempotent(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    threads_before = set(engine_threads())
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        join_and_sync(stack, client, code, recorder)
        started = [t for t in engine_threads() if t not in threads_before]
        assert len(started) == 1

        stack.close()
        registry.close()
        started[0].join(timeout=ENGINE_WAIT_SECONDS)
        assert not started[0].is_alive()
        registry.close()

    still_alive = [t for t in engine_threads() if t not in threads_before]
    assert still_alive == []


def test_ac4_an_input_after_close_is_refused_without_a_task(
    recorder: RuleRecorder, fx01_grid: Grid, dist_dir: Path
) -> None:
    threads_before = set(engine_threads())
    with (
        running_room(fx01_grid, dist_dir) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        websocket, _ = join_and_sync(stack, client, code, recorder)
        registry.close()
        events_after_close = list(recorder.events)

        websocket.send_text(SELECT_TEXT)
        websocket.send_text(UNDO_TEXT)
        time.sleep(SETTLE_SECONDS)

        assert recorder.events == events_after_close

    assert [t for t in engine_threads() if t not in threads_before] == []
