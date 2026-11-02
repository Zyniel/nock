---
id: B-062
title: The erasure leaves `account/account.md`
status: To Do
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:account
  - domain:erasure
milestone: m-3
dependencies: []
documentation:
  - specs/account/account.md
priority: medium
ordinal: 17000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: account/account → account/erasure (new)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `account/account.md` is 31.7 KB with 34 criteria, twice the budget of `specs/_map.md`.
- In scope: rules 18 to 24 and 26 to 28 (erasure, what is kept, history records, grid progress) and AC-3, AC-14, AC-15, AC-19 to AC-22, AC-24 to AC-30 move to `account/erasure.md`, about 13.9 KB and 14 criteria; about 31 test functions in 9 files move to `tests/test_erasure_*.py` (still importing `account_harness.py`); the pointers of 029 and 033 move; account's « Out of scope » points to erasure for the files that cite the moved rules. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code; account's sheet and page, the next cut if account grows (account stays at 20 criteria and about 18.8 KB; a new file must not be named `account-*`); the citations in host, lifetime, results and library (B-064); operations' citations (B-063).
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
