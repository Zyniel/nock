---
id: DRAFT-057
title: myRooms reads its dates with a lenient Date.parse
status: Draft
assignee: []
created_date: '2026-11-02T15:52:00Z'
labels:
  - follow-up
dependencies: []
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
Follow-up of B-047: isTime in web/src/lib/myRooms.ts uses Date.parse alone, which differs between engines (V8 reads some non-ISO strings as dates); B-047 anchored ops.ts's isDateTime to an ISO 8601 pattern first. Same fix here, with a test in the domain that owns « Mes salons » (lobby/summaries).
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
