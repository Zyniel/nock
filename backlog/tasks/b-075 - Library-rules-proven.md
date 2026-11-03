---
id: B-075
title: Library rules proven
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:library
milestone: m-5
dependencies: []
documentation:
  - specs/content/library.md
priority: low
ordinal: 63000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-016. library rules 8, 10, 16 and AC-6 are kept by the code but untested: the catalogue asks once and refuses items that are not summaries; the force filter makes no new request; the grid page's loading line and its non-summary answer; after a chip, only that chip pressed. library.md is past the budget (25 criteria): widen existing criteria rather than add.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of the four behaviours has a test that fails if the code stops keeping it
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
