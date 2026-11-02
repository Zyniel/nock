---
id: B-062
title: The erasure leaves `account/account.md`
status: In Progress
assignee: []
created_date: '2026-11-01T16:44:00Z'
updated_date: '2026-11-02T10:45:00Z'
labels:
  - domain:account
  - domain:erasure
  - domain:joining
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 erasure AC-1 (new, was account AC-3)
- [ ] #2 account AC-3 (deleted, moved to erasure AC-1)
- [ ] #3 erasure AC-2 (new, was account AC-14)
- [ ] #4 account AC-14 (deleted, moved to erasure AC-2)
- [ ] #5 erasure AC-3 (new, was account AC-15)
- [ ] #6 account AC-15 (deleted, moved to erasure AC-3)
- [ ] #7 erasure AC-4 (new, was account AC-19)
- [ ] #8 account AC-19 (deleted, moved to erasure AC-4)
- [ ] #9 erasure AC-5 (new, was account AC-20)
- [ ] #10 account AC-20 (deleted, moved to erasure AC-5)
- [ ] #11 erasure AC-6 (new, was account AC-21)
- [ ] #12 account AC-21 (deleted, moved to erasure AC-6)
- [ ] #13 erasure AC-7 (new, was account AC-22)
- [ ] #14 account AC-22 (deleted, moved to erasure AC-7)
- [ ] #15 erasure AC-8 (new, was account AC-24)
- [ ] #16 account AC-24 (deleted, moved to erasure AC-8)
- [ ] #17 erasure AC-9 (new, was account AC-25)
- [ ] #18 account AC-25 (deleted, moved to erasure AC-9)
- [ ] #19 erasure AC-10 (new, was account AC-26)
- [ ] #20 account AC-26 (deleted, moved to erasure AC-10)
- [ ] #21 erasure AC-11 (new, was account AC-27)
- [ ] #22 account AC-27 (deleted, moved to erasure AC-11)
- [ ] #23 erasure AC-12 (new, was account AC-28)
- [ ] #24 account AC-28 (deleted, moved to erasure AC-12)
- [ ] #25 erasure AC-13 (new, was account AC-29)
- [ ] #26 account AC-29 (deleted, moved to erasure AC-13)
- [ ] #27 erasure AC-14 (new, was account AC-30)
- [ ] #28 account AC-30 (deleted, moved to erasure AC-14)
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
1. Spec: account/account.md → account/erasure.md (new), specs/_map.md; the pointers of 029 and 033 move.
2. Tests: about 31 functions in 9 files move to tests/test_erasure_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs account,erasure --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started in parallel with B-048's review (different domains). Spec-writer on Fable at high (new domain). Base: origin/main 4005dc3.

Lead: the by-name citations of moved content in product.md (routes table owner cells, core flow 8) and joining.md rule 3 (« Ancien joueur ») are repointed here, as the pitch's answer for B-059's route cell; the task takes domain:joining (B-059 not started). By-number citations left to their tasks: operations.md:49/51/69 (B-063); host.md:99/129/136/138, lifetime.md:85, results.md:153, library.md:53 (B-064). Spec-checker APPROVED in round 1. Its note: account AC-2, AC-10, AC-13 prove behaviour whose rules are now erasure rules 3 and 4, and account's Depends on (three files, the template's maximum) cannot list erasure; left, the out-of-scope line links them.
<!-- SECTION:NOTES:END -->
