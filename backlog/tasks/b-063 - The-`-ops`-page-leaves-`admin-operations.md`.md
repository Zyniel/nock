---
id: B-063
title: The `/ops` page leaves `admin/operations.md`
status: Done
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T17:34:00Z'
labels:
  - domain:operations
  - domain:ops-page
  - domain:overrides
  - domain:viewport
milestone: m-3
dependencies:
  - B-062
documentation:
  - specs/admin/operations.md
  - specs/admin/overrides.md
priority: medium
ordinal: 18000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: admin/operations → admin/ops-page (new); admin/overrides (cites rules 16 and 18, near its lines 95 and 109)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `admin/operations.md` is 23.2 KB with 25 criteria, past the budget of `specs/_map.md`.
- In scope: rules 14 to 19 (the replay's edits and the page: the token form, its states, the dashboard card, the period chips, the replay card) and AC-11 to AC-20 move to `admin/ops-page.md`, about 9.7 KB and 10 criteria; the pointers of 038 AC-7 to AC-9 and 048 AC-6 to AC-12 move (no test function is renamed); rule 7's « rule 15's replay » is edited in place; operations' citations of account rules 18, 20, 22, 26 and 27 point to `account/erasure.md`. A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code.
- Screens: none.
- Open questions: none.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 ops-page AC-1 (new, was operations AC-11)
- [x] #2 operations AC-11 (deleted, moved to ops-page AC-1)
- [x] #3 ops-page AC-2 (new, was operations AC-12)
- [x] #4 operations AC-12 (deleted, moved to ops-page AC-2)
- [x] #5 ops-page AC-3 (new, was operations AC-13)
- [x] #6 operations AC-13 (deleted, moved to ops-page AC-3)
- [x] #7 ops-page AC-4 (new, was operations AC-14)
- [x] #8 operations AC-14 (deleted, moved to ops-page AC-4)
- [x] #9 ops-page AC-5 (new, was operations AC-15)
- [x] #10 operations AC-15 (deleted, moved to ops-page AC-5)
- [x] #11 ops-page AC-6 (new, was operations AC-16)
- [x] #12 operations AC-16 (deleted, moved to ops-page AC-6)
- [x] #13 ops-page AC-7 (new, was operations AC-17)
- [x] #14 operations AC-17 (deleted, moved to ops-page AC-7)
- [x] #15 ops-page AC-8 (new, was operations AC-18)
- [x] #16 operations AC-18 (deleted, moved to ops-page AC-8)
- [x] #17 ops-page AC-9 (new, was operations AC-19)
- [x] #18 operations AC-19 (deleted, moved to ops-page AC-9)
- [x] #19 ops-page AC-10 (new, was operations AC-20)
- [x] #20 operations AC-20 (deleted, moved to ops-page AC-10)
- [x] #21 ops-page AC-11 (new, was operations AC-26)
- [x] #22 operations AC-26 (deleted, moved to ops-page AC-11)
- [x] #23 ops-page AC-12 (new, was operations AC-27)
- [x] #24 operations AC-27 (deleted, moved to ops-page AC-12)
- [x] #25 ops-page AC-13 (new, was operations AC-28)
- [x] #26 operations AC-28 (deleted, moved to ops-page AC-13)
- [x] #27 ops-page AC-14 (new, was operations AC-29)
- [x] #28 operations AC-29 (deleted, moved to ops-page AC-14)
- [x] #29 ops-page AC-15 (new, was operations AC-30)
- [x] #30 operations AC-30 (deleted, moved to ops-page AC-15)
- [x] #31 ops-page AC-16 (new, was operations AC-31)
- [x] #32 operations AC-31 (deleted, moved to ops-page AC-16)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
- [x] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: admin/operations.md → admin/ops-page.md (new), admin/overrides.md citations, specs/_map.md; operations' account rule citations → account/erasure.md.
2. Tests: the domain tests of the moved criteria → tests/test_ops_page_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs operations,ops-page,overrides --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead (2026-11-02): started after B-047 (#109, which held domain:operations and added operations AC-31 to rule 19, the replay) and B-062 merged. Spec-writer on Fable at high (new domain). Account → erasure rule map (B-062): 18→1, 19→2, 20→3, 21→4, 26→5, 27→6, 28→7, 22→8, 23→9, 24→10. Base: origin/main b9871e7.

Lead: operations AC-26 to AC-31 (added after the task, all the page and its replay) moved with it: ops-page 16 criteria, operations 15. By-name repoints kept: overrides.md, gameplay/viewport.md Out of scope (the task takes domain:viewport), _settings.md:24. Repoints in server.md:269-270, product.md:44-45 and :60, results.md:136, shell.md:225 were reverted: B-064 (in progress) holds those domains and takes them after this task merges. Spec-checker APPROVED in round 1; its minor notes left (« latency measured in the browsers » now in ops-page's Out of scope; ops-page named inside overrides' operations bullet rather than its own, Depends on being at three).

Lead: reviewer APPROVE in round 1 (it also ran the nine test files of the moved criteria directly: 165 passed); its three suggestions taken (762e765: a lost bullet dash and the browser latency exclusion back in operations; 163dcb0: harness comments). Full gate green (8704 parallel, 162 serial).

Pull request: https://github.com/Zyniel/nock/pull/110
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Rules 14 to 19 of admin/operations.md (the replay's edits and the /ops page: the token form, its states, the dashboard card, the period chips, the replay card) moved to the new domain admin/ops-page.md as rules 1 to 6, text unchanged but for cross-references. operations.md: 14.7 KB, 15 criteria (rules 1-13, 20 keep their numbers); ops-page.md: 11.7 KB, 16 criteria. No behaviour or code change.

Criteria and their tests (operations → ops-page):
- ops-page AC-1 to AC-10 (were AC-11 to AC-20): pointers ← 038 AC-7 to AC-9, 048 AC-6 to AC-12
- ops-page AC-11 to AC-16 (were AC-26 to AC-31): tests/test_ops_page_states.py (renamed from test_operations_page.py, bodies unchanged)

Also: rule 7 names ops-page rule 2's replay; operations' account citations name account/erasure.md (rules 8, 5, 6, 1, 3); overrides' citations of rules 16 and 18 name ops-page rules 3 and 5; gameplay/viewport.md and _settings.md repointed by name; _map.md row, split cell, glossary « ops page, replay ».
Spec-checker: APPROVED in round 1. Reviewer: APPROVE in round 1; three suggestions taken.
Decisions: AC-26 to AC-31 (added after the task) moved too; five by-name repoints in server.md, product.md, results.md and shell.md left to B-064, which held those domains.
Full gate: green (8704 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
