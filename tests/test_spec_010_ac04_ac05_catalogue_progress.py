"""Tests of spec 010, AC-4 and AC-5: the progress of a grid on this device.

AC-4: starting a grid marks it started in `nock.progress`. AC-5: solving it
marks it finished. The shared setup is in `spec010_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import GridSolved
from spec010_harness import (
    CATALOGUE_RECORD,
    PROGRESS_KEY,
    ROOM_RECORD_KEY,
    ROOM_URL_PATTERN,
    MockRoomSocket,
    catalogue_from_grid,
    code_from_url,
    expect_joined,
    grid_from_text,
    item_play_button,
    open_mock_room,
    read_json_object,
    read_storage,
    seed_local_storage,
    send_snapshot,
    settle,
    start_from_catalogue,
    submit_form,
    wait_for_storage,
    wait_until,
)

STARTED_PROGRESS = json.dumps({"1": "started"})


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1, force 2."""
    return catalogue_from_grid(fx01_grid)


def wait_for_progress(page: Page, expected: dict[str, str]) -> None:
    """Wait until `nock.progress` parses to exactly `expected`."""

    def has_expected() -> bool:
        raw = read_storage(page, PROGRESS_KEY)
        if raw is None:
            return False
        return json.loads(raw) == expected

    wait_until(page, has_expected)


def send_solved_event(mock: MockRoomSocket) -> None:
    event = GridSolved(seq=1, elapsed_ms=1000)
    mock.send(event.model_dump_json())


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
    page.wait_for_url(ROOM_URL_PATTERN)
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
