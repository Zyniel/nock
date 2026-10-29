"""Tests of lobby/lifetime, AC-3 to AC-6, AC-11 and AC-12: which life a room has.

A room is open at exactly its room life and expired half a second after, counted
from its starting point: its last edit time while unsolved, its solve time once
solved (`lobby/lifetime.md` rules 4 and 5).

- AC-3 and AC-5 write an unsolved room to a store file (one hand-made edit at
  `t`) and read it with a registry on the fake clock: AC-3 by lookups, AC-5 by
  sweeps (`expire_rooms`), which rule 5 says decide the same.
- AC-4, AC-6 and AC-11 solve a room for real: the app of `host_harness` (a fake
  clock, a file database), a socket, 17 letters, then the solving letter at the
  chosen time. A solve time is made by the step that solves the room, so no
  test writes one by hand here. AC-4 reads the stored solve time from the
  database file (the column `solved_at` of `room_times`) and checks the room
  after a restart too.
- AC-12 starts the app on the same database file with accounts on, then off
  (`host_app(accounts_on=...)`), at chosen clock times.

Reading taken where the spec leaves room: "last edited at `t`" of a room that
nobody edits is its creation time (`lobby/lifetime.md` rule 1), so the creator
room of AC-12 is only created at `t`.

The shared setup is in `lifetime_harness`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from host_harness import (
    create_room_as,
    host_app,
    lea_creates_a_room,
    stored_creator,
)
from lifetime_harness import (
    HALF_SECOND,
    HOUR,
    LEA_ACCOUNT,
    T0,
    assert_open_then_expired,
    config_with_lives,
    solve_room,
    stored_room,
    stored_solve_time,
    wait_until_deleted,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import CODE_A, grid_from_text, registry_on_file


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


# ---- AC-3: an unsolved creator room, from its last edit time -----------------------


@pytest.mark.parametrize("other_hours", [24, 8760])
def test_ac3_an_unsolved_creator_room_lives_its_creator_room_hours(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock, other_hours: int
) -> None:
    last_edit_at = T0 + 100
    config = config_with_lives(
        creator_solved=other_hours,
        creator=48,
        anonymous_solved=other_hours,
        anonymous=other_hours,
    )

    with registry_on_file(tmp_path / "rooms.sqlite3", fake_clock, config) as (
        registry,
        store,
    ):
        stored_room(store, fx01_grid, CODE_A, last_edit_at, creator=LEA_ACCOUNT)
        fake_clock.now = last_edit_at + 48 * HOUR
        served = registry.room_state(CODE_A)
        fake_clock.now = last_edit_at + 48 * HOUR + HALF_SECOND
        deleted = registry.room_state(CODE_A)
        still_stored = store.has_room(CODE_A)

    assert served is not None
    assert served.creator_account_id == LEA_ACCOUNT
    assert deleted is None
    assert still_stored is False


# ---- AC-4: a solved creator room, from its solve time ------------------------------

LETTERS_AT = T0 + HOUR
SOLVED_AT = T0 + 10 * HOUR


def test_ac4_the_solving_letter_stores_the_solve_time_equal_to_the_last_edit(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(creator_solved=24, creator=8760)

    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as app:
        room = lea_creates_a_room(app)
        solve_room(app, room.code, LETTERS_AT, SOLVED_AT, room.session)
        solve_time = stored_solve_time(app.database_path, room.code)
        last_edit_at = app.store.last_edit_at(room.code)

        assert solve_time == SOLVED_AT
        assert last_edit_at == SOLVED_AT
        assert_open_then_expired(app.registry, fake_clock, room.code, SOLVED_AT, 24)


def test_ac4_the_solve_time_and_the_life_it_starts_survive_a_restart(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(creator_solved=24, creator=8760)
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as app:
        room = lea_creates_a_room(app)
        solve_room(app, room.code, LETTERS_AT, SOLVED_AT, room.session)

    fake_clock.now = SOLVED_AT + 24 * HOUR
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, config=config
    ) as restarted:
        solve_time = stored_solve_time(restarted.database_path, room.code)
        assert solve_time == SOLVED_AT
        assert_open_then_expired(
            restarted.registry, fake_clock, room.code, SOLVED_AT, 24
        )


# ---- AC-5: an unsolved anonymous room, from its last edit time ----------------------


def test_ac5_an_unsolved_anonymous_room_lives_its_anonymous_room_hours(
    tmp_path: Path, fx01_grid: Grid, fake_clock: FakeClock
) -> None:
    last_edit_at = T0 + 100
    config = config_with_lives(creator_solved=24, creator=24, anonymous=96)

    with registry_on_file(tmp_path / "rooms.sqlite3", fake_clock, config) as (
        registry,
        store,
    ):
        stored_room(store, fx01_grid, CODE_A, last_edit_at)
        fake_clock.now = last_edit_at + 96 * HOUR
        swept_at_the_limit = registry.expire_rooms()
        open_at_the_limit = store.has_room(CODE_A)
        fake_clock.now = last_edit_at + 96 * HOUR + HALF_SECOND
        swept_after = registry.expire_rooms()
        stored_after = store.has_room(CODE_A)

    assert swept_at_the_limit == []
    assert open_at_the_limit is True
    assert swept_after == [CODE_A]
    assert stored_after is False


# ---- AC-6: a solved anonymous room, from its solve time -----------------------------


def test_ac6_a_solved_anonymous_room_lives_its_solved_hours_from_its_solve_time(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(anonymous_solved=72, anonymous=24)

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False, config=config
    ) as app:
        code = create_room_as(app, None)
        solve_room(app, code, LETTERS_AT, SOLVED_AT)

        assert_open_then_expired(app.registry, fake_clock, code, SOLVED_AT, 72)


# ---- AC-11: the solved life replaces the unsolved one -------------------------------


def test_ac11_a_room_solved_by_a_letter_takes_its_solved_life_from_that_letter(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    last_edit_at = T0 + HOUR
    solved_at = last_edit_at + 10 * HOUR
    config = config_with_lives(anonymous=48, anonymous_solved=24)

    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False, config=config
    ) as app:
        code = create_room_as(app, None)
        solve_room(app, code, last_edit_at, solved_at)

        # t + 34 h: open; half a second later: expired. The unsolved life, 48 h
        # from the solving letter (t + 58 h), does not apply to a solved room.
        assert_open_then_expired(app.registry, fake_clock, code, solved_at, 24)


# ---- AC-12: a creator room while accounts are off -----------------------------------


def test_ac12_with_accounts_off_a_creator_room_takes_the_anonymous_life(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(creator=96, anonymous=48)
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as on:
        room = lea_creates_a_room(on)

    fake_clock.now = T0 + 48 * HOUR
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False, config=config
    ) as off:
        found = off.registry.room_state(room.code)
        creator_in_the_store = stored_creator(off.database_path, room.code)
        fake_clock.now = T0 + 48 * HOUR + HALF_SECOND
        found_later = off.registry.room_state(room.code)
        still_stored = off.store.has_room(room.code)

    assert found is not None
    assert found.creator_account_id is None
    assert creator_in_the_store == room.account_id
    assert found_later is None
    assert still_stored is False


def test_ac12_with_accounts_on_the_creator_life_holds_until_accounts_go_off(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    config = config_with_lives(creator=96, anonymous=48)
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as on:
        room = lea_creates_a_room(on)

    fake_clock.now = T0 + 60 * HOUR
    with host_app(tmp_path, fake_clock, catalogue, monkeypatch, config=config) as on:
        found = on.registry.room_state(room.code)
    with host_app(
        tmp_path, fake_clock, catalogue, monkeypatch, accounts_on=False, config=config
    ) as off:
        # No lookup: only the sweep the app runs when it starts can delete it.
        wait_until_deleted(off.store, room.code)

    assert found is not None
    assert found.creator_account_id == room.account_id
