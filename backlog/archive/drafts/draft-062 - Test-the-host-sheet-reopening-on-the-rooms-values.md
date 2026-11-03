---
id: DRAFT-062
title: Test the host sheet reopening on the room's values
status: Draft
assignee: []
created_date: '2026-11-03T13:32:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Grid and room screens » close. B-050's first review round blocked on the host settings sheet reopening on the abandoned typed values; the fix (specs/lobby/host.md rule 8, about line 80) has no test. Add a criterion and a browser test: type a count, close without saving, reopen: the room's values show. Three other B-050 fixes have no test and could only be tested at a lower level (L12 the menu placed again after tick() in RoomPopover.svelte, L14 one watcher per list in scrollingLists.ts, L15 the lost pointerup in pinchPan.ts); a unit test in tests/web/ could take L14 and L15.
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
