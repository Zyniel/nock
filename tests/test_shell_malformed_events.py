"""Tests of `client/shell.md` AC-34: an event applies whole, a part of the wrong
shape skipped (rule 4).

Ana's page at 1280 by 720 on spec 043's mocked room, joined on FX-01 with Bob's `X`
at (1, 0) and `Y` at (1, 1), snapshot at seq 5. The mock sends Bob's grid check as
`check_result` 6 whose `wrong` is `[null, {"row": 1, "column": 0}, {"row": "1",
"column": 1}]` (the JSON of a valid `CheckResult` with that list put in): the page
takes seq 6, strikes (1, 0) (`data-wrong` true) and not (1, 1), and adds the
stream line « Bob a vérifié la grille ». Event 7, Bob's `V` at (2, 1), then gives
seq 7 and shows.
"""

from __future__ import annotations

import json

from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.protocol import CheckResult, GridTarget
from spec043_harness import (
    cell_at,
    expect_seq,
    fr_format,
    fx01_view,
    letter_frame,
    open_room,
    players_up_to,
    snapshot_frame,
)

MALFORMED_WRONG: list[object] = [
    None,
    {"row": 1, "column": 0},
    {"row": "1", "column": 1},
]
X_AND_Y: list[tuple[int, int, dict[str, object]]] = [
    (1, 0, {"letter": "X", "author": "p2"}),
    (1, 1, {"letter": "Y", "author": "p2"}),
]


def malformed_check_frame() -> str:
    """Bob's grid check at seq 6, its `wrong` list holding two malformed cells."""
    result = CheckResult(
        seq=6, player_id="p2", target=GridTarget(), correct=(), wrong=()
    )
    event = result.model_dump(mode="json")
    event["wrong"] = MALFORMED_WRONG
    return json.dumps(event)


def test_ac34_a_check_result_with_malformed_cells_strikes_only_the_valid_one(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    frame = snapshot_frame(fx01_view(fx01_grid, X_AND_Y), players_up_to(3))
    mock = open_room(page, live_server, frame)

    mock.send(malformed_check_frame())

    expect_seq(page, 6)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-wrong", "true")
    expect(cell_at(page, 1, 1)).to_have_attribute("data-wrong", "false")
    check_lines = page.get_by_test_id("activity-feed").locator(
        '[data-testid="feed-item"][data-kind="check"]'
    )
    expect(check_lines).to_have_text([fr_format("feed.check.grid", name="Bob")])

    mock.send(letter_frame(7, 2, 1, "V", "p2"))

    expect_seq(page, 7)
    expect(cell_at(page, 2, 1)).to_have_attribute("data-letter", "V")
