---
id: B-085
title: social/presence.md splits in two
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T20:05:00Z'
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
- [x] #1 presence.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 presence AC-10 to AC-20 move to social/authorship.md as authorship AC-1 to AC-11, still proven by their 019 and 045 pointers
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
The new social/authorship.md (domain authorship) takes authorship and « Auteurs » mode: presence rules 12-18 as authorship rules 1-7, and presence AC-10..20 as authorship AC-1..11, pointers 019 and 045 unchanged. Presence keeps rules 1-11 and AC-1..9. Repoint _map.md (row, glossary), _settings.md, product.md, results.md, co-op.md, menus.md and foundation.md. gate.py: LetterCell, RoomMenu and RoomPage gain authorship, and RoomMenu loses presence. No test moves.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (authorship) over Cut B (selections). It is the coherent topic (019 and 045 whole), leaves both files near 10 KB (9 and 11 criteria), and needs no test move and no code-comment change. Cut B would leave presence at 14.5 KB with 15 criteria.

Spec-checker APPROVED in round 2. Round 1 asked for the list of shared criteria in _map.md to be completed (043 AC-16, AC-17 and AC-19, 013 AC-5, 036 AC-12), for the chat row to list what chat shares, and for one line to be rewrapped.

Reviewer round 1: APPROVE. Not taken, both optional: adding platform/realtime.md to authorship's Depends on (the template's limit is three files, and it is cited inline), and more code names in the glossary row.

Full gate here (Chromium): static checks, 8,774 parallel and 162 serial tests, all green. Main then brought B-003 and B-083 and merged cleanly. Lint, traceability and shared components passed again. No test or code changed, so Firefox and WebKit are left to CI after the merge.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
social/presence.md splits in two: the new social/authorship.md (domain authorship) takes the letters' authors and « Auteurs » mode (presence rules 12-18 as authorship rules 1-7; presence AC-10..20 as authorship AC-1..11, still proven by their 019 and 045 pointers). presence.md is 9.8 KB with 9 criteria, authorship.md 9.7 KB with 11. _map.md gets a new row and a glossary entry, and its list of shared criteria is completed (043 AC-16, AC-17 and AC-19, 013 AC-5, 036 AC-12). Citations in six specs follow, and gate.py's shared-component map gains authorship. No test or code changed.
<!-- SECTION:FINAL_SUMMARY:END -->
