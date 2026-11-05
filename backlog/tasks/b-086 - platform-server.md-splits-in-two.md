---
id: B-086
title: platform/server.md splits in two
status: To Do
assignee: []
created_date: '2026-11-05T01:53:00Z'
labels:
  - domain:server
milestone: m-7
dependencies: []
documentation:
  - specs/platform/server.md
priority: medium
ordinal: 74000
---

## Description

<!-- SECTION:DESCRIPTION:BEGIN -->
From DRAFT-058. server is 17.3 KB with 23 criteria. Out of scope: any behaviour change. Runs after B-038 (Upkeep), which changes server.py's answers.
<!-- SECTION:DESCRIPTION:END -->

## Acceptance Criteria
<!-- AC:BEGIN -->
- [ ] #1 server.md is under about 15 KB and 20 criteria, the part moved with its criteria and pointers, _map.md updated, the gate's traceability green
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
