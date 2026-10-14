"""Tests of spec 013, AC-2: the selections of the other players.

The rules, the real WebSocket and the outlines of the page. The shared setup is in
`spec013_harness`.

Not tested here: the loss of selections on a server restart (spec 018
`after_restart`), because nothing observable in the public interface of this spec
tells a selection from the other fields of a player there.
"""

from __future__ import annotations

import contextlib
import math
import random
import time
from pathlib import Path

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import (
    Direction,
    ErrorCode,
    ErrorMessage,
    LeaveReason,
    Ping,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    SelectCell,
    Selection,
    SelectionMoved,
)
from nock.room import RoomConfig, disconnect_player, handle_message, snapshot_for, tick
from spec013_harness import (
    NOW,
    QUIET_CONFIG,
    ROW_2_WORD,
    SETTLE_SECONDS,
    TICK_SECONDS,
    WAIT_TIMEOUT_MS,
    WS_DETECTION_SECONDS,
    FakeClock,
    Peer,
    all_remote_selections,
    background_of,
    border_of,
    cell_at,
    clear_frame,
    events_of,
    expected_tints,
    grid_from_text,
    join_two,
    letter_cells_of_fx01,
    make_dist_dir,
    open_peer,
    open_room,
    ping_and_wait,
    player_of,
    player_view,
    remote_players_on,
    room_of_players,
    roster_item,
    running_room,
    selection_events,
    selection_frame,
    settle,
    state_event,
    state_frame,
    swatch_colour,
    tinted_by_map,
)

RELAY_P95_SECONDS = 0.1
RELAY_SAMPLES = 100
DRAW_BUDGET_MS = 300


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- AC-2: selections, rules -----------------------------------------------------


@pytest.mark.parametrize(
    ("row", "column"),
    [(0, 0), (0, 2), (0, 3), (2, 0), (4, 0), (5, 1), (1, 5), (50, 50)],
    ids=[
        "clue_00",
        "clue_02",
        "clue_03",
        "clue_20",
        "clue_40",
        "below",
        "right",
        "far",
    ],
)
def test_ac2_a_selection_outside_the_letter_cells_is_refused(
    fx01_grid: Grid, row: int, column: int
) -> None:
    room = room_of_players(fx01_grid, 2)
    first = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.DOWN), NOW + 1
    )
    kept = Selection(row=1, column=1, direction=Direction.DOWN)

    outcome = handle_message(
        first.state,
        "p1",
        SelectCell(row=row, column=column, direction=Direction.ACROSS),
        NOW + 2,
    )

    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, ErrorMessage)
    assert reply.code is ErrorCode.NOT_A_LETTER_CELL
    assert outcome.to_others == ()
    assert outcome.entries == ()
    assert player_of(outcome.state, "p1").selection == kept


@pytest.mark.parametrize("direction", [Direction.ACROSS, Direction.DOWN])
@pytest.mark.parametrize(("row", "column"), [(0, 1), (1, 0), (2, 2), (4, 4)])
def test_ac2_a_selection_on_a_letter_cell_is_stored_and_relayed(
    fx01_grid: Grid, row: int, column: int, direction: Direction
) -> None:
    room = room_of_players(fx01_grid, 2)
    selection = Selection(row=row, column=column, direction=direction)

    outcome = handle_message(
        room, "p1", SelectCell(row=row, column=column, direction=direction), NOW + 1
    )

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    assert player_of(outcome.state, "p1").selection == selection
    assert player_of(outcome.state, "p2").selection is None
    assert outcome.state.seq == room.seq


def test_ac2_a_selection_equal_to_the_current_one_is_relayed_again(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    message = SelectCell(row=3, column=3, direction=Direction.DOWN)
    selection = Selection(row=3, column=3, direction=Direction.DOWN)
    first = handle_message(room, "p1", message, NOW + 1)

    second = handle_message(first.state, "p1", message, NOW + 2)

    assert second.to_others == (SelectionMoved(player_id="p1", selection=selection),)
    assert player_of(second.state, "p1").selection == selection


def test_ac2_a_later_selection_replaces_the_earlier_one(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)
    first = handle_message(
        room, "p1", SelectCell(row=1, column=1, direction=Direction.ACROSS), NOW + 1
    )

    second = handle_message(
        first.state,
        "p1",
        SelectCell(row=4, column=4, direction=Direction.DOWN),
        NOW + 2,
    )

    expected = Selection(row=4, column=4, direction=Direction.DOWN)
    assert player_of(second.state, "p1").selection == expected


def test_ac2_the_snapshot_carries_the_selections_of_the_others(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW + 1
    )

    snapshot = snapshot_for(moved.state, "p2")

    views = {view.player_id: view for view in snapshot.players}
    assert views["p1"].selection == Selection(row=2, column=3, direction=Direction.DOWN)
    assert views["p2"].selection is None


def test_ac2_disconnecting_clears_the_selection_and_relays_the_clearing(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW + 1
    )

    outcome = disconnect_player(moved.state, "p1", NOW + 5)

    assert events_of(outcome.entries) == [
        state_event(moved.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=None),)
    player = player_of(outcome.state, "p1")
    assert player.selection is None
    assert player.state is PlayerState.DISCONNECTED


def test_ac2_disconnecting_without_a_selection_relays_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = disconnect_player(room, "p1", NOW + 5)

    assert events_of(outcome.entries) == [
        state_event(3, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == ()


def test_ac2_an_idle_player_keeps_their_selection(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 1)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=2, direction=Direction.ACROSS), NOW
    )

    outcome = tick(moved.state, NOW + 120, QUIET_CONFIG)

    assert events_of(outcome.entries) == [state_event(2, "p1", PlayerState.IDLE)]
    assert outcome.to_others == ()
    assert player_of(outcome.state, "p1").selection == Selection(
        row=2, column=2, direction=Direction.ACROSS
    )


def test_ac2_a_tick_disconnecting_a_silent_player_clears_and_relays_the_selection(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
    room = room_of_players(fx01_grid, 2)
    moved = handle_message(
        room, "p1", SelectCell(row=2, column=3, direction=Direction.DOWN), NOW
    )
    awake = handle_message(moved.state, "p2", Ping(), NOW + 3)

    outcome = tick(awake.state, NOW + 6, config)

    assert events_of(outcome.entries) == [
        state_event(awake.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == (SelectionMoved(player_id="p1", selection=None),)
    silent = player_of(outcome.state, "p1")
    assert silent.state is PlayerState.DISCONNECTED
    assert silent.selection is None
    assert player_of(outcome.state, "p2").state is PlayerState.ACTIVE


def test_ac2_a_tick_disconnecting_a_silent_player_without_selection_relays_nothing(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
    room = room_of_players(fx01_grid, 2)
    awake = handle_message(room, "p2", Ping(), NOW + 3)

    outcome = tick(awake.state, NOW + 6, config)

    assert events_of(outcome.entries) == [
        state_event(awake.state.seq + 1, "p1", PlayerState.DISCONNECTED)
    ]
    assert outcome.to_others == ()


# ---- AC-2: selections through the real WebSocket -------------------------------------


def error_events(peer: Peer) -> list[ErrorMessage]:
    found: list[ErrorMessage] = []
    for message in peer.events():
        if isinstance(message, ErrorMessage):
            found.append(message)
    return found


def test_ac2_websocket_100_selections_are_relayed_to_the_other_player_only(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    cells = letter_cells_of_fx01()
    generator = random.Random(13)
    relay_seconds: list[float] = []
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
        sent: list[Selection] = []

        for number in range(1, RELAY_SAMPLES + 1):
            row, column = generator.choice(cells)
            direction = generator.choice([Direction.ACROSS, Direction.DOWN])
            sent.append(Selection(row=row, column=column, direction=direction))
            started = time.monotonic()
            peer_a.send(SelectCell(row=row, column=column, direction=direction))
            peer_b.wait_until(
                lambda target=number: len(selection_events(peer_b)) >= target,
                f"selection number {number} on B",
            )
            relay_seconds.append(time.monotonic() - started)

        received = selection_events(peer_b)
        expected = [SelectionMoved(player_id=a_id, selection=s) for s in sent]
        assert received == expected
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []
    ordered = sorted(relay_seconds)
    percentile_95 = ordered[math.ceil(0.95 * RELAY_SAMPLES) - 1]
    assert percentile_95 <= RELAY_P95_SECONDS


def test_ac2_websocket_a_selection_on_a_clue_cell_is_refused_and_not_relayed(
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

        peer_a.send(SelectCell(row=0, column=0, direction=Direction.ACROSS))
        peer_a.wait_until(lambda: len(error_events(peer_a)) == 1, "A's refusal")

        assert error_events(peer_a)[0].code is ErrorCode.NOT_A_LETTER_CELL
        time.sleep(SETTLE_SECONDS)
        assert peer_b.events() == []
        assert selection_events(peer_a) == []


def test_ac2_websocket_a_joiner_sees_the_current_selections_and_a_leaver_clears_it(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    selection = Selection(row=3, column=2, direction=Direction.DOWN)
    with (
        running_room(fx01_grid, dist_dir, fake_clock, QUIET_CONFIG) as (
            client,
            _registry,
            code,
        ),
        contextlib.ExitStack() as stack,
        contextlib.ExitStack() as a_stack,
        contextlib.ExitStack() as c_stack,
    ):
        peer_a, peer_b = join_two(a_stack, stack, client, code)
        a_id = peer_a.snapshot().you
        peer_a.send(SelectCell(row=3, column=2, direction=Direction.DOWN))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")

        peer_c = open_peer(c_stack, client, code, "Cleo")
        views = {view.player_id: view for view in peer_c.snapshot().players}
        assert views[a_id].selection == selection
        assert views[a_id].state is PlayerState.ACTIVE

        a_stack.close()
        peer_b.wait_until(
            lambda: len(selection_events(peer_b)) == 2, "the clearing of A's selection"
        )

        tail = peer_b.events()[-2:]
        assert tail == [
            PlayerStateChanged(seq=4, player_id=a_id, state=PlayerState.DISCONNECTED),
            SelectionMoved(player_id=a_id, selection=None),
        ]
        peer_d_stack = contextlib.ExitStack()
        with peer_d_stack:
            peer_d = open_peer(peer_d_stack, client, code, "Dan")
            view_of_a = {v.player_id: v for v in peer_d.snapshot().players}[a_id]
            assert view_of_a.selection is None
            assert view_of_a.state is PlayerState.DISCONNECTED


def test_ac2_websocket_a_silent_player_has_their_selection_cleared_for_the_others(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    config = RoomConfig(tick_seconds=TICK_SECONDS, silence_timeout_seconds=6)
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
        peer_a.send(SelectCell(row=3, column=2, direction=Direction.DOWN))
        peer_b.wait_until(lambda: len(selection_events(peer_b)) == 1, "A's selection")
        fake_clock.advance(3)
        ping_and_wait(peer_b)

        fake_clock.advance(3)

        peer_b.wait_until(
            lambda: len(selection_events(peer_b)) == 2,
            "the clearing of A's selection",
            WS_DETECTION_SECONDS,
        )
        tail = peer_b.events()[-2:]
        assert tail == [
            PlayerStateChanged(seq=3, player_id=a_id, state=PlayerState.DISCONNECTED),
            SelectionMoved(player_id=a_id, selection=None),
        ]
        time.sleep(SETTLE_SECONDS)
        assert selection_events(peer_a) == []


# ---- AC-2: selections in the browser ----------------------------------------


def start_outline_log(page: Page, selector: str) -> None:
    """Record in the page the time at which `selector` first matches an element."""
    page.evaluate(
        """selector => {
            window.__outlineDrawnAt = null;
            const observer = new MutationObserver(() => {
                const drawn = document.querySelector(selector) !== null;
                if (drawn && window.__outlineDrawnAt === null) {
                    window.__outlineDrawnAt = performance.now();
                }
            });
            observer.observe(document.body, { subtree: true, childList: true });
        }""",
        selector,
    )


def test_ac2_browser_the_outline_appears_within_300_ms_of_the_move(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    selector = (
        '[data-testid="cell"][data-row="2"][data-column="2"] '
        '[data-testid="remote-selection"]'
    )
    expect(page.locator(selector)).to_have_count(0)
    start_outline_log(page, selector)
    sent_at = float(page.evaluate("() => performance.now()"))

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))

    expect(page.locator(selector)).to_have_count(1, timeout=WAIT_TIMEOUT_MS)
    drawn_at = page.evaluate("() => window.__outlineDrawnAt")
    assert drawn_at is not None
    assert float(drawn_at) - sent_at <= DRAW_BUDGET_MS


def test_ac2_browser_the_selection_of_another_player_is_outlined_and_tinted(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))

    outline = cell_at(page, 2, 2).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p2")
    expect(outline).to_have_attribute("data-colour", "3")
    style, colour, width = border_of(outline)
    assert style == "dashed"
    assert width >= 2
    assert colour == swatch_colour(page, "p2")
    assert all_remote_selections(page) == 1
    expect(cell_at(page, 2, 4)).to_have_attribute("data-tinted-by", "p2")
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))
    assert background_of(cell_at(page, 2, 1)) != background_of(cell_at(page, 1, 1))


def test_ac2_browser_the_outline_colour_is_the_colour_of_that_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True),
            player_view("p2", "Bob", 1),
            player_view("p3", "Cleo", 5),
        ],
    )

    mock.send(selection_frame("p3", 4, 4, Direction.ACROSS))

    outline = cell_at(page, 4, 4).get_by_test_id("remote-selection")
    expect(outline).to_have_count(1)
    expect(outline).to_have_attribute("data-player-id", "p3")
    expect(outline).to_have_attribute("data-colour", "5")
    assert border_of(outline)[1] == swatch_colour(page, "p3")
    assert border_of(outline)[1] != swatch_colour(page, "p2")


def test_ac2_browser_the_tint_follows_the_direction_of_the_selection(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 1)],
    )

    mock.send(selection_frame("p2", 4, 4, Direction.DOWN))

    expect(cell_at(page, 1, 4)).to_have_attribute("data-tinted-by", "p2")
    column_4_word = [(1, 4), (2, 4), (3, 4), (4, 4)]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(column_4_word, "p2"))
    assert remote_players_on(page, 4, 4) == [("p2", "1")]
    assert all_remote_selections(page) == 1


def test_ac2_browser_a_null_selection_removes_the_outline_and_the_tint(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(clear_frame("p2"))

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})


def test_ac2_browser_a_new_selection_moves_the_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(selection_frame("p2", 3, 3, Direction.ACROSS))

    expect(cell_at(page, 3, 3).get_by_test_id("remote-selection")).to_have_count(1)
    expect(page.get_by_test_id("remote-selection")).to_have_count(1)
    row_3_word = [(3, 1), (3, 2), (3, 3), (3, 4)]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(row_3_word, "p2"))


def test_ac2_browser_the_same_selection_sent_again_draws_the_same_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    settle(page)

    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert all_remote_selections(page) == 1
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_the_selections_of_the_snapshot_are_drawn(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    selection = Selection(row=2, column=2, direction=Direction.ACROSS)
    open_room(
        page,
        live_server,
        fx01_grid,
        [
            player_view("p1", "Ana", 0, is_host=True),
            player_view("p2", "Bob", 3, selection=selection),
        ],
    )

    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)
    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_an_idle_player_keeps_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(state_frame(4, "p2", PlayerState.IDLE))

    expect(roster_item(page, "p2")).to_have_attribute("data-state", "idle")
    settle(page)
    assert remote_players_on(page, 2, 2) == [("p2", "3")]
    assert tinted_by_map(page) == expected_tints(dict.fromkeys(ROW_2_WORD, "p2"))


def test_ac2_browser_a_disconnected_player_loses_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    mock.send(state_frame(4, "p2", PlayerState.DISCONNECTED))

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})


def test_ac2_browser_a_player_who_leaves_loses_their_outline(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(
        page,
        live_server,
        fx01_grid,
        [player_view("p1", "Ana", 0, is_host=True), player_view("p2", "Bob", 3)],
    )
    mock.send(selection_frame("p2", 2, 2, Direction.ACROSS))
    expect(cell_at(page, 2, 2).get_by_test_id("remote-selection")).to_have_count(1)

    left = PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.LEFT)
    mock.send(left.model_dump_json())

    expect(page.get_by_test_id("remote-selection")).to_have_count(0)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-tinted-by", "")
    assert tinted_by_map(page) == expected_tints({})
