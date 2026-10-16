---
id: "032"
title: Room resume
status: approved
---

# 032 - Room resume

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

(Note from the lead, 2026-10-15: folded in. The answer is decision 11 (seat back, AC-7). Specs 012 and 017 are refined by the lead before this spec's tests are written. "Open questions" holds one new question that the seat back raised.)

(Note from the lead, 2026-10-16: the human answered that question on 2026-10-16 with option (b), "Join as Ana 2": it is decision 12, and "Open questions" says "None." Specs 012 (join step 4a and its edge cases) and 017 (its rule for a time-out in the join, AC-3 and the edge case "After a time-out") are refined for the seat back, with dated notes; spec 017 AC-3 changed, so the test-writer updates its tests before the implementer runs. From a check against specs 019 to 028, 035 and 036, "Seat back" now says what a seat back keeps and what starts afresh, and what a refusal after a time-out in the join gives; AC-7 gained the runs "Fresh record" and "Locked, time-out in the join"; the edge cases gained "Nothing logged at deletion" and "Team names and spec 028"; "New `fr.json` keys" and "Out of scope" gained a paragraph and an item.)

(Note from the lead, 2026-10-16: the lead decided that a mute survives a time-out and a seat back, decision 13, which the human may override: `PastPlayer` keeps `muted`, the seat back restores it, and AC-7 gained the run "Muted". Spec 038's table of what the server keeps lists the flag. Specs 014, 022 and 040 were reworded where they disagreed with this spec's members, seat back or criterion numbers.)

Epic E9 Accounts and resume (US-9.1) · Release: V1 · Epic depends on: E3
The FX-01 reference grid is in `specs/_reference.md`. The rooms engine, `RoomConfig`
and the fake-clock harness are defined in spec 011; joining, the stored identity and
the room page flow in spec 012; time-outs in spec 017; the store, `replay` and the
simulated restart in spec 018; the catalogue page in spec 004; room creation from the
catalogue in spec 010; the reveal budget in spec 024; the shared timer in spec 027.
The messages are those of spec 039. Accounts (spec 033) and game history (spec 029)
build on this spec.

## Goal

As a player, I want to come back to our grid tomorrow, so that a long grid doesn't need one sitting.

The MVP ships with guests only: a guest can do everything needed to finish a grid. Accounts arrive in V1 and only add memory across devices.

## Public interface

### Terms

- **Edit**: a logged entry whose event is a `letter_changed` (a letter written,
  erased, confirmed or undone) or a `cell_locked` (a cell locked by a check or a
  reveal). `nock.room.is_edit(entry)` tells it.
- **Last edit time** of a room: the largest `at` of its edit entries, or the time its
  life started when it has none (its `created_at`, or the registry's clock time for a
  room added with `add_room`, see `nock.hub`).
- **Expired**: a room is expired at time `now` when
  `now - last edit time > config.room_life_seconds` (30 days, 2,592,000 seconds).
  Exactly 30 days after the last edit it is still open. Joins, chat, flags, votes,
  presence changes and host actions do not move the last edit time.
- **Member** of a room: a player of its `players` or of its `past_players` (below).
  A removed player (spec 014) is not a member.
- **My rooms**, on a device: the rooms for which this device stores a valid identity
  `nock.identity.<CODE>` (spec 012). Spec 033 adds the rooms of an account.
- **Open** room: a room that exists, that is, has not been deleted. A solved room is
  open until it expires.

### `nock.room`

```python
# src/nock/room.py (additions)
from pydantic import AwareDatetime

MAX_PAST_PLAYERS: int = 100


class RoomConfig(RoomModel):
    # ... fields of specs 011 to 037
    room_life_seconds: float = Field(default=2_592_000.0, gt=0)  # spec 032 AC-1: 30 days
    expiry_sweep_seconds: float = Field(default=3_600.0, gt=0)  # how often the app deletes expired rooms


class PastPlayer(RoomModel):
    """A player who left the room by time-out or on purpose. Never sent as is."""

    player_id: PlayerId
    resume_token: ResumeToken  # secret, like PlayerRecord.resume_token
    nickname: Nickname
    colour: Colour
    muted: StrictBool = False  # the record's mute (specs 014, 022), kept for a seat back (decision 13)


class RoomState(RoomModel):
    # ... fields of specs 011 to 028
    past_players: tuple[PastPlayer, ...] = Field(
        default=(), max_length=MAX_PAST_PLAYERS
    )  # in the order they left, oldest first


class RoomKey(RoomModel):
    """A room and the resume token of one of its members, as a device keeps them."""

    code: RoomCode
    resume_token: ResumeToken


class RoomSummary(RoomModel):
    """What "My rooms" shows of one room. It holds no letter of the grid."""

    code: RoomCode
    grid_number: int | None  # catalogue number (spec 004); None for a bare grid
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    players: tuple[Nickname, ...]  # team_nicknames(state)
    last_activity_at: AwareDatetime  # the last edit time, in UTC
    solved: StrictBool


def is_edit(entry: LogEntry) -> bool:
    """Tell whether a logged entry is an edit: a letter_changed or a cell_locked."""


def member_id(state: RoomState, resume_token: str) -> str | None:
    """Return the id of the member whose resume token is `resume_token`.

    The players of `players`, then those of `past_players`, are compared with
    `secrets.compare_digest`. None when no member holds that token.
    """


def team_nicknames(state: RoomState) -> tuple[str, ...]:
    """Return the nicknames of the room's members, each once.

    First those of `past_players` in the order they left, then those of `players`
    in `players` order. A nickname equal to an earlier one under `casefold()` is
    left out.
    """


def room_summary(state: RoomState, last_edit_at: float) -> RoomSummary:
    """Return the summary of a room.

    `grid_number`, the grid's `width` and `height`, `team_nicknames(state)`,
    `last_edit_at` as a UTC datetime (`datetime.fromtimestamp(t, UTC)`), and
    `state.solved`.
    """
```

`replay` (spec 018 table), changed rows:

| Event | Effect on the state |
| --- | --- |
| `player_joined` | the player is appended to `players`, as before (spec 012). When `past_players` holds a `PastPlayer` with the same `player_id`, that record is removed from `past_players` (seat back, AC-7) |
| `player_left` | the player is removed from `players`, as before. Reason `removed`: their token is added to `removed_tokens` (spec 014). Reason `timed_out` or `left`: `PastPlayer(player_id, resume_token, nickname, colour, muted)` of their record is appended to `past_players`, after dropping the oldest one when it already holds `MAX_PAST_PLAYERS` |

(Note from the lead, 2026-10-15: the `player_joined` row was added with AC-7,
decision 11.) (Note from the lead, 2026-10-16: `PastPlayer` gained its `muted`
field, and the `player_left` row copies the record's `muted` into it; the row used
to build `PastPlayer(player_id, resume_token, nickname, colour)`, decision 13. The
`player_joined` row needs no change for it: spec 018 builds the record from the
event's view, `muted` included.)

The live time-out (spec 017, in `tick` and in `join_room`) builds its state with
`replay`, so a live room and a replayed one agree. A past player's token does not
resume them (spec 012 step 2 looks only at `players`); a join with it seats them
back, as "Seat back" below says. (Note from the lead, 2026-10-15: this sentence
used to say that a past player's token still does not resume, spec 017 being
unchanged, and pointed to open question 1; decision 11 settles it.)

### Seat back (`nock.room.join_room`)

(Note from the lead, 2026-10-15: this section was added with AC-7, decision 11.
Specs 012 (join steps) and 017 (AC-3 and its edge case "After a time-out") are
refined by the lead to match, with dated notes, before this spec's tests are
written.) (Note from the lead, 2026-10-16: done. Spec 017's rule for a time-out in
the join, which said that the join then goes on as a new player, was refined too.)

A join whose `resume_token` belongs to a past player of the room brings that player
back. Spec 012's join steps gain one step, step 4a, after step 4 (room full) and
before step 5 (nickname). (Note from the lead, 2026-10-16: "step 4a" was added:
spec 012 now holds the step under that number, so that its steps 5 and 6, which
other specs cite, keep theirs.) The rules:

- Steps before it, unchanged: step 1 (removed token, spec 014), step 2 (resume of a
  player of `players`, within spec 017's window), step 3 (room locked, spec 014) and
  step 4 (room full). So in a locked room the join gets
  `ErrorMessage(code=ROOM_LOCKED)` and in a full room
  `ErrorMessage(code=ROOM_FULL)`, each with `close_sender`, and with no entry and
  the state unchanged when the player was a past player before the join (for a
  time-out in the join itself, see "Time-out in the same step" below). The past
  player stays in `past_players`, and their token stays a member's (AC-4). (Note
  from the lead, 2026-10-16: "and with no entry and the state unchanged when the
  player was a past player before the join" used to read "no entry and the state
  unchanged", which does not hold when the join itself times the player out.)
- Seat back: `message.resume_token` equals, compared with `secrets.compare_digest`,
  the `resume_token` of a `PastPlayer` of `state.past_players`. With
  `seq = state.seq + 1`, a `PlayerRecord` is appended at the end of `players`, built
  as spec 012 step 6 builds a new player, except for these fields:
  - `player_id` and `resume_token`: the past player's. `new_player_id` and
    `new_resume_token` are not used.
  - `nickname`: the past player's, made unique by spec 012's "Duplicate nicknames"
    rule against the nicknames of `players`. So it is kept unless a player of
    `players` has it under `casefold()` (decision 12). (Note from the lead,
    2026-10-16: "new open question 1" became "decision 12", the human's answer.)
  - `colour`: the past player's when no player of `players` (connected or
    disconnected) has it, else the lowest index 0 to 7 that no player of `players`
    has, as spec 012 step 6 assigns it.
  - `muted`: the past player's (decision 13), so a player muted before their
    time-out comes back muted, and their view in the `player_joined` and in their
    snapshot says so. (Note from the lead, 2026-10-16: added, decision 13.)
  - `message.nickname` is ignored and not checked, as in a resume, so step 5 does not
    apply.

  The other fields are those of a new player: `is_host` is True only when no player
  of the room is host, `state = active`, `joined_seq = seq` and
  `last_input_at = last_seen_at = now`, and every other field of `PlayerRecord`
  takes its default ("What a seat back keeps, and what starts afresh" below). (Note
  from the lead, 2026-10-16: the clause from "and every other field" was added.)
  (Note from the lead, 2026-10-16: "`muted` is False" was taken out of this list,
  since the past player's `muted` is kept, decision 13.)
  The `PastPlayer` is removed from `past_players`. There is one entry,
  `LogEntry(at=now, event=PlayerJoined(seq, player=<its view>), resume_token=<the past player's token>)`,
  and `reply = (snapshot_for(new_state, player_id),)`. The other players receive the
  `player_joined`, as for any joiner. The hub binds the socket to the snapshot's
  `you` (spec 012), so the connection belongs to the player who came back.
- Letters: cells keep their `author` and `changed_by` ids (spec 017), so the
  authorship view (spec 019) and the recap (spec 028) see one person with one id.
- Time-out in the same step: when spec 017's resume step times out the token's
  player (disconnected for more than `resume_window_seconds`), that player becomes a
  past player in this step (a `player_left` with reason `timed_out`, then a
  `host_changed` when they were host and another player remains), and the join goes
  on with steps 3 and 4, then
  seats them back. So whether a player gets their seat back does not depend on
  whether a tick saw the time-out first. When step 3 then refuses the join (a
  locked room), the outcome keeps the time-out: its entries, its state, where the
  player is a past player whose token stays a member's (AC-4), and then the
  refusal's `ErrorMessage` and `close_sender`. A refusal undoes nothing that the
  step did before it, as a refusal keeps spec 013's wake entry. Step 4 never
  refuses after such a time-out, since the player who timed out held one of the
  seats. (Note from the lead, 2026-10-16: the last three sentences were added. The
  text did not say what a refusal after a time-out in the join gives; the code
  built for spec 017 already keeps the time-out then.)
- Removed players are never past players (the `player_left` row above), and step 1
  refuses their token (spec 014), so a removed player is never seated back.

What a seat back keeps, and what starts afresh, in the state that other specs
define. (Note from the lead, 2026-10-16: added from the check of this spec against
specs 019 to 028.)

- Letters (specs 019 and 028): every cell keeps its `author` and `changed_by`, so
  the player's letters are theirs again. Once the page applies the seat back's
  `player_joined`, the player is a player of its kept snapshot again, so spec 019
  gives their bands their colour index of now in place of the hatching, within
  300 ms as for the other events it follows (another index than before when a
  newcomer took theirs, "Seat back, colour taken"), and its clue bar names them by
  the nickname of that event. The recap gives them one row (spec 028's "Players").
- Chat (spec 022): the snapshot holds the whole history (`state.chat`), with the
  player's earlier lines under their id, so their page marks those lines as their
  own (`data-you`). Which lines count as unread is spec 022's rule: a page that
  stayed open counts the lines since its `lastSeenChatSeq`, and a page loaded anew
  counts none.
- Votes (spec 025): a vote's `eligible` and its ballots hold player ids, and the
  seat back keeps the id, so spec 025's rules apply as they are: the player is
  eligible only when their id is in `eligible`, and a ballot they cast before their
  time-out still counts, so a second one changes nothing. With the default
  thresholds, a player seated back while a vote is open was a past player when it
  opened, since a vote lasts 20 seconds and a time-out needs more than 300 seconds
  of disconnection (spec 017): they are not eligible, their page shows the buttons,
  and their ballot changes nothing, as for any player who joins during a vote
  (spec 025).
- Timer (spec 027): the seat back's `player_joined` is a join like any other for
  the timer rules: a started, paused timer of an unsolved room resumes at `now`
  (its rule 4), and the snapshot is built after it (its "The join step"). A
  time-out in the join changes no timer field, since the player who leaves was
  already disconnected.
- Offline edits (specs 017 and 020): a page that comes back after the time-out
  resends its pending edits, pencil edits and confirmations after the snapshot, as
  after a resume. Spec 017's stale rule compares `changed_by` with the same id, so
  the player's own earlier changes do not make them stale.
- Flag (spec 021): a player's flag goes with their record at the time-out (spec
  021's "departures"), and the seat back does not bring it back: `flag` is None, no
  `flag_changed` entry is written, and the snapshot's `flags` hold none of theirs.
- Undo (specs 018 and 020): `last_edit` is None, so an undo, of a pencil edit or a
  confirmation as of any other edit, answers `nothing_to_undo` until the player's
  next edit. Pencil mode belongs to the page (spec 020), and the server keeps
  nothing of it.
- Limits (specs 037 and 022): `recent_edits`, `recent_chat` and `recent_reactions`
  start empty. A time-out needs more than 300 seconds of disconnection, far longer
  than those windows (1, 10 and 10 seconds), so nothing they held still counted.
- Mute (specs 014 and 022): kept. `muted` is the past player's (decision 13), and
  it reaches the pages as any player's flag does: the player's own view in their
  snapshot (`snapshot_for` copies `muted` through `player_views`, spec 012) and in
  the others' `player_joined`. A muted player's page then disables the chat and
  the reactions, as spec 022 says of a page whose own `muted` is true in a
  snapshot, and the host's `mute-player` for them reads `t("chat.unmute")`; their
  `Chat` is refused `muted` and their `React` dropped (spec 022). (Note from the
  lead, 2026-10-16: added; this block first put `muted` among the fields that start
  afresh, decision 13.)
- Presence and host role (specs 013 and 014): `state` is `active`, `selection` and
  `disconnected_at` are None, and `is_host` follows spec 012's step 6 ("Host role
  and mute after a seat back"). (Note from the lead, 2026-10-16: this item read
  "Presence, mute and host role (specs 013, 022 and 014)" and said "`muted` is
  False"; the mute is the item above, decision 13.)
- The room's own state does not change: the reveal budget and `reveals_used`
  (spec 024), the settings, `removed_tokens` and the other players' records.

### `nock.store`

```python
# src/nock/store.py (changes and additions)
class RoomStore:
    def create_room(self, state: RoomState, *, last_edit_at: float | None = None) -> None:
        """Record a new room and `state` as its first snapshot (spec 018).

        The room's creation time is `state.created_at`. Its last edit time starts
        at `last_edit_at`, or at `state.created_at` when it is None.
        """

    def last_edit_at(self, code: str) -> float | None:
        """Return the room's last edit time, or None for an unknown room."""

    def expired_codes(self, before: float) -> list[str]:
        """Return the codes of the rooms whose last edit time is strictly less than
        `before`, in code-point order."""

    def delete_room(self, code: str) -> bool:
        """Delete the room, its snapshots, its log and its share token, in one
        transaction.

        Returns:
            True when the room existed. Its code is then free for a new room, and
            `code_for_share_token(<its share token>)` returns None (spec 028).
        """
```

- `append(code, entries)` sets, in the same transaction as the entries, the room's
  last edit time to the largest of its current value and the `at` of each entry for
  which `is_edit(entry)` is True. It never goes down.
- A database file written before this spec (the tables of spec 018, `rooms` holding
  only `code`) is upgraded when it is opened: each room gets its creation time (the
  `created_at` of its first snapshot) and its last edit time (the largest `at` of its
  logged edit entries, or its creation time when it has none). The layout is the
  implementer's choice (spec 018).
- Spec 018's rule "the log is never rewritten or truncated" keeps its exception for
  expiry: `delete_room` removes the whole room. That includes its share token (spec
  028): afterwards `code_for_share_token(<that token>)` returns None, so the share
  page and its API route answer 404, as for an unknown token (spec 028), and an old
  share link never reaches a new room that draws the same code. (Note from the lead,
  2026-10-16: added from spec 028's first review, because spec 028 stores share
  tokens and a deleted room must not leave one behind. The sentence used to say how
  spec 028 stores them, which is the implementer's choice (spec 028); only the rule
  stays: deleting a room deletes its share token (second review of spec 028).)

### `nock.hub`

```python
# src/nock/hub.py (additions)
ROOM_NOT_FOUND_CLOSE_CODE: int = 4404  # moved here from nock.server, which re-exports it


class RoomRegistry:
    @property
    def store(self) -> RoomStore:
        """The store of the rooms. The server's routes read logs through it."""

    def expire_rooms(self) -> list[str]:
        """Delete every room that is expired at `clock()`; return their codes,
        in code-point order."""

    def peek_room(self, code: str) -> RoomState | None:
        """Return the room's latest state without making it live.

        A live room gives its live state; a room only in the store gives
        `store.load_room(code)`, with no `after_restart` step and nothing logged.
        None when the room is unknown or expired (an expired room is deleted first,
        as by `expire_rooms`).
        """

    def member_id(self, code: str, resume_token: str) -> str | None:
        """Return `nock.room.member_id` of the room's latest state (as `peek_room`
        reads it), or None when the room is unknown or expired."""

    def room_summaries(self, keys: Sequence[RoomKey]) -> list[RoomSummary]:
        """Return the summaries of the rooms of `keys` that the key's token is a
        member of.

        One summary per code, whatever the number of keys naming it. A room that
        is unknown or expired, or whose keys hold no member's token, is left out.
        Order: `last_activity_at` newest first, then code in code-point order.
        """
```

Deleting a room, by `expire_rooms` or by a lookup:

1. When the room is live, its task stops, each of its connections is sent a close
   with `ROOM_NOT_FOUND_CLOSE_CODE` and no other message, and the room leaves the
   registry. An input still in its inbox is dropped. A step whose `append` happens
   after the deletion fails like any failed append (spec 018 AC-4): nothing is sent.
2. `store.delete_room(code)`.

Lookups: `find_room`, `room_state`, `connect`, `peek_room`, `member_id` and
`room_summaries` first check the room's last edit time against `clock()`. An expired
room is deleted at once, as above, and the lookup answers as for an unknown room. So
an expired room is never served, even between two sweeps.

`add_room(state)` (tests) records the room with
`store.create_room(state, last_edit_at=clock())`, so a room added that way starts
its life at the registry's clock time, whatever its `created_at`.
`register_room` keeps `create_room(state)`, since its `created_at` is `clock()`.

### `nock.server`

```python
# src/nock/server.py (additions)
from nock.hub import ROOM_NOT_FOUND_CLOSE_CODE  # re-exported, value unchanged (4404)
from nock.room import RoomKey, RoomSummary


class RoomSummariesRequest(BaseModel):
    """The body of POST /api/rooms/summaries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rooms: tuple[RoomKey, ...] = Field(max_length=100)
```

| Method and path | Answer |
| --- | --- |
| `POST /api/rooms/summaries`, a valid `RoomSummariesRequest` | 200, a JSON array: `model_dump(mode="json")` of each `rooms.room_summaries(body.rooms)`, in that order |
| `POST /api/rooms/summaries`, a body that is not valid (not JSON, more than 100 keys, a code breaking `RoomCode`, a token breaking `ResumeToken`, an extra key) | 422, FastAPI's validation body |

A summary in JSON:
`{"code": "XYZ789", "grid_number": 2, "width": 5, "height": 5, "players": ["Ana", "Bob"], "last_activity_at": "2026-10-14T08:30:00Z", "solved": false}`.

The route never tells why a room is left out (unknown, expired, removed player or
wrong token), so it cannot be used to guess room codes, and it is not counted by
spec 011's wrong-code throttle. It never makes a room live and logs nothing.

Expiry sweep: the app's lifespan runs `rooms.expire_rooms()` (in a worker thread,
`asyncio.to_thread`) once when the app starts, then every
`rooms.config.expiry_sweep_seconds` seconds until it stops, for the registry it
serves, given or created. A sweep that raises is logged, and the next one runs as
planned.

The room socket route keeps its rule "`room_state(code)` is None: close with 4404
and count a wrong code" (specs 011, 040); an expired room is now one of those.

### Client: "My rooms" on the catalogue page

The catalogue page (spec 004, `catalogue-page`) gains a section placed after its
`h1` and before the force filter. It exists only when this device stores at least
one valid identity (spec 012's rule: a JSON object with `player_id`,
`resume_token` and `nickname` as non-empty strings) under a key
`nock.identity.<CODE>` whose `<CODE>` matches `^[A-Z0-9]{6}$`.

- `data-testid="my-rooms"`: a `section` with an `h2` `t("my_rooms.heading")` and
  `data-state`: `loading` until the summaries answer, then `ready`, or `error` when a
  request fails or an answer is not a JSON array of summaries.
- On load the page sends `POST /api/rooms/summaries` with
  `{"rooms": [{"code": <CODE>, "resume_token": <stored token>}, ...]}`, one key per
  valid stored identity. With more than 100, it sends several requests of at most
  100 keys and lists the summaries of all of them, sorted as the server sorts them.
- `ready` with no summary: the section shows `t("my_rooms.empty")`. `loading`:
  `t("my_rooms.loading")`. `error`: `t("my_rooms.error")`. The rest of the catalogue
  page does not wait for this request and is not changed by its failure.
- One `data-testid="my-room"` element per summary, in the order received, with:

  | Attribute or child | Value |
  | --- | --- |
  | `data-code` | the room code |
  | `data-grid` | `grid_number` in decimal, `""` when it is null |
  | `data-solved` | `true` or `false` |
  | `data-last-activity` | `last_activity_at` as received |
  | grid label | `t("catalogue.item.number", {number})`, or `t("my_rooms.unnumbered")` when `grid_number` is null |
  | size | `t("catalogue.item.size", {width, height})` |
  | `data-testid="my-room-players"` | `t("my_rooms.players", {names})`, the nicknames joined by `", "`, inserted as text (spec 037) |
  | `data-testid="my-room-activity"` | `t("my_rooms.last_activity", {date, time})`: `date` by `new Intl.DateTimeFormat("fr-FR", {day: "numeric", month: "long", year: "numeric"})` and `time` by `new Intl.DateTimeFormat("fr-FR", {hour: "2-digit", minute: "2-digit"})`, both in the browser's time zone |
  | `data-testid="my-room-solved"` | only when solved: `t("catalogue.progress.finished")`, a text sign rather than a colour |
  | `data-testid="my-room-link"` | an `<a>` with `href` `/r/<code>`, text `t("my_rooms.open")`, `aria-label` `t("my_rooms.open_label", {code})` and `tabindex="0"`, since WebKit puts a link in the Tab order only with a `tabindex` (as spec 035 does for `share-link`) |

- Following `my-room-link` loads the room page, where spec 012's room page flow
  applies (a stored identity joins at once, case a).
- Rooms that the server leaves out are not listed. Their stored identities stay on the
  device (spec 014 keeps a removed player's identity on purpose).
- Accessibility (spec 035): the links are reachable with `Tab`, show spec 035 AC-2's
  visible focus, and every text meets the 4.5:1 contrast. Layout (spec 006 AC-5): no
  horizontal page scroll; long lists of names wrap.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `my_rooms.heading` | `Mes salons` |
| `my_rooms.loading` | `Chargement de vos salons…` |
| `my_rooms.empty` | `Aucun salon ouvert.` |
| `my_rooms.error` | `Impossible de charger vos salons.` |
| `my_rooms.unnumbered` | `Grille hors catalogue` |
| `my_rooms.players` | `Joueurs : {names}` |
| `my_rooms.last_activity` | `Dernière activité : {date} à {time}` |
| `my_rooms.open` | `Reprendre` |
| `my_rooms.open_label` | `Reprendre le salon {code}` |

Spec 035 AC-9's checker reads every `fr.json` value as a pattern and must still
flag its samples; none of these values matches them. None of their placeholders
stands for a number: `{names}`, `{date}`, `{time}` and `{code}` are in the list of
placeholders that match one or more characters (spec 035's "Language scan": a date
reads `14 octobre 2026`, a time `10:30`), so spec 035's list of number placeholders
does not change. The keys reused from spec 004 keep their number placeholders
(`{number}`, `{width}`, `{height}`). (Note from the lead, 2026-10-16: added from
the check of this spec against spec 035.)

### Test harness

- Times: `DAY = 86_400.0`, `LIFE = 30 * DAY`. Python criteria call `nock.room` and
  `RoomStore` directly with chosen times; store criteria use
  `RoomStore(tmp_path / "nock.sqlite3")`.
- Old database (AC-1): the test writes a file with `sqlite3` holding spec 018's
  three tables exactly as `src/nock/store.py` creates them today (`rooms` with only
  `code`), with rows built from `model_dump_json()`, then opens it with
  `RoomStore(path)`.
- Registries with a fake clock: `RoomRegistry(clock=fake_clock, store=RoomStore(path), config=...)`.
  "No tick changes anything" means `RoomConfig(idle_after_seconds=1e9,
  host_handover_seconds=1e9, silence_timeout_seconds=1e9, resume_window_seconds=1e9)`
  plus the fields the criterion names.
- WebSocket criteria open the app with `with TestClient(create_app(rooms=registry, dist_dir=tmp_path)) as client:`,
  so the lifespan, and with it the sweep, runs.
- Simulated restart (AC-3): spec 018's harness; process two's registry uses the same
  fake clock object, moved forward by the test.
- Browser with mocked routes (AC-5, AC-6): `page.route("**/api/rooms/summaries", handler)`
  answers with JSON built from `RoomSummary.model_dump(mode="json")` and records the
  request body; identities are seeded with `context.add_init_script` before
  `page.goto`; the context has `timezone_id="Europe/Paris"`. The catalogue request is
  served by the live server with an empty catalogue, or mocked the same way.
- Browser with live server (AC-3, AC-5): the `live_server`, `room_registry` and
  `catalogue` fixtures, with a catalogue holding FX-01 as published entry 1 (spec
  010's harness). Two players are two browser contexts (separate storage).
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only.
- Earlier tests: a room whose last edit time is more than 30 days before its
  registry's clock now expires. Rooms seeded with `add_room` are safe, since their
  life starts at the registry's clock. This spec's test-writer runs the whole suite
  and updates any earlier test that loads, on a registry, a room written to a store
  with times far before that registry's clock; their assertions do not change.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-9.1.1) (Python) A room's life runs 30 days from its last edit. With a store file and a FX-01 room created at `t0` (`new_room(code, grid, t0)`, then `create_room`): `last_edit_at(code) == t0`; after appending, one at a time, a `player_joined` at `t0 + 5`, a `letter_changed` at `t0 + 10`, a `chat_message` at `t0 + 20`, a `check_result` at `t0 + 25` and a `cell_locked` at `t0 + 30`, it reads `t0`, `t0 + 10`, `t0 + 10`, `t0 + 10` and `t0 + 30`; then `expired_codes(t0 + 30)` does not hold the code and `expired_codes(t0 + 30.5)` does, so the room is still open at `t0 + 30 + LIFE` and expired at `t0 + 30.5 + LIFE`. `is_edit` is True for a `letter_changed` with a letter, a `letter_changed` erasing, a `cell_locked` of a check and one of a reveal, and False for `player_joined`, `player_state_changed`, `chat_message`, `check_result`, `settings_changed` and `grid_solved`. `create_room(state, last_edit_at=t0 + 99)` starts the last edit time at `t0 + 99`. A file written before this spec (see "Test harness") holding room A, created at `t0` with a `letter_changed` at `t0 + 10` then a `player_state_changed` at `t0 + 50`, and room B, created at `t0 + 1` with no entry, opened with `RoomStore(path)`, gives `last_edit_at(A) == t0 + 10` and `last_edit_at(B) == t0 + 1`, and an edit appended to B at `t0 + 60` makes it `t0 + 60`.
- **AC-2** (AC-9.1.1) (Python; WebSocket with a fake clock; HTTP with a fake clock) An expired room is deleted, and nobody can reach it any more. Python: a registry with a fake clock and a store file holds room A (last edit at `t0 + 10`) and room B (last edit at `t0 + 20`), each with a share token (spec 028), `TOKEN_A` and `TOKEN_B`: the token `register_room` gave the room (read from `room_state(<code>).share_token` before any expiry), or the `share_token` of the state given to `add_room`. `store.code_for_share_token(TOKEN_A)` is A and `store.code_for_share_token(TOKEN_B)` is B. With the clock at `t0 + 10 + LIFE`, `expire_rooms()` returns `[]`; at `t0 + 11 + LIFE` it returns `[A]`, then `store.has_room(A)` is False, `store.read_log(A) == []`, `store.load_room(A)` is None, `store.code_for_share_token(TOKEN_A)` is None, `room_state(A)`, `find_room(A)` and `peek_room(A)` are None, B still loads with its log and `store.code_for_share_token(TOKEN_B)` is still B, and `add_room` of a fresh state with A's code succeeds. Without any call of `expire_rooms`, with the clock moved to `t0 + 21 + LIFE`, `room_state(B)` is None, `store.has_room(B)` is False and `store.code_for_share_token(TOKEN_B)` is None. (Note from the lead, 2026-10-16: added from spec 028's first review, because spec 028 stores share tokens and a deleted room must not leave one behind. The note used to say how spec 028 stores them, which is the implementer's choice (spec 028). Wording only: the criterion is unchanged (second review of spec 028).) WebSocket: with no tick changing anything and `expiry_sweep_seconds=0.05`, `Ana` and `Bob` join a FX-01 room and Ana writes `T` at (1, 0); after `advance(LIFE + 1)`, both sockets are closed with code 4404 within 1 second of real time, and neither receives a message after Ana's `letter_changed`; a new socket to the same code is then closed with 4404 before any message. HTTP: on a registry of its own, with a fake clock starting at `t0` and `expiry_sweep_seconds` left at its default, over a store file written as spec 028 AC-9 writes its file: a FX-01 room created with `new_room("ABC123", fx01_grid, t0, grid_number=1, share_token="tok_ABCDEFGHIJKLMNOP")` and the entries of spec 028's `PLAY_R` appended, with `t0` as its `NOW`. That room is solved, its last edit is at `t0 + 754`, and it is only in the store. The app is `TestClient(create_app(rooms=registry, dist_dir=tmp_path))`, with an `index.html` written in `tmp_path`. With the clock at `t0 + 754 + LIFE`, `GET /recap/tok_ABCDEFGHIJKLMNOP` answers 200 with `index.html` and `GET /api/recaps/tok_ABCDEFGHIJKLMNOP` answers 200 with a body that parses to `PublicRecap(grid_number=1, elapsed_ms=754000, team=("Ana", "Bob"))`, so the link works until the room expires. With the clock at `t0 + 755 + LIFE` and no call of `expire_rooms`, both requests answer 404 with `{"detail": "Not Found"}`, exactly as `GET /recap/tok_unknown_0123456789` and `GET /api/recaps/tok_unknown_0123456789` do (spec 028 AC-8). (Note from the lead, 2026-10-16: the HTTP part and the kind "HTTP" were added. Spec 028's edge case "Expiry" says that once this spec deletes a room, its share link answers 404, and no criterion checked it. Rooms A and B are not solved, so their share links answer 404 before the expiry too; the check uses a solved room built as spec 028 AC-9 builds its room (first review of spec 028).)
- **AC-3** (AC-9.1.2) (WebSocket with a fake clock and a simulated restart; browser with live server) Opening the link on another device shows the same letters, timer and hint budget, also the next day and after a restart. WebSocket: in process one (store file, fake clock), a FX-01 room is created at `t0`; `Ana` joins at `t0`, writes `T` at (1, 0) at `t0 + 10` and `A` at (1, 1) at `t0 + 20`, reveals the letter (4, 4) at `t0 + 30` (spec 024), and her socket closes at `t0 + 100`; process one stops. The clock moves to `t0 + 100 + DAY` and process two starts on the same file. A client with no token (another device) joins as `Bob`: its snapshot's `grid` equals `grid_state` of the room as process one left it (`T` and `A` authored by Ana's id, `T` at (4, 4) locked and revealed), its `reveal_budget` is `RevealBudget(letters=4, words=1)`, and its `timer_elapsed_ms` is within 1,000 of 90,000, since the timer ran from the first letter at `t0 + 10` until nobody was connected at `t0 + 100` (spec 027 AC-1, AC-2). Then a client joining with Ana's token (her device; she timed out, so she is seated back, AC-7) receives a snapshot whose `you` is Ana's player id of process one, with the same `grid` and `reveal_budget` as Bob's, and a `timer_elapsed_ms` within 1,000 of Bob's. (Note from the lead, 2026-10-15: "she joins as a new player, spec 017" became "she is seated back, AC-7", and the check of `you` was added, which shows that past players survive the restart; decision 11.) Browser: on the live server, page 1 (context 1) enters a FX-01 room as `Ana`, types `T` then `A` from (1, 0) across, and is closed; page 2 in context 2 (empty storage) opens the room's link, enters as `Bob`, and its cells (1, 0) and (1, 1) have `data-letter` `T` and `A`.
- **AC-4** (AC-9.1.3) (Python; HTTP) The server gives a room's summary only to a member of the room. Python: a `player_left` with reason `timed_out` replayed on a state holding `Bob` (token `TB`, colour 1) removes him from `players` and appends `PastPlayer(player_id=<Bob>, resume_token=TB, nickname="Bob", colour=1)` to `past_players`; with reason `removed` nothing is appended and `TB` goes to `removed_tokens`; on a state with `MAX_PAST_PLAYERS` past players, one more time-out drops the oldest and keeps 100. `member_id` gives Bob's id for `TB` after his time-out, `None` after his removal, and `None` for an unknown token. With past players `Bob`, `ana` and players `Ana`, `Cy`, `team_nicknames` is `("Bob", "ana", "Cy")`. HTTP: on room A (FX-01, grid number 1) where `Ana` (token `TA`), `Bob` (`TB`) and `Cy` (`TC`) joined, Ana wrote `T` at (1, 0) at `t0 + 10`, Ana removed Cy and Bob timed out, and room B (FX-01 added with `grid_number` None) where `Dan` (`TD`) wrote a letter at `t0 + 50`: `POST /api/rooms/summaries` with A's code and `TA` answers 200 with a JSON array of one item, which `RoomSummary.model_validate` turns into `RoomSummary(code=A, grid_number=1, width=5, height=5, players=("Bob", "Ana"), last_activity_at=<t0 + 10 as a UTC datetime>, solved=False)` (compared as models, so that fields a later spec adds with a default, such as spec 029's, keep it passing); with `TB` the same; with `TC`, with a token no player ever had, or with the code `ZZZZZZ`, `[]`; with A by `TA`, B by `TD` and A again by `TB`, two summaries, B then A. A body with 101 keys, a code `abc`, a token of 15 characters or an extra key answers 422. A room that only the store holds keeps the same log after the request. An expired room is left out and deleted.
- **AC-5** (AC-9.1.3) (browser with mocked routes; browser with live server) "My rooms" lists my open rooms with their grid, players and last activity. Mocked: with valid identities stored for `XYZ789` and `ABC234` and a corrupt `nock.identity.QQQQQQ` (`not json`), the page sends one `POST /api/rooms/summaries` whose body holds exactly the keys of `XYZ789` and `ABC234` with their stored tokens. When the answer is the summary of `XYZ789` (grid 2, 5 by 5, players `Ana`, `Bob`, last activity `2026-10-14T08:30:00Z`, not solved) then that of `ABC234` (grid null, 13 by 17, players `Ana`, last activity `2026-10-13T20:05:00Z`, solved), `my-rooms` reaches `data-state="ready"` with two `my-room` items in that order. The first has `data-code="XYZ789"`, `data-grid="2"`, `data-solved="false"`, the texts `Grille n° 2`, `5 × 5`, `Joueurs : Ana, Bob` and `Dernière activité : 14 octobre 2026 à 10:30`, no `my-room-solved`, and a `my-room-link` with `href="/r/XYZ789"`, text `Reprendre` and `aria-label` `Reprendre le salon XYZ789`. The second has `data-grid=""`, the texts `Grille hors catalogue`, `13 × 17`, `Joueurs : Ana` and `Dernière activité : 13 octobre 2026 à 22:05`, and a `my-room-solved` reading `Terminée`. An answer `[]` shows `fr.json["my_rooms.empty"]`; an answer with status 500 gives `data-state="error"` and `fr.json["my_rooms.error"]`, while the catalogue list still reaches `data-state="ready"`. With no identity stored, the page has no `my-rooms` element and sends no summaries request. Live: Ana (context 1) starts FX-01 from the catalogue (spec 010) and types `T` at (1, 0); Bob (context 2) joins her room; Ana's context then opens `/`: `my-rooms` holds one `my-room` with her room's code, `data-grid="1"` and the text `Joueurs : Ana, Bob`; clicking its `my-room-link` opens `/r/<code>`, whose room page reaches `data-status="joined"` with the same `data-you` as before, without showing `nickname-form`.
- **AC-6** (new) (browser with mocked routes; keyboard only for the walk) "My rooms" meets spec 035 and the window sizes of spec 006 AC-5. With the two summaries of AC-5, at 1280 by 720 and at 360 by 740: spec 035's contrast scan and language scan find no offending element on `/`; keyboard only, `tab_to` (spec 035 "Test harness") reaches each `my-room-link`, which then shows spec 035 AC-2's outline (style neither `none` nor `auto`, width at least 2 px, colour of contrast at least 3:1 against white), and `Enter` on the first loads `/r/XYZ789`. At each window size of spec 006 AC-5, `document.documentElement.scrollWidth <= window.innerWidth`, also when the first summary lists 8 players whose nicknames have 20 characters each.
- **AC-7** (new, decision 11) (Python; WebSocket and HTTP with a fake clock) A player who comes back after spec 017's time-out with their stored token gets their seat back: the same player id, letters and mute flag, and the same nickname and colour while no player of the room has them (else spec 012's suffix and the lowest free colour). The rules are those of "Seat back". (Note from the lead, 2026-10-16: "the same player id, nickname and letters, and the same colour while no player of the room has it" became the text above, which says decision 12's suffix.) (Note from the lead, 2026-10-16: "and mute flag" was added, decision 13.) Python, on a FX-01 room with the `RoomConfig` of "no tick changes anything" (see "Test harness") except `resume_window_seconds`, left at its default of 300: `Ana` (token `TA`), `Bob` (`TB`) and `Cy` (`TC`) join at `t0` (seq 1 to 3, colours 0 to 2, Ana host); Ana writes `T` at (1, 0) (seq 4); her connection closes at `t0 + 10` (`disconnect_player`, seq 5); `tick` at `t0 + 311` gives `PlayerLeft(player_id=<Ana>, reason="timed_out")` (seq 6) then `HostChanged(player_id=<Bob>)` (seq 7), and `past_players` holds Ana. Then:
  - Seat back: `join_room` with `Join(nickname="Autre", resume_token=TA)` at `t0 + 400`, `new_player_id="pNEW"` and a fresh `new_resume_token`, gives exactly one entry, a `PlayerJoined` with seq 8 whose `player` is `PlayerView(player_id=<Ana>, nickname="Ana", colour=0, state="active", is_host=False, muted=False, selection=None)`, logged with `resume_token == TA`. Its reply is one `Snapshot` with `you == <Ana>` and `resume_token == TA`, and `close_sender` is False. In the new state Ana is last in `players` with `joined_seq == 8`, `past_players` is empty, (1, 0) has `author == <Ana>`, `member_id(state, TA) == <Ana>`, and no player has the id `pNEW`. Replaying every entry from `new_room` gives the same `past_players` and the same player ids, nicknames, colours and `is_host` in `players`.
  - Fresh record: in a run where Ana flags IDES (`Flag(clue=ClueRef(row=0, column=3, clue_index=0))`) before her disconnection, the seat back gives exactly one entry, its `PlayerJoined`, with no `FlagChanged`; in the new state Ana's `flag` is None, and the snapshot's `flags` is empty. An `Undo` from Ana right after it is answered `nothing_to_undo`, although her `T` at (1, 0) has not changed since she wrote it. (Note from the lead, 2026-10-16: added with "What a seat back keeps, and what starts afresh".)
  - Muted: in a run where Ana, host, sends `MutePlayer(player_id=<Cy>, muted=True)` at `t0 + 5` (seq 5) and it is Cy whose connection closes at `t0 + 10` (seq 6), the `tick` at `t0 + 311` gives `PlayerLeft(player_id=<Cy>, reason="timed_out")` (seq 7) alone, and `past_players` is `(PastPlayer(player_id=<Cy>, resume_token=TC, nickname="Cy", colour=2, muted=True),)`. Cy's join with `TC` at `t0 + 400` then gives exactly one entry, a `PlayerJoined` with seq 8 whose `player` is `PlayerView(player_id=<Cy>, nickname="Cy", colour=2, state="active", is_host=False, muted=True, selection=None)`, and a reply whose `Snapshot` has `you == <Cy>` and, in its `players`, Cy's view with `muted` True. A `Chat(text="salut")` from Cy right after is answered with one `ErrorMessage(code="muted")` and gives no entry (spec 022). Ana's `MutePlayer(player_id=<Cy>, muted=False)` then gives one `PlayerMuted(player_id=<Cy>, muted=False)`, and Cy's next `Chat(text="salut")` gives its `ChatMessage`. Replaying every entry from `new_room` gives, after the time-out, the same `past_players`, and after the seat back, Cy in `players` with `muted` True and an empty `past_players`. (Note from the lead, 2026-10-16: added, decision 13.)
  - Colour taken: in a second run, after the time-out, `Dan` joins and gets colour 0 (spec 012). Ana's join with `TA` then gives her old id, the nickname `Ana` and colour 3, the lowest index that no player has.
  - Nickname taken: in a third run, after the time-out, `ana` joins and keeps the nickname `ana`, since no player has it, with colour 0. Ana's join with `TA` then gives her old id, the nickname `Ana 2` (spec 012's duplicate rule; decision 12) and colour 3. (Note from the lead, 2026-10-16: "new open question 1" became "decision 12", the human's answer.)
  - Full: in a run where six more players join after the time-out, so that `players` holds 8, Ana's join with `TA` gives `reply == (ErrorMessage(code="room_full", ...),)` (code compared), `close_sender` True, no entry and the same state. Ana stays in `past_players`, and `member_id(state, TA)` is still her id.
  - Locked: in a run where Bob, host since the time-out, sends `LockRoom(locked=True)`, Ana's join with `TA` gives `ErrorMessage(code="room_locked")` with the same checks as a full room. After Bob sends `LockRoom(locked=False)`, the same join seats her back.
  - Time-out in the join: in a run with no tick after the disconnection, Ana's join with `TA` at `t0 + 310.5` (300.5 seconds after her disconnection) gives three entries: `PlayerLeft(player_id=<Ana>, reason="timed_out")`, `HostChanged(player_id=<Bob>)`, then a `PlayerJoined` of `<Ana>` with nickname `Ana`, colour 0 and `is_host` False. Its snapshot has `you == <Ana>`.
  - Locked, time-out in the join: in a run where Ana, still host, sends `LockRoom(locked=True)` before her disconnection and no tick follows the disconnection, Ana's join with `TA` at `t0 + 310.5` gives two entries, `PlayerLeft(player_id=<Ana>, reason="timed_out")` then `HostChanged(player_id=<Bob>)`, `reply == (ErrorMessage(code="room_locked", ...),)` (code compared) and `close_sender` True; in its state Ana is in `past_players`, Bob is host, and `member_id(state, TA)` is Ana's id. After Bob sends `LockRoom(locked=False)`, the same join seats her back. (Note from the lead, 2026-10-16: added with the refusal rule of "Time-out in the same step".)
  - Removed: in a run where Ana removes Cy (spec 014) at `t0 + 5`, before her disconnection, a join with `TC` at `t0 + 400` gets `ErrorMessage(code="removed")` with `close_sender` True and no entry, and `past_players` holds Ana only.

  WebSocket and HTTP: on a registry with a fake clock, a store file and the same `RoomConfig` with `tick_seconds=0.05`, clients A (`Ana`) and B (`Bob`) join a FX-01 room and A writes `T` at (1, 0); A's socket closes; after `advance(301)`, B receives `PlayerLeft(player_id=<A>, reason="timed_out")` within 1 second of real time. A new socket that sends `{"type": "join", "nickname": "Autre", "resume_token": <A's token>}` receives a `Snapshot` with `you == <A>`, `resume_token` equal to A's token, A's view with the nickname `Ana` and colour 0, and (1, 0) with `author == <A>`; B receives a `player_joined` whose `player.player_id` is `<A>`. Then `POST /api/rooms/summaries` with the room's code and A's token answers one summary whose `players` is `("Bob", "Ana")`, each name once. (Note from the lead, 2026-10-15: added, decision 11.)

## Edge cases and errors

- Exactly 30 days (AC-1): `now - last edit time == LIFE` is still open; any more is
  expired. The sweep runs every hour, so a room nobody looks up is deleted between 30
  days and 30 days and one hour after its last edit; a lookup deletes it at once.
- Clock going back (AC-1): the last edit time never goes down; an edit entry whose
  `at` is older than the stored value changes nothing.
- No edit at all (AC-1): a room created and never edited expires 30 days after its
  life started.
- What does not count (AC-1): joins, chat, flags, reactions, votes, presence changes,
  host actions, checks that lock nothing (a `check_result` alone) and completion
  events. Their entries are logged as before; only edits move the last edit time.
- Players connected at expiry (AC-2): the room is deleted all the same and their
  sockets are closed with 4404, a final close (spec 017), so each page shows
  `fr.json["room.status.not_found"]` (spec 040). A page reloaded later gets 4404 too.
- Step in flight at deletion (AC-2): its `append` fails (unknown room) and the step is
  dropped (spec 018 AC-4); nothing re-creates the room.
- Nothing logged at deletion (AC-2): a deletion runs no rule step. The closes of its
  sockets run no `disconnect_player`, so no entry is written, and no player, vote
  or timer changes before the room goes (no `player_state_changed`, no time-out, no
  pause of spec 027's timer). The room's whole state goes with it: its chat (spec
  022), flags (spec 021), open vote (spec 025), timer (spec 027) and share token
  (spec 028). (Note from the lead, 2026-10-16: added from the check of this spec
  against specs 021 to 028.)
- Code reused (AC-2): after deletion the code can be drawn again (spec 011). A device
  that still stores an identity for the old room joins the new one as a new player:
  its token is unknown there (spec 012, "Unknown resume token").
- Throttle (AC-2): a socket to an expired code counts as a wrong code (spec 011).
- Sweep failure (AC-2): logged; the next sweep runs. Lookups still refuse expired
  rooms meanwhile.
- After a restart (AC-3): the room loads from the store (spec 018), its players are
  disconnected by `after_restart`, and the first tick of the new task times out
  those disconnected for more than 5 minutes (spec 017), so they become past players
  before the next joiner's snapshot.
- Timer (AC-3): its value is spec 027's. This spec checks only that another device,
  or the same device the next day, gets the value the room kept.
- Past players (AC-4): a past player's token makes them a member for summaries
  (spec 029 and 034 use the same rule), and a join with it seats them back (AC-7).
  A player who is seated back leaves `past_players`, so a player who times out
  again has one past record, under their one id. Removed players are never past
  players. (Note from the lead, 2026-10-15: "but it does not resume them in the
  room (spec 017; open question 1). A player who times out again under a new id
  adds another past record" became the text above, decision 11.)
- Seat back, colour taken (AC-7): a newcomer may take the colour of a past player
  (spec 012 gives the lowest free index). The past player then comes back with the
  lowest index that no player of `players` has, and their letters show that colour
  in the authorship view (spec 019). (Note from the lead, 2026-10-15: added,
  decision 11.)
- Seat back, nickname taken (AC-7): a newcomer may take the nickname of a past
  player, since spec 012 only compares with `players`. The past player then comes
  back with spec 012's suffix (`Ana 2`), and their stored identity takes the new
  nickname from the next snapshot (spec 012). See decision 12. (Note from the lead,
  2026-10-15: added, decision 11.) (Note from the lead, 2026-10-16: "See new open
  question 1" became "See decision 12", the human's answer.)
- Seat back in a full or locked room (AC-7): refused as a newcomer would be, with
  `room_full` or `room_locked`, which is final on the page (spec 017), so it shows
  `data-status="full"` (spec 012) or `data-status="locked"` (spec 014). The player stays
  a past player and a member: "My rooms" still lists the room, and the same token
  seats them back once a seat is free or the room is unlocked. (Note from the lead,
  2026-10-15: added, decision 11.)
- Host role and mute after a seat back (AC-7): the host role is not given back
  (spec 014: a host who comes back after the hand-over is an ordinary player): the
  player is host only when no player of the room is host, which spec 014 allows
  only in a room that nobody else is in, as for any joiner (spec 012 step 6).
  The mute is given back: `PastPlayer` keeps `muted`, so a player muted before
  their time-out comes back muted, until a host unmutes them (spec 022). A muted
  player who comes back to a room nobody else is in is host, and stays muted until
  another host unmutes them, since spec 014 refuses a mute on one's own id (spec
  022's "Muted host"). (Note from the lead, 2026-10-15: added, decision 11.)
  (Note from the lead, 2026-10-16: the clause from "the player is host only" was
  added; the item said only that the role is not given back, while a player who
  comes back to a room nobody else is in becomes host as any joiner.) (Note from
  the lead, 2026-10-16: the mute sentences used to read "`muted` starts False, as
  for a new player, since `PastPlayer` keeps no flag. The host can mute the player
  again (spec 022).", decision 13.)
- Removing or muting a past player (AC-7): not possible, since spec 014's
  `remove_player` and `mute_player` target players of `players` (`invalid_target`
  otherwise). Once seated back, the player can be removed or muted like any other,
  and a removed player's token is then refused (spec 014). (Note from the lead,
  2026-10-15: added, decision 11.) (Note from the lead, 2026-10-16: muting was
  added; the item spoke of removing only.) A past player's mute thus stays as it
  was when they left, and a host changes it once they are seated back (decision
  13). (Note from the lead, 2026-10-16: the sentence before this note was added,
  decision 13.)
- Past record dropped by the cap (AC-4, AC-7): a past player dropped by the cap of
  100 is no longer known. Their token then matches nobody, and the join makes a new
  player (spec 012, "Unknown resume token"). (Note from the lead, 2026-10-15: added,
  decision 11.)
- Two devices of one player (AC-7): the first device whose join seats the player
  back takes the seat. The other device's join with the same token is then a resume
  of a player of `players` (spec 012 step 2), and the older socket is closed with
  4001 (`replaced`). (Note from the lead, 2026-10-15: added, decision 11.)
- Cap (AC-4): with 100 past players, the oldest is dropped; that device's token no
  longer gets the summary, so the room leaves its "My rooms".
- Duplicate keys (AC-4): several keys for one room give one summary; it is enough that
  one of them is a member's.
- Team names and spec 028 (AC-4): `team_nicknames` compares nicknames under
  `casefold()`, so of `Ana` and `ana` it keeps the one that comes first in its
  order and leaves out the other. Spec 028's team (its share page) keeps each
  nickname once as an exact string, in join order, so the share page of the same
  room names both. The two lists serve two pages and may differ in their names and
  their order; spec 028 is not changed. (Note from the lead, 2026-10-16: added from
  the check of this spec against spec 028.)
- Former players (AC-4): spec 033 may give an erased player the nickname `--`; it is
  kept in `players` of the summary like any nickname, and the page shows it as spec
  033 says.
- Corrupt identity (AC-5): spec 012's rule; it is not sent and does not count for
  showing the section.
- Identity of another room code shape (AC-5): a key such as `nock.identity.abc` is
  ignored (its code breaks `^[A-Z0-9]{6}$`).
- Time zone (AC-5): the date and time are those of the browser's time zone, unlike
  the publication dates of spec 004, which are dates without a time.
- Nicknames (AC-5): inserted as text, never as HTML (spec 037 AC-4).
- No room returned (AC-5): the section stays, with `my_rooms.empty`.
- Answers stay on the server (AC-4): a summary holds no letter, no clue and no answer
  (spec 037 "What a browser may receive").

## Out of scope

- Payments and subscriptions (epic E9).
- Optional account: spec 033 (rooms of an account on every device).
- Catching up after an absence: spec 034.
- The list of finished grids after their rooms are deleted: spec 029.
- Privacy measures of deletion (secure delete, logs, what the database keeps):
  spec 038.
- A warning before expiry, extending a room by hand, restoring a deleted room,
  backups.
- Giving back the host role after a time-out: AC-7 seats a player back as an
  ordinary player, who is host only in a room that nobody else is in, as any
  joiner. Their `muted` flag, though, is kept (decision 13). (Note from the lead,
  2026-10-15: this line used to read "Getting back one's old player id, colour and
  authorship after a time-out (open question 1)", which AC-7 now does; decision
  11.) (Note from the lead, 2026-10-16: the clause from "who is host only" was
  added.) (Note from the lead, 2026-10-16: "or the `muted` flag" and "unmuted"
  were taken out, and the sentence on the kept flag was added, decision 13.)
- Setting the room life or the sweep interval from the environment. This spec reads
  no environment variable: `room_life_seconds` and `expiry_sweep_seconds` are
  `RoomConfig` fields, whose defaults the app uses, and the sweep deletes from the
  store that spec 018 opens from `NOCK_DATABASE`. Spec 036's rules for the
  variables of `python -m nock` thus add nothing here. (Note from the lead,
  2026-10-16: added from the check of this spec against spec 036.)
- Leaving a room for good, or removing a room from "My rooms".
- Clearing the device's stored identities of deleted rooms.
- Sorting or filtering "My rooms".

## Work packages

None.

## Decisions

Proposed by the spec-writer on 2026-10-14 for the Phase 6 refine, with the human's
answer of the same day (numeric thresholds: keep the backlog defaults). They are
part of the spec above and are approved with it.

1. What counts as an edit (AC-1). Options: a `letter_changed` only; any change of a
   cell (`letter_changed` or `cell_locked`); any event. Pick: any change of a cell,
   which is what "edit" means for the grid (spec 018's `changed_seq` follows the
   same two events). Joins and chat do not keep a room alive, as the backlog says
   "after its last edit".
2. Where the last edit time lives (AC-1). Pick: in the store, updated by `append` in
   the same transaction, so the sweep can find expired rooms without loading them.
   Old database files are upgraded on open.
3. When a room is deleted (AC-2). Pick: an hourly sweep for privacy (spec 038), and a
   check at every lookup so that the 30-day rule is exact for players. A room with
   connected players is deleted all the same, with the final close 4404, so a
   forgotten open tab cannot keep data forever.
4. Seeded rooms (harness). `add_room` starts a room's life at the registry's clock,
   so that tests seeding rooms with `created_at = 1_000_000.0` on a real clock keep
   working; `add_room` is a test seam.
5. Members (AC-4). Pick: current and past players, so that a device keeps its room
   in "My rooms" after spec 017's 5-minute time-out. Removed players are left out.
   `past_players` is capped at 100 to bound the state.
6. Summaries over HTTP (AC-4). Options: an HTTP route, or a new WebSocket message
   (a change to spec 039). Pick: `POST /api/rooms/summaries`: tokens travel in the
   body, never in a URL that logs could keep; the answer never says why a room is
   left out, so it is no oracle for room codes and needs no throttle.
7. "Open rooms" (AC-5). Pick: the rooms that exist, solved ones included, with a
   "Terminée" text, since AC-1 calls a room "open" until it is deleted. Finished
   grids are also listed by spec 029 after their rooms are gone.
8. "Last activity" (AC-5). Pick: the last edit time, the same time that drives
   expiry.
9. "Players" (AC-5). Pick: the room's members, past then current, each nickname once,
   so that the team shows the next day, when everyone has timed out.
10. Close code. `ROOM_NOT_FOUND_CLOSE_CODE` moves to `nock.hub`, which closes the
    sockets of a deleted room; `nock.server` re-exports it, so spec 040's and 011's
    tests are unchanged.

Decided by the human on 2026-10-14, who approved the recommended answer to every
open question.

11. Getting one's player back after a time-out (former open question 1). Spec 017
    makes a player who stays away more than 5 minutes leave the room, so a player
    who came back the next day with their stored token joined as a new player, and
    the authorship view (spec 019), the recap (spec 028) and an account's "same
    seat, colour and authorship" (spec 033 AC-2) split one person in two. Options:
    (a) keep spec 017 as it is; (b) a join whose token belongs to a past player
    brings that player back. Pick: (b). What it changed: the "Seat back" section,
    the `player_joined` row of `replay`, AC-7 (new), AC-3's join with Ana's token,
    the edge cases on past players and seat backs, and "Out of scope". The player
    comes back with the same id and nickname (spec 012's suffix when a player took
    the nickname meanwhile, decision 12; note from the lead, 2026-10-16: this
    parenthesis used to end with "open question 1", which the human answered), and
    the same colour when no player of `players` has it, connected or disconnected,
    since spec 012 keeps a disconnected
    player's colour (else the lowest free index, as spec 012 assigns it), as long as
    the room is neither full nor locked. A full or locked room refuses the join with
    spec 012's and 014's refusals (`room_full`, `room_locked`). A removed player is
    never seated back (spec 012's step 1, built by spec 014). Their letters keep their author
    id, so specs 019 and 028 see one person. The lead refines spec 012 (join steps,
    and the edge cases on colours, duplicates, unknown tokens, full rooms and the
    order of refusals) and spec 017 (AC-3 and its edge case "After a time-out"),
    with dated notes, before this spec's tests are written; the test-writer then
    updates their tests before the implementer runs.

Decided by the human on 2026-10-16. It is already part of the spec above. (Note
from the lead, 2026-10-16: this group was added; its item was open question 1.)

12. Nickname taken while a player was away (AC-7, former open question 1, raised on
    2026-10-15). Spec 012 makes nicknames unique only among `players`, so a
    newcomer may take the nickname of a past player (`ana` after `Ana` timed out).
    When the past player is seated back, options: (a) keep their nickname as it
    was, so two players of `players` have the same nickname under `casefold()`,
    against spec 012's rule; (b) apply spec 012's duplicate rule, as for a
    newcomer, so they come back as `Ana 2`, with the same id, colour rule and
    letters. Pick: (b), the human's answer ("Join as Ana 2"). "Seat back", AC-7's
    "Nickname taken" and the edge case "Seat back, nickname taken" follow it, and
    spec 012's step 4a and its edge case "Duplicate check" say the same.

Decided by the lead on 2026-10-16, after the check of this spec against spec 022.
The human may override it. It is already part of the spec above. (Note from the
lead, 2026-10-16: this group was added.)

13. The mute after a time-out and a seat back (AC-7). Since decision 11, a player
    who times out and comes back with their token is the same player, with the
    same id, letters and nickname. Options: (a) `muted` starts False at the seat
    back, as for a new player, since `PastPlayer` keeps no flag, and a host mutes
    the player again; (b) `PastPlayer` keeps the record's `muted`, and the seat
    back restores it. Pick: (b). The mute is the host's tool against abuse (spec
    022, its decisions 1 and 3), and it already survives a restart (spec 014
    AC-6); with (a), a muted player could lift their own mute by closing the tab
    for five minutes. Another browser still joins as a new player, unmuted, the
    limit of "the same browser" that spec 014 accepts for a removal (its decision
    2). What it changed: `PastPlayer` (its `muted` field), the `player_left` row
    of `replay`, the `muted` field of "Seat back", the mute in "What a seat back
    keeps, and what starts afresh", AC-7 (its opening sentence and the run
    "Muted"), the edge cases "Host role and mute after a seat back" and "Removing
    or muting a past player", "Out of scope", and the `PastPlayer` fields in spec
    038's table of what the server keeps. Nothing else is needed: `snapshot_for`
    copies `muted` into each view (spec 012's `player_views`), spec 018's `replay`
    of `player_joined` takes `muted` from the view, and spec 022's page reads its
    own mute from its snapshot or a `player_muted`.

## Open questions

None. (Note from the lead, 2026-10-16: this section held open question 1, on a
nickname taken while a player was away. The human answered it on 2026-10-16 with
option (b), and it is now decision 12.)
