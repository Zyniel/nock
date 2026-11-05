"""Tests of `social/reactions.md` AC-10: « Réagir » and « Je bloque » while the page
is not joined.

Rules 5 and 8. Ana's page on spec 017's mocked room (`joined_room`, FX-01, seq 5,
1280 by 720).

AC-10: with MIME selected and the picker open, the socket closes with 1011: within
5 s « Réagir » and « Je bloque » are disabled and the picker is gone, no `react`
or `flag` sent; they stay disabled on the new socket until its snapshot, which
enables both. After a close 4001 both stay disabled, also once the selection
moves to another word.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import Page, expect

from nock.grid import Grid
from spec017_harness import (
    LOSS_BUDGET_MS,
    STORED_JOIN,
    MockRoom,
    expect_status,
    first_join,
    grid_from_text,
    joined_room,
    settle,
    snapshot_frame,
)
from spec022_harness import flag_button, frames_of_kind, picker, react_button
from spec043_harness import press_cell, select_mime

LOST_CLOSE = 1011
REPLACED_CLOSE = 4001
STAYS_DISABLED_MS = 1500  # longer than the first retry delay at its highest


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def sent_on_any_socket(room: MockRoom, kind: str) -> int:
    """How many frames of one `type` the page sent, on every socket."""
    count = 0
    for connection in room.connections:
        count += len(frames_of_kind(connection, kind))
    return count


# ---- AC-10: disabled while the page is not joined ----------------------------------


def test_ac10_a_loss_disables_both_buttons_and_closes_the_picker_until_a_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    select_mime(page)
    expect(flag_button(page)).to_be_enabled()
    react_button(page).click()
    expect(picker(page)).to_be_visible()

    room.connections[0].close(LOST_CLOSE)

    expect(react_button(page)).to_be_disabled(timeout=LOSS_BUDGET_MS)
    expect(flag_button(page)).to_be_disabled(timeout=LOSS_BUDGET_MS)
    expect(picker(page)).to_have_count(0)
    room.wait_for_connections(2)
    second = room.connections[1]
    assert first_join(page, second) == STORED_JOIN
    settle(page)
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    assert sent_on_any_socket(room, "react") == 0
    assert sent_on_any_socket(room, "flag") == 0

    second.send(snapshot_frame(fx01_grid, 5))

    expect_status(page, "joined")
    expect(react_button(page)).to_be_enabled()
    expect(flag_button(page)).to_be_enabled()


def test_ac10_after_a_close_4001_both_buttons_stay_disabled(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_room(page, live_server, fx01_grid)
    select_mime(page)
    expect(react_button(page)).to_be_enabled()

    room.connections[0].close(REPLACED_CLOSE)

    expect_status(page, "replaced")
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    press_cell(page, 1, 0)
    page.wait_for_timeout(STAYS_DISABLED_MS)
    expect(react_button(page)).to_be_disabled()
    expect(flag_button(page)).to_be_disabled()
    assert len(room.connections) == 1
