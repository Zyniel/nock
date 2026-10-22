"""Tests of spec 032, AC-7's page run: the page of a player who sees another one
seated back (browser with mocked socket, spec 019's authors view).

The page opens `/r/ABC123` on spec 040's mocked socket and gets a FX-01 snapshot
(seq 7) whose `you` is `p2` (Bob, colour 1, host), whose players are `p2` and `p3`
(Cy, colour 2), and whose (1, 0) holds `T` by `p1`, Ana's id. Ana is a past player,
so she is not in `players`: once `authors-switch` is on, spec 019 hatches her band,
and the clue bar names her by `fr.json["feed.someone"]`, since this page knew no
nickname for `p1`. The mock then sends her seat back, `PlayerJoined(seq=8)` of `p1`
as `Ana`, colour 0: within 300 ms (measured, as spec 019 measures it, from the
moment `room-page` shows `data-seq="8"`) her band has her swatch's colour and no
pattern, and the clue bar names her `Ana`.

The bands are read with spec 019's readers and checks (`band_readings`,
`hatched_problems` and `pattern_problems`, which use `first_gradient_argument`,
`is_diagonal` and `is_ink_or_white`: the hatch is ink and white since spec 041),
and the swatch with `swatch_colour`.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import Locator, Page, expect

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
    band_readings,
    cell_at,
    expect_seq,
    grid_from_text,
    hatched_problems,
    load_fr,
    marks_in,
    pattern_problems,
    player_joined_frame,
    player_view,
    swatch_colour,
    turn_switch_on,
    wait_until,
    with_letter_cells,
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
    expect(marks_in(page, 1, 0)).to_have_count(1)
    wait_for_fonts(page)
    return mock


def send_the_seat_back(page: Page, mock: MockRoomSocket) -> None:
    """Send Ana's seat back and wait until the page shows its seq."""
    mock.send(player_joined_frame(SEAT_BACK_SEQ, player_view("p1", "Ana", 0)))
    expect_seq(page, SEAT_BACK_SEQ)


def author_line(page: Page) -> Locator:
    return page.get_by_test_id("clue-bar-author")


def selected_text(name: str) -> str:
    """`t("authors.selected", { name })`, built from `fr.json`."""
    return load_fr()["authors.selected"].replace("{name}", name)


def test_ac7_page_before_the_seat_back_the_past_players_letter_is_hatched(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_bobs_page(page, live_server, fx01_grid)

    expect(marks_in(page, 1, 0)).to_have_attribute("data-colour", "")
    assert hatched_problems(band_readings(page, [(1, 0)])[0]) == []


def test_ac7_page_before_the_seat_back_the_clue_bar_names_someone(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_bobs_page(page, live_server, fx01_grid)

    cell_at(page, 1, 0).click()

    expect(author_line(page)).to_have_text(selected_text(load_fr()["feed.someone"]))


def test_ac7_page_within_300_ms_of_the_seat_back_the_letter_has_her_colour(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_bobs_page(page, live_server, fx01_grid)
    expect(marks_in(page, 1, 0)).to_have_attribute("data-colour", "")

    send_the_seat_back(page, mock)

    expect(marks_in(page, 1, 0)).to_have_attribute(
        "data-colour", "0", timeout=FOLLOW_MS
    )
    reading = band_readings(page, [(1, 0)])[0]
    assert reading.mark_background == swatch_colour(page, "p1")
    assert pattern_problems(reading) == []


def test_ac7_page_after_the_seat_back_the_clue_bar_names_the_player(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_bobs_page(page, live_server, fx01_grid)
    cell_at(page, 1, 0).click()
    expect(author_line(page)).to_have_text(selected_text(load_fr()["feed.someone"]))

    send_the_seat_back(page, mock)
    cell_at(page, 1, 0).click()

    expect(author_line(page)).to_have_text(selected_text("Ana"))
