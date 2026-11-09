---
id: B-109
title: Pointers and citations fixed
status: Done
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T19:29:00Z'
labels:
  - domain:summaries
  - domain:history
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-077, DRAFT-075 and DRAFT-097. (1) _map.md's glossary gets a row for social/reactions.md (« Réagir », « Je bloque », the picker), and the my-account row's Look column reads 'pages, room'. (2) lobby/summaries.md's Tests line « tests/test_spec_032_ac03_ac05_* (AC-5) » says « (032 AC-5) ». (3) gameplay/history.md's edge case « Two erased team-mates read « Ancien joueur » twice » points at displayNickname's tests, not at summaries AC-5 and erasure AC-18, which check the server's answer only. (4) tests/test_hud_final_states.py:20 cites client/menus.md rule 2, not 'rule 9'. (5) web/src/lib/catalogue.ts:95 cites content/cards.md rule 1, not 'spec 004 rule 7'; line 4 of web/src/lib/dateTime.ts is wrapped under 88 characters. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 The five slips are fixed and the gate's traceability is green
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
Specs: specs/_map.md, specs/lobby/summaries.md, specs/gameplay/history.md
Tests: tests/test_hud_final_states.py (docstring citation only)
Gate: uv run python scripts/gate.py --specs summaries,history --browsers chromium
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead: the spec-writer also fixed the same slip on summaries.md's Tests line (046 AC-11, AC-12): kept. (3): no unit test of displayNickname exists; the edge case points at joining.md rule 3 and the page tests of history AC-3 and erasure AC-3; no new test in this tidy task.

Spec-checker APPROVED, two minor notes: history.md's Depends on does not list lobby/joining.md (now cited by the edge case), and the two cited criteria show one erased player each, so « twice » rests on rule 3. Both left for a follow-up draft.

Pull request: https://github.com/Zyniel/nock/pull/184
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
No behaviour change; no criterion added, changed or deleted.
- #1 The five slips are fixed, traceability green: (1) _map.md glossary row for social/reactions.md (« Je bloque », « Réagir », the picker) and the my-account row's Look « pages, room »; (2) summaries.md's Tests line « (032 AC-5) », and the same slip « (046 AC-11, AC-12) » on that line; (3) history.md's edge case of two erased team-mates points at joining.md rule 3 (displayNickname's rule) and the page tests of history AC-3 and erasure AC-3, and its Depends on lists joining.md; (4) tests/test_hud_final_states.py cites client/menus.md rule 2 (menus.md has no rule 9); (5) catalogue.ts cites content/cards rule 1, dateTime.ts's top comment is under 88 characters.
- Spec-checker APPROVED twice (the change, then the review's two history.md fixes). Reviewer: APPROVE in one round.
- Full gate: GATE PASSED (full), 8915 parallel and 147 serial tests.
- Assumed: no unit test of displayNickname exists; the two-player case rests on joining.md rule 3.
<!-- SECTION:FINAL_SUMMARY:END -->
