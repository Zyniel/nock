# Settings

Not a spec. Every setting of Nock, its scope and the domain file and rule that
own it. The owner states the behaviour; this file only lists values and
defaults.

## Player (per browser)

Kept in `localStorage`, for every room of the browser; they send nothing.

| Setting (UI) | Values, default first | Key | Owner |
| --- | --- | --- | --- |
| « Auteurs » (Menu) | off, on | `nock.authors`: `"true"` or `"false"` | `social/presence.md` 14 |
| « Mots des autres » (Menu) | on, off | `nock.others_tint`: `"false"` is off | `gameplay/board.md` 18 |
| « Accessibilité » (Menu) | off, on | `nock.accessibility`: `"true"` is on | `gameplay/board.md` 18 |
| « Masquer le chrono » (Menu) | shown, hidden | `nock.timer_hidden` = `true` while hidden, else absent | `gameplay/rules.md` 13 |
| « Clavier » (top bar, touch screen) | shown, hidden | `nock.keyboard_hidden` = `true` while hidden, else absent | `gameplay/board.md` 16 |
| « Salon » (column layout) | open, closed | `nock.salon_closed` = `true` while closed, else absent | `client/room.md` 2 |

The other keys hold data, not settings: `nock.nickname` and
`nock.identity.<CODE>` (`lobby/joining.md`), `nock.room.<CODE>`
(`lobby/rooms.md`), `nock.progress` (`content/library.md`), `nock.history`
(`gameplay/results.md`), `nock.account_rooms` (`account/account.md`). The operator token sits in the tab's
`sessionStorage` (`admin/operations.md`).

## Host (per room)

Set in « Réglages de l'hôte » (`lobby/host.md` rule 8), sent in
`settings_changed`; a new room's values: `lobby/rooms.md` rule 7.

| Setting (UI) | Values, default first | Owner |
| --- | --- | --- |
| « Verrouiller le salon » | off, on | `lobby/host.md` 3 |
| « Aide » | « libre » (`free`), « par vote » (`vote`), « désactivée » (`none`) | `gameplay/hints.md` 1 |
| « Lettres à révéler » | 5; 0 to 99 on the page, any count from 0 on the server | `gameplay/hints.md` 8 |
| « Mots à révéler » | 1; 0 to 99 on the page, any count from 0 on the server | `gameplay/hints.md` 8 |

## Server (environment)

Read by `python -m nock` before it serves (`platform/serving.md` rule 6). An
empty variable counts as unset.

| Variable | Meaning | Default (unset) | Owner |
| --- | --- | --- | --- |
| `NOCK_HOST` | address to listen on | `127.0.0.1` | `platform/serving.md` 7 |
| `NOCK_PORT` | port to listen on | 8000 | `platform/serving.md` 8 |
| `NOCK_DATABASE` | SQLite file of the rooms and accounts | in memory, no file | `platform/serving.md` 9; `platform/server.md` 1 |
| `NOCK_OPERATOR_TOKEN` | secret of the `/ops` pages | operator pages off | `admin/operations.md` 4 |
| `NOCK_CREATOR_SOLVED_ROOM_HOURS` * | life of a solved creator room, from its solve time (whole hours, 24 to 8760) | 720 | `lobby/lifetime.md` 4, 7 |
| `NOCK_CREATOR_ROOM_HOURS` * | life of an unsolved creator room, from its last edit (whole hours, 24 to 8760) | 720 | `lobby/lifetime.md` 4, 7 |
| `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` * | life of a solved anonymous room, from its solve time (whole hours, 24 to 8760) | 720 | `lobby/lifetime.md` 4, 7 |
| `NOCK_ANONYMOUS_ROOM_HOURS` * | life of an unsolved anonymous room, from its last edit (whole hours, 24 to 8760) | 720 | `lobby/lifetime.md` 4, 7 |
| `NOCK_EXPIRY_SWEEP_MINUTES` * | how often the expired rooms are deleted (whole minutes, 1 to 1440) | 60 | `lobby/lifetime.md` 6, 7 |
| `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` | rooms one client address may create in an hour (whole number, 1 to 10000) | 30 | `lobby/rooms.md` 13, 14 |
| `NOCK_SOCKETS_PER_ADDRESS` | room sockets one client address may hold open at once (whole number, 1 to 10000) | 50 | `platform/realtime.md` 2, 26 |
| `NOCK_PUBLIC_URL` | public URL of the sign-in links | accounts off | `account/account.md` 1, 2 |
| `NOCK_SMTP_HOST` | mail server | accounts off | `account/account.md` 1, 2 |
| `NOCK_SMTP_SECURITY` | `starttls`, `tls` or `none` | `starttls` | `account/account.md` 2 |
| `NOCK_SMTP_PORT` | mail server's port | 587, 465 or 25, by security | `account/account.md` 2 |
| `NOCK_SMTP_USER` | mail login, with the password | no login | `account/account.md` 2 |
| `NOCK_SMTP_PASSWORD` | mail password, a secret | no login | `account/account.md` 2 |
| `NOCK_SMTP_FROM` | sender address | none: required with accounts on | `account/account.md` 2 |

Accounts are on when `NOCK_PUBLIC_URL` and `NOCK_SMTP_HOST` are both set; the
other `NOCK_SMTP_*` are read only then.

\* The operator can override these five from `/ops`, within the same bounds:
the override, stored in the room store (table `overrides`; in memory when
`NOCK_DATABASE` is unset), outranks the variable until reset. Owner:
`admin/overrides.md`.
