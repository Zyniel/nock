---
id: B-094
title: How two hyphen edges meet in a cell
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T23:58:00Z'
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
- [x] #1 cells.md says how two hyphen edges meet, the cell sheet draws both cases, and a test checks the painted pixels
- [x] #2 viewport AC-21: the painted pixels where two hyphen edges meet; _design/cells.md says it and the cell sheet draws both cases
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: the criterion goes in gameplay/viewport.md as AC-21 (option a), because design files hold no criteria. viewport.md goes to 21 criteria, one over the budget, recorded with DRAFT-079. A split would be an escalation, and folding the criterion into AC-9 would rewrite its tests. The cell sheet's corner pixel in the 4b drawings is also corrected to match the code. No change of look in the app.

Spec-checker APPROVED in one round. Not taken, all optional: three wording refinements in cells.md (the t = 2 outer pixel, the mirror case, line 34's « stays plain »). For m-8's close: add viewport.md (21 criteria) and hud.md (15.4 KB) to DRAFT-079. For the test-writer: the two cases are two separate grids, read at fractional cell sizes.

Tests: test_ac21 passes on both grids, as the spec writes down what the code paints; no code change. tests/test_viewport_hyphen_edges.py is now 831 lines, a little over 800; a split by criterion group can come with DRAFT-078's test tidy.

Reviewer round 1: APPROVE. It checked that the test fails on a white corner pixel and on solid strips, and that the cell sheet's new drawings show AC-21's pixels. Not taken: a docstring wording and a second cell size near 72 px (the geometry holds over the whole range). For m-8's close: add viewport.md (21 criteria), hud.md (15.4 KB) and _design/cells.md (18.1 KB) to DRAFT-079.

Full gate here (Chromium): static checks pass, as do 8,775 of 8,776 parallel tests and all 162 serial ones. The one failure, test_spec_035_ac08 contrast on a flashing cell at phone-7, missed the cell's flash (data-flash empty). That is a timing race under load. B-094 changes no code, and the test passed 16/16 three times on rerun. For m-8's close: add it to B-100's notes. Firefox and WebKit are left to CI after the merge.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
_design/cells.md says how two hyphen edges meet in a cell, as the code already paints it: each edge stops one pixel short of the crossing line, the crossing pixel is rule grey, and at t = 2 and 3 the pixels around it are plain lines or background. The hand-drawn cell sheet draws both cases (two edges of one cell; an edge ending where another starts), and the corner pixel of its existing 4b drawings now matches the code. viewport AC-21 checks the 3 by 3 pixels around each crossing on two grids, and its test fails on a wrong painting. viewport.md has 21 criteria, one over the budget, recorded for DRAFT-079. No code change.
<!-- SECTION:FINAL_SUMMARY:END -->
