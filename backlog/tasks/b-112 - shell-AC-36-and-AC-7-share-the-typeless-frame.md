---
id: B-112
title: shell's typeless frame in one criterion
status: In Progress
assignee: []
created_date: '2026-11-06T13:46:00Z'
updated_date: '2026-11-09T18:38:00Z'
labels:
  - domain:shell
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-083 (B-097's review). client/shell.md AC-7 lists {"seq": 6} among the frames that change nothing and AC-36 proves it apart from event 6. Keep the typeless frame in one criterion. Also: AC-36's binary case tells a decoded frame only by a check after SETTLE_MS (300 ms); make its test tell it by an effect. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The typeless frame is in one criterion of shell.md, its test proves it, and the other criterion no longer lists it
- [ ] #2 AC-36's binary case is proven without waiting a fixed delay
- [ ] #3 shell AC-7 (changed)
- [ ] #4 shell AC-36 (changed)
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
Specs: specs/client/shell.md (AC-7, AC-36)
Tests: tests/test_shell_*.py proving AC-7 and AC-36
Gate: uv run python scripts/gate.py --specs shell --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: AC-36 keeps the typeless frame, AC-7 drops it. The 040 test's {"type": 3, "seq": 6} frame stays as it is (outside B-112); proving rule 3's string type properly goes to a follow-up draft.

No implementation phase: the change is in a criterion's wording and its tests, with no behaviour change; both tests pass on the current code.

Review round 1: CHANGES REQUESTED. The binary frame reaches the page as a Blob, whose read waits, so W-then-V sent back to back missed a decoder that waits. Lead's call: AC-36 puts a visible step between the ignored frame and event 6 (a text event 7 buffered, one pending), then event 6 V applies both; spec-writer, spec-checker, then test-writer (Opus, after a send-back).
<!-- SECTION:NOTES:END -->
