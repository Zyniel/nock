---
id: B-109
title: Pointers and citations fixed
status: To Do
assignee: []
created_date: '2026-11-05T22:33:00Z'
updated_date: '2026-11-09T04:50:00Z'
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
- [ ] #1 The five slips are fixed and the gate's traceability is green
<!-- AC:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
