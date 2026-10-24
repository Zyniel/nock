# Map of the domain specs

Not a spec: the quality gate reads only the numbered files at the top of `specs/`.

From the v1.1.0 baseline, Nock's behaviour is described by **domain specs**, one
file per domain, grouped in areas. A domain spec says what is true now, with no
history. The numbered specs (`002-...` to `048-...`) are the build record: they
stay the gate's traceability source until every domain is written, then move to
`specs/_archive/v1.1.0/`.

Read this file, then only the domain files your task names, their `Depends on`
files, and the design file they cite. Do not read the numbered specs unless a
domain spec is still `pending` below.

(Human decision, 2026-10-24: the 8-area map and the naming rules below, the look
in the design files only, accessibility and performance as baselines in
`_product.md`, operations as their own domain.)

## Areas

| Area | File | What it covers | From specs | State |
| --- | --- | --- | --- | --- |
| account | `account/account.md` | sign-in, profile, the player's own data and its deletion | 033, 048 (account page), 038 (player data) | pending |
| lobby | `lobby/rooms.md` | solo start, room creation, invitation, host controls | 010, 011, 014 | pending |
| lobby | `lobby/joining.md` | guest join, room resume, « Mes salons » | 012, 032 | pending |
| gameplay | `gameplay/board.md` | grid display, word selection, letter entry, navigation, in-app keyboard | 006, 007, 008, 009, 042, 044 | pending |
| gameplay | `gameplay/co-op.md` | shared letters, same-cell conflicts, pencil letters | 015, 016, 020 | pending |
| gameplay | `gameplay/rules.md` | completion, shared timer | 026, 027 | pending |
| gameplay | `gameplay/hints.md` | check, reveal, the group vote on help | 023, 024, 025 | pending |
| gameplay | `gameplay/results.md` | end of game, recap, history, shared recap page | 028, 029, 047, 048 (shared recap) | pending |
| gameplay | `gameplay/modes.md` | race, teams (Phase 8) | 030, 031 | pending |
| social | `social/presence.md` | who is here and where, authorship, Auteurs mode | 013, 019, 045 | pending |
| social | `social/chat.md` | chat, reactions, clue flag, mute | 021, 022 | pending |
| social | `social/catch-up.md` | what changed while a player was away | 034 | pending |
| content | `content/grids.md` | grid model, grid files, import checks, credits, withdrawal | 002, 003, 005, 004 (grid files) | draft |
| content | `content/library.md` | what players browse: list, filter, grid page | 004, 046 | pending |
| admin | `admin/operations.md` | logs, metrics, retention, the `/ops` page | 038, 048 (`/ops`) | pending |
| platform | `platform/realtime.md` | room events protocol, reconnection, fair play | 039, 017, 037 | pending |
| platform | `platform/server.md` | durable state, serving, environment settings | 018, 040 (server side) | pending |
| client | `client/shell.md` | client routing, loading, empty and error states | 040 (client side), 048 (state lines) | pending |
| client | `client/hud.md` | the room's top bar, menus, sheets and popover rules | 043 | pending |

Shared files, read as each domain spec says:

- `_product.md` (pending): core flows, stable routes, the accessibility and
  performance baselines (from 035 and 036), supported browsers and windows.
- `_reference.md`: the FX-01 reference grid and FX-02.
- `_architecture.md`: stack and modeling rules.
- `settings.md` (pending): every setting, its scope (player, host, server) and the
  domain file that owns it.
- `_design.md` and `docs/design/`: the look. It is split by area into
  `design/*.md` later; a domain spec never describes a look, it cites the design.

## Naming rules

- Specs are written in English with the usual terms of online games; the UI is in
  French. The glossary below maps them.
- An area is a lowercase singular noun: `account`, `lobby`, `gameplay`, `social`,
  `content`, `admin`, `platform`, `client`.
- A domain file is a kebab-case noun: `co-op.md`, `catch-up.md`.
- A criterion is named by its file and number: `content/grids AC-3`. Each
  criterion lists the numbered criteria it carries over, for example
  `(← 003 AC-1)`, so its tests stay linked while the numbered specs remain the
  gate's source.
- The domain format is `_domain_template.md`.

## Glossary

| Spec term | UI (French) | Code |
| --- | --- | --- |
| library | « Grilles » (the catalogue page) | `catalogue.py`, `catalogue-page` |
| grid file | (not shown) | `grids/*.json`, `CatalogueEntry` |
| room | « salon » | `room.py`, `/r/<code>` |
| lobby: resume list | « Mes salons » | `my_rooms` |
| hud | the top bar: « Aide », « Salon », « Menu » | `RoomTopBar.svelte` |
| hints | « Aide »: « Vérifier », « Révéler » | `check`, `reveal` |
| hint vote | « … propose de vérifier la grille » | `vote` |
| authorship | « Auteurs » | `authors` |
| results | « Bilan de la partie », « Voir le bilan » | `recap.py`, `recap` |
| history | « Grilles terminées » | `history` |
| operations | « Exploitation » | `operations.py`, `/ops` |
| force | « Force » (difficulty 1 to 4) | `force` |
