"""Tests of spec 032, AC-1: a room's life runs 30 days from its last edit.

`RoomStore` keeps each room's last edit time, which only edits move (`is_edit`: a
`letter_changed` or a `cell_locked`), and lists the rooms whose last edit time is
older than a given time (`expired_codes`). A registry reads the room life from
`RoomConfig.room_life_seconds`: exactly 30 days after the last edit a room is still
open, and any later it is expired. The shared setup is in `spec032_harness`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

import nock.room
from nock.grid import Grid
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    ChatMessage,
    Check,
    CheckResult,
    ClueRef,
    FlagChanged,
    GridFullWrong,
    GridSolved,
    HelpMode,
    HostChanged,
    LeaveReason,
    LetterChanged,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    RevealBudget,
    RevealResult,
    RoomSettings,
    SettingsChanged,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
)
from nock.room import LogEntry, RoomConfig, new_room
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec032_harness import (
    ANA,
    BOB,
    CODE_A,
    LIFE,
    NO_TICK_CONFIG,
    T0,
    TA,
    grid_from_text,
    registry_on_file,
)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def store_path(tmp_path: Path) -> Path:
    return tmp_path / "nock.sqlite3"


@pytest.fixture
def store(store_path: Path) -> Iterator[RoomStore]:
    room_store = RoomStore(store_path)
    yield room_store
    room_store.close()


# ---- Entries -------------------------------------------------------------------


def ana_view() -> PlayerView:
    return PlayerView(
        player_id=ANA,
        nickname="Ana",
        colour=0,
        state=PlayerState.ACTIVE,
        is_host=True,
        muted=False,
        selection=None,
    )


def joined_entry(seq: int, at: float) -> LogEntry:
    return LogEntry(
        at=at, event=PlayerJoined(seq=seq, player=ana_view()), resume_token=TA
    )


def letter_entry(seq: int, at: float, letter: str | None = "T") -> LogEntry:
    event = LetterChanged(
        seq=seq, row=1, column=0, letter=letter, pencil=False, player_id=ANA
    )
    return LogEntry(at=at, event=event)


def chat_entry(seq: int, at: float) -> LogEntry:
    return LogEntry(at=at, event=ChatMessage(seq=seq, player_id=ANA, text="salut"))


def check_entry(seq: int, at: float) -> LogEntry:
    event = CheckResult(
        seq=seq,
        player_id=ANA,
        target=CellTarget(row=1, column=0),
        correct=(CellRef(row=1, column=0),),
        wrong=(),
    )
    return LogEntry(at=at, event=event)


def locked_entry(seq: int, at: float, revealed: bool = False) -> LogEntry:
    event = CellLocked(seq=seq, row=1, column=0, letter="T", revealed=revealed)
    return LogEntry(at=at, event=event)


def presence_entry(seq: int, at: float) -> LogEntry:
    event = PlayerStateChanged(seq=seq, player_id=ANA, state=PlayerState.DISCONNECTED)
    return LogEntry(at=at, event=event)


def settings_entry(seq: int, at: float) -> LogEntry:
    budget = RevealBudget(letters=5, words=1)
    settings = RoomSettings(help_mode=HelpMode.FREE, reveal_budget=budget, locked=True)
    event = SettingsChanged(
        seq=seq, player_id=ANA, settings=settings, reveal_budget=budget
    )
    return LogEntry(at=at, event=event)


def solved_entry(seq: int, at: float) -> LogEntry:
    return LogEntry(at=at, event=GridSolved(seq=seq, elapsed_ms=754_000))


def the_five_entries() -> list[LogEntry]:
    """AC-1's entries, appended one at a time after the room was created at t0."""
    return [
        joined_entry(1, T0 + 5),
        letter_entry(2, T0 + 10),
        chat_entry(3, T0 + 20),
        check_entry(4, T0 + 25),
        locked_entry(5, T0 + 30),
    ]


def room_after_the_five_entries(store: RoomStore, grid: Grid) -> None:
    """Create the FX-01 room at t0 and append AC-1's entries: last edit t0 + 30."""
    store.create_room(new_room(CODE_A, grid, T0))
    store.append(CODE_A, the_five_entries())


# ---- The last edit time --------------------------------------------------------


def test_ac1_a_new_room_starts_its_life_when_it_is_created(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0))

    assert store.last_edit_at(CODE_A) == T0


def test_ac1_only_the_edits_appended_move_the_last_edit_time(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0))
    readings: list[float | None] = []

    for entry in the_five_entries():
        store.append(CODE_A, [entry])
        readings.append(store.last_edit_at(CODE_A))

    assert readings == [T0, T0 + 10, T0 + 10, T0 + 10, T0 + 30]


def test_ac1_create_room_can_start_the_life_at_a_given_time(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0), last_edit_at=T0 + 99)

    assert store.last_edit_at(CODE_A) == T0 + 99


def test_ac1_an_unknown_room_has_no_last_edit_time(store: RoomStore) -> None:
    assert store.last_edit_at(CODE_A) is None


def test_ac1_one_append_takes_the_latest_of_its_edits(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0))

    store.append(CODE_A, [letter_entry(1, T0 + 40), letter_entry(2, T0 + 35, "A")])

    assert store.last_edit_at(CODE_A) == T0 + 40


def test_ac1_an_older_edit_never_moves_the_last_edit_time_back(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0))
    store.append(CODE_A, [letter_entry(1, T0 + 50)])

    store.append(CODE_A, [letter_entry(2, T0 + 20, "A")])

    assert store.last_edit_at(CODE_A) == T0 + 50


def test_ac1_an_edit_older_than_a_given_start_changes_nothing(
    store: RoomStore, fx01_grid: Grid
) -> None:
    store.create_room(new_room(CODE_A, fx01_grid, T0), last_edit_at=T0 + 99)

    store.append(CODE_A, [letter_entry(1, T0 + 10)])

    assert store.last_edit_at(CODE_A) == T0 + 99


# ---- What is an edit -----------------------------------------------------------


@pytest.mark.parametrize(
    "entry",
    [
        letter_entry(2, T0 + 10, "T"),
        letter_entry(2, T0 + 10, None),
        locked_entry(2, T0 + 10, revealed=False),
        locked_entry(2, T0 + 10, revealed=True),
    ],
    ids=["letter_written", "letter_erased", "locked_by_a_check", "locked_by_a_reveal"],
)
def test_ac1_a_change_of_a_cell_is_an_edit(entry: LogEntry) -> None:
    assert nock.room.is_edit(entry) is True


@pytest.mark.parametrize(
    "entry",
    [
        joined_entry(2, T0 + 10),
        presence_entry(2, T0 + 10),
        chat_entry(2, T0 + 10),
        check_entry(2, T0 + 10),
        settings_entry(2, T0 + 10),
        solved_entry(2, T0 + 10),
    ],
    ids=[
        "player_joined",
        "player_state_changed",
        "chat_message",
        "check_result",
        "settings_changed",
        "grid_solved",
    ],
)
def test_ac1_the_events_that_change_no_cell_are_not_edits(entry: LogEntry) -> None:
    assert nock.room.is_edit(entry) is False


def every_other_event() -> list[LogEntry]:
    """One entry of each logged event that the criterion does not name."""
    check = Check(target=CellTarget(row=1, column=0))
    return [
        LogEntry(
            at=T0,
            event=FlagChanged(
                seq=2, player_id=ANA, clue=ClueRef(row=0, column=3, clue_index=0)
            ),
        ),
        LogEntry(
            at=T0,
            event=VoteOpened(
                seq=2,
                vote_id=1,
                player_id=ANA,
                request=check,
                timeout_seconds=20,
                eligible_voters=2,
            ),
        ),
        LogEntry(
            at=T0,
            event=VoteClosed(
                seq=2,
                vote_id=1,
                outcome=VoteOutcome.PASSED,
                yes_votes=2,
                eligible_voters=2,
            ),
        ),
        LogEntry(
            at=T0,
            event=RevealResult(
                seq=2,
                player_id=ANA,
                target=CellTarget(row=4, column=4),
                reveal_budget=RevealBudget(letters=4, words=1),
            ),
        ),
        LogEntry(at=T0, event=HostChanged(seq=2, player_id=BOB)),
        LogEntry(at=T0, event=PlayerMuted(seq=2, player_id=BOB, muted=True)),
        LogEntry(
            at=T0,
            event=PlayerLeft(seq=2, player_id=BOB, reason=LeaveReason.TIMED_OUT),
        ),
        LogEntry(at=T0, event=GridFullWrong(seq=2)),
    ]


@pytest.mark.parametrize(
    "entry",
    every_other_event(),
    ids=[
        "flag_changed",
        "vote_opened",
        "vote_closed",
        "reveal_result",
        "host_changed",
        "player_muted",
        "player_left",
        "grid_full_wrong",
    ],
)
def test_ac1_flags_votes_reveal_results_and_departures_are_not_edits(
    entry: LogEntry,
) -> None:
    assert nock.room.is_edit(entry) is False


# ---- Expired codes -------------------------------------------------------------


def test_ac1_expired_codes_holds_a_room_only_after_its_last_edit_time(
    store: RoomStore, fx01_grid: Grid
) -> None:
    room_after_the_five_entries(store, fx01_grid)

    assert store.expired_codes(T0 + 30) == []
    assert store.expired_codes(T0 + 30.5) == [CODE_A]


def test_ac1_expired_codes_are_in_code_point_order(
    store: RoomStore, fx01_grid: Grid
) -> None:
    for code in ["BBBBBB", "AAAAAA", "AAAAA9"]:
        store.create_room(new_room(code, fx01_grid, T0))
    store.create_room(new_room("CCCCCC", fx01_grid, T0 + 500))

    assert store.expired_codes(T0 + 100) == ["AAAAA9", "AAAAAA", "BBBBBB"]


# ---- The room life on a registry -----------------------------------------------


def test_ac1_the_room_life_is_30_days_by_default() -> None:
    assert RoomConfig().room_life_seconds == 2_592_000.0


@pytest.mark.parametrize("seconds", [0.0, -1.0])
def test_ac1_the_room_life_must_be_positive(seconds: float) -> None:
    # The message names the field and its bound, not an unknown field.
    with pytest.raises(ValidationError, match=r"room_life_seconds\s+.*greater than 0"):
        RoomConfig(room_life_seconds=seconds)


def test_ac1_a_room_is_still_open_exactly_30_days_after_its_last_edit(
    store_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    writer = RoomStore(store_path)
    try:
        room_after_the_five_entries(writer, fx01_grid)
    finally:
        writer.close()
    fake_clock.now = T0 + 30 + LIFE

    with registry_on_file(store_path, fake_clock, NO_TICK_CONFIG) as (registry, _):
        expired = registry.expire_rooms()

    assert expired == []


def test_ac1_a_room_is_expired_any_later_than_30_days_after_its_last_edit(
    store_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    writer = RoomStore(store_path)
    try:
        room_after_the_five_entries(writer, fx01_grid)
    finally:
        writer.close()
    fake_clock.now = T0 + 30.5 + LIFE

    with registry_on_file(store_path, fake_clock, NO_TICK_CONFIG) as (registry, _):
        expired = registry.expire_rooms()

    assert expired == [CODE_A]


def test_ac1_a_room_never_edited_expires_30_days_after_its_creation(
    store_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    writer = RoomStore(store_path)
    try:
        writer.create_room(new_room(CODE_A, fx01_grid, T0))
        writer.append(CODE_A, [joined_entry(1, T0 + 5), chat_entry(2, T0 + 20)])
    finally:
        writer.close()

    with registry_on_file(store_path, fake_clock, NO_TICK_CONFIG) as (registry, _):
        fake_clock.now = T0 + LIFE
        at_30_days = registry.expire_rooms()
        fake_clock.now = T0 + LIFE + 0.5
        after_30_days = registry.expire_rooms()

    assert at_30_days == []
    assert after_30_days == [CODE_A]


def test_ac1_the_room_life_follows_the_configuration(
    fx01_grid: Grid, fake_clock: FakeClock, store_path: Path
) -> None:
    config = RoomConfig(
        idle_after_seconds=1e9,
        host_handover_seconds=1e9,
        silence_timeout_seconds=1e9,
        resume_window_seconds=1e9,
        room_life_seconds=100.0,
    )
    with registry_on_file(store_path, fake_clock, config) as (registry, _):
        registry.add_room(new_room(CODE_A, fx01_grid, T0))
        fake_clock.now = T0 + 100
        at_the_limit = registry.expire_rooms()
        fake_clock.now = T0 + 100.5
        after_the_limit = registry.expire_rooms()

    assert at_the_limit == []
    assert after_the_limit == [CODE_A]
