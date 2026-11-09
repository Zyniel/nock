---
id: B-111
title: A calendar example for « Mes salons » and /ops dates
status: To Do
assignee: []
created_date: '2026-11-06T03:26:00Z'
updated_date: '2026-11-09T04:50:00Z'
labels:
  - domain:summaries
  - domain:operations
milestone: m-11
dependencies: []
priority: low
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-080. isDateTime (web/src/lib/dateTime.ts) refuses a date-time the calendar lacks in every engine, which changes « Mes salons » (lobby/summaries.md rule 2) and the /ops replay reading; no criterion of those domains shows it. Out of scope: any change to isDateTime.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 lobby/summaries.md AC-4 includes an impossible date such as 2026-02-30, with a test that fails if the check is removed
- [ ] #2 admin/operations.md's date criterion, if one exists, includes the same case with a test; otherwise the task's notes say so
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
