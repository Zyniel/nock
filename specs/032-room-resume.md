---
id: "032"
title: Room resume
status: approved
---

# 032 - Room resume

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

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

`replay` (spec 018 table), changed row:

| Event | Effect on the state |
| --- | --- |
| `player_left` | the player is removed from `players`, as before. Reason `removed`: their token is added to `removed_tokens` (spec 014). Reason `timed_out` or `left`: `PastPlayer(player_id, resume_token, nickname, colour)` of their record is appended to `past_players`, after dropping the oldest one when it already holds `MAX_PAST_PLAYERS` |

The live time-out (spec 017, in `tick` and in `join_room`) builds its state with
`replay`, so a live room and a replayed one agree. A past player's token still does
not resume (spec 017 is unchanged; see open question 1).

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
        """Delete the room, its snapshots and its log, in one transaction.

        Returns:
            True when the room existed. Its code is then free for a new room.
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
  expiry: `delete_room` removes the whole room.

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
- **AC-2** (AC-9.1.1) (Python; WebSocket with a fake clock) An expired room is deleted, and nobody can reach it any more. Python: a registry with a fake clock and a store file holds room A (last edit at `t0 + 10`) and room B (last edit at `t0 + 20`). With the clock at `t0 + 10 + LIFE`, `expire_rooms()` returns `[]`; at `t0 + 11 + LIFE` it returns `[A]`, then `store.has_room(A)` is False, `store.read_log(A) == []`, `store.load_room(A)` is None, `room_state(A)`, `find_room(A)` and `peek_room(A)` are None, B still loads with its log, and `add_room` of a fresh state with A's code succeeds. Without any call of `expire_rooms`, with the clock moved to `t0 + 21 + LIFE`, `room_state(B)` is None and `store.has_room(B)` is False. WebSocket: with no tick changing anything and `expiry_sweep_seconds=0.05`, `Ana` and `Bob` join a FX-01 room and Ana writes `T` at (1, 0); after `advance(LIFE + 1)`, both sockets are closed with code 4404 within 1 second of real time, and neither receives a message after Ana's `letter_changed`; a new socket to the same code is then closed with 4404 before any message.
- **AC-3** (AC-9.1.2) (WebSocket with a fake clock and a simulated restart; browser with live server) Opening the link on another device shows the same letters, timer and hint budget, also the next day and after a restart. WebSocket: in process one (store file, fake clock), a FX-01 room is created at `t0`; `Ana` joins at `t0`, writes `T` at (1, 0) at `t0 + 10` and `A` at (1, 1) at `t0 + 20`, reveals the letter (4, 4) at `t0 + 30` (spec 024), and her socket closes at `t0 + 100`; process one stops. The clock moves to `t0 + 100 + DAY` and process two starts on the same file. A client with no token (another device) joins as `Bob`: its snapshot's `grid` equals `grid_state` of the room as process one left it (`T` and `A` authored by Ana's id, `T` at (4, 4) locked and revealed), its `reveal_budget` is `RevealBudget(letters=4, words=1)`, and its `timer_elapsed_ms` is within 1,000 of 90,000, since the timer ran from the first letter at `t0 + 10` until nobody was connected at `t0 + 100` (spec 027 AC-1, AC-2). Then a client joining with Ana's token (her device; she timed out, so she joins as a new player, spec 017) receives a snapshot with the same `grid` and `reveal_budget` as Bob's, and a `timer_elapsed_ms` within 1,000 of Bob's. Browser: on the live server, page 1 (context 1) enters a FX-01 room as `Ana`, types `T` then `A` from (1, 0) across, and is closed; page 2 in context 2 (empty storage) opens the room's link, enters as `Bob`, and its cells (1, 0) and (1, 1) have `data-letter` `T` and `A`.
- **AC-4** (AC-9.1.3) (Python; HTTP) The server gives a room's summary only to a member of the room. Python: a `player_left` with reason `timed_out` replayed on a state holding `Bob` (token `TB`, colour 1) removes him from `players` and appends `PastPlayer(player_id=<Bob>, resume_token=TB, nickname="Bob", colour=1)` to `past_players`; with reason `removed` nothing is appended and `TB` goes to `removed_tokens`; on a state with `MAX_PAST_PLAYERS` past players, one more time-out drops the oldest and keeps 100. `member_id` gives Bob's id for `TB` after his time-out, `None` after his removal, and `None` for an unknown token. With past players `Bob`, `ana` and players `Ana`, `Cy`, `team_nicknames` is `("Bob", "ana", "Cy")`. HTTP: on room A (FX-01, grid number 1) where `Ana` (token `TA`), `Bob` (`TB`) and `Cy` (`TC`) joined, Ana wrote `T` at (1, 0) at `t0 + 10`, Ana removed Cy and Bob timed out, and room B (FX-01 added with `grid_number` None) where `Dan` (`TD`) wrote a letter at `t0 + 50`: `POST /api/rooms/summaries` with A's code and `TA` answers 200 with a JSON array of one item, which `RoomSummary.model_validate` turns into `RoomSummary(code=A, grid_number=1, width=5, height=5, players=("Bob", "Ana"), last_activity_at=<t0 + 10 as a UTC datetime>, solved=False)` (compared as models, so that fields a later spec adds with a default, such as spec 029's, keep it passing); with `TB` the same; with `TC`, with a token no player ever had, or with the code `ZZZZZZ`, `[]`; with A by `TA`, B by `TD` and A again by `TB`, two summaries, B then A. A body with 101 keys, a code `abc`, a token of 15 characters or an extra key answers 422. A room that only the store holds keeps the same log after the request. An expired room is left out and deleted.
- **AC-5** (AC-9.1.3) (browser with mocked routes; browser with live server) "My rooms" lists my open rooms with their grid, players and last activity. Mocked: with valid identities stored for `XYZ789` and `ABC234` and a corrupt `nock.identity.QQQQQQ` (`not json`), the page sends one `POST /api/rooms/summaries` whose body holds exactly the keys of `XYZ789` and `ABC234` with their stored tokens. When the answer is the summary of `XYZ789` (grid 2, 5 by 5, players `Ana`, `Bob`, last activity `2026-10-14T08:30:00Z`, not solved) then that of `ABC234` (grid null, 13 by 17, players `Ana`, last activity `2026-10-13T20:05:00Z`, solved), `my-rooms` reaches `data-state="ready"` with two `my-room` items in that order. The first has `data-code="XYZ789"`, `data-grid="2"`, `data-solved="false"`, the texts `Grille n° 2`, `5 × 5`, `Joueurs : Ana, Bob` and `Dernière activité : 14 octobre 2026 à 10:30`, no `my-room-solved`, and a `my-room-link` with `href="/r/XYZ789"`, text `Reprendre` and `aria-label` `Reprendre le salon XYZ789`. The second has `data-grid=""`, the texts `Grille hors catalogue`, `13 × 17`, `Joueurs : Ana` and `Dernière activité : 13 octobre 2026 à 22:05`, and a `my-room-solved` reading `Terminée`. An answer `[]` shows `fr.json["my_rooms.empty"]`; an answer with status 500 gives `data-state="error"` and `fr.json["my_rooms.error"]`, while the catalogue list still reaches `data-state="ready"`. With no identity stored, the page has no `my-rooms` element and sends no summaries request. Live: Ana (context 1) starts FX-01 from the catalogue (spec 010) and types `T` at (1, 0); Bob (context 2) joins her room; Ana's context then opens `/`: `my-rooms` holds one `my-room` with her room's code, `data-grid="1"` and the text `Joueurs : Ana, Bob`; clicking its `my-room-link` opens `/r/<code>`, whose room page reaches `data-status="joined"` with the same `data-you` as before, without showing `nickname-form`.
- **AC-6** (new) (browser with mocked routes; keyboard only for the walk) "My rooms" meets spec 035 and the window sizes of spec 006 AC-5. With the two summaries of AC-5, at 1280 by 720 and at 360 by 740: spec 035's contrast scan and language scan find no offending element on `/`; keyboard only, `tab_to` (spec 035 "Test harness") reaches each `my-room-link`, which then shows spec 035 AC-2's outline (style neither `none` nor `auto`, width at least 2 px, colour of contrast at least 3:1 against white), and `Enter` on the first loads `/r/XYZ789`. At each window size of spec 006 AC-5, `document.documentElement.scrollWidth <= window.innerWidth`, also when the first summary lists 8 players whose nicknames have 20 characters each.

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
  (spec 029 and 034 use the same rule), but it does not resume them in the room
  (spec 017; open question 1). A player who times out again under a new id adds
  another past record. Removed players are never past players.
- Cap (AC-4): with 100 past players, the oldest is dropped; that device's token no
  longer gets the summary, so the room leaves its "My rooms".
- Duplicate keys (AC-4): several keys for one room give one summary; it is enough that
  one of them is a member's.
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
- Getting back one's old player id, colour and authorship after a time-out (open
  question 1).
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

## Open questions

1. Getting one's player back after a time-out. Spec 017 makes a player who stayed
   away more than 5 minutes leave the room; when they come back the next day with
   their stored token, they join as a new player, with a new id and possibly another
   colour, and their letters keep the old id. The authorship view (spec 019), the
   recap (spec 028) and an account's "same seat, colour and authorship" (spec 033
   AC-1) then split one person in two. Options: (a) keep spec 017 as it is (this
   spec as written); (b) a join whose token belongs to a past player brings that
   player back with the same id and nickname, and the same colour when it is free
   (else the lowest free one), as long as the room is not full or locked; this needs
   a refinement of spec 017 (AC-3 and its edge case "After a time-out") and of spec
   012's join steps, and would be one more criterion here. Pick: (b), as a refinement
   of specs 017 and 012 before this spec is built.
