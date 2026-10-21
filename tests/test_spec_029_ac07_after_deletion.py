"""Tests of spec 029, AC-7: an account's finished grid stays after its room is deleted.

HTTP with a fake clock, on the app of spec 033's "Test harness": Ana's account
holds room R (solved, with Bob) and room S (not solved), and has not asked its
history yet; both rooms expire and the sweep (`expire_rooms`, spec 032) deletes
them. Then `GET /api/account/history` lists R's record, saved by the app's delete
hook, and nothing for S.

Code reused: Ana's account holds an identity in room C (not solved) and has not
asked its history; C expires and the sweep deletes it; a solved FX-01 room with the
same code C, whose members are Bob and Cy only, is registered with `add_room`,
expires, and the sweep deletes it (the hook runs for it); the history lists no
record of code C.

Python, on a registry with a fake clock and a store file: `set_delete_hook` calls
its hook with the room's latest state just before each deletion, by the sweep or by
a lookup; a hook that raises is logged at WARNING or above (this test's reading of
"is logged", as spec 032's failed sweep) and the room is deleted all the same.
`AccountStore.accounts_of_room` names the accounts that hold an identity with a
code, also of an older room that had that code.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import pytest

from nock.grid import Grid
from nock.room import RoomState
from spec017_harness import FakeClock
from spec029_harness import (
    Player,
    account_id_of,
    elapsed_ms_of,
    history_body,
    link_room,
    play_fx01,
    sign_in_from,
    solved_at_of,
)
from spec032_harness import (
    ANA,
    BOB,
    CY,
    LIFE,
    NO_TICK_CONFIG,
    T0,
    TA,
    TB,
    TC,
    grid_from_text,
    registry_on_file,
    utc,
)
from spec033_harness import ANA_EMAIL, ZELIE_EMAIL, account_app

R_CODE = "RRRRRR"
S_CODE = "SSSSSS"
C_CODE = "CCCCCC"
ANA_PLAYER = Player("Ana", ANA, TA)
BOB_PLAYER = Player("Bob", BOB, TB)
CY_PLAYER = Player("Cy", CY, TC)
HOOK_ERROR = "the test's delete hook fails on purpose"


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class RecordingHook:
    """A delete hook that keeps each state it is given, and whether its room was
    still in the store at that moment."""

    def __init__(self, store_has_room: Callable[[str], bool]) -> None:
        self.states: list[RoomState] = []
        self.still_stored: list[bool] = []
        self.store_has_room = store_has_room

    def __call__(self, state: RoomState) -> None:
        self.states.append(state)
        self.still_stored.append(self.store_has_room(state.code))


def raising_hook(state: RoomState) -> None:
    """A delete hook that always raises."""
    raise RuntimeError(HOOK_ERROR)


# ---- The app's hook: R solved, S not ----------------------------------------------


def test_ac7_the_history_lists_the_solved_room_the_sweep_deleted(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    unsolved = play_fx01(
        fx01_grid, S_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0, solved_after=None
    )
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(solved.state)
        app.registry.add_room(unsolved.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        link_room(app.client, session, S_CODE, TA)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [R_CODE, S_CODE]

        records = history_body(app.client, session)

    expected = {
        "code": R_CODE,
        "grid_number": 1,
        "width": 5,
        "height": 5,
        "finished_at": utc(solved_at_of(solved)),
        "elapsed_ms": elapsed_ms_of(solved),
        "teammates": ["BOB"],
    }
    assert records == [expected]


def test_ac7_a_record_saved_before_the_deletion_stays_one_record(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(solved.state)
        session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        before = history_body(app.client, session)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [R_CODE]

        after = history_body(app.client, session)

    assert len(before) == 1
    assert after == before


def test_ac7_a_reused_code_gives_no_record_through_the_delete_hook(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    old_room = play_fx01(fx01_grid, C_CODE, [ANA_PLAYER], start=T0, solved_after=None)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(old_room.state)
        session = sign_in_from(app, ANA_EMAIL, C_CODE, TA)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [C_CODE]
        new_room = play_fx01(
            fx01_grid, C_CODE, [BOB_PLAYER, CY_PLAYER], start=fake_clock.now
        )
        app.registry.add_room(new_room.state)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [C_CODE]

        records = history_body(app.client, session)

    assert records == []


# ---- accounts_of_room -------------------------------------------------------------


def test_ac7_accounts_of_room_names_the_accounts_with_an_identity_of_that_code(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    room_r = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    room_s = play_fx01(fx01_grid, S_CODE, [BOB_PLAYER], start=T0, solved_after=None)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(room_r.state)
        app.registry.add_room(room_s.state)
        ana_session = sign_in_from(app, ANA_EMAIL, R_CODE, TA)
        other_session = sign_in_from(app, ZELIE_EMAIL, S_CODE, TB)
        ana_id = account_id_of(app, ana_session)
        other_id = account_id_of(app, other_session)

        of_r = app.accounts.accounts_of_room(R_CODE)
        of_s = app.accounts.accounts_of_room(S_CODE)
        of_unknown = app.accounts.accounts_of_room("ZZZZZZ")

    assert of_r == [ana_id]
    assert of_s == [other_id]
    assert of_unknown == []


def test_ac7_accounts_of_room_also_names_an_identity_of_an_older_room(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    old_room = play_fx01(fx01_grid, C_CODE, [ANA_PLAYER], start=T0, solved_after=None)
    with account_app(tmp_path, fake_clock) as app:
        app.registry.add_room(old_room.state)
        session = sign_in_from(app, ANA_EMAIL, C_CODE, TA)
        ana_id = account_id_of(app, session)
        fake_clock.advance(LIFE + 1)
        assert app.registry.expire_rooms() == [C_CODE]
        new_room = play_fx01(
            fx01_grid, C_CODE, [BOB_PLAYER, CY_PLAYER], start=fake_clock.now
        )
        app.registry.add_room(new_room.state)

        candidates = app.accounts.accounts_of_room(C_CODE)

    assert candidates == [ana_id]


# ---- RoomRegistry.set_delete_hook -------------------------------------------------


def test_ac7_the_hook_gets_the_rooms_latest_state_before_the_sweep_deletes_it(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    path = tmp_path / "nock.sqlite3"
    with registry_on_file(path, fake_clock, NO_TICK_CONFIG) as (registry, store):
        hook = RecordingHook(store.has_room)
        registry.set_delete_hook(hook)
        registry.add_room(solved.state)
        fake_clock.advance(LIFE + 1)

        deleted = registry.expire_rooms()
        stored_after = store.has_room(R_CODE)

    assert deleted == [R_CODE]
    assert len(hook.states) == 1
    assert hook.states[0].code == R_CODE
    assert hook.states[0].solved is True
    assert hook.states[0].seq == solved.state.seq
    assert hook.still_stored == [True]
    assert stored_after is False


def test_ac7_a_lookup_that_deletes_an_expired_room_calls_the_hook(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    path = tmp_path / "nock.sqlite3"
    with registry_on_file(path, fake_clock, NO_TICK_CONFIG) as (registry, store):
        hook = RecordingHook(store.has_room)
        registry.set_delete_hook(hook)
        registry.add_room(solved.state)
        fake_clock.advance(LIFE + 1)

        looked_up = registry.peek_room(R_CODE)

    assert looked_up is None
    assert len(hook.states) == 1
    assert hook.states[0].code == R_CODE
    assert hook.still_stored == [True]


def test_ac7_a_hook_that_raises_is_logged(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG)
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    path = tmp_path / "nock.sqlite3"
    with registry_on_file(path, fake_clock, NO_TICK_CONFIG) as (registry, _):
        registry.set_delete_hook(raising_hook)
        registry.add_room(solved.state)
        fake_clock.advance(LIFE + 1)
        caplog.clear()

        registry.expire_rooms()

    serious: list[logging.LogRecord] = []
    for record in caplog.records:
        if record.levelno >= logging.WARNING:
            serious.append(record)
    assert len(serious) >= 1, caplog.records


def test_ac7_a_hook_that_raises_does_not_stop_the_deletion(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    solved = play_fx01(fx01_grid, R_CODE, [ANA_PLAYER, BOB_PLAYER], start=T0)
    path = tmp_path / "nock.sqlite3"
    with registry_on_file(path, fake_clock, NO_TICK_CONFIG) as (registry, store):
        registry.set_delete_hook(raising_hook)
        registry.add_room(solved.state)
        fake_clock.advance(LIFE + 1)

        deleted = registry.expire_rooms()
        still_stored = store.has_room(R_CODE)
        looked_up = registry.peek_room(R_CODE)

    assert deleted == [R_CODE]
    assert still_stored is False
    assert looked_up is None
