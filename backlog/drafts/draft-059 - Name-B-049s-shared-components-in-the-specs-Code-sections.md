---
id: DRAFT-059
title: Name B-049's shared components in the specs' Code sections
status: Draft
assignee: []
created_date: '2026-11-02T23:44:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-049 (reviewer round 2 suggestions). FocusableLink.svelte (the WebKit link workaround, used by 13 components across several domains, carrying spec 035 AC-1), PlayButton.svelte and wideWindow.ts are named by no domain spec's Code section, so B-055's SHARED_COMPONENT_DOMAINS does not widen the quick gate when they change. Name them in the Code sections of the domains they serve (the gate's static check then adds FocusableLink.svelte to the map). Also: client/hud.md's Code line « … GridStatus.svelte (the grid's completion line) and its parts » reads as if the parts were GridStatus's, runs about 100 columns, and « announced by RoomPage.svelte » leaves out NoteSlot, RecapDialog, PlayersPanel and RoomSheet; VoteBanner.svelte's layer comment has a line of about 106 characters.
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
