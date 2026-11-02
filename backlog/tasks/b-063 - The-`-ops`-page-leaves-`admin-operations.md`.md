---
id: B-063
title: The `/ops` page leaves `admin/operations.md`
status: To Do
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:operations
  - domain:ops-page
  - domain:overrides
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

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
