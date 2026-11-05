---
id: B-091
title: The final status's wording and ISO dates in results
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T22:38:00Z'
labels:
  - domain:hud
  - domain:shell
  - domain:history
milestone: m-8
dependencies: []
documentation:
  - specs/client/hud.md
  - specs/client/shell.md
  - specs/gameplay/history.md
priority: low
ordinal: 79000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-056 and DRAFT-066: what « the selection still moves » covers in a final status, its untested drops, an all-malformed check; results.md says a « Grilles terminées » record needs an ISO date, and whether the calendar is checked. Runs after the hud and results splits.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 The rules say what the code does in each case of the two drafts, each with a criterion and its test
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

## Implementation Notes

<!-- SECTION:NOTES:BEGIN -->
After B-082: the rule that a « Grilles terminées » record needs an ISO date is now in gameplay/history.md.
<!-- SECTION:NOTES:END -->
