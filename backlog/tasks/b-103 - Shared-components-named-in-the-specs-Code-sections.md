---
id: B-103
title: Shared components named in the specs' Code sections
status: To Do
assignee: []
created_date: '2026-11-05T01:54:00Z'
labels:
  - tooling
milestone: m-9
dependencies: []
priority: low
ordinal: 91000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-059: FocusableLink.svelte, PlayButton.svelte and wideWindow.ts are named in the Code sections of the domains they serve, so the quick gate widens when they change; hud's Code line about GridStatus reads right.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The three files are in the Code sections, and the gate's shared-component map lists them
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
