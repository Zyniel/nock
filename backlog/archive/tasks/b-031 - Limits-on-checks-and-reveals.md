---
id: B-031
title: Limits on checks and reveals
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:hints
  - domain:realtime
dependencies: []
ordinal: 41000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
<!-- SECTION:DESCRIPTION:END -->
