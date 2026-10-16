"""Tests of spec 012, AC-2: colours, duplicate nicknames and the roster.

The rules (`join_room` and `player_views`), the real WebSocket and the browser, with
spec 040's mocked socket. The shared setup is in `spec012_harness`.
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
    Direction,
    LeaveReason,
    PlayerJoined,
    PlayerLeft,
    PlayerState,
    PlayerView,
    Selection,
)
from nock.room import (
    PlayerRecord,
    player_views,
)
from spec012_harness import (
    active_view,
    grid_from_text,
    join_as,
    load_fr,
    make_app,
    make_dist_dir,
    make_player,
    make_registry,
    make_state,
    open_mock_room,
    receive_message,
    run_join,
    snapshot_frame,
    submit_form,
    three_players,
)

# ---- Fixtures and helpers ---------------------------------------------------


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


@pytest.fixture
def registry() -> Iterator[RoomRegistry]:
    """A registry that ticks fast and never times a silent socket out."""
    room_registry = make_registry()
    yield room_registry
    room_registry.close()


@pytest.fixture
def room_code(registry: RoomRegistry, fx01_grid: Grid) -> str:
    return registry.register_room(fx01_grid)


@pytest.fixture
def ws_client(
    registry: RoomRegistry, room_code: str, dist_dir: Path
) -> Iterator[TestClient]:
    """One client, one event loop, on an app serving the room `room_code`."""
    app = make_app(registry, dist_dir)
    with TestClient(app) as client:
        yield client


# ---- AC-2: colours, duplicate nicknames, roster -------------------------------


def test_ac2_eight_joins_give_eight_colours_and_unique_nicknames(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [])
    typed = ["Ana", "ana", "Ana", "Bob", "Cy", "Di", "Ed", "Flo"]

    for number, nickname in enumerate(typed):
        outcome = run_join(state, nickname, number)
        state = outcome.state

    assert [player.nickname for player in state.players] == [
        "ANA",
        "ANA 2",
        "ANA 3",
        "BOB",
        "CY",
        "DI",
        "ED",
        "FLO",
    ]
    assert [player.colour for player in state.players] == [0, 1, 2, 3, 4, 5, 6, 7]
    assert [player.is_host for player in state.players] == [True] + [False] * 7
    assert state.seq == 8


def test_ac2_a_taken_nickname_gets_the_smallest_free_suffix(fx01_grid: Grid) -> None:
    players = [make_player(0, "ANA", is_host=True), make_player(1, "ANA 3")]
    state = make_state(fx01_grid, players)

    first = run_join(state, "Ana", 5)
    second = run_join(first.state, "Ana", 6)

    assert first.state.players[-1].nickname == "ANA 2"
    assert second.state.players[-1].nickname == "ANA 4"


def test_ac2_a_player_called_ana_2_pushes_the_next_ana_to_ana_3(
    fx01_grid: Grid,
) -> None:
    players = [make_player(0, "ANA", is_host=True), make_player(1, "ANA 2")]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Ana", 5)

    assert outcome.state.players[-1].nickname == "ANA 3"


def test_ac2_a_nickname_of_20_characters_keeps_the_suffix_within_20(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "X" * 20, is_host=True)])

    second = run_join(state, "x" * 20, 5)
    third = run_join(second.state, "x" * 20, 6)

    assert second.state.players[-1].nickname == "X" * 18 + " 2"
    assert third.state.players[-1].nickname == "X" * 18 + " 3"
    assert len(second.state.players[-1].nickname) == 20


def test_ac2_trailing_spaces_of_the_cut_base_are_removed(fx01_grid: Grid) -> None:
    taken = "A" * 17 + " BB"
    assert len(taken) == 20
    state = make_state(fx01_grid, [make_player(0, taken, is_host=True)])

    outcome = run_join(state, "a" * 17 + " bb", 5)

    assert outcome.state.players[-1].nickname == "A" * 17 + " 2"


def test_ac2_the_duplicate_check_compares_the_capitals(fx01_grid: Grid) -> None:
    # "Stra\u00dfe" in capitals is "STRASSE", the nickname of the player in the room.
    state = make_state(fx01_grid, [make_player(0, "STRASSE", is_host=True)])

    outcome = run_join(state, "Stra\u00dfe", 5)

    assert outcome.state.players[-1].nickname == "STRASSE 2"


def test_ac2_the_duplicate_check_is_accent_sensitive(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [make_player(0, "ELODIE", is_host=True)])

    outcome = run_join(state, "\u00c9lodie", 5)

    assert outcome.state.players[-1].nickname == "\u00c9LODIE"


def test_ac2_a_disconnected_player_still_holds_their_nickname(
    fx01_grid: Grid,
) -> None:
    players = [make_player(0, "ANA", is_host=True, state=PlayerState.DISCONNECTED)]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Ana", 5)

    assert outcome.state.players[-1].nickname == "ANA 2"


def test_ac2_the_suffix_goes_to_the_newcomer_only(fx01_grid: Grid) -> None:
    existing = make_player(0, "ANA", is_host=True)
    state = make_state(fx01_grid, [existing])

    outcome = run_join(state, "ana", 5)

    assert outcome.state.players[0] == existing
    assert outcome.state.players[1].nickname == "ANA 2"


@pytest.mark.parametrize(
    ("taken_colours", "expected_colour"),
    [([0, 2], 1), ([1, 2], 0), ([0, 1, 2, 3, 4, 5, 6], 7), ([5], 0)],
)
def test_ac2_a_new_player_gets_the_lowest_colour_nobody_has(
    fx01_grid: Grid, taken_colours: list[int], expected_colour: int
) -> None:
    players: list[PlayerRecord] = []
    for index, colour in enumerate(taken_colours):
        players.append(make_player(index, f"PLAYER{index}", colour=colour))
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Newbie", 9)

    assert outcome.state.players[-1].colour == expected_colour


def test_ac2_a_disconnected_player_keeps_their_colour(fx01_grid: Grid) -> None:
    players = [
        make_player(0, "ANA", is_host=True, state=PlayerState.DISCONNECTED),
        make_player(1, "BOB"),
    ]
    state = make_state(fx01_grid, players)

    outcome = run_join(state, "Cy", 9)

    assert outcome.state.players[-1].colour == 2


def test_ac2_only_the_first_joiner_is_host(fx01_grid: Grid) -> None:
    host_away = make_player(0, "ANA", is_host=True, state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host_away])

    outcome = run_join(state, "Bob", 5)

    assert outcome.state.players[-1].is_host is False
    assert outcome.state.players[0].is_host is True


def test_ac2_a_room_without_host_gives_the_role_to_the_next_joiner(
    fx01_grid: Grid,
) -> None:
    state = make_state(fx01_grid, [make_player(0, "ANA"), make_player(1, "BOB")])

    outcome = run_join(state, "Cy", 5)

    assert outcome.state.players[-1].is_host is True
    assert outcome.state.players[0].is_host is False
    assert outcome.state.players[1].is_host is False
    event = outcome.entries[0].event
    assert isinstance(event, PlayerJoined)
    assert event.player.is_host is True


def test_ac2_player_views_copy_the_player_records_without_the_token(
    fx01_grid: Grid,
) -> None:
    selection = Selection(row=1, column=2, direction=Direction.DOWN)
    host = make_player(0, "ANA", is_host=True).model_copy(
        update={"muted": True, "selection": selection}
    )
    away = make_player(1, "BOB", state=PlayerState.DISCONNECTED)
    state = make_state(fx01_grid, [host, away])

    views = player_views(state)

    assert views == (
        PlayerView(
            player_id="player0",
            nickname="ANA",
            colour=0,
            state=PlayerState.ACTIVE,
            is_host=True,
            muted=True,
            selection=selection,
        ),
        PlayerView(
            player_id="player1",
            nickname="BOB",
            colour=1,
            state=PlayerState.DISCONNECTED,
            is_host=False,
            muted=False,
            selection=None,
        ),
    )
    assert player_views(make_state(fx01_grid, [])) == ()
    assert "resume" not in views[0].model_dump_json()


def test_ac2_websocket_three_clients_get_distinct_colours_and_suffixes(
    ws_client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        first, first_snapshot = join_as(stack, ws_client, room_code, "Ana")
        second, second_snapshot = join_as(stack, ws_client, room_code, "Ana")
        _, third_snapshot = join_as(stack, ws_client, room_code, "Bob")

        assert [(p.nickname, p.colour) for p in third_snapshot.players] == [
            ("ANA", 0),
            ("ANA 2", 1),
            ("BOB", 2),
        ]
        second_view = active_view(second_snapshot.you, "ANA 2", 1)
        bob_view = active_view(third_snapshot.you, "BOB", 2)
        player_ids = {first_snapshot.you, second_snapshot.you, third_snapshot.you}
        assert len(player_ids) == 3
        assert receive_message(first) == PlayerJoined(seq=2, player=second_view)
        assert receive_message(first) == PlayerJoined(seq=3, player=bob_view)
        assert receive_message(second) == PlayerJoined(seq=3, player=bob_view)


def test_ac2_browser_the_roster_lists_the_players_of_the_snapshot(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    fr = load_fr()
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)

    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))

    expect(page.get_by_test_id("roster")).to_contain_text(fr["roster.heading"])
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)
    expected = [
        ("p0", "0", "false", "Ana"),
        ("p1", "1", "true", "Ana 2"),
        ("p2", "2", "false", "Bob"),
    ]
    for position, (player_id, colour, is_you, nickname) in enumerate(expected):
        item = items.nth(position)
        expect(item).to_have_attribute("data-player-id", player_id)
        expect(item).to_have_attribute("data-colour", colour)
        expect(item).to_have_attribute("data-state", "active")
        expect(item).to_have_attribute("data-you", is_you)
        expect(item.get_by_test_id("roster-nickname")).to_have_text(nickname)
        if is_you == "true":
            expect(item).to_contain_text(fr["roster.you"])
        else:
            expect(item).not_to_contain_text(fr["roster.you"])
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-you", "p1")


def test_ac2_browser_player_joined_appends_and_player_left_removes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    mock.send(snapshot_frame(fx01_grid, three_players(), you="p1", seq=3))
    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(3)

    joined = PlayerJoined(seq=4, player=active_view("p3", "Cy", 3))
    mock.send(joined.model_dump_json())

    expect(items).to_have_count(4)
    expect(items.nth(3)).to_have_attribute("data-player-id", "p3")
    expect(items.nth(3)).to_have_attribute("data-colour", "3")
    expect(items.nth(3).get_by_test_id("roster-nickname")).to_have_text("Cy")
    left = PlayerLeft(seq=5, player_id="p2", reason=LeaveReason.TIMED_OUT)
    mock.send(left.model_dump_json())

    expect(items).to_have_count(3)
    expect(items.nth(0)).to_have_attribute("data-player-id", "p0")
    expect(items.nth(1)).to_have_attribute("data-player-id", "p1")
    expect(items.nth(2)).to_have_attribute("data-player-id", "p3")
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-seq", "5")


def test_ac2_browser_the_eight_colours_are_different_on_screen(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    players: list[PlayerView] = []
    for index in range(8):
        players.append(active_view(f"p{index}", f"Player{index}", index, index == 0))

    mock.send(snapshot_frame(fx01_grid, players, you="p0", seq=8))

    items = page.get_by_test_id("roster").get_by_test_id("roster-player")
    expect(items).to_have_count(8)
    backgrounds: list[str] = []
    for index in range(8):
        swatch = items.nth(index).get_by_test_id("roster-colour")
        background = swatch.evaluate("el => getComputedStyle(el).backgroundColor")
        assert isinstance(background, str)
        backgrounds.append(background)
    assert "rgba(0, 0, 0, 0)" not in backgrounds
    assert "transparent" not in backgrounds
    assert len(set(backgrounds)) == 8


def test_ac2_browser_a_nickname_is_shown_as_plain_text(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_mock_room(page, live_server)
    submit_form(page, "Ana")
    mock.wait_for_frames(1)
    players = [active_view("p0", "<b>Eve</b>", 0, True)]

    mock.send(snapshot_frame(fx01_grid, players, you="p0"))

    nickname = page.get_by_test_id("roster-nickname")
    # Spec 040's displayNickname writes `<b>Eve</b>` as `<b>eve</b>`.
    expect(nickname).to_have_text("<b>eve</b>")
    expect(nickname.locator("b")).to_have_count(0)


def test_ac2_fr_json_has_the_roster_texts() -> None:
    fr = load_fr()

    assert fr["roster.heading"] == "Joueurs"
    assert fr["roster.you"] == "(vous)"
