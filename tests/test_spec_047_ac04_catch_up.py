"""Tests of spec 047, AC-4: spec 034's catch-up adds no `vote` line.

Added after spec 047's first review (2026-10-23). The page turns an applied
`vote_closed` into a `vote` line (`feedItemFor`), so "the snapshot and spec 034's
catch-up add no such line" holds only because a catch-up never carries a
`vote_closed`. That is pinned at both ends:

- The server: a catch-up line is a `check_result`, a `reveal_result` or a
  `word_completed` (spec 034's `CatchUpLine`; unknown fields and other types are
  refused), so `CatchUp` cannot hold a `vote_closed` at all; and
  `build_catch_up` over an absence that spans two closed votes (one passed, one
  rejected) gives the passed vote's `reveal_result` and no line of a vote.
- The page: a reconnection whose catch-up is that real answer (spec 034's mocked
  catch-up route answering `build_catch_up`'s JSON) shows the reveal line and no
  `vote` line.

The absence is played on spec 025's room `V3` (`p1` host, `p2`, `p3`, vote mode,
seq 4): `p1` asks to reveal (1, 0) (vote 1, seq 5), `p2` votes yes (`vote_closed`
`passed` seq 6, `reveal_result` seq 7, `cell_locked` seq 8); `p2` asks for a grid
check (vote 2, seq 9), `p1` and `p3` vote no (`vote_closed` `rejected` seq 10).
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect
from pydantic import ValidationError

from nock.catch_up import CatchUp, build_catch_up
from nock.grid import Grid
from nock.protocol import (
    RevealResult,
    Vote,
    VoteClosed,
    VoteOutcome,
)
from nock.room import RoomState
from room_panels import show_tab
from spec025_harness import GRID_CHECK, REVEAL_1_0, Play, v3
from spec034_harness import (
    CatchUpRoute,
    expect_catch_up_applied,
    open_mocked_room,
    reconnect_with_snapshot,
    record_with,
)
from spec047_harness import vote_lines

ABSENCE_START_SEQ = 4  # `V3`'s seq: the page saw it before the absence
ABSENCE_END_SEQ = 10


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return Grid.model_validate_json(fx01_text)


def absence_with_two_closed_votes(grid: Grid) -> tuple[RoomState, Play, int]:
    """Play the absence on `V3`.

    Returns:
        The room before the absence, the play, and the index of the absence's
        first entry in `play.entries`.
    """
    play = v3(grid)
    before = play.state
    first = len(play.entries)
    play.send("p1", REVEAL_1_0)
    play.send("p2", Vote(vote_id=1, yes=True))
    play.send("p2", GRID_CHECK)
    play.send("p1", Vote(vote_id=2, yes=False))
    play.send("p3", Vote(vote_id=2, yes=False))
    assert play.state.seq == ABSENCE_END_SEQ
    return before, play, first


def absence_catch_up(grid: Grid) -> tuple[CatchUp, list[object]]:
    """The catch-up of the absence, and the events the absence logged."""
    before, play, first = absence_with_two_closed_votes(grid)
    entries = play.entries[first:]
    catch_up = build_catch_up(ABSENCE_START_SEQ, ABSENCE_END_SEQ, before, entries)
    events: list[object] = [entry.event for entry in entries]
    return catch_up, events


# ---- The server ----------------------------------------------------------------


def test_ac4_a_catch_up_over_two_closed_votes_holds_no_line_of_a_vote(
    fx01_grid: Grid,
) -> None:
    catch_up, events = absence_catch_up(fx01_grid)

    closed_votes = [event for event in events if isinstance(event, VoteClosed)]
    outcomes = [event.outcome for event in closed_votes]
    assert outcomes == [VoteOutcome.PASSED, VoteOutcome.REJECTED]
    types = [line.type for line in catch_up.lines]
    assert types == ["reveal_result"]
    assert isinstance(catch_up.lines[0], RevealResult)
    assert catch_up.lines[0].seq == 7
    assert "vote" not in catch_up.model_dump_json()


def test_ac4_a_catch_up_cannot_carry_a_vote_closed_line() -> None:
    closed_vote = VoteClosed(
        seq=6, vote_id=1, outcome=VoteOutcome.PASSED, yes_votes=2, eligible_voters=3
    )
    body = {
        "after_seq": 4,
        "until_seq": 10,
        "cells": [],
        "lines": [closed_vote.model_dump(mode="json")],
        "names": [],
    }

    with pytest.raises(ValidationError, match="lines"):
        CatchUp.model_validate(body)


# ---- The page --------------------------------------------------------------------


def test_ac4_a_reconnection_whose_catch_up_spans_closed_votes_adds_no_vote_line(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    catch_up, _ = absence_catch_up(fx01_grid)
    route = CatchUpRoute(answer=catch_up.model_dump_json())
    mock = open_mocked_room(
        page,
        live_server,
        fx01_grid,
        route,
        record=record_with(None),
        seq=ABSENCE_START_SEQ,
    )

    reconnect_with_snapshot(mock, fx01_grid, ABSENCE_END_SEQ)

    expect_catch_up_applied(page, f"{ABSENCE_START_SEQ}-{ABSENCE_END_SEQ}")
    show_tab(page, "discussion")
    reveal = page.locator('[data-testid="feed-item"][data-kind="reveal"]')
    expect(reveal).to_have_count(1)
    expect(reveal).to_have_attribute("data-seq", "7")
    expect(vote_lines(page)).to_have_count(0)
