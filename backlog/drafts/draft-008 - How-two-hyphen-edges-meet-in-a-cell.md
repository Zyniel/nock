---
id: DRAFT-008
title: How two hyphen edges meet in a cell
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`_design/cells.md` « Hyphen edges » does not say how two hyphen edges meet: a cell with both marks (the code draws a 1 px rule-grey corner pixel), and, at 3 px thickness, an across edge ending where a down edge starts (the outer pixel can fall in the other edge's gap); neither is drawn in the cell sheet.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
