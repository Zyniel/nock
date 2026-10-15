"""Tests of spec 016, AC-1: the last edit received wins.

Checked on `handle_message` (arrival order decides), on the real WebSocket with two
racing clients (50 rounds) and on the page with a mocked socket. The shared setup is
in `spec016_harness`.
"""

from __future__ import annotations

import contextlib
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Erase, LetterChanged
from nock.room import handle_message
from spec016_harness import (
    NOW,
    WAIT_SECONDS,
    Edit,
    Peer,
    cell_at,
    cell_state,
    default_players,
    expect_letter,
    grid_from_text,
    join_peers,
    letter_changed_frame,
    make_app,
    make_dist_dir,
    make_registry,
    open_fx01,
    two_player_room,
    view_cell,
)

ROUNDS = 50


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
def client(registry: RoomRegistry, dist_dir: Path) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-1: the last edit received wins (Python) -------------------------------


def test_ac1_python_the_second_edit_received_overwrites_the_first(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=0, letter="B"), NOW
    )

    assert [entry.event.seq for entry in first.entries] == [3]
    assert [entry.event.seq for entry in second.entries] == [4]
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_by, cell.changed_seq) == (
        "B",
        "p2",
        "p2",
        4,
    )


def test_ac1_python_the_other_arrival_order_gives_the_other_winner(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p2", EditLetter(row=1, column=0, letter="B"), NOW)
    second = handle_message(
        first.state, "p1", EditLetter(row=1, column=0, letter="A"), NOW
    )

    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p1", 4)


def test_ac1_python_the_same_letter_twice_gives_two_events_and_the_second_author(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(
        first.state, "p2", EditLetter(row=1, column=0, letter="A"), NOW
    )

    assert second.entries[0].event == LetterChanged(
        seq=4, row=1, column=0, letter="A", pencil=False, player_id="p2"
    )
    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_seq) == ("A", "p2", 4)


def test_ac1_python_an_erase_after_a_letter_leaves_the_cell_empty(
    fx01_grid: Grid,
) -> None:
    state = two_player_room(fx01_grid)

    first = handle_message(state, "p1", EditLetter(row=1, column=0, letter="A"), NOW)
    second = handle_message(first.state, "p2", Erase(row=1, column=0), NOW)

    cell = cell_state(second.state, 1, 0)
    assert (cell.letter, cell.author, cell.changed_by) == (None, None, "p2")


# ---- AC-1: two clients typing in the same cell at once (WebSocket) -------------


def send_at_once(first: tuple[Peer, Edit], second: tuple[Peer, Edit]) -> None:
    """Send one edit from each peer, from two threads released by one barrier."""
    start = threading.Barrier(2, timeout=WAIT_SECONDS)
    problems: list[str] = []

    def run(peer: Peer, edit: Edit) -> None:
        try:
            start.wait()
            peer.send(edit)
        except Exception as error:  # reported by the test thread
            problems.append(repr(error))

    threads: list[threading.Thread] = []
    for peer, edit in (first, second):
        thread = threading.Thread(target=run, args=(peer, edit), daemon=True)
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join(timeout=WAIT_SECONDS)
        assert not thread.is_alive(), "a sender thread did not finish"
    assert problems == []


def test_ac1_websocket_both_clients_see_the_same_order_and_the_last_seq_wins(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        a_id = peer_a.you()
        b_id = peer_b.you()
        for round_index in range(ROUNDS):
            send_at_once(
                (peer_a, EditLetter(row=1, column=0, letter="A")),
                (peer_b, EditLetter(row=1, column=0, letter="B")),
            )
            expected_count = 2 * (round_index + 1)
            for peer in (peer_a, peer_b):
                peer.wait_for_letter_events(
                    expected_count, f"both events of round {round_index}"
                )
            events_a = peer_a.letter_events()[expected_count - 2 : expected_count]
            events_b = peer_b.letter_events()[expected_count - 2 : expected_count]
            assert events_a == events_b
            first, second = events_a
            assert second.seq == first.seq + 1
            assert first.seq == 2 + expected_count - 1
            assert {
                (first.player_id, first.letter),
                (second.player_id, second.letter),
            } == {
                (a_id, "A"),
                (b_id, "B"),
            }

            state = registry.room_state(room_code)
            assert state is not None
            server_cell = cell_state(state, 1, 0)
            assert server_cell.letter == second.letter
            assert server_cell.author == second.player_id
            assert server_cell.changed_seq == second.seq
            assert state.seq == second.seq
            expected_value = (second.letter, second.player_id)
            assert view_cell(peer_a, 1, 0) == expected_value
            assert view_cell(peer_b, 1, 0) == expected_value

        assert peer_a.letter_events() == peer_b.letter_events()
        assert peer_a.errors() == []
        assert peer_b.errors() == []


# ---- AC-1: the page shows the letter of the higher seq ---------------------------


def test_ac1_browser_my_pending_letter_then_the_other_players_later_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))
    mock.send(letter_changed_frame(7, 1, 0, "B", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "B")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "false")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


def test_ac1_browser_my_pending_letter_then_my_later_letter_wins(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    expect_letter(page, 1, 0, "A")

    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "true")
    mock.send(letter_changed_frame(7, 1, 0, "A", "p1"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-unconfirmed", "false")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p1")


def test_ac1_browser_the_same_letter_from_both_shows_the_second_author(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")

    mock.send(letter_changed_frame(6, 1, 0, "A", "p1"))
    mock.send(letter_changed_frame(7, 1, 0, "A", "p2"))

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect_letter(page, 1, 0, "A")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "3")


def test_ac1_browser_my_pending_edit_replaced_by_the_other_flashes_after_my_answer(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, players=default_players())
    cell_at(page, 1, 0).click()
    page.keyboard.press("a")
    mock.send(letter_changed_frame(6, 1, 0, "B", "p2"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "6")
    # The other player replaced nothing of mine yet: my letter is only pending.
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "")

    mock.send(letter_changed_frame(7, 1, 0, "A", "p1"))
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "7")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "")
    mock.send(letter_changed_frame(8, 1, 0, "C", "p3"))

    expect_letter(page, 1, 0, "C")
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "5")
