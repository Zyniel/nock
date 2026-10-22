"""Tests of spec 026, AC-1 to AC-3: the grid becomes solved.

AC-1 checks the completion rule on `handle_message`. AC-2 uses the real WebSocket
with three simulated clients. AC-3 runs two browsers on the live server. The shared
setup is in `spec026_harness`.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Check,
    EditLetter,
    GridFullWrong,
    GridSolved,
    GridTarget,
    LetterChanged,
    Undo,
)
from nock.room import LogEntry, handle_message, snapshot_for
from spec026_harness import (
    LAST_CELL,
    NOW,
    EnterRoom,
    events_of,
    full17,
    grid_from_text,
    join_peers,
    load_fr,
    make_client,
    make_dist_dir,
    make_registry,
    play_live_game,
    solved_room,
    type_17_letters,
    write,
)
from spec043_harness import expect_status_text

SOLVED_BUDGET_SECONDS = 1.0
SOLVED_BUDGET_MS = 1000

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry whose throttle never refuses and that never times a socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    with make_client(registry, dist_dir) as test_client:
        yield test_client


# ---- AC-1: the last empty cell filled right solves the grid ----


def test_ac1_the_last_right_letter_is_followed_by_grid_solved(fx01_grid: Grid) -> None:
    before = full17(fx01_grid)

    outcome = write(before, "p2", LAST_CELL, "T", NOW + 754.0)

    assert events_of(outcome) == [
        LetterChanged(
            seq=20, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=21, elapsed_ms=754000),
    ]
    assert outcome.state.solved is True
    assert outcome.state.seq == 21


def test_ac1_the_snapshot_of_a_solved_room_says_so(fx01_grid: Grid) -> None:
    state = solved_room(fx01_grid)

    assert snapshot_for(state, "p1").solved is True
    assert snapshot_for(full17(fx01_grid), "p1").solved is False


def test_ac1_the_entries_are_logged_entries_of_the_step(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW + 754.0)

    assert len(outcome.entries) == 2
    for entry in outcome.entries:
        assert isinstance(entry, LogEntry)


@pytest.mark.parametrize(
    ("seconds", "elapsed_ms"),
    [(0.0, 0), (1.2346, 1235), (1.2344, 1234), (3600.0, 3_600_000)],
)
def test_ac1_elapsed_ms_is_the_timer_value_since_the_first_letter_rounded_to_whole_ms(
    fx01_grid: Grid, seconds: float, elapsed_ms: int
) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW + seconds)

    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=elapsed_ms)


def test_ac1_elapsed_ms_is_never_negative(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "T", NOW - 5.0)

    assert events_of(outcome)[-1] == GridSolved(seq=21, elapsed_ms=0)


def test_ac1_an_undo_that_puts_back_the_last_right_letter_completes_the_grid(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p1", (4, 3), "X").state
    state = write(state, "p2", LAST_CELL, "T").state
    assert state.seq == 22
    assert state.solved is False

    outcome = handle_message(state, "p1", Undo(), NOW + 10.0)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(
            seq=23, row=4, column=3, letter="S", pencil=False, player_id="p1"
        ),
        GridSolved(seq=24, elapsed_ms=10000),
    ]
    assert outcome.state.solved is True


def test_ac1_a_grid_whose_cells_are_all_locked_by_checks_is_solved_by_the_last_edit(
    fx01_grid: Grid,
) -> None:
    checked = handle_message(
        full17(fx01_grid), "p1", Check(target=GridTarget()), NOW + 1.0
    )
    assert checked.reply == ()
    assert checked.state.solved is False
    assert checked.state.seq == 19 + 1 + 17
    for entry in checked.entries:
        assert not isinstance(entry.event, GridSolved | GridFullWrong)

    outcome = write(checked.state, "p2", LAST_CELL, "T", NOW + 2.0)

    assert events_of(outcome) == [
        LetterChanged(
            seq=38, row=4, column=4, letter="T", pencil=False, player_id="p2"
        ),
        GridSolved(seq=39, elapsed_ms=2000),
    ]
    assert outcome.state.solved is True


def test_ac1_a_check_of_a_full_wrong_grid_adds_no_completion_entry(
    fx01_grid: Grid,
) -> None:
    full_wrong = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    assert full_wrong.seq == 21

    outcome = handle_message(full_wrong, "p1", Check(target=GridTarget()), NOW + 1.0)

    assert outcome.reply == ()
    for entry in outcome.entries:
        assert not isinstance(entry.event, GridSolved | GridFullWrong)
    assert outcome.state.solved is False


def test_ac1_a_second_grid_solved_is_never_produced(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p1", EditLetter(row=1, column=0, letter="T"), NOW)

    assert outcome.entries == ()
    assert outcome.state.seq == 21


# ---- AC-2: all players learn it within 1 second (WebSocket) ----


def test_ac2_websocket_all_players_get_grid_solved_right_after_the_last_letter(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _ = peers
        type_17_letters(ana, bob, peers)

        sent_at = time.monotonic()
        bob.send(EditLetter(row=4, column=4, letter="T"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_solved on {peer.name}")

        for peer in peers:
            tail = peer.received()[-2:]
            letter_event = tail[0][2]
            solved_event = tail[1][2]
            assert isinstance(letter_event, LetterChanged)
            assert (letter_event.row, letter_event.column) == (4, 4)
            assert letter_event.letter == "T"
            assert letter_event.seq == 3 + 18
            assert isinstance(solved_event, GridSolved)
            assert solved_event.seq == letter_event.seq + 1
            assert solved_event.elapsed_ms >= 0
            for received_at, _, _ in tail:
                assert received_at - sent_at <= SOLVED_BUDGET_SECONDS
            assert peer.errors() == []


# ---- AC-3: every page shows the solved grid (live server) ----


def test_ac3_both_pages_show_the_solved_grid_within_a_second(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        play_live_game(page, bob_page, f"{live_server}/r/{code}", enter_room, "t")

        for watcher in (page, bob_page):
            expect(watcher.get_by_test_id("room-page")).to_have_attribute(
                "data-solved", "true", timeout=SOLVED_BUDGET_MS
            )
            status = watcher.get_by_test_id("grid-status")
            expect(status).to_have_attribute(
                "data-state", "solved", timeout=SOLVED_BUDGET_MS
            )
            expect_status_text(status, load_fr()["completion.solved"])
            expect(status).to_have_attribute("role", "status")
    finally:
        bob_context.close()


def test_ac3_the_solved_text_in_fr_json() -> None:
    assert load_fr()["completion.solved"] == "Grille terminée, bravo !"
