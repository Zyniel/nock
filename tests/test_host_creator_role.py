"""Tests of lobby/host, AC-11 to AC-14: the creator's player is host whenever
connected, and no stand-in keeps them out.

AC-11 runs over the room socket, with the app of `host_harness` (the creator comes
from a signed-in `POST /api/rooms`, the session from the socket's cookie). AC-12 to
AC-14 run on the rules with exact clock values: `join_room` with `account_id`,
`tick`, `handle_message`. The page of AC-11 is in `test_host_creator_pages.py`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from host_harness import (
    AWAY_AT,
    HAND_OVER_AT,
    HAND_OVER_SECONDS,
    LEA_ACCOUNT,
    TIMED_OUT_AT,
    away,
    event_types,
    events_without_pongs,
    host_app,
    host_changes,
    host_flags,
    host_ids,
    lea_creates_a_room,
    lea_joins,
    open_member,
    received_text,
    room_with_creator,
    room_without_lea,
    stand_in_room,
    ticked,
    wait_for_host,
    wait_for_message,
    wait_for_state,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    HostChanged,
    LeaveReason,
    LockRoom,
    MutePlayer,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    RemovePlayer,
)
from nock.room import Outcome, RoomState, handle_message, join_room
from spec014_harness import (
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    QUIET_RULES,
    assert_nothing_changed,
    events_of,
    new_guest,
    ping_and_wait,
    player_ids,
    player_of,
    sole_error,
    token_of,
    with_player,
)
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


# ---- AC-11: the creator's join over the sockets ------------------------------------


def test_ac11_the_creators_join_tells_the_host_player_joined_then_host_changed(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        room = lea_creates_a_room(app)
        with contextlib.ExitStack() as bob_stack, contextlib.ExitStack() as lea_stack:
            bob = open_member(bob_stack, app.client, room.code, "Bob")
            bob_id = bob.snapshot().you
            bob_roster = host_flags(bob.snapshot().players)

            lea = open_member(
                lea_stack, app.client, room.code, "Lea", None, room.session
            )
            lea_id = lea.snapshot().you
            wait_for_message(bob, HostChanged)
            ping_and_wait(bob)
            bob_events = events_without_pongs(bob)
            heard = received_text(bob) + received_text(lea)

    assert bob_roster == {bob_id: True}
    assert event_types(bob_events) == ["player_joined", "host_changed"]
    joined, changed = bob_events
    assert isinstance(joined, PlayerJoined)
    assert isinstance(changed, HostChanged)
    assert joined.player.player_id == lea_id
    assert changed.player_id == lea_id
    assert changed.seq == joined.seq + 1
    assert host_flags(lea.snapshot().players) == {bob_id: False, lea_id: True}
    assert room.account_id not in heard


def test_ac11_a_creator_who_joins_her_own_room_first_gets_no_host_changed(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app:
        room = lea_creates_a_room(app)
        with contextlib.ExitStack() as stack:
            lea = open_member(stack, app.client, room.code, "Lea", None, room.session)
            ping_and_wait(lea)
            lea_events = events_without_pongs(lea)

    assert host_flags(lea.snapshot().players) == {lea.snapshot().you: True}
    assert lea_events == []


# ---- AC-12: the role comes and goes with the creator's player ----------------------


def test_ac12_her_resume_after_the_hand_over_gives_one_host_changed(
    fx01_grid: Grid,
) -> None:
    state = away(room_with_creator(fx01_grid), "p1", AWAY_AT)
    state, handed = ticked(state, HAND_OVER_AT)

    state, events, snapshot = lea_joins(state, HAND_OVER_AT + 1, token_of(1))

    assert host_changes(handed) == ["p2"]
    assert host_changes(events) == ["p1"]
    assert "player_joined" not in event_types(events)
    assert host_ids(state) == ["p1"]
    assert host_flags(snapshot.players) == {"p1": True, "p2": False, "p3": False}


def test_ac12_her_seat_back_gives_player_joined_then_host_changed(
    fx01_grid: Grid,
) -> None:
    state = away(room_with_creator(fx01_grid), "p1", AWAY_AT)
    state, left = ticked(state, TIMED_OUT_AT)

    state, events, snapshot = lea_joins(state, TIMED_OUT_AT + 1, token_of(1))

    assert event_types(left) == ["player_left", "host_changed"]
    assert host_changes(left) == ["p2"]
    assert event_types(events) == ["player_joined", "host_changed"]
    assert host_changes(events) == ["p1"]
    assert host_ids(state) == ["p1"]
    assert host_flags(snapshot.players)["p1"] is True


@pytest.mark.parametrize("presence", [PlayerState.ACTIVE, PlayerState.IDLE])
def test_ac12_a_tick_gives_a_connected_creator_the_role_back(
    fx01_grid: Grid, presence: PlayerState
) -> None:
    state = room_with_creator(fx01_grid)
    state = with_player(state, "p1", is_host=False, state=presence)
    state = with_player(state, "p2", is_host=True)

    state, events = ticked(state, NOW + 20)

    assert host_changes(events) == ["p1"]
    assert host_ids(state) == ["p1"]


@pytest.mark.parametrize("seconds_away", [1, 61, 200])
def test_ac12_no_tick_gives_a_disconnected_creator_the_role(
    fx01_grid: Grid, seconds_away: int
) -> None:
    state = room_with_creator(fx01_grid)
    state = with_player(state, "p1", is_host=False)
    state = with_player(state, "p2", is_host=True)
    state = away(state, "p1", AWAY_AT)

    state, events = ticked(state, AWAY_AT + seconds_away)

    assert host_changes(events) == []
    assert host_ids(state) == ["p2"]


def test_ac12_her_token_alone_gives_the_role_back(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as lea_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        room = lea_creates_a_room(app)
        lea = open_member(lea_stack, app.client, room.code, "Lea", None, room.session)
        lea_id = lea.snapshot().you
        lea_token = lea.snapshot().resume_token
        bob = open_member(bob_stack, app.client, room.code, "Bob")
        bob_id = bob.snapshot().you
        lea_stack.close()
        wait_for_state(app.registry, room.code, lea_id, PlayerState.DISCONNECTED)
        fake_clock.advance(HAND_OVER_SECONDS + 1)
        wait_for_host(app.registry, room.code, bob_id)

        with contextlib.ExitStack() as back_stack:
            back = open_member(back_stack, app.client, room.code, "Lea", lea_token)
            bob.wait_until(
                lambda: host_changes(bob.events()) == [bob_id, lea_id],
                "the host_changed of Lea's return",
            )
            ping_and_wait(bob)
            bob_events = events_without_pongs(bob)

    assert "player_joined" not in event_types(bob_events)
    assert host_flags(back.snapshot().players) == {lea_id: True, bob_id: False}


# ---- AC-13: a stand-in host cannot touch the creator's player ----------------------


@pytest.mark.parametrize(
    "message",
    [RemovePlayer(player_id="p1"), MutePlayer(player_id="p1", muted=True)],
    ids=["remove", "mute"],
)
def test_ac13_a_stand_in_host_gets_invalid_target_on_the_creators_player(
    fx01_grid: Grid, message: RemovePlayer | MutePlayer
) -> None:
    before = stand_in_room(fx01_grid)

    outcome = handle_message(before, "p2", message, HAND_OVER_AT + 1, QUIET_RULES)

    assert sole_error(outcome.reply).code == ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert_nothing_changed(before, outcome.state)
    assert player_of(outcome.state, "p1").muted is False


def test_ac13_the_stand_in_host_still_removes_others_and_the_creator_removes_him(
    fx01_grid: Grid,
) -> None:
    state = stand_in_room(fx01_grid)

    removal = handle_message(
        state, "p2", RemovePlayer(player_id="p3"), HAND_OVER_AT + 1, QUIET_RULES
    )
    back, _, _ = lea_joins(removal.state, HAND_OVER_AT + 2, token_of(1))
    lea_removes = handle_message(
        back, "p1", RemovePlayer(player_id="p2"), HAND_OVER_AT + 3, QUIET_RULES
    )

    removed = events_of(removal.entries)
    assert event_types(removed) == ["player_left"]
    left = removed[0]
    assert isinstance(left, PlayerLeft)
    assert (left.player_id, left.reason) == ("p3", LeaveReason.REMOVED)
    assert player_ids(removal.state) == ["p1", "p2"]
    assert host_ids(back) == ["p1"]
    assert player_ids(lea_removes.state) == ["p1"]


# ---- AC-14: a lock does not keep the creator's session out -------------------------


def locked_by(state: RoomState, player_id: str, now: float) -> RoomState:
    """The room after the host `player_id` locked it."""
    lock = handle_message(state, player_id, LockRoom(locked=True), now, QUIET_RULES)
    assert lock.state.settings.locked is True
    return lock.state


def join_from_the_session(state: RoomState, nickname: str, now: float) -> Outcome:
    """A signed-in Lea's join with no token, and the outcome as it is."""
    return join_room(
        state,
        new_guest(nickname),
        now,
        NEW_PLAYER_ID,
        NEW_TOKEN,
        account_id=LEA_ACCOUNT,
    )


def test_ac14_a_locked_room_refuses_cy_back_but_seats_the_creator_back(
    fx01_grid: Grid,
) -> None:
    state = away(room_with_creator(fx01_grid), "p1", AWAY_AT)
    state = away(state, "p3", AWAY_AT)
    state, _ = ticked(state, TIMED_OUT_AT)
    assert player_ids(state) == ["p2"]
    state = locked_by(state, "p2", TIMED_OUT_AT + 1)
    now = TIMED_OUT_AT + 2

    cy = join_room(state, new_guest("Cy", token_of(3)), now, NEW_PLAYER_ID, NEW_TOKEN)
    back, events, _ = lea_joins(state, now, token_of(1))

    assert sole_error(cy.reply).code == ErrorCode.ROOM_LOCKED
    assert cy.close_sender is True
    assert player_ids(cy.state) == ["p2"]
    assert event_types(events) == ["player_joined", "host_changed"]
    assert player_ids(back) == ["p2", "p1"]
    assert host_ids(back) == ["p1"]


def test_ac14_a_new_device_of_the_creator_joins_a_locked_room_as_host(
    fx01_grid: Grid,
) -> None:
    state = locked_by(room_without_lea(fx01_grid, 2), "p2", NOW + 1)
    now = NOW + 2

    stranger = join_room(state, new_guest("Zoe"), now, "p-zoe", "token-of-zoe-0001")
    lea = join_from_the_session(state, "Lea", now)

    assert sole_error(stranger.reply).code == ErrorCode.ROOM_LOCKED
    assert event_types(events_of(lea.entries)) == ["player_joined", "host_changed"]
    assert player_ids(lea.state) == ["p2", "p3", NEW_PLAYER_ID]
    assert host_ids(lea.state) == [NEW_PLAYER_ID]


def test_ac14_a_full_room_refuses_the_creator_as_anyone(fx01_grid: Grid) -> None:
    state = locked_by(room_without_lea(fx01_grid, 8), "p2", NOW + 1)

    lea = join_from_the_session(state, "Lea", NOW + 2)

    assert sole_error(lea.reply).code == ErrorCode.ROOM_FULL
    assert lea.close_sender is True
    assert player_ids(lea.state) == player_ids(state)
