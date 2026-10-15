"""Tests of spec 016, AC-3: a locked cell refuses edits.

Checked on `handle_message`, on the real WebSocket and on the page with a mocked
socket. The shared setup is in `spec016_harness`.

Locked cells are seeded the way the spec says: `registry.add_room(state)` with a
locked cell, a snapshot with a locked cell, or a mocked `cell_locked` event.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    parse_client_message,
)
from nock.room import CellState, RoomState, handle_message, new_room
from spec016_harness import (
    NOW,
    ROOM_CODE,
    SETTLE_MS,
    START_TIME,
    Edit,
    MockRoomSocket,
    cell_at,
    cell_locked_frame,
    cell_state,
    default_players,
    expect_letter,
    grid_from_text,
    join_peers,
    make_app,
    make_dist_dir,
    make_registry,
    open_fx01,
    two_player_room,
    view_cell,
)

# ---- Fixtures ---------------------------------------------------------------


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
def client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- Helpers of the locked cell tests ------------------------------------------


def with_cell(state: RoomState, changed: CellState) -> RoomState:
    cells: list[CellState] = []
    for cell in state.cells:
        if (cell.row, cell.column) == (changed.row, changed.column):
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def locked_cell(
    author: str | None = "p2", revealed: bool = False, changed_by: str | None = "p2"
) -> CellState:
    """The cell (1, 2) holding `M`, locked."""
    return CellState(
        row=1,
        column=2,
        letter="M",
        author=author,
        locked=True,
        revealed=revealed,
        changed_seq=2,
        changed_by=changed_by,
    )


def room_with_locked_cell(grid: Grid) -> RoomState:
    return with_cell(two_player_room(grid), locked_cell())


def sent_edits(mock: MockRoomSocket) -> list[Edit]:
    edits: list[Edit] = []
    for frame in mock.received:
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | Erase):
            edits.append(message)
    return edits


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


# ---- AC-3: a locked cell refuses edits (Python) ------------------------------------

LOCKED_EDITS: list[Edit] = [
    EditLetter(row=1, column=2, letter="X"),
    EditLetter(row=1, column=2, letter="M"),
    Erase(row=1, column=2),
]


@pytest.mark.parametrize("player_id", ["p1", "p2"])
@pytest.mark.parametrize(
    "edit", LOCKED_EDITS, ids=["other-letter", "same-letter", "erase"]
)
def test_ac3_python_a_locked_cell_refuses_the_edit_and_nothing_changes(
    fx01_grid: Grid, edit: Edit, player_id: str
) -> None:
    before = room_with_locked_cell(fx01_grid)

    outcome = handle_message(before, player_id, edit, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED
    assert outcome.to_others == ()
    assert outcome.disconnects == ()
    assert outcome.close_sender is False


@pytest.mark.parametrize(
    "edit", LOCKED_EDITS, ids=["other-letter", "same-letter", "erase"]
)
def test_ac3_python_a_revealed_locked_cell_without_author_refuses_edits(
    fx01_grid: Grid, edit: Edit
) -> None:
    before = with_cell(
        two_player_room(fx01_grid),
        locked_cell(author=None, revealed=True, changed_by=None),
    )

    outcome = handle_message(before, "p1", edit, NOW)

    assert outcome.state == before
    assert outcome.entries == ()
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


def test_ac3_python_the_neighbour_of_a_locked_cell_still_accepts_edits(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid)

    outcome = handle_message(before, "p1", EditLetter(row=1, column=1, letter="X"), NOW)

    assert outcome.reply == ()
    assert outcome.state.seq == 3
    assert cell_state(outcome.state, 1, 1).letter == "X"
    assert cell_state(outcome.state, 1, 2) == locked_cell()


def test_ac3_python_a_locked_cell_is_refused_before_the_stale_edit_check(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid)
    edit = EditLetter(row=1, column=2, letter="X", base_seq=0)

    outcome = handle_message(before, "p1", edit, NOW)

    assert outcome.state == before
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


def test_ac3_python_a_locked_cell_is_refused_before_the_solved_check(
    fx01_grid: Grid,
) -> None:
    before = room_with_locked_cell(fx01_grid).model_copy(update={"solved": True})

    outcome = handle_message(before, "p1", Erase(row=1, column=2), NOW)

    assert outcome.state == before
    assert len(outcome.reply) == 1
    refusal = outcome.reply[0]
    assert isinstance(refusal, ErrorMessage)
    assert refusal.code is ErrorCode.CELL_LOCKED


# ---- AC-3: a locked cell refuses edits (WebSocket) ----------------------------------


def test_ac3_websocket_both_players_are_refused_on_a_locked_cell(
    registry: RoomRegistry, client: TestClient, fx01_grid: Grid
) -> None:
    registry.add_room(
        with_cell(new_room(ROOM_CODE, fx01_grid, START_TIME), locked_cell())
    )
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, ROOM_CODE, ["Ana", "Bob"])
        seq_before = peer_a.last_seq()
        assert seq_before == 2
        for peer in (peer_a, peer_b):
            peer.send(EditLetter(row=1, column=2, letter="X"))
            peer.send(Erase(row=1, column=2))
        for peer in (peer_a, peer_b):
            peer.wait_for_errors(2, "two errors")

        state = registry.room_state(ROOM_CODE)
        assert state is not None
        assert state.seq == seq_before
        assert cell_state(state, 1, 2) == locked_cell()

        # An accepted edit afterwards proves no letter_changed came before it.
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        for peer in (peer_a, peer_b):
            peer.wait_for_letter_events(1, "the T edit")

        for peer in (peer_a, peer_b):
            codes = [error.code for error in peer.errors()]
            assert codes == [ErrorCode.CELL_LOCKED, ErrorCode.CELL_LOCKED]
            events = peer.letter_events()
            assert [(event.row, event.column) for event in events] == [(1, 0)]
            assert view_cell(peer, 1, 2) == ("M", "p2")
    final = registry.room_state(ROOM_CODE)
    assert final is not None
    assert cell_state(final, 1, 2) == locked_cell()


# ---- AC-3: a locked cell on the page ------------------------------------------


def test_ac3_browser_cell_locked_shows_the_letter_and_the_lock_over_a_pending_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell = cell_at(page, 1, 2)
    cell.click()
    page.keyboard.press("x")
    expect_letter(page, 1, 2, "X")
    expect(cell).to_have_attribute("data-locked", "false")

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-locked", "true")

    # Typing advanced the selection to (1,3): select the locked cell again.
    cell.click()
    page.keyboard.press("e")
    page.keyboard.press("Backspace")
    page.wait_for_timeout(SETTLE_MS)
    sent = sent_edits(mock)
    assert len(sent) == 1
    assert isinstance(sent[0], EditLetter)
    assert (sent[0].row, sent[0].column, sent[0].letter) == (1, 2, "X")
    expect_letter(page, 1, 2, "M")

    mock.send(error_frame(ErrorCode.CELL_LOCKED))

    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-unconfirmed", "false")
    expect(cell).to_have_attribute("data-locked", "true")


def test_ac3_browser_typing_and_erasing_on_a_locked_cell_of_the_snapshot_send_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "M", "author": "p2", "locked": True})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)
    expect(cell).to_have_attribute("data-locked", "true")
    cell.click()

    page.keyboard.press("e")
    page.keyboard.press("Backspace")
    page.keyboard.press("Delete")
    page.wait_for_timeout(SETTLE_MS)

    assert sent_edits(mock) == []
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-unconfirmed", "false")


def test_ac3_browser_a_revealed_cell_locked_event_clears_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "Q", "author": "p2"})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)
    expect(cell).to_have_attribute("data-author", "p2")

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=True))

    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-author", "")


def test_ac3_browser_a_checked_cell_locked_event_keeps_the_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "M", "author": "p2"})],
        players=default_players(),
    )
    cell = cell_at(page, 1, 2)

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect(cell).to_have_attribute("data-locked", "true")
    expect_letter(page, 1, 2, "M")
    expect(cell).to_have_attribute("data-author", "p2")


def test_ac3_browser_a_cell_locked_event_replaces_a_different_confirmed_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        page,
        live_server,
        fx01_grid,
        changes=[(1, 2, {"letter": "Q", "author": "p2"})],
        players=default_players(),
    )

    mock.send(cell_locked_frame(6, 1, 2, "M", revealed=False))

    expect_letter(page, 1, 2, "M")
    expect(cell_at(page, 1, 2)).to_have_attribute("data-locked", "true")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
