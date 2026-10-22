"""Shared setup of the tests of spec 020: pencil letters.

This module is not a test file: pytest does not collect it. The tests of spec 020
are in `tests/test_spec_020_*.py`, one file per criterion group:

- `test_spec_020_ac01_pencil_letters.py`: AC-1 (rule, WebSocket, page with a
  mocked socket, live pages) and its edge cases (same letter, locked cell, erase,
  lock over a pending pencil edit, in-app keyboard, flash, checks, reveals);
- `test_spec_020_ac02_confirm.py`: AC-2 (rule, page with a mocked socket, live
  pages) and the flash of a confirmation;
- `test_spec_020_ac03_ac05_completion_and_undo.py`: AC-3 and AC-5 (rule,
  `replay`, `RoomStore`);
- `test_spec_020_ac04_edit_checks.py`: AC-4 (rule, WebSocket);
- `test_spec_020_ac06_pending_and_resend.py`: AC-6 (page with a mocked socket,
  spec 017's reconnection mock);
- `test_spec_020_ac07_controls_a11y.py`: AC-7 (toolbar at every window, keyboard
  run, contrast states, `fr.json`) and the solved-grid edge case of the controls.

It holds what more than one of those files uses: the pencil edits and
confirmations sent with `handle_message`, the rooms built from them, the frames a
mocked socket sends, the edit messages a page sent, and the checks of a cell's
pencil look. The rooms, the simulated WebSocket clients and the mocked room socket
themselves are spec 024's (`spec024_harness`) and, for the reconnection, spec
017's (`spec017_harness`), as the spec's "Test harness" says. The fixtures are
defined in each test file as thin wrappers around the harness functions: a fixture
imported from here would be an unused import for ruff.
"""

from __future__ import annotations

import json
from collections.abc import Callable

from playwright.sync_api import Locator, Page, expect

from nock.grid import Grid
from nock.protocol import (
    ConfirmPencil,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    GridSolved,
    LetterChanged,
    PencilEdit,
    parse_client_message,
)
from nock.room import Outcome, RoomConfig, RoomState, handle_message
from room_panels import open_aide
from spec024_harness import (
    LAST_CELL,
    NOW,
    SETTLE_MS,
    WAIT_TIMEOUT_MS,
    cell_at,
    cell_state,
    check_cell,
    computed,
    full17,
    two_player_room,
    wait_until_page,
    write,
)

RULE_CONFIG = RoomConfig()  # the defaults of `handle_message`
SOLVED_AT = NOW + 754.0  # spec 026 AC-1: the last letter 754 s after creation

Cell = tuple[int, int]
CellValue = tuple[str | None, bool, str | None]  # letter, pencil, author
EditMessage = EditLetter | Erase | PencilEdit | ConfirmPencil

# ---- Pencil edits and confirmations on `handle_message` ----


def pencil(
    state: RoomState,
    player_id: str,
    row: int,
    column: int,
    letter: str,
    *,
    now: float = NOW,
    base_seq: int | None = None,
    config: RoomConfig = RULE_CONFIG,
) -> Outcome:
    """Send `PencilEdit(row, column, letter, base_seq)` from a player."""
    message = PencilEdit(row=row, column=column, letter=letter, base_seq=base_seq)
    return handle_message(state, player_id, message, now, config)


def accepted_pencil(
    state: RoomState,
    player_id: str,
    row: int,
    column: int,
    letter: str,
    *,
    now: float = NOW,
    base_seq: int | None = None,
) -> Outcome:
    """Send a pencil edit, after checking it was not refused."""
    outcome = pencil(state, player_id, row, column, letter, now=now, base_seq=base_seq)
    assert outcome.reply == (), outcome.reply
    return outcome


def confirm(
    state: RoomState,
    player_id: str,
    row: int,
    column: int,
    *,
    now: float = NOW,
    base_seq: int | None = None,
    config: RoomConfig = RULE_CONFIG,
) -> Outcome:
    """Send `ConfirmPencil(row, column, base_seq)` from a player."""
    message = ConfirmPencil(row=row, column=column, base_seq=base_seq)
    return handle_message(state, player_id, message, now, config)


def accepted_confirm(
    state: RoomState,
    player_id: str,
    row: int,
    column: int,
    *,
    now: float = NOW,
    base_seq: int | None = None,
) -> Outcome:
    """Send a confirmation, after checking it was not refused."""
    outcome = confirm(state, player_id, row, column, now=now, base_seq=base_seq)
    assert outcome.reply == (), outcome.reply
    return outcome


def solved_room(grid: Grid) -> RoomState:
    """`FULL17` after `p2` wrote `T` at (4, 4) at `SOLVED_AT` (spec 026 AC-1): seq 21.

    `p1` wrote every other cell with a normal letter, so (1, 0) holds `T` by `p1`
    with `changed_seq` 3.
    """
    row, column = LAST_CELL
    state = write(full17(grid), "p2", row, column, "T", SOLVED_AT).state
    assert state.solved is True
    assert state.seq == 21
    return state


def locked_room(grid: Grid) -> RoomState:
    """A FX-01 room where `p1` wrote `T` at (1, 0) at NOW and a check locked it.

    The check (spec 023) gives `check_result` (seq 4) then `cell_locked` (seq 5),
    so the locked cell has `changed_seq` 5 and no `changed_by`.
    """
    written = write(two_player_room(grid), "p1", 1, 0, "T").state
    state = check_cell(written, 1, 0)
    assert cell_state(state, 1, 0).locked is True
    assert state.seq == 5
    return state


def cell_values(state: RoomState) -> dict[Cell, CellValue]:
    """The (letter, pencil, author) of every letter cell of a room."""
    values: dict[Cell, CellValue] = {}
    for cell in state.cells:
        values[(cell.row, cell.column)] = (cell.letter, cell.pencil, cell.author)
    return values


# ---- Frames a mocked room socket sends ----


def letter_changed_frame(
    seq: int,
    row: int,
    column: int,
    letter: str | None,
    player_id: str,
    *,
    pencil: bool,
) -> str:
    event = LetterChanged(
        seq=seq,
        row=row,
        column=column,
        letter=letter,
        pencil=pencil,
        player_id=player_id,
    )
    return event.model_dump_json()


def error_frame(code: ErrorCode) -> str:
    return ErrorMessage(code=code, message="refused").model_dump_json()


def grid_solved_frame(seq: int) -> str:
    return GridSolved(seq=seq, elapsed_ms=754000).model_dump_json()


# ---- What a page sent ----


def edit_messages(frames: list[str]) -> list[EditMessage]:
    """The `edit_letter`, `erase`, `pencil_edit` and `confirm_pencil` messages sent.

    `select_cell`, `join` and `ping` frames are left aside (spec 008's harness and
    the lead's note of 2026-10-15 on spec 017's heartbeat).
    """
    found: list[EditMessage] = []
    for frame in frames:
        if json.loads(frame)["type"] == "ping":
            continue
        message = parse_client_message(frame)
        if isinstance(message, EditLetter | Erase | PencilEdit | ConfirmPencil):
            found.append(message)
    return found


def wait_for_edit_messages(
    page: Page, frames: Callable[[], list[str]], count: int
) -> list[EditMessage]:
    """Wait for `count` edit messages, give extra ones time to come, return all."""
    wait_until_page(
        page, lambda: len(edit_messages(frames())) >= count, f"{count} edit messages"
    )
    page.wait_for_timeout(SETTLE_MS)
    return edit_messages(frames())


def new_frames_after(
    page: Page, frames: Callable[[], list[str]], before: int, count: int
) -> list[str]:
    """Wait for `count` frames past the first `before`, give extra ones time, return.

    Args:
        page: The page that sends the frames.
        frames: Gives the frames the page sent so far, without `ping` frames.
        before: How many frames there were before the action under test.
        count: How many new frames the action should send.
    """
    wait_until_page(page, lambda: len(frames()) >= before + count, "new frames")
    page.wait_for_timeout(SETTLE_MS)
    return frames()[before:]


def edit_messages_after_a_pause(
    page: Page, frames: Callable[[], list[str]]
) -> list[EditMessage]:
    """The edit messages sent so far, after giving an unwanted one time to come."""
    page.wait_for_timeout(SETTLE_MS)
    return edit_messages(frames())


# ---- The room page's pencil controls and cells ----


def pencil_toggle(page: Page) -> Locator:
    return page.get_by_test_id("pencil-toggle")


def confirm_button(page: Page) -> Locator:
    return page.get_by_test_id("confirm-pencil")


def click_pencil_toggle(page: Page) -> None:
    """Click `pencil-toggle` (bounded wait: the control may not exist yet)."""
    pencil_toggle(page).click(timeout=WAIT_TIMEOUT_MS)


def turn_pencil_mode_on(page: Page) -> None:
    """Click `pencil-toggle` once and wait until it says it is pressed."""
    click_pencil_toggle(page)
    expect(pencil_toggle(page)).to_have_attribute("aria-pressed", "true")


def click_confirm(page: Page) -> None:
    """Click `confirm-pencil` (bounded wait: the control may not exist yet).

    It is the first item of the Aide menu (spec 043), which is opened first.
    """
    open_aide(page)
    confirm_button(page).click(timeout=WAIT_TIMEOUT_MS)


def tap(page: Page, row: int, column: int) -> None:
    cell_at(page, row, column).click(timeout=WAIT_TIMEOUT_MS)


def expect_selected_cell(page: Page, row: int, column: int) -> None:
    """Wait until the grid's selected cell is (row, column), whatever the word."""
    grid = page.get_by_test_id("grid")
    expect(grid).to_have_attribute("data-selected-row", str(row))
    expect(grid).to_have_attribute("data-selected-column", str(column))


def expect_cell_shows(
    page: Page,
    row: int,
    column: int,
    letter: str,
    *,
    pencil: bool,
    unconfirmed: bool,
) -> None:
    """Wait until a cell shows `letter` ("" when empty) with these two flags."""
    cell = cell_at(page, row, column)
    expect(cell).to_have_attribute("data-letter", letter)
    expect(cell).to_have_attribute("data-pencil", "true" if pencil else "false")
    expect(cell).to_have_attribute(
        "data-unconfirmed", "true" if unconfirmed else "false"
    )


def font_style(cell: Locator) -> str:
    """The computed `font-style` of a `cell` element."""
    return computed(cell, "fontStyle")


def text_colour(cell: Locator) -> str:
    """The computed `color` of a `cell` element."""
    return computed(cell, "color")
