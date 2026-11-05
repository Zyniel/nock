---
id: B-099
title: Lower-level tests of three B-050 fixes
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - domain:hud
milestone: m-9
dependencies: []
documentation:
  - specs/client/hud.md
priority: low
ordinal: 87000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-071: L12 (RoomPopover placed again after tick()), L14 (one watcher per list), L15 (a lost pointerup).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each of L12, L14 and L15 has a test that fails without its fix
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
