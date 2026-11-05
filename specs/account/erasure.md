---
area: account
file: erasure
status: approved
---

# account/erasure - Erasure, what is kept, history records, grid progress

## Purpose

A player who deletes their account loses their address at once; an erasure,
retried until it is done, deletes the rooms they created, turns them into
« Ancien joueur » in the other rooms, and an e-mail says when it is done. This
domain also holds what the account keeps of a player's play: the records of
their solved rooms and their progress on the grids, which a team-mate's
erasure must never undo.

## Depends on

- `account/account.md`: accounts on or off, the session, identities and their
  tokens, the mailer, the page's « Supprimer mon compte ».
- `lobby/joining.md`: members, past players, the seat back, the device's
  identities; the creator rooms are `lobby/host.md`.
- `lobby/lifetime.md`: the sweep that runs the attempts and the purge; its
  checkpoint is `admin/operations.md` rule 20.

## Rules

### Erasure and what is kept

1. `DELETE /api/account` deletes in one transaction the account, its
   sessions, identities, history and its address's links, makes its players
   `--` among the other accounts' team-mates (rule 9) and writes the erasure
   as pending: the account id, the address, the request time and the code and
   player id of every identity it held, nothing else of them. It then runs
   one attempt of the erasure (rule 5) and answers 204, clearing the cookie,
   whatever the attempt did. Each write of the erasure that removes an
   address, a nickname or a player id ends with a checkpoint
   (`admin/operations.md` rule 20): once they have emptied the WAL, no copy
   of the address or of those nicknames is left in the database files. A
   checkpoint that stays busy leaves the answer a 204, and the next sweep
   empties the WAL.
2. No join can take `--`, and a past `--` is seated back as `--` with no
   suffix (`lobby/joining.md` rules 1 and 13); pages show it as « Ancien
   joueur » (`player.former`).
3. Links and sessions are stored as SHA-256 only; an identity holds its
   resume token in clear, since the account gives it back to its devices
   (`account/account.md` rule 12): a copy of the database file resumes those
   players and signs nobody in. Each expiry sweep (`lobby/lifetime.md` rule
   6), the first at the app's start, deletes the links older than 30 minutes,
   the sessions older than 90 days and the done erasures older than 5 years
   (`ERASURE_RECORD_LIFE_SECONDS`), then runs a checkpoint
   (`admin/operations.md` rule 20); a failed purge is logged and the next
   sweep runs.
4. No log record, traceback included, holds an address, a link token, a
   session, a resume token or the SMTP password. An anonymous player is
   stored as a nickname and random identifiers, nothing of their browser;
   playing sets no cookie.
5. An erasure runs in attempts: the route's, then one in each sweep
   (`lobby/lifetime.md` rule 6), the first at the app's start, for as long as
   it is pending. The app runs one attempt of an erasure at a time: an
   attempt that finds the erasure done, or another attempt of it running,
   does nothing and is not counted. Otherwise an attempt counts itself, then
   runs these steps in order, each idempotent, going on past a step that
   fails, which is logged at WARNING or above:
   1. for each player it holds not yet marked erased whose room still
      exists, live or stored, the player stays as an anonymous player named
      `--`: the member's account link is cleared and the nickname becomes
      `--` in the live state, the stored snapshots and the logged
      `player_joined`, with no event; ids, colours, seqs and letters stay,
      nothing else of the room changes; a live room's engine is waited for
      at most 5 s. The player is then marked erased, as is one whose room is
      gone; the erasure holds every player, marked or not, until it is done;
   2. its creator rooms are deleted, live and stored (`lobby/host.md` rule
      14); a room counts as deleted only when its deletion removed it;
   3. last, every player the erasure holds, marked or not, becomes `--`
      among the team-mates of every history record (rule 9).

   When no step failed, the e-mail of rule 6 goes, then one write marks the
   erasure done: it keeps the request and completion times, the attempts, how
   many players it held, how many rooms step 2 deleted and the time the
   e-mail was accepted, or none; its account id, address and players go in
   that write. A done erasure is kept 5 years, then purged (rule 3); a
   pending one stays until an attempt ends it.
6. The e-mail goes once, in the attempt that ends the erasure, to the address
   the pending erasure holds, from `NOCK_SMTP_FROM`, subject
   `email.deleted.subject` (« Votre compte Nock a été supprimé »), plain
   UTF-8 body `email.deleted.body`, with no link: « Bonjour,\n\nVotre compte
   Nock et les données qui lui étaient liées ont été supprimés. Les salons
   que vous aviez créés sont fermés ; dans les autres, vous apparaissez comme
   « Ancien joueur ».\n\nSi vous n'aviez rien demandé, une personne connectée
   à ce compte l'a supprimé. », sent as `account/account.md` rule 7 says. A
   `MailError` is logged (rule 4) and the erasure is marked done the same,
   with no e-mail time; nothing sends it again.
7. A device of the erased player that still holds its identity in a room
   (`lobby/joining.md` rule 8) enters it by that token with no form, as the
   member `--`, resumed or seated back (rule 2): its id, colour and letters
   kept, shown « Ancien joueur » to everyone, itself included, linked to no
   account and playing as an anonymous player. A session cookie of the
   deleted account reads signed out on every device.

### History records

8. An account's record of a solved room is saved once, by the first of `GET
   /api/account/history` (for each room of its identities) and the delete
   hook, which gets a room's latest state just before the sweep, a lookup or
   an erasure (rule 5) deletes it; a failing hook is logged and the deletion
   goes on. Only identities whose token is a member's of that room count, so a
   room that drew an old code saves nothing. A record: `code`, `grid_number`,
   `width`, `height`, `finished_at`, `elapsed_ms` (`gameplay/history.md` rule
   1) and `teammates`, the other members in `team_nicknames` order, each
   once. In the save's transaction, a team-mate whose code and player id a
   pending erasure holds, marked erased or not (rule 5), is written `--`.
9. `GET /api/account/history` lists the records, newest `finished_at` first,
   then by code. An erasure makes its players `--` among the others'
   team-mates: in the deletion's transaction (rule 1), at the last step of
   every attempt (rule 5) and in any record saved while it is pending (rule
   8), so a save that read the room before the erasure, or by the delete
   hook of a room an attempt deletes, never brings the nickname back.

### Grid progress

10. `GET /api/account/progress` answers the account's progress as
    `nock.progress` holds the device's (`content/library.md` rule 7): an object
    from grid numbers in decimal to `"finished"`, for each history record and
    each solved room of an identity `account/account.md` rule 12 lists, or
    `"started"`, for each unsolved one and each creator room (`lobby/host.md`
    rule 11) that still exists; `finished` wins. A room or record with no grid
    number gives nothing; `{}` when nothing does. Derived at each request,
    nothing stored: it saves no record, and « Grilles terminées » lists every
    grid it marks `finished`, since rule 8 saves each solved room that counts
    here.

## Acceptance criteria

- **AC-1** Ana, signed in from R, solves it with Bob: her history is R's
  record, 5 × 5, solve time in UTC, `["BOB"]`; an unsolved room gives none, a
  room stored without solve times its logged ones. Swept unasked, a solved R
  keeps its record, and a raising hook is logged while the room still goes. A
  code reused by Bob and Cy's room gives Ana nothing. Once Zoé, of R too,
  deletes her account, Ana's R reads `["--", "BOB"]`, also with R expired
  unswept. (← 029 AC-3, 029 AC-6, 029 AC-7)
- **AC-2** Zoé, in R with Bob, writes `T`, signs in, linked S where she
  timed out, and deletes her account: 204; her cookie reads signed out, her
  unused link 404. In R her record, named `--`, keeps its id, colour and `T`,
  her logged join reads `--`, a newcomer sees `--`; in S her past record is
  `--`. The files hold neither her address nor `ZOÉ`, still `BOB`, also after
  a restart, from a second app, and with no room. A `PUT` racing the deletion
  gets 401. A past `--` seated back beside a `--` is `--`. (← 033 AC-4)
- **AC-3** Then Bob's reloaded page names Zoé « Ancien joueur » in the
  roster, « Retirer Ancien joueur du salon » and the feed (« Ancien joueur a
  vérifié un mot »); « Mes salons » reads « Joueurs : Bob, Ancien joueur »;
  the recap names her « Ancien joueur ». No page shows `--`. (← 033 AC-5)
- **AC-4** Ana, signed in, is a member of R (grid 1, solved), S (grid 2,
  unsolved) and S2 (grid 3, unsolved), holds a record of a swept room of grid
  3, and created U (grid 4) without joining it: `GET /api/account/progress`
  answers exactly `{"1": "finished", "2": "started", "3": "finished", "4":
  "started"}` with `Cache-Control: no-store`, and `GET /api/account/history`
  asked next lists grids 1 and 3. An account with no room gets `{}`.
- **AC-5** Once S expires the answer loses `"2"`, also when a new room with
  S's code plays grid 2 with Bob and Cy; a solved room with no grid number
  gives nothing; R expired unswept still gives `"1": "finished"`.
- **AC-6** Without a cookie `GET /api/account/progress` answers 401
  `{"detail": "Not authorized"}`; accounts off, 404 `{"detail": "Not
  Found"}`.
- **AC-7** Zoé, in R, deletes her account while a second connection to the
  file holds a read open: the answer is 204 within 2 seconds, her cookie then
  reads signed out, and WARNING records are logged.
  Once that connection closes, the next sweep leaves neither her address nor
  `ZOÉ` in the database file or its WAL.
- **AC-8** Zoé, in R (live) and S (stored) and creator of U, deletes her
  account: 204; R's and S's players are `--`, U is gone, and her address
  receives one e-mail from `NOCK_SMTP_FROM`, subject « Votre compte Nock a été
  supprimé », plain UTF-8 body exactly rule 6's text, with no link.
  `account_erasures` then holds one row: `account_id` and `email` null,
  `requested_at`, `done_at` and `notified_at` set, `attempts` 1, `players` 2,
  `rooms_deleted` 1; `account_erasure_players` is empty; the files hold
  neither her address nor `ZOÉ`.
- **AC-9** Zoé, in live rooms R and S and creator of U, deletes her account
  while S's engine is held in a step for more than 5 s: 204 within 7 s, her
  cookie reads signed out, one WARNING record is logged, R's player is `--`,
  U is gone, no e-mail is sent; her erasure is pending, holding R's player
  marked erased and S's not, `attempts` 1, and the files hold her address and
  S's `ZOÉ`.
  Once S's engine answers, the next sweep, or the first of an app started on
  that database, makes S's player `--`, sends the e-mail and marks the
  erasure done, `attempts` 2, `players` 2, `rooms_deleted` 1; the files then
  hold neither her address nor `ZOÉ`, and a later sweep sends nothing.
- **AC-10** With the mailer raising `MailError` at completion, the deletion
  answers 204, one WARNING record is logged without the address, the erasure
  is done with `notified_at` null, the files hold no address, and no later
  sweep sends anything.
- **AC-11** Zoé, in R and S, deletes her account while S's engine is held
  for more than 5 s: R's player is `--` and her erasure is pending. Bob's
  record of solved R, read before her deletion and saved now, names her `--`
  among its team-mates; so does one saved after a second attempt that S still
  holds up, and the record the delete hook saves when an attempt deletes her
  expired room T.
- **AC-12** Zoé's device, holding her R identity, reloads R after her
  deletion: it enters with no form as the player `--`, named « Ancien joueur »
  in its own roster with her colour and letters, a letter it types is
  applied, and `GET /api/account` there reads signed out.
- **AC-13** A done erasure of time 0 is deleted by the purge at 157,680,001 s
  and kept at 157,679,999 s, no other row touched. A purge at 157,680,001 s
  that raises is logged, and the next sweep's purge deletes that erasure.
- **AC-15** A sign-in link used again, or 1,801 s after it was asked, gets
  404; used at 1,799 s, 200. A session signs in a second short of 90 days,
  not a second past. A second sign-in leaves the first working; behind
  `https://` the cookie has `Secure`. Two spellings of an address are one
  account; a player removed before the link is used gets `room_code` null.
  Purges at 1,801 s and 7,776,001 s delete a link and a session of time 0, no
  byte of the link's address left; at 1,799 s and 7,775,999 s they stay.
  (← 033 AC-1)
- **AC-16** Across a link, a sign-in, a status, a `PUT`, a sign-out, a failed
  mail and a deletion, no log holds the link token, the session, a resume
  token, the address or the SMTP password; the files hold the address, and
  the link and session only as SHA-256 hex. A sign-out answers 204 and ends
  the session, also when there is none. (← 033 AC-10)
- **AC-17** With accounts on, a browser with no cookie or storage solves
  FX-01 with a word check: no 401 or 403, no cookie, the account sheet never
  opens, every frame parses as a client message; solving from the catalogue,
  nothing sets a cookie and every request stays on the origin. An anonymous
  player who plays leaves only `ANA` and her id in the files, nothing of her
  browser's agent, headers, language or address. (← 033 AC-3, 038 AC-1,
  038 AC-2)
- **AC-14** Zoé, in live room R and creator of U, deletes her account while
  R's engine is held for 1 s, and a sweep starts during the route's attempt:
  once both are over, R's player is `--`, U is gone, her address received
  one e-mail, and the erasure is done with `attempts` 1 and `rooms_deleted`
  1.

## Edge cases

- An erased player's open pages keep the old name until their next snapshot
  (AC-3).
- A creator room is deleted whoever is host in it then; an anonymous room where
  the account's player is host stays, that player `--` (`lobby/host.md`
  AC-15).
- A solved creator room the account never joined is `started`, as its history
  never lists it (AC-4).
- A held player's room that expired meanwhile is deleted by step 1, its hook
  saving the nickname, which step 3 erases (AC-11).
- An app stopped between the e-mail and the write that marks the erasure done
  sends it again at its next attempt (AC-9).
- A sweep that starts during the route's attempt leaves that erasure to it
  (AC-14).
- With accounts in memory (`account/account.md` rule 3), a pending erasure
  goes with the app.
- The deleted account's sessions are gone, so a second `DELETE` from another
  device gets 401 (AC-2).

## Out of scope

- Sign-in, the session, the account's rooms, the sheet and the page, including
  « Supprimer mon compte » and what the device forgets on a 204:
  `account/account.md`. AC-15 to AC-17 check part of that behaviour together
  with rules 3 and 4; the rules of that behaviour stay in
  `account/account.md`.
- An export of the account, a confirmation link or a grace period before
  deleting, keeping creator rooms alive; erasing chat lines or backups.
- Pushing a device's progress up to the account; a guest's progress across
  devices. How the pages merge the account's progress with the device's:
  `content/library.md`. The history on screen: `gameplay/history.md`.
- Logs and retention: `admin/operations.md`.

## Code

- `src/nock/accounts.py` (the pending erasures, the history records, the
  checkpoints, `ERASURE_RECORD_LIFE_SECONDS`), `mailer.py` (the deleted
  message), `server.py` (`DELETE /api/account`, the history and progress
  routes, the erasure's attempts, the purge).
- `room.py` (`FORMER_PLAYER_NICKNAME`, `with_player_erased`, `member_id`),
  `store.py` (`erase_player`), `hub.py` (`erase_player`, the creator rooms'
  deletion, the delete hook).
- Tests: those of the pointers, in `tests/test_spec_NNN_*`;
  `tests/test_erasure_*` (AC-4 to AC-14), which share `tests/account_harness.py`.
