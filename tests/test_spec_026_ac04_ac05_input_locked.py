"""Tests of spec 026, AC-4 and AC-5: input is locked once solved.

AC-4 checks the refusals on `handle_message` and on the real WebSocket. AC-5 drives
the room page with a mocked socket. The shared setup is in `spec026_harness`.

Reading of AC-5: tapping a cell sends a `select_cell` frame (selection is not
locked), so "sends no frame" is checked as "sends no frame after the tap".
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import Browser, Page, expect

from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    Check,
    ConfirmPencil,
    Direction,
    EditLetter,
    Erase,
    ErrorCode,
    GridSolved,
    GridTarget,
    PencilEdit,
    SelectCell,
    SelectionMoved,
    Undo,
)
from nock.room import handle_message
from spec026_harness import (
    LAST_CELL,
    NOW,
    SETTLE_MS,
    MockRoomSocket,
    cell_at,
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
    refusal_code,
    solved_room,
    type_17_letters,
    wait_until_page,
    write,
)

QUIET_MS = 300

# Makes `matchMedia("(pointer: coarse)")` report a match, other queries unchanged.
COARSE_POINTER_SCRIPT = """
(() => {
  const original = window.matchMedia.bind(window);
  window.matchMedia = (query) => {
    const result = original(query);
    if (query.replace(/\\s/g, '') !== '(pointer:coarse)') {
      return result;
    }
    return new Proxy(result, {
      get(target, property) {
        if (property === 'matches') {
          return true;
        }
        const value = target[property];
        return typeof value === 'function' ? value.bind(target) : value;
      },
    });
  };
})();
"""

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


# ---- AC-4: input is locked on the server once solved ----


@pytest.mark.parametrize(
    "message",
    [
        EditLetter(row=1, column=0, letter="A"),
        Erase(row=1, column=0),
        PencilEdit(row=1, column=0, letter="A"),
        ConfirmPencil(row=1, column=0),
        Check(target=GridTarget()),
    ],
    ids=["edit_letter", "erase", "pencil_edit", "confirm_pencil", "check"],
)
def test_ac4_a_solved_room_refuses_input_of_p1(
    fx01_grid: Grid,
    message: EditLetter | Erase | PencilEdit | ConfirmPencil | Check,
) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p1", message, NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 21
    assert outcome.state.solved is True
    assert outcome.state.cells == solved.cells
    assert outcome.to_others == ()
    assert outcome.close_sender is False
    assert outcome.disconnects == ()


def test_ac4_a_solved_room_refuses_the_undo_of_p2(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(solved, "p2", Undo(), NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.GRID_SOLVED
    assert outcome.entries == ()
    assert outcome.state.seq == 21
    assert outcome.state.cells == solved.cells


def test_ac4_nothing_to_undo_is_answered_before_grid_solved(fx01_grid: Grid) -> None:
    state = full17(fx01_grid)
    solved = write(state, "p1", LAST_CELL, "T").state
    assert solved.solved is True

    outcome = handle_message(solved, "p2", Undo(), NOW + 755.0)

    assert refusal_code(outcome) is ErrorCode.NOTHING_TO_UNDO


def test_ac4_the_edit_checks_one_to_four_come_before_grid_solved(
    fx01_grid: Grid,
) -> None:
    solved = solved_room(fx01_grid)

    on_a_clue_cell = handle_message(
        solved, "p1", EditLetter(row=0, column=0, letter="A"), NOW + 755.0
    )

    assert refusal_code(on_a_clue_cell) is ErrorCode.NOT_A_LETTER_CELL


def test_ac4_a_selection_is_still_accepted(fx01_grid: Grid) -> None:
    solved = solved_room(fx01_grid)

    outcome = handle_message(
        solved,
        "p1",
        SelectCell(row=1, column=0, direction=Direction.ACROSS),
        NOW + 755.0,
    )

    assert outcome.reply == ()
    assert outcome.entries == ()
    assert len(outcome.to_others) == 1
    assert isinstance(outcome.to_others[0], SelectionMoved)
    assert outcome.to_others[0].player_id == "p1"


def test_ac4_websocket_an_edit_after_the_solution_is_refused_to_its_sender_only(
    registry: RoomRegistry, client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        peers = join_peers(stack, client, room_code, ["Ana", "Bob", "Cy"])
        ana, bob, cy = peers
        type_17_letters(ana, bob, peers)
        bob.send(EditLetter(row=4, column=4, letter="T"))
        for peer in peers:
            peer.wait_for_seq(3 + 18 + 1, f"grid_solved on {peer.name}")

        cy.send(EditLetter(row=1, column=0, letter="A"))
        cy.wait_until(lambda: len(cy.errors()) == 1, "the refusal on Cy")
        ana.send(Undo())
        ana.wait_until(lambda: len(ana.errors()) == 1, "the refusal on Ana")

        assert [error.code for error in cy.errors()] == [ErrorCode.GRID_SOLVED]
        assert [error.code for error in ana.errors()] == [ErrorCode.GRID_SOLVED]
        assert bob.errors() == []
        state = registry.room_state(room_code)
        assert state is not None
        assert state.seq == 3 + 18 + 1
        assert state.solved is True
        for peer in peers:
            assert peer.last_seq() == 3 + 18 + 1


# ---- AC-5: input is locked on the page once solved ----


def grid_solved_frame(seq: int) -> str:
    return GridSolved(seq=seq, elapsed_ms=1000).model_dump_json()


def expect_selection(page: Page, row: int, column: int) -> None:
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


SOLVED_WAYS = ["grid_solved_event", "solved_snapshot"]


def open_solved_page(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> MockRoomSocket:
    """A page on a full, right grid that is solved, by an event or by a snapshot."""
    changes = letters_except([])
    if way == "solved_snapshot":
        return open_fx01(page, live_server, fx01_grid, changes, seq=5, solved=True)
    mock = open_fx01(page, live_server, fx01_grid, changes, seq=5)
    mock.send(grid_solved_frame(6))
    expect_seq(page, 6)
    return mock


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_letters_erase_and_undo_keys_send_nothing_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    mock = open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)
    page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    for key in ("b", "Backspace", "Control+z", "Meta+z"):
        page.keyboard.press(key)
    page.wait_for_timeout(QUIET_MS)

    assert mock.received[already_sent:] == []
    expect(cell_at(page, 1, 0)).to_have_attribute("data-letter", "T")
    expect_selection(page, 1, 0)


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_undo_and_check_buttons_are_disabled_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()

    for identifier in ("undo-button", "check-letter", "check-word", "check-grid"):
        expect(page.get_by_test_id(identifier)).to_be_disabled()


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_arrow_keys_and_taps_still_move_the_selection_once_solved(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)

    page.keyboard.press("ArrowRight")
    expect_selection(page, 1, 1)
    cell_at(page, 2, 2).click()
    expect_selection(page, 2, 2)


@pytest.mark.parametrize("way", SOLVED_WAYS)
def test_ac5_the_page_shows_the_solved_attribute_and_status(
    page: Page, live_server: str, fx01_grid: Grid, way: str
) -> None:
    open_solved_page(page, live_server, fx01_grid, way)

    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "true")
    status = page.get_by_test_id("grid-status")
    expect(status).to_have_attribute("data-state", "solved")
    expect(status).to_have_text(load_fr()["completion.solved"])


def test_ac5_control_an_unsolved_page_sends_the_same_keys(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(page, live_server, fx01_grid, letters_except([(1, 0)]))
    cell_at(page, 1, 0).click()
    expect_selection(page, 1, 0)
    page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    page.keyboard.press("b")
    page.keyboard.press("Control+z")

    wait_until_page(page, lambda: "undo" in mock.sent_types()[already_sent:])
    page.wait_for_timeout(SETTLE_MS)
    sent = mock.sent_types()[already_sent:]
    assert [kind for kind in sent if kind != "select_cell"] == ["edit_letter", "undo"]
    expect(page.get_by_test_id("room-page")).to_have_attribute("data-solved", "false")


@pytest.fixture
def touch_page(browser: Browser, browser_name: str) -> Iterator[Page]:
    """A 360 by 740 touch page; its pointer is coarse, so the keyboard shows."""
    viewport = {"width": 360, "height": 740}
    if browser_name == "firefox":
        context = browser.new_context(viewport=viewport, has_touch=True)
    else:
        context = browser.new_context(viewport=viewport, has_touch=True, is_mobile=True)
    if browser_name != "chromium":
        context.add_init_script(COARSE_POINTER_SCRIPT)
    try:
        yield context.new_page()
    finally:
        context.close()


def test_ac5_the_in_app_keyboard_sends_nothing_once_solved(
    touch_page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_fx01(
        touch_page, live_server, fx01_grid, letters_except([]), seq=5, solved=True
    )
    cell_at(touch_page, 1, 0).tap()
    expect_selection(touch_page, 1, 0)
    expect(touch_page.get_by_test_id("keyboard")).to_be_visible()
    touch_page.wait_for_timeout(SETTLE_MS)
    already_sent = len(mock.received)

    touch_page.locator('[data-testid="key"][data-key="B"]').tap()
    touch_page.get_by_test_id("key-delete").tap()
    touch_page.wait_for_timeout(QUIET_MS)

    assert mock.received[already_sent:] == []
    expect(cell_at(touch_page, 1, 0)).to_have_attribute("data-letter", "T")
