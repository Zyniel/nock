"""Tests of spec 032, AC-7's page run: the page of a player who sees another one
seated back (browser with mocked socket, spec 019's authors view).

The page opens `/r/ABC123` on spec 040's mocked socket and gets a FX-01 snapshot
(seq 7) whose `you` is `p2` (Bob, colour 1, host), whose players are `p2` and `p3`
(Cy, colour 2), and whose (1, 0) holds `T` by `p1`, Ana's id. Ana is a past player,
so she is not in `players`. The mock then sends her seat back, `PlayerJoined(seq=8)`
of `p1` as `Ana`, colour 0; "within 300 ms" is measured, as spec 019 measures it,
from the moment `room-page` shows `data-seq="8"`.

Refined by spec 045 (the design's Auteurs mode): the band and the clue bar's
author line are gone. Once `authors-switch` is on, (1, 0) has no finder before the
seat back (`data-author-colour=""` and the computed `color` rgb(20, 24, 31)), and
`authors-legend` names `Bob` then `Cy`; within 300 ms of the seat back, (1, 0) has
`data-author-colour="0"` and the computed `color` of `--player-ink-0`, and the
legend names `Bob`, `Cy`, then `Ana`. The inks and the legend are read with spec
045's readers (`spec045_harness`).
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Page, expect

from fonts_ready import wait_for_fonts
from nock.grid import Grid
from nock.protocol import RevealBudget, Snapshot, grid_view
from spec019_harness import (
    DEFAULT_SETTINGS,
    FOLLOW_MS,
    FX01_CELL_COUNT,
    ROOM_CODE,
    SNAPSHOT_RESUME_TOKEN,
    WAIT_TIMEOUT_MS,
    MockRoomSocket,
    expect_seq,
    grid_from_text,
    player_joined_frame,
    player_view,
    turn_switch_on,
    wait_until,
    with_letter_cells,
)
from spec045_harness import (
    INK,
    INKS,
    cell_shows_within,
    finder_problems,
    legend_reading,
    name_texts,
    names_within,
    read_cell,
)

SNAPSHOT_SEQ = 7
SEAT_BACK_SEQ = 8


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def bobs_snapshot(grid: Grid) -> str:
    """The run's snapshot: Bob's, with Cy, and Ana's `T` at (1, 0)."""
    view = with_letter_cells(grid_view(grid), [(1, 0, {"letter": "T", "author": "p1"})])
    players = (player_view("p2", "Bob", 1, is_host=True), player_view("p3", "Cy", 2))
    snapshot = Snapshot(
        seq=SNAPSHOT_SEQ,
        you="p2",
        resume_token=SNAPSHOT_RESUME_TOKEN,
        grid=view,
        players=players,
        settings=DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=(),
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_bobs_page(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Open /r/ABC123 on a mocked socket, show Bob's snapshot, switch authors on."""
    mock = MockRoomSocket()
    page.route_web_socket(re.compile(r".*/api/rooms/ABC123/ws$"), mock.handle)
    page.goto(f"{base_url}/r/{ROOM_CODE}")
    nickname_input = page.get_by_test_id("nickname-input")
    nickname_input.fill("Bob", timeout=WAIT_TIMEOUT_MS)
    nickname_input.press("Enter", timeout=WAIT_TIMEOUT_MS)
    wait_until(page, lambda: len(mock.received) > 0)
    mock.send(bobs_snapshot(grid))
    expect_seq(page, SNAPSHOT_SEQ)
    expect(page.get_by_test_id("cell")).to_have_count(FX01_CELL_COUNT)
    turn_switch_on(page)
    expect(page.get_by_test_id("authors-legend")).to_be_visible()
    wait_for_fonts(page)
    return mock


def send_the_seat_back(page: Page, mock: MockRoomSocket) -> None:
    """Send Ana's seat back and wait until the page shows its seq."""
    mock.send(player_joined_frame(SEAT_BACK_SEQ, player_view("p1", "Ana", 0)))
    expect_seq(page, SEAT_BACK_SEQ)


def test_ac7_page_before_the_seat_back_the_past_players_letter_is_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_bobs_page(page, live_server, fx01_grid)

    assert finder_problems("(1, 0)", read_cell(page, 1, 0), "", INK) == []


def test_ac7_page_before_the_seat_back_the_legend_names_bob_then_cy(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_bobs_page(page, live_server, fx01_grid)

    reading = legend_reading(page)

    assert [text.strip() for text in name_texts(reading)] == ["Bob", "Cy"]


def test_ac7_page_within_300_ms_of_the_seat_back_the_letter_has_her_ink(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_bobs_page(page, live_server, fx01_grid)

    send_the_seat_back(page, mock)

    reading = cell_shows_within(page, 1, 0, "0", INKS[0], FOLLOW_MS)
    assert finder_problems("(1, 0)", reading, "0", INKS[0]) == []


def test_ac7_page_after_the_seat_back_the_legend_names_bob_cy_then_ana(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_bobs_page(page, live_server, fx01_grid)
    legend_reading(page)

    send_the_seat_back(page, mock)

    expected = ["Bob", "Cy", "Ana"]
    reading = names_within(
        page, lambda found: [text.strip() for text in name_texts(found)] == expected
    )
    assert [text.strip() for text in name_texts(reading)] == expected
