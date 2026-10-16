"""Tests of spec 022, AC-7 to AC-9: mute, where chat is kept, and the server's
limits.

AC-7: the rule on `handle_message` (muted chat refused, reactions dropped, an idle
sender still woken as the lead's note of 2026-10-15 says, and every other action
still allowed), the real WebSocket, two browsers on the live server, and a page
with a mocked socket whose snapshot mutes `you` (the panel's focus, and an `error`
`muted` that touches no pending edit). AC-8: a `RoomStore` on a file read back
with `sqlite3`, `replay` through `RoomStore.load_room`, and the WebSocket with
every logger captured at level DEBUG. AC-9: the rule with exact clock values, and
the WebSocket with spec 011's fake clock frozen.

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
import time
from collections.abc import Sequence
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    Chat,
    ChatMessage,
    Check,
    CheckResult,
    ClueRef,
    ErrorCode,
    ErrorMessage,
    FlagChanged,
    Join,
    MutePlayer,
    PlayerState,
    PlayerStateChanged,
    Pong,
    Reaction,
    ServerMessage,
)
from nock.room import (
    LogEntry,
    RoomConfig,
    RoomState,
    after_restart,
    disconnect_player,
    handle_message,
    join_room,
    new_room,
    tick,
)
from nock.store import RoomStore
from spec013_harness import FakeClock
from spec021_harness import IDES, MIME, send_flag
from spec022_harness import (
    LIVE_WITHIN_SECONDS,
    SETTLE_MS,
    WS_CONFIG,
    chat_messages_of,
    chat_room,
    new_player_page,
    open_chat_room,
    open_panel,
    own_player_id,
    remaining_ms,
    send_chat,
    send_react,
    set_muted,
    shown,
    three_players,
    wait_for_chat_count,
)
from spec024_harness import (
    NOW,
    EnterRoom,
    cell_at,
    events_of,
    grid_from_text,
    join_peers,
    load_fr,
    make_dist_dir,
    ping_and_wait,
    player_record,
    refusal_code,
    seen_at,
    two_player_room,
    write,
)
from spec025_harness import fr_text

QUIET_RULES = RoomConfig(silence_timeout_seconds=3600)
CHAT_LIMIT = 5  # the defaults of RoomConfig.chat_limit and reaction_limit
WINDOW_SECONDS = 10.0  # the defaults of the two windows


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def without_pongs(messages: Sequence[ServerMessage]) -> list[ServerMessage]:
    """The messages that are not a `pong`."""
    kept: list[ServerMessage] = []
    for message in messages:
        if not isinstance(message, Pong):
            kept.append(message)
    return kept


# ---- AC-7: the rule ----


def test_ac7_python_a_muted_player_cannot_chat_or_react_until_unmuted(
    fx01_grid: Grid,
) -> None:
    muted = set_muted(two_player_room(fx01_grid), "p2", True)

    refused = send_chat(muted, "p2", "salut")
    reacted = send_react(refused.state, "p2", IDES, Reaction.CLAP)
    unmuted = set_muted(reacted.state, "p2", False)
    accepted = send_chat(unmuted, "p2", "salut")

    assert refusal_code(refused) == ErrorCode.MUTED
    assert refused.entries == ()
    assert refused.state.chat == ()
    assert refused.state == seen_at(muted, "p2", NOW)
    assert reacted.entries == ()
    assert reacted.reply == ()
    assert reacted.to_others == ()
    expected = ChatMessage(seq=unmuted.seq + 1, player_id="p2", text="salut")
    assert events_of(accepted) == [expected]
    assert accepted.reply == ()


def test_ac7_python_a_refused_chat_message_still_wakes_an_idle_sender(
    fx01_grid: Grid,
) -> None:
    muted = set_muted(two_player_room(fx01_grid), "p2", True)
    idle = tick(muted, NOW + 120, QUIET_RULES).state
    assert player_record(idle, "p2").state == PlayerState.IDLE

    refused = send_chat(idle, "p2", "salut", NOW + 130)

    woken = PlayerStateChanged(
        seq=idle.seq + 1, player_id="p2", state=PlayerState.ACTIVE
    )
    assert refusal_code(refused) == ErrorCode.MUTED
    assert events_of(refused) == [woken]
    assert refused.state.chat == ()


def test_ac7_python_a_muted_player_still_types_checks_and_flags(
    fx01_grid: Grid,
) -> None:
    muted = set_muted(two_player_room(fx01_grid), "p2", True)

    typed = write(muted, "p2", 1, 0, "T")
    check_message = Check(target=CellTarget(row=1, column=0))
    check = handle_message(typed.state, "p2", check_message, NOW)
    flagged = send_flag(check.state, "p2", MIME)

    assert check.reply == ()
    assert isinstance(events_of(check)[0], CheckResult)
    assert flagged.reply == ()
    assert events_of(flagged) == [
        FlagChanged(seq=check.state.seq + 1, player_id="p2", clue=MIME)
    ]


# ---- AC-7: the WebSocket ----


def test_ac7_websocket_a_muted_players_chat_is_refused_until_the_host_unmutes(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, _, code),
        contextlib.ExitStack() as stack,
    ):
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
        bob_id = bob.you()
        ana.send(MutePlayer(player_id=bob_id, muted=True))
        ana.wait_for_seq(3, "the player_muted event")
        bob.wait_for_seq(3, "the player_muted event")
        ana_count = len(ana.messages())

        bob.send(Chat(text="salut"))
        bob.wait_until(lambda: len(bob.errors()) >= 1, "the refusal")
        ping_and_wait(bob)
        ping_and_wait(ana)
        refusals = [error.code for error in bob.errors()]
        ana_meanwhile = without_pongs(ana.messages()[ana_count:])

        ana.send(MutePlayer(player_id=bob_id, muted=False))
        ana.wait_for_seq(4, "the second player_muted event")
        bob.wait_for_seq(4, "the second player_muted event")
        bob.send(Chat(text="salut"))
        wait_for_chat_count(ana, 1)
        wait_for_chat_count(bob, 1)
        ana_messages = chat_messages_of(ana)
        bob_messages = chat_messages_of(bob)

    expected = ChatMessage(seq=5, player_id=bob_id, text="salut")
    assert refusals == [ErrorCode.MUTED]
    assert ana_meanwhile == []
    assert ana_messages == [expected]
    assert bob_messages == [expected]


# ---- AC-7: two browsers on the live server ----


def test_ac7_browser_the_host_mutes_and_unmutes_a_players_chat(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    fr = load_fr()
    code = room_registry.register_room(fx01_grid)
    ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
    try:
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        try:
            expect(ana.get_by_test_id("roster-player")).to_have_count(2)
            bob_id = own_player_id(bob)
            cell_at(bob, 0, 3).click()
            expect(bob.get_by_test_id("grid")).to_have_attribute("data-word", "0,3,0")
            open_panel(ana)
            open_panel(bob)
            bob_input = bob.get_by_test_id("chat-input")
            bob_send = bob.get_by_test_id("chat-send")
            bob_react = bob.get_by_test_id("react-button")
            bob_input.fill("salut")
            expect(bob_send).to_be_enabled()
            expect(bob_react).to_be_enabled()
            expect(bob.get_by_test_id("chat-moderation")).to_have_count(0)

            moderation = ana.get_by_test_id("chat-moderation")
            rows = moderation.get_by_test_id("mute-row")
            expect(rows).to_have_count(1)
            expect(rows).to_have_attribute("data-player-id", bob_id)
            expect(rows.get_by_test_id("mute-name")).to_have_text("Bob")
            expect(moderation.locator("h3")).to_have_text(fr["chat.moderation_heading"])
            mute = rows.get_by_test_id("mute-player")
            expect(mute).to_have_text(fr["chat.mute"])
            expect(mute).to_have_attribute("aria-label", "Couper la discussion de Bob")
            expect(mute).to_have_attribute("data-muted", "false")

            mute.click()
            deadline = time.monotonic() + LIVE_WITHIN_SECONDS
            expect(bob_input).to_be_disabled(timeout=remaining_ms(deadline))
            expect(bob_send).to_be_disabled(timeout=remaining_ms(deadline))
            expect(bob.get_by_test_id("chat-muted")).to_have_text(
                fr["chat.muted"], timeout=remaining_ms(deadline)
            )
            expect(bob_react).to_be_disabled(timeout=remaining_ms(deadline))
            expect(mute).to_have_text(fr["chat.unmute"], timeout=remaining_ms(deadline))
            expect(mute).to_have_attribute(
                "data-muted", "true", timeout=remaining_ms(deadline)
            )
            expect(mute).to_have_attribute(
                "aria-label", fr_text("chat.unmute_label", name="Bob")
            )

            mute.click()
            deadline = time.monotonic() + LIVE_WITHIN_SECONDS
            expect(bob_input).to_be_enabled(timeout=remaining_ms(deadline))
            expect(bob.get_by_test_id("chat-muted")).to_have_count(
                0, timeout=remaining_ms(deadline)
            )
        finally:
            close_bob()
    finally:
        close_ana()


# ---- AC-7: a muted page, with a mocked socket ----


def test_ac7_browser_a_muted_page_cannot_chat_and_keeps_its_pending_edits(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    players = three_players()
    players[0] = players[0].model_copy(update={"muted": True})
    mock = open_chat_room(page, live_server, fx01_grid, players=players)
    toggle = page.get_by_test_id("chat-toggle")

    cell_at(page, 0, 3).click()
    expect(page.get_by_test_id("grid")).to_have_attribute("data-word", "0,3,0")
    expect(page.get_by_test_id("react-button")).to_be_disabled()
    toggle.click()
    expect(page.get_by_test_id("chat-panel")).to_be_visible()
    expect(page.get_by_test_id("chat-input")).to_be_disabled()
    expect(page.get_by_test_id("chat-send")).to_be_disabled()
    expect(page.get_by_test_id("chat-muted")).to_have_text(fr["chat.muted"])
    expect(toggle).to_be_focused()  # the input is disabled, so the focus stays

    # A muted player still types; an `error` `muted` answers no edit (spec 015).
    toggle.click()
    expect(page.get_by_test_id("chat-panel")).to_have_count(0)
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    letter_cell = cell_at(page, 1, 0)
    expect(letter_cell).to_have_attribute("data-unconfirmed", "true")
    refusal = ErrorMessage(code=ErrorCode.MUTED, message="Muted.")
    mock.send(refusal.model_dump_json())
    page.wait_for_timeout(SETTLE_MS)

    expect(letter_cell).to_have_attribute("data-letter", "T")
    expect(letter_cell).to_have_attribute("data-unconfirmed", "true")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")


# ---- AC-8: chat is kept only with its room ----


def row_holds(row: Sequence[object], text: str) -> bool:
    """Whether one column of a database row holds `text`."""
    for value in row:
        if isinstance(value, str) and text in value:
            return True
        if isinstance(value, bytes) and text.encode("utf-8") in value:
            return True
    return False


def rows_holding(path: Path, text: str) -> list[tuple[str, dict[str, object]]]:
    """Every row of every table of a SQLite file that holds `text` in a column.

    Returns:
        For each such row, its table's name and its columns by name.
    """
    connection = sqlite3.connect(path)
    found: list[tuple[str, dict[str, object]]] = []
    try:
        tables = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        for (table,) in tables:
            cursor = connection.execute(f'SELECT * FROM "{table}"')
            columns = [description[0] for description in cursor.description]
            for row in cursor.fetchall():
                if row_holds(row, text):
                    found.append((str(table), dict(zip(columns, row, strict=True))))
    finally:
        connection.close()
    return found


def joined_two(state: RoomState) -> tuple[RoomState, list[LogEntry]]:
    """`p1` (Ana, host) then `p2` (Bob) join at NOW; the state and the entries."""
    entries: list[LogEntry] = []
    first = join_room(
        state, Join(nickname="Ana", resume_token=None), NOW, "p1", "token-of-player-01"
    )
    entries.extend(first.entries)
    second = join_room(
        first.state,
        Join(nickname="Bob", resume_token=None),
        NOW,
        "p2",
        "token-of-player-02",
    )
    entries.extend(second.entries)
    return second.state, entries


def test_ac8_python_chat_text_is_stored_only_in_rows_of_its_room(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "rooms.sqlite3"
    store = RoomStore(path)
    try:
        room_a = new_room("AAAAAA", fx01_grid, NOW)
        store.create_room(room_a)
        store.create_room(new_room("BBBBBB", fx01_grid, NOW))
        state, entries = joined_two(room_a)
        chat = send_chat(state, "p1", "secret-a-42")
        assert chat.reply == ()
        entries.extend(chat.entries)
        store.append("AAAAAA", entries)
        store.save_snapshot(chat.state)
    finally:
        store.close()

    rows = rows_holding(path, "secret-a-42")

    assert rows != []
    for table, row in rows:
        assert row.get("code") == "AAAAAA", (table, row)


def test_ac8_python_the_rooms_log_gives_back_its_chat_but_not_the_limit_times(
    fx01_grid: Grid,
) -> None:
    store = RoomStore(":memory:")
    try:
        room = new_room("AAAAAA", fx01_grid, NOW)
        store.create_room(room)
        state, entries = joined_two(room)
        first = send_chat(state, "p1", "Qui a une idée ?")
        second = send_chat(first.state, "p2", "IDES, je crois")
        entries.extend(first.entries)
        entries.extend(second.entries)
        store.append("AAAAAA", entries)
        loaded = store.load_room("AAAAAA")
    finally:
        store.close()

    assert loaded is not None
    assert loaded.chat == (
        ChatMessage(seq=3, player_id="p1", text="Qui a une idée ?"),
        ChatMessage(seq=4, player_id="p2", text="IDES, je crois"),
    )
    assert player_record(loaded, "p1").recent_chat == ()
    assert player_record(loaded, "p2").recent_chat == ()


def test_ac8_websocket_no_log_record_holds_a_chat_text(
    fx01_grid: Grid, dist_dir: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    for name in list(logging.root.manager.loggerDict):
        caplog.set_level(logging.DEBUG, logger=name)
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, _, code),
        contextlib.ExitStack() as stack,
    ):
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
        ana.send(Chat(text="secret-b-77"))
        wait_for_chat_count(bob, 1)
        ping_and_wait(ana)
        received = chat_messages_of(bob)[0].text

    holding = [
        record.name for record in caplog.records if "secret-b-77" in record.getMessage()
    ]
    assert received == "secret-b-77"
    assert holding == []


# ---- AC-9: the limits of the rule ----


def test_ac9_python_a_sixth_chat_message_in_10_seconds_is_dropped(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for number in range(1, CHAT_LIMIT + 1):
        outcome = send_chat(state, "p1", f"m{number}")
        expected = ChatMessage(seq=2 + number, player_id="p1", text=f"m{number}")
        assert events_of(outcome) == [expected]
        state = outcome.state

    for later in (0.0, 9.9, 9.999):
        dropped = send_chat(state, "p1", "encore", NOW + later)
        assert dropped.entries == (), later
        assert dropped.reply == (), later
        assert dropped.state == seen_at(state, "p1", NOW + later), later
        state = dropped.state
    accepted = send_chat(state, "p1", "m6", NOW + WINDOW_SECONDS)

    assert events_of(accepted) == [ChatMessage(seq=8, player_id="p1", text="m6")]
    assert len(accepted.state.chat) == CHAT_LIMIT + 1


def test_ac9_python_each_player_has_a_limit_of_their_own(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    for number in range(1, CHAT_LIMIT + 2):
        state = send_chat(state, "p1", f"m{number}").state

    outcome = send_chat(state, "p2", "à moi")

    assert events_of(outcome) == [ChatMessage(seq=8, player_id="p2", text="à moi")]


def test_ac9_python_refused_and_dropped_messages_are_not_counted(
    fx01_grid: Grid,
) -> None:
    state = set_muted(two_player_room(fx01_grid), "p2", True)  # seq 3
    for _ in range(3):
        refused = send_chat(state, "p2", "refusé")
        assert refusal_code(refused) == ErrorCode.MUTED
        state = refused.state
    state = set_muted(state, "p2", False)  # seq 4
    for number in range(1, CHAT_LIMIT + 1):
        outcome = send_chat(state, "p2", f"b{number}")
        assert len(events_of(outcome)) == 1, number  # seq 5 to 9
        state = outcome.state

    for number in range(1, CHAT_LIMIT + 1):
        state = send_chat(state, "p1", f"a{number}").state  # seq 10 to 14
    for _ in range(CHAT_LIMIT):
        dropped = send_chat(state, "p1", "trop tôt", NOW + 9)
        assert dropped.entries == ()
        state = dropped.state
    accepted = send_chat(state, "p1", "a6", NOW + WINDOW_SECONDS)

    assert events_of(accepted) == [ChatMessage(seq=15, player_id="p1", text="a6")]


def test_ac9_python_a_sixth_reaction_in_10_seconds_is_dropped(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    expected = (shown("p1", IDES, Reaction.CLAP),)
    for number in range(1, CHAT_LIMIT + 1):
        relayed = send_react(state, "p1", IDES, Reaction.CLAP)
        assert relayed.reply == expected, number
        assert relayed.to_others == expected, number
        state = relayed.state

    dropped = send_react(state, "p1", IDES, Reaction.CLAP)
    again = send_react(dropped.state, "p1", IDES, Reaction.CLAP, NOW + WINDOW_SECONDS)

    assert dropped.entries == ()
    assert dropped.reply == ()
    assert dropped.to_others == ()
    assert dropped.state == seen_at(state, "p1", NOW)
    assert again.reply == expected
    assert again.to_others == expected


def test_ac9_python_a_dropped_chat_message_still_wakes_an_idle_sender(
    fx01_grid: Grid,
) -> None:
    config = RoomConfig(idle_after_seconds=5, silence_timeout_seconds=3600)
    state = two_player_room(fx01_grid)
    for number in range(1, CHAT_LIMIT + 1):
        outcome = send_chat(state, "p2", f"m{number}", NOW, config)
        assert len(events_of(outcome)) == 1, number
        state = outcome.state
    idle = tick(state, NOW + 5, config).state
    assert player_record(idle, "p2").state == PlayerState.IDLE

    dropped = send_chat(idle, "p2", "m6", NOW + 6, config)

    woken = PlayerStateChanged(
        seq=idle.seq + 1, player_id="p2", state=PlayerState.ACTIVE
    )
    assert events_of(dropped) == [woken]
    assert dropped.reply == ()
    assert dropped.state.chat == idle.chat


# ---- AC-9: the sliding window, dropped reactions, restart ----

STAGGER_SECONDS = (0.0, 1.0, 2.0, 3.0, 4.0)  # the five sends of the window
NO_WORD = ClueRef(row=1, column=0, clue_index=0)  # a letter cell: names no word


def test_ac9_python_the_chat_window_slides_with_staggered_sends(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for offset in STAGGER_SECONDS:
        outcome = send_chat(state, "p1", f"m{offset}", NOW + offset)
        assert len(events_of(outcome)) == 1, offset
        state = outcome.state

    accepted = send_chat(state, "p1", "m10", NOW + 10.0)
    dropped = send_chat(accepted.state, "p1", "m10.5", NOW + 10.5)

    assert events_of(accepted) == [ChatMessage(seq=8, player_id="p1", text="m10")]
    assert dropped.entries == ()
    assert dropped.reply == ()
    assert dropped.state == seen_at(accepted.state, "p1", NOW + 10.5)


def test_ac9_python_the_reaction_window_slides_with_staggered_sends(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    expected = (shown("p1", IDES, Reaction.WOW),)
    for offset in STAGGER_SECONDS:
        outcome = send_react(state, "p1", IDES, Reaction.WOW, NOW + offset)
        assert outcome.reply == expected, offset
        state = outcome.state

    accepted = send_react(state, "p1", IDES, Reaction.WOW, NOW + 10.0)
    dropped = send_react(accepted.state, "p1", IDES, Reaction.WOW, NOW + 10.5)

    assert accepted.reply == expected
    assert accepted.to_others == expected
    assert dropped.reply == ()
    assert dropped.to_others == ()
    assert dropped.entries == ()


def test_ac9_python_a_muted_reaction_is_not_counted(fx01_grid: Grid) -> None:
    state = set_muted(two_player_room(fx01_grid), "p2", True)
    for _ in range(CHAT_LIMIT + 1):
        dropped = send_react(state, "p2", IDES, Reaction.CLAP)
        assert dropped.reply == ()
        state = dropped.state
    assert player_record(state, "p2").recent_reactions == ()

    state = set_muted(state, "p2", False)
    expected = (shown("p2", IDES, Reaction.CLAP),)
    for number in range(1, CHAT_LIMIT + 1):
        relayed = send_react(state, "p2", IDES, Reaction.CLAP)
        assert relayed.reply == expected, number
        assert relayed.to_others == expected, number
        state = relayed.state


def test_ac9_python_a_reaction_on_no_word_is_not_counted(fx01_grid: Grid) -> None:
    state = two_player_room(fx01_grid)
    for _ in range(CHAT_LIMIT + 1):
        dropped = send_react(state, "p1", NO_WORD, Reaction.CLAP)
        assert dropped.reply == ()
        state = dropped.state
    assert player_record(state, "p1").recent_reactions == ()

    expected = (shown("p1", IDES, Reaction.CLAP),)
    for number in range(1, CHAT_LIMIT + 1):
        relayed = send_react(state, "p1", IDES, Reaction.CLAP)
        assert relayed.reply == expected, number
        state = relayed.state


def test_ac9_python_a_reaction_over_the_limit_is_not_counted(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for _ in range(CHAT_LIMIT):
        state = send_react(state, "p1", IDES, Reaction.CLAP).state
    kept = player_record(state, "p1").recent_reactions

    for _ in range(CHAT_LIMIT):
        dropped = send_react(state, "p1", IDES, Reaction.CLAP, NOW + 9)
        assert dropped.reply == ()
        state = dropped.state
    again = send_react(state, "p1", IDES, Reaction.CLAP, NOW + WINDOW_SECONDS)

    assert player_record(state, "p1").recent_reactions == kept
    assert again.reply == (shown("p1", IDES, Reaction.CLAP),)


def test_ac9_python_a_restart_gives_every_player_fresh_windows(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)
    for number in range(1, CHAT_LIMIT + 1):
        state = send_chat(state, "p1", f"m{number}").state
        state = send_react(state, "p1", IDES, Reaction.CLAP).state
    state = send_chat(state, "p2", "salut").state
    state = send_react(state, "p2", IDES, Reaction.WOW).state
    state = disconnect_player(state, "p2", NOW).state

    # Beforehand: five times in each of p1's windows, one in each of p2's, and p2
    # is already disconnected when the restart comes.
    before_p1 = player_record(state, "p1")
    before_p2 = player_record(state, "p2")
    assert before_p1.recent_chat == (NOW,) * CHAT_LIMIT
    assert before_p1.recent_reactions == (NOW,) * CHAT_LIMIT
    assert before_p2.recent_chat == (NOW,)
    assert before_p2.recent_reactions == (NOW,)
    assert before_p1.state != PlayerState.DISCONNECTED
    assert before_p2.state == PlayerState.DISCONNECTED

    outcome = after_restart(state, NOW + 1)

    # The restart writes an entry for each player who was not disconnected: p1.
    only_entry = PlayerStateChanged(
        seq=state.seq + 1, player_id="p1", state=PlayerState.DISCONNECTED
    )
    assert events_of(outcome) == [only_entry]
    player_ids = [player.player_id for player in outcome.state.players]
    assert player_ids == ["p1", "p2"]
    for player in outcome.state.players:
        assert player.recent_chat == (), player.player_id
        assert player.recent_reactions == (), player.player_id


# ---- AC-9: the WebSocket with a fake clock ----


def test_ac9_websocket_the_server_drops_chat_over_the_limit_without_an_answer(
    fx01_grid: Grid, dist_dir: Path, fake_clock: FakeClock
) -> None:
    config = RoomConfig(
        max_edits_per_second=1000, tick_seconds=0.05, silence_timeout_seconds=3600
    )
    with (
        chat_room(fx01_grid, dist_dir, config, clock=fake_clock) as (client, _, code),
        contextlib.ExitStack() as stack,
    ):
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
        for number in range(1, 8):
            bob.send(Chat(text=f"m{number}"))
        ping_and_wait(bob)
        ping_and_wait(ana)
        ana_texts = [message.text for message in chat_messages_of(ana)]
        bob_texts = [message.text for message in chat_messages_of(bob)]
        bob_errors = bob.errors()

        fake_clock.advance(WINDOW_SECONDS)
        bob.send(Chat(text="m8"))
        wait_for_chat_count(ana, CHAT_LIMIT + 1)
        ana_last = chat_messages_of(ana)[-1].text

    first_five = [f"m{number}" for number in range(1, CHAT_LIMIT + 1)]
    assert ana_texts == first_five
    assert bob_texts == first_five
    assert bob_errors == []
    assert ana_last == "m8"
