---
id: B-037
title: Lean snapshots
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:server
  - domain:host
  - domain:lifetime
  - domain:chat
  - domain:catch-up
dependencies: []
ordinal: 47000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Status: done
- Priority: ninth (the disk grows with play, slowly)
- Waits for: nothing (B-035 is merged)
- Domains: platform/server (snapshots), lobby/host (the removed tokens),
  lobby/lifetime (migration 4); social/chat if the chat is bounded;
  social/catch-up keeps its rules (a catch-up replays from the first
  snapshot)
- Architecture decision: yes (stored data): options from the Plan agent on
  Fable
- Criteria: server AC-27, AC-28 (new), host AC-17 (new), AC-9 (changed),
  lifetime AC-18 (new), AC-13, AC-17 (changed), chat AC-21 (new),
  operations AC-23 (changed)
- Branch: feat/b-037-lean-snapshots · PR: #79
- Problem: a snapshot stores the whole room (grid, every cell, the chat, past
  players, removed tokens) at seq 0, every 100 events, at each task end and at
  shutdown, and none is ever deleted (B-028 M6). Measured on FX-02: 30 KiB
  fresh (grid 12, cells 18), 35 KiB mid-game, 77 KiB in a long game. A
  typical game writes 5 to 8 snapshots (about 75 % of the room's bytes), a
  long one 60 to 80 (3 to 6 MiB). Only `load_room_at` (the catch-up) reads an
  old snapshot; the erasure rewrites every one of them, and each holds a copy
  of nicknames, tokens and chat. `removed_tokens` grows with every removal
  (L10).
- Market practice: snapshots are a cache of the log; only the newest is
  needed to load, any past state is rebuilt by replaying from a kept one
  (cheap here: 5,000 events in 70 ms); static data is kept once; unbounded
  collections are bounded.
- In scope: options.
  - 1 (lead's pick): keep two snapshots per room, the first and the newest;
    each save deletes the others in its transaction; a catch-up from before
    the newest replays the log from the first. `removed_tokens` keeps the last
    100. Migration 4 deletes the other snapshots in SQL alone, no JSON
    rewritten. Erasure then rewrites two rows, not up to 80.
  - 2: 1, plus the grid in a table of its own, once per room. Saves 23 KiB a
    room once only two snapshots stay; the migration rewrites every room's
    JSON.
  - Rejected by the Plan agent: the grid by catalogue number (a re-imported
    file would change a room's answers), one snapshot per day of play.
- Out of scope: the log, append-only (`platform/server.md`); writing cells
  without their default fields (a format change of its own).
- Screens: none.
- Open questions:
  1. The removed tokens: A (lead's default) the last 100 banned, an older one
     joins as a new player, as any other token already does
     (`lobby/host.md` rule 2); B every token kept.
  2. The chat in a snapshot: A (lead's default) the last 200 lines, the
     page's own cap (`social/chat.md` rule 8 changes, nothing visible); B all
     of it.
- Decisions: the human, 2026-10-31: option 1, the first and the newest
  snapshots kept; the last 100 removed tokens (1A); the last 200 chat
  lines in a snapshot (2A). The spec change approved, with the chat
  bounded in the room's state, not only in the stored snapshot.
<!-- SECTION:DESCRIPTION:END -->
