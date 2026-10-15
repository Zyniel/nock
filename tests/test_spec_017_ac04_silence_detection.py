"""Tests of spec 017, AC-4: silence is detected and shown in the roster.

The rules (`tick`, `handle_message`) are tested directly, the hub with the real
WebSocket and a fake clock, and the roster in the page with spec 040's mocked
socket. The shared setup is in `spec017_harness`.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

import nock.hub
import nock.server
from nock.grid import Grid
from nock.protocol import (
    Direction,
    EditLetter,
    Erase,
    Join,
    Ping,
    PlayerState,
    PlayerStateChanged,
    Pong,
    SelectCell,
    Snapshot,
    Undo,
)
from nock.room import (
    Disconnect,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    tick,
)
from spec017_harness import (
    NOW,
    SETTLE_SECONDS,
    TICK_SECONDS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    error_events,
    events_of,
    grid_from_text,
    has_state_change,
    join_two,
    joined_room,
    keep_seen,
    make_dist_dir,
    open_peer,
    player_of,
    running_room,
    socket_url,
    two_player_room,
    with_player,
)

SILENCE_CLOSE = 4408
ROSTER_BUDGET_MS = 300


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def pong_count(peer: Peer) -> int:
    count = 0
    for message in peer.messages():
        if isinstance(message, Pong):
            count += 1
    return count


def ping_and_wait(peer: Peer) -> None:
    """Send a ping and wait for its pong: the room has handled the ping."""
    before = pong_count(peer)
    peer.send(Ping())
    peer.wait_until(lambda: pong_count(peer) > before, "the pong of a ping")


DEFAULT_SILENCE_CONFIG = RoomConfig(tick_seconds=TICK_SECONDS)


def state_changed_frame(seq: int, player_id: str, state: PlayerState) -> str:
    event = PlayerStateChanged(seq=seq, player_id=player_id, state=state)
    return event.model_dump_json()


# ---- AC-4: the rules ---------------------------------------------------------


def silent_room(grid: Grid) -> RoomState:
    """Two players; `p1` last seen at NOW, `p2` seen 5 seconds later."""
    return with_player(two_player_room(grid), "p2", last_seen_at=NOW + 5.0)


def test_ac4_the_silence_close_code_is_4408_in_the_hub_and_the_server() -> None:
    assert nock.hub.SILENCE_CLOSE_CODE == SILENCE_CLOSE
    assert nock.server.SILENCE_CLOSE_CODE == SILENCE_CLOSE


def test_ac4_a_tick_5_9_seconds_after_the_last_frame_changes_nothing(
    fx01_grid: Grid,
) -> None:
    room = silent_room(fx01_grid)

    outcome = tick(room, NOW + 5.9)

    assert outcome.state == room
    assert outcome.entries == ()
    assert outcome.disconnects == ()


def test_ac4_a_tick_6_seconds_after_the_last_frame_disconnects_the_player(
    fx01_grid: Grid,
) -> None:
    room = silent_room(fx01_grid)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED)
    ]
    assert outcome.disconnects == (Disconnect(player_id="p1", close_code=4408),)
    assert outcome.state == disconnect_player(room, "p1", NOW + 6.0).state
    silent = player_of(outcome.state, "p1")
    assert silent.state == PlayerState.DISCONNECTED
    assert silent.disconnected_at == NOW + 6.0
    assert player_of(outcome.state, "p2").state == PlayerState.ACTIVE


def test_ac4_an_idle_player_is_disconnected_by_silence_too(fx01_grid: Grid) -> None:
    room = with_player(silent_room(fx01_grid), "p1", state=PlayerState.IDLE)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED)
    ]
    assert outcome.disconnects == (Disconnect(player_id="p1", close_code=4408),)


def test_ac4_a_player_already_disconnected_is_not_disconnected_again(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(silent_room(fx01_grid), "p2", NOW + 1.0).state
    room = keep_seen(room, NOW + 100.0)

    outcome = tick(room, NOW + 100.0)

    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert outcome.state == room


def test_ac4_the_silence_timeout_follows_the_configuration(fx01_grid: Grid) -> None:
    config = RoomConfig(silence_timeout_seconds=2.0)
    room = silent_room(fx01_grid)

    before = tick(room, NOW + 1.75, config)
    at_limit = tick(room, NOW + 2.0, config)

    assert before.entries == ()
    assert at_limit.disconnects == (Disconnect(player_id="p1", close_code=4408),)


def test_ac4_two_silent_players_are_disconnected_in_players_order(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)

    outcome = tick(room, NOW + 6.0)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=3, player_id="p1", state=PlayerState.DISCONNECTED),
        PlayerStateChanged(seq=4, player_id="p2", state=PlayerState.DISCONNECTED),
    ]
    assert outcome.disconnects == (
        Disconnect(player_id="p1", close_code=4408),
        Disconnect(player_id="p2", close_code=4408),
    )


def test_ac4_a_ping_answers_with_a_pong_and_only_refreshes_last_seen_at(
    fx01_grid: Grid,
) -> None:
    room = two_player_room(fx01_grid)
    later = NOW + 4.0

    outcome = handle_message(room, "p1", Ping(), later)

    assert outcome.reply == (Pong(),)
    assert outcome.entries == ()
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False
    assert outcome.state.seq == room.seq
    assert outcome.state.cells == room.cells
    pinged = player_of(outcome.state, "p1")
    assert pinged.last_seen_at == later
    assert pinged.last_input_at == NOW
    assert pinged.state == PlayerState.ACTIVE
    assert player_of(outcome.state, "p2") == player_of(room, "p2")


@pytest.mark.parametrize(
    "message",
    [
        EditLetter(row=1, column=0, letter="T"),
        Erase(row=1, column=1),
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        Undo(),
        Ping(),
    ],
    ids=["edit_letter", "erase", "select_cell", "undo", "ping"],
)
def test_ac4_every_message_of_a_joined_player_sets_last_seen_at(
    fx01_grid: Grid,
    message: EditLetter | Erase | SelectCell | Undo | Ping,
) -> None:
    room = two_player_room(fx01_grid)
    later = NOW + 4.0

    outcome = handle_message(room, "p1", message, later)

    assert player_of(outcome.state, "p1").last_seen_at == later
    assert player_of(outcome.state, "p2").last_seen_at == NOW


def test_ac4_a_player_who_pings_is_not_silent_at_the_tick(fx01_grid: Grid) -> None:
    room = two_player_room(fx01_grid)
    pinged = handle_message(room, "p1", Ping(), NOW + 4.0).state
    pinged = handle_message(pinged, "p2", Ping(), NOW + 4.0).state

    outcome = tick(pinged, NOW + 8.0)

    assert outcome.entries == ()
    assert outcome.disconnects == ()


# ---- AC-4: the hub with a fake clock -----------------------------------------


def test_ac4_websocket_a_ping_before_the_join_gets_a_pong_not_not_joined(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
        peer = Peer(websocket)

        peer.send(Ping())

        peer.wait_until(lambda: len(peer.messages()) >= 1, "the answer to the ping")
        time.sleep(SETTLE_SECONDS)
        assert peer.messages() == [Pong()]
        state = registry.room_state(code)
        assert state is not None
        assert state.players == ()
        peer.send(Join(nickname="Ana", resume_token=None))
        peer.wait_until(lambda: len(peer.messages()) >= 2, "the snapshot")
        assert isinstance(peer.messages()[1], Snapshot)


def test_ac4_websocket_a_ping_after_the_join_gets_a_pong(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
    ):
        peer = open_peer(stack, client, code, "Ana")

        ping_and_wait(peer)

        assert peer.events() == [Pong()]


def test_ac4_websocket_a_silent_player_is_disconnected_and_their_socket_closed(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(3)
        ping_and_wait(peer_b)

        fake_clock.advance(3)

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's silence on B",
            timeout=WS_DETECTION_SECONDS,
        )
        peer_a.wait_until(
            lambda: peer_a.close_code is not None,
            "the close of A's silent socket",
            timeout=WS_DETECTION_SECONDS,
        )
        assert peer_a.close_code == SILENCE_CLOSE
        assert peer_b.close_code is None
        ping_and_wait(peer_b)
        assert not has_state_change(
            peer_b, peer_b.snapshot().you, PlayerState.DISCONNECTED
        )
        state = registry.room_state(code)
        assert state is not None
        assert player_of(state, a_id).state == PlayerState.DISCONNECTED


def test_ac4_websocket_5_75_seconds_of_silence_changes_nothing_6_does(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(3)
        ping_and_wait(peer_b)
        fake_clock.advance(2.75)
        time.sleep(SETTLE_SECONDS)

        assert not has_state_change(peer_b, a_id, PlayerState.DISCONNECTED)
        assert peer_a.close_code is None

        fake_clock.advance(0.25)

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's silence on B",
            timeout=WS_DETECTION_SECONDS,
        )


def test_ac4_websocket_players_who_ping_every_3_seconds_are_never_disconnected(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(4):
            fake_clock.advance(3)
            ping_and_wait(peer_a)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for peer in (peer_a, peer_b):
            for message in peer.events():
                assert not isinstance(message, PlayerStateChanged)


def send_invalid_frame_and_wait(peer: Peer) -> None:
    """Send a frame that is not a message and wait for the error it gets."""
    errors_before = len(error_events(peer))
    peer.send_raw("this is not a message")
    peer.wait_until(
        lambda: len(error_events(peer)) > errors_before,
        "the error answering an invalid frame",
    )


def test_ac4_websocket_a_player_sending_only_invalid_frames_is_not_silent(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(3):
            fake_clock.advance(3)
            send_invalid_frame_and_wait(peer_a)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for message in peer_b.events():
            assert not isinstance(message, PlayerStateChanged)


def test_ac4_websocket_a_player_sending_only_repeated_joins_is_not_silent(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)

        for _ in range(3):
            fake_clock.advance(3)
            peer_a.send(Join(nickname="Ana", resume_token=None))
            time.sleep(SETTLE_SECONDS)
            ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert peer_a.close_code is None
        assert peer_b.close_code is None
        for message in peer_b.events():
            assert not isinstance(message, PlayerStateChanged)


def test_ac4_websocket_a_socket_closed_by_the_client_is_seen_without_the_clock(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, DEFAULT_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you

        a_stack.close()

        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's closed socket on B",
            timeout=WS_DETECTION_SECONDS,
        )


# ---- AC-4: the roster in the browser -----------------------------------------


def test_ac4_browser_a_state_change_shows_in_the_roster_within_300_ms(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid, seq=5)
    connection = room.connections[0]
    bob = page.locator('[data-testid="roster-player"][data-player-id="p2"]')
    ana = page.locator('[data-testid="roster-player"][data-player-id="p1"]')
    expect(bob).to_have_attribute("data-state", "active")

    connection.send(state_changed_frame(6, "p2", PlayerState.DISCONNECTED))

    expect(bob).to_have_attribute(
        "data-state", "disconnected", timeout=ROSTER_BUDGET_MS
    )
    expect(ana).to_have_attribute("data-state", "active")

    connection.send(state_changed_frame(7, "p2", PlayerState.ACTIVE))

    expect(bob).to_have_attribute("data-state", "active", timeout=ROSTER_BUDGET_MS)
