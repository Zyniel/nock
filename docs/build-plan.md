# Nock build plan

Every command needed to build Nock, in order. Tick the boxes as you go.

Who types what:

- **Shell** blocks run in a terminal at the project root.
- **Prompt** blocks are typed into Claude Code (this app or `claude` in the
  project folder). `/feature` and `/new-spec` only start when you type them.

## How one spec goes through

Every spec below follows the same four steps. Only step 1 changes per phase.

1. **Refine.** The phase gives a prompt that has the spec-writer write the public
   interface and settles the open questions. Read the updated specs.
2. **Approve.** Prompt: `Specs NNN, NNN are approved.`
3. **Build.** Start from an up-to-date `main`, then run the feature:

   ```bash
   git switch main
   ```

   ```bash
   git pull
   ```

   ```
   /feature specs/NNN-name.md
   ```

   This creates `feat/NNN-name`, runs test-writer, implementer and reviewer, and
   makes one commit per phase.
4. **Publish.** Push the branch and open the pull request, then merge it once CI
   is green.

   ```bash
   git push -u origin feat/NNN-name
   ```

   ```bash
   gh pr create --fill
   ```

Build specs one at a time, in the order given. A spec may rely on the code of the
ones before it.

## Phase 0 - Setup (once)

- [ ] Push the first commit:

  ```bash
  git push -u origin main
  ```

- [ ] In the GitHub repository settings, protect `main` and require the
  "Quality gate" checks.
- [ ] Add Pydantic, needed from spec 002:

  ```bash
  uv add pydantic
  ```

  ```bash
  git commit -am "build: add pydantic"
  ```

## Phase 1 - Grid model (pure Python)

- [ ] Refine. Prompt:

  ```
  Have the spec-writer update specs 002 and 003 with these answers.
  002: solution letters live on each clue, as proposed; the one-cell-per-position
  rule is a model validator in 002; pydantic is now installed.
  003: import stops at the first problem, and the message names the cell, run or
  words.
  Remove the answered questions.
  ```

- [ ] Approve 002 and 003, then build in this order:
  - [ ] `/feature specs/002-grid-schema.md`
  - [ ] Before pushing the 002 branch, archive the starter example. It could
    not go earlier: its test was the only one, and pytest fails when it finds
    none. Prompt:

    ```
    On this branch, move specs/001-slugify.md, tests/test_spec_001_slugify.py
    and src/nock/text.py into specs/_archive/001-slugify/ with git mv, update
    the README section that mentions them, run the gate and commit as
    "chore: archive the starter example".
    ```

  - [ ] `/feature specs/003-grid-import-validation.md`

## Phase 2 - Server foundation

- [ ] Add the server dependencies:

  ```bash
  uv add fastapi "uvicorn[standard]"
  ```

  ```bash
  uv add --dev httpx2
  ```

  ```bash
  git commit -am "build: add fastapi, uvicorn and httpx2"
  ```

- [ ] Write the room events contract. Prompt:

  ```
  /new-spec Room events protocol. The list of every message exchanged between the
  browser and the server over the room WebSocket, as Pydantic models in
  src/nock/protocol.py, following specs/_architecture.md. Two discriminated
  unions on a "type" field: ClientMessage (join, select cell, edit letter, erase,
  pencil edit, confirm pencil, check, reveal, vote, flag, chat, reaction, undo,
  host actions: remove player, lock room, change settings) and ServerMessage
  (snapshot with sequence number, letter changed, cell locked, player joined, left,
  state changed, selection moved, check result, reveal result, vote opened and
  closed, flag changed, chat message, reaction, settings changed, grid solved,
  grid full but wrong, error). Every server event that changes the room carries a
  sequence number. A snapshot never contains an answer letter the room has not
  earned. Acceptance criteria: each message round-trips through JSON; an unknown
  type or a malformed field is rejected with a validation error; an edit letter
  must be one character A to Z; the snapshot model has no field that can hold
  solution letters for unrevealed cells. Out of scope: the server logic behind
  each message, which belongs to specs 011 to 038.
  ```

- [ ] Answer its open questions, approve it, then build it:
  - [ ] `/feature specs/039-room-events-protocol.md` (use the number the
    spec-writer gave it)

## Phase 3 - Client toolchain and shell

Tooling changes: you run the shell part; the prompt asks Claude to change the
gate, CI and the role rules, which you have approved by sending it.

- [ ] Install Node.js LTS (once per machine):

  ```bash
  winget install --id OpenJS.NodeJS.LTS -e
  ```

- [ ] Create the Svelte app:

  ```bash
  npm create vite@latest web -- --template svelte-ts
  ```

  ```bash
  npm --prefix web install
  ```

- [ ] Add browser testing:

  ```bash
  uv add --dev pytest-playwright
  ```

  ```bash
  uv run playwright install chromium
  ```

- [ ] Wire it in. Prompt:

  ```
  Tooling change, approved: (1) scripts/gate.py runs, in web/, "npm ci",
  "npx svelte-check" and "npm run build" before pytest in the full stage;
  (2) .github/workflows/ci.yml installs Node LTS and runs
  "uv run playwright install --with-deps chromium" before the gate;
  (3) scripts/hooks/guard_paths.py and the role table in CLAUDE.md let the
  implementer write web/; (4) .gitignore ignores web/node_modules and web/dist.
  Run the gate, then commit as "build: add the web client toolchain".
  ```

- [ ] Write the client shell. Prompt:

  ```
  /new-spec Web client shell. FastAPI (src/nock/server.py) serves the built
  Svelte app from web/dist and exposes the room WebSocket of the room events
  protocol spec. The app has two routes: the catalogue at "/" and a room at
  "/r/<room code>". It opens the WebSocket on the room route, keeps the latest
  snapshot and applies later events in sequence order. Every user-facing string
  comes from web/src/i18n/fr.json; French is the only language for now.
  Acceptance criteria: GET / returns the app; GET /r/ABC123 returns the app;
  an unknown API path returns 404; a browser test opens /r/<code> of a room on
  FX-01 and sees the room page receive a snapshot; no string literal shown to the
  user is outside fr.json. Out of scope: grid rendering (spec 006) and room
  rules (specs 011 onwards).
  ```

- [ ] Answer its open questions, approve it, then build it:
  - [ ] `/feature specs/040-web-client-shell.md`

## Phase 4 - MVP: catalogue, solo play, rooms, sync

- [ ] Refine. Prompt:

  ```
  Have the spec-writer write the public interface of specs 004, 006, 007, 008,
  009, 010, 011, 012, 013, 014, 015, 016, 017, 018, 037 following
  specs/_architecture.md and the room events protocol spec, and say for each
  criterion whether it is a Python test or a pytest-playwright browser test.
  Answers to their open questions:
  - Numeric thresholds: keep the backlog defaults.
  - 004: the grid source decision does not block the code; build and test with
    FX-01 and test fixtures. The source is decided before launch.
  - 006: FX-02 is a full-size original grid (13 by 17) stored as
    tests/fixtures/fx02.json and valid for import_grid; the test-writer creates it.
  - 012: a nickname allows letters (accents included), digits, spaces, hyphens,
    apostrophes and underscores, trimmed, 2 to 20 characters after trimming.
  - 018: keep undo (AC-3) in this spec.
  Remove the answered questions and list any new ones.
  ```

- [ ] Approve them, then build in this order (solo play is a room of one, so rooms
  come before instant solo start):
  - [ ] `/feature specs/004-grid-catalogue.md`
  - [ ] `/feature specs/006-grid-rendering.md`
  - [ ] `/feature specs/007-word-selection.md`
  - [ ] `/feature specs/009-keyboard-navigation.md`
  - [ ] `/feature specs/011-room-creation.md`
  - [ ] `/feature specs/012-guest-join.md`
  - [ ] `/feature specs/015-shared-letters.md`
  - [ ] `/feature specs/016-same-cell-conflicts.md`
  - [ ] `/feature specs/008-letter-entry.md` (needs the cell lock of 016)
  - [ ] `/feature specs/010-instant-solo-start.md`
  - [ ] `/feature specs/037-integrity.md` (server-side edit checks, early)
  - [ ] `/feature specs/018-durable-room-state.md`
  - [ ] `/feature specs/017-reconnection.md`
  - [ ] `/feature specs/013-presence.md`
  - [ ] `/feature specs/014-host-controls.md`

## Phase 5 - MVP: help, completion, quality bar

- [ ] Refine. Prompt:

  ```
  Have the spec-writer write the public interface of specs 005, 023, 026, 035,
  036 following specs/_architecture.md, with the test type of each criterion.
  Answers:
  - 005: the grid source decision does not block the code. AC-2 is tested by a
    test that fails when a module under src/ imports an HTTP client (httpx, httpx2,
    requests, urllib.request, aiohttp) or opens an outgoing connection.
  - 036: FX-02 is tests/fixtures/fx02.json. "Mid-range phone over 4G" is a
    Playwright run with 4x CPU throttling and a 4G network profile (9 Mbit/s
    down, 1.5 up, 170 ms latency); these tests run inside the normal gate.
  - Numeric thresholds: keep the backlog defaults.
  Remove the answered questions and list any new ones.
  ```

- [ ] Approve them, then build:
  - [ ] `/feature specs/023-check.md`
  - [ ] `/feature specs/026-completion-detection.md`
  - [ ] `/feature specs/005-licensed-content.md` (AC-3 needs rooms)
  - [ ] `/feature specs/035-accessibility.md`
  - [ ] `/feature specs/036-performance.md`

**MVP done:** a group can open a link, fill one grid together and see it solved.
Tag it:

```bash
git tag v0.1.0
```

```bash
git push origin v0.1.0
```

## Phase 6 - V1

- [ ] Refine. Prompt:

  ```
  Have the spec-writer write the public interface of specs 019, 020, 021, 022,
  024, 025, 027, 028, 029, 032, 033, 034, 038 following specs/_architecture.md,
  with the test type of each criterion. Answers:
  - 025: a word check needs no vote; only a reveal and a grid check, as written.
  - 033: send the sign-in link with the standard library (smtplib) and SMTP
    settings from environment variables; no new dependency.
  - 038: the dashboard is an operator-only page served by the app from the room
    log; no new dependency.
  - Numeric thresholds: keep the backlog defaults.
  Remove the answered questions and list any new ones.
  ```

- [x] Approve them, then build (all merged by 2026-10-22, PRs #7 to #26):
  - [x] `/feature specs/024-reveal.md`
  - [x] `/feature specs/025-help-mode-vote.md`
  - [x] `/feature specs/019-authorship-view.md`
  - [x] `/feature specs/020-pencil-letters.md`
  - [x] `/feature specs/021-clue-flag.md`
  - [x] `/feature specs/022-chat-reactions.md`
  - [x] `/feature specs/027-shared-timer.md`
  - [x] `/feature specs/028-end-of-game-recap.md` (needs authorship, 019)
  - [x] `/feature specs/032-room-resume.md`
  - [x] `/feature specs/038-privacy-operations.md` (needs room expiry, 032)
  - [x] `/feature specs/034-catch-up.md`
  - [x] `/feature specs/033-optional-account.md`
  - [x] `/feature specs/029-game-history.md` (history across devices needs 033)

```bash
git tag v1.0.0
```

```bash
git push origin v1.0.0
```

## Phase 7 - Visual design

Decided by the human on 2026-10-22: the whole client is rebuilt on the design
system before any extra mode ("a new phase BEFORE phase 7 and any extra mode").
The design system is `specs/_design.md` (the reference), drawn in
`docs/design/cell-sheet.html` (grid cells) and `docs/design/screens-sheet.html`
(every screen, built by `docs/design/screens_sheet/build.py`). Today's screens
work but use browser defaults; this phase changes their look and layout, not the
game's rules or its protocol.

Every spec of this phase is a set of screens that one pull request can carry
(spec 043 is the exception: two, one per work package). Each one leaves the app
working and every test passing, and builds on the ones before it. A spec also
refines the older specs whose tests check the look it changes, with dated notes,
so their tests change in the same pull request.

| Order | Spec | Screens | Status (2026-10-23) |
| --- | --- | --- | --- |
| 1 | 041 Visual foundation | tokens, player colours, fonts, icons, buttons, focus ring, menus, badge, note; today's screens take the colours, no layout change | done (#32) |
| 2 | 042 Grid cells | every cell: letters, marks, players' corners, clues, arrows, flag, the « Accessibilité » and « Mots des autres » switches | done (#34) |
| 3 | 043 Room layout | top bar, Aide and Menu, Salon (column or sheet), Joueurs, clue bar, notes, completion band; two pull requests (WP-1 the frame, WP-2 the feedback) | done (#35, #36) |
| 4 | 044 Keyboard | the in-app keyboard, ✎, ⇄, « Clavier » | done (#38) |
| 5 | 045 Auteurs mode | the authorship view of the grid, replacing spec 019's band | done |
| 6 | 046 Catalogue and entry pages | the catalogue and its sections (« Mes salons », the history), the nickname form, joining, a room not found or expired, the opening room | approved |
| 7 | 047 Room overlays | the help-mode vote, the end of the game, the recap dialog | approved |
| 8 | 048 Plain pages and states | the account page and deletion, the shared recap page, the operator page, the loading, empty and error states | approved |

- [x] Draft and approve: specs 044 to 048 are drafted from `_design.md` and the
  screens sheet; the human approves each (only the human sets `approved`).
- [x] Merge the design specs: one pull request of `specs/` and `docs/design/`
  only (branch `design-specs`), so every build starts from the approved text.
  Then the tooling rule that keeps the visual documentation current (PR #30).
- [ ] Build, in the order of the table, one pull request each:
  - [x] `/feature specs/041-visual-foundation.md`
  - [x] `/feature specs/042-grid-cells.md`
  - [x] `/feature specs/043-room-layout.md` (WP-1, then WP-2)
  - [x] `/feature specs/044-keyboard.md`
  - [x] `/feature specs/045-auteurs-mode.md`
  - [ ] `/feature specs/046-catalogue-and-entry-pages.md`
  - [ ] `/feature specs/047-room-overlays.md`
  - [ ] `/feature specs/048-plain-pages-and-states.md`

```bash
git tag v1.1.0
```

```bash
git push origin v1.1.0
```

## Phase 8 - Later: competitive modes

Decided by the human on 2026-10-22: E8 is wanted, and waits until the visual
design (Phase 7) is built. Specs 030 and 031 are 45-line stubs approved before
their interface existed: the spec-writer writes them in full first.

- [ ] Refine. Prompt:

  ```
  Have the spec-writer write the public interface of specs 030 and 031 following
  specs/_architecture.md. Answers: E8 is wanted. 031: teams differ in size by
  at most one player and no team is empty; the host cannot start with fewer
  than 2 players.
  ```

- [ ] Approve them, then build:
  - [ ] `/feature specs/030-race-mode.md`
  - [ ] `/feature specs/031-team-mode.md`

## Decisions still yours

The prompts above carry my recommended answers. Change them before sending if
you disagree. These are not covered by any prompt:

- **Grid source** for real content (commission, licence, or generate and
  review). Needed before launch, not before coding.
- **Le Parisien baseline:** confirm it from screenshots if you still want the
  comparison.
- **Hosting** (Fly.io, Render or a VPS) and a domain, before the first public
  test.
- **Archive:** `specs/_archive/` holds what is no longer used: the original
  backlog (`complete.md`) and, from phase 1, the starter example. The gate,
  pytest and pyrefly ignore it.
