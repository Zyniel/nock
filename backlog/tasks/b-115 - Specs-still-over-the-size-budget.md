---
id: B-115
title: platform/realtime.md under the size guide
status: Done
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T20:17:00Z'
labels:
  - domain:realtime
  - domain:fair-play
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-079. platform/realtime.md is 17.7 KB with 19 criteria. Move one part, its criteria as they are, to a new domain spec; the Plan agent proposes the options, the lead picks. gameplay/co-op.md, first in this task, went to B-116: both cuts did not fit one agent context. The other files over the guide (hud, catch-up, rules, joining, viewport, the _design files) stay in a draft. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 realtime.md is under about 15 KB and 20 criteria, any moved part has its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 fair-play AC-1 (moved from realtime AC-6)
- [x] #3 fair-play AC-2 (moved from realtime AC-12)
- [x] #4 fair-play AC-3 (moved from realtime AC-13; rule 23 cited as rule 1)
- [x] #5 fair-play AC-4 (moved from realtime AC-14)
- [x] #6 chat AC-14 (changed: points at fair-play)
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
Specs: specs/platform/realtime.md, new specs/platform/fair-play.md, specs/_map.md, the specs that cite realtime's fair-play rules
Tests: renames only if a moved criterion is proven by tests/test_realtime_* (none expected: the moved criteria are pointers)
Gate: uv run python scripts/gate.py --specs realtime,fair-play --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's pick among the Plan agent's options (Fable, high): R1, move realtime's « Fair play » section (rules 23-25, AC-6, AC-12, AC-13, AC-14, all pointers to 037/039/040) to a new domain platform/fair-play.md, criteria text unchanged and renumbered from AC-1 (precedent B-085); the hyphen-mark part of rule 23 and AC-20 stay in realtime. Rejected: R2 (a sockets domain, three test files renamed and ten pointers rewritten), R3 (too little margin). Adding a domain is covered by the bet: the pitch names each split adding one. co-op's cut went to B-116 (both did not fit one context).

Spec-checker APPROVED. realtime.md 15,213 bytes, 15 criteria; fair-play.md 3,894 bytes, 4 criteria. 037 stays partly in realtime (AC-9, AC-11 point at 037 AC-2). No test renamed, no code: every moved criterion is a pointer. Left for a follow-up: _map.md's realtime row could name the join deadline and the sockets per address.

Review round 1: CHANGES REQUESTED (hints.md and votes.md Depends on still sent « what a browser may receive » to realtime). Fixed with two suggestions (hints.md rewrap, _map.md's realtime row names the join deadline and the sockets per address); spec-checker APPROVED.

Close: platform/server.md still held B-086's « New interface » section (production_app, now in its Code); removed, as the close step does for each domain file of the task.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change. Architecture decision: the Plan agent (Fable, high) gave three options; the lead picked R1, a new domain platform/fair-play.md (the pitch names each split adding a domain).
- #1 realtime.md is 15,213 bytes with 15 criteria (was 17.7 KB, 19); fair-play.md 3,894 bytes, 4 criteria. Moved word for word: rules 23 (minus its hyphen-mark sentences, now realtime rule 27), 24, 25 -> fair-play rules 1-3; realtime AC-6, AC-12, AC-13 (« rule 23 » -> « rule 1 »), AC-14 -> fair-play AC-1 to AC-4, each with its pointer (← 039 AC-14 to AC-17; 037 AC-3; 037 AC-1, 040 AC-9; 037 AC-4), proven by tests/test_spec_037_*, 039_*, 040_* (no test moved). chat AC-14 points at fair-play. _map.md: new fair-play row, realtime row rewritten. Pointers fixed in reconnection, co-op, server, hints, votes, viewport, rooms, chat.
- Spec-checker APPROVED (twice). Reviewer: CHANGES REQUESTED in round 1 (hints.md and votes.md still sent « what a browser may receive » to realtime), APPROVE in round 2.
- Close: server.md's leftover « New interface » section of B-086 removed.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- B-116 (co-op's cut) edits co-op.md after this merges.
<!-- SECTION:FINAL_SUMMARY:END -->
