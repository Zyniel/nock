"""Tests of lobby/host, AC-17: a room keeps its newest 100 banned tokens.

Ana, the host, lets one player after another join and removes each (101 players,
`p2` to `p102`, the token of `p<n>` being `token_of(n)`), all on the rules
(`join_room`, `handle_message`). The first removed player's token is then no
longer banned, and the 100 others are. The room is read four ways, each of which
has to give the same joins:

- live: the state the rules return;
- replayed: the initial state and `replay` of every logged entry, in order;
- from the log: a `RoomStore` file holding the first snapshot and the whole log,
  read by `load_room` (a restart with no later snapshot);
- from a snapshot: the same store after `save_snapshot` of the live state, read by
  `load_room` (a restart after the room's snapshot).

A join with a token is `join_room` with that token: a banned token gets the
`removed` error and a close; any other token is a new player, who gets a snapshot
with the id and the token the rules give them.

A room stored before the banned tokens had a bound may hold more: its snapshot,
written by hand into the store file (`server_harness.insert_stored_snapshot`),
bans 150 tokens (`token_of(1000)` to `token_of(1149)`, oldest first) while Ana and
Bob (`p2`) are in it. Ana removing Bob brings the live room and the room loaded
from the store to the newest 100: the last 99 of those and Bob's.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.protocol import ErrorCode, ErrorMessage, Join, RemovePlayer, Snapshot
from nock.room import (
    LogEntry,
    Outcome,
    RoomState,
    handle_message,
    join_room,
    new_room,
    replay,
)
from nock.store import RoomStore
from server_harness import insert_stored_snapshot
from spec014_harness import NEW_PLAYER_ID, NEW_TOKEN, NOW, QUIET_RULES, token_of
from spec018_harness import grid_from_text

CODE = "ABCDEF"
HOST = "p1"
REMOVALS = 101
KEPT_BANS = 100
FIRST_REMOVED = 2  # `p2`, the first player removed: the only token that is forgotten
LAST_REMOVED = FIRST_REMOVED + REMOVALS - 1  # `p102`


class RemovedRoom:
    """The room after the removals: its states and its log."""

    def __init__(self, grid: Grid) -> None:
        self.initial = new_room(CODE, grid, NOW)
        self.entries: list[LogEntry] = []
        self.live = self.initial
        self._apply(join_room(self.live, _join("Ana"), NOW, HOST, token_of(1)))
        for number in range(FIRST_REMOVED, LAST_REMOVED + 1):
            player_id = f"p{number}"
            joined = join_room(
                self.live, _join("Bob"), NOW, player_id, token_of(number)
            )
            self._apply(joined)
            removed = handle_message(
                self.live, HOST, RemovePlayer(player_id=player_id), NOW, QUIET_RULES
            )
            self._apply(removed)
        assert len(self.live.players) == 1, "only the host is left"

    def _apply(self, outcome: Outcome) -> None:
        """Keep the state and the entries of a step, fail on a refusal."""
        for message in outcome.reply:
            assert not isinstance(message, ErrorMessage), message
        self.entries.extend(outcome.entries)
        self.live = outcome.state


def _join(nickname: str, resume_token: str | None = None) -> Join:
    return Join(nickname=nickname, resume_token=resume_token)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def removed_room(fx01_grid: Grid) -> RemovedRoom:
    return RemovedRoom(fx01_grid)


def live_state(room: RemovedRoom, tmp_path: Path) -> RoomState:
    return room.live


def replayed_state(room: RemovedRoom, tmp_path: Path) -> RoomState:
    state = room.initial
    for entry in room.entries:
        state = replay(state, entry)
    return state


def state_from_log(room: RemovedRoom, tmp_path: Path) -> RoomState:
    store = RoomStore(tmp_path / "from-log.sqlite3")
    try:
        store.create_room(room.initial)
        store.append(CODE, room.entries)
        loaded = store.load_room(CODE)
    finally:
        store.close()
    assert loaded is not None
    return loaded


def state_from_snapshot(room: RemovedRoom, tmp_path: Path) -> RoomState:
    store = RoomStore(tmp_path / "from-snapshot.sqlite3")
    try:
        store.create_room(room.initial)
        store.append(CODE, room.entries)
        store.save_snapshot(room.live)
        loaded = store.load_room(CODE)
    finally:
        store.close()
    assert loaded is not None
    return loaded


READINGS: dict[str, Callable[[RemovedRoom, Path], RoomState]] = {
    "live": live_state,
    "replayed": replayed_state,
    "from the log": state_from_log,
    "from a snapshot": state_from_snapshot,
}


@pytest.fixture(params=list(READINGS))
def room_state(
    request: pytest.FixtureRequest, removed_room: RemovedRoom, tmp_path: Path
) -> RoomState:
    return READINGS[request.param](removed_room, tmp_path)


def test_ac17_the_first_removed_players_token_joins_as_a_new_player(
    room_state: RoomState,
) -> None:
    join = _join("Zed", token_of(BOB_NUMBER))

    outcome = join_room(room_state, join, NOW, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is False
    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, Snapshot)
    assert reply.you == NEW_PLAYER_ID


@pytest.mark.parametrize(
    "number",
    [FIRST_REMOVED + 1, FIRST_REMOVED + 50, LAST_REMOVED - 1, LAST_REMOVED],
)
def test_ac17_the_newest_100_removed_tokens_are_still_banned(
    room_state: RoomState, number: int
) -> None:
    join = _join("Zed", token_of(number))

    outcome = join_room(room_state, join, NOW, NEW_PLAYER_ID, NEW_TOKEN)

    assert outcome.close_sender is True
    assert len(outcome.reply) == 1
    reply = outcome.reply[0]
    assert isinstance(reply, ErrorMessage)
    assert reply.code == ErrorCode.REMOVED


def test_ac17_the_room_holds_100_banned_tokens(room_state: RoomState) -> None:
    assert len(room_state.removed_tokens) == KEPT_BANS
    assert set(room_state.removed_tokens) == {
        token_of(number) for number in range(FIRST_REMOVED + 1, LAST_REMOVED + 1)
    }


# ---- A room stored with more than 100 banned tokens ---------------------------------

LEGACY_BANS = 150
LEGACY_FIRST = 1000  # `token_of(1000)`, the oldest token banned in the stored room
BOB_NUMBER = 2  # Bob joins second, after Ana (`p1`)
BOB = f"p{BOB_NUMBER}"


def legacy_tokens() -> tuple[str, ...]:
    """The 150 tokens the stored room bans, oldest first."""
    tokens: list[str] = []
    for number in range(LEGACY_FIRST, LEGACY_FIRST + LEGACY_BANS):
        tokens.append(token_of(number))
    return tuple(tokens)


def bob_removed_from_a_stored_room(
    grid: Grid, path: Path
) -> tuple[RoomState, RoomState]:
    """Ana removes Bob from a room whose stored snapshot bans 150 tokens.

    Returns:
        The live state after the removal, and the room the store then loads.
    """
    state = new_room(CODE, grid, NOW)
    entries: list[LogEntry] = []
    for nickname, player_id, number in (("Ana", HOST, 1), ("Bob", BOB, BOB_NUMBER)):
        joined = join_room(state, _join(nickname), NOW, player_id, token_of(number))
        entries.extend(joined.entries)
        state = joined.state
    stored = state.model_copy(update={"removed_tokens": legacy_tokens()})
    writer = RoomStore(path)
    try:
        writer.create_room(new_room(CODE, grid, NOW))
        writer.append(CODE, entries)
    finally:
        writer.close()
    insert_stored_snapshot(path, stored)
    store = RoomStore(path)
    try:
        loaded = store.load_room(CODE)
        assert loaded is not None
        assert loaded.removed_tokens == legacy_tokens(), "stored as it was"
        removed = handle_message(
            loaded, HOST, RemovePlayer(player_id=BOB), NOW, QUIET_RULES
        )
        assert len(removed.entries) > 0, "Bob was not removed"
        store.append(CODE, removed.entries)
        reloaded = store.load_room(CODE)
    finally:
        store.close()
    assert reloaded is not None
    return removed.state, reloaded


@pytest.mark.parametrize("reading", ["live", "from the store"])
def test_ac17_a_stored_room_over_100_bans_keeps_the_newest_100_after_a_removal(
    fx01_grid: Grid, tmp_path: Path, reading: str
) -> None:
    live, loaded = bob_removed_from_a_stored_room(
        fx01_grid, tmp_path / "legacy.sqlite3"
    )
    state = live if reading == "live" else loaded
    dropped = token_of(LEGACY_FIRST + LEGACY_BANS - KEPT_BANS)
    oldest_kept = token_of(LEGACY_FIRST + LEGACY_BANS - KEPT_BANS + 1)

    forgotten = join_room(state, _join("Zed", dropped), NOW, NEW_PLAYER_ID, NEW_TOKEN)
    banned = join_room(state, _join("Zed", oldest_kept), NOW, NEW_PLAYER_ID, NEW_TOKEN)

    newest = (*legacy_tokens()[LEGACY_BANS - KEPT_BANS + 1 :], token_of(BOB_NUMBER))
    assert len(state.removed_tokens) == KEPT_BANS
    assert set(state.removed_tokens) == set(newest)
    assert forgotten.close_sender is False
    forgotten_reply = forgotten.reply[0]
    assert isinstance(forgotten_reply, Snapshot)
    assert forgotten_reply.you == NEW_PLAYER_ID
    assert banned.close_sender is True
    banned_reply = banned.reply[0]
    assert isinstance(banned_reply, ErrorMessage)
    assert banned_reply.code == ErrorCode.REMOVED
