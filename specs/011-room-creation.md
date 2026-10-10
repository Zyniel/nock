---
id: "011"
title: Room creation and invitation
status: approved
---

# 011 - Room creation and invitation

Epic E3 Rooms and presence (US-3.1) · Release: MVP · Epic depends on: E2
The FX-01 reference grid is in `specs/_reference.md`. The stack and modeling rules
are in `specs/_architecture.md`. The messages are those of spec 039
(`nock.protocol`), the server, routes and client shell those of spec 040, the
catalogue that of spec 004.

## Goal

As a host, I want a link to send to my friends, so that they land directly on our grid.

A room is one grid shared by up to 8 players and reached by a link.

This spec also defines, once, the rooms engine that specs 012 to 018 and 037
build on: the room state model (`nock.room`), the registry that runs live rooms
(`nock.hub`), and how the server drives them. Later specs add behaviour to the
functions listed here; they do not redefine the models.

## Public interface

### Modules

| Module | Holds | Built by |
| --- | --- | --- |
| `nock/room.py` | Room state models and the pure rules applied to each event: no network, no database, no clock of its own (time is passed in as `now`) | models and `new_room`, `grid_state`: this spec; each function: the spec named below |
| `nock/hub.py` | `RoomRegistry`: live rooms, room codes, the per-room task, connections | this spec, extended by 012 to 018 |
| `nock/server.py` | FastAPI app (spec 040), `POST /api/rooms`, the wrong-code throttle; re-exports `RoomRegistry` | this spec |
| `nock/store.py` | SQLite log and snapshots | spec 018 |

`RoomRegistry` moves from `nock/server.py` to `nock/hub.py`; `nock.server`
re-exports it (`from nock.hub import RoomRegistry`), so
`from nock.server import RoomRegistry` (spec 040 tests, `tests/conftest.py`) keeps
working.

### `nock.room`: state model (all of it defined here)

```python
# src/nock/room.py
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StrictBool

from nock.grid import Grid
from nock.protocol import (
    CellLocked, ChatMessage, CheckResult, Colour, Coordinate, ErrorMessage,
    FlagChanged, GridSolved, GridFullWrong, GridView, HelpMode, HostChanged,
    Letter, LetterChanged, Nickname, PlayerId, PlayerJoined, PlayerLeft,
    PlayerMuted, PlayerState, PlayerStateChanged, PlayerView, ResumeToken,
    RevealBudget, RevealResult, RoomSettings, Selection, SelectionMoved, Seq,
    ServerMessage, SettingsChanged, Snapshot, VoteClosed, VoteOpened,
)

Clock = Callable[[], float]          # seconds since the epoch; the default is time.time
RoomCode = Annotated[str, Field(pattern=r"^[A-Z0-9]{6}$")]

MAX_PLAYERS: int = 8                                          # spec 012 AC-4
DEFAULT_REVEAL_BUDGET: RevealBudget = RevealBudget(letters=5, words=1)   # spec 024 AC-2
DEFAULT_SETTINGS: RoomSettings = RoomSettings(
    help_mode=HelpMode.FREE, reveal_budget=DEFAULT_REVEAL_BUDGET, locked=False
)

# The 16 server messages that carry a seq (spec 039, "seq" column).
SeqEvent = Annotated[
    LetterChanged | CellLocked | PlayerJoined | PlayerLeft | PlayerStateChanged
    | CheckResult | RevealResult | VoteOpened | VoteClosed | FlagChanged
    | ChatMessage | SettingsChanged | HostChanged | PlayerMuted | GridSolved
    | GridFullWrong,
    Field(discriminator="type"),
]


class RoomModel(BaseModel):
    """Base of the room models: immutable, unknown fields rejected."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class RoomConfig(RoomModel):
    """Thresholds of the room rules. Defaults are the backlog values."""

    idle_after_seconds: float = Field(default=120.0, gt=0)       # spec 013 AC-1
    host_handover_seconds: float = Field(default=60.0, gt=0)     # spec 014 AC-3
    silence_timeout_seconds: float = Field(default=6.0, gt=0)    # spec 017 AC-4
    resume_window_seconds: float = Field(default=300.0, gt=0)    # spec 017 AC-3
    max_edits_per_second: int = Field(default=20, ge=1)          # spec 037 AC-3
    snapshot_every: int = Field(default=100, ge=1)               # spec 018
    tick_seconds: float = Field(default=1.0, gt=0)               # how often the hub runs tick()


class CellState(RoomModel):
    """The room's state of one letter cell."""

    row: Coordinate
    column: Coordinate
    letter: Letter | None = None
    pencil: StrictBool = False
    author: PlayerId | None = None       # None when empty or revealed
    locked: StrictBool = False
    revealed: StrictBool = False
    wrong: StrictBool = False
    changed_seq: int = Field(default=0, ge=0, strict=True)   # seq of the last letter_changed or cell_locked on it
    changed_by: PlayerId | None = None   # who made that change; None: nobody yet, or a reveal


class UndoEntry(RoomModel):
    """A player's last edit and the cell as it was before it (spec 018 AC-3)."""

    row: Coordinate
    column: Coordinate
    seq: Seq                             # seq of that edit's letter_changed
    letter: Letter | None                # the cell before the edit
    pencil: StrictBool
    author: PlayerId | None


class PlayerRecord(RoomModel):
    """A player of the room, as the server keeps them (never sent as is)."""

    player_id: PlayerId
    resume_token: ResumeToken            # secret, spec 039 decision 5
    nickname: Nickname
    colour: Colour
    is_host: StrictBool
    muted: StrictBool = False
    state: PlayerState = PlayerState.ACTIVE
    joined_seq: Seq                      # seq of their player_joined: smaller = present longer
    last_input_at: float                 # spec 013: last message other than join and ping
    last_seen_at: float                  # spec 017: last frame of any kind
    disconnected_at: float | None = None
    selection: Selection | None = None
    recent_edits: tuple[float, ...] = () # spec 037 AC-3: times of the edits accepted in the last second
    last_edit: UndoEntry | None = None   # spec 018 AC-3


class RoomState(RoomModel):
    """The whole state of one room. Replaced, never mutated."""

    code: RoomCode
    grid: Grid                           # holds the answers: never sent to a browser
    grid_number: int | None = None       # catalogue number (spec 004); None for a bare grid
    created_at: float
    seq: int = Field(default=0, ge=0, strict=True)   # seq of the last event; 0 for a fresh room
    cells: tuple[CellState, ...]         # one per letter cell, in the order of grid.cells
    players: tuple[PlayerRecord, ...] = Field(default=(), max_length=8)  # in joined_seq order
    settings: RoomSettings = DEFAULT_SETTINGS
    reveal_budget: RevealBudget = DEFAULT_REVEAL_BUDGET  # what is left
    removed_tokens: tuple[ResumeToken, ...] = ()         # spec 014 AC-1
    solved: StrictBool = False                           # spec 026


class LogEntry(RoomModel):
    """One numbered event as written to the room's log (spec 018)."""

    at: float                            # clock time of the step that made it
    event: SeqEvent                      # exactly what the players receive
    resume_token: ResumeToken | None = None   # on player_joined only: the new player's token
    undo: StrictBool = False             # a letter_changed made by an undo (spec 018)


class Disconnect(RoomModel):
    """A player connection the hub must close after a step."""

    player_id: PlayerId
    close_code: int = Field(ge=1000, le=4999, strict=True)
    error: ErrorMessage | None = None    # sent just before closing


class Outcome(RoomModel):
    """What one step of the rules produced. See "Delivery order"."""

    state: RoomState
    entries: tuple[LogEntry, ...] = ()           # numbered events, in seq order
    reply: tuple[ServerMessage, ...] = ()        # to the sender's connection only
    to_others: tuple[SelectionMoved, ...] = ()   # to every joined connection except the sender's
    close_sender: StrictBool = False             # close the sender's socket, code 1000, after the reply
    disconnects: tuple[Disconnect, ...] = ()


def new_room(
    code: str, grid: Grid, now: float, grid_number: int | None = None
) -> RoomState:
    """Return a fresh room: seq 0, no player, every letter cell empty.

    `cells` holds one `CellState(row=..., column=...)` per letter cell of `grid`,
    in the order of `grid.cells`; `created_at` is `now`; settings and budget are
    the defaults. Raises pydantic.ValidationError when `code` breaks RoomCode.
    """


def grid_state(state: RoomState) -> GridView:
    """Return the client view of the room's grid with its current letters.

    It is `grid_view(state.grid)` (spec 039) with each letter cell's `letter`,
    `pencil`, `author`, `locked`, `revealed` and `wrong` taken from
    `state.cells`. It never holds an answer.
    """
```

Fields are added to these models only with a default, and only by a spec that
says so. Each comment names the spec that gives the field its meaning; this spec
only builds the models.

### `nock.room`: rule functions (signatures fixed here, behaviour in the owning spec)

Every function is pure: same input, same output, no I/O. `now` is the clock time
of the step. A function that refuses a message returns the unchanged state, no
entry, and one `ErrorMessage` in `reply`.

| Function | Behaviour defined by |
| --- | --- |
| `new_room(code, grid, now, grid_number=None) -> RoomState` | this spec |
| `grid_state(state) -> GridView` | this spec |
| `player_views(state) -> tuple[PlayerView, ...]` | 012 |
| `snapshot_for(state, player_id: str) -> Snapshot` | 012 |
| `normalize_nickname(text: str) -> str` | 012 |
| `join_room(state, message: Join, now: float, new_player_id: str, new_resume_token: str) -> Outcome` | 012, extended by 014 (removed, locked) and 017 (resume window) |
| `disconnect_player(state, player_id: str, now: float) -> Outcome` | 012, extended by 013 (selection) |
| `handle_message(state, player_id: str, message: ClientMessage, now: float, config: RoomConfig = RoomConfig()) -> Outcome` | 015 (edits), extended by 013, 014, 016, 017, 018, 037 |
| `tick(state, now: float, config: RoomConfig = RoomConfig()) -> Outcome` | 017 (silence, time-out), extended by 013 (idle) and 014 (host hand-over) |
| `replay(state, entry: LogEntry) -> RoomState` | 018 |
| `after_restart(state, now: float) -> Outcome` | 018 |

Until the spec that gives a client message its meaning is built,
`handle_message` returns the unchanged state and nothing else for it (spec 040
behaviour: read and ignored).

### `nock.hub`: the registry of live rooms

```python
# src/nock/hub.py
from __future__ import annotations

from nock.grid import Grid
from nock.room import Clock, RoomConfig, RoomState

ROOM_CODE_ALPHABET: str = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no 0, O, 1, I
ROOM_CODE_LENGTH: int = 6


class RoomRegistry:
    """The rooms of this process, by code, and the tasks that run them.

    A plain class, not a Pydantic model: a mutable service. Every method may be
    called from any thread.
    """

    def __init__(
        self, *, config: RoomConfig | None = None, clock: Clock | None = None
    ) -> None:
        """config None: RoomConfig(). clock None: time.time."""

    @property
    def config(self) -> RoomConfig: ...

    @property
    def clock(self) -> Clock: ...

    def register_room(self, grid: Grid, grid_number: int | None = None) -> str:
        """Create a room on `grid` with new_room(code, grid, clock(), grid_number)
        and return its code: ROOM_CODE_LENGTH characters of ROOM_CODE_ALPHABET,
        drawn with `secrets`, redrawn while the code is taken."""

    def add_room(self, state: RoomState) -> None:
        """Register a room in a given state (tests, and spec 018's loader).

        Raises:
            ValueError: a room with `state.code` already exists.
        """

    def find_room(self, code: str) -> Grid | None:
        """Return the grid of room `code`, or None when there is no such room."""

    def room_state(self, code: str) -> RoomState | None:
        """Return the latest state of room `code`, or None. Read-only: the
        returned model is the one the room task last stored."""

    def close(self) -> None:
        """Stop the room tasks and the engine thread. Idempotent. Spec 018 adds
        saving a snapshot of each live room first."""
```

`register_room(grid)` and `find_room(code)` keep the meaning they had in spec 040.

### Runtime model (binding guarantees; mechanics are the implementer's)

1. Engine thread. A registry runs its rooms on its own asyncio event loop in a
   daemon thread, started on first use. One asyncio task per live room runs on
   that loop and applies the room's inputs one at a time, in the order they
   reach its inbox. A WebSocket handler, whatever event loop it runs on, passes
   inputs to the inbox thread-safely and receives its outbound messages on its
   own loop. (This is why spec 040's tests, whose TestClient opens each socket on
   its own event loop, and the live-server thread both work.)
2. A step. For each input the task calls one function of `nock.room` with
   `now = clock()` and the current state, stores the returned state as the
   room's state (one reference assignment, so `room_state` never sees half a
   step), then delivers the outcome.
3. Delivery order of one outcome:
   1. each entry is appended to the room's log (spec 018; before that spec, kept
      in memory only);
   2. each entry's `event`, in seq order, to every connection that was joined
      before this step (the sender's included);
   3. `reply`, to the sender's connection;
   4. `to_others`, to every joined connection except the sender's;
   5. for each `Disconnect`: its `error` (if any) then a close with
      `close_code`, on that player's connection;
   6. if `close_sender`, a close with code 1000 on the sender's connection.

   A step with no sender (`tick`, `after_restart`) has an empty `reply`, and its
   `to_others` go to every joined connection. For `disconnect_player` the sender is
   the player whose connection closed.
4. Each connection has its own outbound FIFO queue and writer. Messages reach one
   connection in the order the room produced them. A slow or stalled connection
   never delays the room task or any other connection.
5. Every `config.tick_seconds` (real time), the task runs a step with
   `tick(state, clock(), config)`, once `tick` exists (spec 017).
6. When a room has no connection left, its task may stop; the room's state stays
   in the registry. A task that starts again (a new connection) runs one `tick`
   step before any input, so time-outs that fell due meanwhile apply first.

Until spec 012, the join on the socket keeps spec 040's answer (snapshot `seq` 0,
`players` empty, built from `grid_state` of the room's state); the room task has
nothing to apply yet.

### `nock.server`: changes to spec 040

```python
# src/nock/server.py (additions)
from nock.hub import RoomRegistry          # re-exported

THROTTLED_CLOSE_CODE: int = 4429           # WebSocket close code, too many wrong codes
WRONG_CODE_LIMIT: int = 10
WRONG_CODE_WINDOW_SECONDS: float = 60.0


class CreateRoomRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    grid_number: int = Field(ge=1, strict=True)     # a catalogue number (spec 004)


class CreateRoomResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str                  # matches ROOM_CODE_PATTERN
    share_url: str             # absolute: <scheme>://<host>/r/<code>
```

`create_app` keeps the signature of spec 040 plus the `catalogue` argument of
spec 004; this spec adds no argument. The throttle reads the time from
`rooms.clock`.

New HTTP route:

| Method and path | Answer |
| --- | --- |
| `POST /api/rooms`, JSON body `{"grid_number": N}` with `N` a published grid of the catalogue | 201, `CreateRoomResponse` JSON; the room is created with `rooms.register_room(entry.grid, grid_number=N)` |
| `POST /api/rooms`, `N` unknown or unpublished (`catalogue.find_published(N)` is None) | 404, `{"detail": "Not Found"}`, no room created |
| `POST /api/rooms`, body not valid for `CreateRoomRequest` (not JSON, missing key, `"2"`, `0`, extra key) | 422, FastAPI's validation body, no room created |
| `GET /api/rooms` | still 404, `{"detail": "Not Found"}` (spec 040 AC-3), not FastAPI's 405 for a path that only has `POST` |
| `PUT`, `PATCH`, `DELETE` on `/api/rooms` | 405 (FastAPI default) |

`share_url` is built from the request's base URL: `str(request.base_url)` without
its trailing `/`, then `/r/<code>`. With the TestClient it is
`http://testserver/r/<code>`.

Room WebSocket `/api/rooms/{code}/ws`, step 2 of spec 040 becomes:

1. The server accepts the connection and reads the client address
   (`websocket.client.host`, or `"unknown"` when absent).
2. If that address has at least `WRONG_CODE_LIMIT` wrong-code failures whose time
   `t` satisfies `t > now - WRONG_CODE_WINDOW_SECONDS` (`now = rooms.clock()`), the
   server closes the socket with `THROTTLED_CLOSE_CODE` and sends nothing, whatever
   the code, existing or not. This refusal is not counted as a failure.
3. Otherwise, if `rooms.find_room(code)` is None, the server records one failure
   at `now` for that address and closes with 4404 (spec 040).
4. Otherwise the socket goes on as before.

The failures are kept per app (each `create_app` call has its own), in memory.

### Client: `web/`

Room page additions (shown once `data-status="joined"`):

- `data-testid="share-panel"`, holding:
  - `data-testid="share-link"`: an `<a>` whose `href` and text are both
    `location.origin + "/r/" + code`, labelled `t("room.share.label")`;
  - `data-testid="copy-link"`: a button with the text `t("room.share.copy")`.
    Clicking it writes the link with `navigator.clipboard.writeText`; on success
    the button text becomes `t("room.share.copied")` for 2 seconds, then returns.
    If the clipboard is not available or refuses, nothing changes.
- Closing code 4429 sets `data-status="throttled"`; `room-status` shows
  `t("room.status.throttled")`. Like `not_found`, it is final.

New `fr.json` keys:

| Key | Value |
| --- | --- |
| `room.share.label` | `Lien d'invitation` |
| `room.share.copy` | `Copier le lien` |
| `room.share.copied` | `Lien copié` |
| `room.status.throttled` | `Trop de codes erronés. Réessayez dans une minute.` |

### Test harness

These apply to every spec from 011 to 018 and 037.

- WebSocket criteria use `fastapi.testclient.TestClient` on
  `create_app(rooms=registry, dist_dir=tmp_path, catalogue=...)`, opened as a
  context manager (`with TestClient(app) as client:`) when one test opens several
  sockets, so that they share one event loop. Messages are parsed with
  `parse_server_message`.
- A `FakeClock` the test-writer adds to `tests/conftest.py`: a callable object
  holding `now` (a float, starting at `1_000_000.0`) with `advance(seconds)`. A
  registry built with `RoomRegistry(clock=fake_clock, config=RoomConfig(tick_seconds=0.05))`
  lets a test pass minutes of room time in milliseconds: advance the fake clock,
  then wait for the next tick (at most 1 real second) for the expected message.
- Python criteria call `nock.room` functions directly with chosen `now` values.
- Limits built later must not break earlier tests: a WebSocket test in which one
  player may send more than 20 edits in a second uses
  `RoomConfig(max_edits_per_second=1000)` (spec 037), and a test in which a joined
  client may stay silent for more than 5 real seconds with the real clock uses
  `RoomConfig(silence_timeout_seconds=600)` (spec 017).
- Browser criteria use spec 040's `live_server` and `room_registry` fixtures, or its
  mocked socket. The test-writer adds a helper `enter_room(page, url, nickname="Ana")`
  to `tests/conftest.py`: it opens `url`, waits until the room page's
  `data-status` is `joined` or `nickname`, and when it is `nickname` (spec 012)
  fills `nickname-input` with `nickname`, submits, and waits for `joined`. Tests
  of this spec use it so they keep passing after spec 012.
- Clipboard: the browser context is created with
  `permissions=["clipboard-read", "clipboard-write"]`, and the test reads
  `page.evaluate("navigator.clipboard.readText()")`.
- Phone: `viewport={"width": 360, "height": 740}`, `has_touch=True`,
  `is_mobile=True` (as spec 006). Desktop: 1280 by 800.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-3.1.1) (HTTP; browser with live server) Creating a room gives a share link and a 6-character room code. HTTP: with a catalogue holding FX-01 as published entry 2, `POST /api/rooms` with `{"grid_number": 2}` answers 201 with a JSON body that parses to `CreateRoomResponse`, whose `code` matches `^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$` and whose `share_url` is `http://testserver/r/<code>`; then `registry.find_room(code)` equals the FX-01 grid and `registry.room_state(code).grid_number == 2`. Browser: for a room registered on FX-01, after `enter_room`, `share-link` has `href` and text `<base_url>/r/<code>`, and clicking `copy-link` puts that same text in the clipboard and shows `fr.json["room.share.copied"]` on the button.
- **AC-2** (AC-3.1.2) (browser with live server, phone and desktop contexts) The link opens the room on the grid, on phone and desktop, with no install. For a room registered on FX-01, opening its `share_url` path `/r/<code>` with `enter_room` in the phone context and, separately, in the desktop context reaches `data-status="joined"` and `data-grid="5x5"`, and the `grid` element of spec 006 is visible with 25 `cell` elements.
- **AC-3** (AC-3.1.3) (Python; WebSocket with a fake clock; browser with mocked socket) Room codes are random, not sequential. Ten wrong codes from one address within a minute are throttled. Python: 1,000 calls to `register_room` on one registry give 1,000 distinct codes, all matching the alphabet pattern of AC-1; at each of the 6 positions at least 20 different characters occur; and no code, read as a base-32 number over `ROOM_CODE_ALPHABET`, is exactly 1 more than the code returned just before it. WebSocket: with a registry holding one room `<code>` and a `FakeClock`, ten connections to `/api/rooms/ZZZZZZ/ws` each close with 4404; the eleventh connection, to `/api/rooms/<code>/ws`, closes with 4429 before any message; after `advance(60)` a connection to `<code>` is accepted and its join receives a `Snapshot`. Browser: when the mock closes the socket with 4429, the room page reaches `data-status="throttled"` and `room-status` shows `fr.json["room.status.throttled"]`.

## Edge cases and errors

- Request body (AC-1): `{"grid_number": "2"}`, `{"grid_number": 0}`, `{}`, `not json`
  and `{"grid_number": 2, "x": 1}` answer 422 and create no room (the registry's
  codes are unchanged). `{"grid_number": 4}` with entry 4 unpublished, and
  `{"grid_number": 99}` unknown, answer 404 `{"detail": "Not Found"}`.
- Answers (AC-1): the body of `POST /api/rooms` holds only `code` and `share_url`,
  never grid data.
- Method (AC-1): `GET /api/rooms` keeps answering 404 JSON as in spec 040 AC-3,
  even though the path now has a `POST` route; `POST /api/rooms/` (trailing slash)
  answers 404 with no redirect (spec 040 AC-28).
- Code collisions (AC-3): `register_room` redraws until the code is free in the
  registry (spec 018 adds: and in the store). `add_room` with a taken code raises
  `ValueError` and leaves the existing room unchanged.
- Codes the router accepts (AC-3): `ROOM_CODE_PATTERN` of spec 040 stays
  `^[A-Z0-9]{6}$`, so a mistyped code holding `0`, `O`, `1` or `I` still reaches the
  socket, closes with 4404 and counts as a wrong code. `/api/rooms/abc/ws` also
  closes with 4404 and counts.
- Window edge (AC-3): failures recorded at fake time `T`; a connection at
  `T + 59.9` is refused with 4429; at `T + 60.0` those failures no longer count.
- Throttle scope (AC-3): refused connections (4429) do not extend the window. The
  throttle applies to every code once triggered, so it cannot be used to tell
  existing codes apart. A valid code never adds a failure. `GET /r/<code>` (HTTP)
  is never counted: it always serves the app (spec 040).
- Address (AC-3): the address is the socket peer address. Behind a reverse proxy
  every player would share one address; trusting `X-Forwarded-For` is out of scope.
- Throttled browser (AC-3): `throttled` is final; the page does not reconnect
  (spec 017 lists the final states).
- Copy (AC-1): when `navigator.clipboard` is missing (plain HTTP on another host),
  the button does nothing and the link stays visible and selectable.
- Share panel before the snapshot (AC-1): absent; on `not_found` and `throttled`,
  absent.
- `room_state` (AC-1): returns the same object for two calls with no step in
  between; a room added with `add_room(state)` returns `state` until a step runs.
- `close()` (all): a second call does nothing; after `close`, `register_room`
  raises `RuntimeError`.

## Out of scope

- Matchmaking with strangers and voice chat (epic E3).
- Guest join, nickname, players and the player list: spec 012.
- Presence: spec 013.
- Host controls: spec 014.
- Starting a game from the catalogue in one tap (the button that calls
  `POST /api/rooms`): spec 010.
- Throttling room creation itself, or any HTTP route; proxies and
  `X-Forwarded-For`.
- Room expiry and deletion (spec 032); persistence across restarts (spec 018).
- Web Share API, QR codes, sending the link by e-mail.

## Work packages

None.

## Open questions

Each pick below is already written into the spec. The lead confirms or changes it.

1. Where the runtime lives. The architecture names `room.py`, `store.py` and
   `server.py`. Options: put the registry and room tasks in `server.py`, or in a
   new `nock/hub.py`. Pick: `nock/hub.py`, re-exported by `nock.server`, so the
   pure rules (`room.py`), the runtime (`hub.py`) and the HTTP layer (`server.py`)
   stay apart.
2. Event loops. Spec 040's tests open each TestClient socket on its own event loop,
   and the live server runs uvicorn in another thread, while the architecture asks
   for one asyncio task per room. Options: (a) the registry runs its own event
   loop in a daemon thread and connections hand inputs to it thread-safely; (b) a
   `threading.Lock` per room and no task; (c) require one event loop and rewrite
   spec 040's tests. Pick: (a), which keeps the one-task-per-room design and works
   with every caller.
3. Room code alphabet. Spec 040 allowed `A-Z0-9`. Pick: draw from 32 characters
   without `0`, `O`, `1`, `I` (about 10^9 codes), keep the router pattern of spec
   040 so mistyped codes still count as wrong.
4. Throttle rule. "Ten wrong codes from one address within a minute are
   throttled." Options: block only wrong codes, or every connection; fixed or
   sliding window. Pick: once an address has 10 failures in the last 60 seconds
   (sliding), every connection from it is closed with 4429 until fewer than 10
   remain; refusals do not count. The first 10 wrong codes still get 4404.
5. Room creation input. Spec 004 names grids by `number` and gives
   `Catalogue.find_published`. Pick: `POST /api/rooms` with `{"grid_number": N}`,
   201 with `code` and an absolute `share_url`; 404 for an unknown or unpublished
   grid. The lead merges `create_app` with spec 004's `catalogue` argument (spec 004
   open question 9); this spec adds no argument.
6. Who is the host. The creator gets no secret over HTTP. Pick: the first player to
   join a room becomes host (spec 012); the creator is normally first because the
   catalogue sends them to the room at once (spec 010).
7. Defining the engine here. Pick: every model of `nock.room` (with fields used by
   later specs) and every rule function signature are fixed in this spec; each
   later spec defines the behaviour of what it owns and says so. A spec that needs
   a new field adds it with a default.
8. Test clock. Pick: an injectable `clock` on `RoomRegistry` and short
   `tick_seconds` in tests, so thresholds of minutes keep their real default values
   and are reached by advancing a fake clock. Python tests pass `now` directly.
9. Grid number on the client. The snapshot (spec 039) does not carry
   `grid_number`, which spec 010 may need to write `nock.progress` for invited
   players. Pick: not added here; spec 010 decides (it may need a protocol field).
