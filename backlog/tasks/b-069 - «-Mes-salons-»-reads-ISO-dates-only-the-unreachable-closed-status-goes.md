---
id: B-069
title: « Mes salons » reads ISO dates only; the unreachable closed status goes
status: To Do
assignee: []
created_date: '2026-11-03T16:02:00Z'
labels:
  - domain:summaries
  - domain:shell
milestone: m-4
dependencies: []
documentation:
  - specs/lobby/summaries.md
  - specs/client/shell.md
priority: low
ordinal: 57000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-057 and DRAFT-020. isTime in web/src/lib/myRooms.ts uses Date.parse alone, which reads some non-ISO strings as dates in V8 only; anchor it to an ISO 8601 pattern first, as B-047 did for ops.ts's isDateTime. The room page's 'closed' status can no longer be reached, yet room.status.closed (« Connexion perdue. ») is a required key of 040 AC-22's test: drop the key, the status and that test entry. Out of scope: DRAFT-020's history entries of 046 AC-23 and 043 AC-31 (archived specs, left as they are).
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 A summary whose last_activity_at is not ISO 8601 reads as no date in every engine
- [ ] #2 The room page has no closed status and no room.status.closed key
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
