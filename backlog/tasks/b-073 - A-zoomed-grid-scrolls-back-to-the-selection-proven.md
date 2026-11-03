---
id: B-073
title: A zoomed grid scrolls back to the selection, proven
status: In Progress
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T19:48:00Z'
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
- [ ] #1 After the grid is scrolled past the selection, moving it left or up scrolls back the least that shows the cell with one cell of margin
- [ ] #2 viewport AC-19 (new)
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
1. Spec: gameplay/viewport.md (a criterion for the backward scroll of rule 4).
2. Tests: tests/test_viewport_zoom_follow.py.
3. Quick gate: uv run python scripts/gate.py --specs viewport --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: ArrowUp alone along JAMBE (the backward branch on both axes, the across one clamped at column 0); the row-0 top-edge clamp is left to rule 3 (shared code).
<!-- SECTION:NOTES:END -->
