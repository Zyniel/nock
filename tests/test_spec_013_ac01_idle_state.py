"""Tests of spec 013, AC-1: the idle state and the roster.

The rules, the real WebSocket and the roster of the page. The shared setup is in
`spec013_harness`.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    Chat,
    Check,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    Flag,
    GridTarget,
    Join,
    LockRoom,
    PencilEdit,
    Ping,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Reveal,
    SelectCell,
    Selection,
    SelectionMoved,
    Snapshot,
    Undo,
    Vote,
)
from nock.room import (
    PlayerRecord,
    RoomConfig,
    RoomState,
    disconnect_player,
    handle_message,
    join_room,
    tick,
)
from spec013_harness import (
    NOW,
    QUIET_CONFIG,
    SETTLE_SECONDS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    events_of,
    grid_from_text,
    join_two,
    load_fr,
    make_dist_dir,
    open_room,
    ping_and_wait,
    player_of,
    player_view,
    room_of_players,
    roster_item,
    running_room,
    selection_events,
    socket_url,
    state_event,
    state_frame,
    swatch_colour,
    token_of,
)

IDLE_AFTER_SECONDS = 120.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- Helpers of the idle state tests ----------------------------------------


def with_player(room: RoomState, player_id: str, **update: object) -> RoomState:
    """The room with some fields of one player replaced."""
    players: list[PlayerRecord] = []
    for player in room.players:
        if player.player_id == player_id:
            players.append(player.model_copy(update=update))
        else:
            players.append(player)
    return room.model_copy(update={"players": tuple(players)})


def idle_room(grid: Grid) -> RoomState:
    """A two-player room where both players are idle (after 120 s without input)."""
    room = room_of_players(grid, 2)
    outcome = tick(room, NOW + IDLE_AFTER_SECONDS, QUIET_CONFIG)
    assert player_of(outcome.state, "p1").state is PlayerState.IDLE
    return outcome.state


# ---- AC-1: the idle state, rules -----------------------------------------------


def test_ac1_tick_just_before_120_seconds_changes_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 119.9, QUIET_CONFIG)

    assert outcome.entries == ()
    assert outcome.state == room
    assert outcome.to_others == ()


def test_ac1_tick_at_120_seconds_makes_the_player_idle(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert len(outcome.entries) == 1
    entry = outcome.entries[0]
    assert entry.event == state_event(2, "p1", PlayerState.IDLE)
    assert entry.at == NOW + 120
    assert player_of(outcome.state, "p1").state is PlayerState.IDLE
    assert outcome.state.seq == 2


def test_ac1_tick_after_the_threshold_is_also_idle(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)

    outcome = tick(room, NOW + 500, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_tick_idles_players_in_players_order(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [
        state_event(4, "p1", PlayerState.IDLE),
        state_event(5, "p2", PlayerState.IDLE),
        state_event(6, "p3", PlayerState.IDLE),
    ]


def test_ac1_only_the_players_without_recent_input_turn_idle(fx01_grid: Grid) -> None:
    room = with_player(room_of_players(fx01_grid, 2), "p1", last_input_at=NOW + 100)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(3, "p2", PlayerState.IDLE)]
    assert player_of(outcome.state, "p1").state is PlayerState.ACTIVE


def test_ac1_idleness_counts_from_last_input_not_from_last_seen(
    fx01_grid: Grid,
) -> None:
    room = with_player(room_of_players(fx01_grid, 1), "p1", last_seen_at=NOW + 119)

    outcome = tick(room, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_the_threshold_is_the_configured_one(fx01_grid: Grid) -> None:
    config = RoomConfig(idle_after_seconds=30, silence_timeout_seconds=3600)
    room = room_of_players(fx01_grid, 1)

    before = tick(room, NOW + 29.9, config)
    at_threshold = tick(room, NOW + 30, config)

    assert before.entries == ()
    assert events_of(at_threshold.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_an_idle_player_does_not_turn_idle_again(fx01_grid: Grid) -> None:
    idle = idle_room(fx01_grid)

    outcome = tick(idle, NOW + 400, QUIET_CONFIG)

    assert outcome.entries == ()
    assert outcome.state == idle


def test_ac1_a_disconnected_player_never_turns_idle(fx01_grid: Grid) -> None:
    room = with_player(
        room_of_players(fx01_grid, 2),
        "p2",
        state=PlayerState.DISCONNECTED,
        disconnected_at=NOW + 10,
    )

    outcome = tick(room, NOW + 200, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(3, "p1", PlayerState.IDLE)]
    assert player_of(outcome.state, "p2").state is PlayerState.DISCONNECTED


def test_ac1_a_select_cell_from_an_idle_player_makes_them_active_first(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)
    selection = Selection(row=1, column=1, direction=Direction.ACROSS)

    outcome = handle_message(
        idle, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 130
    )

    assert events_of(outcome.entries) == [
        state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130
    assert player.selection == selection
    assert player_of(outcome.state, "p2").state is PlayerState.IDLE


@pytest.mark.parametrize("message", [Ping(), Join(nickname="Ana", resume_token=None)])
def test_ac1_ping_and_join_are_not_input(fx01_grid: Grid, message: Ping | Join) -> None:
    idle = idle_room(fx01_grid)

    outcome = handle_message(idle, "p1", message, NOW + 130)

    assert outcome.entries == ()
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.IDLE
    assert player.last_input_at == NOW


InputMessage = (
    SelectCell
    | EditLetter
    | Erase
    | PencilEdit
    | ConfirmPencil
    | Undo
    | Check
    | Reveal
    | Vote
    | Flag
    | Chat
    | LockRoom
)

INPUT_MESSAGES: list[InputMessage] = [
    SelectCell(row=1, column=1, direction=Direction.DOWN),
    EditLetter(row=1, column=0, letter="T"),
    Erase(row=1, column=0),
    PencilEdit(row=1, column=0, letter="T"),
    ConfirmPencil(row=1, column=0),
    Undo(),
    Check(target=GridTarget()),
    Reveal(target=CellTarget(row=1, column=0)),
    Vote(vote_id=1, yes=True),
    Flag(clue=None),
    Chat(text="bonjour"),
    LockRoom(locked=True),
]


@pytest.mark.parametrize("message", INPUT_MESSAGES, ids=lambda m: m.type)
def test_ac1_any_other_message_is_input_and_reactivates_before_its_own_effect(
    fx01_grid: Grid, message: InputMessage
) -> None:
    idle = idle_room(fx01_grid)

    outcome = handle_message(idle, "p1", message, NOW + 130)

    events = events_of(outcome.entries)
    assert events[:1] == [state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)]
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130


def test_ac1_an_input_from_an_active_player_adds_no_entry_and_restarts_the_count(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 1)

    moved = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 50
    )

    assert moved.entries == ()
    assert player_of(moved.state, "p1").last_input_at == NOW + 50
    assert tick(moved.state, NOW + 169.9, QUIET_CONFIG).entries == ()
    late = tick(moved.state, NOW + 170, QUIET_CONFIG)
    assert events_of(late.entries) == [state_event(2, "p1", PlayerState.IDLE)]


def test_ac1_a_resumed_player_starts_active_with_a_fresh_last_input(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)
    away = disconnect_player(idle, "p1", NOW + 130).state

    outcome = join_room(
        away,
        Join(nickname="Ana", resume_token=token_of(1)),
        NOW + 200,
        "new-id",
        "new-token-0000000000",
        QUIET_CONFIG,
    )

    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 200


def test_ac1_a_resumed_idle_player_starts_active_with_an_entry(
    fx01_grid: Grid,
) -> None:
    idle = idle_room(fx01_grid)

    outcome = join_room(
        idle,
        Join(nickname="Ana", resume_token=token_of(1)),
        NOW + 130,
        "new-id",
        "new-token-0000000000",
        QUIET_CONFIG,
    )

    assert events_of(outcome.entries) == [
        state_event(idle.seq + 1, "p1", PlayerState.ACTIVE)
    ]
    player = player_of(outcome.state, "p1")
    assert player.state is PlayerState.ACTIVE
    assert player.last_input_at == NOW + 130
    assert player_of(outcome.state, "p2").state is PlayerState.IDLE
    snapshots = [m for m in outcome.reply if isinstance(m, Snapshot)]
    assert len(snapshots) == 1
    views = {view.player_id: view for view in snapshots[0].players}
    assert views["p1"].state is PlayerState.ACTIVE
    assert views["p2"].state is PlayerState.IDLE


# ---- AC-1: the idle state through the real WebSocket -------------------------


def has_state_change(peer: Peer, player_id: str, state: PlayerState) -> bool:
    for message in peer.messages():
        if not isinstance(message, PlayerStateChanged):
            continue
        if message.player_id == player_id and message.state == state:
            return True
    return False


def test_ac1_websocket_idle_after_120_seconds_then_active_on_the_next_selection(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    selection = Selection(row=2, column=2, direction=Direction.ACROSS)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you

        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.IDLE),
            "B idle on A",
            WS_DETECTION_SECONDS,
        )
        peer_a.send(SelectCell(row=2, column=2, direction=Direction.ACROSS))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")

        assert peer_b.events() == [
            state_event(3, a_id, PlayerState.IDLE),
            state_event(4, b_id, PlayerState.IDLE),
            state_event(5, a_id, PlayerState.ACTIVE),
            SelectionMoved(player_id=a_id, selection=selection),
        ]
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []
        assert has_state_change(peer_a, a_id, PlayerState.ACTIVE)


def test_ac1_websocket_nothing_changes_before_120_seconds(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you

        fake_clock.advance(119)
        time.sleep(SETTLE_SECONDS)
        assert peer_b.events() == []

        fake_clock.advance(1)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )


def test_ac1_websocket_a_ping_does_not_wake_an_idle_player(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )

        ping_and_wait(peer_a)
        time.sleep(SETTLE_SECONDS)

        assert not has_state_change(peer_b, a_id, PlayerState.ACTIVE)
        assert not has_state_change(peer_a, a_id, PlayerState.ACTIVE)


def open_resumed_peer(
    stack: contextlib.ExitStack, client: TestClient, code: str, token: str
) -> Peer:
    """Open a new socket that resumes with `token`; return once its snapshot came."""
    websocket = stack.enter_context(client.websocket_connect(socket_url(code)))
    peer = Peer(websocket)
    peer.send(Join(nickname="Ana", resume_token=token))
    peer.wait_until(
        lambda: any(isinstance(m, Snapshot) for m in peer.messages()),
        "the snapshot of the resumed player",
    )
    return peer


def test_ac1_websocket_a_resumed_idle_player_is_active_on_a_new_socket(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as resumed_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        a_token = peer_a.snapshot().resume_token
        fake_clock.advance(120)
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.IDLE),
            "A idle on B",
            WS_DETECTION_SECONDS,
        )
        fake_clock.advance(10)

        resumed = open_resumed_peer(resumed_stack, client, code, a_token)

        assert resumed.snapshot().you == a_id
        views = {view.player_id: view for view in resumed.snapshot().players}
        assert views[a_id].state is PlayerState.ACTIVE
        peer_b.wait_until(
            lambda: has_state_change(peer_b, a_id, PlayerState.ACTIVE),
            "A active again on B",
            WS_DETECTION_SECONDS,
        )
        state = registry.room_state(code)
        assert state is not None
        player = player_of(state, a_id)
        assert player.state is PlayerState.ACTIVE
        assert player.last_input_at == fake_clock.now


# ---- AC-1: the roster in the browser -------------------------------------------


def three_states_players() -> list[PlayerView]:
    return [
        player_view("p1", "Ana", 0, is_host=True),
        player_view("p2", "Bob", 1, state=PlayerState.IDLE),
        player_view("p3", "Cleo", 2, state=PlayerState.DISCONNECTED),
    ]


def test_ac1_browser_the_roster_shows_colour_and_state_of_each_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, three_states_players())

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)
    expected = [
        ("p1", "0", "active", "actif"),
        ("p2", "1", "idle", "inactif"),
        ("p3", "2", "disconnected", "déconnecté"),
    ]
    for position, (player_id, colour, state, text) in enumerate(expected):
        item = items.nth(position)
        expect(item).to_have_attribute("data-player-id", player_id)
        expect(item).to_have_attribute("data-colour", colour)
        expect(item).to_have_attribute("data-state", state)
        expect(item.get_by_test_id("roster-state")).to_have_text(text)


def test_ac1_browser_the_state_texts_come_from_fr_json(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    open_room(page, live_server, fx01_grid, three_states_players())

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items.nth(0).get_by_test_id("roster-state")).to_have_text(
        fr["presence.active"]
    )
    expect(items.nth(1).get_by_test_id("roster-state")).to_have_text(
        fr["presence.idle"]
    )
    expect(items.nth(2).get_by_test_id("roster-state")).to_have_text(
        fr["presence.disconnected"]
    )


def test_ac1_browser_the_three_colours_differ_on_screen(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, three_states_players())
    expect(page.get_by_test_id("roster-player")).to_have_count(3)

    backgrounds = [swatch_colour(page, player) for player in ["p1", "p2", "p3"]]

    assert "rgba(0, 0, 0, 0)" not in backgrounds
    assert len(set(backgrounds)) == 3


def test_ac1_browser_a_state_change_updates_the_item_of_that_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_states_players())
    item = roster_item(page, "p2")
    expect(item).to_have_attribute("data-state", "idle")

    mock.send(state_frame(4, "p2", PlayerState.ACTIVE))

    expect(item).to_have_attribute("data-state", "active")
    expect(item.get_by_test_id("roster-state")).to_have_text("actif")
    expect(roster_item(page, "p1")).to_have_attribute("data-state", "active")
    expect(roster_item(page, "p3")).to_have_attribute("data-state", "disconnected")

    mock.send(state_frame(5, "p1", PlayerState.IDLE))

    first = roster_item(page, "p1")
    expect(first).to_have_attribute("data-state", "idle")
    expect(first.get_by_test_id("roster-state")).to_have_text("inactif")
    expect(item).to_have_attribute("data-state", "active")


def test_ac1_browser_the_items_keep_the_join_order_after_a_change(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, three_states_players())

    mock.send(state_frame(4, "p3", PlayerState.ACTIVE))

    expect(roster_item(page, "p3")).to_have_attribute("data-state", "active")
    items = page.get_by_test_id("roster-player")
    expect(items.nth(0)).to_have_attribute("data-player-id", "p1")
    expect(items.nth(1)).to_have_attribute("data-player-id", "p2")
    expect(items.nth(2)).to_have_attribute("data-player-id", "p3")


def test_ac1_fr_json_has_the_presence_texts() -> None:
    fr = load_fr()

    assert fr["presence.active"] == "actif"
    assert fr["presence.idle"] == "inactif"
    assert fr["presence.disconnected"] == "déconnecté"
