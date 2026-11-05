---
id: B-091
title: The final status's wording and ISO dates in results
status: In Progress
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T23:26:00Z'
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
- [ ] #2 hud AC-30 and AC-31, shell AC-35 and history AC-5: what a final status still lets move, the all-malformed check, and real ISO dates for « Grilles terminées »
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

Lead decisions on the spec-writer's choices:
- hud rule 19: a typed letter or an erase changes nothing and moves nothing in a final status, as the code does.
- shell rule 4: only an empty wrong list counts as a clean check, as the code does.
- history rule 2: the calendar is checked in every engine (2026-02-30, hour 24 and :60 refused). The check goes in the shared isDateTime of dateTime.ts, which makes lobby/summaries.md rule 2's « in every engine » true; this also changes « Mes salons » and the /ops replay reading.
- hud.md ends at 15.3 KB with 15 criteria, a little over the budget m-7 brought it under; it joins DRAFT-079.
- Follow-ups: a calendar example for summaries.md AC-4, and DRAFT-056's pressed « Je bloque » under the disabled look (reactions); both are drafted at m-8's close.

Spec-checker APPROVED in round 2. Round 1 asked to test :60 and +24:00 in history AC-5, to complete rule 2's list, to name ⇄, a clue and the reaction pill in hud rule 19, to add the reveal to AC-31, and to name the grid in shell AC-35. Final hud.md is 15,419 bytes with 15 criteria.

Reviewer: CHANGES REQUESTED in round 1 (the date test missed century leap years and month lengths; AC-31 now shows that the kept requests go after a snapshot), APPROVE in round 2. It checked that broken copies of dateTime.ts all fail the unit test. Not taken: rewrapping one 93-character comment line in dateTime.ts.
<!-- SECTION:NOTES:END -->
