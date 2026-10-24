# Map of the domain specs

Not a spec. The gate traces the domain specs and the numbered specs; it never
reads a file or folder whose name starts with `_`.

Nock's behaviour is described by domain specs: one file per domain, grouped in
eight areas, each saying what is true now. Every role reads this file first, then
only the files its task names, their `Depends on` files and the design file they
cite.

(Human decision, 2026-10-24: the 8-area map, the naming rules, the look in the
design files only, accessibility and performance as baselines in `product.md`,
operations as their own domain, and specs that state the current truth with no
history.)

## Areas

| Area | File | What it covers | Look | From the v1.1.0 specs |
| --- | --- | --- | --- | --- |
| account | `account/account.md` | sign-in, profile, the player's own data and its deletion | pages | 033, 048 (account page), 038 (player data) |
| lobby | `lobby/rooms.md` | solo start, room creation, invitation, host controls | room | 010, 011, 014 |
| lobby | `lobby/joining.md` | guest join, room resume, « Mes salons » | pages | 012, 032 |
| gameplay | `gameplay/board.md` | grid display, word selection, letter entry, navigation, in-app keyboard | cells, room | 006, 007, 008, 009, 042, 044 |
| gameplay | `gameplay/co-op.md` | shared letters, same-cell conflicts, pencil letters | cells | 015, 016, 020 |
| gameplay | `gameplay/rules.md` | completion, shared timer | room, overlays | 026, 027 |
| gameplay | `gameplay/hints.md` | check, reveal, the group vote on help | room, overlays | 023, 024, 025 |
| gameplay | `gameplay/results.md` | end of game, recap, history, shared recap page | overlays, pages | 028, 029, 047, 048 (shared recap) |
| gameplay | `gameplay/modes.md` | race, teams | | 030, 031 |
| social | `social/presence.md` | who is here and where, authorship, Auteurs mode | cells, room | 013, 019, 045 |
| social | `social/chat.md` | chat, reactions, clue flag, mute | room | 021, 022 |
| social | `social/catch-up.md` | what changed while a player was away | cells, room | 034 |
| content | `content/grids.md` | grid model, grid files, import checks, credits, withdrawal | | 002, 003, 005, 004 (grid files) |
| content | `content/library.md` | what players browse: list, filter, grid page | pages | 004, 046 |
| admin | `admin/operations.md` | logs, metrics, retention, the `/ops` page | pages | 038, 048 (`/ops`) |
| platform | `platform/realtime.md` | room events protocol, reconnection, fair play | room | 039, 017, 037 |
| platform | `platform/server.md` | durable state, serving, environment settings | | 018, 040 (server side) |
| client | `client/shell.md` | client routing, loading, empty and error states | pages, foundation | 040 (client side), 048 (state lines) |
| client | `client/hud.md` | the room's top bar, menus, sheets and popover rules | room | 043 |

A file of the table that does not exist yet is pending: until it is written, the
numbered specs it lists are the truth for that domain.

## Shared files

- `product.md`: what Nock is, its core flows and stable routes, and the baselines
  every domain keeps (accessibility and performance, from 035 and 036; supported
  browsers and windows). It has criteria, so the gate traces it as the domain
  `product`.
- `_reference.md`: the FX-01 and FX-02 grids used in examples.
- `_architecture.md`: stack and modeling rules.
- `_settings.md`: every setting, its scope (player, host, server) and the domain
  file that owns it.
- `_design/`: the look, which a domain spec cites and never repeats:
  `foundation.md` (authority rules, colour tokens, player colours, type, icons,
  components, focus, how conformance is checked), `cells.md` (grid cells,
  Auteurs mode), `room.md` (the room page: layouts, top bar, Aide, Menu, Salon,
  notes, reactions, connection lost, sheets, layers), `overlays.md` (vote, end of
  grid, recap), `pages.md` (catalogue, entry and not-found pages, plain pages,
  loading, empty and error states). Until they exist, `_design.md` is the look.
  The drawings are in `docs/design/`.
- `_template.md`: the format of a domain spec.
- `_archive/v1.1.0/`: the numbered specs once their domains are written.
- `Backlog.md`, at the repository root: the work queue (briefs, the status of
  each change, the release checklist).

## How domain specs work

### Files and names

- A domain spec is `specs/<area>/<file>.md` (or `specs/product.md`). Its front
  matter holds `area`, `file` (the file name without `.md`) and `status`.
- File names are unique across areas. `spec` is not a file name, and no name
  written with `_` for `-` followed by `_` may begin another (`co` and `co-op`
  could not both exist), so a test file always names one domain.

### Status

- `draft`: being written or changed, not approved yet.
- `approved`: the human approved the file or its last change. Only the human
  approves; the lead writes the status line on their word. Criteria without a
  test are reported as pending, not failed: the change is not built yet.
- `done`: built. Every criterion is proven by a test, or the gate fails.
- A change to a `done` file makes it `draft` again until the human approves it.

### Criteria and their tests

- A criterion is a bullet `- **AC-n** ...`, numbered per file. A number is never
  reused: a criterion that goes away is deleted with its tests, and the next new
  one takes the next free number.
- A criterion is proven by a test named `test_acN_...` in `tests/test_<name>_*.py`
  or `tests/test_<name>.py`, where `<name>` is the `file` value with `-` written
  `_` (`co-op` gives `tests/test_co_op_pencil.py`). Shared helpers of a domain's
  tests go in `tests/<name>_harness.py`.
- Or by a pointer `(← NNN AC-n, ...)`: the tests of those numbered criteria in
  `tests/test_spec_NNN_*.py` prove it. A pointer says which tests prove the
  criterion, not that the numbered text still reads the same: when the behaviour
  changes, those tests are edited in place and the numbered spec is not.
- The gate fails on a test that points to a criterion that does not exist, and
  on a pointer to a numbered criterion that does not exist or that no test
  proves.
- `scripts/gate.py --specs grids` runs the browser tests of `tests/test_grids_*`
  and of every numbered spec that `grids` cites; numbers still work
  (`--specs 027`).

### The numbered specs of v1.1.0

- `002-...` to `048-...` are the build record of v1.1.0 and are never edited
  again. While one sits in `specs/`, the gate checks it as before.
- Once every criterion of it that has a test is cited by a domain spec, it moves
  to `specs/_archive/v1.1.0/`. From then the gate fails when a criterion of an
  archived spec that has a test is cited by no domain spec: no tested behaviour
  may lose its owner. An archived criterion with no test left is retired.

### What a spec holds

- About 15 KB and 20 criteria per file. Over that, split the domain and update
  the table above.
- Never the look (cite the design file and section), never test mechanics
  (window sizes, test ids, sample lists, fixtures: the tests hold them), never
  copies of code (name the module), never history (the commit message holds the
  reason; a `<file>.notes.md` next to the spec keeps one only when a later change
  will need it).
- "New interface" only while a change is being built.

## Naming rules

- Specs are written in English with the usual terms of online games; the UI is in
  French. The glossary below maps them.
- An area is a lowercase singular noun: `account`, `lobby`, `gameplay`, `social`,
  `content`, `admin`, `platform`, `client`.
- A domain file is a kebab-case noun: `co-op.md`, `catch-up.md`.
- A criterion is named by its file and number: `grids AC-3`.

## Glossary

| Spec term | UI (French) | Code |
| --- | --- | --- |
| library | « Grilles » (the catalogue page) | `catalogue.py`, `catalogue-page` |
| grid file | (not shown) | `grids/*.json`, `CatalogueEntry` |
| room | « salon » | `room.py`, `/r/<code>` |
| resume list | « Mes salons » | `my_rooms` |
| hud | the top bar: « Aide », « Salon », « Menu » | `RoomTopBar.svelte` |
| hints | « Aide »: « Vérifier », « Révéler » | `check`, `reveal` |
| hint vote | « … propose de vérifier la grille » | `vote` |
| authorship | « Auteurs » | `authors` |
| results | « Bilan de la partie », « Voir le bilan » | `recap.py`, `recap` |
| history | « Grilles terminées » | `history` |
| operations | « Exploitation » | `operations.py`, `/ops` |
| force | « Force » (difficulty 1 to 4) | `force` |
