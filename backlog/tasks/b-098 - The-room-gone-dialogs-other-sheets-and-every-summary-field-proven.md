---
id: B-098
title: The room-gone dialog's other sheets and every summary field, proven
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - domain:hud
  - domain:library
milestone: m-9
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/content/library.md
priority: low
ordinal: 86000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-070 and DRAFT-072: hud AC-21 widens to the recap and the account sheet; a parametrised unit test covers every isGridSummary field check.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Deleting any sheet's close line in leaveDeletedRoom, or any field check of isGridSummary, fails a test
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
