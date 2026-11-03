---
id: B-072
title: The host sheet reopens on the room's values, proven
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:host
milestone: m-5
dependencies: []
documentation:
  - specs/lobby/host.md
priority: medium
ordinal: 60000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-062. B-050's first review round blocked on the host settings sheet reopening on abandoned typed values; the fix (host rule 8) has no test. host.md is past the budget: widen host AC-21 rather than add. Out of scope: lower-level tests of L12, L14, L15.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Typed values closed without saving are gone when the sheet reopens: the room's values show
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
