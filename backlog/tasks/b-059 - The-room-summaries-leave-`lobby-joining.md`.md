---
id: B-059
title: The room summaries leave `lobby/joining.md`
status: Done
assignee: []
created_date: '2026-11-02T01:16:00Z'
updated_date: '2026-11-02T13:37:00Z'
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

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 summaries AC-1 (new, was joining AC-17)
- [x] #2 joining AC-17 (deleted, moved to summaries AC-1)
- [x] #3 summaries AC-2 (new, was joining AC-18)
- [x] #4 joining AC-18 (deleted, moved to summaries AC-2)
- [x] #5 summaries AC-3 (new, was joining AC-19)
- [x] #6 joining AC-19 (deleted, moved to summaries AC-3)
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [x] #1 Spec change APPROVED by the spec-checker, or no spec change
- [x] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [x] #3 Tests committed before the code, or a tooling task
- [x] #4 Reviewer APPROVE within two rounds
- [x] #5 Full gate green
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

Lead: all three moved criteria are pointers (032 AC-4 to AC-6, 046 AC-11, AC-12): no domain test moves. product.md: the routes cell of POST /api/rooms/summaries and core flow 7 (« Mes salons ») name summaries; no baseline. results.md:115 and :287 (by number) repointed. Spec-checker: CHANGES REQUESTED round 1 (joining's Code section lost the 032 ac02_ac07 sockets file, which proves AC-7; fixed), APPROVED round 2. By-name citations left: results.md:20, lifetime.md:222-223, library.md:264, hud.md:85-86 (B-064); account.md:18/107/294 (to add to B-064). The spec change was first committed as a wip commit to merge origin/main (B-055's check) before the spec-checker; this commit completes it.

Lead: reviewer APPROVE in round 1 (its suggestion, results.md:20, is on B-064's list via PR #104). Full gate green (8674 parallel, 162 serial).
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
Rules 16 and 17 of lobby/joining.md (the summaries route, « Mes salons ») moved to the new domain lobby/summaries.md as rules 1 and 2, text unchanged. joining.md: 15.4 KB, 18 criteria (rules 1-15 keep their numbers); summaries.md: 4.8 KB, 3 criteria. No behaviour or code change.

Criteria and their tests (joining → summaries):
- summaries AC-1 (was AC-17): ← 032 AC-4 (tests/test_spec_032_ac04_members_and_summaries.py)
- summaries AC-2 (was AC-18): ← 032 AC-5, 046 AC-12
- summaries AC-3 (was AC-19): ← 032 AC-6, 046 AC-11
No domain test moved (all three are pointers).

Also: results.md:115 and :287 cite summaries rule 1 and AC-1; product.md's routes cell for POST /api/rooms/summaries and core flow 7 name summaries (the pitch's question 1, option A); joining rule 9's realtime rule 20 names platform/reconnection.md rule 5; _map.md row, split cell, glossary « summary ». tests/hud_harness.py's stale citation of joining rule 16 now names lobby/lifetime.md rule 6.
Spec-checker: CHANGES REQUESTED in round 1 (joining's Code section lost the 032 ac02_ac07 sockets file, which proves AC-7; fixed), APPROVED in round 2. Reviewer: APPROVE in round 1.
Decisions: product.md core flow 7 also names summaries; by-name citations left for B-064 (results.md:20, lifetime.md:222-223, library.md:264, hud.md:85-86, account.md:18/107/294; added to B-064's notes in #104). The spec change was first committed as a wip commit to merge origin/main before the spec-checker.
Full gate: green (8674 parallel, 162 serial).
<!-- SECTION:FINAL_SUMMARY:END -->
