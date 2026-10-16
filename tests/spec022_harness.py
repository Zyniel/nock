"""Shared setup of the tests of spec 022: chat and reactions.

This module is not a test file: pytest does not collect it. The tests of spec 022
are in `tests/test_spec_022_*.py`, one file per criterion group:

- `test_spec_022_ac01_ac02_chat_messages.py`: AC-1 (rule, WebSocket, two browsers
  on the live server, and the page's edge cases of AC-1) and AC-2 (WebSocket,
  page);
- `test_spec_022_ac03_ac05_reactions.py`: AC-3 (rule, WebSocket, live server),
  AC-4 (rule for a clue that names no word, page) and AC-5 (page);
- `test_spec_022_ac06_unread.py`: AC-6 (page);
- `test_spec_022_ac07_ac09_mute_storage_and_limits.py`: AC-7 (rule, WebSocket,
  live server, page), AC-8 (`RoomStore`, `replay`, WebSocket with captured logs)
  and AC-9 (rule, WebSocket with a fake clock);
- `test_spec_022_ac10_pacing.py`: AC-10 (page, real time);
- `test_spec_022_ac11_ac12_chat_list_scroll.py`: AC-11 and AC-12 (page);
- `test_spec_022_ac13_ac14_escaping_and_traffic.py`: AC-13 (page) and AC-14
  (WebSocket traffic);
- `test_spec_022_ac15_layout.py`: AC-15 (page, every window, desktop and touch);
- `test_spec_022_ac16_keyboard_and_french.py`: AC-16 (`fr.json`, keyboard, scans);
- `test_spec_022_ac17_banner_over_panel.py`: AC-17 (page, every window);
- `test_spec_022_ac18_mute_closes_picker.py`: AC-18 (page, one 300 ms deadline from
  the mute);
- `test_spec_022_ac19_chat_notes.py`: AC-19 (page, the chat notes at every window);
- `test_spec_022_ac20_focus_after_send.py`: AC-20 (page, the focus after a send).

It holds what more than one of those files uses: the chat and reaction steps on
`handle_message`, the room on the real WebSocket, the snapshot with chat lines
sent on spec 025's mocked socket (which answers pings and follows a
reconnection), and the readings of the chat list and of a clue's reaction. It
builds on spec 024's harness (the two-player room `p1` and `p2` at NOW, the
simulated client `Peer`, spec 035's walker and scans, spec 013's contexts) and on
spec 021's (the clue references of FX-01, the selection of a word by its clue):
the test files import those from there directly. The fixtures (`fx01_grid`,
`dist_dir`) are defined in each test file as thin wrappers, so that no imported
fixture is an unused import.
"""

from __future__ import annotations

import contextlib
import json
import re
import time
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from typing import Any, NamedTuple

from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Chat,
    ChatMessage,
    ClueRef,
    HelpMode,
    MutePlayer,
    PlayerView,
    React,
    Reaction,
    ReactionShown,
    RevealBudget,
    RoomSettings,
    Snapshot,
    grid_view,
)
from nock.room import Outcome, RoomConfig, RoomState, handle_message
from nock.server import create_app
from nock.store import RoomStore
from spec021_harness import clue_at
from spec024_harness import (
    NOW,
    ROOM_CODE,
    SNAPSHOT_RESUME_TOKEN,
    EnterRoom,
    Peer,
    player_view,
)
from spec025_harness import MockRoomSocket, wait_until

PAGE_TIMEOUT_MS = 10_000
QUIET_MS = 300  # "sends nothing": no frame within 300 ms
SETTLE_MS = 400
LIVE_WITHIN_SECONDS = 1.0  # "within 1 s" (AC-1, AC-3, AC-7)
POLL_MS = 25

# The five reactions in the order of spec 039's `Reaction`.
REACTION_VALUES = ["thumbs_up", "clap", "laugh", "wow", "thinking"]
NICKNAMES = {"p1": "Ana", "p2": "Bob", "p3": "Cy"}
DEFAULT_BUDGET = RevealBudget(letters=5, words=1)
CHAT_LIST_SELECTOR = '[data-testid="chat-list"]'

# The WebSocket tests' room: the edit limit never refuses, and no socket is timed
# out for silence while a test waits ("Test harness": spec 011's TestClient with
# `RoomConfig(max_edits_per_second=1000)`).
WS_CONFIG = RoomConfig(max_edits_per_second=1000, silence_timeout_seconds=600)


# ---- Chat and reactions on handle_message ----


def send_chat(
    state: RoomState,
    player_id: str,
    text: str,
    now: float = NOW,
    config: RoomConfig | None = None,
) -> Outcome:
    """Send `Chat(text)` from a player with `handle_message`.

    Args:
        state: The room.
        player_id: The sender.
        text: The message's text.
        now: The clock time of the step.
        config: The room's thresholds; None for the defaults.

    Returns:
        The outcome of the step.
    """
    message = Chat(text=text)
    if config is None:
        return handle_message(state, player_id, message, now)
    return handle_message(state, player_id, message, now, config)


def send_react(
    state: RoomState,
    player_id: str,
    clue: ClueRef,
    reaction: Reaction,
    now: float = NOW,
    config: RoomConfig | None = None,
) -> Outcome:
    """Send `React(clue, reaction)` from a player with `handle_message`.

    Args:
        state: The room.
        player_id: The sender.
        clue: The clue of the word the reaction is on.
        reaction: The reaction.
        now: The clock time of the step.
        config: The room's thresholds; None for the defaults.

    Returns:
        The outcome of the step.
    """
    message = React(clue=clue, reaction=reaction)
    if config is None:
        return handle_message(state, player_id, message, now)
    return handle_message(state, player_id, message, now, config)


def set_muted(
    state: RoomState, player_id: str, muted: bool, now: float = NOW
) -> RoomState:
    """The room after the host `p1` sent `MutePlayer`, checked as accepted."""
    message = MutePlayer(player_id=player_id, muted=muted)
    outcome = handle_message(state, "p1", message, now)
    assert outcome.reply == (), outcome.reply
    assert len(outcome.entries) == 1, outcome.entries
    return outcome.state


def shown(player_id: str, clue: ClueRef, reaction: Reaction) -> ReactionShown:
    """The `ReactionShown` of a reaction."""
    return ReactionShown(player_id=player_id, clue=clue, reaction=reaction)


# ---- The real WebSocket ----


@contextlib.contextmanager
def chat_room(
    grid: Grid,
    dist_dir: Path,
    config: RoomConfig,
    *,
    clock: Callable[[], float] | None = None,
    store: RoomStore | None = None,
) -> Iterator[tuple[TestClient, RoomRegistry, str]]:
    """Yield a client, its registry and the code of one FX-01 room; close it all.

    Args:
        grid: FX-01.
        dist_dir: The directory the app serves.
        config: The room's thresholds.
        clock: The registry's clock; None for the real time.
        store: The registry's store; None for its own in-memory store. A store
            given here is not closed.
    """
    registry = RoomRegistry(config=config, clock=clock, store=store)
    try:
        code = registry.register_room(grid)
        app = create_app(rooms=registry, dist_dir=dist_dir)
        with TestClient(app) as client:
            yield client, registry, code
    finally:
        registry.close()


def chat_messages_of(peer: Peer) -> list[ChatMessage]:
    """Every `chat_message` a simulated client received after its snapshot."""
    found: list[ChatMessage] = []
    for message in peer.messages()[1:]:
        if isinstance(message, ChatMessage):
            found.append(message)
    return found


def reactions_of(peer: Peer) -> list[ReactionShown]:
    """Every `reaction` a simulated client received after its snapshot."""
    found: list[ReactionShown] = []
    for message in peer.messages()[1:]:
        if isinstance(message, ReactionShown):
            found.append(message)
    return found


def wait_for_chat_count(peer: Peer, count: int) -> None:
    """Wait until a client received at least `count` chat messages, else fail."""
    peer.wait_until(
        lambda: len(chat_messages_of(peer)) >= count,
        f"{count} chat_message events on {peer.name}",
    )


def wait_for_reaction_count(peer: Peer, count: int) -> None:
    """Wait until a client received at least `count` reactions, else fail."""
    peer.wait_until(
        lambda: len(reactions_of(peer)) >= count,
        f"{count} reaction frames on {peer.name}",
    )


def chat_triples(messages: Sequence[ChatMessage]) -> list[tuple[int, str, str]]:
    """The `(seq, player_id, text)` of each chat message, in order."""
    triples: list[tuple[int, str, str]] = []
    for message in messages:
        triples.append((message.seq, message.player_id, message.text))
    return triples


def room_seq(registry: RoomRegistry, code: str) -> int:
    """The seq of the room's latest state."""
    state = registry.room_state(code)
    assert state is not None, f"no room {code}"
    return state.seq


def chat_json(text: str) -> str:
    """A raw `chat` frame with a text sent as it is (not trimmed by a model)."""
    return json.dumps({"type": "chat", "text": text})


# ---- The page with a mocked socket ----


def three_players(host: str = "p1") -> list[PlayerView]:
    """`p1` (Ana), `p2` (Bob) and `p3` (Cy); `host` is the host."""
    return [
        player_view("p1", "Ana", 0, is_host=host == "p1"),
        player_view("p2", "Bob", 1, is_host=host == "p2"),
        player_view("p3", "Cy", 2, is_host=host == "p3"),
    ]


def chat_snapshot(
    grid: Grid,
    *,
    seq: int,
    players: list[PlayerView],
    chat: list[ChatMessage],
) -> Snapshot:
    """A FX-01 snapshot for `p1` with chat lines, help mode `free`, no vote.

    Args:
        grid: FX-01.
        seq: The snapshot's seq.
        players: The roster.
        chat: The snapshot's `chat`, in seq order.

    Returns:
        The snapshot.
    """
    settings = RoomSettings(
        help_mode=HelpMode.FREE, reveal_budget=DEFAULT_BUDGET, locked=False
    )
    return Snapshot(
        seq=seq,
        you="p1",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=grid_view(grid),
        players=tuple(players),
        settings=settings,
        reveal_budget=DEFAULT_BUDGET,
        flags=(),
        chat=tuple(chat),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )


def open_chat_room(
    page: Page,
    base_url: str,
    grid: Grid,
    *,
    seq: int = 5,
    players: list[PlayerView] | None = None,
    chat: list[ChatMessage] | None = None,
) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, join as Ana and show a FX-01 snapshot.

    Args:
        page: A fresh page.
        base_url: The live server, which serves the built client.
        grid: FX-01.
        seq: The snapshot's seq.
        players: The roster (default: `three_players()`, `p1` host).
        chat: The snapshot's chat lines (default: none).

    Returns:
        Spec 025's mocked socket: it answers each ping with a pong, and `send`
        and `close` act on the newest socket the page opened.
    """
    page.set_default_timeout(PAGE_TIMEOUT_MS)
    mock = MockRoomSocket(page)
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Ana")
    nickname_input.press("Enter")
    mock.wait_for_join_on_socket(0)
    shown_players = three_players() if players is None else players
    shown_chat = [] if chat is None else chat
    snapshot = chat_snapshot(grid, seq=seq, players=shown_players, chat=shown_chat)
    mock.send(snapshot.model_dump_json())
    expect_seq(page, seq)
    expect(page.get_by_test_id("cell")).to_have_count(25)
    return mock


def expect_seq(page: Page, seq: int) -> None:
    """Wait until the room page shows `seq` as its `data-seq`, else fail."""
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", str(seq))


def chat_frame(seq: int, player_id: str, text: str) -> str:
    """The JSON text of a `chat_message` event."""
    return ChatMessage(seq=seq, player_id=player_id, text=text).model_dump_json()


def reaction_frame(player_id: str, clue: ClueRef, reaction: Reaction) -> str:
    """The JSON text of a `reaction` frame."""
    return shown(player_id, clue, reaction).model_dump_json()


def open_panel(page: Page, touch: bool = False) -> None:
    """Click (or tap) `chat-toggle` and wait until `chat-panel` shows."""
    toggle = page.get_by_test_id("chat-toggle")
    if touch:
        toggle.tap()
    else:
        toggle.click()
    expect(page.get_by_test_id("chat-panel")).to_be_visible()


class ChatLine(NamedTuple):
    """What one `chat-message` of the chat list shows."""

    seq: str | None
    player_id: str | None
    you: str | None
    author: str | None
    text: str | None


CHAT_LINES_SCRIPT = r"""
() => {
  const lines = [];
  const selector = '[data-testid="chat-list"] [data-testid="chat-message"]';
  for (const item of document.querySelectorAll(selector)) {
    const author = item.querySelector('[data-testid="chat-author"]');
    const text = item.querySelector('[data-testid="chat-text"]');
    lines.push([
      item.getAttribute('data-seq'),
      item.getAttribute('data-player-id'),
      item.getAttribute('data-you'),
      author === null ? null : author.textContent.trim(),
      text === null ? null : text.textContent.trim(),
    ]);
  }
  return lines;
}
"""


def read_chat_lines(page: Page) -> list[ChatLine]:
    """Every `chat-message` of `chat-list`, oldest first."""
    found = page.evaluate(CHAT_LINES_SCRIPT)
    lines: list[ChatLine] = []
    for seq, player_id, you, author, text in found:
        lines.append(ChatLine(seq, player_id, you, author, text))
    return lines


def chat_seqs(page: Page) -> list[int]:
    """The `data-seq` of each `chat-message`, oldest first."""
    seqs: list[int] = []
    for line in read_chat_lines(page):
        assert line.seq is not None, line
        seqs.append(int(line.seq))
    return seqs


def sent_frames(mock: MockRoomSocket) -> list[dict[str, Any]]:
    """Every frame the page sent, `ping` frames left out, as JSON objects.

    The values are the page's JSON, hence `Any`.
    """
    found: list[dict[str, Any]] = []
    for frame in mock.frames_without_pings():
        parsed = json.loads(frame)
        assert isinstance(parsed, dict), frame
        found.append(parsed)
    return found


def frames_of_type(mock: MockRoomSocket, kind: str) -> list[dict[str, Any]]:
    """The frames of one `type` the page sent, in order."""
    found: list[dict[str, Any]] = []
    for frame in sent_frames(mock):
        if frame.get("type") == kind:
            found.append(frame)
    return found


def wait_for_frame_count(
    page: Page, mock: MockRoomSocket, kind: str, count: int
) -> None:
    """Wait until the page sent at least `count` frames of one `type`, else fail."""
    wait_until(page, lambda: len(frames_of_type(mock, kind)) >= count)


def frames_after(
    page: Page, mock: MockRoomSocket, action: Callable[[], object]
) -> list[dict[str, Any]]:
    """Do `action`, then return the frames the page sent, pings left out.

    It waits for a first frame, then QUIET_MS more for any other one.
    """
    before = len(mock.frames_without_pings())
    action()
    wait_until(page, lambda: len(mock.frames_without_pings()) > before)
    page.wait_for_timeout(QUIET_MS)
    return sent_frames(mock)[before:]


def assert_sends_nothing(
    page: Page, mock: MockRoomSocket, action: Callable[[], object]
) -> None:
    """Do `action`, then fail if the page sent a frame other than a ping."""
    before = len(mock.frames_without_pings())
    action()
    page.wait_for_timeout(QUIET_MS)
    assert sent_frames(mock)[before:] == []


def remaining_ms(deadline: float) -> float:
    """Milliseconds left until `deadline` (`time.monotonic`), at least 1.

    Playwright reads a timeout of 0 as "no timeout", hence the floor of 1 ms.
    """
    left = (deadline - time.monotonic()) * 1000
    return max(left, 1.0)


# Where a popover (`chat-panel`, `reaction-picker`) sits in the document: inside
# `room-toolbar` or not, after it or not, and which of the roster, the feed and
# the grid it does not come before.
POPOVER_PLACE_SCRIPT = r"""
testId => {
  const element = document.querySelector(`[data-testid="${testId}"]`);
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  if (element === null || toolbar === null) {
    return null;
  }
  const follows = (first, second) => Boolean(
    first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING
  );
  const notBefore = [];
  for (const id of ['roster', 'activity-feed', 'grid']) {
    const other = document.querySelector(`[data-testid="${id}"]`);
    if (other === null || !follows(element, other)) {
      notBefore.push(id);
    }
  }
  return {
    insideToolbar: toolbar.contains(element),
    afterToolbar: follows(toolbar, element),
    notBefore: notBefore,
  };
}
"""

# A popover outside the toolbar, after it, before the roster, the feed and the grid.
POPOVER_PLACE: dict[str, object] = {
    "insideToolbar": False,
    "afterToolbar": True,
    "notBefore": [],
}


def popover_place(page: Page, test_id: str) -> object:
    """Where `chat-panel` or `reaction-picker` sits in the document order."""
    return page.evaluate(POPOVER_PLACE_SCRIPT, test_id)


# ---- A clue's reaction ----

REACTION_SCRIPT = r"""
clue => {
  const reactions = clue.querySelectorAll('[data-testid="clue-reaction"]');
  const labels = clue.querySelectorAll('[data-testid="clue-reaction-label"]');
  const result = {reactions: reactions.length, labels: labels.length};
  if (reactions.length === 1) {
    result.reaction = reactions[0].getAttribute('data-reaction');
    result.playerId = reactions[0].getAttribute('data-player-id');
    result.ariaHidden = reactions[0].getAttribute('aria-hidden');
    result.text = reactions[0].textContent.trim();
  }
  if (labels.length === 1) {
    result.labelText = labels[0].textContent.trim();
    result.labelHidden = labels[0].classList.contains('visually-hidden');
  }
  return result;
}
"""


def read_reaction(page: Page, clue: ClueRef) -> dict[str, Any]:
    """What the clue of a word shows of the reactions (a JSON object).

    The values are what the page holds, so their types are the page's (`Any`).
    """
    reading = clue_at(page, clue).evaluate(REACTION_SCRIPT)
    assert isinstance(reading, dict)
    return reading


def shown_reading(
    player_id: str, reaction: str, text: str, label: str
) -> dict[str, object]:
    """What a clue showing one reaction must read ("Client: a shown reaction").

    Args:
        player_id: The reacting player's id.
        reaction: The reaction's value, such as `clap`.
        text: The emoji, `t("reaction.<value>")`.
        label: The text of `clue-reaction-label`.
    """
    return {
        "reactions": 1,
        "labels": 1,
        "reaction": reaction,
        "playerId": player_id,
        "ariaHidden": "true",
        "text": text,
        "labelText": label,
        "labelHidden": True,
    }


def reactions_on_page(page: Page) -> int:
    """How many `clue-reaction` elements the whole page holds."""
    return page.get_by_test_id("clue-reaction").count()


# ---- Two browsers on the live server ----


def new_player_page(
    browser: Browser, live_server: str, code: str, nickname: str, enter: EnterRoom
) -> tuple[Page, Callable[[], None]]:
    """A 1280 by 720 page of its own context, joined to a room; and its closer.

    Args:
        browser: The browser of the test.
        live_server: The live server's base URL.
        code: The room's code.
        nickname: The nickname the player enters.
        enter: Spec 011's `enter_room` helper.

    Returns:
        The joined page and the function that closes its context.
    """
    context = browser.new_context(viewport={"width": 1280, "height": 720})
    try:
        page = context.new_page()
        page.set_default_timeout(PAGE_TIMEOUT_MS)
        enter(page, f"{live_server}/r/{code}", nickname)
    except BaseException:
        context.close()
        raise
    return page, context.close


def own_player_id(page: Page) -> str:
    """The player id of the page's own roster row (`data-you="true"`)."""
    row = page.locator('[data-testid="roster-player"][data-you="true"]')
    expect(row).to_have_count(1)
    player_id = row.get_attribute("data-player-id")
    assert player_id is not None
    return player_id


def wait_for_reading(
    page: Page, read: Callable[[], object], expected: object, deadline: float
) -> None:
    """Read until `read()` gives `expected` or `deadline` passes, then assert it.

    Args:
        page: The page whose clock paces the reads.
        read: The reading, made in Python.
        expected: The value it must reach.
        deadline: A `time.monotonic` value.
    """
    while read() != expected and time.monotonic() < deadline:
        page.wait_for_timeout(POLL_MS)
    assert read() == expected
