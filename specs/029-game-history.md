---
id: "029"
title: Game history
status: approved
---

# 029 - Game history

(Note from the lead, 2026-10-14: approved by the human after the Phase 6 refine, with the recommended answer to every open question. Before the test-writer runs, the spec-writer folds those answers into the text, moves them to the decisions, and makes the follow-on refinements of the other specs they name.)

Epic E7 Completion and recap (US-7.3) · Release: V1 · Epic depends on: E6
The FX-01 reference grid is in `specs/_reference.md`. The catalogue page and
`nock.progress` are those of spec 004; the play flow of spec 010; the stored identity
of spec 012; completion, `grid_solved` and `elapsed_ms` of spec 026 (as spec 027 may
redefine `elapsed_ms`); members, `team_nicknames`, `RoomSummary`, "My rooms", the
summaries route and room deletion of spec 032; the duration text of spec 038;
accounts, sessions, `AccountStore` and erasure of spec 033. The messages are those of
spec 039. This spec is built last of Phase 6, after spec 033.

## Goal

As a returning player, I want my finished grids listed, so that I pick a new one and remember the old ones.

The recap credits contributions without turning a cooperative game into a ranking.

## Public interface

### Terms

- **Finished grid**: a room whose grid is solved (spec 026). Its **date** is the time
  of its `grid_solved` entry, and its **time taken** is that event's `elapsed_ms`.
- **Team-mates**: the room's members (spec 032) other than the player of this device
  or account, by nickname (`team_nicknames`).
- **History record**: one finished grid as a device or an account keeps it, so that
  it stays listed after its room is deleted (spec 032).

### `nock.room`

```python
# src/nock/room.py (additions)
class RoomState(RoomModel):
    # ... fields of specs 011 to 032
    solved_at: float | None = None  # the `at` of the grid_solved entry
    solved_elapsed_ms: int | None = Field(default=None, ge=0, strict=True)  # its elapsed_ms


class RoomSummary(RoomModel):
    # ... fields of spec 032
    finished_at: AwareDatetime | None = None  # solved_at in UTC; None unless solved
    elapsed_ms: int | None = Field(default=None, ge=0, strict=True)  # None unless solved
```

- `replay` of `grid_solved` (spec 026's row) also sets `solved_at = entry.at` and
  `solved_elapsed_ms = event.elapsed_ms`. The live completion rule builds its state
  with `replay`, so a live room and a replayed one agree.
- `room_summary` (spec 032) fills `finished_at` and `elapsed_ms` from them.
- A room solved before this spec may have a stored state with `solved` True and
  `solved_at` None. `RoomRegistry.room_summaries` then reads the two values from the
  room's `grid_solved` log entry.

### `nock.hub`: before a room is deleted

```python
# src/nock/hub.py (addition)
class RoomRegistry:
    def set_delete_hook(self, hook: Callable[[RoomState], None] | None) -> None:
        """Call `hook` with a room's latest state just before each deletion of
        spec 032 (by the sweep or by a lookup), in the deleting thread. A hook that
        raises is logged, and the deletion goes on."""
```

The app sets a hook on the registry it serves, at startup, which saves the history
records of the accounts linked to the room (below).

### Account history (`nock.accounts`)

```python
# src/nock/accounts.py (additions to spec 033)
class HistoryRecord(AccountModel):
    """One finished grid of an account."""

    code: RoomCode
    grid_number: int | None
    width: int = Field(gt=0, strict=True)
    height: int = Field(gt=0, strict=True)
    finished_at: AwareDatetime
    elapsed_ms: int = Field(ge=0, strict=True)
    teammates: tuple[Nickname, ...]  # in team_nicknames order


class AccountStore:
    def save_history(self, account_id: str, state: RoomState) -> None:
        """Save the record of the solved room `state` for the account, once: a
        record already saved for that account and room code is kept as it is.

        Team-mates are the members of `state` whose player id is not one of the
        account's identities in that room, kept with their player ids (for
        erasure). Does nothing when the room is not solved.
        """

    def history(self, account_id: str) -> list[HistoryRecord]:
        """The account's records, `finished_at` newest first, then code."""

    def accounts_of_room(self, code: str) -> list[str]:
        """The ids of the accounts that hold an identity in room `code`."""
```

- Records are saved (1) by `GET /api/account/history`, for each room of the account's
  identities (all of them, not only the latest per room) that exists and is solved;
  (2) by the delete hook, for each account of `accounts_of_room(code)`, when the
  deleted room is solved. So an account's finished grid stays listed after its room
  is deleted at expiry.
- Erasure (spec 033 `delete_account`) also deletes the account's records, and, in the
  records of every other account, replaces the nickname of each team-mate whose room
  code and player id are an identity of the deleted account with
  `FORMER_PLAYER_NICKNAME` (`--`).

| Method and path | Answer |
| --- | --- |
| `GET /api/account/history` | 200, JSON array of `HistoryRecord`, `history(account)` after saving the missing records; 401 without a session; 404 when accounts are off (spec 033) |

A record in JSON:
`{"code": "XYZ789", "grid_number": 2, "width": 5, "height": 5, "finished_at": "2026-10-14T08:30:00Z", "elapsed_ms": 754000, "teammates": ["Bob", "Cy"]}`.

### Client: history on this device

`localStorage` key `nock.history`: a JSON array of records, `finished_at` newest
first, at most `HISTORY_LIMIT = 100` (the oldest go). A record:

```json
{"code": "XYZ789", "grid": 2, "width": 5, "height": 5, "finished_at": "2026-10-14T08:30:00Z", "elapsed_ms": 754000, "teammates": ["Bob", "Cy"]}
```

`grid` is the catalogue number or `null`. A stored value that is not a JSON array is
read as `[]`; an item whose fields do not have these types (strings, numbers, an array
of strings) is ignored.

Writing a record: from a `RoomSummary` with `solved` true, the page writes a record for
its code, replacing any record of that code: `grid` from `grid_number`, `width`,
`height`, `finished_at`, `elapsed_ms`, and `teammates` = the summary's `players`
without the names equal to the nickname of this device's identity for that room
(spec 012), compared with `toLowerCase()`. It does so:

- on the catalogue page, for each solved summary of "My rooms" (spec 032);
- on the room page, when the grid becomes solved (a `grid_solved` event, or a snapshot
  with `solved: true`, spec 026): it sends `POST /api/rooms/summaries` with its own
  code and `snapshot.resume_token`, and writes the record from the answer.

Records stay when their room is deleted; nothing on the device removes them.

### Client: the history list on the catalogue page

The catalogue page (spec 004) gains, after the catalogue list, a section
`data-testid="history"` with an `h2` `t("history.heading")`. It exists when the
device holds at least one valid record or, signed in (spec 033), when
`GET /api/account/history` gives at least one record.

- When signed in, the page asks `GET /api/account/history` and lists its records
  together with the device's, one item per room code (an account record replaces the
  device's record of the same code), `finished_at` newest first, then code. The
  account's records are not written to the device.
- One `data-testid="history-item"` per record, with:

  | Attribute or child | Value |
  | --- | --- |
  | `data-code` | the room code |
  | `data-grid` | the catalogue number in decimal, `""` when null |
  | `data-finished-at` | `finished_at` as stored |
  | `data-elapsed-ms` | `elapsed_ms` in decimal |
  | grid label | `t("catalogue.item.number", {number})`, or `t("my_rooms.unnumbered")` when null (spec 032) |
  | size | `t("catalogue.item.size", {width, height})` |
  | `data-testid="history-date"` | `t("history.finished", {date})`, `date` written as spec 032's `date` (day, long month, year, in the browser's time zone) |
  | `data-testid="history-time"` | `t("history.time", {duration})`, `duration` the duration text of spec 038 |
  | `data-testid="history-teammates"` | `t("history.teammates", {names})`, the nicknames joined by `", "`, each `--` shown as `t("player.former")` (spec 033); `t("history.alone")` when there is none |
  | `data-testid="history-replay"` | only when the grid number is known: a button with the text `t("history.replay")` and the `aria-label` `t("history.replay_label", {number})` |
  | `data-testid="history-error"` | `role="alert"`, `t("catalogue.play_failed")`, after a failed replay of this item |

- Replay (AC-4): a click on `history-replay` runs spec 010's play button steps for that
  number: `nock.progress` is marked started unless it is finished, `POST /api/rooms`
  with `{"grid_number": <number>}`, the room record `nock.room.<new code>` is written
  as `{"grid": <number>, "selection": null}`, then the page loads `/r/<new code>`,
  where the creator joins at once (spec 010). The button is disabled while the
  request runs; a failure shows `history-error` in that item and enables the button
  again.
- Accessibility (spec 035): the buttons are reachable with `Tab`, show AC-2's visible
  focus, and every text meets 4.5:1. Layout (spec 006 AC-5): no horizontal page
  scroll; long lists of names wrap.

### New `fr.json` keys

| Key | Value |
| --- | --- |
| `history.heading` | `Grilles terminées` |
| `history.finished` | `Terminée le {date}` |
| `history.time` | `en {duration}` |
| `history.teammates` | `Avec {names}` |
| `history.alone` | `En solo` |
| `history.replay` | `Rejouer` |
| `history.replay_label` | `Rejouer la grille n° {number}` |

### Test harness

- Python and HTTP: as specs 026, 032 and 033 (a FX-01 room driven to its solved
  state, a registry with a fake clock on a store file, an app with `accounts=SETTINGS`,
  an `AccountStore` on the same file and a recording mailer).
- `SOLVED_XYZ`: the summary of a solved room `XYZ789` (grid 2, 5 by 5, players `Bob`,
  `Ana`, `Cy`, last activity and `finished_at` `2026-10-14T08:30:00Z`, `elapsed_ms`
  754,000). `OPEN_ABC`: an unsolved room `ABC234` (grid 1, players `Ana`).
- Browser with mocked routes: `page.route("**/api/rooms/summaries", ...)`,
  `page.route("**/api/account", ...)`, `page.route("**/api/account/history", ...)`
  and `page.route("**/api/rooms", ...)` as each case says; `nock.identity.<CODE>` (for
  example nickname `Ana`) and `nock.history` seeded with `context.add_init_script`; the
  context has `timezone_id="Europe/Paris"`. The room page cases use spec 040's mocked
  socket.
- Browser with live server: the `live_server`, `room_registry` and `catalogue`
  fixtures with FX-01 as published entry 1 (spec 010's harness); accounts as spec
  033's harness. Two players are two contexts; the two pages solve FX-01 as spec 026
  AC-3 does.
- Engines: every browser criterion runs in Chromium, Firefox and WebKit. No check of
  this spec is Chromium-only.

## Acceptance criteria

The words in brackets say how each criterion is tested.

- **AC-1** (AC-7.3.1) (Python; HTTP) A finished room's summary carries the date it was finished and the time it took. Python: in spec 026 AC-1's play (`FULL17`, then `T` at (4, 4) at `NOW + 754.0`), the new state has `solved_at == NOW + 754.0` and `solved_elapsed_ms == 754000`; replaying the play's entries from `new_room` gives the same two values; `room_summary` of that state has `finished_at` equal to `NOW + 754.0` in UTC and `elapsed_ms == 754000`, and that of an unsolved room has both None. HTTP: `POST /api/rooms/summaries` for a solved room answers its summary with those `finished_at` and `elapsed_ms`, and for an unsolved one with `"finished_at": null` and `"elapsed_ms": null`. A room stored before this spec, whose latest snapshot has `solved` true without `solved_at` (written by the test without the two fields), gets the values of its `grid_solved` log entry.
- **AC-2** (AC-7.3.1) (browser with mocked routes and socket; browser with live server) My history on this device lists each finished grid with its date, its time and my team-mates' nicknames. Mocked: with identities for `XYZ789` and `ABC234` (nickname `Ana`) and the summaries answer `SOLVED_XYZ`, `OPEN_ABC`, the catalogue page writes `nock.history` as exactly one record `{"code": "XYZ789", "grid": 2, "width": 5, "height": 5, "finished_at": "2026-10-14T08:30:00Z", "elapsed_ms": 754000, "teammates": ["Bob", "Cy"]}`, and `history` shows one `history-item` with `data-code="XYZ789"`, the texts `Grille n° 2`, `5 × 5`, `Terminée le 14 octobre 2026`, `en 12 min 34 s` and `Avec Bob, Cy`, and a `history-replay` reading `Rejouer` with the `aria-label` `Rejouer la grille n° 2`. With `nock.history` also seeded with an older record of `QQQQQQ` (grid null, `elapsed_ms` 3,725,000, no team-mate), which the summaries no longer return, the list shows it second, with `Grille hors catalogue`, `en 1 h 02 min 05 s`, `En solo` and no `history-replay`. A `nock.history` of `not json` reads as empty, and an item with `"elapsed_ms": "754000"` is ignored. With no record and no account, the page has no `history` element. Room page: given a snapshot with `solved: true` (or a `grid_solved` event after a snapshot), the page sends `POST /api/rooms/summaries` with its code and token, and, from a solved answer, `nock.history` gets the room's record. Live: `Ana` (context 1) and `Bob` (context 2) solve FX-01 in a room started from the catalogue; context 1 then opens `/`: `history` lists one item with `data-grid="1"`, `Avec Bob`, a `data-elapsed-ms` equal to the room's `solved_elapsed_ms` and a date text of its `solved_at`.
- **AC-3** (AC-7.3.1) (HTTP; browser with live server) With an account, my history follows me across devices. HTTP: Ana signs in from room R (spec 033) and R is solved with `Bob`; `GET /api/account/history` answers one record `{"code": R, "grid_number": 1, "width": 5, "height": 5, "finished_at": <R's solved_at in UTC>, "elapsed_ms": <R's>, "teammates": ["Bob"]}`; a linked room that is not solved gives no record; without a session it answers 401, and with accounts off 404. Browser: after Ana and Bob solve R, Ana's second device (a new context, empty storage) signs in with her address (spec 033 AC-2) and opens `/`: `history` lists R with `Avec Bob`, although that device never opened R.
- **AC-4** (AC-7.3.2) (browser with live server) Replaying a finished grid opens a new room with an empty grid. With `nock.progress` seeded to `{"1": "finished"}` and a history record of a room on grid 1, a click on its `history-replay` loads `/r/<code>` with a code other than the record's; the room page reaches `data-status="joined"` without `nickname-form`, `data-solved="false"`, 18 letter cells with `data-letter=""`; `nock.room.<code>` holds `"grid": 1`, and `nock.progress["1"]` is still `"finished"`. When `POST /api/rooms` answers 500 (or 404, as for a withdrawn grid, spec 005), the page stays on `/`, the item shows `history-error` with `fr.json["catalogue.play_failed"]`, and the button is enabled again.
- **AC-5** (new) (browser with mocked routes; keyboard only for the walk) The history list meets spec 035 and the window sizes of spec 006 AC-5. With the two records of AC-2, at 1280 by 720 and at 360 by 740: spec 035's contrast scan and language scan find no offending element on `/`; keyboard only, `tab_to` reaches each `history-replay`, which shows spec 035 AC-2's outline, and `Enter` on it sends `POST /api/rooms` with that grid number. At each window size of spec 006 AC-5, `document.documentElement.scrollWidth <= window.innerWidth`, also with a record that lists 7 team-mates of 20 characters each.
- **AC-6** (new) (HTTP) Deleting an account removes its history and makes its player a former player in the others' history. Ana's and Zélie's accounts (spec 033) both hold room R, solved with Ana, Zélie and Bob, and both have asked their history once. When Zélie deletes her account, Ana's `GET /api/account/history` lists R with `"teammates": ["--", "Bob"]` in R's `team_nicknames` order, Zélie's records are gone, and the database files no longer hold `Zélie-Probe`. On Ana's page, that item reads `Avec Ancien joueur, Bob`.
- **AC-7** (new) (HTTP with a fake clock) An account's finished grid stays in its history after the room is deleted. Ana's account holds room R (solved) and room S (not solved), and has not asked its history yet; both rooms expire and the sweep deletes them (spec 032). Then `GET /api/account/history` lists R's record, saved by the delete hook, and nothing for S; a hook that raises is logged, and the room is deleted all the same.

## Edge cases and errors

- Time taken (AC-1): `elapsed_ms` of `grid_solved`, as spec 026 defines it and spec 027
  may redefine it; this spec shows it and does not compute it.
- One grid finished twice (AC-2): two rooms, two records.
- Finished while I was away (AC-2): the record is written when this device next sees
  the room solved, on the room page or in "My rooms", while the room exists.
- Rooms deleted before this device saw them solved (AC-2): a guest's device has no
  record of them; an account keeps one (AC-7).
- Removed players (AC-2): a removed player is not a member (spec 032), so the room
  gives them no summary and no record.
- My own nickname (AC-2): removed from the team-mates by name, so a team-mate with my
  nickname in another case is removed too (rare; spec 012 makes such names unique in
  a room with a suffix only while both are present).
- Former players (AC-2, AC-6): a team-mate erased by spec 033 reads `Ancien joueur`;
  a name already stored on another device stays as it was (spec 033).
- Limit (AC-2): the 101st device record drops the oldest by `finished_at`.
- Unpublished or withdrawn grid (AC-4): the creation request answers 404 (specs 004,
  005), and the item shows the error.
- Bare grids (AC-4): no catalogue number, no replay button.
- Progress (AC-4): replaying keeps `"finished"` (spec 010 step 1).
- Same code on two lists (AC-3): the account's record wins on the page.
- A hook that fails (AC-7): logged; the deletion goes on, so privacy wins over history.
- Answers stay on the server (AC-1, AC-3): records hold no letter, clue or answer
  (spec 037).

## Out of scope

- Public leaderboards (epic E7).
- Shared timer: spec 027.
- End-of-game recap: spec 028 (the history links to no recap).
- Unfinished rooms (spec 032's "My rooms" lists them).
- Deleting a record by hand, sorting or filtering the history, statistics over it.
- Moving a device's records to an account.

## Work packages

None.

## Decisions

Proposed by the spec-writer on 2026-10-14 for the Phase 6 refine. They are part of the
spec above and are approved with it.

1. Where the history lives (AC-2, AC-3). Rooms are deleted 30 days after their last
   edit (spec 032), so the history must be kept elsewhere. Pick: on the device for
   everyone, and on the server for an account (spec 033's "history follows me across
   devices").
2. Data of a finished room (AC-1). Pick: the date and the time taken are kept in the
   room's state by `replay` of `grid_solved`, and travel in spec 032's summaries, so
   the device needs no other route.
3. When an account's records are saved (AC-3, AC-7). Pick: when the account asks its
   history, and just before its room is deleted, so that a record never depends on
   a page being open when the grid is solved.
4. Team-mates (AC-2). Pick: the room's members other than me, past players included,
   so that the team shows even when everyone has left.
5. Replay (AC-4). Pick: spec 010's play flow for the grid number, so a replay is a new
   room exactly like a start from the catalogue.

## Open questions

1. Team-mates' nicknames after the room is gone. An account's records keep the
   nicknames of other players, guests included, after the room is deleted at expiry,
   while spec 038 AC-2 deletes room data then. Options: (a) keep them, as the backlog
   asks for "team-mates' nicknames" (as written; an erased account's nickname becomes
   "former player"); (b) keep only the number of team-mates. Pick: (a).
