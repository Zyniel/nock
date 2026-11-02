---
id: B-047
title: Connection hardening
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T13:43:00Z'
labels:
  - domain:hud
  - domain:chat
  - domain:co-op
  - domain:realtime
  - domain:reconnection
  - domain:shell
  - domain:catch-up
  - domain:operations
  - domain:library
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 reconnection AC-6 (new): a hidden page keeps a live socket; checks on return
- [ ] #2 reconnection AC-7 (new): the 6 s connect timeout
- [ ] #3 reconnection AC-8 (new): ±20 % retry delays, reset after a snapshot
- [ ] #4 hud AC-28 (new): a final status makes the grid read-only, pending letters dropped
- [ ] #5 hud AC-29 (new): « Annuler » and the Aide items disabled in a final status
- [ ] #6 chat AC-22 (new): « Réagir » and « Je bloque » disabled while not joined
- [ ] #7 chat AC-23 (new): only a send that went out counts for pacing
- [ ] #8 co-op AC-21 (new): the five error codes answer only their messages (server test)
- [ ] #9 shell AC-34 (new): a malformed event field is skipped, the event keeps its seq
- [ ] #10 catch-up AC-21 (new): a malformed word_completed clue fails the answer
- [ ] #11 operations AC-31 (new): a malformed replay time or seq shows the error line
- [ ] #12 library AC-25 (new): an invalid published_on gives the error state
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: platform/reconnection.md (hidden tabs, connect timeout, jitter), client/hud.md (final status: grid read-only), social/chat.md (Réagir, Je bloque while not joined), gameplay/co-op.md rule 12 (the error codes' invariant).
2. Tests: tests/test_reconnection_*, test_hud_*, test_chat_*, test_co_op_* (a server test for the invariant).
3. Quick gate: uv run python scripts/gate.py --specs reconnection,realtime,hud,chat,co-op --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-057 (#98) and B-060 (#103) merged. B-057 moved the realtime rules this task names (16 hidden tabs → now reconnection's heartbeat rule; 18 the connect; 21 retries) into platform/reconnection.md, so the connection rules are written there; the task takes domain:reconnection. Open questions, the lead's defaults (the pitch: « with the lead's defaults »): 1 A, a 6-second connect timeout, the silence limit; 2 A, the page checks the silence again on visibilitychange before it closes — taken directly, without the measure in three engines first: it is harmless when no drop happens and keeps the pitch's « no protocol change »; 3 A, ±20 % jitter on each retry delay. Test-writer and implementer on Opus: criteria about timing in a browser. Base: origin/main af1fef7.

Lead: answers to the spec-writer: in a final status (not not_found) pending letters and kept undos/checks/reveals are dropped, letters, erases, « Annuler » and the Aide items send nothing (disabled look); a retry waiting when the page becomes visible tries at once; the connect timeout stays 6 s (the server's silence limit, not the page's 4 s); the parser rules live where each parser's rule already lives (shell, catch-up, operations, library: the task takes those labels; B-058, which held domain:shell, had merged first, and the spec was committed after it); « Je bloque » pressed and disabled keeps its pressed state under the disabled look (drawn in s-net). Parsers: in a room event a malformed field is treated as absent and the event applies with its seq; HTTP bodies with a malformed field are refused whole. Spec-checker: CHANGES REQUESTED in round 1 (six wording fixes: co-op rule 12's pronouns, chat AC-23's state, rule 6's clock reading on a hidden page, AC-21's message types, an edge case's citation, AC-7's margin), APPROVED in round 2; its cosmetic note (one long line in chat rule 5) left. The file sizes (operations 24.9 KB / 31 criteria, hud 21.2 KB, chat 20.6 KB, library 25 criteria, co-op and catch-up 21) go to a follow-up draft: a split is the human's call. The 017 tests behind reconnection AC-3/AC-4 assume exact delays: the test-writer edits them in place.
<!-- SECTION:NOTES:END -->
