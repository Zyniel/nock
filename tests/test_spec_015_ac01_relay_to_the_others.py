"""Tests of spec 015, AC-1: a letter typed by one player reaches the others.

The relay of the server is measured on localhost with the real WebSocket (p95 at
most 100 ms) and the browser on localhost (a letter within 300 ms). The shared
setup is in `spec015_harness`.

Spec 026 adds `grid_full_wrong` events, which take seqs: the random run of the
relay test fills FX-01, so that test counts them.
"""

from __future__ import annotations

import contextlib
import random
import string
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Protocol

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, LetterChanged
from spec015_harness import (
    Peer,
    answer_of,
    cell_selector,
    grid_from_text,
    join_peers,
    letter_cells,
    make_app,
    make_dist_dir,
    make_registry,
)

MAX_RELAY_P95_SECONDS = 0.100
RELAY_SAMPLES = 200
P95_INDEX = 189  # the 190th smallest of 200 (spec: "95th percentile")
BROWSER_BUDGET_MS = 300


class EnterRoom(Protocol):
    """The `enter_room` fixture of conftest."""

    def __call__(self, page: Page, url: str, nickname: str = "Ana") -> None: ...


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


# ---- AC-1: relay to the others -----------------------------------------------


def test_ac1_server_relay_p95_is_at_most_100_ms(
    client: TestClient,
    room_code: str,
    fx01_grid: Grid,
    record_property: Callable[[str, object], None],
) -> None:
    """A sends 200 edits one by one; time from A's send to B's receipt of it."""
    cells = letter_cells(fx01_grid)
    rng = random.Random(15)
    edits: list[EditLetter] = []
    sent_at: list[float] = []
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        for index in range(RELAY_SAMPLES):
            row, column = rng.choice(cells)
            letter = rng.choice(string.ascii_uppercase)
            edit = EditLetter(row=row, column=column, letter=letter)
            edits.append(edit)
            sent_at.append(time.monotonic())
            peer_a.send(edit)
            peer_a.wait_until(
                lambda: len(peer_a.answers()) >= len(edits),
                f"the answer to edit {index + 1}",
            )
        a_id = peer_a.you()
        peer_b.wait_until(
            lambda: len(relayed_from(peer_b, a_id)) >= RELAY_SAMPLES,
            "all the letter_changed events on B",
        )
        relayed = relayed_from(peer_b, a_id)
        full_wrong_seqs = peer_b.full_wrong_seqs()

    assert len(relayed) == RELAY_SAMPLES
    first_seq = relayed[0][1].seq
    relay_times: list[float] = []
    for index, (received_at, event) in enumerate(relayed):
        edit = edits[index]
        # A `grid_full_wrong` (spec 026) takes the seq after the edit that fills
        # the grid: the later letter_changed events are shifted by it.
        shift = len([seq for seq in full_wrong_seqs if seq < event.seq])
        assert event.seq == first_seq + index + shift
        assert (event.row, event.column, event.letter) == answer_of(edit)
        assert event.pencil is False
        relay_times.append(received_at - sent_at[index])
    relay_times.sort()
    p95 = relay_times[P95_INDEX]
    record_property("relay_p95_ms", round(p95 * 1000, 2))
    record_property("relay_max_ms", round(relay_times[-1] * 1000, 2))
    print(f"AC-1 relay: p95 {p95 * 1000:.1f} ms, max {relay_times[-1] * 1000:.1f} ms")
    assert p95 <= MAX_RELAY_P95_SECONDS, (
        f"p95 (190th smallest) of {RELAY_SAMPLES} relay times, from A's send_text "
        f"to B's reader getting the matching letter_changed, localhost TestClient: "
        f"{p95 * 1000:.1f} ms, limit 100 ms (max {relay_times[-1] * 1000:.1f} ms)"
    )


def relayed_from(peer: Peer, author_id: str) -> list[tuple[float, LetterChanged]]:
    """The `letter_changed` events of `author_id` on `peer`, with receipt times."""
    found: list[tuple[float, LetterChanged]] = []
    for received_at, message in peer.timed_messages():
        if isinstance(message, LetterChanged) and message.player_id == author_id:
            found.append((received_at, message))
    return found


def test_ac1_the_author_receives_its_own_letter_changed_too(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peer_a, peer_b = join_peers(stack, client, room_code, ["Ana", "Bob"])
        peer_a.send(EditLetter(row=1, column=0, letter="T"))
        peer_a.wait_until(lambda: len(peer_a.answers()) == 1, "A's own answer")
        peer_b.wait_for_seq(3, "B's copy")

        expected = LetterChanged(
            seq=3, row=1, column=0, letter="T", pencil=False, player_id=peer_a.you()
        )
        assert peer_a.answers() == [expected]
        assert peer_b.events()[-1] == expected


def test_ac1_a_letter_typed_by_ana_shows_on_bobs_page_within_300_ms(
    page: Page,
    browser: Browser,
    live_server: str,
    room_registry: RoomRegistry,
    fx01_grid: Grid,
    enter_room: EnterRoom,
) -> None:
    code = room_registry.register_room(fx01_grid)
    url = f"{live_server}/r/{code}"
    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        enter_room(page, url, "Ana")
        enter_room(bob_page, url, "Bob")
        page.locator(cell_selector(1, 0)).click()
        for column, letter in enumerate("TAMIS"):
            page.keyboard.press(letter.lower())
            bob_cell = bob_page.locator(cell_selector(1, column))
            expect(bob_cell).to_have_attribute(
                "data-letter", letter, timeout=BROWSER_BUDGET_MS
            )
    finally:
        bob_context.close()
