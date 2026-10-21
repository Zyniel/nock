"""What changed in a room during one absence of a page (spec 034).

Pure: no I/O. The hub reads the room's state at the page's seen seq and the
logged entries of the absence from the store, and this module turns them into a
catch-up: the changed cells, the lines of the activity feed and the names of the
players of those lines. A catch-up holds no letter of the grid.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Literal, NamedTuple

from pydantic import BaseModel, ConfigDict, Field

from nock.grid import ClueCell, Grid
from nock.protocol import (
    CellLocked,
    CellRef,
    CheckResult,
    ClueRef,
    LetterChanged,
    Nickname,
    PlayerId,
    ResumeToken,
    RevealResult,
    Seq,
    SnapshotSeq,
)
from nock.room import CellState, LogEntry, RoomState, replay

CATCH_UP_LINE_LIMIT: int = 100  # spec 013's feed keeps 100 lines


class CatchUpModel(BaseModel):
    """Base of the catch-up models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class WordCompleted(CatchUpModel):
    """A word completed during the absence."""

    type: Literal["word_completed"] = "word_completed"
    seq: Seq  # the letter_changed that completed it
    player_id: PlayerId  # that letter_changed's player
    clue: ClueRef  # the word, named by its clue


CatchUpLine = Annotated[
    CheckResult | RevealResult | WordCompleted, Field(discriminator="type")
]


class PlayerName(CatchUpModel):
    """The nickname of a player that a catch-up line names."""

    player_id: PlayerId
    nickname: Nickname


class CatchUpRequest(CatchUpModel):
    """The body of POST /api/rooms/{code}/catch-up."""

    resume_token: ResumeToken  # the page's own token (snapshot.resume_token)
    after_seq: SnapshotSeq  # the page's seen seq
    until_seq: SnapshotSeq  # the seq of the snapshot of the return


class CatchUp(CatchUpModel):
    """What changed during one absence. It holds no letter of the grid."""

    after_seq: SnapshotSeq  # as in the request
    until_seq: SnapshotSeq  # as in the request
    cells: tuple[CellRef, ...]  # the changed cells, each once, in row-major order
    lines: tuple[CatchUpLine, ...]  # in seq order, at most CATCH_UP_LINE_LIMIT
    names: tuple[PlayerName, ...]  # the nickname of each player_id of `lines`


class _NamedLine(NamedTuple):
    """A catch-up line and the nickname its player had when they made it."""

    line: CheckResult | RevealResult | WordCompleted
    nickname: str | None  # None: the player was not in the room then


def build_catch_up(
    after_seq: int,
    until_seq: int,
    before: RoomState,
    entries: Sequence[LogEntry],
) -> CatchUp:
    """Return the catch-up of the absence that `entries` hold.

    Args:
        after_seq: The request's `after_seq`, copied to the answer.
        until_seq: The request's `until_seq`, copied to the answer.
        before: The room just before the first entry (`load_room_at`).
        entries: The logged entries of the absence, in seq order, the first one
            right after `before`.

    Returns:
        `cells`: the changed cells. `lines`: the `CheckResult` and `RevealResult`
        events of `entries` as they are (`entry.event`), and a `WordCompleted`
        for each word completed by a `letter_changed` of `entries` (found by
        replaying `entries` from `before`), in seq order; words completed by one
        letter come in clue order (`row`, `column`, `clue_index`); when there
        are more than CATCH_UP_LINE_LIMIT lines, only the last
        CATCH_UP_LINE_LIMIT are kept. `names`: for each distinct `player_id` of
        `lines`, in order of first appearance, the nickname of that player in
        `players` of the replayed state just before the event of their first
        line, that is, the nickname they had when they made it; a player id
        that is not in `players` then is left out.
    """
    named_lines: list[_NamedLine] = []
    state = before
    for entry in entries:
        next_state = replay(state, entry)
        named_lines.extend(_lines_of_entry(state, next_state, entry))
        state = next_state

    kept_lines = named_lines[-CATCH_UP_LINE_LIMIT:]
    lines: list[CheckResult | RevealResult | WordCompleted] = []
    for named_line in kept_lines:
        lines.append(named_line.line)
    return CatchUp(
        after_seq=after_seq,
        until_seq=until_seq,
        cells=_changed_cells(entries),
        lines=tuple(lines),
        names=_names_of(kept_lines),
    )


def _lines_of_entry(
    state_before: RoomState, state_after: RoomState, entry: LogEntry
) -> list[_NamedLine]:
    """Return the catch-up lines that one entry adds, with their player's name.

    Args:
        state_before: The room just before the entry.
        state_after: The room just after it.
        entry: The logged entry.

    Returns:
        The check or reveal result itself, or one `WordCompleted` per word that a
        `letter_changed` completes, in clue order; no line for any other event.
    """
    event = entry.event
    if isinstance(event, CheckResult | RevealResult):
        nickname = _nickname_in(state_before, event.player_id)
        return [_NamedLine(line=event, nickname=nickname)]
    if not isinstance(event, LetterChanged):
        return []

    named_lines: list[_NamedLine] = []
    nickname = _nickname_in(state_before, event.player_id)
    for clue in _words_completed(state_before, state_after, event):
        line = WordCompleted(seq=event.seq, player_id=event.player_id, clue=clue)
        named_lines.append(_NamedLine(line=line, nickname=nickname))
    return named_lines


def _words_completed(
    state_before: RoomState, state_after: RoomState, event: LetterChanged
) -> list[ClueRef]:
    """Return the words that a `letter_changed` completes, in clue order.

    A letter completes a word only when it fills a cell that was empty just
    before it, and the word is then complete: each of its cells holds a letter,
    pencil or not (spec 026).
    """
    if event.letter is None:
        return []
    cell_before = _cell_at(state_before, event.row, event.column)
    if cell_before is None or cell_before.letter is not None:
        return []

    filled_positions = _filled_positions(state_after)
    completed: list[ClueRef] = []
    for clue, positions in _words_of_grid(state_after.grid):
        if (event.row, event.column) not in positions:
            continue
        is_complete = True
        for position in positions:
            if position not in filled_positions:
                is_complete = False
        if is_complete:
            completed.append(clue)
    return completed


def _words_of_grid(grid: Grid) -> list[tuple[ClueRef, list[tuple[int, int]]]]:
    """Return each clue of the grid with the positions of its word, in clue order.

    Clue order is by the clue cell's row, then its column, then the clue's index
    in that cell.
    """
    clue_cells: list[ClueCell] = []
    for cell in grid.cells:
        if isinstance(cell, ClueCell):
            clue_cells.append(cell)
    clue_cells.sort(key=lambda clue_cell: (clue_cell.row, clue_cell.column))

    words: list[tuple[ClueRef, list[tuple[int, int]]]] = []
    for clue_cell in clue_cells:
        for clue_index in range(len(clue_cell.clues)):
            positions = grid.word_cells(clue_cell.row, clue_cell.column, clue_index)
            clue = ClueRef(
                row=clue_cell.row, column=clue_cell.column, clue_index=clue_index
            )
            words.append((clue, positions))
    return words


def _filled_positions(state: RoomState) -> set[tuple[int, int]]:
    """Return the positions of the cells that hold a letter, pencil or not."""
    filled: set[tuple[int, int]] = set()
    for cell in state.cells:
        if cell.letter is not None:
            filled.add((cell.row, cell.column))
    return filled


def _cell_at(state: RoomState, row: int, column: int) -> CellState | None:
    """Return the room's state of the letter cell at (row, column), or None."""
    for cell in state.cells:
        if cell.row == row and cell.column == column:
            return cell
    return None


def _nickname_in(state: RoomState, player_id: str) -> str | None:
    """Return the nickname of a player of `state.players`, or None."""
    for player in state.players:
        if player.player_id == player_id:
            return player.nickname
    return None


def _changed_cells(entries: Sequence[LogEntry]) -> tuple[CellRef, ...]:
    """Return each cell named by a letter_changed or a cell_locked, once, row-major."""
    positions: set[tuple[int, int]] = set()
    for entry in entries:
        event = entry.event
        if isinstance(event, LetterChanged | CellLocked):
            positions.add((event.row, event.column))

    cells: list[CellRef] = []
    for row, column in sorted(positions):
        cells.append(CellRef(row=row, column=column))
    return tuple(cells)


def _names_of(named_lines: list[_NamedLine]) -> tuple[PlayerName, ...]:
    """Return the name of each distinct player of the lines, by first appearance.

    A player who was not in the room when they made their first line is left out.
    """
    seen_ids: set[str] = set()
    names: list[PlayerName] = []
    for named_line in named_lines:
        player_id = named_line.line.player_id
        if player_id in seen_ids:
            continue
        seen_ids.add(player_id)
        if named_line.nickname is not None:
            names.append(PlayerName(player_id=player_id, nickname=named_line.nickname))
    return tuple(names)
