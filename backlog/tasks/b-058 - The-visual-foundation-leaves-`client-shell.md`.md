---
id: B-058
title: The visual foundation leaves `client/shell.md`
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T13:09:00Z'
labels:
  - domain:shell
  - domain:foundation
milestone: m-3
dependencies:
  - B-057
documentation:
  - specs/client/shell.md
priority: medium
ordinal: 13000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: client/shell → client/foundation (new)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `client/shell.md` is 20 KB with 28 criteria, past the budget of `specs/_map.md`.
- In scope: rules 11 to 16 and 18 (state lines, motion, tokens, fonts, icons, components, the grid's focus ring, what a frame redraws) and AC-13, AC-16 to AC-28 move to `client/foundation.md`, about 9 KB and 14 criteria; rule 17 (the brand) stays, cited by hud and library. The three `tests/test_shell_*.py` files move to `tests/test_foundation_*.py` (about 11 functions); the pointers of 041, 048 AC-13 and 040 AC-26 move; the « Chromium only » notes of AC-25 to AC-27 drop (test mechanics). Shell's citations of realtime rules 19 and 20 point to `platform/reconnection.md`. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; `admin/operations.md` (B-063).
- Screens: none (`specs/_design/foundation.md` keeps its name, as `client/room.md` and `_design/room.md` already share one).
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 foundation AC-1 (new, was shell AC-13)
- [x] #2 shell AC-13 (deleted, moved to foundation AC-1)
- [x] #3 foundation AC-2 (new, was shell AC-16)
- [x] #4 shell AC-16 (deleted, moved to foundation AC-2)
- [x] #5 foundation AC-3 (new, was shell AC-17)
- [x] #6 shell AC-17 (deleted, moved to foundation AC-3)
- [x] #7 foundation AC-4 (new, was shell AC-18)
- [x] #8 shell AC-18 (deleted, moved to foundation AC-4)
- [x] #9 foundation AC-5 (new, was shell AC-19)
- [x] #10 shell AC-19 (deleted, moved to foundation AC-5)
- [x] #11 foundation AC-6 (new, was shell AC-20)
- [x] #12 shell AC-20 (deleted, moved to foundation AC-6)
- [x] #13 foundation AC-7 (new, was shell AC-21)
- [x] #14 shell AC-21 (deleted, moved to foundation AC-7)
- [x] #15 foundation AC-8 (new, was shell AC-22)
- [x] #16 shell AC-22 (deleted, moved to foundation AC-8)
- [x] #17 foundation AC-9 (new, was shell AC-23)
- [x] #18 shell AC-23 (deleted, moved to foundation AC-9)
- [x] #19 foundation AC-10 (new, was shell AC-24)
- [x] #20 shell AC-24 (deleted, moved to foundation AC-10)
- [x] #21 foundation AC-11 (new, was shell AC-25)
- [x] #22 shell AC-25 (deleted, moved to foundation AC-11)
- [x] #23 foundation AC-12 (new, was shell AC-26)
- [x] #24 shell AC-26 (deleted, moved to foundation AC-12)
- [x] #25 foundation AC-13 (new, was shell AC-27)
- [x] #26 shell AC-27 (deleted, moved to foundation AC-13)
- [x] #27 foundation AC-14 (new, was shell AC-28)
- [x] #28 shell AC-28 (deleted, moved to foundation AC-14)
- [x] #29 foundation AC-15 (new, was shell AC-32)
- [x] #30 shell AC-32 (deleted, moved to foundation AC-15)
- [x] #31 foundation AC-16 (new, was shell AC-33)
- [x] #32 shell AC-33 (deleted, moved to foundation AC-16)
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
1. Spec: client/shell.md → client/foundation.md (new), specs/_map.md; shell's realtime rule 19/20 citations → platform/reconnection.md rules 4/5.
2. Tests: tests/test_shell_*.py (3 files, ~11 functions) → tests/test_foundation_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs shell,foundation --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-057 (#98) merged. Spec-writer on Fable at high (new domain). The realtime citations at shell.md:67 and :70 go to reconnection rules 4 and 5 (B-057's map: realtime 19→reconnection 4, 20→5). If B-055 (held, PR #101) merges first, its map of shared components must follow any Code-section line that moves from shell to foundation; the lead reconciles whichever merges second. Base: origin/main f6a5666.

Lead: shell rule 21 and AC-32/AC-33 (font subsets, the room page's preload), added after the task was written, move with the fonts (foundation rule 5, AC-15/AC-16): one coherent part, so foundation has 16 criteria and shell 17, and tests/test_shell_fonts.py moves too. product.md:286 (Reduced motion, a file name in Out of scope) repointed to foundation, as B-062 did for product's route cells; results.md:300 (by name) left for B-064. Spec-checker APPROVED in round 1; its minor note (foundation's Look cell in _map.md could add pages) left: the column already lists only the main files. shell's Code section no longer names GridViewport.svelte (foundation does): B-055's map must follow when both are on main.

Lead: review round 1 CHANGES REQUESTED (ten code comments in web/src/ citing moved shell rules 16, 18, 21), fixed by the implementer in e2a58d6; suggestions left (foundation's font tests import shell_harness; shorter section rulers). origin/main merged (b5b0733, no conflict); B-055's map of shared components: GridViewport.svelte moves from shell to foundation (5977a1d, the lead's tooling commit). Round 2 APPROVE. Full gate green (8674 parallel, 162 serial).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Rules 11 to 16, 18 and 21 of client/shell.md (state lines, motion, tokens, fonts and their subsets, icons, components, the grid's focus ring, what a frame redraws) moved to the new domain client/foundation.md as rules 1 to 8, text unchanged but for cross-references and three « Chromium » test notes. shell.md: 13.2 KB, 17 criteria (rules 1-10, 17, 19, 20 keep their numbers); foundation.md: 10.0 KB, 16 criteria. No behaviour or code change.

Criteria and their tests (shell → foundation):
- foundation AC-1 to AC-6 (were AC-13, AC-16 to AC-20): pointers ← 048 AC-13, 041 AC-1 to AC-21, 040 AC-26
- foundation AC-7 (was AC-21): tests/test_foundation_grid_focus_ring.py
- foundation AC-8 to AC-11, AC-14 (were AC-22 to AC-25, AC-28): tests/test_foundation_remote_updates.py
- foundation AC-12, AC-13 (were AC-26, AC-27): tests/test_foundation_remote_pace.py (serial)
- foundation AC-15, AC-16 (were AC-32, AC-33): tests/test_foundation_fonts.py
16 test functions in 4 files moved and renamed, bodies unchanged.

Also: shell rule 6's realtime rules 19/20 name platform/reconnection.md rules 4/5; product.md's reduced-motion line names foundation; _map.md row, split cell, glossary « foundation, state line ».
Spec-checker: APPROVED in round 1 (minor note on foundation's Look cell left). Reviewer: CHANGES REQUESTED in round 1 (stale rule numbers in ten web/src/ comments, fixed), APPROVE in round 2.
Decisions: rule 21 and AC-32/AC-33 (added after the task was written) moved with the fonts; product.md:286 repointed; results.md:300 left for B-064; SERIAL_TEST_FILES and B-055's map follow the move.
Full gate: green (8674 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
