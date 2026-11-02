"""Tests of `gameplay/co-op.md` AC-21: the five error codes that end a pending edit
answer only the messages rule 12 names.

The server through the real WebSocket (`spec022_harness.chat_room`, the real clock,
an edit limit high enough for the 18 letters), with Ana (host, first to join) and
Bob joined on FX-01. Each message is sent as its JSON frame and the answer is read
on Ana's socket:

- a `select_cell`, a check and a reveal of the clue cell (0, 0) each get one
  `error` `not_a_letter_cell`;
- once Ana's 18 letters, `S` at (1, 4) last, have solved the grid
  (`grid_solved` event), her `undo`, a check of the grid and a reveal of (1, 0)
  each get one `error` `grid_solved`;
- on that solved grid her `chat`, `react`, `flag`, `vote`, `mute_player`,
  `lock_room`, `change_settings`, `remove_player` of Bob, a second `join` and a
  `ping` get none of `rate_limited`, `not_a_letter_cell`, `cell_locked`,
  `stale_edit` and `grid_solved`. The answers have all come once the pong of a
  last `ping` has: the room handles a socket's frames in order.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest
from pydantic import BaseModel

from nock.grid import Grid
from nock.protocol import (
    CellTarget,
    ChangeSettings,
    Chat,
    Check,
    ClueRef,
    Direction,
    EditLetter,
    ErrorCode,
    Flag,
    GridSolved,
    GridTarget,
    HelpMode,
    Join,
    LockRoom,
    MutePlayer,
    Ping,
    Pong,
    React,
    Reaction,
    RemovePlayer,
    Reveal,
    RevealBudget,
    SelectCell,
    Undo,
    Vote,
)
from spec017_harness import Peer, error_events, grid_from_text, join_two, make_dist_dir
from spec022_harness import WS_CONFIG, chat_room
from spec043_harness import FX01_SOLUTION

EDIT_ERROR_CODES = {
    ErrorCode.RATE_LIMITED,
    ErrorCode.NOT_A_LETTER_CELL,
    ErrorCode.CELL_LOCKED,
    ErrorCode.STALE_EDIT,
    ErrorCode.GRID_SOLVED,
}
SOLVING_CELL = (1, 4)  # Ana's `S`, her last letter
MIME = ClueRef(row=0, column=2, clue_index=0)


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def dist_dir(tmp_path: Path) -> Path:
    return make_dist_dir(tmp_path)


def send(peer: Peer, message: BaseModel) -> None:
    """Send any client message as its JSON frame."""
    peer.send_raw(message.model_dump_json())


def answer_code(peer: Peer, message: BaseModel) -> ErrorCode:
    """Send a message that the server refuses; return the code of its one error."""
    errors_before = len(error_events(peer))
    send(peer, message)
    peer.wait_until(
        lambda: len(error_events(peer)) > errors_before, f"the answer to {message!r}"
    )
    return error_events(peer)[errors_before].code


def pong_count(peer: Peer) -> int:
    count = 0
    for message in peer.events():
        if isinstance(message, Pong):
            count += 1
    return count


def wait_for_a_last_pong(peer: Peer) -> None:
    """Send a `ping` and wait for its pong: every earlier frame is answered."""
    pongs_before = pong_count(peer)
    send(peer, Ping())
    peer.wait_until(lambda: pong_count(peer) > pongs_before, "the pong of a ping")


def solve_the_grid(peer: Peer) -> None:
    """Ana writes FX-01's 18 letters, `S` at (1, 4) last, and the grid is solved."""
    for (row, column), letter in FX01_SOLUTION.items():
        if (row, column) != SOLVING_CELL:
            send(peer, EditLetter(row=row, column=column, letter=letter))
    row, column = SOLVING_CELL
    send(peer, EditLetter(row=row, column=column, letter=FX01_SOLUTION[SOLVING_CELL]))
    peer.wait_until(
        lambda: any(isinstance(event, GridSolved) for event in peer.events()),
        "the grid_solved event",
    )


def test_ac21_a_select_a_check_and_a_reveal_of_a_clue_cell_get_not_a_letter_cell(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    clue_cell = CellTarget(row=0, column=0)
    messages: list[BaseModel] = [
        SelectCell(row=0, column=0, direction=Direction.ACROSS),
        Check(target=clue_cell),
        Reveal(target=clue_cell),
    ]
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, _registry, code),
        contextlib.ExitStack() as ana_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        ana, _bob = join_two(ana_stack, bob_stack, client, code)

        codes = [answer_code(ana, message) for message in messages]

    assert codes == [ErrorCode.NOT_A_LETTER_CELL] * 3


def test_ac21_on_a_solved_grid_an_undo_a_check_and_a_reveal_get_grid_solved(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    messages: list[BaseModel] = [
        Undo(),
        Check(target=GridTarget()),
        Reveal(target=CellTarget(row=1, column=0)),
    ]
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, _registry, code),
        contextlib.ExitStack() as ana_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        ana, _bob = join_two(ana_stack, bob_stack, client, code)
        solve_the_grid(ana)

        codes = [answer_code(ana, message) for message in messages]

    assert codes == [ErrorCode.GRID_SOLVED] * 3


def test_ac21_on_a_solved_grid_no_other_message_gets_one_of_the_five_codes(
    fx01_grid: Grid, dist_dir: Path
) -> None:
    with (
        chat_room(fx01_grid, dist_dir, WS_CONFIG) as (client, _registry, code),
        contextlib.ExitStack() as ana_stack,
        contextlib.ExitStack() as bob_stack,
    ):
        ana, bob = join_two(ana_stack, bob_stack, client, code)
        bob_id = bob.snapshot().you
        solve_the_grid(ana)
        errors_before = len(error_events(ana))
        messages: list[BaseModel] = [
            Chat(text="Bravo"),
            React(clue=MIME, reaction=Reaction.CLAP),
            Flag(clue=MIME),
            Vote(vote_id=1, yes=True),
            MutePlayer(player_id=bob_id, muted=True),
            LockRoom(locked=True),
            ChangeSettings(
                help_mode=HelpMode.VOTE,
                reveal_budget=RevealBudget(letters=3, words=1),
            ),
            RemovePlayer(player_id=bob_id),
            Join(nickname="Ana", resume_token=None),
            Ping(),
        ]
        for message in messages:
            send(ana, message)
        wait_for_a_last_pong(ana)

        codes = {error.code for error in error_events(ana)[errors_before:]}

    assert codes & EDIT_ERROR_CODES == set()
