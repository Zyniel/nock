---
id: B-043
title: Remote updates in proportion to what changed
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T21:58:00Z'
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 shell AC-22 (new): a pong, a chat_message and a same-place selection_moved mutate no node of the grid
- [ ] #2 shell AC-23 (new): a remote letter, and its flash, mutate no node of the grid outside its cell
- [ ] #3 shell AC-24 (new): a cursor move mutates only the cells it leaves and enters, and their tints
- [ ] #4 shell AC-25 (new): a pinch mutates no cell, and the triangle takes the new side
- [ ] #5 shell AC-26 (new): rule 23's echo holds on FX-02 with 7 others typing
- [ ] #6 shell AC-27 (new): a frame that changes no cell costs at most 2 ms of main-thread time on average
- [ ] #7 shell AC-28 (new): a catch-up ring mutates no node of the grid outside its cell
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
Spec: specs/client/shell.md (a frame that changes nothing of a cell leaves it untouched; the measure), cell sheet if the arrows' halo is drawn as a filter.
Tests: tests/test_shell_remote_updates.py (in SERIAL_TEST_FILES if it measures a pace).
Quick gate: uv run python scripts/gate.py --specs shell,board,product --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: base commit ffc9b81. No open question. The quick gate is widened with board and product because the change touches GridViewport.svelte (two regressions of B-041/B-042 hid there).

Lead, on the spec-writer's questions: (1) shell.md is at 26 criteria, 21 KB: the split (client/foundation.md for the visual foundation) is a follow-up for the human. (2) 7 others plus the measured player (a room holds 8). (3) 250 ms between the measured player's letters, as product AC-13. (4) The mutation counts may pass before the fix, Svelte skipping unchanged writes: kept as guards, plus one criterion that measures the fix itself, at most 2 ms of main-thread time per frame that changes no cell, on average over a burst of about 100, on the reference phone and FX-02. (5) The halo is 1.2 units of the arrow's 24-unit box. (6) Rule 18 asks nothing of a snapshot.

Spec-checker: CHANGES REQUESTED in round 1 (AC-23's scope, the catch-up ring untested, the snapshot exemption outside the rule, what is averaged), APPROVED in round 2. The design: the arrows' halo is a white copy of the path and head under the ink, 1.2 units wide (specs/_design/cells.md « Direction arrows », cell sheet and screens sheet redrawn); it changes how the halo is drawn, not how it looks, so the spec-writer's halo tests move from the filter to the stroke (042 AC-15, AC-16 tests and spec042_harness.py).
<!-- SECTION:NOTES:END -->
