"""Tests of spec 012, AC-6 and AC-7: the stored identity and the remembered nickname.

AC-6: when the room page joins at once. AC-7: what the page stores after a join.
The page is tested with spec 040's mocked socket and a seeded `localStorage`.
The shared setup is in `spec012_harness`.
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    Join,
    PlayerView,
    parse_client_message,
)
from spec012_harness import (
    MOCK_TOKEN,
    OTHER_TOKEN,
    WAIT_TIMEOUT_MS,
    active_view,
    error_frame,
    grid_from_text,
    load_fr,
    open_mock_room,
    settle,
    snapshot_frame,
    submit_form,
    wait_until,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


STORED_IDENTITY = json.dumps(
    {"player_id": "p1", "resume_token": MOCK_TOKEN, "nickname": "Ana 2"}
)
CATALOGUE_RECORD = json.dumps({"grid": 1, "selection": None})


# ---- Helpers for the browser -------------------------------------------------


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


# ---- AC-6: when the page joins at once ----------------------------------------------


def test_ac6_a_stored_identity_joins_at_once_with_its_token(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {"nock.identity.ABC123": STORED_IDENTITY})
    mock.wait_for_frames(1)

    assert parse_client_message(mock.frames_without_pings()[0]) == Join(
        nickname="Ana 2", resume_token=MOCK_TOKEN
    )
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joining"]
    )
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    settle(page)
    assert len(mock.frames_without_pings()) == 1


@pytest.mark.parametrize(
    "extra_items",
    [
        {"nock.room.ABC123": CATALOGUE_RECORD},
        {"nock.nickname": "Zo\u00e9"},
        {"nock.room.ABC123": CATALOGUE_RECORD, "nock.nickname": "Zo\u00e9"},
    ],
    ids=["with-room-record", "with-remembered-nickname", "with-both"],
)
def test_ac6_a_stored_identity_wins_over_the_record_and_the_remembered_nickname(
    page: Page, live_server: str, extra_items: dict[str, str]
) -> None:
    items = {"nock.identity.ABC123": STORED_IDENTITY, **extra_items}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    assert parse_client_message(mock.frames_without_pings()[0]) == Join(
        nickname="Ana 2", resume_token=MOCK_TOKEN
    )
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_catalogue_room_joins_at_once_with_the_remembered_nickname(
    page: Page, live_server: str
) -> None:
    items = {"nock.room.ABC123": CATALOGUE_RECORD, "nock.nickname": "Zo\u00e9"}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    assert parse_client_message(mock.frames_without_pings()[0]) == Join(
        nickname="Zo\u00e9", resume_token=None
    )
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


@pytest.mark.parametrize(
    "remembered",
    [None, "A", "Ana!", "--"],
    ids=["absent", "too-short", "bad-characters", "punctuation-only"],
)
def test_ac6_a_catalogue_room_without_a_valid_nickname_joins_as_the_default(
    page: Page, live_server: str, remembered: str | None
) -> None:
    items = {"nock.room.ABC123": CATALOGUE_RECORD}
    if remembered is not None:
        items["nock.nickname"] = remembered
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    assert parse_client_message(mock.frames_without_pings()[0]) == Join(
        nickname=load_fr()["room.default_nickname"], resume_token=None
    )
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


NO_JOIN_SCENARIOS = {
    "no-record": {},
    "grid-null": {"nock.room.ABC123": json.dumps({"grid": None, "selection": None})},
    "grid-string": {"nock.room.ABC123": json.dumps({"grid": "1", "selection": None})},
    "grid-missing": {"nock.room.ABC123": json.dumps({"selection": None})},
    "record-not-an-object": {"nock.room.ABC123": "[1]"},
    "record-not-json": {"nock.room.ABC123": "not json"},
    "identity-of-another-room": {"nock.identity.ZZZZZZ": STORED_IDENTITY},
}


@pytest.mark.parametrize("scenario", list(NO_JOIN_SCENARIOS))
def test_ac6_without_identity_or_catalogue_record_the_form_is_shown(
    page: Page, live_server: str, scenario: str
) -> None:
    mock = open_mock_room(page, live_server, NO_JOIN_SCENARIOS[scenario])

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(page.get_by_test_id("nickname-input")).to_have_value("")
    settle(page)
    assert mock.frames_without_pings() == []


def test_ac6_the_form_is_prefilled_with_the_remembered_nickname(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {"nock.nickname": "Zo\u00e9"})

    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "nickname"
    )
    expect(page.get_by_test_id("nickname-input")).to_have_value("Zo\u00e9")
    settle(page)
    assert mock.frames_without_pings() == []


CORRUPT_IDENTITIES = [
    "not json",
    "[]",
    json.dumps({"player_id": "p1"}),
    json.dumps({"player_id": "p1", "resume_token": "", "nickname": "Ana"}),
    json.dumps({"player_id": 5, "resume_token": MOCK_TOKEN, "nickname": "Ana"}),
]


@pytest.mark.parametrize("identity", CORRUPT_IDENTITIES)
def test_ac6_a_corrupt_identity_is_ignored_and_the_form_is_shown(
    page: Page, live_server: str, identity: str
) -> None:
    mock = open_mock_room(page, live_server, {"nock.identity.ABC123": identity})

    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "nickname"
    )
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.frames_without_pings() == []


@pytest.mark.parametrize("identity", CORRUPT_IDENTITIES)
def test_ac6_a_corrupt_identity_falls_back_to_the_catalogue_record(
    page: Page, live_server: str, identity: str
) -> None:
    items = {"nock.identity.ABC123": identity, "nock.room.ABC123": CATALOGUE_RECORD}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    assert parse_client_message(mock.frames_without_pings()[0]) == Join(
        nickname=load_fr()["room.default_nickname"], resume_token=None
    )
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac6_a_catalogue_creator_refused_by_the_server_gets_the_form(
    page: Page, live_server: str
) -> None:
    items = {"nock.room.ABC123": CATALOGUE_RECORD}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    mock.send(error_frame(ErrorCode.INVALID_NICKNAME))

    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(page.get_by_test_id("nickname-error")).to_have_text(
        load_fr()["join.error.characters"]
    )
    submit_form(page, "Bob")
    mock.wait_for_frames(2)
    assert mock.joins()[1] == Join(nickname="Bob", resume_token=None)


# ---- AC-7: what the page stores after a join ----------------------------------------


def players_named(nickname: str) -> list[PlayerView]:
    return [active_view("p1", nickname, 0, True)]


def expected_identity(nickname: str, token: str = MOCK_TOKEN) -> dict[str, str]:
    return {"player_id": "p1", "resume_token": token, "nickname": nickname}


def identity_is(page: Page, expected: dict[str, str]) -> bool:
    """Tell whether the stored identity of ABC123 is JSON equal to `expected`."""
    raw = read_storage(page, "nock.identity.ABC123")
    if raw is None:
        return False
    return json.loads(raw) == expected


def test_ac7_a_join_from_the_form_stores_the_identity_and_the_nickname_as_sent(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, " Ana ")
    mock.wait_for_frames(1)
    assert mock.joins() == [Join(nickname="Ana", resume_token=None)]

    mock.send(snapshot_frame(fx01_grid, players_named("Ana 2")))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    identity = wait_for_storage(page, "nock.identity.ABC123")
    assert json.loads(identity) == expected_identity("Ana 2")
    assert wait_for_storage(page, "nock.nickname") == "Ana"


def test_ac7_a_refused_join_stores_no_nickname(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(error_frame(ErrorCode.INVALID_NICKNAME))
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "nickname"
    )
    settle(page)
    assert read_storage(page, "nock.nickname") is None
    assert read_storage(page, "nock.identity.ABC123") is None
    submit_form(page, "Bob")
    mock.wait_for_frames(2)

    mock.send(snapshot_frame(fx01_grid, players_named("Bob")))

    assert wait_for_storage(page, "nock.nickname") == "Bob"
    assert json.loads(wait_for_storage(page, "nock.identity.ABC123")) == (
        expected_identity("Bob")
    )


def test_ac7_a_join_sent_at_once_stores_the_identity_but_no_nickname(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server, {"nock.room.ABC123": CATALOGUE_RECORD})
    mock.wait_for_frames(1)

    mock.send(snapshot_frame(fx01_grid, players_named("Invit\u00e9")))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    identity = wait_for_storage(page, "nock.identity.ABC123")
    assert json.loads(identity) == expected_identity("Invit\u00e9")
    settle(page)
    assert read_storage(page, "nock.nickname") is None


def test_ac7_a_join_sent_at_once_never_rewrites_the_remembered_nickname(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    items = {"nock.room.ABC123": CATALOGUE_RECORD, "nock.nickname": "Zo\u00e9"}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    mock.send(snapshot_frame(fx01_grid, players_named("Zo\u00e9 2")))

    identity = wait_for_storage(page, "nock.identity.ABC123")
    assert json.loads(identity) == expected_identity("Zo\u00e9 2")
    settle(page)
    assert read_storage(page, "nock.nickname") == "Zo\u00e9"


def test_ac7_a_resume_updates_the_identity_and_keeps_the_remembered_nickname(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    items = {"nock.identity.ABC123": STORED_IDENTITY, "nock.nickname": "Zo\u00e9"}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    mock.send(
        snapshot_frame(fx01_grid, players_named("Ana 2"), resume_token=OTHER_TOKEN)
    )

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-status", "joined")
    wait_until(
        page,
        lambda: identity_is(page, expected_identity("Ana 2", OTHER_TOKEN)),
    )
    settle(page)
    assert read_storage(page, "nock.nickname") == "Zo\u00e9"
