---
id: B-059
title: The room summaries leave `lobby/joining.md`
status: In Progress
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T11:58:00Z'
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
1. Spec: lobby/joining.md → lobby/summaries.md (new), gameplay/results.md citations, product.md's routes cell, specs/_map.md; joining's realtime rule 20 citation → reconnection rule 5.
2. Tests: the joining tests of AC-17 to AC-19 → tests/test_summaries_*.py, renamed to the new numbers.
3. Quick gate: uv run python scripts/gate.py --specs joining,summaries,results --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Human (2026-11-02, chat, on the pitch's question): A. B-059 updates the one cell of specs/product.md's routes table that names the owner of POST /api/rooms/summaries, from lobby/joining.md to lobby/summaries.md; no behaviour change.

Lead (2026-11-02): started after B-062 (#102, which also changed joining.md rule 3) merged. Spec-writer on Fable at high (new domain). product.md's routes cell for POST /api/rooms/summaries names summaries (the pitch's option A, taken with the pitch's merge). joining.md:102's realtime rule 20 → reconnection rule 5 (B-057's map). Base: origin/main 75c4263.
<!-- SECTION:NOTES:END -->
