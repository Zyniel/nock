---
id: DRAFT-077
title: m-7 leftovers in _map.md and one test docstring
status: Draft
assignee: []
created_date: '2026-11-05T22:33:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-7's close review: (1) _map.md's glossary has no row for social/reactions.md (« Réagir », « Je bloque », the picker); every other new domain of m-7 got one. (2) The my-account row's Look column should read 'pages, room', since my-account.md cites _design/room.md « Room sheets ». (3) tests/test_hud_final_states.py:20 says 'rule 9' for the Aide menu, which is now client/menus.md rule 2. Spec-writer and test-writer, size XS. m-8 did not take it; for m-9. Also wrap line 4 of web/src/lib/dateTime.ts (93 characters, from B-091).
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
