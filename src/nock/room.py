"""Room state models and the pure rules applied to each event.

Nothing here does I/O, reads a clock or touches the network: time is passed in
as `now`. The runtime that drives these functions is `nock.hub`.
"""

from __future__ import annotations

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
    Coordinate,
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

MAX_PLAYERS: int = 8  # spec 012 AC-4
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
    """Return the nickname without the spaces around it (spec 012 adds the rules)."""
    return text.strip()


def player_views(state: RoomState) -> tuple[PlayerView, ...]:
    """Return the players as the other players see them (spec 012)."""
    views: list[PlayerView] = []
    for player in state.players:
        views.append(
            PlayerView(
                player_id=player.player_id,
                nickname=player.nickname,
                colour=player.colour,
                state=player.state,
                is_host=player.is_host,
                muted=player.muted,
                selection=player.selection,
            )
        )
    return tuple(views)


def snapshot_for(state: RoomState, player_id: str) -> Snapshot:
    """Return the snapshot sent to a player of the room (spec 012).

    Raises:
        ValueError: `player_id` is not a player of `state`.
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
    raise ValueError(f"Player {player_id!r} is not in room {state.code}")


def join_room(
    state: RoomState,
    message: Join,
    now: float,
    new_player_id: str,
    new_resume_token: str,
) -> Outcome:
    """Apply a join (spec 012, 014, 017). For now nobody is added."""
    return Outcome(state=state)


def disconnect_player(state: RoomState, player_id: str, now: float) -> Outcome:
    """Apply the closing of a player's connection (spec 012, 013)."""
    return Outcome(state=state)


def handle_message(
    state: RoomState,
    player_id: str,
    message: ClientMessage,
    now: float,
    config: RoomConfig = DEFAULT_CONFIG,
) -> Outcome:
    """Apply a message of a joined player (spec 015 and later).

    Until the spec that gives a message its meaning is built, the message is
    read and ignored: the state is unchanged and nothing is sent.
    """
    return Outcome(state=state)


def tick(state: RoomState, now: float, config: RoomConfig = DEFAULT_CONFIG) -> Outcome:
    """Apply the passing of time (spec 013, 014, 017)."""
    return Outcome(state=state)


def replay(state: RoomState, entry: LogEntry) -> RoomState:
    """Return the state after a logged event (spec 018)."""
    return state


def after_restart(state: RoomState, now: float) -> Outcome:
    """Apply what a server restart changes (spec 018)."""
    return Outcome(state=state)
