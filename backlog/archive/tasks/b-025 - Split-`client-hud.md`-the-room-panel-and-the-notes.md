---
id: B-025
title: 'Split `client/hud.md`: the room panel and the notes'
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:hud
  - domain:room
  - domain:chat
  - domain:catch-up
  - domain:presence
  - domain:hints
  - domain:server
  - domain:shell
dependencies: []
ordinal: 35000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
<!-- SECTION:DESCRIPTION:END -->
