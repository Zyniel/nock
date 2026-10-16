"""Tests of spec 032 over the room socket with a fake clock: AC-2 and AC-7.

AC-2: with no tick changing anything and a sweep every 0.05 s, the sweep deletes
an expired room while Ana and Bob are connected and a third socket, opened to the
room, has sent no join: the three sockets are closed with 4404 within 1 second of
real time, Ana's and Bob's after nothing more than Ana's `letter_changed`, the
third after no message at all; a new socket to the code is then closed with 4404
before any message. A socket to an expired code also counts as a wrong code for
spec 011's throttle.

AC-7: ticks every 0.05 s and spec 017's resume window of 300 s. Ana writes `T` and
leaves; after `advance(301)` Bob receives her time-out within 1 second of real
time; a join with her token and another nickname, even one that spec 012 refuses,
seats her back with the same id, nickname, colour and letters, Bob receives her
`player_joined`, and the room's summary then names each member once.

Each "within 1 second of real time" check waits up to that bound for the change
and fails once it has passed; no test measures a duration. The shared setup is in
`spec032_harness` and `spec017_harness`.
"""

from __future__ import annotations

import contextlib
import json
import time
from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from fastapi.testclient import TestClient

import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    LeaveReason,
    LetterChanged,
    PlayerLeft,
    PlayerState,
    ServerMessage,
    Snapshot,
)
from nock.room import new_room
from nock.server import create_app
from nock.store import RoomStore
from spec012_harness import close_code_of_next_read
from spec017_harness import (
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    has_player_joined,
    has_state_change,
    join_two,
    socket_url,
)
from spec032_harness import (
    CODE_A,
    CODE_B,
    LIFE,
    NO_TICK_CONFIG,
    SEAT_BACK_SOCKET_CONFIG,
    T0,
    grid_from_text,
    make_dist_dir,
    post_summaries,
    refused_by_spec_012,
    snapshot_cell,
    sweeping_config,
)

ROOM_NOT_FOUND = 4404
THROTTLED = 4429
WRONG_CODE_LIMIT = 10  # spec 011 AC-3: ten wrong codes in a minute
# Made only of punctuation: spec 012 refuses it, the protocol's length does not.
REFUSED_NICKNAME = "--"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def has_letter_changed(peer: Peer) -> bool:
    return any(isinstance(message, LetterChanged) for message in peer.events())


def time_out_of(peer: Peer, player_id: str) -> PlayerLeft | None:
    """The `player_left` with reason `timed_out` of a player, None before it."""
    for message in peer.events():
        if not isinstance(message, PlayerLeft):
            continue
        if message.player_id == player_id and message.reason == LeaveReason.TIMED_OUT:
            return message
    return None


def close_code_before_any_message(client: TestClient, code: str) -> int:
    """Open a socket to a room and return the code it is closed with."""
    with client.websocket_connect(socket_url(code)) as websocket:
        return close_code_of_next_read(websocket)


def wait_for_closes(peers: list[Peer], seconds: float) -> None:
    """Wait until every peer's socket is closed, `seconds` in all, or fail.

    The peers share one deadline, `seconds` after the call.
    """
    deadline = time.monotonic() + seconds
    for peer in peers:
        left = max(deadline - time.monotonic(), 0.0)
        peer.wait_until(lambda peer=peer: peer.close_code is not None, "a close", left)


# ---- AC-2: the sweep closes the sockets of an expired room ---------------------


class SweptRoom(NamedTuple):
    """What the three sockets of AC-2's room saw, before and after its expiry."""

    closes: list[int | None]  # Ana's, Bob's, then the unjoined socket's close code
    before: list[list[ServerMessage]]  # Ana's and Bob's messages before the expiry
    after: list[list[ServerMessage]]  # their messages once closed
    unjoined: list[ServerMessage]  # every message the unjoined socket received


def sweep_with_three_sockets(
    path: Path, grid: Grid, clock: FakeClock, dist_dir: Path
) -> SweptRoom:
    """AC-2's WebSocket run, up to the three closes.

    Ana and Bob join, Ana writes `T` at (1, 0), and a third socket opens to the
    room and sends no join. Then the clock moves past the room's life, and the
    three closes must come within 1 second of real time.
    """
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store, config=sweeping_config())
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client, contextlib.ExitStack() as stack:
            ana, bob = join_two(stack, stack, client, code)
            ana.send(EditLetter(row=1, column=0, letter="T"))
            ana.wait_until(lambda: has_letter_changed(ana), "Ana's T on Ana")
            bob.wait_until(lambda: has_letter_changed(bob), "Ana's T on Bob")
            unjoined = Peer(
                stack.enter_context(client.websocket_connect(socket_url(code)))
            )
            before = [ana.messages(), bob.messages()]

            clock.advance(LIFE + 1)
            wait_for_closes([ana, bob, unjoined], WS_DETECTION_SECONDS)

            closes = [ana.close_code, bob.close_code, unjoined.close_code]
            after = [ana.messages(), bob.messages()]
            unjoined_messages = unjoined.messages()
    finally:
        registry.close()
        store.close()
    return SweptRoom(closes, before, after, unjoined_messages)


def test_ac2_websocket_the_sweep_closes_the_three_sockets_with_4404_within_a_second(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"

    swept = sweep_with_three_sockets(path, fx01_grid, fake_clock, dist_dir)

    assert swept.closes == [ROOM_NOT_FOUND, ROOM_NOT_FOUND, ROOM_NOT_FOUND]


def test_ac2_websocket_the_joined_sockets_receive_nothing_after_the_letter(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"

    swept = sweep_with_three_sockets(path, fx01_grid, fake_clock, dist_dir)

    assert isinstance(swept.before[0][-1], LetterChanged)
    assert isinstance(swept.before[1][-1], LetterChanged)
    assert swept.after == swept.before


def test_ac2_websocket_the_socket_with_no_join_receives_no_message_before_its_close(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"

    swept = sweep_with_three_sockets(path, fx01_grid, fake_clock, dist_dir)

    assert swept.closes[2] == ROOM_NOT_FOUND
    assert swept.unjoined == []


def test_ac2_websocket_a_new_socket_to_a_deleted_room_is_closed_with_4404(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=fake_clock, store=store, config=sweeping_config())
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client, contextlib.ExitStack() as stack:
            ana, bob = join_two(stack, stack, client, code)
            ana.send(EditLetter(row=1, column=0, letter="T"))
            bob.wait_until(lambda: has_letter_changed(bob), "Ana's T on Bob")
            fake_clock.advance(LIFE + 1)
            wait_for_closes([ana, bob], WS_DETECTION_SECONDS)

            new_socket = close_code_before_any_message(client, code)
    finally:
        registry.close()
        store.close()

    assert new_socket == ROOM_NOT_FOUND


def test_ac2_websocket_the_deletion_writes_nothing_and_leaves_no_room(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    store = RoomStore(tmp_path / "nock.sqlite3")
    registry = RoomRegistry(clock=fake_clock, store=store, config=sweeping_config())
    try:
        code = registry.register_room(fx01_grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client, contextlib.ExitStack() as stack:
            ana, bob = join_two(stack, stack, client, code)
            ana.send(EditLetter(row=1, column=0, letter="T"))
            bob.wait_until(lambda: has_letter_changed(bob), "Ana's T on Bob")
            fake_clock.advance(LIFE + 1)
            wait_for_closes([ana, bob], WS_DETECTION_SECONDS)
            has_room = store.has_room(code)
            log = store.read_log(code)
            state = registry.room_state(code)
    finally:
        registry.close()
        store.close()

    assert (has_room, log, state) == (False, [], None)


def test_ac2_websocket_a_socket_to_an_expired_code_counts_as_a_wrong_code(
    fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    registry = RoomRegistry(clock=fake_clock, config=NO_TICK_CONFIG)
    try:
        registry.add_room(new_room(CODE_A, fx01_grid, T0))
        fake_clock.advance(LIFE + 1)
        registry.add_room(new_room(CODE_B, fx01_grid, T0))
        # Not entered as a context: no sweep runs, so the first socket meets the
        # expired room itself, and its lookup deletes it.
        client = TestClient(create_app(rooms=registry, dist_dir=dist_dir))
        wrong_codes: list[int] = []
        for _ in range(WRONG_CODE_LIMIT):
            wrong_codes.append(close_code_before_any_message(client, CODE_A))
        eleventh = close_code_before_any_message(client, CODE_B)
    finally:
        registry.close()

    assert wrong_codes == [ROOM_NOT_FOUND] * WRONG_CODE_LIMIT
    assert eleventh == THROTTLED


# ---- AC-7: a seat back over the room socket ------------------------------------


class TimedOut(NamedTuple):
    """Ana's room once Bob has received her time-out."""

    client: TestClient
    code: str
    bob: Peer
    ana_id: str
    ana_token: str


@contextlib.contextmanager
def ana_timed_out(
    grid: Grid, dist_dir: Path, clock: FakeClock, path: Path
) -> Iterator[TimedOut]:
    """Ana and Bob join, Ana writes `T` at (1, 0), leaves and times out.

    After `advance(301)`, Bob's `player_left` must come within 1 second of real
    time: the wait for it lasts at most that long.
    """
    store = RoomStore(path)
    registry = RoomRegistry(clock=clock, store=store, config=SEAT_BACK_SOCKET_CONFIG)
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with (
            TestClient(app) as client,
            contextlib.ExitStack() as bob_stack,
            contextlib.ExitStack() as ana_stack,
        ):
            ana, bob = join_two(ana_stack, bob_stack, client, code)
            ana_id = ana.snapshot().you
            ana_token = ana.snapshot().resume_token
            ana.send(EditLetter(row=1, column=0, letter="T"))
            bob.wait_until(lambda: has_letter_changed(bob), "Ana's T on Bob")
            ana_stack.close()
            bob.wait_until(
                lambda: has_state_change(bob, ana_id, PlayerState.DISCONNECTED),
                "Ana's disconnection on Bob",
            )

            clock.advance(301)
            bob.wait_until(
                lambda: time_out_of(bob, ana_id) is not None,
                "Ana's time-out on Bob",
                timeout=WS_DETECTION_SECONDS,
            )
            yield TimedOut(client, code, bob, ana_id, ana_token)
    finally:
        registry.close()
        store.close()


def first_answer_to_a_join_with_the_token(
    stack: contextlib.ExitStack, timed_out: TimedOut, nickname: str
) -> ServerMessage:
    """Join on a new socket with Ana's token and `nickname`; the first answer."""
    websocket = stack.enter_context(
        timed_out.client.websocket_connect(socket_url(timed_out.code))
    )
    peer = Peer(websocket)
    join = {"type": "join", "nickname": nickname, "resume_token": timed_out.ana_token}
    peer.send_raw(json.dumps(join))
    peer.wait_until(
        lambda: peer.messages() != [],
        f"the answer to the join with Ana's token as {nickname!r}",
    )
    return peer.messages()[0]


def join_with_the_token(stack: contextlib.ExitStack, timed_out: TimedOut) -> Snapshot:
    """Join on a new socket with Ana's token and another nickname; its snapshot."""
    answer = first_answer_to_a_join_with_the_token(stack, timed_out, "Autre")
    assert isinstance(answer, Snapshot), answer
    return answer


def test_ac7_websocket_bob_receives_the_time_out_within_a_second(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    # `ana_timed_out` fails unless the time-out comes within the second.
    with ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out:
        left = time_out_of(timed_out.bob, timed_out.ana_id)

    assert left is not None
    assert (left.player_id, left.reason) == (timed_out.ana_id, LeaveReason.TIMED_OUT)


def test_ac7_websocket_a_join_with_the_token_after_the_time_out_gives_the_same_id(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    with (
        ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out,
        contextlib.ExitStack() as stack,
    ):
        snapshot = join_with_the_token(stack, timed_out)

    assert snapshot.you == timed_out.ana_id
    assert snapshot.resume_token == timed_out.ana_token


def test_ac7_websocket_the_player_seated_back_keeps_nickname_colour_and_letters(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    with (
        ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out,
        contextlib.ExitStack() as stack,
    ):
        snapshot = join_with_the_token(stack, timed_out)

    views = {view.player_id: view for view in snapshot.players}
    assert timed_out.ana_id in views
    ana_view = views[timed_out.ana_id]
    assert (ana_view.nickname, ana_view.colour) == ("Ana", 0)
    assert snapshot_cell(snapshot, 1, 0).author == timed_out.ana_id


def test_ac7_websocket_a_join_with_the_token_and_a_refused_nickname_seats_her_back(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    assert refused_by_spec_012(REFUSED_NICKNAME) is True
    path = tmp_path / "nock.sqlite3"
    with (
        ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out,
        contextlib.ExitStack() as stack,
    ):
        answer = first_answer_to_a_join_with_the_token(
            stack, timed_out, REFUSED_NICKNAME
        )

    assert isinstance(answer, Snapshot), answer
    assert answer.you == timed_out.ana_id
    views = {view.player_id: view for view in answer.players}
    assert views[timed_out.ana_id].nickname == "Ana"


def test_ac7_websocket_bob_receives_the_player_joined_of_the_same_id(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    with (
        ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out,
        contextlib.ExitStack() as stack,
    ):
        join_with_the_token(stack, timed_out)
        timed_out.bob.wait_until(
            lambda: has_player_joined(timed_out.bob, timed_out.ana_id),
            "the player_joined of Ana's id on Bob",
        )


def test_ac7_http_after_the_seat_back_the_summary_names_each_member_once(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, dist_dir: Path
) -> None:
    path = tmp_path / "nock.sqlite3"
    with (
        ana_timed_out(fx01_grid, dist_dir, fake_clock, path) as timed_out,
        contextlib.ExitStack() as stack,
    ):
        join_with_the_token(stack, timed_out)
        response = post_summaries(
            timed_out.client, [(timed_out.code, timed_out.ana_token)]
        )

    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, list)
    assert len(body) == 1
    summary = nock.room.RoomSummary.model_validate(body[0])
    assert summary.players == ("Bob", "Ana")
