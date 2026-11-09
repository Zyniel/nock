---
area: account
file: records
status: done
---

# account/records - History records and grid progress

## Purpose

An account keeps what its player played: the records of their solved rooms,
listed by `GET /api/account/history`, and the progress they give on each grid,
derived by `GET /api/account/progress`, which a team-mate's erasure must never
undo.

## Depends on

- `account/erasure.md`: the deletion, the erasure's attempts and the players a
  pending erasure holds (rules 1, 5); the identities are `account/account.md`
  rule 12.
- `lobby/summaries.md`: how a summary lists the members' nicknames (rule 1).
- `gameplay/history.md`: a room's solve time and `elapsed_ms` (rule 1); the
  records on screen.

## Rules

### History records

1. An account's record of a solved room is saved once, by the first of `GET
   /api/account/history` (for each room of its identities) and the delete
   hook, which gets a room's latest state just before the sweep, a lookup or
   an erasure (`account/erasure.md` rule 5) deletes it; a failing hook is
   logged and the deletion goes on. Only identities whose token is a member's
   of that room count, so a room that drew an old code saves nothing. A
   record: `code`, `grid_number`, `width`, `height`, `finished_at`,
   `elapsed_ms` (`gameplay/history.md` rule 1) and `teammates`, the other
   members' nicknames as a summary lists them (`lobby/summaries.md` rule 1).
   In the save's transaction, a team-mate whose code and player id a pending
   erasure holds, marked erased or not (`account/erasure.md` rule 5), is
   written `--`.
2. `GET /api/account/history` lists the records, newest `finished_at` first,
   then by code. An erasure makes its players `--` among the others'
   team-mates: in the deletion's transaction (`account/erasure.md` rule 1),
   at the last step of every attempt (`account/erasure.md` rule 5) and in any
   record saved while it is pending (rule 1), so neither a save that read the
   room before the erasure and writes while it is pending nor the delete hook
   of a room an attempt deletes brings the nickname back.

### Grid progress

3. `GET /api/account/progress` answers the account's progress as
   `nock.progress` holds the device's (`content/cards.md` rule 1): an object
   from grid numbers in decimal to `"finished"`, for each history record and
   each solved room of an identity `account/account.md` rule 12 lists, or
   `"started"`, for each unsolved one and each creator room (`lobby/creator.md`
   rule 2) that still exists; `finished` wins. A room or record with no grid
   number gives nothing; `{}` when nothing does. Derived at each request,
   nothing stored: it saves no record, and « Grilles terminées » lists every
   grid it marks `finished`, since rule 1 saves each solved room that counts
   here.

## Acceptance criteria

- **AC-1** Ana, signed in from R, solves it with Bob: her history is R's
  record, 5 × 5, solve time in UTC, `["BOB"]`; an unsolved room gives none, a
  room stored without solve times its logged ones. Swept unasked, a solved R
  keeps its record, and a raising hook is logged while the room still goes. A
  code reused by Bob and Cy's room gives Ana nothing. Once Zoé, of R too,
  deletes her account, Ana's R reads `["--", "BOB"]`, also with R expired
  unswept. (← 029 AC-3, 029 AC-6, 029 AC-7)
- **AC-2** Ana, signed in, is a member of R (grid 1, solved), S (grid 2,
  unsolved) and S2 (grid 3, unsolved), holds a record of a swept room of grid
  3, and created U (grid 4) without joining it: `GET /api/account/progress`
  answers exactly `{"1": "finished", "2": "started", "3": "finished", "4":
  "started"}` with `Cache-Control: no-store`, and `GET /api/account/history`
  asked next lists grids 1 and 3. An account with no room gets `{}`.
- **AC-3** Once S expires the answer loses `"2"`, also when a new room with
  S's code plays grid 2 with Bob and Cy; a solved room with no grid number
  gives nothing; R expired unswept still gives `"1": "finished"`.
- **AC-4** Without a cookie `GET /api/account/progress` answers 401
  `{"detail": "Not authorized"}`; accounts off, 404 `{"detail": "Not
  Found"}`.
- **AC-5** Zoé, in R and S, deletes her account while S's engine is held
  for more than 5 s: R's player is `--` and her erasure is pending. Bob's
  record of solved R, read before her deletion and saved now, names her `--`
  among its team-mates; so does one saved after a second attempt that S still
  holds up, and the record the delete hook saves when an attempt deletes her
  expired room T.
- **AC-6** Ana, Bob, Zoé and Lou, joined in that order, solve R; Zoé and
  Lou delete their accounts: Ana's record of R reads `["BOB", "--", "--"]`,
  saved before the deletions or after.

## Edge cases

- A solved creator room the account never joined is `started`, as its history
  never lists it (AC-2).
- A held player's room that expired meanwhile is deleted by step 1 of
  `account/erasure.md` rule 5, its hook saving the nickname, which step 3
  erases (AC-5).
- A record that `GET /api/account/history` saves from a room it read before
  that step 1 reached the room, and writes once the erasure is done, keeps the
  nickname: the whole erasure must end between that read and that write.
- The delete hook reads and saves under the rooms' lock, which that step 1
  takes too, so no erasure reaches its room in between. A socket opening to
  any room meanwhile waits for it; a database busy past SQLite's 5-second
  timeout fails the hook, logged, and that room's records not yet saved are
  lost (AC-1).

## Out of scope

- The deletion, the erasure's attempts, « Ancien joueur » and what is kept:
  `account/erasure.md`.
- Pushing a device's progress up to the account; a guest's progress across
  devices. How the pages merge the account's progress with the device's:
  `content/cards.md`. The history on screen: `gameplay/history.md`.

## Code

- `src/nock/accounts.py` (the history records, `progress`), `server.py` (the
  history and progress routes, the delete hook), `hub.py` (the delete hook).
- Tests: those of the pointers, in `tests/test_spec_029_*`;
  `tests/test_records_*` (AC-2 to AC-6), which share
  `tests/account_harness.py`.
