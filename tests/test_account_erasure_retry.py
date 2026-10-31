"""Tests of account/account, AC-25: a held engine leaves the erasure pending, and the
next attempt finishes it.

This file measures real time (the answer within 7 s while an engine is held for more
than the 5 s that the erasure waits for it), so it runs in the serial pass
(`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

Zoé plays R and S, both live (a socket of hers stays open to each), signs in, and
created U. The engine's loop is held for real: the store of the app is a
`HoldingStore` (`account_harness`) whose `erase_player` of S's code sleeps for 5.6 s,
inside the step of S's task, and then raises, once. It is armed just before
`DELETE /api/account`. The two rooms share one engine loop, so whichever of R and S
the attempt takes first, the other waits behind the hold at most until it ends, well
inside the 5 s of its own wait; the answer comes in about 5.6 s at the latest. The
step fails after the hold, so that S's stored rows still hold `ZOÉ` when the answer
comes, whichever room came first. While the erasure is pending it holds both her
players, R's marked erased and S's not, read from `pending_erasures` and as the two
rows of `account_erasure_players`.

After the answer, the test waits for the hold to end, stops the app (its first
attempt is over: the erasure is pending), and starts a second app on the same file.
The first sweep of that app, the "app started on that database" of the criterion, is
the next attempt; it needs no held engine. The periodic sweep of an app that stays up
is in `test_account_erasure.py`. A third app, which sweeps every 0.1 s, shows that
a later sweep sends nothing.
"""

from __future__ import annotations

import contextlib
import logging
import time
from pathlib import Path

import pytest

from account_harness import (
    DELETED_SUBJECT,
    FAST_SWEEP_CONFIG,
    U_CODE,
    ZOE_EMAIL,
    ZOE_STORED,
    ErasureRow,
    HoldingStore,
    erasure_rows,
    listed_players,
    nicknames_of,
    zoe_in_rooms,
)
from nock.accounts import ErasedPlayer
from nock.grid import Grid
from operations_harness import LOGGER_PREFIX
from spec017_harness import FakeClock
from spec032_harness import grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    FORMER_NICKNAME,
    SIGNED_OUT,
    account_app,
    database_bytes,
    state_of,
    strings_in,
    wait_for,
    with_session,
)

HOLD_SECONDS = 5.6  # more than the 5 s that the erasure waits for an engine
ANSWER_BOUND_SECONDS = 7.0
LATER_SWEEPS_SECONDS = 1.0  # ten sweeps of FAST_SWEEP_CONFIG
ONE_DAY = 86_400.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def test_ac25_a_held_engine_leaves_the_erasure_pending_and_the_next_attempt_ends_it(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER_PREFIX)
    store = HoldingStore(tmp_path / "nock.sqlite3")
    requested_at = fake_clock()
    with (
        account_app(tmp_path, fake_clock, store=store) as first,
        contextlib.ExitStack() as stack,
    ):
        rooms = zoe_in_rooms(first, stack, fx01_grid, s_live=True)
        assert first.registry.live_codes() >= {rooms.r_code, rooms.s_code}
        sent_before = len(first.mailer.messages)
        store.hold(rooms.s_code, HOLD_SECONDS, fail=True, once=True)
        caplog.clear()

        started = time.monotonic()
        deletion = first.client.delete(
            ACCOUNT_PATH, headers=with_session(rooms.session)
        )
        elapsed = time.monotonic() - started

        status = first.client.get(ACCOUNT_PATH, headers=with_session(rooms.session))
        warnings = [
            record
            for record in caplog.records
            if record.name.startswith(LOGGER_PREFIX)
            and record.levelno >= logging.WARNING
        ]
        r_state = state_of(first.registry, rooms.r_code)
        u_exists = first.store.has_room(U_CODE)
        sent = list(first.mailer.messages[sent_before:])
        pending = first.accounts.pending_erasures()
        rows = erasure_rows(first.database_path)
        held = listed_players(first.database_path)
        secrets = strings_in(
            database_bytes(first.database_path), [ZOE_EMAIL, ZOE_STORED]
        )
        assert store.hold_over.wait(timeout=10.0)

    assert deletion.status_code == 204
    assert elapsed < ANSWER_BOUND_SECONDS
    assert status.json() == SIGNED_OUT
    assert len(warnings) == 1
    assert nicknames_of(r_state, rooms.zoe_in_r) == [FORMER_NICKNAME]
    assert u_exists is False
    assert sent == []
    assert len(pending) == 1
    assert (pending[0].account_id, pending[0].email) == (rooms.account_id, ZOE_EMAIL)
    assert (pending[0].requested_at, pending[0].attempts) == (requested_at, 1)
    assert set(pending[0].players) == {
        ErasedPlayer(code=rooms.r_code, player_id=rooms.zoe_in_r, is_erased=True),
        ErasedPlayer(code=rooms.s_code, player_id=rooms.zoe_in_s, is_erased=False),
    }
    assert held == sorted(
        [(rooms.r_code, rooms.zoe_in_r), (rooms.s_code, rooms.zoe_in_s)]
    )
    assert rows == [
        ErasureRow(rooms.account_id, ZOE_EMAIL, requested_at, None, None, 1, 2, 1)
    ]
    assert secrets == [ZOE_EMAIL, ZOE_STORED]

    fake_clock.advance(ONE_DAY)
    with account_app(tmp_path, fake_clock) as second:
        wait_for(lambda: second.accounts.pending_erasures() == [], "the erasure done")
        sent_second = list(second.mailer.messages)
        s_state = state_of(second.registry, rooms.s_code)
        rows_after = erasure_rows(second.database_path)
        listed = listed_players(second.database_path)
        wait_for(
            lambda: strings_in(
                database_bytes(second.database_path), [ZOE_EMAIL, ZOE_STORED]
            )
            == [],
            "the files without her address and nickname",
        )

    assert len(sent_second) == 1
    assert (sent_second[0]["To"], sent_second[0]["Subject"]) == (
        ZOE_EMAIL,
        DELETED_SUBJECT,
    )
    assert nicknames_of(s_state, rooms.zoe_in_s) == [FORMER_NICKNAME]
    done_at = fake_clock()
    assert rows_after == [
        ErasureRow(None, None, requested_at, done_at, done_at, 2, 2, 1)
    ]
    assert listed == []

    with account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG) as third:
        time.sleep(LATER_SWEEPS_SECONDS)
        sent_third = list(third.mailer.messages)
        rows_last = erasure_rows(third.database_path)

    assert sent_third == []
    assert rows_last == rows_after
