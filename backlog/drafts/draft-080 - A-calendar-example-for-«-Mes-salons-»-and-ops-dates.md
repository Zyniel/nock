---
id: DRAFT-080
title: A calendar example for « Mes salons » and /ops dates
status: Draft
assignee: []
created_date: '2026-11-06T03:26:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From m-8's close review and B-091: isDateTime (web/src/lib/dateTime.ts) now refuses a date-time the calendar lacks in every engine, which also changes « Mes salons » (lobby/summaries.md rule 2) and the /ops replay reading. No criterion of those domains shows it. Add an impossible date such as 2026-02-30 to lobby/summaries.md AC-4, and to the ops page's date criterion if one exists, with tests. Spec-writer and test-writer, size S.
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
