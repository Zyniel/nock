"""Tests of gameplay/results, AC-21 and AC-22: reading a recap without making the
room live, and building it once per seq.

A solved FX-01 room only in the store (`results_harness.stored_solved_app`), read
over HTTP through the recap route and both share routes, and joined over its
socket for AC-22.

Seam of "built once" (AC-22): the registry calls the module-level name
`build_recap` of `nock.hub`; the test replaces it by a wrapper that counts its
calls and calls the real function. It reads no private name of the registry.

Readings of the spec's wording:

- AC-21's "as before": the recap route answers the recap of `PLAY_R` as
  `build_recap` gives it, and the share routes its public recap and `index.html`.
- AC-22's "twice each" is made at the same seq; "the next request" after Dan's
  join is a request of the public recap, and one more request after it builds
  nothing again (the recap is kept for the new seq).
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

import nock.hub
from nock.grid import Grid
from nock.recap import Recap, build_recap, public_recap
from nock.room import LogEntry, RoomState
from results_harness import (
    RECAP_LOG_LENGTH,
    recap_route,
    shared_api_route,
    shared_page_route,
    stored_solved_app,
)
from spec011_harness import INDEX_HTML
from spec014_harness import open_peer
from spec024_harness import ROOM_CODE
from spec028_harness import SHARE_TOKEN
from spec032_harness import grid_from_text


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


class CountingBuild:
    """`build_recap` wrapped: it counts its calls and gives the real recap."""

    def __init__(self) -> None:
        self.seqs: list[int] = []

    def __call__(self, state: RoomState, log: list[LogEntry]) -> Recap:
        self.seqs.append(state.seq)
        return build_recap(state, log)


# ---- AC-21: read without making the room live --------------------------------------


def test_ac21_the_recap_routes_answer_as_before_and_leave_the_room_unloaded(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    with stored_solved_app(tmp_path, fx01_grid) as app:
        stored = app.registry.peek_room(ROOM_CODE)
        assert stored is not None
        connected_before = [player.state.value for player in stored.players]
        log_before = app.store.read_log(ROOM_CODE)
        live_before = app.registry.live_codes()

        recap = app.client.get(recap_route(ROOM_CODE))
        shared = app.client.get(shared_api_route(SHARE_TOKEN))
        page = app.client.get(shared_page_route(SHARE_TOKEN))

        live_after = app.registry.live_codes()
        log_after = app.store.read_log(ROOM_CODE)

    expected = build_recap(app.game.state, app.game.log)
    assert connected_before == ["active", "active"]
    assert len(log_before) == RECAP_LOG_LENGTH
    assert live_before == frozenset()
    assert recap.status_code == 200
    assert recap.json() == expected.model_dump(mode="json")
    assert shared.status_code == 200
    assert shared.json() == public_recap(expected).model_dump(mode="json")
    assert page.status_code == 200
    assert page.text == INDEX_HTML
    assert live_after == frozenset()
    assert log_after == log_before


# ---- AC-22: built once, again after a new log entry --------------------------------


def test_ac22_the_recap_is_built_once_and_again_when_dan_joins(
    tmp_path: Path, fx01_grid: Grid, monkeypatch: pytest.MonkeyPatch
) -> None:
    counting = CountingBuild()
    monkeypatch.setattr(nock.hub, "build_recap", counting)

    with (
        stored_solved_app(tmp_path, fx01_grid) as app,
        contextlib.ExitStack() as stack,
    ):
        app.client.get(recap_route(ROOM_CODE))
        for _ in range(2):
            app.client.get(shared_page_route(SHARE_TOKEN))
            app.client.get(shared_api_route(SHARE_TOKEN))
        built_before_dan = list(counting.seqs)

        open_peer(stack, app.client, ROOM_CODE, "Dan")

        next_request = app.client.get(shared_api_route(SHARE_TOKEN))
        one_more = app.client.get(shared_api_route(SHARE_TOKEN))
        built_after_dan = list(counting.seqs)

    assert built_before_dan == [app.game.state.seq]
    assert len(built_after_dan) == 2
    assert built_after_dan[0] == app.game.state.seq
    assert built_after_dan[1] > app.game.state.seq
    assert next_request.status_code == 200
    assert next_request.json()["team"] == ["ANA", "BOB", "DAN"]
    assert one_more.json() == next_request.json()
