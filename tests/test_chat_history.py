"""Tests of social/chat, AC-21: the history is the room's newest 200 messages.

Ana (`p1`, the host) and Bob (`p2`) are in a FX-01 room at seq 2 (`joined_room`).
They send messages with `handle_message`, alternately, with a chat limit that never
drops one: message number n has the seq `2 + n` and the text `Ligne <seq>`. The
history is read three ways, which have to agree:

- live: `RoomState.chat` after the last message, and the `chat` of the snapshot a
  joiner gets from `join_room` (`Snapshot.chat`);
- from the store: `RoomStore.load_room` of a file holding the first state and the
  whole log, with no later snapshot; with a snapshot saved midway through the
  history; and with a snapshot saved after the last message;
- on the page: a room of the live server whose log holds 205 messages, opened in a
  browser, shows the newest 200 in its stream.

A room stored before the history had a bound may hold more: its snapshot, written
by hand into the store file (`server_harness.insert_stored_snapshot`), has 300
messages. One more message brings the live room, a joiner's snapshot and the room
loaded from the store to the newest 200.

A message that leaves the history still counts: the room's seq is that of the
last message. The page's cap on the stream is the same 200 (`social/chat.md`
rule 18), so the page part of the criterion already held before the server capped
the history; it is checked here with the real server, which sends the 200.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple

import pytest
from playwright.sync_api import Browser, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import ChatMessage, Join, Snapshot
from nock.room import LogEntry, RoomConfig, RoomState, join_room, new_room
from nock.store import RoomStore
from server_harness import insert_stored_snapshot
from spec022_harness import chat_seqs, open_panel, send_chat
from spec024_harness import (
    NOW,
    ROOM_CODE,
    EnterRoom,
    joined_room,
)
from spec032_harness import grid_from_text

HISTORY_CAP = 200
JOINED_AT_SEQ = 2
CHAT_CONFIG = RoomConfig(chat_limit=1_000)
SENT_BY = ("p1", "p2")
STORED_MESSAGES = 205
MIDWAY_SEQ = 150
LEGACY_MESSAGES = 300


class SentRoom(NamedTuple):
    """A room where messages were sent: its states, its log and its first state."""

    initial: RoomState
    states: dict[int, RoomState]
    entries: list[LogEntry]

    @property
    def live(self) -> RoomState:
        """The state after the last message."""
        return self.states[max(self.states)]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def room_after_messages(grid: Grid, count: int) -> SentRoom:
    """The room after `count` messages, alternately from Ana and from Bob."""
    state, entries = joined_room(grid)
    states = {state.seq: state}
    for number in range(count):
        seq = JOINED_AT_SEQ + number + 1
        sender = SENT_BY[number % len(SENT_BY)]
        outcome = send_chat(state, sender, f"Ligne {seq}", NOW, CHAT_CONFIG)
        assert len(outcome.entries) == 1, f"message {seq} was not accepted"
        entries.extend(outcome.entries)
        state = outcome.state
        states[state.seq] = state
    return SentRoom(new_room(ROOM_CODE, grid, NOW), states, entries)


def expected_seqs(count: int) -> list[int]:
    """The seqs of the newest 200 messages of a history of `count` messages."""
    last_seq = JOINED_AT_SEQ + count
    first_seq = max(JOINED_AT_SEQ + 1, last_seq - HISTORY_CAP + 1)
    return list(range(first_seq, last_seq + 1))


def seqs_of(messages: tuple[ChatMessage, ...]) -> list[int]:
    """The seq of each message, in the order given."""
    seqs: list[int] = []
    for message in messages:
        seqs.append(message.seq)
    return seqs


def texts_of(messages: tuple[ChatMessage, ...]) -> list[str]:
    """The text of each message, in the order given."""
    texts: list[str] = []
    for message in messages:
        texts.append(message.text)
    return texts


@pytest.mark.parametrize("count", [150, 200, 201, 205])
def test_ac21_the_live_room_and_a_joiners_snapshot_hold_the_newest_200_messages(
    fx01_grid: Grid, count: int
) -> None:
    sent = room_after_messages(fx01_grid, count)
    seqs = expected_seqs(count)

    joined = join_room(
        sent.live, Join(nickname="Cy", resume_token=None), NOW, "p3", "cy-token-0001-aa"
    )

    reply = joined.reply[0]
    assert isinstance(reply, Snapshot)
    assert sent.live.seq == JOINED_AT_SEQ + count
    assert seqs_of(sent.live.chat) == seqs
    assert seqs_of(reply.chat) == seqs
    assert texts_of(reply.chat) == [f"Ligne {seq}" for seq in seqs]


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "nock.sqlite3"


@pytest.fixture
def store(store_path: Path) -> Iterator[RoomStore]:
    opened = RoomStore(store_path)
    yield opened
    opened.close()


@pytest.mark.parametrize(
    "snapshot_seq",
    [
        pytest.param(None, id="the log alone"),
        pytest.param(MIDWAY_SEQ, id="a snapshot midway"),
        pytest.param(JOINED_AT_SEQ + STORED_MESSAGES, id="a snapshot at the end"),
    ],
)
def test_ac21_the_room_loaded_from_the_store_holds_the_newest_200_messages(
    store: RoomStore, fx01_grid: Grid, snapshot_seq: int | None
) -> None:
    sent = room_after_messages(fx01_grid, STORED_MESSAGES)
    store.create_room(sent.initial)
    store.append(ROOM_CODE, sent.entries)
    if snapshot_seq is not None:
        store.save_snapshot(sent.states[snapshot_seq])

    loaded = store.load_room(ROOM_CODE)

    assert loaded is not None
    assert loaded.seq == JOINED_AT_SEQ + STORED_MESSAGES
    assert seqs_of(loaded.chat) == expected_seqs(STORED_MESSAGES)
    assert loaded.chat == sent.live.chat


def test_ac21_a_message_after_a_snapshot_of_200_drops_the_oldest(
    store: RoomStore, fx01_grid: Grid
) -> None:
    sent = room_after_messages(fx01_grid, STORED_MESSAGES)
    full_seq = JOINED_AT_SEQ + HISTORY_CAP
    store.create_room(sent.initial)
    store.append(ROOM_CODE, sent.entries)
    store.save_snapshot(sent.states[full_seq])

    loaded = store.load_room(ROOM_CODE)

    assert sent.states[full_seq].chat[0].seq == JOINED_AT_SEQ + 1
    assert loaded is not None
    assert loaded.chat[0].seq == JOINED_AT_SEQ + STORED_MESSAGES - HISTORY_CAP + 1
    assert len(loaded.chat) == HISTORY_CAP


def stored_room_over_the_cap(
    grid: Grid, path: Path, count: int
) -> tuple[RoomStore, RoomState]:
    """A store file holding a room whose newest snapshot has `count` messages.

    The room is the one of `joined_room` followed by `count` messages, all in the
    log; its snapshot after the last one holds every message, written by hand as
    a store kept it before the history had a bound.

    Returns:
        The store opened on the file, and the room it loads.
    """
    state, entries = joined_room(grid)
    messages: list[ChatMessage] = []
    for number in range(count):
        seq = JOINED_AT_SEQ + number + 1
        sender = SENT_BY[number % len(SENT_BY)]
        message = ChatMessage(seq=seq, player_id=sender, text=f"Ligne {seq}")
        messages.append(message)
        entries.append(LogEntry(at=NOW, event=message))
    stored = state.model_copy(
        update={"chat": tuple(messages), "seq": JOINED_AT_SEQ + count}
    )
    writer = RoomStore(path)
    try:
        writer.create_room(new_room(ROOM_CODE, grid, NOW))
        writer.append(ROOM_CODE, entries)
    finally:
        writer.close()
    insert_stored_snapshot(path, stored)
    store = RoomStore(path)
    loaded = store.load_room(ROOM_CODE)
    assert loaded is not None
    assert len(loaded.chat) == count, "the stored history is loaded as it was"
    return store, loaded


def test_ac21_a_stored_history_over_200_keeps_the_newest_200_after_a_message(
    store_path: Path, fx01_grid: Grid
) -> None:
    store, stored = stored_room_over_the_cap(fx01_grid, store_path, LEGACY_MESSAGES)
    try:
        last_seq = stored.seq + 1
        outcome = send_chat(stored, "p1", f"Ligne {last_seq}", NOW, CHAT_CONFIG)
        assert len(outcome.entries) == 1, "the message was not accepted"
        live = outcome.state
        joined = join_room(
            live, Join(nickname="Cy", resume_token=None), NOW, "p3", "cy-token-0001-aa"
        )
        store.append(ROOM_CODE, outcome.entries)
        loaded = store.load_room(ROOM_CODE)
    finally:
        store.close()

    seqs = list(range(last_seq - HISTORY_CAP + 1, last_seq + 1))
    reply = joined.reply[0]
    assert isinstance(reply, Snapshot)
    assert live.seq == last_seq
    assert seqs_of(live.chat) == seqs
    assert seqs_of(reply.chat) == seqs
    assert texts_of(reply.chat) == [f"Ligne {seq}" for seq in seqs]
    assert loaded is not None
    assert loaded.seq == last_seq
    assert loaded.chat == live.chat


# ---- The stream on the page ----------------------------------------------------------


@pytest.fixture
def room_registry(tmp_path: Path) -> Iterator[RoomRegistry]:
    """The live server's registry, on a store file that the test fills."""
    store = RoomStore(tmp_path / "live.sqlite3")
    registry = RoomRegistry(store=store)
    yield registry
    registry.close()
    store.close()


def test_ac21_browser_the_stream_shows_the_newest_200_of_205_messages(
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    entries: list[LogEntry] = []
    for seq in range(1, STORED_MESSAGES + 1):
        message = ChatMessage(seq=seq, player_id="p1", text=f"Ligne {seq}")
        entries.append(LogEntry(at=NOW, event=message))
    room_registry.store.append(code, entries)
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        page = context.new_page()
        enter_room(page, f"{live_server}/r/{code}", "Ana")
        open_panel(page)

        expect(page.get_by_test_id("chat-message")).to_have_count(HISTORY_CAP)
        assert chat_seqs(page) == list(
            range(STORED_MESSAGES - HISTORY_CAP + 1, STORED_MESSAGES + 1)
        )
    finally:
        context.close()
