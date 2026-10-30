"""Tests of gameplay/results, AC-23: an erased nickname and a deleted room.

Over HTTP and the room socket, with the app of `host_harness` (accounts on, a fake
clock, the rooms' store on a file). Ana (anonymous) and Zoe (signed in, her room
identity recorded with `PUT /api/account/rooms`) play a room and solve it; its
recap is read, Zoe's account is erased, and the recap is read again. The room is
then deleted by its expiry (721 hours after it was solved, the life of a solved
anonymous room being 720), and both share routes are read.

Readings of the spec's wording:

- The erasure is tried twice: with the two sockets still open (the room is live)
  and after they closed (the room is only in the store).
- "The next recap names her `--`" is read on both recaps, the room's (`players`) and
  the public one (`team`).
- Nicknames are stored in capitals, so the recap names `ANA` and `ZOE`.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from host_harness import (
    create_room_as,
    host_app,
    open_member,
    sign_in_as,
    wait_for_message,
)
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.protocol import GridSolved
from results_harness import (
    recap_route,
    shared_api_route,
    shared_page_route,
    type_the_solution,
)
from server_harness import wait_until_not_live
from spec011_harness import INDEX_HTML
from spec017_harness import FakeClock
from spec024_harness import make_catalogue
from spec032_harness import grid_from_text
from spec033_harness import ACCOUNT_PATH, HOUR, ROOMS_PATH, room_key, with_session

ZOE_EMAIL = "zoe.probe@example.org"
FORMER_NICKNAME = "--"
NOT_FOUND = {"detail": "Not Found"}
PAST_THE_SOLVED_LIFE_HOURS = 721


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    return make_catalogue(fx01_grid)


@pytest.mark.parametrize("sockets_open", [True, False], ids=["live", "stored"])
def test_ac23_an_erased_member_is_named_dashes_and_a_deleted_room_has_no_recap(
    tmp_path: Path,
    fake_clock: FakeClock,
    catalogue: Catalogue,
    monkeypatch: pytest.MonkeyPatch,
    sockets_open: bool,
) -> None:
    (tmp_path / "index.html").write_text(INDEX_HTML, encoding="utf-8")

    with (
        host_app(tmp_path, fake_clock, catalogue, monkeypatch) as app,
        contextlib.ExitStack() as stack,
    ):
        zoe_session = sign_in_as(app, ZOE_EMAIL)
        code = create_room_as(app, None)
        ana = open_member(stack, app.client, code, "Ana")
        zoe = open_member(stack, app.client, code, "Zoe", session=zoe_session)
        recorded = app.client.put(
            ROOMS_PATH,
            json=room_key(code, zoe.snapshot().resume_token),
            headers=with_session(zoe_session),
        )
        type_the_solution(zoe)
        wait_for_message(ana, GridSolved)
        wait_for_message(zoe, GridSolved)
        if not sockets_open:
            stack.close()
            wait_until_not_live(app.registry, code)
        solved = app.registry.peek_room(code)
        assert solved is not None
        token = solved.share_token
        assert token is not None

        recap_before = app.client.get(recap_route(code)).json()
        team_before = app.client.get(shared_api_route(token)).json()["team"]
        erased = app.client.delete(ACCOUNT_PATH, headers=with_session(zoe_session))
        recap_after = app.client.get(recap_route(code)).json()
        team_after = app.client.get(shared_api_route(token)).json()["team"]

        stack.close()
        wait_until_not_live(app.registry, code)
        fake_clock.now += PAST_THE_SOLVED_LIFE_HOURS * HOUR
        api_after_deletion = app.client.get(shared_api_route(token))
        page_after_deletion = app.client.get(shared_page_route(token))
        room_stored = app.store.has_room(code)

    assert recorded.status_code == 204
    assert [player["nickname"] for player in recap_before["players"]] == ["ANA", "ZOE"]
    assert team_before == ["ANA", "ZOE"]
    assert erased.status_code == 204
    names_after = [player["nickname"] for player in recap_after["players"]]
    assert names_after == ["ANA", FORMER_NICKNAME]
    assert team_after == ["ANA", FORMER_NICKNAME]
    assert room_stored is False
    assert api_after_deletion.status_code == 404
    assert api_after_deletion.json() == NOT_FOUND
    assert page_after_deletion.status_code == 404
    assert page_after_deletion.json() == NOT_FOUND
