"""Tests of account/account, AC-27: a history record never brings an erased name back.

Two plays of Bob's record of the solved room, Bob, Zoé and Cy having played it:

- the save that read the room before the deletion: on an `AccountStore` alone, Zoé's
  account holds her players in R and in S; her deletion writes the pending erasure,
  which lists both; then Bob's `save_history` of R's state as it was before (it still
  names her `ZOÉ`) writes her `--` among his team-mates and leaves Cy's name;
- the delete hook of a room the erasure deletes: over HTTP, T is solved by Bob and
  Zoé, has expired and is not swept; both signed in from it; Zoé deletes her account
  and the erasure deletes T (rule 26, step 1), whose delete hook saves Bob's record
  from the state that still names her. His history then lists T with `["--"]`.
  That play also holds for the old erasure; the test pins the rule's outcome.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from account_harness import BOB_EMAIL, TZ, ZOE, ZOE_EMAIL, ZOE_STORED
from nock.accounts import AccountStore, ErasedPlayer, RoomIdentity
from nock.grid import Grid
from spec017_harness import FakeClock
from spec029_harness import (
    Player,
    history_body,
    play_fx01,
    sign_in_from,
)
from spec032_harness import BOB, CY, LIFE, T0, TB, TC, grid_from_text
from spec033_harness import ACCOUNT_PATH, FORMER_NICKNAME, account_app, with_session

R_CODE = "RRRRRR"
S_CODE = "SSSSSS"
T_CODE = "TTTTTT"
ZOE_IN_S = "p-zoe-in-s"
ZOE_TOKEN_IN_S = "token-of-zoe-0002"
DELETED_AT = T0 + 60.0


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def test_ac27_a_save_from_a_state_read_before_the_deletion_names_her_dashes(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    played = play_fx01(
        fx01_grid,
        R_CODE,
        [Player("Bob", BOB, TB), Player("Zoé", ZOE, TZ), Player("Cy", CY, TC)],
        start=T0,
    )
    accounts = AccountStore(tmp_path / "nock.sqlite3")
    try:
        bob = accounts.sign_in(BOB_EMAIL, T0)
        zoe = accounts.sign_in(ZOE_EMAIL, T0)
        bob_in_r = RoomIdentity(
            code=R_CODE, player_id=BOB, resume_token=TB, nickname="BOB"
        )
        zoe_in_r = RoomIdentity(
            code=R_CODE, player_id=ZOE, resume_token=TZ, nickname=ZOE_STORED
        )
        zoe_in_s = RoomIdentity(
            code=S_CODE,
            player_id=ZOE_IN_S,
            resume_token=ZOE_TOKEN_IN_S,
            nickname=ZOE_STORED,
        )
        assert accounts.link_identity(bob.account_id, bob_in_r, T0)
        assert accounts.link_identity(zoe.account_id, zoe_in_r, T0)
        assert accounts.link_identity(zoe.account_id, zoe_in_s, T0)
        pending = accounts.delete_account(zoe.account_id, DELETED_AT)
        assert pending is not None
        assert set(pending.players) == {
            ErasedPlayer(code=R_CODE, player_id=ZOE),
            ErasedPlayer(code=S_CODE, player_id=ZOE_IN_S),
        }

        accounts.save_history(bob.account_id, played.state)
        teammates = [record.teammates for record in accounts.history(bob.account_id)]
    finally:
        accounts.close()

    assert teammates == [(FORMER_NICKNAME, "CY")]


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
