---
id: B-056
title: The ipuz format leaves `content/grid-files.md`
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:16:00Z'
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or assigned to @zyniel
<!-- DOD:END -->
