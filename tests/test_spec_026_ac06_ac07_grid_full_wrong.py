"""Tests of spec 026, AC-6 and AC-7: a full grid with a wrong letter.

AC-6 checks the rule on `handle_message` and on the real WebSocket. AC-7 drives the
room page with a mocked socket, and runs two browsers on the live server. The shared
setup is in `spec026_harness`.

Refined by `gameplay/rules.md` AC-7 (B-046): the status has no live role, and the
page's status region reads it, also on a page that joins a full, wrong grid
(`client/hud.md` rule 17).
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Locator, Page, expect

from hud_harness import expect_page_region_reads, live_role_problems
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import EditLetter, Erase, GridFullWrong, LetterChanged
from nock.room import handle_message
from spec026_harness import (
    LAST_CELL,
    NOW,
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    ChangeList,
    EnterRoom,
    cell_at,
    events_of,
    expect_seq,
    full17,
    grid_from_text,
    join_peers,
    letters_except,
    load_fr,
    make_client,
    make_dist_dir,
    make_registry,
    open_fx01,
    play_live_game,
    type_17_letters,
    wait_until_page,
    write,
)

# ---- Fixtures ----


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
    with make_client(registry, dist_dir) as test_client:
        yield test_client


# ---- AC-6: a full grid with a wrong letter ----


def test_ac6_a_full_wrong_grid_is_followed_by_grid_full_wrong(
    fx01_grid: Grid,
) -> None:
    before = full17(fx01_grid)

    outcome = write(before, "p2", LAST_CELL, "X")

    assert events_of(outcome) == [
        LetterChanged(
            seq=20, row=4, column=4, letter="X", pencil=False, player_id="p2"
        ),
        GridFullWrong(seq=21),
    ]
    assert outcome.state.solved is False
    assert outcome.state.seq == 21


def test_ac6_the_event_carries_nothing_but_its_type_and_seq(fx01_grid: Grid) -> None:
    outcome = write(full17(fx01_grid), "p2", LAST_CELL, "X")

    event = events_of(outcome)[1]
    assert isinstance(event, GridFullWrong)
    assert json.loads(event.model_dump_json()) == {
        "type": "grid_full_wrong",
        "seq": 21,
    }


def test_ac6_rewriting_a_letter_of_a_full_wrong_grid_adds_no_event(
    fx01_grid: Grid,
) -> None:
    full_wrong = write(full17(fx01_grid), "p2", LAST_CELL, "X").state

    outcome = write(full_wrong, "p2", LAST_CELL, "Y")

    assert events_of(outcome) == [
        LetterChanged(seq=22, row=4, column=4, letter="Y", pencil=False, player_id="p2")
    ]
    assert outcome.state.solved is False


def test_ac6_a_wrong_letter_fixed_while_another_stays_wrong_adds_no_event(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p1", (1, 2), "N").state
    state = write(state, "p2", LAST_CELL, "X").state
    assert state.seq == 22

    outcome = write(state, "p2", LAST_CELL, "T")

    assert events_of(outcome) == [
        LetterChanged(seq=23, row=4, column=4, letter="T", pencil=False, player_id="p2")
    ]
    assert outcome.state.solved is False


def test_ac6_erasing_then_filling_the_grid_again_sends_a_new_event(
    fx01_grid: Grid,
) -> None:
    state = write(full17(fx01_grid), "p2", LAST_CELL, "X").state
    erased = handle_message(state, "p2", Erase(row=4, column=4), NOW)
    assert erased.reply == ()
    assert events_of(erased) == [
        LetterChanged(
            seq=22, row=4, column=4, letter=None, pencil=False, player_id="p2"
        )
    ]

    outcome = write(erased.state, "p2", LAST_CELL, "X")

    assert events_of(outcome) == [
        LetterChanged(
            seq=23, row=4, column=4, letter="X", pencil=False, player_id="p2"
        ),
        GridFullWrong(seq=24),
    ]


def test_ac6_an_edit_that_leaves_the_grid_not_full_adds_nothing(
    fx01_grid: Grid,
) -> None:
    outcome = write(full17(fx01_grid), "p1", (1, 2), "N")

    assert len(outcome.entries) == 1
    assert outcome.state.solved is False


def test_ac6_websocket_each_client_gets_grid_full_wrong_right_after_the_letter(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, _ = peers
        type_17_letters(ana, bob, peers)

        bob.send(EditLetter(row=4, column=4, letter="X"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_full_wrong on {peer.name}")

        for peer in peers:
            frames = peer.received()
            letter_index = len(frames) - 2
            letter_event = frames[letter_index][2]
            assert isinstance(letter_event, LetterChanged)
            assert letter_event.letter == "X"
            frame_text = frames[letter_index + 1][1]
            assert json.loads(frame_text) == {
                "type": "grid_full_wrong",
                "seq": letter_event.seq + 1,
            }
            assert set(json.loads(frame_text)) == {"type", "seq"}
            assert peer.errors() == []


# ---- AC-7: all players see "grid full, not yet correct" ----


def letter_changed_frame(
    seq: int, row: int, column: int, letter: str | None, player_id: str
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return event.model_dump_json()


def grid_full_wrong_frame(seq: int) -> str:
    return GridFullWrong(seq=seq).model_dump_json()


GRID_CONTENT_SCRIPT = """
grid => Array.from(grid.querySelectorAll('*')).map(element => {
    const data = {};
    for (const attribute of element.attributes) {
        if (attribute.name.startsWith('data-')) {
            data[attribute.name] = attribute.value;
        }
    }
    const ownText = Array.from(element.childNodes)
        .filter(node => node.nodeType === Node.TEXT_NODE)
        .map(node => node.textContent.trim())
        .join('');
    return [element.tagName, ownText, data];
})
"""


def grid_content(page: Page) -> list[object]:
    """Letters and data-* attributes of every element of the grid.

    Style and sizing are left out: the grid may be resized when a banner shows.
    """
    content = page.get_by_test_id("grid").evaluate(GRID_CONTENT_SCRIPT)
    assert isinstance(content, list)
    return content


FULL_WRONG_CHANGES: ChangeList = [
    *letters_except([LAST_CELL]),
    (4, 4, {"letter": "X", "author": "p2"}),
]


def status_locator(page: Page) -> Locator:
    return page.get_by_test_id("grid-status")


def wrong_cells(page: Page) -> Locator:
    return page.locator('[data-testid="cell"][data-wrong="true"]')


def test_ac7_the_banner_follows_the_full_wrong_grid(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    expect(status_locator(page)).to_have_count(0)

    mock.send(letter_changed_frame(6, 4, 4, "X", "p2"))
    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    status = status_locator(page)
    expect(status).to_have_attribute("data-state", "full_wrong")
    assert live_role_problems(status) == []
    expect(status).to_have_text(load_fr()["completion.full_wrong"])
    expect_page_region_reads(page, load_fr()["completion.full_wrong"])
    expect(wrong_cells(page)).to_have_count(0)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")

    mock.send(letter_changed_frame(8, 4, 4, None, "p2"))

    expect_seq(page, 8)
    expect(status_locator(page)).to_have_count(0)


def test_ac7_grid_full_wrong_changes_no_cell(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    mock.send(letter_changed_frame(6, 4, 4, "X", "p2"))
    expect_seq(page, 6)
    before = grid_content(page)

    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    assert grid_content(page) == before


def test_ac7_a_page_that_joins_a_full_wrong_grid_shows_the_banner_at_once(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, FULL_WRONG_CHANGES)

    status = status_locator(page)
    expect(status).to_have_attribute("data-state", "full_wrong")
    expect(status).to_have_text(load_fr()["completion.full_wrong"])
    assert live_role_problems(status) == []
    expect_page_region_reads(page, load_fr()["completion.full_wrong"])
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


def test_ac7_a_pending_letter_does_not_count_for_the_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([LAST_CELL]))
    cell_at(page, 4, 4).click()
    page.keyboard.press("x")
    expect(cell_at(page, 4, 4)).to_have_attribute("data-unconfirmed", "true")
    wait_until_page(page, lambda: "edit_letter" in mock.sent_types())
    page.wait_for_timeout(SETTLE_MS)
    expect(status_locator(page)).to_have_count(0)

    mock.send(letter_changed_frame(6, 4, 4, "X", "p1"))
    mock.send(grid_full_wrong_frame(7))

    expect_seq(page, 7)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")


def test_ac7_the_banner_stays_while_a_wrong_letter_is_fixed_and_another_remains(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [
        *FULL_WRONG_CHANGES,
        (1, 2, {"letter": "N", "author": "p2"}),
    ]
    mock = open_fx01(page, live_server, fx01_grid, changes)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")

    mock.send(letter_changed_frame(6, 4, 4, "T", "p2"))

    expect_seq(page, 6)
    expect(status_locator(page)).to_have_attribute("data-state", "full_wrong")


def test_ac7_an_unsolved_page_with_empty_cells_has_no_banner(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_fx01(page, live_server, fx01_grid, [])

    expect(status_locator(page)).to_have_count(0)
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


def test_ac7_both_live_pages_show_full_wrong_when_the_last_letter_is_wrong(
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
        play_live_game(page, bob_page, f"{live_server}/r/{code}", enter_room, "x")

        for watcher in (page, bob_page):
            status = status_locator(watcher)
            expect(status).to_have_attribute(
                "data-state", "full_wrong", timeout=WAIT_TIMEOUT_MS
            )
            expect(status).to_have_text(load_fr()["completion.full_wrong"])
            expect(watcher.get_by_test_id("room-page")).to_have_attribute(
                "data-solved", "false"
            )
            expect(wrong_cells(watcher)).to_have_count(0)
    finally:
        bob_context.close()


def test_ac7_the_full_wrong_text_in_fr_json() -> None:
    assert (
        load_fr()["completion.full_wrong"] == "Grille complète, mais pas encore juste."
    )
