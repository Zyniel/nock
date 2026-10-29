---
area: lobby
file: joining
status: done
---

# lobby/joining - Joining, resuming and « Mes salons »

## Purpose

An invited player enters a room with only a nickname. A player who comes back
gets the same seat: after a reload, the next day, after a server restart, from
« Mes salons » on the catalogue page, or from any device signed in to their
account. A room lives 30 days after its last edit.

## Depends on

- `lobby/host.md`: removing and locking, the creator, the account of a member.
- `platform/realtime.md`: the join message, error codes, the resume window and the
  time-out of a disconnected player.
- `platform/server.md`: the store that keeps a room across restarts.

## Rules

### Nicknames

1. Before this rule, the join itself needs 2 to 20 code points once stripped,
   counted before NFC and the capitals; outside that it is `invalid_message`
   (`platform/realtime.md`). A nickname is then stored as: NFC, stripped,
   `str.upper()`, NFC again. On that result: 2 to 20 code points; each one a
   Unicode letter, a mark of category Mn or Mc, an ASCII digit, or one of space,
   `-`, `'`, `’`, `_`; at least one letter or digit. A broken rule is
   `invalid_nickname`.
2. Nicknames compare exactly. A nickname held by a player of the room, connected
   or not, is taken; past players hold none. A taken nickname gets ` n`, the
   smallest free `n >= 2`, the base cut so the whole fits in 20 characters,
   trailing spaces removed: a second `xxxxxxxxxxxxxxxxxxxx` is
   `XXXXXXXXXXXXXXXXXX 2`. Only the joiner gets a suffix.
3. Every page shows a nickname as plain text in capitalised words: the first
   character and each one after a space, `-`, `'` or `’` (not `_`) in capitals,
   the rest small, so `JEAN-LUC` reads `Jean-Luc` and a Greek name keeps its final
   sigma. An erased player's `--` (`account/account.md`) reads « Ancien joueur ».

### Join

4. A join's member is chosen once, before the steps: signed in
   (`account/account.md` rule 9), the account's member of the room, player or
   past player, whatever token the join carries; else the member whose token it
   carries. A token that is not the join's member's is not used: its member is
   not touched and their connection stays open. Then these steps run in order;
   the first that applies ends the join:
   1. the token used, a removed player's: `removed` (`lobby/host.md`);
   2. the member a player: resume (rule 6), unless they have been away longer
      than the resume window: they time out here (rule 12) and the join goes on;
   3. a locked room: `room_locked` (`lobby/host.md`), skipped for a join from
      the creator's session, member or not;
   4. 8 players: `room_full`, for everyone;
   5. the member a past player: seat back (rule 13);
   6. a nickname that breaks rule 1: `invalid_nickname`;
   7. a new player: the lowest colour index 0 to 7 that no player has, host
      when no player is host, appended last, linked to the session's account
      when signed in.

   `removed`, `room_locked` and `room_full` close the socket; `invalid_nickname`
   leaves it open for another join. A token that matches nobody is ignored. The
   creator's player is host at the end of their join whatever step seated them
   (`lobby/host.md` rule 13).
5. The joiner gets a snapshot that already counts the join and holds the room's
   letters, hint budget and timer; the others get `player_joined`, the joiner
   never does. A second join on a joined socket is ignored.
6. A resume keeps the player's id, nickname, colour, host role and letters and
   ignores the join's nickname. A disconnected player becomes active, which the
   others see (an idle one too, `social/presence.md`). An active player still
   connected elsewhere is taken over, by their token or by their account alike:
   the older socket is closed with 4001 and the others get nothing.
7. A closed socket makes its player disconnected; they keep their seat, colour,
   nickname and letters, and count among the 8, until they time out.

### The room page

8. When its socket opens, the page:
   1. with a valid identity stored for this room code, joins at once with its
      nickname and token;
   2. else, for a room created from the catalogue on this device (a room record
      whose `grid` is a JSON number), joins at once as a new player with the
      remembered nickname, sent as stored when it passes rule 1's checks after
      the capitals, else `room.default_nickname` (« Invité »);
   3. else shows the nickname form, prefilled with the remembered nickname, as a
      card under the room code line `room.heading` (« Salon <code> »).

   A valid identity is a JSON object whose `player_id`, `resume_token` and
   `nickname` are non-empty strings; anything else counts as absent.
9. The form applies rule 1's checks after the capitals before it sends: a length
   break shows `join.error.length`, any other `join.error.characters`, announced
   as an alert, and nothing is sent. The status `room.status.nickname` is read
   but not seen. The field shows capitals and keeps its value as typed. Submit is
   disabled while joining; Enter submits. An `invalid_nickname` from the server,
   whatever sent the join, shows the form again with `join.error.characters`.
10. Every snapshot stores the identity, `nock.identity.<CODE>`: id, token and the
    nickname the server holds. A join sent from the form, once a snapshot answers
    it, also stores `nock.nickname`, the nickname as sent; a join sent at once
    never does.
11. `room_full` ends on `room.status.full`, a 4001 close on
    `room.status.replaced`. Before any snapshot, such a refusal, like those of
    `lobby/host.md`, is the card's title, under the room code line
    `room.heading` (« Salon <code> »), with one link, `share.home` (« Voir les
    grilles »), to `/`. Once joined, the roster lists the players in snapshot
    order with their colour, marks one's own row with `roster.you`, and follows
    `player_joined`, `player_state_changed` and `player_left`.

### Past players and seat back

12. A player who times out, or leaves with reason `left`, leaves the players and
    becomes a past player, with their id, token, nickname, colour and mute.
    The 100 latest are kept. A removed player never is one. A host can neither
    remove nor mute a past player: `invalid_target`, and the record stays as it
    is. The members of a room are its players and past players.
13. A seat back brings the past player back as a player, appended last, in one
    `player_joined`: same id, token, letters and mute; nickname made unique by
    rule 2 (an erased player's `--` keeps no suffix); colour kept unless a player
    has it, else the lowest free one. The join's nickname is ignored. They are
    host only when no player is, or when they are the creator's player
    (`lobby/host.md` rule 13). Their flag, undo history and rate windows start
    afresh, and a vote opened while they were away does not count them.
14. A seat back refused (locked, full) leaves them a past player and a member. A
    refusal after a time-out inside the join keeps that time-out.

### Room life

15. An edit is a `letter_changed` or a `cell_locked`. A room's last edit time is
    its latest edit's, or the start of its life; it never goes back. A room is
    expired once more than 30 days have passed since; at exactly 30 days it is
    open.
16. A sweep at server start, then every hour, deletes the expired rooms; any
    lookup that meets one (a socket, a summary) deletes it first. Deletion removes
    the room, its log, its snapshots and its share token, closes every socket
    opened to it, joined or not, with 4404 and nothing else, and writes no log
    entry; a page that had shown the room then shows the room-gone dialog
    (`client/hud.md` rule 16). The code may then be drawn again, where an old
    token matches nobody. Until the deletion, a live room's open sockets keep
    working. A sweep that fails is logged at WARNING or above, and the next one
    runs.

### Summaries and « Mes salons »

17. `POST /api/rooms/summaries` takes `{"rooms": [{"code", "resume_token"}]}`,
    at most 100 keys, and answers one summary per room that some key holds a
    member's token for, newest last activity first, then code order. A summary is
    the code, the grid number (null outside the catalogue), width, height, the
    members' nicknames (past players in leaving order, then players, each once),
    the last activity (the last edit time, UTC), `solved` and the result fields
    of `gameplay/results.md`; no letter. The answer never says why a room is left
    out; it is not counted by the wrong-code throttle, makes no room live and
    writes nothing. An invalid body answers 422.
18. The catalogue page sends the identities whose code matches `^[A-Z0-9]{6}$`
    and whose token matches `^[A-Za-z0-9_-]{16,128}$`, in requests of at most
    100 keys, and lists the summaries in the server's order. With none to send
    it has no « Mes salons »; while loading and with no summary it shows
    nothing; a failed request, or an answer that is not a list of summaries,
    shows `my_rooms.error`. The rest of the page never waits for it. A row
    shows the grid label (`my_rooms.unnumbered` without a grid number), size,
    players, last activity in the browser's time zone,
    `catalogue.progress.finished` when solved, and the link `my_rooms.open` to
    `/r/<code>`, named `my_rooms.open_label`. A room left out is not listed,
    and its identity stays on the device.

### Look

- The nickname form, its refused field and the refusal card: `_design/pages.md`,
  « Entry and not-found pages ».
- « Mes salons » rows: `_design/pages.md`, « Catalogue »; its error line:
  « States: opening, loading, empty, error ».
- The roster: `_design/room.md`, « Salon ». Player colours:
  `_design/foundation.md`, « Player colours ».

## Acceptance criteria

- **AC-1** Rule 1 stores `  Ana  ` as `ANA` and `Élodie` as `ÉLODIE`, accepts
  `Jean-Luc`, `O’Neil`, `bob_42`, `Zoë`, `12` and `राम`, and refuses `A`, 21 `x`,
  `<b>Eve</b>`, `Ana!`, `--` and `Ana⃝`; sent in a join, 21 `x` is already
  `invalid_message`. (← 012 AC-1)
- **AC-2** The rule counts after the capitals: `Straßenbahnfahrerin` is stored
  `STRASSENBAHNFAHRERIN`, 11 `ß` get `invalid_nickname`, and `Παΐσιος` typed in
  small letters or in capitals is stored alike, in NFC. (← 012 AC-8)
- **AC-3** On a fresh room, a join as ` Ana ` gets a snapshot with seq 1 and one
  player `ANA`, colour 0, host, active; a join as `<b>Eve</b>` gets
  `invalid_nickname`, adds nobody, and a valid join on the same socket then
  succeeds. (← 012 AC-1)
- **AC-4** On the form, `Ana` enters the room and one's own roster row reads
  `Ana`, while `A` shows « Le pseudo doit faire de 2 à 20 caractères. » and sends
  nothing; typed `ana` shows in capitals and keeps the value `ana`. The form, and
  its field once refused, follow the entry pages design ("Look").
  (← 012 AC-1, 012 AC-8, 046 AC-15, 046 AC-16)
- **AC-5** Joins as `Ana`, `ana`, `Ana`, `Bob`, `Cy`, `Di`, `Ed`, `Flo` give
  colours 0 to 7 and `ANA`, `ANA 2`, `ANA 3`, `BOB`, `CY`, `DI`, `ED`, `FLO`, with
  only the first host; beside `STRAẞE`, `Strasse` is stored `STRASSE`.
  (← 012 AC-2)
- **AC-6** In a room whose (1, 0) holds `T` and whose budget is 3 letters and 1
  word, a join's snapshot arrives within 1 second with that `T`, its author, that
  budget and a timer at 0, stopped. (← 012 AC-3)
- **AC-7** A ninth join gets `room_full`, its socket closes, nobody hears of it
  and the room keeps 8 players; the page shows « Ce salon est complet (8
  joueurs). » as its card's title under « Salon <code> », with one link « Voir
  les grilles » to `/`, as for `room_locked`, `removed`, too many wrong codes or
  a 4001 close before any snapshot. (← 012 AC-4, 046 AC-17)
- **AC-8** After Ana's socket closes, a join with her token and the nickname
  `Autre` is Ana again (same id, `ANA`, colour 0, host), and a reload of her page
  joins without the form as the same player. (← 012 AC-5)
- **AC-9** The same identity opened in a second tab takes over: the first tab's
  socket closes with 4001 and it shows « Ce salon est ouvert dans un autre
  onglet. », with no event to the others. (← 012 AC-5)
- **AC-10** With an identity stored for `ABC123`, the page's first frame is a
  join with that nickname and token and no form shows; with only a record
  `{"grid": 1}` and `Zoé` remembered it is a join as `Zoé`, without token; with
  nothing remembered, or `A`, as « Invité ». (← 012 AC-6, 012 AC-8)
- **AC-11** With a record `{"grid": null}`, no record, or an identity for
  another code only, the page sends nothing and shows the form, prefilled with
  `Zoé` when `Zoé` is remembered. (← 012 AC-6)
- **AC-12** A form join as `Ana` answered as `ANA 2` stores the identity with
  `ANA 2` and remembers `ANA`; a join sent at once stores the identity and
  remembers nothing. (← 012 AC-7)
- **AC-13** Players `JEAN-LUC`, `D'ARTAGNAN`, `ANA 2`, `O’NEIL` and `ΝΊΚΟΣ` read
  `Jean-Luc`, `D'Artagnan`, `Ana 2`, `O’Neil` and `Νίκος` in the roster, the
  host's remove labels, a flag's label, the Auteurs legend, the chat and its mute
  rows. (← 012 AC-8)
- **AC-14** A room created at t0 with a letter at t0 + 10, a chat line at t0 +
  20, a check result at t0 + 25 and a locked cell at t0 + 30 has its last edit at
  t0 + 30: open 30 days later, expired half a second after. (← 032 AC-1)
- **AC-15** A room whose last edit is at t0 + 10 survives the sweep at t0 + 10 +
  30 days and is deleted one second later: its sockets close with 4404, its
  store rows and share link are gone, a new room may take its code, and a join
  there with an old token makes a new player. (← 032 AC-2)
- **AC-16** After Ana writes `T` and `A`, reveals (4, 4) and leaves, a day later
  and after a restart Bob, from another device, gets those letters, a budget of 4
  letters and 1 word and about 90 seconds of timer, and Ana's token seats her back
  with her id. (← 032 AC-3)
- **AC-17** In room A, where Bob timed out and Cy was removed, Ana's or Bob's
  token gets one summary naming `BOB` then `ANA`; Cy's token, an unknown token or
  code gets `[]`; 101 keys get 422; an expired room is left out and deleted.
  (← 032 AC-4)
- **AC-18** With identities for `XYZ789` and `ABC234`, one corrupt and one with a
  15-character token, « Mes salons » sends the two valid keys and lists `Grille n°
  2`, `5 × 5`, « Joueurs : Ana, Bob », « Dernière activité : 14 octobre 2026 à
  10:30 » in a browser set to Paris time, and « Reprendre », whose link resumes
  the room without the form. While its request waits, or after `[]`, it takes no
  space and shows no text; a 500 shows « Impossible de charger vos salons. » and
  the grids still load. (← 032 AC-5, 046 AC-12)
- **AC-19** « Mes salons » keeps the baselines of `product.md`: no contrast
  or language offender, every link reached by Tab with a visible focus, and
  no horizontal scroll with 8 players of 20 characters. Its rows follow the
  catalogue design ("Look"). (← 032 AC-6, 046 AC-11)
- **AC-20** Ana, timed out, joins with her token as `Autre`: one `player_joined`
  gives back her id, `ANA`, colour 0, her letters and her mute, not the host role;
  if `ana` joined meanwhile she is `ANA 2`, and if Dan took colour 0 she gets 3;
  in a full or locked room she is refused and stays a member. (← 032 AC-7)
- **AC-21** In R, Lea (signed in, token T, host, `T` at (1, 0)) and Bob (token
  U) are players: a device signed in as Lea joining with no token, with U or
  with an unknown token resumes Lea, same id, colour, letters and host role,
  closes her older connection with 4001, and leaves Bob and his connection
  untouched; signed out, the join with U resumes Bob. Lea timed out, the
  signed-in join with no token seats her back with her id.

## Edge cases

- `ΐ` and 18 `α` count 20 after the second NFC and are accepted (AC-2).
- A full room answers `room_full` even to an invalid nickname, and accepts a
  resume (AC-7).
- A disconnected player keeps their nickname and colour from a newcomer (AC-5).
- A corrupt identity (`not json`, `[]`, a missing or empty field) gives case 2
  or 3 of rule 8; a server `invalid_nickname` to case 2 shows the form (AC-10).
- A seat back ignores a nickname that rule 1 refuses (AC-20).
- A second device with the same token, after the seat back, is a resume: the
  older socket gets 4001 (AC-20).
- A signed-in device whose account has no member in the room joins by the token
  it carries, as before (AC-21).
- A past player dropped by the cap of 100 joins as a new player (AC-17, AC-20).
- Several keys for one room give one summary; one member's key is enough (AC-17).
- A socket to an expired code counts as a wrong code (AC-15).
- More than 100 identities go in several requests, listed in the server's order
  (AC-18).
## Out of scope

- Changing one's nickname or colour, choosing a colour, keeping the typed case
  (`McLean` shows as `Mclean`).
- Leaving a room on purpose, removing a room from « Mes salons », sorting it,
  clearing identities of deleted rooms.
- A warning before expiry, extending or restoring a room.
- Presence states in the roster: `social/presence.md`. Host controls and the
  creator: `lobby/host.md`. Codes and creation: `lobby/rooms.md`. The rooms of
  an account: `account/account.md`. Finished grids
  after deletion: `gameplay/results.md`. What changed while away:
  `social/catch-up.md`. What deletion erases for privacy:
  `admin/operations.md`.

## Code

- `src/nock/room.py`: nicknames, `join_room` (the member by account or token),
  disconnection, seat back, members, `room_summary`; `RoomConfig` holds the
  room life and sweep interval.
- `src/nock/store.py`: last edit time, expired codes, deletion.
- `src/nock/hub.py`: the sweep, lookups and their deletions, summaries.
- `src/nock/server.py`: the summaries route and the app's sweep.
- `web/src/lib/joinRules.ts`, `roomSession.ts`, `RoomPage.svelte`: the room
  page's join; `nickname.ts`: the display; `myRooms.ts`, `MyRooms.svelte`:
  « Mes salons ».
- Tests: `tests/test_spec_012_*`, `tests/test_spec_032_*`, `tests/test_joining_*`.
