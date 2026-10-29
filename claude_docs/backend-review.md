# Python backend review

Senior code review of `src/nock/` (20 modules, about 12,700 lines) on
`feat/b-028-backend-review`, cut from `origin/main` at `a2b9531`. Every module was
read in full. The figures in the findings were measured on the maintainer's
machine with the largest catalogue grid (12 x 15, 180 cells); the scripts are
described in the appendix.

## Executive summary

The backend is in good shape for its size. The pure rules (`room.py`, `recap.py`,
`catch_up.py`, `operations.py`) are cleanly separated from time, threads and disk
(`hub.py`, `store.py`, `server.py`). The models are frozen, strict and closed.
The security basics are done with care: answers never leave the server, tokens
come from `secrets` and are compared in constant time, link and session tokens
are stored hashed, cookies are `HttpOnly` / `SameSite=Lax` / `Secure` behind
https, secrets never reach a message, and every SQL statement is parameterised.
The gate passes: ruff, black, pyrefly, svelte-check and the 4,364 tests that do
not need a browser.

The weak side is **capacity under hostile or heavy load**, which the specs leave
out of scope and the tests do not measure:

- two cheap requests let one client hurt every room on the server: creating
  rooms without limit (memory and disk), and repeating grid checks (the single
  engine thread);
- several hot paths recompute the grid's words or solution letters by linear
  scans, in the one thread that runs every room;
- the uvicorn event loop does synchronous SQLite reads and can wait on the
  registry lock when a socket connects.

None of these is a bug in the rules. They are what a public deployment would hit
first. The fixes are mostly small (a cached solution map, a per-address limit, a
join deadline), but two of them change behaviour that a spec rules out of scope
today, so they are decisions for the human.

| Severity | Count |
| --- | --- |
| Critical | 0 |
| High | 2 |
| Medium | 7 |
| Low | 11 |

## Findings

### High

#### H1. Room creation has no limit, and every room stays in memory for its whole life

`POST /api/rooms` (`server.py:1107`) creates a room for any caller, with no
session and no throttle. `RoomRegistry.register_room` (`hub.py:874`) writes the
room and its first snapshot, then keeps a live runner in `_runners`
(`hub.py:911`) until the room expires, 720 hours later by default. Nothing ever
evicts a runner (see M5).

Measured: **89 KiB of memory and 32 KiB of database per room**, about 685
creations a second on this machine. A script at 100 requests a second for one
hour leaves 360,000 rooms: about 31 GiB of memory and 11 GiB of disk, which ends
with the process killed or the disk full.

`lobby/rooms.md` lists "Throttling creation" under *Out of scope*, so this is a
spec decision, not an implementation slip.

Recommendation (needs the human):

- a per-address limit on room creation, reusing the lock-correct pattern of
  `_LinkLimits` (for example 30 rooms an hour per address);
- a global cap on live runners, plus eviction of idle runners (M5), so memory is
  bounded by activity and not by the number of rooms created in 30 days;
- optionally, keep the grid out of each room's snapshot (M6), which divides the
  disk cost by about ten.

#### H2. One player can saturate the engine thread that runs every room

All rooms run on one asyncio loop in one thread (`hub.py:1421`). A step's CPU
time therefore delays every other room, and the store commit of every step runs
in that thread too.

`_solution_letter` (`room.py:2405`) walks every clue cell, rebuilds each word
with `Grid.word_cells` (`grid.py:289`), whose `cell_at` (`grid.py:267`) is a
linear scan of the cells, and re-normalises the answer through the `Clue.letters`
property (`grid.py:186`) at each call. One lookup costs O(clues x word length x
cells). It is called once per cell by:

- `_is_right` (`room.py:1830`), on **every edit of a full grid** and on the
  solving edit: up to **56 ms** on the 12 x 15 grid (it stops at the first
  wrong letter, so the solving edit pays the whole walk);
- `_apply_check` (`room.py:2221`), on a grid check: **80 ms** per check on a grid
  filled with wrong letters.

Checks are not rate-limited (`_run_help_message`, `room.py:2033`; only edits
count toward `max_edits_per_second`), the default help mode is `free`, and a
check of wrong cells locks nothing, so the next check costs the same. A player
who creates their own room, fills its 145 letter cells with `A`s (about
7 seconds at 20 edits a second) and then sends about 12 grid checks a second
stays under the flood bound and keeps the engine thread busy **all the time**:
every room on the server lags. Each check also appends a 3.3 KB `check_result`
to the log (about 3.4 GB a day) and is broadcast to the room.

Honest play hits the same cost more gently: a team hunting the wrong letter in a
full grid pays up to 56 ms of the shared thread per keystroke.

Recommendation:

- compute the solution once per grid: a `dict[(row, column), letter]` built from
  the words, as `ipuz._solution_letters` already does (`ipuz.py:611`), cached on
  the `Grid` (a private attribute filled after validation, or a module cache
  keyed by grid) together with a position index for `cell_at`. Both
  `_is_right` and `_apply_check` drop to well under a millisecond;
- count checks and reveals in a per-player rate limit, as chat and reactions are
  (a spec change: `gameplay/hints.md`);
- longer term, measure the engine thread's step time in the dashboard (spec 038
  already logs relay times) and alert when it exceeds a budget.

### Medium

#### M1. The event loop blocks when a socket connects

`_serve_socket` (`server.py:789`) calls `RoomRegistry.connect` (`hub.py:1160`)
directly on the uvicorn event loop. `connect` runs `_find_runner`, which:

- reads `room_times` from SQLite synchronously (`_delete_if_expired`,
  `hub.py:1333`), under the store lock that the engine thread and the sweep also
  take;
- may take the registry lock, which another thread holds while it loads a room
  from the store or while `_delete_room` waits **up to 5 seconds** for the engine
  (`hub.py:1377`);
- may itself delete an expired room and wait for that deletion.

`room_socket` already moves the first lookup to a worker thread
(`server.py:1404`); `connect` undoes part of that. While the loop waits, every
socket and HTTP request of the process waits.

Recommendation: run `connect` in a worker thread too, or split it into a
thread-safe `_find_runner` call made with `asyncio.to_thread` followed by a
non-blocking `RoomConnection` creation on the loop.

#### M2. Sockets that never join stay open forever, with no limit per address

A socket that opens a room and never sends `join` is kept in `_open_connections`
(`hub.py:411`) with its reader and writer tasks. The silence time-out of
`tick` (`room.py:2497`) only applies to joined players, and uvicorn's ping only
closes dead peers. Nothing limits the number of sockets per address or per room.
A client can hold thousands of idle sockets on any known room code.

Recommendation: close a socket that has not joined after a short deadline
(10 seconds, say, with a new close code), and cap the open sockets per address.

#### M3. No limit on request bodies

Neither uvicorn nor the `Caddyfile` limits the size of an HTTP body, and FastAPI
reads it whole before validation. `SignInLinkRequest.email` (`accounts.py:208`)
and the keys of `POST /api/rooms/summaries` are only bounded after parsing.
Megabytes of JSON per request are accepted and parsed.

Recommendation: `request_body { max_size 64KB }` in the `Caddyfile`, and a small
middleware that refuses a `Content-Length` above the same size for direct
deployments (the WebSocket frames are already bounded at 8 KiB).

#### M4. A catch-up rebuilds every word of the grid for each letter of the absence

`build_catch_up` replays the absence and, for each `letter_changed` that fills a
cell, `_words_completed` calls `_words_of_grid(state_after.grid)`
(`catch_up.py:181`), which rebuilds every word of the grid with the linear
`word_cells`. A member who asks with `after_seq` 0 replays the whole log. The
route is not throttled (by design, `server.py:1158`) and runs in the shared
thread pool, holding the GIL.

Recommendation: compute `_words_of_grid` once per call (the grid never changes)
and keep a `position -> words` map, as `recap._completers` does
(`recap.py:553`).

#### M5. Live runners are never evicted

Any lookup that goes through `room_state` (a socket, the recap route, a view of
the public recap page) loads a stored room into `_runners` (`hub.py:1245`), logs
its `after_restart` step and keeps it until the room expires. Memory therefore
grows with every room ever touched, not with the rooms in play. On shutdown,
`_finish` (`hub.py:1409`) writes a fresh snapshot of each of them, since a
loaded runner starts with `snapshot_seq` None.

Recommendation: when a runner's task ends with no open connection, save its
snapshot and drop it from `_runners` (under the registry lock); the next lookup
loads it again. The read-only paths (`peek_room`) already show that a room does
not need to be live to be read.

#### M6. Every snapshot carries the whole grid and the whole chat, and none is pruned

Every 100 events (`snapshot_every`), `save_snapshot` stores the complete
`RoomState` (`store.py:700`): the grid with its clues and answers, every cell,
and the room's whole chat history. Old snapshots are never deleted
(`snapshots` table, `store.py:47`); `load_room_at` (`store.py:489`) needs some
of them for catch-up, but not all. Storage grows linearly with the events, and
the grid alone is about 30 KiB of each row.

Recommendation: keep the grid once per room (or reference it by
`grid_number`, the catalogue being part of the image), and prune the snapshots
older than the oldest one a catch-up can still ask for.

#### M7. The expiry sweep checkpoints the WAL once per deleted room, and never checks the result

`delete_room` runs `PRAGMA wal_checkpoint(TRUNCATE)` after each deletion
(`store.py:347`), inside the store lock that the engine thread needs for every
step. A sweep that deletes a few thousand rooms stalls all rooms for as many
checkpoints. The result row of the checkpoint is fetched and ignored: when the
second connection of the same file (`AccountStore`) reads or writes at that
moment, the checkpoint can give up after its busy timeout and report `busy`, the
WAL is not truncated, and the zeroed pages of spec 038 are not the only copy
left. The same
applies to `erase_player`, `AccountStore.delete_account`,
`erase_players_from_history` and `purge`.

Recommendation: delete the expired rooms of one sweep, then checkpoint once;
read the `busy` column of the result and log (or retry) when it is not 0, so
that the "no byte stays" promise is checked rather than assumed.

### Low

#### L1. The accounts docstring overstates what a database copy protects

The module docstring of `accounts.py` (`accounts.py:11`) says a copy of the
database "cannot sign anybody in". That holds for link and session tokens, which
are hashed, but `account_identities.resume_token` and
`account_links.room_resume_token` (`accounts.py:75`, `accounts.py:82`) are
stored as given, and a resume token is a full credential for its player in its
room. (The rooms' own snapshots hold them too, which the room rules need.)

Recommendation, revised on a second reading: hashing them cannot work, because
`GET /api/account/rooms` hands the raw token back to the player's other devices,
which is the point of the identities. Correct the docstring to say what a copy
does give; protecting the tokens further would mean encrypting them at rest,
which the threat does not justify today.

#### L2. A failure half-way through `DELETE /api/account` leaves the erasure unfinished

`delete_account` (`server.py:1367`) deletes the account rows, then erases each
player from the live rooms. `RoomRegistry.erase_player` and `_delete_room` wait
for the engine with a 5-second timeout (`hub.py:1106`, `hub.py:1377`) and raise
`TimeoutError` when it is busy (see H2). The route then answers 500 after the
account is gone, and the remaining rooms and the history records keep the
nickname, with no record left to retry from.

Recommendation: catch and log per room, go on with the others, and always run
`erase_players_from_history`; keep a small "pending erasures" table that the
sweep retries.

#### L3. An expiry is decided outside the lock that deletes

`_delete_if_expired` (`hub.py:1333`) reads the room's times without the
registry lock, and `_delete_room` deletes without checking again. Between the
two, another thread can delete the room and `register_room` can give its code to
a new room, which would then be deleted. The odds are about one in a billion per
race, but the fix is two lines: check the expiry again under the lock.

#### L4. The public recap is rebuilt on every view

`GET /recap/{token}` (`server.py:1081`) builds the whole recap (the full log
parsed and replayed) only to choose between the page and a 404, and the page
then calls `GET /api/recaps/{token}` (`server.py:1141`), which builds it again.
Both routes are public and unthrottled, and both make the room live (M5). A
solved room never changes, so its recap can be cached once it is built.

#### L5. Missing indexes

These queries scan their whole table: `room_times` by `created_at` and by
`creator_account_id` (`store.py:277`, `store.py:300`), `account_identities` by
`code` (run by the delete hook for every deleted room), `account_history_teammates`
by `(code, player_id)`, `account_links` by `email`, `account_sessions` by
`account_id`. Harmless today, linear in the data tomorrow. Add the indexes in
the next migration (`_SCHEMA_VERSION` 3).

#### L6. No security headers

Neither the app nor the `Caddyfile` sets `Content-Security-Policy`,
`X-Content-Type-Options: nosniff`, `Referrer-Policy` or `frame-ancestors`, so
any site can frame the room page (clickjacking of the host's buttons) or the
`/ops` page. Caddy's `header` directive can add them in one block.

#### L7. The `Bearer` scheme is compared case-sensitively

`_carries_token` (`server.py:665`) requires the exact prefix `"Bearer "`. RFC 9110
makes the scheme case-insensitive; a client that sends `bearer` gets a 401, which
also counts toward the throttle. Compare the scheme with `.lower()`.

#### L8. The modeling rules drift at the HTTP boundary

`_architecture.md` asks for a Pydantic model for everything that crosses JSON
and keeps `NamedTuple` private. Several answers are built as
`dict[str, object]`: `RoomLifeOverrides.answer` (`overrides.py:238`),
the dashboard's `offered_days` added to a dumped model (`server.py:1190`),
`{"rooms": n}` of the dry run, `{}` of the link route. `Setting` and `SETTINGS`
(`overrides.py:42`) are a public `NamedTuple`. No route declares a
`response_model`, so no answer is validated on the way out.

#### L9. The server only runs from the repository layout, and builds itself at import

`WEB_DIST_DIR` (`server.py:120`), `GRIDS_DIR` (`catalogue.py:37`) and
`FR_JSON_PATH` (`i18n.py:14`) are `Path(__file__).parents[2] / ...`. The
`Dockerfile` copies the layout on purpose and says so, but an installed wheel
would serve nothing. `nock.server` also reads the whole catalogue and builds the
app when it is imported (`server.py:1451`), so a broken grid file makes every
`import nock.server` fail, tests included. An app factory used by `__main__`
(and an environment variable for the data folders) would remove both.

#### L10. Small model inconsistencies

- `RoomState.players` and `Snapshot.players` use `max_length=8` instead of
  `MAX_PLAYERS` (`room.py:277`, `protocol.py:739`).
- `RoomState.removed_tokens` (`room.py:283`) grows without bound: a host who
  removes players who rejoin under new tokens adds one token each time, into
  every snapshot.
- `ChatText` (`protocol.py:66`) accepts control and bidirectional override
  characters (U+202E). Svelte escapes them, so this is no injection, but a
  message can display reversed; nicknames already refuse them.

#### L11. Minor library use

- `SmtpMailer._send` (`mailer.py:93`) calls `quit()` inside `with connection:`,
  whose exit sends `QUIT` again (the error is swallowed by `smtplib`).
- The SMTP send runs in the shared thread pool of the sync routes with a
  10-second timeout; a slow mail server under many distinct addresses can fill
  the 40 threads that every sync route uses. Low, given the per-address limits.

## What is done well

- **Separation of concerns.** `room.py` is pure (time comes in as `now`), the
  hub owns threads and time, the store owns SQLite, the server owns HTTP. Every
  rule can be tested without a socket, and the test suite does so.
- **Event sourcing done right.** Every entry is committed before it is sent
  (`_store_and_deliver`), seqs are checked to be contiguous in `append`, a
  failed commit drops the step without touching the state, and `replay` rebuilds
  exactly what the live step made.
- **Bounded connections.** Frames are capped twice (uvicorn's `ws_max_size` and
  `MAX_FRAME_BYTES`), each connection bounds its inbound and outbound queues,
  and the flood and stall closes are handled across threads without races (the
  check and the count share one lock).
- **Secrets.** Tokens from `secrets` with enough entropy; `compare_digest`
  everywhere a token is compared; hashed link and session tokens; the sign-in
  link carries its token in the URL fragment, so it never reaches a log or a
  `Referer`; the link route always answers 202 (no address enumeration);
  `MailError ... from None` keeps an address out of tracebacks; the operator
  token is read from the header only and never echoed; `repr()` of refused
  values keeps messages on one line.
- **Throttles that hold under concurrency.** `record_unless_blocked` checks and
  records in one locked step, so a burst cannot slip past the limit.
- **SQL.** Parameterised everywhere; the only f-strings use module constants;
  transactions use `BEGIN IMMEDIATE` with rollback on `BaseException`; the
  migration runs in one transaction and reads old rows as plain JSON.
- **Readability.** Names, docstrings and comments say why, in the house style;
  the code reads like the specs it implements.

## Prioritised recommendations

1. **Fix the gate's pyrefly step** (B-029), so every later item is type-checked
   in full.
2. **Cache the solution and the cell index of a grid** (H2, M4: B-030). Small,
   local, no behaviour change, removes the worst CPU path.
3. **Rate-limit checks and reveals per player** (H2: B-031). A spec change in
   `gameplay/hints.md`.
4. **Decide on creation limits and runner eviction** (H1, M5, L4: B-032). A
   spec change in `lobby/rooms.md` for the limit; eviction is internal.
5. **Keep the event loop free and close sockets that never join** (M1, M2, L3:
   B-033).
6. **Bound request bodies and add security headers** (M3, L6, L7: B-034).
7. **Batch the sweep's checkpoints and check their result**, with the missing
   indexes in the same migration (M7, L5: B-035).
8. **Make account erasure finish** (L2, L1: B-036).
9. **Slim the snapshots** (M6: B-037) and **type the server's answers** (L8, L9:
   B-038) when convenient.

A load test would keep these from coming back: a script that creates rooms,
connects a few hundred sockets and replays a recorded game while timing the
engine's steps, run by hand before a release.

## Appendix: method and measurements

- Static checks and tests: `uv run python scripts/gate.py --tests other`, green
  (ruff, black, screens sheet, traceability, pyrefly 0 errors, svelte-check
  0 errors, grids, vite build, 4,300 parallel and 64 serial tests).
- Measurements, run with `uv run python` against `src/nock` and the grids of the
  main checkout, Windows 11, CPython 3.14:
  - `_is_right` on the 180-cell grid, filled with its answers: 56 ms;
  - `handle_message` with a grid `check` on 145 wrong cells: 80 ms per step,
    3,287 bytes of log entry;
  - `register_room` x 2,000 on a file store: 685 rooms a second, 89 KiB of
    traced memory and 32 KiB of database per room.
- Aside, outside the backend, confirmed on a second look: the gate puts
  `scripts/` on `PYTHONPATH` (`scripts/gate.py:241`) for every step, and
  pyrefly then reads it as a site-packages folder and leaves it out of the
  project (`pyrefly dump-config` lists it under `project-excludes`). So
  `scripts/` is not type-checked by the gate, locally or in CI, in a worktree
  or not. A plain `uv run pyrefly check` checks it, with 0 errors today.

## Backlog items

The findings were regrouped into coherent fixes and queued in `Backlog.md`, in
this order:

| Item | Fix | Findings |
| --- | --- | --- |
| B-029 | The gate type-checks `scripts/` (tooling) | the aside above |
| B-030 | Grid lookups in constant time | H2 (CPU), M4 |
| B-031 | Limits on checks and reveals | H2 (abuse) |
| B-032 | Room capacity: a creation limit, idle rooms leave memory | H1, M5, L4 |
| B-033 | Sockets: off the event loop, a join deadline, a cap per address | M1, M2, L3 |
| B-034 | HTTP edge: body size, security headers, the Bearer scheme | M3, L6, L7 |
| B-035 | The store: checked secure deletion, one checkpoint per sweep, indexes | M7, L5 |
| B-036 | Account erasure that always finishes | L2, L1 |
| B-037 | Lean snapshots | M6, L10 (removed tokens) |
| B-038 | Server structure: typed answers and an app factory | L8, L9 |
| Small follow-ups | `MAX_PLAYERS`, chat characters, double `QUIT`, the SMTP threads | L10, L11 |

B-029 to B-034 come before the first public test: together they close the ways
one client can hurt every room. B-035 and B-036 make two privacy promises
checked rather than assumed. B-037 and B-038 can wait.

One constraint surfaced while writing the briefs: a check over its limit cannot
be answered `rate_limited`, because the client reads that code as the answer to
an edit and drops its oldest pending edit (`web/src/lib/roomSession.ts:1289`).
B-031 therefore proposes dropping it silently, as chat does.
