---
id: B-047
title: Connection hardening
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T16:20:00Z'
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
- [x] #1 reconnection AC-6 (new): a hidden page keeps a live socket; checks on return
- [x] #2 reconnection AC-7 (new): the 6 s connect timeout
- [x] #3 reconnection AC-8 (new): ±20 % retry delays, reset after a snapshot
- [x] #4 hud AC-28 (new): a final status makes the grid read-only, pending letters dropped
- [x] #5 hud AC-29 (new): « Annuler » and the Aide items disabled in a final status
- [x] #6 chat AC-22 (new): « Réagir » and « Je bloque » disabled while not joined
- [x] #7 chat AC-23 (new): only a send that went out counts for pacing
- [x] #8 co-op AC-21 (new): the five error codes answer only their messages (server test)
- [x] #9 shell AC-34 (new): a malformed event field is skipped, the event keeps its seq
- [x] #10 catch-up AC-21 (new): a malformed word_completed clue fails the answer
- [x] #11 operations AC-31 (new): a malformed replay time or seq shows the error line
- [x] #12 library AC-25 (new): an invalid published_on gives the error state
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
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

Lead: tests 3821640 (co-op AC-21 and AC-7's 5 s half already true); implementation 4a43010 (Opus); the implementer's gate found tests/test_joining_reconnection.py assuming an exact 1000 ms first retry: the test-writer allowed the jitter (ca11c2e). Reviewer APPROVE in round 1 (8284 + 160 passed); suggestions taken: the read-only tests check the grid's focus, the server test's sends in a plain loop (08e2d80), ops.ts's date check anchored to ISO 8601 (002931f); suggestions left as DRAFT-056 (rule 19's wording, the all-malformed check, untested parts) and DRAFT-057 (myRooms' dates); the spec sizes as DRAFT-058 (board PR #108). Full gate green (8704 parallel, 162 serial).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The B-039 review's rare cases of the connection, with the lead's defaults (no server pings, no protocol change).

Criteria and their tests:
- reconnection AC-6 (a hidden page keeps a live socket, pings on return, a waiting retry tries at once): tests/test_reconnection_hidden_page.py (3)
- reconnection AC-7 (6 s connect limit by the clock): tests/test_reconnection_retries.py (2)
- reconnection AC-8 (±20 % retry delays, reset after a snapshot): tests/test_reconnection_retries.py (2 × lowest/highest)
- hud AC-28 (a final status: grid read-only, pending letters dropped), AC-29 (« Annuler », Aide items disabled): tests/test_hud_final_states.py (5)
- chat AC-22 (« Réagir », « Je bloque » disabled while not joined), AC-23 (only a send that went out counts): tests/test_chat_connection.py (4)
- co-op AC-21 (the five error codes answer only their messages): tests/test_co_op_error_answers.py (3, server; already true)
- shell AC-34, catch-up AC-21, operations AC-31, library AC-25 (malformed server fields): tests/test_shell_malformed_events.py, test_catch_up_malformed_answer.py, test_operations_page.py, test_library_date_check.py
Edited for the jitter, names kept: spec017_harness.py, spec014_harness.py, test_spec_017_ac01/ac05, test_joining_reconnection.py.
Code: RoomPage.svelte, roomSession.ts, AideMenu.svelte, RoomTopBar.svelte, ClueBar.svelte, catchUp.ts, activityFeed.ts, ops.ts, catalogue.ts. Look: s-net and s-final redrawn (disabled clue bar buttons, pressed « Je bloque » under the disabled look).
Spec-checker: CHANGES REQUESTED round 1 (six wording fixes), APPROVED round 2. Reviewer: APPROVE round 1; three suggestions taken, the rest in DRAFT-056 and DRAFT-057.
Decisions: 6 s connect limit (the server's silence limit); the hidden-tab fix taken without the three-engine measure; ±20 % jitter; a final status drops pending letters and kept requests and disables « Annuler » and the Aide items; a waiting retry tries at once on return; malformed fields skipped in room events, refused in HTTP bodies, written where each parser's rule lives (shell, catch-up, operations, library); « Je bloque » pressed and disabled keeps its pressed state. Assumed by the implementer: a typed letter in a final status does not move the selection; an all-malformed check is not shown as clean (DRAFT-056).
Full gate: green (8704 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
