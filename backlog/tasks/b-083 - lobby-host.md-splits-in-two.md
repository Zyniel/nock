---
id: B-083
title: lobby/host.md splits in two
status: Done
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T18:39:00Z'
labels:
  - domain:host
milestone: m-7
dependencies: []
documentation:
  - specs/lobby/host.md
priority: medium
ordinal: 71000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058 (and DRAFT-051, folded into it). host is 18.5 KB with 22 criteria. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 host.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
- [x] #2 host AC-9 to AC-16 move to lobby/creator.md as creator AC-1 to AC-8, their tests renamed to tests/test_creator_*.py
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
The new lobby/creator.md (domain creator) takes members' accounts and the creator: host rules 10-15 as creator rules 1-6, and host AC-9..16 as creator AC-1..8. The creator Edge cases move. Repoint _map.md (new row, glossary), rooms.md, lifetime.md, joining.md, realtime.md, account.md and erasure.md. Rename six test files to tests/test_creator_*.py with renumbered test names. Repoint the code comments in hub.py, store.py and room.py. No gate.py change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (creator) over Cut B (client/controls). It is the coherent topic, leaves host.md near 11.4 KB with 14 criteria, and needs no gate.py change. tests/host_harness.py keeps its name: it is the shared socket app of eight domains, and renaming it would touch 28 files, many of them also changed by B-003. Its docstring is updated instead.

Spec-checker APPROVED in one round. When B-082 merges first, the merge from main must make creator.md rule 5 cite gameplay/history.md rule 2, take this branch's deletion in host.md, and keep both edits in joining.md's Out of scope.

Reviewer round 1: APPROVE. Not taken, all optional and none a regression: moving the glossary's lobby/creator.md mention to the Code column, adding lobby/rooms.md to creator's Depends on (the template's limit is three files, and rooms.md is cited inline), and re-wrapping one line in rooms.md.

Full gate here (Chromium): static checks, 8,774 parallel and 162 serial tests, all green. Main then brought in B-003 (shared test fixtures) and merged cleanly. The renamed creator tests keep no local fixture copies. Lint, traceability, shared components and the 80 creator and host tests passed again. Firefox and WebKit are left to CI after the merge, since only tests were renamed and comments repointed.
<!-- SECTION:NOTES:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
lobby/host.md splits in two: the new lobby/creator.md (domain creator) takes a member's account and the creator (host rules 10-15 as creator rules 1-6; host AC-9..16 as creator AC-1..8). host.md is 11.1 KB with 14 criteria, creator.md 8.6 KB with 8. Six test files move to tests/test_creator_*.py with renumbered names and unchanged bodies. tests/host_harness.py keeps its name, shared by eight domains. _map.md, citations in seven specs and the code comments of hub.py, room.py and store.py follow. Creator rule 5 cites gameplay/history.md rule 2 after B-082.
<!-- SECTION:FINAL_SUMMARY:END -->
