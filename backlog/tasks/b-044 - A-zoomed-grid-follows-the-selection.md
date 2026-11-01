---
id: B-044
title: A zoomed grid follows the selection
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:board
milestone: m-1
dependencies: []
documentation:
  - specs/gameplay/board.md
priority: medium
ordinal: 5000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: fifth of B-039's items (phones)
- Domains: gameplay/board (rule 3: while zoomed, a change of selection
  scrolls the grid the least needed to show the selected cell)
- Architecture decision: no
- Model: Opus for the test-writer and the implementer (layout, `CLAUDE.md`)
- Problem: the selection moves only `aria-activedescendant`, which no engine
  scrolls into view, and nothing outside the pinch and pan code sets the
  viewport's scroll (`GridViewport.svelte:544`, `:577`). On a 360 px phone,
  zoomed to read a clue, letters 6 and 7 of a word typed with the in-app
  keyboard land off-screen; Tab and the arrows can select a word wholly
  off-screen (B-039 M6).
- In scope: while zoomed, an effect on the selected cell and the cell size
  scrolls the viewport the least that shows the cell with a margin; a tap
  moves nothing, its cell being in view.
- Out of scope: the zoom itself; the grid at zoom 1.
- Screens: none (the zoomed grid scrolls; no new look).
- Open questions:
  1. The margin kept around the cell: A (lead's default) one cell; B none.
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
