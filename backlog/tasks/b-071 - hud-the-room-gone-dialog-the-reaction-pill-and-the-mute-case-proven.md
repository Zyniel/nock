---
id: B-071
title: 'hud: the room-gone dialog, the reaction pill and the mute case proven'
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:hud
milestone: m-5
dependencies:
  - B-070
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 59000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-002, 022, 064. hud rule 16: AC-21 proves only the Salon sheet giving way to the room-gone dialog; an open room sheet or the recap would prove the native modals give way. Rule 14: no test taps the reaction pill on a clue (a tap selects that clue). Rule 12: when the page moves the focus out of the Salon sheet (mute), the sheet stays open, with no criterion of its own. hud.md is past the budget: widen AC-21 and the existing criteria of rules 12 and 14 rather than add. Out of scope: the Android back gesture.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 An open room sheet or the recap gives way to the room-gone dialog
- [ ] #2 A tap on a clue's reaction pill selects that clue
- [ ] #3 Muting from the Salon sheet keeps it open
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
