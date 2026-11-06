---
id: B-093
title: Reconnection and remote selection follow-ups
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T17:20:00Z'
labels:
  - domain:reconnection
  - domain:presence
milestone: m-10
dependencies: []
documentation:
  - specs/platform/reconnection.md
  - specs/social/presence.md
priority: low
ordinal: 81000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-044 and DRAFT-046: the two lead's decisions of B-041 get criteria (a queued request kept again, the dying socket's request), and the reuse of remotesByCell gets a guard.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The two B-041 decisions and the remotesByCell reuse each have a criterion and a test that fails without them
- [ ] #2 reconnection AC-10 (new)
- [ ] #3 reconnection AC-11 (new)
- [ ] #4 reconnection AC-12 (new)
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
Spec: platform/reconnection.md (the two B-041 decisions as criteria), social/presence.md (a criterion guarding the remotesByCell reuse)
Tests: tests/test_reconnection_*.py, tests/test_presence_*.py
Quick gate: uv run python scripts/gate.py --specs reconnection,presence --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead's decisions on the spec-writer's report: (3) the dying socket: a request never handed to its socket (closing, close not yet heard) is kept for the next snapshot; one handed to a socket whose network is dead is lost (a resend could double an undo, a reveal or a vote) — rule 7 and AC-11; (2) the remotesByCell pace belongs with foundation rule 8's other pace, not presence; (1) its budget is set from a measurement with and without the reuse before the spec goes to the checker; if the two do not separate clearly, the guard becomes a node unit test and the criterion is dropped (recorded).

Measurement (scratchpad b093/, 2 rounds of 10 alternating runs, under load 9-13 on 4 CPUs): per selection_moved, with the reuse median ~5.9 ms, without ~7.5 ms, ranges overlapping heavily: no browser budget can tell them apart. Lead's decision: no pace criterion for the reuse; it is guarded by a deterministic node unit test in tests/web (the same object comes back for a cell whose remotes did not change), which proves no criterion. The task's criterion is therefore met in part for the reuse (a test, no criterion); presence.md is left unchanged.

Spec-checker round 1: CHANGES REQUESTED (rule 7's queued requests, no criterion for the lost half, wording); round 2: APPROVED.
<!-- SECTION:NOTES:END -->
