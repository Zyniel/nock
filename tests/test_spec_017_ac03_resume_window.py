"""Tests of spec 017, AC-3: reconnecting within 5 minutes restores the player.

The 300-second window is tested on the rules (`join_room`, `tick`), through the
real WebSocket with a fake clock, and with a page reloading on the live server. The
shared setup is in `spec017_harness`.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path
from typing import Protocol

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    HostChanged,
    Join,
    LeaveReason,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    Snapshot,
)
from nock.room import (
    CellState,
    RoomConfig,
    RoomState,
    disconnect_player,
    join_room,
    tick,
)
from spec017_harness import (
    LONG_SILENCE_CONFIG,
    NOW,
    SETTLE_SECONDS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    cell_at,
    cell_state,
    events_of,
    expect_cell,
    grid_from_text,
    has_state_change,
    join_two,
    keep_seen,
    make_dist_dir,
    open_peer,
    player_of,
    player_view,
    room_of_players,
    room_page,
    running_room,
    sole_error,
    token_of,
    two_player_room,
    with_cell,
)

NEW_PLAYER_ID = "new-player"
NEW_TOKEN = "new-player-token-0000"
FORM_WATCHER = (
    "window.__formSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"nickname-form\"]')) {"
    " window.__formSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def player_ids(state: RoomState) -> list[str]:
    ids: list[str] = []
    for player in state.players:
        ids.append(player.player_id)
    return ids


def player_left_events(peer: Peer) -> list[PlayerLeft]:
    found: list[PlayerLeft] = []
    for message in peer.messages():
        if isinstance(message, PlayerLeft):
            found.append(message)
    return found


# ---- AC-3: the 300 s window on the rules -------------------------------------

DISCONNECTED_AT = NOW + 10.0


def room_with_bob_disconnected(grid: Grid) -> RoomState:
    """Two players; `p2` (Bob, colour 1) wrote `B` at (1, 0) and left at t."""
    room = with_cell(
        two_player_room(grid),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=2,
            changed_by="p2",
        ),
    )
    return disconnect_player(room, "p2", DISCONNECTED_AT).state


def test_ac3_a_join_with_the_token_exactly_300_seconds_later_resumes_the_player(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    resume = Join(nickname="Autre", resume_token=token_of(2))

    outcome = join_room(room, resume, DISCONNECTED_AT + 300, NEW_PLAYER_ID, NEW_TOKEN)

    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == "p2"
    views = {view.player_id: view for view in snapshot.players}
    assert sorted(views) == ["p1", "p2"]
    assert (views["p2"].nickname, views["p2"].colour) == ("Bob", 1)
    assert views["p2"].state == PlayerState.ACTIVE
    for event in events_of(outcome.entries):
        assert not isinstance(event, PlayerLeft | PlayerJoined)
    assert player_ids(outcome.state) == ["p1", "p2"]
    assert cell_state(outcome.state, 1, 0).author == "p2"


def test_ac3_a_join_with_the_token_after_300_seconds_times_the_player_out(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    join = Join(nickname="Bob", resume_token=token_of(2))

    outcome = join_room(room, join, DISCONNECTED_AT + 300.5, NEW_PLAYER_ID, NEW_TOKEN)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT),
        PlayerJoined(seq=5, player=player_view(NEW_PLAYER_ID, "Bob", 1)),
    ]
    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID
    assert player_ids(outcome.state) == ["p1", NEW_PLAYER_ID]
    new_player = player_of(outcome.state, NEW_PLAYER_ID)
    assert new_player.resume_token == NEW_TOKEN
    assert new_player.is_host is False
    old_cell = cell_state(outcome.state, 1, 0)
    assert (old_cell.letter, old_cell.author) == ("B", "p2")


def test_ac3_the_new_player_after_a_time_out_takes_the_nickname_of_the_join(
    fx01_grid: Grid,
) -> None:
    room = room_with_bob_disconnected(fx01_grid)
    join = Join(nickname="Zoe", resume_token=token_of(2))

    outcome = join_room(room, join, DISCONNECTED_AT + 300.5, NEW_PLAYER_ID, NEW_TOKEN)

    assert player_of(outcome.state, NEW_PLAYER_ID).nickname == "Zoe"


def test_ac3_a_tick_exactly_300_seconds_after_the_disconnection_keeps_the_player(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 300)

    outcome = tick(room, DISCONNECTED_AT + 300)

    assert outcome.entries == ()
    assert outcome.state == room
    assert player_ids(outcome.state) == ["p1", "p2"]


def test_ac3_a_tick_after_300_seconds_removes_the_player_and_keeps_their_letters(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 300.5)

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT)
    ]
    assert outcome.state.seq == 4
    assert player_ids(outcome.state) == ["p1"]
    assert outcome.disconnects == ()
    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == ("B", "p2")


def test_ac3_the_window_follows_the_configuration(fx01_grid: Grid) -> None:
    config = RoomConfig(resume_window_seconds=20.0)
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 20.5)

    at_limit = tick(keep_seen(room, DISCONNECTED_AT + 20), DISCONNECTED_AT + 20, config)
    after_limit = tick(room, DISCONNECTED_AT + 20.5, config)

    assert at_limit.entries == ()
    assert events_of(after_limit.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.TIMED_OUT)
    ]


def test_ac3_a_host_who_times_out_hands_the_role_over_at_once(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(two_player_room(fx01_grid), "p1", DISCONNECTED_AT).state
    room = keep_seen(room, DISCONNECTED_AT + 300.5)

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=5, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2"]
    assert player_of(outcome.state, "p2").is_host is True


def test_ac3_when_nobody_is_left_the_next_joiner_becomes_host(
    fx01_grid: Grid,
) -> None:
    room = disconnect_player(room_of_players(fx01_grid, 1), "p1", DISCONNECTED_AT).state

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=3, player_id="p1", reason=LeaveReason.TIMED_OUT)
    ]
    assert outcome.state.players == ()
    joined = join_room(
        outcome.state,
        Join(nickname="Ana", resume_token=None),
        DISCONNECTED_AT + 301,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )
    assert player_of(joined.state, NEW_PLAYER_ID).is_host is True


def host_timing_out_room(
    grid: Grid, count: int, disconnected_players: list[str]
) -> RoomState:
    """Return `count` players where the host `p1` is ready to time out.

    `p1` disconnected at DISCONNECTED_AT; each player of `disconnected_players`
    disconnected 250 seconds later (inside their window and under the 60 seconds
    of spec 014's hand-over at the time-out tick); the others are active and
    seen at the time-out tick.
    """
    room = disconnect_player(room_of_players(grid, count), "p1", DISCONNECTED_AT).state
    for player_id in disconnected_players:
        room = disconnect_player(room, player_id, DISCONNECTED_AT + 250).state
    return keep_seen(room, DISCONNECTED_AT + 300.5)


def test_ac3_a_timed_out_host_hands_over_to_a_connected_player_not_a_disconnected(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 3, ["p2"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p3"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p2").is_host is False


def test_ac3_a_timed_out_host_hands_over_to_the_longest_present_connected_player(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 4, ["p2"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p3"),
    ]
    assert player_of(outcome.state, "p3").is_host is True
    assert player_of(outcome.state, "p4").is_host is False


def test_ac3_a_timed_out_host_hands_over_to_the_longest_present_when_all_are_away(
    fx01_grid: Grid,
) -> None:
    room = host_timing_out_room(fx01_grid, 3, ["p2", "p3"])

    outcome = tick(room, DISCONNECTED_AT + 300.5)

    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p1", reason=LeaveReason.TIMED_OUT),
        HostChanged(seq=room.seq + 2, player_id="p2"),
    ]
    assert player_ids(outcome.state) == ["p2", "p3"]
    assert player_of(outcome.state, "p2").is_host is True
    assert player_of(outcome.state, "p3").is_host is False


def test_ac3_a_disconnected_player_keeps_the_seat_for_the_whole_window(
    fx01_grid: Grid,
) -> None:
    full_room = disconnect_player(
        room_of_players(fx01_grid, 8), "p8", DISCONNECTED_AT
    ).state
    ninth = Join(nickname="Ivy", resume_token=None)

    outcome = join_room(
        full_room, ninth, DISCONNECTED_AT + 100, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_FULL
    assert outcome.state.players == full_room.players


def test_ac3_after_the_time_out_the_seat_is_free_again(fx01_grid: Grid) -> None:
    full_room = disconnect_player(
        room_of_players(fx01_grid, 8), "p8", DISCONNECTED_AT
    ).state
    after_window = DISCONNECTED_AT + 300.5
    ticked = tick(keep_seen(full_room, after_window), after_window)
    assert player_ids(ticked.state) == [f"p{n}" for n in range(1, 8)]

    outcome = join_room(
        ticked.state,
        Join(nickname="Ivy", resume_token=None),
        after_window,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert len(outcome.reply) == 1
    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID
    assert len(outcome.state.players) == 8


def test_ac3_a_timed_out_token_no_longer_resumes_after_the_tick(
    fx01_grid: Grid,
) -> None:
    room = keep_seen(room_with_bob_disconnected(fx01_grid), DISCONNECTED_AT + 301)
    ticked = tick(room, DISCONNECTED_AT + 301)

    outcome = join_room(
        ticked.state,
        Join(nickname="Bob", resume_token=token_of(2)),
        DISCONNECTED_AT + 302,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    snapshot = outcome.reply[0]
    assert isinstance(snapshot, Snapshot)
    assert snapshot.you == NEW_PLAYER_ID


# ---- AC-3: the 300 s window through the real WebSocket -----------------------


def test_ac3_websocket_a_return_within_299_seconds_resumes_the_same_player(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(299)
        time.sleep(SETTLE_SECONDS)

        assert player_left_events(peer_b) == []
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Autre", a_token)
            snapshot = second_a.snapshot()
            assert snapshot.you == a_id
            views = {view.player_id: view for view in snapshot.players}
            assert (views[a_id].nickname, views[a_id].colour) == ("Ana", 0)
            assert len(snapshot.players) == 2
            peer_b.wait_until(
                lambda: has_state_change(peer_b, a_id, PlayerState.ACTIVE),
                "A back to active on B",
            )


def test_ac3_websocket_a_return_exactly_300_seconds_later_still_resumes(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(300)
        time.sleep(SETTLE_SECONDS)

        assert player_left_events(peer_b) == []
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Autre", a_token)
            assert second_a.snapshot().you == a_id


def test_ac3_websocket_after_301_seconds_the_player_times_out_and_the_token_is_new(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, LONG_SILENCE_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(301)

        peer_b.wait_until(
            lambda: len(player_left_events(peer_b)) == 1,
            "A's time-out on B",
            timeout=WS_DETECTION_SECONDS,
        )
        assert player_left_events(peer_b) == [
            PlayerLeft(seq=4, player_id=a_id, reason=LeaveReason.TIMED_OUT)
        ]
        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Ana", a_token)
            snapshot = second_a.snapshot()
            assert snapshot.you != a_id
            ids = [view.player_id for view in snapshot.players]
            assert a_id not in ids
            assert len(ids) == 2
            new_view = next(v for v in snapshot.players if v.player_id == snapshot.you)
            assert (new_view.nickname, new_view.colour) == ("Ana", 0)


def test_ac3_websocket_the_hub_gives_its_resume_window_to_the_join(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    """A short window in the config: the join, not only the tick, applies it.

    The tick period is an hour of real time, so no tick runs: only the join of
    the returning player can time the absent one out.
    """
    config = RoomConfig(
        tick_seconds=3600.0, silence_timeout_seconds=3600, resume_window_seconds=10.0
    )
    with (
        running_room(fx01_grid, dist_dir, fake_clock, config) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        a_stack.close()
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.DISCONNECTED),
            "A's disconnection",
        )

        fake_clock.advance(11)

        with contextlib.ExitStack() as second_stack:
            second_a = open_peer(second_stack, client, code, "Ana", a_token)
            assert second_a.snapshot().you != a_id
            peer_b.wait_until(
                lambda: len(player_left_events(peer_b)) == 1,
                "A's time-out on B",
            )
            assert player_left_events(peer_b) == [
                PlayerLeft(seq=4, player_id=a_id, reason=LeaveReason.TIMED_OUT)
            ]


# ---- AC-3: a reload on the live server ---------------------------------------


def test_ac3_browser_a_reload_resumes_the_same_player_without_the_form(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        room = room_page(page)
        you_before = room.get_attribute("data-you")
        assert you_before
        cell_at(page, 1, 0).click()
        page.keyboard.press("t")
        expect_cell(page, 1, 0, "T", unconfirmed=False, author=you_before)
        ana_item = page.get_by_test_id("roster-player").filter(
            has=page.get_by_test_id("roster-nickname").get_by_text("Ana", exact=True)
        )
        colour_before = ana_item.get_attribute("data-colour")
        assert colour_before is not None
        page.add_init_script(FORM_WATCHER)

        page.reload()

        expect(room).to_have_attribute("data-status", "joined")
        expect(room).to_have_attribute("data-you", you_before)
        assert page.evaluate("window.__formSeen") is False
        expect(page.get_by_test_id("nickname-form")).to_have_count(0)
        expect(ana_item).to_have_attribute("data-colour", colour_before)
        expect_cell(page, 1, 0, "T", unconfirmed=False, author=you_before)
        bob_roster = bob_page.get_by_test_id("roster-player")
        expect(bob_roster).to_have_count(2)
        bob_view_of_ana = bob_roster.filter(
            has=bob_page.get_by_test_id("roster-nickname").get_by_text(
                "Ana", exact=True
            )
        )
        expect(bob_view_of_ana).to_have_attribute("data-state", "active")
        expect(bob_view_of_ana).to_have_attribute("data-player-id", you_before)
        expect(bob_roster).to_have_count(2)
    finally:
        bob_context.close()
