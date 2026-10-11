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
    ChangeSettings,
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
    LeaveReason,
    Letter,
    LetterCellView,
    LetterChanged,
    LockRoom,
    MutePlayer,
    Nickname,
    PencilEdit,
    Ping,
    PlayerId,
    PlayerJoined,
    PlayerLeft,
    PlayerMuted,
    PlayerState,
    PlayerStateChanged,
    PlayerView,
    Pong,
    RemovePlayer,
    ResumeToken,
    RevealBudget,
    RevealResult,
    RoomSettings,
    SelectCell,
    Selection,
    SelectionMoved,
    Seq,
    ServerMessage,
    SettingsChanged,
    Snapshot,
    Undo,
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
_NORMAL_CLOSE_CODE: int = 1000  # a normal closing
SILENCE_CLOSE_CODE: int = 4408  # spec 017: close code of a silent socket
_REMOVED_TEXT: str = "You were removed from this room."
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
    config: RoomConfig = DEFAULT_CONFIG,
) -> Outcome:
    """Apply a join on a connection that has not joined yet.

    The steps run in this order and the first that applies ends the join:
    removed token, resume of a known player, room locked, room full, invalid
    nickname, new player. A token whose player has been disconnected
    for more than the resume window does not resume: that player times out in
    this same step and the join goes on as a new player.

    Args:
        state: The room.
        message: The join received.
        now: Clock time of the join.
        new_player_id: Id given to a new player.
        new_resume_token: Token given to a new player.
        config: Thresholds of the room rules.

    Returns:
        The outcome. A success replies with the snapshot of the player.
    """
    if _is_removed_token(state, message.resume_token):
        refusal = ErrorMessage(code=ErrorCode.REMOVED, message=_REMOVED_TEXT)
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    resumed = _find_by_token(state, message.resume_token)
    timeout_entries: tuple[LogEntry, ...] = ()
    if resumed is not None and _has_timed_out(resumed, now, config):
        timeout = _time_out_player(state, resumed, now)
        state = timeout.state
        timeout_entries = timeout.entries
        resumed = None
    if resumed is not None:
        return _resume_player(state, resumed, now)
    outcome = _join_as_new_player(state, message, now, new_player_id, new_resume_token)
    all_entries = (*timeout_entries, *outcome.entries)
    return outcome.model_copy(update={"entries": all_entries})


def _join_as_new_player(
    state: RoomState,
    message: Join,
    now: float,
    new_player_id: str,
    new_resume_token: str,
) -> Outcome:
    """Run the steps of a join that does not resume: locked, full, nickname, add."""
    if state.settings.locked:
        refusal = ErrorMessage(
            code=ErrorCode.ROOM_LOCKED, message="The room is locked."
        )
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    if len(state.players) >= MAX_PLAYERS:
        refusal = ErrorMessage(code=ErrorCode.ROOM_FULL, message="The room is full.")
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    try:
        nickname = normalize_nickname(message.nickname)
    except ValueError as error:
        refusal = ErrorMessage(code=ErrorCode.INVALID_NICKNAME, message=str(error))
        return Outcome(state=state, reply=(refusal,))
    return _add_player(state, nickname, now, new_player_id, new_resume_token)


def _is_removed_token(state: RoomState, token: str | None) -> bool:
    """Tell whether the host removed the player who owns `token`."""
    if token is None:
        return False
    for removed_token in state.removed_tokens:
        if secrets.compare_digest(removed_token, token):
            return True
    return False


def _has_timed_out(player: PlayerRecord, now: float, config: RoomConfig) -> bool:
    """Tell whether the player is disconnected for more than the resume window."""
    if player.state != PlayerState.DISCONNECTED or player.disconnected_at is None:
        return False
    return now - player.disconnected_at > config.resume_window_seconds


def _time_out_player(state: RoomState, player: PlayerRecord, now: float) -> Outcome:
    """Remove a player who stayed away too long; their letters stay.

    When the player was the host, the role moves at once to the remaining player
    with the smallest `joined_seq` among those not disconnected, or among all of
    them when every one is disconnected (spec 014).
    """
    left = PlayerLeft(
        seq=state.seq + 1, player_id=player.player_id, reason=LeaveReason.TIMED_OUT
    )
    left_entry = LogEntry(at=now, event=left)
    entries = [left_entry]
    new_state = replay(state, left_entry)
    if player.is_host:
        new_host = _next_host(new_state)
        if new_host is not None:
            changed = HostChanged(seq=new_state.seq + 1, player_id=new_host.player_id)
            host_entry = LogEntry(at=now, event=changed)
            entries.append(host_entry)
            new_state = replay(new_state, host_entry)
    return Outcome(state=new_state, entries=tuple(entries))


def _next_host(state: RoomState) -> PlayerRecord | None:
    """Return the longest-present player, preferring those who are connected."""
    connected: list[PlayerRecord] = []
    for player in state.players:
        if player.state != PlayerState.DISCONNECTED:
            connected.append(player)
    candidates = connected if connected else list(state.players)
    best: PlayerRecord | None = None
    for player in candidates:
        if best is None or player.joined_seq < best.joined_seq:
            best = player
    return best


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
        Their selection is cleared; when they had one, `to_others` holds the
        `SelectionMoved` to `None` for the other players.
    """
    for player in state.players:
        if player.player_id != player_id:
            continue
        if player.state == PlayerState.DISCONNECTED:
            break
        changed = player.model_copy(
            update={
                "state": PlayerState.DISCONNECTED,
                "disconnected_at": now,
                "selection": None,
            }
        )
        outcome = _with_state_change(state, changed, now)
        if player.selection is None:
            return outcome
        cleared = SelectionMoved(player_id=player_id, selection=None)
        return outcome.model_copy(update={"to_others": (cleared,)})
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
    """Join `player` again on a new connection.

    A disconnected or idle player becomes active, with one `PlayerStateChanged`.
    """
    resumed = player.model_copy(update={"last_seen_at": now, "last_input_at": now})
    if player.state != PlayerState.ACTIVE:
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
    """Apply a message of a player of the room.

    A message from a player who is not in the room (removed, timed out or
    unknown) is refused with `not_joined` and changes nothing, a ping included
    (spec 014 AC-5). Otherwise every message sets the player's `last_seen_at`.
    A ping is answered with a pong and is not input; neither is a join. Any
    other message is input: it sets `last_input_at`, and an idle player becomes
    active with a `PlayerStateChanged` entry ahead of the message's own entries.
    `select_cell`, edits (`edit_letter`, `erase`), `undo` and the host actions
    (`remove_player`, `lock_room`, `change_settings`, `mute_player`) have their
    rules here. `pencil_edit` and `confirm_pencil` only go through the rate
    limit (spec 037); spec 020 gives them their meaning. Until the spec that
    gives another message its meaning is built, the message is read and
    ignored: nothing is sent.
    """
    if _find_player(state, player_id) is None:
        return _refuse(state, ErrorCode.NOT_JOINED, "Join the room first.")
    reactivation: tuple[LogEntry, ...] = ()
    active_state = state
    if not isinstance(message, Ping | Join):
        input_step = _register_input(state, player_id, now)
        active_state = input_step.state
        reactivation = input_step.entries
    outcome = _apply_message(active_state, player_id, message, now, config)
    seen_state = with_last_seen(outcome.state, player_id, now)
    all_entries = (*reactivation, *outcome.entries)
    return outcome.model_copy(update={"state": seen_state, "entries": all_entries})


def _register_input(state: RoomState, player_id: str, now: float) -> Outcome:
    """Record an input of the player and wake them up when they were idle.

    Returns:
        The outcome: `last_input_at` is `now`; an idle player becomes active
        with one `PlayerStateChanged` entry.
    """
    player = _find_player(state, player_id)
    if player is None:
        return Outcome(state=state)
    active = player.model_copy(update={"last_input_at": now})
    if player.state != PlayerState.IDLE:
        return Outcome(state=_replace_player(state, active))
    active = active.model_copy(update={"state": PlayerState.ACTIVE})
    return _with_state_change(state, active, now)


def _apply_message(
    state: RoomState,
    player_id: str,
    message: ClientMessage,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Run the rule of one message."""
    if isinstance(message, Ping):
        return Outcome(state=state, reply=(Pong(),))
    if isinstance(message, EditLetter):
        return _apply_edit(state, player_id, message, now, config)
    if isinstance(message, Erase):
        return _apply_edit(state, player_id, message, now, config)
    if isinstance(message, PencilEdit | ConfirmPencil):
        return _count_unhandled_edit(state, player_id, now, config)
    if isinstance(message, Undo):
        return _undo(state, player_id, now)
    if isinstance(message, SelectCell):
        return _select_cell(state, player_id, message)
    if isinstance(message, RemovePlayer | LockRoom | ChangeSettings | MutePlayer):
        return _host_action(state, player_id, message, now)
    return Outcome(state=state)


def _host_action(
    state: RoomState,
    player_id: str,
    message: RemovePlayer | LockRoom | ChangeSettings | MutePlayer,
    now: float,
) -> Outcome:
    """Run a host action, or refuse it with not_host for any other player."""
    sender = _find_player(state, player_id)
    if sender is None or not sender.is_host:
        return _refuse(state, ErrorCode.NOT_HOST, "Only the host can do this.")
    if isinstance(message, RemovePlayer):
        return _remove_player(state, sender, message.player_id, now)
    if isinstance(message, LockRoom):
        return _lock_room(state, sender, message.locked, now)
    if isinstance(message, MutePlayer):
        return _mute_player(state, sender, message, now)
    return _change_settings(state, sender, message, now)


def _remove_player(
    state: RoomState, host: PlayerRecord, target_id: str, now: float
) -> Outcome:
    """Remove a player, ban their token and close their connection."""
    target = _find_player(state, target_id)
    if target is None or target.player_id == host.player_id:
        return _refuse(
            state, ErrorCode.INVALID_TARGET, "That player cannot be removed."
        )
    left = PlayerLeft(
        seq=state.seq + 1, player_id=target_id, reason=LeaveReason.REMOVED
    )
    entry = LogEntry(at=now, event=left)
    removal = Disconnect(
        player_id=target_id,
        close_code=_NORMAL_CLOSE_CODE,
        error=ErrorMessage(code=ErrorCode.REMOVED, message=_REMOVED_TEXT),
    )
    return Outcome(state=replay(state, entry), entries=(entry,), disconnects=(removal,))


def _mute_player(
    state: RoomState, host: PlayerRecord, message: MutePlayer, now: float
) -> Outcome:
    """Mute or unmute a player's chat; nothing happens when it already is so."""
    target = _find_player(state, message.player_id)
    if target is None or target.player_id == host.player_id:
        return _refuse(state, ErrorCode.INVALID_TARGET, "That player cannot be muted.")
    if target.muted == message.muted:
        return Outcome(state=state)
    event = PlayerMuted(
        seq=state.seq + 1, player_id=target.player_id, muted=message.muted
    )
    entry = LogEntry(at=now, event=event)
    return Outcome(state=replay(state, entry), entries=(entry,))


def _announce_settings(
    state: RoomState,
    host: PlayerRecord,
    settings: RoomSettings,
    reveal_budget: RevealBudget,
    now: float,
) -> Outcome:
    """Number a settings_changed event and apply it."""
    event = SettingsChanged(
        seq=state.seq + 1,
        player_id=host.player_id,
        settings=settings,
        reveal_budget=reveal_budget,
    )
    entry = LogEntry(at=now, event=event)
    return Outcome(state=replay(state, entry), entries=(entry,))


def _lock_room(
    state: RoomState, host: PlayerRecord, locked: bool, now: float
) -> Outcome:
    """Lock or unlock the room; nothing happens when it already is so."""
    if locked == state.settings.locked:
        return Outcome(state=state)
    settings = state.settings.model_copy(update={"locked": locked})
    return _announce_settings(state, host, settings, state.reveal_budget, now)


def _remaining_count(old_allowance: int, old_remaining: int, new_allowance: int) -> int:
    """Return the new allowance minus what was used, never below 0."""
    used = old_allowance - old_remaining
    return max(0, new_allowance - used)


def _change_settings(
    state: RoomState, host: PlayerRecord, message: ChangeSettings, now: float
) -> Outcome:
    """Change the help mode and the reveal allowance, keeping what was used."""
    current = state.settings
    if (
        message.help_mode == current.help_mode
        and message.reveal_budget == current.reveal_budget
    ):
        return Outcome(state=state)
    settings = current.model_copy(
        update={
            "help_mode": message.help_mode,
            "reveal_budget": message.reveal_budget,
        }
    )
    remaining = RevealBudget(
        letters=_remaining_count(
            current.reveal_budget.letters,
            state.reveal_budget.letters,
            message.reveal_budget.letters,
        ),
        words=_remaining_count(
            current.reveal_budget.words,
            state.reveal_budget.words,
            message.reveal_budget.words,
        ),
    )
    return _announce_settings(state, host, settings, remaining, now)


def _select_cell(state: RoomState, player_id: str, message: SelectCell) -> Outcome:
    """Store the player's selection and relay it to the other players."""
    player = _find_player(state, player_id)
    if player is None:
        return Outcome(state=state)
    if _find_cell(state, message.row, message.column) is None:
        return _refuse(
            state,
            ErrorCode.NOT_A_LETTER_CELL,
            f"({message.row}, {message.column}) is not a letter cell.",
        )
    selection = Selection(
        row=message.row, column=message.column, direction=message.direction
    )
    changed = player.model_copy(update={"selection": selection})
    moved = SelectionMoved(player_id=player_id, selection=selection)
    return Outcome(state=_replace_player(state, changed), to_others=(moved,))


def with_last_seen(state: RoomState, player_id: str, now: float) -> RoomState:
    """Return the state with the player's `last_seen_at` set to `now`.

    Args:
        state: Room state to start from. It is not modified.
        player_id: Id of the player who was seen.
        now: Time the player was seen, in seconds.

    Returns:
        A new state where the player's `last_seen_at` is `now`. The given
        state itself when the player is not in the room.
    """
    player = _find_player(state, player_id)
    if player is None:
        return state
    seen = player.model_copy(update={"last_seen_at": now})
    return _replace_player(state, seen)


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

    Check 5 (solved grid, spec 026) belongs to a later spec: it keeps its place
    in the order but never refuses yet.
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
    if _is_stale(cell, player_id, edit):
        return _refuse(
            state,
            ErrorCode.STALE_EDIT,
            f"({edit.row}, {edit.column}) changed since the edit was made.",
        )
    return None


def _is_stale(cell: CellState, player_id: str, edit: EditLetter | Erase) -> bool:
    """Tell whether someone else changed the cell after the edit's `base_seq`."""
    if edit.base_seq is None:
        return False
    if cell.changed_seq <= edit.base_seq:
        return False
    return cell.changed_by != player_id


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
    old_cell = _find_cell(state, edit.row, edit.column)
    if old_cell is None:
        return _refuse(state, ErrorCode.NOT_A_LETTER_CELL, "Not a letter cell.")
    edited_cell = old_cell.model_copy(
        update={
            "letter": letter,
            "pencil": False,
            "author": author,
            "wrong": False,
            "changed_seq": seq,
            "changed_by": player_id,
        }
    )
    last_edit = _undo_entry_before(old_cell, seq)
    counted_state = _with_edit_counted(state, player_id, now)
    edited_state = _replace_cell(counted_state, edited_cell)
    new_state = _with_last_edit(edited_state, player_id, last_edit)
    new_state = new_state.model_copy(update={"seq": seq})
    event = LetterChanged(
        seq=seq,
        row=edit.row,
        column=edit.column,
        letter=letter,
        pencil=False,
        player_id=player_id,
    )
    return Outcome(state=new_state, entries=(LogEntry(at=now, event=event),))


def _undo_entry_before(cell: CellState, seq: int) -> UndoEntry:
    """Return what `last_edit` holds for an edit of `cell` numbered `seq`."""
    return UndoEntry(
        row=cell.row,
        column=cell.column,
        seq=seq,
        letter=cell.letter,
        pencil=cell.pencil,
        author=cell.author,
    )


def _replace_cell(state: RoomState, changed: CellState) -> RoomState:
    """Return the state with `changed` in place of the cell at the same position."""
    cells: list[CellState] = []
    for cell in state.cells:
        if cell.row == changed.row and cell.column == changed.column:
            cells.append(changed)
        else:
            cells.append(cell)
    return state.model_copy(update={"cells": tuple(cells)})


def _with_last_edit(
    state: RoomState, player_id: str, last_edit: UndoEntry | None
) -> RoomState:
    """Return the state with the player's `last_edit` set (None clears it)."""
    player = _find_player(state, player_id)
    if player is None:
        return state
    changed = player.model_copy(update={"last_edit": last_edit})
    return _replace_player(state, changed)


def _undo(state: RoomState, player_id: str, now: float) -> Outcome:
    """Give the cell of the player's last edit back its previous content.

    The undo is refused with nothing_to_undo when the player has no last edit,
    or when the cell was changed or locked since. It is not counted by the rate
    limit. The grid-solved refusal belongs to spec 026.
    """
    player = _find_player(state, player_id)
    if player is None or player.last_edit is None:
        return _refuse(state, ErrorCode.NOTHING_TO_UNDO, "Nothing to undo.")
    last_edit = player.last_edit
    cell = _find_cell(state, last_edit.row, last_edit.column)
    if cell is None or cell.locked or cell.changed_seq != last_edit.seq:
        forgotten = _with_last_edit(state, player_id, None)
        return _refuse(forgotten, ErrorCode.NOTHING_TO_UNDO, "Nothing to undo.")

    seq = state.seq + 1
    author = player_id if last_edit.letter is not None else None
    restored_cell = cell.model_copy(
        update={
            "letter": last_edit.letter,
            "pencil": last_edit.pencil,
            "author": author,
            "wrong": False,
            "changed_seq": seq,
            "changed_by": player_id,
        }
    )
    restored_state = _replace_cell(state, restored_cell)
    new_state = _with_last_edit(restored_state, player_id, None)
    new_state = new_state.model_copy(update={"seq": seq})
    event = LetterChanged(
        seq=seq,
        row=last_edit.row,
        column=last_edit.column,
        letter=last_edit.letter,
        pencil=last_edit.pencil,
        player_id=player_id,
    )
    entry = LogEntry(at=now, event=event, undo=True)
    return Outcome(state=new_state, entries=(entry,))


def tick(state: RoomState, now: float, config: RoomConfig = DEFAULT_CONFIG) -> Outcome:
    """Apply the passing of time (spec 013, 014, 017).

    For each player, in `players` order: a joined player silent for too long is
    disconnected and their socket is to be closed; a player disconnected for
    more than the resume window leaves the room. Then each active player
    without input for the idle delay becomes idle. Last, a host disconnected for
    more than the hand-over delay hands the host role to the longest-present
    connected player.
    """
    current = state
    entries: list[LogEntry] = []
    disconnects: list[Disconnect] = []
    to_others: list[SelectionMoved] = []
    for listed in state.players:
        player = _find_player(current, listed.player_id)
        if player is None:
            continue
        if player.state != PlayerState.DISCONNECTED:
            silence = now - player.last_seen_at
            if silence >= config.silence_timeout_seconds:
                step = disconnect_player(current, player.player_id, now)
                current = step.state
                entries.extend(step.entries)
                to_others.extend(step.to_others)
                silent = Disconnect(
                    player_id=player.player_id, close_code=SILENCE_CLOSE_CODE
                )
                disconnects.append(silent)
        elif _has_timed_out(player, now, config):
            step = _time_out_player(current, player, now)
            current = step.state
            entries.extend(step.entries)
    idle_step = _idle_step(current, now, config)
    entries.extend(idle_step.entries)
    handover_step = _handover_step(idle_step.state, now, config)
    entries.extend(handover_step.entries)
    return Outcome(
        state=handover_step.state,
        entries=tuple(entries),
        to_others=tuple(to_others),
        disconnects=tuple(disconnects),
    )


def _idle_step(state: RoomState, now: float, config: RoomConfig) -> Outcome:
    """Turn the active players without input for long enough into idle ones."""
    current = state
    entries: list[LogEntry] = []
    for listed in state.players:
        player = _find_player(current, listed.player_id)
        if player is None or player.state != PlayerState.ACTIVE:
            continue
        if now - player.last_input_at < config.idle_after_seconds:
            continue
        idle = player.model_copy(update={"state": PlayerState.IDLE})
        step = _with_state_change(current, idle, now)
        current = step.state
        entries.extend(step.entries)
    return Outcome(state=current, entries=tuple(entries))


def _handover_step(state: RoomState, now: float, config: RoomConfig) -> Outcome:
    """Give the host role to a connected player after the host stayed away."""
    for host in state.players:
        if not host.is_host or host.state != PlayerState.DISCONNECTED:
            continue
        if host.disconnected_at is None:
            continue
        if now - host.disconnected_at <= config.host_handover_seconds:
            continue
        new_host = _longest_present_connected(state)
        if new_host is None:
            continue
        changed = HostChanged(seq=state.seq + 1, player_id=new_host.player_id)
        entry = LogEntry(at=now, event=changed)
        return Outcome(state=replay(state, entry), entries=(entry,))
    return Outcome(state=state)


def _longest_present_connected(state: RoomState) -> PlayerRecord | None:
    """Return the connected player with the smallest `joined_seq`, or None."""
    best: PlayerRecord | None = None
    for player in state.players:
        if player.state == PlayerState.DISCONNECTED:
            continue
        if best is None or player.joined_seq < best.joined_seq:
            best = player
    return best


def replay(state: RoomState, entry: LogEntry) -> RoomState:
    """Return the state after the logged `entry`, as the live step left it.

    Args:
        state: The room before the entry.
        entry: The next logged entry.

    Returns:
        The room after it, for every field the log carries. Events of later
        specs only move `seq` until those specs extend this function.

    Raises:
        ValueError: a `player_joined` entry has no resume token.
    """
    event = entry.event
    if isinstance(event, PlayerJoined):
        replayed = _replay_player_joined(state, entry, event)
    elif isinstance(event, PlayerStateChanged):
        replayed = _replay_state_changed(state, entry, event)
    elif isinstance(event, PlayerLeft):
        replayed = _replay_player_left(state, event)
    elif isinstance(event, LetterChanged):
        replayed = _replay_letter_changed(state, entry, event)
    elif isinstance(event, CellLocked):
        replayed = _replay_cell_locked(state, event)
    elif isinstance(event, SettingsChanged):
        replayed = state.model_copy(
            update={"settings": event.settings, "reveal_budget": event.reveal_budget}
        )
    elif isinstance(event, HostChanged):
        replayed = _replay_host_changed(state, event)
    elif isinstance(event, PlayerMuted):
        replayed = _replay_player_muted(state, event)
    else:
        replayed = state
    return replayed.model_copy(update={"seq": event.seq})


def _replay_player_joined(
    state: RoomState, entry: LogEntry, event: PlayerJoined
) -> RoomState:
    """Append the player of a logged join."""
    if entry.resume_token is None:
        raise ValueError(f"The player_joined entry {event.seq} has no resume token")
    view = event.player
    player = PlayerRecord(
        player_id=view.player_id,
        resume_token=entry.resume_token,
        nickname=view.nickname,
        colour=view.colour,
        is_host=view.is_host,
        muted=view.muted,
        state=view.state,
        joined_seq=event.seq,
        last_input_at=entry.at,
        last_seen_at=entry.at,
    )
    return state.model_copy(update={"players": (*state.players, player)})


def _replay_state_changed(
    state: RoomState, entry: LogEntry, event: PlayerStateChanged
) -> RoomState:
    """Set the presence of a player."""
    player = _find_player(state, event.player_id)
    if player is None:
        return state
    disconnected_at = None
    if event.state == PlayerState.DISCONNECTED:
        disconnected_at = entry.at
    changed = player.model_copy(
        update={"state": event.state, "disconnected_at": disconnected_at}
    )
    return _replace_player(state, changed)


def _replay_player_left(state: RoomState, event: PlayerLeft) -> RoomState:
    """Remove a player, and ban their token when they were removed."""
    remaining: list[PlayerRecord] = []
    removed_tokens = state.removed_tokens
    for player in state.players:
        if player.player_id != event.player_id:
            remaining.append(player)
        elif event.reason == LeaveReason.REMOVED:
            removed_tokens = (*removed_tokens, player.resume_token)
    return state.model_copy(
        update={"players": tuple(remaining), "removed_tokens": removed_tokens}
    )


def _replay_letter_changed(
    state: RoomState, entry: LogEntry, event: LetterChanged
) -> RoomState:
    """Write the letter in its cell and update the player's last edit."""
    old_cell = _find_cell(state, event.row, event.column)
    if old_cell is None:
        return state
    author = event.player_id if event.letter is not None else None
    changed_cell = old_cell.model_copy(
        update={
            "letter": event.letter,
            "pencil": event.pencil,
            "author": author,
            "wrong": False,
            "changed_seq": event.seq,
            "changed_by": event.player_id,
        }
    )
    last_edit: UndoEntry | None = None
    if not entry.undo:
        last_edit = _undo_entry_before(old_cell, event.seq)
    changed_state = _replace_cell(state, changed_cell)
    return _with_last_edit(changed_state, event.player_id, last_edit)


def _replay_cell_locked(state: RoomState, event: CellLocked) -> RoomState:
    """Lock a cell with its letter; a reveal also clears the author."""
    cell = _find_cell(state, event.row, event.column)
    if cell is None:
        return state
    locked_cell = cell.model_copy(
        update={
            "letter": event.letter,
            "locked": True,
            "revealed": event.revealed,
            "changed_seq": event.seq,
            "changed_by": None,
        }
    )
    if event.revealed:
        locked_cell = locked_cell.model_copy(update={"author": None})
    return _replace_cell(state, locked_cell)


def _replay_host_changed(state: RoomState, event: HostChanged) -> RoomState:
    """Give the host role to one player and take it from the others."""
    players: list[PlayerRecord] = []
    for player in state.players:
        is_host = player.player_id == event.player_id
        players.append(player.model_copy(update={"is_host": is_host}))
    return state.model_copy(update={"players": tuple(players)})


def _replay_player_muted(state: RoomState, event: PlayerMuted) -> RoomState:
    """Set the muted flag of a player."""
    player = _find_player(state, event.player_id)
    if player is None:
        return state
    return _replace_player(state, player.model_copy(update={"muted": event.muted}))


def after_restart(state: RoomState, now: float) -> Outcome:
    """Disconnect every player who is not, for a room loaded in a new process.

    Args:
        state: The room as loaded from the store.
        now: Clock time of the loading.

    Returns:
        The outcome: each player not disconnected gets `disconnected_at = now`,
        no selection and no recent edits, with one logged
        `PlayerStateChanged(disconnected)` each, in players order.
    """
    seq = state.seq
    players: list[PlayerRecord] = []
    entries: list[LogEntry] = []
    for player in state.players:
        if player.state == PlayerState.DISCONNECTED:
            players.append(player)
            continue
        seq += 1
        disconnected = player.model_copy(
            update={
                "state": PlayerState.DISCONNECTED,
                "disconnected_at": now,
                "selection": None,
                "recent_edits": (),
            }
        )
        players.append(disconnected)
        event = PlayerStateChanged(
            seq=seq, player_id=player.player_id, state=PlayerState.DISCONNECTED
        )
        entries.append(LogEntry(at=now, event=event))
    new_state = state.model_copy(update={"players": tuple(players), "seq": seq})
    return Outcome(state=new_state, entries=tuple(entries))
