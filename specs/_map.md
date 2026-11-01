# Map of the domain specs

Not a spec. The gate traces the domain specs and the numbered specs; it never
reads a file or folder whose name starts with `_`.

Nock's behaviour is described by domain specs: one file per domain, grouped in
areas (eight today), each saying what is true now. Every role reads this file first, then
only the files its task names, their `Depends on` files and the design file they
cite.

(Human decision, 2026-10-24: the 8-area map, the naming rules, the look in the
design files only, accessibility and performance as baselines in `product.md`,
operations as their own domain, and specs that state the current truth with no
history.)

The eight areas fit Nock as it is now; they are not a closed list. When a change
brings a coherent group of behaviour that no area holds, a new area or domain
file is added, and an area or file that grows apart may be split. Adding,
splitting or merging is an architecture decision: the human approves it, and the
table, the naming rules and the glossary follow in the same change.

## Areas

| Area | File | What it covers | Look | From the v1.1.0 specs |
| --- | --- | --- | --- | --- |
| account | `account/account.md` | sign-in, profile, the player's own data and its deletion | pages | 033; 029 AC-3, AC-6, AC-7 (server side); 038 AC-1, AC-2; 046 AC-3; 048 AC-3 to AC-5 |
| lobby | `lobby/rooms.md` | solo start, room creation and its limit per address, invitation, the room engine, the wrong-code throttle | room | 010, 011; 040 AC-7 |
| lobby | `lobby/host.md` | the host role: who holds it, how it passes, what it may do; the creator | room | 014 |
| lobby | `lobby/joining.md` | join by link, the account's one seat, room resume, « Mes salons » | pages | 012; 032 AC-3 to AC-7; 046 AC-11, AC-12, AC-15 to AC-17 |
| lobby | `lobby/lifetime.md` | room lifetime: the kinds of room and their lives, when a room expires, the sweep that deletes it, the five variables | | 032 AC-1, AC-2 |
| gameplay | `gameplay/board.md` | grid display, word selection, letter entry, navigation, in-app keyboard | cells, room | 006, 007, 008, 009, 042, 044 |
| gameplay | `gameplay/co-op.md` | shared letters, same-cell conflicts, pencil letters | cells, room | 015, 016, 020 |
| gameplay | `gameplay/rules.md` | completion, shared timer | room, overlays | 026, 027 |
| gameplay | `gameplay/hints.md` | check, reveal, the group vote on help | room, overlays | 023, 024, 025; 047 AC-1 to AC-5, AC-13, AC-14 |
| gameplay | `gameplay/results.md` | end of game, recap, history, shared recap page | overlays, pages | 028, 029; 046 AC-13; 047 AC-6 to AC-11, AC-13, AC-14; 048 AC-1, AC-2 |
| gameplay | `gameplay/modes.md` | race, teams (B-002, not written yet) | | 030, 031 (untested stubs) |
| social | `social/presence.md` | who is here and where, authorship, Auteurs mode | cells, room | 013 (but AC-7, AC-8), 019, 045 |
| social | `social/chat.md` | chat, reactions, clue flag, mute | room | 021, 022; 013 AC-7, AC-8; 047 AC-12, AC-14 |
| social | `social/catch-up.md` | what changed while a player was away | cells, room | 034 |
| content | `content/grids.md` | grid model, import checks, no third-party content | | 002, 003; 005 AC-4, AC-5 |
| content | `content/grid-files.md` | the index `grids/catalogue.json`, the `.ipuz` grid files, credits, withdrawal, the converter | | 004 AC-5, AC-7; 005 AC-1 to AC-3, AC-6, AC-7 |
| content | `content/library.md` | what players browse: list, filter, grid page | pages | 004 AC-1 to AC-4, AC-6, AC-7; 046 AC-2, AC-4 to AC-10, AC-14 |
| admin | `admin/operations.md` | logs, metrics, retention, the `/ops` page | pages | 038 AC-3 to AC-11; 048 AC-6 to AC-12 |
| admin | `admin/overrides.md` | the `/ops` overrides of the room lives and the sweep interval: effective value, settings routes, dry run, storage, the settings card | pages | |
| platform | `platform/realtime.md` | room events protocol, reconnection, fair play | room | 039, 017, 037; 040 AC-8 to AC-13 |
| platform | `platform/server.md` | durable state, undo, engine time, the rooms held in memory | | 018; 036 AC-12 |
| platform | `platform/serving.md` | serving the built client, the HTTP edge (body limit, security headers, caching), `main()` and the environment settings | | 040 AC-1 to AC-6, AC-27 to AC-29; 036 AC-10 to AC-12 |
| client | `client/shell.md` | client routing, connection states, text and translations, visual foundation, entry and not-found pages, loading, empty and error states | pages, foundation | 040 AC-14 to AC-26; 041; 046 AC-1, AC-18 to AC-23; 048 AC-13, AC-14 |
| client | `client/hud.md` | the room's layouts, top bar, menus, popover rules, sheets, clue bar, play area, the room-gone dialog | room, overlays | 043 AC-1 to AC-12, AC-21 to AC-25, AC-27 to AC-29, AC-31 |
| client | `client/room.md` | the room panel « Salon » (progress, chat and players tabs), what « Salon » carries while closed, the 3-second notes | room | 043 AC-5, AC-13 to AC-20, AC-26, AC-30 |

`product.md` takes 035 and 036 AC-1 to AC-9. A numbered spec named without
criteria goes whole to its row; a criterion may be cited by more than one domain
(043 AC-5 is cited by `hud` and `room`, 047 AC-13 by `hints` and `results`,
047 AC-14 by `hints`, `results` and `chat`), and each of them states the part
its own screens hold.

Every file of the table exists but `gameplay/modes.md`, which B-002 writes; until
then nothing of race or teams is built.

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
  grid, recap, room gone), `pages.md` (catalogue, entry and not-found pages,
  plain pages, loading, empty and error states). The drawings are in
  `docs/design/`.
- `_template.md`: the format of a domain spec.
- `_archive/v1.1.0/`: the numbered specs once their domains are written.
- `backlog/`, at the repository root: the work queue, kept with the Backlog.md
  CLI (milestones, tasks and their status, drafts, the release checklist).

## How domain specs work

### Files and names

- A domain spec is `specs/<area>/<file>.md` (or `specs/product.md`). Its front
  matter holds `area`, `file` (the file name without `.md`) and `status`.
- File names are unique across areas. `spec` is not a file name, and no name
  written with `_` for `-` followed by `_` may begin another (`co` and `co-op`
  could not both exist), so a test file always names one domain.

### Status

- `draft`: being written or changed, not approved yet.
- `approved`: the spec-checker approved the file or its last change, inside a
  milestone the human bet on; the lead writes the status line on its APPROVED.
  Criteria without a test are reported as pending, not failed: the change is
  not built yet.
- `done`: built. Every criterion is proven by a test, or the gate fails.
- A change to a `done` file makes it `draft` again until the spec-checker
  approves it.

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

- `002-...` to `048-...`, in `specs/_archive/v1.1.0/`, are the build record of
  v1.1.0 and are never edited again.
- The gate fails when a criterion of an archived spec that has a test is cited by
  no domain spec: no tested behaviour may lose its owner. An archived criterion
  with no test left is retired.

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
- An area is a lowercase singular noun: today `account`, `lobby`, `gameplay`,
  `social`, `content`, `admin`, `platform`, `client`.
- A domain file is a kebab-case noun: `co-op.md`, `catch-up.md`.
- A criterion is named by its file and number: `grids AC-3`.

## Glossary

| Spec term | UI (French) | Code |
| --- | --- | --- |
| library | « Grilles » (the catalogue page) | `catalogue.py`, `catalogue-page` |
| grid file | (not shown) | `grids/*.ipuz`, `GridFile` |
| index | (not shown) | `grids/catalogue.json`, `IndexEntry`, `CatalogueEntry` |
| room | « salon » | `room.py`, `/r/<code>` |
| live room | (not shown: a room held in memory with its task, from a socket's opening until its task ends with no socket open) | `RoomRegistry.live_codes` |
| member | (a player or a past player of a room) | `PlayerRecord`, `PastPlayer` |
| connection | (one socket of a player; "session" is the sign-in cookie) | `RoomConnection`, `nock_session` |
| invited player | the nickname form under « Salon <code> » | `join` without token |
| account player, anonymous player | (a member linked to an account, to none) | `PlayerRecord.account_id` |
| host, stand-in host | « hôte » (a host who is not the creator's player) | `is_host`, `host_changed` |
| hand-over delay | (not shown) | `host_handover_seconds` (60 s) |
| creator, creator room, anonymous room | (not shown: the account whose session sent `POST /api/rooms`; a room with one, without) | `creator_account_id` |
| creator's player | (not shown: the member linked to the creator) | `creator_account_id` = `account_id` |
| resume list | « Mes salons » | `my_rooms` |
| edit, last edit time | (not shown: a letter change or a cell lock; the latest one's time) | `is_edit`, `last_edit_at` |
| solve time | (not shown: the time of the room's `grid_solved`) | `solved_at` |
| room life | (not shown: how long a room lasts after its starting point, one per kind) | `RoomConfig.*_room_hours`, `NOCK_*_ROOM_HOURS` |
| expired room | « Ce salon n'existe pas. » (more than its room life past its starting point; at exactly its room life it is open) | the expiry function (`lobby/lifetime.md`) |
| sweep | (not shown: the deletion of the expired rooms at start, then at each interval) | `expire_rooms`, `NOCK_EXPIRY_SWEEP_MINUTES` |
| shortest room life | (not shown: the least of the four effective room lives) | `offered_days` (the `/ops` periods it allows) |
| default value | « par défaut » (a source on « Durées de vie des salons ») | `RoomConfig` field defaults, `DEFAULT_ROOM_LIFE_HOURS`, `DEFAULT_SWEEP_MINUTES` |
| environment value | « variable » (the variable's value, when set) | `room_config_from_env`, `NOCK_*_ROOM_HOURS`, `NOCK_EXPIRY_SWEEP_MINUTES` |
| override | « modifiée » (a value saved from `/ops`, stored in the database, in memory when `NOCK_DATABASE` is unset) | table `overrides`, `PUT /api/ops/settings` |
| effective value | the value each row of « Durées de vie des salons » shows (the override, else the environment value, else the default; every rule reads it) | `RoomRegistry.config` |
| dry run | « Cela effacera N salons maintenant. » (how many rooms a proposed value would delete now; nothing saved) | `POST /api/ops/settings/dry-run` |
| hud | the top bar: « Aide », « Salon », « Menu » | `RoomTopBar.svelte` |
| room panel, notes | « Salon » (the panel beside or over the grid), the 3-second notes | `Salon.svelte`, `RoomNote.svelte` |
| hints | « Aide »: « Vérifier », « Révéler » | `check`, `reveal` |
| hint vote | « … propose de vérifier la grille » | `vote` |
| authorship | « Auteurs » | `authors` |
| results | « Bilan de la partie », « Voir le bilan » | `recap.py`, `recap` |
| history | « Grilles terminées » | `history` |
| operations | « Exploitation » | `operations.py`, `/ops` |
| force | « Force » (difficulty 1 to 4) | `force` |
