---
id: DRAFT-105
title: 'Dates: an impossible time and a leap day shown'
status: Draft
assignee: []
created_date: '2026-11-09T22:22:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From B-111. summaries rule 2 and ops-page rule 6 say a date is on a day and at a time the calendar has, but no criterion shows an impossible time (T25:00:00Z, minute 60) nor an accepted leap day (2028-02-29): removing isDateTime's hour/minute checks, or a daysInMonth that always gives February 28 days, passes every test. Add both examples to summaries AC-4 and ops-page AC-16 with tests.
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
