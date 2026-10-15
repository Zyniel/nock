"""Tests of spec 011, AC-3: random room codes and the wrong-code throttle.

The codes of `register_room`, the throttle on the room socket with a fake clock
and the real WebSocket, and the throttled page with a mocked socket. The shared
setup is in `spec011_harness`.
"""

from __future__ import annotations

import itertools
import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, WebSocketRoute, expect
from starlette.websockets import WebSocketDisconnect

import nock.hub
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import ROOM_CODE_ALPHABET, ROOM_CODE_LENGTH, RoomRegistry
from nock.protocol import Join, Snapshot, parse_server_message
from nock.room import RoomConfig
from nock.server import (
    THROTTLED_CLOSE_CODE,
    WRONG_CODE_LIMIT,
    WRONG_CODE_WINDOW_SECONDS,
    create_app,
)
from spec011_harness import (
    CODE_PATTERN,
    EXPECTED_FR_VALUES,
    JOIN_TEXT,
    START_TIME,
    UNKNOWN_CODE,
    FakeClock,
    build_catalogue,
    fresh_state,
    grid_from_text,
    load_fr,
    make_dist_dir,
    receive_text_or_fail,
    socket_url,
)

WAIT_TIMEOUT_MS = 5000
STORED_IDENTITY_SCRIPT = (
    "localStorage.setItem('nock.identity.ABC123', JSON.stringify("
    "{player_id: 'p1', resume_token: 'r7Kq2mXo9vB4tY1zW8nP', nickname: 'Ana'}));"
)


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


def code_as_number(code: str) -> int:
    """Read a room code as a base-32 number over ROOM_CODE_ALPHABET."""
    value = 0
    for character in code:
        value = value * 32 + ROOM_CODE_ALPHABET.index(character)
    return value


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
