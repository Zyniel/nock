---
id: B-094
title: How two hyphen edges meet in a cell
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T22:38:00Z'
labels:
  - design
milestone: m-8
dependencies: []
documentation:
  - specs/_design/cells.md
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
