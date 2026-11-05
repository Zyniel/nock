---
id: B-095
title: Spec 029's leftovers
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
updated_date: '2026-11-05T16:30:00Z'
labels:
  - domain:erasure
  - domain:history
milestone: m-10
dependencies: []
documentation:
  - specs/account/erasure.md
  - specs/gameplay/history.md
priority: low
ordinal: 83000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-015: a history save across an erasure, the delete hook's SQLite write under the registry lock, two erased team-mates shown as one, the summary asked once, peek_room re-reading old logs. Decide each, fix what is cheap.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 Each leftover of DRAFT-015 is fixed with a test or stated in the spec as it is
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
