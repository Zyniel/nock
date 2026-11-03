---
id: DRAFT-071
title: Lower-level tests of three B-050 fixes
status: Draft
assignee: []
created_date: '2026-11-03T22:36:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Test gaps » close (the last sentence of DRAFT-062, archived with it by mistake). Three B-050 fixes have no test: L12 (RoomPopover.svelte, the menu placed again after tick()), L14 (scrollingLists.ts, one watcher per list) and L15 (pinchPan.ts, a lost pointerup). Unit tests in tests/web/ could take L14 and L15; L12 needs a component or browser test. DRAFT-063 covers only L15's pen-panning effect.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
