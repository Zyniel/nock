---
id: B-061
title: The grid's viewport leaves `gameplay/board.md`
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T14:38:00Z'
labels:
  - domain:board
  - domain:viewport
  - domain:product
  - domain:foundation
  - domain:grids
  - domain:hints
milestone: m-3
dependencies: []
documentation:
  - specs/gameplay/board.md
priority: medium
ordinal: 16000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: gameplay/board → gameplay/viewport (new)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `gameplay/board.md` is 23.1 KB with 29 criteria, past the budget of `specs/_map.md`.
- In scope: rules 1 to 4 and 20 (the grid's drawing, cursors, fit, zoom, following the selection, hyphen edges) and AC-1 to AC-8 and AC-21 to AC-29 move to `gameplay/viewport.md`, about 10.7 KB and 18 criteria, with the cells half of AC-20 as a new viewport criterion citing 042 AC-20 (board's AC-20 keeps 044 AC-11). Both `tests/test_board_*.py` files move to `tests/test_viewport_*.py` and `board_harness.py` becomes `viewport_harness.py`; the pointers of 006 and 042 move; « (Chromium only, as AC-2) » in AC-2 and AC-28 drops (test mechanics). Rules 5 to 19 keep their numbers (`product.md` rule 12 cites board rule 15). A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; hud's « Depends on » wording (B-064). Not named `gameplay/grid.md`: `grid_` begins `grid_files_`.
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 viewport AC-9 (new, was board AC-21)
- [x] #2 board AC-21 (deleted, moved to viewport AC-9)
- [x] #3 viewport AC-10 (new, was board AC-22)
- [x] #4 board AC-22 (deleted, moved to viewport AC-10)
- [x] #5 viewport AC-11 (new, was board AC-23)
- [x] #6 board AC-23 (deleted, moved to viewport AC-11)
- [x] #7 viewport AC-12 (new, was board AC-24)
- [x] #8 board AC-24 (deleted, moved to viewport AC-12)
- [x] #9 viewport AC-13 (new, was board AC-25)
- [x] #10 board AC-25 (deleted, moved to viewport AC-13)
- [x] #11 viewport AC-14 (new, was board AC-26)
- [x] #12 board AC-26 (deleted, moved to viewport AC-14)
- [x] #13 viewport AC-15 (new, was board AC-27)
- [x] #14 board AC-27 (deleted, moved to viewport AC-15)
- [x] #15 viewport AC-16 (new, was board AC-28)
- [x] #16 board AC-28 (deleted, moved to viewport AC-16)
- [x] #17 viewport AC-17 (new, was board AC-29)
- [x] #18 board AC-29 (deleted, moved to viewport AC-17)
- [x] #19 viewport AC-1 (new, was board AC-1)
- [x] #20 board AC-1 (deleted, moved to viewport AC-1)
- [x] #21 viewport AC-2 (new, was board AC-2)
- [x] #22 board AC-2 (deleted, moved to viewport AC-2)
- [x] #23 viewport AC-3 (new, was board AC-3)
- [x] #24 board AC-3 (deleted, moved to viewport AC-3)
- [x] #25 viewport AC-4 (new, was board AC-4)
- [x] #26 board AC-4 (deleted, moved to viewport AC-4)
- [x] #27 viewport AC-5 (new, was board AC-5)
- [x] #28 board AC-5 (deleted, moved to viewport AC-5)
- [x] #29 viewport AC-6 (new, was board AC-6)
- [x] #30 board AC-6 (deleted, moved to viewport AC-6)
- [x] #31 viewport AC-7 (new, was board AC-7)
- [x] #32 board AC-7 (deleted, moved to viewport AC-7)
- [x] #33 viewport AC-8 (new, was board AC-8)
- [x] #34 board AC-8 (deleted, moved to viewport AC-8)
- [x] #35 viewport AC-18 (new: the cells half of board AC-20, ← 042 AC-20)
- [x] #36 board AC-20 (changed: keeps the keyboard half, ← 044 AC-11)
- [x] #37 board AC-9 (changed: a cross-reference to viewport AC-4)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: gameplay/board.md → gameplay/viewport.md (new), specs/_map.md.
2. Tests: tests/test_board_*.py → tests/test_viewport_*.py, board_harness.py → viewport_harness.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs board,viewport --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-058, B-059, B-060, B-062 (the other splits). Spec-writer on Fable at high (new domain). B-055's map of shared components (scripts/gate.py) follows if a component moves between Code sections (GridViewport.svelte, RoomPage.svelte): the lead's tooling commit. Base: origin/main bef13dc.

Lead: by-name citations whose referent is now viewport repointed here, one line each (as B-058 and B-062 did): _design/cells.md:45, product.md:276, client/foundation.md:177, content/grids.md:209, gameplay/hints.md:209-210; the task takes those labels. Viewport's Code line keeps the Chromium-only clause (product.md rule 10, a baseline). Spec-checker APPROVED in round 1. Its notes: three test_board_*.py files move, not two (test_board_pinch_third_finger.py keeps test_ac2_); presence.md:20 (the grid under board, by name) goes to B-064's list; board's Tests line naming test_board_* stays harmless. B-055's map of shared components: viewport's Code section names GridViewport.svelte and RoomPage.svelte (the lead's tooling commit).

Lead: review round 1 CHANGES REQUESTED (five web/src/ comments citing board rules 3 and 20, fixed by the implementer in b3090d9; board's Tests line still naming test_board_*, fixed by the spec-writer in 9f1d879); origin/main merged (7c2427b, no conflict). Round 2 APPROVE. presence.md:20 (« the grid » under board, by name) is for B-064, added to its list on the next board branch. Full gate green (8674 parallel, 162 serial).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Rules 1 to 4 and 20 of gameplay/board.md (the grid's drawing, cursors, fit, zoom, following the selection, hyphen edges) moved to the new domain gameplay/viewport.md as rules 1 to 5, text unchanged but for cross-references and the « Chromium only » test notes. board.md: 13.6 KB, 12 criteria (rules 5-19 keep their numbers); viewport.md: 11.9 KB, 18 criteria. No behaviour or code change.

Criteria and their tests (board → viewport):
- viewport AC-1 to AC-8 (same numbers): pointers ← 006, 042; AC-2 also tests/test_viewport_pinch_third_finger.py
- viewport AC-9, AC-10 (were AC-21, AC-22): tests/test_viewport_hyphen_edges.py
- viewport AC-11 to AC-17 (were AC-23 to AC-29): tests/test_viewport_zoom_follow.py
- viewport AC-18 (new, the cells half of board AC-20): ← 042 AC-20
- board AC-20 keeps the keyboard half (← 044 AC-11); board AC-9 cites viewport AC-4.
3 test files and board_harness.py (now viewport_harness.py) moved and renamed, bodies unchanged.

Also: five by-name citations of what is now viewport repointed (_design/cells.md, product.md:276, foundation.md:177, grids.md:209, hints.md:209-210); _map.md row, split cell, glossary « viewport »; B-055's map of shared components gains viewport under GridViewport.svelte and RoomPage.svelte.
Spec-checker: APPROVED in round 1. Reviewer: CHANGES REQUESTED in round 1 (five stale comments in web/src/, board's Tests line), APPROVE in round 2.
Decisions: three test files moved (the task said two); the by-name repoints; viewport's Code line keeps the Chromium-only clause (product.md rule 10). Left for B-064: presence.md:20.
Full gate: green (8674 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
