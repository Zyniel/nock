"""Tests of spec 020, AC-2: any player can confirm a pencil letter with one action,
and it then shows as a normal letter.

The rule on `handle_message`, the page with a mocked socket and two pages on the
live server. The edge cases of AC-2 are here too: two confirmations at once, a
confirmation of my pencil letter by another player (it flashes, decision 11), a
confirmation of my own pending pencil letter, and a cell locked over it. The
confirmer becomes the author (decision 1); a cell without a pencil letter is
refused `stale_edit` (decision 2); the page's `seq` goes in `base_seq` (decision
3). The shared setup is in `spec020_harness` and `spec024_harness`.

Refined by spec 043 (the design's room layout): `confirm-pencil` is the first item
of the Aide menu, present only while the selected cell shows a pencil letter, is
not locked and the grid is not solved (it was disabled otherwise), with the text
`fr.json["pencil.confirm"]` (« Confirmer la lettre au crayon ») and no
`aria-label`. The harness's `click_confirm` opens the Aide menu first.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from nock.hub import RoomRegistry
from nock.protocol import (
    CellTarget,
    ConfirmPencil,
    ErrorCode,
    LetterChanged,
    PencilEdit,
    RevealBudget,
    SelectCell,
    parse_client_message,
)
from nock.room import CellState, RoomState
from spec020_harness import (
    accepted_confirm,
    accepted_pencil,
    cell_values,
    click_confirm,
    confirm,
    confirm_button,
    error_frame,
    expect_cell_shows,
    expect_selected_cell,
    font_style,
    letter_changed_frame,
    new_frames_after,
    tap,
    turn_pencil_mode_on,
    wait_for_edit_messages,
)
from spec024_harness import (
    NOW,
    WAIT_TIMEOUT_MS,
    ChangeList,
    EnterRoom,
    cell_at,
    cell_locked_frame,
    cell_state,
    cell_view,
    events_of,
    expect_selection,
    expect_seq,
    grid_from_text,
    make_catalogue,
    make_dist_dir,
    open_room,
    refusal_code,
    reveal_result_frame,
    seen_at,
    two_player_room,
    wait_until_page,
    write,
)

CONFIRM_TEXT = "Confirmer la lettre au crayon"  # `pencil.confirm`, spec 043
WORD_W1 = "0,0,0"

# (1, 0) holds a pencil `T` by `p2` (AC-2's mocked snapshot, seq 5).
PENCIL_T_BY_P2: ChangeList = [(1, 0, {"letter": "T", "pencil": True, "author": "p2"})]


def selection_sent(frames: list[str], row: int, column: int) -> bool:
    """Tell whether the page sent a `select_cell` for (row, column)."""
    for frame in frames:
        message = parse_client_message(frame)
        if isinstance(message, SelectCell) and (message.row, message.column) == (
            row,
            column,
        ):
            return True
    return False


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


# ---- Rooms of the rule tests ----


def pencil_t_room(grid: Grid) -> RoomState:
    """The room of AC-1 after `p1`'s pencil `T` at (1, 0): seq 3."""
    state = accepted_pencil(two_player_room(grid), "p1", 1, 0, "T").state
    assert state.seq == 3
    return state


def pencil_t_then_a_room(grid: Grid) -> RoomState:
    """`p1` wrote a pencil `T` (seq 3) then a pencil `A` (seq 4) at (1, 0)."""
    state = accepted_pencil(pencil_t_room(grid), "p1", 1, 0, "A").state
    assert state.seq == 4
    return state


# ---- AC-2, rule ----


def test_ac2_another_player_confirms_a_pencil_letter(fx01_grid: Grid) -> None:
    outcome = confirm(pencil_t_room(fx01_grid), "p2", 1, 0)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=4, row=1, column=0, letter="T", pencil=False, player_id="p2")
    ]
    assert outcome.state.seq == 4


def test_ac2_the_confirmed_letter_is_normal_and_its_author_is_the_confirmer(
    fx01_grid: Grid,
) -> None:
    state = accepted_confirm(pencil_t_room(fx01_grid), "p2", 1, 0).state

    assert cell_state(state, 1, 0) == CellState(
        row=1,
        column=0,
        letter="T",
        pencil=False,
        author="p2",
        locked=False,
        revealed=False,
        wrong=False,
        changed_seq=4,
        changed_by="p2",
    )
    view = cell_view(state, 1, 0)
    assert (view.letter, view.pencil, view.author) == ("T", False, "p2")


def test_ac2_a_player_confirms_their_own_pencil_letter(fx01_grid: Grid) -> None:
    outcome = confirm(pencil_t_room(fx01_grid), "p1", 1, 0)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=4, row=1, column=0, letter="T", pencil=False, player_id="p1")
    ]
    assert cell_values(outcome.state)[(1, 0)] == ("T", False, "p1")


def test_ac2_a_confirmation_on_an_empty_cell_is_refused_stale_edit(
    fx01_grid: Grid,
) -> None:
    before = pencil_t_room(fx01_grid)

    outcome = confirm(before, "p2", 1, 1)

    assert refusal_code(outcome) == ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", NOW)


def test_ac2_a_confirmation_on_a_normal_letter_is_refused_stale_edit(
    fx01_grid: Grid,
) -> None:
    before = write(two_player_room(fx01_grid), "p1", 1, 0, "T").state

    outcome = confirm(before, "p2", 1, 0)

    assert refusal_code(outcome) == ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", NOW)


def test_ac2_a_confirmation_from_before_a_newer_pencil_letter_is_refused_stale_edit(
    fx01_grid: Grid,
) -> None:
    before = pencil_t_then_a_room(fx01_grid)

    outcome = confirm(before, "p2", 1, 0, base_seq=3)

    assert refusal_code(outcome) == ErrorCode.STALE_EDIT
    assert outcome.entries == ()
    assert outcome.state == seen_at(before, "p2", NOW)


def test_ac2_a_confirmation_with_the_latest_base_seq_confirms_the_newest_letter(
    fx01_grid: Grid,
) -> None:
    outcome = confirm(pencil_t_then_a_room(fx01_grid), "p2", 1, 0, base_seq=4)

    assert outcome.reply == ()
    assert events_of(outcome) == [
        LetterChanged(seq=5, row=1, column=0, letter="A", pencil=False, player_id="p2")
    ]
    assert cell_values(outcome.state)[(1, 0)] == ("A", False, "p2")


def test_ac2_of_two_confirmations_at_once_the_second_is_refused_stale_edit(
    fx01_grid: Grid,
) -> None:
    first = accepted_confirm(pencil_t_room(fx01_grid), "p2", 1, 0, base_seq=3)

    second = confirm(first.state, "p1", 1, 0, base_seq=3)

    assert refusal_code(second) == ErrorCode.STALE_EDIT
    assert second.entries == ()
    assert cell_values(second.state)[(1, 0)] == ("T", False, "p2")


# ---- AC-2, page with a mocked socket ----


def test_ac2_page_confirm_pencil_is_a_button_present_only_on_a_selected_pencil_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    open_room(page, live_server, fx01_grid, changes=PENCIL_T_BY_P2)
    button = confirm_button(page)

    expect(button).to_have_count(0)
    tap(page, 1, 1)
    expect_selected_cell(page, 1, 1)
    expect(button).to_have_count(0)
    tap(page, 1, 0)
    expect_selected_cell(page, 1, 0)
    expect(button).to_have_count(1)
    expect(button).to_be_enabled()

    expect(button).to_have_text(CONFIRM_TEXT)
    assert button.get_attribute("aria-label") is None
    kind = button.evaluate(
        "el => [el.tagName, el.getAttribute('type')]", timeout=WAIT_TIMEOUT_MS
    )
    assert kind == ["BUTTON", "button"]


def test_ac2_page_a_click_sends_confirm_pencil_and_shows_a_normal_pending_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=PENCIL_T_BY_P2)
    tap(page, 1, 0)
    expect(confirm_button(page)).to_be_enabled()
    # The tap's `select_cell` must be in before the count, or it would look new.
    wait_until_page(
        page,
        lambda: selection_sent(mock.frames_without_pings(), 1, 0),
        "the select_cell of the tap",
    )
    before = len(mock.frames_without_pings())

    click_confirm(page)

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)
    new_frames = new_frames_after(page, mock.frames_without_pings, before, 1)
    sent: list[object] = []
    for frame in new_frames:
        sent.append(parse_client_message(frame))
    assert sent == [ConfirmPencil(row=1, column=0, base_seq=5)]
    expect_selection(page, 1, 0, "across", WORD_W1)

    mock.send(letter_changed_frame(6, 1, 0, "T", "p1", pencil=False))
    expect_seq(page, 6)

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p1")
    assert font_style(cell_at(page, 1, 0)) == "normal"


def test_ac2_page_a_refused_confirmation_shows_the_confirmed_pencil_letter_again(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=PENCIL_T_BY_P2)
    tap(page, 1, 0)
    click_confirm(page)
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 1)
    assert sent == [ConfirmPencil(row=1, column=0, base_seq=5)]

    mock.send(error_frame(ErrorCode.STALE_EDIT))

    expect_cell_shows(page, 1, 0, "T", pencil=True, unconfirmed=False)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")
    assert font_style(cell_at(page, 1, 0)) == "italic"


def test_ac2_page_after_two_confirmations_at_once_the_loser_sees_the_first_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid, changes=PENCIL_T_BY_P2)
    tap(page, 1, 0)
    click_confirm(page)
    wait_for_edit_messages(page, mock.frames_without_pings, 1)

    mock.send(letter_changed_frame(6, 1, 0, "T", "p2", pencil=False))
    expect_seq(page, 6)
    mock.send(error_frame(ErrorCode.STALE_EDIT))

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


def test_ac2_page_confirm_pencil_is_enabled_on_my_pending_pencil_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)
    page.keyboard.press("t")
    expect_selection(page, 1, 1, "across", WORD_W1)
    tap(page, 1, 0)
    expect_selected_cell(page, 1, 0)
    expect(confirm_button(page)).to_be_enabled()

    click_confirm(page)

    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=True)
    sent = wait_for_edit_messages(page, mock.frames_without_pings, 2)
    assert sent == [
        PencilEdit(row=1, column=0, letter="T"),
        ConfirmPencil(row=1, column=0, base_seq=5),
    ]


def test_ac2_page_confirm_pencil_is_absent_on_a_cell_locked_over_my_pencil_letter(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    mock = open_room(page, live_server, fx01_grid)
    turn_pencil_mode_on(page)
    tap(page, 1, 0)
    page.keyboard.press("x")
    expect_cell_shows(page, 1, 0, "X", pencil=True, unconfirmed=True)
    left = RevealBudget(letters=4, words=1)
    mock.send(reveal_result_frame(6, CellTarget(row=1, column=0), left))
    mock.send(cell_locked_frame(7, 1, 0, "T", revealed=True))
    expect_seq(page, 7)

    tap(page, 1, 0)

    expect_selected_cell(page, 1, 0)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-locked", "true")
    expect(confirm_button(page)).to_have_count(0)


def test_ac2_page_another_player_confirming_my_pencil_letter_makes_it_flash(
    page: Page, live_server: str, fx01_grid: Grid
) -> None:
    changes: ChangeList = [(1, 0, {"letter": "T", "pencil": True, "author": "p1"})]
    mock = open_room(page, live_server, fx01_grid, changes=changes)

    mock.send(letter_changed_frame(6, 1, 0, "T", "p2", pencil=False))

    # `p2` has colour 1 in the default roster.
    expect(cell_at(page, 1, 0)).to_have_attribute("data-flash", "1")
    expect_cell_shows(page, 1, 0, "T", pencil=False, unconfirmed=False)
    expect(cell_at(page, 1, 0)).to_have_attribute("data-author", "p2")


# ---- AC-2, two pages on the live server ----


def test_ac2_live_bob_confirms_anas_pencil_letter_on_both_pages(
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
        expect_cell_shows(bob_page, 1, 0, "T", pencil=True, unconfirmed=False)
        tap(bob_page, 1, 0)

        click_confirm(bob_page)

        styles: list[str] = []
        for watcher in (page, bob_page):
            expect_cell_shows(watcher, 1, 0, "T", pencil=False, unconfirmed=False)
            styles.append(font_style(cell_at(watcher, 1, 0)))
    finally:
        bob_context.close()

    assert styles == ["normal", "normal"]
