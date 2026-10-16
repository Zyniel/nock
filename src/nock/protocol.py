"""Room events protocol: every message between the browser and the server.

Messages are frozen Pydantic models. Unknown fields are rejected, and integers
and booleans are strict. The grid sent to the browser never holds answers.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    TypeAdapter,
)

from nock.grid import Arrow, ClueCell, EmptyCell, Grid, LetterCell


class ProtocolModel(BaseModel):
    """Base of every protocol model: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---- Shared value types -------------------------------------------------

Coordinate = Annotated[int, Field(ge=0, strict=True)]  # row or column
Count = Annotated[int, Field(ge=0, strict=True)]
Seq = Annotated[int, Field(ge=1, strict=True)]  # room event number
SnapshotSeq = Annotated[int, Field(ge=0, strict=True)]
ClueIndex = Annotated[int, Field(ge=0, le=1, strict=True)]
VoteId = Annotated[int, Field(ge=1, strict=True)]
Colour = Annotated[int, Field(ge=0, le=7, strict=True)]  # palette index
Letter = Annotated[str, Field(min_length=1, max_length=1, pattern=r"^[A-Z]$")]
PlayerId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
ResumeToken = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")]
Nickname = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=20)
]


# A chat text is stripped as Python's str.strip() does, then must hold 1 to 280
# characters (spec 039 AC-8). Pydantic's strip_whitespace keeps the separators
# U+001C to U+001F, so it is not used here.
def _strip_text(value: object) -> object:
    """Return a str stripped as str.strip() does; any other value unchanged.

    Args:
        value: The raw value of a chat text field.

    Returns:
        The stripped text when `value` is a str, else `value` itself, which the
        str validation that follows then refuses.
    """
    if isinstance(value, str):
        return value.strip()
    return value


ChatText = Annotated[
    str, Field(min_length=1, max_length=280), BeforeValidator(_strip_text)
]


class Direction(StrEnum):
    """Direction in which a player types."""

    ACROSS = "across"
    DOWN = "down"


class PlayerState(StrEnum):
    """Presence of a player."""

    ACTIVE = "active"  # spec 013 AC-1
    IDLE = "idle"
    DISCONNECTED = "disconnected"


class HelpMode(StrEnum):
    """Who may ask for checks and reveals."""

    FREE = "free"  # spec 025 AC-1
    VOTE = "vote"
    NONE = "none"


class Reaction(StrEnum):
    """The reactions a player can show on a clue."""

    THUMBS_UP = "thumbs_up"  # spec 022 AC-2, a set of 5
    CLAP = "clap"
    LAUGH = "laugh"
    WOW = "wow"
    THINKING = "thinking"


class LeaveReason(StrEnum):
    """Why a player left the room."""

    LEFT = "left"  # closed the room on purpose
    REMOVED = "removed"  # removed by the host, spec 014 AC-1
    TIMED_OUT = "timed_out"  # disconnected past the spec 017 window


class VoteOutcome(StrEnum):
    """How a vote ended."""

    PASSED = "passed"  # spec 025 AC-2, AC-3
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class ErrorCode(StrEnum):
    """Why the server refused a message."""

    INVALID_MESSAGE = "invalid_message"  # failed parse_client_message
    NOT_JOINED = "not_joined"  # any message before join
    ROOM_FULL = "room_full"  # spec 012 AC-4
    ROOM_LOCKED = "room_locked"  # spec 014 AC-2
    REMOVED = "removed"  # spec 014 AC-1
    NOT_HOST = "not_host"  # host action from a non-host
    NOT_A_LETTER_CELL = "not_a_letter_cell"  # spec 037 AC-2
    CELL_LOCKED = "cell_locked"  # spec 016 AC-3
    HELP_DISABLED = "help_disabled"  # help mode none, spec 025 AC-4
    BUDGET_EXHAUSTED = "budget_exhausted"  # spec 024 AC-3
    VOTE_IN_PROGRESS = "vote_in_progress"
    NO_OPEN_VOTE = "no_open_vote"
    MUTED = "muted"  # spec 022 AC-4
    RATE_LIMITED = "rate_limited"  # spec 037 AC-3
    NOTHING_TO_UNDO = "nothing_to_undo"  # spec 018 AC-3
    GRID_SOLVED = "grid_solved"  # input locked, spec 026 AC-1
    INVALID_NICKNAME = "invalid_nickname"  # refused nickname, spec 012 join step 5
    INVALID_TARGET = "invalid_target"  # host action on a bad player, spec 014
    STALE_EDIT = "stale_edit"  # offline edit on a changed cell, spec 017 AC-2


class CellRef(ProtocolModel):
    """A cell, named by its position."""

    row: Coordinate
    column: Coordinate


class ClueRef(ProtocolModel):
    """A word, named by its clue: clue cell position and index in that cell."""

    row: Coordinate
    column: Coordinate
    clue_index: ClueIndex


class Selection(ProtocolModel):
    """The cell a player has selected and the direction of typing."""

    row: Coordinate
    column: Coordinate
    direction: Direction


class CellTarget(ProtocolModel):
    """A check or reveal aimed at one letter cell."""

    scope: Literal["letter"] = "letter"
    row: Coordinate
    column: Coordinate


class WordTarget(ProtocolModel):
    """A check or reveal aimed at the word of one clue."""

    scope: Literal["word"] = "word"
    row: Coordinate  # clue cell
    column: Coordinate
    clue_index: ClueIndex


class GridTarget(ProtocolModel):
    """A check aimed at the whole grid."""

    scope: Literal["grid"] = "grid"


CheckTarget = Annotated[
    CellTarget | WordTarget | GridTarget, Field(discriminator="scope")
]
RevealTarget = Annotated[CellTarget | WordTarget, Field(discriminator="scope")]


class RevealBudget(ProtocolModel):
    """How many letters and words can still be revealed.

    Spec 024 AC-2: the default is 5 letters and 1 word.
    """

    letters: Count
    words: Count


class RoomSettings(ProtocolModel):
    """Settings the host controls."""

    help_mode: HelpMode
    reveal_budget: RevealBudget  # the allowance the host set
    locked: StrictBool  # spec 014 AC-2


# ---- Client to server ---------------------------------------------------


class Join(ProtocolModel):
    """Enter the room, or resume with a token from an earlier snapshot."""

    type: Literal["join"] = "join"
    nickname: Nickname
    resume_token: ResumeToken | None = None  # from an earlier snapshot


class SelectCell(ProtocolModel):
    """Select a cell."""

    type: Literal["select_cell"] = "select_cell"
    row: Coordinate
    column: Coordinate
    direction: Direction


class EditLetter(ProtocolModel):
    """Write a letter in a cell."""

    type: Literal["edit_letter"] = "edit_letter"
    row: Coordinate
    column: Coordinate
    letter: Letter
    base_seq: SnapshotSeq | None = None


class Erase(ProtocolModel):
    """Erase a cell."""

    type: Literal["erase"] = "erase"
    row: Coordinate
    column: Coordinate
    base_seq: SnapshotSeq | None = None


class PencilEdit(ProtocolModel):
    """Write a pencil letter in a cell."""

    type: Literal["pencil_edit"] = "pencil_edit"
    row: Coordinate
    column: Coordinate
    letter: Letter
    base_seq: SnapshotSeq | None = None


class ConfirmPencil(ProtocolModel):
    """Turn a pencil letter into a pen letter."""

    type: Literal["confirm_pencil"] = "confirm_pencil"
    row: Coordinate
    column: Coordinate
    base_seq: SnapshotSeq | None = None


class Check(ProtocolModel):
    """Ask for a check of a letter, a word or the grid."""

    type: Literal["check"] = "check"
    target: CheckTarget


class Reveal(ProtocolModel):
    """Ask for the reveal of a letter or a word."""

    type: Literal["reveal"] = "reveal"
    target: RevealTarget


class Vote(ProtocolModel):
    """Answer an open vote."""

    type: Literal["vote"] = "vote"
    vote_id: VoteId
    yes: StrictBool


class Flag(ProtocolModel):
    """Flag a clue as stuck; `clue` of None removes my flag."""

    type: Literal["flag"] = "flag"
    clue: ClueRef | None  # None removes my flag


class Chat(ProtocolModel):
    """Send a chat message."""

    type: Literal["chat"] = "chat"
    text: ChatText


class React(ProtocolModel):
    """Show a reaction on a clue."""

    type: Literal["react"] = "react"
    clue: ClueRef
    reaction: Reaction


class Undo(ProtocolModel):
    """Undo my last change."""

    type: Literal["undo"] = "undo"


class RemovePlayer(ProtocolModel):
    """Host action: remove a player."""

    type: Literal["remove_player"] = "remove_player"
    player_id: PlayerId


class LockRoom(ProtocolModel):
    """Host action: lock the room, or unlock it with `locked` False."""

    type: Literal["lock_room"] = "lock_room"
    locked: StrictBool  # False unlocks


class ChangeSettings(ProtocolModel):
    """Host action: change the help mode and the reveal budget."""

    type: Literal["change_settings"] = "change_settings"
    help_mode: HelpMode
    reveal_budget: RevealBudget


class MutePlayer(ProtocolModel):
    """Host action: mute or unmute the chat of a player."""

    type: Literal["mute_player"] = "mute_player"
    player_id: PlayerId
    muted: StrictBool


class Ping(ProtocolModel):
    """Heartbeat, spec 017. The server answers with a pong."""

    type: Literal["ping"] = "ping"


ClientMessage = Annotated[
    Join
    | SelectCell
    | EditLetter
    | Erase
    | PencilEdit
    | ConfirmPencil
    | Check
    | Reveal
    | Vote
    | Flag
    | Chat
    | React
    | Undo
    | RemovePlayer
    | LockRoom
    | ChangeSettings
    | MutePlayer
    | Ping,
    Field(discriminator="type"),
]


# ---- Grid view (no answers) ---------------------------------------------


class ClueView(ProtocolModel):
    """A clue as the browser sees it: no answer."""

    text: str = Field(min_length=1)
    arrow: Arrow


class LetterCellView(ProtocolModel):
    """A letter cell and the room's current state of it."""

    type: Literal["letter"] = "letter"
    row: Coordinate
    column: Coordinate
    letter: Letter | None
    pencil: StrictBool
    author: PlayerId | None
    locked: StrictBool
    revealed: StrictBool
    wrong: StrictBool


class ClueCellView(ProtocolModel):
    """A clue cell as the browser sees it."""

    type: Literal["clue"] = "clue"
    row: Coordinate
    column: Coordinate
    clues: tuple[ClueView, ...] = Field(min_length=1, max_length=2)


class EmptyCellView(ProtocolModel):
    """An empty cell."""

    type: Literal["empty"] = "empty"
    row: Coordinate
    column: Coordinate


CellView = Annotated[
    LetterCellView | ClueCellView | EmptyCellView, Field(discriminator="type")
]


class GridView(ProtocolModel):
    """The client-facing copy of a grid layout."""

    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    cells: tuple[CellView, ...]


def _view_of_letter_cell(cell: LetterCell) -> LetterCellView:
    """Return the empty view of a letter cell."""
    return LetterCellView(
        row=cell.row,
        column=cell.column,
        letter=None,
        pencil=False,
        author=None,
        locked=False,
        revealed=False,
        wrong=False,
    )


def _view_of_clue_cell(cell: ClueCell) -> ClueCellView:
    """Return the view of a clue cell, keeping text and arrow only."""
    clue_views: list[ClueView] = []
    for clue in cell.clues:
        clue_views.append(ClueView(text=clue.text, arrow=clue.arrow))
    return ClueCellView(row=cell.row, column=cell.column, clues=tuple(clue_views))


def grid_view(grid: Grid) -> GridView:
    """Return the client view of a fresh room on `grid`: no letters, no answers.

    Cells keep the order of `grid.cells`; clues keep their order in each cell.

    Args:
        grid: An imported grid.

    Returns:
        The grid layout with every letter cell empty and no clue answer.
    """
    cell_views: list[CellView] = []
    for cell in grid.cells:
        if isinstance(cell, LetterCell):
            cell_views.append(_view_of_letter_cell(cell))
        elif isinstance(cell, ClueCell):
            cell_views.append(_view_of_clue_cell(cell))
        elif isinstance(cell, EmptyCell):
            cell_views.append(EmptyCellView(row=cell.row, column=cell.column))
        else:
            raise TypeError(f"Unknown cell kind: {type(cell).__name__}")
    return GridView(width=grid.width, height=grid.height, cells=tuple(cell_views))


# ---- Server to client ---------------------------------------------------


class PlayerView(ProtocolModel):
    """A player as the other players see them."""

    player_id: PlayerId
    nickname: Nickname
    colour: Colour
    state: PlayerState
    is_host: StrictBool
    muted: StrictBool
    selection: Selection | None


class FlagView(ProtocolModel):
    """A clue flagged by a player."""

    player_id: PlayerId
    clue: ClueRef


class LetterChanged(ProtocolModel):
    """A cell got a letter, or was erased when `letter` is None."""

    type: Literal["letter_changed"] = "letter_changed"
    seq: Seq
    row: Coordinate
    column: Coordinate
    letter: Letter | None  # None: the cell was erased
    pencil: StrictBool
    player_id: PlayerId  # who made the change (the new author)


class CellLocked(ProtocolModel):
    """A cell is locked; `revealed` True means it was revealed, with no author."""

    type: Literal["cell_locked"] = "cell_locked"
    seq: Seq
    row: Coordinate
    column: Coordinate
    letter: Letter  # the letter now locked in the cell
    revealed: StrictBool  # True: revealed, no author (spec 024 AC-1)


class PlayerJoined(ProtocolModel):
    """A player entered the room."""

    type: Literal["player_joined"] = "player_joined"
    seq: Seq
    player: PlayerView


class PlayerLeft(ProtocolModel):
    """A player left the room."""

    type: Literal["player_left"] = "player_left"
    seq: Seq
    player_id: PlayerId
    reason: LeaveReason


class PlayerStateChanged(ProtocolModel):
    """The presence of a player changed."""

    type: Literal["player_state_changed"] = "player_state_changed"
    seq: Seq
    player_id: PlayerId
    state: PlayerState


class SelectionMoved(ProtocolModel):
    """A player moved their selection. Has no seq."""

    type: Literal["selection_moved"] = "selection_moved"
    player_id: PlayerId
    selection: Selection | None


class CheckResult(ProtocolModel):
    """The result of a check."""

    type: Literal["check_result"] = "check_result"
    seq: Seq
    player_id: PlayerId
    target: CheckTarget
    correct: tuple[CellRef, ...]  # locked by the cell_locked events that follow
    wrong: tuple[CellRef, ...]  # struck through


class RevealResult(ProtocolModel):
    """The result of a reveal: the budget left. Letters come as cell_locked."""

    type: Literal["reveal_result"] = "reveal_result"
    seq: Seq
    player_id: PlayerId
    target: RevealTarget
    reveal_budget: RevealBudget  # what is left after this reveal


class VoteOpened(ProtocolModel):
    """A vote on a check or a reveal started."""

    type: Literal["vote_opened"] = "vote_opened"
    seq: Seq
    vote_id: VoteId
    player_id: PlayerId  # requester, counts as a yes
    request: Annotated[Check | Reveal, Field(discriminator="type")]
    timeout_seconds: int = Field(ge=1, strict=True)
    eligible_voters: int = Field(ge=1, strict=True)


class VoteClosed(ProtocolModel):
    """A vote ended."""

    type: Literal["vote_closed"] = "vote_closed"
    seq: Seq
    vote_id: VoteId
    outcome: VoteOutcome
    yes_votes: Count
    eligible_voters: int = Field(ge=1, strict=True)


class FlagChanged(ProtocolModel):
    """A player flagged a clue, or cleared their flag when `clue` is None."""

    type: Literal["flag_changed"] = "flag_changed"
    seq: Seq
    player_id: PlayerId
    clue: ClueRef | None  # None: the player's flag is cleared


class ChatMessage(ProtocolModel):
    """A chat message."""

    type: Literal["chat_message"] = "chat_message"
    seq: Seq
    player_id: PlayerId
    text: ChatText


class ReactionShown(ProtocolModel):
    """A reaction shown on a clue. Has no seq."""

    type: Literal["reaction"] = "reaction"
    player_id: PlayerId
    clue: ClueRef
    reaction: Reaction


class SettingsChanged(ProtocolModel):
    """The host changed the settings."""

    type: Literal["settings_changed"] = "settings_changed"
    seq: Seq
    player_id: PlayerId  # who changed them
    settings: RoomSettings
    reveal_budget: RevealBudget  # what is left now


class HostChanged(ProtocolModel):
    """The host role passed to another player."""

    type: Literal["host_changed"] = "host_changed"
    seq: Seq
    player_id: PlayerId  # the new host


class PlayerMuted(ProtocolModel):
    """A player was muted or unmuted."""

    type: Literal["player_muted"] = "player_muted"
    seq: Seq
    player_id: PlayerId
    muted: StrictBool


class GridSolved(ProtocolModel):
    """The grid is solved."""

    type: Literal["grid_solved"] = "grid_solved"
    seq: Seq
    elapsed_ms: Count


class GridFullWrong(ProtocolModel):
    """The grid is full but wrong. Carries no hint of where, spec 026 AC-2."""

    type: Literal["grid_full_wrong"] = "grid_full_wrong"
    seq: Seq


class Pong(ProtocolModel):
    """The answer to a ping, spec 017. Has no seq."""

    type: Literal["pong"] = "pong"


class ErrorMessage(ProtocolModel):
    """The server refused a message. Has no seq."""

    type: Literal["error"] = "error"
    code: ErrorCode
    message: str  # English, for logs; the UI uses `code`


class Snapshot(ProtocolModel):
    """The full state of the room, sent to a player who joins."""

    type: Literal["snapshot"] = "snapshot"
    seq: SnapshotSeq  # seq of the last event already included
    you: PlayerId  # the receiving player
    resume_token: ResumeToken  # only ever sent to that player
    grid: GridView
    players: tuple[PlayerView, ...] = Field(max_length=8)
    settings: RoomSettings
    reveal_budget: RevealBudget  # what is left
    flags: tuple[FlagView, ...]
    chat: tuple[ChatMessage, ...]  # full history, in seq order
    open_vote: VoteOpened | None
    timer_elapsed_ms: Count
    timer_running: StrictBool
    solved: StrictBool


ServerMessage = Annotated[
    Snapshot
    | LetterChanged
    | CellLocked
    | PlayerJoined
    | PlayerLeft
    | PlayerStateChanged
    | SelectionMoved
    | CheckResult
    | RevealResult
    | VoteOpened
    | VoteClosed
    | FlagChanged
    | ChatMessage
    | ReactionShown
    | SettingsChanged
    | HostChanged
    | PlayerMuted
    | GridSolved
    | GridFullWrong
    | Pong
    | ErrorMessage,
    Field(discriminator="type"),
]

_CLIENT_MESSAGE_ADAPTER: TypeAdapter[ClientMessage] = TypeAdapter(ClientMessage)
_SERVER_MESSAGE_ADAPTER: TypeAdapter[ServerMessage] = TypeAdapter(ServerMessage)


def parse_client_message(text: str | bytes) -> ClientMessage:
    """Parse one JSON message from the browser.

    Args:
        text: The JSON text of one message.

    Returns:
        The message, as an instance of its class.

    Raises:
        pydantic.ValidationError: invalid JSON, unknown or missing type,
            or any field that breaks its constraint.
    """
    return _CLIENT_MESSAGE_ADAPTER.validate_json(text)


def parse_server_message(text: str | bytes) -> ServerMessage:
    """Parse one JSON message from the server.

    Args:
        text: The JSON text of one message.

    Returns:
        The message, as an instance of its class.

    Raises:
        pydantic.ValidationError: like `parse_client_message`.
    """
    return _SERVER_MESSAGE_ADAPTER.validate_json(text)
