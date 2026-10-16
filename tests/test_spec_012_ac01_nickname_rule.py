"""Tests of spec 012, AC-1: a valid nickname puts me in the room.

The nickname rule (`normalize_nickname` and `join_room`), the real WebSocket and the
browser, with the live server and with spec 040's mocked socket.
The shared setup is in `spec012_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

import nock.hub
import nock.room
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    Join,
    PlayerJoined,
    PlayerState,
    PlayerView,
    Snapshot,
)
from nock.room import (
    LogEntry,
    PlayerRecord,
    normalize_nickname,
    player_views,
    snapshot_for,
)
from nock.server import create_app
from spec012_harness import (
    FORM_TIMEOUT_MS,
    NOW,
    ROOM_CODE,
    active_view,
    error_frame,
    grid_from_text,
    join_as,
    join_text,
    load_fr,
    make_app,
    make_dist_dir,
    make_player,
    make_registry,
    make_state,
    only_error_code,
    open_mock_room,
    receive_error_code,
    receive_message,
    receive_snapshot,
    run_join,
    settle,
    snapshot_frame,
    socket_url,
    submit_form,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry that ticks fast and never times a silent socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def ws_client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One client, one event loop, on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as client:
        yield client


NON_EMPTY_MESSAGE = r".+"  # the message names the broken rule
RAW_JOIN_WITH_SPACES = '{"type": "join", "nickname": " Ana ", "resume_token": null}'
RAW_JOIN_TOO_LONG = (
    '{"type": "join", "nickname": "' + "x" * 21 + '", "resume_token": null}'
)


# ---- AC-1: the nickname rule -------------------------------------------------


GREEK_NAME = "\u1f08\u03bb\u03ad\u03be\u03b7\u03c2"
GREEK_NAME_IN_CAPITALS = "\u1f08\u039b\u0388\u039e\u0397\u03a3"
POLISH_NAME = "\u0141ukasz"
POLISH_NAME_IN_CAPITALS = "\u0141UKASZ"
DECOMPOSED_E = "E\u0301"
COMPOSED_E = "\u00c9"
RAM_NAME = "\u0930\u093e\u092e"  # \u093e is a spacing mark (Mc); no case
ENCLOSED_NAME = "Ana\u20dd"  # \u20dd is an enclosing mark (Me)

# What is typed, and the nickname as stored: NFC, stripped, then in capitals
# (spec 012 decision 12).
VALID_NICKNAMES = [
    ("Ana", "ANA"),
    ("  Ana  ", "ANA"),
    ("\u00c9lodie", "\u00c9LODIE"),
    (DECOMPOSED_E + "lodie", COMPOSED_E + "LODIE"),
    ("Jean-Luc", "JEAN-LUC"),
    ("O'Neil", "O'NEIL"),
    ("O\u2019Neil", "O\u2019NEIL"),
    ("bob_42", "BOB_42"),
    ("Anne Marie", "ANNE MARIE"),
    ("Anne  Marie", "ANNE  MARIE"),
    ("Zo\u00eb", "ZO\u00cb"),
    (POLISH_NAME, POLISH_NAME_IN_CAPITALS),
    (GREEK_NAME, GREEK_NAME_IN_CAPITALS),
    ("12", "12"),
    ("_1", "_1"),
    ("a-", "A-"),
    ("x" * 20, "X" * 20),
    ("q\u0323", "Q\u0323"),
    (RAM_NAME, RAM_NAME),
    (DECOMPOSED_E + "x" * 19, COMPOSED_E + "X" * 19),
]

# AC-1: for each of these, `normalize_nickname` returns `text.upper()`.
UPPER_CASED_AS_TYPED = [
    "Jean-Luc",
    "O'Neil",
    "O\u2019Neil",
    "bob_42",
    "Anne Marie",
    "Zo\u00eb",
    "12",
    RAM_NAME,
    "x" * 20,
]

INVALID_NICKNAMES = [
    "A",
    "",
    "   ",
    " A ",
    "x" * 21,
    "<b>Eve</b>",
    "Ana!",
    "a@b",
    "Ana\tB",
    "Ana\nB",
    "Ana.",
    'A"na',
    "A&b",
    "Ana>",
    "Ana\U0001f600",
    "\u0663\u0663",
    "Ana\u0663",
    "Ana\u00a0B",
    "--",
    "_ _",
    "-_-",
    "'\u2019",
    "\u0301\u0301",
    DECOMPOSED_E,
    ENCLOSED_NAME,
]


def test_ac1_nickname_punctuation_constant() -> None:
    assert nock.room.NICKNAME_PUNCTUATION == " -'\u2019_"


@pytest.mark.parametrize(("typed", "stored"), VALID_NICKNAMES)
def test_ac1_normalize_nickname_accepts_and_returns_the_stored_form(
    typed: str, stored: str
) -> None:
    assert normalize_nickname(typed) == stored


@pytest.mark.parametrize("text", UPPER_CASED_AS_TYPED)
def test_ac1_normalize_nickname_returns_the_text_in_capitals(text: str) -> None:
    assert normalize_nickname(text) == text.upper()


@pytest.mark.parametrize("typed", INVALID_NICKNAMES)
def test_ac1_normalize_nickname_rejects_a_broken_rule(typed: str) -> None:
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(typed)


def test_ac1_normalize_nickname_counts_code_points_after_nfc() -> None:
    # 21 code points typed, 20 once composed: accepted.
    assert len(DECOMPOSED_E + "x" * 19) == 21
    assert normalize_nickname(DECOMPOSED_E + "x" * 19) == COMPOSED_E + "X" * 19
    # 22 characters after NFC: refused.
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(COMPOSED_E + "x" * 21)


def test_ac1_join_room_adds_the_first_player(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, "  Ana ")

    expected_player = PlayerRecord(
        player_id="joiner1",
        resume_token="joiner-token-number-1",
        nickname="ANA",
        colour=0,
        is_host=True,
        muted=False,
        state=PlayerState.ACTIVE,
        joined_seq=1,
        last_input_at=NOW,
        last_seen_at=NOW,
        disconnected_at=None,
        selection=None,
    )
    assert outcome.state.players == (expected_player,)
    assert outcome.state.seq == 1
    expected_entry = LogEntry(
        at=NOW,
        event=PlayerJoined(seq=1, player=active_view("joiner1", "ANA", 0, True)),
        resume_token="joiner-token-number-1",
    )
    assert outcome.entries == (expected_entry,)
    assert outcome.reply == (snapshot_for(outcome.state, "joiner1"),)
    assert outcome.close_sender is False
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.seq == 1
    assert snapshot.you == "joiner1"
    assert snapshot.resume_token == "joiner-token-number-1"
    assert snapshot.players == (active_view("joiner1", "ANA", 0, True),)


def test_ac1_join_room_numbers_the_join_after_the_last_event(
    fx01_grid: Grid,
) -> None:
    existing = [make_player(0, "ANA", is_host=True)]
    state = make_state(fx01_grid, existing).model_copy(update={"seq": 5})

    outcome = run_join(state, "Bob")

    assert outcome.state.seq == 6
    assert outcome.state.players[:1] == tuple(existing)
    assert outcome.state.players[1].joined_seq == 6
    assert outcome.state.players[1].player_id == "joiner1"
    assert len(outcome.entries) == 1
    event = outcome.entries[0].event
    assert isinstance(event, PlayerJoined)
    assert event.seq == 6
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.seq == 6
    assert [view.nickname for view in snapshot.players] == ["ANA", "BOB"]


@pytest.mark.parametrize("typed", ["<b>Eve</b>", "Ana!", "--", "a@b", DECOMPOSED_E])
def test_ac1_join_room_refuses_a_bad_nickname_and_changes_nothing(
    fx01_grid: Grid, typed: str
) -> None:
    state = make_state(fx01_grid, [make_player(0, "ANA", is_host=True)])

    outcome = run_join(state, typed)

    assert only_error_code(outcome) == ErrorCode.INVALID_NICKNAME
    assert outcome.close_sender is False
    assert outcome.entries == ()
    assert outcome.state == state


def test_ac1_join_room_stores_the_normalised_nickname(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, DECOMPOSED_E + "lodie")

    assert outcome.state.players[0].nickname == COMPOSED_E + "LODIE"


def test_ac1_websocket_join_answers_a_snapshot_with_the_player(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with ws_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(RAW_JOIN_WITH_SPACES)

        snapshot = receive_snapshot(websocket)

        assert snapshot.seq == 1
        assert snapshot.players == (
            PlayerView(
                player_id=snapshot.you,
                nickname="ANA",
                colour=0,
                state=PlayerState.ACTIVE,
                is_host=True,
                muted=False,
                selection=None,
            ),
        )
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 1
        assert len(state.players) == 1
        stored = state.players[0]
        assert stored.player_id == snapshot.you
        assert stored.resume_token == snapshot.resume_token
        assert stored.nickname == "ANA"
        assert stored.colour == 0
        assert stored.is_host is True
        assert player_views(state) == snapshot.players


@pytest.mark.parametrize("typed", ["<b>Eve</b>", "Ana!", "--", "a@b"])
def test_ac1_websocket_bad_nickname_is_refused_and_the_socket_stays_open(
    ws_client: TestClient, registry: RoomRegistry, room_code: str, typed: str
) -> None:
    with ws_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(join_text(typed))

        assert receive_error_code(websocket) == ErrorCode.INVALID_NICKNAME

        state = registry.room_state(room_code)
        assert state is not None
        assert state.players == ()
        assert state.seq == 0
        websocket.send_text(join_text("Ana"))
        snapshot = receive_snapshot(websocket)
    assert snapshot.seq == 1
    assert [view.nickname for view in snapshot.players] == ["ANA"]


def test_ac1_websocket_nickname_of_21_characters_is_an_invalid_message(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with ws_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(RAW_JOIN_TOO_LONG)

        assert receive_error_code(websocket) == ErrorCode.INVALID_MESSAGE

        websocket.send_text(join_text("Ana"))
        snapshot = receive_snapshot(websocket)
    assert snapshot.seq == 1


def test_ac1_websocket_second_join_on_a_joined_socket_is_ignored(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        first, _ = join_as(stack, ws_client, room_code, "Ana")

        first.send_text(join_text("Bob"))
        _, other_snapshot = join_as(stack, ws_client, room_code, "Cy")

        message = receive_message(first)
        assert message == PlayerJoined(
            seq=2, player=active_view(other_snapshot.you, "CY", 1)
        )
    state = registry.room_state(room_code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA", "CY"]


def test_ac1_websocket_joiner_never_receives_its_own_player_joined(
    registry: RoomRegistry, fx01_grid: Grid, dist_dir: Path
) -> None:
    registry.add_room(make_state(fx01_grid, []).model_copy(update={"seq": 5}))
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as client, contextlib.ExitStack() as stack:
        first, first_snapshot = join_as(stack, client, ROOM_CODE, "Ana")
        _, second_snapshot = join_as(stack, client, ROOM_CODE, "Bob")

        assert first_snapshot.seq == 6
        assert first_snapshot.players == (
            active_view(first_snapshot.you, "ANA", 0, True),
        )
        assert receive_message(first) == PlayerJoined(
            seq=7, player=active_view(second_snapshot.you, "BOB", 1)
        )
        assert second_snapshot.seq == 7


# ---- AC-1: browser -----------------------------------------------------------


def test_ac1_browser_the_form_joins_the_room(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    code = room_registry.register_room(fx01_grid)
    page.goto(f"{live_server}/r/{code}")
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.nickname"]
    )

    page.get_by_test_id("nickname-input").fill("Ana", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("nickname-submit").click(timeout=FORM_TIMEOUT_MS)

    expect(room).to_have_attribute("data-status", "joined")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    roster = page.get_by_test_id("roster")
    items = roster.get_by_test_id("roster-player")
    expect(items).to_have_count(1)
    expect(items).to_have_attribute("data-you", "true")
    expect(items.get_by_test_id("roster-nickname")).to_have_text("Ana")
    state = room_registry.room_state(code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA"]


def test_ac1_browser_the_form_shows_heading_label_placeholder_and_button(
    page: Page, live_server: str
) -> None:
    fr = load_fr()
    open_mock_room(page, live_server)

    form = page.get_by_test_id("nickname-form")
    expect(form).to_be_visible()
    expect(form).to_contain_text(fr["join.heading"])
    nickname_input = page.get_by_test_id("nickname-input")
    expect(page.get_by_label(fr["join.nickname_label"], exact=True)).to_have_attribute(
        "data-testid", "nickname-input"
    )
    expect(nickname_input).to_have_attribute("placeholder", fr["room.default_nickname"])
    expect(page.get_by_test_id("nickname-submit")).to_have_text(fr["join.submit"])
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-you", "")


def test_ac1_browser_a_valid_nickname_is_sent_normalised(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    page.get_by_test_id("nickname-input").fill(" Ana ", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("nickname-submit").click(timeout=FORM_TIMEOUT_MS)

    mock.wait_for_frames(1)

    assert mock.joins() == [Join(nickname="ANA", resume_token=None)]
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joining"]
    )
    expect(page.get_by_test_id("nickname-submit")).to_be_disabled()


@pytest.mark.parametrize(
    ("typed", "sent"),
    [
        (DECOMPOSED_E + "lodie", COMPOSED_E + "LODIE"),
        ("Zo\u00eb", "ZO\u00cb"),
        (POLISH_NAME, POLISH_NAME_IN_CAPITALS),
        (GREEK_NAME, GREEK_NAME_IN_CAPITALS),
        ("O\u2019Neil", "O\u2019NEIL"),
        ("Jean-Luc", "JEAN-LUC"),
        ("bob_42", "BOB_42"),
        ("12", "12"),
        ("Anne Marie", "ANNE MARIE"),
        (RAM_NAME, RAM_NAME),
    ],
)
def test_ac1_browser_the_page_accepts_what_the_server_rule_accepts(
    page: Page, live_server: str, typed: str, sent: str
) -> None:
    mock = open_mock_room(page, live_server)

    submit_form(page, typed)

    mock.wait_for_frames(1)
    assert mock.joins() == [Join(nickname=sent, resume_token=None)]


@pytest.mark.parametrize(
    ("typed", "error_key"),
    [
        ("A", "join.error.length"),
        (" A ", "join.error.length"),
        ("   ", "join.error.length"),
        ("--", "join.error.characters"),
        ("Ana!", "join.error.characters"),
        ("<b>Eve</b>", "join.error.characters"),
        ("a@b", "join.error.characters"),
        ("Ana\U0001f600", "join.error.characters"),
        ("\u0663\u0663", "join.error.characters"),
        (DECOMPOSED_E, "join.error.length"),
        (ENCLOSED_NAME, "join.error.characters"),
    ],
)
def test_ac1_browser_a_bad_nickname_shows_the_error_and_sends_nothing(
    page: Page, live_server: str, typed: str, error_key: str
) -> None:
    mock = open_mock_room(page, live_server)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")

    submit_form(page, typed)

    expect(page.get_by_test_id("nickname-error")).to_have_text(load_fr()[error_key])
    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-form")).to_be_visible()
    settle(page)
    assert mock.frames_without_pings() == []


def test_ac1_browser_the_server_refusing_a_nickname_brings_the_form_back(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")

    mock.send(error_frame(ErrorCode.INVALID_NICKNAME))

    expect(room).to_have_attribute("data-status", "nickname")
    expect(page.get_by_test_id("nickname-error")).to_have_text(
        load_fr()["join.error.characters"]
    )
    expect(page.get_by_test_id("nickname-submit")).to_be_enabled()
    submit_form(page, "Bob")
    mock.wait_for_frames(2)
    assert mock.joins() == [
        Join(nickname="ANA", resume_token=None),
        Join(nickname="BOB", resume_token=None),
    ]
    assert len(mock.routes) == 1


def test_ac1_browser_data_you_follows_the_first_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-you", "")

    mock.send(snapshot_frame(fx01_grid, [active_view("p1", "Ana", 0, True)]))

    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-you", "p1")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)


def test_ac1_fr_json_has_the_join_texts() -> None:
    fr = load_fr()

    assert fr["join.heading"] == "Choisissez un pseudo"
    assert fr["join.nickname_label"] == "Pseudo"
    assert fr["join.submit"] == "Entrer dans le salon"
    assert (
        fr["join.error.length"]
        == "Le pseudo doit faire de 2 \u00e0 20 caract\u00e8res."
    )
    assert fr["join.error.characters"] == (
        "Lettres, chiffres, espaces, tirets, apostrophes et _ uniquement."
    )
    assert fr["room.status.nickname"] == "Choisissez un pseudo pour entrer."
    assert fr["room.status.joining"] == "Entr\u00e9e dans le salon\u2026"


def test_ac1_fr_json_has_a_status_text_for_every_status() -> None:
    fr = load_fr()
    statuses = ["connecting", "nickname", "joining", "joined", "full", "replaced"]
    statuses += ["not_found", "throttled", "closed"]

    for status in statuses:
        assert fr[f"room.status.{status}"] != "", status
