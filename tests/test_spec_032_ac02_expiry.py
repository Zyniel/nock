"""Tests of spec 032, AC-2: an expired room is deleted, and nobody can reach it.

Python: a registry with a fake clock on a store file holds room A, written to the
file with a share token and a log whose last edit is at t0 + 10, and room B,
registered with `register_room` when the clock reads t0 + 20, so that its last
edit time is t0 + 20; its share token is read from `room_state` before any
expiry. `expire_rooms` deletes A at t0 + 11 + LIFE, not at t0 + 10 + LIFE, and
every lookup then answers as for an unknown room; a lookup alone deletes a room
once it is expired. On a fresh room that reuses A's code, A's old token `TA` makes
a new player (spec 012's unknown token) and belongs to no member.

HTTP: the share link of a solved room, written to a store file as spec 028 AC-9
writes it (`stored_play_r`, whose `NOW` is the t0 of that part), works until the
room expires, then answers 404 as an unknown token does. The app's sweep runs when
it starts, for a registry given or created, and keeps running after a sweep that
raises, which is logged at WARNING or above.

The WebSocket part of AC-2 is in `test_spec_032_ac02_ac07_sockets.py`.

Not tested: a step in flight at the deletion (its append fails as any failed
append of spec 018 AC-4); nothing outside the hub can hold a step at that point.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

import nock.hub
import nock.room
import nock.server
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Join, PlayerJoined, PlayerState, PlayerView
from nock.recap import PublicRecap
from nock.room import RoomConfig, RoomState, handle_message, join_room, new_room
from nock.server import create_app
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec024_harness import NOW
from spec028_harness import SHARE_TOKEN, UNKNOWN_TOKEN, stored_play_r
from spec032_harness import (
    ANA,
    CODE_A,
    INDEX_HTML,
    LIFE,
    NEW_PLAYER_ID,
    NO_TICK_CONFIG,
    T0,
    TA,
    events_of,
    grid_from_text,
    make_dist_dir,
    snapshot_of,
    sweeping_config,
)

SHARE_TOKEN_A = "share-token-of-room-a"
FRESH_TOKEN = "token-of-the-fresh-room"  # the `new_resume_token` of the join
PLAY_R_T0 = NOW  # the t0 of the HTTP part: spec 028's NOW
NOT_FOUND = {"detail": "Not Found"}
WAIT_SECONDS = 5.0
POLL_SECONDS = 0.02


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def write_room_a(path: Path, grid: Grid) -> None:
    """Write room A to a store file: Ana joins at t0 and writes `T` at t0 + 10."""
    room = new_room(CODE_A, grid, T0, share_token=SHARE_TOKEN_A)
    joined = join_room(room, Join(nickname="Ana"), T0, ANA, TA)
    written = handle_message(
        joined.state, ANA, EditLetter(row=1, column=0, letter="T"), T0 + 10
    )
    store = RoomStore(path)
    try:
        store.create_room(room)
        store.append(CODE_A, [*joined.entries, *written.entries])
    finally:
        store.close()


class TwoRooms(NamedTuple):
    """AC-2's registry, its store, and what the test knows of rooms A and B."""

    registry: RoomRegistry
    store: RoomStore
    clock: FakeClock
    code_b: str
    state_b: RoomState
    token_b: str


@pytest.fixture
def two_rooms(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> Iterator[TwoRooms]:
    """Room A in the store (last edit t0 + 10), room B registered at t0 + 20."""
    path = tmp_path / "nock.sqlite3"
    write_room_a(path, fx01_grid)
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=NO_TICK_CONFIG)
    try:
        fake_clock.now = T0 + 20
        code_b = registry.register_room(fx01_grid)
        state_b = registry.room_state(code_b)
        assert state_b is not None
        assert state_b.share_token is not None
        yield TwoRooms(
            registry, store, fake_clock, code_b, state_b, state_b.share_token
        )
    finally:
        registry.close()
        store.close()


def expire_room_a(rooms: TwoRooms) -> list[str]:
    """Move the clock to t0 + 11 + LIFE and run `expire_rooms`."""
    rooms.clock.now = T0 + 11 + LIFE
    return rooms.registry.expire_rooms()


# ---- Python: expire_rooms ------------------------------------------------------


def test_ac2_the_store_finds_each_room_by_its_share_token(two_rooms: TwoRooms) -> None:
    store = two_rooms.store

    assert store.code_for_share_token(SHARE_TOKEN_A) == CODE_A
    assert store.code_for_share_token(two_rooms.token_b) == two_rooms.code_b


def test_ac2_no_room_is_deleted_exactly_30_days_after_the_last_edit_of_a(
    two_rooms: TwoRooms,
) -> None:
    two_rooms.clock.now = T0 + 10 + LIFE

    assert two_rooms.registry.expire_rooms() == []
    assert two_rooms.store.has_room(CODE_A) is True


def test_ac2_expire_rooms_deletes_the_expired_room_and_returns_its_code(
    two_rooms: TwoRooms,
) -> None:
    assert expire_room_a(two_rooms) == [CODE_A]


def test_ac2_a_deleted_room_leaves_nothing_in_the_store(two_rooms: TwoRooms) -> None:
    store = two_rooms.store
    assert len(store.read_log(CODE_A)) == 2

    expire_room_a(two_rooms)

    assert store.has_room(CODE_A) is False
    assert store.read_log(CODE_A) == []
    assert store.load_room(CODE_A) is None
    assert store.code_for_share_token(SHARE_TOKEN_A) is None
    assert store.last_edit_at(CODE_A) is None


def test_ac2_a_deleted_room_is_unknown_to_every_lookup(two_rooms: TwoRooms) -> None:
    registry = two_rooms.registry

    expire_room_a(two_rooms)

    assert registry.room_state(CODE_A) is None
    assert registry.find_room(CODE_A) is None
    assert registry.peek_room(CODE_A) is None


def test_ac2_the_room_that_is_not_expired_stays_as_it_was(two_rooms: TwoRooms) -> None:
    store = two_rooms.store

    expire_room_a(two_rooms)

    assert store.has_room(two_rooms.code_b) is True
    assert store.load_room(two_rooms.code_b) == two_rooms.state_b
    assert store.read_log(two_rooms.code_b) == []
    assert store.code_for_share_token(two_rooms.token_b) == two_rooms.code_b


def test_ac2_the_code_of_a_deleted_room_can_be_used_again(
    two_rooms: TwoRooms, fx01_grid: Grid
) -> None:
    expire_room_a(two_rooms)
    fresh = new_room(CODE_A, fx01_grid, T0 + 11 + LIFE)

    two_rooms.registry.add_room(fresh)

    assert two_rooms.registry.room_state(CODE_A) == fresh


def fresh_room_on_the_code_of_a(rooms: TwoRooms, grid: Grid) -> RoomState:
    """Expire A at t0 + 11 + LIFE, add a fresh room with its code; its state."""
    expire_room_a(rooms)
    rooms.registry.add_room(new_room(CODE_A, grid, T0 + 11 + LIFE))
    fresh = rooms.registry.room_state(CODE_A)
    assert fresh is not None
    return fresh


def test_ac2_on_the_reused_code_the_old_token_joins_as_a_new_player(
    two_rooms: TwoRooms, fx01_grid: Grid
) -> None:
    fresh = fresh_room_on_the_code_of_a(two_rooms, fx01_grid)

    outcome = join_room(
        fresh,
        Join(nickname="Ana", resume_token=TA),
        T0 + 11 + LIFE,
        NEW_PLAYER_ID,
        FRESH_TOKEN,
    )

    assert events_of(outcome) == [
        PlayerJoined(
            seq=1,
            player=PlayerView(
                player_id=NEW_PLAYER_ID,
                nickname="Ana",
                colour=0,
                state=PlayerState.ACTIVE,
                is_host=True,
                muted=False,
                selection=None,
            ),
        )
    ]
    assert outcome.entries[0].resume_token == FRESH_TOKEN
    snapshot = snapshot_of(outcome)
    assert (snapshot.you, snapshot.resume_token) == (NEW_PLAYER_ID, FRESH_TOKEN)


def test_ac2_on_the_reused_code_the_old_token_is_no_members_token(
    two_rooms: TwoRooms, fx01_grid: Grid
) -> None:
    fresh_room_on_the_code_of_a(two_rooms, fx01_grid)

    assert two_rooms.registry.member_id(CODE_A, TA) is None


def test_ac2_a_lookup_alone_deletes_a_room_once_it_is_expired(
    two_rooms: TwoRooms,
) -> None:
    two_rooms.clock.now = T0 + 21 + LIFE

    assert two_rooms.registry.room_state(two_rooms.code_b) is None
    assert two_rooms.store.has_room(two_rooms.code_b) is False
    assert two_rooms.store.code_for_share_token(two_rooms.token_b) is None


# Each lookup of "Lookups", and what it answers for an unknown room.
def look_up_room_state(registry: RoomRegistry) -> object:
    return registry.room_state(CODE_A)


def look_up_find_room(registry: RoomRegistry) -> object:
    return registry.find_room(CODE_A)


def look_up_peek_room(registry: RoomRegistry) -> object:
    return registry.peek_room(CODE_A)


def look_up_member_id(registry: RoomRegistry) -> object:
    return registry.member_id(CODE_A, TA)


def look_up_room_summaries(registry: RoomRegistry) -> object:
    key = nock.room.RoomKey(code=CODE_A, resume_token=TA)
    return registry.room_summaries([key])


@pytest.mark.parametrize(
    ("look_up", "unknown_answer"),
    [
        (look_up_room_state, None),
        (look_up_find_room, None),
        (look_up_peek_room, None),
        (look_up_member_id, None),
        (look_up_room_summaries, []),
    ],
    ids=["room_state", "find_room", "peek_room", "member_id", "room_summaries"],
)
def test_ac2_each_lookup_deletes_an_expired_room_that_only_the_store_holds(
    two_rooms: TwoRooms,
    look_up: Callable[[RoomRegistry], object],
    unknown_answer: object,
) -> None:
    two_rooms.clock.now = T0 + 11 + LIFE

    answer = look_up(two_rooms.registry)

    assert answer == unknown_answer
    assert two_rooms.store.has_room(CODE_A) is False
    assert two_rooms.store.code_for_share_token(SHARE_TOKEN_A) is None


def test_ac2_expire_rooms_returns_the_codes_in_code_point_order(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=fake_clock, store=store, config=NO_TICK_CONFIG)
    try:
        for code in ["BBBBBB", "AAAAAA", "AAAAA9"]:
            registry.add_room(new_room(code, fx01_grid, T0))
        fake_clock.now = T0 + LIFE + 1
        expired = registry.expire_rooms()
    finally:
        registry.close()
        store.close()

    assert expired == ["AAAAA9", "AAAAAA", "BBBBBB"]


# ---- The interface -------------------------------------------------------------


def test_ac2_the_sweep_runs_every_hour_by_default() -> None:
    assert RoomConfig().expiry_sweep_seconds == 3_600.0


@pytest.mark.parametrize("seconds", [0.0, -1.0])
def test_ac2_the_sweep_interval_must_be_positive(seconds: float) -> None:
    # The message names the field and its bound, not an unknown field.
    with pytest.raises(
        ValidationError, match=r"expiry_sweep_seconds\s+.*greater than 0"
    ):
        RoomConfig(expiry_sweep_seconds=seconds)


def test_ac2_the_close_code_4404_is_in_the_hub_and_the_server() -> None:
    assert nock.hub.ROOM_NOT_FOUND_CLOSE_CODE == 4404
    assert nock.server.ROOM_NOT_FOUND_CLOSE_CODE == nock.hub.ROOM_NOT_FOUND_CLOSE_CODE


# ---- The app's sweep -----------------------------------------------------------


def wait_until(condition: Callable[[], bool], what: str) -> None:
    deadline = time.monotonic() + WAIT_SECONDS
    while not condition():
        if time.monotonic() > deadline:
            pytest.fail(f"timed out after {WAIT_SECONDS}s waiting for {what}")
        time.sleep(POLL_SECONDS)


def test_ac2_the_app_sweeps_once_when_it_starts(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    write_room_a(path, fx01_grid)
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store, config=NO_TICK_CONFIG)
    fake_clock.now = T0 + 11 + LIFE
    try:
        assert store.has_room(CODE_A) is True
        # Nothing looks the room up: with the default interval of an hour, only
        # the sweep made when the app starts can delete it.
        with TestClient(create_app(rooms=registry, dist_dir=dist_dir)):
            wait_until(lambda: not store.has_room(CODE_A), "the sweep at the start")
    finally:
        registry.close()
        store.close()


def test_ac2_the_app_sweeps_the_registry_it_creates(
    tmp_path: Path,
    fx01_grid: Grid,
    dist_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Room A's last edit, t0 + 10, is decades before the real clock that a
    # registry created by the app reads.
    path = tmp_path / "data.sqlite3"
    write_room_a(path, fx01_grid)
    monkeypatch.setenv("NOCK_DATABASE", str(path))

    def room_a_is_gone() -> bool:
        reader = RoomStore(path)
        try:
            return not reader.has_room(CODE_A)
        finally:
            reader.close()

    with TestClient(create_app(dist_dir=dist_dir)):
        wait_until(room_a_is_gone, "the sweep of the registry the app created")


class FirstSweepFails(RoomRegistry):
    """A registry whose first `expire_rooms` raises `failure`, then works as usual."""

    def __init__(self, clock: FakeClock, config: RoomConfig) -> None:
        super().__init__(clock=clock, config=config)
        self.sweep_count = 0
        self.failure = RuntimeError("the first sweep fails")

    def expire_rooms(self) -> list[str]:
        self.sweep_count += 1
        if self.sweep_count == 1:
            raise self.failure
        return super().expire_rooms()


def logs_the_failure(record: logging.LogRecord, failure: BaseException) -> bool:
    """Whether a record at WARNING or above is the log of `failure`.

    The spec names no logger and no wording, so the record is known by the
    failure it carries: the exception itself (`exc_info`, as `logger.exception`
    or `exc_info=` give it), or the exception's text in its message.
    """
    if record.levelno < logging.WARNING:
        return False
    if record.exc_info is not None and record.exc_info[1] is failure:
        return True
    return str(failure) in record.getMessage()


def test_ac2_a_sweep_that_raises_is_logged_and_the_next_one_runs(
    fake_clock: FakeClock, dist_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING)
    registry = FirstSweepFails(fake_clock, sweeping_config())
    try:
        with TestClient(create_app(rooms=registry, dist_dir=dist_dir)):
            wait_until(lambda: registry.sweep_count >= 2, "the sweep after the failure")
    finally:
        registry.close()

    assert any(
        logs_the_failure(record, registry.failure) for record in caplog.records
    ), caplog.records


# ---- HTTP: the share link of a solved room -------------------------------------


@pytest.fixture
def share_registry(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> Iterator[RoomRegistry]:
    """A registry on spec 028 AC-9's store file, its fake clock starting at t0."""
    path = tmp_path / "rooms.db"
    stored_play_r(path, fx01_grid)
    fake_clock.now = PLAY_R_T0
    store = RoomStore(path)
    registry = RoomRegistry(clock=fake_clock, store=store)
    yield registry
    registry.close()
    store.close()


@pytest.fixture
def share_client(share_registry: RoomRegistry, tmp_path: Path) -> TestClient:
    """The app of the HTTP part, with an `index.html` in `tmp_path`.

    The client is not entered as a context, so the app's lifespan, and with it
    the sweep, does not run: only the lookups of the requests can delete a room.
    """
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")
    return TestClient(create_app(rooms=share_registry, dist_dir=tmp_path))


def test_ac2_http_the_share_link_works_until_the_room_expires(
    share_client: TestClient, fake_clock: FakeClock
) -> None:
    fake_clock.now = PLAY_R_T0 + 754 + LIFE

    page = share_client.get(f"/recap/{SHARE_TOKEN}")
    recap = share_client.get(f"/api/recaps/{SHARE_TOKEN}")

    assert page.status_code == 200
    assert page.text == INDEX_HTML
    assert recap.status_code == 200
    assert PublicRecap.model_validate(recap.json()) == PublicRecap(
        grid_number=1, elapsed_ms=754000, team=("Ana", "Bob")
    )


def test_ac2_http_once_the_room_expires_its_share_link_answers_404(
    share_client: TestClient, fake_clock: FakeClock
) -> None:
    fake_clock.now = PLAY_R_T0 + 754 + LIFE
    assert share_client.get(f"/api/recaps/{SHARE_TOKEN}").status_code == 200
    fake_clock.now = PLAY_R_T0 + 755 + LIFE

    page = share_client.get(f"/recap/{SHARE_TOKEN}")
    recap = share_client.get(f"/api/recaps/{SHARE_TOKEN}")

    assert (page.status_code, recap.status_code) == (404, 404)
    assert (page.json(), recap.json()) == (NOT_FOUND, NOT_FOUND)


@pytest.mark.parametrize("path", ["/recap/{token}", "/api/recaps/{token}"])
def test_ac2_http_an_expired_share_link_answers_exactly_as_an_unknown_token(
    share_client: TestClient, fake_clock: FakeClock, path: str
) -> None:
    fake_clock.now = PLAY_R_T0 + 755 + LIFE

    expired = share_client.get(path.format(token=SHARE_TOKEN))
    unknown = share_client.get(path.format(token=UNKNOWN_TOKEN))

    assert (unknown.status_code, unknown.json()) == (404, NOT_FOUND)
    assert expired.status_code == unknown.status_code
    assert expired.json() == unknown.json()
