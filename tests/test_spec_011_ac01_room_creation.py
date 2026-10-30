"""Tests of spec 011, AC-1: creating a room gives a share link and a room code.

The HTTP route `POST /api/rooms`, the registry and the room module it relies on,
and the share panel of the page (all three engines; the clipboard in Chromium).
The shared setup is in `spec011_harness`.

Refined by spec 043 (the design's room layout): `share-panel` sits in the Salon's
Joueurs tab, so the browser tests open it with `show_tab(page, "players")` (spec
043's "Test harness") before they look at it or click in it; after a copy the
green line `share-copied` shows `fr.json["room.share.copied"]` while `copy-link`
keeps its text.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, BrowserContext, Page, expect
from pydantic import ValidationError

import nock.hub
import nock.server
from nock.catalogue import Catalogue
from nock.grid import Grid, LetterCell
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    GridView,
    HelpMode,
    LetterCellView,
    RevealBudget,
    RoomSettings,
    grid_view,
)
from nock.room import (
    DEFAULT_REVEAL_BUDGET,
    DEFAULT_SETTINGS,
    MAX_PLAYERS,
    CellState,
    RoomConfig,
    grid_state,
    new_room,
)
from nock.server import CreateRoomRequest, CreateRoomResponse, create_app
from room_panels import show_tab
from spec011_harness import (
    CODE_PATTERN,
    EXPECTED_FR_VALUES,
    PUBLISHED_NUMBER,
    START_TIME,
    UNKNOWN_CODE,
    UNPUBLISHED_NUMBER,
    EnterRoom,
    FakeClock,
    build_catalogue,
    fresh_state,
    grid_from_text,
    load_fr,
    make_dist_dir,
    open_fx01_room,
)

NOT_FOUND_BODY = {"detail": "Not Found"}
SETTLE_MS = 500
UNKNOWN_NUMBER = 99


# ---- Fixtures and helpers ----------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue with FX-01 as published entry 2 and as unpublished entry 4.

    The conftest `live_server` serves this catalogue, so keep the fixture even in
    a file whose tests never name it.
    """
    return build_catalogue(fx01_grid)


class RecordingRegistry(RoomRegistry):
    """A real registry that remembers each room creation it was asked for."""

    def __init__(self, *, clock: FakeClock | None = None) -> None:
        super().__init__(clock=clock)
        self.created: list[tuple[Grid, int | None]] = []

    def register_room(
        self,
        grid: Grid,
        grid_number: int | None = None,
        creator_account_id: str | None = None,
    ) -> str:
        self.created.append((grid, grid_number))
        return super().register_room(
            grid, grid_number=grid_number, creator_account_id=creator_account_id
        )


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


def letter_cells_of(grid: Grid) -> list[LetterCell]:
    letter_cells: list[LetterCell] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            letter_cells.append(cell)
    return letter_cells


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

        assert registry.room_state("ABCDEF") == state
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


def test_ac1_browser_share_link_points_at_the_room(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    link = open_fx01_room(enter_room, page, live_server, room_registry, fx01_grid)
    fr = load_fr()
    show_tab(page, "players")

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
    show_tab(clipboard_page, "players")
    copy_button = clipboard_page.get_by_test_id("copy-link")

    copy_button.click()

    copied = clipboard_page.get_by_test_id("share-copied")
    expect(copied).to_have_text(fr["room.share.copied"])
    expect(copied).to_have_attribute("role", "status")
    expect(copy_button).to_have_text(fr["room.share.copy"])
    assert clipboard_page.evaluate("navigator.clipboard.readText()") == link
    expect(copied).to_have_count(0, timeout=4000)


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
        show_tab(page, "players")
        copy_button = page.get_by_test_id("copy-link")

        copy_button.click()
        page.wait_for_timeout(SETTLE_MS)

        expect(copy_button).to_have_text(fr["room.share.copy"])
        expect(page.get_by_test_id("share-copied")).to_have_count(0)
        expect(page.get_by_test_id("share-link")).to_have_text(link)
    finally:
        context.close()
