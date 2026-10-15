"""Tests of spec 015, AC-4: edits to different cells never interfere.

Two Python clients edit different cells at the same time on the real WebSocket;
on the page (mocked socket) a pending edit stays when another cell changes.
Spec 026 adds `grid_full_wrong` events, which take seqs: the 36 edits fill FX-01,
so the WebSocket test counts the one it causes. The shared setup is in
`spec015_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, LetterChanged
from spec015_harness import (
    Edit,
    Peer,
    cell_at,
    errors_received,
    expect_cell,
    grid_from_text,
    grid_of_peer,
    join_peers,
    letter_cells,
    letter_changed_frame,
    make_app,
    make_dist_dir,
    make_registry,
    open_fx01,
    send_edits_together,
    server_grid,
    settled_server_seq,
    type_key,
    wait_with_progress,
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
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-4: edits to different cells never interfere --------------------------


def test_ac4_two_clients_editing_different_cells_at_once_lose_nothing(
    registry: RoomRegistry, client: TestClient, room_code: str, fx01_grid: Grid
) -> None:
    cells = letter_cells(fx01_grid)
    assert len(cells) == 18
    plan_a: list[Edit] = []
    plan_b: list[Edit] = []
    for row, column in cells:
        plan_a.append(EditLetter(row=row, column=column, letter="A"))
    for row, column in reversed(cells):
        plan_b.append(EditLetter(row=row, column=column, letter="B"))
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        send_edits_together([peer_a, peer_b], [plan_a, plan_b])
        wait_with_progress(
            [peer_a, peer_b],
            lambda: all(len(letter_events(peer)) >= 36 for peer in (peer_a, peer_b)),
            "36 letter_changed events on both clients",
        )
        final_seq = settled_server_seq(registry, room_code)
        wait_with_progress(
            [peer_a, peer_b],
            lambda: all(peer.last_seq() >= final_seq for peer in (peer_a, peer_b)),
            "both clients to receive the last seq",
        )

        events_a = letter_events(peer_a)
        events_b = letter_events(peer_b)
        assert events_a == events_b
        assert len(events_a) == 36
        assert errors_received(peer_a) == []
        assert errors_received(peer_b) == []
        a_cells: list[tuple[int, int]] = []
        b_cells: list[tuple[int, int]] = []
        last_letter: dict[tuple[int, int], str | None] = {}
        for event in sorted(events_a, key=lambda event: event.seq):
            position = (event.row, event.column)
            last_letter[position] = event.letter
            if event.player_id == peer_a.you():
                assert event.letter == "A"
                a_cells.append(position)
            else:
                assert event.player_id == peer_b.you()
                assert event.letter == "B"
                b_cells.append(position)
        # Each sender's own edits were applied in the order it sent them.
        assert a_cells == cells
        assert b_cells == list(reversed(cells))
        expected_grid = server_grid(registry, room_code)
        for position in cells:
            assert expected_grid[position][0] == last_letter[position]
        assert grid_of_peer(peer_a) == expected_grid
        assert grid_of_peer(peer_b) == expected_grid
        state = registry.room_state(room_code)
        assert state is not None
        # The grid becomes full once, with wrong letters: one `grid_full_wrong`.
        assert state.seq == 2 + 36 + 1
        assert peer_a.full_wrong_seqs() == peer_b.full_wrong_seqs()
        assert len(peer_a.full_wrong_seqs()) == 1


def letter_events(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.events():
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def test_ac4_a_pending_edit_stays_when_another_cell_changes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, seq=5)
    cell_at(page, 1, 0).click()
    type_key(page, "t")
    expect_cell(page, 1, 0, "T", unconfirmed=True)

    mock.send(letter_changed_frame(6, 1, 1, "A", "p2"))

    expect_cell(page, 1, 1, "A", unconfirmed=False, author="p2")
    expect_cell(page, 1, 0, "T", unconfirmed=True)
