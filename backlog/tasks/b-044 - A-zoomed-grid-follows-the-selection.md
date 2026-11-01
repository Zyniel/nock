---
id: B-044
title: A zoomed grid follows the selection
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-01T22:41:00Z'
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 board AC-23 (new): zoomed, typing along an across word scrolls across only, one cell of margin
- [x] #2 board AC-24 (new): zoomed, ArrowDown and Shift+Tab scroll the least that shows the cell with its margin
- [x] #3 board AC-25 (new): zoomed, a cell already in view, or a tap on a cut cell, scrolls nothing
- [x] #4 board AC-26 (new): at zoom 1, typing, Tab and the arrows scroll nothing
- [x] #5 board AC-27 (new): a viewport under three cells on an axis centres the selected cell
- [x] #6 board AC-28 (new): after a pan, ⇄, a pinch and the keyboard hidden do not bring the cell back
- [x] #7 board AC-29 (new): zoomed, a tap on a clue scrolls like a key
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
Spec: specs/gameplay/board.md (rule 3: while zoomed, a change of selection scrolls the grid the least needed to show the selected cell, with a margin of one cell).
Tests: tests/test_board_zoom_follow.py.
Quick gate: uv run python scripts/gate.py --specs board,product --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: base commit ffc9b81. Open question 1 (the margin kept around the cell): A, one cell, the lead's default. The quick gate is widened with product because the change touches GridViewport.svelte.

Lead, on the spec-writer's questions: (1) only a change of selected cell scrolls; a pinch or a resize never does (A: a literal reading would undo every pinch). (2) A tap on a clue scrolls like a key (A); only a tap on a letter cell scrolls nothing. (3) A viewport smaller than the cell and two margins centres the cell on that axis (A). (4) The scroll is at once, no animation (A: fast typing and deterministic tests). board.md is at 27 criteria, over the 20 of _map.md: the split (the in-app keyboard as its own domain file) is an architecture decision for the human, recorded as a follow-up draft.

Spec-checker: CHANGES REQUESTED in round 1 (pinch and ⇄ untested, AC-23's start condition, AC-27's reachability, the least vertical scroll, wording), APPROVED in round 2. Its non-blocking notes: AC-29's start (OREIL already typed with the viewport at the top-left corner) is for the test-writer to set up, by typing then panning back or a snapshot.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
While zoomed, a change of selected cell now scrolls the grid's viewport the least that shows the cell with one cell of margin (board rule 3).

Criteria (`specs/gameplay/board.md`, tests in `tests/test_board_zoom_follow.py`):
- AC-23: `test_ac23_typing_oreille_scrolls_across_only_to_the_cell_after_the_selected_one` (in-app keys and physical keyboard): typing along an across word scrolls across only, one cell of margin.
- AC-24: `test_ac24_arrow_down_column_zero_scrolls_down_only_one_cell_below_the_selected`, `test_ac24_shift_tab_selects_echec_and_scrolls_to_the_grid_bottom_and_shows_16_7`: the least scroll down, clamped at the grid's edge.
- AC-25: `test_ac25_a_cell_in_view_with_its_margin_and_a_tap_on_a_cut_cell_scroll_nothing` (guard).
- AC-26: `test_ac26_at_zoom_1_typing_shift_tab_and_arrows_leave_everything_unscrolled` (guard, three engines).
- AC-27: `test_ac27_a_viewport_of_two_and_a_half_cells_centres_the_cell_left_to_right`.
- AC-28: `test_ac28_after_a_pan_swap_pinch_and_hidden_keyboard_never_scroll_to_the_cell` (guard).
- AC-29: `test_ac29_a_tap_on_the_clue_selects_1_7_and_scrolls_across_to_1_8`.

The zoomed tests are Chromium-only (the zoom comes from AC-2's CDP pinch). AC-25, AC-26 and AC-28 pass without the feature: they guard against a follower that scrolls when it must not.

Reviewer: APPROVE in round 1. Taken: the zoom-follow helpers' docstrings and spec006_harness's reflowed docstring. Not taken, as follow-up drafts: the scroll backwards (left or up) has no criterion; "(Chromium only, as AC-2)" in AC-2 and AC-28 is test mechanics, for board.md's split.

Lead's decisions: a margin of one cell (the task's default); only a change of selected cell scrolls, a pinch, a pan, a resize, a refit, the keyboard and ⇄ never do (a trigger on the cell size would undo every pinch); a tap on a clue scrolls like a key; centring on an axis too small for the cell and its margins; an instant scroll. The spec-checker asked for changes once (pinch and ⇄ untested, AC-23's start, AC-27's reachability, the least vertical scroll) and approved the second round.

Flagged: `board.md` is at 29 criteria and 23 KB, over the budget of `specs/_map.md`; its split (the in-app keyboard as its own domain) is an architecture decision for the human, recorded as a follow-up. The pinch and pan helpers moved unchanged from spec 006's AC-1 tests into `tests/spec006_harness.py`.

Code: `web/src/lib/GridViewport.svelte` (an effect keyed on the selected cell, the rest read untracked; `tappedCellKey` from the tap handler), `web/src/lib/gridLayout.ts` (`scrollShowingCell`).
<!-- SECTION:FINAL_SUMMARY:END -->
