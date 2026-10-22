"""Tests of spec 025, AC-2: in vote mode, a reveal or a grid check needs a majority.

The rule on `handle_message` (the room `V3` and rooms of 2 to 8 players), the real
WebSocket, two browsers on the live server, and the activity feed on a page with a
mocked socket (votes add no line; a passed vote's reveal names its requester). The
shared setup is in `spec025_harness`.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    CheckResult,
    Direction,
    GridSolved,
    GridTarget,
    LeaveReason,
    PlayerLeft,
    PlayerState,
    RemovePlayer,
    Reveal,
    RevealBudget,
    RevealResult,
    SelectCell,
    Vote,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
)
from nock.room import RoomConfig
from nock.server import create_app
from room_panels import open_aide
from spec025_harness import (
    FIVE_AND_ONE,
    GRID_CHECK,
    NOW,
    REVEAL_1_0,
    EnterRoom,
    MockRoomSocket,
    all_but_last_cell,
    cell_at,
    closed,
    events_of,
    feed_lines,
    fr_text,
    grid_from_text,
    host_sets_help_mode,
    join_peers,
    last_vote_id_of,
    make_catalogue,
    make_dist_dir,
    make_registry,
    open_room,
    open_vote,
    open_vote_of,
    opened,
    set_vote_mode,
    settle,
    v3,
    vote_room,
    vote_timeout_of,
    write,
)

WITHIN_MS = 1000  # "within 1 s"
FOUR_AND_ONE = RevealBudget(letters=4, words=1)

# The numbered events the feed tests send to the page.
FeedTestEvent = VoteOpened | VoteClosed | RevealResult | CellLocked | PlayerLeft

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


def feed_items(page: Page) -> Locator:
    """Every line of the activity feed (spec 013)."""
    return page.get_by_test_id("activity-feed").get_by_test_id("feed-item")


def send_event(page: Page, mock: MockRoomSocket, event: FeedTestEvent) -> None:
    """Have the mocked socket send a numbered event; return once it is applied."""
    mock.send(event.model_dump_json())
    expected_seq = str(event.seq)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", expected_seq)


def reveal_of_1_0_event(seq: int, requester: str) -> RevealResult:
    """The `reveal_result` of a passed vote on the reveal of (1, 0), budget 5/1."""
    return RevealResult(
        seq=seq,
        player_id=requester,
        target=CellTarget(row=1, column=0),
        reveal_budget=FOUR_AND_ONE,
    )


def reveal_of_1_0_applied(first_seq: int, requester: str) -> list[object]:
    """The `reveal_result` and `cell_locked` of the reveal of (1, 0), budget 5/1."""
    return [
        reveal_of_1_0_event(first_seq, requester),
        CellLocked(seq=first_seq + 1, row=1, column=0, letter="T", revealed=True),
    ]


# ---- AC-2: the rule ----


def test_ac2_the_default_vote_timeout_is_20_seconds() -> None:
    assert vote_timeout_of(RoomConfig()) == 20


def test_ac2_a_reveal_in_vote_mode_opens_a_vote_and_changes_nothing_else(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    before = play.state

    outcome = play.send("p1", REVEAL_1_0)

    opening = opened(5, 1, "p1", REVEAL_1_0, 3)
    assert events_of(outcome) == [opening]
    assert outcome.reply == ()
    assert play.state.seq == 5
    assert play.state.cells == before.cells
    assert play.state.reveal_budget == FIVE_AND_ONE
    assert play.state.settings == before.settings
    expected = open_vote(opening, NOW, ("p1", "p2", "p3"), ("p1",))
    assert open_vote_of(play.state) == expected
    assert last_vote_id_of(play.state) == 1


def test_ac2_a_second_yes_of_three_within_the_time_passes_and_applies_the_reveal(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    play.send("p1", REVEAL_1_0)

    outcome = play.send("p2", Vote(vote_id=1, yes=True), NOW + 19.9)

    assert events_of(outcome) == [
        closed(6, 1, VoteOutcome.PASSED, 2, 3),
        *reveal_of_1_0_applied(7, "p1"),
    ]
    assert outcome.reply == ()
    assert open_vote_of(play.state) is None
    assert play.state.seq == 8
    assert play.state.reveal_budget == FOUR_AND_ONE
    revealed = play.state.cells[1]
    assert (revealed.row, revealed.column) == (1, 0)
    assert (revealed.letter, revealed.locked, revealed.revealed) == ("T", True, True)


def test_ac2_a_grid_check_is_voted_the_same_way_and_names_its_requester(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    write(play, "p1", [(1, 0, "T"), (1, 1, "X")])
    cells_before = play.state.cells

    opening = play.send("p2", GRID_CHECK)

    assert events_of(opening) == [opened(7, 1, "p2", GRID_CHECK, 3)]
    assert play.state.cells == cells_before

    deciding = play.send("p3", Vote(vote_id=1, yes=True))

    assert events_of(deciding) == [
        closed(8, 1, VoteOutcome.PASSED, 2, 3),
        CheckResult(
            seq=9,
            player_id="p2",
            target=GridTarget(),
            correct=(CellRef(row=1, column=0),),
            wrong=(CellRef(row=1, column=1),),
        ),
        CellLocked(seq=10, row=1, column=0, letter="T", revealed=False),
    ]
    assert open_vote_of(play.state) is None


@pytest.mark.parametrize(
    ("count", "needed"),
    [(2, 2), (3, 2), (4, 3), (8, 5)],
    ids=["2-need-2", "3-need-2", "4-need-3", "8-need-5"],
)
def test_ac2_the_majority_is_more_than_half_of_the_players_connected_at_the_opening(
    fx01_grid: Grid, count: int, needed: int
) -> None:
    play = vote_room(fx01_grid, count)
    opening = play.send("p1", REVEAL_1_0)
    assert events_of(opening) == [opened(count + 2, 1, "p1", REVEAL_1_0, count)]

    for number in range(2, needed):
        ballot = play.send(f"p{number}", Vote(vote_id=1, yes=True))
        assert ballot.entries == (), f"the vote closed with {number} yes of {count}"
        assert ballot.reply == ()
    deciding = play.send(f"p{needed}", Vote(vote_id=1, yes=True))

    assert events_of(deciding) == [
        closed(count + 3, 1, VoteOutcome.PASSED, needed, count),
        *reveal_of_1_0_applied(count + 4, "p1"),
    ]


def test_ac2_a_disconnected_player_is_not_eligible_and_an_idle_one_is(
    fx01_grid: Grid,
) -> None:
    play = vote_room(fx01_grid, 4)
    select = SelectCell(row=1, column=0, direction=Direction.ACROSS)
    play.send("p1", select, NOW + 100.0)
    play.tick(NOW + 120.0)
    play.disconnect("p3", NOW + 121.0)
    states = [player.state for player in play.state.players]
    assert states == [
        PlayerState.ACTIVE,
        PlayerState.IDLE,
        PlayerState.DISCONNECTED,
        PlayerState.IDLE,
    ]
    seq = play.state.seq

    outcome = play.send("p1", REVEAL_1_0, NOW + 122.0)

    opening = opened(seq + 1, 1, "p1", REVEAL_1_0, 3)
    assert events_of(outcome) == [opening]
    expected = open_vote(opening, NOW + 122.0, ("p1", "p2", "p4"), ("p1",))
    assert open_vote_of(play.state) == expected


def test_ac2_a_voter_who_is_removed_keeps_the_ballot_they_cast(fx01_grid: Grid) -> None:
    play = vote_room(fx01_grid, 4)
    opening = play.send("p1", REVEAL_1_0)
    assert events_of(opening) == [opened(6, 1, "p1", REVEAL_1_0, 4)]
    assert play.send("p2", Vote(vote_id=1, yes=True)).entries == ()
    removal = play.send("p1", RemovePlayer(player_id="p2"))
    assert events_of(removal) == [
        PlayerLeft(seq=7, player_id="p2", reason=LeaveReason.REMOVED)
    ]

    deciding = play.send("p3", Vote(vote_id=1, yes=True))

    assert events_of(deciding) == [
        closed(8, 1, VoteOutcome.PASSED, 3, 4),
        *reveal_of_1_0_applied(9, "p1"),
    ]


def test_ac2_the_vote_goes_on_when_its_requester_leaves_and_the_result_names_them(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    opening = play.send("p2", REVEAL_1_0)
    assert events_of(opening) == [opened(5, 1, "p2", REVEAL_1_0, 3)]
    vote_before = open_vote_of(play.state)
    removal = play.send("p1", RemovePlayer(player_id="p2"))
    assert events_of(removal) == [
        PlayerLeft(seq=6, player_id="p2", reason=LeaveReason.REMOVED)
    ]
    assert open_vote_of(play.state) == vote_before

    deciding = play.send("p3", Vote(vote_id=1, yes=True))

    assert events_of(deciding) == [
        closed(7, 1, VoteOutcome.PASSED, 2, 3),
        *reveal_of_1_0_applied(8, "p2"),
    ]


def test_ac2_a_passed_reveal_that_fills_the_grid_is_followed_by_grid_solved(
    fx01_grid: Grid,
) -> None:
    play = v3(fx01_grid)
    write(play, "p1", all_but_last_cell())
    assert play.state.seq == 21
    last_cell = Reveal(target=CellTarget(row=4, column=4))
    assert events_of(play.send("p1", last_cell)) == [opened(22, 1, "p1", last_cell, 3)]

    deciding = play.send("p2", Vote(vote_id=1, yes=True), NOW + 5.0)

    events = events_of(deciding)
    assert events[:3] == [
        closed(23, 1, VoteOutcome.PASSED, 2, 3),
        RevealResult(
            seq=24,
            player_id="p1",
            target=CellTarget(row=4, column=4),
            reveal_budget=FOUR_AND_ONE,
        ),
        CellLocked(seq=25, row=4, column=4, letter="T", revealed=True),
    ]
    assert len(events) == 4
    # Its `elapsed_ms` is spec 026's (and spec 027 changes it), not this spec's.
    solved_event = events[3]
    assert isinstance(solved_event, GridSolved)
    assert solved_event.seq == 26
    assert play.state.solved is True


# ---- AC-2: WebSocket ----


def test_ac2_websocket_one_yes_of_three_passes_and_the_reveal_reaches_everyone(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _cy = peers
        assert set_vote_mode(ana, peers) == 4

        ana.send(REVEAL_1_0)

        opening = opened(5, 1, ana.you(), REVEAL_1_0, 3)
        for peer in peers:
            peer.wait_for_seq(5, "the vote_opened")
            assert peer.numbered_from(5) == [opening]

        bob.send_text('{"type": "vote", "vote_id": 1, "yes": true}')

        expected = [
            closed(6, 1, VoteOutcome.PASSED, 2, 3),
            *reveal_of_1_0_applied(7, ana.you()),
        ]
        for peer in peers:
            peer.wait_for_seq(8, "the end of the vote and the reveal")
            assert peer.numbered_from(6) == expected
            assert peer.errors() == []


# ---- AC-2: browser, live server ----


def test_ac2_browser_bob_votes_yes_and_both_pages_show_the_revealed_letter(
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
        expect(page.get_by_test_id("roster-player")).to_have_count(2)
        host_sets_help_mode(page, "vote")
        expect(feed_lines(bob_page, "settings_changed")).to_have_count(1)
        question = fr_text("vote.question.reveal_letter", name="Ana")
        assert question == "Ana propose de révéler une lettre."

        cell_at(page, 1, 0).click()
        open_aide(page)  # spec 043: the reveal items are in the Aide menu
        page.get_by_test_id("reveal-letter").click()

        for watcher in (page, bob_page):
            banner = watcher.get_by_test_id("vote-banner")
            expect(banner).to_be_visible(timeout=WITHIN_MS)
            expect(banner.get_by_test_id("vote-question")).to_have_text(question)
        expect(page.get_by_test_id("vote-status")).to_have_text(fr_text("vote.waiting"))
        expect(page.get_by_test_id("vote-yes")).to_have_count(0)
        expect(page.get_by_test_id("vote-no")).to_have_count(0)

        bob_page.get_by_test_id("vote-yes").click()

        for watcher in (page, bob_page):
            revealed = cell_at(watcher, 1, 0)
            expect(revealed).to_have_attribute(
                "data-revealed", "true", timeout=WITHIN_MS
            )
            expect(revealed).to_have_attribute("data-letter", "T", timeout=WITHIN_MS)
            expect(watcher.get_by_test_id("reveal-letter-detail")).to_have_text(
                fr_text("reveal.letters_left", count=4), timeout=WITHIN_MS
            )
            expect(watcher.get_by_test_id("vote-result")).to_have_text(
                fr_text("vote.result.passed"), timeout=WITHIN_MS
            )
    finally:
        bob_context.close()


# ---- AC-2: votes and the activity feed (browser with mocked socket) ----


def test_ac2_browser_vote_events_add_no_feed_line(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    items = feed_items(page)
    lines_before = items.count()

    send_event(page, mock, opened(6, 1, "p2", REVEAL_1_0, 3))
    send_event(page, mock, closed(7, 1, VoteOutcome.REJECTED, 1, 3))
    send_event(page, mock, opened(8, 2, "p3", GRID_CHECK, 3))
    send_event(page, mock, closed(9, 2, VoteOutcome.TIMED_OUT, 1, 3))

    expect(page.get_by_test_id("vote-result")).to_have_text(
        fr_text("vote.result.timed_out")
    )
    settle(page)
    expect(items).to_have_count(lines_before)


def test_ac2_browser_a_passed_votes_reveal_line_names_the_requester(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    items = feed_items(page)
    lines_before = items.count()

    send_event(page, mock, opened(6, 1, "p2", REVEAL_1_0, 3))
    send_event(page, mock, closed(7, 1, VoteOutcome.PASSED, 2, 3))
    send_event(page, mock, reveal_of_1_0_event(8, "p2"))
    send_event(
        page, mock, CellLocked(seq=9, row=1, column=0, letter="T", revealed=True)
    )

    expect(items).to_have_count(lines_before + 1)
    reveal_line = feed_lines(page, "reveal")
    expect(reveal_line).to_have_count(1)
    expect(reveal_line).to_have_attribute("data-seq", "8")
    expect(reveal_line).to_have_text(fr_text("feed.reveal.letter", name="Bob"))


def test_ac2_browser_the_reveal_line_names_a_requester_who_left_during_the_vote(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    items = feed_items(page)
    lines_before = items.count()

    send_event(page, mock, opened(6, 1, "p2", REVEAL_1_0, 3))
    removal = PlayerLeft(seq=7, player_id="p2", reason=LeaveReason.REMOVED)
    send_event(page, mock, removal)
    send_event(page, mock, closed(8, 1, VoteOutcome.PASSED, 2, 3))
    send_event(page, mock, reveal_of_1_0_event(9, "p2"))
    send_event(
        page, mock, CellLocked(seq=10, row=1, column=0, letter="T", revealed=True)
    )

    expect(items).to_have_count(lines_before + 2)
    expect(feed_lines(page, "player_removed")).to_have_count(1)
    reveal_line = feed_lines(page, "reveal")
    expect(reveal_line).to_have_count(1)
    expect(reveal_line).to_have_attribute("data-seq", "9")
    expect(reveal_line).to_have_text(fr_text("feed.reveal.letter", name="Bob"))
