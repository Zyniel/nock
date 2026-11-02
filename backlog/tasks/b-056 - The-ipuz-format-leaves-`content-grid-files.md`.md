---
id: B-056
title: The ipuz format leaves `content/grid-files.md`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:35:00Z'
labels:
  - domain:grid-files
  - domain:ipuz
  - domain:grids
milestone: m-3
dependencies: []
documentation:
  - specs/content/grid-files.md
  - specs/content/grids.md
priority: medium
ordinal: 11000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: content/grid-files → content/ipuz (new); content/grids (cites rules 8 and 12, near its lines 75 and 140)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `content/grid-files.md` is 18.7 KB with 21 criteria, past the budget of `specs/_map.md`.
- In scope: the file format (rules 5 to 10, 12 and 14: the ipuz object, the mapping, strict reading, arrows, breaks, difficulty and date, the reader's added checks, the writer) and AC-6 to AC-16, AC-18, AC-19, AC-21 move to `content/ipuz.md`, about 13 KB and 14 criteria; rule 11 and AC-17 stay (cited by `content/library.md`). About 57 test functions move to `tests/test_ipuz_*.py` (`test_grid_files_fields.py` splits: AC-16 goes, AC-17 stays); pointer 004 AC-7 moves. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; trimming the sample lists.
- Order: first of the milestone: the most renames, it proves the procedure.
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 ipuz AC-1 (moved from grid-files AC-6)
- [ ] #2 ipuz AC-2 (moved from grid-files AC-7)
- [ ] #3 ipuz AC-3 (moved from grid-files AC-8)
- [ ] #4 ipuz AC-4 (moved from grid-files AC-9)
- [ ] #5 ipuz AC-5 (moved from grid-files AC-10)
- [ ] #6 ipuz AC-6 (moved from grid-files AC-11)
- [ ] #7 ipuz AC-7 (moved from grid-files AC-12)
- [ ] #8 ipuz AC-8 (moved from grid-files AC-13)
- [ ] #9 ipuz AC-9 (moved from grid-files AC-14)
- [ ] #10 ipuz AC-10 (moved from grid-files AC-15)
- [ ] #11 ipuz AC-11 (moved from grid-files AC-16)
- [ ] #12 ipuz AC-12 (moved from grid-files AC-18)
- [ ] #13 ipuz AC-13 (moved from grid-files AC-19)
- [ ] #14 ipuz AC-14 (moved from grid-files AC-21)
- [ ] #15 grid-files AC-3 (changed: cites content/ipuz.md rule 6, no behaviour change)
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
Specs: specs/content/grid-files.md -> specs/content/ipuz.md (new), specs/content/grids.md, specs/_map.md
Tests: tests/test_grid_files_*.py -> tests/test_ipuz_*.py (moved criteria renamed), pointer 004 AC-7 moves
Quick gate: uv run python scripts/gate.py --specs grid-files,ipuz,grids --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
The pitch's merge settled the architecture options (the Plan agent's split, the lead's pick), so no new Plan run: the spec-writer runs on Fable at high effort.

Spec change: Fable spec-writer, spec-checker APPROVED in its second round. Decisions: ipuz rules 1-8 are old grid-files rules 5,6,7,8,9,10,12,14 and its AC-1..14 old AC-6..16,18,19,21, in order; grid-files' Depends on drops content/library.md to stay at three files (library already depends on grid-files); grid-files AC-3 cites ipuz rule 6 for the author refusal; grid-files rule 3 says a file breaking ipuz's rules also stops the server (the checker's finding: 'these rules' lost the format rules); grids' Depends on names content/ipuz.md alone (three files), its by-name citations of grid-files left to B-064; ipuz AC-10 names content/grids.md rule 6 explicitly where bare 'rule 6' would now mean ipuz's own.
<!-- SECTION:NOTES:END -->
