"""Tests of spec 020, AC-1: a letter typed in pencil mode shows in grey italics for
every player.

The rule on `handle_message`, the real WebSocket, the page with a mocked socket and
two pages on the live server. The edge cases of AC-1 are here too: the same letter
typed in either mode (decision 10), a locked cell, an erase, a lock over a pending
pencil edit, the in-app keyboard, the flash of a pencil edit over my letter
(decision 11), and the checks and reveals of a pencil letter ("Unchanged" in the
server rule). The shared setup is in `spec020_harness` and `spec024_harness`.
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
    CellTarget,
    Check,
    CheckResult,
    EditLetter,
    Erase,
    ErrorCode,
    LetterCellView,
    LetterChanged,
    PencilEdit,
    RevealBudget,
)
from nock.room import CellState, handle_message
from nock.server import create_app
from spec013_harness import make_page
from spec017_harness import first_join, room_page
from spec017_harness import joined_room as joined_reconnecting_room
from spec017_harness import snapshot_frame as reconnect_snapshot_frame
from spec020_harness import (
    accepted_pencil,
    cell_values,
    click_pencil_toggle,
    edit_messages_after_a_pause,
    error_frame,
    expect_cell_shows,
    font_style,
    letter_changed_frame,
    pencil,
    pencil_toggle,
    tap,
    text_colour,
    turn_pencil_mode_on,
    wait_for_edit_messages,
)
from spec024_harness import (
    NOW,
    WAIT_TIMEOUT_MS,
    ChangeList,
    EnterRoom,
    Peer,
    accepted_reveal,
    cell_at,
    cell_locked_frame,
    cell_selector,
    cell_state,
    cell_view,
    check_cell,
    events_of,
    expect_selection,
    expect_seq,
    grid_from_text,
    join_one,
    join_peers,
    make_catalogue,
    make_dist_dir,
    make_registry,
    open_room,
    reveal_result_frame,
    snapshot_cell,
    two_player_room,
    write,
)

BROWSER_BUDGET_MS = 300  # spec 015 AC-1
TOGGLE_TEXT = "Crayon"  # `pencil.toggle` in "New fr.json keys"
PENCIL_EDIT_JSON = (
    '{"type": "pencil_edit", "row": 1, "column": 0, "letter": "T", "base_seq": null}'
)
WORD_W1 = "0,0,0"

# (1, 2) holds `M`, a normal letter by `p2` (AC-1's mocked snapshot).
M_AT_1_2: ChangeList = [(1, 2, {"letter": "M", "author": "p2"})]


def pencil_letter(letter: str, author: str) -> dict[str, object]:
    """The update of a snapshot cell that holds a pencil letter."""
    return {"letter": letter, "pencil": True, "author": author}


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


def test_ac1_a_pencil_edit_gives_one_letter_changed_with_pencil_true(
    fx01_grid: Grid,
) -> None:
    outcome = pencil(two_player_room(fx01_grid), "p1", 1, 0, "T")

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=3, row=1, column=0, letter="T", pencil=True, player_id="p1")
    ]
    assert outcome.state.seq == 3


def test_ac1_the_cell_holds_the_pencil_letter_and_its_author(fx01_grid: Grid) -> None:
    state = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T").state

    assert cell_state(state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=True,
        author="p1",
        locked=False,
        revealed=False,
        wrong=False,
        changed_seq=3,
        changed_by="p1",
    )


def test_ac1_grid_state_shows_the_pencil_letter(fx01_grid: Grid) -> None:
    state = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T").state

    assert cell_view(state, 1, 0) == LetterCellView(
        row=1,
        column=0,
        letter="T",
        pencil=True,
        author="p1",
        locked=False,
        revealed=False,
        wrong=False,
    )


def test_ac1_a_pencil_edit_changes_its_cell_only(fx01_grid: Grid) -> None:
    before = two_player_room(fx01_grid)
    state = accepted_pencil(before, "p1", 1, 0, "T").state

    expected = cell_values(before)
    expected[(1, 0)] = ("T", True, "p1")
    assert cell_values(state) == expected


def test_ac1_a_pencil_edit_that_changes_nothing_still_gets_its_letter_changed(
    fx01_grid: Grid,
) -> None:
    first = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 0, "T")

    again = pencil(first.state, "p1", 1, 0, "T")

    assert again.reply == ()
    assert events_of(again) == [
        LetterChanged(seq=4, row=1, column=0, letter="T", pencil=True, player_id="p1")
    ]


def test_ac1_a_pencil_edit_over_the_same_normal_letter_makes_it_a_pencil_letter(
    fx01_grid: Grid,
) -> None:
    written = write(two_player_room(fx01_grid), "p2", 1, 0, "T").state

    outcome = pencil(written, "p1", 1, 0, "T")

    assert events_of(outcome) == [
        LetterChanged(seq=4, row=1, column=0, letter="T", pencil=True, player_id="p1")
    ]
    assert cell_values(outcome.state)[(1, 0)] == ("T", True, "p1")


def test_ac1_an_edit_letter_over_a_pencil_letter_makes_it_normal_by_the_typer(
    fx01_grid: Grid,
) -> None:
    pencilled = accepted_pencil(two_player_room(fx01_grid), "p2", 1, 0, "T").state

    outcome = write(pencilled, "p1", 1, 0, "T")

    assert events_of(outcome) == [
        LetterChanged(seq=4, row=1, column=0, letter="T", pencil=False, player_id="p1")
    ]
    assert cell_values(outcome.state)[(1, 0)] == ("T", False, "p1")


def test_ac1_a_pencil_edit_clears_the_strike_of_a_wrong_letter(
    fx01_grid: Grid,
) -> None:
    written = write(two_player_room(fx01_grid), "p1", 1, 1, "X").state
    struck = check_cell(written, 1, 1)
    assert cell_state(struck, 1, 1).wrong is True

    state = accepted_pencil(struck, "p2", 1, 1, "A").state

    cell = cell_state(state, 1, 1)
    assert (cell.letter, cell.pencil, cell.author, cell.wrong) == (
        "A",
        True,
        "p2",
        False,
    )


def test_ac1_a_check_leaves_a_pencil_letter_out(fx01_grid: Grid) -> None:
    pencilled = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 1, "A").state
    target = CellTarget(row=1, column=1)

    outcome = handle_message(pencilled, "p2", Check(target=target), NOW)

    assert events_of(outcome) == [
        CheckResult(seq=4, player_id="p2", target=target, correct=(), wrong=())
    ]
    cell = cell_state(outcome.state, 1, 1)
    assert (cell.letter, cell.pencil, cell.locked, cell.wrong) == (
        "A",
        True,
        False,
        False,
    )


def test_ac1_a_reveal_replaces_a_pencil_letter_and_clears_its_flag(
    fx01_grid: Grid,
) -> None:
    pencilled = accepted_pencil(two_player_room(fx01_grid), "p1", 1, 1, "X").state

    state = accepted_reveal(pencilled, CellTarget(row=1, column=1), "p2").state

    cell = cell_state(state, 1, 1)
    assert (cell.letter, cell.pencil, cell.author, cell.locked, cell.revealed) == (
        "A",
        False,
        None,
        True,
        True,
    )
    assert cell_view(state, 1, 1).pencil is False


# ---- AC-1, WebSocket ----


def letter_changes(peer: Peer) -> list[LetterChanged]:
    found: list[LetterChanged] = []
    for message in peer.messages()[1:]:
        if isinstance(message, LetterChanged):
            found.append(message)
    return found


def test_ac1_websocket_both_players_receive_the_pencil_letter_changed(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send_text(PENCIL_EDIT_JSON)
        for peer in (ana, bob):
            peer.wait_for_seq(3, f"the pencil letter on {peer.name}")
        expected = LetterChanged(
            seq=3, row=1, column=0, letter="T", pencil=True, player_id=ana.you()
        )
        on_ana = letter_changes(ana)
        on_bob = letter_changes(bob)

    assert on_ana == [expected]
    assert on_bob == [expected]


def test_ac1_websocket_a_later_joiner_gets_the_pencil_letter_in_its_snapshot(
    client: TestClient, room_code: str
) -> None:
    with contextlib.ExitStack() as stack:
        ana, bob = join_peers(stack, client, room_code, ["Ana", "Bob"])
        ana.send_text(PENCIL_EDIT_JSON)
        bob.wait_for_seq(3, "the pencil letter on Bob")
        cleo = join_one(stack, client, room_code, "Cleo")
        cell = snapshot_cell(cleo.snapshot(), 1, 0)
        ana_id = ana.you()

    assert (cell.letter, cell.pencil, cell.author) == ("T", True, ana_id)


# ---- AC-1, page with a mocked socket ----


def test_ac1_page_pencil_toggle_is_a_button_that_starts_off_and_each_click_flips(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid)
    toggle = pencil_toggle(page)
    expect(toggle).to_have_attribute("aria-pressed", "false")
    expect(toggle).to_have_text(TOGGLE_TEXT)
    kind = toggle.evaluate(
        "el => [el.tagName, el.getAttribute('type')]", timeout=WAIT_TIMEOUT_MS
    )

    click_pencil_toggle(page)
    expect(toggle).to_have_attribute("aria-pressed", "true")
    click_pencil_toggle(page)
    expect(toggle).to_have_attribute("aria-pressed", "false")

    assert kind == ["BUTTON", "button"]


def test_ac1_page_pencil_mode_is_off_again_after_a_reload(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    room = joined_reconnecting_room(page, live_server, fx01_grid, seq=5)
    turn_pencil_mode_on(page)

    page.reload()
    room.wait_for_connections(2)
    second = room.connections[1]
    first_join(page, second)
    second.send(reconnect_snapshot_frame(fx01_grid, 6))
    expect(room_page(page)).to_have_attribute("data-seq", "6")

    expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "false")


def test_ac1_page_typing_in_pencil_mode_shows_a_grey_italic_pending_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=M_AT_1_2)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)

    page.keyboard.press("t")

    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)
    expect_selection(page, 1, 1, "across", WORD_W1)
    pencil_cell = cell_at(page, 1, 0)
    normal_cell = cell_at(page, 1, 2)
    expect(normal_cell).to_have_attribute("data-pencil", "false")
    assert font_style(pencil_cell) == "italic"
    assert font_style(normal_cell) == "normal"
    # Both cells are in my selected word and not selected: the same state.
    assert text_colour(pencil_cell) != text_colour(normal_cell)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [PencilEdit(row=1, column=0, letter="T")]

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1", pencil=True))
    expect_seq(page, 6)

    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=False)
    assert font_style(pencil_cell) == "italic"


def test_ac1_page_pencil_letters_from_a_snapshot_and_from_another_player_show(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [*M_AT_1_2, (3, 1, pencil_letter("A", "p2"))]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    snapshot_pencil = cell_at(page, 3, 1)
    normal_cell = cell_at(page, 1, 2)
    expect_cell_shows(page, 3, 1, "A", pencil=True, unconfirmed=False)
    expect(snapshot_pencil).to_have_attribute("data-author", "p2")
    expect(normal_cell).to_have_attribute("data-pencil", "false")
    expect(cell_at(page, 4, 4)).to_have_attribute("data-pencil", "false")
    assert font_style(snapshot_pencil) == "italic"
    assert font_style(normal_cell) == "normal"
    # Neither cell is selected, in my word or tinted: the same state.
    assert text_colour(snapshot_pencil) != text_colour(normal_cell)

    mock.send(letter_changed_frame(6, 2, 2, "I", "p2", pencil=True))
    expect_seq(page, 6)

    expect_cell_shows(page, 2, 2, "I", pencil=True, unconfirmed=False)
    assert font_style(cell_at(page, 2, 2)) == "italic"


def test_ac1_page_typing_with_pencil_mode_off_sends_edit_letter_in_normal_style(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=M_AT_1_2)
    turn_pencil_mode_on(page)
    click_pencil_toggle(page)
    expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "false")
    tap(page, 1, 0)

    page.keyboard.press("t")

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)
    assert font_style(cell_at(page, 1, 0)) == "normal"
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [EditLetter(row=1, column=0, letter="T")]


def test_ac1_page_typing_the_pencil_letter_a_cell_shows_sends_nothing_and_moves_on(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, pencil_letter("T", "p2"))]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)

    page.keyboard.press("t")

    expect_selection(page, 1, 1, "across", WORD_W1)
    assert edit_messages_after_a_pause(page, mock.frames_without_pings) == []
    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=False)


def test_ac1_page_typing_in_pencil_mode_over_the_same_normal_letter_sends_pencil(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p2"})]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)

    page.keyboard.press("t")

    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [PencilEdit(row=1, column=0, letter="T")]
    expect_selection(page, 1, 1, "across", WORD_W1)


def test_ac1_page_typing_over_a_pencil_letter_with_pencil_mode_off_sends_an_edit(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, pencil_letter("T", "p2"))]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "false")
    tap(page, 1, 0)

    page.keyboard.press("t")

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)
    assert font_style(cell_at(page, 1, 0)) == "normal"
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [EditLetter(row=1, column=0, letter="T")]


def test_ac1_page_typing_in_pencil_mode_on_a_locked_cell_sends_nothing(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p2", "locked": True})]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)

    page.keyboard.press("x")

    assert edit_messages_after_a_pause(page, mock.frames_without_pings) == []
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-locked", "true")


def test_ac1_page_backspace_erases_a_pencil_letter_in_pencil_mode(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, pencil_letter("T", "p1"))]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)

    page.keyboard.press("Backspace")

    expect_cell_shows(page, 1, 0, "", pencil=False, unconfirmed=True)
    expect_selection(page, 1, 0, "across", WORD_W1)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [Erase(row=1, column=0)]


def test_ac1_page_a_lock_over_my_pending_pencil_edit_shows_the_locked_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)
    page.keyboard.press("x")
    expect_cell_shows(page, 1, 0, "X", pencil=True, unconfirmed=True)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [PencilEdit(row=1, column=0, letter="X")]
    cell = cell_at(page, 1, 0)

    left = RevealBudget(letters=4, words=1)
    mock.send(reveal_result_frame(6, CellTarget(row=1, column=0), left))
    mock.send(cell_locked_frame(7, 1, 0, "T", revealed=True))
    expect_seq(page, 7)

    expect(cell).to_have_attribute("data-locked", "true")
    expect(cell).to_have_attribute("data-letter", "T")
    expect(cell).to_have_attribute("data-pencil", "false")
    assert font_style(cell) == "normal"

    mock.send(error_frame(ErrorCode.CELL_LOCKED))

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)


def test_ac1_page_the_in_app_keyboard_follows_pencil_mode(
    browser: Browser, browser_name: str, live_server: str, fx01_grid: Grid
) -> None:
    page, close = make_page(browser, browser_name, 360, 740, True)
    try:
        mock = open_room(page, live_server, fx01_grid)
        pencil_toggle(page).tap(timeout=WAIT_TIMEOUT_MS)
        expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "true")
        cell_at(page, 1, 0).tap(timeout=WAIT_TIMEOUT_MS)

        key = page.locator('[data-testid="key"][data-key="T"]')
        key.tap(timeout=WAIT_TIMEOUT_MS)

        expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=True)
        sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    finally:
        close()

    assert sent == [PencilEdit(row=1, column=0, letter="T")]


def test_ac1_page_a_pencil_letter_from_another_player_over_my_letter_flashes(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "author": "p1"})]
    mock = open_room(page, live_server, fx01_grid, changes=changes)

    mock.send(letter_changed_frame(6, 1, 0, "X", "p2", pencil=True))

    # `p2` has colour 1 in the default roster.
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "1")
    expect_cell_shows(page, 1, 0, "X", pencil=True, unconfirmed=False)


def test_ac1_page_a_reveal_replaces_a_pencil_letter_with_a_normal_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 1, pencil_letter("X", "p2"))]
    mock = open_room(page, live_server, fx01_grid, changes=changes)
    expect_cell_shows(page, 1, 1, "X", pencil=True, unconfirmed=False)

    left = RevealBudget(letters=4, words=1)
    mock.send(reveal_result_frame(6, CellTarget(row=1, column=1), left))
    mock.send(cell_locked_frame(7, 1, 1, "A", revealed=True))
    expect_seq(page, 7)

    expect_cell_shows(page, 1, 1, "A", pencil=False, unconfirmed=False)
    expect(cell_at(page, 1, 1)).to_have_attribute("data-locked", "true")
    assert font_style(cell_at(page, 1, 1)) == "normal"


# ---- AC-1, two pages on the live server ----


def test_ac1_live_a_pencil_letter_reaches_the_other_page_within_300_ms(
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
        turn_pencil_mode_on(page)
        tap(page, 1, 0)

        page.keyboard.press("t")

        # One wait for both attributes, so the 300 ms count from the key press.
        pencil_t = bob_page.locator(
            cell_selector(1, 0) + '[data-letter="T"][data-pencil="true"]'
        )
        expect(pencil_t).to_have_count(1, timeout=BROWSER_BUDGET_MS)
        style = font_style(cell_at(bob_page, 1, 0))
    finally:
        bob_context.close()

    assert style == "italic"
