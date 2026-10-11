"""Tests of spec 012: guest join, nicknames, colours, resume and the room page."""

from __future__ import annotations

import contextlib
import json
import queue
import re
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, WebSocketRoute, expect
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

import nock.hub
import nock.room
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Direction,
    ErrorCode,
    ErrorMessage,
    Join,
    LeaveReason,
    LetterCellView,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
    Selection,
    Snapshot,
    grid_view,
    parse_client_message,
    parse_server_message,
)
from nock.room import (
    MAX_PLAYERS,
    CellState,
    LogEntry,
    Outcome,
    PlayerRecord,
    RoomConfig,
    RoomState,
    disconnect_player,
    grid_state,
    join_room,
    new_room,
    normalize_nickname,
    player_views,
    snapshot_for,
)
from nock.server import create_app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FR_JSON_PATH = PROJECT_ROOT / "web" / "src" / "i18n" / "fr.json"

INDEX_HTML = '<!doctype html><title></title><div id="app"></div>'
ROOM_CODE = "ABCDEF"
NOW = 2_000_000.0
OLD_TIME = 1_500_000.0
START_TIME = 1_000_000.0
RECEIVE_TIMEOUT_SECONDS = 5.0
SETTLE_SECONDS = 0.4
WAIT_TIMEOUT_MS = 5000
SETTLE_MS = 500
MOCK_TOKEN = "r7Kq2mXo9vB4tY1zW8nP"
OTHER_TOKEN = "q3Wm8xYo2vB4tY1zW9nR"
SESSION_REPLACED = 4001
NON_EMPTY_MESSAGE = r".+"  # the message names the broken rule
RAW_JOIN_WITH_SPACES = '{"type": "join", "nickname": " Ana ", "resume_token": null}'
RAW_JOIN_TOO_LONG = (
    '{"type": "join", "nickname": "' + "x" * 21 + '", "resume_token": null}'
)
STORED_IDENTITY = json.dumps(
    {"player_id": "p1", "resume_token": MOCK_TOKEN, "nickname": "Ana 2"}
)
CATALOGUE_RECORD = json.dumps({"grid": 1, "selection": None})


# ---- Fixtures and helpers ---------------------------------------------------


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
def registry() -> Iterator[RoomRegistry]:
    """A registry that ticks fast and never times a silent socket out."""
    config = RoomConfig(tick_seconds=0.05, silence_timeout_seconds=600)
    room_registry = RoomRegistry(config=config)
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
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with TestClient(app) as client:
        yield client


def load_fr() -> dict[str, str]:
    return json.loads(FR_JSON_PATH.read_text(encoding="utf-8"))


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


def receive_message(websocket: WebSocketTestSession) -> object:
    return parse_server_message(receive_text_or_fail(websocket))


def receive_snapshot(websocket: WebSocketTestSession) -> Snapshot:
    message = receive_message(websocket)
    assert isinstance(message, Snapshot), message
    return message


def receive_error_code(websocket: WebSocketTestSession) -> ErrorCode:
    message = receive_message(websocket)
    assert isinstance(message, ErrorMessage), message
    return message.code


def close_code_of_next_read(websocket: WebSocketTestSession) -> int:
    """Return the close code the socket receives; fail if a message comes first."""
    try:
        text = receive_text_or_fail(websocket)
    except WebSocketDisconnect as closed:
        return closed.code
    pytest.fail(f"the socket should have closed, but it received: {text}")


def socket_url(code: str) -> str:
    return f"/api/rooms/{code}/ws"


def join_text(nickname: str, resume_token: str | None = None) -> str:
    return Join(nickname=nickname, resume_token=resume_token).model_dump_json()


def join_as(
    stack: contextlib.ExitStack,
    client: TestClient,
    code: str,
    nickname: str,
    resume_token: str | None = None,
) -> tuple[WebSocketTestSession, Snapshot]:
    """Open a socket in `stack`, join, and return the socket and its snapshot."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    websocket.send_text(join_text(nickname, resume_token))
    return websocket, receive_snapshot(websocket)


def expect_joined_seqs(websocket: WebSocketTestSession, seqs: list[int]) -> None:
    """Read one `player_joined` per seq of `seqs`, in order."""
    for seq in seqs:
        message = receive_message(websocket)
        assert isinstance(message, PlayerJoined), message
        assert message.seq == seq


def active_view(
    player_id: str, nickname: str, colour: int, is_host: bool = False
) -> PlayerView:
    return PlayerView(
        player_id=player_id,
        nickname=nickname,
        colour=colour,
        state=PlayerState.ACTIVE,
        is_host=is_host,
        muted=False,
        selection=None,
    )


def make_player(
    index: int,
    nickname: str,
    *,
    colour: int | None = None,
    state: PlayerState = PlayerState.ACTIVE,
    is_host: bool = False,
) -> PlayerRecord:
    """A player of a seeded room: ids and tokens are derived from `index`."""
    return PlayerRecord(
        player_id=f"player{index}",
        resume_token=f"resume-token-number-{index}",
        nickname=nickname,
        colour=index if colour is None else colour,
        is_host=is_host,
        state=state,
        joined_seq=index + 1,
        last_input_at=OLD_TIME,
        last_seen_at=OLD_TIME,
        disconnected_at=OLD_TIME if state is PlayerState.DISCONNECTED else None,
    )


def make_state(grid: Grid, players: list[PlayerRecord]) -> RoomState:
    """A room holding `players`; `seq` is the number of players."""
    fresh = new_room(ROOM_CODE, grid, START_TIME)
    return fresh.model_copy(update={"players": tuple(players), "seq": len(players)})


def eight_players(state: PlayerState = PlayerState.ACTIVE) -> list[PlayerRecord]:
    players: list[PlayerRecord] = []
    for index in range(MAX_PLAYERS):
        players.append(
            make_player(index, f"Player{index}", state=state, is_host=index == 0)
        )
    return players


def run_join(
    state: RoomState, nickname: str, number: int = 1, token: str | None = None
) -> Outcome:
    """Apply a join with fresh ids derived from `number`."""
    message = Join(nickname=nickname, resume_token=token)
    return join_room(
        state, message, NOW, f"joiner{number}", f"joiner-token-number-{number}"
    )


def only_error_code(outcome: Outcome) -> ErrorCode:
    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, ErrorMessage)
    return reply.code


# ---- AC-1: the nickname rule -------------------------------------------------

GREEK_NAME = "\u1f08\u03bb\u03ad\u03be\u03b7\u03c2"
POLISH_NAME = "\u0141ukasz"
DECOMPOSED_E = "E\u0301"
COMPOSED_E = "\u00c9"

VALID_NICKNAMES = [
    ("Ana", "Ana"),
    ("  Ana  ", "Ana"),
    ("\u00c9lodie", "\u00c9lodie"),
    (DECOMPOSED_E + "lodie", COMPOSED_E + "lodie"),
    ("Jean-Luc", "Jean-Luc"),
    ("O'Neil", "O'Neil"),
    ("O\u2019Neil", "O\u2019Neil"),
    ("bob_42", "bob_42"),
    ("Anne Marie", "Anne Marie"),
    ("Anne  Marie", "Anne  Marie"),
    ("Zo\u00eb", "Zo\u00eb"),
    (POLISH_NAME, POLISH_NAME),
    (GREEK_NAME, GREEK_NAME),
    ("12", "12"),
    ("_1", "_1"),
    ("a-", "a-"),
    ("x" * 20, "x" * 20),
    ("q\u0323", "q\u0323"),
    (DECOMPOSED_E + "x" * 19, COMPOSED_E + "x" * 19),
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
]


def test_ac1_nickname_punctuation_constant() -> None:
    assert nock.room.NICKNAME_PUNCTUATION == " -'\u2019_"


@pytest.mark.parametrize(("typed", "stored"), VALID_NICKNAMES)
def test_ac1_normalize_nickname_accepts_and_returns_the_stored_form(
    typed: str, stored: str
) -> None:
    assert normalize_nickname(typed) == stored


@pytest.mark.parametrize("typed", INVALID_NICKNAMES)
def test_ac1_normalize_nickname_rejects_a_broken_rule(typed: str) -> None:
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(typed)


def test_ac1_normalize_nickname_counts_code_points_after_nfc() -> None:
    # 21 code points typed, 20 once composed: accepted.
    assert len(DECOMPOSED_E + "x" * 19) == 21
    assert normalize_nickname(DECOMPOSED_E + "x" * 19) == COMPOSED_E + "x" * 19
    # 22 characters after NFC: refused.
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(COMPOSED_E + "x" * 21)


def test_ac1_join_room_adds_the_first_player(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, "  Ana ")

    expected_player = PlayerRecord(
        player_id="joiner1",
        resume_token="joiner-token-number-1",
        nickname="Ana",
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
        event=PlayerJoined(seq=1, player=active_view("joiner1", "Ana", 0, True)),
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
    assert snapshot.players == (active_view("joiner1", "Ana", 0, True),)


def test_ac1_join_room_numbers_the_join_after_the_last_event(
    fx01_grid: Grid,
) -> None:
    existing = [make_player(0, "Ana", is_host=True)]
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
    assert [view.nickname for view in snapshot.players] == ["Ana", "Bob"]


@pytest.mark.parametrize("typed", ["<b>Eve</b>", "Ana!", "--", "a@b", DECOMPOSED_E])
def test_ac1_join_room_refuses_a_bad_nickname_and_changes_nothing(
    fx01_grid: Grid, typed: str
) -> None:
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True)])

    outcome = run_join(state, typed)

    assert only_error_code(outcome) == ErrorCode.INVALID_NICKNAME
    assert outcome.close_sender is False
    assert outcome.entries == ()
    assert outcome.state == state


def test_ac1_join_room_stores_the_normalised_nickname(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, DECOMPOSED_E + "lodie")

    assert outcome.state.players[0].nickname == COMPOSED_E + "lodie"


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
            nickname="Ana",
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
    assert stored.nickname == "Ana"
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
    assert [view.nickname for view in snapshot.players] == ["Ana"]


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
            seq=2, player=active_view(other_snapshot.you, "Cy", 1)
        )
    state = registry.room_state(room_code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["Ana", "Cy"]


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
            active_view(first_snapshot.you, "Ana", 0, True),
        )
        assert receive_message(first) == PlayerJoined(
            seq=7, player=active_view(second_snapshot.you, "Bob", 1)
        )
        assert second_snapshot.seq == 7


# ---- AC-1: browser -----------------------------------------------------------


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

    def joins(self) -> list[Join]:
        """The frames received so far, each parsed as a Join."""
        parsed: list[Join] = []
        for frame in self.received:
            message = parse_client_message(frame)
            assert isinstance(message, Join), frame
            parsed.append(message)
        return parsed


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


def seed_local_storage(page: Page, items: dict[str, str]) -> None:
    """Fill `localStorage` before the page's own scripts run."""
    script = (
        f"const items = {json.dumps(items)};"
        "for (const [key, value] of Object.entries(items)) {"
        " localStorage.setItem(key, value); }"
    )
    page.context.add_init_script(script)


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


def open_mock_room(
    page: Page, base_url: str, items: dict[str, str] | None = None
) -> MockRoomSocket:
    """Open /r/ABC123 with a mocked socket and `localStorage` seeded with `items`."""
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    if items:
        seed_local_storage(page, items)
    page.goto(f"{base_url}/r/ABC123")
    return mock


FORM_TIMEOUT_MS = 5000


def submit_form(page: Page, nickname: str) -> None:
    """Fill the nickname form and submit it with Enter."""
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill(nickname, timeout=FORM_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)


def snapshot_frame(
    grid: Grid,
    players: list[PlayerView],
    you: str = "p1",
    resume_token: str = MOCK_TOKEN,
    seq: int = 1,
) -> str:
    snapshot_players = tuple(players)
    snapshot = Snapshot(
        seq=seq,
        you=you,
        resume_token=resume_token,
        grid=grid_view(grid),
        players=snapshot_players,
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


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
    assert [player.nickname for player in state.players] == ["Ana"]


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

    assert mock.joins() == [Join(nickname="Ana", resume_token=None)]
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joining"]
    )
    expect(page.get_by_test_id("nickname-submit")).to_be_disabled()


@pytest.mark.parametrize(
    ("typed", "sent"),
    [
        (DECOMPOSED_E + "lodie", COMPOSED_E + "lodie"),
        ("Zo\u00eb", "Zo\u00eb"),
        (POLISH_NAME, POLISH_NAME),
        (GREEK_NAME, GREEK_NAME),
        ("O\u2019Neil", "O\u2019Neil"),
        ("Jean-Luc", "Jean-Luc"),
        ("bob_42", "bob_42"),
        ("12", "12"),
        ("Anne Marie", "Anne Marie"),
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
    assert mock.received == []


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
        Join(nickname="Ana", resume_token=None),
        Join(nickname="Bob", resume_token=None),
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


# ---- AC-2: colours, duplicate nicknames, roster -------------------------------


def test_ac2_eight_joins_give_eight_colours_and_unique_nicknames(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [])
    typed = ["Ana", "ana", "Ana", "Bob", "Cy", "Di", "Ed", "Flo"]

    for number, nickname in enumerate(typed):
        outcome = run_join(state, nickname, number)
        state = outcome.state

    assert [player.nickname for player in state.players] == [
        "Ana",
        "ana 2",
        "Ana 3",
        "Bob",
        "Cy",
        "Di",
        "Ed",
        "Flo",
    ]
    assert [player.colour for player in state.players] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert [player.is_host for player in state.players] == [True] + [False] * 7
    assert state.seq == 8


def test_ac2_a_taken_nickname_gets_the_smallest_free_suffix(fx01_grid: Grid) -> None:
    players = [make_player(0, "Ana", is_host=True), make_player(1, "Ana 3")]
    state = make_state(fx01_grid, players)

    first = run_join(state, "Ana", 5)
    second = run_join(first.state, "Ana", 6)

    assert first.state.players[-1].nickname == "Ana 2"
    assert second.state.players[-1].nickname == "Ana 4"


def test_ac2_a_player_called_ana_2_pushes_the_next_ana_to_ana_3(
    fx01_grid: Grid,
) -> None:
    players = [make_player(0, "Ana", is_host=True), make_player(1, "Ana 2")]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Ana", 5)

    assert outcome.state.players[-1].nickname == "Ana 3"


def test_ac2_a_nickname_of_20_characters_keeps_the_suffix_within_20(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "x" * 20, is_host=True)])

    second = run_join(state, "x" * 20, 5)
    third = run_join(second.state, "x" * 20, 6)

    assert second.state.players[-1].nickname == "x" * 18 + " 2"
    assert third.state.players[-1].nickname == "x" * 18 + " 3"
    assert len(second.state.players[-1].nickname) == 20


def test_ac2_trailing_spaces_of_the_cut_base_are_removed(fx01_grid: Grid) -> None:
    taken = "a" * 17 + " bb"
    assert len(taken) == 20
    state = make_state(fx01_grid, [make_player(0, taken, is_host=True)])

    outcome = run_join(state, taken, 5)

    assert outcome.state.players[-1].nickname == "a" * 17 + " 2"


def test_ac2_the_duplicate_check_ignores_case_with_casefold(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [make_player(0, "Strasse", is_host=True)])

    outcome = run_join(state, "STRA\u00dfE", 5)

    assert outcome.state.players[-1].nickname == "STRA\u00dfE 2"


def test_ac2_the_duplicate_check_is_accent_sensitive(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [make_player(0, "Elodie", is_host=True)])

    outcome = run_join(state, "\u00c9lodie", 5)

    assert outcome.state.players[-1].nickname == "\u00c9lodie"


def test_ac2_a_disconnected_player_still_holds_their_nickname(
    fx01_grid: Grid,
) -> None:
    players = [make_player(0, "Ana", is_host=True, state=PlayerState.DISCONNECTED)]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Ana", 5)

    assert outcome.state.players[-1].nickname == "Ana 2"


def test_ac2_the_suffix_goes_to_the_newcomer_only(fx01_grid: Grid) -> None:
    existing = make_player(0, "Ana", is_host=True)
    state = make_state(fx01_grid, [existing])

    outcome = run_join(state, "ana", 5)

    assert outcome.state.players[0] == existing
    assert outcome.state.players[1].nickname == "ana 2"


@pytest.mark.parametrize(
    ("taken_colours", "expected_colour"),
    [([0, 2], 1), ([1, 2], 0), ([0, 1, 2, 3, 4, 5, 6], 7), ([5], 0)],
)
def test_ac2_a_new_player_gets_the_lowest_colour_nobody_has(
    fx01_grid: Grid, taken_colours: list[int], expected_colour: int
) -> None:
    players: list[PlayerRecord] = []
    for index, colour in enumerate(taken_colours):
        players.append(make_player(index, f"Player{index}", colour=colour))
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Newbie", 9)

    assert outcome.state.players[-1].colour == expected_colour


def test_ac2_a_disconnected_player_keeps_their_colour(fx01_grid: Grid) -> None:
    players = [
        make_player(0, "Ana", is_host=True, state=PlayerState.DISCONNECTED),
        make_player(1, "Bob"),
    ]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Cy", 9)

    assert outcome.state.players[-1].colour == 2


def test_ac2_only_the_first_joiner_is_host(fx01_grid: Grid) -> None:
    host_away = make_player(0, "Ana", is_host=True, state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host_away])

    outcome = run_join(state, "Bob", 5)

    assert outcome.state.players[-1].is_host is False
    assert outcome.state.players[0].is_host is True


def test_ac2_a_room_without_host_gives_the_role_to_the_next_joiner(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "Ana"), make_player(1, "Bob")])

    outcome = run_join(state, "Cy", 5)

    assert outcome.state.players[-1].is_host is True
    assert outcome.state.players[0].is_host is False
    assert outcome.state.players[1].is_host is False
    event = outcome.entries[0].event
    assert isinstance(event, PlayerJoined)
    assert event.player.is_host is True


def test_ac2_player_views_copy_the_player_records_without_the_token(
    fx01_grid: Grid,
) -> None:
    selection = Selection(row=1, column=2, direction=Direction.DOWN)
    host = make_player(0, "Ana", is_host=True).model_copy(
        update={"muted": True, "selection": selection}
    )
    away = make_player(1, "Bob", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host, away])

    views = player_views(state)

    assert views == (
        PlayerView(
            player_id="player0",
            nickname="Ana",
            colour=0,
            state=PlayerState.ACTIVE,
            is_host=True,
            muted=True,
            selection=selection,
        ),
        PlayerView(
            player_id="player1",
            nickname="Bob",
            colour=1,
            state=PlayerState.DISCONNECTED,
            is_host=False,
            muted=False,
            selection=None,
        ),
    )
    assert player_views(make_state(fx01_grid, [])) == ()
    assert "resume" not in views[0].model_dump_json()


def test_ac2_websocket_three_clients_get_distinct_colours_and_suffixes(
    ws_client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        first, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        second, second_snapshot = join_as(stack, ws_client, room_code, "Ana")
        _, third_snapshot = join_as(stack, ws_client, room_code, "Bob")

        assert [(p.nickname, p.colour) for p in third_snapshot.players] == [
            ("Ana", 0),
            ("Ana 2", 1),
            ("Bob", 2),
        ]
        second_view = active_view(second_snapshot.you, "Ana 2", 1)
        bob_view = active_view(third_snapshot.you, "Bob", 2)
        player_ids = {first_snapshot.you, second_snapshot.you, third_snapshot.you}
        assert len(player_ids) == 3
        assert receive_message(first) == PlayerJoined(seq=2, player=second_view)
        assert receive_message(first) == PlayerJoined(seq=3, player=bob_view)
        assert receive_message(second) == PlayerJoined(seq=3, player=bob_view)


def three_players() -> list[PlayerView]:
    return [
        active_view("p0", "Ana", 0, True),
        active_view("p1", "Ana 2", 1),
        active_view("p2", "Bob", 2),
    ]


def test_ac2_browser_the_roster_lists_the_players_of_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)

    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))

    expect(page.get_by_test_id("roster")).to_contain_text(fr["roster.heading"])
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)
    expected = [
        ("p0", "0", "false", "Ana"),
        ("p1", "1", "true", "Ana 2"),
        ("p2", "2", "false", "Bob"),
    ]
    for position, (player_id, colour, is_you, nickname) in enumerate(expected):
        item = items.nth(position)
        expect(item).to_have_attribute("data-player-id", player_id)
        expect(item).to_have_attribute("data-colour", colour)
        expect(item).to_have_attribute("data-state", "active")
        expect(item).to_have_attribute("data-you", is_you)
        expect(item.get_by_test_id("roster-nickname")).to_have_text(nickname)
        if is_you == "true":
            expect(item).to_contain_text(fr["roster.you"])
        else:
            expect(item).not_to_contain_text(fr["roster.you"])
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-you", "p1")


def test_ac2_browser_player_joined_appends_and_player_left_removes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)

    joined = PlayerJoined(seq=4, player=active_view("p3", "Cy", 3))
    mock.send(joined.model_dump_json())

    expect(items).to_have_count(4)
    expect(items.nth(3)).to_have_attribute("data-player-id", "p3")
    expect(items.nth(3)).to_have_attribute("data-colour", "3")
    expect(items.nth(3).get_by_test_id("roster-nickname")).to_have_text("Cy")
    left = PlayerLeft(seq=5, player_id="p2", reason=LeaveReason.TIMED_OUT)
    mock.send(left.model_dump_json())

    expect(items).to_have_count(3)
    expect(items.nth(0)).to_have_attribute("data-player-id", "p0")
    expect(items.nth(1)).to_have_attribute("data-player-id", "p1")
    expect(items.nth(2)).to_have_attribute("data-player-id", "p3")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")


def test_ac2_browser_the_eight_colours_are_different_on_screen(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    players: list[PlayerView] = []
    for index in range(8):
        players.append(active_view(f"p{index}", f"Player{index}", index, index == 0))

    mock.send(snapshot_frame(fx01_grid, players, you="p0", seq=8))

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(8)
    backgrounds: list[str] = []
    for index in range(8):
        swatch = items.nth(index).get_by_test_id("roster-colour")
        background = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert isinstance(background, str)
        backgrounds.append(background)
    assert "rgba(0, 0, 0, 0)" not in backgrounds
    assert "transparent" not in backgrounds
    assert len(set(backgrounds)) == 8


def test_ac2_browser_a_nickname_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    players = [active_view("p0", "<b>Eve</b>", 0, True)]

    mock.send(snapshot_frame(fx01_grid, players, you="p0"))

    nickname = page.get_by_test_id("roster-nickname")
    expect(nickname).to_have_text("<b>Eve</b>")
    expect(nickname.locator("b")).to_have_count(0)


def test_ac2_fr_json_has_the_roster_texts() -> None:
    fr = load_fr()

    assert fr["roster.heading"] == "Joueurs"
    assert fr["roster.you"] == "(vous)"


# ---- AC-3: the snapshot at once ------------------------------------------------


def seeded_room(grid: Grid) -> RoomState:
    """A FX-01 room with T and A written by `p9`, and a budget of 3 and 1."""
    fresh = new_room(ROOM_CODE, grid, START_TIME)
    cells: list[CellState] = []
    for cell in fresh.cells:
        if (cell.row, cell.column) == (1, 0):
            cell = cell.model_copy(update={"letter": "T", "author": "p9"})
        if (cell.row, cell.column) == (1, 1):
            cell = cell.model_copy(update={"letter": "A", "author": "p9"})
        cells.append(cell)
    return fresh.model_copy(
        update={
            "cells": tuple(cells),
            "reveal_budget": RevealBudget(letters=3, words=1),
        }
    )


def letter_view_at(snapshot: Snapshot, row: int, column: int) -> LetterCellView:
    for cell in snapshot.grid.cells:
        if (
            isinstance(cell, LetterCellView)
            and cell.row == row
            and cell.column == column
        ):
            return cell
    pytest.fail(f"no letter cell at ({row}, {column}) in the snapshot")


def test_ac3_snapshot_arrives_within_a_second_with_letters_timer_and_budget(
    registry: RoomRegistry, fx01_grid: Grid, dist_dir: Path
) -> None:
    registry.add_room(seeded_room(fx01_grid))
    app = create_app(rooms=registry, dist_dir=dist_dir)
    with (
        TestClient(app) as client,
        client.websocket_connect(socket_url(ROOM_CODE)) as websocket,
    ):
        started = time.monotonic()
        websocket.send_text(join_text("Ana"))
        snapshot = receive_snapshot(websocket)
        elapsed = time.monotonic() - started

    assert elapsed < 1.0
    # The snapshot answers a real join: it counts the joiner and the join itself.
    assert snapshot.seq == 1
    assert [view.player_id for view in snapshot.players] == [snapshot.you]
    state = registry.room_state(ROOM_CODE)
    assert state is not None
    assert snapshot.grid == grid_state(state)
    first = letter_view_at(snapshot, 1, 0)
    assert (first.letter, first.author) == ("T", "p9")
    second = letter_view_at(snapshot, 1, 1)
    assert (second.letter, second.author) == ("A", "p9")
    assert snapshot.reveal_budget == RevealBudget(letters=3, words=1)
    assert snapshot.timer_elapsed_ms == 0
    assert snapshot.timer_running is False


def test_ac3_snapshot_for_fills_every_field_from_the_room(fx01_grid: Grid) -> None:
    state = seeded_room(fx01_grid).model_copy(
        update={
            "players": (make_player(0, "Ana", is_host=True), make_player(1, "Bob")),
            "seq": 7,
            "solved": True,
        }
    )

    snapshot = snapshot_for(state, "player1")

    assert snapshot == Snapshot(
        seq=7,
        you="player1",
        resume_token="resume-token-number-1",
        grid=grid_state(state),
        players=player_views(state),
        settings=state.settings,
        reveal_budget=RevealBudget(letters=3, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=True,
    )


def test_ac3_snapshot_for_an_unknown_player_raises_key_error(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True)])

    with pytest.raises(KeyError):
        snapshot_for(state, "nobody")


# ---- AC-4: room full ------------------------------------------------------------


def test_ac4_join_room_refuses_a_ninth_player(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players())

    outcome = run_join(state, "Zoe", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert outcome.state == state


def test_ac4_disconnected_players_still_hold_their_seats(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players(PlayerState.DISCONNECTED))

    outcome = run_join(state, "Zoe", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True
    assert outcome.state == state


def test_ac4_a_full_room_answers_room_full_even_to_a_bad_nickname(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, eight_players())

    outcome = run_join(state, "--", 9)

    assert only_error_code(outcome) == ErrorCode.ROOM_FULL
    assert outcome.close_sender is True


def test_ac4_a_room_of_seven_still_takes_one_more(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, eight_players()[:7])

    outcome = run_join(state, "Zoe", 9)

    assert len(outcome.state.players) == 8
    assert outcome.close_sender is False
    assert isinstance(outcome.reply[0], Snapshot)


def test_ac4_a_resume_is_accepted_in_a_full_room(fx01_grid: Grid) -> None:
    players = eight_players()
    players[3] = make_player(3, "Player3", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Zoe", 9, token="resume-token-number-3")

    assert outcome.close_sender is False
    assert len(outcome.state.players) == 8
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "player3"


def test_ac4_websocket_a_ninth_join_is_refused_then_the_socket_closes(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as last_stack:
        first, _ = join_as(stack, ws_client, room_code, "Player1")
        for number in range(2, 8):
            join_as(stack, ws_client, room_code, f"Player{number}")
        _, eighth_snapshot = join_as(last_stack, ws_client, room_code, "Player8")
        expect_joined_seqs(first, [2, 3, 4, 5, 6, 7, 8])

        with ws_client.websocket_connect(socket_url(room_code)) as ninth:
            ninth.send_text(join_text("Zo\u00e9"))

            assert receive_error_code(ninth) == ErrorCode.ROOM_FULL
            assert close_code_of_next_read(ninth) == 1000

        state = registry.room_state(room_code)
        assert state is not None
        assert len(state.players) == 8
        assert state.seq == 8
        # The next thing the first client hears is the eighth leaving: the
        # refused join produced no event.
        last_stack.close()
        assert receive_message(first) == PlayerStateChanged(
            seq=9, player_id=eighth_snapshot.you, state=PlayerState.DISCONNECTED
        )


def eight_disconnected_room(grid: Grid) -> RoomState:
    return make_state(grid, eight_players(PlayerState.DISCONNECTED))


def test_ac4_browser_a_full_room_shows_room_full(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    room_registry.add_room(eight_disconnected_room(fx01_grid))
    page.goto(f"{live_server}/r/{ROOM_CODE}")
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "nickname")

    submit_form(page, "Zo\u00e9")

    expect(room).to_have_attribute("data-status", "full")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.full"]
    )
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    state = room_registry.room_state(ROOM_CODE)
    assert state is not None
    assert len(state.players) == 8


def test_ac4_browser_room_full_is_final_even_after_the_close(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Zo\u00e9")
    mock.wait_for_frames(1)
    room = page.get_by_test_id("room-page")

    mock.send(error_frame(ErrorCode.ROOM_FULL))
    mock.close(1000)

    expect(room).to_have_attribute("data-status", "full")
    settle(page)
    expect(room).to_have_attribute("data-status", "full")
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    assert len(mock.received) == 1
    assert len(mock.routes) == 1


def test_ac4_fr_json_has_the_room_full_text() -> None:
    assert load_fr()["room.status.full"] == "Ce salon est complet (8 joueurs)."


# ---- AC-5: disconnection, resume, two tabs ---------------------------------------


def test_ac5_disconnect_player_keeps_the_seat_and_tells_the_others(
    fx01_grid: Grid,
) -> None:
    host = make_player(0, "Ana", is_host=True)
    other = make_player(1, "Bob")
    state = make_state(fx01_grid, [host, other])

    outcome = disconnect_player(state, "player0", NOW)

    assert outcome.state.seq == 3
    assert outcome.state.players[0] == host.model_copy(
        update={"state": PlayerState.DISCONNECTED, "disconnected_at": NOW}
    )
    assert outcome.state.players[1] == other
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=PlayerStateChanged(
                seq=3, player_id="player0", state=PlayerState.DISCONNECTED
            ),
        ),
    )


def test_ac5_disconnecting_an_idle_player_marks_them_disconnected(
    fx01_grid: Grid,
) -> None:
    idle = make_player(1, "Bob", state=PlayerState.IDLE)
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True), idle])

    outcome = disconnect_player(state, "player1", NOW)

    assert outcome.state.players[1].state is PlayerState.DISCONNECTED
    assert outcome.state.players[1].disconnected_at == NOW
    assert len(outcome.entries) == 1


def test_ac5_disconnecting_twice_or_an_unknown_player_changes_nothing(
    fx01_grid: Grid,
) -> None:
    away = make_player(1, "Bob", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True), away])

    again = disconnect_player(state, "player1", NOW)
    unknown = disconnect_player(state, "nobody", NOW)

    for outcome in (again, unknown):
        assert outcome.state == state
        assert outcome.entries == ()


def test_ac5_resume_of_a_disconnected_player_brings_them_back(
    fx01_grid: Grid,
) -> None:
    host = make_player(0, "Ana", is_host=True)
    away = make_player(1, "Bob", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host, away])

    outcome = run_join(state, "Autre", 9, token="resume-token-number-1")

    assert outcome.state.seq == 3
    assert outcome.state.players[0] == host
    assert outcome.state.players[1] == away.model_copy(
        update={
            "state": PlayerState.ACTIVE,
            "disconnected_at": None,
            "last_seen_at": NOW,
            "last_input_at": NOW,
        }
    )
    assert outcome.entries == (
        LogEntry(
            at=NOW,
            event=PlayerStateChanged(
                seq=3, player_id="player1", state=PlayerState.ACTIVE
            ),
        ),
    )
    assert outcome.reply == (snapshot_for(outcome.state, "player1"),)
    assert outcome.close_sender is False
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.seq == 3
    assert snapshot.you == "player1"
    assert snapshot.resume_token == "resume-token-number-1"
    assert [view.nickname for view in snapshot.players] == ["Ana", "Bob"]


def test_ac5_resume_of_a_connected_player_makes_no_event(fx01_grid: Grid) -> None:
    host = make_player(0, "Ana", is_host=True)
    still_open = make_player(1, "Bob")
    state = make_state(fx01_grid, [host, still_open])

    outcome = run_join(state, "Autre", 9, token="resume-token-number-1")

    assert outcome.entries == ()
    assert outcome.state.seq == state.seq
    assert outcome.state.players[0] == host
    assert outcome.state.players[1] == still_open.model_copy(
        update={"last_seen_at": NOW, "last_input_at": NOW}
    )
    assert outcome.reply == (snapshot_for(outcome.state, "player1"),)
    assert outcome.close_sender is False


def test_ac5_resume_ignores_the_nickname_of_the_join(fx01_grid: Grid) -> None:
    away = make_player(0, "Ana", is_host=True, state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [away])

    outcome = run_join(state, "!!", 9, token="resume-token-number-0")

    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "player0"
    assert snapshot.players[0].nickname == "Ana"
    assert snapshot.players[0].is_host is True
    assert snapshot.players[0].colour == 0
    assert outcome.state.players[0].joined_seq == away.joined_seq


def test_ac5_an_unknown_token_is_ignored_and_the_join_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "Ana", is_host=True)])

    outcome = run_join(state, "Cy", 9, token=OTHER_TOKEN)

    assert len(outcome.state.players) == 2
    newcomer = outcome.state.players[1]
    assert newcomer.player_id == "joiner9"
    assert newcomer.nickname == "Cy"
    assert newcomer.resume_token == "joiner-token-number-9"
    assert len(outcome.entries) == 1


def test_ac5_websocket_a_closed_player_resumes_with_the_token(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack_b:
        with contextlib.ExitStack() as stack_a:
            _, snapshot_a = join_as(stack_a, ws_client, room_code, "Ana")
            socket_b, snapshot_b = join_as(stack_b, ws_client, room_code, "Bob")

        assert receive_message(socket_b) == PlayerStateChanged(
            seq=3, player_id=snapshot_a.you, state=PlayerState.DISCONNECTED
        )
        state = registry.room_state(room_code)
        assert state is not None
        assert len(state.players) == 2
        assert state.players[0].state is PlayerState.DISCONNECTED
        assert state.players[0].is_host is True
        assert state.players[1].is_host is False

        _, resumed = join_as(
            stack_b, ws_client, room_code, "Autre", resume_token=snapshot_a.resume_token
        )

        assert resumed.you == snapshot_a.you
        assert resumed.resume_token == snapshot_a.resume_token
        assert resumed.seq == 4
        assert resumed.players == (
            active_view(snapshot_a.you, "Ana", 0, True),
            active_view(snapshot_b.you, "Bob", 1),
        )
        assert receive_message(socket_b) == PlayerStateChanged(
            seq=4, player_id=snapshot_a.you, state=PlayerState.ACTIVE
        )
    final_state = registry.room_state(room_code)
    assert final_state is not None
    assert len(final_state.players) == 2


def test_ac5_websocket_an_unknown_token_makes_a_new_player(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        _, snapshot = join_as(
            stack, ws_client, room_code, "Cy", resume_token=OTHER_TOKEN
        )

    assert snapshot.resume_token != OTHER_TOKEN
    assert [view.nickname for view in snapshot.players] == ["Cy"]
    assert snapshot.players[0].is_host is True


def test_ac5_websocket_a_second_tab_takes_over_and_the_first_is_closed(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as second_tab_stack:
        first_tab, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        other, _ = join_as(stack, ws_client, room_code, "Bob")
        expect_joined_seqs(first_tab, [2])

        second_tab, second_snapshot = join_as(
            second_tab_stack,
            ws_client,
            room_code,
            "Ana",
            resume_token=first_snapshot.resume_token,
        )

        assert second_snapshot.you == first_snapshot.you
        assert second_snapshot.seq == 2
        assert close_code_of_next_read(first_tab) == SESSION_REPLACED
        time.sleep(SETTLE_SECONDS)
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 2
        assert state.players[0].state is PlayerState.ACTIVE
        _, third_snapshot = join_as(stack, ws_client, room_code, "Cy")
        third_view = active_view(third_snapshot.you, "Cy", 2)
        assert receive_message(other) == PlayerJoined(seq=3, player=third_view)
        assert receive_message(second_tab) == PlayerJoined(seq=3, player=third_view)


def test_ac5_websocket_closing_the_new_tab_disconnects_the_player(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with contextlib.ExitStack() as stack, contextlib.ExitStack() as second_tab_stack:
        first_tab, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        other, _ = join_as(stack, ws_client, room_code, "Bob")
        expect_joined_seqs(first_tab, [2])
        join_as(
            second_tab_stack,
            ws_client,
            room_code,
            "Ana",
            resume_token=first_snapshot.resume_token,
        )
        assert close_code_of_next_read(first_tab) == SESSION_REPLACED

        second_tab_stack.close()

        assert receive_message(other) == PlayerStateChanged(
            seq=3, player_id=first_snapshot.you, state=PlayerState.DISCONNECTED
        )


def test_ac5_session_replaced_close_code_is_4001() -> None:
    assert nock.server.SESSION_REPLACED_CLOSE_CODE == SESSION_REPLACED
    assert nock.hub.SESSION_REPLACED_CLOSE_CODE == SESSION_REPLACED


def test_ac5_browser_reloading_keeps_the_same_player(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    enter_room(page, f"{live_server}/r/{code}")
    room = page.get_by_test_id("room-page")
    player_id = room.get_attribute("data-you")
    assert player_id

    page.reload()

    expect(room).to_have_attribute("data-status", "joined")
    expect(room).to_have_attribute("data-you", player_id)
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    expect(page.get_by_test_id("roster").get_by_test_id("roster-player")).to_have_count(
        1
    )
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1
    assert state.players[0].player_id == player_id


def test_ac5_browser_a_second_tab_replaces_the_first(
    page: Page,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    enter_room(page, url)
    first_room = page.get_by_test_id("room-page")
    player_id = first_room.get_attribute("data-you")
    assert player_id
    second_page = page.context.new_page()

    enter_room(second_page, url)

    second_room = second_page.get_by_test_id("room-page")
    expect(second_room).to_have_attribute("data-status", "joined")
    expect(second_room).to_have_attribute("data-you", player_id)
    expect(first_room).to_have_attribute("data-status", "replaced")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.replaced"]
    )
    state = room_registry.room_state(code)
    assert state is not None
    assert len(state.players) == 1


def test_ac5_browser_close_4001_means_replaced_and_is_final(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, [active_view("p1", "Ana", 0, True)]))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")

    mock.close(SESSION_REPLACED)

    expect(room).to_have_attribute("data-status", "replaced")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.replaced"]
    )
    settle(page)
    expect(room).to_have_attribute("data-status", "replaced")
    assert len(mock.routes) == 1


def test_ac5_browser_player_state_changed_updates_the_roster(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)

    away = PlayerStateChanged(
        seq=4, player_id="p2", state=PlayerState.DISCONNECTED
    ).model_dump_json()
    mock.send(away)

    expect(items.nth(2)).to_have_attribute("data-state", "disconnected")
    expect(items.nth(0)).to_have_attribute("data-state", "active")
    expect(items.nth(1)).to_have_attribute("data-state", "active")
    back = PlayerStateChanged(
        seq=5, player_id="p2", state=PlayerState.ACTIVE
    ).model_dump_json()
    mock.send(back)

    expect(items.nth(2)).to_have_attribute("data-state", "active")


def test_ac5_fr_json_has_the_replaced_text() -> None:
    assert (
        load_fr()["room.status.replaced"] == "Ce salon est ouvert dans un autre onglet."
    )


# ---- AC-6: when the page joins at once ----------------------------------------------


def test_ac6_a_stored_identity_joins_at_once_with_its_token(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {"nock.identity.ABC123": STORED_IDENTITY})
    mock.wait_for_frames(1)

    assert parse_client_message(mock.received[0]) == Join(
        nickname="Ana 2", resume_token=MOCK_TOKEN
    )
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joining")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.joining"]
    )
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    settle(page)
    assert len(mock.received) == 1


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

    assert parse_client_message(mock.received[0]) == Join(
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

    assert parse_client_message(mock.received[0]) == Join(
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

    assert parse_client_message(mock.received[0]) == Join(
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
    assert mock.received == []


def test_ac6_the_form_is_prefilled_with_the_remembered_nickname(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server, {"nock.nickname": "Zo\u00e9"})

    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "nickname"
    )
    expect(page.get_by_test_id("nickname-input")).to_have_value("Zo\u00e9")
    settle(page)
    assert mock.received == []


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
    assert mock.received == []


@pytest.mark.parametrize("identity", CORRUPT_IDENTITIES)
def test_ac6_a_corrupt_identity_falls_back_to_the_catalogue_record(
    page: Page, live_server: str, identity: str
) -> None:
    items = {"nock.identity.ABC123": identity, "nock.room.ABC123": CATALOGUE_RECORD}
    mock = open_mock_room(page, live_server, items)
    mock.wait_for_frames(1)

    assert parse_client_message(mock.received[0]) == Join(
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
