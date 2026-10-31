---
area: admin
file: operations
status: approved
---

# admin/operations - Logs, retention and the operator pages

## Purpose

Nock keeps as little data as it can: the server logs no address or secret, and a
room's data goes at expiry with no copy left. An operator with the token reads, on
`/ops`, the figures of recent rooms and replays one room's edits.

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
   store open or closed. With accounts on, which share that database,
   an account keeps its identity in the room (code, player id, resume token,
   nickname) and its record of a solved room until the account goes, and a
   pending sign-in link its room key until used or expired
   (`account/account.md` rules 12, 22). A deleted account's erasure keeps its
   address and its players' codes and ids until it is done, then its times
   and counts alone for 5 years (`account/account.md` rules 26, 27).
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
    (`account/account.md` rules 18, 20, 26).

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
   `GET /api/ops/rooms/<code>/edits`: 200, rule 15's replay; 404 for an unknown
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

### Replay

14. The edits are the log's `letter_changed` and `cell_locked` entries in seq
    order, each with its seq, time (UTC), cell and the event's letter. A letter
    change that undoes is `undone`, else `typed` with a letter or `erased`
    without; a lock is `locked` (a check) or `revealed`. A letter change keeps its
    pencil flag, its player id and the nickname of that player's latest
    `player_joined` before it, as stored; a lock has no player, nickname or
    pencil, and an edit with no join before it no nickname.
15. The replay is the room's code, its grid with no letter and no answer, and its
    edits.

### The operator page

16. `/ops` (heading `ops.heading`) is `locked` on the token form until a token is
    given or found in the tab's `sessionStorage`, its only place (never
    `localStorage`, a cookie or a URL). The form holds a password input with
    autocomplete off, `ops.token_label`, and the button `ops.token_submit`.
    Every ops request sends the token in its header. Then `loading`
    (`ops.loading`) until the dashboard, asked with no period, answers: 200
    `ready`; any 401 or 429 of
    the page, dashboard, settings card (`admin/overrides.md`) or replay,
    forgets the token and goes back to `locked`
    with `ops.token_refused` or `ops.throttled`; another dashboard answer (a 404
    or a malformed 200 too) or a network failure gives `error` (`ops.error`)
    until a reload.
17. `ready` shows the card `ops.dashboard_heading`, then the settings card
    (`admin/overrides.md` rule 11), then the replay card (rule 19). The
    dashboard card: the group `ops.period_label`
    of one chip per offered period of the answer, `ops.period.one_day`,
    `ops.period.seven_days`, `ops.period.thirty_days` in that order, the
    answer's `days` pressed, then the six figures in rule 12's order (the
    latency as one), each its `ops.metric.*` line in French notation: players
    per room with one decimal; the rate rounded to whole percent
    (`ops.percent`, 0.126 reads « 13 % »); the latency `ops.latency_value`, both
    rounded to whole milliseconds (30.6 reads 31); disconnections with two
    decimals; the time in whole seconds rounded down, as `duration.minutes`
    under one hour, seconds on two digits (5,999 ms reads « 0 min 05 s »), else
    `duration.hours`, minutes and seconds on two digits (3,725,999 ms reads
    « 1 h 02 min 05 s »). None reads `ops.no_data`.
18. A period press keeps the page `ready`, with the dashboard, the replay and the
    focus on the button, and changes the figures and the pressed period on the
    answer; a 401 or 429 locks, another answer gives `error`. An answer that
    finds the page no longer `ready` changes nothing.
19. The card `ops.replay_heading` holds a form, the field `ops.replay_code_label`
    and the button `ops.replay_submit`. It sends the code in capitals and shows
    under the form `loading` (`ops.loading`), `not_found` (a 404,
    `ops.replay_not_found`), `error` (any other failure, `ops.error`) or
    `ready`, the dashboard staying above. A room with no edit shows only
    `ops.replay_empty`. Otherwise: every edit by its `ops.edit.*` line
    (`typed_pencil` for a pencil letter), its time as fr-FR hours, minutes and
    seconds on two digits in the browser's zone, the nickname as
    `lobby/joining.md` rule 3 shows it or « Quelqu'un »; a range input
    `ops.replay_position_label` from 0 to the number of edits, at the end on
    load; `ops.replay_step`; and the grid `ops.replay_grid_label` at step k:
    each letter cell shows the letter of the last of the first k edits on it,
    locked once one locked or revealed it, revealed once one revealed it,
    pencil when the last put a pencil letter on an unlocked cell. Edits before
    k are done, k is current, the rest later.

### Look

- The page frame, token form, dashboard, chips, tiles, replay and its two layouts:
  `_design/pages.md`, « Plain pages: account, shared recap, operator »; the
  settings card between them: `admin/overrides.md`.
- The state lines: `_design/pages.md`, « States: opening, loading, empty,
  error ».
- The replay's cells: `_design/cells.md`, « Grid lines and empty cells » and
  « Letter marks »; the slider and
  buttons: `_design/foundation.md`, « Components ».

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
- **AC-11** `ANA` types `T` at (1, 0), `BOB` `A` at (1, 1) then `M` in pencil at
  (1, 2), Ana erases (1, 0) and undoes it, a check locks (1, 1), a reveal (1, 2),
  with joins, chat and presence between: the edits are `typed` T, `typed` A,
  `typed` M pencil, `erased`, `undone` T, `locked` A, `revealed` M, the first
  five with their player and `ANA` or `BOB`, the last two with none.
  (← 038 AC-8)
- **AC-12** With the token, a room's edits answer its empty grid and those edits,
  with none of FX-01's eight answers and no key `answer`; `abc`, an unknown and
  an expired room answer 404. (← 038 AC-8)
- **AC-13** `/ops` opens `locked` on a password field « Jeton d'opérateur »; a
  wrong token shows « Jeton refusé. », the input marked invalid and described
  by it; the token reaches `ready`, sent in every request's header, kept only
  in `sessionStorage`, in no URL; a reload skips the form, a new tab asks
  again; a later 401 or 429 brings the form back with « Jeton refusé. » or
  « Trop d'essais. Réessayez dans une minute. ». Locked, at a computer and a
  phone window, the top bar's Nock mark and « Nock » are the link « Accueil »
  to `/` with no `aria-current`. The page and form follow the plain pages
  design ("Look"). (← 038 AC-7, 048 AC-6)
- **AC-14** AC-3's 7-day figures read « Salons créés : 3 », « Joueurs par salon :
  2,0 », « Grilles terminées : 67 % », « Temps médian de résolution : 12 min 30
  s », « Latence du serveur : 30 ms (médiane), 50 ms (95e centile) », « Coupures
  par joueur : 0,50 », 7 days pressed among three chips; with `[1, 7]` offered,
  two chips and 7 pressed, with `[1]` one chip, pressed; no room reads `0` then
  « aucune donnée » five times. Chips named by « Période » and tiles follow the
  design ("Look"). (← 038 AC-7, 048 AC-8)
- **AC-15** A replay shown, pressing 30 from the keyboard sends `days=30`, presses
  it, keeps the focus and the replay, `ready` while waiting; a 500 gives `error`,
  a 429 locks; a 200 arriving after a replay's 401 locked the page leaves it
  `locked` with « Jeton refusé. » and no dashboard. (← 038 AC-7)
- **AC-16** With the token kept and the dashboard pending, the page shows only
  « Chargement… » under its heading, announced politely; a 500 or a network
  failure shows « Impossible de charger les données. », announced at once. Both
  follow the states design ("Look"). (← 038 AC-7, 048 AC-7)
- **AC-17** After Ana typed `TAMIS` across row 1 of FX-01 and erased (1, 4), the
  code in small letters lists five `typed` and one `erased` with `Ana`, « Étape
  6 sur 6 », row 1 `TAMI`; step 5 shows `S` at (1, 4), step 0 an empty grid.
  With seven edits at step 4, 1 to 3 are done, 4 current, 5 to 7 later; the two
  layouts follow the design ("Look"). A code with no room shows « Salon
  introuvable. ». (← 038 AC-9, 048 AC-9)
- **AC-18** With `D` in pencil at (2, 3), `M` checked at (1, 2) and `N` revealed
  at (3, 4), the last step shows them pencil, locked, revealed, clue cells empty
  blocks; at step 4, (1, 2) is unlocked and (3, 4) empty. No edit: only « Aucune
  modification dans ce salon. », no grid, slider or list. The cells follow the
  design, without clues, arrows or players ("Look"). (← 048 AC-10)
- **AC-19** The step control is a range input named « Étape »; Tab shows the focus
  ring on its knob and ArrowLeft from 7 reads « Étape 6 sur 7 ». A pending,
  404 or 500 replay shows one line, « Chargement… », « Salon introuvable. » or
  « Impossible de charger les données. », under the form, the dashboard above.
  (← 048 AC-11, 048 AC-12)
- **AC-20** The page keeps `product.md`'s baselines: Tab reaches the token input,
  Enter loads the dashboard, each period shows the visible focus; the contrast
  and language scans find nothing on the `ready` page, on a computer or a phone;
  no supported window scrolls sideways. (← 038 AC-7)
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
  returns as usual. On an in-memory store none runs.
- **AC-24** Room A, with the chat `chat-busy-6610`, expires and a lookup
  deletes it while a second connection to the file holds a read open: the
  lookup returns within 1 second, A's code is then unknown, one WARNING is
  logged and the WAL is not empty. Once that connection closes, the next
  sweep, which deletes nothing, leaves the WAL at 0 bytes, and neither file
  holds the chat text or A's code.

## Edge cases

- A room created exactly `days × 86 400 s` ago is in the period (AC-3).
- A player who times out and is seated back is no drop (AC-3).
- A confirmed pencil letter is `typed` without pencil; an undo that empties its
  cell is `undone` without letter (AC-11).
- A seated-back player's later edits take the nickname of the new join (AC-11).
- A code breaking the pattern shows « Salon introuvable. » (AC-17).
- A checkpoint busy at every sweep leaves the deleted pages in the WAL until
  one finds it free (AC-24).

## Out of scope

- Backups, log retention, the host's own logs; latency measured in the browsers,
  charts, alerts, exports; operator accounts, rotating the token without a
  restart; editing a room's log.
- An anonymous player's stored data, cookies, the player's own data:
  `account/account.md`.
  The other environment variables: `platform/serving.md`, `lobby/lifetime.md`.
  Overriding the room lives and the sweep interval from `/ops`, the settings
  routes and card: `admin/overrides.md`.

## Code

- `src/nock/operations.py`: figures, edits. `src/nock/server.py`: ops routes,
  guard, throttles, `/ops`. `src/nock/settings.py`: `operator_token_from_env`.
  `src/nock/store.py`: deletion, `checkpoint_wal`, `codes_created_since`.
  `src/nock/accounts.py`: its checkpoints. `src/nock/hub.py`: `relay_ms`.
  `src/nock/__main__.py`: `main()`.
- `web/src/lib/OpsPage.svelte`, `OpsReplay.svelte`, `ops.ts`, `duration.ts`.
- Tests: `tests/test_spec_038_ac03*` to `ac11*`, `tests/test_spec_048_ac06*`,
  `ac09_ac10*`, `ac11_ac12*`; `tests/test_operations_*` for AC-21 to AC-25.
