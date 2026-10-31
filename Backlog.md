# Backlog

The work queue of Nock: one item per change, from its brief to done. The lead
keeps this file; only the human approves a brief or a spec change. Keep it short:
every role reads the item it works on. A done item leaves the file at the next
release (git keeps it).

## How an item moves

`brief` → `approved` → `ready` → `building` → `done`, or `blocked` at any point,
with the reason.

- `brief`: the lead wrote it (`/new-spec`); it waits for the human.
- `approved`: the human approved the brief; the spec-writer changes the domain
  specs.
- `ready`: the human approved the spec change; `/feature B-NNN` can build it.
- `building`: on its branch, through tests, code and review.
- `done`: closed by `/feature`; it ships when its pull request is merged.

An item's number, branch and worktree come from
`uv run python scripts/claim_item.py <short-name>` when its brief starts, never
from this file: a brief reaches `main` only when its pull request merges. A
number is final, and a dropped item leaves a gap. `--list` shows the items in
flight and the spec files each one changes.

An item looks like this:

```md
### B-NNN Short title

- Status: brief
- Domains: content/grids, content/library
- Architecture decision: no (or yes: options from the Plan agent on Fable)
- Criteria: grids AC-20 (new), grids AC-7 (changed), library AC-3 (deleted)
- Branch: feat/b-NNN-short-name · PR: none yet
- Problem: one or two lines.
- In scope: ...
- Out of scope: ...
- Screens: the screens it touches, or none. When the look changes, two or three
  options with the lead's pick.
- Open questions: ...
```

"Criteria" is filled when the human approves the spec change. "Waits for" names
an item that must be done first. "Priority: first" puts an item ahead of the
others, at the top of the list.

## Items

### B-026 The gate's load on the machine

- Status: done (the human asked for it, 2026-10-29: « Apply suggestions. Set
  NOCK_WORKERS au 10 »; tooling, built by the lead)
- Priority: first (the human, 2026-10-29): every item's gates and review
  rounds run on it.
- Domains: none (tooling only: `scripts/gate.py`, `scripts/hooks/role_gate.py`,
  `.claude/settings.json`, `CLAUDE.md`)
- Architecture decision: no (the human chose the fixes)
- Branch: feat/b-026-gate-load · PR: #62
- Problem: review rounds froze the human's desktop. `--workers auto` started
  one pytest worker per logical CPU (16), each with its own Chromium: 64
  Chromium processes, about 10 GB and 94 % CPU on 2026-10-29, while the
  implementer's finish hook ran a second gate. At its timeout, `role_gate.py`
  stopped only `uv`, and the gate's tree ran on.
- In scope: `NOCK_WORKERS`, the default of `--workers`, set to 10 in
  `.claude/settings.json`; never more workers than logical CPUs; the parallel
  pass at a low priority (the serial pass keeps the normal one for its
  timings); one gate's tests at a time per clone (a lock in `.git/`; another
  gate waits up to 10 minutes, then fails naming the holder); `role_gate.py`
  stops the gate's whole process tree at its timeout.
- Out of scope: CI (no `NOCK_WORKERS` there: `auto` as before); a bare
  `uv run pytest`; tests, specs and code.
- Screens: none.
- A worktree gets it once its branch takes `main` after the merge: the hook
  runs the `gate.py` of the checkout it checks.

### B-028 Review of the Python backend

- Status: done (the human asked for it, 2026-10-29: « As the Code Reviewer
  agent "code-reviewer.md", create a new branch and proceed to a full review
  of the python backend. »; a review, built by the lead)
- Domains: none (the report `claude_docs/backend-review.md`; no spec, test or
  code changes)
- Architecture decision: no
- Branch: feat/b-028-backend-review · PR: none yet
- Problem: no review had looked at `src/nock/` as a whole, across specs, for
  security, capacity and maintainability.
- In scope: every module of `src/nock/`, the gate without browser tests, and
  measurements of the hot paths on the largest catalogue grid.
- Out of scope: the web client, the tests themselves, the tooling.
- Screens: none.
- Findings: 2 High (unlimited room creation that stays in memory; grid checks
  and full-grid edits that pin the one engine thread), 7 Medium, 11 Low, and a
  gap of the gate (pyrefly skips `scripts/`). One recommendation changed on a
  second reading: L1 asked to hash the resume tokens of the account tables,
  which cannot work, since the account hands the raw token back to the
  player's other devices; only the docstring that promises safety is wrong
  (B-036).
- Queued (the human, 2026-10-29: « Review your comments, regroupe them in
  technical coherent fixes and queue them in the backlog »), one item per
  coherent fix, in the lead's order:
  1. Before the first public test, the ways one client hurts every room:
     B-029 (gate), B-030 (grid lookups), B-031 (check and reveal limits),
     B-032 (room capacity), B-033 (sockets), B-034 (HTTP edge).
  2. Next, privacy promises that are not checked: B-035 (store deletion),
     B-036 (account erasure).
  3. When convenient, cost and structure: B-037 (lean snapshots), B-038
     (server structure).
  The rest went to "Small follow-ups". Each item's branch takes `main` once
  this one is merged, so it has its brief. The human approved the order on
  2026-10-29 (« Approve the order: B-029 to B-034 before the first public
  test, then B-035 and B-036, then B-037 and B-038. Start with B-029. »); the
  briefs B-030 to B-038 still wait for their own approval.

### B-029 The gate type-checks `scripts/`

- Status: done (the human, 2026-10-29: « Start with B-029 »; tooling, built
  by the lead)
- Waits for: nothing (B-028 is merged, with B-030).
- Priority: first (every item's gate runs on it; the smallest fix of B-028)
- Domains: none (tooling only: `scripts/gate.py`)
- Architecture decision: no
- Criteria: none (tooling)
- Branch: feat/b-029-gate-pyrefly-scripts · PR: #68
- Problem: the gate puts `scripts/` on `PYTHONPATH` (`scripts/gate.py:241`)
  for every step. Pyrefly then reads `scripts/` as a site-packages folder and
  leaves it out of the project ("Skipping include pattern ...scripts because
  it is matched by `project-excludes`"), so neither the local gate nor CI
  type-checks `scripts/`, though `pyproject.toml` includes it. A plain
  `uv run pyrefly check` does check it, with 0 errors today.
- In scope: run pyrefly without `scripts/` on its `PYTHONPATH`, the other
  steps unchanged; a test of the gate that pyrefly's environment holds no
  `scripts/` entry, if it stays cheap.
- Out of scope: the other steps of the gate; `src/` and `tests/`.
- Screens: none.
- Open questions: none.
- Built: `run_tool` puts `scripts/` on `PYTHONPATH` for pytest only, the one
  step that loads a module from it (the `gate_browsers` plugin); no other step
  imports from `scripts/`, so ruff, black, the screens sheet, svelte-check and
  the grids step lose an entry they never read. Checked with a file of
  `scripts/` holding a type error, run through the gate's own `run_tool`:
  before the fix pyrefly answered 0 errors, after it reports the error and
  the step fails. The full gate without browser tests passes (4,300 parallel
  and 64 serial tests, which load the plugin). No test of the gate: `tests/`
  holds the domains' tests only, and the probe above is the check.

### B-030 Grid lookups in constant time

- Status: done (the human approved the brief and picked A, then approved the
  spec change, 2026-10-30; the Plan agent on Fable confirmed A, with the two
  corrections below; both review rounds approved)
- Priority: second (B-028's worst CPU path; no behaviour change)
- Domains: content/grids (the model's lookups), platform/server (a time
  budget)
- Architecture decision: yes (new public names of `Grid`, read by `room.py`,
  `catch_up.py`, `recap.py`, `grid_import.py` and `ipuz.py`): options from
  the Plan agent on Fable
- Criteria: grids AC-22 (new), grids AC-23 (new), grids AC-24 (new), server
  AC-20 (new), server AC-21 (new), server AC-22 (new)
- Branch: feat/b-030-grid-lookups · PR: none yet
- Problem: one engine thread runs every room (`nock.hub`), and the hottest
  rules find a cell's answer by linear scans: `Grid.cell_at` walks every cell,
  `word_cells` calls it for each letter, `_solution_letter` (`room.py:2405`)
  rebuilds every word of the grid for each cell, and `Clue.letters`
  normalises the answer again at each read. On the largest catalogue grid
  (12 x 15), the solving edit, and any edit of a full grid, cost up to 56 ms
  of that thread, a grid check 80 ms, and a catch-up rebuilds every word for
  each letter of the absence (`catch_up.py:181`). Every other room waits
  meanwhile (B-028 H2, M4).
- In scope: a grid computes its cell index, its words and its solution
  letters once, and the rules read them. Options:
  - A (the human's pick): private attributes filled after validation, read
    through public methods (`Grid.solution_letter`, `Grid.words` of a frozen
    `Word`); the model stays frozen and its JSON, schema and equality
    unchanged. The Plan agent's corrections: fill them at the end of the
    grid's after-validator, since `model_post_init` runs before it and would
    change AC-5's message; index only the clues that resolve, so that
    `grid_import` keeps its own messages for the others (AC-6).
  - B: a module cache keyed by the grid, outside the model (rejected: no
    cheap key, state the tests cannot see).
  - C: precompute in the catalogue only (rejected: every store load builds a
    grid, so rooms after a restart, catch-up and recaps stay slow).
  A time budget proves it, measured on FX-02 (`tests/fixtures/fx02.json`,
  13 x 17), since the catalogue files are not in the repository: for example
  the solving edit under 5 ms, a check of a grid full of wrong letters under
  10 ms, a catch-up over 100 letters under 50 ms (its test file goes in
  `SERIAL_TEST_FILES`); the spec-writer picks the measure and its home.
- Out of scope: the limits on checks and reveals (B-031); the protocol, the
  answers and the store.
- Screens: none.
- Open questions: none left. The spec-writer's two, answered by the lead:
  `Grid.solution_letter` gives none for a position outside the grid (callers
  ask only about room cells, and it stays total), and a cell held by words
  that disagree takes the first word in clue order (deterministic, so
  equality holds; the import still refuses such a grid, AC-11).
- Build note: `tests/test_server_engine_time.py` measures durations; the lead
  adds it to `SERIAL_TEST_FILES` (`scripts/gate_browsers.py`) before the
  test-writer's gate.

### B-031 Limits on checks and reveals

- Status: done (the human approved the brief with the lead's defaults,
  2026-10-30: « 5 checks and reveals per 10 seconds per player, extra ones
  dropped silently », then the spec change as written; both review rounds
  approved)
- Priority: third (with B-030 it closes B-028 H2: B-030 makes a check cheap,
  this one bounds how often)
- Domains: gameplay/hints, platform/realtime
- Architecture decision: no (the lead's defaults: no new error code)
- Criteria: hints AC-21 (new), hints AC-22 (new), hints AC-23 (new); realtime
  rule 12 points to the limit (no criterion)
- Branch: feat/b-031-hint-limits · PR: none yet
- Problem: checks and reveals count toward no limit (`room.py:2033`; only
  edits count toward `max_edits_per_second`), the default help mode is
  `free`, and a check of wrong cells locks nothing, so the next one costs the
  same and logs another `check_result`. One player can send about 12 grid
  checks a second in their own room: 3.3 KB of log each (about 3.4 GB a day)
  and, until B-030, a fully busy engine thread for every room.
- In scope: a window per player for `check` and `reveal` requests, a vote
  request included, with its numbers in `RoomConfig`.
- Out of scope: the edit limit; the reveal budget (`gameplay/hints.md`).
- Screens: none with the lead's default (a dropped request shows nothing).
- Open questions (answered, A and A):
  1. The numbers: A (lead's default, picked) 5 requests per 10 seconds per
     player, as chat; B 1 a second.
  2. A request over the limit: A (lead's default, picked) dropped without an
     answer, as a chat message over its limit is. Not `rate_limited`: the
     client reads it as the answer to an edit and drops its oldest pending
     edit (`web/src/lib/roomSession.ts:1289`). B: a new error code the page
     shows, a protocol change and a new text.
- The spec-writer's choices where the brief left it open: a ballot never
  counts and is never dropped; a refused request uses no place; the limit
  comes before every other step, so a full window drops even a request that
  would be refused, with no error, and leaves an expired vote for the tick;
  the vote that passes uses no place.
- Build note: `tests/test_spec_023_ac03_ac04_result_reaches_players.py`
  sends 30 grid checks from one player at once; its test is edited in place
  with a higher `hint_limit` (`specs/_map.md`: a pointer's tests change with
  the behaviour).

### B-032 Room capacity: a creation limit, idle rooms leave memory

- Status: done (the human, 2026-10-30: « Use pattern 2 », « Approve and
  process »: the limit in an environment variable read at start, with the
  lead's defaults; then the spec change « Approved as written, with the
  spec-writer's picks (the restart step on reload, the recap kept per seq,
  live_codes as a test hook) »; both review rounds approved)
- Priority: fourth (before the first public test)
- Domains: lobby/rooms (a creation limit; its "Out of scope" line on
  throttling creation goes), platform/server (a room stays in memory only
  while it is played), gameplay/results (the recap read without making the
  room live, kept once built)
- Architecture decision: no (inside `nock.hub` and `nock.server`; a refused
  creation answers 429, which the catalogue already shows as
  `catalogue.play_failed`, `lobby/rooms.md` rule 2)
- Criteria: rooms AC-13 to AC-17 (new), server AC-23, AC-24 (new),
  results AC-21 to AC-23 (new)
- Branch: feat/b-032-room-capacity · PR: #73
- Problem: `POST /api/rooms` creates rooms for anyone, with no limit, and
  every room created or loaded keeps its runner in memory until it expires,
  720 hours later by default: 89 KiB of memory and 32 KiB of database each,
  about 685 creations a second. 100 requests a second for an hour leave about
  31 GiB in memory (B-028 H1). Any read through `room_state` (a recap route,
  a socket) loads a stored room and keeps it too, and the shutdown writes a
  snapshot of each (M5). The public recap is built twice per view, from the
  whole log (L4).
- In scope: a per-address limit on creation, on the pattern of `_LinkLimits`,
  answered 429, its count of rooms an hour read at start from
  `NOCK_ROOMS_PER_ADDRESS_PER_HOUR` (a whole number, default 30; a bad
  value stops the start, like the other variables; listed in
  `specs/_settings.md`, no `/ops` override); a runner whose task ends with
  no open socket saves its snapshot and leaves memory; the recap routes read
  through `peek_room`, and a solved room's recap is kept once built.
- Out of scope: the limits of sockets (B-033); the size of snapshots (B-037).
- Screens: none.
- Decisions: 30 rooms an hour per address, set by
  `NOCK_ROOMS_PER_ADDRESS_PER_HOUR`; no cap on rooms in memory once idle
  rooms leave. A `/ops` override of the limit would be a later item.

### B-033 Sockets: off the event loop, a deadline to join, a cap per address

- Status: done (the human, 2026-10-30: « Approve the B-033 brief with the
  lead's picks (1A, 2A, 3A, 4A, 5) and process it »; then the spec change
  « Approved as written »; both review rounds approved)
- Priority: fifth (before the first public test)
- Domains: platform/realtime (a join deadline and its close code, a cap on
  open sockets per address), platform/server (the lookup in one worker-thread
  call), lobby/lifetime (the expiry read again under the lock), lobby/rooms
  (an out-of-scope line)
- Criteria: realtime AC-21 to AC-23 (new), server AC-25, AC-26 (new),
  lifetime AC-14, AC-15 (new)
- Architecture decision: yes (a close code is part of the protocol,
  `platform/realtime.md` rule 13): options from the Plan agent on Fable
- Branch: feat/b-033-socket-hygiene · PR: #74
- Problem: `_serve_socket` calls `RoomRegistry.connect` on uvicorn's event
  loop; `connect` reads SQLite and can wait for the registry lock, which a
  deletion holds up to 5 seconds, and every request of the process waits
  meanwhile (B-028 M1). A socket that never sends `join` stays open for ever,
  and nothing caps the sockets of one address (M2). An expiry is decided
  outside the lock that deletes the room (L3). Since B-032, rooms leave
  memory, so a socket to a room not in memory is the common case: `connect`
  then always takes the registry lock and loads and replays the room on the
  event loop, after `room_socket` already replayed it once with `peek_room`
  (B-032 review, round 1).
- In scope: `connect` off the event loop, with one load of the room per
  socket; a socket not joined that sends nothing for some seconds is closed;
  a cap on the open sockets of an address; the expiry checked again under the
  registry lock.
- Out of scope: frame sizes and the flood and stall bounds (unchanged).
- Screens: none (an honest page pings every 2 seconds, so it never meets the
  deadline; the page treats both close codes below as a loss, as today).
- Options (Plan agent on Fable; lead's picks marked):
  1. The lookup. A (pick): one worker-thread call, `connect`, replaces
     `peek_room` in `room_socket`: the expiry check, one load and replay, and
     the socket counted, in one step under the registry lock (B-032's
     invariant kept); the wrong-code throttle decides on its `None`. A handler
     cancelled while the thread runs leaves the connection it gets back. B:
     keep `peek_room`, thread `connect` only: two loads per socket. C: thread
     the runner lookup, build the connection on the loop: same work, a private
     type crosses the module.
  2. The deadline. The page opens its socket, pings, and only then shows the
     nickname form, so a player on the form holds an unjoined socket as long
     as they think: an absolute deadline would close it again and again. A
     (pick): a silence before the join: no frame of any kind for 10 seconds
     (a ping resets it), held by the connection, its value in `RoomConfig`.
     B: an absolute 10 or 30 seconds from the open, with a page change on the
     form.
  3. Its close code. A (pick): 4408, the silence code, extended to sockets not
     yet joined; the page already retries on it. B: a new 44xx code.
  4. The cap. A (pick): 50 open sockets per address, counted by the server at
     accept and released at close, read at start from
     `NOCK_SOCKETS_PER_ADDRESS` (whole number, default 50, a bad value stops
     the start; no `/ops` override); over the cap, a close with a new code
     4503, a loss for the page (it retries every 8 seconds) since it clears
     when a tab closes; 4429 would be final and read « too many wrong codes ».
     B: 20, fixed: a class of 30 behind one school address would not fit.
  5. L3: `_delete_if_expired` reads the times again under the registry lock
     before deleting; the creator's deletion, which deletes rooms not expired,
     keeps its own path.
- Decisions: the lead's picks, 1A, 2A, 3A, 4A and 5.

### B-034 HTTP edge: body size, security and caching headers, the Bearer scheme

- Status: done
- Priority: sixth (before the first public test; small)
- Domains: platform/serving (new, split from platform/server: serving the
  client, environment settings, the HTTP edge), platform/server,
  admin/operations (the scheme of the operator token)
- Architecture decision: yes, the new domain (the human, 2026-10-31); the
  rest is one middleware and the `Caddyfile` of B-009
- Criteria: serving AC-7 to AC-14 (new), serving AC-1 to AC-6 (moved from
  server AC-14 to AC-19, retired with server AC-27 to AC-33), operations
  AC-21 (new)
- Branch: feat/b-034-http-edge · PR: #75
- Problem: neither uvicorn nor the `Caddyfile` limits a request body, and
  FastAPI reads it whole before validation (B-028 M3). No answer has a
  `Content-Security-Policy`, `X-Content-Type-Options` or `Referrer-Policy`,
  and any site can frame the room page or `/ops` (L6). The ops API accepts the
  exact prefix `Bearer ` only, though the scheme is case-insensitive
  (RFC 9110), and a wrong case counts toward the throttle (L7). The page
  routes answer `index.html`, and `/assets/` its hashed files, with no
  `Cache-Control` (`server.py:711`, `:1408`; the `Caddyfile` adds none): a
  browser can keep a days-old `index.html` after a deploy and ask for
  scripts the new build no longer has, a blank page (B-039 M10).
- In scope: a body limit (lead's proposal: 64 KB) in the app (a middleware
  answering 413) and in the `Caddyfile` (`request_body max_size`); the
  headers on every answer, the CSP to `'self'` with `frame-ancestors 'none'`;
  the scheme compared case-insensitively; `Cache-Control: no-cache` on
  `index.html` for every page route, and `public, max-age=31536000,
  immutable` on `/assets/*`.
- Out of scope: the WebSocket frame size (8 KiB already); CORS (no
  cross-origin use).
- The `Caddyfile` is deployment configuration, not tooling under `CLAUDE.md`;
  the implementer changes it with the app.
- Screens: none (a CSP that breaks the page shows in the browser tests). The
  client has no inline script, no `style="…"` in its markup and no outside
  source; Svelte sets styles through the CSSOM, which a CSP does not block.
- Open questions:
  1. Where the headers are set: A (lead's default) by the app, so they hold
     behind any proxy and in the tests; B by Caddy only.
- Decisions: the human, 2026-10-31: 1A, the app sets the headers; the spec
  change approved, with `platform/server.md` split into
  `platform/serving.md` first. The lead's picks: `Referrer-Policy:
  no-referrer`, no `X-Frame-Options`, `no-cache` on the build's root files,
  the brief's CSP as it stands, one space after the scheme; server.md keeps
  rules 20 to 22 at their numbers (no reference changes).

### B-035 The store: checked secure deletion, one checkpoint per sweep, indexes

- Status: done
- Priority: seventh (privacy promise and sweep cost)
- Domains: admin/operations (no copy of a deleted room stays), lobby/lifetime
  (the sweep), account/account (the purge)
- Architecture decision: no (indexes in migration 3 and the order of the
  statements; no row changes)
- Criteria: operations AC-22 to AC-25 (new), lifetime AC-16, AC-17 (new),
  lifetime AC-13 (changed), account AC-22, AC-23 (new), host AC-9 (changed)
- Branch: feat/b-035-store-deletion · PR: #76
- Problem: each room deletion runs `PRAGMA wal_checkpoint(TRUNCATE)`
  (`store.py:347`) inside the store lock that the engine thread takes for
  each step, so a sweep of thousands of expired rooms stalls every room. The
  checkpoint's result is never read: one that gave up (busy, while the
  account store's connection to the same file is active) leaves the old pages
  in the log, although `admin/operations.md` says no byte of the room stays.
  The same holds for `erase_player`, `delete_account`,
  `erase_players_from_history` and `purge` (B-028 M7). Several queries scan
  their whole table: rooms by creation time and by creator, identities by
  room code, team-mates by code and player, links by address, sessions by
  account (L5).
- In scope: a sweep deletes its expired rooms, then checkpoints once; each
  checkpoint reads its `busy` column; the indexes, in migration 3.
- Out of scope: the size of snapshots (B-037).
- Screens: none.
- Open questions:
  1. A checkpoint that stays busy: A (lead's default) one retry, then a
     WARNING, and the next sweep empties the log; B the request fails.
- Decisions: the human, 2026-10-31: 1A, one retry, then a WARNING, and the
  next sweep empties the log. The spec change approved, with the lead's
  picks: a checkpoint try never waits on the busy handler; the account
  store makes its own indexes when it opens; two checkpoints per sweep
  with accounts on; `nock.store.checkpoint_wal` as the one checkpoint.

### B-036 Account erasure that always finishes

- Status: done
- Priority: eighth (privacy; the failure needs a busy engine, which B-030 and
  B-031 make rare)
- Domains: account/account, lobby/lifetime (the sweep's step),
  admin/operations (the record's retention)
- Waits for: B-035 (PR #76: it changes `account/account.md` and the sweep
  whose shape option 1's retries follow)
- Architecture decision: yes (a new table, stored data): options from the
  Plan agent on Fable
- Criteria: account AC-24 to AC-30 (new), operations AC-23 (changed)
- Branch: feat/b-036-erasure-finishes · PR: #77
- Problem: `DELETE /api/account` (`server.py:1696`) deletes the account rows,
  then erases its players from the live rooms, waiting up to 5 seconds on the
  engine for each (`hub.py:1548`, `hub.py:1685`). A timeout answers 500 once
  the account is gone; the remaining rooms and the history records keep the
  nickname, and nothing is left to retry from (B-028 L2). Also, from spec 029
  ("Small follow-ups"): a history save that read the room before an erasure
  and writes after it keeps the nickname. And the module docstring of
  `accounts.py` promises that a copy of the database "cannot sign anybody
  in": true of accounts, but its room identities hold resume tokens in clear,
  as they must (the account gives them back to the player's devices).
- Market practice (Plan agent on Fable, 2026-10-31): mature products split
  deactivated, deletion requested (a grace period, undone by signing in:
  Discord 15 days, Steam and Facebook 30) and deleted; a deleted user's
  posts in shared spaces stay under a placeholder (GitHub's ghost, Discord's
  Deleted User), which Nock already does with `--`; the erasure runs as a job
  retried until done, with a record of completion that keeps no personal
  data (CNIL: within one month, keep a record of the request, and the purge
  and the erasure share one mechanism); a notice by e-mail on completion.
  Nock lacks the job, the record and the notice.
- In scope: every step of the erasure runs even when one room fails, and a
  failure is not lost; the history-save race; the docstring says what a copy
  of the database does give. Options:
  - 1: a table of pending erasures written in the deletion's transaction;
    the route tries once and answers 204 whatever happens; the sweep and the
    app's start retry each pending erasure (rooms, creator rooms, history
    last), idempotent, until done; a done row keeps only its times and
    counts.
  - 2 (lead's pick): 1, plus an e-mail « Votre compte Nock a été supprimé »
    sent once the erasure is done, best effort, and a line in the spec on a
    device that rejoins as « Ancien joueur ».
  - 3: an account lifecycle epic: a deletion requested with a grace period
    and an undo by signing in, then 1's erasure; four or five items, a state
    that every account query and the engine's account checks must read.
- Out of scope: an export of the account; backups and chat texts; a
  confirmation link before deleting and a grace period (option 3, later if
  abuse shows up); keeping creator rooms alive for their other players.
- Screens: none.
- Open questions:
  1. The completion e-mail (option 2): A (lead's default) yes; B no.
  2. Creator rooms on deletion: A (lead's default) still deleted
     (`lobby/host.md` rule 14); B made anonymous so the others finish, as
     an item of its own.
- Decisions: the human, 2026-10-31: option 2, the pending-erasure job
  retried by the sweep, the completion e-mail (1A), the spec line on a
  returning device; creator rooms still deleted (2A). The spec change
  approved, with the lead's picks: a done erasure kept 5 years with times
  and counts only; the e-mail sent in the request when its attempt ends
  the erasure; a save slower than a whole erasure accepted; no split of
  account.md in this item.

### B-037 Lean snapshots

- Status: brief
- Priority: ninth (the disk grows with play, slowly)
- Waits for: B-035 (both migrate the schema)
- Domains: platform/server (snapshots), social/catch-up (which snapshots a
  catch-up needs), lobby/host (the removed tokens)
- Architecture decision: yes (stored data): options from the Plan agent on
  Fable
- Branch: feat/b-037-lean-snapshots · PR: none yet
- Problem: every 100 events a snapshot stores the whole room: the grid with
  its clues and answers (about 30 KiB), every cell and the whole chat, and no
  snapshot is ever deleted, though `load_room_at` needs only those a catch-up
  can still ask for (B-028 M6). `removed_tokens` grows with every removal and
  goes into every snapshot (L10).
- In scope: the grid out of the snapshots; the snapshots no catch-up can reach
  pruned; a bound on `removed_tokens` (lead's proposal: the last 100, as past
  players). Options for the grid:
  - A (lead's pick): stored once per room, in a table of its own.
  - B: by its catalogue number; a room on a bare or withdrawn grid still needs
    its own copy.
- Out of scope: the log, append-only (`platform/server.md`).
- Screens: none.
- Open questions:
  1. Which snapshots stay: A (lead's default) the first and the newest, a
     catch-up from further back replaying the log from the first; B one per
     day of play.

### B-038 Server structure: typed answers and an app factory

- Status: brief
- Priority: last (maintainability; no player sees it)
- Waits for: nothing (B-027, which changed `server.py`, is merged)
- Domains: platform/server, admin/overrides, admin/operations (the answers
  keep their JSON)
- Architecture decision: yes (`nock.server`'s public names, how the app is
  built, and the modeling rules of `_architecture.md`): options from the Plan
  agent on Fable
- Branch: feat/b-038-server-structure · PR: none yet
- Problem: several answers are built as `dict[str, object]`
  (`RoomLifeOverrides.answer`, the dashboard's `offered_days`, the dry run's
  `{"rooms": n}`, the link route's `{}`), `Setting` and `SETTINGS` are a
  public `NamedTuple`, against the modeling rules, and no route declares a
  `response_model`, so no answer is checked on its way out (B-028 L8).
  `nock.server` reads the catalogue and builds the app when it is imported
  (`server.py:1475`), so one bad grid file fails every import, tests
  included, and the data folders resolve only from the repository layout
  (L9).
- In scope: a model per answer and `response_model` on each route, with the
  same JSON; `Setting` private, or a model; an app factory that `__main__`
  calls.
- Out of scope: any change of what an answer holds.
- Screens: none.
- Open questions:
  1. The data folders (`web/dist`, `grids/`, `fr.json`) from variables: A
     (lead's default) no, the image keeps the layout (B-009); B yes.

### B-039 Review of the web client

- Status: done (the human asked for it, 2026-10-30: « As the Code Reviewer
  agent "code-reviewer.md", create a new branch and proceed to a full review
  of the frontend. Propose a strategy to resolve each point. »; a review,
  built by the lead)
- Domains: none (the report `claude_docs/frontend-review.md`; no spec, test or
  code changes)
- Architecture decision: no
- Branch: feat/b-039-frontend-review · PR: #70
- Problem: no review had looked at `web/` as a whole, across specs, for
  correctness, security, accessibility, performance and maintainability.
- In scope: every file of `web/src`, the web client's config, its build,
  audit and type check, and a screenshot check of the grid's focus ring in
  Chromium and WebKit.
- Out of scope: the Python backend (B-028), the tests themselves, the tooling.
- Screens: none.
- Findings: 1 High (sign-out leaves the account's seats on the device),
  11 Medium (undo, check and reveal overtake the resent edits; no rejoin when
  storage is refused; the selection is not sent again after a reconnection;
  the grid's focus ring is painted under the letter cells; every frame
  re-runs every letter cell; a zoomed grid does not follow the selection;
  focus under the sheets; four copies of the dialog; live regions created
  full; no caching headers; the connection inside `RoomPage.svelte`),
  27 Low. The report proposes twelve items; most need a spec change first.
- Queued (the human, 2026-10-30: « Claim the twelve proposed items of the
  B-039 review and write their briefs in Backlog.md, in the proposed
  order. »), in the report's order. Eleven items, claimed with
  `scripts/claim_item.py`; the twelfth, the caching headers (M10), joins
  B-034 as the report proposed, since both set the headers of the same
  answers:
  1. Before the first public test, with B-031 to B-034: B-040 (sign-out
     forgets the account's seats), B-041 (reconnection keeps order and
     presence), and B-034 with the caching headers.
  2. Next, a baseline the product breaks today: B-042 (the grid's focus
     ring).
  3. Then cost, reach and focus on the room page: B-043 (remote updates),
     B-044 (zoomed grid), B-045 (room sheets), B-046 (one status region),
     B-047 (connection hardening).
  4. Before the split, if the human takes it: B-048 (unit tests, tooling).
  5. Last: B-049 (the split of `RoomPage.svelte` and `GridViewport.svelte`),
     once B-041 and B-045 pin the behaviour it keeps. B-050 (small fixes)
     at any time.
  Each item's branch takes `main` once this one is merged, so it has its
  brief. The human approved the order on 2026-10-30 (« Approve the order.
  Push and open PR for all new features. Let the main session handle the
  queuing / priority management »): the main session places these items
  among the others and sets their priorities. Each brief still waits for
  its own approval.

### B-040 Sign-out forgets the account's seats on the device

- Status: brief
- Priority: first of B-039's items (before the first public test: a leak of
  seats on shared devices, B-039 H1)
- Domains: account/account (rules 13 and 17: what sign-out and deletion
  forget on the device), client/hud (its « Out of scope » line on forgetting
  identities)
- Architecture decision: no with option A (a new device record that only the
  account code reads); yes with option B (the identity record of
  `lobby/joining.md` rule 8, which every page reads)
- Branch: feat/b-040-signout-forgets-seats · PR: none yet
- Problem: after a sign-in, and on every catalogue load while signed in,
  `storeMissingIdentities` (`web/src/lib/account.ts:192`) copies each seat of
  the account (player id, resume token, nickname) into `localStorage`
  (`account/account.md` rule 13). « Se déconnecter » and « Supprimer mon
  compte » (`AccountPage.svelte:103`, `:112`) remove nothing, and nothing
  prunes `nock.identity.*`, `nock.room.*` or `nock.history`. On a shared
  computer the next person sees the account's rooms in « Mes salons », and
  « Reprendre » takes a seat with its nickname, its colour and its host
  rights. After a deletion the seats stay too, as `--`, and the history keeps
  the team-mates' nicknames.
- In scope: the device knows which identities the account brought; a 204 from
  sign-out or deletion removes them, their `nock.room.*` records and the
  history records of their rooms, then shows the state. The seats the device
  took itself stay: they are how a guest comes back. Options:
  - A (lead's pick): a list `nock.account_rooms` of the codes that
    `storeMissingIdentities` wrote.
  - B: a flag `from_account` in each identity record.
- Out of scope: forgetting an identity whose room the summaries no longer
  return; a session that expires with no sign-out (its seats stay until the
  next sign-out on that device).
- Overlaps: B-036 changes `account/account.md` rule 18, a different rule.
  The file is over the size guideline already ("Small follow-ups").
- Screens: none (« Mes salons » lists fewer rooms; no new state).
- Open questions:
  1. A sign-out or deletion that fails: A (lead's default) the device keeps
     everything, as the account does, and the page shows `error` (rule 16);
     B the device forgets anyway.

### B-041 Reconnection keeps order and presence

- Status: brief
- Priority: second of B-039's items (before the first public test: after a
  network drop an undo erases another letter for everyone, B-039 M1)
- Waits for: B-031's merge (done on its branch; it changes
  `gameplay/hints.md` and `platform/realtime.md` too)
- Domains: gameplay/hints (check and reveal wait for the resent edits),
  lobby/joining (rule 8: a page that has joined rejoins with the identity it
  holds; rule 9: the kept form's button), platform/realtime (rule 22: the kept
  selection sent again), platform/server (rule 9 already orders the undo; its
  reconnection case has no test)
- Architecture decision: no (the order of the page's sends; no message
  changes)
- Branch: feat/b-041-reconnect-order · PR: none yet
- Problem: after a reconnection only edits wait for the resend
  (`sendEdit`, `RoomPage.svelte:1718`; `resendPendingEdits`, `:1839`, one
  every 100 ms). Undo, check and reveal (`:868`, `:876`, `:934`) go at once,
  or are dropped while the socket is closed (`:552`): offline, the player
  types A, B, C; a Ctrl+Z 50 ms into the resend reaches the server before B
  and undoes A for everyone, against `platform/server.md` rule 9 (M1). A
  browser that refuses storage cannot rejoin after its first drop: the join
  plan reads the identity from `localStorage` only (`joinRules.ts:96`), so
  the band asks for a nickname and no form shows (M2). After a reconnection
  the others no longer see the player's cursor: the server cleared it at the
  disconnection (`room.py:1146`) and the page sends no unchanged selection
  (M3). « Rejoindre » on the kept form does nothing during the retry delay
  (`:633`, `:2011`; L11).
- In scope: one way to send a command after the pending edits (kept while
  not joined, queued behind a running resend, else sent), used by undo,
  check and reveal; the identity of the last snapshot kept in memory and
  used first by the join on open; the kept selection, checked against the
  new snapshot's words, sent before the resend; « Rejoindre » disabled
  unless the status is `nickname`.
- Out of scope: reactions and flags sent offline (B-047); moving the
  connection out of `RoomPage.svelte` (B-049).
- Screens: the kept join form while the page reconnects, « Rejoindre »
  disabled (a look that exists; drawn if the screens sheet draws that form).
- Open questions:
  1. A check or reveal pressed before the snapshot after a loss: A (lead's
     default) kept and sent after the resent edits, as the undo is; B
     refused, the buttons disabled until joined.

### B-042 The grid's focus ring above the cells

- Status: brief
- Priority: third of B-039's items (a baseline the product breaks today:
  `product.md` rule 14)
- Domains: client/shell (AC-18 reads the ring's computed style only; a
  pixel check along the grid's edges), `_design/foundation.md` « Focus »
  with option B only
- Architecture decision: no
- Model: Opus for the test-writer and the implementer (painted pixels,
  `CLAUDE.md`)
- Branch: feat/b-042-grid-focus-ring · PR: none yet
- Problem: `.grid:focus-visible` draws its ring inside, at offset -3 px
  (`GridViewport.svelte:1195`), over the edge cells, and the letter cells are
  positioned and opaque (`:896`): Chromium and WebKit paint them after the
  grid's outline. On screenshots of a 14 by 9 grid focused from the keyboard,
  the ring shows only where a clue cell touches the edge and is hidden along
  every letter cell (B-039 M4). The test of the ring
  (`tests/test_spec_041_ac07_ac08_focus_ring.py`) reads the computed style,
  so the gate cannot see it.
- In scope: a ring that shows along the whole edge, and a pixel check along
  the right and bottom edges in Chromium and WebKit. Options:
  - A (lead's pick): the same ring drawn by an `aria-hidden` overlay painted
    after the cells (`inset: 0`, `pointer-events: none`), outlined while the
    grid has `:focus-visible`; the look as designed.
  - B: the ring outside the grid, at the foundation's offset of 2 px; the
    look changes and the viewport must not clip it.
- Out of scope: the focus of the cells themselves (`aria-activedescendant`).
- Screens: the grid focused from the keyboard; none changes with option A
  (the ring is drawn as designed), the screens sheet redrawn with option B.
- Open questions: none beyond the option.

### B-043 Remote updates in proportion to what changed

- Status: brief
- Priority: fourth of B-039's items (on the path of `product.md` rules 23
  and 24)
- Domains: client/shell (a frame that changes nothing of a cell leaves it
  untouched; the spec-writer picks the measure)
- Architecture decision: no (inside `roomSession.ts` and
  `GridViewport.svelte`)
- Model: Opus for the test-writer and the implementer (timing in a browser,
  `CLAUDE.md`)
- Branch: feat/b-043-remote-update-cost · PR: none yet
- Problem: every frame, the pong every 2 seconds included, assigns a new
  array of cursors (`roomSession.ts:1197`), and each letter cell reads fresh
  arrays from `cursorsOn` and `tintsOn` (`GridViewport.svelte:171`), so every
  frame re-runs the template of every letter cell. With 8 players at 2
  letters a second (rule 24) that is about 16 passes over the grid a second,
  against the 50 ms local echo of rule 23 on the throttled phone (B-039 M5;
  not measured). Each keystroke also copies every cell for `filledWords`
  with the Salon closed, and scans the grid once per cell of a word (L13). A
  pinch sets `--triangle` on every letter cell, and every arrow has two
  `drop-shadow` filters (L16).
- In scope: `nextCursors` returns the same array when nothing moved; one
  derived map from cell to its cursors and tint, with shared empty values;
  the same for flashes and caught-up cells; a cell index per snapshot and a
  map of the latest pending edit per cell; `--triangle` on `.grid`; the
  arrows' white halo as an SVG stroke. A measure proves it, for example "a
  pong changes no cell of the grid" (a mutation count) and rule 23's echo
  with 8 remote players typing; its test file goes in `SERIAL_TEST_FILES`
  if it measures a pace.
- Out of scope: splitting the cells into components (B-049).
- Screens: none (the halo as a stroke looks the same; the cell sheet checks
  it).
- Open questions: none.

### B-044 A zoomed grid follows the selection

- Status: brief
- Priority: fifth of B-039's items (phones)
- Domains: gameplay/board (rule 3: while zoomed, a change of selection
  scrolls the grid the least needed to show the selected cell)
- Architecture decision: no
- Model: Opus for the test-writer and the implementer (layout, `CLAUDE.md`)
- Branch: feat/b-044-zoom-follows-selection · PR: none yet
- Problem: the selection moves only `aria-activedescendant`, which no engine
  scrolls into view, and nothing outside the pinch and pan code sets the
  viewport's scroll (`GridViewport.svelte:544`, `:577`). On a 360 px phone,
  zoomed to read a clue, letters 6 and 7 of a word typed with the in-app
  keyboard land off-screen; Tab and the arrows can select a word wholly
  off-screen (B-039 M6).
- In scope: while zoomed, an effect on the selected cell and the cell size
  scrolls the viewport the least that shows the cell with a margin; a tap
  moves nothing, its cell being in view.
- Out of scope: the zoom itself; the grid at zoom 1.
- Screens: none (the zoomed grid scrolls; no new look).
- Open questions:
  1. The margin kept around the cell: A (lead's default) one cell; B none.

### B-045 One room sheet, focus kept in overlays

- Status: brief
- Priority: sixth of B-039's items (before B-049, whose split its tests pin)
- Domains: client/hud (rule 12: the focus and an open menu or the Salon
  sheet; rule 13: Tab stays in every room sheet), lobby/host (rule 8: the
  settings form's errors, the focus when the host role goes), gameplay/hints
  (rule 19: the vote's « Oui » disabled under the focus), account/account
  (rule 14: the backdrop closes the sheet only on a press and a release on
  it)
- Architecture decision: no (a client component)
- Branch: feat/b-045-room-sheet-focus · PR: none yet
- Problem: in the sheet layout, Shift+Tab from « Discussion » goes to the
  clue bar's buttons under the Salon sheet, and Tab from an open Aide menu
  goes to the grid under the scrim while the menu stays open (B-039 M7).
  `HostSettings`, `AccountDialog`, `RecapDialog` and `RoomGoneDialog` each
  reimplement the dialog, with different Tab traps, and the host sheet has
  none: Tab from « Enregistrer » leaves for the address bar (M8). When the
  host role goes, the sheet is unmounted and the focus falls to the page;
  « Oui » of the vote is disabled under the focus when the connection drops
  (L8). An invalid count in the host settings fails silently or in the
  browser's language (`HostSettings.svelte:65`, no `novalidate`; L9). A drag
  that starts in the account sheet and ends on the backdrop closes it,
  losing the typed address (L17).
- In scope: one `RoomSheet.svelte` (layout, title, backdrop and cancel
  rules, one Tab trap on a full tabbable selector, `open()`, `close()`,
  `onClosed`) used by the four sheets; the host sheet closed through it when
  the role goes; the vote buttons give the focus away before they are
  disabled, as the chat does for a mute; the settings form with
  `novalidate`, an error line from `fr.json`, `aria-invalid` and
  `aria-describedby`; the focus kept in an open menu or the Salon sheet.
- Out of scope: the settings form reset by any `settings_changed` (B-050);
  the overlays' state, which B-049 moves.
- Screens: the host's settings with an invalid count (a new error line,
  drawn in `docs/design/screens_sheet/`).
- Open questions:
  1. Focus leaving an open menu or the Salon sheet: A (lead's default) the
     overlay closes, without moving the focus; B Tab wraps inside it, as in
     the sheets.

### B-046 One live status region, and the names and references

- Status: brief
- Priority: seventh of B-039's items (screen readers)
- Domains: client/hud (one status region for the room page), with the rules
  that call a message a status (`platform/realtime.md` rule 20 for the
  band, `client/room.md` for the notes, `gameplay/results.md` for the
  recap); the spec-writer finds them
- Architecture decision: no
- Branch: feat/b-046-live-status · PR: none yet
- Problem: the connection band, the grid status, the undo note, the Joueurs
  status and the recap status are live regions created with their text
  already in them (`RoomPage.svelte:2131`, `:2304`, `RoomNote.svelte:75`,
  `PlayersPanel.svelte:155`, `RecapDialog.svelte:220`); screen readers often
  stay silent for a region that is created full (B-039 M9, plausible). The
  vote banner does it right (`RoomPage.svelte:2173`). The catalogue's
  « Jouer » buttons cannot be told apart, `aria-controls="reaction-picker"`
  points to an element that exists only while open, and the nickname field
  is `aria-invalid` with no `aria-describedby` (L22).
- In scope: one persistent, visually hidden `role="status"` region in the
  room page and an `announce(text)` passed down; the visible elements lose
  their role; « Jouer » described by its card's title; the references set
  only while their target exists.
- Out of scope: the vote banner's region (already right); the alerts of the
  forms.
- Screens: none.
- Open questions: none.

### B-047 Connection hardening

- Status: brief
- Priority: eighth of B-039's items (rare cases of the connection)
- Waits for: B-041 (the same connection code of `RoomPage.svelte`) and B-033
  (the same rules of `platform/realtime.md`; its new close code is one more
  the page reads)
- Domains: client/hud (a final status makes the grid read-only), social/chat
  (rules 5 and 13: « Je bloque » and « Réagir » while not joined),
  gameplay/co-op (rule 12: which errors answer an edit), platform/realtime
  (rules 16, 18 and 21: hidden tabs, the connect timeout, the jitter)
- Architecture decision: no with the lead's defaults; yes with option B of
  question 2 (pings sent by the server, a protocol change)
- Branch: feat/b-047-connection-hardening · PR: none yet
- Problem (B-039 L1 to L7): after a 4001, a removal or a lock the grid still
  takes letters that are never sent (`RoomPage.svelte:813`). Reactions and
  flags sent offline are lost but count for the pacing (`:1171`), and both
  buttons stay enabled while not joined, unlike « Envoyer ». Five error codes
  drop the oldest pending edit (`roomSession.ts:1288`), and two of them also
  answer undo, check, reveal and `select_cell`; harmless today, but written
  nowhere. Some server data is cast unchecked, and an invalid date throws in
  `Intl.DateTimeFormat` after `session.seq` moved (`roomSession.ts:991`,
  `activityFeed.ts:138`, `ops.ts:499`, `catalogue.ts:96`). The heartbeat runs
  on page timers, which hidden tabs throttle (plausible). A socket stuck
  connecting has no timeout (`:1896`). Every page retries at exactly 1, 2,
  4 and 8 seconds after a server restart.
- In scope: the grid read-only in a final status; « Réagir » and « Je
  bloque » disabled while not joined, and only a send that went out counts;
  the invariant of the error codes in `gameplay/co-op.md` rule 12, with a
  server test; the parsers check those fields; a measure of hidden tabs in
  the three engines, then the fix it calls for; a connect timeout; a jitter
  on the delays.
- Out of scope: a client reference echoed in the errors (an architecture
  decision of its own, if the invariant ever breaks).
- Screens: the clue bar while not joined, « Réagir » and « Je bloque »
  disabled (a look that exists; drawn if the screens sheet draws that
  state).
- Open questions:
  1. The connect timeout: A (lead's default) 6 seconds, the silence limit;
     B 10 seconds.
  2. Hidden tabs, if the measure shows drops: A (lead's default) the page
     checks the silence again on `visibilitychange` before it closes; B the
     server sends the pings.
  3. The jitter: A (lead's default) ±20 % on each delay; B none, the delays
     of rule 21 kept exact.

### B-048 Unit tests for the client's pure modules

- Status: brief (tooling, built by the lead; the runner, and a new
  dependency with option B, are the human's call)
- Priority: before B-049, if the human takes it
- Domains: none (tooling: `web/package.json`, `scripts/gate.py`, CI)
- Architecture decision: yes (the design of the tooling: a second test
  runner in the gate): options from the Plan agent on Fable
- Criteria: none (tooling)
- Branch: feat/b-048-client-unit-tests · PR: none yet
- Problem: the client's pure modules (`roomSession`, `activityFeed`,
  `catchUp`, `remoteSelections`, `joinRules`, `navigation`, `history`,
  `wordSelection`, `gridLayout`, `ops.cellStatesAtStep`) are tested only
  through Playwright, one page per case. Their permutations (a gap in the
  sequence, an error during a resend, a snapshot over pending edits) are slow
  to reach that way, and the split of B-049 needs them pinned.
- In scope: a runner for TypeScript tests of those modules, a gate step and
  its CI job, and one test that proves the step runs; the test-writer adds
  tests with the items that need them. Options:
  - A (lead's pick): Node's own `node:test`, which runs TypeScript in Node 24
    (CI takes `lts/*`): no new dependency, but a resolve hook for the
    extensionless imports, the import of `fr.json` and `svelte/reactivity`.
  - B: Vitest, a new dev dependency that reads the Vite config as it is.
- Out of scope: component tests (the Svelte components stay with the browser
  tests).
- Screens: none.
- Open questions:
  1. Where the tests live: A (lead's default) `tests/web/`, written by the
     test-writer, whose folder it is; B beside the modules in `web/src`,
     which the implementer owns.
  2. Whether such a test proves a criterion: A (lead's default) no, criteria
     stay proven by `tests/test_<name>_*.py`; B the traceability check reads
     them too.

### B-049 Split `RoomPage.svelte` and `GridViewport.svelte`

- Status: brief
- Priority: last of B-039's items (maintainability; no player sees it)
- Waits for: B-041 and B-045 (their tests pin the behaviour the split
  keeps), and B-048 if the human takes it; best after B-042 to B-047, which
  change the same files
- Domains: none (no behaviour change: `web/src/lib/` only)
- Architecture decision: yes (new modules of the client and their public
  names): the Plan agent checks the report's split on Fable
- Criteria: none new; every existing test proves nothing changed
- Branch: feat/b-049-client-structure · PR: none yet
- Problem: `RoomPage.svelte` holds 2,720 lines and five concerns: the
  transport, the game commands, the view state, the layout arithmetic and
  the device storage. `session` has two writers, and the connection code,
  where M1, M2, M3, L1, L2, L6 and L11 come from, is reachable only by a
  browser test (B-039 M11). `GridViewport.svelte` mixes gestures, key
  mapping, legend arithmetic, announcements and cell drawing in 1,321 lines.
  The one-overlay rule is applied by hand in eight places, the expiry timers
  are three copies, and the play state machine and the WebKit link
  workaround are repeated (L24); some leftovers and comments are wrong
  (L25).
- In scope: the nine steps of the report's « Structure », one commit each,
  every `data-testid`, id and the document order of `client/hud.md` rule 3
  kept, no wrapper element added: `roomConnection.ts` (an injected socket
  factory and clock, the only writer of `session.status`),
  `expiry.svelte.ts`, `VoteBanner`, `GridStatus`, `EntryPage`, `NoteSlot`,
  `roomOverlays.svelte.ts`, `playFit.svelte.ts` (last, on Opus: pixels),
  optionally `roomCommands.ts`; for the grid `LetterCell`, `ClueCell`, a
  `use:pinchPan` action, `gridKeys.ts` and `legendLayout.ts`; the duplicates
  of L24 and the leftovers of L25.
- Out of scope: any change a player or a test can see.
- Screens: none.
- Open questions:
  1. The props drilled through `Salon` (22) and `RoomTopBar` (26): A (lead's
     default) grouped into a few objects here; B left as they are.

### B-050 Small fixes of the web client

- Status: brief
- Priority: any time, between larger items; one fix per commit
- Domains: lobby/host (rule 8: the settings form), admin/operations (rules
  16, 18 and 19: the ops requests and the token), `product.md` (« Stable
  routes »); the other fixes keep rules that already hold
- Architecture decision: no (L26 adds the row of an existing route; no
  baseline changes)
- Branch: feat/b-050-client-small-fixes · PR: none yet
- Problem and fix, one per B-039 Low finding:
  - L10: any `settings_changed` resets the unsaved settings form
    (`RoomPage.svelte:588`): only the fields that changed are copied.
  - L12: a menu keeps its old place when the top bar changes form with no
    layout change (`RoomPopover.svelte:50`, plausible): placed again after
    `tick()`.
  - L14: the scrolling lists observe every item again on each new line, with
    two ResizeObservers on the chat stream (`scrollingLists.ts:16`, `:203`):
    one watcher per list.
  - L15: a pinch that gains a third finger and loses one makes the zoom jump
    (`GridViewport.svelte:526`), and a lost `pointerup` can leave a ghost
    finger: a new baseline at two fingers, the pointer captured.
  - L18: crossing answers of `/ops` can end on the wrong period, the replay
    too (`OpsPage.svelte:83`, `OpsReplay.svelte:70`): a request counter per
    kind.
  - L19: a token that cannot be a header value sticks in `sessionStorage`
    (`OpsPage.svelte:95`, `ops.ts:176`): its shape checked before it is
    stored, the field cleared on lock and focused when the form comes back.
  - L20: the list separator `', '` (four places) and the units « h » and
    « min » (`OpsSettings.svelte:52`) are outside `fr.json`:
    `Intl.ListFormat('fr')` or a key, and two unit keys.
  - L21: on the plain pages the top bar is inside `<main>`, so there is no
    banner landmark (`CatalogueFrame.svelte:34`, `EntryFrame.svelte:24`):
    the frames own `<main>` after the top bar.
  - L23: one bundle serves every route, and the fonts are neither subset nor
    preloaded: `import()` per page in `App.svelte`, the `latin` and
    `latin-ext` subsets, a preload of the grid's two faces, measured against
    `product.md` rule 22 before and after.
  - L26: « Stable routes » omits `GET /api/account/progress`
    (`account/account.md` rule 24): one row.
  - L27: patches for svelte, svelte-check and vite, and two low advisories,
    build-time only: tooling, the human's call, taken with the next tooling
    item.
- Out of scope: the host sheet's errors and focus (B-045).
- Screens: none (L21 moves no pixel; the tests that locate `main` are
  checked).
- Open questions:
  1. A change of the lock alone: A (lead's default) the typed counts stay;
     B they reset, as today.
  2. The ops fixes (L18, L19): A (lead's default) in this item; B an item of
     their own.

### B-051 CI runs only the gate jobs that read the changed files

- Status: done (the human asked for it, 2026-10-30: « PR B-039 is triggering
  Quality Gates when only updating backlog and claude_docs review. This should
  not happen. », then « Review my requirements and include coherent files in
  potential QG skips »; tooling, built by the lead)
- Domains: none (tooling only: `.github/workflows/ci.yml`)
- Architecture decision: no
- Criteria: none (tooling)
- Branch: feat/b-051-ci-skip-notes-only · PR: #71 (the notes-only rule);
  feat/b-051-ci-skip-by-file · PR: #72 (every file)
- Problem: CI skipped the browser jobs only for a pull request that changed
  nothing outside `specs/`, `docs/` and `grids/`. B-039 (#70) changed
  `Backlog.md` and `claude_docs/frontend-review.md` only, files no check and
  no test reads, and still ran the static job and the Chromium job.
- In scope: each changed file of a pull request says which gate jobs it
  needs. None, for a file no check and no test reads: `Backlog.md`,
  `CLAUDE.md`, `claude_docs/`, `.claude/`, `docs/` outside `docs/design/`,
  `Dockerfile`, `.dockerignore`, `compose*.yaml`, `Caddyfile`,
  `.env.*.example`. The static job only, for a file only it reads: `specs/`
  (traceability), `docs/design/` (the screens sheet), `grids/` (the shipped
  grids), `README.md` (the font credits, spec 041 AC-6, a test without a
  browser). Every job for any other file and for a Python file anywhere
  (ruff and black read the whole repository). The `Quality gate` check
  accepts a skipped static job only when the files allow it.
- Out of scope: a push to `main` and a run started by hand (every job, as
  before). Files that change what a check sees stay in every job:
  `.gitignore` (ruff and black skip what it lists), `.gitattributes` (line
  endings at checkout), `.python-version`, `pyproject.toml`, `uv.lock`,
  `.github/`.
- Screens: none.
- Built: checked by running the workflow's shell step under `bash -e` on 31
  sample file lists, one or more per kind above, with look-alike paths
  (`Backlog.mdx`, `claude_docsx/`, `compose.yml`, `.env`), a quoted
  non-ASCII path, a path with a space and an empty list (every job); a push
  runs every job.

### B-001 Rebaseline v1.1.0 into domain specs

- Status: done (the human approved every domain file, 2026-10-24)
- Domains: all (`specs/_map.md`)
- Branch: feat/b-001-rebaseline · PR: none yet
- Problem: the numbered specs (2 MB) mix the contract with its history, and a
  role reads about 60k tokens before it starts; the domain specs state the
  current truth.
- In scope: the tooling for domain specs; the 18 domain files still pending,
  `product.md` and `_settings.md`; the design split into `specs/_design/`; a
  review of each domain file against the tests and code of v1.1.0; moving the
  numbered specs to `specs/_archive/v1.1.0/`.
- Out of scope: any change of behaviour or code; compacting the tests (B-003).
- Screens: none (the screens sheet's captions follow the design split).
- The design split also: states the state lines as v1.1.0 draws them (a line
  standing for a page is 16 px with no role, the catalogue's and « Mes
  salons »'s load errors included; inside a card, sheet or dialog, waiting and
  done lines are `role="status"`, error lines `role="alert"`; a failed
  action's error line is `role="alert"`); takes the phone top bar's 40 px
  buttons and the clue bar's minimum width (320 px) into `_design/room.md`;
  takes the grid's name in the computer top bar out of the design.

### B-003 Compact the tests

- Status: brief (the human delays the decision)
- Domains: none (tests only)
- Waits for: B-001
- Problem: 4.9 MB of tests for 875 KB of code; helpers are copied from file to
  file (`dist_dir` in 72 files, `catalogue` in 82) and near-copies of one test
  stand where a parameter would do.
- In scope: shared fixtures and harnesses; parametrized tests in place of
  copies; the same criteria proven, no weaker check.
- Out of scope: the code; what the tests prove.
- Screens: none.

### B-005 Grid progress on the account

- Status: done (spec 004's decision 8, 2026-10-10: progress shows "on my
  device or account"; the human approved this brief with option A,
  2026-10-29, the spec change and AC-24's rewording, 2026-10-30; review
  approved in rounds 1 and 2)
- Domains: account/account (the route), content/library (rule 7, the merge)
- Architecture decision: yes (a new account route): options from the Plan
  agent on Fable; the human picked A
- Criteria: account AC-19, AC-20, AC-21 (new); library AC-22, AC-23, AC-24
  (new)
- Branch: feat/b-005-account-progress · PR: #66
- Problem: a grid's « Commencée » or « Terminée » comes only from this
  device's `nock.progress`; a signed-in player on another device sees none.
- In scope: a signed-in player's progress read from the account and merged
  with the device's on `/` and `/g/<n>`, per grid `finished` over `started`
  over none. Signed out, accounts off, or a failed request: the device's
  progress alone, the page ready either way. Options:
  - A (lead's pick): derived, nothing stored. `GET /api/account/progress`
    answers `{"<n>": "started" | "finished"}` like `nock.progress`:
    `finished` for each history record, and for each solved room still
    existing of the account's identities; `started` for the others and for
    its creator rooms still existing. 401 without session, 404 accounts off.
    Erasure and privacy unchanged. Lost: « Commencée » once an unsolved room
    expires (it can no longer be resumed); « Terminée » lasts as « Grilles
    terminées » does. About 3 criteria; no clash with B-036 or B-038.
  - B: a table `account_progress (account, grid, progress)` written by the
    client beside `nock.progress` (`PUT /api/account/progress`), read by the
    same `GET`. Keeps « Commencée » forever; erasure must delete it (clashes
    with B-036 on rule 18), and `account.md` would pass the size guidance, so
    a new domain file `account/progress.md` (a map change).
  - C: B's table written by the server (room creation, signed-in join,
    `grid_solved`). Counts rooms joined by link too, but changes the room
    engine and three more domains.
- Out of scope: guests' progress across devices; pushing a device's progress
  up to the account at sign-in; progress from a room joined by link before
  the account's identity was stored; splitting `account/account.md` (19.8 KB,
  a later item after B-036).
- Screens: none change: the catalogue's and `/g/<n>`'s pills as drawn today,
  shown from the device at once, then with the account's when it answers.
- Open questions: none (the human picked A).

### B-008 Docs and comments follow the domain specs

- Status: done (the human asked for it, 2026-10-25)
- Domains: none (docs and comments only)
- Branch: feat/b-008-workflow-docs
- Problem: after B-001, `README.md`, `docs/build-plan.md` and `docs/handoff.md`
  describe the numbered-spec workflow, and comments in `web/src` and four test
  harnesses cite `specs/_design.md` by section.
- In scope: README's workflow on `Backlog.md`, `/new-spec` and `/feature B-NNN`;
  the two old docs removed, anything still current kept in README or the
  backlog; every `_design.md` citation in a comment names its
  `specs/_design/<file>.md` heading.
- Out of scope: any change of behaviour, test or look.
- Screens: none.

### B-009 Run Nock in a Docker container, dev and prod

- Status: done (the human approved option A, 2026-10-25)
- Domains: none (deployment files and README; no behaviour of the app)
- Architecture decision: yes (options from the Plan agent on Fable; the human
  picked A: files and docs, checked once by hand; a CI check is a later item)
- Branch: feat/b-009-docker
- Problem: a maintainer cannot run Nock in a container. The two local attempts
  put `.env*`, `data/` and `.git` into the image (no `.dockerignore`), run as
  root on Python 3.13 (the project pins 3.14) with Node and dev dependencies
  left in, and behind Caddy every player shares the proxy's address, so one
  player's wrong tokens throttle everyone (uvicorn trusts only 127.0.0.1).
- In scope: a two-stage image (Node builds `web/dist`; a 3.14-slim runtime with
  the venv, `src`, `web/dist`, `web/src/i18n` and `grids` at the repo layout
  the server reads), non-root, a `/data` volume, a healthcheck on `/`, `CMD`
  the venv's `python -m nock`; `.dockerignore`; one replica; dev = the same
  image over http on port 8000 with Mailpit for mail; prod = the image behind
  Caddy, the domain from `NOCK_DOMAIN` (default `nock.zyniel.com`), TLS
  automatic, `FORWARDED_ALLOW_IPS` so players keep their address; secrets from
  an env file git ignores (`.env.dev`, `.env.prod`, `data/` in `.gitignore`);
  README's "Running in Docker" with the two `docker compose` commands, in place
  of the PowerShell scripts. Checked once by hand: both setups build, `/`
  serves, a room join works, a room survives a restart.
- Out of scope: a spec and a CI check (option B, later); the hosting choice;
  live reload in a container; Docker secrets files; more than one replica.
- Dependencies (approved with A): base images `python:3.14-slim`,
  `node:lts-slim`, `ghcr.io/astral-sh/uv`, `axllent/mailpit`, `caddy:2-alpine`.
- Screens: none.

### B-010 The brand in the top bar leads home

- Status: done (the human approved option A and the spec change,
  2026-10-25; review approved in round 1)
- Domains: client/shell, client/hud, content/library
- Architecture decision: no (one new `fr.json` key; no protocol, data or
  module interface)
- Criteria: shell AC-10, AC-11 (changed); hud AC-2, AC-20 (changed); library
  AC-12 (changed), AC-19, AC-20 (new)
- Branch: feat/b-010-brand-home-link · PR: #49 (merged)
- Problem: the human asked: "On all displays extended displays, in the top
  bar, the Polygon + "Nock" should he a link back to the home page, grid
  selection." Today the brand (the Nock mark and « Nock », `TopBarBrand`) is
  plain text on every top bar that has it.
- In scope: the brand becomes a link to `/` (the catalogue, « Grilles ») on
  every top bar that shows it: the catalogue (there too, with
  `aria-current="page"`; activating it loads the catalogue again) and the grid
  page, the entry frame (nickname card, status cards, page not found), the
  shared recap, account and operator pages, and the room's computer top bar.
  Its name is a new key `topbar.home`, « Accueil ». From a room it does what
  the Menu's « Retour aux grilles » does: no question, the page loads `/`, the
  player is disconnected and keeps the seat, to resume from « Mes salons »
  within the resume window (`lobby/joining.md`). While the room opens its top
  bar is inert (`client/shell.md` rule 7), the brand with it. The room's Tab
  order on the computer top bar starts with the brand.
- Out of scope: the room's phone top bar, and so the low column layout, stay
  without the brand: there the Menu's « Retour aux grilles » is the way home.
  A question before leaving a room; any change to the Menu; client-side
  routing.
- Screens: every top bar that shows the brand (`_design/room.md` « Computer
  top bar »; `_design/pages.md` « Catalogue », « Entry and not-found pages »,
  « Plain pages »; a « Brand link » row in `_design/foundation.md`
  « Components »), redrawn in the screens sheet with the hover and focus
  states. Option A, picked by the human: the brand keeps its place and look at
  rest; on hover it takes a word-blue background, radius 6 px, as a top-bar
  button does (padding drawn inside a negative margin, so nothing moves);
  focused, the ring of « Components ». Set aside: B, the Nock mark alone on
  the phone top bar (more buttons there, and the Menu already leads home); C,
  the mark at every phone width under the 40 px floor (breaks too much).
- Open questions: none left.

### B-011 The catalogue's brand is plain text

- Status: done (the human approved the brief, its answers and the spec
  change, 2026-10-25; library keeps 21 criteria; review approved in round 1)
- Domains: client/shell, content/library
- Architecture decision: no
- Criteria: library AC-19, AC-20 (changed), AC-21 (new); shell rule 17
  (changed, no criterion)
- Branch: feat/b-011-catalogue-brand · PR: #50 (merged)
- Problem: B-010 made the brand a link to `/` on every top bar that shows it,
  the catalogue included (with `aria-current="page"`). The human decided: the
  Nock mark and « Nock » bring back to the catalogue on any page other than
  the catalogue, the grid page `/g/<n>` and the room included; on the
  catalogue itself they are "simply a plain text + logo".
- In scope: on `/` the brand is the mark and « Nock » as plain text: not a
  link, not a Tab stop, no `aria-current`, no name of its own (it reads
  « Nock »), no hover look. Everywhere else it stays the link « Accueil » to
  `/` (B-010). A criterion that the grid page's brand is that link, which
  B-010 left untested.
- Out of scope: any other page's brand; the name « Accueil ».
- Screens: the catalogue's top bar. The look at rest does not change; only
  the hover and focus states go away there. One option, the human's: the
  brand on `/` as it was before B-010 (`_design/foundation.md` « Brand link »
  no longer applies on the catalogue; `_design/pages.md` « Catalogue »).
- Answers (the human, 2026-10-25): library AC-20 checks the hover look on
  the grid page `/g/<n>`; `/ops` keeps the link, as any page other than `/`.

### B-012 Compound words: a dashed line where the hyphen falls

- Status: done (the human approved look E′ and the spec change, 2026-10-25;
  model option A, the lead's pick; review approved in round 1)
- Domains: content/grids, platform/realtime, gameplay/board
- Architecture decision: yes (grid file, stored grid and the snapshot's grid;
  options from the Plan agent on Fable)
- Criteria: grids AC-3 (changed), AC-20, AC-21 (new); realtime AC-20 (new);
  board AC-21, AC-22 (new)
- Branch: feat/b-012-compound-words · PR: none yet
- Problem: the human asked: "Grid should support "compound word". A compound
  word is represented on the grid with a special representation. Instead of
  standard cell design, the compound word "-" will be represented by a dotted
  line in between the cells instead of a plain line. Propose design options for
  all selection scenarios (selected, no players selecting)". Today rule 4 of
  `content/grids.md` drops the hyphen (`ARC-EN-CIEL` gives `ARCENCIEL`) and
  nothing of it reaches the grid.
- In scope: a hyphen takes no cell, as in printed grids: the edge between the
  two letters it joins is drawn dashed instead of the plain grid line (across:
  the right edge of the letter before it; down: its bottom edge). Typing,
  navigation, word length, check and reveal do not change (they work on
  cells). The model, the new import checks, the snapshot's hyphen marks, and
  the look of the dashed edge in every state.
- Out of scope: marks for spaces and apostrophes (`AUJOURD'HUI` stays as
  today; the model leaves room to add them later); showing the hyphen in the
  clue bar or a word's length pattern; the catalogue's generic grid drawing;
  any change to typing, navigation, check or reveal.
- Model, option A (picked): the hyphen stays in the answer. The file keeps
  writing `"answer": "ARC-EN-CIEL"`: no new key, rule 9 and existing files
  unchanged. The model keeps the answer as written and derives its letters
  (`ARCENCIEL`, today's normalised answer, which the import checks and the
  room's solution read) and its breaks (after letters 3 and 5). New checks
  when the file parses: a hyphen sits between two letters (`-ARC`, `ARC-`,
  `ARC--EN`, `ARC- EN` refused, naming the answer); new last step of rule 6:
  two words sharing an edge (a short word inside a longer run) agree on its
  hyphen, naming both answers and the edge. The snapshot's letter cells get
  two booleans, `hyphen_right` and `hyphen_down` (false by default); realtime
  rule 23 says the grid holds hyphen marks, which name an edge and never a
  letter. Rooms stored before the change hold normalised answers: they load
  and draw no dashed edge. FX-01 and FX-02 stay; criteria use FX-01 variants
  (`VI-DE`, `NA-VAL`). Set aside: B, explicit `"breaks"` per clue (authors
  count letters, a hyphen left in the answer is silently dropped); C, edge
  flags on letter cells in the file (nothing ties a flag to its word).
- Screens: grid cells (`_design/cells.md` « Grid lines and empty cells »,
  « Drawing order », each mark's least size; `cell-sheet.html` by hand; a new
  token in `_design/foundation.md`), then the room in the screens sheet,
  phone and computer. Look E′ (picked by the human, drawn on the throwaway
  comparison page): the plain line of that edge goes; in its place dashes in
  a grey of their own, a new token `--nock-hyphen` (#5E6573, darker than the
  grid lines), the same in every state (no one selecting the word, mine,
  another player's tint, mine and another's, a crossing word selected,
  locked, revealed, checked wrong, catch-up ring, flash, Auteurs mode, pencil
  letters):
  - a whole number of dashes per edge, at least 3, a period of about 5 px per
    pixel of thickness, 60 % dash, half a gap at each end so the corners stay
    open and the edge never merges into the crossing lines; dash ends on
    whole pixels, so fractional cell sizes and pinch zoom never blur them;
  - thickness 1 px under 36 px cells, 2 px from 36 px, 3 px from 72 px: 3
    dashes of about 3 px at 18 px cells (a 320 by 568 phone), about 7 of 5 px
    at a computer's 56 px, 8 of about 7 px at zoom 5 (90 px);
  - contrast 4.26:1 on my selected cell to 5.86:1 on white, 3:1 or more on
    every word, tint and locked background; 2.93:1 on the darkest flash,
    accepted for its 1 s;
  - my selected cell beside the edge: its navy border turns dashed on that
    side, with the same dashes (navy on selected 9.65:1), so the hyphen never
    hides under the border;
  - the triangles, icons, catch-up ring, notch and arrows stay as they are;
    no arrow ever sits on a hyphen edge (an arrow's edge faces its clue
    cell); the revealed notch lies over the dashes of a down hyphen.

  Set aside: ink dots (A, A′), a dotted rule-grey line (B), dots that follow
  the word's state (C), short ink dashes (D), the first E in rule grey (1.27
  to 2.54:1, hidden under my selection border, blurred at fractional sizes).
- Open questions: none left.

### B-013 Grid files in the ipuz ArrowWord format

- Status: done (the human picked option D and named the ipuz fields the
  grids will carry, then approved the spec change with compound words in
  ipuz's own notation, 2026-10-26; review approved in round 1, its
  suggestions checked in round 2)
- Domains: content/grid-files (new, split from content/grids, which keeps
  the model and the import checks), content/grids, content/library (pointers
  only); `specs/_map.md` (table and glossary)
- Architecture decision: yes (the grid file format; options from the Plan
  agent on Fable, two independent passes)
- Criteria: grid-files AC-1 to AC-21 (new domain; AC-1 to AC-5 take grids
  AC-13 to AC-17 and their pointers); grids AC-1, AC-4, AC-5, AC-6, AC-18,
  AC-19 (changed), AC-13 to AC-17 (deleted, moved); library rule 1 (changed,
  no criterion)
- Branch: feat/b-013-ipuz-grids · PR: none yet
- Problem: the human asked: "Replace grid custom grid definition format by the
  standard "ipuz" Arrowword standard. This format is documented at
  https://www.puzzazz.com/ipuz. Shifting to a open-source standard will help
  using of external tooling, and libraries to possbly interact with the grid
  definitions." Today a grid file is Nock's own JSON (rule 9 of
  `content/grids.md`), which no other tool reads.
- What ipuz gives: ipuz v2 (`"version": "http://ipuz.org/v2"`) has a kind
  ArrowWord, `"kind": ["http://ipuz.org/crossword/arrowword#1"]`, with
  `"clueplacement": "blocks"`, one clue list `clues.Clues` and a clue
  `location` `[col, row]`. It has no arrow names, no rule for two clues in one
  cell, and no field for Nock's own decisions (number, published, withdrawn,
  licence). Tools seldom support ArrowWord, and none is known to keep keys it
  does not know when it saves a file, so anything Nock-only written into an
  `.ipuz` file must be assumed lost after an outside edit (the Plan agent's
  reading, not checked against the tools).
- Options:
  - **D (the human's pick): pure ipuz for the grid, Nock's decisions in an
    index.** Each `.ipuz` file uses standard ipuz fields only, no extension
    key, so an outside tool can open and save it without losing anything.
    `grids/catalogue.json` holds what Nock decides about each grid. The grid
    model, the stored rooms, the protocol and the browser do not change. No
    new dependency.
  - Set aside: A, Nock's data in namespaced extension keys of the `.ipuz`
    file (an outside edit can drop `withdrawn` or the licence without a
    word); B, both formats for a time; C, ipuz as import and export only
    (both keep two formats); ipuz as the stored model too (a migration of the
    rooms' snapshots and a client move to `[col, row]`, for no gain).
- Answers (the human, 2026-10-26): option D. Most grids will come from
  external sites, so these ipuz fields will be filled: `publisher`,
  `publication`, `url`, `uniqueid`, `title`, `author`, `editor`, `date`,
  `difficulty` (the equivalent of force), `origin`, `block`, `empty`.
- What lives where (the lead's split, from that answer): what describes the
  grid as published is in the `.ipuz` file, in its standard fields, since
  tools keep those; what Nock decides is in the index.

  | Today's key | Where it lives |
  | --- | --- |
  | `number`, `published`, `withdrawn` (optional, false), `source`, `licence` | the index entry, with `file` (the `.ipuz` name); strict as rule 9 is today |
  | `force` | ipuz `difficulty`, required, 1 to 4 (a number or the same digit as text, as ipuz allows); any other text is refused |
  | `published_on` | ipuz `date`, required, exactly `MM/DD/YYYY`, a real date |
  | `author` | ipuz `author`, required, 1 to 200 characters once stripped |
  | (new) | ipuz `title`, `editor`, `publisher`, `publication`, `url`, `uniqueid`, `origin`, `copyright`: optional text, recorded as written with the entry, never shown to players and never interpreted, like the credits; written back by the writer |

- Grid mapping. Positions stay `(row, column)` in the model and in every
  error; the reader turns ipuz's `[col, row]` into `(row, column)` before any
  message (a message may quote the value as written: `location [4, 0], that
  is (0, 4)`). Coordinates count from zero, as the standard's examples do.

  | Today | ipuz |
  | --- | --- |
  | the file | `version` `http://ipuz.org/v2`, `kind` exactly `["http://ipuz.org/crossword/arrowword#1"]`, `"clueplacement": "blocks"`, clues under `clues.Clues` |
  | `width`, `height` | `dimensions` |
  | letter cell | the file's `empty` value in `puzzle` (ipuz's default `0`; `0` and `"0"` are the same) |
  | clue cell | the file's `block` value (default `"#"`) with one or two clues whose `location` is that cell, in the cell's order; a third is refused |
  | empty cell | a block with no clue (`null`, ipuz's "no cell", is refused) |
  | clue text | `clue` (plain text; HTML entities decoded, a tag refused) |
  | arrow | derived from `location` and the word's `cells` (required): first cell to the right or below, word across or down, gives the four arrows; a one-letter word gets the straight arrow (no grid today has one) |
  | answer | `answer`, as written (B-012: `ARC-EN-CIEL`) |
  | (new) | `solution` (the letters and the block) and `enumeration` (`"3-2-5"`), written by the writer, checked against the answers when present |

  `block` and `empty` must differ. Source of truth: `puzzle` and each clue's
  `location`, `cells` and `answer`. `cells` must be the word that rule 3
  resolves (this check gives AC-6's error); `solution` and `enumeration`,
  when present, must agree with the answers. Reading is strict: an unknown
  core key, or an ipuz feature Nock does not support (`saved`, `checksum`,
  `styles`, `zones`, `Across`, a cell written as an object or a clue number,
  another `clueplacement`, ...), is refused, as the standard asks of a
  reader; ipuz's remaining descriptive keys (`notes`, `intro`,
  `explanation`, `annotation`, `charset`) are accepted and ignored; keys of
  another tool's namespace (`x:y`) are ignored. In the index, an unknown key
  is refused, as today.
- Files: the index names each grid's file; grids are read in the index's
  order (rule 8 today: file-name order); an entry naming a missing file, or
  two entries naming the same file or number, stops the start; a `.ipuz` file
  the index does not name is ignored; no index is an empty catalogue.
- Converter: a writer of the same module turns a catalogue entry back into
  ipuz, for the tests and for a one-shot converter of today's `.json` files
  into `.ipuz` files and index entries, run as a module of the package
  (`uv run python -m nock....`), so no new script in `scripts/`.
- How B-012 fits: B-012 (PR #52, merged) went first; its
  model is unchanged here (the answer as written, `Clue.letters`,
  `Clue.breaks`, `Grid.hyphen_edges`). The human asked (2026-10-26) that a
  compound word use the ipuz format itself, so the file writes it with ipuz's
  own means, all three agreeing: `enumeration` (`"3-2-5"`, ipuz's notation
  for a hyphenated answer), `answer` with or without its hyphens, and the
  `dashed` bar style on the letter before each hyphen (`R` across, `B` down),
  which is the dashed edge B-012 draws. Breaks are the enumeration's hyphens
  when it has one, else the answer's; `dashed`, when a file has any, must
  name exactly the grid's hyphen edges. A space or an apostrophe in an
  enumeration is refused for now (B-012 gives breaks to hyphens only).
- In scope: rules 8 to 12 of `content/grids.md` (the index, the `.ipuz`
  files, the split above, the mapping, the arrow rule, the new checks); the
  criteria that name the file (AC-1, AC-4 as load, write, load equal, AC-5,
  AC-6, AC-13 to AC-15) reworded; new criteria for the version and kind,
  `block` and `empty`, the `puzzle` values, the clues and their locations, a
  clue cell's order and a third clue, `cells`, `solution` and `enumeration`
  disagreeing, `difficulty` and `date`, the recorded descriptive fields,
  `[col, row]` written `(row, column)`, unknown core and foreign-namespace
  keys, the index, and the converter. `tests/fixtures/fx01.ipuz` and
  `fx02.ipuz` added; `fx01.json` and `fx02.json` stay, as the model's own JSON
  (rooms store it). The README's grid-files section follows. If
  `content/grids.md` nears 15 KB, the file rules move to a new
  `content/grid-files.md`.
- Out of scope: the grid model, the stored rooms, the protocol and the browser
  (unchanged); the library (summaries unchanged: `force` and `published_on`
  keep their names there); showing any of the descriptive fields; reading
  other ipuz kinds; a grid editor; converting
  files automatically at start.
- Screens: none.
- Open questions: none left. The lead's picks, to overrule if needed: force
  read from `difficulty` and `published_on` from `date` (one truth each, in
  the file a tool keeps); `difficulty` only 1 to 4, so an importer writes
  `3`, not `Force 3`; `author` moves to the `.ipuz` file while `source` and
  `licence` stay in the index; one index rather than a side file per grid.

### B-014 Tests for the brand link on `/ops`, the recap and the account page

- Status: done (the human picked option A and one state per page, and
  approved the spec change, 2026-10-25; review approved in round 1; no
  implementation step: the tests passed as written)
- Domains: client/shell, admin/operations
- Architecture decision: no (criteria and tests only; no behaviour, code or
  look changes)
- Criteria: shell AC-10 (changed), operations AC-13 (changed)
- Branch: feat/b-014-brand-link-tests · PR: none yet
- Problem: `client/shell.md` rule 17 makes the brand the link « Accueil » to
  `/` on every top bar that shows it but the catalogue's. Criteria prove it on
  the entry frame of a room (shell AC-10), the room's computer top bar (hud
  AC-2) and the grid page (library AC-21), but not on the shared recap
  `/recap/<token>`, the account page `/account` or the operator page `/ops`.
  All use `TopBarBrand` today, so nothing is broken, but a brand drawn another
  way there would go unseen.
- In scope: the link, its name « Accueil », its target `/` and no
  `aria-current`, on those three pages, at a computer and a phone window. The
  recap and account pages share the entry frame (shell rule 9), whose page
  frame `gameplay/results.md` and `account/account.md` leave to
  `client/shell.md`; `/ops` uses the catalogue's frame, and its page belongs
  to `admin/operations.md`.
- Out of scope: any change of behaviour or look; the brand's name (the
  label-in-name follow-up); following the link (B-010 and B-011 test that it
  loads `/`).
- Screens: none.
- Options (the three files are at 20 criteria and over 15 KB, so no new
  criterion is wanted):
  - A. Extend two criteria in place: shell AC-10 names the recap and account
    pages besides `/r/ZZZZZZ`; operations AC-13 says the `/ops` bar's brand is
    the link « Accueil » to `/`. The tests behind their pointers (046 AC-1,
    048 AC-6) are edited in place.
  - B. One new criterion per page's domain (results, account, operations).
    Puts each check by its page, but takes all three files over their budget.
  - C. One new criterion in `client/shell.md`, rule 17's owner, for all
    three pages. Puts shell at 21 criteria and over 16 KB.
  - Lead's pick: A. The checks sit with the criteria that already prove each
    frame, and no file grows.
- Answers (the human, 2026-10-25): option A; one state per page: the recap
  loaded, the account page signed out, `/ops` locked.

### B-015 Word breaks: abbreviations, spaces, apostrophes; ipuz reader review

- Status: done (the human answered the brief and approved the spec change,
  2026-10-27; review approved in round 1, its suggestions checked in round 2)
- Domains: content/grids, content/grid-files; gameplay/board (one Out of
  scope line); `_design/cells.md` « Hyphen edges » and the captions of the
  cell sheet's « 4b » and the screens sheet's compound words (text only, no
  change of look). `platform/realtime.md` rule 23 and `gameplay/board.md`
  rule 20 already speak of a word's break and its marks, so they stay.
- Architecture decision: yes (the stored grid's answers and the grid file
  format; options from the Plan agent on Fable)
- Criteria: grids AC-3, AC-20, AC-21 (changed); grid-files AC-7, AC-15,
  AC-18, AC-21 (changed); board: no criterion (one Out of scope line)
- Branch: feat/b-015-abbreviations · PR: none yet
- Problem: the human asked: "Review the ipuz parser, and include abreviation
  support. Abreviations should visually behave like compound words. They will
  use "." i the "enumeration" field to separate letters. A.I will have AI as
  answer, Artificial Intelligence as clue for example." Today an enumeration
  holding `.` is refused, and so is an answer holding one.
- Review of the reader (`src/nock/ipuz.py` against ipuz v2.0.2):
  - Accepted: the v2 ArrowWord kind only, `clueplacement` `blocks`, clues
    under `clues.Clues` as objects of `clue`, `location`, `cells`, `answer`
    and an optional `enumeration`; `puzzle` values `block`, `empty`, or a
    letter cell with the `dashed` style; `solution` of letters A to Z and the
    block; `notes`, `intro`, `explanation`, `annotation`, `charset` ignored;
    namespace keys (`x:y`) ignored; clue text plain, entities decoded.
  - Refused by design (strict reader, rule 7): `saved`, `checksum`,
    `styles`, `zones`, `Across`, a clue as a text or a pair, a clue's
    `number`, `label`, `hints`, `image`, `continued`, `references`, named
    styles, `barred`, null cells.
  - Gaps found:
    1. Enumeration separators: only `-`. ipuz also writes ` ` (words), `.`
       (an abbreviation's period, after its count: `A.M.` is `1.1.`), `'`,
       `,` and `;`. **The human's three Le Parisien sample files are all
       refused today** for this: `I A` under `"1 1"` (INTELLIGENCE
       ARTIFICIELLE), `RC` `"1 1"`, `ESE` and `DCA` `"1 1 1"`, `ENAVANT`
       `"2 5"`.
    2. An answer holding `.` (`A.I`) is refused by the model (rule 4 of
       `content/grids.md` removes only spaces, hyphens and apostrophes).
    3. `showenumerations` (a core crossword key tools write) is refused.
    4. `dotted` is refused, though ipuz draws dotted with dashed as dashed.
    5. `solution` must hold Nock's normalised letters: `É` or a lower-case
       letter there is refused (ipuz's solution is case-sensitive).
    6. A key written twice in one object silently keeps its last value.
    7. A file starting with a UTF-8 byte order mark (some Windows tools
       write one) is refused as "not valid JSON".
    8. A clue's descriptive `explanation`, `tags` or `type` is refused.
  - This item fixes 1 (`.`, ` ` and `'`, each a break with the dashed
    edge), 2 and 3. Gaps 4 to 8 go to « Small follow-ups » (none hits a file
    the human has today).
- Options (Plan agent on Fable):
  - **A (picked): the separators stay in the answer as written.** Rule 4
    gains `.`: the letters drop it as they drop `-`, ` ` and `'`. The answer
    as written keeps each separator's kind (`A.I.` stays `A.I.`), so the
    model needs no new field; `Clue.breaks` and the edges keep their shape.
    Stored rooms: same shape. Protocol: unchanged, the same `hyphen_right` /
    `hyphen_down` marks, now set for every break. No client change.
  - B: breaks get a kind in the model and in the snapshot's marks, ready for
    kinds that look different one day. Adds the protocol, the room, the
    client and their criteria, for no visible difference. Set aside: the kind
    can reach the mark the day a kind looks different, since A keeps it in
    the answer.
  - C: the reader turns `.` into `-`. The writer then writes `1-1` for
    `1.1.`, so a grid no longer survives the round trip as written. Set
    aside.
- Answers (the human, 2026-10-27): "Update my spec and support
  abbreviations, apostrophes in the most ipuz fashion. Include support for
  proper "." abbreviations and simple space " ". A.I. or "A I" "A.I" on top
  of current "-"". Then: "do not do A.I. (last dot). Support answer A but
  with space, dot, hyphen". The lead reads them as option A, with every separator
  between two letters, hyphen, dot, space or apostrophe, a break drawn as the
  compound word's dashed edge (so `A I`, `A.I` and `A-I` look the same, and
  so do `EN AVANT` and `AUJOURD'HUI`), and no trailing dot.
- The model (`content/grids.md` rule 4):
  - The separators are `-`, `.`, ` ` and `'` (`’` is read as `'`). The
    letters drop them all. A break is exactly one separator between two
    letters, counted as the letters before it: `A.I`, `A I` and `A-I` give
    the letters `AI` and a break after 1; `AUJOURD'HUI` a break after 7;
    `ARC-EN CIEL` after 3 and 5.
  - A separator at the start or the end, or two in a row, is refused,
    naming the answer: `A.I.`, `.AI`, `A..I`, `A.-I`, `A  I`, `DR. NO`,
    `-ARC`, `ARC- EN`.
  - Step 8 of rule 6: two words sharing an edge agree on its break, not on
    its kind (both draw the same dashes).
  - Rooms stored since B-012 keep their answers as written, so one holding
    `AUJOURD'HUI` now draws its edge; rooms stored before hold letters only
    and draw none, as today.
- The file (`content/grid-files.md` rules 7, 9, 12, 14), as ipuz writes an
  enumeration:
  - Enumeration: counts of one or more joined by single `-`, `.`, ` ` or
    `'`: `1.1`, `1 1`, `1-1`, `7'3`, `3-2-5`, `1.1-3` load. A trailing `.`
    (ipuz's `1.1.`, `5 1.1.`), two separators in a row (`2. 2`), `,`, `;`,
    `0` (unknown length), `*`, `^`, `+` and `=` are refused.
  - Answer: written with the enumeration's separators (`A.I` under `1.1`,
    `A I` under `1 1`), or as letters only (`AI`), which takes the
    enumeration's separators: `AI` under `1.1` is the model's `A.I`.
    Separators that differ from the enumeration's, kind included, are
    refused naming the clue (`A I` or `A-I` under `1.1`). Without
    enumeration the answer's own separators rule, as today.
  - `dashed` names every break edge, whatever its separator, with today's
    check.
  - Writer: `answer` as written and the enumeration derived from it, so
    `A.I` writes `1.1`, `A I` `1 1`, `A-I` `1-1`, and each reads back
    equal.
  - `showenumerations` (a boolean) is accepted and ignored.
- In scope: rule 4 and step 8 of `content/grids.md`; rules 7, 9, 12, 14 of
  `content/grid-files.md`; one sentence in `_design/cells.md` « Hyphen
  edges » saying every break is drawn so. Criteria changed in place where
  they can: grids AC-3 (`AUJOURD'HUI` gets its break), AC-20; grid-files
  AC-7, AC-15 (`"2 3"` and `"2'3"` load), AC-18, AC-21. No new criterion in
  `content/grid-files.md`, already over its size budget.
- Out of scope: a mark of its own per separator (option B); showing the
  enumeration in the clue bar; the reader's gaps 4 to 8 (« Small
  follow-ups »); rewriting the Le Parisien files (they load once this is
  built: `I A` under `1 1` draws the dashed edge).
- Screens: none redrawn. Every break is drawn as B-012's dashed edge (look
  E′), whose drawing does not change; « Hyphen edges » and the cell sheet's
  « 4b · Compound words » caption name the other separators.
- Open questions: none left. To overrule if the lead misread: a space and an
  apostrophe draw the dashed edge too, not only the dot; the apostrophe stays
  in (asked in the first answer, not named in the second).

### B-025 Split `client/hud.md`: the room panel and the notes

- Status: done (the human approved the brief, option A and both of the
  lead's defaults, with the new file named `client/room.md`, then the spec
  change as written, 2026-10-28; built and reviewed in two rounds, 2026-10-28)
- Domains: client/hud, client/room (new); citations repointed in social/chat,
  social/catch-up, social/presence, gameplay/hints, platform/server,
  client/shell, `_settings.md` and `_map.md`
- Architecture decision: yes, it adds a domain (options from the Plan agent on
  Fable)
- Criteria: room AC-1 to AC-7 (new file, moved word for word from hud AC-4,
  AC-11 to AC-14, AC-17, AC-18 with their 043 pointers); hud AC-4, AC-11 to
  AC-14, AC-17, AC-18 (moved out, numbers never reused)
- Branch: feat/b-025-hud-split · PR: none yet
- Problem: `client/hud.md` holds 19.4 KB and 20 criteria, over the budget of
  about 15 KB and 20 (`specs/_map.md`, « What a spec holds »). B-021 (the room
  gone dialog) adds about 1.8 KB and 2 criteria to it, and waits for this item.
- In scope: the room panel (« Salon ») and the 3-second notes leave `hud.md`
  for a new `client/room.md`. Rules and criteria move word for word; each criterion
  keeps its pointer to 043 and takes a number from AC-1 in the new file; the
  numbers it leaves in `hud.md` are never reused. Rules are renumbered in both
  files and every citation in other specs follows. `_map.md` gains the file's
  row (043 split between the two rows) and a glossary line for the room panel
  and the notes. The table's Look column keeps naming the design file
  `_design/room.md`.
- Out of scope: any change of behaviour, look or tests. Every `hud.md`
  criterion is proven by its pointer to 043, so no test file changes and no
  code cites `hud.md`. B-022 (creator rooms) runs alongside: it edits `hud.md`
  rules 11 and 18 (they stay) and one word of rule 17 (it moves), and both
  items touch the glossary; whichever merges second resolves it.
- Screens: none.
- Options (the Plan agent on Fable; the lead's pick first):
  - **A (pick): the request's cut, with rule 7.** Rules 7 (the « Salon »
    button's badge and dot), 14 to 17 (the Salon) and 20 to 22 (the notes),
    with AC-4, AC-11 to AC-14, AC-17 and AC-18, go to a new file:
    `hud.md` about 13.3 KB and 13 criteria (about 15.1 KB and 15 after B-021),
    the new file about 7.8 KB and 7. It follows the seam that
    `_design/room.md`, the code (`Salon`, `PlayersPanel`, `RoomNote`) and the
    other specs already draw: chat, catch-up and hints cite the Salon and the
    notes as one pair. About ten citations move.
  - B: the Salon only (rules 7, 14 to 17; AC-4, AC-11 to AC-14). `hud.md`
    about 15.0 KB and 15 criteria, but about 16.9 KB and 17 after B-021: over
    budget again, so a second split follows.
  - C: A, and the menus and sheets (rules 9 to 12 and 18; AC-6 to AC-9 and
    AC-15) to a third file `client/menus.md`. The most room (`hud.md` about
    9.2 KB, 8 criteria), but it cuts the popover rule 13 and AC-10 across files
    and moves nine more citations for a budget problem that does not exist yet.
- Answers (the human, 2026-10-28): option A. Rule 7 moves with AC-4, which
  proves it (`hud.md` rules 8 to 13 become 7 to 12; `client/shell.md` and
  `social/chat.md` follow). « Salon » is the room, so the new file is
  `client/room.md`, not `client/salon.md`; its title says it is the room
  panel and the notes.
- Naming: once a domain is called `room`, no other may be called `room-...`
  (the gate: its test files would also name `room`). B-023 planned a
  `lobby/room-life.md`; its brief takes another name.

### B-022 Creator rooms and host return

- Status: done (the human approved the brief as written, with the lead's
  calls, then the spec change as written, `invalid_target` included,
  2026-10-28; in review round 1 the human made erasure delete the creator
  rooms and approved that spec change, 2026-10-29; built and reviewed in two
  rounds, 2026-10-29)
- Domains: lobby/host (new: the host role, moved from `lobby/rooms.md` rules
  13 to 21), lobby/rooms, lobby/joining, account/account, platform/realtime;
  `specs/_map.md` (a table row, the glossary); "guest" reworded in product,
  client/hud, admin/operations, `_reference.md`; citations of the host rules
  repointed in client/hud (rules 10 and 13), client/room, and wherever else
  `lobby/rooms.md` is cited for them
- Architecture decision: yes (a new domain file; stored data: the room's
  creator and each member's account; the room socket reads the session
  cookie). The options were weighed by the Plan agent on Fable for the first
  brief of this request; the human settled them, so no new Plan run.
- Criteria: host AC-1 to AC-8 (moved from rooms AC-13 to AC-20, pointers to
  014 kept), host AC-9 to AC-16 (new); rooms AC-13 to AC-20 (deleted, moved);
  joining AC-21 (new); account AC-13, hud AC-8, product AC-1 (wording only)
- Branch: feat/b-022-creator-rooms · PR: none yet
- Problem: the human asked: "Creator rooms and host return." Today the first
  joiner is host, a host away 60 s loses the role for good, an account may
  hold several members of one room, and "guest" means three things (an
  invited player, a player with no account, a player who is not host).
- In scope, the human's request as written:
  - Terms, in the glossary of `specs/_map.md` and used the same way in every
    domain; "guest" dropped as a spec term: account player (a member linked
    to an account); anonymous player (a member linked to no account);
    invited player (someone who enters by the room link and the nickname
    form); connection (one socket of a player; "session" stays the sign-in
    cookie); creator (the account whose session sent `POST /api/rooms`, set
    once at creation and never changed; none without a valid session or
    with accounts off); creator room and anonymous room (a room with and
    without a creator; a room created without a session stays anonymous
    even if its host signs in later); creator's player (the member of a
    creator room linked to its creator); stand-in host (a host of a creator
    room other than the creator's player); hand-over delay
    (`host_handover_seconds`, 60 s).
  - An account is at most one player in a room. A signed-in join to a room
    where the account already has a member gets that member back (seat,
    colour, letters, host role), and the older connection is closed with
    4001 as in today's takeover. The room socket learns the account from
    the session cookie.
  - The creator's player is host whenever connected: their join, resume or
    seat back gives them the role at once in one `host_changed`; while they
    are away longer than the hand-over delay, the role passes on as today.
  - A stand-in host cannot remove or mute the creator's player; a lock does
    not keep the creator's player out; a full room still does.
  - If the creator's account is erased, the room is deleted (the human's
    decision in review round 1, replacing "becomes an anonymous room").
  - Every duration or limit is written as its name with its default, never
    a bare number.
- Out of scope: any mark of the creator in the roster, the snapshot or the
  page; room lives (B-023); handing the role on by hand; co-hosts.
- Screens: none.
- Already decided by the human (on the first brief of this request and its
  spec change, 2026-10-28):
  - Where it lives: **A, a new file `lobby/host.md`**, "the host role: who
    holds it, how it passes, what it may do; the creator". It takes
    `rooms.md` rules 13 to 21 and AC-13 to AC-20 (pointers to 014 kept,
    renumbered from AC-1) and adds about eight criteria; `rooms.md` falls to
    12 criteria. The one-player-per-account rule changes in place in
    `joining.md` and `account.md`; `realtime.md` gets a sentence on the
    cookie and no criterion. Rejected: B, a `lobby/members.md`; C, edits in
    place in four files already at their budget.
  - Terms: **A, written in this item**, not in a wording-only item first.
  - Shape:
    - The room stores its creator's account id, set by `POST /api/rooms`
      from a valid `nock_session` (none with accounts off), in a nullable
      column of the store table `room_times`, beside `last_edit_at`, so that
      B-023's sweep reads a room's kind from one table. Stored rooms without
      it are anonymous rooms. The column makes `PRAGMA user_version` 1;
      B-023 takes 2.
    - Each member stores its account id, set at a signed-in join. The
      creator's player is the member whose account is the creator, not a
      stored member id, so a time-out and seat back keeps them.
      `PUT /api/account/rooms` stays for pages already open and links no
      member.
    - The join's member is chosen once, before the steps: signed in, the
      account's member of the room, player or past player, whatever token
      the join carries; else the member whose token it carries. A token
      that is not the join's member's is not used: its member is not
      touched and their connection stays open. Steps: removed token; the
      member a player: resume (older connection 4001), or time out and go
      on; locked (skipped for a join from the creator's session, member or
      not); full (for everyone); the member a past player: seat back;
      nickname; new player.
    - The hand-over tick also gives the role back to a connected creator's
      player who lacks it, so "whenever connected" holds after a plain
      reconnection; the tick never gives the role to a disconnected player.
    - Erasure deletes the account's creator rooms, live and stored, as an
      expired room's deletion does; in other rooms its recorded identities'
      players become `--`, unlinked. Its criterion lives in `host.md`
      (AC-15). (Review round 1; the first shape cleared the creator.)
    - Rooms where one account already holds several members get no
      backfill: the member whose token the device sends is stamped at the
      next signed-in join. A member linked to account A, joined with its
      token by a device signed in as B with no member there, is resumed and
      stays A's.
    - Accounts turned off after creation: the room keeps its creator in the
      store and plays as an anonymous room while accounts are off.
    - A signed-in page with no stored identity still shows the nickname
      form; a removed account player may come back from another device as a
      new player, as today.
- New since the first brief (the lead's calls; say if any should change):
  - B-025 split `client/hud.md`: the host rules are cited from hud rule 10
    (« Réglages de l'hôte » in the Menu) and rule 13 (the settings sheet),
    and the remove and mute buttons from `client/room.md` (the Salon's
    Joueurs tab). Those citations move to `lobby/host.md`.
  - `joining.md` gains one criterion (the account's member wins over a
    token) and goes to 21 criteria and about 17.5 KB, a little over the
    budget of about 15 KB and 20; `account.md` is already at about 19 KB.
    The lead keeps them there, since the rules belong there, and adds a
    small follow-up to trim or split both.
  - B-021 (room gone dialog) runs at the same time and may touch
    `joining.md` and `hud.md`; whichever merges second merges `origin/main`
    and resolves. B-023 waits for this item.
- Open questions: none.
- Review round 1 (2026-10-29): one blocking finding, `account.md` rule 18
  promising that erasure unlinks the account's members in every room while
  the code did it only in its creator rooms and through its identities. The
  human: "Make things simpler. When deleting an account, remove all rooms
  belonging to the host.", then "Go: erasure deletes the account's creator
  rooms, as you laid it out, with your defaults." The defaults: "belonging
  to the host" means the rooms the account created; their players' sockets
  close with 4404 (the room-gone dialog of B-021); other players' finished
  grids stay in their history; in other rooms the account's recorded
  identities' players become `--`, unlinked, and rule 18 says only that.
  B-023's "a room that changes kind (… its creator's account erased)" no
  longer happens: its brief drops that case.

### B-021 Room gone dialog

- Status: done (the human approved the brief as written, then the spec
  change as written, 2026-10-28; built and reviewed in two rounds,
  2026-10-28)
- Domains: client/hud (a new rule and two criteria; rules 3 and 7 name the
  dialog), client/shell (rule 7, one line), lobby/joining (rule 16, one line);
  `_design/overlays.md` (a new section « Room gone »), `_design/room.md`
  « Connection lost » and « Layers », `_design/foundation.md` (the dialog
  scrim and bottom sheet rows); the screens sheet, part 3
- Architecture decision: no (the client only: the server already closes every
  socket of a deleted room with 4404; no message, stored data or public name
  changes)
- Criteria: hud AC-21, AC-22 (new); shell, joining: no criterion (one line
  each)
- Branch: feat/b-021-room-gone · PR: none yet
- Request (the human, 2026-10-28, word for word): "Players inside a room that
  expires are displayed a "This room no longuer exists" popup (To translate in
  French) and routed back to the menu."
- Problem: once the room has shown, the 4404 close of a deleted room ends the
  page on `not_found`: the status band « Ce salon n'existe pas. » under the top
  bar (`client/hud.md` rule 7), the grid still drawn and typable under it, its
  letters going nowhere, and no way on but « Retour aux grilles » or the brand.
- When it happens: a room expires 30 days after its last edit and the hourly
  sweep deletes it (`lobby/joining.md` rules 15, 16). A player meets it with a
  tab left open on an idle room, or when a page back from a long sleep or an
  offline spell opens a socket to the deleted room: a 4404 after the first
  snapshot, joined or reconnecting.
- In scope: on that 4404, a modal alert dialog titled `room.gone.title`
  « Ce salon n'existe plus. », with the existing line
  `room.status.not_found_detail` (« Un salon est effacé 30 jours après sa
  dernière modification. ») and one primary link, `share.home` « Voir les
  grilles », to `/`, the catalogue (the lead reads the human's "menu" as the
  home page, not the room's « Menu »). The dialog takes the focus and is
  announced; a menu, the Salon sheet, a room sheet or the recap open at that
  moment closes; the connection band goes, pending edits are dropped, and the
  room under the scrim is inert. It goes into `client/hud.md` (about 15.1 KB
  and 15 criteria after it, within the budget).
- Out of scope (the human's answer: removed players): a player removed by the
  host keeps the status band « Vous avez été retiré de ce salon. ». Also: a
  4404 before the first snapshot (the entry card « Ce salon n'existe pas. »
  stays, that player never saw the room); the other final statuses once the
  room has shown (locked, replaced, throttled keep the band); a warning before
  expiry or extending a room; forgetting the stored identity of a deleted room.
- Screens: the room page once it has shown, in both layouts; the screens sheet
  draws « The room deleted after it showed » in part 3. Options:
  - **A (the human's pick): a dialog with one way out.** The recap's frame
    (`_design/overlays.md` « Recap »: a 440 px dialog in the column layout, a
    bottom sheet in the sheet layout, over the dialog scrim): the title, the
    30-day line in muted, « Voir les grilles » right-aligned. Escape does
    nothing, since there is no room to go back to. The page changes only on
    the player's press, as the accessibility baseline wants.
  - B (rejected): the same dialog, and `/` loads by itself after 10 seconds.
  - C (rejected): no dialog; `/` loads at once and the catalogue shows a
    3-second note.
- Order: B-022 (creator rooms) runs alongside; the two share only this file.
  B-023 later moves `lobby/joining.md` rule 16 with this item's line in it.
- Answers (the human, 2026-10-28, on an earlier brief of this request):
  "Approved, option A. Removed players stay out of scope."
- Open questions: none new. To overrule if the lead misread: "menu" is the
  catalogue `/`, and the French text is the title « Ce salon n'existe plus. »
  over the existing 30-day line.

### B-023 Room lives as variables

- Status: done (the human approved the brief as written, with the lead's
  calls: `lobby/lifetime.md`, the erasure case dropped, then the spec change
  as written, 2026-10-29; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-021, B-022 and B-025 are merged and on this
  branch). B-024 (/ops overrides) waits for this item.
- Domains: lobby/lifetime (new: joining rules 15, 16 and AC-14, AC-15 move
  there), lobby/joining, admin/operations, platform/server, client/shell (the
  card line); citations and the quoted line in client/hud, lobby/host,
  account/account; citations only in gameplay/results and social/catch-up;
  `specs/_map.md` (a table row, the glossary), `_settings.md`,
  `_design/pages.md`, `_design/overlays.md`; the screens sheet
- Architecture decision: yes (a new domain file, stored data: the solve time
  in `room_times` and `PRAGMA user_version` 2, `RoomConfig` fields, five
  environment variables, the `/ops` dashboard answer). The Plan agent on
  Fable weighed the options for the first brief of this request and the
  human picked them; no new Plan run.
- Criteria: lifetime AC-1, AC-2 (moved from joining AC-14, AC-15, pointers
  to 032 AC-1, AC-2 kept), lifetime AC-3 to AC-13 (new); joining AC-14,
  AC-15 (deleted, moved); operations AC-4, AC-14 (changed); host AC-9
  (changed); hud AC-21, shell AC-9 (changed: the card line); joining AC-17
  (wording only)
- Branch: feat/b-023-room-lives · PR: #63
- Problem: a room lives a fixed 30 days after its last edit
  (`lobby/joining.md` rules 15, 16), a bare number in four specs, the
  expired-room card and the room-gone dialog, with no setting. The human wants
  one life per kind of room, each an environment variable, and exact terms.
- In scope, the human's request as written (2026-10-28):
  - Glossary terms: edit and last edit time (as today); solve time (the time
    of the room's `grid_solved`); room life (how long a room lasts after its
    starting point); expired room (more than its room life past its starting
    point; at exactly its room life it is not expired); sweep; shortest room
    life (the least of the four).
  - The 30-day rule is replaced by four room lives, each an environment
    variable in whole hours from 24 to 8760 with a `RoomConfig` field, all
    defaulting to 720: `NOCK_CREATOR_SOLVED_ROOM_HOURS` (a solved creator
    room, from its solve time), `NOCK_CREATOR_ROOM_HOURS` (an unsolved creator
    room, from its last edit), `NOCK_ANONYMOUS_SOLVED_ROOM_HOURS` (a solved
    anonymous room, from its solve time), `NOCK_ANONYMOUS_ROOM_HOURS` (an
    unsolved anonymous room, from its last edit).
  - The sweep runs at start and every `NOCK_EXPIRY_SWEEP_MINUTES`, whole
    minutes from 1 to 1440, default 60. A value out of bounds stops
    `python -m nock` before it serves, as the other variables do.
  - A room that changes kind takes the matching life from the same starting
    point (see the open question on erasure). With accounts off every room
    is anonymous.
  - The `/ops` dashboard offers only those of its 1, 7 and 30-day periods no
    longer than the shortest room life.
  - The expired-room card's line names no duration.
  - Specs write each life as its variable with its default, never a bare
    number.
- Out of scope (the human's): changing the values from `/ops` (B-024); other
  durations (resume window, idle state, votes, sign-in links) stay constants.
  Also: a warning before expiry; a log of how many rooms a sweep deletes.
- Note: a room's solve time equals its last edit time (the solving letter and
  `grid_solved` are one step, and `gameplay/rules.md` rule 3 refuses every
  edit once solved), so the solved and unsolved lives differ only by which
  variable applies. The specs keep both names, as asked, and say so once.
- Size: more than three domain files, kept as one change. Five files get only
  a repointed citation or the reworded line, and the two parts that could
  leave (the `/ops` periods, the card line) would be false the day the lives
  ship. `joining.md` falls to about 16 KB and 19 criteria.
- Already decided by the human (every pick A of the first brief of this
  request, 2026-10-28):
  1. **A new lobby file** takes `joining.md` rules 15 and 16 and AC-14,
     AC-15 (pointers to 032 kept), the kinds, starting points, change of
     kind, accounts off, the sweep and the five variables' rules;
     `platform/server.md` rule 15 only adds them to its order of checks;
     joining keeps AC-17 and points to the new file. Rule 16 moves with
     B-021's clause word for word ("a page that had shown the room then shows
     the room-gone dialog (`client/hud.md` rule 16)"), and every citation of
     joining rules 15 and 16 is repointed: `lobby/host.md` rule 14,
     `client/hud.md` rule 16, `account/account.md` rule 20,
     `admin/operations.md` rule 2 and its Depends on, `platform/server.md`,
     and the Depends on and Out of scope lines that name the sweep.
  2. **Stored data:** `room_times` gains the solve time (the creator column
     is already there, B-022, `user_version` 1); one pure function decides
     expiry for the sweep, the lookups and B-024's dry run; old databases are
     migrated once at open to `user_version` 2, the solve time read from each
     solved room.
  3. **`RoomConfig`:** four `int` fields in hours
     (`creator_solved_room_hours`, `creator_room_hours`,
     `anonymous_solved_room_hours`, `anonymous_room_hours`, 24 to 8760,
     default 720) replacing `room_life_seconds`; `expiry_sweep_seconds` stays
     a float in seconds, the whole-minute bound on the variable only.
  4. **The `/ops` periods:** the dashboard answer names the offered periods
     (1 day is always offered, since the shortest life is at least 24 hours;
     the default is 7 days when offered, else 1); the page draws only those;
     a period not offered answers 422 as a wrong one; rule 12 reads "within
     an offered period none has expired".
  5. **The card line:** `room.status.not_found_detail` becomes « Un salon est
     effacé après un certain temps sans modification. », in the entry card
     (`client/shell.md` AC-9, `_design/pages.md`) and the room-gone dialog
     (`client/hud.md` AC-21, `_design/overlays.md` « Room gone »); the key
     stays.
- Screens: the expired-room card (screens sheet part 2) and the room-gone
  dialog (part 3) change one muted line, as picked; the `/ops` dashboard draws
  only the offered periods, all three with the default lives, so its drawing
  stays. No option left to choose.
- New since the first brief (the lead's calls; say if any should change):
  - The file is **`lobby/lifetime.md`**, « Room lifetime: when a room
    expires and the sweep that deletes it ». `lobby/room-life.md` is no
    longer possible: B-025 named a domain `room` (`client/room.md`), and no
    domain may be `room-...`, since its test files would also start
    `test_room_`. Another name would be `lobby/expiry.md`.
  - The sweep interval also paces the purge of old sign-in links and
    sessions (`account/account.md` rule 20), which then runs as often as
    every minute; it stays tied to the sweep.
- Open questions:
  1. **Erasure no longer changes a room's kind.** The request says "a room
     that changes kind (solved, or its creator's account erased)". Since
     B-022's review, erasing the creator's account deletes the creator room
     (`lobby/host.md` rule 14); it never becomes anonymous. The changes of
     kind left are: solved, and accounts turned off (a creator room plays as
     an anonymous room while accounts are off, `lobby/host.md` rule 15) or
     back on. The lead drops the erasure case and writes those two; a room
     already past its new life then goes at the next sweep or lookup.

### B-024 /ops overrides of the room lives

- Status: done (the human approved the brief as written, with the lead's
  calls, and picked A for the INFO log, then the spec change as written with
  the lead's calls, 2026-10-29; the dry run's count and AC-16's wording fixed
  on the human's word; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-023 is merged and on this branch).
- Domains: admin/overrides (new), admin/operations (its token and throttle
  rules cover the new routes; the periods read the effective lives),
  lobby/lifetime (its rules read the effective value), product (the stable
  routes); `specs/_map.md` (a table row, the glossary), `_settings.md`,
  `_design/pages.md` « Plain pages: account, shared recap, operator »; the
  screens sheet, the `/ops` part
- Architecture decision: yes (a new domain file, new stable routes, stored
  data, the first write in the ops API). The Plan agent on Fable weighed the
  options for the first brief of this request and the human picked them; no
  new Plan run.
- Criteria: overrides AC-1 to AC-20 (new); operations, lifetime, product:
  no criterion changed (rules only)
- Branch: feat/b-024-ops-overrides · PR: #64
- Problem: the room lives and the sweep interval are environment variables
  (`lobby/lifetime.md` rules 4, 7), so changing one means a restart, and the
  operator cannot see how many rooms a shorter life would delete.
- In scope, the human's request as written (2026-10-28):
  - Glossary terms: default value (built in); environment value (the
    variable's, when set); override (a value saved from `/ops`, stored in the
    database, in memory when `NOCK_DATABASE` is unset); effective value (the
    override, else the environment value, else the default; every rule reads
    it); dry run (how many rooms a proposed value would delete now, nothing
    saved).
  - The operator page gets a section listing the four room lives and the
    sweep interval, each with its effective value and its source (default,
    variable, override).
  - The operator can save an override within the same bounds, or reset it to
    the environment value.
  - `GET /api/ops/settings` reads them, `PUT /api/ops/settings` saves one,
    and a dry run gives the count without saving, all behind the operator
    token and its throttle.
  - Saving a shorter room life asks for confirmation with the dry run's count.
  - An override applies at once (lookups and the next sweep use it) and is
    logged at INFO with its name, old and new value, never the token.
  - The dashboard periods follow the effective shortest room life.
- Out of scope (the human's): overriding other settings. Also: several app
  processes sharing overrides (`platform/server.md` leaves them out); a
  history of overrides (between two operator tabs, the last save wins);
  splitting `operations.md`.
- Size: four domain files, kept as one change: `lifetime.md` and
  `product.md` get one line each, and `operations.md` changes in place with
  no new criterion (it is at about 18.8 KB and 20 criteria).
- Already decided by the human (every pick A of the first brief of this
  request, 2026-10-28):
  1. **Where:** a new domain file **`admin/overrides.md`** holds the
     effective value, the routes, the storage, the log and the page section;
     its tests are `tests/test_overrides_*.py`. `operations.md` keeps the
     token, the throttle and rules 6, 8 to 10, which also cover the new
     routes.
  2. **API:** `GET /api/ops/settings` answers the five settings, each with
     its name, effective value, source, default, environment value,
     override, bounds and unit, and `durable` (whether a database file holds
     the overrides). `PUT /api/ops/settings {"name", "value"}` saves one,
     `value: null` resets it, and answers the same list.
     `POST /api/ops/settings/dry-run` with the same body answers
     `{"rooms": n}`; it takes only the four lives (the sweep interval deletes
     nothing), and a reset's dry run uses the value the reset falls back to.
     An unknown name or a value out of bounds answers 422.
  3. **Storage:** one table `overrides (name, value)` in the room store,
     untouched by room deletion, in memory when `NOCK_DATABASE` is unset. At
     start a stored override with an unknown name or a value out of bounds is
     dropped with one WARNING; the start never fails over it. An override
     outranks the variable even if the variable changed since; the page shows
     the variable's value beside it. Without a database file the card shows
     the muted line « Sans base de données, ces réglages sont perdus au
     redémarrage. »
  4. **Applying at once:** the registry swaps its config under its lock; the
     next lookup uses the new value; the sweep uses it on its next run, and a
     new interval starts after the current wait. Saving does not sweep.
  5. **Dashboard periods:** see "New since the first brief".
  6. **Screen:** one card « Durées de vie des salons » under the dashboard,
     five rows (« Salon d'un compte, résolu », « Salon d'un compte, en
     cours », « Salon anonyme, résolu », « Salon anonyme, en cours »,
     « Intervalle de nettoyage »), each with its value (« 720 h »,
     « 60 min »), a source chip (« par défaut », « variable », « modifiée »),
     a number field, « Enregistrer » (primary) and « Rétablir » (quiet). The
     confirmation is the account page's disclosure pattern inside the card,
     under a divider: « Cela effacera N salons maintenant. », « Confirmer »
     (primary), « Annuler »; no red button. A value out of bounds shows
     « Valeur hors limites (24 à 8760 h). » On a phone each row stacks.
- Screens: `/ops` gains that card (`_design/pages.md`, screens sheet part 7,
  in both layouts, with the confirmation open in one of them).
- New since the first brief (the lead's calls; say if any should change):
  - **Dashboard periods (pick 5 replaced):** B-023 already made the
    dashboard answer name its offered periods (`offered_days`,
    `admin/operations.md` rule 12). Pick 5's `period_limit_days` is dropped;
    `offered_days` and the default period are computed from the effective
    lives, so a saved override changes them at the next dashboard request.
  - **Settled by B-023:** the dry run calls B-023's one expiry function
    (`is_room_expired`) over the stored room times, which hold the kind and
    the solve time; the expired-room line already names no duration. These
    two open questions of the first brief are closed.
  - **What the dry run counts:** every room the proposed value would delete
    now, including any already due under the current value (the lead's
    default in the first brief), so the count matches what the next sweep
    would do.
  - **Throttle and cache:** the new routes follow `operations.md` rules 8 to
    10: only a 401 counts toward the throttle, a 422 never does, and every
    answer has `Cache-Control: no-store`.
  - **Environment value of an app given a registry** (the tests'
    `create_app(rooms=...)`): its config stands in for the environment
    values, as `lobby/lifetime.md` rule 7 already reads no variable then.
  - **Lowering the sweep interval** asks no confirmation: it deletes nothing
    by itself.
- Open questions:
  1. **The INFO record is not printed by `python -m nock`.** `product.md`
     rule 27 runs the server at `warning`, so an override logged at INFO, as
     the request says, reaches only a host that sets up logging (and the
     tests). Options:
     - **A (lead's default): INFO as asked, runner unchanged.** The spec says
       so; no baseline changes.
     - B: log the override at WARNING, so the default runner prints it. It
       departs from the request's word, but the operator sees every change.
     - C: run the server at `info`. A baseline change: the runner would then
       print every INFO record of `nock.*` and uvicorn's start lines too.
- Answers (the human, 2026-10-29): "Approve and pick A": the INFO record as
  asked, the runner unchanged, and the spec says so.

## Small follow-ups

Taken when a change touches them.

- `lobby/joining.md` (about 18.2 KB, 21 criteria after B-022) and
  `account/account.md` (about 19.5 KB, 18 criteria) are over the size
  guideline: trim them or split each, an architecture decision.
- `client/hud.md` rule 16 closes the menus, the reaction picker, a room sheet
  and the recap before the room-gone dialog shows, but AC-21 proves only the
  Salon sheet (B-021's review); an open room sheet or the recap in AC-21's
  second case would prove the native modals give way. The Android back
  gesture's reopen is tested only through `close()`.
- `content/grid-files.md` is over the size guideline (about 18.7 KB, 21
  criteria after B-015): the converter (rule 15, AC-20) could leave for its own
  short section or file, or the sample lists of AC-9 and AC-18 shrink.
- The converter does not refuse two former files with the same `number`; the
  index it writes is then refused at server start. Refusing it there, naming
  the second file, keeps its "writes nothing" promise
  (`content/grid-files.md` rule 15 does not ask for it).
- An index `file` may hold `:` (on Windows, `C:x.ipuz` resolves outside
  `grids/`, `a:b.ipuz` opens an NTFS stream), and `A.ipuz` and `a.ipuz` are
  one file on a case-insensitive disk (`content/grid-files.md` rule 2). The
  operator writes the index and CI runs on Linux: hardening only.
- A `grids/` still holding former `.json` files and no `catalogue.json`
  starts with an empty catalogue and no error (`content/grid-files.md` rule
  1): run `uv run python -m nock.ipuz_convert` on it once.
- `gameplay/board.md` is over the size guideline (about 20 KB, 22 criteria
  after B-012): split the grid's look (rules 1 to 4 and 20, AC-4 to AC-8,
  AC-21, AC-22) into its own domain file, an architecture decision.
- `_design/cells.md` « Hyphen edges » does not say how two hyphen edges meet:
  a cell with both marks (the code draws a 1 px rule-grey corner pixel), and,
  at 3 px thickness, an across edge ending where a down edge starts (the outer
  pixel can fall in the other edge's gap); neither is drawn in the cell sheet.
- The ipuz reader's gaps left by B-015 (`src/nock/ipuz.py`): `dotted` is
  refused, though ipuz draws dotted with dashed as dashed; `solution` must
  hold Nock's normalised letters (`É` or a lower-case letter is refused); a
  key written twice in one object keeps its last value silently; a file
  starting with a UTF-8 byte order mark is refused as "not valid JSON"; a
  clue's descriptive `explanation`, `tags` or `type` is refused.
- B-015 left: `’` in an enumeration is refused while rule 4 of
  `content/grids.md` makes it the same separator as `'` (`content/grid-files.md`
  rule 9 lists `'` only; say which); no test locks in that an enumeration
  with a leading zero (`"05"`, `"02-3"`) loads, as it does.
- Spec 025's vote banner test (`test_spec_025_ac07_vote_banner.py`) no longer
  measures a window (spec 047) and can leave `SERIAL_TEST_FILES`.
- Spec 045: no zoom test with the legend shown; the column layout with the legend
  over the grid is not drawn in the screens sheet.
- Spec 048 AC-13's no-animation rule is a text scan and cannot see an animation
  started at run time; a `document.getAnimations()` check, as spec 046 AC-9 does,
  would.
- Spec 035's language scan accepts any "X : Y" text through
  `{name} : {reaction}`; binding open placeholders to their values would close it.
- Spec 029, left for the human in PR #26: a history save that read the room
  before an account's erasure and writes after it keeps the nickname (very
  unlikely); the delete hook writes SQLite under the registry lock; two erased
  team-mates of one record show as one `--`; the room page asks its summary once
  and does not retry; `peek_room` re-reads the log of a room solved before spec
  029 at each call.
- Rules stated but untested (the code does them; a test would catch a
  regression): the catalogue asks once and refuses items that are not
  summaries; the force filter makes no new request; the grid page's loading
  line and its non-summary answer; after a chip, only that chip pressed
  (`content/library.md` rules 8, 10, 16 and AC-6).
- The brand's name « Accueil » does not contain its visible text « Nock »
  (WCAG 2.5.3, label in name): a voice-control user saying "Nock" misses it.
  The human chose « Accueil »; « Nock, accueil » would meet both.
- WebKit reaching the brand by Tab (`tabindex="0"`, hud AC-20) is proven only
  once CI runs WebKit after the merge.
- `client/shell.md` (about 16.4 KB, 20 criteria) and `admin/operations.md`
  (about 19.6 KB, 21 criteria after B-034, whose one criterion the human
  approved without a split) are past the size budget of `specs/_map.md`; the
  next criterion in either needs a split first (an architecture item). For
  shell, the B-010 spec-writer proposed `client/foundation.md` taking rules 13
  to 17 and their criteria.
- The room page's `closed` status can no longer be reached (a socket lost is
  `reconnecting` or `connecting`, `platform/realtime.md`), yet
  `room.status.closed` (« Connexion perdue. ») is still a required key of 040
  AC-22's test: drop the key and that test entry (`client/shell.md`). Likewise
  046 AC-23's test still checks that `my_rooms.loading`, `my_rooms.empty` and
  `account-link` are absent, and 043 AC-31's that 043's removed keys are:
  history no spec states; drop those entries once the numbered specs are
  archived.
- Untested client details: binary frames ignored by the room page; `t()`
  placeholders; a `{"seq": 6}` frame without type cannot be told from event 6
  in 040 AC-19's test (`client/shell.md` rules 2, 3 and 5).
- No test taps the reaction pill on a clue (`client/hud.md` rule 14 says a
  tap selects that clue; 043 AC-25 checks only where the pill is drawn).
- Untested account behaviour the code has: a link token arriving in the URL
  fragment while `/account` already shows signs in; another method on an
  account route answers 405 while accounts are on, and 404 while they are off
  for a method no route has; a failed purge is logged and the sweep goes on
  (`account/account.md`).
- Known flakes: 036 AC-8's join on the room of `NOCK_DATABASE` fails under
  load and passes alone; 046 AC-22's nickname error failed once on Firefox,
  never reproduced; 019 AC-4's legend after Bob leaves failed once in the
  full gate on Windows (B-015), passed alone; on Windows, `net::ERR_NO_BUFFER_SPACE` after several
  gates in a row (rerun alone).
- B-009's option B, once Docker is how Nock deploys: a domain
  `platform/deployment.md` and a CI job that builds the image and checks the
  running container (serves `/`, a room survives a restart, no `.env*` or
  `data/` inside, not root). Needs the human's approval of the CI actions.
- Rule grey `#9AA3B2` is 2.54:1 on white, under the 3:1 WCAG 1.4.11 asks of a
  control's boundary; kept by the human, `#8A93A3` (3.10:1) remains possible.
- B-028: `RoomState.players` and `Snapshot.players` hold `max_length=8` where
  `MAX_PLAYERS` is meant (`room.py:277`, `protocol.py:739`).
- B-028: `SmtpMailer._send` calls `quit()` inside `with connection:`, whose
  exit sends `QUIT` again (`mailer.py:93`); `smtplib` swallows the error.
- B-028: a chat text accepts control and bidirectional override characters
  (U+202E), which can show a message reversed; nicknames refuse them
  (`social/chat.md`, a rule to add).
- B-028: the SMTP send runs in the thread pool of every sync route, with a
  10-second timeout; a slow mail server and many addresses could fill its 40
  threads. Low while the per-address limits hold.
- `gameplay/hints.md` is over the size guideline (about 21 KB, 23 criteria
  after B-031): the spec-writer proposes moving the vote and its banner
  (rules 14 to 22, AC-13 to AC-20, with their pointers) to a new
  `gameplay/votes.md`, an architecture decision. `platform/realtime.md` is
  over too (about 19 KB, 20 criteria).
- `tests/test_spec_046_ac01_ac02_frames.py::test_ac1_the_second_child_of_the_column_is_the_card[chromium-1024x768]`
  failed once in the parallel pass (B-031's close, 2026-10-30): the card's
  background read transparent, as if its styles had not applied yet; alone,
  the file passes. If it fails again, it waits for the styles or goes in
  `SERIAL_TEST_FILES` (a tooling fix of the lead's).

## Grid engine ideas from ipuz

What the ipuz standard can describe and the grid engine does not use yet
(listed by the lead, 2026-10-26, at the human's request). Each becomes an item
through `/new-spec` when the human picks it. To keep the engine free of ipuz,
each adds a concept to Nock's own model first (`src/nock/grid.py`), and only
`nock.ipuz` maps the ipuz field onto it: another file format could fill the
same concept, and the rooms, the protocol and the browser never see ipuz.

- A mark of its own per kind of break: B-015 draws every break (hyphen,
  dot, space, apostrophe) as the same dashed edge and keeps its kind in the
  answer as written; a kind that should look different would reach the
  snapshot's marks then (B-015's option B).
- The length pattern in the clue bar: « (3-2-5) » after the clue text, from
  the letters and breaks the model already has (ipuz's `showenumerations` is
  the file's switch). B-012 left it out of scope.
- The title on the card and the grid page: B-013 records `title` without
  showing it (`intro` and `notes` are read and ignored). Showing it changes
  the summary (`content/library.md` rule 2), an interface change.
- One grid imported twice: B-013 records `uniqueid`; refusing two index
  entries whose files share one would stop the same grid entering twice
  (`content/grid-files.md`).

Not taken from ipuz: its `checksum` (the server needs the answers for check
and reveal), `references` and `continued` (rare in arrowwords), image clues
(the product serves no third-party content). Arrows stay Nock's own: ipuz has
none.

## Decisions waiting for the human

- Le Parisien baseline: confirm it from screenshots, if the comparison is still
  wanted.
- Hosting (Fly.io, Render or a VPS) and a domain, before the first public test.
  A cloud session drafts `docs/hosting.md` on the branch `docs/hosting-plan`.
- Tag `v1.1.0` on `main` (never tagged).
- The branch `feat/b-016-creator-rooms` (8 commits, last on 2026-10-28, not
  merged, no item in this file) changes several spec files that B-031 to
  B-036 touch, while B-022 "Creator rooms and host return" is done: drop it,
  or say what it still carries.

## Release checklist

Before the human tags a release on `main`:

1. Every item of the release is `done` and merged; none is `building`.
2. `main`'s last CI run is green in the three engines
   (`gh run list --branch main`).
3. The full gate passes locally in the three engines (`--browsers all`), each
   single failure rerun alone.
4. Release notes, one line per item, written from this file and approved by the
   human.
5. The human tags `vX.Y.Z` and pushes the tag; the done items then leave this
   file.

### B-027 The order of the overrides holder

- Status: done (the human approved the brief and picked A, 2026-10-29;
  no spec change; built and reviewed in two rounds, 2026-10-29)
- Waits for: nothing left (B-024 is merged and on this branch).
- Domains: none (no behaviour change: `src/nock/server.py` only)
- Architecture decision: no (private names of `server.py`)
- Criteria: none new; the tests of `admin/overrides.md` prove nothing changed
- Branch: feat/b-027-overrides-holder-order · PR: #65
- Problem: in `server.py`, `_RoomsHolder.settings_set()` answers None both for
  a registry given to the app and before any registry exists, which mean
  different things. It works today only because the lifespan calls
  `holder.get()` first (B-024 review round 2, a suggestion).
- In scope: make that order impossible to break by accident. Options:
  - A (the human's pick): `settings_set()` fails loudly when no registry exists
    yet, so None means only "a registry was given".
  - B: `get()` answers the registry and the set together, and
    `settings_set()` goes.
  - C: a comment at the call site only.
- Out of scope: any change to the routes, the answers or the page.
- Screens: none.
- Open questions: none beyond the option.
