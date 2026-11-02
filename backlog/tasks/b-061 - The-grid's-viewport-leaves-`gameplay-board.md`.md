---
id: B-061
title: The grid's viewport leaves `gameplay/board.md`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T13:49:00Z'
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
- [ ] #1 viewport AC-9 (new, was board AC-21)
- [ ] #2 board AC-21 (deleted, moved to viewport AC-9)
- [ ] #3 viewport AC-10 (new, was board AC-22)
- [ ] #4 board AC-22 (deleted, moved to viewport AC-10)
- [ ] #5 viewport AC-11 (new, was board AC-23)
- [ ] #6 board AC-23 (deleted, moved to viewport AC-11)
- [ ] #7 viewport AC-12 (new, was board AC-24)
- [ ] #8 board AC-24 (deleted, moved to viewport AC-12)
- [ ] #9 viewport AC-13 (new, was board AC-25)
- [ ] #10 board AC-25 (deleted, moved to viewport AC-13)
- [ ] #11 viewport AC-14 (new, was board AC-26)
- [ ] #12 board AC-26 (deleted, moved to viewport AC-14)
- [ ] #13 viewport AC-15 (new, was board AC-27)
- [ ] #14 board AC-27 (deleted, moved to viewport AC-15)
- [ ] #15 viewport AC-16 (new, was board AC-28)
- [ ] #16 board AC-28 (deleted, moved to viewport AC-16)
- [ ] #17 viewport AC-17 (new, was board AC-29)
- [ ] #18 board AC-29 (deleted, moved to viewport AC-17)
- [ ] #19 viewport AC-1 (new, was board AC-1)
- [ ] #20 board AC-1 (deleted, moved to viewport AC-1)
- [ ] #21 viewport AC-2 (new, was board AC-2)
- [ ] #22 board AC-2 (deleted, moved to viewport AC-2)
- [ ] #23 viewport AC-3 (new, was board AC-3)
- [ ] #24 board AC-3 (deleted, moved to viewport AC-3)
- [ ] #25 viewport AC-4 (new, was board AC-4)
- [ ] #26 board AC-4 (deleted, moved to viewport AC-4)
- [ ] #27 viewport AC-5 (new, was board AC-5)
- [ ] #28 board AC-5 (deleted, moved to viewport AC-5)
- [ ] #29 viewport AC-6 (new, was board AC-6)
- [ ] #30 board AC-6 (deleted, moved to viewport AC-6)
- [ ] #31 viewport AC-7 (new, was board AC-7)
- [ ] #32 board AC-7 (deleted, moved to viewport AC-7)
- [ ] #33 viewport AC-8 (new, was board AC-8)
- [ ] #34 board AC-8 (deleted, moved to viewport AC-8)
- [ ] #35 viewport AC-18 (new: the cells half of board AC-20, ← 042 AC-20)
- [ ] #36 board AC-20 (changed: keeps the keyboard half, ← 044 AC-11)
- [ ] #37 board AC-9 (changed: a cross-reference to viewport AC-4)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
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
<!-- SECTION:NOTES:END -->
