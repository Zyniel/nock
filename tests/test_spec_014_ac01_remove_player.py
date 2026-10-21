"""Tests of spec 014, AC-1: the host removes a player.

The rules, the real WebSocket and the browser (the live server with two contexts,
and spec 040's mocked socket).

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.

Not tested here, with the reason:

- The `disconnects` entry when the removed player has no open connection: the spec
  says the hub skips it, and does not say whether the rule still returns it.
"""

from __future__ import annotations

import contextlib
import json
import time
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Dialog, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import ErrorCode, LeaveReason, PlayerLeft, RemovePlayer
from nock.room import CellState, RoomState, disconnect_player, handle_message, join_room
from spec014_harness import (
    FORM_TIMEOUT_MS,
    IDENTITY_KEY,
    LOSS_BUDGET_MS,
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    QUIET_CONFIG,
    SETTLE_SECONDS,
    SNAPSHOT_TOKEN,
    EnterRoom,
    FakeClock,
    advance_page,
    assert_nothing_changed,
    banner,
    cell_state,
    error_codes,
    events_of,
    host_acts,
    join_in_order,
    joined_mock_room,
    left_events,
    load_fr,
    locked,
    new_guest,
    open_peer,
    open_refused_peer,
    ping_and_wait,
    player_ids,
    player_of,
    reach_refusal,
    removed_bob,
    room_of_players,
    room_page,
    room_players,
    roster_item,
    running_room,
    settle,
    sole_error,
    sole_snapshot,
    three_players,
    token_of,
    wait_until,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid

FORM_WATCHER = (
    "window.__formSeen = false;"
    "new MutationObserver(() => {"
    " if (document.querySelector('[data-testid=\"nickname-form\"]')) {"
    " window.__formSeen = true; } })"
    ".observe(document, { childList: true, subtree: true });"
)


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


# ---- AC-1: remove a player (rules) ------------------------------------------


def test_ac1_fr_json_holds_the_removal_texts() -> None:
    fr = load_fr()

    assert fr["host.remove"] == "Retirer"
    assert fr["host.remove_label"] == "Retirer {name} du salon"
    assert fr["room.status.removed"] == "Vous avez été retiré de ce salon."


def test_ac1_removing_a_player_gives_one_player_left_removed_entry(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        PlayerLeft(seq=4, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert outcome.state.seq == 4
    assert player_ids(outcome.state) == ["p1", "p3"]


def test_ac1_the_removed_token_is_banned_and_only_that_one(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.state.removed_tokens == (token_of(2),)


def test_ac1_the_removed_player_gets_a_disconnect_with_error_removed(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert len(outcome.disconnects) == 1
    disconnect = outcome.disconnects[0]
    assert disconnect.player_id == "p2"
    assert disconnect.close_code == 1000
    assert disconnect.error is not None
    assert disconnect.error.code is ErrorCode.REMOVED


def test_ac1_the_seat_colour_and_nickname_are_freed(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(room, new_guest("Bob"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    snapshot = sole_snapshot(outcome)
    views = {view.player_id: view for view in snapshot.players}
    assert views[NEW_PLAYER_ID].nickname == "BOB"
    assert views[NEW_PLAYER_ID].colour == 1
    assert len(snapshot.players) == 3


def test_ac1_a_full_room_has_a_seat_after_a_removal(fx01_grid: Grid) -> None:
    room = removed_bob(room_of_players(fx01_grid, 8))

    outcome = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_snapshot(outcome).you == NEW_PLAYER_ID
    assert len(outcome.state.players) == 8


def test_ac1_the_letters_of_the_removed_player_stay_with_their_author(
    fx01_grid: Grid,
) -> None:
    room = with_cell(
        room_of_players(fx01_grid, 3),
        CellState(
            row=1,
            column=0,
            letter="B",
            author="p2",
            changed_seq=3,
            changed_by="p2",
        ),
    )

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    cell = cell_state(outcome.state, 1, 0)
    assert (cell.letter, cell.author) == ("B", "p2")
    assert outcome.state.cells == room.cells


def test_ac1_a_disconnected_player_can_be_removed(fx01_grid: Grid) -> None:
    room = disconnect_player(room_of_players(fx01_grid, 3), "p2", NOW + 0.5).state

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        PlayerLeft(seq=room.seq + 1, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert player_ids(outcome.state) == ["p1", "p3"]
    assert outcome.state.removed_tokens == (token_of(2),)


def test_ac1_a_player_who_is_not_host_gets_not_host_and_nothing_changes(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = handle_message(room, "p2", RemovePlayer(player_id="p3"), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_non_host_cannot_remove_the_host_either(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = handle_message(room, "p2", RemovePlayer(player_id="p1"), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert_nothing_changed(room, outcome.state)


@pytest.mark.parametrize("target", ["p1", "zz"])
def test_ac1_removing_oneself_or_an_unknown_player_is_an_invalid_target(
    fx01_grid: Grid, target: str
) -> None:
    room = room_of_players(fx01_grid, 3)

    outcome = host_acts(room, RemovePlayer(player_id=target))

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert outcome.entries == ()
    assert outcome.disconnects == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_player_removed_twice_is_an_invalid_target_the_second_time(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = host_acts(room, RemovePlayer(player_id="p2"))

    assert sole_error(outcome.reply).code is ErrorCode.INVALID_TARGET
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_join_with_the_removed_token_is_refused_as_removed(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


def test_ac1_a_join_without_a_token_after_a_removal_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(room, new_guest("Bob"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is False
    snapshot = sole_snapshot(outcome)
    assert snapshot.you == NEW_PLAYER_ID
    assert snapshot.resume_token == NEW_TOKEN
    assert player_of(outcome.state, NEW_PLAYER_ID).is_host is False


def test_ac1_a_join_with_another_token_after_a_removal_is_a_new_player(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 3))

    outcome = join_room(
        room,
        new_guest("Bob", "some-other-token-0001"),
        NOW + 2,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == NEW_PLAYER_ID


def test_ac1_removed_is_answered_before_locked_full_and_nickname(
    fx01_grid: Grid,
) -> None:
    room = removed_bob(room_of_players(fx01_grid, 8))
    refilled = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)
    full_room = refilled.state
    assert len(full_room.players) == 8
    locked_full_room = locked(full_room)

    outcome = join_room(
        locked_full_room,
        new_guest("!!", token_of(2)),
        NOW + 3,
        "another-player",
        "another-token-0000000",
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True
    assert outcome.entries == ()


# ---- AC-1: through the real WebSocket ---------------------------------------


def test_ac1_websocket_the_host_removes_a_player_who_is_closed_and_banned(
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
        contextlib.ExitStack() as again_stack,
    ):
        peer_a, peer_b, peer_c = join_in_order(
            [a_stack, b_stack, c_stack], client, code
        )
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        c_id = peer_c.snapshot().you
        b_token = peer_b.snapshot().resume_token

        peer_a.send(RemovePlayer(player_id=b_id))

        removal = PlayerLeft(seq=4, player_id=b_id, reason=LeaveReason.REMOVED)
        peer_a.wait_until(lambda: left_events(peer_a) == [removal], "A told")
        peer_c.wait_until(lambda: left_events(peer_c) == [removal], "C told")
        peer_b.wait_until(
            lambda: peer_b.close_code is not None, "the close of B's socket"
        )
        assert peer_b.close_code == 1000
        assert error_codes(peer_b) == [ErrorCode.REMOVED]
        assert room_players(registry, code) == [a_id, c_id]

        refused = open_refused_peer(again_stack, client, code, "Bob", b_token)

        assert refused.close_code == 1000
        assert len(refused.messages()) == 1
        assert error_codes(refused) == [ErrorCode.REMOVED]
        assert room_players(registry, code) == [a_id, c_id]
        state = registry.room_state(code)
        assert state is not None
        assert state.removed_tokens == (b_token,)


def test_ac1_websocket_a_new_socket_without_a_token_joins_after_a_removal(
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
        contextlib.ExitStack() as new_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        b_id = peer_b.snapshot().you
        peer_a.send(RemovePlayer(player_id=b_id))
        peer_b.wait_until(lambda: peer_b.close_code is not None, "B closed")

        newcomer = open_peer(new_stack, client, code, "Bob")

        assert newcomer.snapshot().you != b_id
        assert len(room_players(registry, code)) == 2


def test_ac1_websocket_a_non_host_and_bad_targets_are_refused_with_no_event(
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
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you

        peer_b.send(RemovePlayer(player_id=a_id))
        peer_a.send(RemovePlayer(player_id=a_id))
        peer_a.send(RemovePlayer(player_id="zz"))
        ping_and_wait(peer_a)
        ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)

        assert error_codes(peer_b) == [ErrorCode.NOT_HOST]
        assert error_codes(peer_a) == [ErrorCode.INVALID_TARGET] * 2
        assert left_events(peer_a) == []
        assert left_events(peer_b) == []
        assert peer_b.close_code is None
        assert room_players(registry, code) == [a_id, b_id]


# ---- AC-1: browser ----------------------------------------------------------


def stored_resume_token(page: Page) -> str | None:
    stored = page.evaluate(f"localStorage.getItem({json.dumps(IDENTITY_KEY)})")
    if stored is None:
        return None
    decoded = json.loads(stored)
    return decoded["resume_token"]


def test_ac1_browser_the_host_removes_a_player_who_cannot_come_back(
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
        bob_page.add_init_script(FORM_WATCHER)
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        expect(page.get_by_test_id("roster-player")).to_have_count(2)
        bob_id = room_page(bob_page).get_attribute("data-you")
        assert bob_id
        expect(bob_page.get_by_test_id("remove-player")).to_have_count(0)
        expect(bob_page.get_by_test_id("host-panel")).to_have_count(0)
        expect(page.get_by_test_id("host-panel")).to_be_visible()

        remove_button = roster_item(page, bob_id).get_by_test_id("remove-player")
        expect(remove_button).to_have_text(load_fr()["host.remove"])
        remove_button.click(timeout=FORM_TIMEOUT_MS)

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "removed", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.removed"]
        )
        expect(page.get_by_test_id("roster-player")).to_have_count(1)
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1

        bob_page.evaluate("window.__formSeen = false")
        bob_page.reload()

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "removed", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("nickname-form")).to_have_count(0)
        assert bob_page.evaluate("window.__formSeen") is False
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.removed"]
        )
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1
    finally:
        bob_context.close()


def test_ac1_browser_the_host_sees_a_labelled_button_on_each_other_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    dialogs: list[str] = []

    def dismiss(dialog: Dialog) -> None:
        dialogs.append(dialog.message)
        dialog.dismiss()

    page.on("dialog", dismiss)

    expect(page.get_by_test_id("remove-player")).to_have_count(2)
    expect(roster_item(page, "p1").get_by_test_id("remove-player")).to_have_count(0)
    for player_id, name in (("p2", "Bob"), ("p3", "Cleo")):
        button = roster_item(page, player_id).get_by_test_id("remove-player")
        expect(button).to_have_text(load_fr()["host.remove"])
        expect(button).to_have_attribute("aria-label", f"Retirer {name} du salon")

    roster_item(page, "p3").get_by_test_id("remove-player").click(
        timeout=FORM_TIMEOUT_MS
    )

    wait_until(
        page, lambda: len(room.connections[0].messages_of_type("remove_player")) > 0
    )
    settle(page)
    sent = room.connections[0].messages_of_type("remove_player")
    assert sent == [{"type": "remove_player", "player_id": "p3"}]
    assert dialogs == []


def test_ac1_browser_a_player_who_is_not_host_sees_no_host_control(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players("p2"), you="p3")

    expect(roster_item(page, "p2")).to_have_count(1)
    expect(page.get_by_test_id("remove-player")).to_have_count(0)
    expect(page.get_by_test_id("host-panel")).to_have_count(0)
    expect(page.get_by_test_id("lock-room")).to_have_count(0)
    expect(page.get_by_test_id("settings-form")).to_have_count(0)


@pytest.mark.parametrize("scenario", ["join", "game", "reconnection"])
def test_ac1_browser_removed_is_a_final_status(
    page: Page, live_server: str, fx01_grid: Grid, scenario: str
) -> None:
    room = reach_refusal(page, live_server, fx01_grid, scenario, ErrorCode.REMOVED)

    expect(room_page(page)).to_have_attribute("data-status", "removed")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.removed"]
    )
    expect(banner(page)).to_be_hidden()
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    count = len(room.connections)
    advance_page(page, 20000)
    assert len(room.connections) == count
    expect(room_page(page)).to_have_attribute("data-status", "removed")
    if scenario != "join":
        assert stored_resume_token(page) == SNAPSHOT_TOKEN
