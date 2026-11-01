---
area: account
file: account
status: done
---

# account/account - Optional account

## Purpose

A player who wants their rooms, and the progress of their grids, on every
device signs in with a link sent by e-mail; nothing else needs an account.
Deleting it erases the address at once; an erasure, retried until it is done,
deletes the rooms it created and turns the player into « Ancien joueur » in
the other rooms, and an e-mail says when it is done.

## Depends on

- `lobby/joining.md`: identities, members, seat back, « Mes salons »; the sweep
  is `lobby/lifetime.md`.
- `platform/serving.md`: `main()`, `NOCK_HOST`, `NOCK_PORT`, `NOCK_DATABASE`;
  the store that file names is `platform/server.md` rule 1.
- `gameplay/results.md`: « Grilles terminées », the history on screen.

## Rules

### Accounts on or off

1. Accounts are on when the app is given account settings or, given none, when
   `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set (empty counts as unset).
   Off, `/account`, `/api/account` and every path under it answer 404
   `{"detail": "Not Found"}` whatever the method. On, `GET /account` serves the
   client (503 while it is not built), another method on an account route
   answers 405, and every answer under `/api/account` has `Cache-Control:
   no-store`. On or off, a body over the limit gets the 413 of
   `platform/serving.md` rule 11 first, `no-store` too.
2. `main()` before serving, and an app given no settings when it starts, read
   (accounts off: only the first two): `NOCK_PUBLIC_URL`, `http://` or
   `https://`, a host as `NOCK_SMTP_HOST` takes but no IPv6, an optional
   `:port` as `NOCK_SMTP_PORT` takes, an optional `/` (dropped);
   `NOCK_SMTP_HOST`, as `NOCK_HOST`; `NOCK_SMTP_SECURITY`, exactly `starttls`
   (default), `tls` or `none`; `NOCK_SMTP_PORT`, as `NOCK_PORT`, by default
   587, 465 or 25; `NOCK_SMTP_USER` and `NOCK_SMTP_PASSWORD`, both or none,
   printable ASCII, no password with `none`; `NOCK_SMTP_FROM`, required,
   printable ASCII that rule 5 accepts.
3. A broken rule, or one of the first two alone, raises `SettingsError`
   naming the variable: one line with no character of category Cc, Cf, Zl or
   Zp, a refused value as `repr(value)`, a missing one with no value, never
   the password, even in part (nor the settings' `repr`). `main()` exits with
   it before serving; an app fails its start. The accounts live in the rooms'
   database, in memory as `platform/server.md` rule 1 says.

### Sign-in

4. An account is an address and a random id, created the first time a link
   sent to that address is used; asking for a link creates none.
5. An address is stored stripped and in small letters: at most 254 characters,
   one `@`, a local part of 1 to 64 ASCII letters, digits, `.` and
   ``!#$%&'*+-/=?^_`{|}~``, a domain of two or more labels of 1 to 63 ASCII
   letters, digits and hyphens, no label starting or ending with a hyphen.
6. `POST /api/account/link`, `{"email", "room"}` (`room` a room key or null),
   checks in order: the body (422); the address (422 `{"detail": "Invalid
   e-mail address"}`); the room (404 unless its token is a member's); the
   limits (429 `{"detail": "Too Many Requests"}`); then it mails: 202 `{}`,
   whether or not the address has an account, or 503 `{"detail": "Mail not
   sent"}`, logged at WARNING or above. Only a 202 or 503 counts: 3 per
   address and 10 per client address with a time `t > now - 3600`, in process
   memory. No account route uses the wrong-code throttle.
7. The e-mail goes from `NOCK_SMTP_FROM`, subject `email.sign_in.subject`,
   plain UTF-8 body `email.sign_in.body` with the link
   `<NOCK_PUBLIC_URL>/account#<token>`, 43 random URL-safe characters, never a
   request's `Host`. Only `src/nock/mailer.py` sends (`content/grids.md`): 10 s
   timeout, `tls` and `starttls` over TLS that checks the certificate and host
   name, a login when a user is set. A failure is `MailError`, whose text and
   traceback hold no address, password or token.
8. `POST /api/account/sign-in`, `{"token"}` (43 URL-safe characters, else
   422), deletes its link: unknown, or asked more than 1,800 s before, 404.
   Else the account is found or created, a session starts, and a link's room
   key still a member's links that member (rule 11) and is `room_code`, else
   null. 200 `{"email", "room_code", "rooms"}`, `rooms` as rule 12 lists them.
9. The session is the app's only cookie: `nock_session`, 43 random
   characters, `HttpOnly; Max-Age=7776000; Path=/; SameSite=Lax`, `Secure`
   behind an `https://` public URL, valid 90 days. A new sign-in ends no other
   session.
10. `GET /api/account` answers `{"signed_in": true, "email"}` or
    `{"signed_in": false, "email": null}`. `POST /api/account/sign-out`
    answers 204, ends the session if any and clears the cookie. Without a
    valid session, `GET` and `PUT /api/account/rooms`, `GET
    /api/account/history`, `GET /api/account/progress` and `DELETE
    /api/account` answer 401 `{"detail": "Not authorized"}`, before the body's
    fields are checked (a body that is not JSON is 422).

### The rooms of an account

11. `PUT /api/account/rooms` with a room key links that member (id and
    nickname from the room; again, it becomes newest): 204; no member's: 404;
    an account deleted since its session was checked: 401, nothing written.
    It records an identity for the account and links no member to it: a member
    is linked by a signed-in join, and an account is at most one player of a
    room, whose seat its signed-in joins reach (`lobby/joining.md` rule 4,
    `lobby/host.md` rule 10).
12. `GET /api/account/rooms` lists the latest identity per room, newest first,
    leaving out any whose token is no member's of the room under that code.
    The account keeps an identity until it is deleted.
13. The room and catalogue pages ask `GET /api/account` once when they load
    and show account controls only on a 200; the account page asks it at load
    unless the fragment holds a link token (rule 16). Signed in, a room page
    sends one `PUT` with its code and its first snapshot's token; the
    catalogue, before « Mes salons » asks, and the account page after a
    sign-in store each identity whose code has none on the device
    (`lobby/joining.md` rule 8), never replacing one, and add its code to
    `nock.account_rooms`, a JSON array of codes only the account code reads
    (anything else reads as empty).

### The account sheet and page

14. « Compte » opens the sheet: in a room from the Menu (`client/hud.md`); on
    the catalogue from the top bar, whose button's `aria-expanded` follows the
    sheet. A modal dialog named by its heading: focus goes to the address
    field, else its first control, and stays inside; Escape, « Fermer » or the
    backdrop, on a press and its release both on it, in a room or on the
    catalogue, close it and focus « Menu » or « Compte ». Signed out it shows
    `account.dialog_heading`, `account.dialog_intro` in a room or
    `account.signed_out_intro` outside, and the e-mail form; signed in
    `account.signed_in_heading`, `account.signed_in_as` and « Gérer mon
    compte » to `/account`.
15. The e-mail form (sheet and page) has the field `account.email_label` (type
    e-mail, the browser's address autocomplete) and the button `account.send`,
    disabled while waiting. It sends the typed address unchecked by the
    browser, with the page's room key in a room, else `"room": null`. 202:
    `account.sent`, a status. 422: `account.error.email`, the field marked
    invalid; 429: `account.error.too_many`; else `account.error.send`; each an
    alert that describes the field. A new submit clears the last answer.
16. `/account` is one card « Mon compte », in one state: `loading` (title
    only) until `GET /api/account` answers, then `signed_in`, `signed_out`
    (`account.signed_out_intro`, the form) or `error`
    (`account.error.generic`), also for a failed sign-out or deletion. A
    fragment of 43 URL-safe characters, at load or later, is dropped from the
    URL, then used: `signing_in` (« Connexion… »), then `signed_in` on a 200,
    `link_invalid` on a 404 (`account.link_invalid` above the form), else
    `error`.
17. Signed in: `account.signed_in_as`; « Retourner au salon <code> » to
    `/r/<code>` after a sign-in with a `room_code`; « Se déconnecter », ending
    on `signed_out`; « Supprimer mon compte », a disclosure of
    `account.delete_warning`, « Supprimer définitivement », which alone sends
    `DELETE /api/account`, and « Garder mon compte », which closes it and
    focuses the disclosure. A 204 ends on `deleted`: `account.deleted` and
    « Voir les grilles » to `/`. Before it shows `signed_out` or `deleted`, a
    204 removes, for each code of `nock.account_rooms`, its identity,
    `nock.room.<CODE>` and its records in `nock.history`, then the list; a
    seat the device took itself stays. A failed sign-out or deletion removes
    nothing.

### Erasure and what is kept

18. `DELETE /api/account` deletes in one transaction the account, its
    sessions, identities, history and its address's links, makes its players
    `--` among the other accounts' team-mates (rule 23) and writes the erasure
    as pending: the account id, the address, the request time and the code and
    player id of every identity it held, nothing else of them. It then runs
    one attempt of the erasure (rule 26) and answers 204, clearing the cookie,
    whatever the attempt did. Each write of the erasure that removes an
    address, a nickname or a player id ends with a checkpoint
    (`admin/operations.md` rule 20): once they have emptied the WAL, no copy
    of the address or of those nicknames is left in the database files. A
    checkpoint that stays busy leaves the answer a 204, and the next sweep
    empties the WAL.
19. No join can take `--`, and a past `--` is seated back as `--` with no
    suffix (`lobby/joining.md` rules 1 and 13); pages show it as « Ancien
    joueur » (`player.former`).
20. Links and sessions are stored as SHA-256 only; an identity holds its
    resume token in clear, since the account gives it back to its devices
    (rule 12): a copy of the database file resumes those players and signs
    nobody in. Each expiry sweep (`lobby/lifetime.md` rule 6), the first at
    the app's start, deletes the links older than 30 minutes, the sessions
    older than 90 days and the done erasures older than 5 years
    (`ERASURE_RECORD_LIFE_SECONDS`), then runs a checkpoint
    (`admin/operations.md` rule 20); a failed purge is logged and the next
    sweep runs.
21. No log record, traceback included, holds an address, a link token, a
    session, a resume token or the SMTP password. An anonymous player is
    stored as a nickname and random identifiers, nothing of their browser;
    playing sets no cookie.
26. An erasure runs in attempts: the route's, then one in each sweep
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
       among the team-mates of every history record (rule 23).

    When no step failed, the e-mail of rule 27 goes, then one write marks the
    erasure done: it keeps the request and completion times, the attempts, how
    many players it held, how many rooms step 2 deleted and the time the
    e-mail was accepted, or none; its account id, address and players go in
    that write. A done erasure is kept 5 years, then purged (rule 20); a
    pending one stays until an attempt ends it.
27. The e-mail goes once, in the attempt that ends the erasure, to the address
    the pending erasure holds, from `NOCK_SMTP_FROM`, subject
    `email.deleted.subject` (« Votre compte Nock a été supprimé »), plain
    UTF-8 body `email.deleted.body`, with no link: « Bonjour,\n\nVotre compte
    Nock et les données qui lui étaient liées ont été supprimés. Les salons
    que vous aviez créés sont fermés ; dans les autres, vous apparaissez comme
    « Ancien joueur ».\n\nSi vous n'aviez rien demandé, une personne connectée
    à ce compte l'a supprimé. », sent as rule 7 says. A `MailError` is logged
    (rule 21) and the erasure is marked done the same, with no e-mail time;
    nothing sends it again.
28. A device of the erased player that still holds its identity in a room
    (`lobby/joining.md` rule 8) enters it by that token with no form, as the
    member `--`, resumed or seated back (rule 19): its id, colour and letters
    kept, shown « Ancien joueur » to everyone, itself included, linked to no
    account and playing as an anonymous player. A session cookie of the
    deleted account reads signed out on every device.

### History records

22. An account's record of a solved room is saved once, by the first of `GET
    /api/account/history` (for each room of its identities) and the delete
    hook, which gets a room's latest state just before the sweep, a lookup or
    an erasure (rule 26) deletes it; a failing hook is logged and the deletion
    goes on. Only identities whose token is a member's of that room count, so a
    room that drew an old code saves nothing. A record: `code`, `grid_number`,
    `width`, `height`, `finished_at`, `elapsed_ms` (`gameplay/results.md` rule
    14) and `teammates`, the other members in `team_nicknames` order, each
    once. In the save's transaction, a team-mate whose code and player id a
    pending erasure holds, marked erased or not (rule 26), is written `--`.
23. `GET /api/account/history` lists the records, newest `finished_at` first,
    then by code. An erasure makes its players `--` among the others'
    team-mates: in the deletion's transaction (rule 18), at the last step of
    every attempt (rule 26) and in any record saved while it is pending (rule
    22), so a save that read the room before the erasure, or by the delete
    hook of a room an attempt deletes, never brings the nickname back.

### Grid progress

24. `GET /api/account/progress` answers the account's progress as
    `nock.progress` holds the device's (`content/library.md` rule 7): an object
    from grid numbers in decimal to `"finished"`, for each history record and
    each solved room of an identity rule 12 lists, or `"started"`, for each
    unsolved one and each creator room (`lobby/host.md` rule 11) that still
    exists; `finished` wins. A room or record with no grid number gives
    nothing; `{}` when nothing does. Derived at each request, nothing stored:
    it saves no record, and « Grilles terminées » lists every grid it marks
    `finished`, since rule 22 saves each solved room that counts here.

### Indexes

25. The account store creates, when it opens, the indexes its lookups read,
    changing no row: identities by room code, history team-mates by room code
    and player id, sign-in links by address, sessions by account.

### Look

- The sheet: `_design/room.md` « Room sheets: host settings and account ».
- The catalogue's « Compte »: `_design/pages.md` « Catalogue ».
- The account page and its deletion: `_design/pages.md` « Plain pages:
  account, shared recap, operator ».
- Its lines: `_design/pages.md` « States: opening, loading, empty, error ».

## Acceptance criteria

- **AC-1** From Ana's room, where she wrote `T`, a link for
  `Lea.Martin@Example.org` padded with spaces answers 202 `{}` and mails
  `lea.martin@example.org` rule 7's subject, body and link. Used, it answers
  200 with her room as `room_code` and her identity, `ANA`, in `rooms`, and
  sets rule 9's cookie; `GET /api/account` says signed in; the room's
  players, cells and log are unchanged and no socket hears of it.
  (← 033 AC-1)
- **AC-2** A link used again, or 1,801 s after it was asked, gets 404; used
  at 1,799 s, 200. A session signs in a second short of 90 days, not a second
  past. A second sign-in leaves the first working; behind `https://` the
  cookie has `Secure`. Two spellings of an address are one account; a player
  removed before the link is used gets `room_code` null. Purges at 1,801 s
  and 7,776,001 s delete a link and a session of time 0, no byte of the
  link's address left; at 1,799 s and 7,775,999 s they stay. (← 033 AC-1)
- **AC-3** Ana, signed in from R, solves it with Bob: her history is R's
  record, 5 × 5, solve time in UTC, `["BOB"]`; an unsolved room gives none, a
  room stored without solve times its logged ones. Swept unasked, a solved R
  keeps its record, and a raising hook is logged while the room still goes. A
  code reused by Bob and Cy's room gives Ana nothing. Once Zoé, of R too,
  deletes her account, Ana's R reads `["--", "BOB"]`, also with R expired
  unswept. (← 029 AC-3, 029 AC-6, 029 AC-7)
- **AC-4** An address with no `@`, nothing on one side, a one-label domain, a
  space, `ç`, `,`, `<` or `"` before the `@`, or 255 characters, gets 422
  `{"detail": "Invalid e-mail address"}`; a room key of no member or no room,
  404 `{"detail": "Not Found"}`; neither mails nor counts.
  `lea+1@example.org` is mailed as written. (← 033 AC-8)
- **AC-5** A fourth request for one address within the hour gets 429 and
  mails nothing, until the hour has passed; an eleventh from one client
  address, for eleven addresses, too. Requests older than 3,600 s no longer
  count; a 503 counts, a 429 does not; a new app starts from zero.
  (← 033 AC-8)
- **AC-6** Accounts off, `GET /account`, `GET` and `DELETE /api/account`,
  `POST` to `link`, `sign-in`, `sign-out`, `GET` and `PUT` to `rooms` answer
  404 `{"detail": "Not Found"}`. On, `GET /account` serves `index.html`, and a
  status, a link and a sign-in, accepted or refused, carry `Cache-Control:
  no-store`. (← 033 AC-8, 033 AC-1)
- **AC-7** `https://jeu.example/`, `smtp.jeu.example` and `nock@jeu.example`
  give `https://jeu.example`, port 587, `starttls`, no login; `tls` and
  `none` 465 and 25; `0002525` 2525; `::1` passes. Nothing set, or both empty
  beside a bad port, is off; an empty `NOCK_DATABASE` keeps accounts in
  memory. (← 033 AC-6)
- **AC-8** A public URL with `ftp://`, a path, a query, a user, port 0 or an
  IPv6 host; a host with a newline or a port; port `65536`; `STARTTLS`; a
  user with `ç`; a password with a newline, or with `none`; no sender; a
  public URL alone: each raises `SettingsError` naming its variable as rule 3
  says, and `python -m nock` exits with it before serving. (← 033 AC-6)
- **AC-9** With `none` an SMTP server receives one `text/plain` UTF-8 message
  from the sender with the link. With `starttls` the mailer connects with a
  10 s timeout, upgrades with a context that requires a certificate and
  checks the host name, logs in, sends, quits; `tls` uses that context from
  the start. A refused recipient raises `MailError` without the address,
  traceback included, and the request gets 503. (← 033 AC-7)
- **AC-10** Across a link, a sign-in, a status, a `PUT`, a sign-out, a failed
  mail and a deletion, no log holds the link token, the session, a resume
  token, the address or the SMTP password; the files hold the address, and
  the link and session only as SHA-256 hex. A sign-out answers 204 and ends
  the session, also when there is none. (← 033 AC-10)
- **AC-11** Signed in from R, Ana's rooms are R, with her id, token and
  `ANA`; after she puts S (204), S then R. A `PUT` of no member gets 404, one
  without cookie 401 even with a malformed key. Once R expires the list is S,
  also when a new room draws R's code. (← 033 AC-11, 033 AC-1)
- **AC-12** Device 1, as Ana in a room, signs in from « Compte »: `/account`
  loses the fragment and offers « Retourner au salon »; her room keeps her
  seat, colour and letters. Device 2 signs in from `/account` (`"room":
  null`) and enters as Ana with no form, replacing device 1
  (`lobby/joining.md` rule 11); its « Mes salons » lists the room, whose page
  sends one `PUT` after its first snapshot. A device holding Bob's identity
  there keeps it. (← 033 AC-2, 033 AC-11)
- **AC-13** With accounts on, a browser with no cookie or storage solves
  FX-01 with a word check: no 401 or 403, no cookie, the sheet never opens,
  every frame parses as a client message; solving from the catalogue, nothing
  sets a cookie and every request stays on the origin. An anonymous player who
  plays leaves only `ANA` and her id in the files, nothing of her browser's agent,
  headers, language or address. (← 033 AC-3, 038 AC-1, 038 AC-2)
- **AC-14** Zoé, in R with Bob, writes `T`, signs in, linked S where she
  timed out, and deletes her account: 204; her cookie reads signed out, her
  unused link 404. In R her record, named `--`, keeps its id, colour and `T`,
  her logged join reads `--`, a newcomer sees `--`; in S her past record is
  `--`. The files hold neither her address nor `ZOÉ`, still `BOB`, also after
  a restart, from a second app, and with no room. A `PUT` racing the deletion
  gets 401. A past `--` seated back beside a `--` is `--`. (← 033 AC-4)
- **AC-15** Then Bob's reloaded page names Zoé « Ancien joueur » in the
  roster, « Retirer Ancien joueur du salon » and the feed (« Ancien joueur a
  vérifié un mot »); « Mes salons » reads « Joueurs : Bob, Ancien joueur »;
  the recap names her « Ancien joueur ». No page shows `--`. (← 033 AC-5)
- **AC-16** « Compte », in the room Menu inside every supported window or a
  catalogue top-bar button, shows the focus ring from the keyboard
  (`product.md` rule 14); Enter opens the sheet on the field, and
  Escape focuses « Menu » or « Compte ». In a room, Tab and Shift+Tab stay
  in the sheet, a 202, 422, 429, 503 and 500 show rule 15's lines, and the
  open sheet keeps `product.md` rules 19 and 20. On the catalogue,
  `lea@example.org` goes with `"room": null` and shows the 202 line, and a
  phone's bottom sheet closes on a press on the backdrop. A 404: no
  « Compte ». (← 033 AC-9, 046 AC-3)
- **AC-17** Each state of rule 16 shows its line: after a 404,
  `account.link_invalid` above the form. A refused address marks the field; a
  new submit answered 202 unmarks it and shows `account.sent` with the typed
  address; a 429 leaves it unmarked. The lines follow "Look". In the states
  signed out, signed in, stale link and deleted the page keeps `product.md`
  rules 19 and 20; signed out and signed in, it has no sideways scroll at any
  supported window. (← 048 AC-5, 033 AC-9)
- **AC-18** Signed in after a link from `K7QM2X`, the card holds « Connecté
  avec <address> », « Retourner au salon K7QM2X » and the two actions,
  collapsed; asked, the deletion's warning and buttons sit in the card, and
  « Garder mon compte » leaves the focus on « Supprimer mon compte »; the
  confirm sends one `DELETE /api/account`. Signed in, no sideways scroll at
  320 by 568, a long address included; with the deletion asked, nothing on
  the page is red. (← 048 AC-3, 048 AC-4, 033 AC-5)
- **AC-19** Ana, signed in, is a member of R (grid 1, solved), S (grid 2,
  unsolved) and S2 (grid 3, unsolved), holds a record of a swept room of grid
  3, and created U (grid 4) without joining it: `GET /api/account/progress`
  answers exactly `{"1": "finished", "2": "started", "3": "finished", "4":
  "started"}` with `Cache-Control: no-store`, and `GET /api/account/history`
  asked next lists grids 1 and 3. An account with no room gets `{}`.
- **AC-20** Once S expires the answer loses `"2"`, also when a new room with
  S's code plays grid 2 with Bob and Cy; a solved room with no grid number
  gives nothing; R expired unswept still gives `"1": "finished"`.
- **AC-21** Without a cookie `GET /api/account/progress` answers 401
  `{"detail": "Not authorized"}`; accounts off, 404 `{"detail": "Not
  Found"}`.
- **AC-22** Zoé, in R, deletes her account while a second connection to the
  file holds a read open: the answer is 204 within 2 seconds, her cookie then
  reads signed out, and WARNING records are logged.
  Once that connection closes, the next sweep leaves neither her address nor
  `ZOÉ` in the database file or its WAL.
- **AC-23** A database holding accounts, sessions, links, identities and
  history records opens in the account store with every row as it was; there,
  as in a new database, SQLite's query plan for each lookup of rule 25 reads
  an index, not a scan of its table.
- **AC-24** Zoé, in R (live) and S (stored) and creator of U, deletes her
  account: 204; R's and S's players are `--`, U is gone, and her address
  receives one e-mail from `NOCK_SMTP_FROM`, subject « Votre compte Nock a été
  supprimé », plain UTF-8 body exactly rule 27's text, with no link.
  `account_erasures` then holds one row: `account_id` and `email` null,
  `requested_at`, `done_at` and `notified_at` set, `attempts` 1, `players` 2,
  `rooms_deleted` 1; `account_erasure_players` is empty; the files hold
  neither her address nor `ZOÉ`.
- **AC-25** Zoé, in live rooms R and S and creator of U, deletes her account
  while S's engine is held in a step for more than 5 s: 204 within 7 s, her
  cookie reads signed out, one WARNING record is logged, R's player is `--`,
  U is gone, no e-mail is sent; her erasure is pending, holding R's player
  marked erased and S's not, `attempts` 1, and the files hold her address and
  S's `ZOÉ`.
  Once S's engine answers, the next sweep, or the first of an app started on
  that database, makes S's player `--`, sends the e-mail and marks the
  erasure done, `attempts` 2, `players` 2, `rooms_deleted` 1; the files then
  hold neither her address nor `ZOÉ`, and a later sweep sends nothing.
- **AC-26** With the mailer raising `MailError` at completion, the deletion
  answers 204, one WARNING record is logged without the address, the erasure
  is done with `notified_at` null, the files hold no address, and no later
  sweep sends anything.
- **AC-27** Zoé, in R and S, deletes her account while S's engine is held
  for more than 5 s: R's player is `--` and her erasure is pending. Bob's
  record of solved R, read before her deletion and saved now, names her `--`
  among its team-mates; so does one saved after a second attempt that S still
  holds up, and the record the delete hook saves when an attempt deletes her
  expired room T.
- **AC-28** Zoé's device, holding her R identity, reloads R after her
  deletion: it enters with no form as the player `--`, named « Ancien joueur »
  in its own roster with her colour and letters, a letter it types is
  applied, and `GET /api/account` there reads signed out.
- **AC-29** A done erasure of time 0 is deleted by the purge at 157,680,001 s
  and kept at 157,679,999 s, no other row touched.
- **AC-30** Zoé, in live room R and creator of U, deletes her account while
  R's engine is held for 1 s, and a sweep starts during the route's attempt:
  once both are over, R's player is `--`, U is gone, her address received
  one e-mail, and the erasure is done with `attempts` 1 and `rooms_deleted`
  1.
- **AC-31** Ana's account lists R and T; her device holds its own seat in T,
  `nock.room.R` and history records of R and T. She signs in from `/account`
  (which stores R), her account links S from another device, and `/` loads
  (which stores S): the device holds R's and S's identities, T's unchanged.
  « Se déconnecter », answered 204, shows `signed_out`; the device then holds
  no identity, room record or history record of R or S and no
  `nock.account_rooms`, T's identity and its history record stay, and « Mes
  salons » on `/` lists T alone.
- **AC-32** On AC-31's device before the sign-out, « Supprimer définitivement »,
  answered 204, shows `deleted` and leaves the device as AC-31's sign-out
  does.
- **AC-33** On AC-31's device before the sign-out, a sign-out answered 500,
  or a deletion answered 500, shows `account.error.generic`, and every
  identity, room record, history record and `nock.account_rooms` stays as it
  was.
- **AC-34** In a room at 1280 by 720 and on the catalogue at 360 by 740, with
  `lea@exa` typed in the account sheet, a press in the field released on the
  backdrop leaves the sheet open with `lea@exa` still typed; a press and its
  release both on the backdrop close it.

## Edge cases

- A mail scanner uses nothing: the token is in the fragment (AC-12).
- An erased player's open pages keep the old name until their next snapshot
  (AC-15).
- A creator room is deleted whoever is host in it then; an anonymous room where
  the account's player is host stays, that player `--` (`lobby/host.md`
  AC-15).
- A solved creator room the account never joined is `started`, as its history
  never lists it (AC-19).
- A held player's room that expired meanwhile is deleted by step 1, its hook
  saving the nickname, which step 3 erases (AC-27).
- An app stopped between the e-mail and the write that marks the erasure done
  sends it again at its next attempt (AC-25).
- A sweep that starts during the route's attempt leaves that erasure to it
  (AC-30).
- With accounts in memory (rule 3), a pending erasure goes with the app.
- The deleted account's sessions are gone, so a second `DELETE` from another
  device gets 401 (AC-14).

## Out of scope

- Passwords, social sign-in, changing or adding an address, merging
  accounts, other e-mails; an export of the account, a confirmation link or a
  grace period before deleting, keeping creator rooms alive; erasing chat
  lines or backups; an IPv6 public URL.
- Pushing a device's progress up to the account; a guest's progress across
  devices. How the pages merge the account's progress with the device's:
  `content/library.md`.
- Catch-up, kept per device: `social/catch-up.md`.
- Forgetting on the device a seat whose room the summaries no longer return;
  forgetting the account's seats when a session expires with no sign-out
  (they stay until the next sign-out on that device).
- Logs and retention: `admin/operations.md`.

## Code

- `src/nock/accounts.py` (with its indexes, checkpoints and the pending
  erasures), `settings.py` (`account_settings_from_env`), `mailer.py` (the two
  messages), `i18n.py`, `server.py` (routes, limits, the erasure's attempts,
  purge).
- `room.py` (`FORMER_PLAYER_NICKNAME`, `with_player_erased`, `member_id`),
  `store.py` (`erase_player`), `hub.py` (`erase_player`, the creator rooms'
  deletion, the delete hook).
- `web/src/lib/account.ts`, `Account*.svelte`, `RoomMenu.svelte`,
  `CataloguePage.svelte`.
- Tests: those of the pointers, in `tests/test_spec_NNN_*`;
  `tests/test_account_*` (the progress route, AC-22 to AC-33).
