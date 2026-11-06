"""Tests of `client/shell.md` AC-37: a placeholder with no value stays as written
(rule 5).

No template of `fr.json` holds two placeholders, so the test serves the room's
check-line template reworded (`shell_harness.ReworkedValues`) to « {name} et {other} ».
Ana's page at 1280 by 720 on spec 043's mocked room, joined on FX-01: the mock sends a
grid check by a player whose nickname is Ana, and the line, filled by the client with
`name` only, reads « Ana et {other} »: the missing value is neither blanked, nor
written « undefined », and the template is not left unfilled.
"""

from __future__ import annotations

from playwright.sync_api import Page, expect

from nock.grid import Grid
from shell_harness import Rewording, ReworkedValues
from spec043_harness import (
    check_frame,
    expect_seq,
    fr_value,
    fx01_view,
    open_room,
    player,
    snapshot_frame,
)

CHECK_KEY = "feed.check.grid"
TWO_PLACEHOLDERS = "{name} et {other}"


def test_ac37_a_placeholder_with_no_value_is_left_as_written(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    rework = ReworkedValues(
        page, [Rewording(CHECK_KEY, fr_value(CHECK_KEY), TWO_PLACEHOLDERS)]
    )
    players = [player("p1", host=True), player("p2", nickname="Ana")]
    frame = snapshot_frame(fx01_view(fx01_grid), players)
    mock = open_room(page, live_server, frame)

    mock.send(check_frame(6, "p2"))

    expect_seq(page, 6)
    assert rework.counts == {CHECK_KEY: 1}
    line = page.locator('[data-testid="feed-item"][data-seq="6"]')
    expect(line).to_have_text("Ana et {other}")
