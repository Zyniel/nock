"""Tests of spec 010, AC-6: the creator joins at once, without a form.

The creator joins with the nickname saved on this device or the default guest
name; a stored identity or a bad record changes what the page does. The shared
setup is in `spec010_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import ErrorCode, ErrorMessage, Join
from spec010_harness import (
    CATALOGUE_RECORD,
    MOCK_CODE,
    MOCK_TOKEN,
    ROOM_RECORD_KEY,
    FrameRecorder,
    catalogue_from_grid,
    expect_joined,
    grid_from_text,
    load_fr,
    open_mock_room,
    read_json_object,
    read_storage,
    seed_local_storage,
    settle,
    start_from_catalogue,
    wait_for_storage,
)

NICKNAME_KEY = "nock.nickname"
IDENTITY_KEY = f"nock.identity.{MOCK_CODE}"
STORED_IDENTITY = json.dumps(
    {"player_id": "p7", "resume_token": MOCK_TOKEN, "nickname": "Ana 2"}
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1, force 2."""
    return catalogue_from_grid(fx01_grid)


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
    assert mock.frames_without_pings() == []


def test_ac6_a_record_without_a_grid_shows_the_form(
    page: Page, live_server: str
) -> None:
    record = json.dumps({"grid": None, "selection": None})
    mock = open_mock_room(page, live_server, {ROOM_RECORD_KEY: record})

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.frames_without_pings() == []


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
