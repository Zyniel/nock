---
id: B-056
title: The ipuz format leaves `content/grid-files.md`
status: Done
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:57:00Z'
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
- [x] #1 ipuz AC-1 (moved from grid-files AC-6)
- [x] #2 ipuz AC-2 (moved from grid-files AC-7)
- [x] #3 ipuz AC-3 (moved from grid-files AC-8)
- [x] #4 ipuz AC-4 (moved from grid-files AC-9)
- [x] #5 ipuz AC-5 (moved from grid-files AC-10)
- [x] #6 ipuz AC-6 (moved from grid-files AC-11)
- [x] #7 ipuz AC-7 (moved from grid-files AC-12)
- [x] #8 ipuz AC-8 (moved from grid-files AC-13)
- [x] #9 ipuz AC-9 (moved from grid-files AC-14)
- [x] #10 ipuz AC-10 (moved from grid-files AC-15)
- [x] #11 ipuz AC-11 (moved from grid-files AC-16)
- [x] #12 ipuz AC-12 (moved from grid-files AC-18)
- [x] #13 ipuz AC-13 (moved from grid-files AC-19)
- [x] #14 ipuz AC-14 (moved from grid-files AC-21)
- [x] #15 grid-files AC-3 (changed: cites content/ipuz.md rule 6, no behaviour change)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or assigned to @zyniel
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

Tests: the test-writer moved 57 functions to tests/test_ipuz_{structure,roundtrip,clues,compound,fields}.py, git mv for the four whole files; tests/grid_files_harness.py stays shared (the 004/005 tests import it). No implementer: no code changes, as the task says.

Review: CHANGES REQUESTED in round 1 (one stale docstring citation of grid-files AC-16 in test_spec_004_ac07, two small renames), APPROVE in round 2. Not taken: the harness docstring's 'the tests of the domain' (singular), too small for a draft. Full gate: one failure, test_spec_012_ac01 nickname browser test (chromium, E+combining acute), outside this change; the file passes alone (100 passed), so a flake under the load of three parallel sessions.

Pull request: https://github.com/Zyniel/nock/pull/93
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
The ipuz file format, its reader and its writer leave content/grid-files.md for the new domain content/ipuz.md (13.0 KB, 14 criteria); grid-files keeps 6.8 KB and 7 criteria. No behaviour or code change.
- ipuz AC-1 to AC-5, AC-12, AC-13 (were grid-files AC-6, 8, 9, 10, 18, 19, plus AC-7 as AC-2): tests/test_ipuz_structure.py (17), tests/test_ipuz_roundtrip.py (8).
- ipuz AC-6 to AC-10 (were AC-11 to AC-15): tests/test_ipuz_clues.py (13).
- ipuz AC-11 (was AC-16, keeps ← 004 AC-7): tests/test_ipuz_fields.py (6) and tests/test_spec_004_ac07_strict_inputs.py.
- ipuz AC-14 (was AC-21): tests/test_ipuz_compound.py (13).
- grid-files AC-3 changed only by a citation of ipuz rule 6 (← 005 AC-1 to AC-3); AC-17 and AC-20 stay with their tests.
- 57 test functions moved, bodies identical (the reviewer compared the ASTs); 178 tests before and after.
- Spec-checker APPROVED in round 2 (round 1: grid-files rule 3 had lost ipuz's rules, grids' Depends on had four files). Reviewer APPROVE in round 2 (round 1: a stale docstring citation).
- Decisions: ipuz rules 1-8 are old rules 5, 6, 7, 8, 9, 10, 12, 14, criteria in the old order; grid-files' Depends on drops library; grids depends on ipuz alone, its by-name citations of grid-files left to B-064; grid_files_harness.py stays shared by both domains.
- Full gate: green but for one browser test outside the change (test_spec_012_ac01, nickname with a combining accent), which passes alone: a flake under load.
<!-- SECTION:FINAL_SUMMARY:END -->
