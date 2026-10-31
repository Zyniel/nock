"""Tests of account/account, AC-27: a history record never brings an erased name back.

HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one file,
a fake clock). Two plays:

- Records saved while the erasure is pending. R is a solved FX-01 room that Bob, Zoé
  and Cy played, in that order, kept in the store; each of them signs in from R.
  S is a live room of Zoé's (a socket of hers stays open), linked to her account.
  The test reads R's state, which still names her `ZOÉ`, then holds S's engine for
  real: the app's room store is a `HoldingStore` (`account_harness`) whose
  `erase_player` of S's code sleeps for 5.6 s, inside the step of S's task, then
  raises, at every call until it is released. Zoé deletes her account: the route's
  attempt erases R's player and gives up on S after its 5 s, so R's player is `--`
  and the erasure is pending. Bob's record of R is then saved from the state read
  before (`AccountStore.save_history`, as the history route or the delete hook
  does with a state it read earlier) and names her `--`. The app sweeps every
  0.1 s (`FAST_SWEEP_CONFIG`); its next attempt is held up by S the same way. Once
  a third attempt has begun (the app runs one at a time, so the second is over),
  Cy's record is saved from the same state and names her `--` too. The test then
  releases S, and the erasure ends before the app stops.
- The delete hook of a room an attempt deletes: T is solved by Bob and Zoé, has
  expired and is not swept; both signed in from it. Zoé deletes her account and the
  attempt deletes T (rule 26, step 1), whose delete hook saves Bob's record from the
  state that still names her. His history then lists T with `["--"]`.

The first play holds an engine for more than 5 s, twice, and waits for the sweeps of
real time: this file runs in the serial pass (`SERIAL_TEST_FILES` of
`scripts/gate_browsers.py`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from account_harness import (
    BOB_EMAIL,
    FAST_SWEEP_CONFIG,
    TZ,
    ZOE,
    ZOE_EMAIL,
    HoldingStore,
    nicknames_of,
    zoe_in_new_live_room,
)
from nock.accounts import AccountStore
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import (
    Player,
    account_id_of,
    history_body,
    link_room,
    play_fx01,
    sign_in_from,
)
from spec032_harness import BOB, CY, LIFE, TB, TC, grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    account_app,
    state_of,
    wait_for,
    with_session,
)

R_CODE = "RRRRRR"
T_CODE = "TTTTTT"
CY_EMAIL = "cy.probe@example.org"
HOLD_SECONDS = 5.6  # more than the 5 s that the erasure waits for an engine
ATTEMPTS_AFTER_THE_SECOND = 3


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def teammates_of(accounts: AccountStore, account_id: str) -> list[tuple[str, ...]]:
    """The team-mates of each history record of the account, newest first."""
    return [record.teammates for record in accounts.history(account_id)]


def is_second_attempt_over(accounts: AccountStore) -> bool:
    """Whether a third attempt of the erasure has begun, or the erasure is done."""
    pending = accounts.pending_erasures()
    if len(pending) == 0:
        return True
    return pending[0].attempts >= ATTEMPTS_AFTER_THE_SECOND


def test_ac27_records_saved_from_a_state_read_before_her_deletion_name_her_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    store = HoldingStore(tmp_path / "nock.sqlite3")
    with (
        account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG, store=store) as app,
        contextlib.ExitStack() as stack,
    ):
        played = play_fx01(
            fx01_grid,
            R_CODE,
            [Player("Bob", BOB, TB), Player("Zoé", ZOE, TZ), Player("Cy", CY, TC)],
            start=app.clock(),
        )
        app.registry.add_room(played.state)
        bob_id = account_id_of(app, sign_in_from(app, BOB_EMAIL, R_CODE, TB))
        cy_id = account_id_of(app, sign_in_from(app, CY_EMAIL, R_CODE, TC))
        zoe_session = sign_in_from(app, ZOE_EMAIL, R_CODE, TZ)
        zoe_in_s = zoe_in_new_live_room(app, stack, fx01_grid)
        link_room(app.client, zoe_session, zoe_in_s.code, zoe_in_s.resume_token)
        read_before = state_of(app.registry, R_CODE)
        store.hold(zoe_in_s.code, HOLD_SECONDS, fail=True, once=False)
        try:
            deletion = app.client.delete(
                ACCOUNT_PATH, headers=with_session(zoe_session)
            )
            app.accounts.save_history(bob_id, read_before)
            bob_teammates = teammates_of(app.accounts, bob_id)
            pending_after_first = len(app.accounts.pending_erasures())
            r_nicknames = nicknames_of(state_of(app.registry, R_CODE), ZOE)

            wait_for(
                lambda: is_second_attempt_over(app.accounts),
                "the second attempt over",
            )
            pending_after_second = len(app.accounts.pending_erasures())
            app.accounts.save_history(cy_id, read_before)
            cy_teammates = teammates_of(app.accounts, cy_id)
        finally:
            store.release()
        wait_for(lambda: app.accounts.pending_erasures() == [], "the erasure done")

    assert deletion.status_code == 204
    assert r_nicknames == [FORMER_NICKNAME]
    assert pending_after_first == 1
    assert bob_teammates == [(FORMER_NICKNAME, "CY")]
    assert pending_after_second == 1
    assert cy_teammates == [("BOB", FORMER_NICKNAME)]


def test_ac27_the_record_saved_by_the_delete_hook_of_her_deleted_room_names_her_dashes(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        played = play_fx01(
            fx01_grid,
            T_CODE,
            [Player("Bob", BOB, TB), Player("Zoé", ZOE, TZ)],
            start=app.clock(),
        )
        app.registry.add_room(played.state)
        bob_session = sign_in_from(app, BOB_EMAIL, T_CODE, TB)
        zoe_session = sign_in_from(app, ZOE_EMAIL, T_CODE, TZ)
        fake_clock.advance(LIFE + 1)

        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(zoe_session))
        records = history_body(app.client, bob_session)

    assert deletion.status_code == 204
    assert [(record["code"], record["teammates"]) for record in records] == [
        (T_CODE, [FORMER_NICKNAME])
    ]
