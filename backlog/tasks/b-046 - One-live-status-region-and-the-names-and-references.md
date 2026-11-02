---
id: B-046
title: One live status region, and the names and references
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:36:00Z'
labels:
  - domain:hud
  - domain:realtime
  - domain:room
  - domain:results
  - domain:rules
  - domain:rooms
  - domain:joining
  - domain:chat
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 hud AC-26 (new)
- [ ] #2 hud AC-27 (new)
- [ ] #3 room AC-8 (new)
- [ ] #4 rooms AC-18 (new)
- [ ] #5 rooms AC-9 (changed)
- [ ] #6 realtime AC-18 (changed)
- [ ] #7 rules AC-3 (changed)
- [ ] #8 rules AC-7 (changed)
- [ ] #9 rules AC-10 (changed)
- [ ] #10 results AC-10 (changed)
- [ ] #11 results AC-13 (changed)
- [ ] #12 joining AC-4 (changed)
- [ ] #13 chat AC-11 (changed)
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
Spec: specs/client/hud.md, with the status rules of specs/platform/realtime.md, specs/client/room.md, specs/gameplay/results.md
Tests: tests/test_hud_*.py and the tests of realtime, room and results for the changed criteria
Quick gate: uv run python scripts/gate.py --specs hud,realtime,room,results --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decisions (2026-11-02):
- Each rule goes in the domain that owns the element: « Jouer » and the Joueurs copied line in lobby/rooms, the nickname field in lobby/joining, « Réagir » in social/chat, the grid status in gameplay/rules. Labels domain:rules, rooms, joining, chat added; no clash with the tasks In Progress.
- One status region in the page, plus one in each open room sheet (option B of the spec-writer): a sheet opened with showModal() makes the page inert, so the recap's lines and the band would go unheard behind a sheet. Same result for players as the pitch intends, only heard.
- The grid status is announced when it appears or its text changes (also on a first snapshot already solved), not when it moves between the clue bar's row and the band.
- A repeated message is announced again: the region is emptied, then written.
- Criteria count over budget in results, joining, chat, hud: splits left out of this task.
<!-- SECTION:NOTES:END -->
