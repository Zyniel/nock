---
id: B-058
title: The visual foundation leaves `client/shell.md`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T11:33:00Z'
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
1. Spec: client/shell.md → client/foundation.md (new), specs/_map.md; shell's realtime rule 19/20 citations → platform/reconnection.md rules 4/5.
2. Tests: tests/test_shell_*.py (3 files, ~11 functions) → tests/test_foundation_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs shell,foundation --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-057 (#98) merged. Spec-writer on Fable at high (new domain). The realtime citations at shell.md:67 and :70 go to reconnection rules 4 and 5 (B-057's map: realtime 19→reconnection 4, 20→5). If B-055 (held, PR #101) merges first, its map of shared components must follow any Code-section line that moves from shell to foundation; the lead reconciles whichever merges second. Base: origin/main f6a5666.
<!-- SECTION:NOTES:END -->
