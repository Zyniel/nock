---
id: B-080
title: client/hud.md splits in two
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T10:46:00Z'
labels:
  - domain:hud
milestone: m-7
dependencies: []
documentation:
  - specs/client/hud.md
priority: medium
ordinal: 68000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. hud is 22.4 KB with 22 criteria. Move one part, its criteria as they are, to a new domain spec; the Plan agent proposes the cut. Out of scope: any behaviour change.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 hud.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
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
1. Plan agent (Fable, high) proposes the cut; the lead picks.
2. spec-writer moves the part to the new domain spec, _map.md follows; spec-checker.
3. Tests: rename or move the domain tests of moved criteria (after B-003 merges, which edits many test files).
4. No code change; reviewer; full gate; pull request.
<!-- SECTION:PLAN:END -->
