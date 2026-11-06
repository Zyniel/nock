"""Tests of lobby/summaries, AC-5: two erased members read `--` twice.

HTTP, on the app of spec 033's "Test harness" (accounts on, both stores on one file,
a fake clock). Room A is a stored FX-01 room where Bob, Zoé and Lou joined in that
order; Zoé and Lou each sign in from it and delete their accounts. Bob's token then
gets one summary, whose players are `BOB`, `--`, `--`.
"""

from __future__ import annotations

from pathlib import Path

from account_harness import (
    BOB_PLAYER,
    LOU,
    LOU_EMAIL,
    LOU_NICKNAME,
    TL,
    TZ,
    ZOE,
    ZOE_EMAIL,
    ZOE_NICKNAME,
)
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import Player, play_fx01, sign_in_from
from spec032_harness import CODE_A, post_summaries
from spec033_harness import ACCOUNT_PATH, FORMER_NICKNAME, account_app, with_session


def test_ac5_two_erased_members_read_dashes_twice_in_the_summary(
    tmp_path: Path, fake_clock: FakeClock, fx01_grid: Grid
) -> None:
    with account_app(tmp_path, fake_clock) as app:
        played = play_fx01(
            fx01_grid,
            CODE_A,
            [BOB_PLAYER, Player(ZOE_NICKNAME, ZOE, TZ), Player(LOU_NICKNAME, LOU, TL)],
            start=app.clock(),
            solved_after=None,
        )
        app.registry.add_room(played.state)
        zoe_session = sign_in_from(app, ZOE_EMAIL, CODE_A, TZ)
        lou_session = sign_in_from(app, LOU_EMAIL, CODE_A, TL)
        zoe_deletion = app.client.delete(
            ACCOUNT_PATH, headers=with_session(zoe_session)
        )
        lou_deletion = app.client.delete(
            ACCOUNT_PATH, headers=with_session(lou_session)
        )

        response = post_summaries(app.client, [(CODE_A, BOB_PLAYER.token)])

    assert zoe_deletion.status_code == 204
    assert lou_deletion.status_code == 204
    assert response.status_code == 200
    body = response.json()
    assert [(summary["code"], summary["players"]) for summary in body] == [
        (CODE_A, ["BOB", FORMER_NICKNAME, FORMER_NICKNAME])
    ]
