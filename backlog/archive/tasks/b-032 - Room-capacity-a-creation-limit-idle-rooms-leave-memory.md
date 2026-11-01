---
id: B-032
title: 'Room capacity: a creation limit, idle rooms leave memory'
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:rooms
  - domain:server
  - domain:results
dependencies: []
ordinal: 42000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
<!-- SECTION:DESCRIPTION:END -->
