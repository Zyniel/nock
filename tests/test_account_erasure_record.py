"""Tests of account/account, AC-29: the purge of the done erasures.

Python, on an `AccountStore` on a file. Three erasures are written with
`delete_account`: Ana's, done at time 0 (`finish_erasure`); Zoé's, done at 1,000, a
newer one; Bob's, requested at 0 and still pending. `purge(157_680_001.0)`, one
second past 5 years, deletes the first only; `purge(157_679_999.0)`, one second
short, deletes none. The rows are read on a connection of the test's own.
"""

from __future__ import annotations

import contextlib
import sqlite3
from pathlib import Path

import pytest

from account_harness import BOB_EMAIL, ZOE_EMAIL
from nock.accounts import ERASURE_RECORD_LIFE_SECONDS, AccountStore
from spec033_harness import ANA_EMAIL

FIVE_YEARS = 157_680_000.0  # 5 x 365 days
NEWER_DONE_AT = 1_000.0


def erasure_ids(database_path: Path) -> list[int]:
    """The id of each row of `account_erasures`, in order."""
    with contextlib.closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT erasure_id FROM account_erasures ORDER BY erasure_id"
        ).fetchall()
    return [int(row[0]) for row in rows]


def test_ac29_the_life_of_a_done_erasure_is_five_years() -> None:
    assert ERASURE_RECORD_LIFE_SECONDS == FIVE_YEARS


@pytest.mark.parametrize(
    ("purged_at", "old_one_kept"),
    [(157_680_001.0, False), (157_679_999.0, True)],
    ids=["one second past 5 years", "one second short of 5 years"],
)
def test_ac29_a_done_erasure_of_time_0_is_purged_past_5_years_and_no_other_row(
    tmp_path: Path, purged_at: float, old_one_kept: bool
) -> None:
    path = tmp_path / "nock.sqlite3"
    accounts = AccountStore(path)
    try:
        ana = accounts.sign_in(ANA_EMAIL, 0.0)
        old = accounts.delete_account(ana.account_id, 0.0)
        zoe = accounts.sign_in(ZOE_EMAIL, NEWER_DONE_AT)
        newer = accounts.delete_account(zoe.account_id, NEWER_DONE_AT)
        bob = accounts.sign_in(BOB_EMAIL, 0.0)
        waiting = accounts.delete_account(bob.account_id, 0.0)
        assert old is not None
        assert newer is not None
        assert waiting is not None
        accounts.finish_erasure(old.erasure_id, 0.0, None)
        accounts.finish_erasure(newer.erasure_id, NEWER_DONE_AT, None)

        accounts.purge(purged_at)
        kept = erasure_ids(path)
    finally:
        accounts.close()

    expected = [newer.erasure_id, waiting.erasure_id]
    if old_one_kept:
        expected = [old.erasure_id, newer.erasure_id, waiting.erasure_id]
    assert kept == sorted(expected)
