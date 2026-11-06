"""Tests of account/erasure, AC-18: two erased team-mates read `--` twice.

HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one file,
a fake clock). Ana, Bob, Zoé and Lou, joined in that order, solved R, a stored FX-01
room; each of the three accounts signs in from R. Zoé and Lou delete their accounts,
one after the other. Ana's record of R, listed by `GET /api/account/history`, has
`["BOB", "--", "--"]` as team-mates, whether the record was saved by a first
`GET /api/account/history` before the deletions or by the one after them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from account_harness import (
    ANA_PLAYER,
    BOB_EMAIL,
    BOB_PLAYER,
    LOU,
    LOU_EMAIL,
    LOU_NICKNAME,
    R_CODE,
    TL,
    TZ,
    ZOE,
    ZOE_EMAIL,
    ZOE_NICKNAME,
)
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import Player, history_body, play_fx01, sign_in_from
from spec033_harness import (
    ACCOUNT_PATH,
    ANA_EMAIL,
    FORMER_NICKNAME,
    account_app,
    with_session,
)

ERASED_TWICE = ["BOB", FORMER_NICKNAME, FORMER_NICKNAME]


@pytest.mark.parametrize(
    "is_saved_before_the_deletions",
    [True, False],
    ids=["saved before the deletions", "saved after the deletions"],
)
def test_ac18_two_erased_teammates_read_dashes_twice_in_the_record(
    tmp_path: Path,
    fake_clock: FakeClock,
    fx01_grid: Grid,
    is_saved_before_the_deletions: bool,
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        played = play_fx01(
            fx01_grid,
            R_CODE,
            [
                ANA_PLAYER,
                BOB_PLAYER,
                Player(ZOE_NICKNAME, ZOE, TZ),
                Player(LOU_NICKNAME, LOU, TL),
            ],
            start=app.clock(),
        )
        app.registry.add_room(played.state)
        ana_session = sign_in_from(app, ANA_EMAIL, R_CODE, ANA_PLAYER.token)
        sign_in_from(app, BOB_EMAIL, R_CODE, BOB_PLAYER.token)
        zoe_session = sign_in_from(app, ZOE_EMAIL, R_CODE, TZ)
        lou_session = sign_in_from(app, LOU_EMAIL, R_CODE, TL)
        records_before: list[dict[str, object]] = []
        if is_saved_before_the_deletions:
            records_before = history_body(app.client, ana_session)

        zoe_deletion = app.client.delete(
            ACCOUNT_PATH, headers=with_session(zoe_session)
        )
        lou_deletion = app.client.delete(
            ACCOUNT_PATH, headers=with_session(lou_session)
        )
        records = history_body(app.client, ana_session)

    assert zoe_deletion.status_code == 204
    assert lou_deletion.status_code == 204
    if is_saved_before_the_deletions:
        assert [record["teammates"] for record in records_before] == [
            ["BOB", ZOE_NICKNAME.upper(), LOU_NICKNAME.upper()]
        ]
    assert [(record["code"], record["teammates"]) for record in records] == [
        (R_CODE, ERASED_TWICE)
    ]
