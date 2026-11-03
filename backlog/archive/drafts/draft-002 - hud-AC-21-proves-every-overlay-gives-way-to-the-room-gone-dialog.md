---
id: DRAFT-002
title: hud AC-21 proves every overlay gives way to the room-gone dialog
status: Draft
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - follow-up
  - domain:hud
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
`client/hud.md` rule 16 closes the menus, the reaction picker, a room sheet and the recap before the room-gone dialog shows, but AC-21 proves only the Salon sheet (B-021's review); an open room sheet or the recap in AC-21's second case would prove the native modals give way. The Android back gesture's reopen is tested only through `close()`.
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
