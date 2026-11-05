---
id: B-083
title: lobby/host.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T17:14:00Z'
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
- [ ] #1 host.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
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
The new lobby/creator.md (domain creator) takes members' accounts and the creator: host rules 10-15 as creator rules 1-6, and host AC-9..16 as creator AC-1..8. The creator Edge cases move. Repoint _map.md (new row, glossary), rooms.md, lifetime.md, joining.md, realtime.md, account.md and erasure.md. Rename six test files to tests/test_creator_*.py with renumbered test names. Repoint the code comments in hub.py, store.py and room.py. No gate.py change.
<!-- SECTION:PLAN:END -->

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
Lead decision: Cut A (creator) over Cut B (client/controls). It is the coherent topic, leaves host.md near 11.4 KB with 14 criteria, and needs no gate.py change. tests/host_harness.py keeps its name: it is the shared socket app of eight domains, and renaming it would touch 28 files, many of them also changed by B-003. Its docstring is updated instead.
<!-- SECTION:NOTES:END -->
