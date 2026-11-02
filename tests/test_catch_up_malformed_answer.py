"""Tests of `social/catch-up.md` AC-21: an answer that is not a catch-up shows
nothing (rule 12).

Spec 034's mocked socket and catch-up route (`spec034_harness.open_mocked_room`):
the room record holds `seen_seq` 5 and the snapshot is at 9, so the page asks for
the catch-up of 5 to 9. The route answers 200 with a body naming (1, 0) among its
cells, whose one `word_completed` line, Bob's at seq 7, has the clue `null` or
`{"row": "2", "column": 0, "clue_index": 0}`. The page highlights no cell, adds no
item to the stream, sends no second request in the 2 seconds after the answer, and
still sends Ana's `T` typed on (1, 0).
"""

from __future__ import annotations

import json

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from spec034_harness import (
    BOB,
    CatchUpRoute,
    JsonObject,
    MockRoom,
    catch_up_body,
    caught_up_values,
    cell_at,
    expected_caught_up,
    feed_item_locator,
    grid_from_text,
    open_mocked_room,
    record_with,
    request_body,
    room_page,
    wait_until,
)

NO_RETRY_MS = 2_000
MALFORMED_CLUES: list[object] = [None, {"row": "2", "column": 0, "clue_index": 0}]


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def answer_with_malformed_clue(clue: object) -> str:
    """The 5-to-9 catch-up naming (1, 0), its word line's clue replaced by `clue`."""
    line: JsonObject = {
        "type": "word_completed",
        "seq": 7,
        "player_id": BOB,
        "clue": clue,
    }
    body = catch_up_body(5, 9, cells=[(1, 0)], lines=[line], names=[(BOB, "BOB")])
    return json.dumps(body)


def has_sent_t_at_1_0(mock: MockRoom) -> bool:
    """Whether the page sent an `edit_letter` of `T` at (1, 0) on its socket."""
    for edit in mock.latest().edit_letters():
        if (edit.row, edit.column, edit.letter) == (1, 0, "T"):
            return True
    return False


@pytest.mark.parametrize("clue", MALFORMED_CLUES, ids=["null", "row-as-text"])
def test_ac21_a_word_line_whose_clue_is_not_three_integers_shows_nothing(
    page: Page, live_server: str, fx01_grid: Grid, clue: object
) -> None:
    route = CatchUpRoute(answer=answer_with_malformed_clue(clue))
    mock = open_mocked_room(
        page, live_server, fx01_grid, route, record=record_with(5), seq=9
    )
    route.wait_for_requests(page, 1)

    page.wait_for_timeout(NO_RETRY_MS)

    assert route.parsed_bodies() == [request_body(5, 9)]
    assert caught_up_values(page) == expected_caught_up([])
    expect(feed_item_locator(page)).to_have_count(0)
    expect(room_page(page)).to_have_attribute("data-catch-up", "")
    cell_at(page, 1, 0).click()
    page.keyboard.press("t")
    wait_until(page, lambda: has_sent_t_at_1_0(mock), "the edit_letter of T at (1, 0)")
