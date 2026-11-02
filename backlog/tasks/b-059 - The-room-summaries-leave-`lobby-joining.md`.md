---
id: B-059
title: The room summaries leave `lobby/joining.md`
status: To Do
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T01:16:00Z'
labels:
  - domain:joining
  - domain:summaries
  - domain:results
milestone: m-3
dependencies:
  - B-057
documentation:
  - specs/lobby/joining.md
  - specs/gameplay/results.md
priority: medium
ordinal: 14000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
- Domains: lobby/joining → lobby/summaries (new); gameplay/results (cites rule 16 near its line 113 and joining AC-17 near 282)
- Architecture decision: yes (a new domain), approved by the merge of the « Spec splits » pitch; the spec-writer runs on Fable at high effort.
- Model: spec-writer on Fable (high); test-writer on Sonnet; no implementer (no code changes).
- Problem: `lobby/joining.md` is 17.9 KB with 21 criteria, past the budget of `specs/_map.md`.
- In scope: rules 16 and 17 (the summaries route, « Mes salons ») and AC-17 to AC-19 move to `lobby/summaries.md`, about 4.5 KB and 3 criteria; the pointers of 032 AC-4 to AC-6 and 046 AC-11, AC-12 move. Joining's citation of realtime rule 20 points to `platform/reconnection.md`. `specs/product.md`'s routes table: as the human answers the pitch's question (the lead's pick: its one cell for `POST /api/rooms/summaries` names summaries). A moved criterion takes the next free number of the new file and its tests are renamed and moved to the new domain's test files; a pointer to the v1.1.0 tests moves as it is. The rules that stay keep their numbers (gaps allowed). `specs/_map.md`: the new row, the split « From the v1.1.0 specs » cell, a glossary line next to its related term.
- Out of scope: any change of behaviour or code.
- Screens: none.
- Open questions: none beyond the pitch's.
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
