"""Tests of spec 014, AC-3: the host role passes on after 60 seconds.

The rules, the real WebSocket with a fake clock and the browser (spec 040's mocked
socket: the page follows `host_changed`).

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    ErrorCode,
    HostChanged,
    LeaveReason,
    LockRoom,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    RemovePlayer,
)
from nock.room import Outcome, RoomConfig, RoomState, disconnect_player, join_room, tick
from spec014_harness import (
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    QUIET_CONFIG,
    QUIET_RULES,
    SETTLE_SECONDS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    error_codes,
    events_of,
    has_state_change,
    join_in_order,
    joined_mock_room,
    keep_seen,
    left_events,
    load_fr,
    new_guest,
    open_peer,
    player_ids,
    player_of,
    room_of_players,
    room_players,
    roster_item,
    running_room,
    settle,
    sole_snapshot,
    three_players,
    token_of,
    with_player,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid


def host_events(peer: Peer) -> list[HostChanged]:
    found: list[HostChanged] = []
    for message in peer.events():
        if isinstance(message, HostChanged):
            found.append(message)
    return found


# ---- AC-3: host hand-over (rules) -------------------------------------------


LEFT_AT = NOW + 10.0


def host_gone_room(grid: Grid, count: int) -> RoomState:
    """Return `count` players where the host `p1` disconnected at LEFT_AT."""
    room = room_of_players(grid, count)
    return disconnect_player(room, "p1", LEFT_AT).state


def tick_at(room: RoomState, seconds_after: float) -> Outcome:
    """Tick `seconds_after` the host left, every connected player seen then."""
    now = LEFT_AT + seconds_after
    return tick(keep_seen(room, now), now, QUIET_RULES)


def test_ac3_fr_json_holds_the_host_label() -> None:
    assert load_fr()["roster.host"] == "hôte"


def test_ac3_exactly_60_seconds_after_the_host_left_nothing_changes(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)

    outcome = tick_at(room, 60)

    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").is_host is True
    assert player_of(outcome.state, "p2").is_host is False


def test_ac3_after_more_than_60_seconds_the_longest_present_becomes_host(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = with_player(room, "p3", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p2")]
    assert outcome.state.seq == room.seq + 1
    assert player_of(outcome.state, "p2").is_host is True
    assert player_of(outcome.state, "p1").is_host is False
    assert player_of(outcome.state, "p3").is_host is False


def test_ac3_the_delay_is_the_configured_one(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    config = RoomConfig(silence_timeout_seconds=3600, host_handover_seconds=10)
    at_limit = tick(keep_seen(room, LEFT_AT + 10), LEFT_AT + 10, config)
    after_limit = tick(keep_seen(room, LEFT_AT + 10.5), LEFT_AT + 10.5, config)

    assert at_limit.entries == ()
    assert events_of(after_limit.entries) == [
        HostChanged(seq=room.seq + 1, player_id="p2")
    ]


def test_ac3_a_host_who_is_connected_never_hands_the_role_over(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = tick(keep_seen(room, NOW + 5000), NOW + 5000, QUIET_RULES)

    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").is_host is True


def test_ac3_an_idle_player_is_a_candidate_and_the_first_joined_wins(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = with_player(room, "p2", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p2")]


def test_ac3_a_disconnected_player_is_not_a_candidate(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 4)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    room = with_player(room, "p3", state=PlayerState.IDLE)

    outcome = tick_at(room, 60.5)

    assert events_of(outcome.entries) == [HostChanged(seq=room.seq + 1, player_id="p3")]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p4").is_host is False


def test_ac3_when_every_other_player_is_disconnected_the_host_stays(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    room = disconnect_player(room, "p3", LEFT_AT + 6).state

    first = tick_at(room, 61)
    later = tick_at(first.state, 120)

    assert first.entries == ()
    assert later.entries == ()
    assert player_of(later.state, "p1").is_host is True
    assert player_of(later.state, "p2").is_host is False


def test_ac3_the_rule_is_tried_again_when_someone_comes_back(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    stuck = tick_at(room, 61)
    assert stuck.entries == ()
    back = join_room(
        stuck.state,
        new_guest("Bob", token_of(2)),
        LEFT_AT + 70,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    assert sole_snapshot(back).you == "p2"

    outcome = tick_at(back.state, 71)

    assert events_of(outcome.entries) == [
        HostChanged(seq=back.state.seq + 1, player_id="p2")
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_resume_does_not_change_who_was_there_first(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 3)
    room = disconnect_player(room, "p2", LEFT_AT + 5).state
    back = join_room(
        room, new_guest("Bob", token_of(2)), LEFT_AT + 20, NEW_PLAYER_ID, NEW_TOKEN
    )
    assert sole_snapshot(back).you == "p2"

    outcome = tick_at(back.state, 61)

    assert events_of(outcome.entries) == [
        HostChanged(seq=back.state.seq + 1, player_id="p2")
    ]


def test_ac3_the_hand_over_comes_after_the_idle_step(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 2)
    now = LEFT_AT + 130
    seen = with_player(room, "p2", last_seen_at=now)

    outcome = tick(seen, now, QUIET_RULES)

    assert events_of(outcome.entries) == [
        PlayerStateChanged(seq=room.seq + 1, player_id="p2", state=PlayerState.IDLE),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_host_who_comes_back_after_the_hand_over_is_an_ordinary_player(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 2)
    handed = tick_at(room, 61)
    assert player_of(handed.state, "p2").is_host is True

    back = join_room(
        handed.state,
        new_guest("Ana", token_of(1)),
        LEFT_AT + 62,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    snapshot = sole_snapshot(back)
    assert snapshot.you == "p1"
    assert player_of(back.state, "p1").is_host is False
    assert player_of(back.state, "p2").is_host is True
    views = {view.player_id: view for view in snapshot.players}
    assert views["p1"].is_host is False
    assert views["p2"].is_host is True
    later = tick_at(back.state, 200)
    assert later.entries == ()
    assert player_of(later.state, "p2").is_host is True


def test_ac3_the_role_moves_again_when_the_new_host_is_away_too(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    first = tick_at(room, 61)
    assert player_of(first.state, "p2").is_host is True
    away = disconnect_player(first.state, "p2", LEFT_AT + 100).state

    early = tick_at(away, 160)
    late = tick_at(away, 160.5)

    assert early.entries == ()
    assert events_of(late.entries) == [HostChanged(seq=away.seq + 1, player_id="p3")]
    assert player_of(late.state, "p3").is_host is True
    assert player_of(late.state, "p2").is_host is False


def test_ac3_a_returned_ordinary_player_can_be_handed_the_role_again(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 3)
    first = tick_at(room, 61)
    back = join_room(
        first.state,
        new_guest("Ana", token_of(1)),
        LEFT_AT + 62,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    away = disconnect_player(back.state, "p2", LEFT_AT + 100).state

    outcome = tick_at(away, 161)

    assert events_of(outcome.entries) == [HostChanged(seq=away.seq + 1, player_id="p1")]
    assert player_of(outcome.state, "p1").is_host is True


def test_ac3_a_player_who_left_after_the_hand_over_leaves_without_a_new_host(
    fx01_grid: Grid,
) -> None:
    room = host_gone_room(fx01_grid, 2)
    handed = tick_at(room, 61)

    outcome = tick_at(handed.state, 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(
            seq=handed.state.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT
        )
    ]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_a_host_who_times_out_gets_one_hand_over_only(fx01_grid: Grid) -> None:
    room = host_gone_room(fx01_grid, 3)

    outcome = tick_at(room, 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p2").is_host is True


# ---- AC-3: through the real WebSocket with a fake clock ---------------------


def test_ac3_websocket_after_60_seconds_the_first_joined_becomes_host(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as b_stack,
        contextlib.ExitStack() as c_stack,
        contextlib.ExitStack() as a_again_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        c_id = peer_c.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        for peer in (peer_b, peer_c):
            peer.wait_until(
                lambda peer=peer: has_state_change(
                    peer, a_id, PlayerState.DISCONNECTED
                ),
                "A's disconnection",
            )

        fake_clock.advance(59)
        time.sleep(SETTLE_SECONDS)

        assert host_events(peer_b) == []
        assert host_events(peer_c) == []

        fake_clock.advance(2)

        for peer in (peer_b, peer_c):
            peer.wait_until(
                lambda peer=peer: len(host_events(peer)) == 1,
                "the host change",
                timeout=WS_DETECTION_SECONDS,
            )
            assert host_events(peer)[0].player_id == b_id
        time.sleep(SETTLE_SECONDS)
        assert len(host_events(peer_b)) == 1

        peer_b.send(RemovePlayer(player_id=c_id))

        removal = PlayerLeft(
            seq=host_events(peer_b)[0].seq + 1,
            player_id=c_id,
            reason=LeaveReason.REMOVED,
        )
        peer_b.wait_until(lambda: left_events(peer_b) == [removal], "B's removal of C")
        assert error_codes(peer_b) == []
        peer_a_again = open_peer(a_again_stack, client, code, "Ana", a_token)
        assert peer_a_again.snapshot().you == a_id
        views = {view.player_id: view for view in peer_a_again.snapshot().players}
        assert views[a_id].is_host is False
        assert views[b_id].is_host is True
        peer_a_again.send(LockRoom(locked=True))
        peer_a_again.wait_until(
            lambda: error_codes(peer_a_again) == [ErrorCode.NOT_HOST], "A refused"
        )
        state = registry.room_state(code)
        assert state is not None
        assert state.settings.locked is False
        assert room_players(registry, code) == [a_id, b_id]


def host_frame(seq: int, player_id: str) -> str:
    return HostChanged(seq=seq, player_id=player_id).model_dump_json()


# ---- AC-3: browser (the page follows host_changed) --------------------------


def test_ac3_browser_the_host_marker_is_on_the_host_item_only(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players("p2"), you="p3")

    expect(roster_item(page, "p2")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p3")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p2")).to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p1")).not_to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p3")).not_to_contain_text(load_fr()["roster.host"])


def test_ac3_browser_host_changed_moves_the_marker_and_gives_me_the_controls(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players("p1"), you="p3")
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)

    room.connections[0].send(host_frame(6, "p3"))

    expect(roster_item(page, "p3")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(roster_item(page, "p3")).to_contain_text(load_fr()["roster.host"])
    expect(roster_item(page, "p1")).not_to_contain_text(load_fr()["roster.host"])
    expect(page.get_by_test_id("host-panel")).to_be_visible()
    expect(page.get_by_test_id("remove-player")).to_have_count(2)
    expect(roster_item(page, "p3").get_by_test_id("remove-player")).to_have_count(0)


def test_ac3_browser_host_changed_takes_the_controls_away_from_the_old_host(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players("p1"), you="p1")
    expect(page.get_by_test_id("host-panel")).to_be_visible()
    expect(page.get_by_test_id("remove-player")).to_have_count(2)
    page_errors: list[str] = []
    page.on("pageerror", lambda error: page_errors.append(str(error)))

    room.connections[0].send(host_frame(6, "p2"))

    expect(roster_item(page, "p2")).to_have_attribute("data-host", "true")
    expect(roster_item(page, "p1")).to_have_attribute("data-host", "false")
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)
    settle(page)
    assert page_errors == []
