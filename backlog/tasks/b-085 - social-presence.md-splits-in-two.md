---
id: B-085
title: social/presence.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T18:07:00Z'
labels:
  - domain:presence
milestone: m-7
dependencies: []
documentation:
  - specs/social/presence.md
priority: medium
ordinal: 73000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. presence is 18.1 KB with 20 criteria. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 presence.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
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
The new social/authorship.md (domain authorship) takes authorship and « Auteurs » mode: presence rules 12-18 as authorship rules 1-7, and presence AC-10..20 as authorship AC-1..11, pointers 019 and 045 unchanged. Presence keeps rules 1-11 and AC-1..9. Repoint _map.md (row, glossary), _settings.md, product.md, results.md, co-op.md, menus.md and foundation.md. gate.py: LetterCell, RoomMenu and RoomPage gain authorship, and RoomMenu loses presence. No test moves.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (authorship) over Cut B (selections). It is the coherent topic (019 and 045 whole), leaves both files near 10 KB (9 and 11 criteria), and needs no test move and no code-comment change. Cut B would leave presence at 14.5 KB with 15 criteria.
<!-- SECTION:NOTES:END -->
