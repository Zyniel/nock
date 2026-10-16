"""Tests of spec 021, AC-1 and AC-2: a flag shows a marker on its clue cell and
adds a line to the activity feed, for every player.

AC-1 on `handle_message`, on the real WebSocket and with two browsers on the live
server; AC-2 with the same two browsers. The edge cases of AC-1 are here too: a
flag is input that wakes an idle player (spec 013), and flags are neither
throttled nor counted as edits by spec 037's rate limit. The shared setup is in
`spec021_harness`.
"""

from __future__ import annotations

import contextlib
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    EditLetter,
    ErrorCode,
    FlagChanged,
    FlagView,
    PlayerState,
    PlayerStateChanged,
)
from nock.room import RoomConfig, handle_message, snapshot_for, tick
from nock.server import create_app
from spec021_harness import (
    IDES,
    IDES_CLUE_TEXT,
    MIME,
    SENT,
    accepted_flag,
    clue_at,
    expect_marker,
    flag_changes,
    flag_of,
    select_word,
    send_flag,
)
from spec024_harness import (
    NOW,
    WAIT_TIMEOUT_MS,
    EnterRoom,
    events_of,
    expect_seq,
    grid_from_text,
    join_one,
    join_peers,
    load_fr,
    make_catalogue,
    make_dist_dir,
    make_registry,
    ping_and_wait,
    player_record,
    refusal_code,
    two_player_room,
)

FLAG_DELAY_SECONDS = 1.0  # "within 1 s" (AC-1)
FLAG_IDES_TEXT = '{"type": "flag", "clue": {"row": 0, "column": 3, "clue_index": 0}}'

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


# ---- AC-1, rule ----


def test_ac1_a_flag_gives_exactly_one_flag_changed_and_no_reply(
    fx01_grid: Grid,
) -> None:
    outcome = send_flag(two_player_room(fx01_grid), "p2", IDES)

    assert events_of(outcome) == [FlagChanged(seq=3, player_id="p2", clue=IDES)]
    assert outcome.reply == ()
    assert outcome.state.seq == 3


def test_ac1_the_flaggers_record_holds_the_clue(fx01_grid: Grid) -> None:
    after = accepted_flag(two_player_room(fx01_grid), "p2", IDES).state

    assert flag_of(after, "p2") == IDES
    assert flag_of(after, "p1") is None


def test_ac1_the_snapshot_of_another_player_lists_the_flag(fx01_grid: Grid) -> None:
    after = accepted_flag(two_player_room(fx01_grid), "p2", IDES).state

    assert snapshot_for(after, "p1").flags == (FlagView(player_id="p2", clue=IDES),)
    assert snapshot_for(after, "p2").flags == (FlagView(player_id="p2", clue=IDES),)


def test_ac1_a_flag_is_input_that_wakes_an_idle_player_first(
    fx01_grid: Grid,
) -> None:
    quiet = RoomConfig(silence_timeout_seconds=3600)
    idle = tick(two_player_room(fx01_grid), NOW + 120, quiet).state
    assert idle.seq == 4
    assert player_record(idle, "p2").state is PlayerState.IDLE

    outcome = accepted_flag(idle, "p2", IDES, NOW + 130)

    assert events_of(outcome) == [
        PlayerStateChanged(seq=5, player_id="p2", state=PlayerState.ACTIVE),
        FlagChanged(seq=6, player_id="p2", clue=IDES),
    ]
    flagger = player_record(outcome.state, "p2")
    assert (flagger.last_input_at, flagger.last_seen_at) == (NOW + 130, NOW + 130)
    assert player_record(outcome.state, "p1").state is PlayerState.IDLE


def test_ac1_flags_are_not_throttled_and_do_not_count_as_edits(
    fx01_grid: Grid,
) -> None:
    one_edit_per_second = RoomConfig(max_edits_per_second=1)
    state = two_player_room(fx01_grid)
    for number, clue in enumerate([IDES, MIME, SENT, IDES, MIME]):
        outcome = send_flag(state, "p2", clue, NOW, one_edit_per_second)
        assert outcome.reply == (), number
        assert events_of(outcome) == [
            FlagChanged(seq=3 + number, player_id="p2", clue=clue)
        ]
        state = outcome.state

    first_edit = EditLetter(row=1, column=0, letter="T")
    edited = handle_message(state, "p2", first_edit, NOW, one_edit_per_second)
    second_edit = EditLetter(row=1, column=1, letter="A")
    throttled = handle_message(
        edited.state, "p2", second_edit, NOW, one_edit_per_second
    )

    assert edited.reply == ()
    assert refusal_code(throttled) is ErrorCode.RATE_LIMITED


# ---- AC-1, WebSocket ----


def test_ac1_websocket_both_players_get_one_flag_changed_with_the_next_seq(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])

        bob.send_text(FLAG_IDES_TEXT)

        for peer in (ana, bob):
            peer.wait_for_seq(3, f"Bob's flag on {peer.name}")
            ping_and_wait(peer)
            assert peer.errors() == []
            assert flag_changes(peer) == [
                FlagChanged(seq=3, player_id=bob.you(), clue=IDES)
            ]


def test_ac1_websocket_a_later_joiner_gets_the_flag_in_its_snapshot(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        bob.send_text(FLAG_IDES_TEXT)
        ana.wait_for_seq(3, "Bob's flag on Ana")

        cy = join_one(stack, client, room_code, "Cy")

        assert cy.snapshot().flags == (FlagView(player_id=bob.you(), clue=IDES),)


# ---- AC-1 and AC-2, two browsers on the live server ----


def bob_flags_ides(page: Page, bob_page: Page, url: str, enter_room: EnterRoom) -> str:
    """Ana and Bob join; Bob taps the clue of (0, 3) and clicks `flag-button`.

    Returns:
        Bob's player id (the `data-you` of his room page).
    """
    enter_room(page, url, "Ana")
    enter_room(bob_page, url, "Bob")
    expect_seq(page, 2)
    expect_seq(bob_page, 2)
    bob_id = bob_page.get_by_test_id("room-page").get_attribute("data-you")
    assert bob_id is not None
    assert bob_id != ""
    select_word(bob_page, IDES)
    bob_page.get_by_test_id("flag-button").click(timeout=WAIT_TIMEOUT_MS)
    return bob_id


def ides_flagged_on(pages: list[Page]) -> bool:
    """Whether the clue of IDES has `data-flagged="true"` on every page."""
    for watcher in pages:
        if clue_at(watcher, IDES).get_attribute("data-flagged") != "true":
            return False
    return True


def test_ac1_browser_both_pages_mark_the_clue_within_one_second(
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
        bob_id = bob_flags_ides(page, bob_page, f"{live_server}/r/{code}", enter_room)
        deadline = time.monotonic() + FLAG_DELAY_SECONDS
        pages = [page, bob_page]
        while not ides_flagged_on(pages) and time.monotonic() < deadline:
            page.wait_for_timeout(50)

        assert ides_flagged_on(pages)
        for watcher in pages:
            expect_marker(watcher, IDES, bob_id, ["Bob"])
        flag_button = bob_page.get_by_test_id("flag-button")
        expect(flag_button).to_have_attribute("aria-pressed", "true")
    finally:
        bob_context.close()


def test_ac2_browser_the_last_feed_line_of_both_pages_is_bobs_flag(
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
        bob_flags_ides(page, bob_page, f"{live_server}/r/{code}", enter_room)

        line = load_fr()["feed.flag"].replace("{name}", "Bob")
        line = line.replace("{clue}", IDES_CLUE_TEXT)
        assert line == "Bob bloque sur « Fatales à César »"
        for watcher in (page, bob_page):
            feed = watcher.get_by_test_id("activity-feed")
            last_item = feed.get_by_test_id("feed-item").last
            expect(last_item).to_have_attribute("data-kind", "flag")
            expect(last_item).to_have_text(line)
    finally:
        bob_context.close()
