---
id: B-076
title: '_map.md: the modes row, « status region », 004 AC-7'
status: Done
assignee: []
created_date: '2026-11-03T16:02:00Z'
updated_date: '2026-11-03T21:14:00Z'
labels:
  - spec
milestone: m-2
dependencies: []
documentation:
  - specs/_map.md
priority: low
ordinal: 64000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-033, DRAFT-048 and the « Spec splits » close. The gameplay/modes.md row and the line under the table say B-002 writes it, but the human dropped B-002: say race and teams have no task. Add « status region » to the glossary and name it in the hud row. The note on criteria cited by more than one domain misses 004 AC-7 (content/ipuz.md and content/library.md). No behaviour.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [x] #1 _map.md names no dropped task, has « status region », and lists 004 AC-7 among shared criteria
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
1. Spec: specs/_map.md (the modes row, « status region » in the glossary and the hud row, 004 AC-7 among shared criteria).
2. Tests: none (no criterion; the gate's traceability check).
3. Gate: uv run python scripts/gate.py --stage tests
<!-- SECTION:PLAN:END -->

## Final Summary

<!-- SECTION:FINAL_SUMMARY:BEGIN -->
specs/_map.md names no dropped task (race and teams: no task writes gameplay/modes.md), has « status region » in the glossary (StatusRegion.svelte, hud rules 17 and 18) and the hud row, and lists 004 AC-7 (ipuz, library) among criteria shared by two domains. No behaviour, no criterion, no test, no code.

Spec-checker: APPROVED. Reviewer: APPROVE. Gate: --stage tests passed (traceability over 33 domain specs; no code changed, so no browser run).
Decisions: the modes row says « not written yet; no task » rather than naming the dropped B-002.
<!-- SECTION:FINAL_SUMMARY:END -->
