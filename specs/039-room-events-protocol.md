---
id: "039"
title: Room events protocol
status: done
---

# 039 - Room events protocol

Build plan phase 2 (server foundation) · Release: MVP · No backlog story: this is
the message contract that the room specs 011 to 038 build on.
The FX-01 reference grid and the glossary are in `specs/_reference.md`. The
modeling rules are in `specs/_architecture.md`.

## Goal

The browser and the server talk over one WebSocket per room. This spec lists
every message that crosses it, as Pydantic models in `src/nock/protocol.py`, so
that the server specs (011 to 038) and the Svelte client share one validated
contract. The contract never gives the browser an answer letter the room has not
earned.

## Public interface

Every name below is importable from `nock.protocol`. Fields are required unless
the listing shows a default. The `type` default only helps Python construction:
`parse_client_message` and `parse_server_message` need `type` in the JSON.

### Modeling choices

- Every model inherits `ProtocolModel`, which is frozen and forbids unknown
  fields (`extra="forbid"`).
- Integers and booleans are strict (`Field(strict=True)` / `StrictBool`): JSON
  `"1"`, `1.0` or `true` is not an integer, and `1` or `"true"` is not a boolean.
  Strings are never coerced from numbers (Pydantic v2 default). Enums and tuples
  stay lax, so Python code may pass `"right"` or a list.
- Positions are `row` and `column` fields, from zero, as in spec 002. The models
  do not know the grid size; checking that a position is on the grid is server
  logic.
- A word is named by its clue: the clue cell's `row`, `column` and `clue_index`
  (0 or 1, the clue's index in `ClueCell.clues` of spec 002).
- Each message is one JSON object, written with `model_dump_json()` and read with
  `parse_client_message` / `parse_server_message`.

### Sequence numbers

- A sequence number is a strict `int`. It numbers the events of one room: the
  first room-changing event is 1 and each next one is 1 more (the numbering is
  server logic, specs 015 to 018; the models only check the range).
- Every room-changing server event has a required field `seq: Seq`, where
  `Seq` is an integer >= 1. These are the 16 types in the "seq" column of the
  server message table below.
- `Snapshot.seq` is an integer >= 0: the `seq` of the last event already
  included in the snapshot, 0 for a room where nothing has happened yet. The
  client applies only later events, in `seq` order.
- `selection_moved`, `reaction`, `pong` and `error` do not change the room: they
  have no `seq` field, so a JSON object for them that holds `seq` is rejected
  (`extra="forbid"`).
- Client messages carry no event `seq`. Cell edits carry an optional `base_seq`
  (integer >= 0): absent or `null` for a live edit, set to the last `seq` the
  client had applied when it resends an edit made offline (spec 017 AC-2 decides
  what the server does with it).
- No upper bound.

### How the snapshot carries the grid without answers

The snapshot does not contain a `nock.grid.Grid`, because `Clue.answer` holds the
solution. It contains a `GridView`, a client-facing copy of the layout:

- `LetterCellView`: position and the room's current state of the cell: `letter`
  (the letter in place, `None` when empty), `pencil`, `author` (who last wrote
  it, `None` for empty or revealed cells), `locked`, `revealed`, `wrong`
  (struck through by the last check).
- `ClueCellView`: position and `clues`, each a `ClueView` with `text` and
  `arrow` only. `ClueView` has no `answer` field and rejects one.
- `EmptyCellView`: position only.

The only letters the browser ever receives are letters players typed and letters
the room revealed (`cell_locked` with `revealed=True`, and `LetterCellView.letter`
of a revealed cell). `grid_view(grid)` builds the empty view of a fresh room from
an imported grid.

### Listing

```python
# src/nock/protocol.py
from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    BeforeValidator,   # (Note from the lead, 2026-10-15: added for ChatText (spec 022's tests).)
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
)

from nock.grid import Arrow, Grid


class ProtocolModel(BaseModel):
    """Base of every protocol model: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


# ---- Shared value types -------------------------------------------------

Coordinate = Annotated[int, Field(ge=0, strict=True)]      # row or column
Count = Annotated[int, Field(ge=0, strict=True)]
Seq = Annotated[int, Field(ge=1, strict=True)]             # room event number
SnapshotSeq = Annotated[int, Field(ge=0, strict=True)]
ClueIndex = Annotated[int, Field(ge=0, le=1, strict=True)]
VoteId = Annotated[int, Field(ge=1, strict=True)]
Colour = Annotated[int, Field(ge=0, le=7, strict=True)]   # palette index
Letter = Annotated[str, Field(min_length=1, max_length=1, pattern=r"^[A-Z]$")]
PlayerId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")]
ResumeToken = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{16,128}$")]
Nickname = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=2, max_length=20)
]


# A chat text is stripped as Python's str.strip() does, then must hold 1 to 280
# characters (AC-8). Pydantic's strip_whitespace keeps U+001C to U+001F, so it is
# not used here; this construction is one way, any with the same result will do.
# (Note from the lead, 2026-10-15: ChatText was StringConstraints(
# strip_whitespace=True, min_length=1, max_length=280); it now strips as
# str.strip() does, to agree with spec 022 AC-2's edge case (spec 022's tests).)
def _strip_text(value: object) -> object:
    """Return a str stripped as str.strip() does; any other value unchanged."""


ChatText = Annotated[
    str, Field(min_length=1, max_length=280), BeforeValidator(_strip_text)
]


class Direction(StrEnum):
    ACROSS = "across"
    DOWN = "down"


class PlayerState(StrEnum):          # spec 013 AC-1
    ACTIVE = "active"
    IDLE = "idle"
    DISCONNECTED = "disconnected"


class HelpMode(StrEnum):             # spec 025 AC-1
    FREE = "free"
    VOTE = "vote"
    NONE = "none"


class Reaction(StrEnum):             # spec 022 AC-2, a set of 5
    THUMBS_UP = "thumbs_up"
    CLAP = "clap"
    LAUGH = "laugh"
    WOW = "wow"
    THINKING = "thinking"


class LeaveReason(StrEnum):
    LEFT = "left"                    # closed the room on purpose
    REMOVED = "removed"              # removed by the host, spec 014 AC-1
    TIMED_OUT = "timed_out"          # disconnected past the spec 017 window


class VoteOutcome(StrEnum):          # spec 025 AC-2, AC-3
    PASSED = "passed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"


class ErrorCode(StrEnum):
    INVALID_MESSAGE = "invalid_message"      # failed parse_client_message
    NOT_JOINED = "not_joined"                # any message before join
    ROOM_FULL = "room_full"                  # spec 012 AC-4
    ROOM_LOCKED = "room_locked"              # spec 014 AC-2
    REMOVED = "removed"                      # spec 014 AC-1
    NOT_HOST = "not_host"                    # host action from a non-host
    NOT_A_LETTER_CELL = "not_a_letter_cell"  # spec 037 AC-2
    CELL_LOCKED = "cell_locked"              # spec 016 AC-3
    HELP_DISABLED = "help_disabled"          # help mode none, spec 025 AC-4
    BUDGET_EXHAUSTED = "budget_exhausted"    # spec 024 AC-3
    VOTE_IN_PROGRESS = "vote_in_progress"
    NO_OPEN_VOTE = "no_open_vote"
    MUTED = "muted"                          # spec 022 AC-4
    RATE_LIMITED = "rate_limited"            # spec 037 AC-3
    NOTHING_TO_UNDO = "nothing_to_undo"      # spec 018 AC-3
    GRID_SOLVED = "grid_solved"              # input locked, spec 026 AC-1
    INVALID_NICKNAME = "invalid_nickname"    # refused nickname, spec 012 join step 5
    INVALID_TARGET = "invalid_target"        # host action on a bad player, spec 014
    STALE_EDIT = "stale_edit"                # offline edit on a changed cell, spec 017 AC-2


class CellRef(ProtocolModel):
    row: Coordinate
    column: Coordinate


class ClueRef(ProtocolModel):
    """A word, named by its clue: clue cell position and index in that cell."""

    row: Coordinate
    column: Coordinate
    clue_index: ClueIndex


class Selection(ProtocolModel):
    row: Coordinate
    column: Coordinate
    direction: Direction


class CellTarget(ProtocolModel):
    scope: Literal["letter"] = "letter"
    row: Coordinate
    column: Coordinate


class WordTarget(ProtocolModel):
    scope: Literal["word"] = "word"
    row: Coordinate          # clue cell
    column: Coordinate
    clue_index: ClueIndex


class GridTarget(ProtocolModel):
    scope: Literal["grid"] = "grid"


CheckTarget = Annotated[
    CellTarget | WordTarget | GridTarget, Field(discriminator="scope")
]
RevealTarget = Annotated[CellTarget | WordTarget, Field(discriminator="scope")]


class RevealBudget(ProtocolModel):    # spec 024 AC-2, default 5 letters, 1 word
    letters: Count
    words: Count


class RoomSettings(ProtocolModel):
    help_mode: HelpMode
    reveal_budget: RevealBudget       # the allowance the host set
    locked: StrictBool                # spec 014 AC-2


# ---- Client to server ---------------------------------------------------

class Join(ProtocolModel):
    type: Literal["join"] = "join"
    nickname: Nickname
    resume_token: ResumeToken | None = None   # from an earlier snapshot


class SelectCell(ProtocolModel):
    type: Literal["select_cell"] = "select_cell"
    row: Coordinate
    column: Coordinate
    direction: Direction


class EditLetter(ProtocolModel):
    type: Literal["edit_letter"] = "edit_letter"
    row: Coordinate
    column: Coordinate
    letter: Letter
    base_seq: SnapshotSeq | None = None


class Erase(ProtocolModel):
    type: Literal["erase"] = "erase"
    row: Coordinate
    column: Coordinate
    base_seq: SnapshotSeq | None = None


class PencilEdit(ProtocolModel):
    type: Literal["pencil_edit"] = "pencil_edit"
    row: Coordinate
    column: Coordinate
    letter: Letter
    base_seq: SnapshotSeq | None = None


class ConfirmPencil(ProtocolModel):
    type: Literal["confirm_pencil"] = "confirm_pencil"
    row: Coordinate
    column: Coordinate
    base_seq: SnapshotSeq | None = None


class Check(ProtocolModel):
    type: Literal["check"] = "check"
    target: CheckTarget


class Reveal(ProtocolModel):
    type: Literal["reveal"] = "reveal"
    target: RevealTarget


class Vote(ProtocolModel):
    type: Literal["vote"] = "vote"
    vote_id: VoteId
    yes: StrictBool


class Flag(ProtocolModel):
    type: Literal["flag"] = "flag"
    clue: ClueRef | None              # None removes my flag


class Chat(ProtocolModel):
    type: Literal["chat"] = "chat"
    text: ChatText


class React(ProtocolModel):
    type: Literal["react"] = "react"
    clue: ClueRef
    reaction: Reaction


class Undo(ProtocolModel):
    type: Literal["undo"] = "undo"


class RemovePlayer(ProtocolModel):
    type: Literal["remove_player"] = "remove_player"
    player_id: PlayerId


class LockRoom(ProtocolModel):
    type: Literal["lock_room"] = "lock_room"
    locked: StrictBool                # False unlocks


class ChangeSettings(ProtocolModel):
    type: Literal["change_settings"] = "change_settings"
    help_mode: HelpMode
    reveal_budget: RevealBudget


class MutePlayer(ProtocolModel):
    type: Literal["mute_player"] = "mute_player"
    player_id: PlayerId
    muted: StrictBool


class Ping(ProtocolModel):            # heartbeat, spec 017; answered by pong
    type: Literal["ping"] = "ping"


ClientMessage = Annotated[
    Join | SelectCell | EditLetter | Erase | PencilEdit | ConfirmPencil
    | Check | Reveal | Vote | Flag | Chat | React | Undo
    | RemovePlayer | LockRoom | ChangeSettings | MutePlayer | Ping,
    Field(discriminator="type"),
]


# ---- Grid view (no answers) ---------------------------------------------

class ClueView(ProtocolModel):
    text: str = Field(min_length=1)
    arrow: Arrow


class LetterCellView(ProtocolModel):
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
    type: Literal["clue"] = "clue"
    row: Coordinate
    column: Coordinate
    clues: tuple[ClueView, ...] = Field(min_length=1, max_length=2)


class EmptyCellView(ProtocolModel):
    type: Literal["empty"] = "empty"
    row: Coordinate
    column: Coordinate


CellView = Annotated[
    LetterCellView | ClueCellView | EmptyCellView, Field(discriminator="type")
]


class GridView(ProtocolModel):
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    cells: tuple[CellView, ...]


def grid_view(grid: Grid) -> GridView:
    """Return the client view of a fresh room on `grid`: no letters, no answers.

    Cells keep the order of `grid.cells`; clues keep their order in each cell.
    """


# ---- Server to client ---------------------------------------------------

class PlayerView(ProtocolModel):
    player_id: PlayerId
    nickname: Nickname
    colour: Colour
    state: PlayerState
    is_host: StrictBool
    muted: StrictBool
    selection: Selection | None


class FlagView(ProtocolModel):
    player_id: PlayerId
    clue: ClueRef


class LetterChanged(ProtocolModel):
    type: Literal["letter_changed"] = "letter_changed"
    seq: Seq
    row: Coordinate
    column: Coordinate
    letter: Letter | None             # None: the cell was erased
    pencil: StrictBool
    player_id: PlayerId               # who made the change (the new author)


class CellLocked(ProtocolModel):
    type: Literal["cell_locked"] = "cell_locked"
    seq: Seq
    row: Coordinate
    column: Coordinate
    letter: Letter                    # the letter now locked in the cell
    revealed: StrictBool              # True: revealed, no author (spec 024 AC-1)


class PlayerJoined(ProtocolModel):
    type: Literal["player_joined"] = "player_joined"
    seq: Seq
    player: PlayerView


class PlayerLeft(ProtocolModel):
    type: Literal["player_left"] = "player_left"
    seq: Seq
    player_id: PlayerId
    reason: LeaveReason


class PlayerStateChanged(ProtocolModel):
    type: Literal["player_state_changed"] = "player_state_changed"
    seq: Seq
    player_id: PlayerId
    state: PlayerState


class SelectionMoved(ProtocolModel):  # no seq
    type: Literal["selection_moved"] = "selection_moved"
    player_id: PlayerId
    selection: Selection | None


class CheckResult(ProtocolModel):
    type: Literal["check_result"] = "check_result"
    seq: Seq
    player_id: PlayerId
    target: CheckTarget
    correct: tuple[CellRef, ...]      # locked by the cell_locked events that follow
    wrong: tuple[CellRef, ...]        # struck through


class RevealResult(ProtocolModel):
    type: Literal["reveal_result"] = "reveal_result"
    seq: Seq
    player_id: PlayerId
    target: RevealTarget
    reveal_budget: RevealBudget       # what is left after this reveal


class VoteOpened(ProtocolModel):
    type: Literal["vote_opened"] = "vote_opened"
    seq: Seq
    vote_id: VoteId
    player_id: PlayerId               # requester, counts as a yes
    request: Annotated[Check | Reveal, Field(discriminator="type")]
    timeout_seconds: int = Field(ge=1, strict=True)
    eligible_voters: int = Field(ge=1, strict=True)


class VoteClosed(ProtocolModel):
    type: Literal["vote_closed"] = "vote_closed"
    seq: Seq
    vote_id: VoteId
    outcome: VoteOutcome
    yes_votes: Count
    eligible_voters: int = Field(ge=1, strict=True)


class FlagChanged(ProtocolModel):
    type: Literal["flag_changed"] = "flag_changed"
    seq: Seq
    player_id: PlayerId
    clue: ClueRef | None              # None: the player's flag is cleared


class ChatMessage(ProtocolModel):
    type: Literal["chat_message"] = "chat_message"
    seq: Seq
    player_id: PlayerId
    text: ChatText


class ReactionShown(ProtocolModel):   # no seq
    type: Literal["reaction"] = "reaction"
    player_id: PlayerId
    clue: ClueRef
    reaction: Reaction


class SettingsChanged(ProtocolModel):
    type: Literal["settings_changed"] = "settings_changed"
    seq: Seq
    player_id: PlayerId               # who changed them
    settings: RoomSettings
    reveal_budget: RevealBudget       # what is left now


class HostChanged(ProtocolModel):
    type: Literal["host_changed"] = "host_changed"
    seq: Seq
    player_id: PlayerId               # the new host


class PlayerMuted(ProtocolModel):
    type: Literal["player_muted"] = "player_muted"
    seq: Seq
    player_id: PlayerId
    muted: StrictBool


class GridSolved(ProtocolModel):
    type: Literal["grid_solved"] = "grid_solved"
    seq: Seq
    elapsed_ms: Count


class GridFullWrong(ProtocolModel):   # carries no hint of where, spec 026 AC-2
    type: Literal["grid_full_wrong"] = "grid_full_wrong"
    seq: Seq


class Pong(ProtocolModel):            # no seq; the answer to a ping, spec 017
    type: Literal["pong"] = "pong"


class ErrorMessage(ProtocolModel):    # no seq
    type: Literal["error"] = "error"
    code: ErrorCode
    message: str                      # English, for logs; the UI uses `code`


class Snapshot(ProtocolModel):
    type: Literal["snapshot"] = "snapshot"
    seq: SnapshotSeq
    you: PlayerId                     # the receiving player
    resume_token: ResumeToken         # only ever sent to that player
    grid: GridView
    players: tuple[PlayerView, ...] = Field(max_length=8)
    settings: RoomSettings
    reveal_budget: RevealBudget       # what is left
    flags: tuple[FlagView, ...]
    chat: tuple[ChatMessage, ...]     # full history, in seq order
    open_vote: VoteOpened | None
    timer_elapsed_ms: Count
    timer_running: StrictBool
    solved: StrictBool


ServerMessage = Annotated[
    Snapshot | LetterChanged | CellLocked | PlayerJoined | PlayerLeft
    | PlayerStateChanged | SelectionMoved | CheckResult | RevealResult
    | VoteOpened | VoteClosed | FlagChanged | ChatMessage | ReactionShown
    | SettingsChanged | HostChanged | PlayerMuted | GridSolved | GridFullWrong
    | Pong | ErrorMessage,
    Field(discriminator="type"),
]


def parse_client_message(text: str | bytes) -> ClientMessage:
    """Parse one JSON message from the browser.

    Raises:
        pydantic.ValidationError: invalid JSON, unknown or missing type,
            or any field that breaks its constraint.
    """


def parse_server_message(text: str | bytes) -> ServerMessage:
    """Parse one JSON message from the server. Raises like parse_client_message."""
```

The comments name the spec that owns each meaning; none of that behaviour is
built here.

### Message tables

Client messages (18):

| `type` | Class | Request item |
| --- | --- | --- |
| `join` | `Join` | join |
| `select_cell` | `SelectCell` | select cell |
| `edit_letter` | `EditLetter` | edit letter |
| `erase` | `Erase` | erase |
| `pencil_edit` | `PencilEdit` | pencil edit |
| `confirm_pencil` | `ConfirmPencil` | confirm pencil |
| `check` | `Check` | check |
| `reveal` | `Reveal` | reveal |
| `vote` | `Vote` | vote |
| `flag` | `Flag` | flag |
| `chat` | `Chat` | chat |
| `react` | `React` | reaction |
| `undo` | `Undo` | undo |
| `remove_player` | `RemovePlayer` | host: remove player |
| `lock_room` | `LockRoom` | host: lock room |
| `change_settings` | `ChangeSettings` | host: change settings |
| `mute_player` | `MutePlayer` | host: mute (added, see decision 1) |
| `ping` | `Ping` | heartbeat (added on reopening, see decision 17) |

Server messages (21). "seq" says whether the message has a required `seq: Seq`.

| `type` | Class | seq | Request item |
| --- | --- | --- | --- |
| `snapshot` | `Snapshot` | own rule (>= 0) | snapshot with sequence number |
| `letter_changed` | `LetterChanged` | yes | letter changed |
| `cell_locked` | `CellLocked` | yes | cell locked |
| `player_joined` | `PlayerJoined` | yes | player joined |
| `player_left` | `PlayerLeft` | yes | left |
| `player_state_changed` | `PlayerStateChanged` | yes | state changed |
| `selection_moved` | `SelectionMoved` | no | selection moved |
| `check_result` | `CheckResult` | yes | check result |
| `reveal_result` | `RevealResult` | yes | reveal result |
| `vote_opened` | `VoteOpened` | yes | vote opened |
| `vote_closed` | `VoteClosed` | yes | vote closed |
| `flag_changed` | `FlagChanged` | yes | flag changed |
| `chat_message` | `ChatMessage` | yes | chat message |
| `reaction` | `ReactionShown` | no | reaction |
| `settings_changed` | `SettingsChanged` | yes | settings changed |
| `host_changed` | `HostChanged` | yes | added, see decision 1 |
| `player_muted` | `PlayerMuted` | yes | added, see decision 1 |
| `grid_solved` | `GridSolved` | yes | grid solved |
| `grid_full_wrong` | `GridFullWrong` | yes | grid full but wrong |
| `pong` | `Pong` | no | heartbeat answer (added on reopening, see decision 17) |
| `error` | `ErrorMessage` | no | error |

### Wire examples

Each line is the exact JSON text of one message (the test-writer may copy them).
They are used by AC-1 to AC-3, AC-12 and AC-20. `PLAYER_P2` stands for
`{"player_id": "p2", "nickname": "Bruno", "colour": 1, "state": "active", "is_host": false, "muted": false, "selection": null}`
and `SETTINGS` for
`{"help_mode": "free", "reveal_budget": {"letters": 5, "words": 1}, "locked": false}`.

Client:

```json
{"type": "join", "nickname": "Ana", "resume_token": null}
{"type": "select_cell", "row": 1, "column": 0, "direction": "across"}
{"type": "edit_letter", "row": 1, "column": 0, "letter": "T", "base_seq": null}
{"type": "erase", "row": 1, "column": 0, "base_seq": 7}
{"type": "pencil_edit", "row": 1, "column": 1, "letter": "A", "base_seq": null}
{"type": "confirm_pencil", "row": 1, "column": 1, "base_seq": null}
{"type": "check", "target": {"scope": "word", "row": 0, "column": 2, "clue_index": 0}}
{"type": "reveal", "target": {"scope": "letter", "row": 4, "column": 4}}
{"type": "vote", "vote_id": 3, "yes": true}
{"type": "flag", "clue": {"row": 0, "column": 0, "clue_index": 1}}
{"type": "chat", "text": "Qui a une idée pour le 3 ?"}
{"type": "react", "clue": {"row": 2, "column": 0, "clue_index": 0}, "reaction": "clap"}
{"type": "undo"}
{"type": "remove_player", "player_id": "p2"}
{"type": "lock_room", "locked": true}
{"type": "change_settings", "help_mode": "vote", "reveal_budget": {"letters": 5, "words": 1}}
{"type": "mute_player", "player_id": "p2", "muted": true}
{"type": "ping"}
```

Server (with `PLAYER_P2` and `SETTINGS` substituted):

```json
{"type": "snapshot", "seq": 0, "you": "p1", "resume_token": "r7Kq2mXo9vB4tY1zW8nP", "grid": {"width": 2, "height": 1, "cells": [{"type": "clue", "row": 0, "column": 0, "clues": [{"text": "Note", "arrow": "right"}]}, {"type": "letter", "row": 0, "column": 1, "letter": null, "pencil": false, "author": null, "locked": false, "revealed": false, "wrong": false}]}, "players": [PLAYER_P2], "settings": SETTINGS, "reveal_budget": {"letters": 5, "words": 1}, "flags": [], "chat": [], "open_vote": null, "timer_elapsed_ms": 0, "timer_running": false, "solved": false}
{"type": "letter_changed", "seq": 12, "row": 1, "column": 0, "letter": "T", "pencil": false, "player_id": "p1"}
{"type": "cell_locked", "seq": 13, "row": 1, "column": 0, "letter": "T", "revealed": false}
{"type": "player_joined", "seq": 2, "player": PLAYER_P2}
{"type": "player_left", "seq": 40, "player_id": "p2", "reason": "removed"}
{"type": "player_state_changed", "seq": 41, "player_id": "p1", "state": "idle"}
{"type": "selection_moved", "player_id": "p1", "selection": {"row": 1, "column": 0, "direction": "across"}}
{"type": "check_result", "seq": 20, "player_id": "p1", "target": {"scope": "grid"}, "correct": [{"row": 1, "column": 0}], "wrong": [{"row": 1, "column": 1}]}
{"type": "reveal_result", "seq": 22, "player_id": "p1", "target": {"scope": "letter", "row": 4, "column": 4}, "reveal_budget": {"letters": 4, "words": 1}}
{"type": "vote_opened", "seq": 30, "vote_id": 3, "player_id": "p1", "request": {"type": "reveal", "target": {"scope": "word", "row": 0, "column": 4, "clue_index": 0}}, "timeout_seconds": 20, "eligible_voters": 3}
{"type": "vote_closed", "seq": 31, "vote_id": 3, "outcome": "passed", "yes_votes": 2, "eligible_voters": 3}
{"type": "flag_changed", "seq": 15, "player_id": "p2", "clue": {"row": 0, "column": 3, "clue_index": 0}}
{"type": "chat_message", "seq": 16, "player_id": "p2", "text": "IDES, je crois"}
{"type": "reaction", "player_id": "p2", "clue": {"row": 0, "column": 3, "clue_index": 0}, "reaction": "wow"}
{"type": "settings_changed", "seq": 5, "player_id": "p1", "settings": SETTINGS, "reveal_budget": {"letters": 5, "words": 1}}
{"type": "host_changed", "seq": 50, "player_id": "p2"}
{"type": "player_muted", "seq": 51, "player_id": "p2", "muted": true}
{"type": "grid_solved", "seq": 60, "elapsed_ms": 754000}
{"type": "grid_full_wrong", "seq": 59}
{"type": "pong"}
{"type": "error", "code": "cell_locked", "message": "cell (1, 0) is locked"}
```

## Acceptance criteria

- **AC-1** Given each of the 18 client wire examples, when it is parsed with `parse_client_message`, then the result is an instance of the class in the client table, and `parse_client_message(message.model_dump_json()) == message`.
- **AC-2** Given each of the 21 server wire examples, when it is parsed with `parse_server_message`, then the result is an instance of the class in the server table, and `parse_server_message(message.model_dump_json()) == message`. The same holds for a `Snapshot` whose `grid` is `grid_view(fx01_grid)` with the letter cell (1, 0) set to `letter="T"`, `author="p1"`.
- **AC-3** Given a wire example, when it is parsed, then its fields carry the values written in the JSON. Examples: the `edit_letter` example gives `EditLetter(row=1, column=0, letter="T", base_seq=None)`; the `vote_opened` example gives `request == Reveal(target=WordTarget(row=0, column=4, clue_index=0))`; the `check_result` example gives `target == GridTarget()`.
- **AC-4** Given a JSON object whose `type` is unknown, missing, or belongs to the other direction, when it is parsed, then `pydantic.ValidationError` is raised. Examples: `{"type": "teleport", "row": 1, "column": 0}` and `{"row": 1, "column": 0, "letter": "T"}` with either parser; the `snapshot` example with `parse_client_message`; the `join` example with `parse_server_message`.
- **AC-5** Given a message with a malformed field, when it is parsed, then `pydantic.ValidationError` is raised. Each line below is one case, all with `parse_client_message` unless marked: the text `not json`; `edit_letter` without `column`; `edit_letter` with `"row": -1`; with `"row": "1"`; with `"row": 1.0`; with `"row": true`; `vote` with `"yes": 1`; `vote` with `"vote_id": 0`; `undo` with an extra `"player_id": "p1"`; `flag` with `"clue_index": 2`; `remove_player` with `"player_id": ""` and with `"player_id": "p 2"`; `change_settings` with `"letters": -1`; `check` with a target that has no `scope`; and (`parse_server_message`) `player_joined` with `"colour": 8`.
- **AC-6** Given an `edit_letter` or `pencil_edit` message, when its `letter` is exactly one character from `A` to `Z`, then it parses; when it is `"a"`, `"É"`, `"AB"`, `""`, `"1"`, `" "` or `null`, then `pydantic.ValidationError` is raised. Each of `"A"` and `"Z"` parses.
- **AC-7** Given a `join` message, when its nickname has 2 to 20 characters after leading and trailing whitespace are removed, then it parses and `nickname` holds the trimmed text (`"  Ana  "` gives `"Ana"`; 20 times `x` parses); when it has fewer than 2 or more than 20 after trimming, then `pydantic.ValidationError` is raised (`"A"`, `"  A  "`, `""`, 21 times `x`).
- **AC-8** Given a `chat` message, when its text has 1 to 280 characters after trimming, then it parses with the trimmed text (280 times `a` parses, `" salut "` gives `"salut"`); when it is empty, whitespace only, or 281 characters after trimming, then `pydantic.ValidationError` is raised. Trimming is Python's `str.strip()`, and whitespace is every character it removes (those for which `str.isspace()` is true, U+001C to U+001F included): `"\u001fsalut\u001c"` gives `"salut"`, and `"\u001c\u001d"` raises `pydantic.ValidationError`. (Note from the lead, 2026-10-15: added; pydantic's whitespace stripping kept U+001C to U+001F, so `"\u001c\u001d"` parsed as a valid chat, against spec 022 AC-2's edge case (spec 022's tests).)
- **AC-9** Given an enumerated field, when it holds one of its listed values, then the message parses; when it holds any other string, then `pydantic.ValidationError` is raised. Listed values: `direction` across, down; `state` active, idle, disconnected; `help_mode` free, vote, none; `reaction` thumbs_up, clap, laugh, wow, thinking; `reason` left, removed, timed_out; `outcome` passed, rejected, timed_out; `scope` letter, word, grid; `code` the 19 values of `ErrorCode` (the 16 of the first version plus `invalid_nickname`, `invalid_target`, `stale_edit`). Rejected examples: `"help_mode": "auto"`, `"help_mode": "FREE"`, `"reaction": "heart"`, `"direction": "diagonal"`.
- **AC-10** Given a `reveal` message, when its target has `"scope": "grid"`, then `pydantic.ValidationError` is raised; the same target in a `check` message parses to `GridTarget()`.
- **AC-11** Given each of the 16 server types marked "yes" in the seq column, when its wire example is parsed with `seq` removed, or with `"seq": 0`, or with `"seq": -1`, then `pydantic.ValidationError` is raised; with `"seq": 1` it parses and `message.seq == 1`.
- **AC-12** Given the `selection_moved`, `reaction`, `pong` or `error` wire example with an added `"seq": 5`, when it is parsed, then `pydantic.ValidationError` is raised.
- **AC-13** Given the `snapshot` wire example, when `seq` is 0 or 42, then it parses with that `seq`; when `seq` is -1 or missing, then `pydantic.ValidationError` is raised.
- **AC-14** Given `Snapshot.model_json_schema()`, when every `properties` mapping in it is walked (top level and all `$defs`), then no property is named `answer` or `solution`.
- **AC-15** Given the clue cell JSON `{"type": "clue", "row": 0, "column": 0, "clues": [{"text": "Note", "arrow": "right", "answer": "A"}]}` inside a snapshot grid, when the snapshot is parsed, then `pydantic.ValidationError` is raised; `ClueView.model_validate({"text": "Note", "arrow": "right", "answer": "A"})` also raises it.
- **AC-16** Given the FX-01 grid (`tests/fixtures/fx01.json`, spec 002), when `grid_view(grid)` is called, then the view has width 5, height 5 and 25 cells with the same `type`, `row` and `column` in the same order as `grid.cells`; the clue cell at (0, 0) holds `ClueView(text="Passoire fine", arrow=Arrow.DOWN_THEN_RIGHT)` then `ClueView(text="De la marine", arrow=Arrow.RIGHT_THEN_DOWN)`; and each of the 18 letter cells has `letter=None`, `pencil=False`, `author=None`, `locked=False`, `revealed=False`, `wrong=False`.
- **AC-17** Given `grid_view(fx01_grid).model_dump_json()`, when the text is searched, then it contains none of `"answer"`, `TAMIS`, `NAVAL`, `MIME`, `IDES`, `SENT`, `VIDE`, `AMEN`, `LEST`.
- **AC-18** Given the `snapshot` wire example, when `players` holds 8 players (ids `p1` to `p8`), then it parses; when it holds 9, then `pydantic.ValidationError` is raised.
- **AC-19** Given a parsed message, when a field is assigned (for example `message.row = 2` on the `edit_letter` example), then `pydantic.ValidationError` is raised and the message is unchanged.
- **AC-20** Given the heartbeat messages, when `{"type": "ping"}` is parsed with `parse_client_message`, then the result equals `Ping()`, and when `{"type": "pong"}` is parsed with `parse_server_message`, then it equals `Pong()`; `{"type": "ping"}` with `parse_server_message`, `{"type": "pong"}` with `parse_client_message`, and `{"type": "ping", "seq": 1}`, `{"type": "ping", "id": 1}` with `parse_client_message` each raise `pydantic.ValidationError`.
- **AC-21** Given `ErrorCode`, when its members are listed, then there are exactly 19, and `ErrorCode("invalid_nickname") is ErrorCode.INVALID_NICKNAME`, `ErrorCode("invalid_target") is ErrorCode.INVALID_TARGET` and `ErrorCode("stale_edit") is ErrorCode.STALE_EDIT`; the `error` wire example with `"code"` set to each of these three values parses to an `ErrorMessage` with that code.

## Edge cases and errors

- Letter (AC-6): the same `Letter` type is used by `LetterChanged.letter`,
  `CellLocked.letter` and `LetterCellView.letter`, so `"a"` is rejected there too.
  The models do not uppercase anything: the client sends uppercase.
- Trailing newline (AC-6): `"A\n"` is two characters and is rejected.
- Characters (AC-7, AC-8) are Python `str` characters (code points). An emoji
  made of several code points counts as several.
- Chat content (AC-8): `"<b>salut</b>"` parses and round-trips unchanged.
  Escaping is the client's job (spec 037 AC-4).
- Chat trimming (AC-8): the separators U+001C to U+001F are invisible and never
  meant as chat text, so a chat text is stripped of them as of any other
  whitespace, as Python's `str.strip()` does; spec 022 AC-2's edge case relies on
  it. `ChatMessage.text` has the same type, so the rule holds in `chat_message`
  and `Snapshot.chat` too. (Note from the lead, 2026-10-15: added with the
  refined `ChatText` (spec 022's tests).)
- Nickname characters (AC-7): this spec checks length only; which characters are
  allowed belongs to spec 012.
- `base_seq` (AC-5): `-1` is rejected, `0` and `null` are accepted, and it may be
  omitted (defaults to `None`).
- `join` without `resume_token` (AC-1): parses with `resume_token=None`.
- `flag` with `"clue": null` (AC-1, AC-3): parses with `clue=None`.
- Erased cell (AC-2): `letter_changed` with `"letter": null` parses.
- Cross-field rules are not checked by the models: a `letter_changed` with
  `letter` null and `pencil` true, a snapshot whose `you` is not in `players`, a
  `GridView` with missing or duplicate positions, duplicate colours, or a
  position outside the grid all parse. Those are server guarantees owned by the
  room specs.
- Sequence numbers have no upper bound (AC-11, AC-13).
- An empty `reveal_budget` (`{"letters": 0, "words": 0}`) is valid.

## Out of scope

- The server logic behind each message: who may send what, in which order
  events are emitted, how `seq` values are assigned and logged, timers, votes,
  checks, reveals, completion, presence, throttling. These belong to specs 011
  to 038.
- The WebSocket endpoint and the FastAPI app (`nock/server.py`), room creation
  over HTTP and the room code (spec 011): the room is chosen by the WebSocket URL,
  so no message carries a room code.
- The TypeScript types of the client.
- Race and team modes (specs 030, 031): no message for opponents' progress or
  ranks.
- Catch-up after an absence (spec 034), the activity feed history and the
  end-of-game recap (spec 028): the snapshot carries no feed history and no
  recap.
- Accounts and "my rooms" (specs 032, 033).
- A message to leave the room on purpose: closing the socket is leaving.
- When a client pings, when the server answers `pong` (also before the join),
  and what silence means: spec 017.
- Client message ids and acknowledgements: a client recognises its own edit in
  the `letter_changed` event by cell and `player_id`.

## Work packages

None.

## Decisions

Approved by the human on 2026-10-10, with the pick of each item kept as written
(item 4 confirmed: strict). Each one is already part of the interface above.

1. Messages added beyond the request. Spec 014 AC-3 (host hand-over) and spec 022
   AC-4 (host mutes a player's chat) need messages the request did not list.
   Options: add them now, or leave them to those specs. Pick: add `host_changed`,
   `mute_player` and `player_muted` now, and a `muted` flag on `PlayerView`.
2. Which server messages have no `seq`. Options: every server message has one,
   or only room-changing ones. Pick: `selection_moved`, `reaction` (shown for 3
   seconds, spec 022 AC-2) and `error` have none; presence states
   (`player_state_changed`) and chat do have one, since the snapshot holds them.
   `pong` was added to the messages without `seq` by decision 17.
3. Lowercase letters. Options: reject `"a"`, or accept and uppercase it. Pick:
   reject; the client uppercases before sending.
4. Strictness. Options: Pydantic's default lax parsing, or strict integers and
   booleans plus `extra="forbid"`. Pick: strict and forbid, so that a malformed
   field is always an error (spec 037 integrity). Cost: a future field added by
   the server breaks an older parser.
5. Identity and reconnection (specs 017 AC-3, 014 AC-1, 038 AC-1). Options: the
   public `player_id` doubles as the resume key, or a separate secret token.
   Pick: a secret `resume_token` (16 to 128 characters of `A-Za-z0-9_-`) sent only
   in that player's snapshot and returned in `join`; `player_id` is public,
   1 to 64 characters of `A-Za-z0-9_-`. `join` still requires a nickname, which
   the server ignores on a successful resume.
6. Player colour. Options: a palette index or a hex colour. Pick: index 0 to 7
   (8 players, spec 012 AC-2); the client maps indexes to colours.
7. Nickname. The protocol checks 2 to 20 characters after trimming; the allowed
   characters are left to spec 012. `PlayerView.nickname` uses the same type, so
   the duplicate suffix of spec 012 AC-2 must keep a name within 20 characters.
   Pick: as written.
8. Chat length. 280 counted as code points after trimming, whitespace-only
   rejected. Pick: as written.
9. The five reactions (spec 022 AC-2 gives only the count). Pick: `thumbs_up`,
   `clap`, `laugh`, `wow`, `thinking`; the client maps each to an emoji.
10. How checks and reveals reach the grid. Options: the result events carry the
    cell changes, or the changes are separate events. Pick: separate.
    `check_result` lists correct and wrong cells for the feed; each newly locked
    cell then comes as a `cell_locked` event. A revealed letter is sent only in
    `cell_locked` (`revealed=True`); `reveal_result` carries the remaining budget.
11. Room lock. Options: a dedicated `room_locked` event, or a `locked` flag in
    the settings. Pick: `RoomSettings.locked`, announced by `settings_changed`;
    `lock_room` carries `locked` so the host can also unlock.
12. Snapshot contents. Pick: includes other players' selections, the flags, the
    full chat history, an open vote, the timer and the remaining reveal budget;
    excludes the activity feed history (spec 034).
13. Offline edits (spec 017 AC-2). Options: no field, or an optional `base_seq`
    on cell edits. Pick: optional `base_seq`, `null` for live edits, so that the
    last-received-wins rule of spec 016 still applies to live typing.
14. Error codes and leave reasons. Pick: the 16 `ErrorCode` values and the 3
    `LeaveReason` values in the listing; specs 011 to 038 may add values. (Three
    values were added on reopening, decisions 18 to 20: 19 in all.)
15. `grid_view` lives in `nock.protocol`. Options: here, or in `nock/room.py`
    later. Pick: here, since it defines what a client may see of a grid.
16. Clearing a flag. Spec 021 says a flag clears when its word is filled and a new
    flag replaces the old one, but not whether a player can remove it by hand.
    Pick: `flag` with `"clue": null` removes the sender's flag.

Added when the spec was reopened, approved by the human on 2026-10-10 (status
back to `approved` for this change). Each one is part of the spec above.

17. Heartbeat (spec 017 decision 1). A browser cannot see WebSocket ping frames,
    so spec 017 needs an application heartbeat. Decision: a client message `ping`
    (`Ping`) and a server message `pong` (`Pong`), each with no field but `type`.
    `pong` has no `seq`, like `selection_moved`: it does not change the room and
    is never logged. Client messages carry no `seq`, so `ping` has none either.
    Wire examples added; AC-1, AC-2 and AC-12 counts and lists updated; AC-20
    added.
18. `invalid_nickname` (spec 012 decision 1). Decision: `ErrorCode.INVALID_NICKNAME`,
    sent when a join's nickname passes the protocol length check but breaks spec
    012's character rules.
19. `invalid_target` (spec 014 decision 1). Decision: `ErrorCode.INVALID_TARGET`,
    sent when the host removes or mutes a player who is not in the room, or
    removes themself.
20. `stale_edit` (spec 017 decision 2). Decision: `ErrorCode.STALE_EDIT`, sent
    when an offline edit (`base_seq` set) targets a cell another player changed
    since.
21. Counts. With decisions 17 to 20: 18 client messages, 21 server messages, 16
    server messages with `seq` (unchanged), 19 `ErrorCode` values. AC-9 lists the
    19 codes; AC-21 checks the three new ones.

## Open questions

None.
