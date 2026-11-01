---
id: B-047
title: Connection hardening
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:hud
  - domain:chat
  - domain:co-op
  - domain:realtime
milestone: m-0
dependencies:
  - B-041
documentation:
  - specs/client/hud.md
  - specs/social/chat.md
  - specs/gameplay/co-op.md
  - specs/platform/realtime.md
priority: medium
ordinal: 8000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
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
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
