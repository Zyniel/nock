---
id: DRAFT-070
title: The recap and the account sheet give way to the room-gone dialog, proven
status: Draft
assignee: []
created_date: '2026-11-03T22:36:00Z'
labels:
  - follow-up
  - domain:hud
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Open item of the « Test gaps » close. leaveDeletedRoom in web/src/lib/RoomPage.svelte closes each sheet with its own line (isRecapOpen = false, hostSettings?.close(), accountDialog?.close()); B-071 proved only the host's settings sheet giving way to the room-gone dialog (hud AC-21), so deleting the recap's or the account sheet's line would pass every test. Widen hud AC-21 with one more sheet case (or the recap), or add a component-level test.
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
