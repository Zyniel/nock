"""Tests of spec 012, AC-8: nicknames are typed and stored in capitals (decision 12).

The rule (`normalize_nickname` and `join_room`) and the real WebSocket store the
capitals. The browser, with the live server and with spec 040's mocked socket,
keeps the nickname input in capitals and shows a nickname with capitalised words,
as spec 040's `displayNickname` writes it: in the roster, in spec 022's chat
authors and in spec 019's author line. The shared setup is in `spec012_harness`.

Choices where the spec leaves room:

- "Typing" is `press_sequentially`, one key at a time; a paste, "a change of its
  text" in one step (room page flow step 3), is `fill`.
- The three cells of the mocked snapshot hold the letters of TAMIS: `T` by `p1`,
  `A` by `p2` and `M` by `p3`. The chat lines are `salut`, `bonjour` and `coucou`.
- The chat panel is opened last, after the author line's checks, so that it never
  covers a cell the test taps.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Locator, Page, expect

import nock.room
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellView,
    ChatMessage,
    ErrorCode,
    GridView,
    Join,
    LetterCellView,
    PlayerJoined,
    RevealBudget,
    Snapshot,
    grid_view,
)
from nock.room import normalize_nickname
from spec012_harness import (
    FORM_TIMEOUT_MS,
    MOCK_TOKEN,
    MockRoomSocket,
    active_view,
    grid_from_text,
    join_text,
    make_app,
    make_dist_dir,
    make_registry,
    make_state,
    only_error_code,
    open_mock_room,
    receive_error_code,
    receive_snapshot,
    run_join,
    socket_url,
    submit_form,
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


STREET_NAME = "Straßenbahnfahrerin"  # 19 characters; its sharp s gives SS
STREET_NAME_IN_CAPITALS = "STRASSENBAHNFAHRERIN"  # 20 characters
ELEVEN_SHARP_S = "ß" * 11  # 11 characters, 22 in capitals
NON_EMPTY_MESSAGE = r".+"  # the message names the broken rule

# The mocked snapshot: `p1` (you), `p2` and `p3`, as the server sends them, and the
# text each page element shows for them.
SNAPSHOT_SEQ = 5
SHOWN_NICKNAMES = ["Jean-Luc", "D'Artagnan", "Ana 2"]
LETTERS_BY_AUTHOR = [(1, 0, "T", "p1"), (1, 1, "A", "p2"), (1, 2, "M", "p3")]
AUTHOR_LINES = [
    ((1, 0), "Lettre de Jean-Luc"),
    ((1, 1), "Lettre de D'Artagnan"),
    ((1, 2), "Lettre de Ana 2"),
]


# ---- AC-8: the rule -----------------------------------------------------------


@pytest.mark.parametrize("typed", ["ana", "Ana"])
def test_ac8_normalize_nickname_returns_the_capitals(typed: str) -> None:
    assert normalize_nickname(typed) == "ANA"


def test_ac8_a_letter_whose_capital_is_longer_counts_as_its_capital() -> None:
    assert len(STREET_NAME) == 19

    stored = normalize_nickname(STREET_NAME)

    assert stored == STREET_NAME_IN_CAPITALS
    assert len(stored) == 20


def test_ac8_eleven_sharp_s_are_too_long_once_in_capitals() -> None:
    with pytest.raises(ValueError, match=NON_EMPTY_MESSAGE):
        normalize_nickname(ELEVEN_SHARP_S)


def test_ac8_join_room_stores_the_capitals(fx01_grid: Grid) -> None:
    outcome = run_join(make_state(fx01_grid, []), "ana")

    assert [player.nickname for player in outcome.state.players] == ["ANA"]
    assert len(outcome.entries) == 1
    event = outcome.entries[0].event
    assert event == PlayerJoined(seq=1, player=active_view("joiner1", "ANA", 0, True))


def test_ac8_join_room_refuses_eleven_sharp_s(fx01_grid: Grid) -> None:
    state = make_state(fx01_grid, [])

    outcome = run_join(state, ELEVEN_SHARP_S)

    assert only_error_code(outcome) == ErrorCode.INVALID_NICKNAME
    assert outcome.state == state


def test_ac8_websocket_eleven_sharp_s_get_invalid_nickname_not_invalid_message(
    ws_client: TestClient, registry: RoomRegistry, room_code: str
) -> None:
    with ws_client.websocket_connect(socket_url(room_code)) as websocket:
        websocket.send_text(join_text(ELEVEN_SHARP_S))

        assert receive_error_code(websocket) == ErrorCode.INVALID_NICKNAME

        websocket.send_text(join_text("ana"))
        snapshot = receive_snapshot(websocket)
    assert [view.nickname for view in snapshot.players] == ["ANA"]
    state = registry.room_state(room_code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA"]


# ---- AC-8: the nickname input, live server --------------------------------------


def own_roster_nickname(page: Page) -> Locator:
    own_item = page.locator('[data-testid="roster-player"][data-you="true"]')
    return own_item.get_by_test_id("roster-nickname")


def test_ac8_browser_typed_letters_show_in_capitals_and_the_roster_reads_ana(
    page: Page, live_server: str, room_registry: RoomRegistry, fx01_grid: Grid
) -> None:
    code = room_registry.register_room(fx01_grid)
    page.goto(f"{live_server}/r/{code}")
    nickname_input = page.get_by_test_id("nickname-input")

    nickname_input.press_sequentially("ana", timeout=FORM_TIMEOUT_MS)

    expect(nickname_input).to_have_value("ANA")
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-status", "joined")
    expect(own_roster_nickname(page)).to_have_text("Ana")
    state = room_registry.room_state(code)
    assert state is not None
    assert [player.nickname for player in state.players] == ["ANA"]


def test_ac8_browser_a_pasted_nickname_shows_in_capitals_and_is_sent_so(
    page: Page, live_server: str
) -> None:
    mock = open_mock_room(page, live_server)
    nickname_input = page.get_by_test_id("nickname-input")

    nickname_input.fill("zoé", timeout=FORM_TIMEOUT_MS)

    expect(nickname_input).to_have_value("ZOÉ")
    nickname_input.press("Enter", timeout=FORM_TIMEOUT_MS)
    mock.wait_for_frames(1)
    assert mock.joins() == [Join(nickname="ZOÉ", resume_token=None)]


# ---- AC-8: names shown with capitalised words, mocked socket ----------------------


def with_authored_letters(view: GridView) -> GridView:
    """The view with the letters of `LETTERS_BY_AUTHOR` in their cells."""
    cells: list[CellView] = []
    for cell in view.cells:
        new_cell = cell
        if isinstance(cell, LetterCellView):
            for row, column, letter, author in LETTERS_BY_AUTHOR:
                if (cell.row, cell.column) == (row, column):
                    update = {"letter": letter, "author": author}
                    new_cell = cell.model_copy(update=update)
        cells.append(new_cell)
    return view.model_copy(update={"cells": tuple(cells)})


def capitals_snapshot_frame(grid: Grid) -> str:
    """The FX-01 snapshot of AC-8: three players, a chat line and a letter each."""
    players = (
        active_view("p1", "JEAN-LUC", 0, True),
        active_view("p2", "D'ARTAGNAN", 1),
        active_view("p3", "ANA 2", 2),
    )
    chat = (
        ChatMessage(seq=2, player_id="p1", text="salut"),
        ChatMessage(seq=3, player_id="p2", text="bonjour"),
        ChatMessage(seq=4, player_id="p3", text="coucou"),
    )
    snapshot = Snapshot(
        seq=SNAPSHOT_SEQ,
        you="p1",
        resume_token=MOCK_TOKEN,
        grid=with_authored_letters(grid_view(grid)),
        players=players,
        settings=nock.room.DEFAULT_SETTINGS,
        reveal_budget=RevealBudget(letters=5, words=1),
        flags=(),
        chat=chat,
        open_vote=None,
        timer_elapsed_ms=0,
        timer_running=False,
        solved=False,
    )
    return snapshot.model_dump_json()


def open_capitals_room(page: Page, base_url: str, grid: Grid) -> MockRoomSocket:
    """Join /r/ABC123 from the form and receive the snapshot of AC-8."""
    mock = open_mock_room(page, base_url)
    submit_form(page, "Jean-Luc")
    mock.wait_for_frames(1)
    mock.send(capitals_snapshot_frame(grid))
    room = page.get_by_test_id("room-page")
    expect(room).to_have_attribute("data-seq", str(SNAPSHOT_SEQ))
    return mock


def test_ac8_browser_the_roster_shows_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_capitals_room(page, live_server, fx01_grid)

    roster = page.get_by_test_id("roster")

    expect(roster.get_by_test_id("roster-nickname")).to_have_text(SHOWN_NICKNAMES)


def test_ac8_browser_the_chat_authors_show_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_capitals_room(page, live_server, fx01_grid)

    page.get_by_test_id("chat-toggle").click()

    expect(page.get_by_test_id("chat-panel")).to_be_visible()
    chat_list = page.get_by_test_id("chat-list")
    expect(chat_list.get_by_test_id("chat-author")).to_have_text(SHOWN_NICKNAMES)


def test_ac8_browser_the_author_line_shows_capitalised_words(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_capitals_room(page, live_server, fx01_grid)
    switch = page.get_by_test_id("authors-switch")
    switch.click()
    expect(switch).to_have_attribute("aria-pressed", "true")
    author_line = page.get_by_test_id("clue-bar-author")

    for (row, column), expected_line in AUTHOR_LINES:
        cell = page.locator(
            f'[data-testid="cell"][data-row="{row}"][data-column="{column}"]'
        )
        cell.click()
        expect(author_line).to_have_text(expected_line)
