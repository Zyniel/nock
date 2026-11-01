---
id: B-043
title: Remote updates in proportion to what changed
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
labels:
  - domain:shell
milestone: m-0
dependencies: []
documentation:
  - specs/client/shell.md
priority: medium
ordinal: 4000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Priority: fourth of B-039's items (on the path of `product.md` rules 23
  and 24)
- Domains: client/shell (a frame that changes nothing of a cell leaves it
  untouched; the spec-writer picks the measure)
- Architecture decision: no (inside `roomSession.ts` and
  `GridViewport.svelte`)
- Model: Opus for the test-writer and the implementer (timing in a browser,
  `CLAUDE.md`)
- Problem: every frame, the pong every 2 seconds included, assigns a new
  array of cursors (`roomSession.ts:1197`), and each letter cell reads fresh
  arrays from `cursorsOn` and `tintsOn` (`GridViewport.svelte:171`), so every
  frame re-runs the template of every letter cell. With 8 players at 2
  letters a second (rule 24) that is about 16 passes over the grid a second,
  against the 50 ms local echo of rule 23 on the throttled phone (B-039 M5;
  not measured). Each keystroke also copies every cell for `filledWords`
  with the Salon closed, and scans the grid once per cell of a word (L13). A
  pinch sets `--triangle` on every letter cell, and every arrow has two
  `drop-shadow` filters (L16).
- In scope: `nextCursors` returns the same array when nothing moved; one
  derived map from cell to its cursors and tint, with shared empty values;
  the same for flashes and caught-up cells; a cell index per snapshot and a
  map of the latest pending edit per cell; `--triangle` on `.grid`; the
  arrows' white halo as an SVG stroke. A measure proves it, for example "a
  pong changes no cell of the grid" (a mutation count) and rule 23's echo
  with 8 remote players typing; its test file goes in `SERIAL_TEST_FILES`
  if it measures a pace.
- Out of scope: splitting the cells into components (B-049).
- Screens: none (the halo as a stroke looks the same; the cell sheet checks
  it).
- Open questions: none.
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
