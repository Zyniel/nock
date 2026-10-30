"""Shared setup of the tests of lobby/lifetime: room lives, the sweep, the variables.

Pytest does not collect this module (its name does not start with `test_`). The
tests are in `tests/test_lifetime_*.py`:

- `test_lifetime_expiry.py`: AC-3 to AC-6 and AC-11, when a room of each kind is
  open and when it is expired; AC-12, a creator room while accounts are off.
- `test_lifetime_variables.py`: AC-7 to AC-10, the five variables
  (`room_config_from_env`, `main()`, `python -m nock`, the app's registry).
- `test_lifetime_sweep.py`: AC-10, the sweeps of a running app and the purge they
  pace.
- `test_lifetime_migration.py`: AC-13, a database below `user_version` 2.

AC-1 and AC-2 are proven by the tests of spec 032 (`tests/test_spec_032_ac01_*`,
`tests/test_spec_032_ac02_*`), which their pointers name.

Times. The fake clock of `conftest` starts at `T0` (`spec032_harness`). A room's
last edit time is set by a hand-made `letter_changed` appended to the store
(`stored_room`), or by a real edit over a socket (`solve_room`), whichever the
criterion needs: a solve time is only made by the step that solves a room, so the
solving criteria play the room over a socket on the app of `host_harness`.

The solve time is read from the stored column `solved_at` of `room_times`, the
name of `RoomState.solved_at` and of the glossary's `solved_at` (`specs/_map.md`).

This module imports only names that exist today; the names the change adds
(`RoomConfig`'s hour fields, `room_config_from_env`) are used inside the tests
that need them, so that each test fails on the name it needs.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import NamedTuple

import pytest

from host_harness import HostApp, open_member
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, GridSolved, LetterChanged
from nock.room import LogEntry, RoomConfig, RoomState, new_room
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec026_harness import FIRST_17, LAST_CELL, SOLUTION
from spec032_harness import T0 as T0
from spec033_harness import wait_for

HOUR = 3_600.0
HALF_SECOND = 0.5
LEA_ACCOUNT = "account-of-lea-0001"
ANA_PLAYER = "p1"
SOLVE_TIME_COLUMN = "solved_at"


class Life(NamedTuple):
    """One room life: its environment variable and its `RoomConfig` field."""

    variable: str
    field: str


CREATOR_SOLVED = Life("NOCK_CREATOR_SOLVED_ROOM_HOURS", "creator_solved_room_hours")
CREATOR = Life("NOCK_CREATOR_ROOM_HOURS", "creator_room_hours")
ANONYMOUS_SOLVED = Life(
    "NOCK_ANONYMOUS_SOLVED_ROOM_HOURS", "anonymous_solved_room_hours"
)
ANONYMOUS = Life("NOCK_ANONYMOUS_ROOM_HOURS", "anonymous_room_hours")
LIVES = (CREATOR_SOLVED, CREATOR, ANONYMOUS_SOLVED, ANONYMOUS)
SWEEP_VARIABLE = "NOCK_EXPIRY_SWEEP_MINUTES"
DEFAULT_LIFE_HOURS = 720
DEFAULT_SWEEP_SECONDS = 3_600.0

# Every variable that `main()` or the app reads at its start: a test that depends on
# the environment clears all of them first.
STARTUP_VARIABLES = (
    "NOCK_HOST",
    "NOCK_PORT",
    "NOCK_DATABASE",
    "NOCK_OPERATOR_TOKEN",
    SWEEP_VARIABLE,
    *(life.variable for life in LIVES),
    "NOCK_ROOMS_PER_ADDRESS_PER_HOUR",
    "NOCK_PUBLIC_URL",
    "NOCK_SMTP_HOST",
    "NOCK_SMTP_PORT",
    "NOCK_SMTP_SECURITY",
    "NOCK_SMTP_USER",
    "NOCK_SMTP_PASSWORD",
    "NOCK_SMTP_FROM",
)

# The rules' thresholds of a room that only the fake clock's moves change.
QUIET_SETTINGS: dict[str, float] = {
    "idle_after_seconds": 1e9,
    "host_handover_seconds": 1e9,
    "silence_timeout_seconds": 1e9,
    "resume_window_seconds": 1e9,
    "max_edits_per_second": 1000,
    "tick_seconds": 0.05,
}


def clear_startup_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    """Delete from the environment every variable the server reads at its start."""
    for variable in STARTUP_VARIABLES:
        monkeypatch.delenv(variable, raising=False)


def config_with_lives(
    *,
    creator_solved: int = DEFAULT_LIFE_HOURS,
    creator: int = DEFAULT_LIFE_HOURS,
    anonymous_solved: int = DEFAULT_LIFE_HOURS,
    anonymous: int = DEFAULT_LIFE_HOURS,
    sweep_seconds: float | None = None,
) -> RoomConfig:
    """A `RoomConfig` with quiet rules, these room lives (hours) and this sweep."""
    settings: dict[str, float] = dict(QUIET_SETTINGS)
    settings[CREATOR_SOLVED.field] = creator_solved
    settings[CREATOR.field] = creator
    settings[ANONYMOUS_SOLVED.field] = anonymous_solved
    settings[ANONYMOUS.field] = anonymous
    if sweep_seconds is not None:
        settings["expiry_sweep_seconds"] = sweep_seconds
    return RoomConfig.model_validate(settings)


# ---- Rooms written by hand --------------------------------------------------------


def letter_entry(seq: int, at: float) -> LogEntry:
    """A `letter_changed` log entry (an edit) at the time `at`."""
    event = LetterChanged(
        seq=seq, row=1, column=0, letter="T", pencil=False, player_id=ANA_PLAYER
    )
    return LogEntry(at=at, event=event)


def stored_room(
    store: RoomStore,
    grid: Grid,
    code: str,
    last_edit_at: float,
    creator: str | None = None,
) -> RoomState:
    """Store an unsolved room created at `T0` whose last edit is at `last_edit_at`.

    Returns:
        The room's first state.
    """
    state = new_room(code, grid, T0, creator_account_id=creator)
    store.create_room(state)
    store.append(code, [letter_entry(1, last_edit_at)])
    return state


def assert_open_then_expired(
    registry: RoomRegistry, clock: FakeClock, code: str, start: float, hours: int
) -> None:
    """Room `code` is open at `start` + `hours`, and expired half a second after.

    The lookups are `room_state` ones: an expired room is deleted by the lookup
    that meets it (`lobby/lifetime.md` rule 6).
    """
    limit = start + hours * HOUR
    clock.now = limit
    assert registry.room_state(code) is not None, "the room is open at its life"
    clock.now = limit + HALF_SECOND
    assert registry.room_state(code) is None, "the room is expired after its life"
    assert registry.store.has_room(code) is False


# ---- Solving a room over a socket --------------------------------------------------


def solve_room(
    app: HostApp,
    code: str,
    letters_at: float,
    solved_at: float,
    session: str | None = None,
) -> None:
    """Play FX-01 in room `code` to its end over one socket, on the app's clock.

    The first 17 letters are written when the clock reads `letters_at`, the last
    one when it reads `solved_at`, which solves the room. Returns once the player
    received `grid_solved`; the socket is closed on the way out.

    Args:
        app: The running app.
        code: A room of FX-01 that nobody has played.
        letters_at: Clock time of the first 17 letters.
        solved_at: Clock time of the solving letter.
        session: The session of the player (the creator, for a creator room), or
            None for an anonymous player.
    """
    with ExitStack() as stack:
        player = open_member(stack, app.client, code, "Lea", session=session)
        app.clock.now = letters_at
        for row, column in FIRST_17:
            player.send(
                EditLetter(row=row, column=column, letter=SOLUTION[row, column])
            )
        player.wait_until(
            lambda: count_letters(player.events()) == len(FIRST_17), "the 17 letters"
        )
        app.clock.now = solved_at
        row, column = LAST_CELL
        player.send(EditLetter(row=row, column=column, letter=SOLUTION[row, column]))
        player.wait_until(
            lambda: any(isinstance(m, GridSolved) for m in player.events()),
            "grid_solved",
        )


def count_letters(messages: Sequence[object]) -> int:
    """How many of the messages are a `letter_changed`."""
    count = 0
    for message in messages:
        if isinstance(message, LetterChanged):
            count += 1
    return count


def wait_until_deleted(store: RoomStore, code: str) -> None:
    """Wait (bounded, real time) until the store no longer holds room `code`."""
    wait_for(lambda: not store.has_room(code), f"room {code} to be deleted")


# ---- The database file ------------------------------------------------------------


def stored_solve_time(database_path: Path, code: str) -> float | None:
    """The solve time that `room_times` holds for the room, None when it has none."""
    connection = sqlite3.connect(database_path)
    try:
        row = connection.execute(
            f"SELECT {SOLVE_TIME_COLUMN} FROM room_times WHERE code = ?", (code,)
        ).fetchone()
    finally:
        connection.close()
    assert row is not None, f"no room_times row for {code}"
    if row[0] is None:
        return None
    return float(row[0])


def select_rows(database_path: Path, query: str) -> list[tuple[object, ...]]:
    """All rows of a query on the database file, as tuples."""
    connection = sqlite3.connect(database_path)
    try:
        rows = connection.execute(query).fetchall()
    finally:
        connection.close()
    return [tuple(row) for row in rows]


def variables_of(monkeypatch: pytest.MonkeyPatch, variables: Mapping[str, str]) -> None:
    """Clear the startup variables, then set `variables`."""
    clear_startup_variables(monkeypatch)
    for name, value in variables.items():
        monkeypatch.setenv(name, value)
