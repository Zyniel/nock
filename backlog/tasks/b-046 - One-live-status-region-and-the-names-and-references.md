---
id: B-046
title: One live status region, and the names and references
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:hud
  - domain:realtime
  - domain:room
  - domain:results
milestone: m-1
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/platform/realtime.md
  - specs/client/room.md
  - specs/gameplay/results.md
priority: medium
ordinal: 7000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: seventh of B-039's items (screen readers)
- Domains: client/hud (one status region for the room page), with the rules
  that call a message a status (`platform/realtime.md` rule 20 for the
  band, `client/room.md` for the notes, `gameplay/results.md` for the
  recap); the spec-writer finds them
- Architecture decision: no
- Problem: the connection band, the grid status, the undo note, the Joueurs
  status and the recap status are live regions created with their text
  already in them (`RoomPage.svelte:2131`, `:2304`, `RoomNote.svelte:75`,
  `PlayersPanel.svelte:155`, `RecapDialog.svelte:220`); screen readers often
  stay silent for a region that is created full (B-039 M9, plausible). The
  vote banner does it right (`RoomPage.svelte:2173`). The catalogue's
  « Jouer » buttons cannot be told apart, `aria-controls="reaction-picker"`
  points to an element that exists only while open, and the nickname field
  is `aria-invalid` with no `aria-describedby` (L22).
- In scope: one persistent, visually hidden `role="status"` region in the
  room page and an `announce(text)` passed down; the visible elements lose
  their role; « Jouer » described by its card's title; the references set
  only while their target exists.
- Out of scope: the vote banner's region (already right); the alerts of the
  forms.
- Screens: none.
- Open questions: none.
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
