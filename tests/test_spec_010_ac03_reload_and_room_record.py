"""Tests of spec 010, AC-3: a reload restores the letters and the selection.

The selection is kept in the room record `nock.room.<code>`: its writing, its
reading when it is valid, absent or corrupt. The shared setup is in
`spec010_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import SelectCell, parse_client_message
from spec010_harness import (
    CATALOGUE_RECORD,
    PROGRESS_KEY,
    ROOM_RECORD_KEY,
    EnterRoom,
    FrameRecorder,
    MockRoomSocket,
    catalogue_from_grid,
    cell_at,
    code_from_url,
    expect_joined,
    grid_from_text,
    load_fr,
    open_mock_room,
    read_json_object,
    read_storage,
    send_snapshot,
    settle,
    start_from_catalogue,
    submit_form,
    tap,
    wait_until,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1, force 2."""
    return catalogue_from_grid(fx01_grid)


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
    assert len(mock.frames_without_pings()) == 1


def test_ac3_a_null_saved_selection_selects_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: CATALOGUE_RECORD})
    mock.first_join()

    send_snapshot(mock, fx01_grid)

    settle(page)
    expect_nothing_selected(page)
    assert len(mock.frames_without_pings()) == 1


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
    assert mock.frames_without_pings() == []


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
