---
id: B-112
title: shell's typeless frame in one criterion
status: Done
assignee: []
created_date: '2026-11-06T13:46:00Z'
updated_date: '2026-11-09T19:53:00Z'
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
- [x] #1 The typeless frame is in one criterion of shell.md, its test proves it, and the other criterion no longer lists it
- [x] #2 AC-36's binary case is proven without waiting a fixed delay
- [x] #3 shell AC-7 (changed)
- [x] #4 shell AC-36 (changed)
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
Specs: specs/client/shell.md (AC-7, AC-36)
Tests: tests/test_shell_*.py proving AC-7 and AC-36
Gate: uv run python scripts/gate.py --specs shell --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: AC-36 keeps the typeless frame, AC-7 drops it. The 040 test's {"type": 3, "seq": 6} frame stays as it is (outside B-112); proving rule 3's string type properly goes to a follow-up draft.

No implementation phase: the change is in a criterion's wording and its tests, with no behaviour change; both tests pass on the current code.

Review round 1: CHANGES REQUESTED. The binary frame reaches the page as a Blob, whose read waits, so W-then-V sent back to back missed a decoder that waits. Lead's call: AC-36 puts a visible step between the ignored frame and event 6 (a text event 7 buffered, one pending), then event 6 V applies both; spec-writer, spec-checker, then test-writer (Opus, after a send-back).

Review round 2: APPROVE. Left as is: the docstring's « T then applies at once » holds for a synchronous decoder only (the conclusion holds either way), and a decoder slower than two round trips would pass, which no fixed delay closes either.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change; only shell.md's wording and two tests.
- #1 (shell AC-7 changed, AC-36 changed): the typeless frame {"seq": 6} is in AC-36 only; AC-7's list (not json, [1, 2], null) and its v1.1.0 test test_ac19_junk_frames_are_ignored (← 040 AC-19) no longer send it.
- #2: AC-36 proves the binary case by effects, with no fixed delay: after the ignored frame (binary event 6 W, or typeless), text event 7 T at (1, 0) is buffered (one pending), then text event 6 V at (2, 1) gives seq 7, nothing pending, V and T shown. test_ac36_a_binary_or_typeless_frame_is_dropped_and_event_6_then_applies (tests/test_shell_malformed_events.py), both cases. A Blob decoder (reads wait) and a synchronous decoder were each tried and fail it.
- Reviewer: CHANGES REQUESTED in round 1 (W then V back to back missed a decoder that waits), APPROVE in round 2.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- Flagged: the 040 test still sends {"type": 3, "seq": 6}, which no criterion lists (follow-up draft); a decoder slower than two round trips would pass, which no fixed delay closes either.
<!-- SECTION:FINAL_SUMMARY:END -->
