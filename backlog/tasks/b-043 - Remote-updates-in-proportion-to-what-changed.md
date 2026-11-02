---
id: B-043
title: Remote updates in proportion to what changed
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T00:06:00Z'
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
- [x] #1 shell AC-22 (new): a pong, a chat_message and a same-place selection_moved mutate no node of the grid
- [x] #2 shell AC-23 (new): a remote letter, and its flash, mutate no node of the grid outside its cell
- [x] #3 shell AC-24 (new): a cursor move mutates only the cells it leaves and enters, and their tints
- [x] #4 shell AC-25 (new): a pinch mutates no cell, and the triangle takes the new side
- [x] #5 shell AC-26 (new): rule 23's echo holds on FX-02 with 7 others typing
- [x] #6 shell AC-27 (new): a frame that changes no cell costs at most 2 ms of main-thread time on average
- [x] #7 shell AC-28 (new): a catch-up ring mutates no node of the grid outside its cell
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
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

Implementer: AC-27 now 0.28 to 0.40 ms per relayed selection (3.05 ms before). Lead: 041 AC-15's arrow test counted one path per arrow, which the halo's white copy contradicts: the test-writer makes it read the ink path. Hyphen edges redrew on a pinch (their dashes sized from the cell side): sized from a variable on .grid too, as rule 18 allows no exception. The selected state held as one value per cell, beyond remote frames, accepted: it serves AC-26's echo.

Reviewer: APPROVE in round 1. Taken: the helpers' docstrings of the two new test files. Not taken, as follow-up drafts: no test guards the reuse of previous values in remotesByCell (a pace for frames that change a cell); every cell still builds a new shown object when any pending edit changes, cheap, for B-049's cell components.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
A remote update now redraws only the cells whose drawing it changes (shell rule 18), and a frame that changes no cell costs a tenth of what it did.

Criteria (`specs/client/shell.md`):
- AC-22: `tests/test_shell_remote_updates.py::test_ac22_a_pong_a_chat_message_and_a_selection_in_place_mutate_no_node` (guard).
- AC-23: `test_ac23_bobs_letter_in_an_empty_cell_mutates_only_that_cell`, `test_ac23_bobs_letter_over_mine_mutates_only_that_cell_through_its_flash` (guards).
- AC-24: `test_ac24_bobs_cursor_moving_along_his_word_mutates_only_the_two_cells`, `test_ac24_bob_turning_down_mutates_only_the_cells_of_tamis_and_mime` (guards).
- AC-25: `test_ac25_a_pinch_from_zoom_1_to_1_5_mutates_no_cell` (failed first: a style write on all 180 cells), `test_ac25_after_the_pinch_bobs_triangle_has_the_leg_of_the_new_side` (Chromium).
- AC-26: `tests/test_shell_remote_pace.py::test_ac26_the_local_echo_holds_while_seven_other_players_type` (serial, reference phone).
- AC-27: `test_ac27_a_selection_bob_already_holds_costs_at_most_2_ms_of_main_thread` (serial, reference phone): 3.05 ms per frame before, 0.28 to 0.40 ms after.
- AC-28: `test_ac28_a_catch_up_naming_one_cell_mutates_only_it_until_its_ring_ends` (guard).
- The arrows' halo (`specs/_design/cells.md` « Direction arrows », board AC-7 ← 042 AC-15): `tests/test_spec_042_ac15_ac16_arrows.py::test_ac15_each_arrow_has_a_thin_white_halo`, edited in place; 041 AC-15's ink arrow test (shell AC-19) reads the ink path.

The mutation counts pass on the old code too, Svelte skipping writes that change nothing: they stay as guards, and AC-27 measures the fix itself. `tests/test_shell_remote_pace.py` is in `SERIAL_TEST_FILES`.

Reviewer: APPROVE in round 1. Taken: the new test files' helper docstrings. Not taken, as follow-up drafts: no test guards the reuse of previous values in `remotesByCell` (a pace for frames that do change a cell); every cell still builds a new `shown` object when any pending edit changes, stopped before the DOM, for B-049's cell components.

Lead's decisions: 7 other players plus the measured one (a room holds 8); the measured player types 250 ms apart, as product AC-13; the fix measured by main-thread time (at most 2 ms per no-op frame, on average over 100 relayed `select_cell`); the halo 1.2 units of the arrow's box; rule 18 asks nothing of a snapshot; hyphen dashes sized from `.grid` too, since rule 18 allows a pinch no cell change; the selected state held as one value per cell, which serves AC-26's echo. The spec-checker asked for changes once (AC-23's scope, the catch-up ring untested, the snapshot exemption) and approved the second round.

Flagged: the arrows' halo is drawn as a stroked white copy under the ink instead of two drop-shadow filters (the cell sheet and the screens sheet redrawn); its look should match, and the pixel tests of the hyphen edges pass in the three engines. `shell.md` is at 28 criteria, over the budget of `specs/_map.md`: its split is a follow-up for the human. The pace file lifts the room's 6 s silence timeout for its simulated players, which send no pings.

Code: `web/src/lib/remoteSelections.ts` (`nextCursors` keeps its array; `remotesByCell`, `NO_REMOTES`), `roomSession.ts` (`latestPendingEdits`, `shownCellWith`, `letterCellIndex`; a selection in place keeps its object), `GridViewport.svelte` (per-cell maps of remotes, flashes, caught-up cells and pending edits; `--triangle` and the hyphen dashes on `.grid`; the halo), `HyphenEdge.svelte` and `gridLayout.ts` (`dashesImage`), `RoomPage.svelte` (`letterCellAt`, `filledWords`, `isWordFullShown` on the index).
<!-- SECTION:FINAL_SUMMARY:END -->
