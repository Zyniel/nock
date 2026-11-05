---
id: B-094
title: How two hyphen edges meet in a cell
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T22:53:00Z'
labels:
  - design
  - domain:viewport
milestone: m-8
dependencies: []
documentation:
  - specs/_design/cells.md
  - specs/gameplay/viewport.md
priority: low
ordinal: 82000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-008: _design/cells.md says how two hyphen edges meet (the corner pixel, the 3 px edges' ends) and the cell sheet draws it, as the code already paints it.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 cells.md says how two hyphen edges meet, the cell sheet draws both cases, and a test checks the painted pixels
- [ ] #2 viewport AC-21: the painted pixels where two hyphen edges meet; _design/cells.md says it and the cell sheet draws both cases
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: the criterion goes in gameplay/viewport.md as AC-21 (option a), because design files hold no criteria. viewport.md goes to 21 criteria, one over the budget, recorded with DRAFT-079. A split would be an escalation, and folding the criterion into AC-9 would rewrite its tests. The cell sheet's corner pixel in the 4b drawings is also corrected to match the code. No change of look in the app.

Spec-checker APPROVED in one round. Not taken, all optional: three wording refinements in cells.md (the t = 2 outer pixel, the mirror case, line 34's « stays plain »). For m-8's close: add viewport.md (21 criteria) and hud.md (15.4 KB) to DRAFT-079. For the test-writer: the two cases are two separate grids, read at fractional cell sizes.

Tests: test_ac21 passes on both grids, as the spec writes down what the code paints; no code change. tests/test_viewport_hyphen_edges.py is now 831 lines, a little over 800; a split by criterion group can come with DRAFT-078's test tidy.
<!-- SECTION:NOTES:END -->
