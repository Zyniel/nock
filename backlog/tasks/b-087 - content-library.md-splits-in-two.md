---
id: B-087
title: content/library.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T20:14:00Z'
labels:
  - domain:library
milestone: m-7
dependencies: []
documentation:
  - specs/content/library.md
  - specs/content/cards.md
priority: medium
ordinal: 75000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. library is 17.0 KB with 25 criteria. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 library.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
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

## Implementation Plan

<!-- SECTION:PLAN:BEGIN -->
The new content/cards.md (domain cards) takes the grid card. Library rules 7 and 12-15 become cards rules 1-5. Library AC-7, 8, 13-16 and 22-24 become cards AC-1..9, with pointers unchanged. Their edge cases move. Library keeps rules 1-6, 8-11, 16 and 17. tests/test_library_progress.py becomes tests/test_cards_progress.py, with ac22-24 renamed ac7-9. library_harness.py keeps its name, and its docstring is updated. Repoint _map.md (row, glossary), _settings.md, lobby/rooms.md and account/erasure.md. No gate change, provided cards' Code names CatalogueItem, catalogue.ts and gridThumb.ts but not CataloguePage.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (cards) over Cut B (grid-data). The four grid-card rules and the progress rule are one topic. No criterion becomes shared, one test file moves, and no gate list changes. library.md ends near 11.9 KB with 16 criteria. B-084 repoints account citations in library.md at the same time; whichever merges second resolves them.
<!-- SECTION:NOTES:END -->
