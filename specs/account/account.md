---
area: account
file: account
status: approved
---

# account/account - Optional account

## Purpose

A player who wants their rooms, and the progress of their grids, on every
device signs in with a link sent by e-mail; nothing else needs an account.
This file holds the settings, the sign-in, the session and the account's
rooms; the sheet and the page are `account/my-account.md`, what the deletion
erases and keeps `account/erasure.md`.

## Depends on

- `lobby/joining.md`: identities, members, seat back; « Mes salons » is
  `lobby/summaries.md`.
- `platform/serving.md`: `main()`, `NOCK_HOST`, `NOCK_PORT`, `NOCK_DATABASE`;
  the store that file names is `platform/server.md` rule 1.

## Rules

### Accounts on or off

1. Accounts are on when the app is given account settings or, given none, when
   `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set (empty counts as unset).
   Off, `/account`, `/api/account` and every path under it answer 404
   `{"detail": "Not Found"}` whatever the method. On, `GET /account` serves the
   client (503 while it is not built), another method on an account route
   answers 405 `{"detail": "Method Not Allowed"}`, and every answer under `/api/account` has `Cache-Control:
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
   name, a login when a user is set, one `QUIT` per message and no command
   once the connection is closed. A failure is `MailError`, whose text and
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
    `lobby/creator.md` rule 1).
12. `GET /api/account/rooms` lists the latest identity per room, newest first,
    leaving out any whose token is no member's of the room under that code.
    The account keeps an identity until it is deleted.

### Indexes

25. The account store creates, when it opens, the indexes its lookups read,
    changing no row: identities by room code, history team-mates by room code
    and player id, sign-in links by address, sessions by account.

## Acceptance criteria

- **AC-1** From Ana's room, where she wrote `T`, a link for
  `Lea.Martin@Example.org` padded with spaces answers 202 `{}` and mails
  `lea.martin@example.org` rule 7's subject, body and link. Used, it answers
  200 with her room as `room_code` and her identity, `ANA`, in `rooms`, and
  sets rule 9's cookie; `GET /api/account` says signed in; the room's
  players, cells and log are unchanged and no socket hears of it.
  (← 033 AC-1)
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
  `POST` to `link`, `sign-in`, `sign-out`, `GET` and `PUT` to `rooms`, and
  the wrong methods `GET` to `link` and `POST /account`, answer 404
  `{"detail": "Not Found"}`. On, `GET /account` serves `index.html`, those
  two wrong methods answer 405 `{"detail": "Method Not Allowed"}`, and a
  status, a link and a sign-in, accepted or refused, and the `GET` to `link`
  carry `Cache-Control: no-store`. (← 033 AC-8, 033 AC-1)
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
  checks the host name, logs in, sends, then issues `QUIT` once and no
  command after it; `tls` uses that context from the start. A refused
  recipient raises `MailError` without the address, traceback included, and
  the request gets 503. (← 033 AC-7)
- **AC-11** Signed in from R, Ana's rooms are R, with her id, token and
  `ANA`; after she puts S (204), S then R. A `PUT` of no member gets 404, one
  without cookie 401 even with a malformed key. Once R expires the list is S,
  also when a new room draws R's code. (← 033 AC-11, 033 AC-1)
- **AC-23** A database holding accounts, sessions, links, identities and
  history records opens in the account store with every row as it was; there,
  as in a new database, SQLite's query plan for each lookup of rule 25 reads
  an index, not a scan of its table.

## Edge cases

- A mail scanner uses nothing: the token is in the fragment
  (`account/my-account.md` AC-1).

## Out of scope

- Passwords, social sign-in, changing or adding an address, merging
  accounts, other e-mails; an IPv6 public URL.
- `DELETE /api/account` and the erasure it starts, what is kept, « Ancien
  joueur », the history records, the account's grid progress; how links and
  sessions are stored and purged, and what no log holds:
  `account/erasure.md`.
- The sheet, the page, what the device stores and forgets for the account:
  `account/my-account.md`.
- Catch-up, kept per device: `social/catch-up.md`.
- Logs and retention: `admin/operations.md`.

## Code

- `src/nock/accounts.py` (accounts, sessions, links, identities, its indexes),
  `settings.py` (`account_settings_from_env`), `mailer.py` (the sign-in
  message), `i18n.py`, `server.py` (routes, limits).
- Tests: those of the pointers, in `tests/test_spec_NNN_*`;
  `tests/test_account_*` (AC-6 for its wrong methods, AC-23).
