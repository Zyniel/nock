"""Tests of spec 014, AC-4: a change of settings is announced.

The rules, the real WebSocket and the browser (the live server with two contexts,
and spec 040's mocked socket).

The shared setup is in `tests/spec014_harness.py`, whose docstring says how the
tests are built.
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
    RevealBudget,
    RoomSettings,
    SettingsChanged,
)
from nock.room import RoomState, handle_message
from spec014_harness import (
    FORM_TIMEOUT_MS,
    LOSS_BUDGET_MS,
    NOW,
    QUIET_CONFIG,
    SETTLE_SECONDS,
    EnterRoom,
    FakeClock,
    assert_nothing_changed,
    change,
    error_codes,
    events_of,
    feed_lines,
    host_acts,
    join_in_order,
    joined_mock_room,
    load_fr,
    locked,
    ping_and_wait,
    room_of_players,
    running_room,
    settings_events,
    settings_frame,
    settle,
    sole_error,
    three_players,
    wait_until,
)
from spec014_harness import dist_dir as dist_dir
from spec014_harness import fx01_grid as fx01_grid

# ---- AC-4: change settings (rules) ------------------------------------------


def room_with_used_budget(grid: Grid) -> RoomState:
    """Allowance 5 letters and 1 word, 2 letters and 0 words left (3 and 1 used)."""
    room = room_of_players(grid, 2)
    return room.model_copy(
        update={
            "reveal_budget": RevealBudget(letters=2, words=0),
            "reveals_used": RevealBudget(letters=3, words=1),
        }
    )


def test_ac4_fr_json_holds_the_settings_texts() -> None:
    fr = load_fr()

    assert fr["settings.heading"] == "Réglages"
    assert fr["settings.help_mode_label"] == "Aide"
    assert fr["settings.reveal_letters_label"] == "Lettres à révéler"
    assert fr["settings.reveal_words_label"] == "Mots à révéler"
    assert fr["settings.save"] == "Enregistrer"


def test_ac4_a_change_announces_the_new_settings_and_the_remaining_budget(
    fx01_grid: Grid,
) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 0))

    expected_settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=3, words=0),
        locked=False,
    )
    assert outcome.reply == ()
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=3,
            player_id="p1",
            settings=expected_settings,
            reveal_budget=RevealBudget(letters=3, words=0),
        )
    ]
    assert outcome.state.settings == expected_settings
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=0)
    assert outcome.state.seq == 3


def test_ac4_the_same_settings_again_produce_nothing(fx01_grid: Grid) -> None:
    room = host_acts(room_of_players(fx01_grid, 2), change(HelpMode.VOTE, 3, 0)).state

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 0))

    assert outcome.entries == ()
    assert outcome.reply == ()
    assert outcome.state.seq == room.seq
    assert outcome.state.settings == room.settings


def test_ac4_the_unchanged_allowance_leaves_the_remaining_budget_alone(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 5, 1))

    assert outcome.entries == ()
    assert outcome.state.reveal_budget == RevealBudget(letters=2, words=0)


def test_ac4_a_new_help_mode_alone_is_announced_and_keeps_the_remaining_budget(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.NONE, 5, 1))

    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=RoomSettings(
                help_mode=HelpMode.NONE,
                reveal_budget=RevealBudget(letters=5, words=1),
                locked=False,
            ),
            reveal_budget=RevealBudget(letters=2, words=0),
        )
    ]


def test_ac4_a_new_allowance_alone_is_announced_with_the_help_mode_unchanged(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 6, 1))

    assert outcome.state.settings.help_mode is HelpMode.FREE
    assert outcome.state.settings.reveal_budget == RevealBudget(letters=6, words=1)
    assert outcome.state.reveal_budget == RevealBudget(letters=3, words=0)
    assert len(outcome.entries) == 1


def test_ac4_the_remaining_budget_is_the_new_allowance_minus_what_was_used(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 10, 3))

    assert outcome.state.reveal_budget == RevealBudget(letters=7, words=2)
    assert events_of(outcome.entries) == [
        SettingsChanged(
            seq=room.seq + 1,
            player_id="p1",
            settings=RoomSettings(
                help_mode=HelpMode.FREE,
                reveal_budget=RevealBudget(letters=10, words=3),
                locked=False,
            ),
            reveal_budget=RevealBudget(letters=7, words=2),
        )
    ]


def test_ac4_an_allowance_below_what_was_used_leaves_zero_never_less(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 2, 0))

    assert outcome.state.reveal_budget == RevealBudget(letters=0, words=0)
    event = outcome.entries[0].event
    assert isinstance(event, SettingsChanged)
    assert event.reveal_budget == RevealBudget(letters=0, words=0)
    assert event.settings.reveal_budget == RevealBudget(letters=2, words=0)


def test_ac4_letters_and_words_are_computed_separately(fx01_grid: Grid) -> None:
    room = room_with_used_budget(fx01_grid)

    outcome = host_acts(room, change(HelpMode.FREE, 9, 0))

    assert outcome.state.reveal_budget == RevealBudget(letters=6, words=0)


def test_ac4_a_cut_allowance_does_not_make_the_room_forget_the_reveals_used(
    fx01_grid: Grid,
) -> None:
    room = room_with_used_budget(fx01_grid)
    lowered = host_acts(room, change(HelpMode.FREE, 1, 1)).state
    assert lowered.reveal_budget == RevealBudget(letters=0, words=0)

    raised = host_acts(lowered, change(HelpMode.FREE, 10, 5))

    # remaining = max(0, new allowance - reveals_used) = (10 - 3, 5 - 1)
    assert raised.state.reveal_budget == RevealBudget(letters=7, words=4)
    assert raised.state.reveals_used == RevealBudget(letters=3, words=1)


def test_ac4_any_count_from_zero_is_accepted_by_the_server(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = host_acts(room, change(HelpMode.FREE, 250, 0))

    assert outcome.reply == ()
    assert outcome.state.settings.reveal_budget == RevealBudget(letters=250, words=0)
    assert outcome.state.reveal_budget == RevealBudget(letters=250, words=0)


def test_ac4_a_change_does_not_touch_the_lock(fx01_grid: Grid) -> None:
    room = locked(room_of_players(fx01_grid, 2))

    outcome = host_acts(room, change(HelpMode.VOTE, 3, 2))

    assert outcome.state.settings.locked is True
    event = outcome.entries[0].event
    assert isinstance(event, SettingsChanged)
    assert event.settings.locked is True
    assert event.settings.help_mode is HelpMode.VOTE


def test_ac4_a_player_who_is_not_host_gets_not_host(fx01_grid: Grid) -> None:
    room = room_of_players(fx01_grid, 2)

    outcome = handle_message(room, "p2", change(HelpMode.VOTE, 3, 0), NOW + 1)

    assert sole_error(outcome.reply).code is ErrorCode.NOT_HOST
    assert outcome.entries == ()
    assert_nothing_changed(room, outcome.state)


# ---- AC-4: through the real WebSocket ---------------------------------------


def test_ac4_websocket_a_change_reaches_both_players_once_and_only_the_host_may(
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
        new_budget = RevealBudget(letters=3, words=0)
        expected = SettingsChanged(
            seq=3,
            player_id=a_id,
            settings=RoomSettings(
                help_mode=HelpMode.VOTE, reveal_budget=new_budget, locked=False
            ),
            reveal_budget=new_budget,
        )

        peer_a.send(change(HelpMode.VOTE, 3, 0))

        for peer in (peer_a, peer_b):
            peer.wait_until(lambda peer=peer: len(settings_events(peer)) == 1, "change")
            assert settings_events(peer) == [expected]

        peer_a.send(change(HelpMode.VOTE, 3, 0))
        ping_and_wait(peer_a)
        ping_and_wait(peer_b)
        time.sleep(SETTLE_SECONDS)
        assert settings_events(peer_a) == [expected]
        assert settings_events(peer_b) == [expected]
        assert error_codes(peer_a) == []

        peer_b.send(change(HelpMode.NONE, 9, 9))
        peer_b.wait_until(
            lambda: error_codes(peer_b) == [ErrorCode.NOT_HOST], "B refused"
        )
        ping_and_wait(peer_a)
        assert settings_events(peer_a) == [expected]
        state = registry.room_state(code)
        assert state is not None
        assert state.settings == expected.settings
        assert state.reveal_budget == new_budget


# ---- AC-4: browser ----------------------------------------------------------


def test_ac4_browser_the_host_changes_the_settings_and_both_feeds_say_so(
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
        expect(bob_page.get_by_test_id("roster-player")).to_have_count(2)
        line = (
            "Ana a modifié les réglages : aide par vote, 3 lettres et 0 mots à révéler"
        )

        page.get_by_test_id("help-mode-select").select_option(
            "vote", timeout=FORM_TIMEOUT_MS
        )
        page.get_by_test_id("reveal-letters-input").fill("3", timeout=FORM_TIMEOUT_MS)
        page.get_by_test_id("reveal-words-input").fill("0", timeout=FORM_TIMEOUT_MS)
        page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)

        expect(feed_lines(bob_page, "settings_changed")).to_have_text(
            line, timeout=LOSS_BUDGET_MS
        )
        expect(feed_lines(page, "settings_changed")).to_have_text(line)
        state = room_registry.room_state(code)
        assert state is not None
        assert state.settings == RoomSettings(
            help_mode=HelpMode.VOTE,
            reveal_budget=RevealBudget(letters=3, words=0),
            locked=False,
        )

        page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)
        settle(page)

        expect(feed_lines(page, "settings_changed")).to_have_count(1)
        expect(feed_lines(bob_page, "settings_changed")).to_have_count(1)
        expect(bob_page.get_by_test_id("settings-form")).to_have_count(0)
    finally:
        bob_context.close()


def test_ac4_browser_the_form_lists_the_modes_and_limits_the_counts(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    settings = RoomSettings(
        help_mode=HelpMode.VOTE,
        reveal_budget=RevealBudget(letters=3, words=2),
        locked=False,
    )
    joined_mock_room(
        page,
        live_server,
        fx01_grid,
        three_players(),
        settings=settings,
        remaining=RevealBudget(letters=1, words=0),
    )

    form = page.get_by_test_id("settings-form")
    select = page.get_by_test_id("help-mode-select")
    letters = page.get_by_test_id("reveal-letters-input")
    words = page.get_by_test_id("reveal-words-input")
    expect(page.get_by_test_id("host-panel")).to_contain_text(fr["settings.heading"])
    expect(select).to_have_accessible_name(fr["settings.help_mode_label"])
    expect(letters).to_have_accessible_name(fr["settings.reveal_letters_label"])
    expect(words).to_have_accessible_name(fr["settings.reveal_words_label"])
    expect(form.get_by_test_id("settings-save")).to_have_text(fr["settings.save"])
    options = select.locator("option")
    expect(options).to_have_count(3)
    for index, mode in enumerate(["free", "vote", "none"]):
        expect(options.nth(index)).to_have_attribute("value", mode)
        expect(options.nth(index)).to_have_text(fr[f"settings.help_mode.{mode}"])
    for number_input in (letters, words):
        expect(number_input).to_have_attribute("type", "number")
        expect(number_input).to_have_attribute("min", "0")
        expect(number_input).to_have_attribute("max", "99")
    expect(select).to_have_value("vote")
    expect(letters).to_have_value("3")
    expect(words).to_have_value("2")


def test_ac4_browser_the_form_follows_a_settings_changed_event(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    new_settings = RoomSettings(
        help_mode=HelpMode.NONE,
        reveal_budget=RevealBudget(letters=8, words=4),
        locked=False,
    )

    room.connections[0].send(settings_frame(6, "p2", new_settings))

    expect(page.get_by_test_id("help-mode-select")).to_have_value("none")
    expect(page.get_by_test_id("reveal-letters-input")).to_have_value("8")
    expect(page.get_by_test_id("reveal-words-input")).to_have_value("4")


def test_ac4_browser_submitting_sends_the_change_settings_message(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]

    page.get_by_test_id("help-mode-select").select_option(
        "none", timeout=FORM_TIMEOUT_MS
    )
    page.get_by_test_id("reveal-letters-input").fill("12", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("reveal-words-input").fill("0", timeout=FORM_TIMEOUT_MS)
    page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)

    wait_until(page, lambda: len(connection.messages_of_type("change_settings")) == 1)
    assert connection.messages_of_type("change_settings") == [
        {
            "type": "change_settings",
            "help_mode": "none",
            "reveal_budget": {"letters": 12, "words": 0},
        }
    ]
    settle(page)
    assert len(connection.messages_of_type("change_settings")) == 1


@pytest.mark.parametrize("bad_value", ["100", "-1", "2.5"])
def test_ac4_browser_the_form_never_sends_a_count_out_of_its_bounds(
    page: Page, live_server: str, fx01_grid: Grid, bad_value: str
) -> None:
    room = joined_mock_room(page, live_server, fx01_grid, three_players())
    connection = room.connections[0]
    page.get_by_test_id("reveal-letters-input").fill(bad_value, timeout=FORM_TIMEOUT_MS)

    page.get_by_test_id("settings-save").click(timeout=FORM_TIMEOUT_MS)
    settle(page)

    for sent in connection.messages_of_type("change_settings"):
        budget = sent["reveal_budget"]
        assert isinstance(budget, dict)
        letters = budget["letters"]
        assert isinstance(letters, int)
        assert 0 <= letters <= 99


def test_ac4_browser_a_player_who_is_not_host_has_no_settings_form(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    joined_mock_room(page, live_server, fx01_grid, three_players(), you="p2")

    expect(page.get_by_test_id("settings-form")).to_have_count(0)
    expect(page.get_by_test_id("help-mode-select")).to_have_count(0)
    expect(page.get_by_test_id("settings-save")).to_have_count(0)
