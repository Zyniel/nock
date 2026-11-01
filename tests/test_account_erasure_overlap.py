"""Tests of account/account, AC-30: one attempt of an erasure at a time.

HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one file,
a fake clock, a recording mailer), which sweeps every 0.1 s of real time
(`FAST_SWEEP_CONFIG`). Zoé plays R, which is live (a socket of hers stays open),
signs in from it, and created U (`creator_room`), a room only in the store where
Bob plays.

R's engine is held for real: the app's room store is a `HoldingStore`
(`account_harness`) whose `erase_player` of R's code sleeps for 1 s inside the step
of R's task, then erases the player, once. The engine runs on a thread of its own and
the sweeps on the app's loop, so the sweeps go on during that second: several start
during the route's attempt and find her erasure pending. Once the erasure is done the
app is stopped, which waits for a sweep under way; then the e-mails sent and the row
of `account_erasures` are read.

This file holds an engine for 1 s and counts on sweeps of real time starting meanwhile:
it runs in the serial pass (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from account_harness import (
    FAST_SWEEP_CONFIG,
    U_CODE,
    ZOE_EMAIL,
    Ana,
    ErasureRow,
    HoldingStore,
    creator_room,
    erasure_rows,
    nicknames_of,
    zoe_in_new_live_room,
)
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import account_id_of, sign_in_from
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    account_app,
    state_of,
    wait_for,
    with_session,
)

HOLD_SECONDS = 1.0  # ten sweeps of FAST_SWEEP_CONFIG, inside the 5 s of the wait


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def test_ac30_a_sweep_during_the_routes_attempt_leaves_the_erasure_to_it(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    store = HoldingStore(tmp_path / "nock.sqlite3")
    requested_at = fake_clock()
    with (
        account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG, store=store) as app,
        contextlib.ExitStack() as stack,
    ):
        zoe_in_r = zoe_in_new_live_room(app, stack, fx01_grid)
        session = sign_in_from(app, ZOE_EMAIL, zoe_in_r.code, zoe_in_r.resume_token)
        account_id = account_id_of(app, session)
        creator_room(app, Ana(session, account_id), fx01_grid, U_CODE, 4, solved=False)
        assert app.registry.live_codes() >= {zoe_in_r.code}
        sent_before = len(app.mailer.messages)
        store.hold(zoe_in_r.code, HOLD_SECONDS, fail=False, once=True)

        deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(session))
        wait_for(lambda: app.accounts.pending_erasures() == [], "the erasure done")
        r_state = state_of(app.registry, zoe_in_r.code)
        u_exists = app.store.has_room(U_CODE)
    # The app has stopped: a sweep's attempt under way is over too.
    sent = list(app.mailer.messages[sent_before:])
    rows = erasure_rows(app.database_path)

    assert deletion.status_code == 204
    assert store.hold_over.is_set()
    assert nicknames_of(r_state, zoe_in_r.player_id) == [FORMER_NICKNAME]
    assert u_exists is False
    assert [message["To"] for message in sent] == [ZOE_EMAIL]
    assert rows == [
        ErasureRow(None, None, requested_at, requested_at, requested_at, 1, 1, 1)
    ]
