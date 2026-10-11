"""Room state models and the pure rules applied to each event.

Nothing here does I/O, reads a clock or touches the network: time is passed in
as `now`. The runtime that drives these functions is `nock.hub`.
"""

from __future__ import annotations

import secrets
import unicodedata
from collections.abc import Callable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from nock.grid import Grid, LetterCell
from nock.protocol import (
    CellLocked,
    CellView,
    ChatMessage,
    CheckResult,
    ClientMessage,
    Colour,
    ConfirmPencil,
    Coordinate,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    FlagChanged,
    GridFullWrong,
    GridSolved,
    GridView,
    HelpMode,
    HostChanged,
    Join,
    Letter,
    LetterCellView,
    LetterChanged,
    Nickname,
    PencilEdit,
    PlayerId,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    ResumeToken,
    RevealBudget,
    RevealResult,
    RoomSettings,
    Selection,
    SelectionMoved,
    Seq,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    VoteClosed,
    VoteOpened,
    grid_view,
)

Clock = Callable[[], float]  # seconds since the epoch; the default is time.time
RoomCode = Annotated[str, Field(pattern=r"^[A-Z0-9]{6}$")]

RATE_WINDOW_SECONDS: float = 1.0  # spec 037 AC-3
MAX_PLAYERS: int = 8  # spec 012 AC-4
# Space, hyphen, apostrophe, right single quotation mark (U+2019), underscore.
NICKNAME_PUNCTUATION: str = " -'" + chr(0x2019) + "_"
NICKNAME_MIN_LENGTH: int = 2
NICKNAME_MAX_LENGTH: int = 20
DEFAULT_REVEAL_BUDGET: RevealBudget = RevealBudget(letters=5, words=1)  # spec 024
DEFAULT_SETTINGS: RoomSettings = RoomSettings(
    help_mode=HelpMode.FREE, reveal_budget=DEFAULT_REVEAL_BUDGET, locked=False
)

# The 16 server messages that carry a seq (spec 039, "seq" column).
SeqEvent = Annotated[
    LetterChanged
    | CellLocked
    | PlayerJoined
    | PlayerLeft
    | PlayerStateChanged
    | CheckResult
    | RevealResult
    | VoteOpened
    | VoteClosed
    | FlagChanged
    | ChatMessage
    | SettingsChanged
    | HostChanged
    | PlayerMuted
    | GridSolved
    | GridFullWrong,
    Field(discriminator="type"),
]


class RoomModel(BaseModel):
    """Base of the room models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RoomConfig(RoomModel):
    """Thresholds of the room rules. Defaults are the backlog values."""

    idle_after_seconds: float = Field(default=120.0, gt=0)  # spec 013 AC-1
    host_handover_seconds: float = Field(default=60.0, gt=0)  # spec 014 AC-3
    silence_timeout_seconds: float = Field(default=6.0, gt=0)  # spec 017 AC-4
    resume_window_seconds: float = Field(default=300.0, gt=0)  # spec 017 AC-3
    max_edits_per_second: int = Field(default=20, ge=1)  # spec 037 AC-3
    snapshot_every: int = Field(default=100, ge=1)  # spec 018
    tick_seconds: float = Field(default=1.0, gt=0)  # how often the hub runs tick()


DEFAULT_CONFIG: RoomConfig = RoomConfig()


class CellState(RoomModel):
    """The room's state of one letter cell."""

    row: Coordinate
    column: Coordinate
    letter: Letter | None = None
    pencil: StrictBool = False
    author: PlayerId | None = None  # None when empty or revealed
    locked: StrictBool = False
    revealed: StrictBool = False
    wrong: StrictBool = False
    # seq of the last letter_changed or cell_locked on it
    changed_seq: int = Field(default=0, ge=0, strict=True)
    # who made that change; None: nobody yet, or a reveal
    changed_by: PlayerId | None = None


class UndoEntry(RoomModel):
    """A player's last edit and the cell as it was before it (spec 018 AC-3)."""

    row: Coordinate
    column: Coordinate
    seq: Seq  # seq of that edit's letter_changed
    letter: Letter | None  # the cell before the edit
    pencil: StrictBool
    author: PlayerId | None


class PlayerRecord(RoomModel):
    """A player of the room, as the server keeps them (never sent as is)."""

    player_id: PlayerId
    resume_token: ResumeToken  # secret, spec 039 decision 5
    nickname: Nickname
    colour: Colour
    is_host: StrictBool
    muted: StrictBool = False
    state: PlayerState = PlayerState.ACTIVE
    joined_seq: Seq  # seq of their player_joined: smaller = present longer
    last_input_at: float  # spec 013: last message other than join and ping
    last_seen_at: float  # spec 017: last frame of any kind
    disconnected_at: float | None = None
    selection: Selection | None = None
    # spec 037 AC-3: times of the edits accepted in the last second
    recent_edits: tuple[float, ...] = ()
    last_edit: UndoEntry | None = None  # spec 018 AC-3


class RoomState(RoomModel):
    """The whole state of one room. Replaced, never mutated."""

    code: RoomCode
    grid: Grid  # holds the answers: never sent to a browser
    grid_number: int | None = None  # catalogue number (spec 004)
    created_at: float
    seq: int = Field(default=0, ge=0, strict=True)  # seq of the last event
    cells: tuple[CellState, ...]  # one per letter cell, in the order of grid.cells
    players: tuple[PlayerRecord, ...] = Field(default=(), max_length=8)
    settings: RoomSettings = DEFAULT_SETTINGS
    reveal_budget: RevealBudget = DEFAULT_REVEAL_BUDGET  # what is left
    removed_tokens: tuple[ResumeToken, ...] = ()  # spec 014 AC-1
    solved: StrictBool = False  # spec 026


class LogEntry(RoomModel):
    """One numbered event as written to the room's log (spec 018)."""

    at: float  # clock time of the step that made it
    event: SeqEvent  # exactly what the players receive
    resume_token: ResumeToken | None = None  # on player_joined only
    undo: StrictBool = False  # a letter_changed made by an undo (spec 018)


class Disconnect(RoomModel):
    """A player connection the hub must close after a step."""

    player_id: PlayerId
    close_code: int = Field(ge=1000, le=4999, strict=True)
    error: ErrorMessage | None = None  # sent just before closing


class Outcome(RoomModel):
    """What one step of the rules produced (see the delivery order of spec 011)."""

    state: RoomState
    entries: tuple[LogEntry, ...] = ()  # numbered events, in seq order
    reply: tuple[ServerMessage, ...] = ()  # to the sender's connection only
    # to every joined connection except the sender's
    to_others: tuple[SelectionMoved, ...] = ()
    close_sender: StrictBool = False  # close the sender's socket, code 1000
    disconnects: tuple[Disconnect, ...] = ()


def new_room(
    code: str, grid: Grid, now: float, grid_number: int | None = None
) -> RoomState:
    """Return a fresh room: seq 0, no player, every letter cell empty.

    Args:
        code: The room code, six characters of A-Z and 0-9.
        grid: The grid to solve.
        now: Clock time of the creation.
        grid_number: Catalogue number of the grid, None for a bare grid.

    Returns:
        The new state. `cells` holds one empty cell per letter cell of `grid`,
        in the order of `grid.cells`.

    Raises:
        pydantic.ValidationError: `code` breaks the room code pattern.
    """
    cells: list[CellState] = []
    for grid_cell in grid.cells:
        if isinstance(grid_cell, LetterCell):
            cells.append(CellState(row=grid_cell.row, column=grid_cell.column))
    return RoomState(
        code=code,
        grid=grid,
        grid_number=grid_number,
        created_at=now,
        cells=tuple(cells),
    )


def grid_state(state: RoomState) -> GridView:
    """Return the client view of the room's grid with its current letters.

    Args:
        state: The room.

    Returns:
        `grid_view(state.grid)` with the letter, pencil, author, locked,
        revealed and wrong values of each letter cell taken from `state.cells`.
        It never holds an answer.
    """
    cells_by_position: dict[tuple[int, int], CellState] = {}
    for cell_state in state.cells:
        cells_by_position[(cell_state.row, cell_state.column)] = cell_state

    fresh_view = grid_view(state.grid)
    cell_views: list[CellView] = []
    for cell_view in fresh_view.cells:
        if isinstance(cell_view, LetterCellView):
            cell_state = cells_by_position[(cell_view.row, cell_view.column)]
            cell_view = LetterCellView(
                row=cell_view.row,
                column=cell_view.column,
                letter=cell_state.letter,
                pencil=cell_state.pencil,
                author=cell_state.author,
                locked=cell_state.locked,
                revealed=cell_state.revealed,
                wrong=cell_state.wrong,
            )
        cell_views.append(cell_view)
    return GridView(
        width=fresh_view.width, height=fresh_view.height, cells=tuple(cell_views)
    )


# ---- Rules owned by later specs ---------------------------------------------
# Each function below has its final signature. Until the spec that owns it is
# built, it does the least that keeps the engine running (spec 011).


def normalize_nickname(text: str) -> str:
    """Return the nickname as stored: NFC-normalised, then stripped.

    Args:
        text: The nickname as typed.

    Returns:
        The nickname, 2 to 20 characters, made of letters, combining marks,
        ASCII digits and NICKNAME_PUNCTUATION, with at least one letter or digit.

    Raises:
        ValueError: a rule is broken; the message names the rule.
    """
    nickname = unicodedata.normalize("NFC", text).strip()
    if len(nickname) < NICKNAME_MIN_LENGTH or len(nickname) > NICKNAME_MAX_LENGTH:
        raise ValueError(
            f"The nickname must have {NICKNAME_MIN_LENGTH} to "
            f"{NICKNAME_MAX_LENGTH} characters, got {len(nickname)}"
        )
    has_letter_or_digit = False
    for character in nickname:
        category = unicodedata.category(character)
        is_letter = category.startswith("L")
        is_digit = "0" <= character <= "9"
        is_mark = category in ("Mn", "Mc")
        is_punctuation = character in NICKNAME_PUNCTUATION
        if not (is_letter or is_digit or is_mark or is_punctuation):
            raise ValueError(f"Character not allowed in a nickname: {character!r}")
        if is_letter or is_digit:
            has_letter_or_digit = True
    if not has_letter_or_digit:
        raise ValueError("The nickname needs at least one letter or digit")
    return nickname


def player_views(state: RoomState) -> tuple[PlayerView, ...]:
    """Return the players as the other players see them, in room order.

    Args:
        state: The room.

    Returns:
        One view per player. A view never holds the resume token.
    """
    views: list[PlayerView] = []
    for player in state.players:
        views.append(_view_of(player))
    return tuple(views)


def snapshot_for(state: RoomState, player_id: str) -> Snapshot:
    """Return the snapshot that player `player_id` receives.

    Args:
        state: The room.
        player_id: A player of the room.

    Returns:
        The snapshot, with the player's own resume token.

    Raises:
        KeyError: no player `player_id` in the room.
    """
    for player in state.players:
        if player.player_id == player_id:
            return Snapshot(
                seq=state.seq,
                you=player.player_id,
                resume_token=player.resume_token,
                grid=grid_state(state),
                players=player_views(state),
                settings=state.settings,
                reveal_budget=state.reveal_budget,
                flags=(),
                chat=(),
                open_vote=None,
                timer_elapsed_ms=0,
                timer_running=False,
                solved=state.solved,
            )
    raise KeyError(player_id)


def join_room(
    state: RoomState,
    message: Join,
    now: float,
    new_player_id: str,
    new_resume_token: str,
) -> Outcome:
    """Apply a join on a connection that has not joined yet.

    The steps run in this order and the first that applies ends the join: resume
    of a known player, room full, invalid nickname, new player. Spec 014 adds
    the removed and locked refusals.

    Args:
        state: The room.
        message: The join received.
        now: Clock time of the join.
        new_player_id: Id given to a new player.
        new_resume_token: Token given to a new player.

    Returns:
        The outcome. A success replies with the snapshot of the player.
    """
    resumed = _find_by_token(state, message.resume_token)
    if resumed is not None:
        return _resume_player(state, resumed, now)
    if len(state.players) >= MAX_PLAYERS:
        refusal = ErrorMessage(code=ErrorCode.ROOM_FULL, message="The room is full.")
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    try:
        nickname = normalize_nickname(message.nickname)
    except ValueError as error:
        refusal = ErrorMessage(code=ErrorCode.INVALID_NICKNAME, message=str(error))
        return Outcome(state=state, reply=(refusal,))
    return _add_player(state, nickname, now, new_player_id, new_resume_token)


def disconnect_player(state: RoomState, player_id: str, now: float) -> Outcome:
    """Apply the closing of a player's connection.

    The player keeps their seat. A player who is not in the room, or who is
    already disconnected, changes nothing.

    Args:
        state: The room before the connection closed.
        player_id: Id of the player whose connection closed.
        now: Current time in seconds.

    Returns:
        The outcome, with the player marked disconnected when they were not yet.
    """
    for player in state.players:
        if player.player_id != player_id:
            continue
        if player.state == PlayerState.DISCONNECTED:
            break
        changed = player.model_copy(
            update={"state": PlayerState.DISCONNECTED, "disconnected_at": now}
        )
        return _with_state_change(state, changed, now)
    return Outcome(state=state)


def _view_of(player: PlayerRecord) -> PlayerView:
    """Return the public view of one player."""
    return PlayerView(
        player_id=player.player_id,
        nickname=player.nickname,
        colour=player.colour,
        state=player.state,
        is_host=player.is_host,
        muted=player.muted,
        selection=player.selection,
    )


def _find_by_token(state: RoomState, token: str | None) -> PlayerRecord | None:
    """Return the player who owns `token`, or None."""
    if token is None:
        return None
    for player in state.players:
        if secrets.compare_digest(player.resume_token, token):
            return player
    return None


def _replace_player(state: RoomState, changed: PlayerRecord) -> RoomState:
    """Return the state with `changed` in place of the player of the same id."""
    players: list[PlayerRecord] = []
    for player in state.players:
        if player.player_id == changed.player_id:
            players.append(changed)
        else:
            players.append(player)
    return state.model_copy(update={"players": tuple(players)})


def _with_state_change(state: RoomState, changed: PlayerRecord, now: float) -> Outcome:
    """Store `changed` and number one player_state_changed event for it."""
    seq = state.seq + 1
    event = PlayerStateChanged(
        seq=seq, player_id=changed.player_id, state=changed.state
    )
    new_state = _replace_player(state, changed).model_copy(update={"seq": seq})
    return Outcome(state=new_state, entries=(LogEntry(at=now, event=event),))


def _resume_player(state: RoomState, player: PlayerRecord, now: float) -> Outcome:
    """Join `player` again on a new connection."""
    resumed = player.model_copy(update={"last_seen_at": now, "last_input_at": now})
    if player.state == PlayerState.DISCONNECTED:
        resumed = resumed.model_copy(
            update={"state": PlayerState.ACTIVE, "disconnected_at": None}
        )
        outcome = _with_state_change(state, resumed, now)
    else:
        outcome = Outcome(state=_replace_player(state, resumed))
    reply = (snapshot_for(outcome.state, player.player_id),)
    return outcome.model_copy(update={"reply": reply})


def _unique_nickname(state: RoomState, nickname: str) -> str:
    """Return `nickname`, or the first `nickname n` (n >= 2) no player has."""
    taken: set[str] = set()
    for player in state.players:
        taken.add(player.nickname.casefold())
    if nickname.casefold() not in taken:
        return nickname
    number = 2
    while True:
        suffix = f" {number}"
        base = nickname[: NICKNAME_MAX_LENGTH - len(suffix)].rstrip()
        candidate = base + suffix
        if candidate.casefold() not in taken:
            return candidate
        number += 1


def _lowest_free_colour(state: RoomState) -> int:
    """Return the lowest colour index 0 to 7 that no player has."""
    used: set[int] = set()
    for player in state.players:
        used.add(player.colour)
    for colour in range(MAX_PLAYERS):
        if colour not in used:
            return colour
    raise ValueError("Every colour is taken")


def _add_player(
    state: RoomState,
    nickname: str,
    now: float,
    player_id: str,
    resume_token: str,
) -> Outcome:
    """Add a new player at the end of the room and number their player_joined."""
    seq = state.seq + 1
    has_host = False
    for existing in state.players:
        if existing.is_host:
            has_host = True
    player = PlayerRecord(
        player_id=player_id,
        resume_token=resume_token,
        nickname=_unique_nickname(state, nickname),
        colour=_lowest_free_colour(state),
        is_host=not has_host,
        joined_seq=seq,
        last_input_at=now,
        last_seen_at=now,
    )
    new_state = state.model_copy(
        update={"players": (*state.players, player), "seq": seq}
    )
    event = PlayerJoined(seq=seq, player=_view_of(player))
    entry = LogEntry(at=now, event=event, resume_token=resume_token)
    reply = (snapshot_for(new_state, player_id),)
    return Outcome(state=new_state, entries=(entry,), reply=reply)


def handle_message(
    state: RoomState,
    player_id: str,
    message: ClientMessage,
    now: float,
    config: RoomConfig = DEFAULT_CONFIG,
) -> Outcome:
    """Apply a message of a joined player (spec 015 and later).

    Edits (`edit_letter`, `erase`) are handled here. `pencil_edit` and
    `confirm_pencil` only go through the rate limit (spec 037); spec 020 gives
    them their meaning. Until the spec that gives another message its meaning
    is built, the message is read and ignored: the state is unchanged and
    nothing is sent.
    """
    if isinstance(message, EditLetter):
        return _apply_edit(state, player_id, message, now, config)
    if isinstance(message, Erase):
        return _apply_edit(state, player_id, message, now, config)
    if isinstance(message, PencilEdit | ConfirmPencil):
        return _count_unhandled_edit(state, player_id, now, config)
    return Outcome(state=state)


def _find_player(state: RoomState, player_id: str) -> PlayerRecord | None:
    """Return the room's record of the player, or None when the player is unknown."""
    for player in state.players:
        if player.player_id == player_id:
            return player
    return None


def _recent_edits(player: PlayerRecord, now: float) -> tuple[float, ...]:
    """Return the times of the player's edits inside the rate window.

    Returns:
        The times `t` with `t > now - RATE_WINDOW_SECONDS`.
    """
    recent: list[float] = []
    for edit_time in player.recent_edits:
        if edit_time > now - RATE_WINDOW_SECONDS:
            recent.append(edit_time)
    return tuple(recent)


def _rate_limit_refusal(
    state: RoomState, player_id: str, now: float, config: RoomConfig
) -> Outcome | None:
    """Return the rate_limited refusal when the player has used up the window."""
    player = _find_player(state, player_id)
    if player is None:
        return None
    if len(_recent_edits(player, now)) >= config.max_edits_per_second:
        return _refuse(
            state,
            ErrorCode.RATE_LIMITED,
            f"At most {config.max_edits_per_second} edits a second.",
        )
    return None


def _with_edit_counted(state: RoomState, player_id: str, now: float) -> RoomState:
    """Return the state with `now` added to the player's recent edits."""
    player = _find_player(state, player_id)
    if player is None:
        return state
    recent = _recent_edits(player, now)
    changed = player.model_copy(update={"recent_edits": (*recent, now)})
    return _replace_player(state, changed)


def _count_unhandled_edit(
    state: RoomState, player_id: str, now: float, config: RoomConfig
) -> Outcome:
    """Count a pencil edit or a confirmation, which spec 020 will give a meaning."""
    refusal = _rate_limit_refusal(state, player_id, now, config)
    if refusal is not None:
        return refusal
    return Outcome(state=_with_edit_counted(state, player_id, now))


def _refuse(state: RoomState, code: ErrorCode, text: str) -> Outcome:
    """Return an outcome that changes nothing and answers with one error."""
    return Outcome(state=state, reply=(ErrorMessage(code=code, message=text),))


def _find_cell(state: RoomState, row: int, column: int) -> CellState | None:
    """Return the room's state of the letter cell at (row, column), or None."""
    for cell in state.cells:
        if cell.row == row and cell.column == column:
            return cell
    return None


def _edit_refusal(
    state: RoomState,
    player_id: str,
    edit: EditLetter | Erase,
    now: float,
    config: RoomConfig,
) -> Outcome | None:
    """Run the edit checks in their fixed order; return the first refusal.

    Checks 4 (stale edit, spec 017) and 5 (solved grid, spec 026) belong to
    later specs: they keep their place in the order but never refuse yet.
    """
    rate_refusal = _rate_limit_refusal(state, player_id, now, config)
    if rate_refusal is not None:
        return rate_refusal
    cell = _find_cell(state, edit.row, edit.column)
    if cell is None:
        return _refuse(
            state,
            ErrorCode.NOT_A_LETTER_CELL,
            f"({edit.row}, {edit.column}) is not a letter cell.",
        )
    if cell.locked:
        return _refuse(
            state,
            ErrorCode.CELL_LOCKED,
            f"({edit.row}, {edit.column}) is locked.",
        )
    return None


def _letter_of(edit: EditLetter | Erase) -> str | None:
    """Return the letter an edit writes: the typed letter, None for an erase."""
    if isinstance(edit, EditLetter):
        return edit.letter
    return None


def _apply_edit(
    state: RoomState,
    player_id: str,
    edit: EditLetter | Erase,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Check one edit, then write it in the cell and number its event."""
    refusal = _edit_refusal(state, player_id, edit, now, config)
    if refusal is not None:
        return refusal

    letter = _letter_of(edit)
    seq = state.seq + 1
    author = player_id if letter is not None else None
    cells: list[CellState] = []
    for cell in state.cells:
        if cell.row == edit.row and cell.column == edit.column:
            edited_cell = cell.model_copy(
                update={
                    "letter": letter,
                    "pencil": False,
                    "author": author,
                    "wrong": False,
                    "changed_seq": seq,
                    "changed_by": player_id,
                }
            )
            cells.append(edited_cell)
        else:
            cells.append(cell)
    counted_state = _with_edit_counted(state, player_id, now)
    new_state = counted_state.model_copy(update={"cells": tuple(cells), "seq": seq})
    event = LetterChanged(
        seq=seq,
        row=edit.row,
        column=edit.column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return Outcome(state=new_state, entries=(LogEntry(at=now, event=event),))


def tick(state: RoomState, now: float, config: RoomConfig = DEFAULT_CONFIG) -> Outcome:
    """Apply the passing of time (spec 013, 014, 017)."""
    return Outcome(state=state)


def replay(state: RoomState, entry: LogEntry) -> RoomState:
    """Return the state after a logged event (spec 018)."""
    return state


def after_restart(state: RoomState, now: float) -> Outcome:
    """Apply what a server restart changes (spec 018)."""
    return Outcome(state=state)
