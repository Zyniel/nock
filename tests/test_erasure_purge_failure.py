"""Tests of account/erasure, AC-13: a purge that raises is logged and retried.

HTTP, on the app of spec 033's "Test harness", which sweeps every 0.1 s. Ana's
erasure is written and finished at time 0 on the database file before the app
starts. The app starts at the fake clock's time of 1,000,000 s, where the erasure is
kept. The `purge` of the app's account store is then wrapped: the first call at
157,680,001 s or later raises, the others run the real one. The clock moves to
157,680,001 s; the test waits for the call that raised and then for the erasure to
be gone.

The sweep that failed leaves the erasure in place (read inside the wrapper, before
the raise), logs the failure at any level on a `nock.*` logger with the exception,
and the next sweep deletes the erasure.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from account_harness import FAST_SWEEP_CONFIG, ErasureRow, erasure_rows
from nock.accounts import AccountStore
from operations_harness import LOGGER_PREFIX
from spec017_harness import FakeClock
from spec033_harness import ANA_EMAIL, DATABASE_FILE_NAME, account_app, wait_for

PURGE_TIME = 157_680_001.0  # one second past 5 years
FAILURE_TEXT = "the disk refused the purge"


class FailingOncePurge:
    """`purge` that raises on its first call at `PURGE_TIME` or later.

    Set on an `AccountStore` instance. It records the time of each call and the
    erasure rows that the failed call found.
    """

    def __init__(self, store: AccountStore, database_path: Path) -> None:
        self._real = store.purge
        self._database_path = database_path
        self.calls: list[float] = []
        self.failed_at: float | None = None
        self.rows_when_failed: list[ErasureRow] = []

    def __call__(self, now: float) -> None:
        self.calls.append(now)
        if now >= PURGE_TIME and self.failed_at is None:
            self.failed_at = now
            self.rows_when_failed = erasure_rows(self._database_path)
            raise OSError(FAILURE_TEXT)
        self._real(now)


def finished_erasure_at_time_0(database_path: Path) -> None:
    """Write Ana's erasure and finish it at time 0, then close the store."""
    accounts = AccountStore(database_path)
    try:
        ana = accounts.sign_in(ANA_EMAIL, 0.0)
        erasure = accounts.delete_account(ana.account_id, 0.0)
        assert erasure is not None
        accounts.finish_erasure(erasure.erasure_id, 0.0, None)
    finally:
        accounts.close()


def test_ac13_a_purge_that_raises_is_logged_and_the_next_sweep_deletes_the_erasure(
    tmp_path: Path, fake_clock: FakeClock, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG, logger=LOGGER_PREFIX)
    database_path = tmp_path / DATABASE_FILE_NAME
    finished_erasure_at_time_0(database_path)

    with account_app(tmp_path, fake_clock, config=FAST_SWEEP_CONFIG) as app:
        assert len(erasure_rows(database_path)) == 1
        purge = FailingOncePurge(app.accounts, database_path)
        app.accounts.purge = purge
        fake_clock.now = PURGE_TIME

        wait_for(lambda: purge.failed_at is not None, "the purge that raises")
        wait_for(lambda: erasure_rows(database_path) == [], "the next purge")
        calls_at_purge_time = [now for now in purge.calls if now >= PURGE_TIME]

    failures_logged = []
    for record in caplog.records:
        if record.name.startswith(LOGGER_PREFIX) and record.exc_info is not None:
            failures_logged.append(str(record.exc_info[1]))

    assert purge.failed_at == PURGE_TIME
    assert len(purge.rows_when_failed) == 1
    assert len(calls_at_purge_time) >= 2
    assert failures_logged == [FAILURE_TEXT]
