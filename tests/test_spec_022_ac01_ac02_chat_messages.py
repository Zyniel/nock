"""Tests of spec 022, AC-1 and AC-2: chat messages reach every player in one
order, and a message holds 1 to 280 characters.

AC-1 is tested on `handle_message` (seqs, `state.chat`, `snapshot_for`, a solved
grid), on the real WebSocket (two clients sending at once, then a third joining)
and with two browsers on the live server. The edge cases the spec files under
AC-1 ("Order", "Departed authors", "History size", "Feed") are checked on the
page: the first three with a mocked socket, the feed with the live browsers.
AC-2 is tested on the WebSocket (280, 281, empty and blank texts, trimming) and
on the page's chat form.

Not tested: the edge case of AC-2 on the separators U+001C to U+001F, which the
spec says Python's `strip()` empties; the protocol's `ChatText` (spec 039) keeps
them today, so the expected answer is a question for the lead (see the report).

The shared setup is in `spec022_harness`.
"""

from __future__ import annotations

import contextlib
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Chat,
    ChatMessage,
    ClientMessage,
    ErrorCode,
    ErrorMessage,
    LeaveReason,
    PlayerLeft,
    Pong,
    ServerMessage,
)
from nock.room import RoomConfig, snapshot_for
from spec022_harness import (
    LIVE_WITHIN_SECONDS,
    QUIET_MS,
    WS_CONFIG,
    ChatLine,
    assert_sends_nothing,
    chat_frame,
    chat_json,
    chat_messages_of,
    chat_room,
    chat_seqs,
    chat_triples,
    expect_seq,
    frames_after,
    new_player_page,
    open_chat_room,
    open_panel,
    read_chat_lines,
    remaining_ms,
    room_seq,
    send_chat,
    wait_for_chat_count,
)
from spec024_harness import (
    EnterRoom,
    events_of,
    full17,
    grid_from_text,
    join_one,
    join_peers,
    load_fr,
    make_dist_dir,
    ping_and_wait,
    two_player_room,
    write,
)

FIRST_TEXT = "Qui a une idée pour le 3 ?"
SECOND_TEXT = "IDES, je crois"
MESSAGES_PER_CLIENT = 20
ALL_MESSAGES = 2 * MESSAGES_PER_CLIENT
SHOWN_LINES = 200  # the page shows the last 200 lines (decision 12)
THREAD_START_SECONDS = 10.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


# ---- AC-1: the rule ----


def test_ac1_python_two_chat_messages_get_the_next_seqs_and_stay_in_order(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = send_chat(state, "p1", FIRST_TEXT)
    second = send_chat(first.state, "p2", SECOND_TEXT)

    first_message = ChatMessage(seq=3, player_id="p1", text=FIRST_TEXT)
    second_message = ChatMessage(seq=4, player_id="p2", text=SECOND_TEXT)
    assert events_of(first) == [first_message]
    assert first.reply == ()
    assert events_of(second) == [second_message]
    assert second.reply == ()
    assert second.state.chat == (first_message, second_message)
    assert snapshot_for(second.state, "p1").chat == (first_message, second_message)


def test_ac1_python_chat_keeps_working_on_a_solved_grid(fx01_grid: Grid) -> None:
    solved = write(full17(fx01_grid), "p1", 4, 4, "T").state
    assert solved.solved is True

    outcome = send_chat(solved, "p2", "Bravo à tous")

    expected = ChatMessage(seq=solved.seq + 1, player_id="p2", text="Bravo à tous")
    assert events_of(outcome) == [expected]
    assert outcome.reply == ()
    assert outcome.state.chat == (expected,)


# ---- AC-1: the WebSocket ----


def send_numbered_texts(
    peer_send: Callable[[ClientMessage], None], prefix: str, start: threading.Barrier
) -> None:
    """Send `<prefix>1` to `<prefix>20` as chat messages, once both threads run."""
    start.wait(timeout=THREAD_START_SECONDS)
    for number in range(1, MESSAGES_PER_CLIENT + 1):
        peer_send(Chat(text=f"{prefix}{number}"))


def texts_of(triples: list[tuple[int, str, str]], player_id: str) -> list[str]:
    """The texts of one sender's lines, in the list's order."""
    texts: list[str] = []
    for _, sender, text in triples:
        if sender == player_id:
            texts.append(text)
    return texts


def test_ac1_websocket_two_clients_sending_at_once_see_one_order(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    config = RoomConfig(
        max_edits_per_second=1000, silence_timeout_seconds=600, chat_limit=1000
    )
    with (
        chat_room(fx01_grid, dist_dir, config) as (client, _, code),
        contextlib.ExitStack() as stack,
    ):
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
        start = threading.Barrier(2)
        senders = [
            threading.Thread(target=send_numbered_texts, args=(ana.send, "A", start)),
            threading.Thread(target=send_numbered_texts, args=(bob.send, "B", start)),
        ]
        for sender in senders:
            sender.start()
        for sender in senders:
            sender.join(timeout=THREAD_START_SECONDS)
        wait_for_chat_count(ana, ALL_MESSAGES)
        wait_for_chat_count(bob, ALL_MESSAGES)
        ping_and_wait(ana)
        ping_and_wait(bob)
        ana_lines = chat_triples(chat_messages_of(ana))
        bob_lines = chat_triples(chat_messages_of(bob))
        cy = join_one(stack, client, code, "Cy")
        cy_lines = chat_triples(cy.snapshot().chat)
        ana_id = ana.you()
        bob_id = bob.you()

    assert len(ana_lines) == ALL_MESSAGES
    assert ana_lines == bob_lines
    seqs = [seq for seq, _, _ in ana_lines]
    assert seqs == list(range(seqs[0], seqs[0] + ALL_MESSAGES))
    expected_a = [f"A{number}" for number in range(1, MESSAGES_PER_CLIENT + 1)]
    expected_b = [f"B{number}" for number in range(1, MESSAGES_PER_CLIENT + 1)]
    assert texts_of(ana_lines, ana_id) == expected_a
    assert texts_of(ana_lines, bob_id) == expected_b
    assert cy_lines == ana_lines


# ---- AC-1: two browsers on the live server ----


def last_lines(page: Page, count: int) -> list[tuple[str | None, str | None]]:
    """The `(chat-author, chat-text)` of the last `count` lines of the chat list."""
    pairs: list[tuple[str | None, str | None]] = []
    for line in read_chat_lines(page)[-count:]:
        pairs.append((line.author, line.text))
    return pairs


def expect_last_line(page: Page, author: str, text: str, deadline: float) -> None:
    """Wait until the chat list ends with this line, at the latest at `deadline`."""
    last = page.get_by_test_id("chat-message").last
    expect(last.get_by_test_id("chat-author")).to_have_text(
        author, timeout=remaining_ms(deadline)
    )
    expect(last.get_by_test_id("chat-text")).to_have_text(
        text, timeout=remaining_ms(deadline)
    )


def test_ac1_browser_two_players_see_the_same_lines_in_the_same_order(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    ana, close_ana = new_player_page(browser, live_server, code, "Ana", enter_room)
    try:
        bob, close_bob = new_player_page(browser, live_server, code, "Bob", enter_room)
        try:
            expect(ana.get_by_test_id("roster-player")).to_have_count(2)
            open_panel(ana)
            open_panel(bob)
            feed_before = [
                page.get_by_test_id("feed-item").count() for page in (ana, bob)
            ]

            ana_input = ana.get_by_test_id("chat-input")
            ana_input.fill(FIRST_TEXT)
            ana_input.press("Enter")
            deadline = time.monotonic() + LIVE_WITHIN_SECONDS
            expect_last_line(ana, "Ana", FIRST_TEXT, deadline)
            expect_last_line(bob, "Ana", FIRST_TEXT, deadline)
            expect(ana_input).to_have_value("")

            bob_input = bob.get_by_test_id("chat-input")
            bob_input.fill(SECOND_TEXT)
            bob_input.press("Enter")
            deadline = time.monotonic() + LIVE_WITHIN_SECONDS
            expect_last_line(ana, "Bob", SECOND_TEXT, deadline)
            expect_last_line(bob, "Bob", SECOND_TEXT, deadline)
            ana.wait_for_timeout(QUIET_MS)
            ana_lines = last_lines(ana, 2)
            bob_lines = last_lines(bob, 2)
            feed_after = [
                page.get_by_test_id("feed-item").count() for page in (ana, bob)
            ]
        finally:
            close_bob()
    finally:
        close_ana()

    expected = [("Ana", FIRST_TEXT), ("Bob", SECOND_TEXT)]
    assert ana_lines == expected
    assert bob_lines == expected
    assert feed_after == feed_before  # chat adds no line to the feed (spec 013)


# ---- AC-1: the page's edge cases, with a mocked socket ----


def test_ac1_browser_lines_follow_the_seq_and_keep_their_authors_names(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    someone = load_fr()["feed.someone"]
    chat = [
        ChatMessage(seq=3, player_id="p2", text="Salut"),
        ChatMessage(seq=4, player_id="p9", text="Coucou"),
    ]
    mock = open_chat_room(page, live_server, fx01_grid, seq=5, chat=chat)
    open_panel(page)

    mock.send(chat_frame(7, "p3", "Ligne 7"))  # before seq 6: the page buffers it
    mock.send(chat_frame(6, "p2", "Ligne 6"))
    expect_seq(page, 7)
    left = PlayerLeft(seq=8, player_id="p2", reason=LeaveReason.LEFT)
    mock.send(left.model_dump_json())
    mock.send(chat_frame(9, "p1", "Ligne 9"))
    expect_seq(page, 9)
    page.wait_for_timeout(QUIET_MS)

    assert read_chat_lines(page) == [
        ChatLine("3", "p2", "false", "Bob", "Salut"),
        ChatLine("4", "p9", "false", someone, "Coucou"),
        ChatLine("6", "p2", "false", "Bob", "Ligne 6"),
        ChatLine("7", "p3", "false", "Cy", "Ligne 7"),
        ChatLine("9", "p1", "true", "Ana", "Ligne 9"),
    ]


def test_ac1_browser_the_page_shows_the_last_200_lines_of_a_long_history(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    last_seq = 210
    chat: list[ChatMessage] = []
    for seq in range(6, last_seq + 1):
        chat.append(ChatMessage(seq=seq, player_id="p2", text=f"Ligne {seq}"))
    open_chat_room(page, live_server, fx01_grid, seq=last_seq, chat=chat)

    open_panel(page)

    expect(page.get_by_test_id("chat-message")).to_have_count(SHOWN_LINES)
    assert chat_seqs(page) == list(range(last_seq - SHOWN_LINES + 1, last_seq + 1))


# ---- AC-2: the WebSocket ----


def errors_of(messages: Sequence[ServerMessage]) -> list[ErrorCode]:
    """The codes of the `error` messages in a list of server messages."""
    codes: list[ErrorCode] = []
    for message in messages:
        if isinstance(message, ErrorMessage):
            codes.append(message.code)
    return codes


def without_pongs(messages: Sequence[ServerMessage]) -> list[ServerMessage]:
    """The messages that are not a `pong`."""
    kept: list[ServerMessage] = []
    for message in messages:
        if not isinstance(message, Pong):
            kept.append(message)
    return kept


def test_ac2_websocket_a_message_holds_1_to_280_characters_after_trimming(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    longest = "a" * 280
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, registry, code),
        contextlib.ExitStack() as stack,
    ):
        ana, bob = join_peers(stack, client, code, ["Ana", "Bob"])
        ana.send_text(chat_json(longest))
        wait_for_chat_count(ana, 1)
        wait_for_chat_count(bob, 1)
        bob_count = len(bob.messages())
        ana_count = len(ana.messages())

        for text in ("a" * 281, "", "   "):
            ana.send_text(chat_json(text))
        ana.wait_until(
            lambda: len(errors_of(ana.messages()[ana_count:])) >= 3,
            "three errors",
        )
        ping_and_wait(ana)
        ping_and_wait(bob)
        refusals = errors_of(ana.messages()[ana_count:])
        bob_meanwhile = without_pongs(bob.messages()[bob_count:])
        seq_after_refusals = room_seq(registry, code)

        ana.send_text(chat_json(" salut "))
        wait_for_chat_count(ana, 2)
        wait_for_chat_count(bob, 2)
        ana_id = ana.you()
        ana_messages = chat_messages_of(ana)
        bob_messages = chat_messages_of(bob)

    first = ChatMessage(seq=3, player_id=ana_id, text=longest)
    trimmed = ChatMessage(seq=4, player_id=ana_id, text="salut")
    assert refusals == [ErrorCode.INVALID_MESSAGE] * 3
    assert bob_meanwhile == []
    assert seq_after_refusals == 3
    assert ana_messages == [first, trimmed]
    assert bob_messages == [first, trimmed]


# ---- AC-2: the page's chat form ----


def test_ac2_browser_the_chat_form_keeps_to_280_characters_and_trims(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_chat_room(page, live_server, fx01_grid)
    open_panel(page)
    chat_input = page.get_by_test_id("chat-input")
    send = page.get_by_test_id("chat-send")

    expect(chat_input).to_have_attribute("type", "text")
    expect(chat_input).to_have_attribute("maxlength", "280")
    expect(chat_input).to_have_attribute("autocomplete", "off")
    expect(chat_input).to_have_attribute("placeholder", fr["chat.placeholder"])
    labelled = page.get_by_label(fr["chat.input_label"], exact=True)
    expect(labelled).to_have_attribute("data-testid", "chat-input")
    expect(send).to_have_attribute("type", "submit")
    expect(send).to_have_text(fr["chat.send"])

    chat_input.press_sequentially("a" * 300)
    expect(chat_input).to_have_value("a" * 280)

    for blank in ("", "   "):
        chat_input.fill(blank)
        expect(send).to_be_disabled()
        assert_sends_nothing(page, mock, lambda: chat_input.press("Enter"))

    chat_input.fill("  salut  ")
    expect(send).to_be_enabled()
    frames = frames_after(page, mock, lambda: send.click())

    assert frames == [{"type": "chat", "text": "salut"}]
