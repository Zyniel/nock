---
id: B-096
title: Three archived specs' checks tightened
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 84000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-011, 013 and 014: spec 025's vote banner test leaves SERIAL_TEST_FILES; 048 AC-13 checks document.getAnimations(); spec 035's scan binds placeholders to their values.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three checks are tightened and fail on the regression each draft names
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
