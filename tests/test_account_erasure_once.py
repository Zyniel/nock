"""Tests of account/account, AC-30: an attempt that has nothing to do does nothing.

No engine is held and nothing here measures time, so the file runs in the parallel
pass. Three cases of rule 26 that `test_account_erasure_overlap.py` (a real overlap,
in the serial pass) cannot pin down, each driven by a name of the code instead of
by time:

- an attempt that finds the erasure done, after it was listed as pending: the app
  of spec 033's "Test harness" sweeps every 0.1 s, Ana deletes her account with no
  room (the route's attempt ends it, one e-mail), and then `pending_erasures` of its
  account store is made to give the sweep the list read before that attempt ended,
  once. The sweep claims the erasure just after that attempt, as a sweep that
  listed it while the attempt ran would; it sends nothing and counts nothing;
- `RoomRegistry.delete_creator_rooms` reports only a room that its deletion
  removed: a room deleted between the listing of the account's rooms and its own
  deletion is not reported;
- `AccountStore.finish_erasure` leaves a done erasure as it is.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from account_harness import (
    BOB_PLAYER,
    FAST_SWEEP_CONFIG,
    U_CODE,
    ErasureRow,
    erasure_rows,
    sign_in_ana_without_room,
)
from nock.accounts import AccountStore, PendingErasure
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.store import RoomStore
from spec017_harness import FakeClock
from spec029_harness import play_fx01
from spec032_harness import NO_TICK_CONFIG, grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    ANA_EMAIL,
    account_app,
    wait_for,
    with_session,
)

GONE_CODE = "GGGGGG"  # a creator room that is deleted after the listing
FIRST_DONE_AT = 10.0
FIRST_NOTIFIED_AT = 5.0
SECOND_DONE_AT = 20.0
SECOND_NOTIFIED_AT = 15.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class StaleListOnce:
    """`pending_erasures` that gives a list read earlier once, then the real one.

    Set on an `AccountStore` instance, it makes the first caller see the erasure
    that its attempt has meanwhile ended as still pending, as a sweep sees it when
    it lists the erasures while the route's attempt runs. The calls are counted.
    """

    def __init__(self, store: AccountStore, stale: PendingErasure) -> None:
        self._real = store.pending_erasures
        self._stale = stale
        self.calls = 0

    def __call__(self) -> list[PendingErasure]:
        self.calls += 1
        if self.calls == 1:
            return [self._stale]
        return self._real()


class ListingThenDeleting(RoomStore):
    """A `RoomStore` that deletes one room just after it lists a creator's rooms."""

    def __init__(self, path: Path, vanishing_code: str) -> None:
        super().__init__(path)
        self._vanishing_code = vanishing_code

    def codes_created_by(self, account_id: str) -> list[str]:
        codes = super().codes_created_by(account_id)
        self.delete_room(self._vanishing_code)
        return codes


def test_ac30_a_sweep_that_claims_a_done_erasure_after_its_list_does_nothing(
    tmp_path: Path, fake_clock: FakeClock
) -> None:
    with account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG) as app:
        ana = sign_in_ana_without_room(app)
        requested_at = fake_clock()
        sent_before = len(app.mailer.messages)
        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(ana.session))
        rows_done = erasure_rows(app.database_path)
        sent_done = len(app.mailer.messages) - sent_before
        stale = PendingErasure(
            erasure_id=1,
            account_id=ana.account_id,
            email=ANA_EMAIL,
            requested_at=requested_at,
            attempts=1,
            players=(),
        )
        stale_list = StaleListOnce(app.accounts, stale)
        app.accounts.pending_erasures = stale_list  # the sweep's next listing

        wait_for(lambda: stale_list.calls >= 2, "the sweep that got the old list")
    # The app has stopped: a sweep under way is over too.
    rows_after = erasure_rows(app.database_path)

    assert deletion.status_code == 204
    assert sent_done == 1
    assert rows_done == [
        ErasureRow(None, None, requested_at, requested_at, requested_at, 1, 0, 0)
    ]
    assert len(app.mailer.messages) - sent_before == 1
    assert rows_after == rows_done


def test_ac30_a_creator_room_deleted_meanwhile_is_not_reported_as_deleted(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    store = ListingThenDeleting(tmp_path / "nock.sqlite3", GONE_CODE)
    registry = RoomRegistry(clock=fake_clock, store=store, config=NO_TICK_CONFIG)
    reported = 0

    def on_deleted() -> None:
        nonlocal reported
        reported += 1

    try:
        for code in (U_CODE, GONE_CODE):
            play = play_fx01(
                fx01_grid, code, [BOB_PLAYER], start=fake_clock(), solved_after=None
            )
            state = play.state.model_copy(update={"creator_account_id": "ana-id"})
            registry.add_room(state)

        registry.delete_creator_rooms("ana-id", on_deleted)
        u_exists = store.has_room(U_CODE)
    finally:
        registry.close()
        store.close()

    assert reported == 1
    assert u_exists is False


def test_ac30_finishing_a_done_erasure_again_keeps_its_first_times(
    tmp_path: Path,
) -> None:
    path = tmp_path / "nock.sqlite3"
    accounts = AccountStore(path)
    try:
        ana = accounts.sign_in(ANA_EMAIL, 0.0)
        erasure = accounts.delete_account(ana.account_id, 0.0)
        assert erasure is not None
        accounts.finish_erasure(erasure.erasure_id, FIRST_DONE_AT, FIRST_NOTIFIED_AT)

        accounts.finish_erasure(erasure.erasure_id, SECOND_DONE_AT, SECOND_NOTIFIED_AT)
        rows = erasure_rows(path)
    finally:
        accounts.close()

    assert rows == [
        ErasureRow(None, None, 0.0, FIRST_DONE_AT, FIRST_NOTIFIED_AT, 0, 0, 0)
    ]
