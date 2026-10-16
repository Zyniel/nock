"""What the operator pages show: the dashboard's figures and the edits of a room.

Pure functions over room logs (spec 038): no I/O and no clock. The server reads
the logs from the store and passes them here, with the time to count from.
"""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from nock.protocol import (
    CellLocked,
    Coordinate,
    GridSolved,
    GridView,
    Letter,
    LetterChanged,
    Nickname,
    PlayerId,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerStateChanged,
    Seq,
)
from nock.room import LogEntry, RoomCode, is_edit

DAY_SECONDS: float = 86_400.0
# spec 036's p95: the ceil(0.95 * n)-th smallest of n values
P95_PERCENT: int = 95

PeriodDays = Literal[1, 7, 30]  # the periods of the dashboard, in days
PERIOD_DAYS: tuple[PeriodDays, ...] = (1, 7, 30)
EditKind = Literal["typed", "erased", "undone", "locked", "revealed"]


class RoomLog(BaseModel):
    """One room's creation time and log, as the dashboard reads them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RoomCode
    created_at: float
    entries: tuple[LogEntry, ...]  # in seq order


class DashboardFigures(BaseModel):
    """The six figures of the dashboard for one period."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    days: PeriodDays
    since: AwareDatetime  # now - days, in UTC
    rooms_created: int = Field(ge=0, strict=True)
    players_per_room: float | None
    completion_rate: float | None  # 0 to 1
    median_solving_ms: float | None
    latency_median_ms: float | None
    latency_p95_ms: int | None
    disconnection_rate: float | None


class RoomEdit(BaseModel):
    """One edit of a room, as the replay shows it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: Seq
    at: AwareDatetime  # the entry's `at`, in UTC
    kind: EditKind
    row: Coordinate
    column: Coordinate
    letter: Letter | None  # the cell's letter after the edit, None when it is empty
    pencil: StrictBool  # the letter_changed's pencil flag; False for a lock
    player_id: PlayerId | None  # who made it; None for "locked" and "revealed"
    # from that player's latest player_joined before the edit; None when unknown
    nickname: Nickname | None


class RoomReplay(BaseModel):
    """What the replay of one room needs: its empty grid and its edits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RoomCode
    grid: GridView  # grid_view(state.grid): no letter, no answer
    edits: tuple[RoomEdit, ...]  # in seq order


# ---- The dashboard ---------------------------------------------------------------


def dashboard_figures(
    rooms: Sequence[RoomLog], days: int, now: float
) -> DashboardFigures:
    """Return the figures of the rooms created at `now - days * DAY_SECONDS` or later.

    Rooms created earlier are ignored. Each figure is defined in spec 038's
    "Dashboard figures"; a figure with no data is None, except `rooms_created`.

    Args:
        rooms: The rooms to read, in any order.
        days: The period: 1, 7 or 30 days before `now`.
        now: The clock time the period ends at, in seconds since the epoch.

    Returns:
        The figures of the period.

    Raises:
        ValueError: `days` is not 1, 7 or 30.
    """
    period = _period_days(days)
    since = now - period * DAY_SECONDS
    period_rooms: list[RoomLog] = []
    for room in rooms:
        if room.created_at >= since:
            period_rooms.append(room)

    join_count = 0
    drop_count = 0
    solved_room_count = 0
    solving_times: list[int] = []
    relay_times: list[int] = []
    for room in period_rooms:
        join_count += _join_count(room.entries)
        drop_count += _drop_count(room.entries)
        room_solving_times = _solving_times(room.entries)
        if len(room_solving_times) > 0:
            solved_room_count += 1
        solving_times.extend(room_solving_times)
        relay_times.extend(_letter_relay_times(room.entries))

    room_count = len(period_rooms)
    return DashboardFigures(
        days=period,
        since=datetime.fromtimestamp(since, UTC),
        rooms_created=room_count,
        players_per_room=_ratio(join_count, room_count),
        completion_rate=_ratio(solved_room_count, room_count),
        median_solving_ms=_median(solving_times),
        latency_median_ms=_median(relay_times),
        latency_p95_ms=_p95(relay_times),
        disconnection_rate=_ratio(drop_count, join_count),
    )


def _period_days(days: int) -> PeriodDays:
    """Return `days` as one of the dashboard's periods.

    Raises:
        ValueError: `days` is not 1, 7 or 30.
    """
    for period in PERIOD_DAYS:
        if days == period:
            return period
    raise ValueError(f"The period must be 1, 7 or 30 days, not {days}")


def _join_count(entries: Sequence[LogEntry]) -> int:
    """Count the `player_joined` entries of a room's log."""
    count = 0
    for entry in entries:
        if isinstance(entry.event, PlayerJoined):
            count += 1
    return count


def _drop_count(entries: Sequence[LogEntry]) -> int:
    """Count the drops of a room's log: the lost connections that came back.

    A drop is a `player_state_changed` to `disconnected` that is followed by one
    to `active` of the same player, before that player's next `disconnected`
    and before any `player_left` of theirs. A player who times out and is seated
    back keeps their id, so their `player_left` ends the wait.
    """
    # The players whose latest disconnection may still turn out to be a drop.
    waiting_players: set[str] = set()
    drops = 0
    for entry in entries:
        event = entry.event
        if isinstance(event, PlayerLeft):
            waiting_players.discard(event.player_id)
        elif isinstance(event, PlayerStateChanged):
            is_back = event.state is PlayerState.ACTIVE
            if event.state is PlayerState.DISCONNECTED:
                waiting_players.add(event.player_id)
            elif is_back and event.player_id in waiting_players:
                drops += 1
                waiting_players.remove(event.player_id)
    return drops


def _solving_times(entries: Sequence[LogEntry]) -> list[int]:
    """Return the `elapsed_ms` of each `grid_solved` entry of a room's log."""
    times: list[int] = []
    for entry in entries:
        if isinstance(entry.event, GridSolved):
            times.append(entry.event.elapsed_ms)
    return times


def _letter_relay_times(entries: Sequence[LogEntry]) -> list[int]:
    """Return the relay times of the `letter_changed` entries that have one."""
    relay_times: list[int] = []
    for entry in entries:
        if isinstance(entry.event, LetterChanged) and entry.relay_ms is not None:
            relay_times.append(entry.relay_ms)
    return relay_times


def _ratio(numerator: int, denominator: int) -> float | None:
    """Return `numerator / denominator`, or None when there is nothing to divide."""
    if denominator == 0:
        return None
    return numerator / denominator


def _median(values: list[int]) -> float | None:
    """Return the median of `values` (`statistics.median`), None when empty."""
    if len(values) == 0:
        return None
    return float(statistics.median(values))


def _p95(values: list[int]) -> int | None:
    """Return the ceil(0.95 * n)-th smallest of the n `values`, None when empty."""
    if len(values) == 0:
        return None
    ordered = sorted(values)
    rank = (P95_PERCENT * len(ordered) + 99) // 100  # ceil(0.95 * n), in integers
    return ordered[rank - 1]


# ---- The replay ------------------------------------------------------------------


def room_edits(entries: Sequence[LogEntry]) -> tuple[RoomEdit, ...]:
    """Return one RoomEdit per edit entry (spec 032 `is_edit`), in seq order.

    Args:
        entries: Entries of one room's log in seq order, as `RoomStore.read_log`
            returns them; a part of the log is fine.

    Returns:
        The edits. The nickname of a letter's author is the one of the latest
        `player_joined` of that player id before the edit, in capitals as the
        server stores it; it is None when no such entry comes before the edit,
        and for a lock or a reveal.
    """
    latest_nicknames: dict[str, str] = {}
    edits: list[RoomEdit] = []
    for entry in entries:
        event = entry.event
        if isinstance(event, PlayerJoined):
            latest_nicknames[event.player.player_id] = event.player.nickname
        if is_edit(entry):
            edits.append(_room_edit(entry, latest_nicknames))
    return tuple(edits)


def _room_edit(entry: LogEntry, latest_nicknames: dict[str, str]) -> RoomEdit:
    """Return the RoomEdit of an edit entry: a letter_changed or a cell_locked.

    Args:
        entry: The edit entry.
        latest_nicknames: The nickname of each player id, from the latest
            `player_joined` of that id before the entry.

    Raises:
        ValueError: the entry is not an edit.
    """
    event = entry.event
    at = datetime.fromtimestamp(entry.at, UTC)
    if isinstance(event, LetterChanged):
        return RoomEdit(
            seq=event.seq,
            at=at,
            kind=_letter_kind(entry.undo, event.letter),
            row=event.row,
            column=event.column,
            letter=event.letter,
            pencil=event.pencil,
            player_id=event.player_id,
            nickname=latest_nicknames.get(event.player_id),
        )
    if isinstance(event, CellLocked):
        return RoomEdit(
            seq=event.seq,
            at=at,
            kind=_lock_kind(event.revealed),
            row=event.row,
            column=event.column,
            letter=event.letter,
            pencil=False,
            player_id=None,
            nickname=None,
        )
    raise ValueError(f"The entry with seq {event.seq} is a {event.type}, not an edit")


def _letter_kind(is_undo: bool, letter: str | None) -> EditKind:
    """Return the kind of a letter_changed: an undo, a letter typed or an erase."""
    if is_undo:
        return "undone"
    if letter is not None:
        return "typed"
    return "erased"


def _lock_kind(revealed: bool) -> EditKind:
    """Return the kind of a cell_locked: a reveal, or a check that locked it."""
    if revealed:
        return "revealed"
    return "locked"
