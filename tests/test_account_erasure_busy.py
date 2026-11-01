"""Tests of account/account, AC-22: an erasure while the database file is held.

The app of spec 033's "Test harness" (accounts on, both stores on one file, a fake
clock). Zoé plays room R with Bob and signs in from it, so her account holds her
identity there. A second connection to the file then holds a read open
(`holding_a_read` of `operations_harness`), which makes every checkpoint busy, and
Zoé deletes her account with `DELETE /api/account`. This test measures real time
(a bound of 2 s against the 5 s busy timeout of the stores' connections), so the
file runs in the serial pass (`SERIAL_TEST_FILES` of `scripts/gate_browsers.py`).

The criterion says "WARNING records are logged" without a number: the test asks for
at least one, each from a `nock.*` logger. "The next sweep" is `expire_rooms()` of
the registry and `purge` of the account store, the two calls that the app's sweep
makes in turn (`lobby/lifetime.md` rule 6, `account/account.md` rule 20).
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from nock.grid import Grid
from operations_harness import LOGGER_PREFIX, holding_a_read, warnings_logged
from spec017_harness import FakeClock
from spec029_harness import Player, play_fx01, sign_in_from
from spec032_harness import BOB, TB, grid_from_text
from spec033_harness import (
    ACCOUNT_PATH,
    SIGNED_OUT,
    ZELIE_EMAIL,
    account_app,
    database_bytes,
    strings_in,
    with_session,
)

CODE_R = "RRRRRR"
ZOE_PLAYER = "p-zoe"
ZOE_TOKEN = "token-of-zoe-0001"
ZOE_STORED = "ZOÉ"  # as the server stores her nickname (spec 012 decision 12)
ANSWER_BOUND_SECONDS = 2.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def test_ac22_the_erasure_answers_at_once_and_the_next_sweep_empties_the_files(
    tmp_path: Path,
    fx01_grid: Grid,
    fake_clock: FakeClock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        play = play_fx01(
            fx01_grid,
            CODE_R,
            [Player("Zoé", ZOE_PLAYER, ZOE_TOKEN), Player("Bob", BOB, TB)],
            start=app.clock(),
            solved_after=None,
        )
        app.registry.add_room(play.state)
        session = sign_in_from(app, ZELIE_EMAIL, CODE_R, ZOE_TOKEN)
        secrets_in_files = [ZELIE_EMAIL, ZOE_STORED]
        assert strings_in(database_bytes(app.database_path), secrets_in_files) == (
            secrets_in_files
        )
        caplog.set_level(logging.WARNING, logger=LOGGER_PREFIX)

        with holding_a_read(app.database_path):
            started = time.monotonic()
            deletion = app.client.delete(ACCOUNT_PATH, headers=with_session(session))
            elapsed = time.monotonic() - started
            warnings = warnings_logged(caplog)

        status = app.client.get(ACCOUNT_PATH, headers=with_session(session))
        app.registry.expire_rooms()
        app.accounts.purge(app.clock())
        left_in_files = strings_in(database_bytes(app.database_path), secrets_in_files)

    assert deletion.status_code == 204
    assert elapsed < ANSWER_BOUND_SECONDS
    assert status.json() == SIGNED_OUT
    assert len(warnings) > 0
    for warning in warnings:
        assert warning.name.startswith(LOGGER_PREFIX)
    assert left_in_files == []
