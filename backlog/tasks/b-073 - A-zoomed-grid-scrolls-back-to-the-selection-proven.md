---
id: B-073
title: A zoomed grid scrolls back to the selection, proven
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T21:11:00Z'
labels:
  - domain:viewport
milestone: m-5
dependencies: []
documentation:
  - specs/gameplay/viewport.md
priority: low
ordinal: 61000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-045 (B-044's review). Every zoomed test of viewport AC-11 to AC-17 scrolls right or down from the top-left corner, so a defect in the backward branch (marginStart < scroll) of scrollShowingCell (web/src/lib/gridLayout.ts) would pass. A criterion, e.g. ArrowLeft back along a word after a pan to the right, and its test.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 After the grid is scrolled past the selection, moving it left or up scrolls back the least that shows the cell with one cell of margin
- [x] #2 viewport AC-19 (new)
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
1. Spec: gameplay/viewport.md (a criterion for the backward scroll of rule 4).
2. Tests: tests/test_viewport_zoom_follow.py.
3. Quick gate: uv run python scripts/gate.py --specs viewport --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: ArrowUp alone along JAMBE (the backward branch on both axes, the across one clamped at column 0); the row-0 top-edge clamp is left to rule 3 (shared code).

Review round 1: APPROVE. Not taken: 1 (simplify the test's loop: not worth a round); 2 (the across clamp at column 0 cannot be told from an unclamped scroll: the row-0 clamp left to rule 3, as noted).

PR #129.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
viewport AC-19 (new) proves the backward branch of the zoomed grid's follow (rule 3): after a pan to the bottom-right, each ArrowUp back along JAMBE scrolls up the least that shows the cell with one cell of margin, and the first also scrolls back across to the grid's left edge. No code change.

Criteria and their tests:
- viewport AC-19 (new): tests/test_viewport_zoom_follow.py::test_ac19_arrow_up_to_2_0_after_a_pan_scrolls_up_to_the_cell_above_and_back_left (Chromium, like the file's other zoomed tests).

Spec-checker: APPROVED. Reviewer: APPROVE in round 1 (a version that never scrolls back, scrolls with no margin or centres fails the test); suggestions not taken (reasons in the notes). Full gate: passed (8733 parallel, 162 serial).
Decisions: ArrowUp alone along JAMBE reaches the branch on both axes; the row-0 top clamp is left to rule 3 (shared code); the tests passed on the existing code, so no implementer phase.
<!-- SECTION:FINAL_SUMMARY:END -->
