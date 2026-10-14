"""Tests of spec 014, AC-2: the host locks the room.

The rules, the real WebSocket and the browser (the live server with two contexts,
and spec 040's mocked socket).

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.

Not tested here, with the reason:

- The seq of the entries of a refused join that also timed out the member in the
  same step: the spec does not say what a refused join leaves in the log.
"""

from __future__ import annotations

import contextlib
import time
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    ErrorCode,
    HelpMode,
    LockRoom,
    PlayerState,
    RevealBudget,
    SettingsChanged,
)
from nock.room import disconnect_player, handle_message, join_room, tick
from spec014_harness import (
    FORM_TIMEOUT_MS,
    LOSS_BUDGET_MS,
    NEW_PLAYER_ID,
    NEW_TOKEN,
    NOW,
    QUIET_CONFIG,
    QUIET_RULES,
    SETTLE_SECONDS,
    START_SETTINGS,
    EnterRoom,
    FakeClock,
    advance_page,
    assert_nothing_changed,
    banner,
    error_codes,
    events_of,
    feed_lines,
    has_state_change,
    host_acts,
    join_in_order,
    joined_mock_room,
    keep_seen,
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
    running_room,
    settings_events,
    settings_frame,
    sole_error,
    sole_snapshot,
    three_players,
    token_of,
    wait_until,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid

# ---- AC-2: lock the room (rules) --------------------------------------------


def test_ac2_fr_json_holds_the_lock_texts() -> None:
    fr = load_fr()

    assert fr["host.lock"] == "Verrouiller le salon"
    assert fr["host.unlock"] == "Déverrouiller le salon"
    assert fr["room.status.locked"] == "Ce salon est verrouillé."


def test_ac2_locking_sets_the_flag_and_announces_settings_changed(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.reply == ()
    assert outcome.state.settings.locked is True
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=3,
            player_id="p1",
            settings=START_SETTINGS.model_copy(update={"locked": True}),
            reveal_budget=START_SETTINGS.reveal_budget,
        )
    ]
    assert outcome.state.seq == 3


def test_ac2_locking_again_produces_no_entry_and_no_reply(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.settings.locked is True
    assert outcome.state.seq == room.seq


def test_ac2_unlocking_announces_settings_changed_with_locked_false(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, LockRoom(locked=False))

    assert outcome.reply == ()
    assert outcome.state.settings.locked is False
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=START_SETTINGS,
            reveal_budget=START_SETTINGS.reveal_budget,
        )
    ]


def test_ac2_unlocking_an_unlocked_room_does_nothing(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, LockRoom(locked=False))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.seq == room.seq


def test_ac2_locking_keeps_the_help_mode_and_the_budget(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)
    changed = room.settings.model_copy(
        update={
            "help_mode": HelpMode.VOTE,
            "reveal_budget": RevealBudget(letters=7, words=4),
        }
    )
    room = room.model_copy(
        update={"settings": changed, "reveal_budget": RevealBudget(letters=3, words=2)}
    )

    outcome = host_acts(room, LockRoom(locked=True))

    assert outcome.state.settings == changed.model_copy(update={"locked": True})
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=2)
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=changed.model_copy(update={"locked": True}),
            reveal_budget=RevealBudget(letters=3, words=2),
        )
    ]


def test_ac2_a_player_who_is_not_host_gets_not_host_on_lock_and_unlock(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)
    lock_attempt = handle_message(room, "p2", LockRoom(locked=True), NOW + 1)
    locked_room = locked(room)
    unlock_attempt = handle_message(locked_room, "p2", LockRoom(locked=False), NOW + 1)

    assert sole_error(lock_attempt.reply).code is ErrorCode.NOT_HOST
    assert lock_attempt.entries == ()
    assert lock_attempt.state.settings.locked is False
    assert sole_error(unlock_attempt.reply).code is ErrorCode.NOT_HOST
    assert unlock_attempt.entries == ()
    assert unlock_attempt.state.settings.locked is True


def test_ac2_a_locked_room_refuses_a_new_joiner_as_room_locked(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(room, new_guest("Zoe"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


def test_ac2_a_joiner_with_an_unknown_token_is_refused_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(
        room,
        new_guest("Zoe", "an-unknown-token-0001"),
        NOW + 2,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True


def test_ac2_a_member_resumes_in_a_locked_room(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == "p2"
    assert player_ids(outcome.state) == ["p1", "p2"]


def test_ac2_a_disconnected_member_resumes_within_the_window_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 2))
    room = disconnect_player(room, "p2", NOW + 10).state

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 10 + 299, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == "p2"
    assert player_of(outcome.state, "p2").state is PlayerState.ACTIVE


def test_ac2_a_member_who_timed_out_is_refused_in_a_locked_room(
    fx01_grid: Grid,
) -> None:
    room = locked(room_of_players(fx01_grid, 3))
    room = disconnect_player(room, "p2", NOW + 10).state
    after_window = NOW + 10 + 300.5
    ticked = tick(keep_seen(room, after_window), after_window, QUIET_RULES)
    assert player_ids(ticked.state) == ["p1", "p3"]

    outcome = join_room(
        ticked.state,
        new_guest("Bob", token_of(2)),
        after_window + 1,
        NEW_PLAYER_ID,
        NEW_TOKEN,
    )

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True
    assert player_ids(outcome.state) == ["p1", "p3"]


def test_ac2_locked_is_answered_before_full(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 8))

    outcome = join_room(room, new_guest("Ivy"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED
    assert outcome.close_sender is True


def test_ac2_locked_is_answered_before_the_nickname_check(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = join_room(room, new_guest("!!"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)

    assert sole_error(outcome.reply).code is ErrorCode.ROOM_LOCKED


def test_ac2_a_member_resumes_in_a_locked_full_room(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 8))

    outcome = join_room(
        room, new_guest("Hal", token_of(8)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_snapshot(outcome).you == "p8"


def test_ac2_removed_is_answered_before_locked(fx01_grid: Grid) -> None:
    room = locked(removed_bob(room_of_players(fx01_grid, 3)))

    outcome = join_room(
        room, new_guest("Bob", token_of(2)), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN
    )

    assert sole_error(outcome.reply).code is ErrorCode.REMOVED
    assert outcome.close_sender is True


def test_ac2_after_unlocking_a_new_joiner_is_accepted(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))
    refused = join_room(room, new_guest("Zoe"), NOW + 2, NEW_PLAYER_ID, NEW_TOKEN)
    assert sole_error(refused.reply).code is ErrorCode.ROOM_LOCKED
    unlocked = host_acts(room, LockRoom(locked=False)).state

    outcome = join_room(unlocked, new_guest("Zoe"), NOW + 3, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is False
    assert sole_snapshot(outcome).you == NEW_PLAYER_ID


# ---- AC-2: through the real WebSocket ---------------------------------------


def test_ac2_websocket_lock_refuses_new_sockets_but_not_members(
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
        contextlib.ExitStack() as b_again_stack,
        contextlib.ExitStack() as refused_stack,
        contextlib.ExitStack() as joiner_stack,
    ):
        peer_a, peer_b = join_in_order([a_stack, b_stack], client, code)
        a_id = peer_a.snapshot().you
        b_id = peer_b.snapshot().you
        b_token = peer_b.snapshot().resume_token

        peer_a.send(LockRoom(locked=True))

        for peer in (peer_a, peer_b):
            peer.wait_until(lambda peer=peer: len(settings_events(peer)) == 1, "lock")
            lock_event = settings_events(peer)[0]
            assert lock_event.player_id == a_id
            assert lock_event.settings.locked is True
        refused = open_refused_peer(refused_stack, client, code, "Cy")
        assert refused.close_code == 1000
        assert len(refused.messages()) == 1
        assert error_codes(refused) == [ErrorCode.ROOM_LOCKED]
        assert room_players(registry, code) == [a_id, b_id]

        b_stack.close()
        peer_a.wait_until(
            lambda: has_state_change(peer_a, b_id, PlayerState.DISCONNECTED),
            "B's disconnection",
        )
        peer_b_again = open_peer(b_again_stack, client, code, "Bob", b_token)
        assert peer_b_again.snapshot().you == b_id
        assert peer_b_again.snapshot().settings.locked is True

        peer_a.send(LockRoom(locked=True))
        ping_and_wait(peer_a)
        time.sleep(SETTLE_SECONDS)
        assert len(settings_events(peer_a)) == 1
        assert error_codes(peer_a) == []

        peer_b_again.send(LockRoom(locked=False))
        peer_b_again.wait_until(
            lambda: error_codes(peer_b_again) == [ErrorCode.NOT_HOST], "not_host"
        )
        ping_and_wait(peer_a)
        assert len(settings_events(peer_a)) == 1

        peer_a.send(LockRoom(locked=False))
        peer_a.wait_until(lambda: len(settings_events(peer_a)) == 2, "unlock on A")
        peer_b_again.wait_until(
            lambda: len(settings_events(peer_b_again)) == 1, "unlock on B"
        )
        assert settings_events(peer_a)[1].settings.locked is False
        assert settings_events(peer_b_again)[0].settings.locked is False
        joiner = open_peer(joiner_stack, client, code, "Cy")
        assert joiner.snapshot().settings.locked is False
        assert len(room_players(registry, code)) == 3


# ---- AC-2: browser ----------------------------------------------------------


def test_ac2_browser_the_host_locks_the_room_and_a_newcomer_is_refused(
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
        enter_room(page, url, "Ana")
        lock = page.get_by_test_id("lock-room")
        expect(lock).to_have_attribute("aria-pressed", "false")
        expect(lock).to_have_text(load_fr()["host.lock"])

        lock.click(timeout=FORM_TIMEOUT_MS)

        expect(lock).to_have_attribute("aria-pressed", "true")
        expect(lock).to_have_text(load_fr()["host.unlock"])
        expect(feed_lines(page, "room_locked")).to_have_text(
            "Ana a verrouillé le salon"
        )
        bob_page = bob_context.new_page()
        bob_page.goto(url)
        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "nickname", timeout=LOSS_BUDGET_MS
        )
        nickname_input = bob_page.get_by_test_id("nickname-input")
        nickname_input.fill("Bob", timeout=FORM_TIMEOUT_MS)
        nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)

        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "locked", timeout=LOSS_BUDGET_MS
        )
        expect(bob_page.get_by_test_id("room-status")).to_have_text(
            load_fr()["room.status.locked"]
        )
        expect(bob_page.get_by_test_id("nickname-form")).to_have_count(0)
        state = room_registry.room_state(code)
        assert state is not None
        assert len(state.players) == 1

        lock.click(timeout=FORM_TIMEOUT_MS)

        expect(lock).to_have_attribute("aria-pressed", "false")
        expect(lock).to_have_text(load_fr()["host.lock"])
        expect(feed_lines(page, "room_unlocked")).to_have_text(
            "Ana a déverrouillé le salon"
        )
        bob_page.reload()
        nickname_input = bob_page.get_by_test_id("nickname-input")
        nickname_input.fill("Bob", timeout=FORM_TIMEOUT_MS)
        nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
        expect(room_page(bob_page)).to_have_attribute(
            "data-status", "joined", timeout=LOSS_BUDGET_MS
        )
    finally:
        bob_context.close()


def test_ac2_browser_the_lock_button_sends_the_opposite_of_the_current_state(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]
    lock = page.get_by_test_id("lock-room")
    expect(lock).to_have_attribute("aria-pressed", "false")

    lock.click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("lock_room")) == 1)
    assert connection.messages_of_type("lock_room") == [
        {"type": "lock_room", "locked": True}
    ]
    expect(lock).to_have_attribute("aria-pressed", "false")
    locked_settings = START_SETTINGS.model_copy(update={"locked": True})
    connection.send(settings_frame(6, "p1", locked_settings))
    expect(lock).to_have_attribute("aria-pressed", "true")
    expect(lock).to_have_text(load_fr()["host.unlock"])

    lock.click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("lock_room")) == 2)
    assert connection.messages_of_type("lock_room")[1] == {
        "type": "lock_room",
        "locked": False,
    }
    connection.send(settings_frame(7, "p1", START_SETTINGS))
    expect(lock).to_have_attribute("aria-pressed", "false")
    expect(lock).to_have_text(load_fr()["host.lock"])


def test_ac2_browser_a_locked_snapshot_shows_the_button_pressed(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    locked_settings = START_SETTINGS.model_copy(update={"locked": True})
    joined_mock_room(
        page, live_server, fx01_grid, three_players(), settings=locked_settings
    )

    lock = page.get_by_test_id("lock-room")
    expect(lock).to_have_attribute("aria-pressed", "true")
    expect(lock).to_have_text(load_fr()["host.unlock"])


@pytest.mark.parametrize("scenario", ["join", "game", "reconnection"])
def test_ac2_browser_room_locked_is_a_final_status(
    page: Page, live_server: str, fx01_grid: Grid, scenario: str
) -> None:
    room = reach_refusal(page, live_server, fx01_grid, scenario, ErrorCode.ROOM_LOCKED)

    expect(room_page(page)).to_have_attribute("data-status", "locked")
    expect(page.get_by_test_id("room-status")).to_have_text(
        load_fr()["room.status.locked"]
    )
    expect(banner(page)).to_be_hidden()
    expect(page.get_by_test_id("nickname-form")).to_have_count(0)
    count = len(room.connections)
    advance_page(page, 20000)
    assert len(room.connections) == count
    expect(room_page(page)).to_have_attribute("data-status", "locked")
