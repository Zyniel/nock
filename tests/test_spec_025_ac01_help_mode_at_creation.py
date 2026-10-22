"""Tests of spec 025, AC-1: the host picks the help mode from the room's start.

The room starts in `free`; the host changes the mode in spec 014's settings form
before anyone else joins (the real WebSocket, then the page opened from the
catalogue with spec 010's one-tap start). The shared setup is in
`spec025_harness`.

Refined by spec 043 (the design's room layout): the settings form is in the
host's settings sheet, and `help-mode-select` is a fieldset of three
`help-mode-option` radios (the checked one is the room's mode); the check panel is
a group of the Aide menu, opened with `open_aide` before it is looked at.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from fonts_ready import wait_for_fonts
from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import ChangeSettings, HelpMode
from nock.server import create_app
from room_panels import open_aide, open_host_settings
from spec010_harness import ROOM_URL_PATTERN
from spec025_harness import (
    FIVE_AND_ONE,
    WAIT_TIMEOUT_MS,
    EnterRoom,
    feed_lines,
    fr_text,
    grid_from_text,
    host_sets_help_mode,
    join_peer,
    make_catalogue,
    make_dist_dir,
    make_registry,
    seed_nickname,
)

JOIN_TIMEOUT_MS = 10_000

# ---- Fixtures ----


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def catalogue(fx01_grid: Grid) -> Catalogue:
    """A catalogue holding FX-01 as published entry 1 (the live server serves it)."""
    return make_catalogue(fx01_grid)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def client(
    registry: RoomRegistry, dist_dir: Path, catalogue: Catalogue
) -> Iterator[TestClient]:
    """One TestClient (one event loop) on an app serving `registry`."""
    app = create_app(rooms=registry, dist_dir=dist_dir, catalogue=catalogue)
    with TestClient(app) as test_client:
        yield test_client


def create_room(client: TestClient) -> str:
    """Create a FX-01 room with `POST /api/rooms` and return its code."""
    response = client.post("/api/rooms", json={"grid_number": 1})
    assert response.status_code == 201, response.text
    code = response.json()["code"]
    assert isinstance(code, str)
    return code


# ---- AC-1: WebSocket ----


def test_ac1_websocket_the_first_joiner_is_the_host_of_a_room_in_free_mode(
    client: TestClient,
) -> None:
    code = create_room(client)
    with contextlib.ExitStack() as stack:
        ana = join_peer(stack, client, code, "Ana")

        snapshot = ana.snapshot()
        assert snapshot.settings.help_mode is HelpMode.FREE
        assert [player.player_id for player in snapshot.players] == [snapshot.you]
        assert snapshot.players[0].is_host is True


def test_ac1_websocket_the_host_sets_vote_then_none_before_the_next_joiners(
    client: TestClient,
) -> None:
    code = create_room(client)
    with contextlib.ExitStack() as stack:
        ana = join_peer(stack, client, code, "Ana")
        ana.send(ChangeSettings(help_mode=HelpMode.VOTE, reveal_budget=FIVE_AND_ONE))
        ana.wait_for_seq(2, "the change to vote")

        bob = join_peer(stack, client, code, "Bob")
        assert bob.snapshot().settings.help_mode is HelpMode.VOTE
        ana.wait_for_seq(3, "Bob's join")

        ana.send(ChangeSettings(help_mode=HelpMode.NONE, reveal_budget=FIVE_AND_ONE))
        ana.wait_for_seq(4, "the change to none")
        cy = join_peer(stack, client, code, "Cy")

        assert cy.snapshot().settings.help_mode is HelpMode.NONE
        assert ana.errors() == []


# ---- AC-1: browser, one-tap start ----


def start_from_catalogue(page: Page, base_url: str) -> None:
    """One click on the `catalogue-play` of item 1, then wait to be joined."""
    page.goto(f"{base_url}/")
    item = page.locator('[data-testid="catalogue-item"][data-number="1"]')
    item.get_by_test_id("catalogue-play").click(timeout=WAIT_TIMEOUT_MS)
    page.wait_for_url(ROOM_URL_PATTERN)
    expect(page.get_by_test_id("room-page")).to_have_attribute(
        "data-status", "joined", timeout=JOIN_TIMEOUT_MS
    )
    wait_for_fonts(page)


def test_ac1_browser_the_creator_finds_free_selected_among_three_modes(
    page: Page, live_server: str
) -> None:
    seed_nickname(page, "Ana")

    start_from_catalogue(page, live_server)

    roster = page.get_by_test_id("roster-player")
    expect(roster).to_have_count(1)
    expect(roster).to_have_attribute("data-host", "true")
    open_host_settings(page)  # spec 043: the modes are in the host's settings sheet
    select = page.get_by_test_id("help-mode-select")
    options = select.get_by_test_id("help-mode-option")
    expect(options).to_have_count(3)
    for index, mode in enumerate(["free", "vote", "none"]):
        expect(options.nth(index)).to_have_attribute("value", mode)
        expect(options.nth(index)).to_have_accessible_name(
            fr_text(f"settings.help_mode.{mode}")
        )
    expect(options.nth(0)).to_be_checked()


def test_ac1_browser_none_chosen_before_anyone_joins_hides_both_help_panels(
    page: Page,
    browser: Browser,
    live_server: str,
    enter_room: EnterRoom,
) -> None:
    seed_nickname(page, "Ana")
    start_from_catalogue(page, live_server)
    open_aide(page)
    expect(page.get_by_test_id("check-panel")).to_be_visible()

    host_sets_help_mode(page, "none")
    expect(feed_lines(page, "settings_changed")).to_have_count(1)

    bob_context = browser.new_context()
    try:
        bob_page = bob_context.new_page()
        enter_room(bob_page, page.url, "Bob")
        for watcher in (page, bob_page):
            expect(watcher.get_by_test_id("roster-player")).to_have_count(2)
            expect(watcher.get_by_test_id("undo-button")).to_be_visible()
            expect(watcher.get_by_test_id("check-panel")).to_have_count(0)
            expect(watcher.get_by_test_id("reveal-panel")).to_have_count(0)
    finally:
        bob_context.close()
