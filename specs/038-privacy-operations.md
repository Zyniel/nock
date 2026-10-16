---
id: "038"
title: Privacy and operations
status: approved
---

# 038 - Privacy and operations

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

(Note from the lead, 2026-10-15: folded in. The answers are decisions 9 and 10, and
"Open questions" is empty. Spec 036 is refined by the lead before this spec's tests
are written.)

(Note from the lead, 2026-10-16: refined for the human's rule that nicknames are
stored in capitals (spec 012 decision 12; spec 039's "Nicknames in capitals").
Changed: AC-1 and AC-4, whose searches of the database files now look for the
nicknames as stored. This spec has no tests yet (human's rule of 2026-10-16:
nicknames in capitals).)

(Note from the lead, 2026-10-16: checked, before this spec's tests are written,
against the code that is now built for specs 027, 028, 032 and 036 and for the
nickname rule. Spec 036 is refined as decision 9 asks, with dated notes there.
Changed here, each with a dated note: the first row of "What the server keeps"
lists the fields that `PlayerRecord` holds; the dashboard and the replay read the
store as `rooms.store` (spec 032); "Operator access" says that rules 2 and 3 are
spec 011's throttle as spec 032 left it, in an instance of its own; a `RoomEdit`'s
nickname is that of the latest `player_joined` of its player before the edit, in
capitals, since a player seated back (spec 032) has a second `player_joined` (also
in the edge case "Edits of a removed or timed-out player"); a drop of
`disconnection_rate` ends at the player's `player_left`, since a seat back keeps
the player id; `median_solving_ms` names spec 027's timer; the ops page shows a
nickname through spec 040's `displayNickname`; the live server of "Test harness"
uses `server_config`. Criteria: AC-4's WebSocket part names the strings it searches
for, AC-8's nicknames are `ANA` and `BOB`, from the `player_joined` entries, and
AC-9 says that its `Ana` is how `displayNickname` shows `ANA`. This spec has no
tests yet (preparation of spec 038).)

(Note from the lead, 2026-10-16: decided after the spec-writer's report, each with
a dated note. The ops API's throttle is a second instance of spec 011's, with spec
011's `WRONG_CODE_LIMIT` and `WRONG_CODE_WINDOW_SECONDS`, so this spec's
`WRONG_TOKEN_LIMIT` and `WRONG_TOKEN_WINDOW_SECONDS` are gone (rule 2).
`RoomStore.codes_created_since` returns `(code, created_at)` pairs in no particular
order, and `RoomStore.created_at` is gone ("`nock.store`", the dashboard's reads).
While the operator pages are off, the ops paths answer exactly as an unknown path
does, with no `Cache-Control` header; `no-store` applies while they are on (rules 1
and 4). The three choices of the note above are confirmed: the latest
`player_joined` before an edit, a drop that ends at `player_left`, and the strings
of AC-4's WebSocket part. Criteria: AC-6 changed, for the store's pairs, which it
checks in Python, and for the answers while the pages are off. This spec has no
tests yet (preparation of spec 038).)

Epic E10 Quality bar (US-10.4) · Release: MVP · Epic depends on: All
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine and its
harness are defined in spec 011; guests and the stored identity in spec 012; the
store, its log and the simulated restart in spec 018; the production entry point
`python -m nock` and `server_config` in spec 036; room expiry, `past_players` and
the expiry sweep in spec 032; chat in spec 022. The messages are those of spec 039.
This spec is built after spec 032.

## Goal

As the product owner, I want minimal data and clear signals, so that we stay compliant and can diagnose a bad game.

These criteria apply to every story above and belong in each agent's definition of done.

## Public interface

### What the server keeps, and for how long

| Where | What | How long |
| --- | --- | --- |
| SQLite `NOCK_DATABASE`, rooms (spec 018) | per room: its code, creation and last edit times (spec 032); snapshots of `RoomState`: the grid with its answers, the cells (letters, authors, locks), the players (`PlayerRecord`: player id, resume token, nickname, colour, host and mute flags, presence state, the seq of their join, the times of their last input, frame and disconnection, selection, the times of their recent edits, chat messages and reactions, last edit, clue flag), the past players (`PastPlayer`: player id, resume token, nickname, colour, mute flag), the removed tokens, the settings and what later specs add | until the room expires, 30 days after its last edit (spec 032 AC-1); then deleted at the next sweep (within an hour) or at once by any lookup |
| SQLite, log of each room (spec 018) | every numbered event exactly as the players received it (letters, checks, reveals, votes, flags, chat texts, joins with the player's view, presence, settings, completion), each with its time `at`, plus the private fields `resume_token` (on a join), `undo` and `relay_ms` (this spec) | the same: deleted with the room |
| Process memory | live rooms; the wrong room codes of each client address (spec 011) and the wrong operator tokens of each address (this spec), for 60 seconds | until the window passes, or the process stops |
| Process logs (stdout, stderr) | warnings and errors of the server and of the app, with room codes and error descriptions | the operator's choice; they hold no client address, no resume token, no operator token and no chat text |
| The player's device | `localStorage` (specs 004, 010, 012, 032 to 034, 029); the ops page's token in `sessionStorage` (this spec) | until the player clears the site's data, or the tab is closed for `sessionStorage` |
| Accounts (spec 033) | defined there | defined there |
| SQLite, history of each account (spec 029) | one record per finished room of the account: its code, grid number, width and height, the time it was solved, the time it took, and the team-mates' nicknames, guests included, with their player ids | until the account is deleted (spec 033), also after the room itself is deleted; when a team-mate's own account is deleted, their nickname becomes `--` (spec 033's `FORMER_PLAYER_NICKNAME`), shown as `Ancien joueur` (spec 029 AC-6) |

(Note from the lead, 2026-10-15: the row "history of each account" was added after
spec 029's decision 6, approved by the human on 2026-10-14: an account's history
keeps the team-mates' nicknames after the room is gone. Without it, this spec said
that a deleted room leaves no byte behind, which spec 029 contradicts.)

(Note from the lead, 2026-10-16: in the first row, the fields of `PastPlayer` gained
"mute flag", after spec 032's decision 13: a past player keeps the mute of their
record, so that a seat back restores it. The list used to read "player id, resume
token, nickname, colour". The flag is game state, kept and deleted with the room,
like every field of `PastPlayer` other than the nickname and the two identifiers.
No criterion changes.)

(Note from the lead, 2026-10-16: in the first row, the fields of `PlayerRecord`
gained the seq of their join (`joined_seq`, spec 011), the times of their recent
chat messages and reactions (`recent_chat` and `recent_reactions`, spec 022) and
their clue flag (`flag`, spec 021), which the code holds. The list read "presence
state and the times of their last input, frame and disconnection, selection,
recent edit times, last edit". These fields are game state, kept and deleted with
the room. No criterion changes (preparation of spec 038).)

- Personal data about a guest is their nickname and two random identifiers, the
  player id and the resume token (AC-1). Every other field of `PlayerRecord` and
  `PastPlayer` is the state of the game in that room, kept and deleted with the room.
  The server stores no client address, no user agent, no language, no cookie value
  and no device identifier.
  A guest's nickname and player id can also stay in the history record of an
  account that played with them (spec 029), until that account is deleted. (Note
  from the lead, 2026-10-15: added after spec 029's decision 6.)
- Deletion: `RoomStore` runs with SQLite's `PRAGMA secure_delete = ON`, so deleted
  rows are overwritten with zeros, and `delete_room` (spec 032) ends with
  `PRAGMA wal_checkpoint(TRUNCATE)` on a file database, so no copy of the room stays
  in the write-ahead log. Once a room is deleted, no byte of its data remains in the
  database files (AC-4), except the history records that accounts keep of it when
  it was solved (spec 029, the row "history of each account" above). (Note from the
  lead, 2026-10-15: the exception was added after spec 029's decision 6.)
  Backups are outside this spec.
- Cookies: no route sets a cookie for a guest, and the client writes none (AC-2).
  Spec 033 adds one session cookie, for a signed-in account only. Everything the
  client keeps is in `localStorage` and `sessionStorage`, for the game itself.
- Third parties: no request of the page leaves the app's origin (spec 005 AC-4 and
  AC-5 already forbid the code that would).

### Logs (changes to spec 036)

```python
# src/nock/server.py (change to spec 036)
def server_config(
    app: FastAPI, host: str = "127.0.0.1", port: int = 8000, log_level: str = "warning"
) -> uvicorn.Config:
    """Return the uvicorn configuration of the server: `ws_max_size` is
    WS_MAX_SIZE_BYTES, `access_log` is False, `log_level` defaults to "warning";
    every other option is uvicorn's default."""
```

- uvicorn writes the client's address in its access log and, at the `info` level, in
  a line for each accepted WebSocket. With `access_log=False` and the `warning` level,
  `python -m nock` (spec 036 `main()`, which uses `server_config`'s default level)
  writes neither (AC-3).
- The app's own log records (`nock.*` loggers) never hold a client address, a resume
  token, the operator token or a chat text.

### `nock.room` and `nock.hub`: server relay time

```python
# src/nock/room.py (addition to spec 011's model)
class LogEntry(RoomModel):
    # ... fields of specs 011 and 018
    relay_ms: int | None = Field(default=None, ge=0, strict=True)  # spec 038
```

- For a step made by a client message (a join, or a message of a joined player), the
  hub sets `relay_ms` on each of the step's entries: the whole milliseconds, rounded
  down, from the moment the server read that message's frame (when
  `RoomConnection.submit` is called) to the moment the step's entries are handed to
  `store.append`, both read with `time.monotonic()`. It includes the wait in the
  room's inbox and the rules; it excludes the commit and the network.
- Entries of steps without a client message (`tick`, `after_restart`, a closed
  connection) have `relay_ms = None`, as have entries logged before this spec.
- `relay_ms` is private, like `resume_token` and `undo` (spec 018 decision 4): the
  players receive `entry.event` only, never the entry.

### `nock.store`

```python
# src/nock/store.py (additions)
class RoomStore:
    def codes_created_since(self, since: float) -> list[tuple[str, float]]:
        """Return a `(code, created_at)` pair for each room whose creation time
        (spec 032) is at least `since`, in no particular order."""
```

`secure_delete` and the checkpoint of `delete_room`: see above.

(Note from the lead, 2026-10-16: decided after the spec-writer's report, one store
read gives each room of the period with its creation time, so that no room can go
between two reads. The block read
`created_at(self, code: str) -> float | None`, "Return the room's creation time
(spec 032), or None for an unknown room.", and
`codes_created_since(self, since: float) -> list[str]`, "Return the codes of the
rooms whose creation time is at least `since`, by creation time, then code." The
figures do not depend on the order of the rooms (preparation of spec 038).)

### Operator access (dashboard and replay)

| Variable | Default | Valid values | Any other value |
| --- | --- | --- | --- |
| `NOCK_OPERATOR_TOKEN` | unset, or empty: the operator pages are off | 32 to 256 characters, each one of `A-Z`, `a-z`, `0-9`, `_` and `-` (for example the output of `python -c "import secrets; print(secrets.token_urlsafe(32))"`) | `main()` raises `SystemExit` whose `code` is a `str` naming `NOCK_OPERATOR_TOKEN` and the rule broken, never the value, before it builds a server, so `python -m nock` prints it on stderr and exits with status 1 |

```python
# src/nock/settings.py (new)
class SettingsError(ValueError):
    """An environment variable holds a value the server cannot use.

    The message names the variable; it never holds the value of a secret.
    """


def operator_token_from_env(environ: Mapping[str, str]) -> str | None:
    """Return the operator token of `environ["NOCK_OPERATOR_TOKEN"]`.

    Returns:
        The token, or None when the variable is unset or empty (operator pages off).

    Raises:
        SettingsError: the value breaks the rule above.
    """


# src/nock/__main__.py (change to spec 036)
def main() -> None:
    """As spec 036, and first `operator_token_from_env(os.environ)`: a
    SettingsError becomes `SystemExit(str(error))`, before any server is built."""


# src/nock/server.py (change)
def create_app(
    rooms: RoomRegistry | None = None,
    dist_dir: Path | None = None,
    catalogue: Catalogue | None = None,
    *,
    operator_token: str | None = None,  # None: NOCK_OPERATOR_TOKEN, read when the app starts
) -> FastAPI: ...
```

Rules, for every path under `/api/ops/` (the ops API):

1. Operator pages off (no token given, and the variable unset or empty when the app
   started): `GET /ops` and every ops API path answer exactly as any unknown path
   does (spec 040): 404 with `{"detail": "Not Found"}` and no `Cache-Control`
   header. None of the rules below applies to them. (Note from the lead,
   2026-10-16: decided after the spec-writer's report; this read "answer 404 with
   `{"detail": "Not Found"}`, as any unknown path (spec 040)", which left open
   whether rule 4 applies while the pages are off (preparation of spec 038).)
2. Throttle: when the client address (as spec 011 reads it) has at least
   `WRONG_CODE_LIMIT` (10) refused ops requests whose time `t` satisfies
   `t > now - WRONG_CODE_WINDOW_SECONDS` (60.0, `now = rooms.clock()`), spec 011's
   constants, the request answers 429 with `{"detail": "Too Many Requests"}`,
   whatever its token. This refusal is not counted. (Note from the lead,
   2026-10-16: decided after the spec-writer's report, the throttle uses spec 011's
   constants; this read "`WRONG_TOKEN_LIMIT = 10`" and "`WRONG_TOKEN_WINDOW_SECONDS`
   (60.0, ...)", two names of this spec with the same values (preparation of spec
   038).)
3. The request must carry the header `Authorization: Bearer <token>`, compared with
   the operator token by `secrets.compare_digest`. A missing or different token
   answers 401 with `{"detail": "Not authorized"}` and the header
   `WWW-Authenticate: Bearer`, and counts as one refusal for its address. This check
   comes right after rules 1 and 2, before anything else of the request (its query,
   its code, its room) is looked at: a request with a missing or wrong token answers
   401 whatever else it holds. For example, `?days=2` with a wrong token answers 401,
   and only a right token with a wrong `days` gets 422. (Note from the lead,
   2026-10-16: added: the spec did not say whether the token check or the validation
   of the request comes first (questions from spec 038's tests).)
4. While the operator pages are on, every ops API answer, refusals included, has
   `Cache-Control: no-store`. (Note from the lead, 2026-10-16: decided after the
   spec-writer's report; this read "Every ops API answer, refusals included, has
   `Cache-Control: no-store`." (preparation of spec 038).)

The token is never read from a URL, a query or a cookie, and never written to a log.
The failures are kept per app, in memory, like spec 011's.

Rules 2 and 3 are spec 011's wrong-code throttle as spec 032 left it, applied to
refused ops requests: the ops API keeps a second instance of that throttle
(`_WrongCodeThrottle` in `nock.server`, with spec 011's constants), checks rule 2
with its `is_blocked`, and counts a refusal of rule 3 with its
`record_unless_blocked`, which checks and records in one step under its lock, as
spec 028's recap route does. A wrong token that this record finds blocked answers
429 instead of 401, so wrong tokens that arrive at once from one address are
counted one after another, as wrong codes are (spec 011). The two instances keep
separate counts. (Note from the lead, 2026-10-16: added from the code of spec 011's
throttle, whose check and record became one locked step in the second review of
spec 032; decided after the spec-writer's report, the ops API's throttle is a
second instance of it, with spec 011's constants (preparation of spec 038).)

The "refused ops requests" of rule 2 are the refusals of rule 3 (a missing or wrong
token), and nothing else: no other answer is counted, and a 404 of
`GET /api/ops/rooms/{code}/edits` for an unknown or expired room, or for a code
breaking `ROOM_CODE_PATTERN`, is not. (Note from the lead, 2026-10-16: added: the
spec did not say whether other answers of the ops API count as refused requests,
such as that 404 (questions from spec 038's tests).)

### Ops API

| Method and path | Answer |
| --- | --- |
| `GET /api/ops/dashboard`, `GET /api/ops/dashboard?days=N` with `N` exactly `1`, `7` or `30` | 200, `DashboardFigures` JSON for that period (default 7 days) |
| `GET /api/ops/dashboard?days=X`, any other `X` | 422, FastAPI's validation body |
| `GET /api/ops/rooms/{code}/edits`, a room that `rooms.peek_room(code)` finds | 200, `RoomReplay` JSON |
| `GET /api/ops/rooms/{code}/edits`, unknown or expired room, or a code breaking `ROOM_CODE_PATTERN` | 404, `{"detail": "Not Found"}` |

The dashboard reads the `(code, created_at)` pairs of
`rooms.store.codes_created_since(now - days * 86_400)` (`now = rooms.clock()`;
`rooms.store` is the registry's store, spec 032), then the whole log of each of
those rooms (`rooms.store.read_log(code)`), without making the room live, and
passes a `RoomLog(code=code, created_at=created_at, entries=<its log>)` per room to
`dashboard_figures`; the replay reads the log of its room the same way. With at
most 30 days, no room of the period can have expired, since its last edit is not
older than its creation (spec 032). (Note from the lead, 2026-10-16: this read "The
dashboard reads, for each code of `store.codes_created_since(now - days * 86_400)`
(`now = rooms.clock()`), its creation time and its whole log, without making the
room live." `store` became `rooms.store`, the registry's store in the code, and,
decided after the spec-writer's report, one read gives the codes with their
creation times (preparation of spec 038).)

```python
# src/nock/operations.py (new): pure functions over logs, no I/O
DAY_SECONDS: float = 86_400.0


class RoomLog(BaseModel):
    """One room's creation time and log, as the dashboard reads them."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RoomCode
    created_at: float
    entries: tuple[LogEntry, ...]  # in seq order


class DashboardFigures(BaseModel):
    """The six figures of the dashboard for one period."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    days: Literal[1, 7, 30]
    since: AwareDatetime  # now - days, in UTC
    rooms_created: int = Field(ge=0, strict=True)
    players_per_room: float | None
    completion_rate: float | None  # 0 to 1
    median_solving_ms: float | None
    latency_median_ms: float | None
    latency_p95_ms: int | None
    disconnection_rate: float | None


def dashboard_figures(
    rooms: Sequence[RoomLog], days: int, now: float
) -> DashboardFigures:
    """Return the figures of the rooms created at `now - days * DAY_SECONDS` or later.

    Rooms created earlier are ignored. See "Dashboard figures".

    Raises:
        ValueError: `days` is not 1, 7 or 30.
    """


class RoomEdit(BaseModel):
    """One edit of a room, as the replay shows it."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: Seq
    at: AwareDatetime  # the entry's `at`, in UTC
    kind: Literal["typed", "erased", "undone", "locked", "revealed"]
    row: Coordinate
    column: Coordinate
    letter: Letter | None  # the cell's letter after the edit, None when it is empty
    pencil: StrictBool  # the letter_changed's pencil flag; False for a lock
    player_id: PlayerId | None  # who made it; None for "locked" and "revealed"
    nickname: Nickname | None  # from that player's player_joined, see below; None when unknown


class RoomReplay(BaseModel):
    """What the replay of one room needs: its empty grid and its edits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    code: RoomCode
    grid: GridView  # grid_view(state.grid): no letter, no answer
    edits: tuple[RoomEdit, ...]  # in seq order


def room_edits(entries: Sequence[LogEntry]) -> tuple[RoomEdit, ...]:
    """Return one RoomEdit per edit entry (spec 032 `is_edit`), in seq order."""
```

Kinds of `room_edits`: a `letter_changed` with `undo` True is `undone` (its letter may
be a letter or None); otherwise one with a letter is `typed` and one with no letter
is `erased`; a `cell_locked` with `revealed` False is `locked` (a check), with
`revealed` True `revealed`. `letter` is the event's letter.

`nickname` is that of the latest `player_joined` of the edit's player before the
edit, in seq order, as the server stores it, in capitals (spec 012). A player seated
back (spec 032) has a second `player_joined` with the same player id, whose
nickname may carry spec 012's suffix (`ANA 2`, spec 032 decision 12); their edits
after it take that nickname. It is None for a `locked` or `revealed` edit, and for
a player with no `player_joined` before the edit in the entries given. (Note from
the lead, 2026-10-16: this paragraph was added, and the comment of
`RoomEdit.nickname` read "from that player's player_joined in the log; None when
unknown", written when a player had one `player_joined` only (preparation of spec
038).)

### Dashboard figures

The rooms of the period are those passed to `dashboard_figures` whose `created_at` is
at least `now - days * 86_400`.

| Figure | Definition | No data |
| --- | --- | --- |
| `rooms_created` | the number of rooms of the period | `0` |
| `players_per_room` | the mean number of `player_joined` entries per room of the period | None when there is no room |
| `completion_rate` | the share of the rooms of the period whose log holds a `grid_solved` entry | None when there is no room |
| `median_solving_ms` | `statistics.median` of the `elapsed_ms` of those `grid_solved` entries (spec 026; spec 027 made it the shared timer's value when the grid is solved) | None when no room is solved |
| `latency_median_ms`, `latency_p95_ms` | over the `relay_ms` values that are not None of the `letter_changed` entries of the rooms of the period: their `statistics.median`, and the `ceil(0.95 × n)`-th smallest (spec 036's p95) | None when there is no such value |
| `disconnection_rate` | the number of drops divided by the number of `player_joined` entries; a drop is a `player_state_changed` to `disconnected` that is followed, later in the same room's log, by a `player_state_changed` to `active` of the same player, before that player's next `disconnected` entry and before any `player_left` of that player | None when there is no join |

A drop is a lost connection that came back within spec 017's window, the sign of a
bad network. A player who closes the tab and does not come back is not a drop. Nor
is a player who times out (spec 017's `player_left`) and is seated back later (spec
032), although the seat back keeps their player id. (Note from the lead,
2026-10-16: in the row `disconnection_rate`, "and before any `player_left` of that
player" was added, with the sentence before this note. Since spec 032's seat back,
a player who timed out comes back with the same id, so a later `active` of theirs,
after an `idle` for example, made their disconnection before the time-out count
as a drop. In the row `median_solving_ms`, "(spec 026, as spec 027 may redefine
it)" became "(spec 026; spec 027 made it the shared timer's value when the grid is
solved)", since spec 027 is built (preparation of spec 038).)

### Client: the ops page `/ops`

Routing (spec 040) gains `/ops`, shown by the ops page; the server serves `index.html`
on `GET /ops` while the operator pages are on (503 when the client is not built, as
`/`), and 404 otherwise.

- Root `data-testid="ops-page"`, heading `t("ops.heading")`, `data-state`: `locked`
  (the token form shows), `loading` (shows `t("ops.loading")` in an element with
  `role="status"`), `ready`, or `error` (an answer other than 200, 401 or 429, or a
  network failure; shows `t("ops.error")`). (Note from the lead, 2026-10-16: added:
  the spec did not say what the page shows while `data-state` is `loading`; the key
  `ops.loading` was listed in "New `fr.json` keys" and used nowhere
  (questions from spec 038's tests).)
- Token form `data-testid="ops-token-form"`: a password input
  `data-testid="ops-token-input"` labelled `t("ops.token_label")`, and a submit
  button `data-testid="ops-token-submit"` with `t("ops.token_submit")`. Submitting
  keeps the token in `sessionStorage["nock.ops_token"]` and loads the dashboard. The
  token is never put in `localStorage`, a cookie or a URL.
- Every ops API request of the page carries `Authorization: Bearer <token>`. A 401
  removes `nock.ops_token`, goes back to `locked` and shows
  `data-testid="ops-token-error"` (`role="alert"`) with `t("ops.token_refused")`;
  a 429 does the same: it removes `nock.ops_token`, goes back to `locked` and shows
  `ops-token-error`, with `t("ops.throttled")` instead of `t("ops.token_refused")`.
  (Note from the lead, 2026-10-16: added: the spec did not say whether a 429 also
  removes `nock.ops_token` and goes back to `locked`, as a 401 does; it read "a 429
  shows it with `t("ops.throttled")`" (questions from spec 038's tests).)
- On load, when `sessionStorage` holds `nock.ops_token`, the page loads the
  dashboard without showing the form.
- Dashboard `data-testid="ops-dashboard"` (heading `t("ops.dashboard_heading")`):
  three buttons `data-testid="ops-period"` with `data-days` `1`, `7`, `30` and the
  texts `t("ops.period.one_day")`, `t("ops.period.seven_days")`,
  `t("ops.period.thirty_days")`, in a group labelled `t("ops.period_label")`; the
  shown period has `aria-pressed="true"`, the others `"false"`; `7` on load. Then
  six `data-testid="ops-metric"` elements with `data-metric` `rooms_created`,
  `players_per_room`, `completion_rate`, `median_solving_time`, `latency` and
  `disconnection_rate`, in that order, each with `data-value` (`String(figure)`,
  `figure` being the number the page received, so a figure `2.0` reads `2`; `""` for
  None; for `latency` the median, plus `data-p95`) and the text
  `t("ops.metric.<data-metric>", {value})`, where `value` is:

  | Metric | `value` |
  | --- | --- |
  | `rooms_created` | the integer |
  | `players_per_room` | `new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 1, maximumFractionDigits: 1})`, for example `2,0` |
  | `completion_rate` | `t("ops.percent", {value: Math.round(rate * 100)})`, for example `67 %` |
  | `median_solving_time` | the duration text below, for example `12 min 30 s` |
  | `latency` | `t("ops.latency_value", {median, p95})`, both rounded to whole milliseconds |
  | `disconnection_rate` | `new Intl.NumberFormat("fr-FR", {minimumFractionDigits: 2, maximumFractionDigits: 2})`, for example `0,50` |

  A figure that is None shows `t("ops.no_data")` as its `value`. (Note from the lead,
  2026-10-16: added: the spec did not say how a number is written in `data-value`;
  `String(figure)` replaces "the figure as received"
  (questions from spec 038's tests).)
- Duration text (shared with spec 029): with `s` the whole seconds of the
  milliseconds (rounded down), `h = floor(s / 3600)`, `m = floor(s % 3600 / 60)`,
  `sec = s % 60`: `t("duration.minutes", {minutes: m, seconds: <sec on 2 digits>})`
  when `h` is 0, for example `12 min 30 s` and `0 min 05 s`; otherwise
  `t("duration.hours", {hours: h, minutes: <m on 2 digits>, seconds: <sec on 2 digits>})`,
  for example `1 h 02 min 05 s`.
- Replay `data-testid="ops-replay"` (heading `t("ops.replay_heading")`), with
  `data-state` `idle`, `loading`, `ready`, `not_found` (shows
  `t("ops.replay_not_found")`) or `error`: a form `data-testid="ops-replay-form"`
  with an input `data-testid="ops-replay-code"` labelled `t("ops.replay_code_label")`
  and a submit button `data-testid="ops-replay-submit"` (`t("ops.replay_submit")`).
  Submitting requests `GET /api/ops/rooms/<code>/edits` with the code in upper case.
  When ready:
  - one `data-testid="ops-edit"` element per edit, in seq order, with `data-seq`,
    `data-kind`, `data-row`, `data-column`, `data-letter` (`""` for none),
    `data-player-id` (`""` for none) and `data-at` (as received), and the text
    `t("ops.edit.<kind>", {time, name, letter, row, column})`, where the kind
    `typed` with `pencil` true uses `ops.edit.typed_pencil`, `time` is
    `new Intl.DateTimeFormat("fr-FR", {hour: "2-digit", minute: "2-digit", second: "2-digit"})`
    of `at` in the browser's time zone, and `name` is the nickname as spec 040's
    `displayNickname` writes it (`ANA` shows as `Ana`), or `t("feed.someone")`
    when it is None. (Note from the lead, 2026-10-16: "the nickname as spec 040's
    `displayNickname` writes it (`ANA` shows as `Ana`)" read "the nickname"; spec
    040 lists the ops replay among the places that show a nickname that way
    (preparation of spec 038).) A room with no edit shows
    `t("ops.replay_empty")`;
  - a range input `data-testid="ops-replay-position"` (minimum 0, maximum the number
    of edits, step 1, labelled `t("ops.replay_position_label")`), at the maximum when
    the edits load, and `data-testid="ops-replay-step"` with
    `t("ops.replay_step", {step, count})`;
  - a grid `data-testid="ops-replay-grid"` (labelled `t("ops.replay_grid_label")`)
    with one `data-testid="ops-replay-cell"` per letter cell of `grid`, each with
    `data-row`, `data-column` and `data-letter`: the letter of the last of the first
    `k` edits on that cell (`k` the position), `""` when none or when that edit left
    it empty. The cell shows that letter as text.
- Small windows (spec 006 AC-5): no horizontal page scroll; the page may scroll
  vertically. Accessibility (spec 035): every control is reachable with `Tab`, shows
  AC-2's visible focus and has a label from `fr.json`; texts meet 4.5:1.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `ops.heading` | `Exploitation` |
| `ops.token_label` | `Jeton d'opérateur` |
| `ops.token_submit` | `Ouvrir` |
| `ops.token_refused` | `Jeton refusé.` |
| `ops.throttled` | `Trop d'essais. Réessayez dans une minute.` |
| `ops.loading` | `Chargement…` |
| `ops.error` | `Impossible de charger les données.` |
| `ops.dashboard_heading` | `Tableau de bord` |
| `ops.period_label` | `Période` |
| `ops.period.one_day` | `Dernières 24 heures` |
| `ops.period.seven_days` | `7 derniers jours` |
| `ops.period.thirty_days` | `30 derniers jours` |
| `ops.metric.rooms_created` | `Salons créés : {value}` |
| `ops.metric.players_per_room` | `Joueurs par salon : {value}` |
| `ops.metric.completion_rate` | `Grilles terminées : {value}` |
| `ops.metric.median_solving_time` | `Temps médian de résolution : {value}` |
| `ops.metric.latency` | `Latence du serveur : {value}` |
| `ops.metric.disconnection_rate` | `Coupures par joueur : {value}` |
| `ops.no_data` | `aucune donnée` |
| `ops.percent` | `{value} %` |
| `ops.latency_value` | `{median} ms (médiane), {p95} ms (95e centile)` |
| `duration.minutes` | `{minutes} min {seconds} s` |
| `duration.hours` | `{hours} h {minutes} min {seconds} s` |
| `ops.replay_heading` | `Relecture d'un salon` |
| `ops.replay_code_label` | `Code du salon` |
| `ops.replay_submit` | `Relire` |
| `ops.replay_not_found` | `Salon introuvable.` |
| `ops.replay_empty` | `Aucune modification dans ce salon.` |
| `ops.replay_position_label` | `Étape` |
| `ops.replay_step` | `Étape {step} sur {count}` |
| `ops.replay_grid_label` | `Grille à l'étape choisie` |
| `ops.edit.typed` | `{time} · {name} écrit {letter} en ({row}, {column})` |
| `ops.edit.typed_pencil` | `{time} · {name} écrit {letter} au crayon en ({row}, {column})` |
| `ops.edit.erased` | `{time} · {name} efface ({row}, {column})` |
| `ops.edit.undone` | `{time} · {name} annule sa dernière modification en ({row}, {column})` |
| `ops.edit.locked` | `{time} · ({row}, {column}) verrouillée par une vérification` |
| `ops.edit.revealed` | `{time} · {letter} révélée en ({row}, {column})` |

### Test harness

- `DAY = 86_400.0` and `LIFE = 30 * DAY`, as spec 032's harness.
- `OPS_TOKEN = "Ops-" + "x" * 40` (44 characters). Ops API criteria use
  `TestClient(create_app(rooms=registry, dist_dir=tmp_path, operator_token=OPS_TOKEN))`;
  "off" is `create_app(rooms=registry, dist_dir=tmp_path)` with
  `NOCK_OPERATOR_TOKEN` deleted by `monkeypatch`.
- Dashboard criteria (AC-5) build `RoomLog` values from hand-made `LogEntry`
  sequences; HTTP checks (AC-6) seed a registry with a fake clock whose store holds
  rooms with chosen creation times (`new_room(code, grid, <creation time>)`, then
  `add_room`, then `store.append` of their entries).
- Database bytes (AC-1, AC-4): the test reads `nock.sqlite3` and, when it exists,
  `nock.sqlite3-wal` from `tmp_path` as bytes and searches them for UTF-8 strings.
- Browser with live server and a file database (AC-1, AC-2, AC-7, AC-9): the test
  module starts its own server the way spec 040's `live_server` does (built client,
  free port of 127.0.0.1, `uvicorn.Server` with `server_config`, as spec 036 left
  it), with
  `create_app(rooms=RoomRegistry(store=RoomStore(tmp_path / "nock.sqlite3")), dist_dir=WEB_DIST_DIR, catalogue=..., operator_token=OPS_TOKEN)`.
  (Note from the lead, 2026-10-16: "with `server_config`, as spec 036 left it" was
  added: `live_server` builds its server with `server_config` since spec 036
  (preparation of spec 038).)
- Probe browser context (AC-1, AC-2): `user_agent="NockPrivacyProbe/7.3"`,
  `extra_http_headers={"X-Nock-Probe": "probe-header-91"}`, `locale="fr-FR"`; the
  test records every request URL and response of the page (`page.on("request")`,
  `page.on("response")`).
- Subprocess (AC-3, AC-10): spec 036's harness for `python -m nock` (a SQLite file
  holding a FX-01 room, `NOCK_DATABASE`, `NOCK_PORT`, no `NOCK_HOST`), plus
  `NOCK_OPERATOR_TOKEN=OPS_TOKEN`; the test captures the process's stdout and stderr.
  `main()` in the test process with `uvicorn.Server.run` replaced is spec 036's
  recorder.
- Relay time (AC-11): spec 036's blocking store (a `RoomStore(":memory:")` subclass
  whose `append` waits on a `threading.Event` while a flag is set) and hub tests on
  their own event loop, as spec 036's AC-6.
- Mocked ops API (AC-7): `page.route("**/api/ops/dashboard*", handler)` answering
  JSON built from `DashboardFigures`; the context has `timezone_id="Europe/Paris"`.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-10.4.1) (browser with live server and a file database) A guest is stored as a nickname and a random identifier, nothing else. In the probe context, a page enters a FX-01 room as `Ana` (spec 011's `enter_room`) and types `T`, `A`, `M` from (1, 0) across; the test then closes the registry (which saves a snapshot) and the store. The bytes of the database files hold `ANA`, her nickname as the server stores it (spec 012), and her `data-you` player id, and hold none of `NockPrivacyProbe`, `probe-header-91`, `fr-FR` and `127.0.0.1`. (Note from the lead, 2026-10-16: the nickname searched was `Ana`, which the store never holds once nicknames are in capitals (human's rule of 2026-10-16: nicknames in capitals).)
- **AC-2** (AC-10.4.1) (browser with live server) Playing needs no advertising cookie, nor any cookie. In the probe context, a page opens `/`, starts FX-01 from the catalogue (spec 010), types the 18 letters of FX-01 word by word, 60 ms or more between keys (spec 037's harness), and reaches `data-solved="true"` (spec 026). Then no recorded response has a `set-cookie` header, `context.cookies()` is empty, `document.cookie` is `""`, and every recorded request URL starts with the server's origin (`http://127.0.0.1:<port>` or `ws://127.0.0.1:<port>`).
- **AC-3** (AC-10.4.1) (subprocess; WebSocket from a Playwright page) The production server writes no client address and no secret to its logs. With the subprocess of "Test harness", a page on the server's origin loads `/`, opens a socket to the stored room, joins as `Ana`, sends three `edit_letter` messages and a `chat` (spec 022) with the text `chat-probe-5521`, then requests `GET /api/ops/dashboard` once with a wrong token and once with `OPS_TOKEN`, and `GET /nothing-here`; the test stops the process. Its stdout and stderr together hold none of `127.0.0.1`, `GET /`, `WebSocket /`, the resume token of Ana's snapshot, `chat-probe-5521` and `OPS_TOKEN`. `server_config(app).access_log is False` and its default `log_level` is `"warning"`.
- **AC-4** (AC-10.4.2) (Python; WebSocket with a fake clock) Room data, chat included, is deleted at room expiry, with no copy left in the database files. Python: with a store file, room A (a code that occurs nowhere else in the file, see "Edge cases") holds the joins of `Zélie` and `Bob`, a `chat_message` of Zélie with the text `chat-secret-4711`, letters and a check; room B holds `Yann` and the chat text `chat-kept-8203`. After room A expires and `expire_rooms()` returns it, while the store is still open, the database files hold none of `chat-secret-4711`, `ZÉLIE` (UTF-8, her nickname as the server stores it, spec 012), A's code and A's resume tokens, and still hold `chat-kept-8203` and `YANN`. (Note from the lead, 2026-10-16: the nicknames searched were `Zélie` and `Yann`, which the store never holds once nicknames are in capitals (human's rule of 2026-10-16: nicknames in capitals).) The same holds once the store is closed. WebSocket: with spec 032 AC-2's setup (`expiry_sweep_seconds=0.05`), after a chat in the room and `advance(LIFE + 1)`, the sweep alone deletes the room, and within 2 seconds of real time the database files hold none of the chat's text, `ANA` and `BOB` (the nicknames of that setup as the server stores them, spec 012), the room's code and its resume tokens. (Note from the lead, 2026-10-16: this read "the sweep alone deletes the room and the same bytes are gone within 2 seconds of real time", which named no string for a room whose players are not those of the Python part (preparation of spec 038).)
- **AC-5** (AC-10.4.3) (Python) The dashboard's figures come from the room logs. With `now = T` and these `RoomLog` values: R1 created at `T - 2 DAY` with 3 `player_joined`, five `letter_changed` with `relay_ms` 10, 20, 30, 40 and None, one drop of `p2` (`disconnected` then `active`), `p3` `disconnected` and never back, and a `grid_solved` with `elapsed_ms` 600,000; R2 created at `T - 1 DAY` with 1 `player_joined`, one `letter_changed` with `relay_ms` 50 and a `grid_solved` with `elapsed_ms` 900,000; R3 created at `T - 3 DAY` with 2 `player_joined`, no edit, and `p1` `disconnected`, `active`, `disconnected`, `active` (two drops); R4 created at `T - 8 DAY` with 5 joins and a `grid_solved`. `dashboard_figures(rooms, 7, T)` gives `rooms_created=3`, `players_per_room=2.0`, `completion_rate` 2/3, `median_solving_ms=750000.0`, `latency_median_ms=30.0`, `latency_p95_ms=50`, `disconnection_rate=0.5` and `since` = `T - 7 DAY` in UTC; with `days=1` it gives `rooms_created=1` (R2, created exactly at the start of the period), `players_per_room=1.0`, `completion_rate=1.0`, `median_solving_ms=900000.0`, `latency_median_ms=50.0`, `latency_p95_ms=50` and `disconnection_rate=0.0`; with no room, `rooms_created=0` and every other figure None; `days=2` raises `ValueError`.
- **AC-6** (AC-10.4.3) (HTTP; Python) Only the operator reaches the dashboard. With `OPS_TOKEN`: `GET /api/ops/dashboard` with `Authorization: Bearer <OPS_TOKEN>` answers 200 with `DashboardFigures` JSON whose `days` is 7 and whose figures are those of `dashboard_figures` over one `RoomLog` per pair of `rooms.store.codes_created_since(now - 7 * DAY)`, with that room's log; `?days=30` gives `days` 30; `?days=2` answers 422. On a store holding rooms created at `now - 8 * DAY`, `now - 7 * DAY` and `now - DAY`, `codes_created_since(now - 7 * DAY)` returns the `(code, created_at)` pairs of the last two and no other, in any order. Without the header, with `Bearer wrong`, with `Basic <OPS_TOKEN>` or with the token in the query `?token=<OPS_TOKEN>`, it answers 401 with `{"detail": "Not authorized"}` and `WWW-Authenticate: Bearer`; while the operator pages are on, every ops answer has `Cache-Control: no-store`. After 10 refused requests from one address within 60 seconds of the fake clock, the next request answers 429, also with the right token; after `advance(60)` the right token gets 200 again. With the operator pages off, `GET /api/ops/dashboard` with the right token, `GET /api/ops/rooms/<code>/edits` and `GET /ops` answer exactly as an unknown path does: 404 with `{"detail": "Not Found"}` and no `Cache-Control` header; with them on, `GET /ops` answers 200 with `index.html`. (Note from the lead, 2026-10-16: decided after the spec-writer's report. "over the store's rooms" became the reads of "Ops API", and the check of `codes_created_since` was added, with "Python" in the brackets, since the figures alone cannot show which rooms the store returns; "every ops answer has `Cache-Control: no-store`" gained "while the operator pages are on"; the answers with the pages off read "answer 404 with `{"detail": "Not Found"}`" (preparation of spec 038).)
- **AC-7** (AC-10.4.3) (browser with live server; browser with mocked ops API) The ops page shows the dashboard once the operator gives the token. Live: `/ops` shows `ops-page` with `data-state="locked"` and the token form; submitting `wrong` shows `ops-token-error` with `fr.json["ops.token_refused"]`; submitting `OPS_TOKEN` reaches `data-state="ready"` with six `ops-metric` elements in the order of "Client", the period `7` pressed, and every ops request carrying `Authorization: Bearer <OPS_TOKEN>`; afterwards `sessionStorage["nock.ops_token"]` is `OPS_TOKEN`, no `localStorage` value and no cookie holds it, and the page's URL is still `<base>/ops`; clicking the period `30` sends `days=30` and presses it; a reload shows the dashboard without the form. Mocked, with the figures of AC-5's 7-day result: the six texts are `Salons créés : 3`, `Joueurs par salon : 2,0`, `Grilles terminées : 67 %`, `Temps médian de résolution : 12 min 30 s`, `Latence du serveur : 30 ms (médiane), 50 ms (95e centile)` and `Coupures par joueur : 0,50`; with the result of no room, they are `Salons créés : 0`, `Joueurs par salon : aucune donnée`, `Grilles terminées : aucune donnée`, `Temps médian de résolution : aucune donnée`, `Latence du serveur : aucune donnée` and `Coupures par joueur : aucune donnée`, and each `data-value` other than that of `rooms_created` is `""`. Keyboard only, `tab_to` reaches the token input, typing the token and `Enter` loads the dashboard, and `tab_to` reaches each `ops-period` with spec 035 AC-2's outline. Spec 035's contrast and language scans find no offending element on the ready page at 1280 by 720 and 360 by 740, and at each window size of spec 006 AC-5 the page has no horizontal scroll.
- **AC-8** (AC-10.4.4) (Python; HTTP) An operator gets the ordered edits of a room from its log. Python: for the entries of a FX-01 room where `Ana` (`p1`) typed `T` at (1, 0), `Bob` (`p2`) typed `A` at (1, 1) and then `M` at (1, 2) in pencil (spec 020), Ana erased (1, 0), Ana undid her erase, a check locked (1, 1), a reveal locked `M` at (1, 2), and joins, chat and presence entries came in between, `room_edits` returns exactly seven `RoomEdit` values in seq order, of kinds `typed` (`T`), `typed` (`A`), `typed` (`M`, `pencil=True`), `erased`, `undone` (letter `T`), `locked` (letter `A`, no player) and `revealed` (letter `M`, no player), with the `seq`, `at` (UTC), `row`, `column` and `player_id` of their entries, and for the first five the `nickname` of their player's `player_joined`: `ANA` or `BOB`, as the server stores them (spec 012). (Note from the lead, 2026-10-16: this read "with the `seq`, `at` (UTC), `row`, `column`, `player_id` and `nickname` (`Ana`, `Bob`) of their entries"; the nicknames come from the `player_joined` entries, which hold them in capitals, spec 039's "Nicknames in capitals" (preparation of spec 038).) HTTP: `GET /api/ops/rooms/<code>/edits` with the token answers 200 with `RoomReplay` JSON whose `grid` equals `grid_view` of the room's grid and whose `edits` equal `room_edits` of its log; its body holds none of the eight FX-01 answers and no key `answer` (spec 037); an unknown code, an expired room and `abc` answer 404.
- **AC-9** (AC-10.4.4) (browser with live server) The ops page replays a room's edits in order. After a page entered a FX-01 room as `Ana` and typed `T`, `A`, `M`, `I`, `S` from (1, 0) across, then clicked (1, 4) and pressed `Backspace`, which erases it (spec 008), the ops page (another context, `timezone_id="Europe/Paris"`, token given) with the room's code in `ops-replay-code` reaches `ops-replay` `data-state="ready"` with six `ops-edit` items in seq order: five `typed` with letters `T`, `A`, `M`, `I`, `S` and one `erased` at (1, 4), each text built from `fr.json` with `Ana`, which is how spec 040's `displayNickname` shows the stored `ANA`; `ops-replay-position` is at 6 and `ops-replay-step` reads `Étape 6 sur 6`; the 18 `ops-replay-cell` elements show `T`, `A`, `M`, `I` on row 1 and nothing else. Setting the position to 5 makes (1, 4) show `S`; to 0, every cell is empty and the step reads `Étape 0 sur 6`. A code with no room shows `fr.json["ops.replay_not_found"]`. (Note from the lead, 2026-10-16: ", which is how spec 040's `displayNickname` shows the stored `ANA`" was added after "with `Ana`"; the texts are unchanged, as spec 039's "Nicknames in capitals" says of a nickname read on a page (preparation of spec 038).)
- **AC-10** (new) (Python, `uvicorn.Server.run` replaced) The operator token is configured by `NOCK_OPERATOR_TOKEN` and its value never shows. `operator_token_from_env` returns None for `{}` and for an empty value, and returns the value for 32 and for 256 characters of the allowed set; it raises `SettingsError` for 31 characters, 257 characters, and a value holding `$`, a space or `é`, and no message holds the value. With spec 036's recorder, `main()` with `NOCK_OPERATOR_TOKEN="Zq9Zq9"` or `"Zq9" * 11 + "$"` raises `SystemExit` whose `code` is a `str` containing `NOCK_OPERATOR_TOKEN` and not the value, and `run` is never called; with `OPS_TOKEN` it calls `run` once.
- **AC-11** (new) (hub test; Python) The log records the server's relay time of each client step, which the dashboard's latency reads. With the blocking store and `RoomConfig(max_edits_per_second=1000)`: connection A joins a FX-01 room; the store starts blocking; A submits `EditLetter(row=1, column=0, letter="T")` (its step waits in `append`), then `EditLetter(row=1, column=1, letter="A")`; after 300 ms the store is released. Then the first edit's entry has `relay_ms` below 250 and the second's at least 250. The entry of A's join has an integer `relay_ms`, and the `player_state_changed` entry logged when A's socket then closes has `relay_ms` None. Python: the entries returned by `tick` (an idle change) and by `after_restart` have `relay_ms` None. No message the clients receive holds the key `relay_ms`, and a `LogEntry` with `relay_ms=-1` or `"5"` is refused by validation.

## Edge cases and errors

- Code of AC-4's room A: any code; the test checks that its six characters as UTF-8
  are absent after the deletion, so it picks a code that occurs nowhere else in the
  file (for example `QJ7WXK`), and room B gets another.
- Database pages (AC-4): `secure_delete` zeroes deleted rows and freed pages; the
  `-shm` file holds no row data. The criterion checks the main file and the WAL file.
- Account history (AC-4): AC-4's rooms belong to no account, so nothing of them
  stays. A solved room in which an account played keeps that account's history
  record after the deletion (spec 029: code, grid, size, date, time taken and
  team-mates' nicknames), outside the room's data, until the account is deleted.
  (Note from the lead, 2026-10-15: added after spec 029's decision 6.)
- Restart after a crash (AC-4): rows deleted before the crash are not in the database
  after it (the deletion is committed); spec 032's lookups and sweep go on deleting
  expired rooms after the restart.
- Nickname in a log (AC-1): a nickname is personal data and is kept with the room;
  spec 033 replaces it when an account is deleted.
- Logs of errors (AC-3): an exception in a room's rules is logged with its traceback
  (spec 011), which may show game data of that room, such as a nickname, never an
  address or a token. Chat texts are not logged on purpose.
- Engines (AC-2): each engine's own requests (for example a favicon request) go to
  the same origin.
- Empty period (AC-5): no room gives `rooms_created=0` and None elsewhere; a period
  with rooms but no `relay_ms` (rooms logged before this spec) gives None latency.
- Period edge (AC-5): a room created exactly `days × 86,400` seconds before `now`
  is in the period.
- Median of an even count (AC-5): `statistics.median` gives the mean of the two
  middle values (`750000.0`).
- A room solved twice (AC-5): impossible (spec 026 produces one `grid_solved`).
- Wrong token in the URL (AC-6): never read; `?token=` is refused like a missing
  token and counts as a refusal.
- Throttle scope (AC-6): only ops requests count; room sockets keep spec 011's
  separate wrong-code count.
- Several apps (AC-6): each `create_app` keeps its own failures.
- Token in the page (AC-7): `sessionStorage` is per tab, so a new tab asks again; the
  input has `autocomplete="off"`.
- A 401 while the dashboard is shown (AC-7): the token was changed on the server;
  the page goes back to `locked` with `ops.token_refused`.
- Lowercase code (AC-9): the page sends the code in upper case; a code that breaks
  `^[A-Z0-9]{6}$` gets 404 and shows `ops.replay_not_found`.
- Long replays (AC-9): every edit is listed; the page scrolls vertically.
- Edits of a removed or timed-out player (AC-8): their nickname comes from the
  latest `player_joined` of their player id before the edit, which stays in the
  log. A player seated back (spec 032) keeps their id, and their edits after the
  seat back take the nickname of its `player_joined`. (Note from the lead,
  2026-10-16: this read "their nickname comes from their `player_joined`, which
  stays in the log"; the sentence on a seat back was added (preparation of spec
  038).)
- Pencil letters (AC-8): no pencil letter exists before spec 020 is built; spec 020
  comes before this spec in the build plan.
- Invalid variable at app start (AC-10): `main()` checks it first; an app built by
  other means (`uvicorn nock.server:app`) fails its startup with the same
  `SettingsError`.
- Slow commit (AC-11): `relay_ms` stops before the commit, so a slow disk shows in
  the next steps' waits, not in the step's own value.

## Out of scope

- Nothing stated in the backlog (epic E10).
- Accessibility: spec 035.
- Performance: spec 036.
- Integrity: spec 037.
- Backups, log retention and the hosting's own logs (proxy, load balancer).
- End-to-end sync latency measured in the browsers (decision 10), charts, alerts,
  exports, and figures per grid or per day. (Note from the lead, 2026-10-15: "open
  question 2" became "decision 10".)
- Operator accounts, roles, sign-in with a password, and rotating the token without a
  restart.
- A consent banner: the game sets no cookie and uses no tracker.
- A command-line replay tool; editing or repairing a room's log.

## Work packages

None.

## Decisions

Proposed by the spec-writer on 2026-10-14 for the Phase 6 refine, with the human's
answers of the same day (the dashboard is an operator-only page served by the app
from the room log, with no new dependency; numeric thresholds: keep the backlog
defaults). They are part of the spec above and are approved with it.

1. Operator access without a dependency (AC-6). Options: a bearer token from an
   environment variable; HTTP Basic credentials (FastAPI has them built in); a second
   listener bound to 127.0.0.1. Pick: a bearer token of at least 32 random
   characters from `NOCK_OPERATOR_TOKEN`, compared in constant time, throttled per
   address, off when unset. Basic credentials would need the browser's own dialog,
   which `fetch` does not show reliably; a second listener needs a second server in
   `main()`. The ops page is part of the Svelte client, so its texts come from
   `fr.json` like every other page.
2. Secrets and configuration. `NOCK_OPERATOR_TOKEN` is checked by `main()` like spec
   036's `NOCK_PORT`, but the message never repeats the value, since it is a secret.
3. Logs (AC-3). uvicorn writes client addresses in its access log and in its info
   lines for WebSockets. Pick: `access_log=False` and the `warning` level by default
   in `server_config`. Errors are still written.
4. Deletion leaves no copy (AC-4). Pick: SQLite's `secure_delete` and a WAL
   checkpoint after each room deletion, both part of SQLite.
5. Latency from the room log (AC-5, AC-11). The log held no time that measures
   sync. Pick: a private `relay_ms` on the entries of each client step, the server's
   share of the sync time (spec 015 decision 1 gives it 100 ms). The network share
   needs reports from the browsers (decision 10). (Note from the lead, 2026-10-15:
   "open question 2" became "decision 10".)
6. Disconnection rate (AC-5). Pick: drops per joined player, a drop being a lost
   connection that came back (`disconnected` then `active`), so that closing a tab
   for good does not count as a bad network.
7. Period (AC-5). Pick: the last 1, 7 or 30 days by creation time; up to 30 days,
   no room of the period has been deleted yet (spec 032), so the figures are exact.
8. Replay (AC-8, AC-9). Pick: the ordered list of edits with time, kind, cell,
   letter and player, and a step control that shows the grid's letters after any
   number of edits, computed in the page from that list.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question.

9. Changes to spec 036 (former open question 1). This spec changes `server_config`
   and `main()`, while spec 036 (a `done` spec) says that every other uvicorn option
   is the default, that `main()` logs at `info`, and that `python -m nock` reads only
   `NOCK_HOST`, `NOCK_PORT` and `NOCK_DATABASE`. Options: (a) the lead refines spec
   036 with a dated note pointing here; (b) keep spec 036 and filter client
   addresses out of uvicorn's info lines, which depends on uvicorn's wording. Pick:
   (a). Already part of the spec above ("Logs (changes to spec 036)" and `main()`).
   The lead refines spec 036 before this spec's tests are written: `server_config`
   gets `access_log=False` and the default `log_level` `"warning"`; `main()` first
   checks `NOCK_OPERATOR_TOKEN` (`operator_token_from_env`); `python -m nock` also
   reads `NOCK_OPERATOR_TOKEN`. The test-writer then updates spec 036's tests that
   expect the `info` level before the implementer runs. (Note from the lead,
   2026-10-16: done: spec 036 holds these changes, each with a dated note, and its
   top note names the tests of its AC-7 and AC-10 that expect `info` and the setup
   of its AC-8 to AC-12, which now runs without `NOCK_OPERATOR_TOKEN` (preparation
   of spec 038).)
10. End-to-end sync latency (former open question 2). Options: (a) only the
    server's share, from the log; (b) also the browsers' measure, reported to the
    server, which needs a new client message (a change to spec 039) and storage.
    Pick: (a) now, (b) only if the server's share does not explain a bad game.
    Already part of the spec above (`relay_ms`, AC-5, AC-11, "Out of scope").

## Open questions

None.
