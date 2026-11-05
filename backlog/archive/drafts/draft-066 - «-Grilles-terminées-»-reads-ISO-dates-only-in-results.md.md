---
id: DRAFT-066
title: « Grilles terminées » reads ISO dates only, in results.md
status: Draft
assignee: []
created_date: '2026-11-03T18:47:00Z'
labels:
  - follow-up
  - domain:results
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-069. myRooms' isTime, now anchored to an ISO 8601 date-time with a zone (web/src/lib/dateTime.ts), is shared with web/src/lib/history.ts, so a stored « Grilles terminées » record whose finished_at is not ISO is now dropped. The server only ever stored ISO strings, so no real record is lost, but gameplay/results.md does not say it: state it there with a criterion. Also: the pattern checks the shape, not the calendar (2026-02-31T00:00:00Z or hour 24 pass it and rely on Date.parse, which engines read differently); decide whether to check the calendar too (ops.ts and myRooms share the helper).
<!-- SECTION:DESCRIPTION:END -->

## Definition of Done
<!-- DOD:BEGIN -->
- [ ] #1 Spec change APPROVED by the spec-checker, or no spec change
- [ ] #2 Change of look drawn in docs/design/ and the screens sheet rebuilt, or no change of look
- [ ] #3 Tests committed before the code, or a tooling task
- [ ] #4 Reviewer APPROVE within two rounds
- [ ] #5 Full gate green
- [ ] #6 Pull request open with auto-merge on, or left to the human to merge
<!-- DOD:END -->
