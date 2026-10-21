"""Tests of spec 018, AC-2: a player joining mid-game.

The real WebSocket with two writer threads sending edits while a third client
joins, on a live room and on a room loaded from the store after a simulated
restart. The shared setup is in `spec018_harness`.
"""

from __future__ import annotations

import contextlib
import random
import string
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Erase, ErrorMessage, PlayerJoined, Snapshot
from spec018_harness import (
    OVERALL_SECONDS,
    POLL_SECONDS,
    SERVER_CONFIG,
    WAIT_SECONDS,
    Peer,
    Process,
    grid_from_text,
    grid_of_peer,
    join_peers,
    letter_cells,
    make_app,
    make_dist_dir,
    make_registry,
    open_peer,
    players_all_disconnected,
    server_grid,
    wait_for,
)

SETTLE_SECONDS = 0.5
EDITS_PER_WRITER = 200

Edit = EditLetter | Erase


# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry (default in-memory store) whose throttle never refuses."""
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


# ---- Helpers for the WebSocket tests ----


def settled_server_seq(server: RoomRegistry, code: str) -> int:
    """Return the room's seq once it has not moved for SETTLE_SECONDS."""
    last_seq = -1
    unchanged_since = time.monotonic()
    deadline = unchanged_since + OVERALL_SECONDS
    while time.monotonic() < deadline:
        state = server.room_state(code)
        assert state is not None
        now = time.monotonic()
        if state.seq != last_seq:
            last_seq = state.seq
            unchanged_since = now
        elif now - unchanged_since >= SETTLE_SECONDS:
            return state.seq
        time.sleep(POLL_SECONDS)
    pytest.fail("the room's seq never stopped moving")


def random_plan(
    rng: random.Random, cells: list[tuple[int, int]], count: int
) -> list[Edit]:
    """`count` random edits: 90 % letters A to Z, 10 % erases."""
    edits: list[Edit] = []
    for _ in range(count):
        row, column = rng.choice(cells)
        if rng.random() < 0.1:
            edits.append(Erase(row=row, column=column))
        else:
            letter = rng.choice(string.ascii_uppercase)
            edits.append(EditLetter(row=row, column=column, letter=letter))
    return edits


class Senders:
    """Writer threads: each sends its peer's plan, all released together."""

    def __init__(self, peers: list[Peer], plans: list[list[Edit]]) -> None:
        self._start = threading.Barrier(len(peers), timeout=WAIT_SECONDS)
        self._problems: list[str] = []
        self._threads: list[threading.Thread] = []
        for peer, plan in zip(peers, plans, strict=True):
            thread = threading.Thread(target=self._run, args=(peer, plan), daemon=True)
            self._threads.append(thread)

    def _run(self, peer: Peer, plan: list[Edit]) -> None:
        try:
            self._start.wait()
            for edit in plan:
                peer.send(edit)
        except Exception as error:  # reported by the test thread
            self._problems.append(repr(error))

    def start(self) -> None:
        for thread in self._threads:
            thread.start()

    def finish(self) -> None:
        for thread in self._threads:
            thread.join(timeout=OVERALL_SECONDS)
            assert not thread.is_alive(), "a sender thread did not finish"
        assert self._problems == []


# ---- AC-2: a player joining mid-game ----


def check_mid_game_joiner(
    server: RoomRegistry, code: str, joiner: Peer, floor: int
) -> None:
    """Check what the joiner got: a snapshot, then every event once, in order."""
    final_seq = settled_server_seq(server, code)
    joiner.wait_for_seq(final_seq, "the joiner to receive the last seq")

    first = joiner.messages()[0]
    assert isinstance(first, Snapshot)
    snapshot_seq = first.seq
    assert snapshot_seq > floor
    seqs: list[int] = []
    for message in joiner.events():
        assert not isinstance(message, Snapshot)
        assert not isinstance(message, ErrorMessage), message
        seq = getattr(message, "seq", None)
        if isinstance(seq, int):
            seqs.append(seq)
    assert seqs == list(range(snapshot_seq + 1, final_seq + 1))
    assert grid_of_peer(joiner) == server_grid(server, code)
    for message in joiner.events():
        assert not (
            isinstance(message, PlayerJoined)
            and message.player.player_id == joiner.you()
        )
    assert joiner.failures() == []


def test_ac2_websocket_a_joiner_gets_a_snapshot_then_every_event_without_a_gap(
    registry: RoomRegistry,
    client: TestClient,
    room_code: str,
    fx01_grid: Grid,
) -> None:
    cells = letter_cells(fx01_grid)[:-1]  # never full
    rng = random.Random(182)
    plans = [random_plan(rng, cells, EDITS_PER_WRITER) for _ in range(2)]
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        senders = Senders([ana, bob], plans)
        senders.start()
        wait_for(
            lambda: (registry.room_state(room_code) or pytest.fail("room")).seq > 50,
            "the room to pass seq 50",
        )

        cy = open_peer(stack, client, room_code, "Cy")
        senders.finish()

        check_mid_game_joiner(registry, room_code, cy, floor=50)
        final = registry.room_state(room_code)
        assert final is not None
        assert final.seq == 2 + 2 * EDITS_PER_WRITER + 1
        assert [player.nickname for player in final.players] == ["ANA", "BOB", "CY"]


def test_ac2_websocket_the_joiner_does_not_receive_its_own_player_joined(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        cy = open_peer(stack, client, room_code, "Cy")
        ana.send(EditLetter(row=1, column=0, letter="T"))
        cy.wait_for_seq(4, "the letter after the join")
        ana.wait_for_seq(4, "the letter after the join")
        bob.wait_for_seq(4, "the letter after the join")

        assert cy.snapshot().seq == 3
        assert [player.nickname for player in cy.snapshot().players] == [
            "ANA",
            "BOB",
            "CY",
        ]
        assert [type(message).__name__ for message in cy.events()] == ["LetterChanged"]
        # Bob, who was in the room already, did receive Cy's join, as event 3.
        joins = [m for m in bob.events() if isinstance(m, PlayerJoined)]
        assert [event.seq for event in joins] == [3]


def test_ac2_websocket_the_same_holds_for_a_room_loaded_after_a_restart(
    tmp_path: Path, dist_dir: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    cells = letter_cells(fx01_grid)[:-1]  # never full
    rng = random.Random(183)
    with contextlib.ExitStack() as cleanup:
        one = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(one.shutdown)
        code = one.registry.register_room(fx01_grid)
        first_run = cleanup.enter_context(contextlib.ExitStack())
        first_client = first_run.enter_context(TestClient(one.app))
        ana = open_peer(first_run, first_client, code, "Ana")
        bob = open_peer(first_run, first_client, code, "Bob")
        bob.wait_for_seq(2, "both joins")
        ana_token = ana.snapshot().resume_token
        bob_token = bob.snapshot().resume_token
        before = Senders(
            [ana, bob], [random_plan(rng, cells, 30), random_plan(rng, cells, 30)]
        )
        before.start()
        before.finish()
        settled_server_seq(one.registry, code)
        first_run.close()
        wait_for(lambda: players_all_disconnected(one, code), "both players logged out")

        two = Process(path, dist_dir, SERVER_CONFIG)
        cleanup.callback(two.shutdown)
        second_run = cleanup.enter_context(contextlib.ExitStack())
        second_client = second_run.enter_context(TestClient(two.app))
        ana_again = open_peer(second_run, second_client, code, "Ana", ana_token)
        bob_again = open_peer(second_run, second_client, code, "Bob", bob_token)
        baseline = settled_server_seq(two.registry, code)
        plans = [random_plan(rng, cells, 100), random_plan(rng, cells, 100)]
        senders = Senders([ana_again, bob_again], plans)
        senders.start()
        wait_for(
            lambda: (two.registry.room_state(code) or pytest.fail("room")).seq
            > baseline + 20,
            "the loaded room to move on",
        )

        cy = open_peer(second_run, second_client, code, "Cy")
        senders.finish()

        check_mid_game_joiner(two.registry, code, cy, floor=baseline + 20)
        final = two.registry.room_state(code)
        assert final is not None
        assert final.seq == baseline + 200 + 1
