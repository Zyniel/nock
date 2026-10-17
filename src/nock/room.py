"""Room state models and the pure rules applied to each event.

Nothing here does I/O, reads a clock or touches the network: time is passed in
as `now`. The runtime that drives these functions is `nock.hub`.
"""

from __future__ import annotations

import secrets
import unicodedata
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StrictBool

from nock.grid import ClueCell, Grid, LetterCell
from nock.protocol import (
    CellLocked,
    CellRef,
    CellTarget,
    CellView,
    ChangeSettings,
    Chat,
    ChatMessage,
    Check,
    CheckResult,
    CheckTarget,
    ClientMessage,
    ClueRef,
    Colour,
    ConfirmPencil,
    Coordinate,
    EditLetter,
    Erase,
    ErrorCode,
    ErrorMessage,
    Flag,
    FlagChanged,
    FlagView,
    GridFullWrong,
    GridSolved,
    GridTarget,
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
    React,
    ReactionShown,
    RemovePlayer,
    ResumeToken,
    Reveal,
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
    Vote,
    VoteClosed,
    VoteOpened,
    VoteOutcome,
    WordTarget,
    grid_view,
)

Clock = Callable[[], float]  # seconds since the epoch; the default is time.time
RoomCode = Annotated[str, Field(pattern=r"^[A-Z0-9]{6}$")]
# spec 028: names a room's public recap; never sent in a snapshot or an event
ShareToken = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,64}$")]

RATE_WINDOW_SECONDS: float = 1.0  # spec 037 AC-3
MAX_PLAYERS: int = 8  # spec 012 AC-4
MAX_PAST_PLAYERS: int = 100  # spec 032 AC-4: past players a room keeps
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
    # spec 036 AC-5: messages a connection's outbound queue may hold
    max_outbound_messages: int = Field(default=1000, ge=1)
    # spec 036 AC-6: inputs of a connection that may wait to be applied
    max_inbound_pending: int = Field(default=100, ge=1)
    vote_timeout_seconds: int = Field(default=20, ge=1)  # spec 025 AC-2
    chat_limit: int = Field(default=5, ge=1)  # spec 022: chat messages per window
    chat_window_seconds: float = Field(default=10.0, gt=0)
    reaction_limit: int = Field(default=5, ge=1)  # spec 022: reactions per window
    reaction_window_seconds: float = Field(default=10.0, gt=0)
    # spec 032 AC-1: a room expires this long after its last edit (30 days)
    room_life_seconds: float = Field(default=2_592_000.0, gt=0)
    # spec 032 AC-2: how often the app deletes the expired rooms
    expiry_sweep_seconds: float = Field(default=3_600.0, gt=0)


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
    flag: ClueRef | None = None  # spec 021: the clue this player flagged
    # spec 022: times of the chat messages accepted in the window (not logged)
    recent_chat: tuple[float, ...] = ()
    # spec 022: times of the reactions relayed in the window (not logged)
    recent_reactions: tuple[float, ...] = ()


class PastPlayer(RoomModel):
    """A player who left the room by time-out or on purpose. Never sent as is.

    A join with their resume token seats them back (spec 032).
    """

    player_id: PlayerId
    resume_token: ResumeToken  # secret, like PlayerRecord.resume_token
    nickname: Nickname
    colour: Colour
    # the record's mute (specs 014, 022), kept for a seat back (spec 032 decision 13)
    muted: StrictBool = False


class OpenVote(RoomModel):
    """The vote a room is holding (spec 025). Ballots are not in the log."""

    opened: VoteOpened  # the event that opened it; snapshots send it
    opened_at: float  # clock time of the step that opened it
    # players not disconnected at the opening, in players order
    eligible: tuple[PlayerId, ...]
    yes: tuple[PlayerId, ...]  # the requester first, then the yes ballots in order
    no: tuple[PlayerId, ...] = ()  # the no ballots in order


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
    # spec 024: the reveals accepted so far, as two counts. A snapshot stored
    # before spec 024 has no such key and loads with 0 and 0, its exact value.
    reveals_used: RevealBudget = RevealBudget(letters=0, words=0)
    removed_tokens: tuple[ResumeToken, ...] = ()  # spec 014 AC-1
    solved: StrictBool = False  # spec 026
    open_vote: OpenVote | None = None  # spec 025
    # spec 025: vote_id of the last vote opened, 0 for none
    last_vote_id: int = Field(default=0, ge=0, strict=True)
    chat: tuple[ChatMessage, ...] = ()  # spec 022: every chat message, in seq order
    # spec 027: the shared timer. A room stored before this spec has no such keys
    # and loads as a timer that was never started.
    timer_started: StrictBool = False  # a letter was typed
    # time counted before the current run, in milliseconds
    timer_elapsed_ms: int = Field(default=0, ge=0, strict=True)
    # clock time the current run began; None when the timer is not running
    timer_resumed_at: float | None = None
    # spec 028: names the public recap. A room stored before this spec has no
    # such key and loads with None: it has no share link.
    share_token: ShareToken | None = None
    # spec 032: the players who left by time-out or on purpose, in the order they
    # left, oldest first. A room stored before this spec loads with none.
    past_players: tuple[PastPlayer, ...] = Field(
        default=(), max_length=MAX_PAST_PLAYERS
    )


class RoomKey(RoomModel):
    """A room and the resume token of one of its members, as a device keeps them."""

    code: RoomCode
    resume_token: ResumeToken


class RoomSummary(RoomModel):
    """What "My rooms" shows of one room (spec 032). It holds no letter of the grid."""

    code: RoomCode
    grid_number: int | None  # catalogue number (spec 004); None for a bare grid
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    players: tuple[Nickname, ...]  # team_nicknames(state)
    last_activity_at: AwareDatetime  # the last edit time, in UTC
    solved: StrictBool


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
    # to every joined connection except the sender's and the item's own player's
    to_others: tuple[SelectionMoved | ReactionShown, ...] = ()
    close_sender: StrictBool = False  # close the sender's socket, code 1000
    disconnects: tuple[Disconnect, ...] = ()


def new_room(
    code: str,
    grid: Grid,
    now: float,
    grid_number: int | None = None,
    share_token: str | None = None,
) -> RoomState:
    """Return a fresh room: seq 0, no player, every letter cell empty.

    Args:
        code: The room code, six characters of A-Z and 0-9.
        grid: The grid to solve.
        now: Clock time of the creation.
        grid_number: Catalogue number of the grid, None for a bare grid.
        share_token: The token of the room's public recap (spec 028), 16 to 64
            characters of A-Z, a-z, 0-9, "_" and "-"; None for no share link.

    Returns:
        The new state. `cells` holds one empty cell per letter cell of `grid`,
        in the order of `grid.cells`.

    Raises:
        pydantic.ValidationError: `code` breaks the room code pattern, or
            `share_token` breaks the share token pattern.
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
        share_token=share_token,
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


# ---- Room life and members (spec 032) -----------------------------------------


def is_edit(entry: LogEntry) -> bool:
    """Tell whether a logged entry is an edit: a letter_changed or a cell_locked.

    Only edits move a room's last edit time, which its 30-day life runs from.

    Args:
        entry: A logged entry of a room.

    Returns:
        True for a letter written, erased, confirmed or undone, and for a cell
        locked by a check or a reveal; False for any other event.
    """
    return isinstance(entry.event, LetterChanged | CellLocked)


def member_id(state: RoomState, resume_token: str) -> str | None:
    """Return the id of the member whose resume token is `resume_token`.

    The players of `players`, then those of `past_players`, are compared with
    `secrets.compare_digest`. A removed player is no member.

    Args:
        state: The room.
        resume_token: The token a device keeps for the room.

    Returns:
        The member's player id, or None when no member holds that token.
    """
    for player in state.players:
        if secrets.compare_digest(player.resume_token, resume_token):
            return player.player_id
    for past_player in state.past_players:
        if secrets.compare_digest(past_player.resume_token, resume_token):
            return past_player.player_id
    return None


def team_nicknames(state: RoomState) -> tuple[str, ...]:
    """Return the nicknames of the room's members, each once.

    Args:
        state: The room.

    Returns:
        First the nicknames of `past_players` in the order they left, then those
        of `players` in `players` order. A nickname equal to an earlier one is
        left out.
    """
    member_nicknames: list[str] = []
    for past_player in state.past_players:
        member_nicknames.append(past_player.nickname)
    for player in state.players:
        member_nicknames.append(player.nickname)

    nicknames: list[str] = []
    for nickname in member_nicknames:
        if nickname not in nicknames:
            nicknames.append(nickname)
    return tuple(nicknames)


def room_summary(state: RoomState, last_edit_at: float) -> RoomSummary:
    """Return the summary of a room, as "My rooms" shows it.

    Args:
        state: The room.
        last_edit_at: The room's last edit time, in seconds since the epoch.

    Returns:
        The grid number, the grid's width and height, `team_nicknames(state)`,
        `last_edit_at` as a UTC datetime, and whether the grid is solved.
    """
    return RoomSummary(
        code=state.code,
        grid_number=state.grid_number,
        width=state.grid.width,
        height=state.grid.height,
        players=team_nicknames(state),
        last_activity_at=datetime.fromtimestamp(last_edit_at, UTC),
        solved=state.solved,
    )


# ---- Rules owned by later specs ---------------------------------------------
# Each function below has its final signature. Until the spec that owns it is
# built, it does the least that keeps the engine running (spec 011).


def normalize_nickname(text: str) -> str:
    """Return the nickname as stored: NFC, stripped, in capitals, then NFC again.

    Args:
        text: The nickname as typed, in any case.

    Returns:
        The nickname in capitals (`str.upper()`) and in NFC, 2 to 20 characters,
        made of letters, combining marks, ASCII digits and NICKNAME_PUNCTUATION,
        with at least one letter or digit. The rules are checked on this result:
        `ß` gives `SS`, two characters. A name typed in small letters and the
        same name typed in the capitals that `str.upper()` gives have the same
        result.

    Raises:
        ValueError: a rule is broken; the message names the rule.
    """
    capitals = unicodedata.normalize("NFC", text).strip().upper()
    # The capitals of a few Greek letters are not in NFC: U+0390 gives U+0399
    # U+0308 U+0301, which NFC writes U+03AA U+0301.
    nickname = unicodedata.normalize("NFC", capitals)
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


# ---- The shared timer (spec 027) -----------------------------------------------


def timer_value_ms(state: RoomState, now: float) -> int:
    """Return the shared timer at `now`, in whole milliseconds.

    Args:
        state: The room.
        now: Clock time of the reading.

    Returns:
        The time counted before the current run, plus the current run up to
        `now` while the timer runs. A clock that went back adds nothing.
    """
    value = state.timer_elapsed_ms
    if state.timer_resumed_at is not None:
        current_run_ms = round((now - state.timer_resumed_at) * 1000)
        value += max(0, current_run_ms)
    return value


def _has_connected_player(state: RoomState) -> bool:
    """Tell whether a player is connected: their state is not `disconnected`."""
    return any(player.state != PlayerState.DISCONNECTED for player in state.players)


def _is_first_letter(state: RoomState, entry: LogEntry) -> bool:
    """Tell whether the entry types the first letter of a room that is not solved.

    A pencil letter is typed, so it counts. An erase and a reveal do not.
    """
    if state.timer_started or state.solved:
        return False
    event = entry.event
    return isinstance(event, LetterChanged) and event.letter is not None


def _with_timer_rules(state: RoomState, entry: LogEntry) -> RoomState:
    """Apply the timer rules of spec 027 to the room `state` that `entry` just made.

    The first rule that applies is used: start at the first letter, stop at the
    solve, pause when no player is connected, resume when one is. The time of
    the rules is `entry.at`, which is the step's `now` in a live step, so that
    `replay` gives the timer of the live step.
    """
    if _is_first_letter(state, entry):
        return state.model_copy(
            update={"timer_started": True, "timer_resumed_at": entry.at}
        )
    event = entry.event
    if isinstance(event, GridSolved):
        return state.model_copy(
            update={"timer_elapsed_ms": event.elapsed_ms, "timer_resumed_at": None}
        )
    is_running = state.timer_resumed_at is not None
    has_connected = _has_connected_player(state)
    if is_running and not has_connected:
        return state.model_copy(
            update={
                "timer_elapsed_ms": timer_value_ms(state, entry.at),
                "timer_resumed_at": None,
            }
        )
    can_resume = state.timer_started and not is_running and not state.solved
    if can_resume and has_connected:
        return state.model_copy(update={"timer_resumed_at": entry.at})
    return state


def snapshot_for(
    state: RoomState, player_id: str, now: float | None = None
) -> Snapshot:
    """Return the snapshot that player `player_id` receives.

    Args:
        state: The room.
        player_id: A player of the room.
        now: Clock time of the step, to read the shared timer at. The rules
            always pass it. Without it (a state built by hand) the snapshot
            holds the time counted before the current run.

    Returns:
        The snapshot, with the player's own resume token. Its `open_vote` is the
        event that opened the room's open vote, None when no vote is open, its
        `chat` is the room's whole chat history (spec 022), and its timer is the
        shared timer of spec 027.

    Raises:
        KeyError: no player `player_id` in the room.
    """
    open_vote: VoteOpened | None = None
    if state.open_vote is not None:
        open_vote = state.open_vote.opened
    timer_elapsed_ms = state.timer_elapsed_ms
    if now is not None:
        timer_elapsed_ms = timer_value_ms(state, now)
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
                flags=_flag_views(state),
                chat=state.chat,
                open_vote=open_vote,
                timer_elapsed_ms=timer_elapsed_ms,
                timer_running=state.timer_resumed_at is not None,
                solved=state.solved,
            )
    raise KeyError(player_id)


def _flag_views(state: RoomState) -> tuple[FlagView, ...]:
    """Return one view per player who holds a flag, in players order (spec 021)."""
    views: list[FlagView] = []
    for player in state.players:
        if player.flag is not None:
            views.append(FlagView(player_id=player.player_id, clue=player.flag))
    return tuple(views)


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
    removed token, resume of a player of the room, room locked, room full, seat
    back of a past player (spec 032), invalid nickname, new player. A token whose
    player has been disconnected for more than the resume window does not
    resume: that player times out in this same step and becomes a past player,
    and the join goes on with the steps after the resume, so that the same token
    seats them back. A refusal after such a time-out keeps the time-out.

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
    outcome = _join_without_resume(state, message, now, new_player_id, new_resume_token)
    all_entries = (*timeout_entries, *outcome.entries)
    return outcome.model_copy(update={"entries": all_entries})


def _join_without_resume(
    state: RoomState,
    message: Join,
    now: float,
    new_player_id: str,
    new_resume_token: str,
) -> Outcome:
    """Run the steps of a join that does not resume.

    Locked, full, seat back (spec 012 step 4a, spec 032), nickname, new player.
    """
    if state.settings.locked:
        refusal = ErrorMessage(
            code=ErrorCode.ROOM_LOCKED, message="The room is locked."
        )
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    if len(state.players) >= MAX_PLAYERS:
        refusal = ErrorMessage(code=ErrorCode.ROOM_FULL, message="The room is full.")
        return Outcome(state=state, reply=(refusal,), close_sender=True)
    past_player = _find_past_player(state, message.resume_token)
    if past_player is not None:
        return _seat_back(state, past_player, now)
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


def _find_past_player(state: RoomState, token: str | None) -> PastPlayer | None:
    """Return the past player who owns `token`, or None (spec 032)."""
    if token is None:
        return None
    for past_player in state.past_players:
        if secrets.compare_digest(past_player.resume_token, token):
            return past_player
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
    """Store `changed` and number one player_state_changed event for it.

    The timer rules of spec 027 run after the entry: a player who leaves or
    returns can pause or resume the timer.
    """
    seq = state.seq + 1
    event = PlayerStateChanged(
        seq=seq, player_id=changed.player_id, state=changed.state
    )
    entry = LogEntry(at=now, event=event)
    new_state = _replace_player(state, changed).model_copy(update={"seq": seq})
    return Outcome(state=_with_timer_rules(new_state, entry), entries=(entry,))


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
    reply = (snapshot_for(outcome.state, player.player_id, now),)
    return outcome.model_copy(update={"reply": reply})


def _unique_nickname(state: RoomState, nickname: str) -> str:
    """Return `nickname`, or the first `nickname n` (n >= 2) no player has."""
    taken: set[str] = set()
    for player in state.players:
        taken.add(player.nickname)
    if nickname not in taken:
        return nickname
    number = 2
    while True:
        suffix = f" {number}"
        base = nickname[: NICKNAME_MAX_LENGTH - len(suffix)].rstrip()
        candidate = base + suffix
        if candidate not in taken:
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


def _seat_back_colour(state: RoomState, colour: int) -> int:
    """Return `colour` when no player of the room has it, else the lowest free one.

    The players of the room count, connected or disconnected (spec 032).
    """
    for player in state.players:
        if player.colour == colour:
            return _lowest_free_colour(state)
    return colour


def _has_host(state: RoomState) -> bool:
    """Tell whether a player of the room is host."""
    return any(player.is_host for player in state.players)


def _add_player(
    state: RoomState,
    nickname: str,
    now: float,
    player_id: str,
    resume_token: str,
) -> Outcome:
    """Add a new player at the end of the room and number their player_joined.

    The nickname gets spec 012's suffix when a player has it, the colour is the
    lowest free one, and the player is host when nobody is.
    """
    view = PlayerView(
        player_id=player_id,
        nickname=_unique_nickname(state, nickname),
        colour=_lowest_free_colour(state),
        state=PlayerState.ACTIVE,
        is_host=not _has_host(state),
        muted=False,
        selection=None,
    )
    return _seat_player(state, view, resume_token, now)


def _seat_back(state: RoomState, past_player: PastPlayer, now: float) -> Outcome:
    """Bring a past player back into the room, with their id and token (spec 032).

    Their nickname gets spec 012's suffix when a player has it, and their colour
    is theirs again unless a player has it. Their mute is kept (spec 032
    decision 13). The rest is a new player's: the host role only when nobody is
    host, no flag, no last edit. The join's nickname is not used.
    """
    view = PlayerView(
        player_id=past_player.player_id,
        nickname=_unique_nickname(state, past_player.nickname),
        colour=_seat_back_colour(state, past_player.colour),
        state=PlayerState.ACTIVE,
        is_host=not _has_host(state),
        muted=past_player.muted,
        selection=None,
    )
    return _seat_player(state, view, past_player.resume_token, now)


def _seat_player(
    state: RoomState, view: PlayerView, resume_token: str, now: float
) -> Outcome:
    """Number the player_joined of a joiner who takes a seat, and apply it.

    `replay` appends the player at the end of the room, takes them out of the
    past players, and runs the timer rules of spec 027, so the joiner's snapshot
    holds a timer that their join resumed.

    Returns:
        The outcome: one entry, logged with `resume_token`, and the joiner's
        snapshot as the reply.
    """
    event = PlayerJoined(seq=state.seq + 1, player=view)
    entry = LogEntry(at=now, event=event, resume_token=resume_token)
    new_state = replay(state, entry)
    reply = (snapshot_for(new_state, view.player_id, now),)
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
    `select_cell`, edits (`edit_letter`, `erase`, `pencil_edit`,
    `confirm_pencil`), `undo` and the host actions (`remove_player`,
    `lock_room`, `change_settings`, `mute_player`), `check`, `reveal`, `vote`,
    `flag`, `chat` and `react` (input, not counted by the edit limit) have
    their rules here. A `chat` or a `react` over its own limit (spec 022) is
    dropped without an answer; an idle sender is still woken. Before a
    `check`, a `reveal` or a `vote`, an open vote whose time is over closes,
    with its entry after the wake-up entry (spec 025). A step that changes a
    letter or a lock clears every flag whose word is now full (spec 021),
    before the completion entry of spec 026. Until the spec that gives another
    message its meaning is built, the message is read and ignored: nothing is
    sent.
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
    """Run the rule of one message, the flag clearing (spec 021), then completion.

    The completion rule is spec 026's; its entry comes after the clearing ones.
    """
    outcome = _run_message(state, player_id, message, now, config)
    outcome_with_flags_cleared = _with_full_flags_cleared(outcome, now)
    return _with_completion(state, outcome_with_flags_cleared, now)


def _run_message(
    state: RoomState,
    player_id: str,
    message: ClientMessage,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Run the rule of one message."""
    if isinstance(message, Ping):
        return Outcome(state=state, reply=(Pong(),))
    if isinstance(message, EditLetter | Erase | PencilEdit):
        return _apply_edit(state, player_id, message, now, config)
    if isinstance(message, ConfirmPencil):
        return _confirm_pencil(state, player_id, message, now, config)
    if isinstance(message, Undo):
        return _undo(state, player_id, now)
    if isinstance(message, Check | Reveal | Vote):
        return _run_help_message(state, player_id, message, now, config)
    if isinstance(message, SelectCell):
        return _select_cell(state, player_id, message)
    if isinstance(message, RemovePlayer | LockRoom | ChangeSettings | MutePlayer):
        return _host_action(state, player_id, message, now)
    if isinstance(message, Flag):
        return _flag(state, player_id, message.clue, now)
    if isinstance(message, Chat):
        return _chat(state, player_id, message.text, now, config)
    if isinstance(message, React):
        return _react(state, player_id, message, now, config)
    return Outcome(state=state)


def _times_in_window(
    times: tuple[float, ...], now: float, window_seconds: float
) -> tuple[float, ...]:
    """Return the times `t` with `t > now - window_seconds`, in their order."""
    recent: list[float] = []
    for past_time in times:
        if past_time > now - window_seconds:
            recent.append(past_time)
    return tuple(recent)


def _chat(
    state: RoomState, player_id: str, text: str, now: float, config: RoomConfig
) -> Outcome:
    """Refuse, drop or number a chat message; the first case that applies decides.

    A muted sender is refused with muted. A sender who already sent
    `config.chat_limit` messages in the window is dropped: nothing changes and
    nothing is sent. Otherwise one chat_message is numbered and added to the
    room's chat (spec 022).
    """
    player = _find_player(state, player_id)
    if player is None:
        return Outcome(state=state)
    if player.muted:
        return _refuse(state, ErrorCode.MUTED, "The host muted your chat.")
    recent = _times_in_window(player.recent_chat, now, config.chat_window_seconds)
    if len(recent) >= config.chat_limit:
        return Outcome(state=state)
    counted = player.model_copy(update={"recent_chat": (*recent, now)})
    counted_state = _replace_player(state, counted)
    event = ChatMessage(seq=state.seq + 1, player_id=player_id, text=text)
    entry = LogEntry(at=now, event=event)
    return Outcome(state=replay(counted_state, entry), entries=(entry,))


def _react(
    state: RoomState, player_id: str, message: React, now: float, config: RoomConfig
) -> Outcome:
    """Relay a reaction to every player, or drop it without an answer.

    It is dropped when the sender is muted, when its clue names no word, or
    when the sender already sent `config.reaction_limit` reactions in the
    window. A relayed reaction has no seq and is never logged (spec 022).
    """
    player = _find_player(state, player_id)
    if player is None or player.muted:
        return Outcome(state=state)
    if _word_cells_of_clue(state, message.clue) is None:
        return Outcome(state=state)
    recent = _times_in_window(
        player.recent_reactions, now, config.reaction_window_seconds
    )
    if len(recent) >= config.reaction_limit:
        return Outcome(state=state)
    counted = player.model_copy(update={"recent_reactions": (*recent, now)})
    reaction_shown = ReactionShown(
        player_id=player_id, clue=message.clue, reaction=message.reaction
    )
    return Outcome(
        state=_replace_player(state, counted),
        reply=(reaction_shown,),
        to_others=(reaction_shown,),
    )


def _flag(
    state: RoomState, player_id: str, clue: ClueRef | None, now: float
) -> Outcome:
    """Set or remove the sender's flag; the first case that applies decides.

    Removing a flag one does not hold, or flagging the clue one already flagged,
    changes nothing. A clue that names no word, or whose word is full, is refused
    with invalid_target. Otherwise one flag_changed is numbered (spec 021).
    """
    player = _find_player(state, player_id)
    if player is None:
        return Outcome(state=state)
    if clue is None:
        if player.flag is None:
            return Outcome(state=state)
        return _announce_flag(state, player_id, None, now)
    word_cells = _word_cells_of_clue(state, clue)
    if word_cells is None:
        return _refuse(state, ErrorCode.INVALID_TARGET, "That clue names no word.")
    if _is_word_full(word_cells):
        return _refuse(state, ErrorCode.INVALID_TARGET, "That word is already full.")
    if clue == player.flag:
        return Outcome(state=state)
    return _announce_flag(state, player_id, clue, now)


def _announce_flag(
    state: RoomState, player_id: str, clue: ClueRef | None, now: float
) -> Outcome:
    """Number one flag_changed for a player and apply it."""
    event = FlagChanged(seq=state.seq + 1, player_id=player_id, clue=clue)
    entry = LogEntry(at=now, event=event)
    return Outcome(state=replay(state, entry), entries=(entry,))


def _word_cells_of_clue(state: RoomState, clue: ClueRef) -> list[CellState] | None:
    """Return the cells of the word a clue names, or None when it names none."""
    try:
        positions = state.grid.word_cells(clue.row, clue.column, clue.clue_index)
    except (IndexError, ValueError):
        return None
    cells: list[CellState] = []
    for row, column in positions:
        cell = _find_cell(state, row, column)
        if cell is not None:
            cells.append(cell)
    return cells


def _is_word_full(cells: list[CellState]) -> bool:
    """Tell whether every cell of a word holds a letter, a pencil letter included."""
    return all(_is_filled(cell) for cell in cells)


def _changes_cells(outcome: Outcome) -> bool:
    """Tell whether a step's entries hold an edit: a change of a letter or a lock."""
    return any(is_edit(entry) for entry in outcome.entries)


def _with_full_flags_cleared(outcome: Outcome, now: float) -> Outcome:
    """Clear, in players order, every flag whose word a step made full (spec 021).

    Only a step that changed a letter or a lock can fill a word. Each cleared
    flag gets one flag_changed with no clue, numbered after the step's entries.
    """
    if not _changes_cells(outcome):
        return outcome
    new_state = outcome.state
    entries = list(outcome.entries)
    for player in outcome.state.players:
        if player.flag is None:
            continue
        word_cells = _word_cells_of_clue(new_state, player.flag)
        if word_cells is None or not _is_word_full(word_cells):
            continue
        flag_removed = FlagChanged(
            seq=new_state.seq + 1, player_id=player.player_id, clue=None
        )
        entry = LogEntry(at=now, event=flag_removed)
        new_state = replay(new_state, entry)
        entries.append(entry)
    return outcome.model_copy(update={"state": new_state, "entries": tuple(entries)})


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


def _remaining_count(new_allowance: int, used: int) -> int:
    """Return the new allowance minus the reveals already used, never below 0."""
    return max(0, new_allowance - used)


def _change_settings(
    state: RoomState, host: PlayerRecord, message: ChangeSettings, now: float
) -> Outcome:
    """Change the help mode and the reveal allowance, keeping what was used.

    What was used is `state.reveals_used` (spec 024 decision 13), so that a cut
    of the allowance to 0 forgets no reveal.
    """
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
    used = state.reveals_used
    remaining = RevealBudget(
        letters=_remaining_count(message.reveal_budget.letters, used.letters),
        words=_remaining_count(message.reveal_budget.words, used.words),
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


def _refuse_solved(state: RoomState) -> Outcome:
    """Refuse an input because the grid is already solved."""
    return _refuse(state, ErrorCode.GRID_SOLVED, "The grid is already solved.")


def _is_filled(cell: CellState) -> bool:
    """Tell whether a letter cell holds a letter, a pencil letter included."""
    return cell.letter is not None


def _is_full(state: RoomState) -> bool:
    """Tell whether every letter cell of the room is filled."""
    return all(_is_filled(cell) for cell in state.cells)


def _is_right(state: RoomState) -> bool:
    """Tell whether the grid is full and every letter is the solution letter."""
    if not _is_full(state):
        return False
    for cell in state.cells:
        if cell.letter != _solution_letter(state.grid, cell.row, cell.column):
            return False
    return True


def _with_completion(before: RoomState, outcome: Outcome, now: float) -> Outcome:
    """Add the `grid_solved` or `grid_full_wrong` entry a step calls for.

    Only a step that changed a letter or a lock on a grid that is not yet solved
    can complete it. The solving time is the shared timer of spec 027 as the
    step's earlier entries left it; the `grid_solved` entry then stops the timer.
    """
    if before.solved or not outcome.entries:
        return outcome
    if not _changes_cells(outcome):
        return outcome

    next_seq = outcome.entries[-1].event.seq + 1
    event: GridSolved | GridFullWrong
    if _is_right(outcome.state):
        elapsed_ms = timer_value_ms(outcome.state, now)
        event = GridSolved(seq=next_seq, elapsed_ms=elapsed_ms)
    elif _is_full(outcome.state) and not _is_full(before):
        event = GridFullWrong(seq=next_seq)
    else:
        return outcome
    entry = LogEntry(at=now, event=event)
    new_state = replay(outcome.state, entry)
    return outcome.model_copy(
        update={"state": new_state, "entries": (*outcome.entries, entry)}
    )


def _refuse(state: RoomState, code: ErrorCode, text: str) -> Outcome:
    """Return an outcome that changes nothing and answers with one error."""
    return Outcome(state=state, reply=(ErrorMessage(code=code, message=text),))


def _find_cell(state: RoomState, row: int, column: int) -> CellState | None:
    """Return the room's state of the letter cell at (row, column), or None."""
    for cell in state.cells:
        if cell.row == row and cell.column == column:
            return cell
    return None


def _check_edit(
    state: RoomState,
    player_id: str,
    edit: EditLetter | Erase | PencilEdit | ConfirmPencil,
    now: float,
    config: RoomConfig,
) -> CellState | Outcome:
    """Run the edit checks in their fixed order.

    Check 5 refuses every edit once the grid is solved (spec 026). A
    confirmation has one more check of its own, after these five (spec 020).

    Returns:
        The edited cell as it is now when every check passes, or else the
        outcome of the first refusal.
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
    if state.solved:
        return _refuse_solved(state)
    return cell


def _is_stale(
    cell: CellState,
    player_id: str,
    edit: EditLetter | Erase | PencilEdit | ConfirmPencil,
) -> bool:
    """Tell whether someone else changed the cell after the edit's `base_seq`."""
    if edit.base_seq is None:
        return False
    if cell.changed_seq <= edit.base_seq:
        return False
    return cell.changed_by != player_id


def _letter_of(edit: EditLetter | Erase | PencilEdit) -> str | None:
    """Return the letter an edit writes: the typed letter, None for an erase."""
    if isinstance(edit, EditLetter | PencilEdit):
        return edit.letter
    return None


def _apply_edit(
    state: RoomState,
    player_id: str,
    edit: EditLetter | Erase | PencilEdit,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Check one edit, then write it in the cell and number its event.

    A `pencil_edit` writes a pencil letter (spec 020); the other two write a
    normal letter or empty the cell.
    """
    cell_or_refusal = _check_edit(state, player_id, edit, now, config)
    if isinstance(cell_or_refusal, Outcome):
        return cell_or_refusal
    old_cell = cell_or_refusal
    letter = _letter_of(edit)
    is_pencil = isinstance(edit, PencilEdit)
    return _write_cell(state, player_id, old_cell, letter, is_pencil, now)


def _confirm_pencil(
    state: RoomState,
    player_id: str,
    confirmation: ConfirmPencil,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Check a confirmation, then make the cell's pencil letter a normal letter.

    After the five edit checks, a cell that holds no pencil letter is refused
    with stale_edit (spec 020 decision 2). The confirmer becomes the author.
    """
    cell_or_refusal = _check_edit(state, player_id, confirmation, now, config)
    if isinstance(cell_or_refusal, Outcome):
        return cell_or_refusal
    old_cell = cell_or_refusal
    if old_cell.letter is None or not old_cell.pencil:
        return _refuse(
            state,
            ErrorCode.STALE_EDIT,
            f"({confirmation.row}, {confirmation.column}) holds no pencil letter.",
        )
    return _write_cell(state, player_id, old_cell, old_cell.letter, False, now)


def _write_cell(
    state: RoomState,
    player_id: str,
    old_cell: CellState,
    letter: str | None,
    is_pencil: bool,
    now: float,
) -> Outcome:
    """Write an accepted edit in its cell, count it and number its event.

    The player becomes the author of the letter (an empty cell has none) and
    their `last_edit` records the cell as it was (spec 018). The first letter
    typed starts the shared timer (spec 027).
    """
    seq = state.seq + 1
    author = player_id if letter is not None else None
    edited_cell = old_cell.model_copy(
        update={
            "letter": letter,
            "pencil": is_pencil,
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
        row=old_cell.row,
        column=old_cell.column,
        letter=letter,
        pencil=is_pencil,
        player_id=player_id,
    )
    entry = LogEntry(at=now, event=event)
    return Outcome(state=_with_timer_rules(new_state, entry), entries=(entry,))


def _run_help_message(
    state: RoomState,
    player_id: str,
    message: Check | Reveal | Vote,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Close an expired vote, then run a check, a reveal or a ballot (spec 025).

    The closing entry of the expired vote comes before the message's own
    entries, so a late ballot finds no open vote.
    """
    expiry = _expire_vote(state, now)
    if isinstance(message, Vote):
        outcome = _vote(expiry.state, player_id, message, now)
    else:
        outcome = _run_request(expiry.state, message, player_id, now, config)
    all_entries = (*expiry.entries, *outcome.entries)
    return outcome.model_copy(update={"entries": all_entries})


def _run_request(
    state: RoomState,
    request: Check | Reveal,
    player_id: str,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Run a check or a reveal: refuse it, put it to a vote, or apply it.

    The refusal steps of spec 023 (a check) or spec 024 (a reveal) come first.
    Then a request that needs a vote is refused while another vote is open,
    applied at once when its sender is the only connected player, and opens a
    vote otherwise (spec 025).
    """
    refusal = _request_refusal(state, request)
    if refusal is not None:
        return refusal
    if not _needs_vote(state, request):
        return _apply_request(state, request, player_id, now)
    if state.open_vote is not None:
        return _refuse(state, ErrorCode.VOTE_IN_PROGRESS, "A vote is already open.")
    eligible = _eligible_voters(state)
    if len(eligible) <= 1:
        return _apply_request(state, request, player_id, now)
    return _open_vote(state, request, player_id, len(eligible), now, config)


def _request_refusal(state: RoomState, request: Check | Reveal) -> Outcome | None:
    """Return the refusal of a check (spec 023) or a reveal (spec 024), or None."""
    if isinstance(request, Check):
        return _check_refusal(state, request.target)
    return _reveal_refusal(state, request.target)


def _apply_request(
    state: RoomState, request: Check | Reveal, player_id: str, now: float
) -> Outcome:
    """Apply a check or a reveal that no refusal step stopped."""
    if isinstance(request, Check):
        return _apply_check(state, request.target, player_id, now)
    return _apply_reveal(state, request.target, player_id, now)


def _needs_vote(state: RoomState, request: Check | Reveal) -> bool:
    """Tell whether a request needs a vote (spec 025).

    In help mode `vote`, a grid check and every reveal need one. A check of a
    letter or a word never does.
    """
    if state.settings.help_mode != HelpMode.VOTE:
        return False
    if isinstance(request, Reveal):
        return True
    return isinstance(request.target, GridTarget)


def _eligible_voters(state: RoomState) -> tuple[str, ...]:
    """Return the ids of the players who are not disconnected, in players order."""
    eligible: list[str] = []
    for player in state.players:
        if player.state != PlayerState.DISCONNECTED:
            eligible.append(player.player_id)
    return tuple(eligible)


def _open_vote(
    state: RoomState,
    request: Check | Reveal,
    player_id: str,
    voter_count: int,
    now: float,
    config: RoomConfig,
) -> Outcome:
    """Number the vote_opened of a request; nothing else changes."""
    opened = VoteOpened(
        seq=state.seq + 1,
        vote_id=state.last_vote_id + 1,
        player_id=player_id,
        request=request,
        timeout_seconds=config.vote_timeout_seconds,
        eligible_voters=voter_count,
    )
    entry = LogEntry(at=now, event=opened)
    return Outcome(state=replay(state, entry), entries=(entry,))


def _vote(state: RoomState, player_id: str, ballot: Vote, now: float) -> Outcome:
    """Count a ballot on the open vote, and close the vote once its outcome is sure.

    A ballot for no open vote is refused with no_open_vote. A ballot of a player
    who is not eligible, or who already voted, changes nothing.
    """
    vote = state.open_vote
    if vote is None or vote.opened.vote_id != ballot.vote_id:
        return _refuse(state, ErrorCode.NO_OPEN_VOTE, "No vote with this id is open.")
    has_voted = player_id in vote.yes or player_id in vote.no
    if player_id not in vote.eligible or has_voted:
        return Outcome(state=state)
    if ballot.yes:
        counted = vote.model_copy(update={"yes": (*vote.yes, player_id)})
    else:
        counted = vote.model_copy(update={"no": (*vote.no, player_id)})
    counted_state = state.model_copy(update={"open_vote": counted})

    eligible_count = len(counted.eligible)
    if len(counted.yes) * 2 > eligible_count:
        return _pass_vote(counted_state, counted, now)
    yes_still_possible = eligible_count - len(counted.no)
    if yes_still_possible * 2 <= eligible_count:
        return _close_vote(counted_state, counted, VoteOutcome.REJECTED, now)
    return Outcome(state=counted_state)


def _pass_vote(state: RoomState, vote: OpenVote, now: float) -> Outcome:
    """Apply the request of a vote that reached a majority of yes.

    The request is checked again as if its requester sent it now. When a
    refusal step stops it, the vote closes `rejected` and nothing else happens.
    """
    request = vote.opened.request
    if _request_refusal(state, request) is not None:
        return _close_vote(state, vote, VoteOutcome.REJECTED, now)
    closing = _close_vote(state, vote, VoteOutcome.PASSED, now)
    applied = _apply_request(closing.state, request, vote.opened.player_id, now)
    all_entries = (*closing.entries, *applied.entries)
    return applied.model_copy(update={"entries": all_entries})


def _close_vote(
    state: RoomState, vote: OpenVote, result: VoteOutcome, now: float
) -> Outcome:
    """Number the vote_closed of the open vote and clear it."""
    closed = VoteClosed(
        seq=state.seq + 1,
        vote_id=vote.opened.vote_id,
        outcome=result,
        yes_votes=len(vote.yes),
        eligible_voters=len(vote.eligible),
    )
    entry = LogEntry(at=now, event=closed)
    return Outcome(state=replay(state, entry), entries=(entry,))


def _expire_vote(state: RoomState, now: float) -> Outcome:
    """Close the open vote `timed_out` once `now` reaches its end time."""
    vote = state.open_vote
    if vote is None:
        return Outcome(state=state)
    ends_at = vote.opened_at + vote.opened.timeout_seconds
    if now < ends_at:
        return Outcome(state=state)
    return _close_vote(state, vote, VoteOutcome.TIMED_OUT, now)


def _check_refusal(state: RoomState, target: CheckTarget) -> Outcome | None:
    """Return the refusal of a check, or None when it may go on.

    The grid-solved refusal (spec 026) comes first, then help mode `none`, then
    a target that names nothing (spec 023).
    """
    if state.solved:
        return _refuse_solved(state)
    if state.settings.help_mode == HelpMode.NONE:
        return _refuse(state, ErrorCode.HELP_DISABLED, "Checks are turned off.")
    return _refuse_bad_target(state, target)


def _apply_check(
    state: RoomState, target: CheckTarget, player_id: str, now: float
) -> Outcome:
    """Apply a check: one check_result, then one cell_locked per correct cell."""
    scope = _cells_in_scope(state, target)

    correct: list[CellState] = []
    wrong: list[CellState] = []
    for cell in scope:
        if cell.letter is None or cell.locked or cell.pencil:
            continue
        if cell.letter == _solution_letter(state.grid, cell.row, cell.column):
            correct.append(cell)
        else:
            wrong.append(cell)

    result = CheckResult(
        seq=state.seq + 1,
        player_id=player_id,
        target=target,
        correct=_refs_of(correct),
        wrong=_refs_of(wrong),
    )
    entries = [LogEntry(at=now, event=result)]
    seq = result.seq
    for cell in correct:
        seq += 1
        locked = CellLocked(
            seq=seq,
            row=cell.row,
            column=cell.column,
            letter=cell.letter or "",
            revealed=False,
        )
        entries.append(LogEntry(at=now, event=locked))

    new_state = state
    for entry in entries:
        new_state = replay(new_state, entry)
    return Outcome(state=new_state, entries=tuple(entries))


def _reveal_refusal(
    state: RoomState, target: CellTarget | WordTarget
) -> Outcome | None:
    """Return the refusal of a reveal, or None when it may go on.

    The refusals come in this order (spec 024): solved grid, help mode `none`,
    a target that names nothing, nothing left to reveal, spent budget.
    """
    if state.solved:
        return _refuse_solved(state)
    if state.settings.help_mode == HelpMode.NONE:
        return _refuse(state, ErrorCode.HELP_DISABLED, "Reveals are turned off.")
    refusal = _refuse_bad_target(state, target)
    if refusal is not None:
        return refusal
    cells_to_reveal = _unlocked_cells(_cells_in_scope(state, target))
    if not cells_to_reveal:
        return _refuse(
            state, ErrorCode.INVALID_TARGET, "Nothing is left to reveal there."
        )
    if _is_budget_spent(state.reveal_budget, target):
        return _refuse(state, ErrorCode.BUDGET_EXHAUSTED, "The reveal budget is spent.")
    return None


def _apply_reveal(
    state: RoomState, target: CellTarget | WordTarget, player_id: str, now: float
) -> Outcome:
    """Apply a reveal: one reveal_result, then one cell_locked per revealed cell."""
    cells_to_reveal = _unlocked_cells(_cells_in_scope(state, target))
    result = RevealResult(
        seq=state.seq + 1,
        player_id=player_id,
        target=target,
        reveal_budget=_budget_after_reveal(state.reveal_budget, target),
    )
    entries = [LogEntry(at=now, event=result)]
    seq = result.seq
    for cell in cells_to_reveal:
        seq += 1
        locked = CellLocked(
            seq=seq,
            row=cell.row,
            column=cell.column,
            letter=_required_solution_letter(state.grid, cell),
            revealed=True,
        )
        entries.append(LogEntry(at=now, event=locked))

    new_state = state
    for entry in entries:
        new_state = replay(new_state, entry)
    return Outcome(state=new_state, entries=tuple(entries))


def _unlocked_cells(cells: list[CellState]) -> list[CellState]:
    """Return the cells that are not locked, in the same order."""
    unlocked: list[CellState] = []
    for cell in cells:
        if not cell.locked:
            unlocked.append(cell)
    return unlocked


def _is_budget_spent(budget: RevealBudget, target: CellTarget | WordTarget) -> bool:
    """Tell whether no letter (letter target) or no word (word target) is left."""
    if isinstance(target, CellTarget):
        return budget.letters == 0
    return budget.words == 0


def _budget_after_reveal(
    budget: RevealBudget, target: CellTarget | WordTarget
) -> RevealBudget:
    """Return the budget left once a reveal is paid: one letter, or one word."""
    if isinstance(target, CellTarget):
        return RevealBudget(letters=budget.letters - 1, words=budget.words)
    return RevealBudget(letters=budget.letters, words=budget.words - 1)


def _required_solution_letter(grid: Grid, cell: CellState) -> str:
    """Return the solution letter of a letter cell.

    Raises:
        ValueError: the cell belongs to no word of the grid, so it has no
            solution letter.
    """
    letter = _solution_letter(grid, cell.row, cell.column)
    if letter is None:
        raise ValueError(
            f"The letter cell ({cell.row}, {cell.column}) belongs to no word"
        )
    return letter


def _refs_of(cells: list[CellState]) -> tuple[CellRef, ...]:
    """Return the positions of the cells, in the same order."""
    references: list[CellRef] = []
    for cell in cells:
        references.append(CellRef(row=cell.row, column=cell.column))
    return tuple(references)


def _refuse_bad_target(state: RoomState, target: CheckTarget) -> Outcome | None:
    """Return the refusal when a check or a reveal names nothing, else None."""
    if isinstance(target, CellTarget):
        cell = _find_cell(state, target.row, target.column)
        if cell is None:
            return _refuse(
                state,
                ErrorCode.NOT_A_LETTER_CELL,
                f"({target.row}, {target.column}) is not a letter cell.",
            )
    if isinstance(target, WordTarget):
        try:
            state.grid.word_cells(target.row, target.column, target.clue_index)
        except (IndexError, ValueError):
            return _refuse(state, ErrorCode.INVALID_TARGET, "That word does not exist.")
    return None


def _cells_in_scope(state: RoomState, target: CheckTarget) -> list[CellState]:
    """Return the cells a check names. The target is already known valid."""
    if isinstance(target, GridTarget):
        return list(state.cells)
    if isinstance(target, CellTarget):
        cell = _find_cell(state, target.row, target.column)
        return [] if cell is None else [cell]
    return _cells_of_word(state, target)


def _cells_of_word(state: RoomState, target: WordTarget) -> list[CellState]:
    """Return the cells of the word of a clue, in reading order."""
    positions = state.grid.word_cells(target.row, target.column, target.clue_index)
    cells: list[CellState] = []
    for row, column in positions:
        cell = _find_cell(state, row, column)
        if cell is not None:
            cells.append(cell)
    return cells


def _solution_letter(grid: Grid, row: int, column: int) -> str | None:
    """Return the solution letter of a letter cell, from a clue whose word holds it."""
    for clue_cell in grid.cells:
        if not isinstance(clue_cell, ClueCell):
            continue
        for clue_index, clue in enumerate(clue_cell.clues):
            positions = grid.word_cells(clue_cell.row, clue_cell.column, clue_index)
            if (row, column) in positions:
                return clue.answer[positions.index((row, column))]
    return None


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
    limit. Once the grid is solved it is refused with grid_solved, after the
    nothing_to_undo checks (spec 026).
    """
    player = _find_player(state, player_id)
    if player is None or player.last_edit is None:
        return _refuse(state, ErrorCode.NOTHING_TO_UNDO, "Nothing to undo.")
    last_edit = player.last_edit
    cell = _find_cell(state, last_edit.row, last_edit.column)
    if cell is None or cell.locked or cell.changed_seq != last_edit.seq:
        forgotten = _with_last_edit(state, player_id, None)
        return _refuse(forgotten, ErrorCode.NOTHING_TO_UNDO, "Nothing to undo.")
    if state.solved:
        return _refuse_solved(state)

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
    return Outcome(state=_with_timer_rules(new_state, entry), entries=(entry,))


def tick(state: RoomState, now: float, config: RoomConfig = DEFAULT_CONFIG) -> Outcome:
    """Apply the passing of time (spec 013, 014, 017).

    For each player, in `players` order: a joined player silent for too long is
    disconnected and their socket is to be closed; a player disconnected for
    more than the resume window leaves the room. Then each active player
    without input for the idle delay becomes idle. Then a host disconnected for
    more than the hand-over delay hands the host role to the longest-present
    connected player. Last, an open vote whose time is over closes `timed_out`
    (spec 025).
    """
    current = state
    entries: list[LogEntry] = []
    disconnects: list[Disconnect] = []
    to_others: list[SelectionMoved | ReactionShown] = []
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
    expiry_step = _expire_vote(handover_step.state, now)
    entries.extend(expiry_step.entries)
    return Outcome(
        state=expiry_step.state,
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
        specs only move `seq` until those specs extend this function. The timer
        rules of spec 027 run after the entry, with the time `entry.at`.

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
    elif isinstance(event, CheckResult):
        replayed = _replay_check_result(state, event)
    elif isinstance(event, RevealResult):
        replayed = _replay_reveal_result(state, event)
    elif isinstance(event, SettingsChanged):
        replayed = state.model_copy(
            update={"settings": event.settings, "reveal_budget": event.reveal_budget}
        )
    elif isinstance(event, HostChanged):
        replayed = _replay_host_changed(state, event)
    elif isinstance(event, PlayerMuted):
        replayed = _replay_player_muted(state, event)
    elif isinstance(event, GridSolved):
        replayed = state.model_copy(update={"solved": True})
    elif isinstance(event, VoteOpened):
        replayed = _replay_vote_opened(state, entry, event)
    elif isinstance(event, VoteClosed):
        replayed = state.model_copy(update={"open_vote": None})
    elif isinstance(event, FlagChanged):
        replayed = _replay_flag_changed(state, event)
    elif isinstance(event, ChatMessage):
        replayed = state.model_copy(update={"chat": (*state.chat, event)})
    else:
        replayed = state
    numbered = replayed.model_copy(update={"seq": event.seq})
    return _with_timer_rules(numbered, entry)


def _replay_vote_opened(
    state: RoomState, entry: LogEntry, event: VoteOpened
) -> RoomState:
    """Open the vote with the requester's yes as its only ballot (spec 025).

    The eligible voters are the players not disconnected before the entry.
    Ballots are not logged, so a vote rebuilt from the log holds no other one.
    """
    vote = OpenVote(
        opened=event,
        opened_at=entry.at,
        eligible=_eligible_voters(state),
        yes=(event.player_id,),
    )
    return state.model_copy(update={"open_vote": vote, "last_vote_id": event.vote_id})


def _replay_reveal_result(state: RoomState, event: RevealResult) -> RoomState:
    """Take the budget left and count one more reveal of the target's kind."""
    used = state.reveals_used
    if isinstance(event.target, CellTarget):
        new_used = RevealBudget(letters=used.letters + 1, words=used.words)
    else:
        new_used = RevealBudget(letters=used.letters, words=used.words + 1)
    return state.model_copy(
        update={"reveal_budget": event.reveal_budget, "reveals_used": new_used}
    )


def _replay_player_joined(
    state: RoomState, entry: LogEntry, event: PlayerJoined
) -> RoomState:
    """Append the player of a logged join.

    A past player with the same id is one no more: the join seated them back
    (spec 032).
    """
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
    still_past: list[PastPlayer] = []
    for past_player in state.past_players:
        if past_player.player_id != view.player_id:
            still_past.append(past_player)
    return state.model_copy(
        update={"players": (*state.players, player), "past_players": tuple(still_past)}
    )


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
    """Remove a player from the room.

    A removed player's token is banned (spec 014). A player who timed out or
    left becomes a past player, whom their token seats back (spec 032).
    """
    remaining: list[PlayerRecord] = []
    removed_tokens = state.removed_tokens
    past_players = state.past_players
    for player in state.players:
        if player.player_id != event.player_id:
            remaining.append(player)
        elif event.reason == LeaveReason.REMOVED:
            removed_tokens = (*removed_tokens, player.resume_token)
        else:
            past_players = _with_past_player(past_players, _past_record_of(player))
    return state.model_copy(
        update={
            "players": tuple(remaining),
            "removed_tokens": removed_tokens,
            "past_players": past_players,
        }
    )


def _past_record_of(player: PlayerRecord) -> PastPlayer:
    """Return what the room keeps of a player who leaves (spec 032)."""
    return PastPlayer(
        player_id=player.player_id,
        resume_token=player.resume_token,
        nickname=player.nickname,
        colour=player.colour,
        muted=player.muted,
    )


def _with_past_player(
    past_players: tuple[PastPlayer, ...], record: PastPlayer
) -> tuple[PastPlayer, ...]:
    """Append `record`; the oldest past player goes when MAX_PAST_PLAYERS are kept."""
    kept = past_players
    if len(kept) >= MAX_PAST_PLAYERS:
        kept = kept[1:]
    return (*kept, record)


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
    """Lock a cell with its letter, never a pencil one; a reveal clears the author."""
    cell = _find_cell(state, event.row, event.column)
    if cell is None:
        return state
    locked_cell = cell.model_copy(
        update={
            "letter": event.letter,
            "pencil": False,
            "locked": True,
            "revealed": event.revealed,
            "wrong": False,
            "changed_seq": event.seq,
            "changed_by": None,
        }
    )
    if event.revealed:
        locked_cell = locked_cell.model_copy(update={"author": None})
    return _replace_cell(state, locked_cell)


def _replay_check_result(state: RoomState, event: CheckResult) -> RoomState:
    """Mark the wrong cells of a check result."""
    replayed = state
    for reference in event.wrong:
        cell = _find_cell(replayed, reference.row, reference.column)
        if cell is None:
            continue
        replayed = _replace_cell(replayed, cell.model_copy(update={"wrong": True}))
    return replayed


def _replay_host_changed(state: RoomState, event: HostChanged) -> RoomState:
    """Give the host role to one player and take it from the others."""
    players: list[PlayerRecord] = []
    for player in state.players:
        is_host = player.player_id == event.player_id
        players.append(player.model_copy(update={"is_host": is_host}))
    return state.model_copy(update={"players": tuple(players)})


def _replay_flag_changed(state: RoomState, event: FlagChanged) -> RoomState:
    """Set or clear a player's flag; nothing when the player is not in the room."""
    player = _find_player(state, event.player_id)
    if player is None:
        return state
    return _replace_player(state, player.model_copy(update={"flag": event.clue}))


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
        `PlayerStateChanged(disconnected)` each, in players order. Every
        player, connected or disconnected, gets empty chat and reaction
        windows, with no entry (spec 022 decision 17). An open vote keeps the
        requester's yes only, with no entry (spec 025 decision 16). A running
        shared timer pauses at `now`, which counts the time since the crash
        (spec 027 decision 7).
    """
    seq = state.seq
    players: list[PlayerRecord] = []
    entries: list[LogEntry] = []
    for player in state.players:
        if player.state == PlayerState.DISCONNECTED:
            already_disconnected = player.model_copy(
                update={"recent_chat": (), "recent_reactions": ()}
            )
            players.append(already_disconnected)
            continue
        seq += 1
        disconnected = player.model_copy(
            update={
                "state": PlayerState.DISCONNECTED,
                "disconnected_at": now,
                "selection": None,
                "recent_edits": (),
                "recent_chat": (),
                "recent_reactions": (),
            }
        )
        players.append(disconnected)
        event = PlayerStateChanged(
            seq=seq, player_id=player.player_id, state=PlayerState.DISCONNECTED
        )
        entries.append(LogEntry(at=now, event=event))
    restarted_state = state.model_copy(
        update={
            "players": tuple(players),
            "seq": seq,
            "open_vote": _without_ballots(state.open_vote),
        }
    )
    # The timer rules of spec 027 (a running timer pauses once nobody is
    # connected). The entries are all at `now` and only disconnect players, so
    # the rules give the same timer on the final room as after each entry.
    new_state = restarted_state
    for entry in entries:
        new_state = _with_timer_rules(new_state, entry)
    return Outcome(state=new_state, entries=tuple(entries))


def _without_ballots(vote: OpenVote | None) -> OpenVote | None:
    """Return the vote with the requester's yes as its only ballot.

    A saved snapshot holds the ballots and the log does not, so this makes a
    room loaded from a snapshot hold the same vote as one rebuilt from the log.
    """
    if vote is None:
        return None
    return vote.model_copy(update={"yes": (vote.opened.player_id,), "no": ()})
