---
id: B-061
title: The grid's viewport leaves `gameplay/board.md`
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:board
  - domain:viewport
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
