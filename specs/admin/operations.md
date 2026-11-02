---
area: admin
file: operations
status: approved
---

# admin/operations - Logs, retention, the operator token and the ops API

## Purpose

Nock keeps as little data as it can: the server logs no address or secret, and a
room's data goes at expiry with no copy left. The ops API gives an operator with
the token the figures of recent rooms and one room's edits; the page that shows
them is `admin/ops-page.md`.

## Depends on

- `lobby/lifetime.md`: room expiry, what a deletion removes and the shortest
  room life (rules 4 to 6).
- `lobby/rooms.md`: the wrong-code throttle (rule 9), whose second instance
  guards the ops API.
- `platform/server.md`: the store and its room log; serving and the other
  settings are `platform/serving.md`.

## Rules

### Logs

1. `python -m nock` has no access log and logs at `warning` (`product.md` rule
   27): its output holds no client address and no request line. The app's
   `nock.*` records, at every level, never hold a client address, a resume
   token, the operator token or a chat text; a traceback may show a room's game
   data, such as a nickname.

### Retention

2. A room's data (rows, snapshots, log, nicknames, resume tokens, chat texts)
   lives until the room is deleted (`lobby/lifetime.md` rules 5, 6). The store
   zeroes deleted rows and, on a file, a checkpoint (rule 20) follows each
   deletion, or each sweep's deletions: once a checkpoint has emptied the WAL,
   none of the deleted room's rows stays in the database file or its WAL, the
   store open or closed. A snapshot that a save deletes (`platform/server.md`
   rule 4) is zeroed like any deleted row, with no checkpoint of its own: its
   pages leave the WAL at the next checkpoint, at the latest the next sweep's;
   what it held stays in the room's newest snapshot and log until the room is
   deleted. With accounts on, which share that database,
   an account keeps its identity in the room (code, player id, resume token,
   nickname) and its record of a solved room until the account goes, and a
   pending sign-in link its room key until used or expired
   (`account/account.md` rule 12, `account/erasure.md` rule 8). A deleted
   account's erasure keeps its address and its players' codes and ids until it
   is done, then its times and counts alone for 5 years (`account/erasure.md`
   rules 5, 6).
3. Memory holds the live rooms and, per app and throttle, the addresses with
   failures and their times, never the code or token that failed, forgotten as
   `lobby/rooms.md` rule 9 says; with accounts on, also the link limits of
   `account/account.md`.
20. A checkpoint copies the WAL into the database file and empties it
    (`PRAGMA wal_checkpoint(TRUNCATE)`), on a file only, through
    `checkpoint_wal` (`src/nock/store.py`). A try never waits on SQLite's
    busy handler: the connection's busy timeout is 0 for the checkpoint and
    restored after it. It reads the result's `busy` column: busy, it tries
    once more at once; still busy, it logs one record at
    WARNING and gives up, the deleted rows' old pages staying in the WAL until
    a later checkpoint empties it, at the latest the next sweep's
    (`lobby/lifetime.md` rule 6). A busy checkpoint never fails its request:
    the deletion, erasure or purge it follows stands and answers as usual.
    One runs after each room deletion outside a sweep, once per sweep, and
    after each of `erase_player`, `delete_account`,
    `erase_players_from_history`, `finish_erasure` and `purge`
    (`account/erasure.md` rules 1, 3, 5), the writes that remove an
    address, a nickname or a player id; no other write of an erasure (an
    attempt's count, a player's mark, a room's count) runs one, nor does a
    snapshot's save.

### Operator token

4. `NOCK_OPERATOR_TOKEN` is 32 to 256 characters of `A-Z`, `a-z`, `0-9`, `_`,
   `-`; unset or empty, the operator pages are off. Any other value:
   `python -m nock`, checking it before its other variables, prints a message
   naming the variable and the rule, never the value, and exits 1 without
   serving; an app built otherwise fails its startup with `SettingsError`. The
   app reads it when it starts.
5. A token given to `create_app` is checked by the same rule when `create_app` is
   called, and the variable is not read: `""` turns the pages off; a value that
   breaks the rule raises `SettingsError`, whose message never holds it.

### Operator pages off

6. Any method on `/api/ops` or under `/api/ops/` answers as on an unknown path
   under `/api/`: 404 `{"detail": "Not Found"}`, no `Cache-Control`, no token
   check, nothing counted. `GET /ops` answers as an unknown path (404); another
   method on `/ops` 405, as on any unknown one-segment path such as `/xyz`, and
   as while the pages are on. A body over the limit gets the 413 of
   `platform/serving.md` rule 11 first, as on any path.

### Operator pages on: the ops API

7. `GET /api/ops/dashboard?days=N`, `N` an offered period (rule 12), the
   default one when absent: 200, rule 12's figures; another `N`, a period not
   offered included: 422.
   `GET /api/ops/rooms/<code>/edits`: 200, `admin/ops-page.md` rule 2's
   replay; 404 for an unknown
   or expired room or a code that is not 6 capitals or digits. Neither makes a
   room live.
8. On those two routes and the three settings routes (`admin/overrides.md`
   rules 3 to 5), in this order: an address with 10 refusals under 60
   seconds old gets 429 `{"detail": "Too Many Requests"}`, whatever its token,
   not counted; a request without `Authorization: Bearer <token>` (the scheme
   in any case, `bearer` or `BEARER` too, then one space; the token compared in
   constant time; never read from the query, a cookie or the URL) gets 401
   `{"detail": "Not authorized"}` with `WWW-Authenticate: Bearer` and counts one
   refusal; only then are its `days`, code, room or body read.
9. The refusals are a second instance of the wrong-code throttle (`lobby/rooms.md`
   rule 9), per app, apart from wrong room codes. Only a 401 counts.
10. Any other request under `/api/ops/` gets FastAPI's 404 (unknown path) or 405
    (another method on a route's path), with no token check, not counted. Every
    answer under `/api/ops/`, refusals included, has `Cache-Control: no-store`;
    `/api/ops` itself answers a plain 404 without it, for every method. A body
    over the limit gets the 413 of `platform/serving.md` rule 11, `no-store`
    too, before any of this.
11. `GET /ops` serves `index.html` to anyone, without a token, or 503 as `/` when
    the client is not built.

### Dashboard figures

12. The periods are 1, 7 and 30 days. A period is offered when it is no longer
    than the shortest room life (`lobby/lifetime.md` rule 4), read from the
    effective lives at each request (`admin/overrides.md` rule 2), so 1 always
    is; the default period is 7 when offered, else 1. The rooms of a period are
    those created at or after `now − days × 86 400 s`, read with their whole
    logs from the store; within an offered period none has expired. The answer
    holds `days`, `offered_days` (the offered periods, rising), `since` (that
    start, in UTC) and the figures. A figure with nothing to count is None, but
    `rooms_created` is 0:
    - `rooms_created`: how many rooms;
    - `players_per_room`: `player_joined` entries per room;
    - `completion_rate`: the share of rooms whose log holds a `grid_solved`;
    - `median_solving_ms`: the median of their `elapsed_ms` (`gameplay/rules.md`);
    - `latency_median_ms`, `latency_p95_ms`: the median and the ⌈0.95 n⌉-th
      smallest of the `relay_ms` of the `letter_changed` entries that have one;
    - `disconnection_rate`: drops per `player_joined`; a drop is a
      `player_state_changed` to `disconnected` followed by one to `active` of the
      same player, before their next `disconnected` and any `player_left`.

### Relay time

13. Each log entry of a step started by a client message (a join, or a joined
    player's message) has `relay_ms`, an integer ≥ 0: the whole milliseconds,
    rounded down, from the server reading the frame to handing the step's entries
    to the store; the inbox wait counts, the commit and the network do not. Other
    steps (a tick, the restart step, a closed socket) and older entries have
    none. It is private: no message to a client holds it. Its budget:
    `product.md` rule 24.

## Acceptance criteria

- **AC-1** `python -m nock` serving a page that joins as `Ana`, types three
  letters, chats `chat-probe-5521`, asks the dashboard with a wrong then the
  right token and loads `/nothing-here` writes none of `127.0.0.1`, `GET /`,
  `WebSocket /`, Ana's resume token, the chat text or the token; the same session
  in process logs no `nock.*` record at `DEBUG` holding one. (← 038 AC-3)
- **AC-2** Room A (`Zélie`, `Bob`, the chat `chat-secret-4711`, letters, a check)
  expires: once `expire_rooms()` deletes it, the database file and WAL hold
  neither the chat text, `ZÉLIE`, A's code nor its resume tokens, the store open
  or closed, while room B keeps `chat-kept-8203` and `YANN`. A room of Ana and
  Bob deleted by the sweep alone leaves, within 2 seconds, none of its chat
  text, `ANA`, `BOB`, its code or tokens. (← 038 AC-4)
- **AC-3** R1 (2 days old: 3 joins, relay times 10, 20, 30, 40 and none, one drop,
  one player gone for good, solved in 600,000 ms), R2 (1 day: 1 join, relay 50,
  solved in 900,000 ms), R3 (3 days: 2 joins, two drops), R4 (8 days, solved):
  7 days give 3 rooms, 2.0, 2/3, 750000.0, 30.0, 50 and 0.5; 1 day only R2 (1,
  1.0, 1.0, 900000.0, 50.0, 50, 0.0); no room 0 and None; 2 days `ValueError`.
  (← 038 AC-5)
- **AC-4** With the token and the default lives, the dashboard answers 200 with
  the 7-day figures of the rooms created 7 days and 1 day ago, not 8, none made
  live, `days` 7 and `offered_days` `[1, 7, 30]`; `?days=30` gives `days` 30
  and `?days=2` 422. With `NOCK_CREATOR_SOLVED_ROOM_HOURS` 168, no `days` gives
  the 7-day figures with `[1, 7]` and `?days=30` 422; at 24, the 1-day figures
  with `[1]`. (← 038 AC-6)
- **AC-5** No header, a wrong token, `Basic <token>` or `?token=<token>` get
  rule 8's 401, as do `?days=2` and the edits of `abc` without the token.
  (← 038 AC-6)
- **AC-6** After 10 refusals the right token gets 429, and 200 again 60 seconds
  after the last; 40 wrong tokens at once get ten 401 and thirty 429; 10 replay
  404s, a second app's refusals or wrong room codes block nothing.
  (← 038 AC-6)
- **AC-7** With the variable unset, `GET`, `POST` and `DELETE` with the token
  on the two routes, `/api/ops`, `/api/ops/` and `/api/ops/xyz` answer as on
  `/api/xyz/dashboard`; with it empty, or `create_app(operator_token="")`
  whatever it holds, `GET` on the routes does too; and `GET /ops` answers as an
  unknown path. (← 038 AC-6, 038 AC-10)
- **AC-8** Pages on: the routes' 200, 422, 404, 401 and 429 have `no-store`,
  as do `GET /api/ops/xyz` (404) and `POST` on the dashboard (405), uncounted;
  `GET /ops` serves `index.html` to a blocked address. (← 038 AC-6)
- **AC-9** The variable gives off when unset or empty and the token at 32 or 256
  allowed characters; 31 or 257, `$`, a space or `é` are refused, naming the
  variable and not the value; `python -m nock` with a 6-character value says so
  and exits 1 without serving; `create_app(operator_token="a")` raises
  `SettingsError`. (← 038 AC-10)
- **AC-10** With the store blocking, a first edit logs `relay_ms` under 250 and a
  second, held 300 ms in the inbox behind it, at least 250; the join logs an
  integer; the closed socket's disconnection, a tick and the restart step none;
  no client message holds `relay_ms`; −1 and `"5"` are refused. (← 038 AC-11)
- **AC-21** With the right token, `Authorization: bearer <token>`, `BEARER
  <token>` and `bEaReR <token>` each get the dashboard's 200, 12 times in a row
  from one address with no 429.
- **AC-22** `checkpoint_wal` on a connection whose first checkpoint reports
  busy and whose second does not runs two checkpoints, returns True and logs
  nothing; on one that reports busy twice it runs exactly two, logs one
  `nock.*` record at WARNING and returns False without raising.
- **AC-25** On a file connection whose busy timeout is 5 s, while a second
  connection holds a read open on the file, `checkpoint_wal` returns False in
  under 1 second, and the connection's busy timeout is 5 s again afterwards.
- **AC-23** On a file database, `delete_room`, `RoomStore.erase_player`,
  `delete_account`, `erase_players_from_history`, `finish_erasure` and
  `purge` each run one checkpoint through `checkpoint_wal`; with it returning
  False each still does its work (the room gone, the nickname `--`, the
  account gone, the erasure done with no address, the old link purged) and
  returns as usual; `begin_attempt`, `mark_player_erased`,
  `count_deleted_room` and a `save_snapshot` that deletes an older snapshot
  run none. On an in-memory store none runs.
- **AC-24** Room A, with the chat `chat-busy-6610`, expires and a lookup
  deletes it while a second connection to the file holds a read open: the
  lookup returns within 1 second, A's code is then unknown, one WARNING is
  logged and the WAL is not empty. Once that connection closes, the next
  sweep, which deletes nothing, leaves the WAL at 0 bytes, and neither file
  holds the chat text or A's code.

## Edge cases

- A room created exactly `days × 86 400 s` ago is in the period (AC-3).
- A player who times out and is seated back is no drop (AC-3).
- A checkpoint busy at every sweep leaves the deleted pages in the WAL until
  one finds it free (AC-24).

## Out of scope

- Backups, log retention, the host's own logs; operator accounts, rotating the
  token without a restart.
- The `/ops` page: the token form, the dashboard card, the replay of a room's
  edits: `admin/ops-page.md`.
  An anonymous player's stored data, cookies, the player's own data:
  `account/account.md`.
  The other environment variables: `platform/serving.md`, `lobby/lifetime.md`.
  Overriding the room lives and the sweep interval from `/ops`, the settings
  routes and card: `admin/overrides.md`.

## Code

- `src/nock/operations.py`: figures, periods. `src/nock/server.py`: ops routes,
  guard, throttles, `/ops`. `src/nock/settings.py`: `operator_token_from_env`.
  `src/nock/store.py`: deletion, `checkpoint_wal`, `codes_created_since`.
  `src/nock/accounts.py`: its checkpoints. `src/nock/hub.py`: `relay_ms`.
  `src/nock/__main__.py`: `main()`.
- Tests: `tests/test_spec_038_ac03*` to `ac06*`, `ac10*`, `ac11*`;
  `tests/test_operations_*` for AC-21 to AC-25.
