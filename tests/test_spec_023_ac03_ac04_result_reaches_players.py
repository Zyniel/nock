"""Tests of spec 023, AC-3 and AC-4: the result reaches every player.

AC-3: the result reaches all players, and a later joiner sees it (the real
WebSocket). AC-4: every player sees the strike and the lock (two browsers on the
live server). The shared setup is in `spec023_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    Check,
    CheckResult,
    EditLetter,
    GridTarget,
    Join,
)
from nock.room import RoomConfig
from nock.server import create_app
from spec023_harness import (
    TAMIS,
    EnterRoom,
    cell_at,
    connect,
    grid_from_text,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    play_ana_checks_the_word,
    refs,
    snapshot_cell,
    strike_through,
)

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1."""
    return make_catalogue(fx01_grid)


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
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


# ---- AC-3: the result reaches all players, and a later joiner sees it ----


def test_ac3_websocket_both_players_get_the_result_then_the_lock(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.send(EditLetter(row=1, column=1, letter="X"))
        ana.wait_for_seq(4, "the two letters on Ana")
        bob.wait_for_seq(4, "the two letters on Bob")

        ana.send_text(
            '{"type": "check", "target": {"scope": "word", "row": 0, '
            '"column": 0, "clue_index": 0}}'
        )

        for peer in (ana, bob):
            peer.wait_for_seq(6, f"the check events on {peer.name}")
            assert peer.errors() == []
            assert peer.check_results() == [
                CheckResult(
                    seq=5,
                    player_id=ana.you(),
                    target=TAMIS,
                    correct=refs((1, 0)),
                    wrong=refs((1, 1)),
                )
            ]
            assert peer.cell_locks() == [
                CellLocked(seq=6, row=1, column=0, letter="T", revealed=False)
            ]
            tail = peer.messages()[-2:]
            assert [message.type for message in tail] == ["check_result", "cell_locked"]


def test_ac3_websocket_a_later_joiner_sees_the_lock_and_the_strike(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send(EditLetter(row=1, column=0, letter="T"))
        ana.send(EditLetter(row=1, column=1, letter="X"))
        ana.send(Check(target=TAMIS))
        bob.wait_for_seq(6, "the check events on Bob")

        cy = connect(stack, client, room_code, "Cy")
        cy.send(Join(nickname="Cy", resume_token=None))
        cy.wait_for_messages(1, "the snapshot of Cy")

        snapshot = cy.snapshot()
        locked = snapshot_cell(snapshot, 1, 0)
        assert (locked.letter, locked.locked, locked.wrong) == ("T", True, False)
        struck = snapshot_cell(snapshot, 1, 1)
        assert (struck.letter, struck.locked, struck.wrong) == ("X", False, True)


def test_ac3_websocket_a_check_does_not_use_the_edit_rate_limit(
    fx01_grid: Grid, dist_dir: Path, catalogue: Catalogue
) -> None:
    # The default edit limit (20 a second) is under the 30 checks sent at once;
    # the hint limit (`hints.md` rule 2) is raised to let all of them apply.
    config = RoomConfig(silence_timeout_seconds=600, hint_limit=30)
    limited_registry = RoomRegistry(config=config)
    code = limited_registry.register_room(fx01_grid)
    app = create_app(rooms=limited_registry, dist_dir=dist_dir, catalogue=catalogue)
    with (
        contextlib.closing(limited_registry),
        TestClient(app) as limited_client,
        contextlib.ExitStack() as stack,
    ):
        (ana,) = join_peers(stack, limited_client, code, ["Ana"])
        for _ in range(30):
            ana.send(Check(target=GridTarget()))
        ana.wait_for_seq(31, "thirty empty checks")

        assert ana.errors() == []
        assert len(ana.check_results()) == 30
        assert ana.cell_locks() == []


# ---- AC-4: every player sees the strike and the lock (live server) ----


def test_ac4_both_pages_show_the_strike_and_the_lock(
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
        play_ana_checks_the_word(page, bob_page, f"{live_server}/r/{code}", enter_room)

        for watcher in (page, bob_page):
            struck = cell_at(watcher, 1, 1)
            expect(struck).to_have_attribute("data-wrong", "true")
            assert "line-through" in strike_through(struck)
            locked = cell_at(watcher, 1, 0)
            expect(locked).to_have_attribute("data-locked", "true")
            expect(locked).to_have_attribute("data-wrong", "false")
            expect(locked).to_have_attribute("data-letter", "T")
    finally:
        bob_context.close()
