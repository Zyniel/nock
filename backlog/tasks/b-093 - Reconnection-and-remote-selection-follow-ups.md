---
id: B-093
title: Reconnection and remote selection follow-ups
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-06T19:59:00Z'
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
- [x] #2 reconnection AC-10 (new)
- [x] #3 reconnection AC-11 (new)
- [x] #4 reconnection AC-12 (new)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
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

Test-writer: AC-11 fails now (the check dropped when send() refuses); AC-10 and AC-12 pass now and each fails on its removal (stopSendQueue not keeping queued requests; a request resent after a dead-network send). remotesByCell: tests/web/remoteSelections.test.ts (identity of unchanged cells), fails with the reuse deleted. Note for the implementer: rule 7 also covers a queued request whose send fails in sendNextQueued; AC-11 exercises request() only.

Review round 1: CHANGES REQUESTED. (1) keepRequest puts a later request with the same editsBefore in front (< must be <=), and stopSendQueue puts the still-queued requests in front of one kept by a sendNextQueued refusal: both break rule 7's « in their places »; (2) no test catches either. Lead's calls: the test-writer adds two node tests in tests/web/ (failing on 399fad5), then the implementer fixes the order; the reviewer's suggestion of a criterion for the queued case is not taken: rule 7 already states it and the unit tests guard it, as for the remotesByCell reuse. The reviewer's gate was held by B-104's full gate; its reconnection browser tests passed outside the gate (14).

Reviewer round 2: APPROVE (each half of the fix guarded by its own node test; quick gate passed: 4775 + 82).

Full gate green (chromium): 8889 parallel + 145 serial passed. Criterion #1 left unchecked: the two B-041 decisions have their criteria (AC-10 to AC-12) and tests, but the remotesByCell reuse has a unit test and no criterion (no browser-observable separation, measured), as decided above.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
B-041's decisions on reconnection are now criteria: a loss during the resend keeps the requests not yet sent (AC-10), a request refused by a closing socket is kept in its place (AC-11), a request handed to a socket whose network is dead is lost while the edits go out again (AC-12). The client keeps a refused request in its place, and, after review round 1, in order among requests with the same edits before it and among those still queued (two node tests). The remotesByCell reuse is guarded by a unit test only: criterion #1 met in part. Firefox and WebKit left to CI.
<!-- SECTION:FINAL_SUMMARY:END -->
