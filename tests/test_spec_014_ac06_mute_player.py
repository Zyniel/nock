"""Tests of spec 014, AC-6: the host mutes a player.

The rules and the real WebSocket.

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.

Not tested here, with the reason:

- The effect of muting on chat and the mute button: spec 022's (AC-6 only covers
  the server rule and its log entry).
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import ErrorCode, MutePlayer, PlayerMuted
from nock.room import Outcome, RoomState, handle_message, join_room, replay
from nock.store import RoomStore
from spec014_harness import (
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    SETTLE_SECONDS,
    FakeClock,
    Peer,
    assert_nothing_changed,
    error_codes,
    events_of,
    join_in_order,
    new_guest,
    ping_and_wait,
    player_ids,
    player_of,
    removed_bob,
    room_of_players,
    sole_error,
    sole_snapshot,
    stored_room,
    token_of,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid

# ---- AC-6: mute a player (rules) --------------------------------------------


def muting(room: RoomState, sender: str, target: str, muted: bool) -> Outcome:
    message = MutePlayer(player_id=target, muted=muted)
    return handle_message(room, sender, message, NOW + 1)


def test_ac6_a_player_who_is_not_host_gets_not_host_and_nothing_changes(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = muting(room, "p2", "p3", True)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert player_of(outcome.state, "p3").muted is False
    assert_nothing_changed(room, outcome.state)


def test_ac6_a_non_host_cannot_unmute_either(fx01_grid: Grid) -> None:
    room = muting(room_of_players(fx01_grid, 3), "p1", "p3", True).state

    outcome = muting(room, "p2", "p3", False)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert player_of(outcome.state, "p3").muted is True


@pytest.mark.parametrize("muted", [True, False])
def test_ac6_the_host_cannot_mute_themselves(fx01_grid: Grid, muted: bool) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = muting(room, "p1", "p1", muted)

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").muted is False
    assert_nothing_changed(room, outcome.state)


@pytest.mark.parametrize("muted", [True, False])
def test_ac6_an_unknown_player_is_an_invalid_target(
    fx01_grid: Grid, muted: bool
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = muting(room, "p1", "zz", muted)

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


def test_ac6_a_removed_player_is_an_invalid_target(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = muting(room, "p1", "p2", True)

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()


def test_ac6_unmuting_an_unmuted_player_does_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = muting(room, "p1", "p2", False)

    assert outcome.reply == ()
    assert outcome.entries == ()
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert_nothing_changed(room, outcome.state)
    assert player_of(outcome.state, "p2").muted is False


def test_ac6_muting_a_muted_player_does_nothing(fx01_grid: Grid) -> None:
    room = muting(room_of_players(fx01_grid, 3), "p1", "p2", True).state

    outcome = muting(room, "p1", "p2", True)

    assert outcome.reply == ()
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)
    assert player_of(outcome.state, "p2").muted is True


def test_ac6_muting_sets_the_flag_and_writes_one_player_muted_entry(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = muting(room, "p1", "p2", True)

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        PlayerMuted(seq=4, player_id="p2", muted=True)
    ]
    assert outcome.state.seq == 4
    assert player_of(outcome.state, "p2").muted is True
    assert player_of(outcome.state, "p1").muted is False
    assert player_of(outcome.state, "p3").muted is False
    assert player_ids(outcome.state) == ["p1", "p2", "p3"]


def test_ac6_unmuting_a_muted_player_writes_one_entry_and_clears_the_flag(
    fx01_grid: Grid,
) -> None:
    room = muting(room_of_players(fx01_grid, 3), "p1", "p2", True).state

    outcome = muting(room, "p1", "p2", False)

    assert events_of(outcome.entries) == [
        PlayerMuted(seq=5, player_id="p2", muted=False)
    ]
    assert player_of(outcome.state, "p2").muted is False


def test_ac6_a_muted_player_appears_muted_in_the_snapshot(fx01_grid: Grid) -> None:
    room = muting(room_of_players(fx01_grid, 3), "p1", "p2", True).state
    rejoin = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    snapshot = sole_snapshot(rejoin)

    muted_flags: dict[str, bool] = {}
    for view in snapshot.players:
        muted_flags[view.player_id] = view.muted
    assert muted_flags == {"p1": False, "p2": True, "p3": False}


def test_ac6_the_flag_survives_a_replay_of_the_entries(fx01_grid: Grid) -> None:
    start = room_of_players(fx01_grid, 3)
    muted = muting(start, "p1", "p2", True)
    unmuted = muting(muted.state, "p1", "p2", False)
    muted_again = muting(unmuted.state, "p1", "p3", True)

    replayed = start
    for entry in (*muted.entries, *unmuted.entries, *muted_again.entries):
        replayed = replay(replayed, entry)

    assert player_of(replayed, "p2").muted is False
    assert player_of(replayed, "p3").muted is True
    assert player_of(replayed, "p1").muted is False
    assert replayed.seq == 6


def test_ac6_the_flag_survives_loading_the_room_from_a_store(
    fx01_grid: Grid,
) -> None:
    start = room_of_players(fx01_grid, 3)
    muted = muting(start, "p1", "p2", True)
    store = RoomStore(":memory:")
    try:
        store.create_room(start)
        store.append(start.code, muted.entries)

        loaded = store.load_room(start.code)
    finally:
        store.close()

    assert loaded is not None
    assert player_of(loaded, "p2").muted is True
    assert player_of(loaded, "p3").muted is False
    assert loaded.seq == 4


# ---- AC-6: through the real WebSocket ---------------------------------------


def muted_events(peer: Peer) -> list[PlayerMuted]:
    found: list[PlayerMuted] = []
    for message in peer.events():
        if isinstance(message, PlayerMuted):
            found.append(message)
    return found


def test_ac6_websocket_the_host_mutes_once_and_only_the_host_may(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        stored_room(fx01_grid, dist_dir, fake_clock) as (
            client,
            store,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as c_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        c_id = peer_c.snapshot().you

        peer_b.send(MutePlayer(player_id=c_id, muted=True))
        peer_a.send(MutePlayer(player_id=a_id, muted=True))
        peer_a.send(MutePlayer(player_id="zz", muted=True))
        peer_a.send(MutePlayer(player_id=b_id, muted=False))
        ping_and_wait(peer_a)
        ping_and_wait(peer_b)
        assert error_codes(peer_b) == [ErrorCode.NOT_HOST]
        assert error_codes(peer_a) == [ErrorCode.INVALID_TARGET] * 2
        assert muted_events(peer_a) == []

        peer_a.send(MutePlayer(player_id=b_id, muted=True))
        peer_a.send(MutePlayer(player_id=b_id, muted=True))
        expected = PlayerMuted(seq=4, player_id=b_id, muted=True)
        for peer in (peer_a, peer_b, peer_c):
            peer.wait_until(lambda peer=peer: muted_events(peer) == [expected], "muted")
        ping_and_wait(peer_a)
        time.sleep(SETTLE_SECONDS)

        for peer in (peer_a, peer_b, peer_c):
            assert muted_events(peer) == [expected]
        state = registry.room_state(code)
        assert state is not None
        assert player_of(state, b_id).muted is True
        assert player_of(state, c_id).muted is False
        loaded = store.load_room(code)
        assert loaded is not None
        assert player_of(loaded, b_id).muted is True
        assert player_of(loaded, c_id).muted is False
        logged: list[object] = []
        for entry in store.read_log(code):
            if isinstance(entry.event, PlayerMuted):
                logged.append(entry.event)
        assert logged == [expected]
